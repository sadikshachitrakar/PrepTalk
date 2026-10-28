"""The mock interviewer, running your newest interview plan.

Run it:  uv run bot.py -t webrtc
Then open http://localhost:7860 in Chrome.
"""

import asyncio
import os

from pathlib import Path
from tempfile import mkdtemp

from dotenv import load_dotenv
from feedback.report import build_report
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
from pipecat.runner.types import EvalRunnerArguments, RunnerArguments
from pipecat.runner.utils import create_transport
from pipecat.services.groq.llm import GroqLLMService
from pipecat.services.groq.stt import GroqSTTService
from pipecat.services.kokoro.tts import KokoroTTSService
from pipecat.transcriptions.language import Language
from pipecat.transports.base_transport import BaseTransport, TransportParams
from pipecat.turns.user_turn_completion_mixin import UserTurnCompletionConfig
from pipecat.turns.user_turn_strategies import FilterIncompleteUserTurnStrategies
from pipecat.workers.runner import WorkerRunner
from report_page import add_report_pages
from setup_page import add_setup_page

from interview import (
    IDLE_NUDGE,
    KICKOFF,
    MuteAfterGoodbye,
    OneTurnPerReply,
    TimeKeeper,
    build_system_prompt,
    end_interview,
    load_plan,
)
from recorder import SESSIONS, SessionRecorder

load_dotenv(override=True)

# How people can connect: "webrtc" is the browser test page; "eval" lets
# automated tests talk to the bot (you'll use it in week 4).
transport_params = {
    "webrtc": lambda: TransportParams(audio_in_enabled=True, audio_out_enabled=True),
    "eval": lambda: EvalTransportParams(audio_in_enabled=True, audio_out_enabled=True),
}


async def run_bot(transport: BaseTransport, runner_args: RunnerArguments):
    # Your newest plan from plans/, or the Week 1 questions if there is none yet.
    testing = isinstance(runner_args, EvalRunnerArguments)
    if testing:
        test = runner_args.body or {}
        plan = load_plan(test.get("plan", "tests/plan.json"))
        plan["minutes"] = test.get("minutes", plan["minutes"])
    else:
        # Your newest plan from plans/, or the Week 1 questions if there is none yet.
        plan = load_plan()
    logger.info(f"Plan: {plan['mode']} interview for the {plan['role']} role at {plan['company']}")

    # Ears: Groq's hosted Whisper turns your speech into text.
    stt = GroqSTTService(api_key=os.environ["GROQ_API_KEY"])

    # Brain: gpt-oss on Groq, following the interviewer prompt. The 120b model, because
    # in replayed tests the 20b one ended the interview after the first answer 3 times in 10.
    llm = GroqLLMService(
        api_key=os.environ["GROQ_API_KEY"],
        settings=GroqLLMService.Settings(
            model="openai/gpt-oss-120b",
            # Medium, not low: on low it often ran past its own turn ("...projects?● Thanks.
            # Next question...") and even answered for the candidate. Costs about 0.4 s a reply.
            reasoning_effort="medium",
            system_instruction=build_system_prompt(plan),
        ),
    )

    # Voice: Kokoro runs on your laptop. Voices starting with "b" are British.
    accent = Language.EN_GB if plan["voice"].startswith("b") else Language.EN_US
    tts = KokoroTTSService(settings=KokoroTTSService.Settings(voice=plan["voice"], language=accent))

    # The conversation history. The interviewer can call end_interview.
    context = LLMContext(tools=[end_interview])
    mute = MuteAfterGoodbye()
    # Says goodbye in code once time is up (see wrap_up_on_time below).
    time_keeper = TimeKeeper(mute)
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(
            vad_analyzer=SileroVADAnalyzer(),
            user_mute_strategies=[mute],
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

    # Saves the plan, answer clips, the transcript and response times to sessions/.
    # Tests save to a throwaway folder instead, so sessions/ keeps only your interviews.
    recorder = SessionRecorder(plan, root=Path(mkdtemp()) if testing else SESSIONS)

    # Audio flows top to bottom: mic -> text -> reply -> voice -> speakers.
    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            user_aggregator,
            llm,
            OneTurnPerReply(),  # never speaks a second turn the LLM ran on into
            time_keeper,
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
        """When the mode's time is up, finish after the current answer."""
        await asyncio.sleep(plan["minutes"] * 60)
        logger.info("Time is up: the interviewer will wrap up after this answer")
        time_keeper.time_up = True

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

    # The call is over: write its feedback report while you open the report page.
    if not testing and any((recorder.folder / "answers").glob("*.wav")):
        try:
            await build_report(recorder.folder)
            logger.info(f"Report ready: http://localhost:7860/report/{recorder.folder.name}")
        except Exception:
            logger.exception("The report failed. Rerun it with: uv run python -m feedback.report")


async def bot(runner_args: RunnerArguments):
    transport = await create_transport(runner_args, transport_params)
    await run_bot(transport, runner_args)


if __name__ == "__main__":
    from pipecat.runner.run import app, main

    add_setup_page(app)  # the setup page at http://localhost:7860
    add_report_pages(app)  # /report and /history
    main()