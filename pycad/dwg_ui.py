"""DWG conversion is a direct GUI child so Cancel cannot orphan a converter."""

from pathlib import Path
import tempfile
import time

from PyQt6.QtCore import QProcess, QTimer, Qt
from PyQt6.QtWidgets import QProgressDialog

from . import dwg_support
from .validation import MAX_FILE_BYTES


def load_dwg(parent, source, timeout_ms=300_000, mode=None):
    from .import_cache import load
    from .dwg_native import requested_mode
    selected=mode or requested_mode()
    return load(parent,source,selected,lambda:_uncached_dwg(parent,source,timeout_ms,selected))


def _uncached_dwg(parent, source, timeout_ms=300_000, mode=None):
    from . import dwg_native
    from .dxf_io import DWGSupportError
    selected = mode or dwg_native.requested_mode()
    if selected not in dwg_native.MODES:
        raise ValueError('Unknown DWG import mode')
    fallback = ''
    if selected != 'compatibility':
        try:
            executable = dwg_native.tool_path('dwgread')
            return _load(parent, source, timeout_ms, executable, direct=True)
        except (DWGSupportError, dwg_native.DirectUnsupported) as ex:
            if selected == 'direct': raise
            fallback = 'Direct DWG reader used compatibility fallback: ' + str(ex)
    return _load(parent, source, timeout_ms, dwg_support.reader_path(), fallback=fallback)


def _load(parent, source, timeout_ms, executable, direct=False, fallback=''):
    from .import_ui import load_dxf
    from .dwg_native import direct_arguments
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="pycad-dwg-") as directory:
        from .import_staging import stage
        if not stage(parent,source,directory,timeout_ms):return None
        dialog = QProgressDialog("Reading DWG directly with LibreDWG…" if direct else "Opening DWG in compatibility mode…", "Cancel", 0, 0, parent)
        dialog.setWindowTitle("Open DWG · " + Path(source).name)
        dialog.setWindowModality(Qt.WindowModality.WindowModal)
        dialog.setMinimumDuration(0)
        dialog.setAutoClose(False)
        dialog.setAutoReset(False)
        process = QProcess(dialog)
        process.setWorkingDirectory(directory)
        state = {"cancelled": False, "timeout": False, "limit": False, "error": "", "log": ""}

        def stop(reason):
            state[reason] = True
            process.kill()
            dialog.reject()

        def failed(kind):
            if kind == QProcess.ProcessError.FailedToStart:
                state["error"] = process.errorString()
                dialog.reject()

        def drain():
            raw = bytes(process.readAllStandardError()) + bytes(process.readAllStandardOutput())
            state["log"] = (state["log"] + raw.decode("utf-8", "replace"))[-8000:]

        process.readyReadStandardError.connect(drain)
        process.readyReadStandardOutput.connect(drain)
        process.finished.connect(dialog.accept)
        process.errorOccurred.connect(failed)
        dialog.canceled.connect(lambda: stop("cancelled"))
        timer = QTimer(dialog)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: stop("timeout"))
        timer.start(max(1, min(timeout_ms, 120_000)))
        QTimer.singleShot(0, lambda: process.start(str(executable), (direct_arguments() if direct else dwg_support.conversion_arguments())))
        dialog.exec()
        timer.stop()
        if process.state() != QProcess.ProcessState.NotRunning:
            process.kill()
            process.waitForFinished(3000)
        drain()
        normal = process.exitStatus() == QProcess.ExitStatus.NormalExit
        code = process.exitCode()
        dialog.deleteLater()
        if state["cancelled"]:
            return None
        if state["timeout"]:
            raise ValueError("DWG conversion timed out; current drawing unchanged")
        if state["error"]:
            raise ValueError("Could not start the LibreDWG reader: " + state["error"])
        if not normal:
            raise ValueError("The DWG reader stopped unexpectedly; current drawing unchanged")
        if direct:
            if code != 0:
                raise ValueError('DWG direct reader failed (exit ' + str(code) + '); current drawing unchanged.\n' + state['log'][-4000:])
            converted = Path(directory) / 'drawing.json'
            if not converted.is_file() or not converted.stat().st_size:
                raise ValueError('DWG direct reader returned no drawing')
        else:
            converted = dwg_support.checked_output(directory, code, state["log"])
        remaining = timeout_ms - int((time.monotonic() - started) * 1000)
        if remaining <= 0:
            raise ValueError("DWG opening timed out; current drawing unchanged")
        return load_dxf(parent, str(converted), timeout_ms=remaining, original_source=str(Path(source).absolute()),
                        import_note=("" if direct else dwg_support.NOTE + ("\n" + fallback if fallback else "")) + ("\nReader diagnostics: " + state["log"][-2000:] if state["log"].strip() else ""))
