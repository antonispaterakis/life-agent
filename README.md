# Life Agent

A personal Telegram bot that acts as a single-owner assistant: it tracks tasks, chats with you via Gemini, syncs with Google Calendar/Tasks, and proactively nudges you on a schedule.

> **Status:** active personal project.

## What it does

| Command | Description |
|---|---|
| `/add <text>` | Add a task (parsed into structured form by Gemini) |
| `/list` | Show local open tasks |
| `/done <id>` / `/drop <id>` | Mark a task done / drop it |
| `/overdue` | Show overdue tasks |
| `/next` | Ask the agent to suggest what to work on next |
| `/chat <message>` | Talk to the agent directly |
| `/tasks` | Show Google Tasks |
| `/sync` | Pull Google Tasks into the local store |
| plain text | Routed straight to chat |

It also runs scheduled jobs (via APScheduler) that proactively message the owner — e.g. check-ins or overdue nudges — and is locked to a single `OWNER_CHAT_ID`, so it only ever responds to its owner.

## Stack

- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) for the bot/command layer
- [google-genai](https://github.com/googleapis/python-genai) (Gemini) for chat, task parsing, and "what's next" suggestions
- `APScheduler` for proactive scheduled jobs
- Google Calendar / Tasks API (`google-api-python-client`) for sync
- SQLite (via a thin `store.py` wrapper) for local task storage

## Project structure

```
life-agent/
├── main.py                     # entrypoint — registers handlers & scheduled jobs
├── store.py                    # SQLite task storage
├── bot/
│   ├── handlers.py             # command handlers (/add, /list, /chat, ...)
│   └── scheduler.py            # proactive scheduled jobs
├── ai/
│   └── gemini.py               # chat / parse_task / suggest_next via Gemini
├── integrations/
│   └── google_services.py      # Google Calendar & Tasks integration
└── prompts/                    # system prompts (character, task parsing, suggestions)
```

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# fill in TELEGRAM_BOT_TOKEN, GEMINI_API_KEY, OWNER_CHAT_ID
```

For Google Calendar/Tasks sync, place an OAuth `credentials.json` (from Google Cloud Console) in the project root.

```bash
python main.py
```

## Notes

This is a single-owner bot by design — `_guard()` in `bot/handlers.py` rejects any chat that isn't `OWNER_CHAT_ID`.
