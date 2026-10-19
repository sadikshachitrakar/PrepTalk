"""Put your two most recent plans side by side, for this week's gate."""

import json
from pathlib import Path

files = sorted(Path("plans").glob("*.json"))[-2:]
if len(files) < 2:
    raise SystemExit("Prepare two interviews first.")
plans = [json.loads(file.read_text()) for file in files]

for plan in plans:
    print(f"\n{plan['role']} at {plan['company']} ({plan['mode']}, {plan['difficulty']})")
    for number, q in enumerate(plan["questions"], start=1):
        print(f"  {number}. [{q['source']}] {q['question']}")

a, b = ({q["question"] for q in plan["questions"]} for plan in plans)
counts = {
    source: sum(q["source"] == source for plan in plans for q in plan["questions"])
    for source in ("planner", "fallback", "library")
}
print(f"\n{len(a & b)} questions appear in both plans.")
print("Tailored: {planner}. Fallbacks: {fallback}. Library: {library}.".format(**counts))