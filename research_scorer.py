"""
research_scorer.py
Pure logic — no UI dependencies.
Scores every recipe across 4 dimensions and returns warnings.
"""

import math
import json
import pandas as pd
from pathlib import Path

RESEARCH_JSON    = Path(__file__).parent / "research.json"
RECIPES_JSON     = Path(__file__).parent / "recipes.json"
SCORED_JSON      = Path(__file__).parent / "research_scored.json"
INGREDIENTS_CSV  = Path(__file__).parent / "ingredients.csv"

NUTRIENTS = ["kcal", "protein", "fat", "sat_fat", "trans_fat",
             "carb", "sugars_total", "sugars_added", "fiber", "sodium"]
SERVING_G = 200

# ── Scoring thresholds ────────────────────────────────────────────────────────
# These are calibrated for gelato (per 100g of finished product)

PROTEIN_TARGET   = 8.0   # g/100g — above this = full score
SUGAR_WORST      = 20.0  # g added sugar / 100g — above this = zero score
BAD_FAT_WORST    = 10.0  # g (sat + trans) / 100g — above this = zero score
NEGLIGIBLE_GRAMS = 5.0   # ingredients below this are considered solver noise
DOMINANCE_THRESH = 0.60  # proportion above which an ingredient is "dominant"

WEIGHTS = {
    "protein":  0.25,
    "sugar":    0.25,
    "bad_fat":  0.25,
    "balance":  0.25,
}

KPI_RANGES = {
    "fat":    (6,  11),
    "sugars": (16, 22),
    "solids": (32, 42),
    "slng":   (7,  11),
    "pac":    (34, 38),
    "pod":    (16, 20),
    "water":  (58, 64),
}


# ── Nutrition helper ─────────────────────────────────────────────────────────

def _compute_nutrition(ingredients: dict, ing_map: dict, base_size: float) -> dict:
    totals = {n: 0.0 for n in NUTRIENTS}
    for name, grams in ingredients.items():
        ing = ing_map.get(name)
        if ing is None:
            continue
        for n in NUTRIENTS:
            totals[n] += ing[n] * grams / 100
    return {
        "serving_g":   SERVING_G,
        "per_100g":    {n: round(totals[n] * 100 / base_size, 2) for n in NUTRIENTS},
        "per_serving": {n: round(totals[n] * SERVING_G / base_size, 2) for n in NUTRIENTS},
    }


# ── Dimension scorers (each returns float 0-1) ────────────────────────────────

def score_protein(nutrition: dict) -> float:
    p = nutrition["per_100g"].get("protein", 0.0)
    return min(p / PROTEIN_TARGET, 1.0)


def score_sugar(nutrition: dict) -> float:
    """Higher score = less added sugar (better)."""
    s = nutrition["per_100g"].get("sugars_added", 0.0)
    return 1.0 - min(s / SUGAR_WORST, 1.0)


def score_bad_fat(nutrition: dict) -> float:
    """Higher score = less bad fat (better)."""
    sat   = nutrition["per_100g"].get("sat_fat",   0.0)
    trans = nutrition["per_100g"].get("trans_fat",  0.0)
    return 1.0 - min((sat + trans) / BAD_FAT_WORST, 1.0)


def score_balance(ingredients: dict) -> float:
    """
    Shannon entropy of ingredient weights, normalised to [0, 1].
    Penalises:
      - negligible amounts (< NEGLIGIBLE_GRAMS) — these are solver noise
      - single dominant ingredient (> DOMINANCE_THRESH of total)
    """
    real = {k: v for k, v in ingredients.items() if v >= NEGLIGIBLE_GRAMS}
    if len(real) < 2:
        return 0.0

    total = sum(real.values())
    proportions = [v / total for v in real.values()]

    entropy = -sum(p * math.log2(p) for p in proportions)
    max_entropy = math.log2(len(real))
    if max_entropy == 0:
        return 0.0

    base_score = entropy / max_entropy

    # Penalty for a single ingredient dominating the recipe
    max_p = max(proportions)
    if max_p > DOMINANCE_THRESH:
        excess = (max_p - DOMINANCE_THRESH) / (1.0 - DOMINANCE_THRESH)
        base_score *= (1.0 - 0.5 * excess)

    return max(0.0, base_score)


def score_recipe(recipe: dict) -> dict:
    nutrition   = recipe.get("nutrition", {})
    ingredients = recipe.get("ingredients", {})

    protein = score_protein(nutrition)
    sugar   = score_sugar(nutrition)
    bad_fat = score_bad_fat(nutrition)
    balance = score_balance(ingredients)

    total = (
        WEIGHTS["protein"]  * protein +
        WEIGHTS["sugar"]    * sugar   +
        WEIGHTS["bad_fat"]  * bad_fat +
        WEIGHTS["balance"]  * balance
    )

    return {
        "protein":  protein,
        "sugar":    sugar,
        "bad_fat":  bad_fat,
        "balance":  balance,
        "total":    total,
    }


# ── Warnings ──────────────────────────────────────────────────────────────────

def get_warnings(recipe: dict) -> list[tuple[str, str]]:
    """
    Returns list of (level, message).
    level is one of: 'good', 'warn', 'bad'
    """
    warnings = []
    ingredients = recipe.get("ingredients", {})
    nutrition   = recipe.get("nutrition", {})
    kpis        = recipe.get("kpis", {})
    per_100     = nutrition.get("per_100g", {})

    # Solver noise
    tiny = [k for k, v in ingredients.items() if 0 < v < NEGLIGIBLE_GRAMS]
    if tiny:
        names = ", ".join(tiny)
        warnings.append(("warn", f"{len(tiny)} ingrediente(s) vestigial(is) < 5g: {names}"))

    # Dominant ingredient
    total = sum(ingredients.values())
    if total > 0:
        for name, grams in ingredients.items():
            pct = grams / total
            if pct > DOMINANCE_THRESH:
                warnings.append(("warn", f"{name} domina a receita ({pct*100:.0f}%)"))

    # KPIs near boundaries (within 5% of range)
    for kpi, (lo, hi) in KPI_RANGES.items():
        val = kpis.get(kpi)
        if val is None:
            continue
        span = hi - lo
        if span > 0 and (val - lo) / span < 0.05:
            from solver import KPI_LABELS
            warnings.append(("warn", f"{KPI_LABELS.get(kpi, kpi)} rente ao mínimo ({val:.2f} vs {lo})"))
        elif span > 0 and (hi - val) / span < 0.05:
            from solver import KPI_LABELS
            warnings.append(("warn", f"{KPI_LABELS.get(kpi, kpi)} rente ao máximo ({val:.2f} vs {hi})"))

    # Positive signals
    added_sugar = per_100.get("sugars_added", 0)
    if added_sugar == 0:
        warnings.append(("good", "Sem açúcar adicionado"))

    protein = per_100.get("protein", 0)
    if protein >= 5:
        warnings.append(("good", f"Rico em proteína — {protein:.1f} g/100g"))

    sat   = per_100.get("sat_fat",  0)
    trans = per_100.get("trans_fat", 0)
    bad   = sat + trans
    if bad == 0:
        warnings.append(("good", "Sem gordura ruim (saturada + trans)"))
    elif bad < 2:
        warnings.append(("good", f"Pouca gordura ruim — {bad:.1f} g/100g"))
    elif bad > 6:
        warnings.append(("warn", f"Gordura ruim elevada — {bad:.1f} g/100g (sat + trans)"))

    return warnings


# ── Public API ────────────────────────────────────────────────────────────────

def compute_and_save() -> int:
    """
    Score every recipe in research.json + recipes.json and write the
    combined result to research_scored.json.
    Slow — always run in a background thread.
    Returns the number of recipes saved.
    """
    # Build ingredient nutrition lookup once
    ing_map = (
        pd.read_csv(INGREDIENTS_CSV)
        .set_index("name")[NUTRIENTS]
        .to_dict(orient="index")
    )

    all_recipes = []

    # ── research.json (already has nutrition) ────────────────────────────────
    if RESEARCH_JSON.exists():
        with open(RESEARCH_JSON, encoding="utf-8", errors="replace") as f:
            for r in json.load(f):
                if "nutrition" not in r:
                    continue
                r["source"] = "research"
                all_recipes.append(r)

    # ── recipes.json (saved by user — compute nutrition on the fly) ──────────
    if RECIPES_JSON.exists():
        with open(RECIPES_JSON, encoding="utf-8", errors="replace") as f:
            for r in json.load(f):
                r = dict(r)   # don't mutate the original
                r["source"]    = "saved"
                r["nutrition"] = _compute_nutrition(
                    r["ingredients"], ing_map, r["base_size"]
                )
                all_recipes.append(r)

    result = []
    for r in all_recipes:
        r["_scores"]   = score_recipe(r)
        r["_warnings"] = get_warnings(r)
        result.append(r)

    result.sort(key=lambda r: r["_scores"]["total"], reverse=True)

    with open(SCORED_JSON, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return len(result)


def load_scored() -> list[dict]:
    """
    Load the pre-scored file.  Fast — just reads research_scored.json.
    Returns an empty list if the file doesn't exist yet.
    """
    if not SCORED_JSON.exists():
        return []
    with open(SCORED_JSON, encoding="utf-8") as f:
        return json.load(f)


def scored_file_exists() -> bool:
    return SCORED_JSON.exists()
