import random
import json
from pathlib import Path
from datetime import datetime

import data
from solver import solve, KPI_DEFAULTS

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

MIN_INGREDIENTS = 4
MAX_INGREDIENTS = 10
BASE_SIZE = 1000.0
MIN_FLAVOR_GRAMS = 50.0  # flavor ingredient must contribute at least this much


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

def run():
    df = data.load_ingredients()

    by_category = {
        cat: df[df["category"] == cat]["name"].tolist()
        for cat in df["category"].unique()
    }

    # Load existing research to seed success cache and name registry
    existing = _load()
    success_cache = {frozenset(r["ingredients"].keys()) for r in existing}
    existing_names = {r["name"] for r in existing}

    found = len(existing)
    attempts = 0

    print(f"Starting research. {found} recipes already saved. Press Ctrl+C to stop.\n")

    try:
        while True:
            attempts += 1
            subset = _pick_subset(by_category)
            if subset is None:
                continue

            key = frozenset(subset)
            if key in success_cache:
                continue

            flavor_name = _pick_flavor(subset, by_category)
            df_selected = df[df["name"].isin(subset)].copy()
            result = solve(df_selected, BASE_SIZE, KPI_DEFAULTS,
                           min_quantities={flavor_name: MIN_FLAVOR_GRAMS})

            if result is None:
                continue

            name = _generate_name(flavor_name, existing_names)

            recipe = {
                "name": name,
                "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "base_size": BASE_SIZE,
                "ingredients": result["quantities"],
                "kpis": result["kpis"],
            }

            existing.append(recipe)
            success_cache.add(key)
            existing_names.add(name)
            found += 1
            _save(existing)

            print(f"  [{found}] {name}  —  {len(result['quantities'])} ingredientes  |  attempt #{attempts}")

    except KeyboardInterrupt:
        print(f"\nStopped. {found} valid recipes saved ({attempts} attempts total).")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _pick_subset(by_category: dict) -> list | None:
    chosen = []

    # Mandatory: 1 base láctea
    if not by_category.get("Base Láctea"):
        return None
    chosen.append(random.choice(by_category["Base Láctea"]))

    # Mandatory: 1 flavor (fruta or saborizante)
    flavor_pool = (
        by_category.get("Fruta", []) + by_category.get("Saborizante", [])
    )
    if not flavor_pool:
        return None
    chosen.append(random.choice(flavor_pool))

    # Mandatory: 1 from Gordura or Lácteo Concentrado (interchangeable fat sources)
    fat_pool = [
        n for n in (
            by_category.get("Gordura", []) + by_category.get("Lácteo Concentrado", [])
        )
        if n not in chosen
    ]
    if not fat_pool:
        return None
    chosen.append(random.choice(fat_pool))

    # Fill remaining slots randomly from the full library
    total = random.randint(MIN_INGREDIENTS, MAX_INGREDIENTS)
    remaining = total - len(chosen)
    all_names = [
        n for names in by_category.values() for n in names if n not in chosen
    ]
    if len(all_names) < remaining:
        return None
    chosen += random.sample(all_names, remaining)

    # Safety: guarantee at least one true Base Láctea is present
    base_lactea = set(by_category.get("Base Láctea", []))
    if not any(n in base_lactea for n in chosen):
        return None


    return chosen


def _pick_flavor(subset: list, by_category: dict) -> str:
    flavor_pool = set(
        by_category.get("Fruta", []) + by_category.get("Saborizante", [])
    )
    for name in subset:
        if name in flavor_pool:
            return name
    return subset[0]


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
