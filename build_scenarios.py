"""
build_scenarios.py: writes the 20 evaluation scenarios from the Forecast Integrity System's synthetic CRM.

Because the flagship data was generated with an answer key, every scenario has
a checkable right answer. The model only sees the question and the context;
the answer key stays in scenarios/answer_key.jsonl.

  python build_scenarios.py --flagship ../revops-forecast-integrity

Five scenario types, four of each:
  A forecast_change   explain why the in-quarter pipeline moved between two weeks
  B inspect_three     which three deals would you inspect before the forecast call, and why
  C commit_credible   is this rep's commit credible?
  D stage_check       is this deal's stage and category right? (abandoned / mis_staged / stalled / no_issue)
  E weighted_math     compute the stage-weighted forecast from a table (tests numbers, not prose)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent


def deal_table(df: pd.DataFrame, cols) -> str:
    d = df[cols].copy()
    for c in d.columns:
        if "date" in c:
            d[c] = pd.to_datetime(d[c]).dt.date.astype(str)
        if c == "amount":
            d[c] = d[c].map(lambda v: f"${v:,.0f}" if pd.notna(v) else "blank")
    return d.to_markdown(index=False) if hasattr(d, "to_markdown") else d.to_string(index=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--flagship", default=str(HERE.parent / "revops-forecast-integrity"))
    root = Path(ap.parse_args().flagship).resolve()
    for p in [root, root / "stage1_hygiene", root / "stage2_forecast", root / "eval"]:
        sys.path.insert(0, str(p))
    from common import TODAY, answer_key, outcomes, quarter_bounds, quarter_of, rules, snapshot_on_week, snapshots
    import forecast as F
    from rules_check import audit
    from eval_stage1 import truth_at

    snaps, ak, o, r = snapshots(), answer_key(), outcomes(), rules()
    won = o[o.outcome == "won"].set_index("deal_id")
    stage_txt = "\n".join(f"- {s['name']} (win probability {int(s['win_probability']*100)}%): {s['definition']} "
                          f"Exit criteria: {s['exit_criteria']}" for s in r["stages"])
    qs = [quarter_of(TODAY) - k for k in range(4, 0, -1)]
    scen, keys = [], []

    def add(kind, q, ctx, key):
        sid = f"S{len(scen) + 1:02d}"
        scen.append({"id": sid, "type": kind, "question": q, "context": ctx})
        keys.append({"id": sid, "type": kind, **key})

    cols = ["deal_id", "owner", "stage", "amount", "close_date", "forecast_category", "last_activity_date",
            "next_step", "decision_maker_identified", "budget_confirmed"]

    # A: forecast change, the busiest week-on-week move between weeks 3 and 10 of each back-test quarter
    for q in qs:
        def pair(w):
            a = F.in_quarter(F.pipeline(snapshot_on_week(snaps, q, w), False), q).set_index("deal_id")
            b = F.in_quarter(F.pipeline(snapshot_on_week(snaps, q, w + 1), False), q).set_index("deal_id")
            return len(a.index.symmetric_difference(b.index)), w
        w = max(pair(w) for w in range(3, 10))[1]
        d0, d1 = snapshot_on_week(snaps, q, w), snapshot_on_week(snaps, q, w + 1)
        p0 = F.in_quarter(F.pipeline(d0, False), q).set_index("deal_id")
        p1 = F.in_quarter(F.pipeline(d1, False), q).set_index("deal_id")
        gone = p0.index.difference(p1.index)
        still = snaps[snaps.snapshot_date == d1].deal_id
        mv = {"won": 0.0, "lost": 0.0, "pushed_out": 0.0, "new_or_pulled_in": 0.0, "amount_change": 0.0}
        for did in gone:
            k = "pushed_out" if did in set(still) else ("won" if did in won.index else "lost")
            mv[k] += float(p0.loc[did, "amount"])
        for did in p1.index.difference(p0.index):
            mv["new_or_pulled_in"] += float(p1.loc[did, "amount"])
        for did in p1.index.intersection(p0.index):
            mv["amount_change"] += float(p1.loc[did, "amount"] - p0.loc[did, "amount"])
        driver = max(mv, key=lambda k: abs(mv[k]))
        ctx = (f"Quarter {q}. In-quarter open pipeline on {d0.date()} (last week):\n\n"
               + deal_table(p0.reset_index(), ["deal_id", "stage", "amount", "close_date"])
               + f"\n\nIn-quarter open pipeline on {d1.date()} (this week):\n\n"
               + deal_table(p1.reset_index(), ["deal_id", "stage", "amount", "close_date"])
               + "\n\nDeals that left the list either closed won, closed lost, or had their close date moved out of the quarter. "
                 f"Closed this week: won {sorted(set(gone) & set(won.index)) or 'none'}; still open in CRM: {sorted(set(gone) & set(still)) or 'none'}.")
        add("forecast_change", "The in-quarter pipeline changed between last week and this week. By how much, and what drove the change? "
                               "Give the total change in dollars and the biggest single driver.", ctx,
            {"total_change": round(float(p1.amount.sum() - p0.amount.sum())), "movements": {k: round(v) for k, v in mv.items()},
             "biggest_driver": driver})

    # B: inspect three, week 6 of each quarter
    for q in qs:
        d = snapshot_on_week(snaps, q, 6)
        a = audit(snaps[snaps.snapshot_date <= d], d)
        a = a[a.close_date.dt.to_period("Q") == q].sort_values("amount", ascending=False).head(14)
        truth = truth_at(ak, d)
        bad = a[a.deal_id.map(lambda x: bool(truth.get(x)))].sort_values("amount", ascending=False)
        ctx = f"Review date {d.date()}. Stage definitions:\n{stage_txt}\n\nIn-quarter deals:\n\n" + deal_table(a, cols)
        add("inspect_three", "Which three deals would you inspect before this week's forecast call, and why? Name the deal IDs.", ctx,
            {"deals_with_planted_problems": bad.deal_id.tolist(), "best_three": bad.deal_id.head(3).tolist(),
             "problems": {x: sorted(truth[x]) for x in bad.deal_id}})

    # C: commit credible, week 6, the reps with the most commit that quarter
    picks = []
    for q in qs:
        d = snapshot_on_week(snaps, q, 6)
        p = F.in_quarter(F.pipeline(d, False), q)
        c = p[p.forecast_category == "commit"]
        top = c.groupby("owner").amount.sum().sort_values(ascending=False)
        owner = next(x for x in top.index if (x, str(q)) not in picks)
        picks.append((owner, str(q)))
        cd = c[c.owner == owner]
        start, end = quarter_bounds(q)
        wq = won[(won.closed_date >= start) & (won.closed_date <= end)]
        closed = float(wq.amount_won.reindex(cd.deal_id).fillna(0).sum())
        ctx = f"Review date {d.date()}, week 6 of {q}. Stage definitions:\n{stage_txt}\n\n{owner}'s commit deals:\n\n" + deal_table(cd, cols)
        add("commit_credible", f"{owner} is calling {'${:,.0f}'.format(cd.amount.sum())} in commit for {q}. Is that commit credible? "
                               "Say yes or no, give your best estimate of what will really close, and name the evidence.", ctx,
            {"commit_called": round(float(cd.amount.sum())), "commit_actually_won": round(closed),
             "credible": closed >= 0.6 * float(cd.amount.sum())})

    # D: stage check, one deal per verdict class from today's AI review set
    v = pd.read_csv(root / "outputs" / "stage1" / "ai_verdicts_all_audits.csv")
    chosen = []
    for lab in ["abandoned", "mis_staged", "stalled", "no_issue"]:
        g = v[v.expected_verdict == lab]
        chosen.append(g.iloc[len(g) // 2])
    for row in chosen:
        d = pd.Timestamp(row.audit_date)
        x = snaps[(snaps.snapshot_date == d) & (snaps.deal_id == row.deal_id)]
        acts = sorted(snaps[(snaps.deal_id == row.deal_id) & (snaps.snapshot_date <= d)].last_activity_date.unique())[-6:]
        ctx = (f"Review date {d.date()}. Stage definitions:\n{stage_txt}\n\nDeal record:\n\n" + deal_table(x, cols)
               + f"\n\nRecent activity dates: {', '.join(str(pd.Timestamp(a).date()) for a in acts)}")
        add("stage_check", "Is this deal's stage and forecast category right? Choose one: abandoned, mis_staged, stalled, no_issue, and explain.",
            ctx, {"verdict": row.expected_verdict})

    # E: weighted math, small table per quarter at week 10
    for q in qs:
        d = snapshot_on_week(snaps, q, 10)
        p = F.in_quarter(F.pipeline(d, False), q).sort_values("deal_id").head(8)
        total = float((p.amount * p.stage.map(r["prob"])).sum())
        ctx = f"Stage win probabilities:\n{stage_txt}\n\nOpen deals:\n\n" + deal_table(p, ["deal_id", "stage", "amount"])
        add("weighted_math", "What is the stage-weighted value of these deals? Show the calculation and give the total in dollars.",
            ctx, {"weighted_total": round(total)})

    (HERE / "scenarios").mkdir(exist_ok=True)
    with open(HERE / "scenarios" / "scenarios.jsonl", "w") as f:
        for s in scen:
            f.write(json.dumps(s) + "\n")
    with open(HERE / "scenarios" / "answer_key.jsonl", "w") as f:
        for k in keys:
            f.write(json.dumps(k, default=str) + "\n")
    print(f"wrote {len(scen)} scenarios")


if __name__ == "__main__":
    main()
