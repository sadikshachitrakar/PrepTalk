"""Check the coach's pause and pace numbers on clips where you know the truth.

Run it:  uv run python -m tests.check_delivery
"""

import asyncio
import json
from pathlib import Path

from dotenv import load_dotenv

from feedback.delivery import combine, measure
from feedback.transcribe import transcribe

HERE = Path(__file__).parent


async def main():
    truth = json.loads((HERE / "clip_truth.json").read_text())
    print("clip   long pauses    longest pause (s)    pace (words a minute)")
    print("       true  coach      true  coach          true  coach")
    right, pause_off, pace_off = 0, [], []
    for clip in truth:
        heard = await transcribe(HERE / "clips" / clip["clip"])  # saved next to the clip
        coach = combine([measure(heard["text"], heard["words"])])
        right += coach["long_pauses"] == clip["long_pauses"]
        pause_off.append(abs(coach["longest_pause"] - clip["longest_pause"]))
        pace_off.append(abs(coach["wpm"] - clip["wpm"]) / clip["wpm"])
        print(
            f"{clip['clip'][:2]}     {clip['long_pauses']:>4}  {coach['long_pauses']:>5}"
            f"      {clip['longest_pause']:>4.1f}  {coach['longest_pause']:>5.1f}"
            f"          {clip['wpm']:>4}  {coach['wpm']:>5}"
        )
    n = len(truth)
    print(f"\nLong pauses counted right in {right} of {n} clips.")
    print(f"Longest pause off by {sum(pause_off) / n:.1f} seconds on average.")
    print(f"Pace off by {sum(pace_off) / n:.0%} on average.")


if __name__ == "__main__":
    load_dotenv(override=True)
    asyncio.run(main())