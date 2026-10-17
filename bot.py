"""The mock interviewer.

Run it:  uv run bot.py -t webrtc
Then open http://localhost:7860 in Chrome and click Connect.
"""

import asyncio
import os

from dotenv import load_dotenv
from loguru import logger

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.evals.transport import EvalTransportParams
from pipecat.frames.frames import LLMMessagesAppendFrame, LLMRunFrame
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
from pipecat.turns.user_turn_completion_mixin import UserTurnCompletionConfig
from pipecat.turns.user_turn_strategies import FilterIncompleteUserTurnStrategies
from pipecat.workers.runner import WorkerRunner

from interview import (
    IDLE_NUDGE,
    KICKOFF,
    MAX_MINUTES,
    TIME_UP,
    MuteAfterGoodbye,
    build_system_prompt,
    end_interview,
)
from recorder import SessionRecorder

load_dotenv(override=True)

# How people can connect: "webrtc" is the browser test page; "eval" lets
# automated tests talk to the bot (you'll use it in week 4).
transport_params = {
    "webrtc": lambda: TransportParams(audio_in_enabled=True, audio_out_enabled=True),
    "eval": lambda: EvalTransportParams(audio_in_enabled=True, audio_out_enabled=True),
}


async def run_bot(transport: BaseTransport, runner_args: RunnerArguments):
    # Ears: Groq's hosted Whisper turns your speech into text.
    stt = GroqSTTService(api_key=os.environ["GROQ_API_KEY"])

    # Brain: gpt-oss on Groq, following the interviewer prompt.
    llm = GroqLLMService(
        api_key=os.environ["GROQ_API_KEY"],
        settings=GroqLLMService.Settings(
            model="openai/gpt-oss-20b",
            reasoning_effort="low",  # less thinking, faster replies
            system_instruction=build_system_prompt(),
        ),
    )

    # Voice: Kokoro runs on your laptop, no key needed.
    tts = KokoroTTSService(settings=KokoroTTSService.Settings(voice="af_heart"))

    # The conversation history. The interviewer can call end_interview.
    context = LLMContext(tools=[end_interview])
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(
            vad_analyzer=SileroVADAnalyzer(),
            user_mute_strategies=[MuteAfterGoodbye()],
            # Smart Turn (on by default) listens for an unfinished sentence; this also
            # lets the LLM check your words before it answers.
            user_turn_strategies=FilterIncompleteUserTurnStrategies(
                config=UserTurnCompletionConfig(
                    incomplete_short_timeout=6.0,  # cut off mid-sentence: wait 6 seconds
                    incomplete_long_timeout=15.0,  # "let me think": wait 15 seconds
                )
            ),
            # Silent for 20 seconds after a question: offer to repeat it.
            user_idle_timeout=20.0,
        ),
    )

    @user_aggregator.event_handler("on_user_turn_idle")
    async def on_user_turn_idle(aggregator):
        await aggregator.push_frame(
            LLMMessagesAppendFrame([{"role": "developer", "content": IDLE_NUDGE}], run_llm=True)
        )

    # Saves answer clips, the transcript and response times to sessions/.
    recorder = SessionRecorder()

    # Audio flows top to bottom: mic -> text -> reply -> voice -> speakers.
    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            user_aggregator,
            llm,
            tts,
            transport.output(),
            recorder.audio,
            assistant_aggregator,
        ]
    )

    worker = PipelineWorker(
        pipeline,
        params=PipelineParams(enable_metrics=True, enable_usage_metrics=True),
        idle_timeout_secs=runner_args.pipeline_idle_timeout_secs,
        processor_unusable_policy=ProcessorUnusablePolicy.END,
        observers=[recorder.latency],
    )
    recorder.attach(worker, user_aggregator, assistant_aggregator)
    runner = WorkerRunner(handle_sigint=runner_args.handle_sigint)
    await runner.add_workers(worker)

    async def wrap_up_on_time():
        """After MAX_MINUTES, tell the interviewer to finish after the current answer."""
        await asyncio.sleep(MAX_MINUTES * 60)
        logger.info("Time is up: the interviewer will wrap up")
        await worker.queue_frames(
            [LLMMessagesAppendFrame([{"role": "developer", "content": TIME_UP}], run_llm=False)]
        )

    timer = None

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        nonlocal timer
        logger.info("Candidate connected")
        context.add_message({"role": "developer", "content": KICKOFF})
        await worker.queue_frames([LLMRunFrame()])
        timer = asyncio.create_task(wrap_up_on_time())

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info("Candidate disconnected")
        await runner.cancel()

    await runner.run()
    if timer:
        timer.cancel()


async def bot(runner_args: RunnerArguments):
    transport = await create_transport(runner_args, transport_params)
    await run_bot(transport, runner_args)


if __name__ == "__main__":
    from pipecat.runner.run import main

    main()