"""Delivery, measured in code from the word timings. No LLM is involved."""

import re

LONG_PAUSE = 2.0  # seconds of silence between two words
FILLERS = ["um", "uh", "like", "you know", "basically"]
HEDGES = ["i think maybe", "kind of", "sort of", "i guess", "probably", "i'm not sure"]
# "What kind of model" isn't hedging, so skip "kind of" and "sort of" after these words.
NOT_HEDGING_AFTER = {"what", "the", "a", "this", "that", "which", "some", "any", "same"}


def tokens(text: str) -> list[str]:
    """Lowercase words with apostrophes kept, and "umm" or "uhh" folded into "um" and "uh"."""
    words = re.findall(r"[a-z']+", text.lower().replace("’", "'"))
    return [re.sub(r"^u+m+$", "um", re.sub(r"^u+h+$", "uh", word)) for word in words]


def count(phrase: str, words: list[str], text: str) -> int:
    """How many times a filler or hedge appears."""
    if phrase == "like":
        # Only the filler kind, which Whisper sets off with commas: "it was, like, huge".
        return len(re.findall(r",\s*like\b|\blike,", text.lower()))
    parts = phrase.split()
    hits = 0
    for i in range(len(words) - len(parts) + 1):
        if words[i : i + len(parts)] == parts:
            if parts[0] in ("kind", "sort") and i > 0 and words[i - 1] in NOT_HEDGING_AFTER:
                continue
            hits += 1
    return hits


def measure(text: str, timed_words: list[dict]) -> dict:
    """Length, pace, long pauses, fillers and hedges for one clip."""
    words = tokens(text)
    fillers = {phrase: count(phrase, words, text) for phrase in FILLERS}
    hedges = {phrase: count(phrase, words, text) for phrase in HEDGES}
    # The silence between one word's end and the next word's start.
    gaps = [after["start"] - before["end"] for before, after in zip(timed_words, timed_words[1:])]
    seconds = timed_words[-1]["end"] - timed_words[0]["start"] if timed_words else 0.0
    return {
        "seconds": round(seconds, 1),
        "words": len(timed_words),
        "long_pauses": sum(gap > LONG_PAUSE for gap in gaps),
        "longest_pause": round(max(gaps, default=0.0), 1),
        "fillers": {phrase: n for phrase, n in fillers.items() if n},
        "hedges": {phrase: n for phrase, n in hedges.items() if n},
    }


def combine(clips: list[dict]) -> dict:
    """Add up several clips (an answer and its follow-ups), then work out the pace."""
    total = {"seconds": 0.0, "words": 0, "long_pauses": 0, "longest_pause": 0.0}
    fillers, hedges = {}, {}
    for clip in clips:
        total["seconds"] += clip["seconds"]
        total["words"] += clip["words"]
        total["long_pauses"] += clip["long_pauses"]
        total["longest_pause"] = max(total["longest_pause"], clip["longest_pause"])
        for phrase, n in clip["fillers"].items():
            fillers[phrase] = fillers.get(phrase, 0) + n
        for phrase, n in clip["hedges"].items():
            hedges[phrase] = hedges.get(phrase, 0) + n
    minutes = total["seconds"] / 60
    total["seconds"] = round(total["seconds"], 1)
    total["wpm"] = round(total["words"] / minutes) if minutes else 0
    total["fillers"], total["hedges"] = fillers, hedges
    total["fillers_per_minute"] = round(sum(fillers.values()) / minutes, 1) if minutes else 0.0
    return total


if __name__ == "__main__":
    # Try it after Day 1:  uv run python -m feedback.delivery
    import json
    from pathlib import Path

    saved_clips = sorted(Path("sessions").glob("*/answers/*.json"))
    if not saved_clips:
        raise SystemExit("Nothing transcribed yet. Run python -m feedback.transcribe first.")
    session = saved_clips[-1].parent.parent
    for saved in sorted((session / "answers").glob("*.json")):
        heard = json.loads(saved.read_text())
        print(saved.stem, combine([measure(heard["text"], heard["words"])]))