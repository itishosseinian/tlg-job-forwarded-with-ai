# Smart Telegram

An AI-powered filter for Telegram. It watches the groups and channels you choose, asks
OpenAI whether each new message matches a rule you wrote in plain language, and forwards
only the matches to you — with a link back to the source.

Useful for busy job boards, deal channels, or any group where 2% of the messages matter
and you don't want to read the other 98%.

## How it works

1. A **userbot** signs in as your own Telegram account and listens to the chats you pick.
   (Your account must already be a member of them.)
2. Every new message is sent to OpenAI with your filter rule, which answers `1` or `0`.
3. Messages that score `1` are forwarded to your Saved Messages — or any chat you choose —
   followed by a card showing the source chat, the sender, and a link to the original.
4. You configure all of it from a **private control bot** on Telegram. No server commands
   after the one-time setup.

## Features

- **Plain-language rules** — write *"job ads for remote Python developers"* and the AI
  handles the rest. No prompt formatting to memorize.
- **Per-chat rules** — every monitored chat gets its own filter and its own destination.
- **Any destination** — Saved Messages, another group, a channel you own, or a DM.
- **Master switch** plus per-chat enable/disable, all from the bot.
- **Groups, supergroups, and channels** are all supported.
- **Rate-limit safe** — concurrent OpenAI calls are capped so message bursts don't fail.

## Requirements

| Item | Where | Cost |
|---|---|---|
| Telegram API ID + hash | [my.telegram.org](https://my.telegram.org) → API development tools | Free |
| Bot token | [@BotFather](https://t.me/BotFather) → `/newbot` | Free |
| OpenAI API key | [platform.openai.com](https://platform.openai.com/api-keys) | Pay per use |
| Python 3.11+ | [python.org](https://python.org) | Free |

## Quick start

```bash
git clone https://github.com/itishosseinian/tlg-job-forwarded-with-ai.git
cd tlg-job-forwarded-with-ai
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # then fill in your keys
python main.py
```

The first run asks for the login code Telegram sends to your phone (and your 2FA password
if you have one). That creates two `.session` files so you never log in again.

When you see `Ready — open @yourbot on Telegram and tap /start`, open your bot and send
`/start`.

Full walkthrough: **[SETUP.md](SETUP.md)** · Persian guide: **[راهنمای فارسی](راهنمای-فارسی.pdf)**

> **Note:** the control bot's interface is in **Persian**. The code, `.env`, and this
> documentation are in English.

## Configuration

All settings live in `.env`:

| Variable | Meaning |
|---|---|
| `TELEGRAM_API_ID` / `TELEGRAM_API_HASH` | From my.telegram.org |
| `TELEGRAM_PHONE` | The account that **reads** the chats |
| `BOT_TOKEN` | The control bot from BotFather |
| `OPENAI_API_KEY` | Your OpenAI key |
| `OPENAI_MODEL` | Optional — defaults to `o4-mini` |

Runtime state (monitored chats, rules, on/off) is stored in `data/*.json`, created
automatically on first run. A fresh install starts with the master switch **off**.

## Notes & limitations

- **Text and captions only.** A photo or video with no caption is skipped — it never
  reaches the AI.
- **Your own messages are classified too.** The listener handles both incoming and
  outgoing messages. Barely noticeable in a busy group; noticeable in a 1:1 chat, where
  half the traffic is yours.
- **Every message in a monitored chat is sent to OpenAI**, not just the ones that match.
  Worth considering before pointing it at a private conversation.
- **Source links work for groups and channels.** Private 1:1 chats have no shareable
  message link in Telegram, so that line won't resolve for a DM.
- **Channel posts usually have no sender**, so the sender line shows `?` unless the
  channel has signatures enabled.
- **Content-protected chats** can't be forwarded; the message text is sent instead.

## Cost

The only running cost is the OpenAI API — a fraction of a cent per message classified with
`o4-mini`. Busy groups cost more, since every message is checked. Cap your spend in the
OpenAI dashboard.

To run it 24/7, use `tmux`/`screen` or a systemd service on an always-on machine.

## Security

- The bot only obeys the account that started it; everyone else is ignored.
- **Never share `.env` or the `.session` files.** The session files *are* the login —
  anyone holding one is signed into your Telegram account. Both are gitignored; keep them
  that way, and never distribute a zip of the project folder.

## License

[MIT](LICENSE) © Amir Hossein Hosseinian
