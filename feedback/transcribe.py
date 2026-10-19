"""Transcribe an answer clip again, carefully, with a start and end time for every word."""

import json
import os
from pathlib import Path

from groq import AsyncGroq

MODEL = "whisper-large-v3-turbo"
# Whisper tends to tidy away "um" and "uh". A prompt written the way people really
# talk nudges it to keep them, so the filler counts mean something.
FILLER_PROMPT = "Um, so, uh, I was, like, working on the, you know, data, and, hmm, basically..."


async def transcribe(clip: Path) -> dict:
    """Return the clip's text and its words with times in seconds. Saved next to the clip."""
    saved = clip.with_suffix(".json")
    if saved.exists():  # transcribed before: no need to spend free quota again
        return json.loads(saved.read_text())

    async with AsyncGroq(api_key=os.environ["GROQ_API_KEY"], max_retries=4) as client:
        result = await client.audio.transcriptions.create(
            file=(clip.name, clip.read_bytes()),
            model=MODEL,
            prompt=FILLER_PROMPT,
            response_format="verbose_json",  # needed for timestamps
            timestamp_granularities=["word"],
            language="en",
            temperature=0,
        )
    data = result.model_dump()
    words = [
        {"word": w["word"], "start": w["start"], "end": w["end"]} for w in data.get("words") or []
    ]
    heard = {"text": data["text"].strip(), "words": words}
    saved.write_text(json.dumps(heard, indent=2))
    return heard


if __name__ == "__main__":
    # Try it:  uv run python -m feedback.transcribe   (your newest session)
    import asyncio

    from dotenv import load_dotenv

    load_dotenv(override=True)
    clips = sorted(Path("sessions").glob("*/answers/*.wav"))
    if not clips:
        raise SystemExit("No recorded answers yet. Run an interview first.")
    session = clips[-1].parent.parent  # the newest session with recorded answers
    for clip in sorted((session / "answers").glob("*.wav")):
        heard = asyncio.run(transcribe(clip))
        print(f"\n{clip.name}: {heard['text']}")
        for word in heard["words"][:10]:
            print(f"  {word['start']:6.2f}s to {word['end']:6.2f}s  {word['word']}")