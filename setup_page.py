"""The setup page. Paste a job, upload your resume, and get an interview plan."""

from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from loguru import logger

from prep.library import FOLLOW_UP_RULES, MODES, VOICES
from prep.planner import latest_plan, prepare

pages = Jinja2Templates(directory=Path(__file__).parent / "pages")
BLANK_FORM = {
    "company": "",
    "posting": "",
    "mode": "behavioral",
    "difficulty": "standard",
    "voice": "af_heart",
}


def add_setup_page(app: FastAPI):
    """Add the setup page and the plan page to the bot's web server."""

    def setup_form(request: Request, form: dict, error: str = ""):
        choices = {"modes": MODES, "levels": FOLLOW_UP_RULES, "voices": VOICES}
        return pages.TemplateResponse(
            request,
            "setup.html",
            {"form": form, "last": latest_plan(), "error": error, **choices},
        )

    @app.get("/")
    async def home(request: Request):
        return setup_form(request, BLANK_FORM)

    @app.post("/prepare")
    async def make_plan(
        request: Request,
        company: Annotated[str, Form()],
        posting: Annotated[str, Form()],
        resume: Annotated[UploadFile, File()],
        mode: Annotated[str, Form()],
        difficulty: Annotated[str, Form()],
        voice: Annotated[str, Form()],
    ):
        try:
            await prepare(company, posting, resume.file, mode, difficulty, voice)
        except Exception as error:
            logger.exception("Preparing the interview failed")
            form = dict(
                company=company, posting=posting, mode=mode, difficulty=difficulty, voice=voice
            )
            return setup_form(request, form, f"Couldn't prepare the interview: {error}")
        return RedirectResponse("/plan", status_code=303)

    @app.get("/plan")
    async def show_plan(request: Request):
        plan = latest_plan()
        if not plan:
            return RedirectResponse("/")
        return pages.TemplateResponse(
            request, "plan.html", {"plan": plan, "mode": MODES[plan["mode"]], "voices": VOICES}
        )