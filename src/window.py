from PyQt6.QtWidgets import QMainWindow, QWidget, QPushButton, QHBoxLayout, QVBoxLayout, QFileDialog, QStackedWidget,\
    QMessageBox, QLabel, QComboBox, QMenu, QDialog, QListWidget, QSpinBox
from PyQt6.QtGui import QAction, QDragEnterEvent, QDropEvent, QPainter, QBrush, QColor, QPixmap
from PyQt6.QtCore import Qt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib import cm
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.patches import Polygon, Circle, Rectangle
from openpyxl import Workbook
import openpyxl.styles as xlstyles
from openpyxl.utils import get_column_letter
from sankeyflow import Sankey
from dataManager import manager
import numpy as np
import os
import pathlib
from functools import partial
from collections import Counter


def bezier_curve(p1, p2, p3, t):
    return (1 - t) ** 2 * np.array(p1) + 2 * (1 - t) * t * np.array(p2) + t ** 2 * np.array(p3)

def draw_bezier_curve(p1, p2, p3, ax):
    t = np.linspace(0, 1, 100)
    curve_points = [bezier_curve(p1, p2, p3, tt) for tt in t]
    curve_points = np.array(curve_points)
    ax.plot(curve_points[:, 0], curve_points[:, 1], color='black', lw=1, zorder=1)

def update_texts_size(ax, texts):
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()

    # Current zoom scale
    scale = max(abs(x1 - x0), abs(y1 - y0))

    fontsize = 7 if scale > 22 else 9 if scale > 19 else 11

    for t in texts:
        t.set_fontsize(fontsize)

    ax.figure.canvas.draw_idle()
    
def compute_jaccard(cat_names, links, years, year_filter='All'):
    idx = {c: i for i, c in enumerate(cat_names)}
    n = len(cat_names)
    co = np.zeros((n, n))
    for link, y in zip(links, years):
        if year_filter != 'All' and str(y) != str(year_filter):
            continue
        ids = [idx[c] for c in set(link)]
        for a in ids:
            for b in ids:
                co[a, b] += 1          # diagonal = category frequency
    freq = np.diag(co)
    union = freq[:, None] + freq[None, :] - co
    return np.divide(co, union, out=np.zeros_like(co), where=union > 0)

class MplCanvas(FigureCanvasQTAgg):
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        self.fig = plt.Figure(figsize=(width, height), dpi=dpi)
        self.axes = self.fig.add_subplot(111)
        super().__init__(self.fig)

class DropWidget(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.setAcceptDrops(True)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#f0f0f0"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor("gray")))

        dot_size = 2
        spacing = 15
        for y in range(0, self.height(), spacing):
            for x in range(0, self.width(), spacing):
                painter.drawEllipse(x, y, dot_size, dot_size)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if urls:
            self.window.on_open(urls[0].toLocalFile())

class CheckableComboBox(QComboBox):
    def __init__(self, title):
        super().__init__()
        # Set editable to False to make it a regular drop-down
        self.setEditable(False)
        # Create the menu that will be used for the drop-down
        self.menu = QMenu(self)
        self.title = title
        self.set_items([])

    def set_items(self, items):
        self.clear()
        self.menu.clear()
        self.addItem(self.title)
        self.addItems(items)
        # Add checkable actions to the menu
        for item in items:
            action = QAction(item, self)
            action.setCheckable(True)
            action.setChecked(True)
            self.menu.addAction(action)

    def mousePressEvent(self, event):
        # Show the custom QMenu when the combo box is clicked
        self.menu.exec(self.mapToGlobal(self.rect().bottomLeft()))

    def get_checked_items(self):
        checked_items = []
        for action in self.menu.actions():
            if action.isChecked():
                checked_items.append(action.text())
        return checked_items

class YearIntervalDialog(QDialog):
    def __init__(self, min_year, max_year, current_bins, btn_ss, parent=None):
        super().__init__(parent)

        self.min_year = min_year
        self.max_year = max_year

        self.setWindowTitle("Set Year Groups")
        self.setModal(True)
        self.setFixedWidth(400)

        layout = QVBoxLayout(self)

        label = QLabel(
            "Add the starting year of each group.\n"
            "The final group will end at the maximum year."
        )
        layout.addWidget(label)

        self.year_list = QListWidget()
        self.year_list.setStyleSheet("""
        QListWidget {
            font-size: 12pt;
        }
        """)
        layout.addWidget(self.year_list)

        input_layout = QHBoxLayout()

        self.year_input = QSpinBox()
        self.year_input.setRange(min_year, max_year)
        self.year_input.setValue(min_year)

        add_btn = QPushButton("Add Start Year")
        add_btn.setStyleSheet(btn_ss)
        add_btn.clicked.connect(self.add_year)

        input_layout.addWidget(self.year_input)
        input_layout.addWidget(add_btn)

        layout.addLayout(input_layout)

        remove_btn = QPushButton("Remove Selected")
        remove_btn.setStyleSheet(btn_ss)
        remove_btn.clicked.connect(self.remove_year)
        layout.addWidget(remove_btn)

        buttons_layout = QHBoxLayout()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet("""
        QPushButton {
            background-color: #dc3545;
            font-size: 16px;
        }
        QPushButton:hover {
            background-color: #c82333;
            font-size: 16px;
        }
        QPushButton:pressed {
            background-color: #bd2130;
            font-size: 16px;
        }
        """)
        cancel_btn.clicked.connect(self.reject)

        apply_btn = QPushButton("Apply")
        apply_btn.setStyleSheet("""
        QPushButton {
            background-color: #28a745;
            font-size: 16px;
        }
        QPushButton:hover {
            background-color: #218838;
            font-size: 16px;
        }
        QPushButton:pressed {
            background-color: #1e7e34;
            font-size: 16px;
        }
        """)
        apply_btn.clicked.connect(self.apply)

        buttons_layout.addWidget(cancel_btn)
        buttons_layout.addWidget(apply_btn)

        layout.addLayout(buttons_layout)

        # Load current bins
        for year in current_bins[:-1]:
            self.year_list.addItem(str(year))

    def add_year(self):
        year = self.year_input.value()

        # Don't allow duplicates
        existing = [
            int(self.year_list.item(i).text())
            for i in range(self.year_list.count())
        ]

        if year in existing:
            return

        self.year_list.addItem(str(year))
        self.sort_years()

    def remove_year(self):
        row = self.year_list.currentRow()

        if row >= 0:
            self.year_list.takeItem(row)

    def sort_years(self):
        years = sorted(
            int(self.year_list.item(i).text())
            for i in range(self.year_list.count())
        )

        self.year_list.clear()

        for year in years:
            self.year_list.addItem(str(year))

    def apply(self):
        if self.year_list.count() == 0:
            QMessageBox.critical(
                self,
                "No Year Groups",
                "Please add at least one starting year."
            )
            return

        self.start_years = sorted(
            int(self.year_list.item(i).text())
            for i in range(self.year_list.count())
        )

        # Make sure the first group starts at/before min_year
        if self.start_years[0] > self.min_year:
            QMessageBox.critical(
                self,
                "Invalid Groups",
                f"The first group must start at {self.min_year}"
            )
            return

        self.accept()

class AppWindow(QMainWindow):
    def __init__(self, title, def_size, min_size, page_names):
        super().__init__()
        self.setWindowTitle(title)
        self.resize(def_size[0], def_size[1])
        self.setMinimumSize(min_size[0], min_size[1])
        self.canvas = [MplCanvas(self) for _ in range(len(page_names)-1)]

        self.DM = manager()
        self.stack_widget = QStackedWidget(self)
        toolbars = [NavigationToolbar2QT(self.canvas[i], self) for i in range(len(self.canvas))]
        for toolbar in toolbars:
            actions = toolbar.actions()
            for action in actions:
                toolbar.removeAction(action)
            for i in range(2, len(actions)+2):
                if i < 9:
                    toolbar.addAction(actions[-i])
                elif i == 10:
                    toolbar.addAction(actions[1])
                elif i == 11:
                    toolbar.addAction(actions[2])
                else:
                    toolbar.addAction(actions[-1])

        with open(os.path.join('_internal', 'themes', 'btn.qss'), 'r') as file:
            btn_ss = file.read()
        with open(os.path.join('_internal', 'themes', 'btn_active.qss'), 'r') as file:
            btn_active_ss = file.read()

        # Main Page
        page_widget = DropWidget(window=self)
        page_layout = QVBoxLayout()

        title_label = QLabel(self)
        title_label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        title_label.setStyleSheet("background: transparent;")

        pixmap = QPixmap(os.path.join('_internal', 'title.png'))
        pixmap = pixmap.scaled(
            362, 120,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

        title_label.setPixmap(pixmap)
        page_layout.addWidget(title_label)
        page_layout.setAlignment(title_label, Qt.AlignmentFlag.AlignCenter)

        drag_label = QLabel('Load the file or Drag and Drop it on this page', self)
        drag_label.setStyleSheet("font: 16pt; font-weight: bold;")
        page_layout.addWidget(drag_label)
        page_layout.setAlignment(drag_label, Qt.AlignmentFlag.AlignCenter)

        open_btn = QPushButton("LOAD", self)
        open_btn.setFixedHeight(50)
        open_btn.setFixedWidth(220)
        open_btn.setStyleSheet(btn_active_ss + "QPushButton {font: 20pt; font-weight: bold;}")
        open_btn.clicked.connect(self.on_open)
        page_layout.addWidget(open_btn)
        page_layout.setAlignment(open_btn, Qt.AlignmentFlag.AlignCenter)
        # Dataset Labels
        self.label_widget = QWidget()
        self.label_widget.setFixedWidth(200)
        label_layout = QVBoxLayout()
        label = QLabel('Loaded Dataset:', self)
        self.label_widget.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
            color: #2E2E2E;
            background-color: #E0E0E0;
            border-radius: 10px;
            padding: 1px;
            border-radius: 10px;
        """)
        label_layout.addWidget(label)
        label_layout.setAlignment(label, Qt.AlignmentFlag.AlignCenter)
        self.data_label = QLabel('None', self)
        self.data_label.setStyleSheet("""
            font-size: 18px;
            font-weight: bold;
            color: #2e7d32;
            background-color: #a5d6a7;
            padding: 8px;
            border-radius: 10px;
        """)
        label_layout.addWidget(self.data_label)
        label_layout.setAlignment(self.data_label, Qt.AlignmentFlag.AlignCenter)
        self.label_widget.setLayout(label_layout)
        page_layout.addWidget(self.label_widget)
        page_layout.setAlignment(self.label_widget, Qt.AlignmentFlag.AlignCenter)

        interval_btn = QPushButton("YEAR GROUPS", self)
        interval_btn.setFixedHeight(40)
        interval_btn.setFixedWidth(220)
        interval_btn.setStyleSheet(btn_ss + "QPushButton {font: 15pt; font-weight: bold;}")
        interval_btn.clicked.connect(partial(self.on_year_interval_dialog, btn_ss))
        page_layout.addWidget(interval_btn)
        page_layout.setAlignment(interval_btn, Qt.AlignmentFlag.AlignCenter)

        plot_btn = QPushButton("PLOTS", self)
        plot_btn.setFixedHeight(60)
        plot_btn.setFixedWidth(220)
        plot_btn.setStyleSheet(btn_ss + "QPushButton {font: 22pt; font-weight: bold;}")
        plot_btn.clicked.connect(partial(self.activate_page, 1))
        page_layout.addWidget(plot_btn)
        page_layout.setAlignment(plot_btn, Qt.AlignmentFlag.AlignCenter)

        table_btn = QPushButton("Summary Table", self)
        table_btn.setFixedHeight(50)
        table_btn.setFixedWidth(220)
        table_btn.setStyleSheet(btn_ss + "QPushButton {font: 18pt; font-weight: bold;}")
        table_btn.clicked.connect(self.on_table)
        page_layout.addWidget(table_btn)
        page_layout.setAlignment(table_btn, Qt.AlignmentFlag.AlignCenter)

        label = QLabel('© 2026 ... and .... | Licensed under GNU GPL v3.0', self)
        label.setStyleSheet("font: 10pt;")
        page_layout.addWidget(label)
        page_layout.setAlignment(label, Qt.AlignmentFlag.AlignCenter)

        page_widget.setLayout(page_layout)
        self.stack_widget.addWidget(page_widget)
        # Lines Page
        page_widget = QWidget()
        page_layout = QVBoxLayout()
        analyze_btn = self.setUpAnalyzeBtn(btn_ss)

        panel_widget = QWidget()
        panel_widget.setFixedHeight(55)
        panel_layout = QHBoxLayout()
        self.lines_cb = CheckableComboBox(title='Filter Categories')
        #self.lines_cb.setStyleSheet("background-color: honeydew;")
        panel_layout.addWidget(self.lines_cb)
        panel_widget.setLayout(panel_layout)

        page_layout.addWidget(self.setUpMenuBtns(len(toolbars) + 1, toolbars[0], page_names, 1, btn_ss, btn_active_ss))

        page_layout.addWidget(self.canvas[0])
        page_layout.addWidget(panel_widget)
        page_layout.addWidget(analyze_btn)
        page_widget.setLayout(page_layout)
        self.stack_widget.addWidget(page_widget)
        # Sankey Page
        page_widget = QWidget()
        page_layout = QVBoxLayout()
        analyze_btn = self.setUpAnalyzeBtn(btn_ss)

        page_layout.addWidget(self.setUpMenuBtns(len(toolbars) + 1, toolbars[1], page_names, 2, btn_ss, btn_active_ss))

        page_layout.addWidget(self.canvas[1])
        page_layout.addWidget(analyze_btn)
        page_widget.setLayout(page_layout)
        self.stack_widget.addWidget(page_widget)
        # Poly Page
        page_widget = QWidget()
        page_layout = QVBoxLayout()
        analyze_btn = self.setUpAnalyzeBtn(btn_ss)

        panel_widget = QWidget()
        panel_widget.setFixedHeight(55)
        panel_layout = QHBoxLayout()
        self.poly_cb = CheckableComboBox(title='Filter Categories')
        #self.poly_cb.setStyleSheet("background-color: honeydew;")
        panel_layout.addWidget(self.poly_cb)
        y_label = QLabel('Years Interval:', self)
        y_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        panel_layout.addWidget(y_label)
        self.poly_yf = QComboBox(self)
        #self.poly_yf.setStyleSheet("background-color: honeydew;")
        panel_layout.addWidget(self.poly_yf)
        
        self.poly_matrix_btn = QPushButton('Jaccard Matrix', self)
        self.poly_matrix_btn.setStyleSheet(btn_ss)
        self.poly_matrix_btn.clicked.connect(self.show_jaccard_matrix)
        panel_layout.addWidget(self.poly_matrix_btn)

        panel_widget.setLayout(panel_layout)

        page_layout.addWidget(self.setUpMenuBtns(len(toolbars) + 1, toolbars[2], page_names, 3, btn_ss, btn_active_ss))

        page_layout.addWidget(self.canvas[2])
        page_layout.addWidget(panel_widget)
        page_layout.addWidget(analyze_btn)
        page_widget.setLayout(page_layout)
        self.stack_widget.addWidget(page_widget)
        # Authors1 Page
        page_widget = QWidget()
        page_layout = QVBoxLayout()
        analyze_btn = self.setUpAnalyzeBtn(btn_ss)

        panel_widget = QWidget()
        panel_widget.setFixedHeight(55)
        panel_layout = QHBoxLayout()
        label = QLabel('Years Interval:', self)
        panel_layout.addWidget(label)
        self.author1_yf = QComboBox(self)
        #self.author1_yf.setStyleSheet("background-color: honeydew;")
        panel_layout.addWidget(self.author1_yf)
        panel_widget.setLayout(panel_layout)

        page_layout.addWidget(self.setUpMenuBtns(len(toolbars) + 1, toolbars[3], page_names, 4, btn_ss, btn_active_ss))

        page_layout.addWidget(self.canvas[3])
        page_layout.addWidget(panel_widget)
        page_layout.addWidget(analyze_btn)
        page_widget.setLayout(page_layout)
        self.stack_widget.addWidget(page_widget)

        # Authors2 Page
        page_widget = QWidget()
        page_layout = QVBoxLayout()
        analyze_btn = self.setUpAnalyzeBtn(btn_ss)

        panel_widget = QWidget()
        panel_widget.setFixedHeight(55)
        panel_layout = QHBoxLayout()
        label = QLabel('Years Interval:', self)
        panel_layout.addWidget(label)
        self.author2_yf = QComboBox(self)
        #self.author2_yf.setStyleSheet("background-color: honeydew;")
        panel_layout.addWidget(self.author2_yf)
        panel_widget.setLayout(panel_layout)

        page_layout.addWidget(self.setUpMenuBtns(len(toolbars) + 1, toolbars[4], page_names, 5, btn_ss, btn_active_ss))

        page_layout.addWidget(self.canvas[4])
        page_layout.addWidget(panel_widget)
        page_layout.addWidget(analyze_btn)
        page_widget.setLayout(page_layout)
        self.stack_widget.addWidget(page_widget)

        self.setCentralWidget(self.stack_widget)
        self.show()

    def setUpAnalyzeBtn(self, btn_ss):
        analyze_btn = QPushButton("Analyze", self)
        analyze_btn.setStyleSheet(btn_ss)
        analyze_btn.setFixedHeight(30)
        analyze_btn.clicked.connect(self.on_analyze)
        return analyze_btn

    def setUpMenuBtns(self, size, toolbar, page_names, index, qss, active_qss):
        toolbar_layout = QHBoxLayout()
        for i in range(size):
            menu_btn = QPushButton(page_names[i], self)
            menu_btn.setFixedWidth(112)
            if i == index:
                menu_btn.setStyleSheet(active_qss)
            else:
                menu_btn.setStyleSheet(qss)
            menu_btn.clicked.connect(partial(self.activate_page, i))
            toolbar_layout.addWidget(menu_btn)
        toolbar_layout.addWidget(toolbar)
        toolbar_widget = QWidget()
        toolbar_widget.setLayout(toolbar_layout)
        toolbar_widget.setFixedHeight(55)
        return toolbar_widget

    def activate_page(self, index):
        self.stack_widget.setCurrentIndex(index)

    def on_open(self, path=None):
        if not path:
            path = QFileDialog.getOpenFileName(self, "Select a dataset", "", "CSV and Excel Files (*.csv *.xlsx)")[0]
        if path:
            result = self.DM.open(path)
            if result == '':
                self.file_name = os.path.basename(path)
                self.directory = path.replace(self.file_name, '')
                msg = self.file_name + ' from ' + self.directory
                if len(msg) > 15:
                    self.label_widget.setFixedWidth(200 + (len(msg) - 15) * 8)
                self.data_label.setText(msg)
                self.lines_cb.set_items(self.DM.categories)
                self.poly_cb.set_items(self.DM.categories)
                self.poly_yf.clear()
                self.author1_yf.clear()
                self.author2_yf.clear()
                self.poly_yf.addItem('All')
                year_groups = sorted(self.DM.year_groups.unique(), key=lambda x: int(x.split('-')[0]))
                self.poly_yf.addItems(year_groups)
                self.author1_yf.addItems(year_groups)
                self.author2_yf.addItems(year_groups)
                dlg = QMessageBox(self)
                dlg.setWindowTitle("Success!")
                dlg.setIcon(QMessageBox.Icon.Information)
                dlg.setText(self.file_name + " loaded successfully!")
                dlg.exec()
            else:
                QMessageBox.critical(self, "Failed!", result)

    def on_year_interval_dialog(self, btn_ss):
        if self.DM.DF is None:
            QMessageBox.critical(self, "Failed!", 'Please Load a dataset!')
            return

        min_year = int(self.DM.DF['year'].min())
        max_year = int(self.DM.DF['year'].max())
        dialog = YearIntervalDialog(
            min_year,
            max_year,
            self.DM.bins,
            btn_ss,
            self
        )

        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.set_year_intervals(dialog.start_years, min_year, max_year)

    def set_year_intervals(self, start_years, min_year, max_year):
        start_years = sorted(start_years)

        self.DM.bins = start_years.copy()

        # Add final boundary
        self.DM.bins.append(max_year + 1)

        self.DM.year_labels = [
            f'{max(start, min_year)}-{min(end - 1, max_year)}'
            for start, end in zip(
                self.DM.bins[:-1],
                self.DM.bins[1:]
            )
        ]

        self.DM.set_year_groups()

        self.poly_yf.clear()
        self.author1_yf.clear()
        self.author2_yf.clear()
        self.poly_yf.addItem('All')
        year_groups = sorted(self.DM.year_groups.unique(), key=lambda x: int(x.split('-')[0]))
        self.poly_yf.addItems(year_groups)
        self.author1_yf.addItems(year_groups)
        self.author2_yf.addItems(year_groups)

    def on_table(self):
        if self.DM.DF is None:
            QMessageBox.critical(self, "Failed!", 'Please Load a dataset!')
            return

        years_original = sorted(self.DM.year_groups.unique(), key=lambda x: int(x.split('-')[0]))
        year_groups = years_original.copy()
        year_groups[-1] = year_groups[-1][:-4] + str(self.DM.DF.loc[self.DM.DF.shape[0] - 1, 'year'])

        year_group_counts = [int(group.split('-')[1]) - int(group.split('-')[0]) + 1 for group in year_groups]
        year_group_counts.append(sum(year_group_counts))

        year_groups.append('Total')
        year_groups = [group+'/'+str(year_group_counts[i])+'Y' for i, group in enumerate(year_groups)]

        year_counts = self.DM.year_groups.value_counts().sort_index().tolist()
        year_counts.append(sum(year_counts))

        year_percentages = [f"{(count / year_counts[-1])*100:.2f}".rstrip('0').rstrip('.') + "%" for count in year_counts]

        year_coefs = [f"{(count / year_group_counts[i]):.2f}".rstrip('0').rstrip('.') for i, count in enumerate(year_counts)]

        author_counts = []
        total_counter = Counter()
        for group_label in years_original:
            _, authors_of_papers = self.DM.analyze(5, group_label)
            name_counts = Counter(name for paper in authors_of_papers for name in paper)
            total_counter.update({n.lower(): v for n, v in name_counts.items()})

            c = list(name_counts.values())
            row = [sum(v == 1 for v in c), sum(v == 2 for v in c), sum(v >= 3 for v in c)]
            author_counts.append(row + [sum(row)])

        c = list(total_counter.values())
        row = [sum(v == 1 for v in c), sum(v == 2 for v in c), sum(v >= 3 for v in c)]
        author_counts.append(row + [sum(row)])

        author_percentages = [f"{(counts[-1] / author_counts[-1][-1]) * 100:.2f}".rstrip('0').rstrip('.') + "%" for counts in author_counts]

        author_coefs = [f"{(year_counts[i] / count[-1]):.2f}".rstrip('0').rstrip('.') for i, count in enumerate(author_counts)]

        data = [[year_groups[i], year_counts[i], year_percentages[i], year_coefs[i], author_counts[i][0], author_counts[i][1],
                author_counts[i][2], author_counts[i][3], author_percentages[i], author_coefs[i]] for i in range(len(year_groups))]
        # --- workbook & sheet ---
        wb = Workbook()
        ws = wb.active
        ws.title = "Summary Table"
        # --- styles ---
        header_font = xlstyles.Font(bold=True)
        center = xlstyles.Alignment(horizontal="center", vertical="center", wrap_text=True)
        thin = xlstyles.Border(
            left=xlstyles.Side(style="thin"), right=xlstyles.Side(style="thin"),
            top=xlstyles.Side(style="thin"), bottom=xlstyles.Side(style="thin")
        )
        # Top-row groups
        ws.merge_cells("A1:A2")
        ws["A1"] = "Year interval/Years count"
        ws.merge_cells("B1:C1")
        ws["B1"] = "Research count and percentage"
        ws.merge_cells("D1:D2")
        ws["D1"] = "Researches per year"
        ws.merge_cells("E1:I1")
        ws["E1"] = "Authors Information"
        ws.merge_cells("J1:J2")
        ws["J1"] = "Researches per author"
        # second-row (explicit sub-headers)
        ws["B2"] = "Count"
        ws["C2"] = "Percentage"
        ws["E2"] = "1 research"
        ws["F2"] = "2 research"
        ws["G2"] = "3 and more research"
        ws["H2"] = "Total: Count"
        ws["I2"] = "Percentage"
        # --- WRITE DATA rows starting at row 3 ---
        start_row = 3
        for r, row in enumerate(data, start=start_row):
            for c, val in enumerate(row, start=1):
                cell = ws.cell(row=r, column=c)
                # treat percent-strings as numbers so Excel shows them as percentages
                if isinstance(val, str) and val.endswith("%"):
                    try:
                        f = float(val.strip("%")) / 100.0
                        cell.value = f
                        # choose format with one decimal if original had decimal, else no decimal
                        cell.number_format = "0.0%" if ("." in val) else "0%"
                    except Exception:
                        cell.value = val
                else:
                    cell.value = val
                    # number formats for numeric columns
                    if c == 4:
                        cell.number_format = "0.00"
                    if c == 10:
                        cell.number_format = "0.00"
                    if c in (2, 5, 6, 7, 8):
                        cell.number_format = "0"

        max_col = 10
        max_row = ws.max_row
        for row in ws.iter_rows(min_row=1, max_row=max_row, min_col=1, max_col=max_col):
            for cell in row:
                cell.alignment = center
                cell.border = thin
        # apply bold to header rows (row1 and row2)
        for col in range(1, max_col + 1):
            ws.cell(row=1, column=col).font = header_font
            ws.cell(row=2, column=col).font = header_font
        # --- column widths ---
        widths = {
            1: 20,  # A
            2: 18,  # B
            3: 12,  # C
            4: 26,  # D
            5: 10,  # E
            6: 10,  # F
            7: 18,  # G
            8: 12,  # H
            9: 12,  # I
            10: 16,  # J
        }
        for col_idx, w in widths.items():
            ws.column_dimensions[get_column_letter(col_idx)].width = w
            
        self.write_cooccurrence_sheet(wb)

        # --- Save file ---
        path = self.directory + pathlib.Path(self.file_name).stem + '__summary__.xlsx'
        try:
            wb.save(path)
            dlg = QMessageBox(self)
            dlg.setWindowTitle("Success!")
            dlg.setIcon(QMessageBox.Icon.Information)
            dlg.setText('Summary file saved at ' + path)
            dlg.exec()
        except Exception as e:
            QMessageBox.critical(self, "Failed!", str(e))
            
    def write_cooccurrence_sheet(self, wb):
        cat_names, links, years = self.DM.analyze(3)
        n = len(cat_names)
        idx = {c: i for i, c in enumerate(cat_names)}

        center = xlstyles.Alignment(horizontal="center", vertical="center", wrap_text=True)
        side = xlstyles.Side(style="thin")
        border = xlstyles.Border(left=side, right=side, top=side, bottom=side)
        bold = xlstyles.Font(bold=True)

        # (None = no filter)
        periods = sorted(set(years), key=lambda x: int(x.split('-')[0]))
        blocks = [(g, g) for g in periods] + [('Total', None)]

        ws = wb.create_sheet("Co-occurrence")
        row = 1
        for title, group in blocks:
            co = np.zeros((n, n), dtype=int)
            num_records = 0
            for link, y in zip(links, years):
                if group is not None and y != group:
                    continue
                num_records += 1
                ids = [idx[c] for c in set(link)]
                co[np.ix_(ids, ids)] += 1      # diagonal = records containing that category

            ws.cell(row=row, column=1, value=f"{title} | {num_records} records").font = bold

            hr = row + 1
            ws.cell(row=hr, column=1, value="Category")
            for j, name in enumerate(cat_names):
                ws.cell(row=hr, column=j + 2, value=name)
            for c in range(1, n + 2):
                cell = ws.cell(row=hr, column=c)
                cell.font = bold
                cell.alignment = center
                cell.border = border
            ws.row_dimensions[hr].height = 32

            for i, name in enumerate(cat_names):
                r = hr + 1 + i
                lab = ws.cell(row=r, column=1, value=name)
                lab.font = bold
                lab.alignment = center
                lab.border = border
                for j in range(n):
                    cell = ws.cell(row=r, column=j + 2, value=int(co[i, j]) if i != j else None)
                    cell.alignment = center
                    cell.border = border

            row = hr + n + 3

        ws.column_dimensions["A"].width = 22
        for j, name in enumerate(cat_names):
            ws.column_dimensions[get_column_letter(j + 2)].width = max(10, min(16, len(name) + 2))

    def on_analyze(self):
        self.analyze_id = self.stack_widget.currentIndex()
        if self.analyze_id == 4:
            result = self.DM.analyze(self.analyze_id, self.author1_yf.currentText())
        elif self.analyze_id == 5:
            result = self.DM.analyze(self.analyze_id, self.author2_yf.currentText())
        else:
            result = self.DM.analyze(self.analyze_id)
        if result is not None:
            self.canvas[self.analyze_id - 1].axes.cla()
            if self.analyze_id == 1:
                self.plt_lines(result[0], result[1], result[2])
            elif self.analyze_id == 2:
                self.plt_sankey(result[0], result[1])
            elif self.analyze_id == 3:
                self.plt_poly(result[0], result[1], result[2])
            elif self.analyze_id == 4:
                self.plt_author1(result[0], result[1], result[2], result[3])
                self.canvas[3].fig.tight_layout()
                self.canvas[3].axes.cla()
                self.plt_author1(result[0], result[1], result[2], result[3])
            elif self.analyze_id == 5:
                self.plt_author2(result[0], result[1])
            self.canvas[self.analyze_id - 1].fig.tight_layout()
            self.canvas[self.analyze_id - 1].draw()

    def show_jaccard_matrix(self):
        result = self.DM.analyze(3)
        if result is None:
            return
        cat_names, links, years = result
        year_filter = self.poly_yf.currentText()
        J = compute_jaccard(cat_names, links, years, year_filter)

        dlg = QDialog(self)
        dlg.setWindowTitle(f'Jaccard similarity matrix (years: {year_filter})')
        dlg.resize(800, 700)
        layout = QVBoxLayout(dlg)

        fig = Figure(figsize=(8, 7), layout='constrained')
        canvas = FigureCanvasQTAgg(fig)
        ax = fig.add_subplot(111)
        im = ax.imshow(J, cmap='viridis', vmin=0, vmax=1)
        fig.colorbar(im, ax=ax, label='Jaccard index')

        n = len(cat_names)
        ax.set_xticks(range(n))
        ax.set_yticks(range(n))
        ax.set_xticklabels(cat_names, rotation=45, ha='right')
        ax.set_yticklabels(cat_names)
        for i in range(n):
            for j in range(n):
                ax.text(j, i, f'{J[i, j]:.2f}', ha='center', va='center',
                        color='white' if J[i, j] < 0.6 else 'black', fontsize=9)

        layout.addWidget(canvas)

        # --- bottom button row ---
        btn_row = QHBoxLayout()
        save_btn = QPushButton('Save as picture...', dlg)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

        def save_figure():
            path, _ = QFileDialog.getSaveFileName(
                dlg,
                'Save Jaccard matrix',
                f'jaccard_matrix_{year_filter}.png',
                'PNG image (*.png);;PDF (*.pdf);;SVG (*.svg);;JPEG (*.jpg)'
            )
            if path:
                fig.savefig(path, dpi=300, bbox_inches='tight')

        save_btn.clicked.connect(save_figure)

        dlg.exec()

    def plt_lines(self, categories, years, year_counts_for_cats):
        if len(categories) > 10:
            colors = [cm.tab20(i % 20) for i in range(len(categories))]
        else:
            colors = cm.tab10(range(len(categories)))

        markers = [7, 6, 5, 4, 11, 10, 9, 8, 3, 2, 1, 0]
        cat_filters = self.lines_cb.get_checked_items()
        for i, name in enumerate(categories):
            alpha = 0.0
            if name in cat_filters:
                alpha = 1.0
            self.canvas[0].axes.plot(years, year_counts_for_cats[i], color=colors[i], marker=markers[i], alpha=alpha, label=name)
            self.canvas[0].axes.fill_between(years, year_counts_for_cats[i], 0, color=colors[i], alpha=alpha*0.2, linewidth=0, zorder=2)

        self.canvas[0].axes.set_ylabel('Counts')
        self.canvas[0].axes.yaxis.tick_right()
        self.canvas[0].axes.yaxis.set_label_position('right')

        self.canvas[0].axes.set_xticks(years)
        self.canvas[0].axes.set_xticklabels(years, fontsize=12, fontweight='bold')
        self.canvas[0].axes.tick_params(axis='x', labelrotation=90)
        self.canvas[0].axes.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{int(x)}'))
        self.canvas[0].axes.set_xlim(years[0] - 0.5, years[-1] + 0.5)
        self.canvas[0].axes.set_ylim(self.canvas[0].axes.get_ylim()[0], self.canvas[0].axes.get_ylim()[1] + 1)

        bins_with_end = self.DM.bins[:-1] + [years[-1]]

        for i in range(len(bins_with_end) - 1):
            color = '#c1d0b5' if i % 2 == 0 else '#f4e7ce'

            self.canvas[0].axes.axvspan(
                bins_with_end[i],
                bins_with_end[i + 1],
                color=color,
                alpha=0.3
            )

        for year in bins_with_end:
            self.canvas[0].axes.axvline(
                x=year,
                color='gray',
                linestyle='--',
                linewidth=1
            )

        self.canvas[0].axes.legend(fontsize=12, loc='upper left', ncol=(len(categories) // 2) + (len(categories) % 2))

    def plt_sankey(self, nodes, flows):
        s = Sankey(flows=flows, nodes=nodes)
        s.draw(self.canvas[1].axes)

    def plt_poly(self, cat_names, links, years):
        color_dict = dict.fromkeys(years, '')
        if len(color_dict) > 10:
            colors = [cm.tab20(i % 20) for i in range(len(color_dict))]
        else:
            colors = cm.tab10(range(len(color_dict)))
        dict_keys = list(color_dict.keys())
        for i in range(len(color_dict)):
            color_dict[dict_keys[i]] = colors[i]
        num_cats = len(cat_names)
        # Angle between each vertex of the big polygon
        angle = 2 * np.pi / num_cats

        links_history = {}
        for link in links:
            for i in range(len(link)):
                for j in range(i + 1, len(link)):
                    c_1 = link[i]
                    c_2 = link[j]
                    if (c_1, c_2) in links_history:
                        links_history[(c_1, c_2)] += 1
                    else:
                        links_history[(c_1, c_2)] = 1
        max_link = max(links_history.values())
        if max_link % 2 == 0:
            max_link += 1
        # Define the size of the small polygon (inner polygon) with the same number of sides as the big polygon
        inner_radius = max_link + 0.5
        # Radius of the large polygon (that will hold the vertices)
        outer_radius = inner_radius * num_cats
        # Create the positions of the vertices of the big polygon (this is where the small polygons will be placed)
        outer_points = [(outer_radius * np.cos(i * angle), outer_radius * np.sin(i * angle)) for i in
                        range(num_cats)]
        # Now, for each class, draw a small polygon at each vertex of the big polygon
        c_positions = {}
        for i, c_name in enumerate(cat_names):
            # Calculate the vertices of the small polygon (each class's polygon)
            small_polygon_points = [
                (inner_radius * np.cos(j * angle), inner_radius * np.sin(j * angle))
                for j in range(num_cats)
            ]

            # Translate the small polygon to the current position based on the vertex of the big polygon
            x_offset, y_offset = outer_points[i]

            # Store the position of each class
            c_positions[c_name] = (x_offset, y_offset)

            # Draw the small polygon at the current position
            small_polygon = Polygon(
                [(x + x_offset, y + y_offset) for x, y in small_polygon_points],
                color='lightblue',
                zorder=2
            )
            self.canvas[2].axes.add_patch(small_polygon)

            # Calculate the angle (direction) from the center to this polygon
            theta = i * angle  # in radians

            # Set how far from the polygon the text should be
            label_offset = inner_radius * 1.4

            # Determine label position outward in the direction of theta
            label_x = x_offset + label_offset * np.cos(theta)
            label_y = y_offset + label_offset * np.sin(theta)
            # Horizontal alignment based on angle
            ha = 'center'
            if np.cos(theta) > 0:
                ha = 'left'
            elif np.cos(theta) < 0:
                ha = 'right'

            # Place the label in the computed direction without rotating it
            self.canvas[2].axes.text(
                label_x, label_y, c_name,
                color='black',
                ha=ha, va='center',
                fontsize=16,
                rotation=0,  # Keep text upright
                zorder=3
            )

        cat_filters = self.poly_cb.get_checked_items()
        current_offsets = {}
        added_years = set()
        # Draw lines for each link in the links list
        for index, link in enumerate(links):
            if self.poly_yf.currentText() != 'All':
                if self.poly_yf.currentText() != years[index]:
                    continue
            for i in range(len(link) - 1):
                for j in range(i + 1, len(link)):
                    c_1 = link[i]
                    c_2 = link[j]

                    if not (c_1 in cat_filters) and not (c_2 in cat_filters):
                        continue

                    if (c_1, c_2) in current_offsets:
                        current_offsets[(c_1, c_2)] *= -1
                        if current_offsets[(c_1, c_2)] >= 0:
                            current_offsets[(c_1, c_2)] += 0.75
                    else:
                        current_offsets[(c_1, c_2)] = 0
                    offset_value = current_offsets[(c_1, c_2)]
                    # Get the positions of the two classes
                    p1 = np.array(c_positions[c_1])
                    p2 = np.array(c_positions[c_2])
                    # Compute the direction vector from p1 to p2
                    direction_vector = p2 - p1
                    # Calculate the normal vector (perpendicular to the direction vector)
                    # For 2D, a perpendicular vector can be obtained by swapping the components and negating one
                    normal_vector = np.array([-direction_vector[1], direction_vector[0]])
                    # Normalize the normal vector to ensure consistent shifting
                    normal_vector = normal_vector / np.linalg.norm(normal_vector)
                    # Move the points by a factor along the normal vector
                    shift = normal_vector * offset_value
                    # Compute the new points by shifting both p1 and p2
                    new_p1 = p1 + shift
                    new_p2 = p2 + shift

                    # Draw the line from the right side of class_1 to the right side of class_2
                    if years[index] in added_years:
                        self.canvas[2].axes.plot([new_p1[0], new_p2[0]], [new_p1[1], new_p2[1]], color=color_dict[years[index]], lw=1, zorder=1)
                    else:
                        added_years.add(years[index])
                        self.canvas[2].axes.plot([new_p1[0], new_p2[0]], [new_p1[1], new_p2[1]], color=color_dict[years[index]], lw=1, zorder=1, label=years[index])

        if len(cat_filters) == 1:
            for c_name in cat_names:
                if c_name != cat_filters[0]:
                    offset_key = (cat_filters[0], c_name) if (cat_filters[0], c_name) in current_offsets else (c_name, cat_filters[0])
                    num = (-1 if current_offsets[offset_key] > 0 else 0) + 2 * round(abs(current_offsets[offset_key]) / 0.75) + 1 if offset_key in current_offsets else 0
                    self.canvas[2].axes.text(
                        c_positions[c_name][0],
                        c_positions[c_name][1],
                        str(num),
                        fontsize=15,
                        ha='center',
                        va='center',
                        zorder=3,
                    )

        # Set the limits and aspect ratio
        #self.canvas[2].axes.set_xlim(-3 * outer_radius, 3 * outer_radius)
        #self.canvas[2].axes.set_ylim(-1.25 * outer_radius, 1.25 * outer_radius)
        self.canvas[2].axes.set_aspect('equal', adjustable='datalim')
        self.canvas[2].axes.legend(fontsize=12, loc='upper left')
        self.canvas[2].axes.axis('off')

    def plt_author1(self, authors, authors_of_papers, categories, links):
        if len(categories) > 10:
            colors = [cm.tab20(i % 20) for i in range(len(categories))]
        else:
            colors = cm.tab10(range(len(categories)))
        links_history = {}
        for row in range(len(authors_of_papers)):
            for i in range(len(authors_of_papers[row])):
                for j in range(len(links[row])):
                    a = authors_of_papers[row][i]
                    c = links[row][j]
                    if (a, c) in links_history:
                        links_history[(a, c)] += 1
                    else:
                        links_history[(a, c)] = 1
        max_link = max(links_history.values())
        circle_centers = np.arange(len(authors)) * max_link * 1.2 + 1
        center_of_circles = (circle_centers[(len(circle_centers) // 2)] + circle_centers[(len(circle_centers) // 2 - 1)]) / 2\
                            if len(circle_centers) % 2 == 0 else circle_centers[(len(circle_centers) // 2)]
        squares_y = -(len(circle_centers) * max_link * 0.2 + 1)
        s_offset = 0
        category_x_positions = []
        squares_xs = []
        for i in range(len(categories)):
            category_x_positions.append(center_of_circles + s_offset)
            rect_x, rect_y = center_of_circles + s_offset, squares_y
            squares_xs.append(rect_x)
            rect = Rectangle((rect_x, rect_y), 0.35, 0.35, angle=45, rotation_point='xy',
                    color=colors[i], zorder=2)
            self.canvas[3].axes.add_artist(rect)
            s_offset *= -1
            if s_offset >= 0:
                s_offset += max((max_link / 2) * (len(circle_centers) / len(categories)), 1.0)

        links_offset = {}
        for row in range(len(authors_of_papers)):
            for i in range(len(authors_of_papers[row])):
                for j in range(len(links[row])):
                    a = authors_of_papers[row][i]
                    c = links[row][j]
                    if (a, c) in links_offset:
                        links_offset[(a, c)] = (links_offset[(a, c)][0] + 1, links_offset[(a, c)][1])
                        offset = 0.8 / (links_history[(a, c)] // 2)
                        if links_offset[(a, c)][0] % 2 == 1:
                            links_offset[(a, c)] = (links_offset[(a, c)][0], links_offset[(a, c)][1] * offset)
                        else:
                            links_offset[(a, c)] = (links_offset[(a, c)][0], links_offset[(a, c)][1] * -1)
                    else:
                        links_offset[(a, c)] = (0, 0)
                    cc = circle_centers[authors.index(a)]
                    xp = category_x_positions[categories.index(c)]
                    off = links_offset[(a, c)][1] * (max_link * 0.05 + 0.05)
                    self.canvas[3].axes.plot([cc + off, xp], [0, squares_y + 0.5], zorder=1, color=colors[categories.index(c)])

        # Plot each circle
        added_years = set()
        for i in range(len(authors)):
            if self.author1_yf.currentText() in added_years:
                circle = Circle((circle_centers[i], 0), max_link * 0.05 + 0.05, color='black', fill=True, zorder=2)
            else:
                added_years.add(self.author1_yf.currentText())
                circle = Circle((circle_centers[i], 0), max_link * 0.05 + 0.05, color='black', fill=True, zorder=2, label=self.author1_yf.currentText())
            self.canvas[3].axes.add_artist(circle)
        # Add x-axis labels as the names of the circles
        self.canvas[3].axes.set_xticks(circle_centers)
        self.canvas[3].axes.xaxis.set_ticks_position('top')
        self.canvas[3].axes.set_xticklabels(authors, fontsize=8)
        self.canvas[3].axes.tick_params(axis='x', labelrotation=90)
        ax_top = self.canvas[3].axes.secondary_xaxis('bottom')
        ax_top.set_xticks(squares_xs)
        ax_top.set_xticklabels(categories, fontsize=12)
        ax_top.tick_params(axis='x', labelrotation=90)
        # Set the aspect ratio to be equal
        self.canvas[3].axes.set_aspect('equal', adjustable='datalim')
        #xlim = (min(center_of_circles - abs(s_offset) - 1, -max_link * 0.05 + 0.5), max(center_of_circles + abs(s_offset) + 1, circle_centers[-1] + max_link * 0.05 + 0.5))
        self.canvas[3].axes.set_ylim((squares_y - 0.5, max_link * 0.05 + 0.5))
        self.canvas[3].axes.legend(fontsize=12, loc='upper left')
        self.canvas[3].axes.get_yaxis().set_visible(False)

    def plt_author2(self, names, authors_of_papers):
        orbit_spacing = 0.05
        circle_radius = 0.05
        name_counts = {name: 0 for name in names}
        # Count appearances
        for group in authors_of_papers:
            for name in group:
                name_counts[name] += 1

        max_orbits = max(name_counts.values()) - 1
        ring_radius = ((4 * circle_radius) / np.sin((2 * np.pi / len(names)) / 2)) + (6 * max_orbits * orbit_spacing)
        angles = np.linspace(0, 2 * np.pi, len(names), endpoint=False)

        positions = {}
        added_years = set()
        texts = []
        for i, name in enumerate(names):
            angle = angles[i]
            x = ring_radius * np.cos(angle)
            y = ring_radius * np.sin(angle)
            positions[name] = (x, y)  # Store the position for each name

            # Draw main circle
            if self.author2_yf.currentText() in added_years:
                self.canvas[4].axes.add_patch(plt.Circle((x, y), circle_radius, color='skyblue', ec='black', zorder=2))
            else:
                added_years.add(self.author2_yf.currentText())
                self.canvas[4].axes.add_patch(plt.Circle((x, y), circle_radius, color='skyblue', ec='black', zorder=2, label=self.author2_yf.currentText()))
            # Draw orbits
            orbits = name_counts[name] - 1
            for j in range(orbits):
                orbit_r = circle_radius + (j + 1) * orbit_spacing
                orbit = plt.Circle((x, y), orbit_r, color='gray', fill=False, alpha=0.6, zorder=1)
                self.canvas[4].axes.add_patch(orbit)

            # Add label
            label_radius = ring_radius + max_orbits * orbit_spacing + 0.5
            lx = label_radius * np.cos(angle)
            ly = label_radius * np.sin(angle)
            # Horizontal alignment based on angle
            ha = 'center'
            if np.cos(angle) > 0:
                ha = 'left'
            elif np.cos(angle) < 0:
                ha = 'right'

            rotation = np.degrees(angle)
            if 90 < rotation <= 270:
                rotation += 180
            txt = self.canvas[4].axes.text(lx, ly, name, ha=ha, va='center',
                    rotation=rotation, rotation_mode='anchor',
                    fontsize=7)
            
            texts.append(txt)

        self.canvas[4].axes.callbacks.connect(
            'xlim_changed',
            lambda ax: update_texts_size(ax, texts)
        )
            
        # Create a set of all connected name pairs (both directions)
        connected_names = set()
        for group in authors_of_papers:
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    name1 = group[i]
                    name2 = group[j]
                    connected_names.add((name1, name2))
                    connected_names.add((name2, name1))  # Undirected graph: add both directions

        for name1, name2 in connected_names:
            p1 = positions[name1]
            p2 = positions[name2]
            control_point = [(p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2]  # Midpoint between p1 and p2
            # Move the control point slightly inward, 0.1 of the ring radius
            control_point = [(control_point[0] * 0.8), (control_point[1] * 0.8)]  # 80% of the distance from the center
            # Draw the curve
            draw_bezier_curve(p1, control_point, p2, self.canvas[4].axes)

        self.canvas[4].axes.legend(fontsize=12, loc='upper left')
        # Set axis limits
        height = self.canvas[4].size().height()
        width = self.canvas[4].size().width()

        self.canvas[4].axes.set_xlim(-1.5 * ring_radius * (width/height), 1.5 * ring_radius * (width/height))
        self.canvas[4].axes.set_ylim(-1.5 * ring_radius, 1.5 * ring_radius)

        self.canvas[4].axes.set_aspect('equal', adjustable='box')
        self.canvas[4].axes.axis('off')
