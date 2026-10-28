"""Is the feedback right? Scores 20 pairs of answers (the same story told well
and badly) and checks that the stronger answer scores higher, that scores hold steady
when an answer is scored again, and that the evidence quotes are real.

Run it:  uv run python -m tests.check_feedback   (about 20 minutes on the free tier)
"""

import asyncio
import json
from pathlib import Path

from dotenv import load_dotenv

from feedback.scorer import DIMENSIONS, score_answer

HERE = Path(__file__).parent
SAVED = HERE.parent / "test-runs" / "feedback_scores.jsonl"  # a rerun carries on from here
STEADY_PAIRS = 5  # the first five pairs are scored three times, to check consistency


def calls(pairs: list[dict]):
    """Every scoring call to make: (pair number, which answer, run)."""
    for number in range(1, len(pairs) + 1):
        for which in ("weak", "strong"):
            for run in range(1, 4 if number <= STEADY_PAIRS else 2):
                yield number, which, run


async def score_all(pairs: list[dict]) -> dict:
    """Score every answer once (the first five pairs three times), saving as it goes."""
    scores = {}
    if SAVED.exists():
        for line in SAVED.open():
            row = json.loads(line)
            scores[(row["pair"], row["which"], row["run"])] = row["result"]
    todo = [call for call in calls(pairs) if call not in scores]
    SAVED.parent.mkdir(exist_ok=True)
    for done, (number, which, run) in enumerate(todo, start=1):
        pair = pairs[number - 1]
        exchange = f"Interviewer: {pair['question']['question']}\nCandidate: {pair[which]}"
        print(f"Scoring {done} of {len(todo)}: pair {number}, {which} answer, run {run}")
        try:
            result = await score_answer(pair["question"], exchange, pair[which])
        except Exception as error:  # usually Groq's free daily limit
            raise SystemExit(f"Stopped: {error}\nRun the same command later to carry on.")
        scores[(number, which, run)] = result
        with SAVED.open("a") as f:
            f.write(json.dumps({"pair": number, "which": which, "run": run, "result": result}))
            f.write("\n")
    return scores


def report(pairs: list[dict], scores: dict):
    # 1. Ranking: does the stronger telling score higher?
    right, missed = 0, []
    for number, pair in enumerate(pairs, start=1):
        weak = scores[(number, "weak", 1)]["average"]
        strong = scores[(number, "strong", 1)]["average"]
        if strong > weak:
            right += 1
        else:
            missed.append(f"pair {number} ({pair['differs_by']}): weak {weak}, strong {strong}")
    print(f"\nRanking: the stronger answer scored higher in {right} of {len(pairs)} pairs.")
    for line in missed:
        print(f"  missed {line}")

    # 2. Consistency: the same answer scored three times.
    steady = total = 0
    for number in range(1, STEADY_PAIRS + 1):
        for which in ("weak", "strong"):
            runs = [scores[(number, which, run)]["scores"] for run in (1, 2, 3)]
            for key in DIMENSIONS:
                values = [run[key]["score"] for run in runs]
                steady += max(values) - min(values) <= 1
                total += 1
    print(f"Consistency: {steady} of {total} scores moved by one point or less over three runs.")

    # 3. Quotes: how many were really in the answer before the code checked them?
    kept = sum(bool(s["quote"]) for result in scores.values() for s in result["scores"].values())
    dropped = sum(result["quotes_dropped"] for result in scores.values())
    print(f"Quotes: {kept} of {kept + dropped} evidence quotes were really in the answer.")
    print(f"  The code dropped the other {dropped} before you ever saw them.")


async def main():
    pairs = json.loads((HERE / "feedback_pairs.json").read_text())
    report(pairs, await score_all(pairs))


if __name__ == "__main__":
    load_dotenv(override=True)
    asyncio.run(main())