import random
import json
import time
from pathlib import Path
from datetime import datetime

import pandas as pd
import data
from solver import solve, KPI_DEFAULTS
from research_scorer import score_recipe, get_warnings

SCORE_THRESHOLD = 0.5

# ── Config ────────────────────────────────────────────────────────────────────

RESEARCH_JSON = Path(__file__).parent / "research.json"

ADJECTIVES = [
    "Sweet", "Creamy", "Smooth", "Rich", "Velvety", "Fluffy", "Refreshing",
    "Chilled", "Cold", "Delicious", "Indulgent", "Silky", "Airy", "Buttery",
    "Frozen", "Sugary", "Decadent", "Light", "Milky", "Luscious",
]

REQUIRED_CATEGORIES = {
    "base":   ["Base Láctea"],
    "flavor": ["Fruta", "Saborizante"],
    "fat":    ["Gordura", "Lácteo Concentrado"],
}

NUTRIENTS     = ["kcal", "protein", "fat", "sat_fat", "trans_fat",
                  "carb", "sugars_total", "sugars_added", "fiber", "sodium"]
SERVING_G     = 200

BASE_SIZE = 1000.0
MIN_FLAVOR_GRAMS = 50.0  # flavor ingredient must contribute at least this much
MAX_INGREDIENTS = 8


# ── Naming ────────────────────────────────────────────────────────────────────

def _generate_name(flavor_ingredient: str, existing_names: set) -> str:
    first_word = flavor_ingredient.split()[0]
    adjective = random.choice(ADJECTIVES)
    base = f"{first_word} {adjective}"
    if base not in existing_names:
        return base
    n = 2
    while f"{base} #{n}" in existing_names:
        n += 1
    return f"{base} #{n}"


# ── Research loop ─────────────────────────────────────────────────────────────

def _compute_nutrition(quantities: dict, df: pd.DataFrame, base_size: float) -> dict:
    ing_map = df.set_index("name")[NUTRIENTS].to_dict(orient="index")
    totals = {n: 0.0 for n in NUTRIENTS}
    for ing_name, grams in quantities.items():
        ing = ing_map[ing_name]
        for n in NUTRIENTS:
            totals[n] += ing[n] * grams / 100
    return {
        "serving_g": SERVING_G,
        "per_100g":    {n: round(totals[n] * 100 / base_size, 2) for n in NUTRIENTS},
        "per_serving": {n: round(totals[n] * SERVING_G / base_size, 2) for n in NUTRIENTS},
    }


def run(stop_event=None, on_recipe_found=None, turbo=False, pinned: dict | None = None):
    df = data.load_ingredients()

    by_category = {
        cat: df[df["category"] == cat]["name"].tolist()
        for cat in df["category"].unique()
    }

    name_to_category = df.set_index("name")["category"].to_dict()

    if pinned:
        if len(pinned) > MAX_INGREDIENTS:
            raise ValueError(f"Muitos ingredientes fixos ({len(pinned)} > {MAX_INGREDIENTS})")
        if sum(pinned.values()) >= BASE_SIZE:
            raise ValueError(f"Soma dos gramas fixados ({sum(pinned.values()):.0f} g) ≥ {BASE_SIZE:.0f} g")

    # Load existing research to seed success cache and name registry
    existing = _load()
    success_cache = {frozenset(r["ingredients"].keys()) for r in existing}
    existing_names = {r["name"] for r in existing}

    found = len(existing)
    attempts = 0

    print(f"Starting research. {found} recipes already saved. Press Ctrl+C to stop.\n")

    try:
        while not (stop_event and stop_event.is_set()):
            attempts += 1
            subset = _pick_subset(by_category, name_to_category, pinned=pinned)
            if subset is None:
                continue

            key = frozenset(subset)
            if key in success_cache:
                continue

            flavor_name = _name_anchor(pinned, name_to_category, subset, by_category)
            df_selected = df[df["name"].isin(subset)].copy()
            merged_min = {flavor_name: MIN_FLAVOR_GRAMS}
            if pinned:
                merged_min.update(pinned)
            result = solve(df_selected, BASE_SIZE, KPI_DEFAULTS,
                           min_quantities=merged_min)

            if result is None:
                continue

            name = _generate_name(flavor_name, existing_names)

            recipe = {
                "name": name,
                "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "base_size": BASE_SIZE,
                "ingredients": result["quantities"],
                "kpis": result["kpis"],
                "nutrition": _compute_nutrition(result["quantities"], df, BASE_SIZE),
            }

            scores = score_recipe(recipe)
            if scores["total"] < SCORE_THRESHOLD:
                continue

            recipe["_scores"] = scores
            recipe["_warnings"] = get_warnings(recipe)

            existing.append(recipe)
            success_cache.add(key)
            existing_names.add(name)
            found += 1
            _save(existing)

            print(f"  [{found}] {name}  —  {len(result['quantities'])} ingredientes  |  score {scores['total']:.2f}  |  attempt #{attempts}")

            if on_recipe_found:
                on_recipe_found(recipe, found, attempts)

            if not turbo:
                time.sleep(0.05)

    except KeyboardInterrupt:
        print(f"\nStopped. {found} valid recipes saved ({attempts} attempts total).")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _pick_subset(by_category: dict, name_to_category: dict,
                 pinned: dict | None = None) -> list | None:
    pinned = pinned or {}
    chosen = list(pinned.keys())
    chosen_set = set(chosen)

    # Determine which required categories are already covered by pinned ingredients
    covered_roles = set()
    for ing_name in chosen:
        cat = name_to_category.get(ing_name, "")
        for role, cats in REQUIRED_CATEGORIES.items():
            if cat in cats:
                covered_roles.add(role)

    # Mandatory: 1 Base Láctea (only if not covered by pinned)
    if "base" not in covered_roles:
        pool = [n for n in by_category.get("Base Láctea", []) if n not in chosen_set]
        if not pool:
            return None
        pick = random.choice(pool)
        chosen.append(pick)
        chosen_set.add(pick)

    # Mandatory: 1 primary flavor (only if not covered by pinned)
    if "flavor" not in covered_roles:
        flavor_pool = [
            n for n in (by_category.get("Fruta", []) + by_category.get("Saborizante", []))
            if n not in chosen_set
        ]
        if not flavor_pool:
            return None
        pick = random.choice(flavor_pool)
        chosen.append(pick)
        chosen_set.add(pick)

    # Mandatory: 1 fat source (only if not covered by pinned)
    if "fat" not in covered_roles:
        fat_pool = [
            n for n in (by_category.get("Gordura", []) + by_category.get("Lácteo Concentrado", []))
            if n not in chosen_set
        ]
        if not fat_pool:
            return None
        fat_pick = random.choice(fat_pool)
        chosen.append(fat_pick)
        chosen_set.add(fat_pick)
    else:
        # Find which pinned ingredient covers the fat role
        fat_pick = next(
            (n for n in chosen
             if name_to_category.get(n, "") in REQUIRED_CATEGORIES["fat"]),
            chosen[0],
        )

    # Structured optional extras — respects reduced remaining capacity
    chosen = _pick_structured_extras(chosen, by_category, fat_pick,
                                     max_total=MAX_INGREDIENTS)

    return chosen


def _pick_structured_extras(chosen: list, by_category: dict, fat_pick: str,
                             max_total: int = MAX_INGREDIENTS) -> list:
    """Layer optional ingredients by functional role, then allow limited free exploration."""
    chosen = list(chosen)
    chosen_set = set(chosen)

    def _pick_from(cats: list[str], prob: float) -> None:
        if len(chosen) >= max_total or random.random() > prob:
            return
        pool = [
            n for cat in cats
            for n in by_category.get(cat, [])
            if n not in chosen_set
        ]
        if pool:
            pick = random.choice(pool)
            chosen.append(pick)
            chosen_set.add(pick)

    # ~40%: secondary flavor for complexity
    _pick_from(["Fruta", "Saborizante"], prob=0.40)

    # ~50%: a milk solid / powder if fat came from Gordura (adds body)
    fat_is_lacteo = fat_pick in by_category.get("Lácteo Concentrado", [])
    if not fat_is_lacteo:
        _pick_from(["Lácteo Concentrado"], prob=0.50)

    # ~65%: a sweetener (almost every gelato needs one)
    _pick_from(["Adoçante"], prob=0.65)

    # ~55%: a stabilizer / fiber for texture
    _pick_from(["Fibra/Estabilizante"], prob=0.55)

    # 0–2 free exploration picks from anything remaining
    free_pool = [
        n for names in by_category.values() for n in names if n not in chosen_set
    ]
    for _ in range(2):
        if len(chosen) >= max_total or not free_pool or random.random() > 0.45:
            break
        pick = random.choice(free_pool)
        chosen.append(pick)
        chosen_set.add(pick)
        free_pool.remove(pick)

    return chosen


def _pick_flavor(subset: list, by_category: dict) -> str:
    flavor_pool = set(by_category.get("Fruta", []) + by_category.get("Saborizante", []))
    for name in subset:
        if name in flavor_pool:
            return name
    return subset[0]


def _name_anchor(pinned: dict | None, name_to_category: dict,
                 subset: list, by_category: dict) -> str:
    """Return the ingredient name that should lead the recipe name.

    Priority:
      1. First pinned sabor (Fruta / Saborizante) ingredient.
      2. First pinned ingredient of any category (e.g. butter).
      3. Fallback: first flavor in the random subset (current behaviour).
    """
    if pinned:
        flavor_cats = set(REQUIRED_CATEGORIES["flavor"])
        sabor_anchor = next(
            (n for n in pinned if name_to_category.get(n, "") in flavor_cats),
            None,
        )
        if sabor_anchor:
            return sabor_anchor
        return next(iter(pinned))
    return _pick_flavor(subset, by_category)


def _load() -> list:
    if not RESEARCH_JSON.exists():
        return []
    with open(RESEARCH_JSON, encoding="utf-8") as f:
        return json.load(f)


def _save(recipes: list):
    with open(RESEARCH_JSON, "w", encoding="utf-8") as f:
        json.dump(recipes, f, indent=2, ensure_ascii=False)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    run()
