import logging
import os

from telegram import Update
from telegram.ext import ContextTypes

import store
from ai.gemini import chat, parse_task, suggest_next
from integrations import google_services

logger = logging.getLogger(__name__)

_NOT_CONFIGURED = "Google integration not configured — add credentials.json to project root."


def _owner_id() -> int:
    return int(os.environ.get("OWNER_CHAT_ID", "0"))


async def _guard(update: Update) -> bool:
    owner = _owner_id()
    if owner and update.effective_chat.id != owner:
        logger.warning("Rejected message from chat_id=%s", update.effective_chat.id)
        return False
    return True


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    await update.message.reply_text(
        "Life Agent ready.\n"
        "/add <text> — add a task\n"
        "/list — show local open tasks\n"
        "/tasks — show Google Tasks\n"
        "/sync — pull Google Tasks → local\n"
        "/done <id> — mark task done\n"
        "/drop <id> — drop a task\n"
        "/overdue — show overdue tasks\n"
        "/next — suggest what to do next\n"
        "/chat <message> — talk to the agent\n"
        "plain text — chat (use /add for tasks)"
    )


async def cmd_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    text = " ".join(context.args) if context.args else ""
    if not text:
        await update.message.reply_text("Usage: /add <task description>")
        return
    await _add_from_text(update, text)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Non-command text is routed to chat()."""
    if not await _guard(update):
        return
    text = update.message.text.strip()
    if text:
        reply = chat(text, open_tasks=[dict(t) for t in store.list_open()])
        await update.message.reply_text(reply)


async def cmd_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    message = " ".join(context.args) if context.args else ""
    if not message:
        await update.message.reply_text("Usage: /chat <message>")
        return
    reply = chat(message, open_tasks=[dict(t) for t in store.list_open()])
    await update.message.reply_text(reply)


async def _add_from_text(update: Update, text: str) -> None:
    parsed = parse_task(text)
    task_id = store.add_task(
        title=parsed["title"],
        notes=parsed["notes"],
        due_date=parsed["due_date"],
    )
    parts = [f"Added #{task_id}: {parsed['title']}"]
    if parsed["due_date"]:
        parts.append(f"Due: {parsed['due_date']}")
    if parsed["notes"]:
        parts.append(f"Notes: {parsed['notes']}")

    # Mirror to Google Tasks best-effort — never block on failure
    try:
        google_services.add_task_to_google(
            title=parsed["title"],
            due_date=parsed["due_date"],
            notes=parsed["notes"],
        )
    except Exception:
        logger.exception("Google mirror failed for task_id=%s", task_id)

    await update.message.reply_text("\n".join(parts))


async def cmd_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    tasks = store.list_open()
    if not tasks:
        await update.message.reply_text("No open tasks.")
        return
    lines = []
    for t in tasks:
        due = f" (due {t['due_date']})" if t["due_date"] else ""
        lines.append(f"#{t['id']} {t['title']}{due}")
    await update.message.reply_text("\n".join(lines))


async def cmd_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    if not google_services.is_configured():
        await update.message.reply_text(_NOT_CONFIGURED)
        return
    tasks = google_services.get_tasks()
    if not tasks:
        await update.message.reply_text("No incomplete Google Tasks.")
        return
    lines = []
    for t in tasks:
        due = f" (due {t['due'][:10]})" if t.get("due") else ""
        lines.append(f"• {t['title']}{due}")
    await update.message.reply_text("Google Tasks:\n" + "\n".join(lines))


async def cmd_sync(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    if not google_services.is_configured():
        await update.message.reply_text(_NOT_CONFIGURED)
        return
    google_tasks = google_services.get_tasks()
    local_titles = {t["title"].lower().strip() for t in store.list_open()}
    synced = 0
    for gt in google_tasks:
        if gt["title"].lower().strip() not in local_titles:
            due = gt["due"][:10] if gt.get("due") else None
            store.add_task(title=gt["title"], notes=gt.get("notes"), due_date=due)
            synced += 1
    await update.message.reply_text(f"Synced {synced} task(s) from Google Tasks.")


async def cmd_done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Usage: /done <task id>")
        return
    task_id = int(context.args[0])
    task = store.get_task(task_id)
    if store.mark_done(task_id):
        await update.message.reply_text(f"Task #{task_id} marked done.")
        # Best-effort: complete matching Google Task by title
        if task:
            _try_complete_google_by_title(task["title"])
    else:
        await update.message.reply_text(f"Task #{task_id} not found or already closed.")


async def cmd_drop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Usage: /drop <task id>")
        return
    task_id = int(context.args[0])
    if store.drop_task(task_id):
        await update.message.reply_text(f"Task #{task_id} dropped.")
    else:
        await update.message.reply_text(f"Task #{task_id} not found or already closed.")


async def cmd_overdue(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    tasks = store.get_overdue()
    if not tasks:
        await update.message.reply_text("No overdue tasks.")
        return
    lines = [f"#{t['id']} {t['title']} (due {t['due_date']})" for t in tasks]
    await update.message.reply_text("Overdue:\n" + "\n".join(lines))


async def cmd_next(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    tasks = [dict(t) for t in store.list_open()]
    if not tasks:
        await update.message.reply_text("No open tasks.")
        return
    calendar_events = google_services.get_todays_calendar_events()
    suggestion = suggest_next(tasks, calendar_events)
    await update.message.reply_text(suggestion)


def _try_complete_google_by_title(title: str) -> None:
    try:
        google_tasks = google_services.get_tasks()
        needle = title.lower().strip()
        for gt in google_tasks:
            if gt["title"].lower().strip() == needle:
                tl_id = gt.get("_tasklist_id", "")
                composite_id = f"{tl_id}/{gt['id']}" if tl_id else gt["id"]
                google_services.complete_google_task(composite_id)
                return
    except Exception:
        logger.exception("_try_complete_google_by_title failed title=%r", title)
