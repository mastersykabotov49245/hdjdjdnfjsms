import json
import logging
import os
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import Application, TypeHandler, ContextTypes
from telegram.error import TelegramError

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
log = logging.getLogger("mute_bot")

BOT_TOKEN = "8677123574:AAFzqoXF10O8dTkFFgefnWPaan8ZRkY1yRw"

DATA_FILE = Path(__file__).with_name("mute_bot_data.json")

DEFAULT_MUTE_TEXT = "Замолчи"
DEFAULT_UNMUTE_TEXT = "Можешь писать"

MODE_FULL = "full"
MODE_TEXT = "text"
MODE_MEDIA = "media"
MODE_OFF = "off"

MEDIA_TYPES = ("photo", "video", "video_note", "voice", "audio", "document", "sticker", "animation")


def load_data() -> dict:
    if DATA_FILE.exists():
        try:
            return json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {
        "owner_by_connection": {},
        "owner_chat_by_connection": {},
        "chat_mode": {},
        "settings": {},
        "message_cache": {},
        "deleted_log": {},
    }


def save_data() -> None:
    DATA_FILE.write_text(json.dumps(DATA, ensure_ascii=False, indent=2), encoding="utf-8")


DATA = load_data()


def ck(connection_id, chat_id) -> str:
    return f"{connection_id}:{chat_id}"


def mk(connection_id, chat_id, message_id) -> str:
    return f"{connection_id}:{chat_id}:{message_id}"


def get_settings(connection_id: str) -> dict:
    s = DATA["settings"].setdefault(connection_id, {})
    s.setdefault("notify", True)
    s.setdefault("mute_text", DEFAULT_MUTE_TEXT)
    s.setdefault("unmute_text", DEFAULT_UNMUTE_TEXT)
    s.setdefault("log_limit", 20)
    return s


def get_mode(connection_id: str, chat_id: int) -> str:
    return DATA["chat_mode"].get(ck(connection_id, chat_id), MODE_OFF)


def set_mode(connection_id: str, chat_id: int, mode: str) -> None:
    key = ck(connection_id, chat_id)
    if mode == MODE_OFF:
        DATA["chat_mode"].pop(key, None)
    else:
        DATA["chat_mode"][key] = mode
    save_data()


def describe_message(message) -> str:
    if message.text:
        return message.text
    if message.caption:
        return f"[медиа] {message.caption}"
    if message.photo:
        return "[фото]"
    if message.video:
        return "[видео]"
    if message.video_note:
        return "[видео-кружок]"
    if message.voice:
        return "[голосовое]"
    if message.audio:
        return "[аудио]"
    if message.document:
        return f"[файл] {message.document.file_name or ''}"
    if message.sticker:
        return f"[стикер] {message.sticker.emoji or ''}"
    if message.animation:
        return "[gif]"
    if message.location:
        return "[геолокация]"
    if message.contact:
        return "[контакт]"
    return "[сообщение]"


def message_type(message) -> str:
    for t in MEDIA_TYPES:
        if getattr(message, t, None):
            return "media"
    if message.text:
        return "text"
    return "media"


def cache_message(connection_id, chat_id, message) -> None:
    DATA["message_cache"][mk(connection_id, chat_id, message.message_id)] = {
        "from_id": message.from_user.id if message.from_user else None,
        "preview": describe_message(message),
    }
    if len(DATA["message_cache"]) > 5000:
        for k in list(DATA["message_cache"].keys())[:1000]:
            del DATA["message_cache"][k]
    save_data()


def log_deletion(connection_id, chat_id, preview) -> None:
    key = ck(connection_id, chat_id)
    log_list = DATA["deleted_log"].setdefault(key, [])
    log_list.append(preview)
    limit = get_settings(connection_id).get("log_limit", 20)
    if len(log_list) > limit:
        del log_list[: len(log_list) - limit]
    save_data()


async def notify_owner(context: ContextTypes.DEFAULT_TYPE, connection_id: str, text: str, force: bool = False) -> None:
    settings = get_settings(connection_id)
    if not force and not settings.get("notify", True):
        return
    owner_chat_id = DATA["owner_chat_by_connection"].get(connection_id)
    if not owner_chat_id:
        return
    try:
        await context.bot.send_message(chat_id=owner_chat_id, text=text, parse_mode=ParseMode.HTML)
    except TelegramError as e:
        log.warning("notify_owner failed: %s", e)


async def resolve_connection(connection_id: str, context: ContextTypes.DEFAULT_TYPE):
    owner_id = DATA["owner_by_connection"].get(connection_id)
    if owner_id is None:
        try:
            conn = await context.bot.get_business_connection(connection_id)
            owner_id = conn.user.id
            DATA["owner_by_connection"][connection_id] = owner_id
            DATA["owner_chat_by_connection"][connection_id] = conn.user_chat_id
            save_data()
        except TelegramError:
            pass
    return owner_id


def main_menu_keyboard(connection_id: str = None) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("📋 Команды", callback_data="menu:commands")],
        [InlineKeyboardButton("🔇 Замученные чаты", callback_data="menu:muted")],
        [InlineKeyboardButton("🗑 Логи удалений", callback_data="menu:logs")],
    ]
    if connection_id:
        notify_state = get_settings(connection_id).get("notify", True)
        label = "🔔 Уведомления: ВКЛ" if notify_state else "🔕 Уведомления: ВЫКЛ"
        rows.append([InlineKeyboardButton(label, callback_data="menu:toggle_notify")])
    return InlineKeyboardMarkup(rows)


HELP_TEXT = (
    "<b>Команды в личном чате с собеседником:</b>\n\n"
    "<code>.mute</code> — полный мут: удаляются все сообщения собеседника (текст и медиа)\n"
    "<code>.mutetext</code> — удалять только текстовые сообщения, медиа разрешено\n"
    "<code>.mutemedia</code> — удалять только медиа (фото/видео/кружки/файлы/стикеры), текст разрешён\n"
    "<code>.unmute</code> — снять мут полностью\n"
    "<code>.status</code> — узнать текущий режим этого чата (пришлю в личку с ботом)\n"
    "<code>.log</code> — прислать в личку с ботом последние удалённые сообщения этого чата\n"
    "<code>.clearlog</code> — очистить сохранённую историю удалений этого чата\n"
    "<code>.notifyon</code> / <code>.notifyoff</code> — включить/выключить уведомления об удалениях\n"
    "<code>.setmute текст</code> — задать свой текст замены при .mute\n"
    "<code>.setunmute текст</code> — задать свой текст замены при .unmute\n\n"
    "⚠️ У бота должно быть включено право «Управлять сообщениями» "
    "в Settings → Business → Chatbots."
)


async def handle_business_connection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    conn = update.business_connection
    connection_id = conn.id
    owner_chat_id = conn.user_chat_id

    DATA["owner_by_connection"][connection_id] = conn.user.id
    DATA["owner_chat_by_connection"][connection_id] = owner_chat_id
    save_data()

    if conn.is_enabled:
        try:
            await context.bot.send_message(
                chat_id=owner_chat_id,
                text=(
                    "✅ <b>Бот подключён к твоему аккаунту!</b>\n\n"
                    "Отправь /start, чтобы увидеть меню, или сразу пиши команды "
                    "(<code>.mute</code>, <code>.mutetext</code>, <code>.mutemedia</code>, "
                    "<code>.unmute</code>) прямо в личных чатах."
                ),
                parse_mode=ParseMode.HTML,
                reply_markup=main_menu_keyboard(connection_id),
            )
        except TelegramError as e:
            log.warning("connect notify failed: %s", e)
    else:
        try:
            await context.bot.send_message(
                chat_id=owner_chat_id,
                text="⚠️ Бизнес-подключение отключено. Команды временно не работают.",
                parse_mode=ParseMode.HTML,
            )
        except TelegramError as e:
            log.warning("disconnect notify failed: %s", e)


async def apply_deletion(context, connection_id, chat_id, message) -> bool:
    try:
        await context.bot.delete_message(
            business_connection_id=connection_id,
            chat_id=chat_id,
            message_id=message.message_id,
        )
        return True
    except TelegramError as e:
        log.warning("delete failed: %s", e)
        await notify_owner(
            context,
            connection_id,
            "⚠️ Не смог удалить сообщение — проверь право «Управлять сообщениями» "
            "в настройках бизнес-подключения.",
            force=True,
        )
        return False


async def handle_owner_command(update, context, message, connection_id, chat_id, text) -> bool:
    settings = get_settings(connection_id)

    if text == ".mute":
        set_mode(connection_id, chat_id, MODE_FULL)
        await context.bot.edit_message_text(business_connection_id=connection_id, chat_id=chat_id,
                                             message_id=message.message_id, text=settings["mute_text"])
        await notify_owner(context, connection_id, "🔇 Полный мут включён в этом чате.")
        return True

    if text == ".mutetext":
        set_mode(connection_id, chat_id, MODE_TEXT)
        await context.bot.edit_message_text(business_connection_id=connection_id, chat_id=chat_id,
                                             message_id=message.message_id, text=settings["mute_text"])
        await notify_owner(context, connection_id, "🔇 Мут текста включён (медиа разрешено).")
        return True

    if text == ".mutemedia":
        set_mode(connection_id, chat_id, MODE_MEDIA)
        await context.bot.edit_message_text(business_connection_id=connection_id, chat_id=chat_id,
                                             message_id=message.message_id, text=settings["mute_text"])
        await notify_owner(context, connection_id, "🔇 Мут медиа включён (текст разрешён).")
        return True

    if text == ".unmute":
        set_mode(connection_id, chat_id, MODE_OFF)
        await context.bot.edit_message_text(business_connection_id=connection_id, chat_id=chat_id,
                                             message_id=message.message_id, text=settings["unmute_text"])
        await notify_owner(context, connection_id, "🔊 Мут снят в этом чате.")
        return True

    if text == ".status":
        mode = get_mode(connection_id, chat_id)
        labels = {MODE_FULL: "полный мут", MODE_TEXT: "мут текста", MODE_MEDIA: "мут медиа", MODE_OFF: "мут выключен"}
        await context.bot.edit_message_text(business_connection_id=connection_id, chat_id=chat_id,
                                             message_id=message.message_id, text=".status")
        await notify_owner(context, connection_id, f"ℹ️ Режим этого чата: {labels[mode]}.", force=True)
        return True

    if text == ".log":
        key = ck(connection_id, chat_id)
        items = DATA["deleted_log"].get(key, [])
        await context.bot.edit_message_text(business_connection_id=connection_id, chat_id=chat_id,
                                             message_id=message.message_id, text=".log")
        if items:
            joined = "\n".join(f"• {i}" for i in items)
            await notify_owner(context, connection_id, f"🗑 Последние удаления в этом чате:\n{joined}", force=True)
        else:
            await notify_owner(context, connection_id, "Логов удалений в этом чате пока нет.", force=True)
        return True

    if text == ".clearlog":
        DATA["deleted_log"].pop(ck(connection_id, chat_id), None)
        save_data()
        await context.bot.edit_message_text(business_connection_id=connection_id, chat_id=chat_id,
                                             message_id=message.message_id, text=".clearlog")
        await notify_owner(context, connection_id, "🧹 Лог удалений этого чата очищен.", force=True)
        return True

    if text == ".notifyon":
        settings["notify"] = True
        save_data()
        await context.bot.edit_message_text(business_connection_id=connection_id, chat_id=chat_id,
                                             message_id=message.message_id, text=".notifyon")
        await notify_owner(context, connection_id, "🔔 Уведомления включены.", force=True)
        return True

    if text == ".notifyoff":
        settings["notify"] = False
        save_data()
        await context.bot.edit_message_text(business_connection_id=connection_id, chat_id=chat_id,
                                             message_id=message.message_id, text=".notifyoff")
        await notify_owner(context, connection_id, "🔕 Уведомления выключены.", force=True)
        return True

    if text.startswith(".setmute "):
        new_text = text[len(".setmute "):].strip()
        if new_text:
            settings["mute_text"] = new_text
            save_data()
            await context.bot.edit_message_text(business_connection_id=connection_id, chat_id=chat_id,
                                                 message_id=message.message_id, text=new_text)
            await notify_owner(context, connection_id, f"✅ Текст для .mute обновлён: {new_text}", force=True)
        return True

    if text.startswith(".setunmute "):
        new_text = text[len(".setunmute "):].strip()
        if new_text:
            settings["unmute_text"] = new_text
            save_data()
            await context.bot.edit_message_text(business_connection_id=connection_id, chat_id=chat_id,
                                                 message_id=message.message_id, text=new_text)
            await notify_owner(context, connection_id, f"✅ Текст для .unmute обновлён: {new_text}", force=True)
        return True

    return False


async def handle_business_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.business_message
    connection_id = message.business_connection_id
    chat_id = message.chat_id
    owner_id = await resolve_connection(connection_id, context)

    is_owner_message = message.from_user and owner_id and message.from_user.id == owner_id

    if is_owner_message:
        text = (message.text or "").strip()
        handled = await handle_owner_command(update, context, message, connection_id, chat_id, text)
        if not handled:
            cache_message(connection_id, chat_id, message)
        return

    cache_message(connection_id, chat_id, message)
    mode = get_mode(connection_id, chat_id)
    mtype = message_type(message)

    should_delete = (
        mode == MODE_FULL
        or (mode == MODE_TEXT and mtype == "text")
        or (mode == MODE_MEDIA and mtype == "media")
    )

    if should_delete:
        preview = describe_message(message)
        ok = await apply_deletion(context, connection_id, chat_id, message)
        if ok:
            log_deletion(connection_id, chat_id, preview)
            await notify_owner(context, connection_id, f"🗑 Удалено сообщение собеседника:\n{preview}")


async def handle_edited_business_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.edited_business_message
    connection_id = message.business_connection_id
    chat_id = message.chat_id
    owner_id = await resolve_connection(connection_id, context)
    is_owner_message = message.from_user and owner_id and message.from_user.id == owner_id

    key = mk(connection_id, chat_id, message.message_id)
    old = DATA["message_cache"].get(key, {}).get("preview", "неизвестно")
    new_preview = describe_message(message)

    if not is_owner_message:
        mode = get_mode(connection_id, chat_id)
        mtype = message_type(message)
        should_delete = (
            mode == MODE_FULL
            or (mode == MODE_TEXT and mtype == "text")
            or (mode == MODE_MEDIA and mtype == "media")
        )
        if should_delete:
            await apply_deletion(context, connection_id, chat_id, message)
            log_deletion(connection_id, chat_id, f"(ред.) {new_preview}")
        await notify_owner(
            context, connection_id,
            f"✏️ Собеседник отредактировал сообщение:\nБыло: {old}\nСтало: {new_preview}",
        )

    cache_message(connection_id, chat_id, message)


async def handle_deleted_business_messages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    deleted = update.deleted_business_messages
    connection_id = deleted.business_connection_id
    chat_id = deleted.chat.id

    lines = []
    for message_id in deleted.message_ids:
        entry = DATA["message_cache"].get(mk(connection_id, chat_id, message_id))
        if entry:
            lines.append(entry["preview"])

    if lines:
        joined = "\n".join(f"• {i}" for i in lines)
        await notify_owner(context, connection_id, f"🗑 Собеседник сам удалил у себя сообщение(-я):\n{joined}")


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    owner_chat_id = update.message.chat_id
    connection_id = None
    for cid, chat in DATA["owner_chat_by_connection"].items():
        if chat == owner_chat_id:
            connection_id = cid
            break
    await update.message.reply_text(
        "Привет! Управляю личными чатами через Telegram Business.\nВыбери раздел:",
        reply_markup=main_menu_keyboard(connection_id),
    )


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    owner_chat_id = query.message.chat_id
    connection_id = None
    for cid, chat in DATA["owner_chat_by_connection"].items():
        if chat == owner_chat_id:
            connection_id = cid
            break

    if query.data == "menu:commands":
        await query.edit_message_text(HELP_TEXT, parse_mode=ParseMode.HTML, reply_markup=main_menu_keyboard(connection_id))

    elif query.data == "menu:muted":
        active = [k for k, v in DATA["chat_mode"].items() if v != MODE_OFF]
        if active:
            text = "🔇 Активные муты:\n" + "\n".join(f"• <code>{k}</code> — {DATA['chat_mode'][k]}" for k in active)
        else:
            text = "Сейчас нет замученных чатов."
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=main_menu_keyboard(connection_id))

    elif query.data == "menu:logs":
        if connection_id and DATA["deleted_log"]:
            chunks = []
            for key, items in DATA["deleted_log"].items():
                if key.startswith(connection_id + ":") and items:
                    chunks.append(f"<b>{key.split(':')[-1]}</b>\n" + "\n".join(f"• {i}" for i in items[-5:]))
            text = "\n\n".join(chunks) if chunks else "Логов пока нет."
        else:
            text = "Логов пока нет."
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=main_menu_keyboard(connection_id))

    elif query.data == "menu:toggle_notify":
        if connection_id:
            settings = get_settings(connection_id)
            settings["notify"] = not settings.get("notify", True)
            save_data()
        await query.edit_message_reply_markup(reply_markup=main_menu_keyboard(connection_id))


async def dispatcher(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        if update.business_connection is not None:
            await handle_business_connection(update, context)
        elif update.business_message is not None:
            await handle_business_message(update, context)
        elif update.edited_business_message is not None:
            await handle_edited_business_message(update, context)
        elif update.deleted_business_messages is not None:
            await handle_deleted_business_messages(update, context)
        elif update.callback_query is not None:
            await handle_callback(update, context)
        elif update.message is not None and update.message.text == "/start":
            await handle_start(update, context)
    except Exception:
        log.exception("dispatcher error")


def main() -> None:
    token = BOT_TOKEN or os.environ.get("BOT_TOKEN")
    if not token:
        raise SystemExit("Вставь токен в переменную BOT_TOKEN в начале файла.")
    application = Application.builder().token(token).build()
    application.add_handler(TypeHandler(Update, dispatcher))
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
