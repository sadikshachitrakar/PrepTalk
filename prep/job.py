"""Turn a job posting into skills, duties and the competencies it needs."""

from typing import Literal

from prep.llm import Strict, ask_json

# The fixed list of behavioral competencies. Every job maps onto 4 to 6 of them.
Competency = Literal[
    "ownership",
    "teamwork",
    "conflict",
    "failure and learning",
    "ambiguity",
    "prioritizing under deadlines",
    "influencing without authority",
    "customer focus",
    "learning fast",
    "explaining technical work",
]


class CompetencyNeed(Strict):
    competency: Competency
    evidence: str  # the line from the posting that shows it


class JobProfile(Strict):
    title: str
    seniority: Literal["intern", "entry", "mid", "senior", "lead"]
    skills: list[str]
    responsibilities: list[str]
    competencies: list[CompetencyNeed]


INSTRUCTIONS = """You read job postings for an interview practice app. Fill in the JSON from the posting.
- title: the job title as written.
- seniority: intern, entry, mid, senior or lead, judged from the title and the years of experience asked for.
- skills: up to 12 tools, methods and concepts the posting asks for, most important first, a few words each.
- responsibilities: up to 8 duties, each copied word for word from the posting.
- competencies: the 4 to 6 behavioral competencies this job needs most. For each, copy the line from the posting that shows it, word for word, as evidence.
Copy text exactly. Never add anything that isn't in the posting."""


async def parse_job(posting: str) -> JobProfile:
    return await ask_json(INSTRUCTIONS, posting, JobProfile)


if __name__ == "__main__":
    # Try it:  uv run python -m prep.job samples/job_a.txt
    import asyncio
    import sys
    from pathlib import Path

    from dotenv import load_dotenv

    load_dotenv(override=True)
    posting = Path(sys.argv[1]).read_text()
    print(asyncio.run(parse_job(posting)).model_dump_json(indent=2))