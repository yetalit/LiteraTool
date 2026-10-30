from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from window import AppWindow
import sys
import os


if __name__ == "__main__":
    internal_path = '_internal' if '--src' not in sys.argv else ''
    app = QApplication([])
    app.setWindowIcon(QIcon(os.path.join(internal_path, 'icon.ico')))
    main_window = AppWindow('LiteraTool', (1280, 720), (600, 400), internal_path,
                            page_names=['Main Page', 'Year Dist.', 'Sankey',
                                        'Cat. Links', 'Author-Cat.', 'Co-Authorship'])
    with open(os.path.join(internal_path, os.path.join('themes', 'theme.qss')), 'r') as file:
        app.setStyleSheet(file.read())
    sys.exit(app.exec())
