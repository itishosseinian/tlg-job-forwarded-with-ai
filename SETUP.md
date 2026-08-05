# Smart Telegram — Setup Guide

An AI-powered Telegram assistant. It watches the Telegram groups/channels you choose,
uses OpenAI to decide whether each new message is relevant to you, and automatically
forwards the relevant ones to you (or any chat you pick) with a link back to the source.

You control everything from a private Telegram bot — no coding or server commands needed
after the one-time setup.

---

## 1. What you need before starting

| Item | Where to get it | Cost |
|---|---|---|
| **Telegram API ID + Hash** | https://my.telegram.org → *API development tools* | Free |
| **A bot token** | Message [@BotFather](https://t.me/BotFather) on Telegram → `/newbot` | Free |
| **OpenAI API key** | https://platform.openai.com/api-keys | Pay-per-use (see §6) |
| **Python 3.11+** | https://python.org | Free |

> The Telegram account whose **phone number** you put in `.env` is the account that will
> *read* the chats. It must already be a member of any group/channel you want to monitor.

---

## 2. Install

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## 3. Configure credentials

Copy the example file and fill in your own values:

```bash
cp .env.example .env
```

Open `.env` and paste in your API ID, API hash, phone number, bot token, and OpenAI key.

## 4. First run (one-time login)

```bash
python main.py
```

The **first** time, Telegram sends a login code to the account's phone — type it in when
prompted (and your 2FA password if you have one). This creates two `.session` files so you
never have to log in again. Keep these files private — they hold the login.

When you see `Ready — open @yourbot on Telegram and tap /start`, it's live.

---

## 5. Using it (all from Telegram)

Open your bot in Telegram and send **`/start`**. You get two buttons:

### 📨 Fetch Messages
Browse your chats and read recent messages — handy for finding the **ID** of a group you
want to monitor.

### ⚙️ Configuration
This is where you set everything up:

- **🟢/🔴 Turn ON/OFF** — the master switch. When OFF, nothing is filtered or forwarded.
- **📋 Monitor Chats** — add a chat to watch. For each chat you pick:
  - the **chat** (`@username` or numeric ID),
  - a **prompt** (the filter rule — see below),
  - a **model** (which AI to use),
  - a **receiver** — where matches are sent (`me` = your Saved Messages, or any `@username`).
  - Each chat can be individually enabled/disabled or deleted.
- **💬 Prompts** — your filter rules. A prompt tells the AI what counts as "relevant."
  Two come pre-loaded (Python / general programming). You can add your own, e.g.
  *"Return 1 if this message is a job posting for a remote designer, else 0."*
  > **Rule for writing prompts:** always end with *"Reply with only 0 or 1, no other text."*
  > The system treats a reply containing `1` as a match.
- **🤖 Models** — which OpenAI model does the classifying. Pre-loaded options:
  - `o4-mini` — fast, cheap, great for filtering *(recommended default)*
  - `gpt-4o-mini` — fast and cheapest
  - `gpt-4o` — most capable, higher cost

### Typical first setup
1. Configuration → **Prompts** → add your filter rule (or use a pre-loaded one).
2. Configuration → **Monitor Chats** → **➕ Add Chat** → pick the chat, prompt, model, receiver.
3. Configuration → **Turn ON**.
4. Done — relevant messages now arrive automatically.

---

## 6. Running costs

The only running cost is the **OpenAI API** — you pay per message classified (typically a
fraction of a cent each with `o4-mini`). Busy groups cost more because every message is
checked. You can cap spend in your OpenAI dashboard. Telegram and the bot are free.

To keep it running 24/7, run `python main.py` on an always-on machine or a cheap VPS
(e.g. inside `tmux`/`screen`, or as a systemd service).

---

## 7. Security notes

- Only **you** can command the bot — it ignores everyone except the account that first ran it.
- Never share `.env` or the `.session` files — they grant full access to the account.
