"""Turn the job, your resume and the company brief into an interview plan."""

import asyncio
import json
import re
from datetime import datetime
from itertools import cycle
from pathlib import Path
from typing import Literal

from prep.company import research_company
from prep.job import parse_job
from prep.library import FALLBACKS, LIBRARY, MODES
from prep.llm import SMART_MODEL, Strict, ask_json
from prep.resume import parse_resume, read_resume

PLANS = Path(__file__).parent.parent / "plans"


class PlannedQuestion(Strict):
    type: Literal[
        "motivation",
        "resume",
        "job_skill",
        "technical",
        "scenario",
        "behavioral",
        "situational",
        "company",
    ]
    competency: str
    based_on: str
    question: str
    strong_answer_covers: list[str]
    follow_ups: list[str]


class Plan(Strict):
    questions: list[PlannedQuestion]


INSTRUCTIONS = """You plan practice job interviews. Write exactly the questions requested, in the order listed.

For every question:
- based_on: copy one line word for word from the JOB POSTING, the RESUME or the COMPANY FACTS. It shows where the question came from. Never paraphrase it.
- question: one or two spoken sentences, the way a real interviewer would ask. Make it specific to this job, this candidate or this company. A question that would fit any job is not allowed.
- competency: for behavioral and situational questions, the competency you were given; otherwise an empty string.
- strong_answer_covers: 3 or 4 short points a strong answer includes.
- follow_ups: 2 short follow-up questions to ask if the answer has a gap.

Question types:
- motivation: why this company and this role. Base it on the posting or a company fact.
- resume: a deep dive into one project or role on the resume: what they decided, what they did, what happened. Base it on a resume line.
- job_skill: how they have used a skill the posting asks for. Base it on the posting line that names the skill.
- technical: explain a concept from the posting simply and correctly, as if to a non-expert. Base it on a posting line.
- scenario: how they would build or fix something this job does. Base it on a responsibility in the posting.
- behavioral: "Tell me about a time..." for the competency given. Base it on the posting line that shows the competency, or a company VALUE fact that matches it.
- situational: "What would you do if..." for the competency given, set in this job. Base it on a posting line.
- company: their view of the company's product, mission or recent news. Base it on a company fact.

Match the depth to the seniority. Friendly difficulty means plain, warm wording. Standard means typical interview questions. Tough means harder versions that probe trade-offs, failures and numbers."""


def words(text: str) -> str:
    """Lowercase words only, so punctuation and line breaks don't matter."""
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def is_quoted(quote: str, sources: str) -> bool:
    """True if the quote (at least 2 words) appears word for word in the sources."""
    pieces = [words(piece) for piece in re.split(r"\.\.\.|…", quote) if words(piece)]
    long_enough = sum(len(piece.split()) for piece in pieces) >= 2
    return long_enough and all(f" {piece} " in sources for piece in pieces)


def fixed(slot: str, source: str, item: dict) -> dict:
    """A library or fallback question in the same shape as a planned one."""
    return {"type": slot, "competency": "", "based_on": "", **item, "source": source}


async def write_questions(posting, resume_text, job, brief, mode, difficulty) -> list[dict]:
    slots = MODES[mode]["slots"]

    # Ask the LLM only for the slots the library doesn't cover, giving each
    # behavioral or situational slot one of the job's competencies in turn.
    competencies = cycle([need.competency for need in job.competencies] or ["ownership"])
    wanted = []
    for slot in slots:
        if slot in ("behavioral", "situational"):
            wanted.append(f"{slot}, competency: {next(competencies)}")
        elif slot not in LIBRARY:
            wanted.append(slot)
    facts = "\n".join(f"{f['topic'].upper()}: {f['fact']}" for f in brief["facts"])
    request = (
        f"JOB POSTING\n{posting}\n\nRESUME\n{resume_text}\n\nCOMPANY FACTS\n{facts or '(none)'}\n\n"
        f"Job title: {job.title}. Seniority: {job.seniority}. Difficulty: {difficulty}.\n\n"
        f"Write these {len(wanted)} questions, in this order:\n"
        + "\n".join(f"{n}. {item}" for n, item in enumerate(wanted, start=1))
    )
    plan = await ask_json(INSTRUCTIONS, request, Plan, model=SMART_MODEL, effort="medium")

    # Fill each slot in order. A planned question that can't quote the line it
    # came from is rejected, and a standard question takes its place.
    sources = f" {words(posting + ' ' + resume_text + ' ' + facts)} "
    planned = list(plan.questions)
    questions = []
    for slot in slots:
        if slot in LIBRARY:
            questions.append(fixed(slot, "library", LIBRARY[slot]))
            continue
        match = next((q for q in planned if q.type == slot), None)
        if match:
            planned.remove(match)
        if match and is_quoted(match.based_on, sources):
            questions.append({**match.model_dump(), "source": "planner"})
        else:
            questions.append(fixed(slot, "fallback", FALLBACKS[slot]))
    return questions


async def prepare(company, posting, resume_pdf, mode, difficulty, voice) -> Path:
    """Run every prep step and save the plan in plans/. Returns the file's path."""
    resume_text = read_resume(resume_pdf)

    async def job_then_company():
        job = await parse_job(posting)
        return job, await research_company(company, job.title, posting)

    # Your resume is read while the job and the company are researched.
    (job, brief), resume = await asyncio.gather(job_then_company(), parse_resume(resume_text))
    questions = await write_questions(posting, resume_text, job, brief, mode, difficulty)

    plan = {
        "created": datetime.now().isoformat(timespec="seconds"),
        "company": company,
        "role": job.title,
        "mode": mode,
        "difficulty": difficulty,
        "voice": voice,
        "minutes": MODES[mode]["minutes"],
        "questions": questions,
        "brief": brief,
        "job": job.model_dump(),
        "resume": resume.model_dump(),
        "posting": posting,
    }
    PLANS.mkdir(exist_ok=True)
    name = re.sub(r"[^a-z0-9]+", "-", company.lower()).strip("-") or "company"
    path = PLANS / f"{datetime.now():%Y-%m-%d_%H-%M-%S}_{name}.json"
    path.write_text(json.dumps(plan, indent=2))
    return path


def latest_plan() -> dict | None:
    """The most recently prepared plan, or None if there isn't one yet."""
    files = sorted(PLANS.glob("*.json"))
    return json.loads(files[-1].read_text()) if files else None


if __name__ == "__main__":
    # Try it:
    # uv run python -m prep.planner samples/job_a.txt "Company" ~/Documents/resume.pdf behavioral standard
    import sys

    from dotenv import load_dotenv

    load_dotenv(override=True)
    posting_file, company, pdf, mode, difficulty = sys.argv[1:6]
    posting = Path(posting_file).read_text()
    path = asyncio.run(prepare(company, posting, pdf, mode, difficulty, "af_heart"))
    plan = json.loads(path.read_text())
    for number, q in enumerate(plan["questions"], start=1):
        print(f"{number}. [{q['type']}] {q['question']}")
        print(f"   based on: {q['based_on'] or q['source']}")
    print(f"\nSaved {path}")