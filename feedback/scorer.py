"""Day 4: score one answer on content, check its quotes, and write a stronger version."""

import re
from pathlib import Path

from prep.llm import SMART_MODEL, Strict, ask_json
from prep.planner import is_quoted, words

PROMPT = (Path(__file__).parent.parent / "prompts" / "scorer.md").read_text()
DIMENSIONS = {
    "answers_question": "Answers the question",
    "structure": "Structure",
    "specificity": "Specificity",
    "ownership": "Ownership",
    "result_and_reflection": "Result and reflection",
    "role_fit": "Role fit",
}


class Score(Strict):
    score: int  # 1 to 5, or 0 when the dimension doesn't apply
    quote: str
    why: str


class Scores(Strict):
    answers_question: Score
    structure: Score
    specificity: Score
    ownership: Score
    result_and_reflection: Score
    role_fit: Score


class Feedback(Strict):
    scores: Scores
    fix: str
    stronger: str


NUMBER = re.compile(r"\d+(?:[.,]\d+)*%?")


def keep_your_numbers(stronger: str, said: str) -> str:
    """Swap any number you never said for a placeholder, so no result is invented."""
    yours = {number.rstrip("%") for number in NUMBER.findall(said)}
    return NUMBER.sub(
        lambda m: m.group() if m.group().rstrip("%") in yours else "[add the number]", stronger
    )


async def score_answer(question: dict, exchange: str, said: str) -> dict:
    """Score one answer. `exchange` is the back-and-forth; `said` is only your words."""
    details = f"type: {question.get('type', 'general')}"
    if question.get("competency"):
        details += f", competency: {question['competency']}"
    covers = "; ".join(question.get("strong_answer_covers", [])) or "not given"
    request = (
        f"QUESTION ({details})\n{question['question']}\n"
        f"A strong answer covers: {covers}\n\nTHE EXCHANGE\n{exchange}"
    )
    feedback = await ask_json(PROMPT, request, Feedback, model=SMART_MODEL, effort="medium")

    # Code checks every quote against your words and drops any that isn't there.
    yours = f" {words(said)} "
    scores, dropped = feedback.scores.model_dump(), 0
    for score in scores.values():
        score["score"] = min(max(score["score"], 0), 5)
        if score["quote"] and not is_quoted(score["quote"], yours):
            score["quote"], dropped = "", dropped + 1
    given = [score["score"] for score in scores.values() if score["score"]]
    return {
        "scores": scores,
        "average": round(sum(given) / len(given), 1) if given else 0.0,
        "fix": feedback.fix,
        "stronger": keep_your_numbers(feedback.stronger, said),
        "quotes_dropped": dropped,
    }


if __name__ == "__main__":
    # Try it:  uv run python -m feedback.scorer   (the same story told weakly, then well)
    import asyncio

    from dotenv import load_dotenv

    load_dotenv(override=True)
    question = {
        "type": "behavioral",
        "competency": "ownership",
        "question": "Tell me about a time you owned a problem nobody assigned to you.",
        "strong_answer_covers": ["a concrete situation", "your own actions", "a measured result"],
    }
    weak = "We had some issues with the data pipeline and we fixed them as a team. It went well."
    strong = (
        "Last spring our nightly data load kept failing and nobody owned it. I traced the "
        "failures to a schema change, wrote a validation step and set up an alert. Failures "
        "dropped from four a week to zero, and I learned to add checks before I add fixes."
    )
    for name, said in (("Weak", weak), ("Strong", strong)):
        exchange = f"Interviewer: {question['question']}\nCandidate: {said}"
        result = asyncio.run(score_answer(question, exchange, said))
        print(f"\n{name} answer: average {result['average']}")
        for key, score in result["scores"].items():
            print(f'  {DIMENSIONS[key]}: {score["score"]}  "{score["quote"]}"')
        print(f"  Fix: {result['fix']}\n  Stronger: {result['stronger']}")