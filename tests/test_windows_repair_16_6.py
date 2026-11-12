import base64
import importlib.util
import ntpath
from pathlib import Path
from types import SimpleNamespace


def script(name):
    path = Path(__file__).resolve().parents[1] / 'scripts' / name
    spec = importlib.util.spec_from_file_location(name.replace('.','_'), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_deep_windows_notice_paths_and_unc_keep_unicode(monkeypatch):
    m = script('export_legal_inventory.py')
    monkeypatch.setattr(m, 'os', SimpleNamespace(name='nt', path=ntpath))
    deep = 'C:\\Users\\Jay ü\\' + 'deep\\'*60 + 'LICENSE'
    result = str(m.filesystem_path(deep))
    assert result == '\\\\?\\'+deep
    unc = '\\\\server\\share\\Jay ü\\LICENSE'
    assert str(m.filesystem_path(unc)) == '\\\\?\\UNC\\server\\share\\Jay ü\\LICENSE'
    assert str(m.filesystem_path(result)) == result


def test_source_launcher_repair_classifies_failure_and_uses_shared_verified_script(tmp_path, monkeypatch):
    m = script('repair_windows_runtime.py')
    monkeypatch.setattr(m, 'sys', SimpleNamespace(platform='win32'))
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path / "Jay's (CAD)! ü"))
    log = tmp_path/'startup.log'
    calls = []
    monkeypatch.setattr(m, 'subprocess', SimpleNamespace(run=lambda args,**kw: calls.append(args) or SimpleNamespace(returncode=0)))
    log.write_text('AssertionError: package version')
    assert m.repair(str(log)) == 1 and not calls
    log.write_text('ImportError: DLL load failed while importing QtCore')
    assert m.repair(str(log)) == 0
    args = calls[0]
    decoded = base64.b64decode(args[-1]).decode('utf-16le')
    assert args[:3] == ['powershell.exe', '-NoProfile', '-NonInteractive']
    assert 'Get-AuthenticodeSignature' in decoded and '-Verb RunAs' in decoded
    assert "Jay''s (CAD)! ü" in decoded
    assert decoded.index('Get-AuthenticodeSignature') < decoded.index('Start-Process')
