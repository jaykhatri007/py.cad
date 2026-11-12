"""Safe mixed text formatting, wrapping and linked multileader tips."""

from html.parser import HTMLParser
from .document import SetAttrCommand


class _SafeHTML(HTMLParser):
    ALLOWED = {
        "p",
        "br",
        "span",
        "b",
        "strong",
        "i",
        "em",
        "u",
        "html",
        "head",
        "body",
        "meta",
        "style",
        "div",
    }

    def handle_starttag(self, tag, attrs):
        if tag not in self.ALLOWED:
            raise ValueError(
                "Text supports paragraphs, spans, bold, italic and underline"
            )
        for key, value in attrs:
            if key not in (
                "style",
                "class",
                "name",
                "content",
                "http-equiv",
                "type",
            ) or (
                value
                and any(
                    x in value.lower()
                    for x in ("url(", "expression", "javascript:", "@import")
                )
            ):
                raise ValueError("External content is not allowed in formatted text")


def validate_html(value):
    if not isinstance(value, str) or len(value) > 200000:
        raise ValueError("Invalid formatted text")
    if any(
        token in value.lower()
        for token in ("url(", "@import", "javascript:", "<script", "<img", "<object")
    ):
        raise ValueError("External content is not allowed in formatted text")
    parser = _SafeHTML()
    parser.feed(value)
    return value


def draw_text(painter, entity, font, zoom, monochrome=False):
    from PyQt6.QtGui import QTextDocument, QAbstractTextDocumentLayout, QPalette
    from PyQt6.QtCore import QPointF

    doc = QTextDocument()
    doc.setDocumentMargin(0)
    doc.setDefaultFont(font)
    if entity.rich_html:
        doc.setHtml(entity.rich_html)
    else:
        doc.setPlainText(entity.text)
    # Rich HTML uses its own point sizes; normalize all runs to the CAD height.
    cursor = __import__("PyQt6.QtGui", fromlist=["QTextCursor"]).QTextCursor(doc)
    cursor.select(cursor.SelectionType.Document)
    fmt = __import__("PyQt6.QtGui", fromlist=["QTextCharFormat"]).QTextCharFormat()
    fmt.setFontPointSize(font.pixelSize() * 72 / 96)
    cursor.mergeCharFormat(fmt)
    doc.setTextWidth(entity.wrap_width * zoom if entity.wrap_width else -1)
    context = QAbstractTextDocumentLayout.PaintContext()
    context.palette.setColor(QPalette.ColorRole.Text, painter.pen().color())
    if monochrome:
        fmt.setForeground(painter.pen().color())
        cursor.mergeCharFormat(fmt)
    painter.translate(QPointF(0, -entity.height * zoom))
    doc.documentLayout().draw(painter, context)


def edit_rich_text(mw):
    from PyQt6.QtWidgets import (
        QDialog,
        QVBoxLayout,
        QTextEdit,
        QDoubleSpinBox,
        QDialogButtonBox,
        QHBoxLayout,
        QPushButton,
        QColorDialog,
        QLabel,
    )
    from PyQt6.QtGui import QTextCharFormat, QFont
    from .geometry import TextEntity

    items = [
        e
        for e in mw.canvas.selected_entities
        if isinstance(e, TextEntity) and e in mw.document.editable_entities()
    ]
    if len(items) != 1:
        raise ValueError("Select one editable text object")
    e = items[0]
    dialog = QDialog(mw)
    dialog.setWindowTitle("Formatted text")
    dialog.resize(560, 380)
    root = QVBoxLayout(dialog)
    editor = QTextEdit()
    editor.setHtml(e.rich_html) if e.rich_html else editor.setPlainText(e.text)
    bar = QHBoxLayout()
    root.addLayout(bar)

    def format_run(kind):
        fmt = QTextCharFormat()
        current = editor.currentCharFormat()
        if kind == "Bold":
            fmt.setFontWeight(
                QFont.Weight.Normal
                if current.fontWeight() == QFont.Weight.Bold
                else QFont.Weight.Bold
            )
        elif kind == "Italic":
            fmt.setFontItalic(not current.fontItalic())
        elif kind == "Underline":
            fmt.setFontUnderline(not current.fontUnderline())
        else:
            color = QColorDialog.getColor(parent=dialog)
            if not color.isValid():
                return
            fmt.setForeground(color)
        editor.mergeCurrentCharFormat(fmt)

    for label in ("Bold", "Italic", "Underline", "Color"):
        button = QPushButton(label)
        button.clicked.connect(lambda _, k=label: format_run(k))
        bar.addWidget(button)
    root.addWidget(editor)
    row = QHBoxLayout()
    row.addWidget(QLabel("Wrap width (drawing units; 0 = no wrap)"))
    width = QDoubleSpinBox()
    width.setRange(0, 1e9)
    width.setDecimals(3)
    width.setValue(e.wrap_width)
    row.addWidget(width)
    root.addLayout(row)
    buttons = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
    )
    root.addWidget(buttons)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return
    markup = validate_html(editor.toHtml())
    doc = mw.document
    doc.undo_stack.beginMacro("Format text")
    for key, value in (
        ("text", editor.toPlainText()),
        ("rich_html", markup),
        ("wrap_width", width.value()),
    ):
        doc.undo_stack.push(
            SetAttrCommand(doc, e, key, getattr(e, key), value, "Format text")
        )
    doc.undo_stack.endMacro()


def link_leader(mw):
    from PyQt6.QtWidgets import QInputDialog

    items = mw.canvas.selected_entities
    leaders = [e for e in items if e.kind == "MLEADER"]
    sources = [e for e in items if e.kind != "MLEADER"]
    if len(leaders) != 1 or len(sources) != 1:
        raise ValueError(
            "Select one multileader and one source line, point, circle or arc"
        )
    source = sources[0]
    anchors = [k for k in ("p1", "p2", "point", "center") if hasattr(source, k)]
    if not anchors:
        raise ValueError("Source has no supported anchors")
    anchor, ok = QInputDialog.getItem(
        mw, "Link leader", "Source anchor", anchors, editable=False
    )
    if not ok:
        return
    leader = leaders[0]
    links = [None] * len(leader.leaders)
    links[0] = {"source": source.id, "anchor": anchor}
    from .feature_data import edit_table

    edit_table(mw.document, "leader_links", leader.id, links, "Link leader tip")
