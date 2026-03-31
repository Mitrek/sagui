import json
import pandas as pd

INGREDIENTS_CSV = "ingredients.csv"
RESEARCH_JSON = "research.json"

# Load valid ingredient names
valid = set(pd.read_csv(INGREDIENTS_CSV)["name"])

# Load recipes
with open(RESEARCH_JSON, encoding="utf-8") as f:
    data = json.load(f)

before = len(data)

clean = [r for r in data if all(name in valid for name in r["ingredients"])]

removed = before - len(clean)

# Save
with open(RESEARCH_JSON, "w", encoding="utf-8") as f:
    json.dump(clean, f, ensure_ascii=False, indent=2)

print(f"Removed : {removed} recipes")
print(f"Remaining: {len(clean)} recipes")
