"""The report page, the history page, and replaying your answer clips."""

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from feedback.history import sessions
from feedback.scorer import DIMENSIONS
from prep.library import MODES

SESSIONS = Path(__file__).parent / "sessions"
pages = Jinja2Templates(directory=Path(__file__).parent / "pages")


def session_folder(name: str) -> Path:
    """A folder inside sessions/ and nothing else, whatever the address says."""
    folder = SESSIONS / name
    if name.startswith(".") or not folder.is_dir():
        raise HTTPException(404)
    return folder


def add_report_pages(app: FastAPI):
    """Add /report, /history and the clip player to the bot's web server."""

    @app.get("/report")
    async def latest_report():
        folders = sorted(SESSIONS.glob("*/"))
        return RedirectResponse(f"/report/{folders[-1].name}" if folders else "/")

    @app.get("/report/{name}")
    async def show_report(request: Request, name: str):
        saved = session_folder(name) / "report.json"
        report = json.loads(saved.read_text()) if saved.exists() else None
        paces = [row["wpm"] for row in sessions() if row["wpm"]]
        your_pace = round(sum(paces) / len(paces)) if paces else None
        return pages.TemplateResponse(
            request,
            "report.html",
            {"report": report, "dimensions": DIMENSIONS, "modes": MODES, "your_pace": your_pace},
        )

    @app.get("/history")
    async def show_history(request: Request):
        return pages.TemplateResponse(request, "history.html", {"rows": sessions()[::-1]})

    @app.get("/clip/{name}/{turn}")
    async def play_clip(name: str, turn: int):
        clip = session_folder(name) / "answers" / f"turn_{turn:02d}.wav"
        if not clip.exists():
            raise HTTPException(404)
        return FileResponse(clip, media_type="audio/wav")