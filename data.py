import json
import pandas as pd
from pathlib import Path
from datetime import datetime

DATA_DIR = Path(__file__).parent
INGREDIENTS_CSV = DATA_DIR / "ingredients.csv"
RECIPES_JSON = DATA_DIR / "recipes.json"


def load_ingredients() -> pd.DataFrame:
    df = pd.read_csv(INGREDIENTS_CSV)
    df["total_solids"] = df["slng"] + df["sugars"] + df["other_solids"]
    return df


def save_recipe(name: str, base_size: float, quantities: dict, kpis: dict) -> int:
    recipes = load_recipes()
    recipe_id = (recipes[-1]["id"] + 1) if recipes else 1
    recipe = {
        "id": recipe_id,
        "name": name,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "base_size": base_size,
        "ingredients": quantities,
        "kpis": kpis,
    }
    recipes.append(recipe)
    with open(RECIPES_JSON, "w", encoding="utf-8") as f:
        json.dump(recipes, f, indent=2, ensure_ascii=False)
    return recipe_id


def load_recipes() -> list:
    if not RECIPES_JSON.exists():
        return []
    with open(RECIPES_JSON, encoding="utf-8") as f:
        return json.load(f)


def delete_recipe(recipe_id: int) -> None:
    recipes = [r for r in load_recipes() if r["id"] != recipe_id]
    with open(RECIPES_JSON, "w", encoding="utf-8") as f:
        json.dump(recipes, f, indent=2, ensure_ascii=False)
