import logging
import os

from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler, MessageHandler, filters

import store
from bot.handlers import (
    cmd_add, cmd_chat, cmd_done, cmd_drop, cmd_list, cmd_next,
    cmd_overdue, cmd_start, cmd_sync, cmd_tasks, handle_message,
)
from bot.scheduler import register_jobs

load_dotenv()

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    level=logging.INFO,
)


def main() -> None:
    store.init_db()

    token = os.environ["TELEGRAM_BOT_TOKEN"]
    owner_chat_id = int(os.environ.get("OWNER_CHAT_ID", "0"))

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("add", cmd_add))
    app.add_handler(CommandHandler("list", cmd_list))
    app.add_handler(CommandHandler("done", cmd_done))
    app.add_handler(CommandHandler("drop", cmd_drop))
    app.add_handler(CommandHandler("overdue", cmd_overdue))
    app.add_handler(CommandHandler("next", cmd_next))
    app.add_handler(CommandHandler("chat", cmd_chat))
    app.add_handler(CommandHandler("tasks", cmd_tasks))
    app.add_handler(CommandHandler("sync", cmd_sync))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    if owner_chat_id:
        register_jobs(app, owner_chat_id)

    app.run_polling()


if __name__ == "__main__":
    main()
