BOT_TOKEN = "8893361270:AAF8kJgzBX_2P5BKwHtWl18slL-FNObQgUw"

SUPER_ADMIN_ID = 2022155738
BOT_VERSION = "4.0"

import ast
import asyncio
import hashlib
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
MEDIA_LIMIT = 500
LOG_LIMIT = 400
PAGE_SIZE = 5
START_TS = time.time()
BOT_USERNAME = ""

DEFAULT_SETTINGS = {
    "save_deleted": True,
    "save_edited": True,
    "notify": True,
    "log_media": True,
    "mute_default": False,
    "silent": False,
    "autodelete_cmd": False,
    "keep_formatting": True,
}

SETTINGS_META = [
    ("save_deleted", "🗑 Сохранять удалённые", "Присылать копию того, что удалил собеседник"),
    ("save_edited", "✏️ Сохранять правки", "Показывать «было → стало» при редактировании"),
    ("notify", "🔔 Уведомления", "Сообщать о подключении и отключении бота"),
    ("log_media", "🖼 Хранить медиа", "Сохранять фото, видео, голосовые для просмотра"),
    ("mute_default", "🔇 Мьют новым чатам", "Новые собеседники сразу попадают в мьют"),
    ("silent", "🤫 Тихий режим", "Уведомления приходят без звука"),
    ("autodelete_cmd", "🧹 Убирать команды", "Стирать своё сообщение с командой после ответа"),
    ("keep_formatting", "🎨 Хранить форматирование", "Сохранять жирный, курсив, ссылки и эмодзи"),
]

PERMS_META = [
    ("broadcast", "📢 Рассылка"),
    ("blocks", "🚫 Блокировки"),
    ("admins", "👮 Управление админами"),
    ("maintenance", "🛠 Режим работы"),
    ("logs", "🗑 Просмотр логов"),
    ("buttons", "🧱 Конструктор кнопок"),
]

CMD_REGISTRY = [
    ("mute", ".mute", "модерация", "собеседник замолкает: его новые сообщения удаляются"),
    ("unmute", ".unmute", "модерация", "снять мьют с текущего чата"),
    ("mutelist", ".mutelist", "модерация", "список чатов в мьюте"),
    ("del", ".del", "модерация", "удалить сообщение, на которое сделан reply"),
    ("clear", ".clear N", "модерация", "удалить последние N своих сообщений"),
    ("afk", ".afk текст", "модерация", "автоответ «я отошёл», по одному разу на чат"),
    ("afkoff", ".afkoff", "модерация", "выключить автоответ"),
    ("pin", ".pin", "модерация", "закрепить сообщение из reply"),
    ("unpin", ".unpin", "модерация", "открепить сообщение из reply"),
    ("ky", ".ky", "текст", "заменяет сообщение на «привет»"),
    ("rev", ".rev текст", "текст", "переворачивает текст задом наперёд"),
    ("spoiler", ".spoiler текст", "текст", "прячет текст под спойлер"),
    ("b", ".b текст", "текст", "жирный текст"),
    ("i", ".i текст", "текст", "курсив"),
    ("fpost", ".fpost текст", "текст", "жирный и курсив одновременно"),
    ("quote", ".quote текст", "текст", "оформляет как цитату"),
    ("up", ".up текст", "текст", "ПЕРЕВОДИТ В ВЕРХНИЙ РЕГИСТР"),
    ("mock", ".mock текст", "текст", "чЕрЕдУеТ рЕгИсТр"),
    ("space", ".space текст", "текст", "р а з р я д к а  б у к в"),
    ("ascii", ".ascii текст", "текст", "крупные буквы из блоков"),
    ("translate", ".translate текст", "текст", "перевод (нужен внешний API)"),
    ("cemoji", ".cemoji", "текст", "памятка про кастомные эмодзи"),
    ("tic", ".tic", "игры", "крестики-нолики прямо в переписке"),
    ("ticstop", ".ticstop", "игры", "завершить партию досрочно"),
    ("roll", ".roll", "игры", "случайное число от 1 до 100"),
    ("coin", ".coin", "игры", "орёл или решка"),
    ("love", ".love", "игры", "процент совместимости"),
    ("8ball", ".8ball вопрос", "игры", "ответ магического шара"),
    ("choose", ".choose а | б | в", "игры", "выбирает один вариант из списка"),
    ("id", ".id", "утилиты", "id чата и владельца"),
    ("info", ".info", "утилиты", "данные о собеседнике"),
    ("ping", ".ping", "утилиты", "проверка задержки"),
    ("time", ".time", "утилиты", "текущие дата и время"),
    ("calc", ".calc выражение", "утилиты", "калькулятор"),
    ("weather", ".weather город", "утилиты", "погода (нужен внешний API)"),
    ("hash", ".hash текст", "утилиты", "MD5 и SHA-256 от текста"),
    ("count", ".count текст", "утилиты", "количество символов и слов"),
    ("type", ".type", "утилиты", "статус «печатает…» до вашего сообщения"),
    ("stats", ".stats", "утилиты", "статистика бота"),
    ("cmds", ".cmds / .help", "утилиты", "список всех команд"),
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
        "broadcasts": 0,
    },
    "logs": {"deleted": [], "edited": []},
    "peers": {},
    "users": {},
    "admins": {},
    "blocked": {},
    "custom_buttons": [],
    "mode": "on",
    "daily": {},
    "afk": {},
    "tic": {},
    "board_games": {},
    "media": {},
    "media_seq": 0,
}
ARCHIVE = {}
TYPING_TASKS = {}
PENDING = {}
_dirty = False


def load_data():
    global ARCHIVE
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            for key, val in data.items():
                if key not in STATE:
                    continue
                if isinstance(STATE[key], dict) and isinstance(val, dict):
                    STATE[key].update(val)
                elif isinstance(val, type(STATE[key])):
                    STATE[key] = val
            log.info("Состояние загружено из %s", STATE_FILE)
        except Exception as e:
            log.error("Не удалось загрузить состояние: %s", e)
    for key, val in DEFAULT_SETTINGS.items():
        STATE["global_settings"].setdefault(key, val)
    for item in CMD_REGISTRY:
        STATE["commands"].setdefault(item[0], True)
    STATE["admins"].setdefault(str(SUPER_ADMIN_ID), {p: True for p, _ in PERMS_META})
    if os.path.exists(ARCHIVE_FILE):
        try:
            with open(ARCHIVE_FILE, "r", encoding="utf-8") as f:
                ARCHIVE = json.load(f)
            log.info("Архив загружен (%d записей)", len(ARCHIVE))
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


def is_admin(uid) -> bool:
    return str(uid) in STATE["admins"]


def has_perm(uid, perm) -> bool:
    if int(uid) == SUPER_ADMIN_ID:
        return True
    return bool(STATE["admins"].get(str(uid), {}).get(perm))


def is_blocked(uid) -> bool:
    return str(uid) in STATE["blocked"]


def mode_allows(uid) -> bool:
    mode = STATE.get("mode", "on")
    if mode == "on":
        return True
    return is_admin(uid) or str(uid) in STATE["connections"]


def remember_user(user):
    if not user:
        return
    STATE["users"][str(user.id)] = {
        "id": user.id,
        "name": " ".join(filter(None, [user.first_name, user.last_name])) or "—",
        "username": user.username or "",
        "seen": int(time.time()),
    }
    mark_dirty()


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
        parts.append(f"{d} д")
    if h:
        parts.append(f"{h} ч")
    if m:
        parts.append(f"{m} мин")
    parts.append(f"{s} с")
    return " ".join(parts)


def memory_text() -> str:
    try:
        import resource

        kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return f"{kb / 1024:.1f} МБ"
    except Exception:
        return "недоступно"


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
        text = f"{STYLE_EMOJI.get(style, '')} {text}"
    return InlineKeyboardButton(text=text, callback_data=data)


def urlbtn(text: str, url: str, style: str = None) -> InlineKeyboardButton:
    if style and STYLE_OK:
        try:
            return InlineKeyboardButton(text=text, url=url, style=style)
        except Exception:
            pass
    if style:
        text = f"{STYLE_EMOJI.get(style, '')} {text}"
    return InlineKeyboardButton(text=text, url=url)


def plain_kb(kb: InlineKeyboardMarkup) -> InlineKeyboardMarkup:
    rows = []
    for row in kb.inline_keyboard:
        new_row = []
        for b in row:
            mark = STYLE_EMOJI.get(getattr(b, "style", None) or "", "")
            label = f"{mark} {b.text}" if mark else b.text
            if b.url:
                new_row.append(InlineKeyboardButton(text=label, url=b.url))
            else:
                new_row.append(InlineKeyboardButton(text=label, callback_data=b.callback_data))
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


ASCII_FONT = {
    "A": "###/#.#/###/#.#/#.#",
    "B": "##./#.#/##./#.#/##.",
    "C": "###/#../#../#../###",
    "D": "##./#.#/#.#/#.#/##.",
    "E": "###/#../##./#../###",
    "F": "###/#../##./#../#..",
    "G": "###/#../#.#/#.#/###",
    "H": "#.#/#.#/###/#.#/#.#",
    "I": "###/.#./.#./.#./###",
    "J": "..#/..#/..#/#.#/###",
    "K": "#.#/#.#/##./#.#/#.#",
    "L": "#../#../#../#../###",
    "M": "#.#/###/###/#.#/#.#",
    "N": "##./#.#/#.#/#.#/#.#",
    "O": "###/#.#/#.#/#.#/###",
    "P": "###/#.#/###/#../#..",
    "Q": "###/#.#/#.#/###/..#",
    "R": "###/#.#/##./#.#/#.#",
    "S": "###/#../###/..#/###",
    "T": "###/.#./.#./.#./.#.",
    "U": "#.#/#.#/#.#/#.#/###",
    "V": "#.#/#.#/#.#/#.#/.#.",
    "W": "#.#/#.#/###/###/#.#",
    "X": "#.#/#.#/.#./#.#/#.#",
    "Y": "#.#/#.#/.#./.#./.#.",
    "Z": "###/..#/.#./#../###",
    "0": "###/#.#/#.#/#.#/###",
    "1": ".#./##./.#./.#./###",
    "2": "###/..#/###/#../###",
    "3": "###/..#/###/..#/###",
    "4": "#.#/#.#/###/..#/..#",
    "5": "###/#../###/..#/###",
    "6": "###/#../###/#.#/###",
    "7": "###/..#/..#/..#/..#",
    "8": "###/#.#/###/#.#/###",
    "9": "###/#.#/###/..#/###",
    "!": ".#./.#./.#./.../.#.",
    "?": "###/..#/.##/.../.#.",
    " ": ".../.../.../.../...",
}


def ascii_art(text: str) -> str:
    chars = [c for c in text.upper() if c in ASCII_FONT][:10]
    if not chars:
        return ""
    rows = ["" for _ in range(5)]
    for c in chars:
        glyph = ASCII_FONT[c].split("/")
        for i in range(5):
            rows[i] += glyph[i].replace("#", "█").replace(".", " ") + " "
    return "\n".join(r.rstrip() for r in rows)


CONTENT_NAMES = {
    "text": "текст",
    "photo": "фото",
    "video": "видео",
    "video_note": "видеокружок",
    "voice": "голосовое",
    "audio": "аудио",
    "document": "файл",
    "sticker": "стикер",
    "animation": "GIF",
    "location": "геолокация",
    "contact": "контакт",
    "poll": "опрос",
    "dice": "дайс",
    "story": "история",
}
MEDIA_TYPES = {"photo", "video", "video_note", "voice", "audio", "document", "animation", "sticker"}
VIEW_LABEL = {
    "photo": "👁 Просмотреть",
    "video": "👁 Просмотреть",
    "video_note": "👁 Просмотреть",
    "animation": "👁 Просмотреть",
    "voice": "▶️ Прослушать",
    "audio": "▶️ Прослушать",
    "document": "📄 Открыть",
    "sticker": "👁 Показать",
}

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
        log.error("Не удалось обновить экран: %s", e)
    if kb is not None:
        try:
            STYLE_OK = False
            await call.message.edit_text(text, reply_markup=plain_kb(kb))
            return
        except Exception as e2:
            log.error("Повторное обновление не удалось: %s", e2)
    try:
        await call.message.answer(text, reply_markup=kb)
    except Exception as e3:
        log.error("Не удалось отправить экран: %s", e3)


async def edit_own(conn_id, chat_id, message_id, text) -> bool:
    try:
        await bot.edit_message_text(
            business_connection_id=conn_id, chat_id=chat_id, message_id=message_id, text=text
        )
        return True
    except Exception as e:
        log.error("Не удалось отредактировать %s в %s: %s", message_id, chat_id, e)
        return False


async def biz_send(conn_id, chat_id, text):
    try:
        return await bot.send_message(chat_id=chat_id, text=text, business_connection_id=conn_id)
    except Exception as e:
        log.error("Не удалось отправить в бизнес-чат %s: %s", chat_id, e)
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


def message_html(message: Message, keep_formatting=True) -> str:
    plain = message.text or message.caption or ""
    if not keep_formatting:
        return html.escape(plain)
    try:
        return message.html_text or html.escape(plain)
    except Exception:
        return html.escape(plain)


def arg_html(message: Message, keep_formatting=True) -> str:
    raw = message_html(message, keep_formatting)
    parts = raw.split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""


def extract_file(message: Message):
    ctype = message.content_type if isinstance(message.content_type, str) else str(message.content_type)
    try:
        if ctype == "photo" and message.photo:
            return message.photo[-1].file_id, ""
        if ctype == "video" and message.video:
            return message.video.file_id, message.video.file_name or ""
        if ctype == "video_note" and message.video_note:
            return message.video_note.file_id, ""
        if ctype == "animation" and message.animation:
            return message.animation.file_id, message.animation.file_name or ""
        if ctype == "voice" and message.voice:
            return message.voice.file_id, ""
        if ctype == "audio" and message.audio:
            return message.audio.file_id, message.audio.file_name or ""
        if ctype == "document" and message.document:
            return message.document.file_id, message.document.file_name or ""
        if ctype == "sticker" and message.sticker:
            return message.sticker.file_id, message.sticker.emoji or ""
    except Exception as e:
        log.error("extract_file: %s", e)
    return "", ""


def describe(message: Message, keep_formatting=True) -> dict:
    ctype = message.content_type if isinstance(message.content_type, str) else str(message.content_type)
    user = message.from_user
    if user:
        name = " ".join(filter(None, [user.first_name, getattr(user, "last_name", None)]))
    else:
        name = "?"
    file_id, file_name = extract_file(message)
    return {
        "chat_id": message.chat.id,
        "message_id": message.message_id,
        "user_id": user.id if user else 0,
        "name": name or "?",
        "username": user.username if user and user.username else "",
        "type": ctype,
        "text": message.text or message.caption or "",
        "html": message_html(message, keep_formatting),
        "file_id": file_id,
        "file_name": file_name,
        "ts": int(time.time()),
    }


def store(message: Message, keep_formatting=True):
    rec = describe(message, keep_formatting)
    ARCHIVE[archive_key(rec["chat_id"], rec["message_id"])] = rec
    mark_dirty()
    return rec


def save_media(rec) -> str:
    if not rec.get("file_id"):
        return ""
    STATE["media_seq"] = int(STATE.get("media_seq", 0)) + 1
    mid = str(STATE["media_seq"])
    STATE["media"][mid] = {
        "id": mid,
        "type": rec.get("type"),
        "file_id": rec.get("file_id"),
        "file_name": rec.get("file_name", ""),
        "name": rec.get("name", "?"),
        "chat_id": rec.get("chat_id"),
        "caption": rec.get("html") or "",
        "owner": rec.get("owner", 0),
        "ts": int(time.time()),
    }
    if len(STATE["media"]) > MEDIA_LIMIT:
        oldest = sorted(STATE["media"], key=lambda k: STATE["media"][k].get("ts", 0))
        for k in oldest[: len(STATE["media"]) - MEDIA_LIMIT]:
            STATE["media"].pop(k, None)
    mark_dirty()
    return mid


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
        btn(f"{page + 1} / {total}", "noop"),
        btn("▶️", f"{prefix}:{min(total - 1, page + 1)}"),
    ]


def home_row(extra_back=None):
    row = []
    if extra_back:
        row.append(btn("⬅️ Назад", extra_back))
    row.append(btn("🏠 Домой", "m:home"))
    return row


MODE_LABEL = {"on": "🟢 Работает", "maint": "🟡 Технические работы", "off": "🔴 Выключен"}


def main_menu_kb(user_id) -> InlineKeyboardMarkup:
    rows = [
        [btn("📋 Команды", "m:cmds", "primary"), btn("⚙️ Настройки", "m:set", "primary")],
        [btn("📊 Статус", "m:status", "success"), btn("🎮 Игры", "m:games", "success")],
        [btn("🔇 Мьюты", "m:mutes", "primary"), btn("🗑 Логи", "m:logs", "primary")],
        [btn("🧩 Команды бота", "m:cmdmgr", "primary"), btn("📈 Аналитика", "m:ana", "primary")],
        [btn("🖼 Медиа-хранилище", "m:media", "primary"), btn("🧱 Мои кнопки", "m:custom", "primary")],
    ]
    if is_admin(user_id):
        rows.append([btn("👑 Админ-панель", "a:home", "danger")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def home_text(user_id) -> str:
    return (
        "🤖 <b>Панель управления</b>\n\n"
        "Я помогаю вести личные переписки: приглушаю нежелательные чаты, "
        "сохраняю удалённые сообщения и правки, помогаю форматировать текст.\n\n"
        f"Режим работы: <b>{MODE_LABEL.get(STATE.get('mode', 'on'))}</b>\n"
        f"Время работы: <b>{uptime_text()}</b>\n"
        f"Чатов в мьюте: <b>{len(muted_of(user_id))}</b>\n\n"
        "Выберите нужный раздел ниже."
    )


def commands_text() -> str:
    out = ["📋 <b>Список команд</b>", ""]
    out.append("<i>Команды пишутся в личной переписке и работают только от вашего имени.</i>")
    out.append("")
    for cat, title in CAT_ORDER:
        out.append(f"<b>{title}</b>")
        for key, display, cat_key, desc in CMD_REGISTRY:
            if cat_key != cat:
                continue
            flag = "" if cmd_enabled(key) else " 🚫"
            out.append(f"<code>{html.escape(display)}</code>{flag} — {html.escape(desc)}")
        out.append("")
    out.append("🚫 — команда выключена в разделе «🧩 Команды бота».")
    return "\n".join(out)


def settings_page(owner_id):
    s = settings_of(owner_id)
    rows = []
    for key, title, _hint in SETTINGS_META:
        on = bool(s.get(key))
        rows.append([btn(f"{'🟢' if on else '🔴'} {title}", f"t:{key}", "success" if on else "danger")])
    rows.append(home_row())
    lines = ["⚙️ <b>Настройки</b>", "", "Нажмите на параметр, чтобы включить или выключить его.", ""]
    for key, title, hint in SETTINGS_META:
        lines.append(f"{'🟢' if s.get(key) else '🔴'} <b>{title}</b> — {hint}")
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows)


def status_text(owner_id) -> str:
    info = conn_of(owner_id) or {}
    s = settings_of(owner_id)
    st = STATE["stats"]
    return (
        "📊 <b>Статус</b>\n\n"
        f"Подключение к бизнес-аккаунту: {'✅ активно' if info.get('is_enabled') else '❌ отсутствует'}\n"
        f"Право удалять сообщения: {'🟢 выдано' if info.get('can_delete') else '🔴 не выдано'}\n"
        f"Право читать сообщения: {'🟢 выдано' if info.get('can_read', True) else '🔴 не выдано'}\n"
        f"Режим работы бота: <b>{MODE_LABEL.get(STATE.get('mode', 'on'))}</b>\n\n"
        f"🔇 Чатов в мьюте: <b>{len(muted_of(owner_id))}</b>\n"
        f"🗑 Удалено ботом: <b>{st.get('deleted_by_bot', 0)}</b>\n"
        f"📥 Сохранено удалённых: <b>{st.get('logged_deleted', 0)}</b>\n"
        f"✏️ Сохранено правок: <b>{st.get('logged_edited', 0)}</b>\n"
        f"🖼 Медиа в хранилище: <b>{len(STATE['media'])}</b>\n"
        f"🎮 Партий сыграно: <b>{st.get('games', 0)}</b>\n\n"
        f"Включено настроек: <b>{sum(1 for k, _t, _h in SETTINGS_META if s.get(k))} из {len(SETTINGS_META)}</b>\n"
        f"⏱ Время работы: <b>{uptime_text()}</b>"
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
        text = (
            "🔇 <b>Мьюты</b>\n\nСписок пуст — сейчас никто не приглушён.\n"
            "Чтобы приглушить чат, напишите в нём <code>.mute</code>."
        )
    else:
        lines = []
        for chat_id in items:
            peer = STATE["peers"].get(str(chat_id), {})
            uname = f" @{peer['username']}" if peer.get("username") else ""
            pname = html.escape(peer.get("name") or "—")
            lines.append(f"• <b>{pname}</b>{html.escape(uname)} — <code>{chat_id}</code>")
        text = (
            f"🔇 <b>Мьюты</b> · всего {len(muted)}\n\n"
            + "\n".join(lines)
            + "\n\nНажмите на кнопку, чтобы вернуть собеседнику возможность писать."
        )
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


def logs_menu(back=None):
    prefix = "al" if back == "a:home" else "lg"
    rows = [
        [btn("🗑 Удалённые", f"{prefix}:d:0", "primary"), btn("✏️ Правки", f"{prefix}:e:0", "primary")],
        home_row(back),
    ]
    text = (
        "🗑 <b>Логи</b>\n\n"
        f"Сохранено удалённых сообщений: <b>{len(STATE['logs'].get('deleted', []))}</b>\n"
        f"Сохранено правок: <b>{len(STATE['logs'].get('edited', []))}</b>\n\n"
        "Выберите, какой журнал открыть."
    )
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


def logs_page(kind, page, back="m:logs"):
    arr = list(reversed(STATE["logs"].get("deleted" if kind == "d" else "edited", [])))
    items, page, total = paginate(arr, page)
    if not arr:
        text = "📭 <b>Журнал пуст</b>\n\nЗаписи появятся, когда собеседник удалит или изменит сообщение."
    else:
        blocks = []
        for it in items:
            if kind == "d":
                body = it.get("html") or html.escape(it.get("text") or "")
                if not body:
                    body = f"<i>{CONTENT_NAMES.get(it.get('type', ''), 'вложение')}</i>"
                blocks.append(
                    f"🗑 <b>{html.escape(it.get('name', '?'))}</b> · {stamp(it.get('ts'))}\n"
                    f"Чат: <code>{it.get('chat_id')}</code>\n<blockquote>{body}</blockquote>"
                )
            else:
                blocks.append(
                    f"✏️ <b>{html.escape(it.get('name', '?'))}</b> · {stamp(it.get('ts'))}\n"
                    f"Чат: <code>{it.get('chat_id')}</code>\n"
                    f"Было:\n<blockquote>{it.get('old') or '—'}</blockquote>"
                    f"Стало:\n<blockquote>{it.get('new') or '—'}</blockquote>"
                )
        title = "🗑 <b>Удалённые сообщения</b>" if kind == "d" else "✏️ <b>Редактирования</b>"
        text = title + f" · всего {len(arr)}\n\n" + "\n\n".join(blocks)
    rows = []
    prefix = "al" if back == "a:logs" else "lg"
    nav = nav_row(f"{prefix}:{kind}", page, total)
    if nav:
        rows.append(nav)
    rows.append([btn("🧹 Очистить журнал", "cf:clearlogs", "danger")])
    rows.append(home_row(back))
    return text[:4000], InlineKeyboardMarkup(inline_keyboard=rows)


def media_page(page=0, back="m:home"):
    items_all = sorted(STATE["media"].values(), key=lambda m: m.get("ts", 0), reverse=True)
    items, page, total = paginate(items_all, page)
    rows = []
    for m in items:
        action = VIEW_LABEL.get(m.get("type"), "👁 Открыть")
        kind = CONTENT_NAMES.get(m.get("type"), "?")
        label = f"{action} · {kind} · {m.get('name', '')}"
        rows.append([btn(label[:60], f"v:{m['id']}", "primary"), btn("🗑", f"md:{m['id']}", "danger")])
    nav = nav_row("mdp", page, total)
    if nav:
        rows.append(nav)
    if items_all:
        rows.append([btn("🧹 Очистить хранилище", "cf:clearmedia", "danger")])
    rows.append(home_row(back if back != "m:home" else None))
    if not items_all:
        text = (
            "🖼 <b>Медиа-хранилище</b>\n\n"
            "Пока пусто. Сюда попадают фото, видео, голосовые и файлы, "
            "которые собеседник удалил из переписки.\n\n"
            "Хранение включается настройкой «🖼 Хранить медиа»."
        )
    else:
        lines = [
            f"• {CONTENT_NAMES.get(m.get('type'), '?')} от "
            f"<b>{html.escape(m.get('name', '?'))}</b> · {stamp(m.get('ts'))}"
            for m in items
        ]
        text = (
            f"🖼 <b>Медиа-хранилище</b> · всего {len(items_all)}\n\n"
            + "\n".join(lines)
            + "\n\nЛевая кнопка открывает файл, правая удаляет его из хранилища."
        )
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


def custom_menu(page=0, back="m:home"):
    items_all = STATE["custom_buttons"]
    items, page, total = paginate(items_all, page)
    rows = []
    for b in items:
        if b.get("action") == "url":
            main = urlbtn(b.get("text", "кнопка")[:40], b.get("value", "https://t.me"), b.get("color"))
            rows.append([main, btn("🗑", f"bt:del:{b['id']}", "danger")])
        else:
            main = btn(b.get("text", "кнопка")[:40], f"cb:{b['id']}", b.get("color"))
            rows.append([main, btn("🗑", f"bt:del:{b['id']}", "danger")])
    nav = nav_row("btp", page, total)
    if nav:
        rows.append(nav)
    rows.append([btn("➕ Создать кнопку", "bt:new", "success")])
    rows.append(home_row(back if back != "m:home" else None))
    text = (
        "🧱 <b>Мои кнопки</b>\n\n"
        "Здесь живут кнопки, созданные через конструктор. "
        "Кнопка может открывать ссылку или показывать заготовленный текст.\n\n"
        f"Создано кнопок: <b>{len(items_all)}</b>\n"
        "Доступные цвета: 🔴 красный, 🟢 зелёный, 🔵 синий или без цвета."
    )
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


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
        "🧩 <b>Команды бота</b>\n\n"
        "Здесь можно временно отключить отдельные команды — они перестанут срабатывать в переписках.\n\n"
        f"Сейчас отключено: <b>{len(off)}</b>"
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
    out = ["📈 <b>Аналитика за 7 дней</b>", "", "Каждая полоса — активность за день.", ""]
    for label, field, icon in (("Удаления", "del", "🗑"), ("Правки", "edit", "✏️"), ("Мьюты", "mute", "🔇")):
        values = [r.get(field, 0) for r in rows]
        mx = max(values) if values else 0
        out.append(f"{icon} <b>{label}</b> · всего за неделю: {sum(values)}")
        for d, v in zip(days, values):
            out.append(f"<code>{d[5:]} {bar_line(v, mx)} {v}</code>")
        out.append("")
    spark = "".join("▁▂▃▅▇█"[min(5, r.get("del", 0))] for r in rows)
    st = STATE["stats"]
    out.append(f"Динамика удалений: <code>{spark}</code>")
    out.append("")
    out.append(
        f"🎮 Игры: партий {st.get('games', 0)}, побед {st.get('wins', 0)}, "
        f"поражений {st.get('losses', 0)}, ничьих {st.get('draws', 0)}"
    )
    return "\n".join(out)


def games_menu():
    st = STATE["stats"]
    text = (
        "🎮 <b>Игры</b>\n\n"
        "Крестики-нолики с кнопками доступны прямо здесь.\n"
        "В переписке с собеседником работает текстовая версия — команда <code>.tic</code>.\n\n"
        f"Партий сыграно: <b>{st.get('games', 0)}</b>\n"
        f"Побед: <b>{st.get('wins', 0)}</b> · Поражений: <b>{st.get('losses', 0)}</b> · "
        f"Ничьих: <b>{st.get('draws', 0)}</b>"
    )
    rows = [[btn("❌⭕️ Начать партию", "g:new", "success")], home_row()]
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
    return "❌⭕️ <b>Крестики-нолики</b>\n\nВы играете крестиками, я — ноликами.\n\n" + status


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
        turn = "ход владельца" if game["turn"] == "X" else "ход собеседника"
        tail = f"\n\n❌ владелец · ⭕️ собеседник\nСейчас: <b>{turn}</b>\nОтправьте цифру от 1 до 9"
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
        await tic_update(conn_id, owner_id, chat_id, game, "⚠️ Клетка занята или не существует")
        return True
    game["board"][index] = symbol
    res = winner_of(game["board"])
    if res == "X":
        game["over"], game["result"] = True, "🏆 Победил владелец ❌"
        bump("wins")
    elif res == "O":
        game["over"], game["result"] = True, "🏆 Победил собеседник ⭕️"
        bump("losses")
    elif res == "D":
        game["over"], game["result"] = True, "🤝 Ничья"
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


BALL_ANSWERS = [
    "Бесспорно",
    "Мне кажется — да",
    "Пока неясно, попробуйте снова",
    "Даже не думайте",
    "Определённо да",
    "Никаких сомнений",
    "Весьма сомнительно",
    "Знаки говорят — да",
    "Лучше не рассказывать",
    "Мой ответ — нет",
]


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
    remember_user(connection.user)
    mark_dirty()
    save_data()

    if connection.is_enabled:
        log.info("Подключение включено: owner=%s", owner_id)
        await send_owner(
            owner_id,
            f"✅ <b>Бот подключён</b>\n\n"
            f"Здравствуйте, {html.escape(name)}. Я готов работать в ваших личных переписках.\n\n"
            f"Идентификатор подключения: <code>{html.escape(connection.id)}</code>\n"
            f"Ваш ID: <code>{owner_id}</code>\n\n"
            "Напишите <code>.cmds</code> в любой переписке, чтобы увидеть список команд, "
            "или воспользуйтесь меню ниже.",
            reply_markup=main_menu_kb(owner_id),
            force=True,
        )
        if not can_read:
            await send_owner(
                owner_id,
                "⚠️ Не выдано право <b>«Читать сообщения»</b>. Без него я не вижу переписку и не смогу помочь.",
                force=True,
            )
        if not can_delete:
            await send_owner(
                owner_id,
                "⚠️ Не выдано право <b>«Удалять сообщения»</b>.\n\n"
                "Без него команда <code>.mute</code> не сможет удалять сообщения собеседника.\n"
                "Настройки → Telegram для бизнеса → Чат-боты → выберите бота → включите «Удалять сообщения».",
                force=True,
            )
    else:
        log.info("Подключение отключено: owner=%s", owner_id)
        await send_owner(
            owner_id,
            "🔌 <b>Бот отключён</b>\n\nЯ больше не обрабатываю ваши переписки. "
            "Подключить меня снова можно в настройках Telegram для бизнеса.",
            force=True,
        )


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
    s = settings_of(owner_id)
    keep = s["keep_formatting"]
    parts = raw.split(maxsplit=1)
    key = parts[0][1:].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""
    arg_fmt = arg_html(message, keep)
    chat_id = message.chat.id
    mid = message.message_id
    muted = muted_of(owner_id)

    known = {c[0] for c in CMD_REGISTRY} | {"help"}
    if key not in known:
        return False
    if not cmd_enabled("cmds" if key == "help" else key):
        await edit_own(conn_id, chat_id, mid, "🚫 Эта команда отключена в настройках бота.")
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
            await send_owner(owner_id, "⚠️ Мьют включён, но право на удаление не выдано — сообщения останутся в чате.")
    elif key == "unmute":
        if chat_id in muted:
            muted.remove(chat_id)
            mark_dirty()
        result = "Размьючен"
    elif key == "mutelist":
        result = (
            "🔇 Список мьютов пуст"
            if not muted
            else f"🔇 Чатов в мьюте: {len(muted)}\n" + "\n".join(f"• {c}" for c in muted[:20])
        )
    elif key == "del":
        target = message.reply_to_message
        if not target:
            result = "⚠️ Ответьте на сообщение, которое нужно удалить."
        else:
            ok = await drop_messages(conn_id, [target.message_id])
            if ok:
                bump("deleted_by_bot")
            result = "🗑 Сообщение удалено" if ok else "⚠️ Не удалось удалить. Проверьте право «Удалять сообщения»."
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
        if not ids:
            result = "Нечего удалять: в этом чате нет сохранённых ваших сообщений."
        else:
            ok = await drop_messages(conn_id, ids)
            if ok:
                bump("deleted_by_bot", len(ids))
            result = f"🧹 Удалено сообщений: {len(ids)}" if ok else "⚠️ Не удалось удалить сообщения."
    elif key == "afk":
        if not arg:
            result = "⚠️ Укажите текст автоответа, например: .afk вернусь через час"
        else:
            STATE["afk"][str(owner_id)] = {"text": arg_fmt or arg, "replied": []}
            mark_dirty()
            result = f"😴 Автоответ включён:\n<blockquote>{arg_fmt or html.escape(arg)}</blockquote>"
    elif key == "afkoff":
        STATE["afk"].pop(str(owner_id), None)
        mark_dirty()
        result = "🙂 Автоответ выключен"
    elif key == "pin":
        target = message.reply_to_message
        if not target:
            result = "⚠️ Ответьте на сообщение, которое нужно закрепить."
        else:
            try:
                await bot.pin_chat_message(
                    chat_id=chat_id, message_id=target.message_id, business_connection_id=conn_id
                )
                result = "📌 Сообщение закреплено"
            except Exception as e:
                log.error("pin: %s", e)
                result = "⚠️ Не удалось закрепить. Нужно право на закрепление сообщений."
    elif key == "unpin":
        target = message.reply_to_message
        try:
            await bot.unpin_chat_message(
                chat_id=chat_id,
                message_id=target.message_id if target else None,
                business_connection_id=conn_id,
            )
            result = "📌 Сообщение откреплено"
        except Exception as e:
            log.error("unpin: %s", e)
            result = "⚠️ Не удалось открепить сообщение."
    elif key == "ky":
        result = "привет"
    elif key == "rev":
        result = html.escape((arg or "нечего переворачивать")[::-1])
    elif key == "spoiler":
        result = f"<tg-spoiler>{arg_fmt or 'сюрприз'}</tg-spoiler>"
    elif key == "b":
        result = f"<b>{arg_fmt or 'жирный текст'}</b>"
    elif key == "i":
        result = f"<i>{arg_fmt or 'курсив'}</i>"
    elif key == "fpost":
        result = f"<b><i>{arg_fmt or 'жирный курсив'}</i></b>"
    elif key == "quote":
        result = f"<blockquote>{arg_fmt or 'цитата'}</blockquote>"
    elif key == "up":
        result = html.escape((arg or "верхний регистр").upper())
    elif key == "mock":
        src = arg or "чередование регистра"
        result = html.escape("".join(ch.upper() if i % 2 else ch.lower() for i, ch in enumerate(src)))
    elif key == "space":
        result = html.escape(" ".join(arg or "разрядка"))
    elif key == "ascii":
        art = ascii_art(arg or "HELLO")
        result = f"<pre>{html.escape(art)}</pre>" if art else "⚠️ Поддерживаются латиница, цифры и знаки ! ?"
    elif key == "translate":
        result = (
            "🌐 Перевод требует подключения внешнего API.\n"
            f"Исходный текст:\n<blockquote>{arg_fmt or 'пусто'}</blockquote>"
        )
    elif key == "weather":
        result = (
            f"🌤 Погода для «{html.escape(arg or 'город не указан')}» требует внешнего API.\n"
            "Подключите сервис погоды и подставьте вызов в функцию команды."
        )
    elif key == "cemoji":
        result = (
            "✨ <b>Кастомные эмодзи</b>\n"
            "Премиум-эмодзи вставляются тегом <code>&lt;tg-emoji emoji-id=\"ID\"&gt;🙂&lt;/tg-emoji&gt;</code>.\n"
            "Работают только если у владельца бота есть Telegram Premium."
        )
    elif key == "hash":
        src = (arg or "").encode("utf-8")
        if not src:
            result = "⚠️ Укажите текст: .hash пример"
        else:
            result = (
                f"🔐 MD5: <code>{hashlib.md5(src).hexdigest()}</code>\n"
                f"🔐 SHA-256: <code>{hashlib.sha256(src).hexdigest()}</code>"
            )
    elif key == "count":
        src = arg or ""
        result = (
            f"🔢 Символов: <b>{len(src)}</b>\n"
            f"🔤 Без пробелов: <b>{len(src.replace(' ', ''))}</b>\n"
            f"📝 Слов: <b>{len(src.split())}</b>"
        )
    elif key == "choose":
        options = [o.strip() for o in arg.replace("|", ",").split(",") if o.strip()]
        result = (
            f"🎯 Мой выбор: <b>{html.escape(random.choice(options))}</b>"
            if options
            else "⚠️ Укажите варианты: .choose кино | театр | дом"
        )
    elif key == "love":
        result = f"💘 Совместимость: <b>{random.randint(0, 100)}%</b>"
    elif key == "8ball":
        result = f"🎱 {random.choice(BALL_ANSWERS)}"
    elif key == "roll":
        result = f"🎲 Выпало: <b>{random.randint(1, 100)}</b>"
    elif key == "coin":
        result = random.choice(["🪙 Орёл", "🪙 Решка"])
    elif key == "id":
        result = (
            f"🆔 Чат: <code>{chat_id}</code>\n"
            f"👤 Владелец: <code>{owner_id}</code>\n"
            f"🔗 Подключение: <code>{html.escape(conn_id)}</code>"
        )
    elif key == "info":
        peer = message.chat
        name = " ".join(filter(None, [peer.first_name, peer.last_name])) or "—"
        uname = f"@{peer.username}" if peer.username else "—"
        result = (
            "ℹ️ <b>Собеседник</b>\n"
            f"Имя: {html.escape(name)}\n"
            f"Username: {html.escape(uname)}\n"
            f"ID: <code>{peer.id}</code>\n"
            f"Мьют: {'🔇 включён' if chat_id in muted else '🔊 выключен'}"
        )
    elif key == "ping":
        sent = message.date.replace(tzinfo=timezone.utc).timestamp() if message.date else time.time()
        result = f"🏓 pong — {max(0.0, time.time() - sent):.2f} с"
    elif key == "time":
        result = f"🕓 {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
    elif key == "calc":
        if not arg:
            result = "⚠️ Пример: .calc 2+2*10"
        else:
            try:
                result = f"🧮 {html.escape(arg)} = <b>{safe_calc(arg)}</b>"
            except Exception:
                result = "⚠️ Не удалось вычислить выражение."
    elif key == "type":
        stop_typing(owner_id, chat_id)
        TYPING_TASKS[(owner_id, chat_id)] = asyncio.create_task(typing_loop(conn_id, chat_id))
        result = "⌨️ Печатаю… (до вашего следующего сообщения)"
    elif key == "stats":
        st = STATE["stats"]
        result = (
            "📊 <b>Статистика</b>\n"
            f"Чатов в мьюте: {len(muted)}\n"
            f"Удалено ботом: {st.get('deleted_by_bot', 0)}\n"
            f"Сохранено удалённых: {st.get('logged_deleted', 0)}\n"
            f"Сохранено правок: {st.get('logged_edited', 0)}\n"
            f"Медиа в хранилище: {len(STATE['media'])}\n"
            f"Партий сыграно: {st.get('games', 0)}\n"
            f"Время работы: {uptime_text()}"
        )
    elif key == "tic":
        game = {"board": [""] * 9, "turn": "X", "over": False, "msg_id": None, "created": time.time()}
        set_tic(owner_id, chat_id, game)
        await edit_own(conn_id, chat_id, mid, "🎮 Партия началась")
        await tic_update(conn_id, owner_id, chat_id, game)
        return True
    elif key == "ticstop":
        if get_tic(owner_id, chat_id):
            del_tic(owner_id, chat_id)
            result = "🏁 Партия завершена"
        else:
            result = "Активной партии нет"
    elif key in ("cmds", "help"):
        result = commands_text()

    if result is None:
        return False
    await edit_own(conn_id, chat_id, mid, result)
    if settings_of(owner_id)["autodelete_cmd"] and key not in ("cmds", "help"):
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
    sender_id = message.from_user.id if message.from_user else 0
    if is_blocked(sender_id) or not mode_allows(owner_id):
        return

    s = settings_of(owner_id)
    rec = store(message, s["keep_formatting"])
    rec["owner"] = owner_id
    chat_id = message.chat.id

    if sender_id == owner_id:
        stop_typing(owner_id, chat_id)
        try:
            if await handle_command(message, owner_id, conn_id):
                return
        except Exception as e:
            log.exception("Ошибка обработки команды: %s", e)
            return
        game = get_tic(owner_id, chat_id)
        if game and (message.text or "").strip().isdigit():
            try:
                await tic_move(conn_id, owner_id, chat_id, game, int(message.text.strip()) - 1, "X")
            except Exception as e:
                log.error("ход владельца: %s", e)
        return

    fresh = remember_peer(rec)
    muted = muted_of(owner_id)
    if fresh and s["mute_default"] and chat_id not in muted:
        muted.append(chat_id)
        bump_daily("mute")
        mark_dirty()
        await send_owner(owner_id, f"🔇 Новый чат <code>{chat_id}</code> автоматически переведён в мьют.")

    if chat_id in muted:
        if await drop_messages(conn_id, [message.message_id]):
            bump("deleted_by_bot")
        return

    game = get_tic(owner_id, chat_id)
    if game and (message.text or "").strip().isdigit():
        try:
            if await tic_move(conn_id, owner_id, chat_id, game, int(message.text.strip()) - 1, "O"):
                return
        except Exception as e:
            log.error("ход собеседника: %s", e)

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
    sender_id = message.from_user.id if message.from_user else 0
    if is_blocked(sender_id):
        return
    s = settings_of(owner_id)
    key = archive_key(message.chat.id, message.message_id)
    old = ARCHIVE.get(key) or {}
    old_html = old.get("html") or html.escape(old.get("text", ""))
    old_file = old.get("file_id", "")
    new_html = message_html(message, s["keep_formatting"])
    new_file, _ = extract_file(message)
    old_rec = dict(old)
    store(message, s["keep_formatting"])

    if not s["save_edited"] or sender_id == owner_id:
        return

    media_changed = bool(old_file) and bool(new_file) and old_file != new_file
    if old_html == new_html and not media_changed:
        return

    name = old.get("name") or (message.from_user.first_name if message.from_user else "собеседник")
    push_log(
        "edited",
        {
            "chat_id": message.chat.id,
            "name": name,
            "old": old_html,
            "new": new_html,
            "ts": int(time.time()),
        },
    )
    bump("logged_edited")
    bump_daily("edit")

    kind = "подпись" if old.get("type") in MEDIA_TYPES else "сообщение"
    head = f"✏️ <b>{html.escape(name)} отредактировал {kind}</b>\n💬 Чат: <code>{message.chat.id}</code>\n\n"
    body = (
        f"Было:\n<blockquote>{old_html or '<i>пусто</i>'}</blockquote>"
        f"Стало:\n<blockquote>{new_html or '<i>пусто</i>'}</blockquote>"
    )
    kb = None
    if media_changed and s["log_media"]:
        old_rec["owner"] = owner_id
        media_id = save_media(old_rec)
        head = f"✏️ <b>{html.escape(name)} заменил вложение</b>\n💬 Чат: <code>{message.chat.id}</code>\n\n"
        if media_id:
            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [btn("👁 Посмотреть прежнее", f"v:{media_id}", "primary")],
                    [btn("🗑 Удалить из хранилища", f"md:{media_id}", "danger")],
                ]
            )
    await send_owner(owner_id, (head + body)[:4000], reply_markup=kb)


async def report_deleted(owner_id, rec, s):
    name = html.escape(rec.get("name") or "Собеседник")
    ctype = rec.get("type", "text")
    chat_line = f"\n💬 Чат: <code>{rec.get('chat_id')}</code>"
    body_html = rec.get("html") or html.escape(rec.get("text") or "")

    if ctype == "text":
        text = f"🗑 <b>{name} удалил сообщение:</b>{chat_line}\n\n<blockquote>{body_html or '<i>пусто</i>'}</blockquote>"
        await send_owner(owner_id, text[:4000])
        return

    label = CONTENT_NAMES.get(ctype, "вложение")
    extra = f" {html.escape(rec.get('file_name'))}" if ctype == "document" and rec.get("file_name") else ""
    head = f"🗑 <b>{name} удалил {label}{extra}</b>{chat_line}"
    if body_html:
        head += f"\n\nПодпись:\n<blockquote>{body_html}</blockquote>"

    if not s["log_media"] or not rec.get("file_id"):
        await send_owner(owner_id, head + "\n\n<i>Сохранение медиа выключено — файл недоступен.</i>")
        return

    rec = dict(rec)
    rec["owner"] = owner_id
    media_id = save_media(rec)
    if not media_id:
        await send_owner(owner_id, head)
        return

    if ctype == "sticker":
        await send_owner(owner_id, head)
        try:
            await bot.send_sticker(owner_chat(owner_id), rec["file_id"])
        except Exception as e:
            log.error("send_sticker: %s", e)
        return

    rows = [[btn(VIEW_LABEL.get(ctype, "👁 Просмотреть"), f"v:{media_id}", "primary")]]
    if BOT_USERNAME:
        rows.append([urlbtn("🔗 Открыть по ссылке", f"https://t.me/{BOT_USERNAME}?start=view_{media_id}")])
    rows.append([btn("🗑 Удалить из хранилища", f"md:{media_id}", "danger")])
    await send_owner(owner_id, head, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


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

    for mid in event.message_ids:
        rec = ARCHIVE.get(archive_key(chat_id, mid))
        if not rec:
            await send_owner(
                owner_id,
                f"🗑 <b>Сообщение удалено</b>\n💬 Чат: <code>{chat_id}</code>\n\n"
                "<i>Копия не сохранилась — сообщение пришло до запуска бота.</i>",
            )
            continue
        if rec.get("user_id") == owner_id:
            continue
        try:
            await report_deleted(owner_id, rec, s)
            push_log("deleted", rec)
            bump("logged_deleted")
            bump_daily("del")
        except Exception as e:
            log.exception("Ошибка отчёта об удалении: %s", e)


async def send_media_to(chat_id, media, with_buttons=True):
    ctype = media.get("type")
    file_id = media.get("file_id")
    caption = f"🗑 {html.escape(media.get('name', '?'))} · {stamp(media.get('ts'))}"
    if media.get("caption"):
        caption += f"\n<blockquote>{media['caption']}</blockquote>"
    kb = (
        InlineKeyboardMarkup(inline_keyboard=[[btn("🗑 Удалить из хранилища", f"md:{media['id']}", "danger")]])
        if with_buttons
        else None
    )
    try:
        if ctype == "photo":
            await bot.send_photo(chat_id, file_id, caption=caption[:1000], reply_markup=kb)
        elif ctype == "video":
            await bot.send_video(chat_id, file_id, caption=caption[:1000], reply_markup=kb)
        elif ctype == "animation":
            await bot.send_animation(chat_id, file_id, caption=caption[:1000], reply_markup=kb)
        elif ctype == "video_note":
            await bot.send_message(chat_id, caption[:1000])
            await bot.send_video_note(chat_id, file_id, reply_markup=kb)
        elif ctype == "voice":
            await bot.send_voice(chat_id, file_id, caption=caption[:1000], reply_markup=kb)
        elif ctype == "audio":
            await bot.send_audio(chat_id, file_id, caption=caption[:1000], reply_markup=kb)
        elif ctype == "document":
            await bot.send_document(chat_id, file_id, caption=caption[:1000], reply_markup=kb)
        elif ctype == "sticker":
            await bot.send_message(chat_id, caption[:1000])
            await bot.send_sticker(chat_id, file_id, reply_markup=kb)
        else:
            await bot.send_message(chat_id, caption[:1000], reply_markup=kb)
        return True
    except Exception as e:
        log.error("send_media_to: %s", e)
        return False


@dp.message(CommandStart(deep_link=True))
async def on_deeplink(message: Message):
    remember_user(message.from_user)
    if is_blocked(message.from_user.id):
        return
    payload = (message.text or "").split(maxsplit=1)
    arg = payload[1].strip() if len(payload) > 1 else ""
    if arg.startswith("view_"):
        media = STATE["media"].get(arg[5:])
        if not media:
            await message.answer("🔍 Файл не найден — возможно, он уже удалён из хранилища.")
            return
        if media.get("owner") and int(media["owner"]) != message.from_user.id and not is_admin(message.from_user.id):
            await message.answer("⛔️ Этот файл доступен только владельцу переписки.")
            return
        await send_media_to(message.chat.id, media)
        return
    await message.answer(home_text(message.from_user.id), reply_markup=main_menu_kb(message.from_user.id))


@dp.message(CommandStart())
async def on_start(message: Message):
    remember_user(message.from_user)
    if is_blocked(message.from_user.id):
        return
    if not mode_allows(message.from_user.id):
        await message.answer(
            "🛠 Бот временно недоступен: идут технические работы.\nПопробуйте, пожалуйста, немного позже."
        )
        return
    settings_of(message.from_user.id)
    await message.answer(home_text(message.from_user.id), reply_markup=main_menu_kb(message.from_user.id))


@dp.message(Command("menu"))
async def on_menu_cmd(message: Message):
    remember_user(message.from_user)
    if is_blocked(message.from_user.id) or not mode_allows(message.from_user.id):
        return
    await message.answer(home_text(message.from_user.id), reply_markup=main_menu_kb(message.from_user.id))


@dp.message(Command("admin"))
async def on_admin_cmd(message: Message):
    remember_user(message.from_user)
    if not is_admin(message.from_user.id):
        await message.answer("⛔️ Раздел доступен только администраторам бота.")
        return
    text, kb = admin_home()
    await message.answer(text, reply_markup=kb)


@dp.callback_query(F.data == "noop")
async def on_noop(call: CallbackQuery):
    await call.answer()


@dp.callback_query(F.data == "cancel")
async def on_cancel(call: CallbackQuery):
    PENDING.pop(call.from_user.id, None)
    uid = call.from_user.id
    if is_admin(uid):
        text, kb = admin_home()
    else:
        text, kb = home_text(uid), main_menu_kb(uid)
    await safe_edit(call, text, kb)
    await call.answer("Отменено")


@dp.callback_query(F.data.startswith("m:"))
async def on_menu(call: CallbackQuery):
    uid = call.from_user.id
    if is_blocked(uid):
        await call.answer("⛔️", show_alert=True)
        return
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
        elif section == "media":
            text, kb = media_page(0)
            await safe_edit(call, text, kb)
        elif section == "custom":
            text, kb = custom_menu(0)
            await safe_edit(call, text, kb)
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


@dp.callback_query(F.data.startswith("mdp:"))
async def on_media_page(call: CallbackQuery):
    text, kb = media_page(int(call.data.split(":")[1]))
    await safe_edit(call, text, kb)
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
        if chat_id in chats and (is_admin(call.from_user.id) or owner == str(call.from_user.id)):
            chats.remove(chat_id)
            mark_dirty()
    save_data()
    body = call.message.text or ""
    if is_admin(call.from_user.id) and "Все мьюты" in body:
        text, kb = admin_mutes(0)
    else:
        text, kb = mutes_page(call.from_user.id, 0)
    await safe_edit(call, text, kb)
    await call.answer("🔊 Мьют снят")


@dp.callback_query(F.data.startswith("cmp:"))
async def on_cmd_page(call: CallbackQuery):
    back = "a:home" if is_admin(call.from_user.id) and "👑" in (call.message.text or "") else "m:home"
    text, kb = cmdmgr_page(int(call.data.split(":")[1]), back=back)
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
    text, kb = cmdmgr_page(page)
    await safe_edit(call, text, kb)
    await call.answer("🟢 Команда включена" if cmd_enabled(key) else "🔴 Команда выключена")


@dp.callback_query(F.data.startswith("lg:"))
async def on_logs(call: CallbackQuery):
    parts = call.data.split(":")
    page = int(parts[2]) if len(parts) > 2 else 0
    text, kb = logs_page(parts[1], page)
    await safe_edit(call, text, kb)
    await call.answer()


@dp.callback_query(F.data.startswith("v:"))
async def on_view_media(call: CallbackQuery):
    media = STATE["media"].get(call.data.split(":", 1)[1])
    if not media:
        await call.answer("Файл уже удалён из хранилища", show_alert=True)
        return
    if media.get("owner") and int(media["owner"]) != call.from_user.id and not is_admin(call.from_user.id):
        await call.answer("⛔️ Доступно только владельцу переписки", show_alert=True)
        return
    ok = await send_media_to(call.message.chat.id, media)
    await call.answer("Отправлено" if ok else "Не удалось открыть файл", show_alert=not ok)


@dp.callback_query(F.data.startswith("md:"))
async def on_media_delete(call: CallbackQuery):
    mid = call.data.split(":", 1)[1]
    media = STATE["media"].get(mid)
    if media and media.get("owner") and int(media["owner"]) != call.from_user.id and not is_admin(call.from_user.id):
        await call.answer("⛔️ Доступно только владельцу переписки", show_alert=True)
        return
    STATE["media"].pop(mid, None)
    mark_dirty()
    save_data()
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await call.answer("🗑 Удалено из хранилища")


@dp.callback_query(F.data.startswith("g:"))
async def on_game(call: CallbackQuery):
    uid = str(call.from_user.id)
    parts = call.data.split(":")
    games = STATE["board_games"]
    if parts[1] == "new":
        games[uid] = {"board": [""] * 9, "over": False}
        mark_dirty()
        await safe_edit(call, board_text("Ваш ход."), board_kb(games[uid]["board"]))
        await call.answer("Партия началась")
        return
    game = games.get(uid)
    if not game or game.get("over"):
        await call.answer("Начните новую партию", show_alert=True)
        return
    index = int(parts[2])
    board = game["board"]
    if board[index]:
        await call.answer("Клетка занята", show_alert=True)
        return
    board[index] = "X"
    status = "Ваш ход."
    res = winner_of(board)
    if not res:
        move = ai_move(board, "O", "X")
        if move is not None:
            board[move] = "O"
        res = winner_of(board)
    if res == "X":
        game["over"], status = True, "🏆 <b>Вы победили.</b> Отличная партия."
        bump("wins")
        bump("games")
    elif res == "O":
        game["over"], status = True, "😌 <b>Победа за мной.</b> Сыграем ещё?"
        bump("losses")
        bump("games")
    elif res == "D":
        game["over"], status = True, "🤝 <b>Ничья.</b> Силы равны."
        bump("draws")
        bump("games")
    mark_dirty()
    await safe_edit(call, board_text(status), board_kb(board, game.get("over", False)))
    await call.answer()


@dp.callback_query(F.data.startswith("cb:"))
async def on_custom_button(call: CallbackQuery):
    bid = call.data.split(":", 1)[1]
    item = next((b for b in STATE["custom_buttons"] if str(b.get("id")) == bid), None)
    if not item:
        await call.answer("Кнопка удалена", show_alert=True)
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[[btn("⬅️ К кнопкам", "m:custom"), btn("🏠 Домой", "m:home")]])
    await safe_edit(call, f"🧱 <b>{html.escape(item.get('text', 'Кнопка'))}</b>\n\n{item.get('value', '')}", kb)
    await call.answer()


def admin_home():
    st = STATE["stats"]
    text = (
        "👑 <b>Админ-панель</b>\n\n"
        f"Версия бота: <b>{BOT_VERSION}</b> · aiogram {aiogram.__version__}\n"
        f"Режим работы: <b>{MODE_LABEL.get(STATE.get('mode', 'on'))}</b>\n"
        f"Время работы: <b>{uptime_text()}</b>\n\n"
        f"Подключений: <b>{len(STATE['connections'])}</b> · "
        f"Пользователей: <b>{len(STATE['users'])}</b> · "
        f"Админов: <b>{len(STATE['admins'])}</b>\n"
        f"Мьютов: <b>{sum(len(v) for v in STATE['muted'].values())}</b> · "
        f"Заблокировано: <b>{len(STATE['blocked'])}</b>\n"
        f"Логи: <b>{len(STATE['logs'].get('deleted', []))}</b> удалений / "
        f"<b>{len(STATE['logs'].get('edited', []))}</b> правок · "
        f"Рассылок: <b>{st.get('broadcasts', 0)}</b>\n\n"
        "Выберите раздел."
    )
    rows = [
        [btn("📊 Дашборд", "a:dash", "primary"), btn("🔗 Подключения", "a:conns", "primary")],
        [btn("👮 Админы", "a:admins", "primary"), btn("🚫 Блокировки", "a:blocks", "primary")],
        [btn("📢 Рассылка", "a:bcast", "success"), btn("🧱 Конструктор кнопок", "a:buttons", "success")],
        [btn("🛠 Режим работы", "a:mode", "danger"), btn("🔇 Мьюты", "a:mutes", "primary")],
        [btn("🗑 Логи", "a:logs", "primary"), btn("⚙️ Глобальные настройки", "a:gset", "primary")],
        [btn("📈 Аналитика", "a:ana", "primary"), btn("👥 Пользователи", "a:users", "primary")],
        [btn("🖼 Медиа", "a:media", "primary"), btn("ℹ️ Система", "a:sys", "primary")],
        home_row(),
    ]
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


def admin_dash():
    st = STATE["stats"]
    active = sum(1 for c in STATE["connections"].values() if c.get("is_enabled"))
    text = (
        "📊 <b>Дашборд</b>\n\n"
        f"Статус бота: <b>{MODE_LABEL.get(STATE.get('mode', 'on'))}</b>\n"
        f"Время работы: <b>{uptime_text()}</b>\n\n"
        f"🔗 Активных подключений: <b>{active}</b> из {len(STATE['connections'])}\n"
        f"👥 Пользователей: <b>{len(STATE['users'])}</b>\n"
        f"👮 Администраторов: <b>{len(STATE['admins'])}</b>\n"
        f"🚫 Заблокировано: <b>{len(STATE['blocked'])}</b>\n"
        f"🔇 Чатов в мьюте: <b>{sum(len(v) for v in STATE['muted'].values())}</b>\n"
        f"🗑 Удалено ботом: <b>{st.get('deleted_by_bot', 0)}</b>\n"
        f"📥 Сохранено удалений: <b>{st.get('logged_deleted', 0)}</b>\n"
        f"✏️ Сохранено правок: <b>{st.get('logged_edited', 0)}</b>\n"
        f"🖼 Медиа в хранилище: <b>{len(STATE['media'])}</b>\n"
        f"🎮 Партий: <b>{st.get('games', 0)}</b>\n"
        f"⌨️ Команд выполнено: <b>{st.get('commands_used', 0)}</b>"
    )
    return text, InlineKeyboardMarkup(inline_keyboard=[[btn("🔄 Обновить", "a:dash", "success")], home_row("a:home")])


def admin_conns():
    if not STATE["connections"]:
        text = "🔗 <b>Подключения</b>\n\nПока никто не подключил бота к бизнес-аккаунту."
    else:
        lines = []
        for owner, c in list(STATE["connections"].items())[:20]:
            uname = f" @{c['username']}" if c.get("username") else ""
            lines.append(
                f"{'🟢' if c.get('is_enabled') else '🔴'} <b>{html.escape(c.get('name', '?'))}</b>{html.escape(uname)}\n"
                f"    ID: <code>{owner}</code>\n"
                f"    Удаление сообщений: {'🟢 разрешено' if c.get('can_delete') else '🔴 запрещено'}\n"
                f"    Подключено: {stamp(c.get('since'))}"
            )
        text = "🔗 <b>Подключения</b>\n\n" + "\n\n".join(lines)
    return text, InlineKeyboardMarkup(inline_keyboard=[[btn("🔄 Обновить", "a:conns", "success")], home_row("a:home")])


def admin_admins(page=0):
    items_all = list(STATE["admins"].items())
    items, page, total = paginate(items_all, page)
    rows = []
    for uid, perms in items:
        user = STATE["users"].get(uid, {})
        label = user.get("name") or uid
        crown = "👑 " if int(uid) == SUPER_ADMIN_ID else ""
        rows.append([btn(f"🔧 {crown}{label}"[:40], f"adp:{uid}", "primary")])
    nav = nav_row("adl", page, total)
    if nav:
        rows.append(nav)
    rows.append([btn("➕ Добавить админа", "ad:new", "success")])
    rows.append(home_row("a:home"))
    lines = []
    for uid, perms in items:
        active = [t for p, t in PERMS_META if perms.get(p)]
        user = STATE["users"].get(uid, {})
        crown = " 👑 супер-админ" if int(uid) == SUPER_ADMIN_ID else ""
        lines.append(
            f"• <b>{html.escape(user.get('name') or 'без имени')}</b>{crown}\n"
            f"    ID: <code>{uid}</code>\n"
            f"    Права: {', '.join(active) if active else 'нет'}"
        )
    text = (
        f"👮 <b>Администраторы</b> · всего {len(items_all)}\n\n"
        + ("\n".join(lines) if lines else "Список пуст.")
        + "\n\nНажмите на администратора, чтобы изменить его права."
    )
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


def admin_perms(uid):
    perms = STATE["admins"].get(str(uid), {})
    user = STATE["users"].get(str(uid), {})
    rows = []
    for p, title in PERMS_META:
        on = bool(perms.get(p)) or int(uid) == SUPER_ADMIN_ID
        rows.append([btn(f"{'🟢' if on else '🔴'} {title}", f"adt:{uid}:{p}", "success" if on else "danger")])
    if int(uid) != SUPER_ADMIN_ID:
        rows.append([btn("➖ Снять с должности", f"cf:deladmin_{uid}", "danger")])
    rows.append(home_row("a:admins"))
    note = ""
    if int(uid) == SUPER_ADMIN_ID:
        note = "\n\n👑 Это супер-администратор: его права нельзя изменить или отозвать."
    text = (
        f"🔧 <b>Права администратора</b>\n\n"
        f"Имя: <b>{html.escape(user.get('name') or 'неизвестно')}</b>\n"
        f"ID: <code>{uid}</code>\n\n"
        "Нажмите на разрешение, чтобы выдать или отозвать его." + note
    )
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


def admin_blocks(page=0):
    items_all = list(STATE["blocked"].items())
    items, page, total = paginate(items_all, page)
    rows = []
    for uid, info in items:
        rows.append([btn(f"✅ Разблокировать · {info.get('name') or uid}"[:55], f"blu:{uid}", "success")])
    nav = nav_row("bll", page, total)
    if nav:
        rows.append(nav)
    rows.append([btn("➕ Заблокировать по ID", "bl:new", "danger")])
    rows.append(home_row("a:home"))
    if not items_all:
        text = (
            "🚫 <b>Блокировки</b>\n\n"
            "Список пуст. Заблокированный пользователь полностью игнорируется ботом: "
            "его сообщения не обрабатываются, команды не работают."
        )
    else:
        lines = [
            f"• <b>{html.escape(info.get('name') or '—')}</b> — <code>{uid}</code> · {stamp(info.get('ts'))}"
            for uid, info in items
        ]
        text = f"🚫 <b>Блокировки</b> · всего {len(items_all)}\n\n" + "\n".join(lines)
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


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
        rows.append([btn(f"🔊 Размутить · {label}"[:55], f"um:{chat_id}", "danger")])
    nav = nav_row("amp", page, total)
    if nav:
        rows.append(nav)
    if flat:
        rows.append([btn("♻️ Размутить все", "cf:unmuteall", "danger")])
    rows.append(home_row("a:home"))
    if not flat:
        text = "🔇 <b>Все мьюты</b>\n\nСписок пуст."
    else:
        lines = [
            f"• Владелец <code>{o}</code> → чат <code>{c}</code> "
            f"({html.escape(STATE['peers'].get(str(c), {}).get('name') or '—')})"
            for o, c in items
        ]
        text = f"🔇 <b>Все мьюты</b> · всего {len(flat)}\n\n" + "\n".join(lines)
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


def admin_gset():
    g = STATE["global_settings"]
    rows = []
    for key, title, _hint in SETTINGS_META:
        on = bool(g.get(key))
        rows.append([btn(f"{'🟢' if on else '🔴'} {title}", f"gs:{key}", "success" if on else "danger")])
    rows.append(home_row("a:home"))
    text = (
        "⚙️ <b>Глобальные настройки</b>\n\n"
        "Эти значения применяются ко всем новым владельцам бота. "
        "У тех, кто уже настроил бота под себя, личные настройки сохраняются."
    )
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


def admin_users(page=0):
    users = sorted(STATE["users"].values(), key=lambda p: p.get("seen", 0), reverse=True)
    items, page, total = paginate(users, page)
    if not users:
        text = "👥 <b>Пользователи</b>\n\nПока никто не запускал бота."
    else:
        lines = [
            f"• <b>{html.escape(p.get('name') or '—')}</b>"
            f"{' @' + html.escape(p['username']) if p.get('username') else ''} — "
            f"<code>{p.get('id')}</code> · {stamp(p.get('seen'))}"
            for p in items
        ]
        text = (
            f"👥 <b>Пользователи</b> · всего {len(users)}\n\n"
            + "\n".join(lines)
            + "\n\nЭтот список используется для рассылки."
        )
    rows = []
    nav = nav_row("aup", page, total)
    if nav:
        rows.append(nav)
    rows.append(home_row("a:home"))
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


def admin_mode():
    mode = STATE.get("mode", "on")
    rows = [
        [btn("🟢 Работает", "cf:mode_on", "success")],
        [btn("🟡 Технические работы", "cf:mode_maint", "primary")],
        [btn("🔴 Выключен", "cf:mode_off", "danger")],
        home_row("a:home"),
    ]
    text = (
        "🛠 <b>Режим работы</b>\n\n"
        f"Сейчас: <b>{MODE_LABEL.get(mode)}</b>\n\n"
        "🟢 <b>Работает</b> — бот доступен всем.\n"
        "🟡 <b>Технические работы</b> — отвечает только владельцам и админам, остальным приходит вежливое уведомление.\n"
        "🔴 <b>Выключен</b> — бот не реагирует ни на кого, кроме владельцев и админов.\n\n"
        "Смена режима запросит подтверждение."
    )
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


def admin_sys():
    text = (
        "ℹ️ <b>Система</b>\n\n"
        f"🤖 Версия бота: <b>{BOT_VERSION}</b>\n"
        f"📦 aiogram: <b>{aiogram.__version__}</b>\n"
        f"🎨 Цветные кнопки: <b>{'нативные (style)' if STYLE_OK else 'эмуляция эмодзи'}</b>\n"
        f"🔗 Username бота: <b>@{BOT_USERNAME or 'неизвестно'}</b>\n"
        f"⏱ Время работы: <b>{uptime_text()}</b>\n"
        f"🧠 Память: <b>{memory_text()}</b>\n"
        f"💾 Состояние: <code>{html.escape(os.path.abspath(STATE_FILE))}</code>\n"
        f"🗂 Архив сообщений: <code>{html.escape(os.path.abspath(ARCHIVE_FILE))}</code>\n"
        f"👑 Супер-админ: <code>{SUPER_ADMIN_ID}</code>"
    )
    rows = [
        [btn("🔄 Обновить", "a:sys", "success"), btn("💾 Сохранить состояние", "do:save", "primary")],
        [btn("🔔 Тестовое уведомление", "do:testnotify", "primary")],
        home_row("a:home"),
    ]
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


def bcast_home(uid):
    draft = PENDING.get(uid, {}).get("draft") if PENDING.get(uid, {}).get("mode", "").startswith("bc") else None
    rows = [[btn("✍️ Составить сообщение", "br:new", "success")]]
    if STATE.get("bcast_draft"):
        rows.append([btn("👁 Предпросмотр черновика", "br:preview", "primary")])
    rows.append(home_row("a:home"))
    text = (
        "📢 <b>Рассылка</b>\n\n"
        f"Получателей в базе: <b>{len(STATE['users'])}</b>\n"
        f"Рассылок отправлено: <b>{STATE['stats'].get('broadcasts', 0)}</b>\n\n"
        "Порядок работы:\n"
        "1. Составьте сообщение — форматирование и эмодзи сохраняются.\n"
        "2. При желании добавьте кнопку со ссылкой.\n"
        "3. Посмотрите предпросмотр и подтвердите отправку."
    )
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


def bcast_preview_kb():
    draft = STATE.get("bcast_draft") or {}
    rows = []
    if draft.get("btn_text") and draft.get("btn_url"):
        rows.append([urlbtn(draft["btn_text"], draft["btn_url"], draft.get("btn_color"))])
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None


def buttons_home(page=0):
    return custom_menu(page, back="a:home")


CONFIRMS = {
    "unmuteall": "Будут сняты все мьюты во всех чатах.",
    "clearlogs": "Журналы удалений и правок будут очищены.",
    "cleararch": "Архив сохранённых сообщений будет очищен.",
    "clearmedia": "Все файлы из медиа-хранилища будут удалены.",
    "mode_on": "Бот станет доступен всем пользователям.",
    "mode_maint": "Бот будет отвечать только владельцам и админам.",
    "mode_off": "Бот перестанет реагировать на всех, кроме владельцев и админов.",
    "bcastsend": "Сообщение будет отправлено всем пользователям бота.",
}


@dp.callback_query(F.data.startswith("a:"))
async def on_admin(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("⛔️ Доступно только администраторам", show_alert=True)
        return
    section = call.data.split(":", 1)[1]
    guard = {
        "admins": "admins",
        "blocks": "blocks",
        "bcast": "broadcast",
        "buttons": "buttons",
        "mode": "maintenance",
        "logs": "logs",
    }.get(section)
    if guard and not has_perm(call.from_user.id, guard):
        await call.answer("⛔️ Недостаточно прав для этого раздела", show_alert=True)
        return
    try:
        if section == "dash":
            text, kb = admin_dash()
        elif section == "conns":
            text, kb = admin_conns()
        elif section == "admins":
            text, kb = admin_admins(0)
        elif section == "blocks":
            text, kb = admin_blocks(0)
        elif section == "bcast":
            text, kb = bcast_home(call.from_user.id)
        elif section == "buttons":
            text, kb = buttons_home(0)
        elif section == "mode":
            text, kb = admin_mode()
        elif section == "mutes":
            text, kb = admin_mutes(0)
        elif section == "logs":
            text, kb = logs_menu(back="a:home")
        elif section == "gset":
            text, kb = admin_gset()
        elif section == "ana":
            text, kb = analytics_text(), InlineKeyboardMarkup(inline_keyboard=[home_row("a:home")])
        elif section == "users":
            text, kb = admin_users(0)
        elif section == "media":
            text, kb = media_page(0, back="a:home")
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
    if not is_admin(call.from_user.id) or not has_perm(call.from_user.id, "logs"):
        await call.answer("⛔️ Недостаточно прав", show_alert=True)
        return
    parts = call.data.split(":")
    text, kb = logs_page(parts[1], int(parts[2]) if len(parts) > 2 else 0, back="a:logs")
    await safe_edit(call, text, kb)
    await call.answer()


@dp.callback_query(F.data.startswith("amp:"))
async def on_admin_mutes_page(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("⛔️", show_alert=True)
        return
    text, kb = admin_mutes(int(call.data.split(":")[1]))
    await safe_edit(call, text, kb)
    await call.answer()


@dp.callback_query(F.data.startswith("aup:"))
async def on_admin_users_page(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("⛔️", show_alert=True)
        return
    text, kb = admin_users(int(call.data.split(":")[1]))
    await safe_edit(call, text, kb)
    await call.answer()


@dp.callback_query(F.data.startswith("adl:"))
async def on_admin_list_page(call: CallbackQuery):
    if not has_perm(call.from_user.id, "admins"):
        await call.answer("⛔️", show_alert=True)
        return
    text, kb = admin_admins(int(call.data.split(":")[1]))
    await safe_edit(call, text, kb)
    await call.answer()


@dp.callback_query(F.data.startswith("bll:"))
async def on_blocks_page(call: CallbackQuery):
    if not has_perm(call.from_user.id, "blocks"):
        await call.answer("⛔️", show_alert=True)
        return
    text, kb = admin_blocks(int(call.data.split(":")[1]))
    await safe_edit(call, text, kb)
    await call.answer()


@dp.callback_query(F.data.startswith("btp:"))
async def on_buttons_page(call: CallbackQuery):
    text, kb = custom_menu(int(call.data.split(":")[1]), back="a:home" if is_admin(call.from_user.id) else "m:home")
    await safe_edit(call, text, kb)
    await call.answer()


@dp.callback_query(F.data.startswith("adp:"))
async def on_admin_perms(call: CallbackQuery):
    if not has_perm(call.from_user.id, "admins"):
        await call.answer("⛔️ Недостаточно прав", show_alert=True)
        return
    uid = call.data.split(":", 1)[1]
    text, kb = admin_perms(uid)
    await safe_edit(call, text, kb)
    await call.answer()


@dp.callback_query(F.data.startswith("adt:"))
async def on_admin_perm_toggle(call: CallbackQuery):
    if not has_perm(call.from_user.id, "admins"):
        await call.answer("⛔️ Недостаточно прав", show_alert=True)
        return
    _, uid, perm = call.data.split(":")
    if int(uid) == SUPER_ADMIN_ID:
        await call.answer("👑 Права супер-администратора изменить нельзя", show_alert=True)
        return
    perms = STATE["admins"].setdefault(uid, {})
    perms[perm] = not perms.get(perm)
    mark_dirty()
    save_data()
    text, kb = admin_perms(uid)
    await safe_edit(call, text, kb)
    await call.answer("🟢 Право выдано" if perms[perm] else "🔴 Право отозвано")


@dp.callback_query(F.data == "ad:new")
async def on_admin_new(call: CallbackQuery):
    if not has_perm(call.from_user.id, "admins"):
        await call.answer("⛔️ Недостаточно прав", show_alert=True)
        return
    PENDING[call.from_user.id] = {"mode": "add_admin"}
    kb = InlineKeyboardMarkup(inline_keyboard=[[btn("❌ Отмена", "cancel", "danger")]])
    await safe_edit(
        call,
        "➕ <b>Новый администратор</b>\n\nОтправьте числовой ID пользователя одним сообщением.\n"
        "Узнать ID можно, попросив человека запустить бота — он появится в разделе «👥 Пользователи».",
        kb,
    )
    await call.answer()


@dp.callback_query(F.data == "bl:new")
async def on_block_new(call: CallbackQuery):
    if not has_perm(call.from_user.id, "blocks"):
        await call.answer("⛔️ Недостаточно прав", show_alert=True)
        return
    PENDING[call.from_user.id] = {"mode": "add_block"}
    kb = InlineKeyboardMarkup(inline_keyboard=[[btn("❌ Отмена", "cancel", "danger")]])
    ask = "🚫 <b>Блокировка</b>\n\nОтправьте числовой ID пользователя, которого нужно заблокировать."
    await safe_edit(call, ask, kb)
    await call.answer()


@dp.callback_query(F.data.startswith("blu:"))
async def on_unblock(call: CallbackQuery):
    if not has_perm(call.from_user.id, "blocks"):
        await call.answer("⛔️ Недостаточно прав", show_alert=True)
        return
    STATE["blocked"].pop(call.data.split(":", 1)[1], None)
    mark_dirty()
    save_data()
    text, kb = admin_blocks(0)
    await safe_edit(call, text, kb)
    await call.answer("✅ Пользователь разблокирован")


@dp.callback_query(F.data == "br:new")
async def on_bcast_new(call: CallbackQuery):
    if not has_perm(call.from_user.id, "broadcast"):
        await call.answer("⛔️ Недостаточно прав", show_alert=True)
        return
    PENDING[call.from_user.id] = {"mode": "bc_text"}
    kb = InlineKeyboardMarkup(inline_keyboard=[[btn("❌ Отмена", "cancel", "danger")]])
    await safe_edit(
        call,
        "✍️ <b>Шаг 1 из 3. Текст рассылки</b>\n\n"
        "Отправьте сообщение, которое получат пользователи. "
        "Жирный, курсив, ссылки, спойлеры и премиум-эмодзи сохранятся.",
        kb,
    )
    await call.answer()


@dp.callback_query(F.data == "br:addbtn")
async def on_bcast_addbtn(call: CallbackQuery):
    if not has_perm(call.from_user.id, "broadcast"):
        await call.answer("⛔️", show_alert=True)
        return
    PENDING[call.from_user.id] = {"mode": "bc_btn"}
    kb = InlineKeyboardMarkup(inline_keyboard=[[btn("❌ Отмена", "cancel", "danger")]])
    await safe_edit(
        call,
        "🔗 <b>Шаг 2 из 3. Кнопка</b>\n\n"
        "Отправьте текст кнопки и ссылку через вертикальную черту:\n"
        "<code>Открыть сайт | https://example.com</code>",
        kb,
    )
    await call.answer()


@dp.callback_query(F.data.startswith("br:color:"))
async def on_bcast_color(call: CallbackQuery):
    color = call.data.split(":")[2]
    draft = STATE.setdefault("bcast_draft", {})
    draft["btn_color"] = None if color == "none" else color
    mark_dirty()
    await show_bcast_preview(call)
    await call.answer("Цвет выбран")


async def show_bcast_preview(call: CallbackQuery):
    draft = STATE.get("bcast_draft") or {}
    rows = []
    if draft.get("btn_text") and draft.get("btn_url"):
        rows.append(
            [
                btn("🔴 Красная", "br:color:danger", "danger"),
                btn("🟢 Зелёная", "br:color:success", "success"),
                btn("🔵 Синяя", "br:color:primary", "primary"),
            ]
        )
        rows.append([btn("⚪️ Без цвета", "br:color:none")])
    else:
        rows.append([btn("🔗 Добавить кнопку", "br:addbtn", "primary")])
    rows.append([btn("✅ Отправить рассылку", "cf:bcastsend", "success")])
    rows.append([btn("✍️ Переписать текст", "br:new", "primary"), btn("❌ Отмена", "cancel", "danger")])
    preview = draft.get("html") or "<i>текст не задан</i>"
    btn_line = (
        f"\n\nКнопка: <b>{html.escape(draft.get('btn_text', ''))}</b> → {html.escape(draft.get('btn_url', ''))}"
        if draft.get("btn_text")
        else "\n\nКнопка не добавлена."
    )
    text = (
        "👁 <b>Шаг 3 из 3. Предпросмотр</b>\n\n"
        "Так сообщение увидят получатели:\n\n"
        f"<blockquote>{preview}</blockquote>"
        f"{btn_line}\n\n"
        f"Получателей: <b>{len(STATE['users'])}</b>"
    )
    await safe_edit(call, text[:4000], InlineKeyboardMarkup(inline_keyboard=rows))


@dp.callback_query(F.data == "br:preview")
async def on_bcast_preview(call: CallbackQuery):
    if not has_perm(call.from_user.id, "broadcast"):
        await call.answer("⛔️", show_alert=True)
        return
    await show_bcast_preview(call)
    await call.answer()


@dp.callback_query(F.data == "bt:new")
async def on_button_new(call: CallbackQuery):
    if not has_perm(call.from_user.id, "buttons") and is_admin(call.from_user.id):
        await call.answer("⛔️ Недостаточно прав", show_alert=True)
        return
    PENDING[call.from_user.id] = {"mode": "btn_text"}
    kb = InlineKeyboardMarkup(inline_keyboard=[[btn("❌ Отмена", "cancel", "danger")]])
    await safe_edit(
        call,
        "🧱 <b>Новая кнопка · шаг 1</b>\n\nОтправьте надпись, которая будет на кнопке.",
        kb,
    )
    await call.answer()


@dp.callback_query(F.data.startswith("bt:act:"))
async def on_button_action(call: CallbackQuery):
    action = call.data.split(":")[2]
    draft = PENDING.setdefault(call.from_user.id, {})
    draft["action"] = action
    draft["mode"] = "btn_value"
    kb = InlineKeyboardMarkup(inline_keyboard=[[btn("❌ Отмена", "cancel", "danger")]])
    hint = (
        "Отправьте ссылку, которую откроет кнопка (например <code>https://example.com</code>)."
        if action == "url"
        else "Отправьте текст, который бот покажет при нажатии."
    )
    await safe_edit(call, f"🧱 <b>Новая кнопка · шаг 3</b>\n\n{hint}", kb)
    await call.answer()


@dp.callback_query(F.data.startswith("bt:color:"))
async def on_button_color(call: CallbackQuery):
    color = call.data.split(":")[2]
    draft = PENDING.get(call.from_user.id, {})
    if not draft.get("text"):
        await call.answer("Черновик потерян, начните заново", show_alert=True)
        return
    item = {
        "id": str(int(time.time() * 1000))[-9:],
        "text": draft.get("text"),
        "action": draft.get("action", "text"),
        "value": draft.get("value", ""),
        "color": None if color == "none" else color,
    }
    STATE["custom_buttons"].append(item)
    PENDING.pop(call.from_user.id, None)
    mark_dirty()
    save_data()
    text, kb = custom_menu(0, back="a:home" if is_admin(call.from_user.id) else "m:home")
    await safe_edit(call, text, kb)
    await call.answer("✅ Кнопка создана")


@dp.callback_query(F.data.startswith("bt:del:"))
async def on_button_delete(call: CallbackQuery):
    bid = call.data.split(":")[2]
    STATE["custom_buttons"] = [b for b in STATE["custom_buttons"] if str(b.get("id")) != bid]
    mark_dirty()
    save_data()
    text, kb = custom_menu(0, back="a:home" if is_admin(call.from_user.id) else "m:home")
    await safe_edit(call, text, kb)
    await call.answer("🗑 Кнопка удалена")


@dp.callback_query(F.data.startswith("gs:"))
async def on_global_toggle(call: CallbackQuery):
    if not is_admin(call.from_user.id):
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
    if action != "unmuteall" and not is_admin(call.from_user.id):
        await call.answer("⛔️ Доступно только администраторам", show_alert=True)
        return
    if action.startswith("deladmin_"):
        question = "Пользователь потеряет доступ к админ-панели."
    else:
        question = CONFIRMS.get(action, "Действие нельзя отменить.")
    cancel = "a:home" if is_admin(call.from_user.id) else "m:home"
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[btn("✅ Да, продолжить", f"do:{action}", "success"), btn("❌ Нет", cancel, "danger")]]
    )
    await safe_edit(call, f"⚠️ <b>Подтвердите действие</b>\n\n{question}", kb)
    await call.answer()


async def run_broadcast(sender_id) -> str:
    draft = STATE.get("bcast_draft") or {}
    text = draft.get("html")
    if not text:
        return "Черновик пуст."
    kb = bcast_preview_kb()
    sent = failed = 0
    for uid in list(STATE["users"].keys()):
        if is_blocked(uid):
            continue
        try:
            await bot.send_message(int(uid), text, reply_markup=kb)
            sent += 1
        except Exception as e:
            failed += 1
            log.warning("Рассылка %s: %s", uid, e)
        await asyncio.sleep(0.05)
    bump("broadcasts")
    STATE["bcast_draft"] = {}
    mark_dirty()
    save_data()
    lines = [
        "📢 Рассылка завершена.",
        "",
        f"✅ Доставлено: <b>{sent}</b>",
        f"⚠️ Ошибок: <b>{failed}</b>",
    ]
    return "\n".join(lines)


@dp.callback_query(F.data.startswith("do:"))
async def on_do(call: CallbackQuery):
    action = call.data.split(":", 1)[1]
    admin = is_admin(call.from_user.id)
    note = None
    try:
        if action == "unmuteall":
            if admin:
                STATE["muted"] = {}
            else:
                STATE["muted"][str(call.from_user.id)] = []
            mark_dirty()
            save_data()
            await call.answer("♻️ Мьюты сняты")
        elif not admin:
            await call.answer("⛔️ Доступно только администраторам", show_alert=True)
            return
        elif action == "clearlogs":
            STATE["logs"] = {"deleted": [], "edited": []}
            mark_dirty()
            save_data()
            await call.answer("🧹 Журналы очищены")
        elif action == "cleararch":
            ARCHIVE.clear()
            mark_dirty()
            save_data()
            await call.answer("🗂 Архив очищен")
        elif action == "clearmedia":
            STATE["media"] = {}
            mark_dirty()
            save_data()
            await call.answer("🧹 Хранилище очищено")
        elif action.startswith("mode_"):
            STATE["mode"] = action.split("_", 1)[1]
            mark_dirty()
            save_data()
            await call.answer(f"Режим: {MODE_LABEL.get(STATE['mode'])}")
        elif action.startswith("deladmin_"):
            uid = action.split("_", 1)[1]
            if int(uid) == SUPER_ADMIN_ID:
                await call.answer("👑 Супер-администратора снять нельзя", show_alert=True)
                return
            STATE["admins"].pop(uid, None)
            mark_dirty()
            save_data()
            await call.answer("➖ Администратор снят")
            text, kb = admin_admins(0)
            await safe_edit(call, text, kb)
            return
        elif action == "bcastsend":
            await call.answer("Отправляю…")
            note = await run_broadcast(call.from_user.id)
        elif action == "save":
            save_data()
            await call.answer("💾 Состояние сохранено")
        elif action == "testnotify":
            await bot.send_message(call.from_user.id, "🔔 Тестовое уведомление. Бот работает нормально.")
            await call.answer("Отправлено")
        else:
            await call.answer("Неизвестное действие", show_alert=True)
            return
    except Exception as e:
        log.exception("do:%s: %s", action, e)
        await call.answer("Произошла ошибка")
    if admin:
        text, kb = admin_home()
    else:
        text, kb = home_text(call.from_user.id), main_menu_kb(call.from_user.id)
    if note:
        text = note + "\n\n" + text
    await safe_edit(call, text, kb)


@dp.message()
async def on_private_message(message: Message):
    if not message.from_user:
        return
    uid = message.from_user.id
    remember_user(message.from_user)
    if is_blocked(uid):
        return
    pending = PENDING.get(uid)
    if not pending:
        if not mode_allows(uid):
            await message.answer("🛠 Идут технические работы. Бот скоро вернётся — спасибо за терпение.")
            return
        return
    mode = pending.get("mode")
    raw = (message.text or "").strip()
    try:
        if mode == "add_admin":
            if not raw.isdigit():
                await message.answer("⚠️ Нужен числовой ID. Попробуйте ещё раз или нажмите «Отмена».")
                return
            STATE["admins"].setdefault(raw, {p: False for p, _ in PERMS_META})
            PENDING.pop(uid, None)
            mark_dirty()
            save_data()
            text, kb = admin_admins(0)
            done = f"✅ Администратор <code>{raw}</code> добавлен. Выдайте ему нужные права."
            await message.answer(done, reply_markup=kb)
        elif mode == "add_block":
            if not raw.isdigit():
                await message.answer("⚠️ Нужен числовой ID. Попробуйте ещё раз или нажмите «Отмена».")
                return
            if int(raw) == SUPER_ADMIN_ID:
                await message.answer("👑 Супер-администратора заблокировать нельзя.")
                return
            user = STATE["users"].get(raw, {})
            STATE["blocked"][raw] = {"name": user.get("name") or "—", "ts": int(time.time())}
            PENDING.pop(uid, None)
            mark_dirty()
            save_data()
            text, kb = admin_blocks(0)
            await message.answer(f"🚫 Пользователь <code>{raw}</code> заблокирован.", reply_markup=kb)
        elif mode == "bc_text":
            STATE["bcast_draft"] = {"html": message_html(message, True)}
            PENDING.pop(uid, None)
            mark_dirty()
            rows = [
                [btn("🔗 Добавить кнопку", "br:addbtn", "primary")],
                [btn("✅ Отправить рассылку", "cf:bcastsend", "success")],
                [btn("✍️ Переписать", "br:new", "primary"), btn("❌ Отмена", "cancel", "danger")],
            ]
            await message.answer(
                "👁 <b>Предпросмотр</b>\n\nТак сообщение увидят получатели:\n\n"
                f"<blockquote>{STATE['bcast_draft']['html']}</blockquote>\n\n"
                f"Получателей: <b>{len(STATE['users'])}</b>",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
            )
        elif mode == "bc_btn":
            if "|" not in raw:
                await message.answer("⚠️ Формат: <code>Текст кнопки | https://ссылка</code>")
                return
            label, url = [p.strip() for p in raw.split("|", 1)]
            if not url.startswith("http"):
                await message.answer("⚠️ Ссылка должна начинаться с http:// или https://")
                return
            draft = STATE.setdefault("bcast_draft", {})
            draft["btn_text"], draft["btn_url"] = label, url
            PENDING.pop(uid, None)
            mark_dirty()
            rows = [
                [
                    btn("🔴 Красная", "br:color:danger", "danger"),
                    btn("🟢 Зелёная", "br:color:success", "success"),
                    btn("🔵 Синяя", "br:color:primary", "primary"),
                ],
                [btn("⚪️ Без цвета", "br:color:none")],
                [btn("✅ Отправить рассылку", "cf:bcastsend", "success"), btn("❌ Отмена", "cancel", "danger")],
            ]
            await message.answer(
                f"🔗 Кнопка добавлена: <b>{html.escape(label)}</b>\n\nВыберите цвет кнопки.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
            )
        elif mode == "btn_text":
            if not raw:
                await message.answer("⚠️ Отправьте текст надписи.")
                return
            pending["text"] = raw[:40]
            pending["mode"] = "btn_action"
            rows = [
                [btn("🔗 Открыть ссылку", "bt:act:url", "primary")],
                [btn("💬 Показать текст", "bt:act:text", "primary")],
                [btn("❌ Отмена", "cancel", "danger")],
            ]
            await message.answer(
                f"🧱 <b>Новая кнопка · шаг 2</b>\n\nНадпись: <b>{html.escape(raw[:40])}</b>\n\n"
                "Что должна делать кнопка?",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
            )
        elif mode == "btn_value":
            if pending.get("action") == "url" and not raw.startswith("http"):
                await message.answer("⚠️ Ссылка должна начинаться с http:// или https://")
                return
            pending["value"] = message_html(message, True) if pending.get("action") != "url" else raw
            pending["mode"] = "btn_color"
            rows = [
                [
                    btn("🔴 Красная", "bt:color:danger", "danger"),
                    btn("🟢 Зелёная", "bt:color:success", "success"),
                    btn("🔵 Синяя", "bt:color:primary", "primary"),
                ],
                [btn("⚪️ Без цвета", "bt:color:none")],
                [btn("❌ Отмена", "cancel", "danger")],
            ]
            await message.answer(
                "🧱 <b>Новая кнопка · шаг 4</b>\n\nВыберите цвет. "
                "Telegram поддерживает три цвета: красный, зелёный и синий.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
            )
    except Exception as e:
        log.exception("pending %s: %s", mode, e)
        await message.answer("⚠️ Что-то пошло не так. Попробуйте начать заново из меню.")


async def main():
    global BOT_USERNAME
    if not BOT_TOKEN:
        raise SystemExit("Вставьте BOT_TOKEN в первую строку файла bot.py")
    load_data()
    asyncio.create_task(autosave_loop())
    try:
        me = await bot.get_me()
        BOT_USERNAME = me.username or ""
        log.info("Бот @%s готов", BOT_USERNAME)
    except Exception as e:
        log.error("get_me: %s", e)
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
        log.info("Бот остановлен")
