"""Responsive, cancellable DXF import with no parser work on the UI thread."""

import json
import hashlib
import logging
import sys
import tempfile
from pathlib import Path

from PyQt6.QtCore import QProcess, QProcessEnvironment, QTimer, Qt, QThread
from PyQt6.QtWidgets import QProgressDialog

logger = logging.getLogger(__name__)


class _PreparingDialog(QProgressDialog):
    def reject(self):
        pass  # Display construction cannot safely be terminated mid-QObject.

    def closeEvent(self, event):
        event.ignore()


class _PrepareDisplay(QThread):
    """Build large block caches away from the GUI thread after worker validation."""
    def __init__(self, raw, owner_thread, parent):
        super().__init__(parent)
        self.raw, self.owner_thread = raw, owner_thread
        self.document = self.error = None

    def run(self):
        try:
            from .native_io import _document_from_validated_dict
            self.document = _document_from_validated_dict(json.loads(self.raw))
            # The only QObject in Document is its undo stack. Transfer ownership
            # from this construction thread before exposing it to the GUI.
            self.document.undo_stack.moveToThread(self.owner_thread)
        except Exception as ex:
            self.error = ex


def prepare_display(parent, raw):
    dialog = _PreparingDialog('Preparing drawing display…', None, 0, 0, parent)
    dialog.setWindowTitle('Open drawing')
    dialog.setWindowModality(Qt.WindowModality.WindowModal)
    dialog.setMinimumDuration(0)
    dialog.setAutoClose(False)
    job = _PrepareDisplay(raw, QThread.currentThread(), dialog)
    job.finished.connect(dialog.accept)
    QTimer.singleShot(0, job.start)
    dialog.exec()
    # This phase is deliberately non-cancellable: never destroy a running
    # QThread or leave QObject ownership on a dead thread.
    job.wait()
    error, document = job.error, job.document
    dialog.deleteLater()
    if error is not None:
        raise error
    return document


def load_dxf(parent, source, timeout_ms=300_000, original_source=None, import_note=None):
    from .native_io import _document_from_validated_dict
    from .validation import MAX_FILE_BYTES

    with tempfile.TemporaryDirectory(prefix="pycad-import-") as directory:
        result = Path(directory) / "drawing.pycad"
        error = Path(directory) / "error.json"
        label = "DWG direct reader" if Path(source).suffix.lower() == ".json" else "DXF reader"
        dialog = QProgressDialog("Starting " + label + "…", "Cancel", 0, 0, parent)
        dialog.setWindowTitle("Open drawing · " + Path(original_source or source).name)
        dialog.setWindowModality(Qt.WindowModality.WindowModal)
        dialog.setMinimumDuration(0)
        dialog.setAutoClose(False)
        dialog.setAutoReset(False)
        process = QProcess(dialog)
        process.setWorkingDirectory(str(Path(__file__).resolve().parents[1]))
        env = QProcessEnvironment.systemEnvironment()
        # Private worker preferences and offscreen Qt prevent app locks or a
        # second desktop window. No inherited Python/Qt plugin overrides.
        for key in list(env.keys()):
            if key.upper().startswith(("PYTHON", "QT_PLUGIN", "QT_QPA_PLATFORM_PLUGIN")):
                env.remove(key)
        env.insert("PYCAD_DATA_DIR", directory)
        env.insert("PYTHONNOUSERSITE", "1")
        env.insert("PYTHONUTF8", "1")
        env.insert("QT_QPA_PLATFORM", "offscreen")
        process.setProcessEnvironment(env)
        args = ["--import-worker"] if getattr(sys, "frozen", False) else ["-m", "pycad.import_worker"]
        args += [str(Path(source).absolute()), str(result), str(error)]
        if original_source:
            args += [str(original_source), import_note or ""]
        state = {"cancelled": False, "timeout": False, "start_error": ""}

        def cancel():
            state["cancelled"] = True
            process.kill()
            dialog.reject()

        def timeout():
            state["timeout"] = True
            process.kill()
            dialog.reject()

        def output():
            text = bytes(process.readAllStandardOutput()).decode("utf-8", "replace").strip()
            if text:
                dialog.setLabelText(text.splitlines()[-1][:200])

        def failed(kind):
            if kind == QProcess.ProcessError.FailedToStart:
                state["start_error"] = process.errorString()
                dialog.reject()

        process.readyReadStandardOutput.connect(output)
        process.finished.connect(dialog.accept)
        process.errorOccurred.connect(failed)
        dialog.canceled.connect(cancel)
        timer = QTimer(dialog)
        timer.setSingleShot(True)
        timer.timeout.connect(timeout)
        timer.start(timeout_ms)
        # Start after exec enters its event loop, including immediate startup
        # failures. The modal event loop continues painting and processing Cancel.
        QTimer.singleShot(0, lambda: process.start(sys.executable, args))
        dialog.exec()
        timer.stop()
        if process.state() != QProcess.ProcessState.NotRunning:
            process.kill()
            process.waitForFinished(3000)
        stderr = bytes(process.readAllStandardError()).decode("utf-8", "replace")[-8000:]
        if stderr:
            logger.info("DXF reader: %s", stderr)
        dialog.deleteLater()
        if state["cancelled"]:
            return None
        if state["timeout"]:
            raise ValueError("DXF reading timed out. The original drawing and current workspace are unchanged.")
        if state["start_error"]:
            raise OSError("Could not start the DXF reader: " + state["start_error"])
        if process.exitStatus() != QProcess.ExitStatus.NormalExit or process.exitCode() != 0:
            message = json.loads(error.read_text(encoding="utf-8"))["message"] if error.exists() else "DXF reader stopped unexpectedly. See the application log."
            if error.exists() and json.loads(error.read_text(encoding='utf-8')).get('type') == 'DirectUnsupported':
                from .dwg_native import DirectUnsupported
                raise DirectUnsupported(message)
            raise ValueError(message)
        if not result.exists():
            raise ValueError("DXF reader returned no drawing")
        raw = result.read_bytes()
        descriptor = json.loads(error.read_text(encoding="utf-8"))
        from .drawing_diagnostics import record
        record("import.worker",original_source or source,**descriptor.get("import_metrics",{}))
        if hashlib.sha256(raw).hexdigest() != descriptor.get("sha256"):
            raise ValueError("DXF reader result failed its integrity check")
        # The child ran the full native validator before writing this private
        # result. Avoid repeating polygon validation on the GUI thread.
        document = prepare_display(parent, raw)
        document.filepath = str(original_source or source)
        # source_filepath, source_archive and import warnings came from the
        # worker, not its temporary interchange file.
        return document
