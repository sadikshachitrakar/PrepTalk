"""Read your resume PDF, remove contact details, and pull out projects and claims."""

import re

from pypdf import PdfReader

from prep.llm import Strict, ask_json

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")
PHONE = re.compile(r"(\+\d{1,3}[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b")


class Role(Strict):
    title: str
    organization: str
    dates: str


class Project(Strict):
    name: str
    summary: str
    my_part: str  # what the candidate did themselves
    results: list[str]


class ResumeProfile(Strict):
    first_name: str
    roles: list[Role]
    projects: list[Project]
    claims: list[str]  # lines with a result or a number, word for word
    skills: list[str]


INSTRUCTIONS = """You read resumes for an interview practice app. Fill in the JSON from the resume.
- first_name: the candidate's first name, or an empty string if it's missing.
- roles: jobs and internships, newest first, with dates as written.
- projects: up to 6 projects or major pieces of work, each with a one-sentence summary, what the candidate did themselves, and the results as written.
- claims: up to 10 lines that state a result or a number, each copied word for word.
- skills: up to 15 skills listed on the resume.
Copy facts and numbers exactly. Never invent, round or improve anything."""


def read_resume(pdf) -> str:
    """Pull the text out of a PDF, then remove email addresses and phone numbers."""
    text = "\n".join(page.extract_text() or "" for page in PdfReader(pdf).pages)
    if not text.strip():
        raise ValueError("No text found in this PDF. Export it from Word or Google Docs instead.")
    text = EMAIL.sub("[email removed]", text)
    return PHONE.sub("[phone removed]", text)


async def parse_resume(text: str) -> ResumeProfile:
    return await ask_json(INSTRUCTIONS, text, ResumeProfile)


if __name__ == "__main__":
    # Try it:  uv run python -m prep.resume ~/Documents/resume.pdf
    import asyncio
    import sys

    from dotenv import load_dotenv

    load_dotenv(override=True)
    text = read_resume(sys.argv[1])
    print(text[:400], "...\n")
    print(asyncio.run(parse_resume(text)).model_dump_json(indent=2))