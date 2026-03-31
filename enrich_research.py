import json
import pandas as pd

INGREDIENTS_CSV = "ingredients.csv"
RESEARCH_JSON = "research.json"

NUTRIENTS = ["kcal", "protein", "fat", "sat_fat", "trans_fat", "carb", "sugars_total", "sugars_added", "fiber", "sodium"]
SERVING_G = 200

# Load ingredients as dict: name -> {nutrient: value_per_100g}
df = pd.read_csv(INGREDIENTS_CSV).set_index("name")
ingredients = df[NUTRIENTS].to_dict(orient="index")

# Load recipes
with open(RESEARCH_JSON, encoding="utf-8") as f:
    data = json.load(f)

for recipe in data:
    base_size = recipe["base_size"]
    totals = {n: 0.0 for n in NUTRIENTS}

    for ing_name, grams in recipe["ingredients"].items():
        ing = ingredients[ing_name]
        for n in NUTRIENTS:
            totals[n] += ing[n] * grams / 100

    per_100g = {n: round(totals[n] * 100 / base_size, 2) for n in NUTRIENTS}
    per_serving = {n: round(totals[n] * SERVING_G / base_size, 2) for n in NUTRIENTS}

    recipe["nutrition"] = {
        "serving_g": SERVING_G,
        "per_100g": per_100g,
        "per_serving": per_serving,
    }

with open(RESEARCH_JSON, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"Enriched {len(data)} recipes with nutritional data.")
