"""One row per answer in a small SQLite database, so progress shows across sessions."""

import sqlite3
from pathlib import Path

from feedback.scorer import DIMENSIONS

DB = Path(__file__).parent.parent / "history.db"
COLUMNS = ["session", "company", "role", "mode", "question", "type", "average", *DIMENSIONS]
COLUMNS += ["seconds", "words", "long_pauses", "fillers"]


def save_report(report: dict):
    """Store every answer of one session, replacing that session's old rows."""
    rows = []
    for answer in report["answers"]:
        delivery = answer["delivery"]
        rows.append(
            [report["session"], report["company"], report["role"], report["mode"]]
            + [answer["number"], answer["type"], answer["average"]]
            + [answer["scores"][key]["score"] for key in DIMENSIONS]
            + [delivery["seconds"], delivery["words"], delivery["long_pauses"]]
            + [sum(delivery["fillers"].values())]
        )
    with sqlite3.connect(DB) as db:
        db.execute(
            f"CREATE TABLE IF NOT EXISTS answers ({', '.join(COLUMNS)}, "
            "PRIMARY KEY (session, question))"
        )
        db.execute("DELETE FROM answers WHERE session = ?", [report["session"]])
        db.executemany(f"INSERT INTO answers VALUES ({', '.join('?' * len(COLUMNS))})", rows)


def sessions() -> list[dict]:
    """One row per session, oldest first, with its averages."""
    if not DB.exists():
        return []
    with sqlite3.connect(DB) as db:
        db.row_factory = sqlite3.Row
        rows = db.execute(
            """SELECT session, company, role, mode, COUNT(*) AS answers,
                      ROUND(AVG(NULLIF(average, 0)), 1) AS score,
                      ROUND(SUM(words) * 60.0 / SUM(seconds)) AS wpm,
                      ROUND(SUM(fillers) * 60.0 / SUM(seconds), 1) AS fillers_per_minute,
                      SUM(long_pauses) AS long_pauses
               FROM answers GROUP BY session ORDER BY session"""
        ).fetchall()
    return [dict(row) for row in rows]