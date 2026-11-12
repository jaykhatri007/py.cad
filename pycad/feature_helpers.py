"""Report recoverable dialog errors without escaping a Qt signal callback."""


def safe_action(parent, callback):
    def invoke(*_):
        try:
            return callback()
        except (ValueError, OverflowError, OSError) as ex:
            getattr(parent,"mw",parent).last_command_failure=str(ex)
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.warning(parent, "Drawing tools", str(ex))

    return invoke
