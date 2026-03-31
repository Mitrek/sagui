"""
research_run_view.py
Research runner tab — start/stop the research pipeline and browse results live.
"""

import threading
import json
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QGroupBox, QFrame, QListWidget, QListWidgetItem,
    QSplitter, QCheckBox, QDoubleSpinBox,
    QSizePolicy, QMessageBox, QLineEdit, QCompleter,
)
from PyQt6.QtCore import Qt, QSize, QThread, pyqtSignal, QTimer, QStringListModel

import data as _data
import research_scorer
from research_view import _DetailPanel, _RecipeCard, MUTED, BORDER, GREEN, GOLD, RED, DARK

RESEARCH_JSON = Path(__file__).parent / "research.json"


# ── Background workers ────────────────────────────────────────────────────────

class _LoadWorker(QThread):
    """Loads research.json, fills missing scores/warnings, sorts newest first."""
    finished = pyqtSignal(list)

    def run(self):
        try:
            print("[LoadWorker] starting")
            if not RESEARCH_JSON.exists():
                print("[LoadWorker] research.json not found")
                self.finished.emit([])
                return

            print("[LoadWorker] reading research.json…")
            with open(RESEARCH_JSON, encoding="utf-8") as f:
                recipes = json.load(f)
            print(f"[LoadWorker] loaded {len(recipes)} recipes")

            needs_score    = sum(1 for r in recipes if "_scores" not in r or "bad_fat" not in r.get("_scores", {}))
            needs_warnings = sum(1 for r in recipes if "_warnings" not in r)
            print(f"[LoadWorker] need score recompute: {needs_score}  need warnings: {needs_warnings}")

            for i, r in enumerate(recipes):
                if i % 500 == 0:
                    print(f"[LoadWorker] processing recipe {i}/{len(recipes)}…")
                if "_scores" not in r or "bad_fat" not in r.get("_scores", {}):
                    r["_scores"] = research_scorer.score_recipe(r)
                if "_warnings" not in r:
                    r["_warnings"] = research_scorer.get_warnings(r)

            print("[LoadWorker] sorting…")
            recipes.sort(key=lambda r: r["date"], reverse=True)
            print(f"[LoadWorker] done — emitting {len(recipes)} recipes")
            self.finished.emit(recipes)
        except Exception as e:
            import traceback
            print(f"[LoadWorker] CRASHED: {e}")
            traceback.print_exc()
            self.finished.emit([])


class _ResearchThread(QThread):
    """Runs research.run() with a stop event."""
    recipe_found = pyqtSignal(dict, int, int)   # recipe, found_count, attempts

    def __init__(self, turbo: bool = False, pinned: dict | None = None):
        super().__init__()
        self._stop_event = threading.Event()
        self._turbo = turbo
        self._pinned = pinned

    def stop(self):
        self._stop_event.set()

    def run(self):
        import research
        research.run(
            stop_event=self._stop_event,
            on_recipe_found=lambda r, f, a: self.recipe_found.emit(r, f, a),
            turbo=self._turbo,
            pinned=self._pinned,
        )


# ── Pinned ingredients UI ────────────────────────────────────────────────────

class _PinnedIngredientRow(QWidget):
    """One ingredient row: [search input] [grams spinbox] [remove ×]"""
    changed          = pyqtSignal()
    remove_requested = pyqtSignal(object)  # emits self

    def __init__(self, all_ingredients: list, excluded_names: set, parent=None):
        super().__init__(parent)
        self._all_ingredients = all_ingredients
        self._excluded: set = set()
        self._current_name: str = ""

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._edit = QLineEdit()
        self._edit.setPlaceholderText("Buscar ingrediente…")
        self._edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._model = QStringListModel()
        self._completer = QCompleter(self._model, self)
        self._completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self._edit.setCompleter(self._completer)

        # Emit changed only when a valid ingredient is chosen from the completer
        self._completer.activated.connect(self._on_activated)
        # Also accept if the user types an exact name and leaves the field
        self._edit.editingFinished.connect(self._on_editing_finished)

        self._spin = QDoubleSpinBox()
        self._spin.setObjectName("spin_min")
        self._spin.setRange(1, 999)
        self._spin.setDecimals(0)
        self._spin.setValue(50)
        self._spin.setFixedWidth(72)
        self._spin.setSuffix(" g")
        self._spin.valueChanged.connect(self.changed.emit)

        self._btn_remove = QPushButton("×")
        self._btn_remove.setFixedSize(24, 24)
        self._btn_remove.setStyleSheet(
            f"color: {RED}; font-weight: bold; font-size: 15px;"
            " background: transparent; border: none; padding: 0;"
        )
        self._btn_remove.clicked.connect(lambda: self.remove_requested.emit(self))

        layout.addWidget(self._edit, stretch=1)
        layout.addWidget(self._spin)
        layout.addWidget(self._btn_remove)

        self.update_available(excluded_names)

    def _available_names(self) -> list:
        return [n for n in self._all_ingredients
                if n not in self._excluded or n == self._current_name]

    def _on_activated(self, name: str):
        self._current_name = name
        self.changed.emit()

    def _on_editing_finished(self):
        text = self._edit.text()
        if text in self._all_ingredients and text != self._current_name:
            self._current_name = text
            self.changed.emit()
        elif text not in self._all_ingredients:
            # Revert to last valid selection
            self._edit.setText(self._current_name)

    def ingredient_name(self) -> str:
        return self._current_name

    def min_grams(self) -> float:
        return self._spin.value()

    def update_available(self, excluded: set):
        self._excluded = excluded
        self._model.setStringList(self._available_names())


class _PinnedPanel(QWidget):
    """Panel that holds pinned ingredient rows + budget/coverage indicators."""
    changed = pyqtSignal()

    ROLE_LABELS = {"base": "Base Láctea", "flavor": "Sabor", "fat": "Gordura"}
    REQUIRED_CATEGORIES = {
        "base":   {"Base Láctea"},
        "flavor": {"Fruta", "Saborizante"},
        "fat":    {"Gordura", "Lácteo Concentrado"},
    }
    MAX_ROWS = 8   # mirrors research.MAX_INGREDIENTS

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: list[_PinnedIngredientRow] = []
        self._all_ingredients: list[str] = []
        self._name_to_category: dict[str, str] = {}
        self._setup_ui()
        self._load_ingredients()

    def _load_ingredients(self):
        df = _data.load_ingredients()
        self._name_to_category = df.set_index("name")["category"].to_dict()
        self._all_ingredients = sorted(df["name"].tolist())

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 6, 0, 0)
        layout.setSpacing(4)

        lbl_header = QLabel("Ingredientes Fixos")
        lbl_header.setStyleSheet(
            f"font-size: 12px; font-weight: bold; color: {DARK}; background: transparent;"
        )
        layout.addWidget(lbl_header)

        # Rows area — auto-sizes with content, no scroll
        self._rows_frame = QFrame()
        self._rows_frame.setStyleSheet(
            f"QFrame {{ border: 1px solid {BORDER}; border-radius: 4px; background: #FAFAF7; }}"
        )
        self._rows_frame.setVisible(False)  # hidden until first row added
        self._rows_layout = QVBoxLayout(self._rows_frame)
        self._rows_layout.setContentsMargins(4, 4, 4, 4)
        self._rows_layout.setSpacing(3)
        layout.addWidget(self._rows_frame)

        self._btn_add = QPushButton("+ Adicionar ingrediente")
        self._btn_add.setObjectName("btn_load")
        self._btn_add.clicked.connect(self._add_row)
        layout.addWidget(self._btn_add)

        self._lbl_budget = QLabel("0 g / 1000 g fixados")
        self._lbl_budget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_budget.setStyleSheet(
            f"font-size: 11px; background: transparent; color: {MUTED};"
        )
        layout.addWidget(self._lbl_budget)

        self._lbl_coverage = QLabel()
        self._lbl_coverage.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_coverage.setTextFormat(Qt.TextFormat.RichText)
        self._lbl_coverage.setWordWrap(True)
        self._lbl_coverage.setStyleSheet("font-size: 11px; background: transparent;")
        layout.addWidget(self._lbl_coverage)

        self._update_indicators()

    def _add_row(self):
        if len(self._rows) >= self.MAX_ROWS:
            return
        excluded = self._current_excluded()
        if len(excluded) >= len(self._all_ingredients):
            return
        row = _PinnedIngredientRow(self._all_ingredients, excluded)
        row.changed.connect(self._on_row_changed)
        row.remove_requested.connect(self._remove_row)
        self._rows.append(row)
        self._rows_layout.addWidget(row)
        self._rows_frame.setVisible(True)
        self._on_row_changed()

    def _remove_row(self, row: _PinnedIngredientRow):
        self._rows.remove(row)
        self._rows_layout.removeWidget(row)
        row.deleteLater()
        if not self._rows:
            self._rows_frame.setVisible(False)
        self._on_row_changed()

    def _current_excluded(self) -> set:
        return {r.ingredient_name() for r in self._rows}

    def _on_row_changed(self):
        excluded = self._current_excluded()
        for row in self._rows:
            own = row.ingredient_name()
            row.update_available(excluded - {own})
        self._update_indicators()
        self.changed.emit()

    def _update_indicators(self):
        pinned = self.get_pinned()
        total_grams = sum(pinned.values())

        if total_grams == 0:
            budget_color = MUTED
        elif total_grams <= 500:
            budget_color = GREEN
        elif total_grams <= 750:
            budget_color = GOLD
        else:
            budget_color = RED

        self._lbl_budget.setText(f"{total_grams:.0f} g / 1000 g fixados")
        self._lbl_budget.setStyleSheet(
            f"font-size: 11px; background: transparent; color: {budget_color};"
        )

        # Category coverage
        covered = set()
        for name in pinned:
            cat = self._name_to_category.get(name, "")
            for role, cats in self.REQUIRED_CATEGORIES.items():
                if cat in cats:
                    covered.add(role)

        parts = []
        for role, label in self.ROLE_LABELS.items():
            if role in covered:
                parts.append(f'<span style="color:{GREEN};">&#9679; {label}</span>')
            else:
                parts.append(f'<span style="color:{MUTED};">&#8211; {label}</span>')
        self._lbl_coverage.setText(" &nbsp; ".join(parts))

        if len(pinned) >= self.MAX_ROWS:
            self._btn_add.setEnabled(False)
            self._btn_add.setToolTip(f"Máximo de {self.MAX_ROWS} ingredientes atingido")
        else:
            self._btn_add.setEnabled(True)
            self._btn_add.setToolTip("")

    def get_pinned(self) -> dict:
        return {r.ingredient_name(): r.min_grams()
                for r in self._rows if r.ingredient_name()}

    def validate(self) -> str | None:
        pinned = self.get_pinned()
        if not pinned:
            return None
        if len(pinned) > self.MAX_ROWS:
            return f"Máximo {self.MAX_ROWS} ingredientes fixos permitidos."
        total = sum(pinned.values())
        if total >= 1000.0:
            return (
                f"A soma dos gramas fixados ({total:.0f} g) não pode atingir "
                "ou ultrapassar 1000 g (tamanho total da base)."
            )
        return None


# ── Main view ─────────────────────────────────────────────────────────────────

class ResearchRunView(QWidget):
    """Research runner tab — index 4 in the app's QStackedWidget."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._recipes: list[dict] = []
        self._thread:      _ResearchThread | None = None
        self._load_worker: _LoadWorker     | None = None
        self._update_timer: QTimer | None = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 8, 14, 14)
        layout.setSpacing(8)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(8)
        splitter.setStyleSheet("QSplitter::handle { background-color: transparent; }")
        splitter.addWidget(self._build_list_panel())
        splitter.addWidget(self._build_detail_panel())
        splitter.setSizes([380, 620])
        layout.addWidget(splitter, stretch=1)

    def _build_list_panel(self) -> QWidget:
        box = QGroupBox("Pesquisa")
        layout = QVBoxLayout(box)
        layout.setSpacing(6)

        self._btn_toggle = QPushButton("▶  Iniciar Pesquisa")
        self._btn_toggle.setObjectName("btn_start")
        self._btn_toggle.clicked.connect(self._toggle)
        layout.addWidget(self._btn_toggle)

        self._chk_turbo = QCheckBox("⚡ Modo Turbo — pesquisa mais rápido, mas o app pode ficar lento")
        self._chk_turbo.setStyleSheet("font-size: 11px; background: transparent;")
        layout.addWidget(self._chk_turbo)

        self._lbl_status = QLabel("Parado")
        self._lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_status.setStyleSheet(
            f"color: {MUTED}; font-size: 11px; background: transparent;"
        )
        layout.addWidget(self._lbl_status)

        self._pinned_panel = _PinnedPanel()
        self._pinned_panel.changed.connect(self._on_pinned_changed)
        layout.addWidget(self._pinned_panel)

        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setFixedHeight(1)
        div.setStyleSheet(f"background-color: {BORDER}; border: none;")
        layout.addWidget(div)

        self._lbl_count = QLabel("Carregando…")
        self._lbl_count.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_count.setStyleSheet(
            f"color: {MUTED}; font-size: 11px; background: transparent;"
        )
        layout.addWidget(self._lbl_count)

        self._list = QListWidget()
        self._list.setSpacing(2)
        self._list.currentItemChanged.connect(self._on_selection_changed)
        layout.addWidget(self._list, stretch=1)

        return box

    def _build_detail_panel(self) -> QWidget:
        self._detail = _DetailPanel()
        return self._detail

    # ── Data ──────────────────────────────────────────────────────────────────

    def _load_existing(self):
        if self._load_worker and self._load_worker.isRunning():
            return
        self._lbl_count.setText("Carregando…")
        self._load_worker = _LoadWorker()
        self._load_worker.finished.connect(self._on_loaded)
        self._load_worker.start()

    def _on_loaded(self, recipes: list):
        self._recipes = recipes
        self._repopulate()

    LIST_CAP = 200

    def _repopulate(self):
        # Remember current selection so we can restore it after rebuild
        current_rid = None
        if self._list.currentItem():
            current_rid = self._list.currentItem().data(Qt.ItemDataRole.UserRole)
        was_empty = self._list.count() == 0

        self._list.clear()
        visible = self._recipes[:self.LIST_CAP]
        for i, recipe in enumerate(visible):
            item = QListWidgetItem()
            item.setSizeHint(QSize(0, 74))
            item.setData(Qt.ItemDataRole.UserRole, id(recipe))
            self._list.addItem(item)
            self._list.setItemWidget(item, _RecipeCard(recipe, i + 1))

        n = len(self._recipes)
        shown = min(n, self.LIST_CAP)
        if n > self.LIST_CAP:
            self._lbl_count.setText(f"Exibindo as {shown} mais recentes de {n}")
        else:
            self._lbl_count.setText(f"{n} receita{'s' if n != 1 else ''}")

        # Restore previous selection; fall back to row 0 only on first load
        restored = False
        if current_rid is not None:
            for i in range(self._list.count()):
                if self._list.item(i).data(Qt.ItemDataRole.UserRole) == current_rid:
                    self._list.setCurrentRow(i)
                    restored = True
                    break
        if not restored and was_empty and self._list.count() > 0:
            self._list.setCurrentRow(0)

    # ── Thread control ────────────────────────────────────────────────────────

    def _toggle(self):
        if self._thread and self._thread.isRunning():
            self._stop()
        else:
            self._start()

    def _start(self):
        err = self._pinned_panel.validate()
        if err:
            QMessageBox.warning(self, "Ingredientes Fixos", err)
            return
        pinned = self._pinned_panel.get_pinned() or None
        self._thread = _ResearchThread(turbo=self._chk_turbo.isChecked(), pinned=pinned)
        self._chk_turbo.setEnabled(False)
        self._pinned_panel.setEnabled(False)
        self._thread.recipe_found.connect(self._on_recipe_found)
        self._thread.finished.connect(self._on_stopped)
        self._thread.start()
        self._session_found = 0
        self._update_timer = QTimer(self)
        self._update_timer.setInterval(2000)
        self._update_timer.timeout.connect(self._repopulate)
        self._update_timer.start()
        self._set_button_state(running=True)
        self._lbl_status.setText("Rodando…")

    def _stop(self):
        if self._thread:
            self._thread.stop()
        self._btn_toggle.setEnabled(False)
        self._lbl_status.setText("Parando…")

    def _set_button_state(self, running: bool):
        if running:
            self._btn_toggle.setText("■  Parar Pesquisa")
            self._btn_toggle.setObjectName("btn_stop")
        else:
            self._btn_toggle.setText("▶  Iniciar Pesquisa")
            self._btn_toggle.setObjectName("btn_start")
        self._btn_toggle.style().unpolish(self._btn_toggle)
        self._btn_toggle.style().polish(self._btn_toggle)
        self._btn_toggle.setEnabled(True)

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_recipe_found(self, recipe: dict, found: int, attempts: int):
        self._session_found += 1
        self._recipes.insert(0, recipe)
        if len(self._recipes) > self.LIST_CAP:
            self._recipes.pop()   # keep in-memory list bounded
        self._lbl_status.setText(f"{self._session_found} encontradas · {attempts} tentativas")

    def _on_pinned_changed(self):
        err = self._pinned_panel.validate()
        self._btn_toggle.setToolTip(err or "")

    def _on_stopped(self):
        if self._update_timer:
            self._update_timer.stop()
            self._update_timer = None
        self._repopulate()
        self._set_button_state(running=False)
        self._chk_turbo.setEnabled(True)
        self._pinned_panel.setEnabled(True)
        self._lbl_status.setText("Parado")

    def _on_selection_changed(self, current: QListWidgetItem, _):
        if current is None:
            return
        rid = current.data(Qt.ItemDataRole.UserRole)
        recipe = next((r for r in self._recipes if id(r) == rid), None)
        if recipe:
            self._detail.load_recipe(recipe)

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def showEvent(self, event):
        super().showEvent(event)
        if not self._recipes and not (self._load_worker and self._load_worker.isRunning()):
            self._load_existing()

    def closeEvent(self, event):
        if self._thread and self._thread.isRunning():
            self._thread.stop()
            self._thread.wait(3000)
        super().closeEvent(event)
