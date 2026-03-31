"""
research_view.py
Research explorer panel — plugs into the app's QStackedWidget (index 3).
"""

import math

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QGroupBox, QFrame, QListWidget, QListWidgetItem,
    QSplitter, QScrollArea, QComboBox, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QSizePolicy, QCheckBox,
)
from PyQt6.QtCore import Qt, QSize, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QFont

import research_scorer
from solver import KPI_LABELS as SOLVER_KPI_LABELS

# ── Palette (mirrors app.py) ──────────────────────────────────────────────────
GREEN  = "#236C45"
GOLD   = "#C5A04D"
RED    = "#C0392B"
BLUE   = "#4A90D9"
PURPLE = "#7B5EA7"
MUTED  = "#8AA094"
DARK   = "#1C2E20"
BG     = "#EDE8D8"
CARD   = "#FAFAF7"
BORDER = "#E3C988"

KPI_RANGES = research_scorer.KPI_RANGES

INGREDIENT_PALETTE = [
    "#236C45", "#C5A04D", "#4A90D9", "#7B5EA7",
    "#E67E22", "#16A085", "#C0392B", "#2980B9",
    "#8E44AD", "#27AE60", "#D35400", "#1ABC9C",
]


# ── Small reusable widgets ────────────────────────────────────────────────────

class _ScoreBar(QWidget):
    """Thin rounded progress bar (0–1)."""

    def __init__(self, value: float, color: str, height: int = 7, parent=None):
        super().__init__(parent)
        self._value = max(0.0, min(1.0, value))
        self._color = QColor(color)
        self.setFixedHeight(height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setStyleSheet("background: transparent;")

    def set_value(self, value: float, color: str | None = None):
        self._value = max(0.0, min(1.0, value))
        if color:
            self._color = QColor(color)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        r = h / 2

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#DDD0A0"))
        p.drawRoundedRect(0, 0, w, h, r, r)

        if self._value > 0:
            p.setBrush(self._color)
            p.drawRoundedRect(0, 0, max(int(w * self._value), h), h, r, r)

        p.end()


class _IngredientBar(QWidget):
    """Horizontal bar for ingredient proportion in the detail view."""

    def __init__(self, name: str, grams: float, proportion: float,
                 color: str, vestigial: bool = False, parent=None):
        super().__init__(parent)
        self._name       = name
        self._grams      = grams
        self._proportion = proportion
        self._color      = QColor(color)
        self._vestigial  = vestigial
        self.setFixedHeight(30)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setStyleSheet("background: transparent;")
        if vestigial:
            self.setToolTip("⚠ Quantidade vestigial (< 5 g) — possível artefacto do solver")

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # Track background
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#F0EBD8"))
        p.drawRoundedRect(0, 6, w, h - 12, 3, 3)

        # Fill
        fill_w = max(int(w * self._proportion), 6)
        alpha_color = QColor(self._color)
        alpha_color.setAlpha(200 if not self._vestigial else 90)
        p.setBrush(alpha_color)
        p.drawRoundedRect(0, 6, fill_w, h - 12, 3, 3)

        # Name (left)
        name_color = QColor("#9B8B7A") if self._vestigial else QColor(DARK)
        p.setPen(name_color)
        p.setFont(QFont("Segoe UI", 10))
        p.drawText(8, 0, w - 120, h,
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                   self._name)

        # Grams + % (right)
        p.setPen(QColor(MUTED))
        p.setFont(QFont("Segoe UI", 9))
        p.drawText(w - 115, 0, 110, h,
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                   f"{self._grams:.0f} g  ({self._proportion * 100:.0f}%)")

        p.end()


# ── Recipe list card ──────────────────────────────────────────────────────────

class _RecipeCard(QWidget):
    """Compact recipe summary for the list panel."""

    def __init__(self, recipe: dict, rank: int, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        scores  = recipe["_scores"]
        per_100 = recipe["nutrition"]["per_100g"]

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 5, 32, 4)
        layout.setSpacing(3)

        # Row 1: rank + name + total %
        top = QHBoxLayout()
        top.setSpacing(6)

        lbl_rank = QLabel(f"#{rank}")
        lbl_rank.setFixedWidth(28)
        lbl_rank.setStyleSheet(f"color: {MUTED}; font-size: 10px; background: transparent;")

        lbl_name = QLabel(recipe["name"])
        lbl_name.setStyleSheet(f"font-weight: bold; color: {DARK}; font-size: 12px; background: transparent;")
        lbl_name.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        total_pct = int(scores["total"] * 100)
        score_color = GREEN if total_pct >= 65 else (GOLD if total_pct >= 40 else RED)
        lbl_score = QLabel(f"{total_pct}%")
        lbl_score.setFixedWidth(42)
        lbl_score.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lbl_score.setStyleSheet(
            f"color: {score_color}; font-weight: bold; font-size: 12px; background: transparent;"
        )

        top.addWidget(lbl_rank)
        top.addWidget(lbl_name, stretch=1)
        if recipe.get("source") == "saved":
            lbl_saved = QLabel("★")
            lbl_saved.setStyleSheet(
                f"color: {GOLD}; font-size: 11px; background: transparent;"
            )
            lbl_saved.setToolTip("Receita salva no app")
            top.addWidget(lbl_saved)
        top.addWidget(lbl_score)
        layout.addLayout(top)

        # Score bar
        layout.addWidget(_ScoreBar(scores["total"], score_color, height=5))

        # Row 2: mini metrics
        metrics = QHBoxLayout()
        metrics.setSpacing(12)

        protein  = per_100.get("protein", 0)
        bad_fat  = per_100.get("sat_fat", 0) + per_100.get("trans_fat", 0)
        sugar    = per_100.get("sugars_added", 0)

        p_color = GREEN if protein >= 5  else (GOLD if protein >= 2 else MUTED)
        f_color = GREEN if bad_fat == 0  else (GOLD if bad_fat < 3  else RED)
        s_color = GREEN if sugar == 0    else (GOLD if sugar < 10   else RED)

        for text, color in [
            (f"💪 {protein:.1f}g", p_color),
            (f"🫀 {bad_fat:.1f}g",  f_color),
            (f"🍬 {sugar:.1f}g",   s_color),
        ]:
            lbl = QLabel(text)
            lbl.setStyleSheet(f"color: {color}; font-size: 10px; background: transparent;")
            metrics.addWidget(lbl)

        # Warning count badge
        warn_count = sum(1 for lvl, _ in recipe["_warnings"] if lvl == "warn")
        if warn_count:
            lbl_w = QLabel(f"⚠ {warn_count}")
            lbl_w.setStyleSheet(f"color: {GOLD}; font-size: 10px; background: transparent;")
            metrics.addWidget(lbl_w)

        metrics.addStretch()
        layout.addLayout(metrics)


# ── Detail panel ──────────────────────────────────────────────────────────────

class _DetailPanel(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self._body = QWidget()
        self._body.setStyleSheet("background: transparent;")
        self._layout = QVBoxLayout(self._body)
        self._layout.setContentsMargins(12, 10, 12, 16)
        self._layout.setSpacing(12)

        self._show_empty()

        self._scroll.setWidget(self._body)
        outer.addWidget(self._scroll)

    # ── helpers ───────────────────────────────────────────────────────────────

    def _clear(self):
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _show_empty(self):
        self._clear()
        self._layout.addStretch()
        lbl = QLabel("← Selecione uma receita para inspecionar")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(f"color: {MUTED}; font-size: 14px; background: transparent;")
        self._layout.addWidget(lbl)
        self._layout.addStretch()

    @staticmethod
    def _divider() -> QFrame:
        d = QFrame()
        d.setFrameShape(QFrame.Shape.HLine)
        d.setFixedHeight(1)
        d.setStyleSheet(f"background-color: {BORDER}; border: none;")
        return d

    @staticmethod
    def _make_table(rows: int, headers: list[str],
                    stretch_col: int = 0, fixed_cols: dict | None = None) -> QTableWidget:
        tbl = QTableWidget(rows, len(headers))
        tbl.setHorizontalHeaderLabels(headers)
        tbl.verticalHeader().setVisible(False)
        tbl.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        tbl.setAlternatingRowColors(True)
        tbl.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        tbl.horizontalHeader().setSectionResizeMode(
            stretch_col, QHeaderView.ResizeMode.Stretch
        )
        if fixed_cols:
            for col, width in fixed_cols.items():
                tbl.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.Fixed)
                tbl.setColumnWidth(col, width)
        tbl.verticalHeader().setDefaultSectionSize(32)
        tbl.setFixedHeight(rows * 32 + 46)
        tbl.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        tbl.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        tbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        return tbl

    # ── main loader ───────────────────────────────────────────────────────────

    def load_recipe(self, recipe: dict):
        self._clear()
        self._scroll.verticalScrollBar().setValue(0)

        scores      = recipe["_scores"]
        warnings    = recipe["_warnings"]
        nutrition   = recipe["nutrition"]
        ingredients = recipe["ingredients"]
        kpis        = recipe.get("kpis", {})

        # ── Header ────────────────────────────────────────────────────────────
        lbl_name = QLabel(recipe["name"])
        lbl_name.setStyleSheet(
            f"font-size: 18px; font-weight: bold; color: {DARK}; background: transparent;"
        )
        lbl_date = QLabel(recipe["date"])
        lbl_date.setStyleSheet(f"color: {MUTED}; font-size: 11px; background: transparent;")
        self._layout.addWidget(lbl_name)
        self._layout.addWidget(lbl_date)
        self._layout.addWidget(self._divider())

        # ── Score breakdown ───────────────────────────────────────────────────
        score_box = QGroupBox("Pontuação")
        sb_layout = QVBoxLayout(score_box)
        sb_layout.setSpacing(7)

        total_pct   = int(scores["total"] * 100)
        total_color = GREEN if total_pct >= 65 else (GOLD if total_pct >= 40 else RED)

        header_row = QHBoxLayout()
        lbl_total = QLabel(f"Total: {total_pct}%")
        lbl_total.setStyleSheet(
            f"font-size: 15px; font-weight: bold; color: {total_color};"
            " background: transparent; border: none;"
        )
        header_row.addWidget(lbl_total)
        header_row.addStretch()
        sb_layout.addLayout(header_row)

        dims = [
            ("💪  Proteína",          scores.get("protein", 0),  GREEN),
            ("🍬  Açúcar adicionado", scores.get("sugar",   0),  GOLD),
            ("🫀  Gordura Ruim",      scores.get("bad_fat", 0),  BLUE),
            ("⚖  Equilíbrio",        scores.get("balance", 0),  PURPLE),
        ]
        for dim_label, dim_score, dim_color in dims:
            row = QHBoxLayout()
            row.setSpacing(8)

            lbl = QLabel(dim_label)
            lbl.setFixedWidth(170)
            lbl.setStyleSheet(
                f"background: transparent; border: none; color: {DARK}; font-size: 12px;"
            )
            bar = _ScoreBar(dim_score, dim_color, height=8)
            pct = QLabel(f"{int(dim_score * 100)}%")
            pct.setFixedWidth(34)
            pct.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            pct.setStyleSheet(
                f"color: {dim_color}; font-size: 11px; font-weight: bold;"
                " background: transparent; border: none;"
            )
            row.addWidget(lbl)
            row.addWidget(bar, stretch=1)
            row.addWidget(pct)
            sb_layout.addLayout(row)

        self._layout.addWidget(score_box)

        # ── Warnings / signals ────────────────────────────────────────────────
        if warnings:
            warn_box = QGroupBox("Diagnóstico")
            wl = QVBoxLayout(warn_box)
            wl.setSpacing(4)
            for level, msg in warnings:
                icon  = "✔" if level == "good" else "⚠"
                color = GREEN if level == "good" else GOLD
                lbl   = QLabel(f"{icon}  {msg}")
                lbl.setWordWrap(True)
                lbl.setStyleSheet(
                    f"color: {color}; font-size: 12px; background: transparent; border: none;"
                )
                wl.addWidget(lbl)
            self._layout.addWidget(warn_box)

        # ── Ingredient distribution ───────────────────────────────────────────
        ing_box = QGroupBox("Composição")
        il = QVBoxLayout(ing_box)
        il.setSpacing(4)

        total_g = sum(ingredients.values())
        sorted_ings = sorted(ingredients.items(), key=lambda x: x[1], reverse=True)

        for idx, (name, grams) in enumerate(sorted_ings):
            prop = grams / total_g if total_g > 0 else 0
            color = INGREDIENT_PALETTE[idx % len(INGREDIENT_PALETTE)]
            vestigial = grams < research_scorer.NEGLIGIBLE_GRAMS
            bar = _IngredientBar(name, grams, prop, color, vestigial)
            il.addWidget(bar)

        self._layout.addWidget(ing_box)

        # ── Nutrition table ───────────────────────────────────────────────────
        nutr_box = QGroupBox("Informação Nutricional")
        nl = QVBoxLayout(nutr_box)

        # ANVISA RDC 429/2020 daily reference values (None = no established VD)
        VD = {
            "kcal":         2000,
            "carb":          300,
            "sugars_total":   50,
            "sugars_added":   50,
            "fat":            65,
            "sat_fat":        20,
            "trans_fat":    None,
            "fiber":          25,
            "protein":        50,
            "sodium":       2400,
        }

        NUTR_ROWS = [
            ("kcal",         "Valor energético",       "kcal"),
            ("carb",         "Carboidratos totais",    "g"),
            ("sugars_total", "  Açúcares totais",      "g"),
            ("sugars_added", "  Açúcares adicionados", "g"),
            ("fat",          "Gorduras totais",        "g"),
            ("sat_fat",      "  Gorduras saturadas",   "g"),
            ("trans_fat",    "  Gorduras trans",       "g"),
            ("fiber",        "Fibra alimentar",        "g"),
            ("protein",      "Proteínas",              "g"),
            ("sodium",       "Sódio",                  "mg"),
        ]

        tbl = self._make_table(
            len(NUTR_ROWS), ["Nutriente", "por 100 g", "por 200 g", "% VD*"],
            stretch_col=0, fixed_cols={1: 100, 2: 100, 3: 68}
        )

        per_100 = nutrition["per_100g"]
        per_srv = nutrition["per_serving"]

        HIGHLIGHT_GOOD = {"protein", "fiber"}
        HIGHLIGHT_BAD  = {"sugars_added", "sat_fat", "trans_fat"}

        for i, (key, label, unit) in enumerate(NUTR_ROWS):
            v100 = per_100.get(key, 0)
            vsrv = per_srv.get(key, 0)
            vd   = VD.get(key)
            vd_str = f"{vsrv / vd * 100:.0f} %" if vd else "*"

            tbl.setItem(i, 0, QTableWidgetItem(label))
            tbl.setItem(i, 1, QTableWidgetItem(f"{v100:.1f} {unit}"))
            tbl.setItem(i, 2, QTableWidgetItem(f"{vsrv:.1f} {unit}"))
            tbl.setItem(i, 3, QTableWidgetItem(vd_str))

            # Subtle highlight for key nutrients
            if key in HIGHLIGHT_GOOD and v100 > 0:
                for c in (1, 2, 3):
                    tbl.item(i, c).setForeground(QColor(GREEN))
            elif key in HIGHLIGHT_BAD and v100 > 0:
                for c in (1, 2, 3):
                    if tbl.item(i, c):
                        tbl.item(i, c).setForeground(QColor(RED if key == "trans_fat" else GOLD))

        nl.addWidget(tbl)
        footnote = QLabel("* Valores diários de referência com base em dieta de 2000 kcal (ANVISA RDC 429/2020). Gorduras trans não possuem valor de referência.")
        footnote.setWordWrap(True)
        footnote.setStyleSheet(f"font-size: 10px; color: {MUTED}; background: transparent;")
        nl.addWidget(footnote)
        self._layout.addWidget(nutr_box)

        # ── KPI table ─────────────────────────────────────────────────────────
        kpi_box = QGroupBox("KPIs da Receita")
        kl = QVBoxLayout(kpi_box)

        kpi_tbl = self._make_table(
            len(kpis), ["KPI", "Valor", "Meta"],
            stretch_col=0, fixed_cols={1: 80, 2: 100}
        )

        for i, (key, val) in enumerate(kpis.items()):
            lo, hi = KPI_RANGES.get(key, (0, 9999))
            in_range = lo <= val <= hi

            kpi_tbl.setItem(i, 0, QTableWidgetItem(SOLVER_KPI_LABELS.get(key, key)))

            val_item = QTableWidgetItem(f"{val:.2f}")
            val_item.setForeground(QColor(GREEN if in_range else RED))
            val_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            kpi_tbl.setItem(i, 1, val_item)
            kpi_tbl.setItem(i, 2, QTableWidgetItem(f"{lo} – {hi}"))

        kl.addWidget(kpi_tbl)
        self._layout.addWidget(kpi_box)

        self._layout.addStretch()


# ── Background workers ───────────────────────────────────────────────────────

class _LoadWorker(QThread):
    """Just reads research_scored.json — fast."""
    finished = pyqtSignal(list)

    def run(self):
        self.finished.emit(research_scorer.load_scored())


class _ScoreWorker(QThread):
    """Recomputes scores from research.json and saves research_scored.json."""
    finished = pyqtSignal(int)   # emits count of scored recipes

    def run(self):
        self.finished.emit(research_scorer.compute_and_save())


# ── Main ResearchView ─────────────────────────────────────────────────────────

LIST_CAP = 200   # max items rendered in the list at once

class ResearchView(QWidget):
    """Explorador de receitas — index 3 in the app's QStackedWidget."""

    SORT_OPTIONS = [
        ("Pontuação Total",  "total"),
        ("Proteína",         "protein"),
        ("Gord. Ruim",       "bad_fat"),
        ("Sem Açúcar Ad.",   "sugar"),
        ("Equilíbrio",       "balance"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._recipes:       list[dict] = []
        self._filtered:      list[dict] = []
        self._load_worker:   _LoadWorker  | None = None
        self._score_worker:  _ScoreWorker | None = None
        self._setup_ui()

    # ── UI construction ───────────────────────────────────────────────────────

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 8, 14, 14)
        layout.setSpacing(8)

        # Nav bar
        nav = QHBoxLayout()

        lbl_title = QLabel("Explorador de Receitas")
        lbl_title.setStyleSheet(
            f"font-size: 16px; font-weight: bold; color: {GREEN}; background: transparent;"
        )
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._lbl_count = QLabel("")
        self._lbl_count.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._lbl_count.setStyleSheet(f"color: {MUTED}; font-size: 11px; background: transparent;")

        nav.addWidget(lbl_title, stretch=1)
        nav.addWidget(self._lbl_count)
        layout.addLayout(nav)

        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setFixedHeight(1)
        div.setStyleSheet(f"background-color: {BORDER}; border: none;")
        layout.addWidget(div)

        # Splitter: list | detail
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(8)
        splitter.setStyleSheet("QSplitter::handle { background-color: transparent; }")
        splitter.addWidget(self._build_list_panel())
        splitter.addWidget(self._build_detail_panel())
        splitter.setSizes([380, 620])
        layout.addWidget(splitter, stretch=1)

    def _build_list_panel(self) -> QWidget:
        box = QGroupBox("Receitas")
        layout = QVBoxLayout(box)
        layout.setSpacing(6)

        # Search + sort
        controls = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText("Buscar...")
        self._search.setMinimumWidth(120)
        self._search.textChanged.connect(lambda _: self._apply_filter())

        self._sort_combo = QComboBox()
        for label, _ in self.SORT_OPTIONS:
            self._sort_combo.addItem(label)
        self._sort_combo.setFixedWidth(155)
        self._sort_combo.currentIndexChanged.connect(lambda _: self._apply_filter())

        controls.addWidget(self._search, stretch=1)
        controls.addWidget(self._sort_combo)
        layout.addLayout(controls)

        # Buttons row
        self._btn_score = QPushButton("⚙  Atualizar Pontuações")
        self._btn_score.setObjectName("btn_load")
        self._btn_score.setToolTip("Recalcular pontuações a partir do research.json (pode demorar)")
        self._btn_score.clicked.connect(self._start_scoring)
        layout.addWidget(self._btn_score)

        self._lbl_status = QLabel("")
        self._lbl_status.setStyleSheet(f"color: {MUTED}; font-size: 11px; background: transparent;")
        self._lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._lbl_status)

        self._chk_saved_only = QCheckBox("Apenas receitas salvas")
        self._chk_saved_only.setStyleSheet("background: transparent; font-size: 12px;")
        self._chk_saved_only.toggled.connect(lambda _: self._apply_filter())
        layout.addWidget(self._chk_saved_only)

        # List
        self._list = QListWidget()
        self._list.setSpacing(2)
        self._list.currentItemChanged.connect(self._on_selection_changed)
        layout.addWidget(self._list, stretch=1)

        return box

    def _build_detail_panel(self) -> QWidget:
        self._detail = _DetailPanel()
        return self._detail

    # ── Data ──────────────────────────────────────────────────────────────────

    def _load_recipes(self):
        if self._load_worker and self._load_worker.isRunning():
            return
        if not research_scorer.scored_file_exists():
            self._lbl_status.setText("Nenhum arquivo encontrado — clique em Atualizar Pontuações.")
            return
        self._lbl_count.setText("Carregando…")
        self._lbl_status.setText("")
        self._load_worker = _LoadWorker()
        self._load_worker.finished.connect(self._on_recipes_loaded)
        self._load_worker.start()

    def _on_recipes_loaded(self, recipes: list):
        self._recipes = recipes
        self._lbl_count.setText(f"{len(recipes)} receitas")
        self._apply_filter()

    def _start_scoring(self):
        if self._score_worker and self._score_worker.isRunning():
            return
        self._btn_score.setEnabled(False)
        self._lbl_status.setText("Calculando pontuações…")
        self._lbl_count.setText("")
        self._score_worker = _ScoreWorker()
        self._score_worker.finished.connect(self._on_scoring_done)
        self._score_worker.start()

    def _on_scoring_done(self, count: int):
        self._btn_score.setEnabled(True)
        self._lbl_status.setText(f"Pontuações atualizadas — {count} receitas.")
        self._load_recipes()

    def _apply_filter(self):
        query    = self._search.text().lower().strip()
        sort_key = self.SORT_OPTIONS[self._sort_combo.currentIndex()][1]

        saved_only = self._chk_saved_only.isChecked()
        filtered = [r for r in self._recipes
                    if (not query or query in r["name"].lower())
                    and (not saved_only or r.get("source") == "saved")]

        def _per100(r, nutrient):
            return r["nutrition"]["per_100g"].get(nutrient, 0)

        if sort_key == "protein":
            filtered.sort(key=lambda r: _per100(r, "protein"), reverse=True)
        elif sort_key == "bad_fat":
            # ascending — least bad fat (sat + trans) first
            filtered.sort(key=lambda r: _per100(r, "sat_fat") + _per100(r, "trans_fat"))
        elif sort_key == "sugar":
            filtered.sort(key=lambda r: _per100(r, "sugars_added"))   # ascending — less is better
        elif sort_key == "balance":
            filtered.sort(key=lambda r: r["_scores"]["balance"], reverse=True)
        else:  # total
            filtered.sort(key=lambda r: r["_scores"]["total"], reverse=True)

        self._filtered = filtered
        self._populate_list()

    def _populate_list(self):
        self._list.clear()
        visible = self._filtered[:LIST_CAP]
        total   = len(self._filtered)

        for rank, recipe in enumerate(visible, start=1):
            item = QListWidgetItem()
            item.setSizeHint(QSize(0, 74))
            item.setData(Qt.ItemDataRole.UserRole, id(recipe))
            self._list.addItem(item)
            self._list.setItemWidget(item, _RecipeCard(recipe, rank))

        if total > LIST_CAP:
            footer = QListWidgetItem(
                f"  … mostrando top {LIST_CAP} de {total}. Refine a busca para ver mais."
            )
            footer.setFlags(Qt.ItemFlag.NoItemFlags)
            footer.setForeground(QColor(MUTED))
            self._list.addItem(footer)

        if visible:
            self._list.setCurrentRow(0)

    def _on_selection_changed(self, current: QListWidgetItem, _):
        if current is None:
            return
        rid = current.data(Qt.ItemDataRole.UserRole)
        recipe = next((r for r in self._filtered if id(r) == rid), None)
        if recipe:
            self._detail.load_recipe(recipe)

    # ── Auto-load when view becomes visible ───────────────────────────────────

    def showEvent(self, event):
        super().showEvent(event)
        if not self._recipes and not (self._load_worker and self._load_worker.isRunning()):
            self._load_recipes()
