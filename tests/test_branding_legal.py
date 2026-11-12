"""User-visible branding/legal access and self-contained release contents."""

import importlib.util
from pathlib import Path
import zipfile

import pytest
from PyQt6.QtWidgets import QLabel, QToolButton

from pycad import branding


def test_legal_viewer_loads_all_documents_without_network(qapp):
    dialog = branding.AboutDialog(legal=True)
    assert dialog.tabs.currentIndex() == 1
    assert not dialog.windowIcon().isNull()
    for title in branding.LEGAL_DOCUMENTS:
        dialog.document_picker.setCurrentText(title)
        assert len(dialog.legal_browser.toPlainText()) > 300
        assert "missing" not in dialog.legal_browser.toPlainText()[:80].lower()
    with pytest.raises(KeyError):
        branding.legal_text("../../arbitrary-file")
    dialog.close()


def test_workspace_has_compact_approved_logo(main_window):
    labels = main_window.findChildren(QLabel, "pycad_logo")
    assert not labels
    button = main_window.findChild(QToolButton, "quick_file_button")
    assert button is not None and not button.icon().isNull()
    assert not button.text() and button.accessibleName()
    assert button.width() <= 48 and button.height() <= 48
    assert not main_window.windowIcon().isNull()
    assert any(action.text() == "Licenses and Legal" for action in main_window.findChildren(__import__('PyQt6.QtGui', fromlist=['QAction']).QAction))


def test_native_payload_contains_legal_assets_and_rebuild_source():
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("setup_build", root / "installer/build.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.prepare()
    with zipfile.ZipFile(root / "installer/assets/payload.zip") as archive:
        names = set(archive.namelist())
        for name in ["LICENSE", "COPYRIGHT", "legal/PRIVACY.md", "THIRD_PARTY_NOTICES.md", "assets/pycad-icon.png", "installer/main.go", "installer/branding.go", "installer/build.py", "packaging/export_icons.py", "scripts/export_legal_inventory.py"]:
            assert "PyCAD-v15/" + name in names
        assert not any("installer/assets/payload.zip" in n or "/installer/packages/" in n for n in names)
