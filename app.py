import sys
import math
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QListWidget, QListWidgetItem, QPushButton, QTableWidget,
    QTableWidgetItem, QLineEdit, QGroupBox, QDoubleSpinBox, QMessageBox,
    QHeaderView, QSplitter, QInputDialog, QAbstractItemView, QCheckBox,
    QStackedWidget, QFrame,
)
from PyQt6.QtCore import Qt, QSize, QTimer, QPointF
from PyQt6.QtGui import QFont, QColor, QPixmap, QPainter

import data
from solver import solve, solve_flexible, diagnose, KPI_DEFAULTS, KPI_LABELS

# ── Sagui brand palette ───────────────────────────────────────────────────────
# #C5A04D brass-gold  |  #236C45 deep green  |  #113516 dark forest green
# #F2CD24 vibrant yellow  |  #E3C988 light golden  |  #FFFFFF white
STYLE = """
QMainWindow, QDialog {
    background-color: #FFFFFF;
}
QWidget {
    background-color: #FFFFFF;
    color: #1C2E20;
    font-family: 'Segoe UI';
    font-size: 13px;
}

/* ── GroupBox cards ── */
QGroupBox {
    background-color: #FAFAF7;
    border: 1px solid #DDD0A0;
    border-top: 3px solid #236C45;
    border-radius: 6px;
    margin-top: 20px;
    padding: 14px 12px 12px 12px;
    font-weight: bold;
    color: #236C45;
    font-size: 11px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 14px;
    top: -1px;
    padding: 0 8px;
    background-color: #FAFAF7;
}

/* ── Buttons ── */
QPushButton {
    background-color: #F2EDD8;
    color: #1C2E20;
    border: 1px solid #D4C07A;
    border-radius: 5px;
    padding: 6px 16px;
}
QPushButton:hover {
    background-color: #E8F4EE;
    border-color: #236C45;
    color: #236C45;
}
QPushButton:pressed {
    background-color: #CEEADB;
    border-color: #113516;
    color: #113516;
}
QPushButton#btn_solve {
    background-color: #236C45;
    color: #FFFFFF;
    font-weight: bold;
    font-size: 15px;
    padding: 12px;
    border: none;
    border-radius: 6px;
}
QPushButton#btn_solve:hover  { background-color: #1E5C3C; }
QPushButton#btn_solve:pressed { background-color: #113516; }
QPushButton#btn_save {
    background-color: #C5A04D;
    color: #FFFFFF;
    font-weight: bold;
    border: none;
    border-radius: 5px;
    padding: 8px 18px;
}
QPushButton#btn_save:hover  { background-color: #B08A3A; }
QPushButton#btn_save:pressed { background-color: #9A7530; }
QPushButton#btn_deselect_all {
    font-size: 11px;
    padding: 5px 12px;
}

/* ── Tables ── */
QTableWidget {
    background-color: #FFFFFF;
    alternate-background-color: #F7F5EE;
    border: 1px solid #DDD0A0;
    border-radius: 5px;
    gridline-color: #EDE8D0;
    selection-background-color: #CEEADB;
    selection-color: #113516;
    color: #1C2E20;
    outline: none;
}
QTableWidget::item { padding: 5px 10px; }
QHeaderView { border: none; }
QHeaderView::section {
    background-color: #EDE8D8;
    color: #4A6B52;
    border: none;
    border-right: 1px solid #DDD0A0;
    border-bottom: 2px solid #C8B870;
    padding: 7px 10px;
    font-weight: bold;
    font-size: 12px;
}

/* ── List widget ── */
QListWidget {
    background-color: #FFFFFF;
    border: 1px solid #DDD0A0;
    border-radius: 5px;
    color: #1C2E20;
    outline: none;
}
QListWidget::item { padding: 4px 8px; }
QListWidget::item:hover { background-color: #E8F4EE; color: #236C45; }
QListWidget::item:selected { background-color: #CEEADB; color: #113516; }

/* ── Inputs ── */
QDoubleSpinBox, QLineEdit {
    background-color: #FFFFFF;
    border: 1px solid #DDD0A0;
    border-radius: 5px;
    padding: 5px 10px;
    color: #1C2E20;
}
QDoubleSpinBox:hover, QLineEdit:hover { border-color: #B8A860; }
QDoubleSpinBox:focus, QLineEdit:focus {
    border-color: #236C45;
    background-color: #FBFFF9;
}
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button { width: 0; height: 0; }

/* ── Scrollbars ── */
QScrollBar:vertical {
    background: #F2EDD8;
    width: 7px;
    border-radius: 4px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background: #C5B070;
    border-radius: 4px;
    min-height: 24px;
}
QScrollBar::handle:vertical:hover { background: #A89050; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { height: 0; }

/* ── Splitter ── */
QSplitter::handle { background-color: #DDD0A0; width: 1px; }

/* ── Checkbox ── */
QCheckBox { spacing: 8px; background: transparent; }
QCheckBox::indicator {
    width: 15px; height: 15px;
    border: 1.5px solid #C5B070;
    border-radius: 3px;
    background-color: #FFFFFF;
}
QCheckBox::indicator:hover {
    border-color: #236C45;
    background-color: #F0FFF4;
}
QCheckBox::indicator:checked {
    background-color: #236C45;
    border-color: #236C45;
}

/* ── Min spinbox (small, inline) ── */
QDoubleSpinBox#spin_min {
    background-color: #F2EDD8;
    border: 1px solid #E3C988;
    border-radius: 3px;
    color: #6B8575;
    font-size: 11px;
    padding: 2px 6px;
}
QDoubleSpinBox#spin_min:disabled {
    color: #C5B8A0;
    background-color: #F5F0E8;
    border-color: #EDE8D8;
}
QDoubleSpinBox#spin_min:enabled:focus { border-color: #236C45; }

/* ── Tooltip ── */
QToolTip {
    background-color: #1C2E20;
    color: #FFFFFF;
    border: none;
    padding: 4px 8px;
    border-radius: 4px;
    font-size: 12px;
}

/* ── Custom title bar controls ── */
QPushButton#btn_min, QPushButton#btn_max {
    background: transparent;
    border: none;
    color: #8AA094;
    font-size: 15px;
    border-radius: 4px;
}
QPushButton#btn_min:hover { background-color: #E8F4EE; color: #236C45; }
QPushButton#btn_max:hover { background-color: #E8F4EE; color: #236C45; }
QPushButton#btn_close {
    background: transparent;
    border: none;
    color: #8AA094;
    font-size: 15px;
    border-radius: 4px;
}
QPushButton#btn_close:hover { background-color: #FDECEA; color: #C0392B; }
"""

GREEN  = "#236C45"
RED    = "#C0392B"
YELLOW = "#C5A04D"
MUTED  = "#8AA094"

# (col, label, unit, vd_ref, indent, no_vd)
# vd_ref = None → no %VD column | no_vd = True → "Não há VD"
ANVISA_NUTRIENTS = [
    ("kcal",         "Valor energético",     "kcal", 2000,  False, False),
    ("carb",         "Carboidratos totais",  "g",    300,   False, False),
    ("sugars_total", "Açúcares totais",      "g",    None,  True,  False),
    ("sugars_added", "Açúcares adicionados", "g",    50,    True,  False),
    ("fat",          "Gorduras totais",      "g",    65,    False, False),
    ("sat_fat",      "Gorduras saturadas",   "g",    20,    True,  False),
    ("trans_fat",    "Gorduras trans",       "g",    None,  True,  True),
    ("fiber",        "Fibra alimentar",      "g",    25,    False, False),
    ("protein",      "Proteínas",            "g",    50,    False, False),
    ("sodium",       "Sódio",               "mg",   2400,  False, False),
]


class _Throbber(QWidget):
    """Windows-style spinning dot ring."""
    NUM  = 12
    SIZE = 80

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(self.SIZE, self.SIZE)
        self._step = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def start(self):
        self._step = 0
        self._timer.start(83)   # ~12 fps → one full rotation per second
        self.show()

    def stop(self):
        self._timer.stop()
        self.hide()

    def _tick(self):
        self._step = (self._step + 1) % self.NUM
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx = cy = self.SIZE / 2
        orbit  = self.SIZE * 0.32
        dot_r  = self.SIZE * 0.09

        for i in range(self.NUM):
            angle = 2 * math.pi * i / self.NUM - math.pi / 2
            x = cx + orbit * math.cos(angle)
            y = cy + orbit * math.sin(angle)

            # age 0 = current (brightest), trails off clockwise
            age = (i - self._step) % self.NUM
            opacity = max(0.07, 1.0 - age / self.NUM)

            color = QColor(35, 108, 69)   # #236C45
            color.setAlphaF(opacity)
            painter.setBrush(color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(x, y), dot_r, dot_r)

        painter.end()


class _TitleBar(QWidget):
    def __init__(self, parent: QMainWindow):
        super().__init__(parent)
        self.setFixedHeight(40)
        self.setStyleSheet("background-color: #FFFFFF; border-bottom: 1px solid #E3C988;")
        self._drag_pos = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 8, 0)
        layout.setSpacing(4)
        layout.addStretch()

        BASE = ("font-size: 14px; font-weight: bold; border-radius: 4px; border: none;"
                " background-color: #EDE8D8; color: #113516; padding: 0;")
        for obj_name, symbol, hover_css in [
            ("btn_min",   "_",  "background-color:#E8F4EE; color:#236C45;"),
            ("btn_max",   "⤢",  "background-color:#E8F4EE; color:#236C45;"),
            ("btn_close", "×",  "background-color:#FDECEA; color:#C0392B;"),
        ]:
            btn = QPushButton(symbol)
            btn.setObjectName(obj_name)
            btn.setFixedSize(32, 28)
            btn.setCursor(Qt.CursorShape.ArrowCursor)
            btn.setStyleSheet(
                f"QPushButton {{ {BASE} }}"
                f"QPushButton:hover {{ {hover_css} }}"
            )
            layout.addWidget(btn)

        self.findChild(QPushButton, "btn_min").clicked.connect(parent.showMinimized)
        self.findChild(QPushButton, "btn_max").clicked.connect(self._toggle_max)
        self.findChild(QPushButton, "btn_close").clicked.connect(parent.close)

    def _toggle_max(self):
        win = self.window()
        if win.isMaximized():
            win.showNormal()
        else:
            win.showMaximized()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.window().frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() == Qt.MouseButton.LeftButton:
            self.window().move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    def mouseDoubleClickEvent(self, event):
        self._toggle_max()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sagui Gelatos — Balanceador de Receitas")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setMinimumSize(1000, 800)
        self._last_nutrition_quantities: dict | None = None
        self._last_nutrition_base_size: float = 1000.0
        self.df_all = data.load_ingredients()
        self._last_result = None
        self._checked_names: set[str] = set()
        self._min_quantities: dict[str, float] = {}
        self._ingredient_widgets: dict[str, tuple] = {}
        self._setup_ui()

    # ── UI construction ───────────────────────────────────────────────────────

    def _setup_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        outer_layout = QVBoxLayout(root)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # Custom title bar (edge-to-edge)
        outer_layout.addWidget(_TitleBar(self))

        # Content area with padding
        content = QWidget()
        main_layout = QVBoxLayout(content)
        main_layout.setContentsMargins(20, 4, 20, 12)
        main_layout.setSpacing(0)

        # Header — logo
        logo_label = QLabel()
        logo_path = str(Path(__file__).parent / "resources" / "Logo.png")
        pixmap = QPixmap(logo_path).scaledToHeight(52, Qt.TransformationMode.SmoothTransformation)
        logo_label.setPixmap(pixmap)
        logo_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        logo_label.setStyleSheet("padding: 2px 0 4px 0; background: transparent;")
        main_layout.addWidget(logo_label)

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setFixedHeight(1)
        divider.setStyleSheet("background-color: #E3C988; border: none;")
        main_layout.addWidget(divider)
        main_layout.addSpacing(6)

        self.stacked = QStackedWidget()
        main_layout.addWidget(self.stacked, stretch=1)
        self.stacked.addWidget(self._build_main_page())      # index 0
        self.stacked.addWidget(self._build_loading_page())    # index 1
        self.stacked.addWidget(self._build_results_page())    # index 2

        outer_layout.addWidget(content, stretch=1)

    def _build_main_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_ingredients_panel())
        splitter.addWidget(self._build_settings_panel())
        splitter.setSizes([450, 550])
        layout.addWidget(splitter)
        return page

    def _build_loading_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._throbber = _Throbber()
        layout.addWidget(self._throbber, alignment=Qt.AlignmentFlag.AlignCenter)
        return page

    def _build_results_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(8)

        # Navigation bar
        nav = QHBoxLayout()
        btn_back = QPushButton("← Voltar")
        btn_back.clicked.connect(lambda: self.stacked.setCurrentIndex(0))

        self.lbl_status = QLabel("Aguardando cálculo...")
        self.lbl_status.setStyleSheet(f"color: {MUTED}; font-size: 13px;")
        self.lbl_status.setWordWrap(True)

        self.btn_save = QPushButton("Salvar Receita")
        self.btn_save.setObjectName("btn_save")
        self.btn_save.setEnabled(False)
        self.btn_save.clicked.connect(self._on_save)

        nav.addWidget(btn_back)
        nav.addWidget(self.lbl_status, stretch=1)
        nav.addWidget(self.btn_save)
        layout.addLayout(nav)

        # Results + nutrition side by side
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_results_panel())
        splitter.addWidget(self._build_nutrition_panel())
        splitter.setSizes([500, 500])
        layout.addWidget(splitter, stretch=1)

        return page

    def _build_ingredients_panel(self) -> QWidget:
        box = QGroupBox("Ingredientes Disponíveis")
        layout = QVBoxLayout(box)

        # Search
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Buscar ingrediente...")
        self.search_bar.textChanged.connect(self._filter_ingredients)
        layout.addWidget(self.search_bar)

        # Buttons row
        btn_row = QHBoxLayout()
        btn_load = QPushButton("Carregar Receita")
        btn_load.clicked.connect(self._on_load_recipe)
        btn_none = QPushButton("Desmarcar Todos")
        btn_none.setObjectName("btn_deselect_all")
        btn_none.clicked.connect(self._deselect_all)
        btn_row.addWidget(btn_load)
        btn_row.addWidget(btn_none)
        layout.addLayout(btn_row)

        # Selection counter
        self.lbl_selected_count = QLabel("0 selecionados")
        self.lbl_selected_count.setStyleSheet("color: #6B8575; font-size: 11px;")
        self.lbl_selected_count.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_selected_count)

        # Ingredient list
        self.ingredient_list = QListWidget()
        self._populate_ingredient_list()
        layout.addWidget(self.ingredient_list, stretch=1)

        return box

    def _populate_ingredient_list(self, filter_text: str = ""):
        self.ingredient_list.clear()
        self._ingredient_widgets.clear()
        current_category = None

        for _, row in self.df_all.iterrows():
            name = row["name"]
            if filter_text and filter_text.lower() not in name.lower():
                continue

            # Category header
            if row["category"] != current_category:
                current_category = row["category"]
                header_item = QListWidgetItem(f"  {current_category}")
                header_item.setFlags(Qt.ItemFlag.NoItemFlags)
                header_item.setForeground(QColor("#236C45"))
                header_item.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
                self.ingredient_list.addItem(header_item)

            # Ingredient row with checkbox + min spinbox
            item = QListWidgetItem()
            item.setSizeHint(QSize(0, 30))
            item.setData(Qt.ItemDataRole.UserRole, name)
            self.ingredient_list.addItem(item)

            checked = name in self._checked_names

            widget = QWidget()
            widget.setStyleSheet("background: transparent;")
            w_layout = QHBoxLayout(widget)
            w_layout.setContentsMargins(6, 0, 6, 0)
            w_layout.setSpacing(4)

            chk = QCheckBox(name)
            chk.setChecked(checked)
            chk.toggled.connect(lambda c, n=name: self._on_checkbox_toggled(n, c))

            lbl_min = QLabel("mín:")
            lbl_min.setStyleSheet("color: #8AA094; font-size: 11px;")
            lbl_min.setFixedWidth(28)

            spin = QDoubleSpinBox()
            spin.setObjectName("spin_min")
            spin.setRange(0, 5000)
            spin.setDecimals(0)
            spin.setSingleStep(10)
            spin.setSuffix(" g")
            spin.setFixedWidth(72)
            spin.setValue(self._min_quantities.get(name, 0))
            spin.setEnabled(checked)
            spin.valueChanged.connect(lambda v, n=name: self._on_min_changed(n, v))

            w_layout.addWidget(chk, stretch=1)
            w_layout.addWidget(lbl_min)
            w_layout.addWidget(spin)

            self.ingredient_list.setItemWidget(item, widget)
            self._ingredient_widgets[name] = (chk, spin)

    def _build_settings_panel(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Base size
        size_box = QGroupBox("Tamanho da Base")
        size_layout = QHBoxLayout(size_box)
        size_layout.addWidget(QLabel("Total (g):"))
        self.spin_base = QDoubleSpinBox()
        self.spin_base.setRange(100, 10000)
        self.spin_base.setValue(1000)
        self.spin_base.setSingleStep(100)
        self.spin_base.setDecimals(0)
        size_layout.addWidget(self.spin_base)
        size_layout.addStretch()
        layout.addWidget(size_box)

        # KPI ranges
        kpi_box = QGroupBox("Metas de KPI  (editáveis)")
        kpi_layout = QVBoxLayout(kpi_box)
        self.kpi_table = self._build_kpi_table()
        kpi_layout.addWidget(self.kpi_table)
        layout.addWidget(kpi_box, stretch=1)

        # Solve button
        self.btn_solve = QPushButton("Calcular Receita")
        self.btn_solve.setObjectName("btn_solve")
        self.btn_solve.clicked.connect(self._on_solve)
        layout.addWidget(self.btn_solve)

        return container

    def _build_kpi_table(self) -> QTableWidget:
        kpis = list(KPI_DEFAULTS.keys())
        table = QTableWidget(len(kpis), 3)
        table.setHorizontalHeaderLabels(["KPI", "Mín", "Máx"])
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(1, 80)
        table.setColumnWidth(2, 80)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        self._kpi_spins = {}
        for row_idx, kpi in enumerate(kpis):
            lo, hi = KPI_DEFAULTS[kpi]

            label_item = QTableWidgetItem(KPI_LABELS[kpi])
            label_item.setForeground(QColor("#113516"))
            table.setItem(row_idx, 0, label_item)

            spin_lo = QDoubleSpinBox()
            spin_lo.setRange(0, 500)
            spin_lo.setDecimals(1)
            spin_lo.setValue(lo)
            spin_lo.setFrame(False)

            spin_hi = QDoubleSpinBox()
            spin_hi.setRange(0, 500)
            spin_hi.setDecimals(1)
            spin_hi.setValue(hi)
            spin_hi.setFrame(False)

            table.setCellWidget(row_idx, 1, spin_lo)
            table.setCellWidget(row_idx, 2, spin_hi)
            self._kpi_spins[kpi] = (spin_lo, spin_hi)

        table.verticalHeader().setDefaultSectionSize(36)
        table.setMaximumHeight(36 * len(kpis) + 34)
        return table

    def _build_results_panel(self) -> QWidget:
        box = QGroupBox("Resultado")
        layout = QVBoxLayout(box)

        # Ingredient quantities
        qty_label = QLabel("Ingredientes")
        qty_label.setStyleSheet("color: #236C45; font-weight: bold;")
        layout.addWidget(qty_label)

        self.qty_table = QTableWidget(0, 3)
        self.qty_table.setHorizontalHeaderLabels(["Ingrediente", "g", "%"])
        self.qty_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.qty_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.qty_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.qty_table.setColumnWidth(1, 70)
        self.qty_table.setColumnWidth(2, 60)
        self.qty_table.verticalHeader().setVisible(False)
        self.qty_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.qty_table.setAlternatingRowColors(True)
        layout.addWidget(self.qty_table, stretch=1)

        # KPI actuals
        kpi_label = QLabel("KPIs")
        kpi_label.setStyleSheet("color: #236C45; font-weight: bold;")
        layout.addWidget(kpi_label)

        self.kpi_result_table = QTableWidget(0, 4)
        self.kpi_result_table.setHorizontalHeaderLabels(["KPI", "Meta", "Atual", "Status"])
        self.kpi_result_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.kpi_result_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.kpi_result_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.kpi_result_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.kpi_result_table.setColumnWidth(1, 90)
        self.kpi_result_table.setColumnWidth(2, 70)
        self.kpi_result_table.setColumnWidth(3, 80)
        self.kpi_result_table.verticalHeader().setVisible(False)
        self.kpi_result_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.kpi_result_table.setAlternatingRowColors(True)
        self.kpi_result_table.setMaximumHeight(220)
        layout.addWidget(self.kpi_result_table)

        return box

    def _build_nutrition_panel(self) -> QWidget:
        box = QGroupBox("Tabela Nutricional")
        layout = QVBoxLayout(box)

        # Serving size control
        serving_row = QHBoxLayout()
        serving_row.addWidget(QLabel("Porção:"))
        self.spin_serving = QDoubleSpinBox()
        self.spin_serving.setRange(10, 1000)
        self.spin_serving.setValue(200)
        self.spin_serving.setDecimals(0)
        self.spin_serving.setSuffix(" g")
        self.spin_serving.setSingleStep(10)
        self.spin_serving.valueChanged.connect(self._refresh_nutrition)
        serving_row.addWidget(self.spin_serving)
        serving_row.addStretch()
        layout.addLayout(serving_row)

        # Placeholder shown before first solve
        self.lbl_nutrition_status = QLabel("Calcule uma receita para ver a tabela nutricional.")
        self.lbl_nutrition_status.setStyleSheet(f"color: {MUTED}; font-size: 12px;")
        self.lbl_nutrition_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_nutrition_status)

        # ANVISA table
        self.nutrition_table = QTableWidget(len(ANVISA_NUTRIENTS), 4)
        self.nutrition_table.setHorizontalHeaderLabels(["Nutriente", "100 g", "Porção", "%VD*"])
        self.nutrition_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.nutrition_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.nutrition_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.nutrition_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.nutrition_table.setColumnWidth(1, 110)
        self.nutrition_table.setColumnWidth(2, 110)
        self.nutrition_table.setColumnWidth(3, 55)
        self.nutrition_table.verticalHeader().setVisible(False)
        self.nutrition_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.nutrition_table.setAlternatingRowColors(True)
        self.nutrition_table.setVisible(False)
        layout.addWidget(self.nutrition_table, stretch=1)

        # Footnote
        footnote = QLabel(
            "* % Valores Diários com base em uma dieta de 2.000 kcal ou 8.400 kJ. "
            "Seus valores diários podem ser maiores ou menores dependendo de suas necessidades energéticas."
        )
        footnote.setStyleSheet("color: #8AA094; font-size: 10px;")
        footnote.setWordWrap(True)
        layout.addWidget(footnote)

        return box

    def _update_nutrition_table(self, quantities: dict, base_size: float):
        self._last_nutrition_quantities = quantities
        self._last_nutrition_base_size = base_size
        self._refresh_nutrition()

    def _refresh_nutrition(self):
        if self._last_nutrition_quantities is None:
            return

        quantities = self._last_nutrition_quantities
        base_size  = self._last_nutrition_base_size
        serving    = self.spin_serving.value()
        df         = self.df_all

        # Compute total of each nutrient for the whole base (base_size grams)
        totals: dict[str, float] = {}
        for col, *_ in ANVISA_NUTRIENTS:
            if col not in df.columns:
                totals[col] = 0.0
                continue
            total = 0.0
            for name, grams in quantities.items():
                rows = df[df["name"] == name]
                if not rows.empty:
                    total += grams * float(rows.iloc[0][col]) / 100
            totals[col] = total

        per_100g = {col: v / base_size * 100   for col, v in totals.items()}
        per_srv  = {col: v / base_size * serving for col, v in totals.items()}

        # Update "Porção" column header with actual grams
        self.nutrition_table.setHorizontalHeaderItem(
            2, QTableWidgetItem(f"{serving:.0f} g")
        )

        for row_idx, (col, label, unit, vd_ref, indent, no_vd) in enumerate(ANVISA_NUTRIENTS):
            v100 = per_100g[col]
            vsrv = per_srv[col]

            # Nutrient label (indented sub-items)
            display_label = f"   {label}" if indent else label
            label_item = QTableWidgetItem(display_label)
            if indent:
                label_item.setForeground(QColor("#475569"))
            self.nutrition_table.setItem(row_idx, 0, label_item)

            # Format values
            if col == "kcal":
                str_100g = f"{v100:.0f} kcal"
                str_srv  = f"{vsrv:.0f} kcal"
            elif unit == "mg":
                str_100g = f"{v100:.0f} mg"
                str_srv  = f"{vsrv:.0f} mg"
            else:
                str_100g = f"{v100:.1f} g"
                str_srv  = f"{vsrv:.1f} g"

            self.nutrition_table.setItem(row_idx, 1, _right_item(str_100g))
            self.nutrition_table.setItem(row_idx, 2, _right_item(str_srv))

            # %VD
            if no_vd or vd_ref is None:
                vd_text = "—" if no_vd else ""
                vd_item = QTableWidgetItem(vd_text)
                vd_item.setForeground(QColor(MUTED))
                vd_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.nutrition_table.setItem(row_idx, 3, vd_item)
            else:
                pct = vsrv / vd_ref * 100
                self.nutrition_table.setItem(row_idx, 3, _right_item(f"{pct:.0f}%"))

        self.lbl_nutrition_status.setVisible(False)
        self.nutrition_table.setVisible(True)

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _update_selected_count(self):
        n = len(self._checked_names)
        self.lbl_selected_count.setText(f"{n} selecionado{'s' if n != 1 else ''}")

    def _on_checkbox_toggled(self, name: str, checked: bool):
        if checked:
            self._checked_names.add(name)
        else:
            self._checked_names.discard(name)
        if name in self._ingredient_widgets:
            self._ingredient_widgets[name][1].setEnabled(checked)
        self._update_selected_count()

    def _on_min_changed(self, name: str, value: float):
        if value > 0:
            self._min_quantities[name] = value
        else:
            self._min_quantities.pop(name, None)

    def _filter_ingredients(self, text: str):
        self._populate_ingredient_list(text)

    def _deselect_all(self):
        self._checked_names.clear()
        self._populate_ingredient_list(self.search_bar.text())
        self._update_selected_count()

    def _throb_then(self, callback):
        """Show the Windows-style spinner page for 2 s, then call callback."""
        self.stacked.setCurrentIndex(1)
        self._throbber.start()

        def _done():
            self._throbber.stop()
            callback()

        QTimer.singleShot(500, _done)

    def _on_load_recipe(self):
        recipes = data.load_recipes()
        if not recipes:
            QMessageBox.information(self, "Receitas", "Nenhuma receita salva ainda.")
            return

        names = [f"#{r['id']} — {r['name']}  ({r['date']})" for r in recipes]
        choice, ok = QInputDialog.getItem(self, "Carregar Receita", "Selecione uma receita:", names, 0, False)
        if not ok:
            return

        recipe = recipes[names.index(choice)]

        self._checked_names.clear()
        self._min_quantities.clear()

        for name, grams in recipe["ingredients"].items():
            if grams > 0:
                self._checked_names.add(name)
                self._min_quantities[name] = round(grams, 1)

        self.spin_base.setValue(recipe["base_size"])
        self._populate_ingredient_list(self.search_bar.text())
        self._update_selected_count()

        # Build result and go straight to the results tab
        kpi_ranges = {
            kpi: (sp_lo.value(), sp_hi.value())
            for kpi, (sp_lo, sp_hi) in self._kpi_spins.items()
        }
        result = {"quantities": recipe["ingredients"], "kpis": recipe["kpis"], "violations": {}}
        self._last_result = result
        self._last_base_size = recipe["base_size"]
        self._last_kpi_ranges = kpi_ranges
        self._display_results(result, recipe["base_size"], kpi_ranges)

        # Override status with the recipe name
        self.lbl_status.setText(f"#{recipe['id']} — {recipe['name']}")
        self.lbl_status.setStyleSheet(f"color: {GREEN}; font-weight: bold;")

        self._throb_then(lambda: self.stacked.setCurrentIndex(2))

    def _on_solve(self):
        selected_names = self._get_selected_names()
        if len(selected_names) < 2:
            QMessageBox.warning(self, "Atenção", "Selecione pelo menos 2 ingredientes.")
            return

        df_selected = self.df_all[self.df_all["name"].isin(selected_names)].copy()
        base_size = self.spin_base.value()
        kpi_ranges = {
            kpi: (spin_lo.value(), spin_hi.value())
            for kpi, (spin_lo, spin_hi) in self._kpi_spins.items()
        }
        min_qty = {
            name: self._min_quantities[name]
            for name in selected_names
            if self._min_quantities.get(name, 0) > 0
        } or None

        result = solve(df_selected, base_size, kpi_ranges, min_quantities=min_qty)

        if result is None:
            flex = solve_flexible(df_selected, base_size, kpi_ranges, min_quantities=min_qty)
            n_viol = sum(flex["violations"].values())

            self._last_result = flex
            self._last_base_size = base_size
            self._last_kpi_ranges = kpi_ranges

            self._display_results(flex, base_size, kpi_ranges)

            self.lbl_status.setText(
                f"Melhor resultado possível — {n_viol} KPI(s) fora da meta."
            )
            self.lbl_status.setStyleSheet(f"color: {YELLOW}; font-weight: bold;")

            issues = diagnose(df_selected, self.df_all, base_size, kpi_ranges,
                              min_quantities=min_qty)
            if issues:
                lines = ["\nSugestões para atingir todos os KPIs:"]
                for issue in issues:
                    dir_labels = " / ".join(
                        f"{KPI_LABELS[k]} muito {issue['directions'][k]}"
                        for k in issue["kpis"]
                    )
                    suggestions = ", ".join(s["name"] for s in issue["suggestions"])
                    lines.append(f"  • {dir_labels}")
                    lines.append(f"    Considere adicionar: {suggestions}")
                self.lbl_status.setText(self.lbl_status.text() + "\n".join(lines))

            self._throb_then(lambda: self.stacked.setCurrentIndex(2))
            return

        self._last_result = result
        self._last_base_size = base_size
        self._last_kpi_ranges = kpi_ranges
        self._display_results(result, base_size, kpi_ranges)
        self._throb_then(lambda: self.stacked.setCurrentIndex(2))

    def _display_diagnosis(self, issues: list):
        self.qty_table.setRowCount(0)
        self.kpi_result_table.setRowCount(0)

        if not issues:
            self.lbl_status.setText(
                "Sem solução. Tente adicionar mais ingredientes ou ampliar os limites dos KPIs."
            )
            return

        lines = ["Problemas encontrados:"]
        for issue in issues:
            kpi_names = " + ".join(KPI_LABELS[k] for k in issue["kpis"])
            dir_labels = " / ".join(
                f"{KPI_LABELS[k]} muito {issue['directions'][k]}"
                for k in issue["kpis"]
            )
            suggestion_names = ", ".join(s["name"] for s in issue["suggestions"])
            lines.append(f"  • {dir_labels}")
            lines.append(f"    Considere adicionar: {suggestion_names}")

        self.lbl_status.setText("\n".join(lines))
        self.lbl_status.setStyleSheet(f"color: {YELLOW}; font-weight: bold;")
        self.lbl_status.setWordWrap(True)

    def _display_results(self, result: dict, base_size: float, kpi_ranges: dict):
        self.lbl_status.setText("Receita encontrada!")
        self.lbl_status.setStyleSheet(f"color: {GREEN}; font-weight: bold;")

        quantities = result["quantities"]
        total = sum(quantities.values())

        # Ingredient table
        self.qty_table.setRowCount(len(quantities))
        for row_idx, (name, grams) in enumerate(
            sorted(quantities.items(), key=lambda kv: kv[1], reverse=True)
        ):
            pct = grams / base_size * 100
            self.qty_table.setItem(row_idx, 0, QTableWidgetItem(name))
            self.qty_table.setItem(row_idx, 1, _right_item(f"{grams:.1f}"))
            self.qty_table.setItem(row_idx, 2, _right_item(f"{pct:.1f}%"))

        # KPI table
        kpis = list(kpi_ranges.keys())
        self.kpi_result_table.setRowCount(len(kpis))
        for row_idx, kpi in enumerate(kpis):
            lo, hi = kpi_ranges[kpi]
            actual = result["kpis"].get(kpi, 0.0)
            in_range = lo <= actual <= hi

            self.kpi_result_table.setItem(row_idx, 0, QTableWidgetItem(KPI_LABELS[kpi]))
            self.kpi_result_table.setItem(row_idx, 1, _right_item(f"{lo}–{hi}"))
            actual_item = _right_item(f"{actual:.2f}")
            actual_item.setForeground(QColor(GREEN if in_range else RED))
            self.kpi_result_table.setItem(row_idx, 2, actual_item)
            status_item = QTableWidgetItem("OK" if in_range else "Fora")
            status_item.setForeground(QColor(GREEN if in_range else RED))
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.kpi_result_table.setItem(row_idx, 3, status_item)

        self._update_nutrition_table(quantities, base_size)
        self.btn_save.setEnabled(True)

    def _prompt_save(self, result: dict, base_size: float, kpi_ranges: dict):
        existing = data.load_recipes()
        placeholder = f"Gelato #{len(existing) + 1}"
        name, ok = QInputDialog.getText(
            self,
            "Salvar Receita",
            "Nome da receita:",
            text=placeholder,
        )
        if not ok:
            return
        if not name.strip():
            name = placeholder
        recipe_id = data.save_recipe(name.strip(), base_size, result["quantities"], result["kpis"])
        QMessageBox.information(self, "Salvo", f'Receita "{name}" salva com ID #{recipe_id}.')

    def _on_save(self):
        if self._last_result:
            self._prompt_save(self._last_result, self._last_base_size, self._last_kpi_ranges)

    def _get_selected_names(self) -> list[str]:
        return list(self._checked_names)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _right_item(text: str) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    return item
