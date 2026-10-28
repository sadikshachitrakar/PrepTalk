"""The interviewer's prompt (built from your plan), how the interview ends, and the time limit."""
import json
from pathlib import Path

from pipecat.frames.frames import (
    EndWorkerFrame,
    FunctionCallResultProperties,
    FunctionCallsStartedFrame,
    LLMFullResponseStartFrame,
    LLMTextFrame,
    TTSSpeakFrame,
)
from pipecat.processors.frame_processor import FrameProcessor
from pipecat.services.llm_service import FunctionCallParams
from pipecat.turns.user_mute.base_user_mute_strategy import BaseUserMuteStrategy

from prep.library import FOLLOW_UP_RULES, MODES
from prep.planner import latest_plan

HERE = Path(__file__).parent
MAX_MINUTES = 15  # used only until you've prepared a plan

KICKOFF = "The candidate just joined. Greet them and ask the first question."
FAREWELL = "Thank you for your time today. That's the end of our interview. Goodbye!"
TIME_UP_FAREWELL = "Thanks. That's all we have time for today. " + FAREWELL
# Used when the candidate stays silent after a question (Week 1, Day 4).
IDLE_NUDGE = (
    "The candidate has been silent since your last question. Start your reply with ● "
    "and say, in one short sentence, that they can take their time and you're happy "
    "to repeat the question."
)


def week1_plan() -> dict:
    """Your Week 1 questions, used until you prepare a plan on the setup page."""
    lines = (HERE / "questions.txt").read_text().splitlines()
    questions = [line.strip() for line in lines if line.strip()]
    return {
        "company": "a company",
        "role": "open",
        "mode": "full",
        "difficulty": "standard",
        "voice": "af_heart",
        "minutes": MAX_MINUTES,
        "questions": [
            {"question": q, "strong_answer_covers": [], "follow_ups": []} for q in questions
        ],
        "brief": {"facts": []},
        "resume": {"first_name": ""},
    }


def load_plan(path: str | None = None) -> dict:
    """The plan file at `path` (the tests use one), else your newest plan or Week 1's questions."""
    if path:
        return json.loads((HERE / path).read_text())
    return latest_plan() or week1_plan()


def build_system_prompt(plan: dict) -> str:
    """Fill prompts/interviewer.md with the plan's questions, rules and company facts."""
    mode = MODES[plan["mode"]]
    lines = []
    for number, q in enumerate(plan["questions"], start=1):
        lines.append(f"{number}. {q['question']}")
        if q["strong_answer_covers"]:
            lines.append(
                f"   Notes: a strong answer covers {'; '.join(q['strong_answer_covers'])}."
            )
        if q["follow_ups"] and mode["follow_ups"]:
            lines.append(f"   Possible follow-ups: {' / '.join(q['follow_ups'])}")
    if mode["follow_ups"]:
        follow_up_rules = FOLLOW_UP_RULES[plan["difficulty"]]
    else:
        follow_up_rules = "Never ask follow-ups in this drill."
    facts = "\n".join(f"- {fact['fact']}" for fact in plan["brief"]["facts"])

    values = {
        "company": plan["company"],
        "role": plan["role"],
        "mode_rules": mode["rules"],
        "count": str(len(plan["questions"])),
        "questions": "\n".join(lines),
        "follow_up_rules": follow_up_rules,
        "candidate": plan["resume"]["first_name"] or "the candidate",
        "company_facts": facts or "- None. Say you can't share details today.",
        "max_minutes": str(plan["minutes"]),
    }
    prompt = (HERE / "prompts" / "interviewer.md").read_text()
    for key, value in values.items():
        prompt = prompt.replace("{" + key + "}", value)
    return prompt


# No cancel_on_interruption=False here: in Pipecat 1.12 that makes a tool "async" and adds
# prompt rules about late tool results, which led the interviewer to end calls early.
# MuteAfterGoodbye already stops the candidate from cutting off the goodbye.
async def end_interview(params: FunctionCallParams):
    """End the interview when the last question is done. Do not say goodbye yourself."""
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


class OneTurnPerReply(FrameProcessor):
    """Cuts a reply where the LLM starts writing a second turn.

    Every reply starts with a turn marker (●, ◐ or ○), which Pipecat removes before the text
    reaches here. So a marker in the middle of a reply means the model ran on: it finished
    its question, then began the next turn or even answered for the candidate. Everything
    from that marker on is dropped, so it's never spoken or saved in the conversation.
    """

    MARKERS = "●◐○"

    def __init__(self):
        super().__init__()
        self.cut = False

    async def process_frame(self, frame, direction):
        await super().process_frame(frame, direction)
        if isinstance(frame, LLMFullResponseStartFrame):
            self.cut = False
        elif isinstance(frame, LLMTextFrame):
            if self.cut:
                return
            stray = next((i for i, c in enumerate(frame.text) if c in self.MARKERS), None)
            if stray is not None:
                self.cut = True
                frame.text = frame.text[:stray]
                if not frame.text.strip():
                    return
        await self.push_frame(frame, direction)


class TimeKeeper(FrameProcessor):
    """Ends the interview in code when time is up. Telling the LLM "time is up" isn't
    enough: in tests it asked the next question anyway most of the time.

    It sits between the LLM and the voice. Once time is up, the interviewer's next spoken
    reply is swapped for a fixed goodbye. A thinking pause gets no spoken reply (the LLM
    answers with ◐ or ○), so the candidate still gets to finish their answer.
    """

    def __init__(self, mute: MuteAfterGoodbye):
        super().__init__()
        self.mute = mute
        self.time_up = False  # set by the timer in bot.py
        self.swap_reply = False  # true for a reply that started after time ran out
        self.ended = False

    async def process_frame(self, frame, direction):
        await super().process_frame(frame, direction)
        if isinstance(frame, LLMFullResponseStartFrame):
            self.swap_reply = self.time_up  # never cut off a reply already being spoken
        elif isinstance(frame, LLMTextFrame) and self.swap_reply:
            if not self.ended:
                self.ended = True
                self.mute.ending = True  # stop listening, as end_interview does
                await self.push_frame(TTSSpeakFrame(TIME_UP_FAREWELL))
                await self.push_frame(EndWorkerFrame())
            return  # the LLM's own words are never spoken
        elif isinstance(frame, TTSSpeakFrame) and self.ended:
            return  # end_interview raced us: one goodbye is enough
        await self.push_frame(frame, direction)