import json
import logging
import os
from pathlib import Path

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

_ROOT = Path(__file__).parent.parent
_PROMPTS = _ROOT / "prompts"


# at module top, after imports
_CLIENT = None

def _client():
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    return _CLIENT


def _read(*parts: str) -> str:
    return (_ROOT / Path(*parts)).read_text(encoding="utf-8")


def chat(message: str, open_tasks: list[dict] = []) -> str:
    """Free-form conversation with full character + profile context."""
    system = _read("prompts", "character.md") + "\n\n" + _read("profile.md")
    if open_tasks:
        task_lines = "\n".join(f"#{t['id']} {t['title']}" for t in open_tasks)
        system = f"Current open tasks:\n{task_lines}\n\n" + system
    try:
        response = _client().models.generate_content(
            model="gemini-2.5-flash",
            contents=message,
            config=types.GenerateContentConfig(
                system_instruction=system,
            ),
        )
        return response.text.strip()
    except Exception:
        logger.exception("chat failed for message=%r", message)
        return "Error reaching Gemini."


def parse_task(text: str) -> dict:
    """Extract title, due_date, notes from free text via Gemini JSON mode."""
    system = _read("prompts", "parse_task.md") + "\n\n" + _read("profile.md")
    try:
        response = _client().models.generate_content(
            model="gemini-2.5-flash",
            contents=text,
            config=types.GenerateContentConfig(
                system_instruction=system,
                response_mime_type="application/json",
            ),
        )
        data = json.loads(response.text)
        return {
            "title": data.get("title") or text,
            "due_date": data.get("due_date") or None,
            "notes": data.get("notes") or None,
        }
    except Exception:
        logger.exception("parse_task failed for text=%r", text)
        return {"title": text, "due_date": None, "notes": None}


def _fmt_calendar_event(event: dict) -> str:
    start, end = event["start"], event["end"]
    if "T" in start:
        time_range = f"{start[11:16]}–{end[11:16]}"
    else:
        time_range = "all day"
    return f"  {time_range}: {event['summary']}"


def suggest_next(open_tasks: list[dict], calendar_events: list[dict] = []) -> str:
    """Return one plain-text suggestion for which task to tackle next."""
    system = (
        _read("prompts", "character.md")
        + "\n\n"
        + _read("prompts", "suggest_next.md")
        + "\n\n"
        + _read("profile.md")
    )
    task_lines = "\n".join(
        f"- #{t['id']} {t['title']}"
        + (f" (due {t['due_date']})" if t.get("due_date") else "")
        + (f" — {t['notes']}" if t.get("notes") else "")
        for t in open_tasks
    )
    sections = []
    if calendar_events:
        cal_lines = "\n".join(_fmt_calendar_event(e) for e in calendar_events)
        sections.append(f"Today's schedule:\n{cal_lines}")
    sections.append(f"Open tasks:\n{task_lines}")
    prompt = "\n\n".join(sections)
    try:
        response = _client().models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system,
            ),
        )
        return response.text.strip()
    except Exception:
        logger.exception("suggest_next failed")
        return "Could not generate a suggestion right now."
