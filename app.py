import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QListWidget, QListWidgetItem, QPushButton, QTableWidget,
    QTableWidgetItem, QLineEdit, QGroupBox, QDoubleSpinBox, QMessageBox,
    QHeaderView, QSplitter, QInputDialog, QAbstractItemView, QCheckBox,
    QStackedWidget,
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont, QColor

import data
from solver import solve, solve_flexible, diagnose, KPI_DEFAULTS, KPI_LABELS

# ── Sagui brand palette ───────────────────────────────────────────────────────
# #C5A04D brass-gold  |  #236C45 deep green  |  #113516 dark forest green
# #F2CD24 vibrant yellow  |  #E3C988 light golden  |  #FFFFFF white
STYLE = """
QMainWindow, QWidget {
    background-color: #FFFFFF;
    color: #113516;
    font-family: 'Segoe UI';
    font-size: 13px;
}
QGroupBox {
    background-color: #FFFFFF;
    border: 1px solid #E3C988;
    border-radius: 8px;
    margin-top: 14px;
    padding: 10px 8px 8px 8px;
    font-weight: bold;
    color: #236C45;
    font-size: 13px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    background-color: #FFFFFF;
}
QPushButton {
    background-color: #F5EDD4;
    color: #113516;
    border: 1px solid #E3C988;
    border-radius: 6px;
    padding: 6px 14px;
}
QPushButton:hover {
    background-color: #EAF4EE;
    border-color: #236C45;
    color: #236C45;
}
QPushButton#btn_solve {
    background-color: #236C45;
    color: #FFFFFF;
    font-weight: bold;
    font-size: 15px;
    padding: 10px;
    border: none;
    border-radius: 8px;
}
QPushButton#btn_solve:hover  { background-color: #1a5234; }
QPushButton#btn_solve:pressed { background-color: #113516; }
QPushButton#btn_save {
    background-color: #C5A04D;
    color: #FFFFFF;
    font-weight: bold;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
}
QPushButton#btn_save:hover  { background-color: #B08A3A; }
QPushButton#btn_select_all, QPushButton#btn_deselect_all {
    font-size: 11px;
    padding: 4px 10px;
}
QTableWidget {
    background-color: #FFFFFF;
    border: 1px solid #E3C988;
    border-radius: 6px;
    gridline-color: #F5EDD4;
    selection-background-color: #EAF4EE;
    color: #113516;
}
QTableWidget::item { padding: 4px 8px; }
QHeaderView::section {
    background-color: #FAFAF7;
    color: #236C45;
    border: none;
    border-right: 1px solid #E3C988;
    border-bottom: 1px solid #E3C988;
    padding: 6px 8px;
    font-weight: bold;
}
QListWidget {
    background-color: #FFFFFF;
    border: 1px solid #E3C988;
    border-radius: 6px;
    color: #113516;
}
QListWidget::item { padding: 3px 6px; }
QListWidget::item:hover { background-color: #EAF4EE; }
QDoubleSpinBox, QLineEdit {
    background-color: #FFFFFF;
    border: 1px solid #E3C988;
    border-radius: 4px;
    padding: 4px 8px;
    color: #113516;
}
QDoubleSpinBox:focus, QLineEdit:focus { border-color: #236C45; }
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button { width: 0px; height: 0px; }
QScrollBar:vertical {
    background: #F5EDD4;
    width: 6px;
    border-radius: 3px;
}
QScrollBar::handle:vertical {
    background: #E3C988;
    border-radius: 3px;
    min-height: 20px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QSplitter::handle { background-color: #E3C988; width: 2px; }
QCheckBox { spacing: 6px; background: transparent; }
QCheckBox::indicator {
    width: 14px; height: 14px;
    border: 1px solid #E3C988;
    border-radius: 3px;
    background-color: #FFFFFF;
}
QCheckBox::indicator:checked {
    background-color: #236C45;
    border-color: #236C45;
}
QDoubleSpinBox#spin_min {
    background-color: #FAFAF7;
    border: 1px solid #E3C988;
    border-radius: 3px;
    color: #64748b;
    font-size: 11px;
    padding: 1px 4px;
}
QDoubleSpinBox#spin_min:disabled {
    color: #E3C988;
    background-color: #FAFAF7;
    border-color: #F5EDD4;
}
"""

GREEN  = "#236C45"
RED    = "#dc2626"
YELLOW = "#C5A04D"
MUTED  = "#94a3b8"

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


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sagui Gelatos — Balanceador de Receitas")
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
        main_layout = QVBoxLayout(root)
        main_layout.setContentsMargins(16, 12, 16, 12)
        main_layout.setSpacing(10)

        # Header
        header = QLabel("Sagui Gelatos")
        header.setStyleSheet("font-size: 26px; font-weight: bold; color: #C5A04D;")
        sub = QLabel("Balanceador de Base — powered by Linear Programming")
        sub.setStyleSheet("color: #94a3b8; font-size: 12px;")
        main_layout.addWidget(header)
        main_layout.addWidget(sub)

        self.stacked = QStackedWidget()
        main_layout.addWidget(self.stacked, stretch=1)
        self.stacked.addWidget(self._build_main_page())
        self.stacked.addWidget(self._build_results_page())

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
        self.lbl_selected_count.setStyleSheet("color: #64748b; font-size: 11px;")
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
            lbl_min.setStyleSheet("color: #94a3b8; font-size: 11px;")
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
        self.nutrition_table.setVisible(False)
        layout.addWidget(self.nutrition_table, stretch=1)

        # Footnote
        footnote = QLabel(
            "* % Valores Diários com base em uma dieta de 2.000 kcal ou 8.400 kJ. "
            "Seus valores diários podem ser maiores ou menores dependendo de suas necessidades energéticas."
        )
        footnote.setStyleSheet("color: #94a3b8; font-size: 10px;")
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

            self.stacked.setCurrentIndex(1)
            return

        self._last_result = result
        self._last_base_size = base_size
        self._last_kpi_ranges = kpi_ranges
        self._display_results(result, base_size, kpi_ranges)
        self.stacked.setCurrentIndex(1)

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
