import pulp
import pandas as pd
from typing import Optional

KPI_DEFAULTS = {
    "fat":    (6.0,  11.0),
    "sugars": (16.0, 22.0),
    "solids": (32.0, 42.0),
    "slng":   (7.0,  11.0),
    "pac":    (34.0, 38.0),
    "pod":    (16.0, 20.0),
    "water":  (58.0, 64.0),
}

KPI_LABELS = {
    "fat":    "Gordura Total (%)",
    "sugars": "Açúcares Totais (%)",
    "solids": "Sólidos Totais (%)",
    "slng":   "SLNG (%)",
    "pac":    "PAC",
    "pod":    "POD",
    "water":  "Água Livre (%)",
}

FLOOR_HIGH_CATEGORIES = {"Fruta", "Saborizante"}
FLOOR_DEFAULT = 30.0
FLOOR_HIGH    = 50.0


def _ingredient_floor(name: str, df: pd.DataFrame, min_quantities: dict | None) -> float:
    """Return the minimum grams for an ingredient: 60g for fruits/saborizantes, 30g otherwise.
    An explicit user-set minimum always wins if higher."""
    category = df.loc[df["name"] == name, "category"].iloc[0]
    base_floor = FLOOR_HIGH if category in FLOOR_HIGH_CATEGORIES else FLOOR_DEFAULT
    explicit = (min_quantities or {}).get(name, 0)
    return max(base_floor, explicit)


# Maps each KPI to the column in the DataFrame used to compute it
KPI_COLUMNS = {
    "fat":    "fat",
    "sugars": "sugars",
    "solids": "total_solids",
    "slng":   "slng",
    "pac":    "pac",
    "pod":    "pod",
    "water":  "water",
}


def solve(
    df: pd.DataFrame,
    base_size: float,
    kpi_ranges: dict,
    min_quantities: dict | None = None,
) -> Optional[dict]:
    """
    Find the optimal ingredient quantities for a gelato base.

    Parameters
    ----------
    df         : DataFrame of available ingredients (subset of the full library).
    base_size  : Total recipe weight in grams.
    kpi_ranges : {kpi_key: (min, max)} — target ranges for each KPI.

    Returns
    -------
    {
        "quantities": {ingredient_name: grams},
        "kpis":       {kpi_key: actual_value},
    }
    or None if no feasible solution exists.
    """
    prob = pulp.LpProblem("gelato_balancer", pulp.LpMinimize)

    names = df["name"].tolist()
    x = {n: pulp.LpVariable(f"x_{i}", lowBound=0) for i, n in enumerate(names)}

    # Auxiliary variables for L1 deviation from the centre of each KPI range
    centers    = {k: (lo + hi) / 2 for k, (lo, hi) in kpi_ranges.items()}
    half_ranges = {k: (hi - lo) / 2 for k, (lo, hi) in kpi_ranges.items()}
    d = {k: pulp.LpVariable(f"d_{k}", lowBound=0) for k in kpi_ranges}

    # Objective: minimise normalised deviation (0 = centred, 1 = at boundary).
    # Dividing by half_range makes all KPIs comparable regardless of their scale.
    prob += pulp.lpSum(d[k] / half_ranges[k] for k in kpi_ranges)

    # ── Hard constraint: recipe must sum to exactly base_size grams ──────────
    prob += pulp.lpSum(x.values()) == base_size

    # ── Minimum quantity constraints ──────────────────────────────────────────
    for name in names:
        prob += x[name] >= _ingredient_floor(name, df, min_quantities)

    # ── KPI range constraints + deviation linearisation ──────────────────────
    # Each KPI value = sum(x_i * ingredient_kpi_i) / base_size
    # (ingredient values are per-100 g, so the /base_size normalises to %)
    for kpi, col in KPI_COLUMNS.items():
        if kpi not in kpi_ranges:
            continue

        expr = pulp.lpSum(
            x[row["name"]] * row[col] / base_size
            for _, row in df.iterrows()
        )

        lo, hi = kpi_ranges[kpi]
        prob += expr >= lo
        prob += expr <= hi

        # |expr - center| linearised as: d >= expr - c  AND  d >= c - expr
        prob += d[kpi] >= expr - centers[kpi]
        prob += d[kpi] >= centers[kpi] - expr

    # ── Solve ─────────────────────────────────────────────────────────────────
    prob.solve(pulp.PULP_CBC_CMD(msg=0))

    if pulp.LpStatus[prob.status] != "Optimal":
        return None

    # ── Extract results ───────────────────────────────────────────────────────
    quantities = {
        n: round(x[n].varValue, 1)
        for n in names
        if x[n].varValue and x[n].varValue >= 5.0
    }

    total = sum(quantities.values())
    actuals = {
        kpi: round(
            sum(
                quantities.get(row["name"], 0) * row[col] / total
                for _, row in df.iterrows()
            ),
            2,
        )
        for kpi, col in KPI_COLUMNS.items()
        if kpi in kpi_ranges
    }

    return {"quantities": quantities, "kpis": actuals}


def solve_flexible(
    df: pd.DataFrame,
    base_size: float,
    kpi_ranges: dict,
    min_quantities: dict | None = None,
) -> dict:
    """
    Like solve(), but KPI range constraints are soft — violations are penalised
    instead of causing infeasibility.  Always returns a result.

    Returns the same structure as solve() plus a 'violations' key:
    {
        "quantities": {name: grams},
        "kpis":       {kpi_key: actual_value},
        "violations": {kpi_key: bool},   # True = outside target range
    }
    """
    prob = pulp.LpProblem("gelato_flexible", pulp.LpMinimize)

    names = df["name"].tolist()
    x = {n: pulp.LpVariable(f"x_{i}", lowBound=0) for i, n in enumerate(names)}

    # Slack variables: how much each bound is violated
    slack_lo = {k: pulp.LpVariable(f"slo_{k}", lowBound=0) for k in kpi_ranges}
    slack_hi = {k: pulp.LpVariable(f"shi_{k}", lowBound=0) for k in kpi_ranges}

    # L1 deviation from center (same secondary objective as solve())
    centers     = {k: (lo + hi) / 2 for k, (lo, hi) in kpi_ranges.items()}
    half_ranges = {k: (hi - lo) / 2 for k, (lo, hi) in kpi_ranges.items()}
    d = {k: pulp.LpVariable(f"d_{k}", lowBound=0) for k in kpi_ranges}

    # Objective: heavily penalise violations, then minimise normalised deviation
    PENALTY = 1000
    prob += (
        PENALTY * pulp.lpSum(slack_lo.values())
        + PENALTY * pulp.lpSum(slack_hi.values())
        + pulp.lpSum(d[k] / half_ranges[k] for k in kpi_ranges)
    )

    # Hard constraint: recipe must sum to base_size
    prob += pulp.lpSum(x.values()) == base_size

    for name in names:
        prob += x[name] >= _ingredient_floor(name, df, min_quantities)

    for kpi, col in KPI_COLUMNS.items():
        if kpi not in kpi_ranges:
            continue

        expr = pulp.lpSum(
            x[row["name"]] * row[col] / base_size
            for _, row in df.iterrows()
        )

        lo, hi = kpi_ranges[kpi]

        # Soft lower bound: expr + slack_lo >= lo
        prob += expr + slack_lo[kpi] >= lo
        # Soft upper bound: expr - slack_hi <= hi
        prob += expr - slack_hi[kpi] <= hi

        # Deviation linearisation (same as solve())
        prob += d[kpi] >= expr - centers[kpi]
        prob += d[kpi] >= centers[kpi] - expr

    prob.solve(pulp.PULP_CBC_CMD(msg=0))

    quantities = {
        n: round(x[n].varValue, 1)
        for n in names
        if x[n].varValue and x[n].varValue >= 5.0
    }

    total = sum(quantities.values())
    actuals = {
        kpi: round(
            sum(
                quantities.get(row["name"], 0) * row[col] / total
                for _, row in df.iterrows()
            ),
            2,
        )
        for kpi, col in KPI_COLUMNS.items()
        if kpi in kpi_ranges
    }

    violations = {
        kpi: not (kpi_ranges[kpi][0] <= actuals[kpi] <= kpi_ranges[kpi][1])
        for kpi in kpi_ranges
    }

    return {"quantities": quantities, "kpis": actuals, "violations": violations}


def diagnose(
    df_selected: pd.DataFrame,
    df_all: pd.DataFrame,
    base_size: float,
    kpi_ranges: dict,
    top_n: int = 3,
    min_quantities: dict | None = None,
) -> list[dict]:
    """
    Called when solve() returns None. Identifies which KPIs are blocking a
    solution and suggests unselected ingredients that would help.

    Returns a list of issues:
    [
        {
            "kpis":        [kpi_key, ...],   # one or two KPIs causing the block
            "direction":   "alto" | "baixo", # per kpi key
            "suggestions": [{"name": ..., "value": ...}, ...]
        },
        ...
    ]
    """
    kpi_list = list(kpi_ranges.keys())

    # ── Step 1: find every single KPI whose removal makes the problem feasible ─
    single_bottlenecks = [
        kpi for kpi in kpi_list
        if solve(df_selected, base_size, {k: (0, 9999) if k == kpi else v
                                          for k, v in kpi_ranges.items()},
                 min_quantities=min_quantities) is not None
    ]

    # ── Step 2: if no single KPI fixes it, try every pair ────────────────────
    pair_bottlenecks = []
    if not single_bottlenecks:
        from itertools import combinations
        for k1, k2 in combinations(kpi_list, 2):
            relaxed = {k: (0, 9999) if k in (k1, k2) else v
                       for k, v in kpi_ranges.items()}
            if solve(df_selected, base_size, relaxed,
                     min_quantities=min_quantities) is not None:
                pair_bottlenecks.append((k1, k2))

    bottleneck_kpis = (
        [(k,) for k in single_bottlenecks] if single_bottlenecks else pair_bottlenecks
    )

    # ── Step 3: for each bottleneck, determine direction + suggest ingredients ─
    df_unselected = df_all[~df_all["name"].isin(df_selected["name"])].copy()
    issues = []

    for kpi_group in bottleneck_kpis:
        directions = {}
        for kpi in kpi_group:
            # Does relaxing the minimum fix it (alone)? → we need MORE of this KPI
            need_more = solve(
                df_selected, base_size,
                {k: (0, v[1]) if k == kpi else v for k, v in kpi_ranges.items()},
                min_quantities=min_quantities,
            ) is not None
            directions[kpi] = "baixo" if need_more else "alto"

        # Score unselected ingredients: for each candidate compute how much it
        # helps on ALL KPIs in this group simultaneously.
        # Score = sum over kpis: value * (+1 if need_more, -1 if need_less)
        def score(row):
            total = 0
            for kpi in kpi_group:
                col = KPI_COLUMNS[kpi]
                val = row[col]
                total += val if directions[kpi] == "baixo" else -val
            return total

        df_unselected["_score"] = df_unselected.apply(score, axis=1)
        top = df_unselected.nlargest(top_n, "_score")

        suggestions = [
            {
                "name": row["name"],
                "values": {kpi: round(row[KPI_COLUMNS[kpi]], 1) for kpi in kpi_group},
            }
            for _, row in top.iterrows()
        ]

        issues.append({
            "kpis": list(kpi_group),
            "directions": directions,
            "suggestions": suggestions,
        })

    return issues
