"""Shared branding and an offline viewer for the shipped legal documents."""

from pathlib import Path
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QPixmap, QPalette
from PyQt6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QLabel, QTabWidget,
    QTextBrowser, QVBoxLayout, QWidget,
)

from ._version import __version__
from .identity import DISPLAY_NAME, PUBLISHER_NAME, PUBLISHER_COUNTRY

ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
LEGAL_DOCUMENTS = {
    "License and your rights": "legal/LICENSING.md",
    "GNU GPL version 3": "LICENSE",
    "Third-party notices": "THIRD_PARTY_NOTICES.md",
    "Privacy and AI data": "legal/PRIVACY.md",
    "Use and professional responsibility": "legal/USE_AND_SAFETY.md",
    "Distribution and source": "legal/DISTRIBUTION.md",
    "Brand and trademarks": "legal/TRADEMARKS.md",
    "Research and remaining review": "legal/RESEARCH.md",
    "Publisher and AI development": "legal/PUBLISHER.md",
    "Public release status": "legal/RELEASE_READINESS.md",
}


def app_icon():
    if sys.platform == 'win32' and (ROOT / 'assets/pycad.ico').is_file():
        return QIcon(str(ROOT / 'assets/pycad.ico'))
    icon = ROOT / "assets/pycad-icon.png"
    return QIcon(str(icon)) if icon.is_file() else QIcon.fromTheme("applications-graphics")


def logo_label(width=116, height=36):
    label = QLabel()
    label.setObjectName("pycad_logo")
    label.setAccessibleName("PY.cad logo")
    label.setToolTip("PY.cad")
    label.setFixedSize(width, height)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setStyleSheet("background:#eef6f8;border-radius:4px;padding:0;")
    artwork = ROOT / "assets/pycad-logo.png"
    if not artwork.is_file():
        label.setText(DISPLAY_NAME)
        return label
    label.setPixmap(QPixmap(str(artwork)).scaled(
        width, height, Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    ))
    return label


def legal_text(title):
    """Titles come from this fixed map; arbitrary filesystem paths are not accepted."""
    path = ROOT / LEGAL_DOCUMENTS[title]
    return path.read_text(encoding="utf-8")


class AboutDialog(QDialog):
    def __init__(self, parent=None, legal=False):
        super().__init__(parent)
        self.setWindowTitle("About PY.cad · Licenses and Legal")
        self.setWindowIcon(app_icon())
        self.resize(640, 520)
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        overview = QWidget()
        overview_layout = QVBoxLayout(overview)
        overview_layout.addWidget(logo_label(300, 112), alignment=Qt.AlignmentFlag.AlignHCenter)
        intro = QLabel(
            f"<h2>{DISPLAY_NAME} {__version__}</h2>"
            "<p>2D drafting, architecture, quantities and optional 3D solids.</p>"
            "<p>Free and open-source software · GNU GPL version 3 only.</p>"
            "<p>You may use PY.cad for commercial work. Your drawings remain yours.<br>"
            "Redistributing the software carries license and source obligations.</p>"
            f"<p>Publisher and maintainer: {PUBLISHER_NAME}, {PUBLISHER_COUNTRY}.<br>"
            "Code and artwork generated with ChatGPT; publisher supplied instructions and testing.</p>"
            "<p>Provided without warranty, subject to applicable law.</p>"
        )
        intro.setWordWrap(True)
        overview_layout.addWidget(intro)
        overview_layout.addStretch()
        self.tabs.addTab(overview, "About")
        page = QWidget()
        page_layout = QVBoxLayout(page)
        self.document_picker = QComboBox()
        self.document_picker.addItems(LEGAL_DOCUMENTS)
        self.legal_browser = QTextBrowser()
        self.legal_browser.setOpenExternalLinks(True)
        dark = self.palette().color(QPalette.ColorRole.Base).lightness() < 128
        self.legal_browser.document().setDefaultStyleSheet(
            "a { color:" + ("#72d5f2" if dark else "#00778c") + "; }"
        )
        page_layout.addWidget(self.document_picker)
        page_layout.addWidget(self.legal_browser)
        self.document_picker.currentTextChanged.connect(self.load_document)
        self.tabs.addTab(page, "Licenses and Legal")
        self.load_document(self.document_picker.currentText())
        if legal:
            self.tabs.setCurrentIndex(1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def load_document(self, title):
        try:
            text = legal_text(title)
        except OSError:
            self.legal_browser.setPlainText("This legal document is missing. Restore the complete PY.cad package.")
            return
        if LEGAL_DOCUMENTS[title].endswith(".md"):
            self.legal_browser.setMarkdown(text)
        else:
            self.legal_browser.setPlainText(text)
