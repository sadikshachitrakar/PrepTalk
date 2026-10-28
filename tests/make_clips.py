"""Make answer clips with thinking pauses of known length, in Kokoro's voice.

Checks the coach's pause and pace numbers against them, and Day 4 plays
them to the interviewer to catch cut-ins. Run it:  uv run python -m tests.make_clips
"""

import json
import wave
from pathlib import Path

import numpy as np
from kokoro_onnx import Kokoro

HERE = Path(__file__).parent
CACHE = Path.home() / ".cache" / "pipecat" / "kokoro-onnx"  # downloaded in Week 1
VOICE = "am_michael"

# Each answer is spoken pieces with pauses (in seconds) between them. Every long
# pause comes where a person stops to think and isn't finished yet.
ANSWERS = [
    [
        "I just finished my master's in data science, and the part I enjoyed most was",
        3.0,
        "cleaning messy hospital data so the dashboards finally made sense.",
    ],
    [
        "Before my master's I worked as a software engineer on mobile apps, and",
        2.5,
        "that's where I learned to care about the people who use the numbers.",
    ],
    [
        "My favorite project was a staffing dashboard for a small clinic. They had",
        3.5,
        "six different spreadsheets, and I merged them into one weekly report.",
    ],
    [
        "Hmm, let me think.",
        3.0,
        "I'd say my strongest skill is SQL, because I use it every single day.",
    ],
    [
        "I applied to this role because",
        2.5,
        "your team builds dashboards for hospitals, and that's the work I want to do.",
    ],
    [
        "In my last internship,",
        0.8,
        "I owned the weekly sales report, and",
        3.0,
        "twice I caught errors before they reached the managers.",
    ],
    [
        "The hardest part of that project was",
        4.0,
        "getting three teams to agree on one definition of an active patient.",
    ],
    [
        "I'm comfortable with Python and SQL, and I've used Tableau and",
        2.5,
        "Power BI for most of my class projects.",
    ],
    [
        "Outside of work,",
        0.7,
        "I volunteer at a food bank, where I built a donation tracker, so",
        3.0,
        "now they know which weeks run short.",
    ],
    [
        "What I'm looking for next is",
        3.0,
        "a team where I can learn from senior analysts and still own real work.",
    ],
]


def trimmed(samples: np.ndarray) -> np.ndarray:
    """Cut Kokoro's own silence off both ends, so each pause is exactly as long as asked."""
    loud = np.flatnonzero(np.abs(samples) > 0.01)
    return samples[loud[0] : loud[-1] + 1]


def main():
    kokoro = Kokoro(str(CACHE / "kokoro-v1.0.onnx"), str(CACHE / "voices-v1.0.bin"))
    (HERE / "clips").mkdir(exist_ok=True)
    truth = []
    for number, answer in enumerate(ANSWERS, start=1):
        audio, pauses, words = [], [], 0
        for piece in answer:
            if isinstance(piece, float):
                audio.append(np.zeros(int(24000 * piece), dtype=np.float32))
                pauses.append(piece)
            else:
                samples, _ = kokoro.create(piece, voice=VOICE, lang="en-us")
                audio.append(trimmed(samples))
                words += len(piece.split())
        audio = np.concatenate([np.zeros(12000, dtype=np.float32), *audio])  # half a second lead-in
        clip = HERE / "clips" / f"{number:02d}.wav"
        with wave.open(str(clip), "wb") as f:
            f.setnchannels(1)
            f.setsampwidth(2)
            f.setframerate(24000)
            f.writeframes((np.clip(audio, -1, 1) * 32767).astype(np.int16).tobytes())
        speaking = (len(audio) - 12000) / 24000  # first word to last word, pauses included
        truth.append(
            {
                "clip": clip.name,
                "text": " ".join(p for p in answer if isinstance(p, str)),
                "seconds": round(len(audio) / 24000, 2),
                "words": words,
                "wpm": round(words / (speaking / 60)),
                "long_pauses": sum(p > 2.0 for p in pauses),
                "longest_pause": max(pauses),
            }
        )
        print(f"{clip.name}: {truth[-1]['seconds']} s, {words} words, pauses {pauses}")
    (HERE / "clip_truth.json").write_text(json.dumps(truth, indent=2))
    write_pause_tests(truth)
    print(f"Wrote {len(truth)} clips, tests/clip_truth.json and tests/pauses.yaml")


def write_pause_tests(truth: list[dict]):
    """Day 4's audio tests: play each clip after the greeting, and fail if the
    interviewer starts talking before the clip has finished."""
    lines = [
        "# Made by tests/make_clips.py. Day 4: each test plays one answer with a thinking",
        "# pause. The interviewer must not start talking until the whole clip has played.",
        "name: pauses",
        "user:",
        "  modality: audio",
        "judge:",
        "  modality: audio",
        "  transcription:",
        "    factory: tests.services.ears",
        "scenarios:",
    ]
    for clip in truth:
        length = int(clip["seconds"] * 1000)
        lines += [
            f"  - name: clip_{clip['clip'][:2]}",
            "    turns:",
            "      - expect:",
            "          - event: bot_stopped_speaking  # the greeting and first question",
            "            within_ms: 30000",
            f"      - user: {json.dumps(clip['text'])}",
            f"        audio: clips/{clip['clip']}",
            "        expect:",
            "          - event: bot_started_speaking  # no cut-in while the clip plays",
            "            absent: true",
            f"            within_ms: {length}",
            "          - event: bot_started_speaking  # then it replies",
            f"            within_ms: {length + 20000}",
        ]
    (HERE / "pauses.yaml").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()