"""Drawing units and display formatting. Geometry always retains full precision."""

import math
from fractions import Fraction

UNIT_NAMES = {
    "mm": "Millimeters",
    "cm": "Centimeters",
    "m": "Meters",
    "in": "Inches",
    "ft": "Feet",
    "unitless": "Unitless",
}
UNIT_MM = {"mm": 1.0, "cm": 10.0, "m": 1000.0, "in": 25.4, "ft": 304.8}
DEFAULT_SETTINGS = {
    "length_format": "decimal",
    "length_precision": 3,
    "angle_format": "degrees",
    "angle_precision": 2,
    "suppress_zeros": False,
}


def validate_settings(settings, units=None):
    if not isinstance(settings, dict) or set(settings) != set(DEFAULT_SETTINGS):
        raise ValueError("Missing or unknown unit display settings")
    if units is not None and units not in UNIT_NAMES:
        raise ValueError("Unsupported drawing units")
    if settings["length_format"] not in ("decimal", "scientific", "architectural"):
        raise ValueError("Unsupported length display format")
    if units == "unitless" and settings["length_format"] == "architectural":
        raise ValueError("Feet/inches display requires a physical drawing unit")
    if settings["angle_format"] not in ("degrees", "radians", "gradians"):
        raise ValueError("Unsupported angle display format")
    for key, maximum in (("length_precision", 8), ("angle_precision", 6)):
        if type(settings[key]) is not int or not 0 <= settings[key] <= maximum:
            raise ValueError(f"{key} must be an integer from 0 to {maximum}")
    if type(settings["suppress_zeros"]) is not bool:
        raise ValueError("Suppress trailing zeros must be boolean")


def number(value, precision, suppress=False, scientific=False):
    if not math.isfinite(value):
        return "—"
    if not scientific and round(value, precision) == 0:
        value = 0.0
    text = f"{value:.{precision}{'e' if scientific else 'f'}}"
    if suppress and "." in text:
        mantissa, separator, exponent = text.partition("e")
        text = mantissa.rstrip("0").rstrip(".") + separator + exponent
    return text


def format_length(value, units, settings, suffix=True):
    if not math.isfinite(value):
        return "—"
    precision = settings["length_precision"]
    if settings["length_format"] == "architectural" and units in UNIT_MM:
        denominator = 2**precision
        ticks = round(abs(value) * UNIT_MM[units] / 25.4 * denominator)
        feet, rest = divmod(ticks, 12 * denominator)
        inches, numerator = divmod(rest, denominator)
        fraction = str(Fraction(numerator, denominator)) if numerator else ""
        return f"{'−' if value < 0 and ticks else ''}{feet}′ {inches}{' ' + fraction if fraction else ''}″"
    text = number(
        value,
        precision,
        settings["suppress_zeros"],
        settings["length_format"] == "scientific",
    )
    return text + (" " + ("u" if units == "unitless" else units) if suffix else "")


def format_angle(degrees, settings, normalize=True):
    if not math.isfinite(degrees):
        return "—"
    if normalize:
        degrees %= 360.0
    kind = settings["angle_format"]
    factor, suffix = {
        "degrees": (1.0, "°"),
        "radians": (math.pi / 180, " rad"),
        "gradians": (10 / 9, " gon"),
    }[kind]
    value = degrees * factor
    precision = settings["angle_precision"]
    # Avoid a rounded bearing of 360°/400 gon at the wrap boundary.
    if (
        normalize
        and kind != "radians"
        and round(value, precision) == round(360 * factor, precision)
    ):
        value = 0.0
    return number(value, precision, settings["suppress_zeros"]) + suffix


def change_units(document, unit, settings):
    """One undo step; changes interpretation/display without rescaling geometry."""
    from PyQt6.QtGui import QUndoCommand

    validate_settings(settings, unit)
    settings = dict(settings)
    if document.units == unit and document.unit_settings == settings:
        return

    class UnitsCommand(QUndoCommand):
        def __init__(self):
            super().__init__("Drawing units and display")
            self.before = document.units, dict(document.unit_settings)

        def redo(self):
            document.units, document.unit_settings = unit, dict(settings)

        def undo(self):
            document.units, document.unit_settings = (
                self.before[0],
                dict(self.before[1]),
            )

    document.undo_stack.push(UnitsCommand())


def units_dialog(window):
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import (
        QDialog,
        QVBoxLayout,
        QFormLayout,
        QComboBox,
        QSpinBox,
        QCheckBox,
        QLabel,
        QDialogButtonBox,
        QGroupBox,
        QMessageBox,
    )

    window.cancel_command()
    doc = window.document
    dialog = QDialog(window)
    dialog.setObjectName("drawing_units_manager")
    dialog.setWindowTitle("Drawing Units Manager")
    dialog.resize(510, 440)
    layout = QVBoxLayout(dialog)
    note = QLabel(
        "Choose how to change units: keep coordinate numbers, or convert geometry to preserve its physical size. Paper sizes and lineweights stay in millimeters."
    )
    note.setWordWrap(True)
    layout.addWidget(note)
    form = QFormLayout()
    unit = QComboBox()
    unit.setObjectName("drawing_unit")
    for key, label in UNIT_NAMES.items():
        unit.addItem(f"{label} ({key})", key)
    unit.setCurrentIndex(unit.findData(doc.units))
    length = QComboBox()
    length.setObjectName("length_format")
    for label, key in (
        ("Decimal", "decimal"),
        ("Scientific", "scientific"),
        ("Architectural — feet / inches", "architectural"),
    ):
        length.addItem(label, key)
    length.setCurrentIndex(length.findData(doc.unit_settings["length_format"]))
    length_precision = QComboBox()
    length_precision.setObjectName("length_precision")
    angle = QComboBox()
    angle.setObjectName("angle_format")
    for label, key in (
        ("Decimal degrees", "degrees"),
        ("Radians", "radians"),
        ("Gradians", "gradians"),
    ):
        angle.addItem(label, key)
    angle.setCurrentIndex(angle.findData(doc.unit_settings["angle_format"]))
    angle_precision = QSpinBox()
    angle_precision.setObjectName("angle_precision")
    angle_precision.setRange(0, 6)
    angle_precision.setValue(doc.unit_settings["angle_precision"])
    zeros = QCheckBox("Suppress trailing zeros")
    zeros.setChecked(doc.unit_settings["suppress_zeros"])
    zeros.setObjectName("suppress_zeros")
    live = QCheckBox("Live measurements beside cursor (F12)")
    live.setChecked(window.dynamic_action.isChecked())
    live.setObjectName("live_measurements")
    form.addRow("Drawing units", unit)
    conversion = QCheckBox('Convert geometry to preserve physical size')
    conversion.setObjectName('convert_geometry')
    form.addRow(conversion)
    conversion_note = QLabel()
    conversion_note.setWordWrap(True)
    conversion_note.setObjectName('conversion_preview')
    form.addRow(conversion_note)
    form.addRow("Length display", length)
    form.addRow("Length precision", length_precision)
    form.addRow("Angle display", angle)
    form.addRow("Angle decimals", angle_precision)
    form.addRow(zeros)
    form.addRow(live)
    layout.addLayout(form)
    group = QGroupBox("Sample output — 1250 drawing units / 45 degrees")
    sample_layout = QVBoxLayout(group)
    preview = QLabel()
    preview.setObjectName("unit_preview")
    preview.setTextFormat(Qt.TextFormat.PlainText)
    sample_layout.addWidget(preview)
    layout.addWidget(group)
    hint = QLabel(
        "Angles are measured counterclockwise from +X. Numeric command input still uses drawing units and degrees (for example @100<45). Dimension annotation styles are managed separately with DIMSTYLE."
    )
    hint.setWordWrap(True)
    layout.addWidget(hint)

    def settings():
        return {
            "length_format": length.currentData(),
            "length_precision": length_precision.currentIndex(),
            "angle_format": angle.currentData(),
            "angle_precision": angle_precision.value(),
            "suppress_zeros": zeros.isChecked(),
        }

    def update(*_):
        can_convert = doc.units in UNIT_MM and unit.currentData() in UNIT_MM and doc.units != unit.currentData()
        conversion.setEnabled(can_convert)
        if not can_convert:
            conversion.setChecked(False)
        if can_convert and conversion.isChecked():
            factor = UNIT_MM[doc.units]/UNIT_MM[unit.currentData()]
            conversion_note.setText(f'1000 {doc.units} becomes {1000*factor:.9g} {unit.currentData()} (×{factor:.9g}). Geometry, constraints, annotation sizes and references convert together. One Undo restores the drawing.')
        elif can_convert:
            conversion_note.setText('Coordinate numbers stay unchanged. This reinterprets the drawing size; enable conversion to keep its physical size.')
        elif doc.units == unit.currentData():
            conversion_note.setText('The drawing unit is unchanged. Display settings do not round stored coordinates.')
        else:
            conversion_note.setText('Unitless geometry cannot be physically converted. Assign its source unit first.')
        length.model().item(2).setEnabled(unit.currentData() != "unitless")
        if unit.currentData() == "unitless" and length.currentData() == "architectural":
            length.setCurrentIndex(0)
        precision = max(0, length_precision.currentIndex())
        length_precision.blockSignals(True)
        length_precision.clear()
        length_precision.addItems(
            [
                ("Whole inch" if p == 0 else f"1/{2**p} inch")
                if length.currentData() == "architectural"
                else f"{p} decimal places"
                for p in range(9)
            ]
        )
        length_precision.setCurrentIndex(precision)
        length_precision.blockSignals(False)
        s = settings()
        preview.setText(
            format_length(1250, unit.currentData(), s)
            + "     /     "
            + format_angle(45, s)
        )

    update()
    length_precision.setCurrentIndex(doc.unit_settings["length_precision"])
    for combo in (unit, length, length_precision, angle):
        combo.currentIndexChanged.connect(update)
    angle_precision.valueChanged.connect(update)
    zeros.toggled.connect(update)
    conversion.toggled.connect(update)
    update()
    buttons = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
    )
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        try:
            if conversion.isChecked():
                from .unit_conversion import convert_units
                factor = convert_units(doc, unit.currentData(), settings())
                window.canvas.pan_offset *= factor
                window.canvas.zoom /= factor
                window.command_history.appendPlainText(f'Converted drawing units ×{factor:.9g}. Physical size preserved. Paper dimensions and lineweights unchanged; stored standards and embedded original DXF are unchanged. Solver tolerance stays within its supported range.')
            else:
                change_units(doc, unit.currentData(), settings())
        except ValueError as ex:
            QMessageBox.warning(window, 'Unit conversion', str(ex))
        if live.isChecked() != window.dynamic_action.isChecked():
            window.dynamic_action.trigger()
        window.refresh_document_ui()
    window.focus_active_viewport()
    dialog.setParent(None)
    dialog.deleteLater()
