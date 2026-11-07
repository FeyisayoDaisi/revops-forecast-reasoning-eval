"""
run_models.py: send every scenario to two or more AI models and save the answers.

  export ANTHROPIC_API_KEY=...   OPENAI_API_KEY=...
  pip install anthropic openai
  python run_models.py --models claude:claude-sonnet-5-5 openai:gpt-5

One call per scenario per model, temperature 0, no tools, 3 retries.
Answers go to answers/<label>.jsonl. Already answered scenarios are skipped,
so a failed run can simply be started again.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SYSTEM = ("You are a revenue operations analyst preparing for a weekly forecast call. "
          "Answer the question using only the data given. Be specific: name deal IDs and dollar amounts. "
          "Under 200 words.")


def ask(provider: str, model: str, prompt: str) -> str:
    for attempt in range(3):
        try:
            if provider == "claude":
                import anthropic
                m = anthropic.Anthropic().messages.create(model=model, max_tokens=600, temperature=0, system=SYSTEM,
                                                          messages=[{"role": "user", "content": prompt}])
                return m.content[0].text
            if provider == "openai":
                from openai import OpenAI
                m = OpenAI().chat.completions.create(model=model, temperature=0, messages=[
                    {"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}])
                return m.choices[0].message.content
            raise ValueError(f"unknown provider {provider}")
        except Exception as e:  # noqa: BLE001
            if attempt == 2:
                return f"ERROR: {e}"
            time.sleep(2 ** attempt)
    return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", required=True, help="provider:model, e.g. claude:claude-sonnet-5-5")
    args = ap.parse_args()
    scen = [json.loads(l) for l in (HERE / "scenarios" / "scenarios.jsonl").read_text().splitlines()]
    (HERE / "answers").mkdir(exist_ok=True)
    for spec in args.models:
        provider, model = spec.split(":", 1)
        path = HERE / "answers" / f"{provider}_{model}.jsonl"
        done = {json.loads(l)["id"] for l in path.read_text().splitlines()} if path.exists() else set()
        with open(path, "a") as f:
            for s in scen:
                if s["id"] in done:
                    continue
                prompt = f"{s['context']}\n\nQuestion: {s['question']}"
                f.write(json.dumps({"id": s["id"], "model": spec, "answer": ask(provider, model, prompt)}) + "\n")
                f.flush()
        print(f"{spec}: {len(scen)} answers in {path.name}")


if __name__ == "__main__":
    main()
