from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from window import AppWindow
import sys


app = QApplication([])
app.setWindowIcon(QIcon('icon.ico'))
main_window = AppWindow('LiteraTool', (1280, 720), (600, 400), page_names=['Main Page', 'Year Dist.', 'Sankey',
                                                                           'Cat. Links', 'Author-Cat.', 'Co-Authorship'])
with open('themes/theme.qss', 'r') as file:
    app.setStyleSheet(file.read())
sys.exit(app.exec())
