#!/usr/bin/env python3
"""
RT-4D Desktop GUI Application
Graphical interface for editing RT-4D radio codeplug files
"""

import os
import sys
from pathlib import Path
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QStyleFactory
from gui import MainWindow
from gui.theme import apply_theme, get_saved_theme


def main():
    """Main entry point"""
    app = QApplication(sys.argv)
    app.setApplicationName("RT-4D Editor")
    app.setOrganizationName("RT4D Tools")

    # Use Fusion style for reliable light/dark palette switching
    app.setStyle(QStyleFactory.create("Fusion"))

    # Apply saved theme
    apply_theme(app, get_saved_theme())

    # Set application icon (works for taskbar, title bar, Alt-Tab)
    # PyInstaller bundles files next to the exe via sys._MEIPASS
    base_path = Path(getattr(sys, '_MEIPASS', Path(__file__).parent))
    icon_path = base_path / '4d.png'
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    # Create and show main window
    window = MainWindow()
    window.show()

    # Run event loop
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
