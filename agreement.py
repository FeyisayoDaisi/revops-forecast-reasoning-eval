"""
agreement.py: compares the human scores with the AI grader's scores and with the answer key.

Outputs results/summary.csv (average score per model per criterion),
results/agreement.csv (exact agreement, within-one agreement and Cohen's kappa per criterion),
and results/fluent_but_wrong.csv (answers the human marked as fluent but wrong).
"""

from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
CRITERIA = ["numerical_correctness", "root_cause", "actionability", "risk_awareness"]


def kappa(a: pd.Series, b: pd.Series) -> float:
    cats = sorted(set(a) | set(b))
    po = (a == b).mean()
    pe = sum((a == c).mean() * (b == c).mean() for c in cats)
    return round((po - pe) / (1 - pe), 3) if pe < 1 else 1.0


def main():
    hp, ap = HERE / "scores" / "human_scores.csv", HERE / "scores" / "ai_grader_scores.csv"
    if not hp.exists():
        print("No human scores yet. Run run_models.py, then make_score_sheet.py, then fill in scores/human_scores.csv.")
        return
    h = pd.read_csv(hp)
    h = h.dropna(subset=CRITERIA)
    if h.empty:
        print("human_scores.csv has no completed rows yet.")
        return
    (HERE / "results").mkdir(exist_ok=True)
    h.groupby("model")[CRITERIA].mean().round(2).to_csv(HERE / "results" / "summary.csv")
    h[h.fluent_but_wrong.astype(str).str.lower().isin(["true", "yes", "1"])].to_csv(HERE / "results" / "fluent_but_wrong.csv", index=False)
    if ap.exists():
        g = pd.read_csv(ap)
        m = h.merge(g, on=["id", "model"], suffixes=("_human", "_ai")).dropna()
        rows = []
        for c in CRITERIA:
            x, y = m[f"{c}_human"].astype(int), m[f"{c}_ai"].astype(int)
            rows.append({"criterion": c, "answers": len(m), "exact_agreement": round((x == y).mean(), 3),
                         "within_one": round(((x - y).abs() <= 1).mean(), 3), "cohens_kappa": kappa(x, y)})
        pd.DataFrame(rows).to_csv(HERE / "results" / "agreement.csv", index=False)
        print(pd.DataFrame(rows).to_string(index=False))
    print(pd.read_csv(HERE / "results" / "summary.csv").to_string(index=False))


if __name__ == "__main__":
    main()
