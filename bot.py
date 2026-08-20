BOT_TOKEN = "8893361270:AAF8kJgzBX_2P5BKwHtWl18slL-FNObQgUw"

ADMIN_ID = 2022155738
BOT_VERSION = "3.0"

import ast
import asyncio
import html
import json
import logging
import operator
import os
import random
import time
from datetime import datetime, timedelta, timezone

import aiogram
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
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
LOG_LIMIT = 400
PAGE_SIZE = 5
START_TS = time.time()

DEFAULT_SETTINGS = {
    "save_deleted": True,
    "save_edited": True,
    "notify": True,
    "log_media": True,
    "mute_default": False,
    "silent": False,
    "autodelete_cmd": False,
}

SETTINGS_META = [
    ("save_deleted", "🗑 Сохранение удалёнок"),
    ("save_edited", "✏️ Сохранение правок"),
    ("notify", "🔔 Уведомления"),
    ("log_media", "🖼 Медиа в удалёнках"),
    ("mute_default", "🔇 Мьют для новых чатов"),
    ("silent", "🤫 Тихий режим"),
    ("autodelete_cmd", "🧹 Автоудаление команд"),
]

CMD_REGISTRY = [
    ("mute", ".mute", "модерация", "заткнуть собеседника — всё, что он пишет, испаряется"),
    ("unmute", ".unmute", "модерация", "вернуть человеку право голоса"),
    ("mutelist", ".mutelist", "модерация", "кто сейчас в списке молчунов"),
    ("del", ".del", "модерация", "удалить сообщение, на которое сделан reply"),
    ("clear", ".clear N", "модерация", "смести последние N своих сообщений"),
    ("afk", ".afk текст", "модерация", "афк-автоответ: один раз на чат, ничего не удаляя"),
    ("afkoff", ".afkoff", "модерация", "выключить афк и вернуться к людям"),
    ("ky", ".ky", "текст", "превращает сообщение в «привет»"),
    ("rev", ".rev текст", "текст", "переворачивает текст задом наперёд"),
    ("spoiler", ".spoiler текст", "текст", "прячет текст под спойлер"),
    ("b", ".b текст", "текст", "жирный текст"),
    ("i", ".i текст", "текст", "курсив"),
    ("quote", ".quote текст", "текст", "оформить как цитату"),
    ("up", ".up текст", "текст", "ПЕРЕВОДИТ В КАПС"),
    ("mock", ".mock текст", "текст", "сАрКаСтИчНыЙ рЕгИсТр"),
    ("tic", ".tic", "игры", "крестики-нолики прямо в переписке"),
    ("ticstop", ".ticstop", "игры", "закончить партию досрочно"),
    ("roll", ".roll", "игры", "случайное число 1–100"),
    ("coin", ".coin", "игры", "орёл или решка"),
    ("id", ".id", "утилиты", "id чата и владельца"),
    ("info", ".info", "утилиты", "досье на собеседника"),
    ("ping", ".ping", "утилиты", "🏓 pong и задержка"),
    ("time", ".time", "утилиты", "текущие дата и время"),
    ("calc", ".calc выражение", "утилиты", "калькулятор без калькулятора"),
    ("type", ".type", "утилиты", "вечное «печатает…» до вашего следующего сообщения"),
    ("stats", ".stats", "утилиты", "личная статистика по боту"),
    ("cmds", ".cmds / .help", "утилиты", "этот самый список"),
]

CAT_ORDER = [
    ("модерация", "🛡 Модерация"),
    ("текст", "✍️ Текст"),
    ("игры", "🎲 Игры"),
    ("утилиты", "🧰 Утилиты"),
]

STATE = {
    "connections": {},
    "conn_index": {},
    "muted": {},
    "settings": {},
    "global_settings": dict(DEFAULT_SETTINGS),
    "commands": {},
    "stats": {
        "deleted_by_bot": 0,
        "logged_deleted": 0,
        "logged_edited": 0,
        "games": 0,
        "wins": 0,
        "losses": 0,
        "draws": 0,
        "commands_used": 0,
    },
    "logs": {"deleted": [], "edited": []},
    "peers": {},
    "daily": {},
    "afk": {},
    "tic": {},
    "board_games": {},
}
ARCHIVE = {}
TYPING_TASKS = {}
_dirty = False


def load_data():
    global ARCHIVE
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            for key, val in data.items():
                if key in STATE and isinstance(val, type(STATE[key])):
                    if isinstance(val, dict):
                        STATE[key].update(val)
                    else:
                        STATE[key] = val
            log.info("Состояние поднято из %s", STATE_FILE)
        except Exception as e:
            log.error("Не удалось загрузить состояние: %s", e)
    for key, val in DEFAULT_SETTINGS.items():
        STATE["global_settings"].setdefault(key, val)
    for item in CMD_REGISTRY:
        STATE["commands"].setdefault(item[0], True)
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
            json.dump(STATE, f, ensure_ascii=False, indent=1)
        if len(ARCHIVE) > ARCHIVE_LIMIT:
            keys = sorted(ARCHIVE, key=lambda k: ARCHIVE[k].get("ts", 0))
            for k in keys[: len(ARCHIVE) - ARCHIVE_LIMIT]:
                ARCHIVE.pop(k, None)
        with open(ARCHIVE_FILE, "w", encoding="utf-8") as f:
            json.dump(ARCHIVE, f, ensure_ascii=False)
        _dirty = False
    except Exception as e:
        log.error("Ошибка сохранения: %s", e)


def mark_dirty():
    global _dirty
    _dirty = True


async def autosave_loop():
    while True:
        await asyncio.sleep(12)
        if _dirty:
            save_data()


def settings_of(owner_id) -> dict:
    key = str(owner_id)
    cur = STATE["settings"].get(key)
    if not cur:
        cur = dict(STATE["global_settings"])
        STATE["settings"][key] = cur
        mark_dirty()
    for k, v in DEFAULT_SETTINGS.items():
        cur.setdefault(k, v)
    return cur


def muted_of(owner_id) -> list:
    key = str(owner_id)
    if key not in STATE["muted"]:
        STATE["muted"][key] = []
        mark_dirty()
    return STATE["muted"][key]


def conn_of(owner_id):
    return STATE["connections"].get(str(owner_id))


def owner_by_conn(conn_id):
    val = STATE["conn_index"].get(conn_id)
    return int(val) if val is not None else None


def owner_chat(owner_id) -> int:
    info = conn_of(owner_id) or {}
    return int(info.get("user_chat_id") or owner_id)


def cmd_enabled(key) -> bool:
    return bool(STATE["commands"].get(key, True))


def bump(key, amount=1):
    STATE["stats"][key] = STATE["stats"].get(key, 0) + amount
    mark_dirty()


def bump_daily(field):
    day = datetime.now().strftime("%Y-%m-%d")
    row = STATE["daily"].setdefault(day, {"del": 0, "edit": 0, "mute": 0})
    row[field] = row.get(field, 0) + 1
    cutoff = (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d")
    for old in [d for d in list(STATE["daily"]) if d < cutoff]:
        STATE["daily"].pop(old, None)
    mark_dirty()


def uptime_text() -> str:
    sec = int(time.time() - START_TS)
    d, sec = divmod(sec, 86400)
    h, sec = divmod(sec, 3600)
    m, s = divmod(sec, 60)
    parts = []
    if d:
        parts.append(f"{d}д")
    if h:
        parts.append(f"{h}ч")
    if m:
        parts.append(f"{m}м")
    parts.append(f"{s}с")
    return " ".join(parts)


def memory_text() -> str:
    try:
        import resource

        kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return f"{kb / 1024:.1f} МБ"
    except Exception:
        return "н/д"


STYLE_OK = False
try:
    _probe = InlineKeyboardButton(text="x", callback_data="x", style="primary")
    STYLE_OK = getattr(_probe, "style", None) == "primary"
except Exception:
    STYLE_OK = False

STYLE_EMOJI = {"success": "🟢", "danger": "🔴", "primary": "🔵"}


def btn(text: str, data: str, style: str = None) -> InlineKeyboardButton:
    if style and STYLE_OK:
        try:
            return InlineKeyboardButton(text=text, callback_data=data, style=style)
        except Exception:
            pass
    if style:
        text = f"{STYLE_EMOJI.get(style, '')}{text}"
    return InlineKeyboardButton(text=text, callback_data=data)


def plain_kb(kb: InlineKeyboardMarkup) -> InlineKeyboardMarkup:
    rows = []
    for row in kb.inline_keyboard:
        new_row = []
        for b in row:
            mark = STYLE_EMOJI.get(getattr(b, "style", None) or "", "")
            new_row.append(InlineKeyboardButton(text=f"{mark}{b.text}", callback_data=b.callback_data))
        rows.append(new_row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


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
    raise ValueError("bad expression")


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
MEDIA_TYPES = {"photo", "video", "video_note", "voice", "audio", "document", "animation", "sticker"}

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()


async def send_owner(owner_id, text, reply_markup=None, force=False):
    global STYLE_OK
    s = settings_of(owner_id)
    if not force and not s["notify"]:
        return None
    try:
        return await bot.send_message(
            owner_chat(owner_id), text, reply_markup=reply_markup, disable_notification=s["silent"]
        )
    except Exception as e:
        log.error("Отправка владельцу %s не удалась: %s", owner_id, e)
        if reply_markup is not None:
            try:
                STYLE_OK = False
                return await bot.send_message(owner_chat(owner_id), text, reply_markup=plain_kb(reply_markup))
            except Exception as e2:
                log.error("Повторная отправка не удалась: %s", e2)
    return None


async def safe_edit(call: CallbackQuery, text: str, kb: InlineKeyboardMarkup = None):
    global STYLE_OK
    try:
        await call.message.edit_text(text, reply_markup=kb)
        return
    except Exception as e:
        if "message is not modified" in str(e).lower():
            return
        log.error("Ошибка обновления экрана: %s", e)
    if kb is not None:
        try:
            STYLE_OK = False
            await call.message.edit_text(text, reply_markup=plain_kb(kb))
        except Exception as e2:
            log.error("Повторное обновление не удалось: %s", e2)


async def edit_own(conn_id, chat_id, message_id, text) -> bool:
    try:
        await bot.edit_message_text(
            business_connection_id=conn_id, chat_id=chat_id, message_id=message_id, text=text
        )
        return True
    except Exception as e:
        log.error("Не смог отредактировать %s в %s: %s", message_id, chat_id, e)
        return False


async def biz_send(conn_id, chat_id, text):
    try:
        return await bot.send_message(chat_id=chat_id, text=text, business_connection_id=conn_id)
    except Exception as e:
        log.error("Не смог отправить в бизнес-чат %s: %s", chat_id, e)
        return None


async def drop_messages(conn_id, message_ids) -> bool:
    if not message_ids:
        return False
    ok = True
    for i in range(0, len(message_ids), 100):
        try:
            await bot.delete_business_messages(
                business_connection_id=conn_id, message_ids=message_ids[i : i + 100]
            )
        except Exception as e:
            log.error("Ошибка удаления %s: %s", message_ids[i : i + 100], e)
            ok = False
    return ok


def archive_key(chat_id, message_id) -> str:
    return f"{chat_id}:{message_id}"


def describe(message: Message) -> dict:
    ctype = message.content_type if isinstance(message.content_type, str) else str(message.content_type)
    user = message.from_user
    name = " ".join(filter(None, [getattr(user, "first_name", None), getattr(user, "last_name", None)])) if user else "?"
    return {
        "chat_id": message.chat.id,
        "message_id": message.message_id,
        "user_id": user.id if user else 0,
        "name": name or "?",
        "username": user.username if user and user.username else "",
        "type": ctype,
        "text": message.text or message.caption or "",
        "ts": int(time.time()),
    }


def store(message: Message):
    rec = describe(message)
    ARCHIVE[archive_key(rec["chat_id"], rec["message_id"])] = rec
    mark_dirty()
    return rec


def remember_peer(rec) -> bool:
    key = str(rec["chat_id"])
    fresh = key not in STATE["peers"]
    STATE["peers"][key] = {
        "id": rec["chat_id"],
        "name": rec["name"],
        "username": rec["username"],
        "last": rec["ts"],
    }
    mark_dirty()
    return fresh


def stamp(ts) -> str:
    return datetime.fromtimestamp(ts or 0).strftime("%d.%m %H:%M")


def render_record(rec, log_media=True) -> str:
    who = html.escape(rec.get("name") or "?")
    uname = f" @{html.escape(rec['username'])}" if rec.get("username") else ""
    ctype = rec.get("type", "?")
    if ctype in MEDIA_TYPES and not log_media:
        return f"👤 <b>{who}</b>{uname}\n🕓 {stamp(rec.get('ts'))}\n🙈 Медиа скрыто настройками"
    body = html.escape(rec.get("text") or "")
    out = [
        f"👤 <b>{who}</b>{uname} <code>{rec.get('user_id')}</code>",
        f"🕓 {stamp(rec.get('ts'))}",
        f"📎 {CONTENT_NAMES.get(ctype, ctype)}",
    ]
    if body:
        out.append(f"💬 {body}")
    return "\n".join(out)


def push_log(kind, entry):
    arr = STATE["logs"].setdefault(kind, [])
    arr.append(entry)
    if len(arr) > LOG_LIMIT:
        del arr[: len(arr) - LOG_LIMIT]
    mark_dirty()


def paginate(items, page):
    total = max(1, (len(items) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total - 1))
    return items[page * PAGE_SIZE : (page + 1) * PAGE_SIZE], page, total


def nav_row(prefix, page, total):
    if total <= 1:
        return []
    return [
        btn("◀️", f"{prefix}:{max(0, page - 1)}"),
        btn(f"{page + 1}/{total}", "noop"),
        btn("▶️", f"{prefix}:{min(total - 1, page + 1)}"),
    ]


def home_row(extra_back=None):
    row = []
    if extra_back:
        row.append(btn("⬅️ Назад", extra_back))
    row.append(btn("🏠 Домой", "m:home"))
    return row


def main_menu_kb(user_id) -> InlineKeyboardMarkup:
    rows = [
        [btn("📋 Команды", "m:cmds", "primary"), btn("⚙️ Настройки", "m:set", "primary")],
        [btn("📊 Статус", "m:status", "success"), btn("🎮 Игры", "m:games", "success")],
        [btn("🔇 Мьюты", "m:mutes", "primary"), btn("🗑 Логи", "m:logs", "primary")],
        [btn("🧩 Управление командами", "m:cmdmgr", "primary"), btn("📈 Аналитика", "m:ana", "primary")],
    ]
    if user_id == ADMIN_ID:
        rows.append([btn("👑 Админ-панель", "a:home", "danger")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def home_text(user_id) -> str:
    return (
        "🤖 <b>Пульт управления личными чатами</b>\n\n"
        "Я сижу в ваших переписках и делаю грязную работу: глушу болтунов, "
        "ловлю удалёнки и правки, иногда играю в крестики-нолики. 😌\n\n"
        f"⏱ Аптайм: <b>{uptime_text()}</b> · 🔇 В мьюте: <b>{len(muted_of(user_id))}</b>\n"
        "Выбирайте раздел ниже 👇"
    )


def commands_text() -> str:
    out = ["📋 <b>Полный арсенал</b>", "", "<i>Команды работают только от вашего имени в личных чатах.</i>", ""]
    for cat, title in CAT_ORDER:
        out.append(f"<b>{title}</b>")
        for key, display, cat_key, desc in CMD_REGISTRY:
            if cat_key != cat:
                continue
            flag = "" if cmd_enabled(key) else " 🚫"
            out.append(f"<code>{html.escape(display)}</code>{flag} — {html.escape(desc)}")
        out.append("")
    out.append("🚫 = выключена в разделе «🧩 Управление командами»")
    return "\n".join(out)


def settings_page(owner_id):
    s = settings_of(owner_id)
    rows = []
    for key, title in SETTINGS_META:
        on = bool(s.get(key))
        rows.append([btn(f"{'🟢' if on else '🔴'} {title}", f"t:{key}", "success" if on else "danger")])
    rows.append(home_row())
    text = (
        "⚙️ <b>Настройки</b>\n\n"
        "Тапайте, чтобы переключить. Зелёное — работает, красное — спит.\n\n"
        "🗑 <i>удалёнки</i> — сохраняю то, что стёр собеседник\n"
        "✏️ <i>правки</i> — показываю «было → стало»\n"
        "🖼 <i>медиа</i> — писать ли тип медиа в логах\n"
        "🔇 <i>мьют по умолчанию</i> — новые чаты сразу в тишину\n"
        "🤫 <i>тихий режим</i> — уведомления без звука\n"
        "🧹 <i>автоудаление</i> — стираю свою команду после ответа"
    )
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


def status_text(owner_id) -> str:
    info = conn_of(owner_id) or {}
    s = settings_of(owner_id)
    st = STATE["stats"]
    on = bool(info.get("is_enabled"))
    return (
        "📊 <b>Статус</b>\n\n"
        f"Подключение: {'✅ живо и здорово' if on else '❌ отсутствует'}\n"
        f"Право удалять: {'🟢 есть' if info.get('can_delete') else '🔴 нет (мьют будет бессилен)'}\n"
        f"Право читать: {'🟢 есть' if info.get('can_read', True) else '🔴 нет'}\n\n"
        f"🔇 В мьюте чатов: <b>{len(muted_of(owner_id))}</b>\n"
        f"🗑 Удалено ботом: <b>{st.get('deleted_by_bot', 0)}</b>\n"
        f"📥 Залогировано удалёнок: <b>{st.get('logged_deleted', 0)}</b>\n"
        f"✏️ Залогировано правок: <b>{st.get('logged_edited', 0)}</b>\n"
        f"🎮 Партий сыграно: <b>{st.get('games', 0)}</b>\n"
        f"🗂 Сообщений в архиве: <b>{len(ARCHIVE)}</b>\n\n"
        f"Активных настроек: <b>{sum(1 for k, _ in SETTINGS_META if s.get(k))}/{len(SETTINGS_META)}</b>\n"
        f"⏱ Аптайм: <b>{uptime_text()}</b>"
    )


def mutes_page(owner_id, page=0):
    muted = muted_of(owner_id)
    items, page, total = paginate(muted, page)
    rows = []
    for chat_id in items:
        peer = STATE["peers"].get(str(chat_id), {})
        name = peer.get("name") or str(chat_id)
        rows.append([btn(f"🔊 Размутить · {name}"[:60], f"um:{chat_id}", "danger")])
    nav = nav_row("mp", page, total)
    if nav:
        rows.append(nav)
    if muted:
        rows.append([btn("♻️ Размутить всех", "cf:unmuteall", "danger")])
    rows.append(home_row())
    if not muted:
        text = "🔇 <b>Мьюты</b>\n\nПусто. Все живы, все говорят. 🕊"
    else:
        lines = []
        for chat_id in items:
            peer = STATE["peers"].get(str(chat_id), {})
            uname = f" @{peer['username']}" if peer.get("username") else ""
            lines.append(
                f"• <b>{html.escape(peer.get('name') or '—')}</b>{html.escape(uname)} — <code>{chat_id}</code>"
            )
        text = f"🔇 <b>Мьюты</b> · всего {len(muted)}\n\n" + "\n".join(lines)
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


def logs_menu():
    rows = [
        [btn("🗑 Удалёнки", "lg:d:0", "primary"), btn("✏️ Редактирования", "lg:e:0", "primary")],
        home_row(),
    ]
    d = len(STATE["logs"].get("deleted", []))
    e = len(STATE["logs"].get("edited", []))
    text = f"🗑 <b>Логи</b>\n\nУдалёнок в памяти: <b>{d}</b>\nПравок в памяти: <b>{e}</b>\n\nВыбирайте, что смотреть."
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


def logs_page(kind, page, back="m:logs"):
    arr = list(reversed(STATE["logs"].get("deleted" if kind == "d" else "edited", [])))
    items, page, total = paginate(arr, page)
    if not arr:
        text = "📭 <b>Пусто</b>\n\nПока ничего не удаляли и не правили. Или все честные. 😇"
    else:
        blocks = []
        for it in items:
            if kind == "d":
                body = it.get("text") or CONTENT_NAMES.get(it.get("type", ""), "медиа")
                blocks.append(
                    f"🗑 <b>{html.escape(it.get('name', '?'))}</b> · {stamp(it.get('ts'))}\n"
                    f"💬 <code>{it.get('chat_id')}</code>\n{html.escape(body)}"
                )
            else:
                blocks.append(
                    f"✏️ <b>{html.escape(it.get('name', '?'))}</b> · {stamp(it.get('ts'))}\n"
                    f"💬 <code>{it.get('chat_id')}</code>\n"
                    f"Было: {html.escape(it.get('old') or '—')}\n"
                    f"Стало: {html.escape(it.get('new') or '—')}"
                )
        title = "🗑 <b>Удалённые сообщения</b>" if kind == "d" else "✏️ <b>Редактирования</b>"
        text = title + f" · всего {len(arr)}\n\n" + "\n\n".join(blocks)
    rows = []
    nav = nav_row(f"lg:{kind}" if back == "m:logs" else f"al:{kind}", page, total)
    if nav:
        rows.append(nav)
    rows.append([btn("🧹 Очистить логи", "cf:clearlogs", "danger")])
    rows.append(home_row(back))
    return text[:4000], InlineKeyboardMarkup(inline_keyboard=rows)


def cmdmgr_page(page=0, back="m:home"):
    items, page, total = paginate(CMD_REGISTRY, page)
    rows = []
    for key, display, _cat, _desc in items:
        on = cmd_enabled(key)
        rows.append([btn(f"{'🟢' if on else '🔴'} {display}", f"cm:{key}:{page}", "success" if on else "danger")])
    nav = nav_row("cmp", page, total)
    if nav:
        rows.append(nav)
    rows.append(home_row(back))
    off = [d for k, d, _c, _x in CMD_REGISTRY if not cmd_enabled(k)]
    text = (
        "🧩 <b>Управление командами</b>\n\n"
        "Тумблеры отключают команды глобально — удобно, если что-то мешает.\n\n"
        f"Выключено сейчас: <b>{len(off)}</b>"
    )
    if off:
        text += "\n" + ", ".join(f"<code>{html.escape(x)}</code>" for x in off[:15])
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


def bar_line(value, maximum, width=12) -> str:
    if maximum <= 0:
        return "░" * width
    filled = max(0, min(width, round(value / maximum * width)))
    return "█" * filled + "░" * (width - filled)


def analytics_text() -> str:
    days = [(datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(6, -1, -1)]
    rows = [STATE["daily"].get(d, {"del": 0, "edit": 0, "mute": 0}) for d in days]
    out = ["📈 <b>Аналитика за 7 дней</b>", ""]
    for label, field, icon in (("Удаления", "del", "🗑"), ("Правки", "edit", "✏️"), ("Мьюты", "mute", "🔇")):
        values = [r.get(field, 0) for r in rows]
        mx = max(values) if values else 0
        out.append(f"{icon} <b>{label}</b> · всего {sum(values)}")
        for d, v in zip(days, values):
            out.append(f"<code>{d[5:]} {bar_line(v, mx)} {v}</code>")
        out.append("")
    spark = "".join("▁▂▃▅▇"[min(4, r.get("del", 0))] for r in rows)
    out.append(f"Пульс удалений: <code>{spark}</code>")
    return "\n".join(out)


def games_menu():
    st = STATE["stats"]
    text = (
        "🎮 <b>Игровая комната</b>\n\n"
        "Крестики-нолики с кнопками — прямо здесь.\n"
        "В переписке с человеком работает текстовая версия: <code>.tic</code>\n\n"
        f"Сыграно: <b>{st.get('games', 0)}</b> · Победы: <b>{st.get('wins', 0)}</b> · "
        f"Поражения: <b>{st.get('losses', 0)}</b> · Ничьи: <b>{st.get('draws', 0)}</b>"
    )
    rows = [[btn("❌⭕️ Крестики-нолики", "g:new", "success")], home_row()]
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


LINES = [(0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6)]


def winner_of(board):
    for a, b_, c in LINES:
        if board[a] and board[a] == board[b_] == board[c]:
            return board[a]
    if all(board):
        return "D"
    return None


def minimax(board, player, ai, human):
    res = winner_of(board)
    if res == ai:
        return 1, None
    if res == human:
        return -1, None
    if res == "D":
        return 0, None
    best_move = None
    best_score = -2 if player == ai else 2
    for i in range(9):
        if board[i]:
            continue
        board[i] = player
        score, _ = minimax(board, human if player == ai else ai, ai, human)
        board[i] = ""
        if player == ai and score > best_score:
            best_score, best_move = score, i
        if player == human and score < best_score:
            best_score, best_move = score, i
    return best_score, best_move


def ai_move(board, ai, human):
    free = [i for i in range(9) if not board[i]]
    if not free:
        return None
    if random.random() < 0.25:
        return random.choice(free)
    _, move = minimax(list(board), ai, ai, human)
    return move if move is not None else random.choice(free)


CELL = {"": "⬜️", "X": "❌", "O": "⭕️"}
DIGITS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"]


def board_kb(board, over=False):
    rows = []
    for r in range(3):
        row = []
        for c in range(3):
            i = r * 3 + c
            row.append(btn(CELL[board[i]], "noop" if over or board[i] else f"g:c:{i}"))
        rows.append(row)
    rows.append([btn("🔄 Заново", "g:new", "success"), btn("⬅️ Назад", "m:games")])
    rows.append([btn("🏠 Домой", "m:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def board_text(status):
    return "❌⭕️ <b>Крестики-нолики</b>\n\nВы — ❌, я — ⭕️\n\n" + status


def text_board(board) -> str:
    rows = []
    for r in range(3):
        cells = []
        for c in range(3):
            i = r * 3 + c
            cells.append(CELL[board[i]] if board[i] else DIGITS[i])
        rows.append(" ".join(cells))
    return "\n".join(rows)


def tic_render(game, note="") -> str:
    head = "❌⭕️ <b>Крестики-нолики</b>\n\n"
    body = text_board(game["board"])
    if game.get("over"):
        tail = f"\n\n{game.get('result', 'Игра окончена')}"
    else:
        turn = "ваш ход" if game["turn"] == "X" else "ход собеседника"
        tail = f"\n\n❌ владелец · ⭕️ собеседник\n👉 Сейчас: <b>{turn}</b>\nОтправьте цифру 1–9"
    return head + body + tail + (f"\n\n{note}" if note else "")


def get_tic(owner_id, chat_id):
    return STATE["tic"].get(str(owner_id), {}).get(str(chat_id))


def set_tic(owner_id, chat_id, game):
    STATE["tic"].setdefault(str(owner_id), {})[str(chat_id)] = game
    mark_dirty()


def del_tic(owner_id, chat_id):
    STATE["tic"].get(str(owner_id), {}).pop(str(chat_id), None)
    mark_dirty()


async def tic_update(conn_id, owner_id, chat_id, game, note=""):
    text = tic_render(game, note)
    fresh = time.time() - game.get("created", 0) < 47 * 3600
    if fresh and game.get("msg_id"):
        if await edit_own(conn_id, chat_id, game["msg_id"], text):
            return
    msg = await biz_send(conn_id, chat_id, text)
    if msg:
        game["msg_id"] = msg.message_id
        game["created"] = time.time()
        set_tic(owner_id, chat_id, game)


async def tic_move(conn_id, owner_id, chat_id, game, index, symbol) -> bool:
    if game.get("over") or game["turn"] != symbol:
        return False
    if index < 0 or index > 8 or game["board"][index]:
        await tic_update(conn_id, owner_id, chat_id, game, "⚠️ Клетка занята или её не существует")
        return True
    game["board"][index] = symbol
    res = winner_of(game["board"])
    if res == "X":
        game["over"], game["result"] = True, "🏆 Победа владельца! ❌"
        bump("wins")
    elif res == "O":
        game["over"], game["result"] = True, "🏆 Победил собеседник! ⭕️"
        bump("losses")
    elif res == "D":
        game["over"], game["result"] = True, "🤝 Ничья — оба хороши"
        bump("draws")
    else:
        game["turn"] = "O" if symbol == "X" else "X"
    if game.get("over"):
        bump("games")
    set_tic(owner_id, chat_id, game)
    await tic_update(conn_id, owner_id, chat_id, game)
    if game.get("over"):
        del_tic(owner_id, chat_id)
    return True


async def typing_loop(conn_id, chat_id):
    try:
        while True:
            try:
                await bot.send_chat_action(chat_id=chat_id, action="typing", business_connection_id=conn_id)
            except Exception as e:
                log.error("chat_action: %s", e)
                return
            await asyncio.sleep(4)
    except asyncio.CancelledError:
        return


def stop_typing(owner_id, chat_id):
    task = TYPING_TASKS.pop((owner_id, chat_id), None)
    if task and not task.done():
        task.cancel()


async def autodelete(conn_id, chat_id, message_id):
    await asyncio.sleep(3)
    await drop_messages(conn_id, [message_id])


@dp.business_connection()
async def on_business_connection(connection: BusinessConnection):
    owner_id = connection.user.id
    rights = getattr(connection, "rights", None)
    can_delete = bool(getattr(rights, "can_delete_all_messages", False)) if rights else False
    can_read = bool(getattr(rights, "can_read_messages", True)) if rights else True
    name = " ".join(filter(None, [connection.user.first_name, connection.user.last_name])) or "владелец"

    STATE["connections"][str(owner_id)] = {
        "connection_id": connection.id,
        "user_chat_id": getattr(connection, "user_chat_id", None) or owner_id,
        "is_enabled": bool(connection.is_enabled),
        "can_delete": can_delete,
        "can_read": can_read,
        "name": name,
        "username": connection.user.username or "",
        "since": int(time.time()),
    }
    STATE["conn_index"][connection.id] = owner_id
    settings_of(owner_id)
    muted_of(owner_id)
    mark_dirty()
    save_data()

    if connection.is_enabled:
        log.info("Подключение включено: owner=%s", owner_id)
        await send_owner(
            owner_id,
            f"✅ <b>Бот на связи, {html.escape(name)}!</b>\n\n"
            "Теперь я живу в ваших личных чатах и всё вижу. 👀\n"
            f"ID подключения: <code>{html.escape(connection.id)}</code>\n"
            f"Ваш ID: <code>{owner_id}</code>\n\n"
            "Напишите <code>.cmds</code> в любой переписке — покажу арсенал.",
            reply_markup=main_menu_kb(owner_id),
            force=True,
        )
        if not can_read:
            await send_owner(owner_id, "⚠️ Нет права <b>«Читать сообщения»</b> — я слеп и бесполезен.", force=True)
        if not can_delete:
            await send_owner(
                owner_id,
                "⚠️ <b>Нет права «Удалять сообщения»</b>\n\n"
                "Без него <code>.mute</code> будет только грозно смотреть. "
                "Настройки → Telegram для бизнеса → Чат-боты → включите <b>«Удалять сообщения»</b>.",
                force=True,
            )
    else:
        log.info("Подключение отключено: owner=%s", owner_id)
        await send_owner(owner_id, "🔌 <b>Меня отключили.</b>\n\nБыло приятно поработать. Возвращайтесь. 👋", force=True)


async def resolve_owner(conn_id):
    owner_id = owner_by_conn(conn_id)
    if owner_id is not None:
        return owner_id
    try:
        connection = await bot.get_business_connection(conn_id)
    except Exception as e:
        log.error("get_business_connection %s: %s", conn_id, e)
        return None
    rights = getattr(connection, "rights", None)
    owner_id = connection.user.id
    STATE["connections"][str(owner_id)] = {
        "connection_id": connection.id,
        "user_chat_id": getattr(connection, "user_chat_id", None) or owner_id,
        "is_enabled": bool(connection.is_enabled),
        "can_delete": bool(getattr(rights, "can_delete_all_messages", False)) if rights else False,
        "can_read": bool(getattr(rights, "can_read_messages", True)) if rights else True,
        "name": connection.user.first_name or "владелец",
        "username": connection.user.username or "",
        "since": int(time.time()),
    }
    STATE["conn_index"][connection.id] = owner_id
    mark_dirty()
    return owner_id


async def handle_command(message: Message, owner_id, conn_id) -> bool:
    raw = (message.text or "").strip()
    if not raw.startswith(".") or len(raw) < 2:
        return False
    parts = raw.split(maxsplit=1)
    key = parts[0][1:].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""
    chat_id = message.chat.id
    mid = message.message_id
    muted = muted_of(owner_id)
    s = settings_of(owner_id)

    known = {c[0] for c in CMD_REGISTRY} | {"help"}
    if key not in known:
        return False
    if not cmd_enabled("cmds" if key == "help" else key):
        await edit_own(conn_id, chat_id, mid, "🚫 Эта команда выключена в настройках бота")
        return True

    bump("commands_used")
    result = None

    if key == "mute":
        if chat_id not in muted:
            muted.append(chat_id)
            bump_daily("mute")
            mark_dirty()
        result = "Замолчи"
        if not (conn_of(owner_id) or {}).get("can_delete"):
            await send_owner(owner_id, "⚠️ Мьют включён, но права на удаление нет — сообщения останутся.")
    elif key == "unmute":
        if chat_id in muted:
            muted.remove(chat_id)
            mark_dirty()
        result = "Размьючен"
    elif key == "mutelist":
        if not muted:
            result = "🔇 Список молчунов пуст"
        else:
            result = f"🔇 Замьючено чатов: {len(muted)}\n" + "\n".join(f"• {c}" for c in muted[:20])
    elif key == "del":
        target = message.reply_to_message
        if not target:
            result = "⚠️ Нужно ответить на сообщение"
        else:
            ok = await drop_messages(conn_id, [target.message_id])
            if ok:
                bump("deleted_by_bot")
            result = "🗑 Удалено" if ok else "⚠️ Не вышло — проверьте право «Удалять сообщения»"
    elif key == "clear":
        try:
            count = max(1, min(100, int(arg)))
        except Exception:
            count = 10
        mine = [
            rec
            for rec in ARCHIVE.values()
            if rec.get("chat_id") == chat_id and rec.get("user_id") == owner_id and rec.get("message_id") != mid
        ]
        mine.sort(key=lambda r: r.get("message_id", 0), reverse=True)
        ids = [r["message_id"] for r in mine[:count]]
        ok = await drop_messages(conn_id, ids)
        if ok:
            bump("deleted_by_bot", len(ids))
        result = f"🧹 Подчистил {len(ids)} сообщ." if ok else "⚠️ Не получилось удалить"
    elif key == "afk":
        if not arg:
            result = "⚠️ Пример: .afk отошёл на час"
        else:
            STATE["afk"][str(owner_id)] = {"text": arg, "replied": []}
            mark_dirty()
            result = f"😴 АФК включён: «{arg}»"
    elif key == "afkoff":
        STATE["afk"].pop(str(owner_id), None)
        mark_dirty()
        result = "🙂 АФК выключен, я снова в строю"
    elif key == "ky":
        result = "привет"
    elif key == "rev":
        result = (arg or "нечего переворачивать")[::-1]
    elif key == "spoiler":
        result = f"<tg-spoiler>{html.escape(arg or 'сюрприз')}</tg-spoiler>"
    elif key == "b":
        result = f"<b>{html.escape(arg or 'жирно')}</b>"
    elif key == "i":
        result = f"<i>{html.escape(arg or 'курсивно')}</i>"
    elif key == "quote":
        result = f"<blockquote>{html.escape(arg or 'цитата')}</blockquote>"
    elif key == "up":
        result = (arg or "капс").upper()
    elif key == "mock":
        src = arg or "сарказм"
        result = "".join(ch.upper() if i % 2 else ch.lower() for i, ch in enumerate(src))
    elif key == "roll":
        result = f"🎲 Выпало: {random.randint(1, 100)}"
    elif key == "coin":
        result = random.choice(["🪙 Орёл", "🪙 Решка"])
    elif key == "id":
        result = (
            f"🆔 Чат: <code>{chat_id}</code>\n"
            f"👑 Владелец: <code>{owner_id}</code>\n"
            f"🔗 Связь: <code>{html.escape(conn_id)}</code>"
        )
    elif key == "info":
        peer = message.chat
        name = " ".join(filter(None, [peer.first_name, peer.last_name])) or "—"
        uname = f"@{peer.username}" if peer.username else "—"
        result = (
            "ℹ️ <b>Досье</b>\n"
            f"Имя: {html.escape(name)}\n"
            f"Username: {html.escape(uname)}\n"
            f"ID: <code>{peer.id}</code>\n"
            f"Мьют: {'🔇 да' if chat_id in muted else '🔊 нет'}"
        )
    elif key == "ping":
        sent = message.date.replace(tzinfo=timezone.utc).timestamp() if message.date else time.time()
        result = f"🏓 pong — {max(0.0, time.time() - sent):.2f} c"
    elif key == "time":
        result = f"🕓 {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
    elif key == "calc":
        if not arg:
            result = "⚠️ Пример: .calc 2+2*10"
        else:
            try:
                result = f"🧮 {html.escape(arg)} = <b>{safe_calc(arg)}</b>"
            except Exception:
                result = "⚠️ Это не считается"
    elif key == "type":
        stop_typing(owner_id, chat_id)
        TYPING_TASKS[(owner_id, chat_id)] = asyncio.create_task(typing_loop(conn_id, chat_id))
        result = "⌨️ Печатаю… (до вашего следующего сообщения)"
    elif key == "stats":
        st = STATE["stats"]
        result = (
            "📊 <b>Статистика</b>\n"
            f"🔇 В мьюте: {len(muted)}\n"
            f"🗑 Удалено ботом: {st.get('deleted_by_bot', 0)}\n"
            f"📥 Удалёнок в логах: {st.get('logged_deleted', 0)}\n"
            f"✏️ Правок в логах: {st.get('logged_edited', 0)}\n"
            f"🎮 Игр: {st.get('games', 0)}\n"
            f"⏱ Аптайм: {uptime_text()}"
        )
    elif key == "tic":
        game = {"board": [""] * 9, "turn": "X", "over": False, "msg_id": None, "created": time.time()}
        set_tic(owner_id, chat_id, game)
        await edit_own(conn_id, chat_id, mid, "🎮 Партия началась!")
        await tic_update(conn_id, owner_id, chat_id, game)
        return True
    elif key == "ticstop":
        if get_tic(owner_id, chat_id):
            del_tic(owner_id, chat_id)
            result = "🏁 Партия завершена"
        else:
            result = "🤷 Активной партии нет"
    elif key in ("cmds", "help"):
        result = commands_text()

    if result is None:
        return False
    await edit_own(conn_id, chat_id, mid, result)
    if s["autodelete_cmd"] and key not in ("cmds", "help"):
        asyncio.create_task(autodelete(conn_id, chat_id, mid))
    return True


@dp.business_message()
async def on_business_message(message: Message):
    conn_id = message.business_connection_id
    if not conn_id or getattr(message, "sender_business_bot", None):
        return
    owner_id = await resolve_owner(conn_id)
    if owner_id is None:
        return

    rec = store(message)
    chat_id = message.chat.id
    sender_id = message.from_user.id if message.from_user else 0
    s = settings_of(owner_id)

    if sender_id == owner_id:
        stop_typing(owner_id, chat_id)
        try:
            if await handle_command(message, owner_id, conn_id):
                return
        except Exception as e:
            log.exception("Ошибка команды: %s", e)
            return
        game = get_tic(owner_id, chat_id)
        if game and (message.text or "").strip().isdigit():
            try:
                await tic_move(conn_id, owner_id, chat_id, game, int(message.text.strip()) - 1, "X")
            except Exception as e:
                log.error("tic owner move: %s", e)
        return

    fresh = remember_peer(rec)
    muted = muted_of(owner_id)
    if fresh and s["mute_default"] and chat_id not in muted:
        muted.append(chat_id)
        bump_daily("mute")
        mark_dirty()
        await send_owner(owner_id, f"🔇 Новый чат <code>{chat_id}</code> сразу отправлен в мьют (так настроено).")

    if chat_id in muted:
        if await drop_messages(conn_id, [message.message_id]):
            bump("deleted_by_bot")
            log.info("Удалено сообщение %s в чате %s", message.message_id, chat_id)
        return

    game = get_tic(owner_id, chat_id)
    if game and (message.text or "").strip().isdigit():
        try:
            if await tic_move(conn_id, owner_id, chat_id, game, int(message.text.strip()) - 1, "O"):
                return
        except Exception as e:
            log.error("tic peer move: %s", e)

    afk = STATE["afk"].get(str(owner_id))
    if afk and chat_id not in afk.get("replied", []):
        await biz_send(conn_id, chat_id, f"😴 {afk['text']}")
        afk.setdefault("replied", []).append(chat_id)
        mark_dirty()


@dp.edited_business_message()
async def on_edited_business_message(message: Message):
    conn_id = message.business_connection_id
    if not conn_id:
        return
    owner_id = await resolve_owner(conn_id)
    if owner_id is None:
        return
    key = archive_key(message.chat.id, message.message_id)
    old = ARCHIVE.get(key) or {}
    old_text = old.get("text", "")
    new_text = message.text or message.caption or ""
    store(message)

    if not settings_of(owner_id)["save_edited"]:
        return
    if (message.from_user and message.from_user.id == owner_id) or old_text == new_text:
        return

    name = old.get("name") or (message.from_user.first_name if message.from_user else "?")
    push_log(
        "edited",
        {"chat_id": message.chat.id, "name": name, "old": old_text, "new": new_text, "ts": int(time.time())},
    )
    bump("logged_edited")
    bump_daily("edit")
    await send_owner(
        owner_id,
        "✏️ <b>Кто-то передумал</b>\n\n"
        f"👤 {html.escape(name)} <code>{message.from_user.id if message.from_user else '?'}</code>\n"
        f"💬 Чат: <code>{message.chat.id}</code>\n\n"
        f"<b>Было:</b>\n{html.escape(old_text) if old_text else '<i>нет данных</i>'}\n\n"
        f"<b>Стало:</b>\n{html.escape(new_text) if new_text else '<i>пусто</i>'}",
    )


@dp.deleted_business_messages()
async def on_deleted_business_messages(event: BusinessMessagesDeleted):
    owner_id = await resolve_owner(event.business_connection_id)
    if owner_id is None:
        return
    s = settings_of(owner_id)
    if not s["save_deleted"]:
        return
    chat_id = event.chat.id
    if chat_id in muted_of(owner_id):
        return

    blocks = []
    for mid in event.message_ids:
        rec = ARCHIVE.get(archive_key(chat_id, mid))
        if not rec:
            blocks.append(f"❔ Сообщение <code>{mid}</code> — содержимое не сохранилось")
            continue
        if rec.get("user_id") == owner_id:
            continue
        blocks.append(render_record(rec, s["log_media"]))
        push_log("deleted", rec)
        bump("logged_deleted")
        bump_daily("del")
    if not blocks:
        return
    text = f"🗑 <b>Замели следы</b>\n💬 Чат: <code>{chat_id}</code>\n\n" + "\n\n".join(blocks)
    for i in range(0, len(text), 3800):
        await send_owner(owner_id, text[i : i + 3800])


@dp.message(CommandStart())
async def on_start(message: Message):
    settings_of(message.from_user.id)
    await message.answer(home_text(message.from_user.id), reply_markup=main_menu_kb(message.from_user.id))


@dp.message(Command("menu"))
async def on_menu_cmd(message: Message):
    await message.answer(home_text(message.from_user.id), reply_markup=main_menu_kb(message.from_user.id))


@dp.message(Command("admin"))
async def on_admin_cmd(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔️ Доступ только для администратора бота.")
        return
    text, kb = admin_home()
    await message.answer(text, reply_markup=kb)


@dp.callback_query(F.data == "noop")
async def on_noop(call: CallbackQuery):
    await call.answer()


@dp.callback_query(F.data.startswith("m:"))
async def on_menu(call: CallbackQuery):
    uid = call.from_user.id
    section = call.data.split(":", 1)[1]
    try:
        if section == "cmds":
            await safe_edit(call, commands_text(), InlineKeyboardMarkup(inline_keyboard=[home_row()]))
        elif section == "set":
            text, kb = settings_page(uid)
            await safe_edit(call, text, kb)
        elif section == "status":
            await safe_edit(call, status_text(uid), InlineKeyboardMarkup(inline_keyboard=[home_row()]))
        elif section == "games":
            text, kb = games_menu()
            await safe_edit(call, text, kb)
        elif section == "mutes":
            text, kb = mutes_page(uid, 0)
            await safe_edit(call, text, kb)
        elif section == "logs":
            text, kb = logs_menu()
            await safe_edit(call, text, kb)
        elif section == "cmdmgr":
            text, kb = cmdmgr_page(0)
            await safe_edit(call, text, kb)
        elif section == "ana":
            await safe_edit(call, analytics_text(), InlineKeyboardMarkup(inline_keyboard=[home_row()]))
        else:
            await safe_edit(call, home_text(uid), main_menu_kb(uid))
    except Exception as e:
        log.exception("menu: %s", e)
    await call.answer()


@dp.callback_query(F.data.startswith("mp:"))
async def on_mutes_page(call: CallbackQuery):
    try:
        text, kb = mutes_page(call.from_user.id, int(call.data.split(":")[1]))
        await safe_edit(call, text, kb)
    except Exception as e:
        log.error("mp: %s", e)
    await call.answer()


@dp.callback_query(F.data.startswith("t:"))
async def on_toggle(call: CallbackQuery):
    key = call.data.split(":", 1)[1]
    s = settings_of(call.from_user.id)
    if key in s:
        s[key] = not s[key]
        mark_dirty()
        save_data()
    text, kb = settings_page(call.from_user.id)
    await safe_edit(call, text, kb)
    await call.answer("🟢 Включено" if s.get(key) else "🔴 Выключено")


@dp.callback_query(F.data.startswith("um:"))
async def on_unmute(call: CallbackQuery):
    try:
        chat_id = int(call.data.split(":")[1])
    except Exception:
        await call.answer()
        return
    for owner, chats in STATE["muted"].items():
        if chat_id in chats and (call.from_user.id == ADMIN_ID or owner == str(call.from_user.id)):
            chats.remove(chat_id)
            mark_dirty()
    save_data()
    if call.from_user.id == ADMIN_ID and "Все мьюты" in (call.message.html_text or call.message.text or ""):
        text, kb = admin_mutes(0)
    else:
        text, kb = mutes_page(call.from_user.id, 0)
    await safe_edit(call, text, kb)
    await call.answer("🔊 Размучен")


@dp.callback_query(F.data.startswith("cmp:"))
async def on_cmd_page(call: CallbackQuery):
    text, kb = cmdmgr_page(int(call.data.split(":")[1]))
    await safe_edit(call, text, kb)
    await call.answer()


@dp.callback_query(F.data.startswith("cm:"))
async def on_cmd_toggle(call: CallbackQuery):
    parts = call.data.split(":")
    key = parts[1]
    page = int(parts[2]) if len(parts) > 2 else 0
    STATE["commands"][key] = not cmd_enabled(key)
    mark_dirty()
    save_data()
    back = "a:home" if call.from_user.id == ADMIN_ID and "👑" in (call.message.text or "") else "m:home"
    text, kb = cmdmgr_page(page, back=back)
    await safe_edit(call, text, kb)
    await call.answer("🟢 Включена" if cmd_enabled(key) else "🔴 Выключена")


@dp.callback_query(F.data.startswith("lg:"))
async def on_logs(call: CallbackQuery):
    parts = call.data.split(":")
    page = int(parts[2]) if len(parts) > 2 else 0
    text, kb = logs_page(parts[1], page)
    await safe_edit(call, text, kb)
    await call.answer()


@dp.callback_query(F.data.startswith("g:"))
async def on_game(call: CallbackQuery):
    uid = str(call.from_user.id)
    parts = call.data.split(":")
    games = STATE["board_games"]
    if parts[1] == "new":
        games[uid] = {"board": [""] * 9, "over": False}
        mark_dirty()
        await safe_edit(call, board_text("Ваш ход! 👇"), board_kb(games[uid]["board"]))
        await call.answer("Погнали!")
        return
    game = games.get(uid)
    if not game or game.get("over"):
        await call.answer("Начните новую партию", show_alert=True)
        return
    index = int(parts[2])
    board = game["board"]
    if board[index]:
        await call.answer("Занято!", show_alert=True)
        return
    board[index] = "X"
    status = "Ваш ход! 👇"
    res = winner_of(board)
    if not res:
        move = ai_move(board, "O", "X")
        if move is not None:
            board[move] = "O"
        res = winner_of(board)
    if res == "X":
        game["over"], status = True, "🏆 <b>Вы победили!</b> Я в шоке."
        bump("wins")
        bump("games")
    elif res == "O":
        game["over"], status = True, "😈 <b>Я выиграл.</b> Реванш?"
        bump("losses")
        bump("games")
    elif res == "D":
        game["over"], status = True, "🤝 <b>Ничья.</b> Достойно."
        bump("draws")
        bump("games")
    mark_dirty()
    await safe_edit(call, board_text(status), board_kb(board, game.get("over", False)))
    await call.answer()


def admin_guard(call: CallbackQuery) -> bool:
    return call.from_user.id == ADMIN_ID


def admin_home():
    st = STATE["stats"]
    text = (
        "👑 <b>Админ-панель</b>\n\n"
        f"Бот v{BOT_VERSION} · aiogram {aiogram.__version__}\n"
        f"⏱ Аптайм: <b>{uptime_text()}</b>\n"
        f"🔗 Подключений: <b>{len(STATE['connections'])}</b> · "
        f"🔇 Мьютов: <b>{sum(len(v) for v in STATE['muted'].values())}</b>\n"
        f"🗑 Логи: <b>{len(STATE['logs'].get('deleted', []))}</b> удалёнок / "
        f"<b>{len(STATE['logs'].get('edited', []))}</b> правок\n"
        f"🎮 Игр сыграно: <b>{st.get('games', 0)}</b>\n\n"
        "Выбирайте раздел 👇"
    )
    rows = [
        [btn("📊 Дашборд", "a:dash", "primary"), btn("🔗 Подключения", "a:conns", "primary")],
        [btn("🔇 Все мьюты", "a:mutes", "primary"), btn("🗑 Логи", "a:logs", "primary")],
        [btn("🧩 Команды", "a:cmds", "primary"), btn("⚙️ Глоб. настройки", "a:gset", "primary")],
        [btn("🎮 Статистика игр", "a:games", "success"), btn("👥 Собеседники", "a:peers", "success")],
        [btn("📈 Аналитика", "a:ana", "primary"), btn("ℹ️ Система", "a:sys", "primary")],
        [btn("📢 Быстрые действия", "a:quick", "danger")],
        home_row(),
    ]
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


def admin_dash():
    st = STATE["stats"]
    active = sum(1 for c in STATE["connections"].values() if c.get("is_enabled"))
    text = (
        "📊 <b>Дашборд</b>\n\n"
        f"⏱ Аптайм: <b>{uptime_text()}</b>\n"
        f"🔗 Активных подключений: <b>{active}</b> из {len(STATE['connections'])}\n"
        f"🔇 Замучено чатов: <b>{sum(len(v) for v in STATE['muted'].values())}</b>\n"
        f"🗑 Удалено ботом: <b>{st.get('deleted_by_bot', 0)}</b>\n"
        f"📥 Залогировано удалёнок: <b>{st.get('logged_deleted', 0)}</b>\n"
        f"✏️ Залогировано правок: <b>{st.get('logged_edited', 0)}</b>\n"
        f"🎮 Партий: <b>{st.get('games', 0)}</b>\n"
        f"⌨️ Команд выполнено: <b>{st.get('commands_used', 0)}</b>\n"
        f"👥 Известных собеседников: <b>{len(STATE['peers'])}</b>\n"
        f"🗂 Архив: <b>{len(ARCHIVE)}</b>"
    )
    return text, InlineKeyboardMarkup(inline_keyboard=[[btn("🔄 Обновить", "a:dash", "success")], home_row("a:home")])


def admin_conns():
    if not STATE["connections"]:
        text = "🔗 <b>Подключения</b>\n\nПусто — никто ещё не подключился."
    else:
        lines = []
        for owner, c in list(STATE["connections"].items())[:20]:
            uname = f" @{c['username']}" if c.get("username") else ""
            lines.append(
                f"{'🟢' if c.get('is_enabled') else '🔴'} <b>{html.escape(c.get('name', '?'))}</b>{html.escape(uname)}\n"
                f"   id: <code>{owner}</code>\n"
                f"   удаление: {'🟢 да' if c.get('can_delete') else '🔴 нет'} · "
                f"чтение: {'🟢' if c.get('can_read', True) else '🔴'}\n"
                f"   с: {stamp(c.get('since'))}"
            )
        text = "🔗 <b>Подключения</b>\n\n" + "\n\n".join(lines)
    return text, InlineKeyboardMarkup(inline_keyboard=[[btn("🔄 Обновить", "a:conns", "success")], home_row("a:home")])


def admin_mutes(page=0):
    flat = []
    for owner, chats in STATE["muted"].items():
        for c in chats:
            flat.append((owner, c))
    items, page, total = paginate(flat, page)
    rows = []
    for owner, chat_id in items:
        peer = STATE["peers"].get(str(chat_id), {})
        label = peer.get("name") or str(chat_id)
        rows.append([btn(f"🔊 {label} ({chat_id})"[:60], f"um:{chat_id}", "danger")])
    nav = nav_row("amp", page, total)
    if nav:
        rows.append(nav)
    if flat:
        rows.append([btn("♻️ Размутить все", "cf:unmuteall", "danger")])
    rows.append(home_row("a:home"))
    if not flat:
        text = "🔇 <b>Все мьюты</b>\n\nПусто."
    else:
        lines = [
            f"• владелец <code>{o}</code> → чат <code>{c}</code> "
            f"({html.escape(STATE['peers'].get(str(c), {}).get('name') or '—')})"
            for o, c in items
        ]
        text = f"🔇 <b>Все мьюты</b> · всего {len(flat)}\n\n" + "\n".join(lines)
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


def admin_logs_menu():
    rows = [
        [btn("🗑 Удалёнки", "al:d:0", "primary"), btn("✏️ Редактирования", "al:e:0", "primary")],
        [btn("🧹 Очистить логи", "cf:clearlogs", "danger")],
        home_row("a:home"),
    ]
    text = (
        "🗑 <b>Логи</b>\n\n"
        f"Удалёнок: <b>{len(STATE['logs'].get('deleted', []))}</b>\n"
        f"Правок: <b>{len(STATE['logs'].get('edited', []))}</b>"
    )
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


def admin_gset():
    g = STATE["global_settings"]
    rows = []
    for key, title in SETTINGS_META:
        on = bool(g.get(key))
        rows.append([btn(f"{'🟢' if on else '🔴'} {title}", f"gs:{key}", "success" if on else "danger")])
    rows.append(home_row("a:home"))
    text = (
        "⚙️ <b>Глобальные настройки</b>\n\n"
        "Это дефолты бота: применяются ко всем новым владельцам.\n"
        "Уже настроенные пользователи сохраняют свои значения."
    )
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


def admin_games():
    st = STATE["stats"]
    w, l, d = st.get("wins", 0), st.get("losses", 0), st.get("draws", 0)
    mx = max(w, l, d, 1)
    text = (
        "🎮 <b>Статистика игр</b>\n\n"
        f"Всего партий: <b>{st.get('games', 0)}</b>\n\n"
        f"<code>Победы  {bar_line(w, mx)} {w}</code>\n"
        f"<code>Пораж.  {bar_line(l, mx)} {l}</code>\n"
        f"<code>Ничьи   {bar_line(d, mx)} {d}</code>\n\n"
        f"Активных текстовых партий: <b>{sum(len(v) for v in STATE['tic'].values())}</b>"
    )
    return text, InlineKeyboardMarkup(inline_keyboard=[[btn("🔄 Обновить", "a:games", "success")], home_row("a:home")])


def admin_peers(page=0):
    peers = sorted(STATE["peers"].values(), key=lambda p: p.get("last", 0), reverse=True)
    items, page, total = paginate(peers, page)
    if not peers:
        text = "👥 <b>Собеседники</b>\n\nПока никого."
    else:
        lines = [
            f"• <b>{html.escape(p.get('name') or '—')}</b>"
            f"{' @' + html.escape(p['username']) if p.get('username') else ''} — "
            f"<code>{p.get('id')}</code> · {stamp(p.get('last'))}"
            for p in items
        ]
        text = f"👥 <b>Собеседники</b> · всего {len(peers)}\n\n" + "\n".join(lines)
    rows = []
    nav = nav_row("ap", page, total)
    if nav:
        rows.append(nav)
    rows.append(home_row("a:home"))
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


def admin_quick():
    rows = [
        [btn("🔔 Тест-уведомление", "do:testnotify", "primary")],
        [btn("💾 Сохранить состояние", "do:save", "primary")],
        [btn("♻️ Сбросить все мьюты", "cf:unmuteall", "danger")],
        [btn("🧹 Очистить все логи", "cf:clearlogs", "danger")],
        [btn("🗂 Очистить архив", "cf:cleararch", "danger")],
        home_row("a:home"),
    ]
    text = "📢 <b>Быстрые действия</b>\n\nСиние — безопасные, красные — с подтверждением."
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


def admin_sys():
    text = (
        "ℹ️ <b>Система</b>\n\n"
        f"🤖 Версия бота: <b>{BOT_VERSION}</b>\n"
        f"📦 aiogram: <b>{aiogram.__version__}</b>\n"
        f"🎨 Цветные кнопки: <b>{'нативные' if STYLE_OK else 'эмуляция эмодзи'}</b>\n"
        f"⏱ Аптайм: <b>{uptime_text()}</b>\n"
        f"🧠 Память: <b>{memory_text()}</b>\n"
        f"💾 Состояние: <code>{html.escape(os.path.abspath(STATE_FILE))}</code>\n"
        f"🗂 Архив: <code>{html.escape(os.path.abspath(ARCHIVE_FILE))}</code>\n"
        f"👑 Админ: <code>{ADMIN_ID}</code>"
    )
    return text, InlineKeyboardMarkup(inline_keyboard=[[btn("🔄 Обновить", "a:sys", "success")], home_row("a:home")])


CONFIRMS = {
    "unmuteall": "♻️ Сбросить <b>все</b> мьюты?",
    "clearlogs": "🧹 Стереть <b>все</b> логи удалёнок и правок?",
    "cleararch": "🗂 Очистить архив сохранённых сообщений?",
}


@dp.callback_query(F.data.startswith("a:"))
async def on_admin(call: CallbackQuery):
    if not admin_guard(call):
        await call.answer("⛔️ Только для администратора", show_alert=True)
        return
    section = call.data.split(":", 1)[1]
    try:
        if section == "dash":
            text, kb = admin_dash()
        elif section == "conns":
            text, kb = admin_conns()
        elif section == "mutes":
            text, kb = admin_mutes(0)
        elif section == "logs":
            text, kb = admin_logs_menu()
        elif section == "cmds":
            text, kb = cmdmgr_page(0, back="a:home")
        elif section == "gset":
            text, kb = admin_gset()
        elif section == "games":
            text, kb = admin_games()
        elif section == "peers":
            text, kb = admin_peers(0)
        elif section == "ana":
            text, kb = analytics_text(), InlineKeyboardMarkup(inline_keyboard=[home_row("a:home")])
        elif section == "quick":
            text, kb = admin_quick()
        elif section == "sys":
            text, kb = admin_sys()
        else:
            text, kb = admin_home()
        await safe_edit(call, text, kb)
    except Exception as e:
        log.exception("admin: %s", e)
    await call.answer()


@dp.callback_query(F.data.startswith("al:"))
async def on_admin_logs(call: CallbackQuery):
    if not admin_guard(call):
        await call.answer("⛔️", show_alert=True)
        return
    parts = call.data.split(":")
    text, kb = logs_page(parts[1], int(parts[2]) if len(parts) > 2 else 0, back="a:logs")
    await safe_edit(call, text, kb)
    await call.answer()


@dp.callback_query(F.data.startswith("amp:"))
async def on_admin_mutes_page(call: CallbackQuery):
    if not admin_guard(call):
        await call.answer("⛔️", show_alert=True)
        return
    text, kb = admin_mutes(int(call.data.split(":")[1]))
    await safe_edit(call, text, kb)
    await call.answer()


@dp.callback_query(F.data.startswith("ap:"))
async def on_admin_peers_page(call: CallbackQuery):
    if not admin_guard(call):
        await call.answer("⛔️", show_alert=True)
        return
    text, kb = admin_peers(int(call.data.split(":")[1]))
    await safe_edit(call, text, kb)
    await call.answer()


@dp.callback_query(F.data.startswith("gs:"))
async def on_global_toggle(call: CallbackQuery):
    if not admin_guard(call):
        await call.answer("⛔️", show_alert=True)
        return
    key = call.data.split(":", 1)[1]
    if key in STATE["global_settings"]:
        STATE["global_settings"][key] = not STATE["global_settings"][key]
        mark_dirty()
        save_data()
    text, kb = admin_gset()
    await safe_edit(call, text, kb)
    await call.answer("🟢 Включено" if STATE["global_settings"].get(key) else "🔴 Выключено")


@dp.callback_query(F.data.startswith("cf:"))
async def on_confirm(call: CallbackQuery):
    action = call.data.split(":", 1)[1]
    if action != "unmuteall" and not admin_guard(call):
        await call.answer("⛔️", show_alert=True)
        return
    question = CONFIRMS.get(action, "Действие необратимо.")
    cancel = "a:home" if call.from_user.id == ADMIN_ID else "m:home"
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[btn("✅ Да", f"do:{action}", "success"), btn("❌ Нет", cancel, "danger")]]
    )
    await safe_edit(call, f"⚠️ <b>Уверены?</b>\n\n{question}\n\n<i>Отменить будет нельзя.</i>", kb)
    await call.answer()


@dp.callback_query(F.data.startswith("do:"))
async def on_do(call: CallbackQuery):
    action = call.data.split(":", 1)[1]
    admin = admin_guard(call)
    try:
        if action == "unmuteall":
            if admin:
                STATE["muted"] = {}
            else:
                STATE["muted"][str(call.from_user.id)] = []
            mark_dirty()
            save_data()
            await call.answer("♻️ Мьюты сброшены")
        elif action == "clearlogs" and admin:
            STATE["logs"] = {"deleted": [], "edited": []}
            mark_dirty()
            save_data()
            await call.answer("🧹 Логи очищены")
        elif action == "cleararch" and admin:
            ARCHIVE.clear()
            mark_dirty()
            save_data()
            await call.answer("🗂 Архив очищен")
        elif action == "save" and admin:
            save_data()
            await call.answer("💾 Сохранено")
        elif action == "testnotify" and admin:
            await bot.send_message(call.from_user.id, "🔔 Тест-уведомление. Всё работает, можно выдохнуть. 😌")
            await call.answer("Отправлено")
        else:
            await call.answer("⛔️", show_alert=True)
            return
    except Exception as e:
        log.exception("do:%s: %s", action, e)
        await call.answer("Ошибка")
    if admin:
        text, kb = admin_home()
    else:
        text, kb = home_text(call.from_user.id), main_menu_kb(call.from_user.id)
    await safe_edit(call, text, kb)


async def main():
    if not BOT_TOKEN:
        raise SystemExit("Вставьте BOT_TOKEN в первую строку bot.py")
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
    log.info("aiogram %s | нативные цветные кнопки: %s", aiogram.__version__, STYLE_OK)
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
