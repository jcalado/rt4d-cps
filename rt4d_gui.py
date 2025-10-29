#!/usr/bin/env python3
"""
RT-4D Desktop GUI Application
Graphical interface for editing RT-4D radio codeplug files
"""

import sys
from PySide6.QtWidgets import QApplication
from gui import MainWindow


def main():
    """Main entry point"""
    app = QApplication(sys.argv)
    app.setApplicationName("RT-4D Editor")
    app.setOrganizationName("RT4D Tools")

    # Create and show main window
    window = MainWindow()
    window.show()

    # Run event loop
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
