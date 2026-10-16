"""Day 2: a first talking bot.

Run it:  uv run bot.py -t webrtc
Then open http://localhost:7860 in Chrome and click Connect.
"""

import os

from dotenv import load_dotenv
from loguru import logger

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.evals.transport import EvalTransportParams
from pipecat.frames.frames import LLMRunFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker, ProcessorUnusablePolicy
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.runner.types import RunnerArguments
from pipecat.runner.utils import create_transport
from pipecat.services.groq.llm import GroqLLMService
from pipecat.services.groq.stt import GroqSTTService
from pipecat.services.kokoro.tts import KokoroTTSService
from pipecat.transports.base_transport import BaseTransport, TransportParams
from pipecat.workers.runner import WorkerRunner

load_dotenv(override=True)

SYSTEM_PROMPT = (
    "You are a friendly practice interviewer on a voice call. Everything you say "
    "is spoken aloud, so use plain sentences with no lists, symbols or emojis. "
    "Keep every reply to one or two short sentences."
)

# How people can connect: "webrtc" is the browser test page; "eval" lets
# automated tests talk to the bot (you'll use it in week 4).
transport_params = {
    "webrtc": lambda: TransportParams(audio_in_enabled=True, audio_out_enabled=True),
    "eval": lambda: EvalTransportParams(audio_in_enabled=True, audio_out_enabled=True),
}


async def run_bot(transport: BaseTransport, runner_args: RunnerArguments):
    # Ears: Groq's hosted Whisper turns your speech into text.
    stt = GroqSTTService(api_key=os.environ["GROQ_API_KEY"])

    # Brain: gpt-oss on Groq decides what to say.
    llm = GroqLLMService(
        api_key=os.environ["GROQ_API_KEY"],
        settings=GroqLLMService.Settings(
            model="openai/gpt-oss-20b",
            reasoning_effort="low",  # less thinking, faster replies
            system_instruction=SYSTEM_PROMPT,
        ),
    )

    # Voice: Kokoro runs on your laptop, no key needed.
    tts = KokoroTTSService(settings=KokoroTTSService.Settings(voice="af_heart"))

    # The conversation history, plus the pieces that add each side's words to it.
    context = LLMContext()
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(vad_analyzer=SileroVADAnalyzer()),
    )

    # Audio flows top to bottom: mic -> text -> reply -> voice -> speakers.
    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            user_aggregator,
            llm,
            tts,
            transport.output(),
            assistant_aggregator,
        ]
    )

    worker = PipelineWorker(
        pipeline,
        params=PipelineParams(enable_metrics=True, enable_usage_metrics=True),
        idle_timeout_secs=runner_args.pipeline_idle_timeout_secs,
        processor_unusable_policy=ProcessorUnusablePolicy.END,
    )
    runner = WorkerRunner(handle_sigint=runner_args.handle_sigint)
    await runner.add_workers(worker)

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.info("Candidate connected")
        context.add_message(
            {"role": "developer", "content": "Greet the user and ask how their day is going."}
        )
        await worker.queue_frames([LLMRunFrame()])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info("Candidate disconnected")
        await runner.cancel()

    await runner.run()


async def bot(runner_args: RunnerArguments):
    transport = await create_transport(runner_args, transport_params)
    await run_bot(transport, runner_args)


if __name__ == "__main__":
    from pipecat.runner.run import main

    main()