"""A short company brief, with a source for every fact.

Facts come from the company's Wikipedia article, or from the job posting when Wikipedia has none.
"""

import asyncio
import re
from typing import Literal

import requests

from prep.llm import Strict, ask_json

API = "https://en.wikipedia.org/w/api.php"
# Wikipedia asks every app for its name and a contact link.
HEADERS = {"User-Agent": "interview-coach/1.0 (https://github.com/sadikshachitrakar/Voice-Mock-Interview-Coach)"}


class Fact(Strict):
    topic: Literal["mission", "product", "value", "news"]
    fact: str
    quote: str  # words copied exactly from the text


class Facts(Strict):
    facts: list[Fact]


INSTRUCTIONS = """You help someone prepare for a job interview at a company.
From the text below, write 4 to 8 short facts about the company itself that are useful in an
interview. Skip anything about the job's duties or requirements.
Each fact has a topic: mission (what the company does and for whom), product (a main product
or service), value (a value or principle the text states outright; skip this topic if
there is none), or news (a recent event, with its year).
For each fact, copy a short quote of 3 to 12 words exactly as it appears in the text.
Use only the text. If it says little about the company, return fewer facts, or none."""


def no_brief(reason: str) -> dict:
    """An empty brief, so the interview can still go ahead without company facts."""
    return {"facts": [], "note": reason}


def words(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def ask_wikipedia(params: dict) -> dict:
    response = requests.get(
        API, params={**params, "format": "json", "formatversion": 2}, headers=HEADERS, timeout=20
    )
    response.raise_for_status()  # a clear error if Wikipedia turns the request down
    return response.json()["query"]


def find_article(company: str) -> tuple[str, str, str] | None:
    """Wikipedia's best article whose title names the company: (title, url, text), or None."""
    first_word = (words(company).split() or [""])[0]
    results = ask_wikipedia(
        {"action": "query", "list": "search", "srsearch": f"{company} company", "srlimit": 3}
    )["search"]
    # Only an article whose title names the company counts: Brex, not Brexit.
    titles = [r["title"] for r in results if first_word in words(r["title"]).split()]
    if not titles:
        return None
    page = ask_wikipedia(
        {"action": "query", "prop": "extracts|info", "explaintext": 1, "inprop": "url",
         "titles": titles[0]}
    )["pages"][0]
    return page["title"], page["fullurl"], page.get("extract", "")[:12000]  # the first part is enough


async def facts_from(text: str, source: dict, company: str, role: str) -> list[dict]:
    """Ask gpt-oss for facts, then keep only those whose quote really is in the text."""
    result = await ask_json(INSTRUCTIONS, f"COMPANY: {company}\nROLE: {role}\n\nTEXT\n{text}", Facts)
    text_words = f" {words(text)} "
    return [
        {"topic": f.topic, "fact": f.fact, "sources": [source]}
        for f in result.facts
        if len(words(f.quote).split()) >= 3 and f" {words(f.quote)} " in text_words
    ]


async def research_company(company: str, role: str, posting: str = "") -> dict:
    """Facts from the company's Wikipedia article, or from the job posting if Wikipedia has none."""
    try:
        article = await asyncio.to_thread(find_article, company)
        if article and article[2]:
            title, url, text = article
            facts = await facts_from(text, {"title": f"Wikipedia: {title}", "url": url}, company, role)
            if facts:
                return {"facts": facts}
        if posting:
            facts = await facts_from(posting, {"title": "Job posting", "url": ""}, company, role)
            if facts:
                return {"facts": facts}
    except Exception as error:  # no internet, Wikipedia said no, or Groq's limit
        return no_brief(f"Company research failed ({type(error).__name__}): {error}")
    looked = "on Wikipedia or in the job posting" if posting else "on Wikipedia"
    return no_brief(f"Found no facts about {company} {looked}.")


if __name__ == "__main__":
    # Try it:  uv run python -m prep.company "Duolingo" "Data Analyst" samples/job_a.txt
    import sys
    from pathlib import Path

    from dotenv import load_dotenv

    load_dotenv(override=True)
    posting = Path(sys.argv[3]).read_text() if len(sys.argv) > 3 else ""
    brief = asyncio.run(research_company(sys.argv[1], sys.argv[2], posting))
    for item in brief["facts"]:
        print(f"{item['topic'].upper()}: {item['fact']}")
        for source in item["sources"]:
            print(f"    {source['title']}  {source['url']}")
    print(brief.get("note", f"\n{len(brief['facts'])} facts."))