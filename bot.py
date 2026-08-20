BOT_TOKEN = "8893361270:AAF8kJgzBX_2P5BKwHtWl18slL-FNObQgUw"

import ast
import asyncio
import html
import json
import logging
import operator
import os
import time
from datetime import datetime, timezone

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import (
    BusinessConnection,
    BusinessMessagesDeleted,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
log = logging.getLogger("business-bot")

STATE_FILE = "bot_state.json"
ARCHIVE_FILE = "bot_archive.json"
ARCHIVE_LIMIT = 8000

DEFAULT_SETTINGS = {
    "save_deleted": True,
    "save_edited": True,
    "notify": True,
}

STATE = {
    "connections": {},
    "muted": {},
    "settings": {},
    "conn_index": {},
}
ARCHIVE = {}
_dirty = False


def load_data():
    global ARCHIVE
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            for key in STATE:
                if key in data and isinstance(data[key], dict):
                    STATE[key] = data[key]
            log.info("Состояние загружено из %s", STATE_FILE)
        except Exception as e:
            log.error("Не удалось загрузить состояние: %s", e)
    if os.path.exists(ARCHIVE_FILE):
        try:
            with open(ARCHIVE_FILE, "r", encoding="utf-8") as f:
                ARCHIVE = json.load(f)
            log.info("Архив сообщений загружен (%d записей)", len(ARCHIVE))
        except Exception as e:
            log.error("Не удалось загрузить архив: %s", e)
            ARCHIVE = {}


def save_data():
    global _dirty
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(STATE, f, ensure_ascii=False, indent=2)
        if len(ARCHIVE) > ARCHIVE_LIMIT:
            keys = sorted(ARCHIVE, key=lambda k: ARCHIVE[k].get("ts", 0))
            for k in keys[: len(ARCHIVE) - ARCHIVE_LIMIT]:
                ARCHIVE.pop(k, None)
        with open(ARCHIVE_FILE, "w", encoding="utf-8") as f:
            json.dump(ARCHIVE, f, ensure_ascii=False)
        _dirty = False
    except Exception as e:
        log.error("Ошибка сохранения данных: %s", e)


def mark_dirty():
    global _dirty
    _dirty = True


async def autosave_loop():
    while True:
        await asyncio.sleep(15)
        if _dirty:
            save_data()


def settings_of(owner_id: int) -> dict:
    key = str(owner_id)
    cur = STATE["settings"].get(key)
    if not cur:
        cur = dict(DEFAULT_SETTINGS)
        STATE["settings"][key] = cur
        mark_dirty()
    for k, v in DEFAULT_SETTINGS.items():
        cur.setdefault(k, v)
    return cur


def muted_of(owner_id: int) -> list:
    key = str(owner_id)
    if key not in STATE["muted"]:
        STATE["muted"][key] = []
    return STATE["muted"][key]


def owner_by_conn(conn_id: str):
    val = STATE["conn_index"].get(conn_id)
    return int(val) if val is not None else None


def conn_of(owner_id: int):
    return STATE["connections"].get(str(owner_id))


def owner_chat(owner_id: int) -> int:
    info = conn_of(owner_id) or {}
    return int(info.get("user_chat_id") or owner_id)


_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _eval_node(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval_node(node.operand))
    raise ValueError("unsupported expression")


def safe_calc(expr: str):
    return _eval_node(ast.parse(expr, mode="eval").body)


CONTENT_NAMES = {
    "text": "текст",
    "photo": "фото",
    "video": "видео",
    "video_note": "кружок",
    "voice": "голосовое",
    "audio": "аудио",
    "document": "файл",
    "sticker": "стикер",
    "animation": "гифка",
    "location": "геолокация",
    "contact": "контакт",
    "poll": "опрос",
    "dice": "дайс",
    "story": "история",
}

COMMANDS = [
    (".mute", "замьютить собеседника — все его новые сообщения удаляются"),
    (".unmute", "снять мьют с текущего чата"),
    (".ky", "заменить сообщение на «привет»"),
    (".id", "показать id текущего чата и собеседника"),
    (".del", "удалить сообщение, на которое сделан reply"),
    (".info", "информация о собеседнике"),
    (".ping", "проверить задержку бота"),
    (".time", "текущие дата и время"),
    (".calc", "калькулятор, например .calc 2+2*10"),
    (".mutelist", "список замьюченных чатов"),
    (".cmds / .help", "этот список команд"),
]


def commands_text() -> str:
    rows = "\n".join(f"<code>{html.escape(c)}</code> — {html.escape(d)}" for c, d in COMMANDS)
    return "📋 <b>Команды</b>\n\n" + rows + "\n\nВсе команды пишутся в личном чате с собеседником и работают только от вашего имени."


def main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📋 Команды", callback_data="menu:cmds"),
                InlineKeyboardButton(text="⚙️ Настройки", callback_data="menu:settings"),
                InlineKeyboardButton(text="📊 Статус", callback_data="menu:status"),
            ]
        ]
    )


def settings_kb(owner_id: int) -> InlineKeyboardMarkup:
    s = settings_of(owner_id)

    def mark(v):
        return "🟢 Вкл" if v else "🔴 Выкл"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"🗑 Сохранение удалёнок: {mark(s['save_deleted'])}", callback_data="toggle:save_deleted")],
            [InlineKeyboardButton(text=f"✏️ Сохранение редактирований: {mark(s['save_edited'])}", callback_data="toggle:save_edited")],
            [InlineKeyboardButton(text=f"🔔 Уведомления: {mark(s['notify'])}", callback_data="toggle:notify")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu:home")],
        ]
    )


def back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="menu:home")]])


def status_text(owner_id: int) -> str:
    info = conn_of(owner_id)
    s = settings_of(owner_id)
    connected = bool(info and info.get("is_enabled"))
    lines = [
        "📊 <b>Статус</b>",
        "",
        f"Подключение: {'✅ активно' if connected else '❌ не активно'}",
        f"Право на удаление: {'✅ есть' if (info or {}).get('can_delete') else '⚠️ нет'}",
        f"Чатов в мьюте: <b>{len(muted_of(owner_id))}</b>",
        f"Сообщений в архиве: <b>{len(ARCHIVE)}</b>",
        "",
        f"🗑 Сохранение удалёнок: {'вкл' if s['save_deleted'] else 'выкл'}",
        f"✏️ Сохранение редактирований: {'вкл' if s['save_edited'] else 'выкл'}",
        f"🔔 Уведомления: {'вкл' if s['notify'] else 'выкл'}",
    ]
    return "\n".join(lines)


def describe(message: Message) -> dict:
    ctype = message.content_type if isinstance(message.content_type, str) else str(message.content_type)
    text = message.text or message.caption or ""
    user = message.from_user
    name = " ".join(filter(None, [getattr(user, "first_name", None), getattr(user, "last_name", None)])) if user else "?"
    return {
        "chat_id": message.chat.id,
        "message_id": message.message_id,
        "user_id": user.id if user else 0,
        "name": name or "?",
        "username": user.username if user and user.username else "",
        "type": ctype,
        "text": text,
        "ts": int(time.time()),
    }


def archive_key(chat_id: int, message_id: int) -> str:
    return f"{chat_id}:{message_id}"


def store(message: Message):
    rec = describe(message)
    ARCHIVE[archive_key(rec["chat_id"], rec["message_id"])] = rec
    mark_dirty()


def render_record(rec: dict) -> str:
    who = html.escape(rec.get("name") or "?")
    uname = f" (@{html.escape(rec['username'])})" if rec.get("username") else ""
    ctype = CONTENT_NAMES.get(rec.get("type"), rec.get("type", "?"))
    body = html.escape(rec.get("text") or "")
    stamp = datetime.fromtimestamp(rec.get("ts", 0)).strftime("%d.%m.%Y %H:%M:%S")
    out = [f"👤 <b>{who}</b>{uname} <code>{rec.get('user_id')}</code>", f"🕓 {stamp}", f"📎 Тип: {ctype}"]
    if body:
        out.append(f"💬 {body}")
    return "\n".join(out)


bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()


async def send_owner(owner_id: int, text: str, reply_markup=None, force: bool = False):
    if not force and not settings_of(owner_id)["notify"]:
        return
    try:
        await bot.send_message(owner_chat(owner_id), text, reply_markup=reply_markup)
    except Exception as e:
        log.error("Не удалось отправить сообщение владельцу %s: %s", owner_id, e)


async def edit_own(conn_id: str, chat_id: int, message_id: int, text: str):
    try:
        await bot.edit_message_text(
            business_connection_id=conn_id,
            chat_id=chat_id,
            message_id=message_id,
            text=text,
        )
        return True
    except Exception as e:
        log.error("Ошибка редактирования сообщения %s в чате %s: %s", message_id, chat_id, e)
        return False


async def drop_messages(conn_id: str, message_ids: list) -> bool:
    try:
        await bot.delete_business_messages(business_connection_id=conn_id, message_ids=message_ids)
        return True
    except Exception as e:
        log.error("Ошибка удаления сообщений %s: %s", message_ids, e)
        return False


@dp.business_connection()
async def on_business_connection(connection: BusinessConnection):
    owner_id = connection.user.id
    user_chat_id = getattr(connection, "user_chat_id", None) or owner_id
    rights = getattr(connection, "rights", None)
    can_delete = bool(getattr(rights, "can_delete_all_messages", False)) if rights else bool(getattr(connection, "can_reply", False)) and False
    can_read = bool(getattr(rights, "can_read_messages", True)) if rights else True

    STATE["connections"][str(owner_id)] = {
        "connection_id": connection.id,
        "user_chat_id": user_chat_id,
        "is_enabled": bool(connection.is_enabled),
        "can_delete": can_delete,
        "can_read": can_read,
        "updated": int(time.time()),
    }
    STATE["conn_index"][connection.id] = owner_id
    settings_of(owner_id)
    muted_of(owner_id)
    mark_dirty()
    save_data()

    if connection.is_enabled:
        log.info("Бизнес-подключение включено: owner=%s conn=%s", owner_id, connection.id)
        hello = (
            "✅ <b>Бот успешно подключён</b>\n\n"
            "Теперь я работаю в ваших личных чатах.\n"
            f"ID подключения: <code>{html.escape(connection.id)}</code>\n"
            f"Ваш ID: <code>{owner_id}</code>\n\n"
            "Напишите <code>.cmds</code> в любом личном чате, чтобы увидеть список команд."
        )
        await send_owner(owner_id, hello, reply_markup=main_kb(), force=True)
        if not can_read:
            await send_owner(
                owner_id,
                "⚠️ Боту не выдано право <b>«Читать сообщения»</b> — он не будет видеть переписку. "
                "Включите его в настройках подключения.",
                force=True,
            )
        if not can_delete:
            await send_owner(
                owner_id,
                "⚠️ <b>Нет права «Удалять сообщения»</b>.\n\n"
                "Без него команда <code>.mute</code> не сможет удалять сообщения собеседника. "
                "Откройте Настройки → Telegram для бизнеса → Чат-боты → выберите бота и включите право "
                "<b>«Удалять сообщения»</b>.",
                force=True,
            )
    else:
        log.info("Бизнес-подключение отключено: owner=%s", owner_id)
        await send_owner(owner_id, "🔌 <b>Бот отключён</b> от бизнес-аккаунта.", force=True)


async def resolve_owner(conn_id: str):
    owner_id = owner_by_conn(conn_id)
    if owner_id is not None:
        return owner_id
    try:
        connection = await bot.get_business_connection(conn_id)
    except Exception as e:
        log.error("Не удалось получить business_connection %s: %s", conn_id, e)
        return None
    owner_id = connection.user.id
    rights = getattr(connection, "rights", None)
    STATE["connections"][str(owner_id)] = {
        "connection_id": connection.id,
        "user_chat_id": getattr(connection, "user_chat_id", None) or owner_id,
        "is_enabled": bool(connection.is_enabled),
        "can_delete": bool(getattr(rights, "can_delete_all_messages", False)) if rights else False,
        "can_read": bool(getattr(rights, "can_read_messages", True)) if rights else True,
        "updated": int(time.time()),
    }
    STATE["conn_index"][connection.id] = owner_id
    mark_dirty()
    return owner_id


async def handle_owner_command(message: Message, owner_id: int, conn_id: str) -> bool:
    raw = (message.text or "").strip()
    if not raw.startswith("."):
        return False
    parts = raw.split(maxsplit=1)
    cmd = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""
    chat_id = message.chat.id
    muted = muted_of(owner_id)

    if cmd == ".mute":
        if chat_id not in muted:
            muted.append(chat_id)
            mark_dirty()
        await edit_own(conn_id, chat_id, message.message_id, "Замолчи")
        if not (conn_of(owner_id) or {}).get("can_delete"):
            await send_owner(
                owner_id,
                "⚠️ Мьют включён, но у бота нет права <b>«Удалять сообщения»</b> — удаление не сработает.",
            )
        log.info("Чат %s замьючен владельцем %s", chat_id, owner_id)
        return True

    if cmd == ".unmute":
        if chat_id in muted:
            muted.remove(chat_id)
            mark_dirty()
        await edit_own(conn_id, chat_id, message.message_id, "Размьючен")
        log.info("Чат %s размьючен владельцем %s", chat_id, owner_id)
        return True

    if cmd == ".ky":
        await edit_own(conn_id, chat_id, message.message_id, "привет")
        return True

    if cmd == ".id":
        peer = message.chat
        text = (
            f"🆔 Чат: <code>{peer.id}</code>\n"
            f"👤 Собеседник: <code>{peer.id}</code>\n"
            f"👑 Владелец: <code>{owner_id}</code>"
        )
        await edit_own(conn_id, chat_id, message.message_id, text)
        return True

    if cmd == ".del":
        target = message.reply_to_message
        if not target:
            await edit_own(conn_id, chat_id, message.message_id, "⚠️ Нужно ответить на сообщение")
            return True
        ok = await drop_messages(conn_id, [target.message_id])
        await edit_own(
            conn_id,
            chat_id,
            message.message_id,
            "🗑 Сообщение удалено" if ok else "⚠️ Не удалось удалить (проверьте право «Удалять сообщения»)",
        )
        return True

    if cmd == ".info":
        peer = message.chat
        name = " ".join(filter(None, [peer.first_name, peer.last_name])) or "—"
        uname = f"@{peer.username}" if peer.username else "—"
        text = (
            "ℹ️ <b>Собеседник</b>\n"
            f"Имя: {html.escape(name)}\n"
            f"Username: {html.escape(uname)}\n"
            f"ID: <code>{peer.id}</code>\n"
            f"Мьют: {'🔇 да' if chat_id in muted else '🔊 нет'}"
        )
        await edit_own(conn_id, chat_id, message.message_id, text)
        return True

    if cmd == ".ping":
        sent = message.date.replace(tzinfo=timezone.utc).timestamp() if message.date else time.time()
        delay = max(0.0, time.time() - sent)
        await edit_own(conn_id, chat_id, message.message_id, f"🏓 pong — {delay:.2f} c")
        return True

    if cmd == ".time":
        now = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        await edit_own(conn_id, chat_id, message.message_id, f"🕓 {now}")
        return True

    if cmd == ".calc":
        if not arg:
            await edit_own(conn_id, chat_id, message.message_id, "⚠️ Пример: .calc 2+2*10")
            return True
        try:
            result = safe_calc(arg)
            await edit_own(conn_id, chat_id, message.message_id, f"🧮 {html.escape(arg)} = <b>{result}</b>")
        except Exception:
            await edit_own(conn_id, chat_id, message.message_id, "⚠️ Не удалось вычислить выражение")
        return True

    if cmd == ".mutelist":
        if not muted:
            text = "🔇 Замьюченных чатов нет"
        else:
            rows = "\n".join(f"• <code>{cid}</code>" for cid in muted)
            text = f"🔇 <b>Замьючено чатов: {len(muted)}</b>\n{rows}"
        await edit_own(conn_id, chat_id, message.message_id, text)
        return True

    if cmd in (".cmds", ".help"):
        await edit_own(conn_id, chat_id, message.message_id, commands_text())
        return True

    return False


@dp.business_message()
async def on_business_message(message: Message):
    conn_id = message.business_connection_id
    if not conn_id:
        return
    if getattr(message, "sender_business_bot", None):
        return

    owner_id = await resolve_owner(conn_id)
    if owner_id is None:
        return

    store(message)

    sender_id = message.from_user.id if message.from_user else 0

    if sender_id == owner_id:
        try:
            await handle_owner_command(message, owner_id, conn_id)
        except Exception as e:
            log.exception("Ошибка обработки команды: %s", e)
        return

    if message.chat.id in muted_of(owner_id):
        ok = await drop_messages(conn_id, [message.message_id])
        if ok:
            log.info("Удалено сообщение %s в замьюченном чате %s", message.message_id, message.chat.id)
        else:
            log.warning("Не удалось удалить сообщение в замьюченном чате %s", message.chat.id)


@dp.edited_business_message()
async def on_edited_business_message(message: Message):
    conn_id = message.business_connection_id
    if not conn_id:
        return
    owner_id = await resolve_owner(conn_id)
    if owner_id is None:
        return

    key = archive_key(message.chat.id, message.message_id)
    old = ARCHIVE.get(key)
    new_text = message.text or message.caption or ""
    old_text = (old or {}).get("text", "")

    store(message)

    if not settings_of(owner_id)["save_edited"]:
        return
    if message.from_user and message.from_user.id == owner_id:
        return
    if old_text == new_text:
        return

    who = html.escape((old or describe(message)).get("name", "?"))
    text = (
        "✏️ <b>Сообщение отредактировано</b>\n\n"
        f"👤 {who} <code>{message.from_user.id if message.from_user else '?'}</code>\n"
        f"💬 Чат: <code>{message.chat.id}</code>\n\n"
        f"<b>Было:</b>\n{html.escape(old_text) if old_text else '<i>нет данных</i>'}\n\n"
        f"<b>Стало:</b>\n{html.escape(new_text) if new_text else '<i>пусто</i>'}"
    )
    await send_owner(owner_id, text)


@dp.deleted_business_messages()
async def on_deleted_business_messages(event: BusinessMessagesDeleted):
    conn_id = event.business_connection_id
    owner_id = await resolve_owner(conn_id)
    if owner_id is None:
        return
    if not settings_of(owner_id)["save_deleted"]:
        return

    chat_id = event.chat.id
    if chat_id in muted_of(owner_id):
        return

    blocks = []
    for mid in event.message_ids:
        rec = ARCHIVE.get(archive_key(chat_id, mid))
        if not rec:
            blocks.append(f"❔ Сообщение <code>{mid}</code> — содержимое не сохранено")
            continue
        if rec.get("user_id") == owner_id:
            continue
        blocks.append(render_record(rec))

    if not blocks:
        return

    text = "🗑 <b>Удалённые сообщения</b>\n💬 Чат: <code>%s</code>\n\n%s" % (chat_id, "\n\n".join(blocks))
    for chunk_start in range(0, len(text), 3800):
        await send_owner(owner_id, text[chunk_start : chunk_start + 3800])


@dp.message(CommandStart())
async def on_start(message: Message):
    owner_id = message.from_user.id
    settings_of(owner_id)
    await message.answer(
        "👋 Это менеджер личных чатов через Telegram Business API.\n\n"
        "Подключите бота: <b>Настройки → Telegram для бизнеса → Чат-боты</b> "
        "и обязательно включите право <b>«Удалять сообщения»</b>.",
        reply_markup=main_kb(),
    )


@dp.callback_query(F.data.startswith("menu:"))
async def on_menu(call: CallbackQuery):
    owner_id = call.from_user.id
    section = call.data.split(":", 1)[1]
    try:
        if section == "cmds":
            await call.message.edit_text(commands_text(), reply_markup=back_kb())
        elif section == "settings":
            await call.message.edit_text("⚙️ <b>Настройки</b>\n\nНажмите, чтобы переключить.", reply_markup=settings_kb(owner_id))
        elif section == "status":
            await call.message.edit_text(status_text(owner_id), reply_markup=back_kb())
        else:
            await call.message.edit_text(
                "🤖 <b>Панель управления</b>\n\nВыберите раздел.", reply_markup=main_kb()
            )
    except Exception as e:
        log.error("Ошибка обновления меню: %s", e)
    await call.answer()


@dp.callback_query(F.data.startswith("toggle:"))
async def on_toggle(call: CallbackQuery):
    owner_id = call.from_user.id
    key = call.data.split(":", 1)[1]
    s = settings_of(owner_id)
    if key in s:
        s[key] = not s[key]
        mark_dirty()
        save_data()
    try:
        await call.message.edit_text("⚙️ <b>Настройки</b>\n\nНажмите, чтобы переключить.", reply_markup=settings_kb(owner_id))
    except Exception as e:
        log.error("Ошибка обновления настроек: %s", e)
    await call.answer("Сохранено")


async def main():
    if not BOT_TOKEN:
        raise SystemExit("Укажите BOT_TOKEN в начале файла bot.py")
    load_data()
    asyncio.create_task(autosave_loop())
    allowed = dp.resolve_used_update_types()
    for extra in (
        "business_connection",
        "business_message",
        "edited_business_message",
        "deleted_business_messages",
        "callback_query",
        "message",
    ):
        if extra not in allowed:
            allowed.append(extra)
    log.info("Запуск polling, allowed_updates=%s", allowed)
    try:
        await bot.delete_webhook(drop_pending_updates=True)
    except Exception as e:
        log.error("delete_webhook: %s", e)
    try:
        await dp.start_polling(bot, allowed_updates=allowed)
    finally:
        save_data()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        save_data()
        log.info("Остановлено")
