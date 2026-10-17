"""The interviewer's prompt, how the interview ends, and the time limit."""

from pathlib import Path

from pipecat.adapters.schemas.direct_function import tool_options
from pipecat.frames.frames import (
    EndWorkerFrame,
    FunctionCallResultProperties,
    FunctionCallsStartedFrame,
    TTSSpeakFrame,
)
from pipecat.services.llm_service import FunctionCallParams
from pipecat.turns.user_mute.base_user_mute_strategy import BaseUserMuteStrategy

HERE = Path(__file__).parent
MAX_MINUTES = 15

KICKOFF = "The candidate just joined. Greet them and ask the first question."
TIME_UP = "Time is up. Do not ask any more questions. Call end_interview now."
FAREWELL = "Thank you for your time today. That's the end of our interview. Goodbye!"
# Used when the candidate stays silent after a question.
IDLE_NUDGE = (
    "The candidate has been silent since your last question. Start your reply with ● "
    "and say, in one short sentence, that they can take their time and you're happy "
    "to repeat the question."
)


def build_system_prompt() -> str:
    """Fill prompts/interviewer.md with the questions from questions.txt."""
    template = (HERE / "prompts" / "interviewer.md").read_text()
    lines = (HERE / "questions.txt").read_text().splitlines()
    questions = [line.strip() for line in lines if line.strip()]
    numbered = "\n".join(f"{i}. {q}" for i, q in enumerate(questions, start=1))
    return (
        template.replace("{questions}", numbered)
        .replace("{count}", str(len(questions)))
        .replace("{max_minutes}", str(MAX_MINUTES))
    )


@tool_options(cancel_on_interruption=False)
async def end_interview(params: FunctionCallParams):
    """End the interview once the candidate has no more questions. Do not say goodbye yourself."""
    # run_llm=False: the LLM doesn't reply to this result; we say a fixed goodbye instead.
    await params.result_callback(
        {"status": "ended"}, properties=FunctionCallResultProperties(run_llm=False)
    )
    await params.llm.push_frame(TTSSpeakFrame(FAREWELL))
    # Ends the session after the goodbye has finished playing.
    await params.llm.push_frame(EndWorkerFrame())


class MuteAfterGoodbye(BaseUserMuteStrategy):
    """Stop listening once end_interview is called, so a last "thanks" can't cut off the goodbye."""

    def __init__(self):
        super().__init__()
        self.ending = False

    async def process_frame(self, frame) -> bool:
        await super().process_frame(frame)
        if isinstance(frame, FunctionCallsStartedFrame):
            if any(call.function_name == "end_interview" for call in frame.function_calls):
                self.ending = True
        return self.ending