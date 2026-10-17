"""Day 5: save each answer as an audio clip, plus the transcript and response times."""

import json
import wave
from datetime import datetime
from pathlib import Path

from loguru import logger

from pipecat.observers.user_bot_latency_observer import UserBotLatencyObserver
from pipecat.processors.audio.audio_buffer_processor import AudioBufferProcessor

SESSIONS = Path(__file__).parent / "sessions"


def save_wav(path: Path, audio: bytes, sample_rate: int, channels: int):
    with wave.open(str(path), "wb") as f:
        f.setnchannels(channels)
        f.setsampwidth(2)  # 16-bit audio
        f.setframerate(sample_rate)
        f.writeframes(audio)


class SessionRecorder:
    """Writes everything about one interview into sessions/<date_time>/."""

    def __init__(self):
        self.folder = SESSIONS / datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        (self.folder / "answers").mkdir(parents=True, exist_ok=True)
        self.turn = 0

        # Records your mic (left channel) and the interviewer (right channel).
        self.audio = AudioBufferProcessor(
            sample_rate=16000,
            num_channels=2,
            enable_turn_audio=True,
            auto_start_recording=True,
        )
        # Measures how long the interviewer takes to start speaking after you stop.
        self.latency = UserBotLatencyObserver()

        @self.audio.event_handler("on_user_turn_audio")
        async def on_user_turn_audio(processor, data):
            clip = self.folder / "answers" / f"turn_{data.turn_number:02d}.wav"
            save_wav(clip, data.audio, data.sample_rate, data.num_channels)
            logger.info(f"Saved {clip.name}")

        @self.audio.event_handler("on_audio_data")
        async def on_audio_data(processor, audio, sample_rate, num_channels):
            save_wav(self.folder / "conversation.wav", audio, sample_rate, num_channels)

        @self.latency.event_handler("on_latency_measured")
        async def on_latency_measured(observer, seconds):
            self.log("latency.jsonl", {"turn": self.turn, "seconds": round(seconds, 3)})

        @self.latency.event_handler("on_latency_breakdown")
        async def on_latency_breakdown(observer, breakdown):
            for line in breakdown.turn_contribution_lines():
                logger.info(f"Latency: {line}")

    def attach(self, worker, user_aggregator, assistant_aggregator):
        """Listen for turns and for each side's finished words."""

        @worker.turn_tracking_observer.event_handler("on_turn_started")
        async def on_turn_started(tracker, turn_number):
            self.turn = turn_number

        @user_aggregator.event_handler("on_user_turn_stopped")
        async def on_user_turn_stopped(aggregator, strategy, message):
            self.log("transcript.jsonl", self.line("candidate", message))

        @assistant_aggregator.event_handler("on_assistant_turn_stopped")
        async def on_assistant_turn_stopped(aggregator, message):
            self.log("transcript.jsonl", self.line("interviewer", message))

    def line(self, speaker, message):
        return {
            "turn": self.turn,
            "speaker": speaker,
            "time": message.timestamp,
            "text": message.content,
        }

    def log(self, filename, record):
        with open(self.folder / filename, "a") as f:
            f.write(json.dumps(record) + "\n")