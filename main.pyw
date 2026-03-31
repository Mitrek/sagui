import sys
import time
import logging
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QSplashScreen, QLabel
from PyQt6.QtGui import QPixmap, QColor, QIcon
from PyQt6.QtCore import Qt, QTimer
from app import MainWindow, STYLE


def setup_logging():
    log_path = Path(__file__).parent / "error.log"
    logging.basicConfig(
        filename=log_path,
        level=logging.ERROR,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


class _DraggableSplash(QSplashScreen):
    def mousePressEvent(self, event):
        self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if hasattr(self, "_drag_pos"):
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None


def main():
    setup_logging()
    try:
        app = QApplication(sys.argv)
        app.setStyle("Fusion")
        app.setStyleSheet(STYLE)
        app.setWindowIcon(QIcon(str(Path(__file__).parent / "resources" / "logo.ico")))

        # Splash screen
        logo_path = Path(__file__).parent / "resources" / "Logo.png"
        pixmap = QPixmap(str(logo_path)).scaled(
            400, 400,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        splash = QSplashScreen(pixmap)
        splash.setStyleSheet("background-color: #FFFFFF;")

        # Center logo on a white 600×600 canvas
        canvas = QPixmap(600, 600)
        canvas.fill(QColor("#FFFFFF"))
        from PyQt6.QtGui import QPainter
        painter = QPainter(canvas)
        x = (600 - pixmap.width()) // 2
        y = (600 - pixmap.height()) // 2
        painter.drawPixmap(x, y, pixmap)
        painter.end()

        splash = _DraggableSplash(canvas, Qt.WindowType.WindowStaysOnTopHint)
        splash.setStyleSheet("background-color: #FFFFFF;")
        splash.show()
        app.processEvents()

        t_start = time.monotonic()
        window = MainWindow()
        elapsed_ms = int((time.monotonic() - t_start) * 1000)
        remaining_ms = max(0, 2000 - elapsed_ms)

        QTimer.singleShot(remaining_ms, lambda: (splash.finish(window), window.show()))

        sys.exit(app.exec())
    except Exception:
        logging.exception("Unhandled exception")
        raise


if __name__ == "__main__":
    main()
