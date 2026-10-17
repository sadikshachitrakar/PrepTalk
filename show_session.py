"""Print the latest interview's transcript and how fast the interviewer replied."""

import json
import statistics
from pathlib import Path

sessions = sorted(Path("sessions").glob("*/"))
if not sessions:
    raise SystemExit("No sessions yet. Run an interview first.")
latest = sessions[-1]
print(f"Session {latest.name}\n")

transcript = latest / "transcript.jsonl"
if transcript.exists():
    for line in transcript.open():
        entry = json.loads(line)
        if entry["text"]:
            print(f"{entry['speaker']:>11}: {entry['text']}")

latency = latest / "latency.jsonl"
if latency.exists():
    waits = [json.loads(line)["seconds"] for line in latency.open()]
    print(
        f"\n{len(waits)} replies. Median wait {statistics.median(waits):.2f} s, "
        f"slowest {max(waits):.2f} s."
    )

clips = sorted((latest / "answers").glob("*.wav"))
print(f"{len(clips)} answer clips in {latest / 'answers'}")