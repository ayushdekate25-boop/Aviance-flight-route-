import sys
import os
import tempfile
from PyQt5.QtWidgets import QApplication
from PyQt5.QtWebEngineWidgets import QWebEngineProfile
from PyQt5.QtCore import Qt
from app import MainWindow


def setup_webengine_cache():
    try:
        cache_dir = os.path.join(tempfile.gettempdir(), "aviance_cache")
        os.makedirs(cache_dir, exist_ok=True)
        profile = QWebEngineProfile.defaultProfile()
        profile.setCachePath(cache_dir)
        profile.setPersistentStoragePath(cache_dir)
        print(f"WebEngine cache set to: {cache_dir}")
    except Exception as e:
        print(f"Cache setup warning: {e}")


def main():
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    app.setApplicationName("Aviance Flight Route Optimizer")
    app.setApplicationVersion("2.0")
    app.setOrganizationName("Aviance")
    setup_webengine_cache()
    try:
        window = MainWindow()
        window.show()
        screen = app.desktop().screenGeometry()
        window.move(
            (screen.width() - window.width()) // 2,
            (screen.height() - window.height()) // 2
        )
        print("✈️ Aviance Flight Route Optimizer started successfully")
        sys.exit(app.exec_())
    except Exception as e:
        print(f"❌ Application startup error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
