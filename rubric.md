# Rubric: forecast reasoning

Each answer is scored 0, 1 or 2 on four criteria. Score against the answer key in `scenarios/answer_key.jsonl`, not against how confident or well written the answer sounds.

| Criterion | 2 | 1 | 0 |
| --- | --- | --- | --- |
| **Numerical correctness** | Every number matches the answer key (within $100 for totals) | Right direction and size, one number off | A wrong total, an invented number, or no number where one was asked for |
| **Root cause** | Names the real driver (the movement, the planted problem, or the rep pattern in the key) | Names a real factor but not the main one | Names the wrong cause, or describes symptoms only |
| **Actionability** | Says what to do, to which deal or rep, before the call | Gives an action but it is generic ("follow up") | No action, or an action that would make the forecast worse |
| **Risk awareness** | Says how sure the answer is and what would change it | Mentions uncertainty in passing | Presents a guess as fact |

**Fluent but wrong.** An answer that reads well and scores 0 on numerical correctness or root cause is logged as fluent-but-wrong. These are the examples that matter most: they are the answers a busy CRO would believe.

**By scenario type, what "the key" means:**
- `forecast_change`: total change in dollars and the biggest single driver.
- `inspect_three`: at least two of the three named deals are in `best_three`; any deal in `deals_with_planted_problems` counts as a reasonable pick.
- `commit_credible`: the yes/no matches `credible`, and the estimate is near `commit_actually_won`.
- `stage_check`: the verdict matches.
- `weighted_math`: the total matches `weighted_total`.
