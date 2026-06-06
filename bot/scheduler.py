import logging
from telegram.ext import Application

import store

logger = logging.getLogger(__name__)


async def daily_overdue_check(context) -> None:
    tasks = store.get_overdue()
    if not tasks:
        return
    lines = [f"#{t['id']} {t['title']} (due {t['due_date']})" for t in tasks]
    msg = "Overdue tasks:\n" + "\n".join(lines)
    chat_id = context.job.data
    await context.bot.send_message(chat_id=chat_id, text=msg)


def register_jobs(app: Application, owner_chat_id: int) -> None:
    app.job_queue.run_daily(
        daily_overdue_check,
        time=__import__("datetime").time(9, 0),
        data=owner_chat_id,
        name="daily_overdue",
    )
