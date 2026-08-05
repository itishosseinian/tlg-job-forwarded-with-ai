import asyncio
from telethon import events
from telethon.tl.types import MessageMediaWebPage
from openai import AsyncOpenAI
from clients import user_client
from config import OPENAI_API_KEY, MODEL
import db

openai = AsyncOpenAI(api_key=OPENAI_API_KEY)

# Max concurrent OpenAI calls — prevents rate limit errors under message bursts
_sem = asyncio.Semaphore(5)


def _matches(key: str, chat_id: int, username: str | None) -> bool:
    """Check if a chats.json key matches the incoming chat."""
    key = key.strip()
    try:
        key_id  = int(key)
        abs_cid = abs(chat_id)
        # Direct match
        if key_id == chat_id or key_id == abs_cid:
            return True
        # Supergroups: event.chat_id = -1005112039579, entity.id = 5112039579
        # Telegram adds -100 prefix: abs(chat_id) - 1_000_000_000_000 = entity.id
        if abs_cid > 1_000_000_000_000 and key_id == abs_cid - 1_000_000_000_000:
            return True
    except ValueError:
        pass
    # @username or plain username
    if username:
        return key.lstrip("@").lower() == username.lower()
    return False


async def _classify(text: str, prompt: str, model: str) -> bool:
    """Ask OpenAI to classify the message. Returns True if relevant.

    The user's prompt can be plain natural language ("job ads for Python
    developers") — we wrap it in a strict 0/1 instruction here so they don't
    have to remember the formatting rule themselves.
    """
    # Combine instruction + prompt + message into a single user turn — works for
    # all models including o-series (o4-mini, o3) which don't use the system role
    content = (
        "You are a strict message classifier. Using the rule below, decide whether "
        "the message is relevant. Reply with ONLY a single digit: 1 if it is "
        "relevant, 0 if it is not. Output nothing else.\n\n"
        f"Rule:\n{prompt}\n\n"
        f"Message:\n{text[:2000]}"
    )
    resp = await openai.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": content}],
    )
    answer = (resp.choices[0].message.content or "").strip()
    return answer[:1] == "1"


def register() -> None:

    @user_client.on(events.NewMessage())
    async def on_new_message(event) -> None:
        try:
            await _handle(event)
        except Exception as exc:
            print(f"[Forwarder error] {exc}")

    async def _handle(event) -> None:
        # ── global toggle ────────────────────────────────────────────────────
        if not db.read("system").get("enabled", False):
            return

        # ── match against monitored chats ────────────────────────────────────
        chat     = await event.get_chat()
        chat_id  = event.chat_id
        username = getattr(chat, "username", None)

        chats       = db.read("chats")
        matched_cfg = None

        for key, cfg in chats.items():
            if not cfg.get("enabled", True):
                continue
            if _matches(key, chat_id, username):
                matched_cfg = cfg
                break

        if not matched_cfg:
            return

        # ── get message text ─────────────────────────────────────────────────
        text = event.message.text or ""
        if not text.strip():
            return

        # ── load prompt ───────────────────────────────────────────────────────
        prompts = db.read("prompts")
        prompt_text = prompts.get(matched_cfg["prompt_id"], {}).get("text", "")

        if not prompt_text:
            return

        # ── classify ─────────────────────────────────────────────────────────
        try:
            async with _sem:
                relevant = await _classify(text, prompt_text, MODEL)
        except Exception as exc:
            print(f"[OpenAI error] {exc}")
            return

        chat_name = getattr(chat, "title", None) or username or str(chat_id)
        print(f"[{chat_name}] {'✅ forward' if relevant else '❌ skip'} — {text[:60].replace(chr(10), ' ')}")

        if not relevant:
            return

        # ── build source info ─────────────────────────────────────────────────
        sender      = await event.get_sender()
        sender_name = getattr(sender, "first_name", None) or getattr(sender, "title", None) or "?"
        sender_user = f"@{sender.username}" if getattr(sender, "username", None) else f"id:{getattr(sender, 'id', '?')}"

        chat_uname = f"@{username}" if username else f"id:{chat_id}"

        # Build a direct message link if possible
        msg_id = event.message.id
        if username:
            msg_link = f"https://t.me/{username}/{msg_id}"
        else:
            # Private supergroup link format
            bare_id = abs(chat_id) - 1_000_000_000_000 if abs(chat_id) > 1_000_000_000_000 else abs(chat_id)
            msg_link = f"https://t.me/c/{bare_id}/{msg_id}"

        source_info = (
            f"📌 From: {chat_name} ({chat_uname})\n"
            f"👤 Sender: {sender_name} ({sender_user})\n"
            f"🔗 {msg_link}"
        )

        # ── deliver as ONE message: source header + the message text ──────────
        receiver = matched_cfg.get("receiver", "me")

        # A link preview isn't real media — don't try to re-send it as a file.
        media = event.message.media
        if isinstance(media, MessageMediaWebPage):
            media = None

        # Telegram caps captions at 1024 chars and plain messages at 4096.
        # Trim the message body, never the header, so the source is never lost.
        room = max(0, (1024 if media else 4096) - len(source_info) - 2)
        body = text if len(text) <= room else text[:max(0, room - 1)] + "…"
        combined = f"{source_info}\n\n{body}"

        try:
            if media:
                await user_client.send_file(receiver, media, caption=combined)
            else:
                await user_client.send_message(receiver, combined, link_preview=False)
        except Exception as exc:
            # Media re-send can fail on content-protected chats — text still gets through
            if media:
                try:
                    await user_client.send_message(receiver, combined, link_preview=False)
                    return
                except Exception as exc2:
                    exc = exc2
            print(f"[Send error] receiver={receiver} — {exc}")
