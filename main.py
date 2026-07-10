import sys

from PySide6.QtWidgets import QApplication

from guitar_fretboard.main_window import MainWindow


def configure_application(app: QApplication) -> None:
    app.setApplicationName("Guitar Fretboard Visualizer")
    app.setOrganizationName("Music Learning Tools")
    app.setStyle("Fusion")


def main(argv: list[str] | None = None) -> int:
    app = QApplication.instance() or QApplication(
        argv if argv is not None else sys.argv
    )
    configure_application(app)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
