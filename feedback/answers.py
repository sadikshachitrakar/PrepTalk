"""Work out which plan question each of your answers belongs to."""

import json
from pathlib import Path

from prep.llm import Strict, ask_json


class Match(Strict):
    line: int
    question: int


class Matches(Strict):
    matches: list[Match]


INSTRUCTIONS = """You line up an interview transcript with the interview plan.
For each numbered interviewer line, give the number of the plan question that line asks.
Use 0 when the line asks no plan question: a follow-up, a clarification, a nudge to take
their time, a reply to the candidate's own question, or a goodbye.
Return one match for every interviewer line."""


async def group_answers(session: Path, plan: dict) -> list[dict]:
    """One entry per plan question you answered, with each part of your answer in order."""
    if not (session / "transcript.jsonl").exists():
        return []  # the call ended before anyone spoke
    transcript = [json.loads(line) for line in (session / "transcript.jsonl").open()]
    transcript = [entry for entry in transcript if entry["text"].strip()]
    lines = [entry["text"] for entry in transcript if entry["speaker"] == "interviewer"]

    questions = "\n".join(f"{n}. {q['question']}" for n, q in enumerate(plan["questions"], 1))
    numbered = "\n".join(f"{n}. {line}" for n, line in enumerate(lines, 1))
    result = await ask_json(INSTRUCTIONS, f"PLAN\n{questions}\n\nINTERVIEWER\n{numbered}", Matches)
    asks = {m.line: m.question for m in result.matches if 1 <= m.question <= len(plan["questions"])}

    # Walk the conversation: a line that asks a plan question starts a new answer;
    # a follow-up keeps adding to the answer you're on.
    answers, current, asked, line = {}, 0, "", 0
    for entry in transcript:
        if entry["speaker"] == "interviewer":
            line += 1
            current = asks.get(line, current)
            asked = entry["text"]
        elif current:
            parts = answers.setdefault(current, {"number": current, "parts": []})["parts"]
            if parts and parts[-1]["turn"] == entry["turn"]:
                parts[-1]["live"] += " " + entry["text"]  # one turn heard as two pieces
            else:
                parts.append({"turn": entry["turn"], "asked": asked, "live": entry["text"]})
    return [answers[number] for number in sorted(answers)]


if __name__ == "__main__":
    # Try it:  uv run python -m feedback.answers   (your newest session)
    import asyncio

    from dotenv import load_dotenv

    load_dotenv(override=True)
    clips = sorted(Path("sessions").glob("*/answers/*.wav"))
    if not clips:
        raise SystemExit("No recorded answers yet. Run an interview first.")
    session = clips[-1].parent.parent
    plan = json.loads((session / "plan.json").read_text())
    for answer in asyncio.run(group_answers(session, plan)):
        print(f"\n{answer['number']}. {plan['questions'][answer['number'] - 1]['question']}")
        for part in answer["parts"]:
            print(f"   Interviewer: {part['asked']}\n   You (turn {part['turn']}): {part['live']}")