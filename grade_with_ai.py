"""
grade_with_ai.py: an AI grader scores every answer with the same rubric and the same answer key the human used.
The point is not to replace the human. It is to measure whether an AI grader can be trusted (see agreement.py).

  python grade_with_ai.py --grader claude-sonnet-5-5
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
CRITERIA = ["numerical_correctness", "root_cause", "actionability", "risk_awareness"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--grader", default="claude-sonnet-5-5")
    args = ap.parse_args()
    import anthropic

    client = anthropic.Anthropic()
    rubric = (HERE / "rubric.md").read_text()
    scen = {json.loads(l)["id"]: json.loads(l) for l in (HERE / "scenarios" / "scenarios.jsonl").read_text().splitlines()}
    keys = {json.loads(l)["id"]: json.loads(l) for l in (HERE / "scenarios" / "answer_key.jsonl").read_text().splitlines()}
    rows = []
    for path in sorted((HERE / "answers").glob("*.jsonl")):
        for line in path.read_text().splitlines():
            a = json.loads(line)
            prompt = (f"RUBRIC:\n{rubric}\n\nQUESTION:\n{scen[a['id']]['question']}\n\nANSWER KEY:\n{json.dumps(keys[a['id']])}\n\n"
                      f"ANSWER TO GRADE:\n{a['answer']}\n\nReply with JSON only: "
                      '{"numerical_correctness":0-2,"root_cause":0-2,"actionability":0-2,"risk_awareness":0-2,"fluent_but_wrong":true/false}')
            m = client.messages.create(model=args.grader, max_tokens=200, temperature=0,
                                       messages=[{"role": "user", "content": prompt}])
            t = m.content[0].text
            try:
                s = json.loads(t[t.index("{"): t.rindex("}") + 1])
            except Exception:  # noqa: BLE001
                s = {c: "" for c in CRITERIA}
            rows.append({"id": a["id"], "model": a["model"], **{c: s.get(c, "") for c in CRITERIA},
                         "fluent_but_wrong": s.get("fluent_but_wrong", "")})
    pd.DataFrame(rows).to_csv(HERE / "scores" / "ai_grader_scores.csv", index=False)
    print(f"graded {len(rows)} answers")


if __name__ == "__main__":
    main()
