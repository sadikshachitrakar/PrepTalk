"""Build the feedback report for one session and add it to your history."""

import json
from datetime import datetime
from pathlib import Path

from feedback.answers import group_answers
from feedback.delivery import combine, measure
from feedback.history import save_report
from feedback.scorer import DIMENSIONS, score_answer
from feedback.transcribe import transcribe

# What to practice next, based on your weakest rubric dimension.
PRACTICE = {
    "answers_question": "Answer the question in your first sentence, then back it up.",
    "structure": "Tell each story in four beats: situation, task, what you did, result.",
    "specificity": "Before your next session, note two numbers and one name for every project.",
    "ownership": 'Say "I" for what you did. Use "we" for the team, then say what your part was.',
    "result_and_reflection": "End every story with the result, a number if you can, and a lesson.",
    "role_fit": "Close each answer by linking it to something in the job description.",
}


async def build_report(session: Path) -> dict:
    """Transcribe, measure and score every answer, then save report.json and your history."""
    if not (session / "plan.json").exists():
        raise ValueError(f"{session.name} has no plan.json, so it was recorded before Week 2.")
    plan = json.loads((session / "plan.json").read_text())

    answers = []
    for group in await group_answers(session, plan):
        question = plan["questions"][group["number"] - 1]
        exchange, said, clips, measured = [], [], [], []
        for part in group["parts"]:
            text = part["live"]  # what live transcription heard, used if there's no clip
            clip = session / "answers" / f"turn_{part['turn']:02d}.wav"
            if clip.exists():
                heard = await transcribe(clip)
                measured.append(measure(heard["text"], heard["words"]))
                clips.append(part["turn"])
                text = heard["text"] or text
            exchange.append({"asked": part["asked"], "said": text})
            said.append(text)
        conversation = "\n".join(
            f"Interviewer: {e['asked']}\nCandidate: {e['said']}" for e in exchange
        )
        feedback = await score_answer(question, conversation, " ".join(said))
        answers.append(
            {
                "number": group["number"],
                "type": question.get("type", "general"),
                "question": question["question"],
                "exchange": exchange,
                "clips": clips,
                "delivery": combine(measured),
                **feedback,
            }
        )

    report = {
        "session": session.name,
        "created": datetime.now().isoformat(timespec="seconds"),
        "company": plan["company"],
        "role": plan["role"],
        "mode": plan["mode"],
        "difficulty": plan["difficulty"],
        "answers": answers,
        "summary": summarize(answers),
    }
    (session / "report.json").write_text(json.dumps(report, indent=2))
    save_report(report)
    return report


def summarize(answers: list[dict]) -> dict:
    """Strengths, fixes, delivery and what to practice next, all worked out in code."""
    averages = {}
    for key in DIMENSIONS:
        given = [a["scores"][key]["score"] for a in answers if a["scores"][key]["score"]]
        if given:
            averages[key] = round(sum(given) / len(given), 1)
    ranked = sorted(averages, key=averages.get, reverse=True)
    scored = sorted((a for a in answers if a["average"]), key=lambda a: a["average"])
    return {
        "average": round(sum(a["average"] for a in scored) / len(scored), 1) if scored else 0.0,
        "dimensions": {DIMENSIONS[key]: value for key, value in averages.items()},
        "strengths": [f"{DIMENSIONS[key]} ({averages[key]} out of 5)" for key in ranked[:3]],
        "fixes": [f"Question {a['number']}: {a['fix']}" for a in scored[:3]],
        "practice_next": PRACTICE[ranked[-1]] if ranked else "",
        "delivery": combine([a["delivery"] for a in answers]),
    }


if __name__ == "__main__":
    # Try it:  uv run python -m feedback.report   (your newest session, or name a folder)
    import asyncio
    import sys

    from dotenv import load_dotenv

    load_dotenv(override=True)
    clips = sorted(Path("sessions").glob("*/answers/*.wav"))
    if len(sys.argv) > 1:
        session = Path(sys.argv[1])
    elif clips:
        session = clips[-1].parent.parent  # the newest session with recorded answers
    else:
        raise SystemExit("No recorded answers yet. Run an interview first.")
    report = asyncio.run(build_report(session))
    summary = report["summary"]
    print(f"{report['role']} at {report['company']}: {summary['average']} out of 5")
    print("Strengths:", "; ".join(summary["strengths"]))
    print("Fix first:", *summary["fixes"], sep="\n  ")
    print("Practice next:", summary["practice_next"])
    print(f"Saved {session / 'report.json'}")