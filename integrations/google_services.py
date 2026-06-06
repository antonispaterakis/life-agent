import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

_ROOT = Path(__file__).parent.parent
_CREDS_FILE = _ROOT / "credentials.json"
_TOKEN_FILE = _ROOT / "token.json"
_ATHENS = ZoneInfo("Europe/Athens")

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/tasks",
]


def is_configured() -> bool:
    return _CREDS_FILE.exists()


def get_credentials():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    creds = None
    if _TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(_TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(_CREDS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        _TOKEN_FILE.write_text(creds.to_json())

    return creds


def get_todays_calendar_events() -> list[dict]:
    if not is_configured():
        return []
    try:
        from googleapiclient.discovery import build

        creds = get_credentials()
        service = build("calendar", "v3", credentials=creds)

        now_athens = datetime.now(_ATHENS)
        day_start = now_athens.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = now_athens.replace(hour=23, minute=59, second=59, microsecond=0)

        result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=day_start.isoformat(),
                timeMax=day_end.isoformat(),
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        events = []
        for e in result.get("items", []):
            start = e["start"].get("dateTime") or e["start"].get("date", "")
            end = e["end"].get("dateTime") or e["end"].get("date", "")
            events.append({
                "summary": e.get("summary", "(no title)"),
                "start": start,
                "end": end,
            })
        return events
    except Exception:
        logger.exception("get_todays_calendar_events failed")
        return []


def get_tasks() -> list[dict]:
    if not is_configured():
        return []
    try:
        from googleapiclient.discovery import build

        creds = get_credentials()
        service = build("tasks", "v1", credentials=creds)

        task_lists = service.tasklists().list().execute().get("items", [])
        tasks = []
        for tl in task_lists:
            items = (
                service.tasks()
                .list(
                    tasklist=tl["id"],
                    showCompleted=False,
                    showHidden=False,
                )
                .execute()
                .get("items", [])
            )
            for t in items:
                tasks.append({
                    "id": t["id"],
                    "title": t.get("title", ""),
                    "due": t.get("due"),
                    "notes": t.get("notes"),
                    "_tasklist_id": tl["id"],
                })
        return tasks
    except Exception:
        logger.exception("get_tasks failed")
        return []


def add_task_to_google(title: str, due_date: str | None, notes: str | None) -> bool:
    if not is_configured():
        return False
    try:
        from googleapiclient.discovery import build

        creds = get_credentials()
        service = build("tasks", "v1", credentials=creds)

        task_lists = service.tasklists().list().execute().get("items", [])
        if not task_lists:
            return False
        tl_id = task_lists[0]["id"]

        body: dict = {"title": title}
        if due_date:
            # Google Tasks API requires RFC 3339 with time component
            body["due"] = f"{due_date}T00:00:00.000Z"
        if notes:
            body["notes"] = notes

        service.tasks().insert(tasklist=tl_id, body=body).execute()
        return True
    except Exception:
        logger.exception("add_task_to_google failed title=%r", title)
        return False


def complete_google_task(task_id: str) -> bool:
    if not is_configured():
        return False
    try:
        from googleapiclient.discovery import build

        creds = get_credentials()
        service = build("tasks", "v1", credentials=creds)

        # task_id is stored as "<tasklist_id>/<task_id>" so we can route correctly;
        # fall back to searching all lists if plain id given
        if "/" in task_id:
            tl_id, t_id = task_id.split("/", 1)
        else:
            tl_id, t_id = _find_task_list(service, task_id)
            if tl_id is None:
                return False

        service.tasks().patch(
            tasklist=tl_id,
            task=t_id,
            body={"status": "completed"},
        ).execute()
        return True
    except Exception:
        logger.exception("complete_google_task failed task_id=%r", task_id)
        return False


def _find_task_list(service, task_id: str) -> tuple[str | None, str]:
    """Return (tasklist_id, task_id) by searching all lists for the task."""
    try:
        task_lists = service.tasklists().list().execute().get("items", [])
        for tl in task_lists:
            items = service.tasks().list(tasklist=tl["id"]).execute().get("items", [])
            for t in items:
                if t["id"] == task_id:
                    return tl["id"], task_id
    except Exception:
        logger.exception("_find_task_list failed")
    return None, task_id
