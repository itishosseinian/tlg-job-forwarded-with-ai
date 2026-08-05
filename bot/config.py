from telethon import events, Button

from clients import bot_client, user_client
from config import MODEL
import db


# How long a multi-step flow waits on each reply before giving up. Generous, so
# stepping away mid-setup doesn't discard what you've already entered.
FLOW_TIMEOUT = 900


# ─── helpers ─────────────────────────────────────────────────────────────────

def _keep(response_text: str, current: str) -> str:
    """Return current value if user typed /skip or sent empty."""
    t = response_text.strip()
    return current if (not t or t.lower() == "/skip") else t


async def _show(event, text: str, buttons) -> None:
    try:
        await event.edit(text, buttons=buttons, parse_mode="md")
    except Exception:
        await event.respond(text, buttons=buttons, parse_mode="md")


# ─── user's dialogs (channels & groups), cached ──────────────────────────────

DIALOGS_PER_PAGE = 8
_dialogs_cache: list[dict] = []


async def load_dialogs(force: bool = False) -> list[dict]:
    """Fetch the account's groups & channels (id, title, username). Cached."""
    global _dialogs_cache
    if _dialogs_cache and not force:
        return _dialogs_cache
    out = []
    async for d in user_client.iter_dialogs():
        if d.is_group or d.is_channel:
            e = d.entity
            out.append({
                "id": e.id,
                "title": (d.name or "?")[:40],
                "username": getattr(e, "username", None),
            })
    _dialogs_cache = out
    return out


def _dialog_key(d: dict) -> str:
    """The value we store to monitor a chat — @username if it has one, else id."""
    return f"@{d['username']}" if d.get("username") else str(d["id"])


def _page_count(n: int) -> int:
    return max(1, (n + DIALOGS_PER_PAGE - 1) // DIALOGS_PER_PAGE)


# ─── screens ─────────────────────────────────────────────────────────────────

async def _send_view(chat_id, view) -> None:
    """Send a screen as a NEW message (used after a conversation flow ends)."""
    text, buttons = view
    await bot_client.send_message(chat_id, text, buttons=buttons, parse_mode="md")


async def _run_flow(coro, chat_id) -> None:
    """Run a conversation flow, surviving timeouts/errors without crashing."""
    try:
        await coro
    except TimeoutError:
        await bot_client.send_message(chat_id, "⏱️ زمان تمام شد، دوباره تلاش کن.")
    except Exception as exc:  # noqa: BLE001
        print(f"[flow error] {exc}")
        await bot_client.send_message(chat_id, "⚠️ خطایی رخ داد، دوباره تلاش کن.")


def _main_view():
    enabled = db.read("system").get("enabled", False)
    status  = "🟢 فعال" if enabled else "🔴 غیرفعال"
    toggle  = "⏸️ توقف ربات" if enabled else "▶️ فعال‌سازی ربات"
    text = f"⚙️ **پنل مدیریت**\nوضعیت ربات: {status}\nمدل هوش مصنوعی: `{MODEL}`"
    buttons = [
        [Button.inline(toggle,                b"cfg:system:toggle")],
        [Button.inline("📡 چت‌های تحت نظر",   b"cfg:chats")],
        [Button.inline("📋 چت‌های من",        b"mychats:nav:0")],
        [Button.inline("💬 پرامپت‌ها",         b"cfg:prompts")],
    ]
    return text, buttons


async def show_main(event) -> None:
    await _show(event, *_main_view())


async def show_my_chats(event, page: int = 0) -> None:
    if not _dialogs_cache:
        try:
            await event.edit("⏳ در حال دریافت چت‌ها از تلگرام...")
        except Exception:
            pass
    dialogs = await load_dialogs()
    total   = len(dialogs)
    if not total:
        await _show(event, "📋 **چت‌های من**\n\nهیچ گروه یا کانالی پیدا نشد.",
                    [[Button.inline("↩️ بازگشت", b"cfg:main")]])
        return

    pages = _page_count(total)
    page  = max(0, min(page, pages - 1))
    chunk = dialogs[page * DIALOGS_PER_PAGE:(page + 1) * DIALOGS_PER_PAGE]

    lines = [f"📋 **چت‌های من**  (صفحه {page + 1}/{pages} — {total} چت)",
             "روی آیدی بزن تا کپی شود 👇\n"]
    for d in chunk:
        uname = f"@{d['username']}" if d["username"] else "—"
        lines.append(f"• **{d['title']}**\n  {uname}  |  `{d['id']}`")

    nav = []
    if page > 0:
        nav.append(Button.inline("◀️ قبلی", f"mychats:nav:{page - 1}".encode()))
    if page < pages - 1:
        nav.append(Button.inline("بعدی ▶️", f"mychats:nav:{page + 1}".encode()))

    buttons = []
    if nav:
        buttons.append(nav)
    buttons.append([Button.inline("🔄 بروزرسانی", b"mychats:refresh")])
    buttons.append([Button.inline("↩️ بازگشت", b"cfg:main")])
    await _show(event, "\n".join(lines), buttons)


def _chats_view():
    chats   = db.read("chats")
    prompts = db.read("prompts")

    lines = ["📡 **چت‌های تحت نظر**\n"]
    buttons = []

    for i, (key, cfg) in enumerate(chats.items()):
        p       = prompts.get(cfg["prompt_id"], {}).get("name", "?")
        enabled = cfg.get("enabled", True)
        status  = "🟢" if enabled else "🔴"
        lines.append(f"{status} `{key}`\n  پرامپت: {p} | ← {cfg['receiver']}")
        toggle_label = "⏸️ خاموش کن" if enabled else "▶️ روشن کن"
        buttons.append([
            Button.inline(f"✏️ {key[:18]}", f"cfg:chats:edit:{i}".encode()),
            Button.inline(toggle_label,      f"cfg:chats:toggle:{i}".encode()),
            Button.inline("🗑️",             f"cfg:chats:del:{i}".encode()),
        ])

    buttons += [
        [Button.inline("➕ افزودن چت", b"cfg:chats:add")],
        [Button.inline("↩️ بازگشت",    b"cfg:main")],
    ]
    text = "\n\n".join(lines) if chats else "📡 **چت‌های تحت نظر**\n_هنوز چتی اضافه نشده._"
    return text, buttons


async def show_chats(event) -> None:
    await _show(event, *_chats_view())


def _prompts_view():
    chats   = db.read("chats")
    prompts = db.read("prompts")

    if not chats:
        text = ("💬 **پرامپت‌ها**\n\n"
                "_هر چت پرامپت مخصوص خودش را دارد._\n"
                "_هنوز چتی اضافه نشده — اول از «📡 چت‌های تحت نظر» یک چت اضافه کن._")
        return text, [[Button.inline("↩️ بازگشت", b"cfg:main")]]

    lines = ["💬 **پرامپت‌ها**\n_هر چت پرامپت (قانون فیلتر) مخصوص خودش را دارد. برای تغییر، روی ویرایش بزن._\n"]
    buttons = []
    for key, cfg in chats.items():
        pid   = cfg.get("prompt_id")
        ptext = prompts.get(pid, {}).get("text", "—")
        lines.append(f"📡 `{key}`\n_{ptext[:90]}…_")
        buttons.append([Button.inline(f"✏️ ویرایش پرامپت «{key[:16]}»", f"cfg:prompts:edit:{pid}".encode())])

    buttons.append([Button.inline("↩️ بازگشت", b"cfg:main")])
    return "\n\n".join(lines), buttons


async def show_prompts(event) -> None:
    await _show(event, *_prompts_view())


# ─── chat picker (used inside the add-chat flow) ─────────────────────────────

def _picker_buttons(dialogs: list[dict], page: int):
    pages = _page_count(len(dialogs))
    page  = max(0, min(page, pages - 1))
    start = page * DIALOGS_PER_PAGE
    rows  = []
    for idx in range(start, min(start + DIALOGS_PER_PAGE, len(dialogs))):
        d     = dialogs[idx]
        uname = f"@{d['username']}" if d["username"] else f"id:{d['id']}"
        label = f"{d['title']} ({uname})"[:55]
        rows.append([Button.inline(label, f"pick:sel:{idx}".encode())])

    nav = []
    if page > 0:
        nav.append(Button.inline("◀️", f"pick:nav:{page - 1}".encode()))
    nav.append(Button.inline(f"{page + 1}/{pages}", b"pick:noop"))
    if page < pages - 1:
        nav.append(Button.inline("▶️", f"pick:nav:{page + 1}".encode()))
    rows.append(nav)
    rows.append([Button.inline("✖️ انصراف", b"pick:cancel")])
    return rows


async def _pick_from_list(conv, edit_target):
    """Show the cached dialog picker and let the user tap one. `edit_target` is
    the callback event whose message we keep editing. Returns the chosen key
    (@username or id) or None if cancelled / nothing found."""
    dialogs = await load_dialogs()
    if not dialogs:
        await edit_target.edit("چتی پیدا نشد. یوزرنیم (`@name`) یا آیدی عددی را بفرست:")
        r = await conv.get_response()
        return r.text.strip() or None

    page = 0
    await edit_target.edit("یکی از چت‌هایت را انتخاب کن:", buttons=_picker_buttons(dialogs, page))
    while True:
        sel  = await conv.wait_event(events.CallbackQuery(pattern=rb"^pick:(sel|nav|cancel|noop)"))
        data = sel.data.decode()
        await sel.answer()
        if data == "pick:noop":
            continue
        if data == "pick:cancel":
            await sel.edit("✖️ لغو شد.")
            return None
        if data.startswith("pick:nav:"):
            page = int(data.split(":")[-1])
            await sel.edit(buttons=_picker_buttons(dialogs, page))
            continue
        if data.startswith("pick:sel:"):
            d   = dialogs[int(data.split(":")[-1])]
            key = _dialog_key(d)
            await sel.edit(f"✅ **{d['title']}**  (`{key}`)")
            return key


async def _choose_chat_key(conv, edit_key: str | None):
    """Step 1 of add-chat: the user either PICKS from their chats or TYPES a
    username/id. Button-driven (no racing) so the conversation never corrupts.
    Returns the chosen key string, or None if cancelled."""
    intro = (
        "کدام کانال یا گروه تحت نظر گرفته شود؟\n\n"
        "از لیست چت‌هایت انتخاب کن، یا یوزرنیم/آیدی را خودت تایپ کن 👇"
    )
    if edit_key:
        intro += f"\n\n_فعلی: `{edit_key}`_"
    buttons = [
        [Button.inline("📋 انتخاب از چت‌هایم", b"pick:open")],
        [Button.inline("⌨️ تایپ یوزرنیم یا آیدی", b"pick:type")],
    ]
    if edit_key:
        buttons.append([Button.inline("✓ نگه‌داشتن فعلی", b"pick:keep")])
    await conv.send_message(intro, buttons=buttons)

    cb   = await conv.wait_event(events.CallbackQuery(pattern=rb"^pick:(open|type|keep)$"))
    data = cb.data.decode()
    await cb.answer()

    if data == "pick:keep":
        await cb.edit(f"✓ نگه‌داشته شد: `{edit_key}`")
        return edit_key

    if data == "pick:type":
        await cb.edit("یوزرنیم (`@name`) یا آیدی عددی را بفرست:")
        r = await conv.get_response()
        return r.text.strip() or None

    # pick:open → show the chat picker
    await cb.edit("⏳ در حال دریافت چت‌ها...")
    return await _pick_from_list(conv, cb)


async def _choose_receiver(conv, current: str | None):
    """Pick where matched messages get forwarded. Button-driven:
    Saved Messages, pick from your chats, or type an id/username.
    Returns the receiver string (never None — falls back to current or 'me')."""
    intro = "📤 پیام‌های مرتبط کجا فرستاده شوند؟"
    if current:
        intro += f"\n\n_فعلی: `{current}`_"
    buttons = [
        [Button.inline("📥 پیام‌های ذخیره‌شده‌ی من", b"recv:me")],
        [Button.inline("📋 انتخاب از چت‌هایم",        b"recv:pick")],
        [Button.inline("⌨️ آیدی یا یوزرنیم",          b"recv:type")],
    ]
    if current:
        buttons.append([Button.inline("✓ نگه‌داشتن فعلی", b"recv:keep")])
    await conv.send_message(intro, buttons=buttons)

    cb   = await conv.wait_event(events.CallbackQuery(pattern=rb"^recv:(me|pick|type|keep)$"))
    data = cb.data.decode()
    await cb.answer()

    if data == "recv:keep":
        await cb.edit(f"✓ مقصد: `{current}`")
        return current
    if data == "recv:me":
        await cb.edit("✓ مقصد: پیام‌های ذخیره‌شده‌ی خودت (Saved Messages)")
        return "me"
    if data == "recv:type":
        await cb.edit("آیدی عددی یا یوزرنیم (`@name`) مقصد را بفرست:")
        r = await conv.get_response()
        return r.text.strip() or current or "me"

    # recv:pick → show the chat picker
    await cb.edit("⏳ در حال دریافت چت‌ها...")
    key = await _pick_from_list(conv, cb)
    return key or current or "me"


# ─── conversation flows ──────────────────────────────────────────────────────

async def flow_add_chat(chat_id: int, edit_key: str = None) -> None:
    existing = db.read("chats").get(edit_key, {}) if edit_key else {}
    title    = "✏️ ویرایش چت" if edit_key else "➕ افزودن چت"

    async with bot_client.conversation(chat_id, timeout=FLOW_TIMEOUT, exclusive=False) as conv:
        await conv.send_message(f"**{title}**")

        # Step 1: choose the chat (type or pick from list)
        new_key = await _choose_chat_key(conv, edit_key)
        if not new_key:
            return

        # Step 2: take the filter rule (prompt) directly — no separate "pick a
        # prompt" step. Each chat gets its own rule, editable later in پرامپت‌ها.
        prompts        = db.read("prompts")
        curr_prompt_id = existing.get("prompt_id")
        curr_text      = prompts.get(curr_prompt_id, {}).get("text", "") if curr_prompt_id else ""
        msg = (
            "🧠 چه پیام‌هایی برایت مهم است؟\n"
            "قانون فیلتر را با زبان خودت بنویس — هوش مصنوعی بر اساس آن تصمیم می‌گیرد "
            "کدام پیام برایت فرستاده شود.\n\n"
            "_مثال: «آگهی‌های استخدام برنامه‌نویس پایتون.»_"
        )
        if curr_text:
            msg += f"\n\n_فعلی: {curr_text[:80]}… — برای نگه‌داشتن /skip بفرست_"
        await conv.send_message(msg)
        r           = await conv.get_response()
        prompt_text = _keep(r.text, curr_text)
        if not prompt_text.strip():
            await conv.send_message("❌ قانون فیلتر خالی بود؛ دوباره از منو تلاش کن.")
            return

        # Step 3: receiver — button-driven (Saved / pick a chat / type an id)
        receiver = await _choose_receiver(conv, existing.get("receiver"))

        # Persist the prompt: update the chat's own rule in place, or create one
        prompts = db.read("prompts")
        if curr_prompt_id and curr_prompt_id in prompts:
            prompts[curr_prompt_id]["text"] = prompt_text
            prompt_id = curr_prompt_id
        else:
            prompt_id = db.next_id(prompts)
            prompts[prompt_id] = {"name": f"فیلتر {new_key}"[:40], "text": prompt_text}
        db.write("prompts", prompts)

        # Save the chat
        chats = db.read("chats")
        if edit_key and edit_key != new_key and edit_key in chats:
            del chats[edit_key]
        chats[new_key] = {
            "prompt_id": prompt_id,
            "receiver":  receiver,
            "enabled":   existing.get("enabled", True),
        }
        db.write("chats", chats)
        await conv.send_message(f"✅ چت `{new_key}` ذخیره شد!\n📤 مقصد: `{receiver}`")


async def flow_edit_prompt(chat_id: int, prompt_id: str) -> None:
    """Edit a chat's filter rule. Prompts are owned per-chat, so this only
    edits the rule text (no name, no creation)."""
    prompts = db.read("prompts")
    if prompt_id not in prompts:
        await bot_client.send_message(chat_id, "❌ این پرامپت پیدا نشد.")
        return

    async with bot_client.conversation(chat_id, timeout=FLOW_TIMEOUT, exclusive=False) as conv:
        curr_text = prompts[prompt_id].get("text", "")
        await conv.send_message(
            "✏️ **ویرایش پرامپت**\n\n"
            "قانون فیلتر جدید را با زبان خودت بنویس — هوش مصنوعی بر اساس آن تصمیم می‌گیرد "
            "کدام پیام برایت فرستاده شود.\n\n"
            "_مثال: «آگهی‌های استخدام برنامه‌نویس پایتون.»_"
            + (f"\n\n_فعلی: {curr_text[:100]}… — برای نگه‌داشتن /skip بفرست_" if curr_text else "")
        )
        r        = await conv.get_response()
        new_text = _keep(r.text, curr_text)

        prompts = db.read("prompts")
        if prompt_id in prompts:
            prompts[prompt_id]["text"] = new_text
            db.write("prompts", prompts)
        await conv.send_message("✅ پرامپت بروزرسانی شد!")


# ─── registration ─────────────────────────────────────────────────────────────

def register(admin_id: int) -> None:

    @bot_client.on(events.NewMessage(pattern=r"^/(start|config|menu)$"))
    async def config_cmd(event):
        if event.sender_id != admin_id:
            return
        await show_main(event)

    @bot_client.on(events.CallbackQuery(pattern=rb"^mychats:"))
    async def mychats_cb(event):
        if event.sender_id != admin_id:
            return
        await event.answer()
        parts  = event.data.decode().split(":")
        action = parts[1]
        if action == "refresh":
            await load_dialogs(force=True)
            await show_my_chats(event, page=0)
        else:  # nav
            await show_my_chats(event, page=int(parts[2]))

    @bot_client.on(events.CallbackQuery(pattern=rb"^cfg:"))
    async def config_cb(event):
        if event.sender_id != admin_id:
            return
        await event.answer()

        parts   = event.data.decode().split(":")
        section = parts[1]
        action  = parts[2] if len(parts) > 2 else None
        arg     = parts[3] if len(parts) > 3 else None

        if section == "main":
            await show_main(event)
            return
        if section == "noop":
            return
        if section == "system" and action == "toggle":
            sys = db.read("system")
            sys["enabled"] = not sys.get("enabled", False)
            db.write("system", sys)
            await show_main(event)
            return

        # ── chats ─────────────────────────────────────────────────────────
        if section == "chats":
            if not action:
                await show_chats(event)

            elif action == "add":
                await _run_flow(flow_add_chat(event.chat_id), event.chat_id)
                await _send_view(event.chat_id, _chats_view())

            elif action == "edit" and arg is not None:
                keys = list(db.read("chats").keys())
                key  = keys[int(arg)] if int(arg) < len(keys) else None
                if key:
                    await _run_flow(flow_add_chat(event.chat_id, edit_key=key), event.chat_id)
                await _send_view(event.chat_id, _chats_view())

            elif action == "toggle" and arg is not None:
                chats = db.read("chats")
                keys  = list(chats.keys())
                key   = keys[int(arg)] if int(arg) < len(keys) else None
                if key:
                    chats[key]["enabled"] = not chats[key].get("enabled", True)
                    db.write("chats", chats)
                await show_chats(event)

            elif action == "del" and arg is not None:
                chats = db.read("chats")
                keys  = list(chats.keys())
                key   = keys[int(arg)] if int(arg) < len(keys) else None
                if key:
                    pid = chats[key].get("prompt_id")
                    del chats[key]
                    db.write("chats", chats)
                    # the prompt is owned by this chat — remove it too
                    if pid:
                        prompts = db.read("prompts")
                        if pid in prompts:
                            del prompts[pid]
                            db.write("prompts", prompts)
                await show_chats(event)

        # ── prompts (per-chat; edit only) ──────────────────────────────────
        elif section == "prompts":
            if not action:
                await show_prompts(event)
            elif action == "edit" and arg:
                await _run_flow(flow_edit_prompt(event.chat_id, arg), event.chat_id)
                await _send_view(event.chat_id, _prompts_view())
