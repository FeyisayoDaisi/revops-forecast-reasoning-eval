"""make_score_sheet.py: builds scores/human_scores.csv, one row per scenario per model, for the human reviewer to fill in."""

import json
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
CRITERIA = ["numerical_correctness", "root_cause", "actionability", "risk_awareness"]

rows = []
for path in sorted((HERE / "answers").glob("*.jsonl")):
    for line in path.read_text().splitlines():
        a = json.loads(line)
        rows.append({"id": a["id"], "model": a["model"], **{c: "" for c in CRITERIA}, "fluent_but_wrong": "", "note": ""})
out = HERE / "scores" / "human_scores.csv"
if out.exists():
    print(f"{out.name} already exists, not overwriting your scores")
else:
    pd.DataFrame(rows).to_csv(out, index=False)
    print(f"wrote {len(rows)} rows to {out.name}: score each criterion 0, 1 or 2 using rubric.md")
