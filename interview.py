"""The interviewer's prompt (built from your plan), how the interview ends, and the time limit."""

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

from prep.library import FOLLOW_UP_RULES, MODES
from prep.planner import latest_plan

HERE = Path(__file__).parent
MAX_MINUTES = 15  # used only until you've prepared a plan

KICKOFF = "The candidate just joined. Greet them and ask the first question."
TIME_UP = "Time is up. Do not ask any more questions. Call end_interview now."
FAREWELL = "Thank you for your time today. That's the end of our interview. Goodbye!"
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


def load_plan() -> dict:
    """The plan you prepared most recently, or the Week 1 questions."""
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


@tool_options(cancel_on_interruption=False)
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