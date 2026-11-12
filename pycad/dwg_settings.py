"""Small DWG reader policy dialog, shared by Help and DWGSETTINGS."""
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QComboBox, QDialogButtonBox
from . import appsettings, dwg_native


def show_settings(parent):
    dialog = QDialog(parent)
    dialog.setWindowTitle('DWG support and settings')
    dialog.resize(580, 290)
    layout = QVBoxLayout(dialog)
    label = QLabel('Choose how DWG drawings open. Auto tries the direct 2D reader first and uses the '
        'DXF compatibility reader when the adapter cannot map the drawing. Direct mode uses LibreDWG JSON '
        'data and in-memory entities; it does not create an intermediate DXF file. Complex objects can '
        'require Compatibility mode. Import notices show the route used. The source DWG is unchanged.')
    label.setWordWrap(True); layout.addWidget(label)
    combo = QComboBox(); combo.setObjectName('dwg_import_mode')
    for key, text in dwg_native.MODES.items(): combo.addItem(text, key)
    combo.setCurrentIndex(combo.findData(dwg_native.requested_mode()))
    layout.addWidget(combo)
    export = QLabel('DWG Save As: bundled GNU LibreDWG writes an R2000-format copy of supported 2D drawing '
        'content on Windows x64 and Ubuntu 24.04+ x64. Saving still uses a DXF bridge. This does not retain '
        'all original DWG objects or modern DWG features. Keep a .pycad master and your original DWG. '
        'macOS/other systems need installed LibreDWG tools, or the separately licensed ODA exporter.')
    export.setWordWrap(True); layout.addWidget(export)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject); layout.addWidget(buttons)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        appsettings.get_settings().setValue('dwg/import_mode', combo.currentData())
        return True
    return False
