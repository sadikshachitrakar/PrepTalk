"""Check: Kokoro, Groq Whisper and gpt-oss all work before you build the bot."""

import os
import wave
from pathlib import Path

import numpy as np
import requests
from dotenv import load_dotenv
from groq import Groq
from kokoro_onnx import Kokoro

load_dotenv()

# Pipecat looks for the Kokoro voice model here, so downloading it now
CACHE = Path.home() / ".cache" / "pipecat" / "kokoro-onnx"
BASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
FILES = ["kokoro-v1.0.onnx", "voices-v1.0.bin"]

# 1. Kokoro: download the model once (about 350 MB), then speak a sentence.
CACHE.mkdir(parents=True, exist_ok=True)
for name in FILES:
    target = CACHE / name
    if not target.exists():
        print(f"Downloading {name} (one time only)...")
        partial = target.with_suffix(".part")
        with requests.get(BASE + name, stream=True, timeout=60) as response:
            response.raise_for_status()
            with open(partial, "wb") as f:
                for chunk in response.iter_content(chunk_size=1 << 20):
                    f.write(chunk)
        partial.rename(target)

kokoro = Kokoro(str(CACHE / FILES[0]), str(CACHE / FILES[1]))
samples, sample_rate = kokoro.create(
    "Tell me about a project you are proud of.", voice="af_heart", lang="en-us"
)
with wave.open("check.wav", "wb") as f:
    f.setnchannels(1)
    f.setsampwidth(2)
    f.setframerate(sample_rate)
    f.writeframes((np.clip(samples, -1, 1) * 32767).astype(np.int16).tobytes())
print("1. Kokoro works: wrote check.wav")

# 2. Groq Whisper: transcribe the sentence Kokoro just spoke.
client = Groq(api_key=os.environ["GROQ_API_KEY"])
with open("check.wav", "rb") as f:
    heard = client.audio.transcriptions.create(
        file=("check.wav", f.read()), model="whisper-large-v3-turbo"
    )
print(f"2. Groq Whisper works: heard '{heard.text.strip()}'")

# 3. gpt-oss on Groq: one short reply.
reply = client.chat.completions.create(
    model="openai/gpt-oss-20b",
    reasoning_effort="low",
    messages=[{"role": "user", "content": "In one short sentence, ask me an interview question."}],
)
print(f"3. gpt-oss works: '{reply.choices[0].message.content.strip()}'")