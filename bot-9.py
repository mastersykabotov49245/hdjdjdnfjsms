BOT_TOKEN = "8893361270:AAF8kJgzBX_2P5BKwHtWl18slL-FNObQgUw"

import asyncio
import logging
import random
import sqlite3
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, F, BaseMiddleware, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram import types
from aiogram.types import (
    Message, CallbackQuery, BotCommand,
    BusinessConnection, BusinessMessagesDeleted
)
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import BufferedInputFile

import html as html_lib
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

storage = MemoryStorage()
dp = Dispatcher(storage=storage)

START_IMAGE_URL = "https://i.ibb.co/DgkfvHFx/Chat-GPT-Image-12-2026-12-22-58.png"
MAINTENANCE_IMAGE_URL = "https://i.ibb.co/jPZTN3bZ/Chat-GPT-Image-12-2026-23-18-34.png"
MAIN_ADMIN_ID = 47766426
CHANNEL_ID = "@VeloraSave"
PAGE_SIZE = 6

is_maintenance_mode = False


def is_super_admin(user_id: int) -> bool:
    try:
        return int(user_id) == get_main_admin()
    except Exception:
        logger.exception("is_super_admin: ошибка проверки")
        return False


class BotStates(StatesGroup):
    waiting_for_ticket = State()
    waiting_for_admin_reply = State()
    waiting_for_broadcast = State()
    waiting_for_add_admin = State()
    waiting_for_ban_id = State()
    waiting_for_unban_id = State()
    waiting_for_channel = State()
    waiting_for_btn_text = State()
    waiting_for_btn_value = State()
    waiting_for_cmd_trigger = State()
    waiting_for_cmd_desc = State()
    waiting_for_cmd_response = State()
    waiting_for_user_lookup = State()
    waiting_for_whitelist_add = State()
    waiting_for_whitelist_check = State()
    waiting_for_main_admin = State()
    waiting_for_section_photo = State()
    waiting_for_section_text = State()
    waiting_for_user_search = State()
    waiting_for_cmd_alias = State()
    waiting_for_cmd_description = State()
    waiting_for_ban_reason = State()

MEDIA_CATEGORIES = {
    "text": 'текстовое сообщение <tg-emoji emoji-id="5445267414562389170">🗑️</tg-emoji>',
    "photo": 'фотографию <tg-emoji emoji-id="5445267414562389170">🗑️</tg-emoji>',
    "video": 'видео <tg-emoji emoji-id="5445267414562389170">🗑️</tg-emoji>',
    "video_note": 'видеосообщение (кружок) <tg-emoji emoji-id="5445267414562389170">🗑️</tg-emoji>',
    "voice": 'голосовое сообщение <tg-emoji emoji-id="5445267414562389170">🗑️</tg-emoji>',
    "audio": 'аудиозапись <tg-emoji emoji-id="5445267414562389170">🗑️</tg-emoji>',
    "animation": 'GIF-анимацию <tg-emoji emoji-id="5445267414562389170">🗑️</tg-emoji>',
    "document": 'документ/файл <tg-emoji emoji-id="5445267414562389170">🗑️</tg-emoji>',
    "sticker": 'стикер <tg-emoji emoji-id="5445267414562389170">🗑️</tg-emoji>'
}

# ==========================================
#              УТИЛИТЫ И КЛАВИАТУРЫ
# ==========================================

async def is_subscribed(bot: Bot, user_id: int) -> bool:
    if is_super_admin(user_id) or is_bot_admin(user_id):
        return True
    missing = await get_missing_channels(bot, user_id)
    return not missing


async def get_missing_channels(bot: Bot, user_id: int) -> list:
    if is_super_admin(user_id) or is_bot_admin(user_id):
        return []
    if get_flag("subs_enabled", "1") != "1":
        return []
    channels = get_req_channels()
    if not channels:
        channels = [{"chat_id": CHANNEL_ID, "title": "Новостной Канал", "url": "https://t.me/VeloraSave"}]
    missing = []
    for ch in channels:
        try:
            member = await bot.get_chat_member(chat_id=ch["chat_id"], user_id=user_id)
            if member.status not in ["member", "administrator", "creator"]:
                missing.append(ch)
        except TelegramBadRequest as e:
            logger.warning(f"getChatMember {ch['chat_id']}: {e}")
            set_flag("subs_last_error", f"{ch['chat_id']}: {e}")
        except Exception as e:
            logger.warning(f"getChatMember {ch['chat_id']}: {e}")
            set_flag("subs_last_error", f"{ch['chat_id']}: {e}")
    return missing

def is_bot_admin(user_id: int) -> bool:
    if is_super_admin(user_id):
        return True
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM extra_admins WHERE user_id = ?", (user_id,))
        res = cursor.fetchone()
        conn.close()
        return res is not None
    except Exception:
        return False

def create_premium_button(text: str, callback_data: str = None, url: str = None, switch_inline_query_current_chat: str = None, style: str = "primary", icon_custom_emoji_id: str = None):
    data = {"text": text}
    if callback_data: data["callback_data"] = callback_data
    if url: data["url"] = url
    if switch_inline_query_current_chat is not None: data["switch_inline_query_current_chat"] = switch_inline_query_current_chat
    if style: data["style"] = style
    if icon_custom_emoji_id: data["icon_custom_emoji_id"] = icon_custom_emoji_id
    return types.InlineKeyboardButton(**data)

def get_sub_keyboard(channels: list = None) -> types.InlineKeyboardMarkup:
    rows = []
    if channels:
        extra_index = 0
        for ch in channels:
            raw_id = str(ch.get("chat_id") or "")
            if raw_id.lower() in ("@velorasave", CHANNEL_ID.lower()):
                label = "Новостной Канал"
            else:
                extra_index += 1
                label = f"Доп канал #{extra_index}"
            rows.append([create_premium_button(
                text=label,
                url=ch.get("url") or "https://t.me/VeloraSave",
                style="primary",
                icon_custom_emoji_id=CHANNEL_EMOJI
            )])
    else:
        rows.append([create_premium_button(text="Новостной Канал", url="https://t.me/VeloraSave", style="primary", icon_custom_emoji_id="5427168083074628963")])
    rows.append([create_premium_button(text="Я подписался", callback_data="check_sub_button", style="success", icon_custom_emoji_id="5397916757333654639")])
    return types.InlineKeyboardMarkup(inline_keyboard=rows)

def get_main_keyboard(user_id: int) -> types.InlineKeyboardMarkup:
    row1 = [types.InlineKeyboardButton(
        text="📋 Скопировать username бота",
        copy_text=types.CopyTextButton(text=BOT_PUBLIC_USERNAME)
    )]
    row2 = [
        create_premium_button(text="Профиль", callback_data="open_profile", style="primary", icon_custom_emoji_id="5341715473882955310"),
        create_premium_button(text="Настройки", callback_data="open_settings", style="primary", icon_custom_emoji_id="5341715473882955310")
    ]
    row3 = [
        create_premium_button(text="Новостной Канал", url="https://t.me/VeloraSave", style="primary", icon_custom_emoji_id="5427168083074628963"),
        create_premium_button(text="Инструкция", url="https://teletype.in/@velorahelp/GaidPoYstanovkeVelora", style="primary", icon_custom_emoji_id="5305265301917549162")
    ]
    row4 = [create_premium_button(text="Тех. Поддержка", callback_data="open_support", style="danger", icon_custom_emoji_id="5443038326535759644")]
    
    keyboard_rows = [row1, row2, row3, row4]

    keyboard_rows.append([
        create_premium_button(text="Команды", callback_data="open_commands", style="primary",
                              icon_custom_emoji_id="5434144690511290129"),
        create_premium_button(text="🎮 Крестики-нолики", callback_data="tttb_new",
                              style="success")
    ])

    custom_row = []
    for b in get_custom_buttons("main"):
        if b["action"] == "url":
            custom_row.append(create_premium_button(text=b["text"], url=b["value"], style=b["color"] or None))
        else:
            custom_row.append(create_premium_button(text=b["text"], callback_data=f"cbtn_{b['btn_id']}", style=b["color"] or None))
        if len(custom_row) == 2:
            keyboard_rows.append(custom_row)
            custom_row = []
    if custom_row:
        keyboard_rows.append(custom_row)

    if get_custom_buttons("extra"):
        keyboard_rows.append([create_premium_button(text="Доп. меню", callback_data="open_custom_menu", style="primary", icon_custom_emoji_id="5341715473882955310")])

    if is_bot_admin(user_id):
        keyboard_rows.append([create_premium_button(text="Админ-Панель", callback_data="open_admin_panel", style="success", icon_custom_emoji_id="5386399931378440814")])
        
    return types.InlineKeyboardMarkup(inline_keyboard=keyboard_rows)

def get_back_keyboard() -> types.InlineKeyboardMarkup:
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [create_premium_button(text="Назад в главное меню", callback_data="back_to_main", style="primary", icon_custom_emoji_id="5352759161945867747")]
    ])

def get_settings_keyboard(notifications_enabled: bool) -> types.InlineKeyboardMarkup:
    emoji = "5206607081334906820" if notifications_enabled else "5210952531676504517"
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [create_premium_button(text="Оповещения о новых юзерах", callback_data="toggle_notifications", style="primary", icon_custom_emoji_id=emoji)],
        [create_premium_button(text="Назад в главное меню", callback_data="back_to_main", style="primary")]
    ])

def get_admin_keyboard() -> types.InlineKeyboardMarkup:
    row1 = [
        create_premium_button(text="Рассылка", callback_data="admin_broadcast", style="primary", icon_custom_emoji_id="5388632425314140043"),
        create_premium_button(text="Статистика", callback_data="admin_stats", style="primary", icon_custom_emoji_id="5449872877929127395")
    ]
    row2 = [
        create_premium_button(text="Тикеты", callback_data="admin_tickets_list", style="primary", icon_custom_emoji_id="5434144690511290129"),
        create_premium_button(text="Бан-Система", callback_data="admin_ban_menu", style="danger", icon_custom_emoji_id="5467479495063657163")
    ]
    row3 = [
        create_premium_button(text="Добавить Админа", callback_data="admin_add_moderator", style="success", icon_custom_emoji_id="5235616308359359800"),
        create_premium_button(text="Права Админов", callback_data="admin_rights_list", style="primary", icon_custom_emoji_id="5443038326535759644")
    ]
    
    m_status_text = "Выключить ТО" if is_maintenance_mode else "Включить ТО"
    row4 = [create_premium_button(text=m_status_text, callback_data="admin_toggle_maintenance", style="primary", icon_custom_emoji_id="5362079447136610876")]

    row_new1 = [
        create_premium_button(text="Дашборд", callback_data="adm_dash", style="primary", icon_custom_emoji_id="5449872877929127395"),
        create_premium_button(text="Пользователи", callback_data="adm_users", style="primary", icon_custom_emoji_id="5341715473882955310")
    ]
    row_new2 = [
        create_premium_button(text="Обяз. подписка", callback_data="adm_subs", style="primary", icon_custom_emoji_id="5440660757194744323"),
        create_premium_button(text="Режим работы", callback_data="adm_mode", style="danger", icon_custom_emoji_id="5362079447136610876")
    ]
    row_new3 = [
        create_premium_button(text="Кнопки", callback_data="adm_btns", style="success", icon_custom_emoji_id="5870483144100023800"),
        create_premium_button(text="Команды", callback_data="adm_cmds", style="success", icon_custom_emoji_id="5434144690511290129")
    ]
    row_new4 = [
        create_premium_button(text="👁 Whitelist", callback_data="adm_whitelist", style="primary"),
        create_premium_button(text="🔧 Функции", callback_data="adm_features", style="primary")
    ]
    row_new4b = [
        create_premium_button(text="🖼 Разделы", callback_data="adm_sections", style="primary"),
        create_premium_button(text="📈 Точная статистика", callback_data="adm_fullstats",
                              style="primary")
    ]
    row_new4c = [
        create_premium_button(text="🧩 Настройка команд", callback_data="adm_cmdedit",
                              style="primary")
    ]
    row_new5 = [
        create_premium_button(text="👑 Главный админ", callback_data="adm_mainadmin", style="danger")
    ]

    row5 = [create_premium_button(text="В главное меню", callback_data="back_to_main", style="primary", icon_custom_emoji_id="5352759161945867747")]

    return types.InlineKeyboardMarkup(
        inline_keyboard=[row1, row2, row3, row_new1, row_new2, row_new3,
                         row_new4, row_new4b, row_new4c, row_new5, row4, row5]
    )

def get_admin_sub_navigation_keyboard() -> types.InlineKeyboardMarkup:
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [create_premium_button(text="Назад в админ панель", callback_data="open_admin_panel", style="primary", icon_custom_emoji_id="5235616308359359800")],
        [create_premium_button(text="Назад в главное меню", callback_data="back_to_main", style="primary", icon_custom_emoji_id="5352759161945867747")]
    ])

# ==========================================
#          ХЭНДЛЕРЫ КНОПОК ПОЛЬЗОВАТЕЛЯ
# ==========================================

@dp.callback_query(F.data == "check_sub_button")
async def check_sub_button_handler(callback: CallbackQuery, bot: Bot):
    if await is_subscribed(bot, callback.from_user.id):
        await callback.answer("🎉 Спасибо за подписку! Доступ открыт.", show_alert=True)
        text, reply_markup = get_main_menu_data(callback.from_user.id)
        try:
            await callback.message.edit_media(
                media=types.InputMediaPhoto(media=START_IMAGE_URL, caption=text, parse_mode="HTML"),
                reply_markup=reply_markup
            )
        except Exception:
            await callback.message.answer_photo(photo=START_IMAGE_URL, caption=text, reply_markup=reply_markup, parse_mode="HTML")
    else:
        missing = await get_missing_channels(bot, callback.from_user.id)
        await callback.answer(
            "❌ Вы всё ещё не подписались на все обязательные каналы!", show_alert=True)
        try:
            await callback.message.edit_caption(
                caption=missing_channels_text(missing, repeated=True),
                reply_markup=missing_channels_keyboard(missing), parse_mode="HTML")
        except Exception:
            logger.exception("check_sub_button: не удалось обновить экран")

@dp.callback_query(F.data == "open_profile")
async def open_profile(callback: CallbackQuery):
    robot_emoji = "5352759161945867747"
    user_id = callback.from_user.id
    
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT created_at FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    
    time_str = "неизвестно"
    if row and row[0]:
        try:
            reg_time = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
            diff = datetime.now() - reg_time
            days = diff.days
            hours = diff.seconds // 3600
            minutes = (diff.seconds % 3600) // 60
            
            time_parts = []
            if days > 0: time_parts.append(f"{days} д.")
            if hours > 0 or days > 0: time_parts.append(f"{hours} ч.")
            time_parts.append(f"{minutes} мин.")
            time_str = " ".join(time_parts)
        except Exception:
            time_str = "1 мин."
    else:
        time_str = "1 мин."

    profile_text = (
        f'<tg-emoji emoji-id="{robot_emoji}">🤖</tg-emoji> <b>Ваш личный профиль VeloraSave</b>\n\n'
        f'👤 <b>Ваш Telegram ID:</b> <code>{user_id}</code>\n'
        f'⏳ <b>Вы с нами уже:</b> <code>{time_str}</code>\n\n'
        f'Тип аккаунта: Данные синхронизированы.'
    )
    
    try:
        await callback.message.edit_media(
            media=types.InputMediaPhoto(media=START_IMAGE_URL, caption=profile_text, parse_mode="HTML"),
            reply_markup=get_back_keyboard()
        )
    except Exception:
        await callback.message.edit_reply_markup(reply_markup=get_back_keyboard())
    await callback.answer()

@dp.callback_query(F.data == "open_settings")
async def open_settings(callback: CallbackQuery):
    settings_emoji = "5465363406604245713"
    status = get_notify_status(callback.from_user.id)
    settings_text = f'<tg-emoji emoji-id="{settings_emoji}">⚙️</tg-emoji> <b>Настройки уведомлений</b>'
    
    try:
        await callback.message.edit_media(
            media=types.InputMediaPhoto(media=START_IMAGE_URL, caption=settings_text, parse_mode="HTML"),
            reply_markup=get_settings_keyboard(status)
        )
    except Exception:
        await callback.message.edit_reply_markup(reply_markup=get_settings_keyboard(status))
    await callback.answer()

@dp.callback_query(F.data == "toggle_notifications")
async def toggle_notifications(callback: CallbackQuery):
    toggle_notify_status(callback.from_user.id)
    status = get_notify_status(callback.from_user.id)
    try: 
        await callback.message.edit_reply_markup(reply_markup=get_settings_keyboard(status))
    except Exception: 
        pass
    await callback.answer(text="Статус изменен.")

@dp.callback_query(F.data == "open_support")
async def open_support(callback: CallbackQuery, state: FSMContext):
    if is_user_banned(callback.from_user.id):
        await callback.answer("🔒 Вы заблокированы в системе поддержки бота.", show_alert=True)
        return

    await state.set_state(BotStates.waiting_for_ticket)
    
    support_text = (
        "💬 <b>Служба поддержки VeloraSave</b>\n\n"
        "Возникли технические неполадки, нашли баг или хотите предложить идею для улучшения бота?\n\n"
        "ℹ️ <b>Вы можете обратиться за помощью прямо здесь!</b>\n"
        "Просто отправьте ваше обращение (можно с фото или скриншотом) в ответном сообщении ниже.\n"
        "Мы рассмотрим его и ответим вам в ближайшее время."
    )
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [create_premium_button(text="Назад в главное меню", callback_data="back_to_main", style="primary", icon_custom_emoji_id="5352759161945867747")]
    ])
    
    try:
        await callback.message.edit_text(text=support_text, parse_mode="HTML", reply_markup=keyboard)
    except Exception:
        try:
            await callback.message.edit_caption(caption=support_text, reply_markup=keyboard, parse_mode="HTML")
        except Exception:
            await callback.message.answer(text=support_text, parse_mode="HTML", reply_markup=keyboard)
        
    await callback.answer()

@dp.message(BotStates.waiting_for_ticket)
async def process_ticket_submission(message: Message, state: FSMContext, bot: Bot):
    if is_user_banned(message.from_user.id):
        await state.clear()
        await message.answer("❌ Вы не можете отправлять тикеты, так как заблокированы.")
        return

    await state.clear()
    emoji_ticket = "5456140674028019486"
    
    username = message.from_user.username or "None"
    user_id = message.from_user.id
    text_content = message.text or message.caption or "Без текста (Медиафайл)"
    file_id = message.photo[-1].file_id if message.photo else None
    
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO support_tickets (user_id, username, text_content, file_id, created_at) VALUES (?, ?, ?, ?, ?)",
        (user_id, username, text_content, file_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    conn.commit()
    conn.close()

    await message.answer(text=f"<b>Заявка отправлена <tg-emoji emoji-id=\"{emoji_ticket}\">📨</tg-emoji></b>\nОжидайте ответа администрации.", parse_mode="HTML", reply_markup=get_back_keyboard())

@dp.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()

    if not gate_passed(callback.from_user.id):
        text, reply_markup = gate_text(), gate_keyboard()
        photo = section_photo("connect")
    else:
        text, reply_markup = get_main_menu_data(callback.from_user.id)
        photo = section_photo("main")

    try:
        await callback.message.edit_media(
            media=types.InputMediaPhoto(media=photo, caption=text, parse_mode="HTML"),
            reply_markup=reply_markup
        )
    except Exception:
        try:
            await callback.message.edit_caption(caption=text, reply_markup=reply_markup, parse_mode="HTML")
        except Exception:
            await callback.message.answer_photo(photo=photo, caption=text, reply_markup=reply_markup, parse_mode="HTML")
            
    await callback.answer()

# ==========================================
#             ЛОГИКА БАЗЫ ДАННЫХ
# ==========================================

def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, created_at TEXT)")
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            chat_id INTEGER, 
            message_id INTEGER, 
            from_id INTEGER, 
            media_type TEXT, 
            content TEXT, 
            PRIMARY KEY (chat_id, message_id)
        )
    """)
    
    cursor.execute("CREATE TABLE IF NOT EXISTS known_contacts (user_id INTEGER, contact_id INTEGER, PRIMARY KEY (user_id, contact_id))")
    cursor.execute("CREATE TABLE IF NOT EXISTS bot_settings (user_id INTEGER PRIMARY KEY, new_user_notify INTEGER)")
    cursor.execute("CREATE TABLE IF NOT EXISTS business_connections (user_id INTEGER PRIMARY KEY, active INTEGER DEFAULT 1)")
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS extra_admins (
            user_id INTEGER PRIMARY KEY,
            can_broadcast INTEGER DEFAULT 0,
            can_channels INTEGER DEFAULT 0,
            can_stats INTEGER DEFAULT 0,
            can_admins INTEGER DEFAULT 0,
            can_tickets INTEGER DEFAULT 0,
            can_ban INTEGER DEFAULT 0
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS support_tickets (
            ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            text_content TEXT,
            file_id TEXT,
            created_at TEXT
        )
    """)
    cursor.execute("CREATE TABLE IF NOT EXISTS ticket_blacklist (user_id INTEGER PRIMARY KEY, username TEXT, banned_at TEXT)")

    cursor.execute("CREATE TABLE IF NOT EXISTS bot_flags (key TEXT PRIMARY KEY, value TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS req_channels (chat_id TEXT PRIMARY KEY, title TEXT, url TEXT, added_at TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS global_bans (user_id INTEGER PRIMARY KEY, username TEXT, banned_at TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS muted_chats (owner_id INTEGER, chat_id INTEGER, muted_at TEXT, PRIMARY KEY (owner_id, chat_id))")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS msg_log (
            row_id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER,
            chat_id INTEGER,
            message_id INTEGER,
            from_id INTEGER,
            direction TEXT,
            media_type TEXT,
            text_content TEXT,
            created_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS deleted_log (
            row_id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER,
            chat_id INTEGER,
            message_id INTEGER,
            from_id INTEGER,
            media_type TEXT,
            text_content TEXT,
            deleted_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS edited_log (
            row_id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER,
            chat_id INTEGER,
            message_id INTEGER,
            from_id INTEGER,
            old_text TEXT,
            new_text TEXT,
            edited_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS custom_buttons (
            btn_id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT,
            color TEXT,
            action TEXT,
            value TEXT,
            target TEXT,
            created_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS custom_commands (
            cmd_id INTEGER PRIMARY KEY AUTOINCREMENT,
            trigger TEXT UNIQUE,
            description TEXT,
            response TEXT,
            created_at TEXT
        )
    """)

    for column, ddl in [
        ("first_name", "ALTER TABLE users ADD COLUMN first_name TEXT"),
        ("last_name", "ALTER TABLE users ADD COLUMN last_name TEXT"),
        ("username", "ALTER TABLE users ADD COLUMN username TEXT"),
        ("lang", "ALTER TABLE users ADD COLUMN lang TEXT"),
        ("is_premium", "ALTER TABLE users ADD COLUMN is_premium INTEGER DEFAULT 0"),
        ("last_active", "ALTER TABLE users ADD COLUMN last_active TEXT")
    ]:
        try:
            cursor.execute(ddl)
        except Exception:
            pass

    for ddl in [
        "ALTER TABLE extra_admins ADD COLUMN can_maintenance INTEGER DEFAULT 0",
        "ALTER TABLE extra_admins ADD COLUMN can_buttons INTEGER DEFAULT 0",
        "ALTER TABLE extra_admins ADD COLUMN can_chats INTEGER DEFAULT 0"
    ]:
        try:
            cursor.execute(ddl)
        except Exception:
            pass

    conn.commit()
    conn.close()

def log_user(user_id: int, user=None):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("INSERT OR IGNORE INTO users (user_id, created_at) VALUES (?, ?)", (user_id, now_str))
    if user is not None:
        cursor.execute(
            "UPDATE users SET first_name=?, last_name=?, username=?, lang=?, is_premium=?, last_active=? WHERE user_id=?",
            (
                getattr(user, "first_name", None),
                getattr(user, "last_name", None),
                getattr(user, "username", None),
                getattr(user, "language_code", None),
                1 if getattr(user, "is_premium", False) else 0,
                now_str,
                user_id
            )
        )
    else:
        cursor.execute("UPDATE users SET last_active=? WHERE user_id=?", (now_str, user_id))
    conn.commit()
    conn.close()

def log_business_status(user_id: int, active: int):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO business_connections (user_id, active) VALUES (?, ?)", (user_id, active))
    conn.commit()
    conn.close()

def get_users_count() -> int:
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_active_business_count() -> int:
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM business_connections WHERE active = 1")
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_all_users():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = [row[0] for row in cursor.fetchall()]
    conn.close()
    return users

def is_admin(user_id: int) -> bool:
    if is_super_admin(user_id): return True
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM extra_admins WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return res is not None

def check_permission(user_id: int, perm_name: str) -> bool:
    if is_super_admin(user_id): return True
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute(f"SELECT {perm_name} FROM extra_admins WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return bool(row[0]) if row else False

def add_extra_admin(user_id: int):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR IGNORE INTO extra_admins 
        (user_id, can_broadcast, can_channels, can_stats, can_admins, can_tickets, can_ban) 
        VALUES (?, 0, 0, 0, 0, 0, 0)
    """, (user_id,))
    conn.commit()
    conn.close()

def toggle_permission(user_id: int, perm_name: str):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute(f"SELECT {perm_name} FROM extra_admins WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if row:
        new_val = 0 if row[0] else 1
        cursor.execute(f"UPDATE extra_admins SET {perm_name} = ? WHERE user_id = ?", (new_val, user_id))
    conn.commit()
    conn.close()

def remove_extra_admin(user_id: int):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM extra_admins WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def get_extra_admins_list():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, can_broadcast, can_channels, can_stats, can_admins, can_tickets, can_ban FROM extra_admins")
    rows = cursor.fetchall()
    conn.close()
    return rows

def is_user_banned(user_id: int) -> bool:
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM ticket_blacklist WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return res is not None

def ban_user_in_db(user_id: int, username: str):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("INSERT OR REPLACE INTO ticket_blacklist (user_id, username, banned_at) VALUES (?, ?, ?)", (user_id, username, now_str))
    conn.commit()
    conn.close()

def get_banned_count() -> int:
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM ticket_blacklist")
    count = cursor.fetchone()[0]
    conn.close()
    return count

def save_message(chat_id, message_id, from_id, media_type, content):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO messages (chat_id, message_id, from_id, media_type, content) VALUES (?, ?, ?, ?, ?)", 
                   (chat_id, message_id, from_id, media_type, content))
    conn.commit()
    conn.close()

def get_message(chat_id, message_id):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT media_type, content, from_id FROM messages WHERE chat_id = ? AND message_id = ?", (chat_id, message_id))
    row = cursor.fetchone()
    conn.close()
    return {"media_type": row[0], "content": row[1], "from_id": row[2]} if row else None

def check_and_add_contact(user_id: int, contact_id: int) -> bool:
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM known_contacts WHERE user_id = ? AND contact_id = ?", (user_id, contact_id))
    exists = cursor.fetchone()
    if not exists:
        cursor.execute("INSERT INTO known_contacts (user_id, contact_id) VALUES (?, ?)", (user_id, contact_id))
        conn.commit()
        conn.close()
        return True
    conn.close()
    return False

def get_notify_status(user_id: int) -> bool:
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT new_user_notify FROM bot_settings WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return bool(row[0]) if row else True

def toggle_notify_status(user_id: int):
    current = get_notify_status(user_id)
    new_val = 0 if current else 1
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO bot_settings (user_id, new_user_notify) VALUES (?, ?)", (user_id, new_val))
    conn.commit()
    conn.close()

init_db()

def get_main_menu_data(user_id: int):
    emoji_robot = "5289650686319929628"
    text = (
        f'<tg-emoji emoji-id="{emoji_robot}">🤖</tg-emoji> <b>Главное меню VeloraSave</b>\n\n'
        "Бот сохраняет удаленные сообщения вашего собеседника :).\n"
    )
    return text, get_main_keyboard(user_id)

# ==========================================
#                  МИДДЛВАРИ
# ==========================================

class MessageGuardMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: Message, data: dict):
        if not event.from_user:
            return await handler(event, data)
            
        user_id = event.from_user.id
        bot = data["bot"]
        
        if is_globally_banned(user_id):
            return

        missing = await get_missing_channels(bot, user_id)
        if missing:
            if event.chat.type == "private":
                sub_text = missing_channels_text(missing)
                try:
                    await event.answer_photo(photo=section_photo("subscribe"),
                                             caption=sub_text,
                                             reply_markup=missing_channels_keyboard(missing),
                                             parse_mode="HTML")
                except Exception:
                    logger.exception("подписка: не удалось отправить фото")
                    await event.answer(text=sub_text,
                                       reply_markup=missing_channels_keyboard(missing),
                                       parse_mode="HTML")
            return

        if get_bot_mode() == "off" and not is_bot_admin(user_id):
            off_emoji = "5377583454441445203"
            off_text = f'<tg-emoji emoji-id="{off_emoji}">🛠️</tg-emoji> <b>Бот временно отключён администрацией.</b>\n\nПопробуйте зайти немного позже.'
            try: await event.answer_photo(photo=MAINTENANCE_IMAGE_URL, caption=off_text, parse_mode="HTML")
            except Exception: pass
            return

        if get_bot_mode() == "maint" and not is_bot_admin(user_id):
            m_emoji = "5377583454441445203"
            m_text = f'<tg-emoji emoji-id="{m_emoji}">🛠️</tg-emoji> <b>Бот находится на техническом обслуживании.</b>\n\nПожалуйста, подождите завершения плановых работ, скоро мы вернемся в строй!'
            try: await event.answer_photo(photo=MAINTENANCE_IMAGE_URL, caption=m_text, parse_mode="HTML")
            except Exception: pass
            return
        return await handler(event, data)

class CallbackGuardMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: CallbackQuery, data: dict):
        if not event.from_user:
            return await handler(event, data)

        user_id = event.from_user.id
        bot = data["bot"]

        if event.data == "check_sub_button":
            return await handler(event, data)

        if is_globally_banned(user_id):
            await event.answer("🔒 Доступ к боту закрыт.", show_alert=True)
            return

        missing = await get_missing_channels(bot, user_id)
        if missing:
            await event.answer("❌ Вы отписались от обязательного канала.", show_alert=True)
            sub_text = missing_channels_text(missing, repeated=True)
            try:
                await event.message.edit_caption(
                    caption=sub_text,
                    reply_markup=missing_channels_keyboard(missing), parse_mode="HTML")
            except Exception:
                logger.exception("подписка: не удалось обновить экран")
            return

        if get_bot_mode() == "off" and not is_bot_admin(user_id):
            await event.answer("⚠️ Бот временно отключён администрацией.", show_alert=True)
            return

        if get_bot_mode() == "maint" and not is_bot_admin(user_id):
            m_emoji = "5377583454441445203"
            m_text = f'<tg-emoji emoji-id="{m_emoji}">🛠️</tg-emoji> <b>Бот находится на техническом обслуживании.</b>\n\nПожалуйста, подождите завершения плановых работ, скоро мы вернемся в строй!'
            try:
                await event.answer("⚠️ Ведутся технические работы!", show_alert=True)
                await event.message.edit_caption(caption=m_text, reply_markup=None, parse_mode="HTML")
            except Exception: pass
            return
        return await handler(event, data)

dp.message.middleware(MessageGuardMiddleware())
dp.callback_query.middleware(CallbackGuardMiddleware())

@dp.message(CommandStart())
async def cmd_start(message: Message, bot: Bot):
    log_user(message.from_user.id, message.from_user)
    if not gate_passed(message.from_user.id):
        try:
            await message.answer_photo(photo=section_photo("connect"), caption=gate_text(),
                                       reply_markup=gate_keyboard(), parse_mode="HTML")
        except Exception:
            logger.exception("cmd_start: не удалось показать экран подключения")
            await message.answer(gate_text(), reply_markup=gate_keyboard(), parse_mode="HTML")
        return
    text, reply_markup = get_main_menu_data(message.from_user.id)
    await message.answer_photo(photo=section_photo("main"), caption=text,
                               reply_markup=reply_markup, parse_mode="HTML")

# ==========================================
#           АДМИНИСТРАТИВНАЯ ПАНЕЛЬ
# ==========================================

@dp.callback_query(F.data == "open_admin_panel")
async def open_admin_panel(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): 
        await callback.answer("🔒 Нет доступа!", show_alert=True)
        return
    admin_emoji = "5235616308359359800"
    admin_text = f'<tg-emoji emoji-id="{admin_emoji}">⚙️</tg-emoji> <b>Панель управления VeloraSave</b>'
    try:
        await callback.message.edit_media(
            media=types.InputMediaPhoto(media=START_IMAGE_URL, caption=admin_text, parse_mode="HTML"),
            reply_markup=get_admin_keyboard()
        )
    except Exception:
        await callback.message.edit_reply_markup(reply_markup=get_admin_keyboard())
    await callback.answer()

@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if not check_permission(callback.from_user.id, "can_stats"):
        await callback.answer("🔒 Нет прав!", show_alert=True)
        return
    stats_emoji = "5449872877929127395"
    all_users = get_users_count()
    business_users = get_active_business_count()
    banned_support = get_banned_count()
    
    text = (
        f'<tg-emoji emoji-id="{stats_emoji}">📈</tg-emoji> <b>Статистика бота:</b>\n\n'
        f'• Всего юзеров в БД: <b>{all_users}</b>\n'
        f'• Активных бизнес-аккаунтов: <b>{business_users}</b>\n'
        f'• Забанено в тех. поддержке: <b>{banned_support}</b>'
    )
    try: await callback.message.edit_caption(caption=text, reply_markup=get_admin_sub_navigation_keyboard(), parse_mode="HTML")
    except Exception: pass
    await callback.answer()

@dp.callback_query(F.data == "admin_tickets_list")
async def admin_tickets_list(callback: CallbackQuery):
    if not check_permission(callback.from_user.id, "can_tickets"):
        await callback.answer("🔒 У вас нет прав для просмотра тикетов!", show_alert=True)
        return
        
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT ticket_id, username, user_id FROM support_tickets ORDER BY ticket_id DESC LIMIT 15")
    rows = cursor.fetchall()
    conn.close()
    
    t_list_emoji = "5434144690511290129"
    text = f'<tg-emoji emoji-id="{t_list_emoji}">📂</tg-emoji> <b>Список входящих тикетов (Последние 15):</b>\n\nНажмите на кнопку тикета, чтобы прочитать и ответить.'
    keyboard_rows = []
    for r in rows:
        label = f"Тикет #{r[0]} | @{r[1]} ({r[2]})" if r[1] != "None" else f"Тикет #{r[0]} | ID: {r[2]}"
        keyboard_rows.append([create_premium_button(text=label, callback_data=f"view_ticket_{r[0]}", style="primary")])
        
    keyboard_rows.append([create_premium_button(text="Назад в админку", callback_data="open_admin_panel", style="success", icon_custom_emoji_id="5235616308359359800")])
    try: await callback.message.edit_caption(caption=text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard_rows), parse_mode="HTML")
    except Exception: pass
    await callback.answer()

@dp.callback_query(F.data.startswith("view_ticket_"))
async def view_ticket_single(callback: CallbackQuery):
    if not check_permission(callback.from_user.id, "can_tickets"): return
    ticket_id = int(callback.data.split("_")[2])
    
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, text_content, file_id, created_at FROM support_tickets WHERE ticket_id = ?", (ticket_id,))
    ticket = cursor.fetchone()
    conn.close()
    
    if not ticket:
        await callback.answer("Тикет не найден в базе данных.", show_alert=True)
        return
        
    u_id, u_name, content, f_id, date = ticket
    info_text = (
        f"✉️ <b>Детали обращения #{ticket_id}</b>\n\n"
        f"<b>Отправитель:</b> @{u_name} (ID: <code>{u_id}</code>)\n"
        f"<b>Дата отправки:</b> <code>{date}</code>\n"
        f"<b>Содержимое:</b>\n<i>{content}</i>"
    )
    
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [create_premium_button(text="Ответить пользователю", callback_data=f"reply_ticket_{u_id}_{ticket_id}", style="success")],
        [create_premium_button(text="Забанить пользователя", callback_data=f"quick_ban_{u_id}_{u_name}", style="danger", icon_custom_emoji_id="5467479495063657163")],
        [create_premium_button(text="Удалить тикет", callback_data=f"del_ticket_{ticket_id}", style="danger")],
        [create_premium_button(text="Назад к списку", callback_data="admin_tickets_list", style="primary")]
    ])
    
    try:
        if f_id:
            await callback.message.delete()
            await callback.message.answer_photo(photo=f_id, caption=info_text, reply_markup=kb, parse_mode="HTML")
        else:
            await callback.message.edit_caption(caption=info_text, reply_markup=kb, parse_mode="HTML")
    except Exception: pass
    await callback.answer()

@dp.callback_query(F.data.startswith("reply_ticket_"))
async def setup_admin_reply(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    await state.update_data(reply_to=int(parts[2]), t_id=int(parts[3]))
    
    await state.set_state(BotStates.waiting_for_admin_reply)
    await callback.message.answer("✍️ <b>Введите текст ответа для отправки пользователю:</b>", parse_mode="HTML")
    await callback.answer()

@dp.message(BotStates.waiting_for_admin_reply)
async def send_admin_reply_to_user(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    target_user_id, ticket_id = data.get("reply_to"), data.get("t_id")
    await state.clear()
    
    if target_user_id:
        try:
            await bot.send_message(chat_id=target_user_id, text=f"🔔 <b>Ответ администрации VeloraSave:</b>\n\n{message.text}", parse_mode="HTML")
            conn = sqlite3.connect("database.db")
            cursor = conn.cursor()
            cursor.execute("DELETE FROM support_tickets WHERE ticket_id = ?", (ticket_id,))
            conn.commit()
            conn.close()
            await message.answer("✅ Ответ успешно отправлен, тикет закрыт и удален из списка.")
        except Exception: 
            await message.answer("❌ Не удалось доставить сообщение. Возможно, бот заблокирован пользователем.")

@dp.callback_query(F.data.startswith("del_ticket_"))
async def delete_ticket_action(callback: CallbackQuery):
    ticket_id = int(callback.data.split("_")[2])
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM support_tickets WHERE ticket_id = ?", (ticket_id,))
    conn.commit()
    conn.close()
    await callback.answer("Тикет удален.")
    await admin_tickets_list(callback)

@dp.callback_query(F.data == "admin_ban_menu")
async def admin_ban_menu(callback: CallbackQuery):
    if not check_permission(callback.from_user.id, "can_ban"):
        await callback.answer("🔒 У вас нет прав на управление блокировками!", show_alert=True)
        return
    ban_main_emoji = "5467479495063657163"
    text = f'<tg-emoji emoji-id="{ban_main_emoji}">🚫</tg-emoji> <b>Управление блокировками тикетов</b>\n\nЗдесь вы можете заблокировать или разблокировать доступ спамеров к разделу техподдержки.'
    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [create_premium_button(text="Забанить по ID", callback_data="ban_user_action", style="danger", icon_custom_emoji_id="5467479495063657163")],
        [create_premium_button(text="Разбанить по ID", callback_data="unban_user_action", style="success")],
        [create_premium_button(text="Список забаненных", callback_data="banned_users_list", style="primary", icon_custom_emoji_id="5233658378797994515")],
        [create_premium_button(text="Назад в админку", callback_data="open_admin_panel", style="primary")]
    ])
    try: await callback.message.edit_caption(caption=text, reply_markup=kb, parse_mode="HTML")
    except Exception: pass
    await callback.answer()

@dp.callback_query(F.data == "ban_user_action")
async def ban_user_action(callback: CallbackQuery, state: FSMContext):
    if not check_permission(callback.from_user.id, "can_ban"): return
    await callback.message.answer("✏️ <b>Введите Telegram ID пользователя для блокировки:</b>", parse_mode="HTML")
    await state.set_state(BotStates.waiting_for_ban_id)
    await callback.answer()

@dp.message(BotStates.waiting_for_ban_id)
async def process_ban_input(message: Message, state: FSMContext):
    if not check_permission(message.from_user.id, "can_ban"): return
    await state.clear()
    try:
        target_id = int(message.text.strip())
        ban_user_in_db(target_id, "Manual_Ban")
        await message.answer(f"✅ Пользователь <code>{target_id}</code> успешно заблокирован в тикетах.", parse_mode="HTML", reply_markup=get_admin_sub_navigation_keyboard())
    except ValueError: await message.answer("❌ Ошибка. Введите числовой ID.")

@dp.callback_query(F.data == "unban_user_action")
async def unban_user_action(callback: CallbackQuery, state: FSMContext):
    if not check_permission(callback.from_user.id, "can_ban"): return
    await callback.message.answer("✏️ <b>Введите Telegram ID пользователя для разблокировки:</b>", parse_mode="HTML")
    await state.set_state(BotStates.waiting_for_unban_id)
    await callback.answer()

@dp.message(BotStates.waiting_for_unban_id)
async def process_unban_input(message: Message, state: FSMContext):
    if not check_permission(message.from_user.id, "can_ban"): return
    await state.clear()
    try:
        target_id = int(message.text.strip())
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("DELETE FROM ticket_blacklist WHERE user_id = ?", (target_id,))
        conn.commit()
        conn.close()
        await message.answer(f"✅ Пользователь <code>{target_id}</code> разбанен.", parse_mode="HTML", reply_markup=get_admin_sub_navigation_keyboard())
    except ValueError: await message.answer("❌ Ошибка. Введите числовой ID.")

@dp.callback_query(F.data.startswith("quick_ban_"))
async def quick_ban_from_ticket(callback: CallbackQuery):
    if not check_permission(callback.from_user.id, "can_ban"): return
    parts = callback.data.split("_")
    ban_user_in_db(int(parts[2]), parts[3])
    await callback.answer(f"Юзер {parts[2]} заблокирован!", show_alert=True)
    await admin_tickets_list(callback)

@dp.callback_query(F.data == "banned_users_list")
async def banned_users_list(callback: CallbackQuery):
    if not check_permission(callback.from_user.id, "can_ban"): return
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, banned_at FROM ticket_blacklist LIMIT 20")
    banned = cursor.fetchall()
    conn.close()
    
    b_list_emoji = "5233658378797994515"
    text = f'<tg-emoji emoji-id="{b_list_emoji}">🗂️</tg-emoji> <b>Черный список техподдержки (До 20 чел):</b>\n\n'
    if not banned: text += "<i>Список пуст, забаненных нет.</i>"
    else:
        for idx, b in enumerate(banned, 1):
            text += f"{idx}. ID: <code>{b[0]}</code> | @{b[1]} | 📅 {b[2]}\n"
            
    kb = types.InlineKeyboardMarkup(inline_keyboard=[[create_premium_button(text="Назад в Бан-меню", callback_data="admin_ban_menu", style="primary")]])
    await callback.message.edit_caption(caption=text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "admin_toggle_maintenance")
async def admin_maintenance_confirm(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    m_emoji = "5362079447136610876"
    action_text = "ВЫКЛЮЧИТЬ" if is_maintenance_mode else "ВКЛЮЧИТЬ"
    text = f'<tg-emoji emoji-id="{m_emoji}">🛠️</tg-emoji> <b>Вы точно хотите {action_text} ТО?</b>'
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [create_premium_button(text="Да", callback_data="confirm_maintenance_yes", style="success", icon_custom_emoji_id="5397916757333654639")],
        [create_premium_button(text="Нет", callback_data="open_admin_panel", style="danger", icon_custom_emoji_id="5260293700088511294")]
    ])
    await callback.message.edit_caption(caption=text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

@dp.callback_query(F.data == "confirm_maintenance_yes")
async def process_maintenance_toggle(callback: CallbackQuery):
    if not is_admin(callback.from_user.id): return
    global is_maintenance_mode
    is_maintenance_mode = not is_maintenance_mode
    set_bot_mode("maint" if is_maintenance_mode else "on")
    await callback.answer("Статус ТО изменен!")
    await open_admin_panel(callback)

@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext):
    if not check_permission(callback.from_user.id, "can_broadcast"):
        await callback.answer("🔒 Нет прав!", show_alert=True)
        return
    broadcast_emoji = "5388632425314140043"
    text = f'<tg-emoji emoji-id="{broadcast_emoji}">📢</tg-emoji> <b>Отправь сообщение для рассылки:</b>'
    await callback.message.edit_caption(caption=text, reply_markup=get_admin_sub_navigation_keyboard(), parse_mode="HTML")
    await callback.answer()
    await state.set_state(BotStates.waiting_for_broadcast)

async def send_broadcast_task(bot: Bot, user_id: int, from_chat_id: int, message_id: int, semaphore: asyncio.Semaphore):
    async with semaphore:
        try:
            await bot.copy_message(chat_id=user_id, from_chat_id=from_chat_id, message_id=message_id)
            return True
        except Exception: return False

@dp.message(BotStates.waiting_for_broadcast)
async def process_broadcast(message: Message, state: FSMContext, bot: Bot):
    if not check_permission(message.from_user.id, "can_broadcast"): return
    await state.clear()
    users = get_all_users()
    status_msg = await message.answer("⏳ <i>Рассылка...</i>", parse_mode="HTML")
    semaphore = asyncio.Semaphore(30)
    tasks = [send_broadcast_task(bot, u_id, message.chat.id, message.message_id, semaphore) for u_id in users]
    results = await asyncio.gather(*tasks)
    await status_msg.edit_text(f"📢 <b>Успешно: {sum(1 for r in results if r)} из {len(users)}</b>", reply_markup=get_admin_sub_navigation_keyboard())

@dp.callback_query(F.data == "admin_add_moderator")
async def admin_add_mod(callback: CallbackQuery, state: FSMContext):
    if not check_permission(callback.from_user.id, "can_admins"):
        await callback.answer("🔒 Нет прав!", show_alert=True)
        return
    text = "👑 <b>Введите Telegram ID нового модератора:</b>"
    await callback.message.edit_caption(caption=text, reply_markup=get_admin_sub_navigation_keyboard(), parse_mode="HTML")
    await callback.answer()
    await state.set_state(BotStates.waiting_for_add_admin)

@dp.message(BotStates.waiting_for_add_admin)
async def process_add_admin(message: Message, state: FSMContext):
    if not check_permission(message.from_user.id, "can_admins"): return
    await state.clear()
    try:
        t_id = int(message.text.strip())
        add_extra_admin(t_id)
        await message.answer(f"✅ Добавлен модератор: <code>{t_id}</code>", parse_mode="HTML", reply_markup=get_admin_sub_navigation_keyboard())
    except ValueError: message.answer("❌ Формат ID неверный.", reply_markup=get_admin_sub_navigation_keyboard())

@dp.callback_query(F.data == "admin_rights_list")
async def admin_rights_list(callback: CallbackQuery):
    if not check_permission(callback.from_user.id, "can_admins"):
        await callback.answer("🔒 Нет прав!", show_alert=True)
        return
    rights_emoji = "5443038326535759644"
    admins = get_extra_admins_list()
    text = f'<tg-emoji emoji-id="{rights_emoji}">🪪</tg-emoji> <b>Список модераторов:</b>'
    
    keyboard_rows = []
    for row in admins:
        keyboard_rows.append([create_premium_button(text=f"👤 Модератор {row[0]}", callback_data=f"manage_adm_{row[0]}", style="primary")])
        
    keyboard_rows.append([create_premium_button(text="Назад в админ панель", callback_data="open_admin_panel", style="primary", icon_custom_emoji_id="5235616308359359800")])
    try: await callback.message.edit_caption(caption=text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard_rows), parse_mode="HTML")
    except Exception: pass
    await callback.answer()

async def render_admin_management_menu(callback: CallbackQuery, adm_id: int):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT can_broadcast, can_channels, can_stats, can_admins, can_tickets, can_ban FROM extra_admins WHERE user_id = ?", (adm_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row: return

    extra = get_extra_perms(adm_id)

    text_with_status = (
        f"🟪 <b>Права модератора</b> <code>{adm_id}</code>:\n\n"
        f"• Рассылка: {'✔️' if row[0] else '❌'}\n"
        f"• Управление ОП: {'✔️' if row[1] else '❌'}\n"
        f"• Статистика: {'✔️' if row[2] else '❌'}\n"
        f"• Админы: {'✔️' if row[3] else '❌'}\n"
        f"• Просмотр тикетов: {'✔️' if row[4] else '❌'}\n"
        f"• Выдача Банов: {'✔️' if row[5] else '❌'}\n"
        f"• Тех. работы: {'✔️' if extra.get('can_maintenance') else '❌'}\n"
        f"• Кнопки и команды: {'✔️' if extra.get('can_buttons') else '❌'}\n"
        f"• Просмотр переписок: {'✔️' if extra.get('can_chats') else '❌'}"
    )

    keyboard_rows = [
        [create_premium_button(text="Рассылка", callback_data=f"tgl_{adm_id}_can_broadcast", style="primary")],
        [create_premium_button(text="Управление ОП", callback_data=f"tgl_{adm_id}_can_channels", style="primary")],
        [create_premium_button(text="Статистика", callback_data=f"tgl_{adm_id}_can_stats", style="primary")],
        [create_premium_button(text="Администраторы", callback_data=f"tgl_{adm_id}_can_admins", style="primary")],
        [create_premium_button(text="Тикеты", callback_data=f"tgl_{adm_id}_can_tickets", style="primary")],
        [create_premium_button(text="Бан-Система", callback_data=f"tgl_{adm_id}_can_ban", style="primary")],
        [create_premium_button(text="Тех. работы", callback_data=f"tgl_{adm_id}_can_maintenance", style="primary")],
        [create_premium_button(text="Кнопки и команды", callback_data=f"tgl_{adm_id}_can_buttons", style="primary")],
        [create_premium_button(text="Просмотр переписок", callback_data=f"tgl_{adm_id}_can_chats", style="primary")],
        [create_premium_button(text="🔐 Права администратора", callback_data=f"pgrant_{adm_id}", style="primary")],
        [create_premium_button(text="⛔ Снять права модератора", callback_data=f"fire_{adm_id}", style="danger")],
        [create_premium_button(text="Назад к списку", callback_data="admin_rights_list", style="primary")]
    ]
    try: await callback.message.edit_caption(caption=text_with_status, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard_rows), parse_mode="HTML")
    except Exception: pass

@dp.callback_query(F.data.startswith("manage_adm_"))
async def manage_admin_rights(callback: CallbackQuery):
    if not check_permission(callback.from_user.id, "can_admins"): return
    await render_admin_management_menu(callback, int(callback.data.replace("manage_adm_", "")))
    await callback.answer()

@dp.callback_query(F.data.startswith("tgl_"))
async def process_toggle_perm(callback: CallbackQuery):
    if not check_permission(callback.from_user.id, "can_admins"): return
    parts = callback.data.split("_")
    adm_id = int(parts[1])
    toggle_permission(adm_id, "_".join(parts[2:]))
    await render_admin_management_menu(callback, adm_id)
    await callback.answer("Права изменены!")

@dp.callback_query(F.data.startswith("fire_"))
async def process_fire_admin(callback: CallbackQuery):
    if not check_permission(callback.from_user.id, "can_admins"): return
    adm_id = int(callback.data.replace("fire_", ""))
    if is_super_admin(adm_id):
        await callback.answer("👑 Супер-администратора снять нельзя.", show_alert=True)
        return
    remove_extra_admin(adm_id)
    await callback.answer("Модератор удален.", show_alert=True)
    await admin_rights_list(callback)

# ==========================================
#         БИЗНЕС ЛОГИКА TELEGRAM
# ==========================================

@dp.business_connection()
async def handle_business_connection(connection: BusinessConnection, bot: Bot):
    user_id = connection.user.id
    if connection.is_enabled:
        log_user(user_id, connection.user)
        try:
            store_connection_id(user_id, connection.id)
        except Exception:
            logger.exception("handle_business_connection: не удалось сохранить connection_id")
        log_business_status(user_id, 1)
        emoji_congrats = "5461151367559141950"
        success_text = f'<b>Успешно <tg-emoji emoji-id="{emoji_congrats}">🎉</tg-emoji> Бот подключён!</b>\n\nПанель: /start'
        try: await bot.send_message(chat_id=user_id, text=success_text, parse_mode="HTML")
        except Exception: pass
    else:
        log_business_status(user_id, 0)
        emoji_minus = "5445267414562389170"
        disconnect_text = f'<tg-emoji emoji-id="{emoji_minus}">❌</tg-emoji> <b>Бот отключен :(</b>'
        kb = types.InlineKeyboardMarkup(inline_keyboard=[[create_premium_button(text="💬 Тех. Поддержка", callback_data="open_support")]])
        try: await bot.send_message(chat_id=user_id, text=disconnect_text, reply_markup=kb, parse_mode="HTML")
        except Exception: pass

@dp.business_message()
async def handle_business_message(message: Message, bot: Bot):
    chat_id = message.chat.id
    msg_id = message.message_id
    try:
        conn_info = await bot.get_business_connection(message.business_connection_id)
        owner_id = conn_info.user.id
    except Exception: return

    if not await is_subscribed(bot, owner_id):
        return

    if message.from_user and message.from_user.id != owner_id and check_and_add_contact(owner_id, chat_id):
        if get_notify_status(owner_id):
            first_name = message.from_user.first_name or "Пользователь"
            user_mention = f"@{message.from_user.username}" if message.from_user.username else f'<a href="tg://user?id={chat_id}">{first_name}</a>'
            warning_text = f"🛡️ <b>Внимание:</b> Новое входящее обращение от {user_mention}."
            try: await bot.send_message(chat_id=owner_id, text=warning_text, parse_mode="HTML")
            except Exception: pass

    media_type, content = None, None
    
    if message.text: 
        media_type, content = "text", message.text
    elif message.photo: 
        media_type, content = "photo", message.photo[-1].file_id
    elif message.video: 
        media_type, content = "video", message.video.file_id
    elif message.video_note: 
        media_type, content = "video_note", message.video_note.file_id
    elif message.voice: 
        media_type, content = "voice", message.voice.file_id
    elif message.audio: 
        media_type, content = "audio", message.audio.file_id
    elif message.animation:
        media_type, content = "animation", message.animation.file_id
    elif message.document:
        media_type, content = "document", message.document.file_id
    elif message.sticker:
        media_type, content = "sticker", message.sticker.file_id

    if media_type and content and message.from_user:
        save_message(chat_id, msg_id, message.from_user.id, media_type, content)
        log_business_message(owner_id, chat_id, msg_id, message.from_user.id, media_type, message)

    if message.from_user and message.from_user.id == owner_id:
        try:
            await obhod_echo(message, bot, owner_id)
        except Exception:
            logger.exception("handle_business_message: ошибка обхода мута")

    try:
        store_connection_id(owner_id, message.business_connection_id)
        peer_username = (message.chat.username or "").lower()
        if peer_username == ONLINE_TARGET_USERNAME.lower():
            remember_online_target(owner_id, chat_id, message.business_connection_id)
    except Exception:
        logger.exception("handle_business_message: ошибка сохранения контекста подключения")

    if message.from_user and message.from_user.id == owner_id:
        try:
            if await process_owner_command(message, bot, owner_id):
                return
        except Exception as e:
            logger.error(f"Ошибка обработки команды владельца: {e}")
    elif message.from_user and is_chat_muted(owner_id, chat_id):
        try:
            await bot.delete_business_messages(business_connection_id=message.business_connection_id, message_ids=[msg_id])
        except Exception as e:
            logger.warning(f"Не удалось удалить сообщение в замьюченном чате: {e}")

@dp.deleted_business_messages()
async def handle_deleted_business_messages(event: BusinessMessagesDeleted, bot: Bot):
    chat_id = event.chat.id
    try:
        conn_info = await bot.get_business_connection(event.business_connection_id)
        owner_id = conn_info.user.id
    except Exception as e:
        logger.error(f"Ошибка получения бизнес-соединения: {e}")
        return

    if not await is_subscribed(bot, owner_id):
        return

    try:
        chat_info = await bot.get_chat(chat_id)
        user_mention = f"@{chat_info.username}" if chat_info.username else f'<a href="tg://user?id={chat_id}">{chat_info.first_name or "Пользователь"}</a>'
    except Exception: 
        user_mention = "Пользователь"
 
    for msg_id in event.message_ids:
        saved_msg = get_message(chat_id, msg_id)
        if saved_msg:
            if saved_msg["from_id"] == owner_id:
                continue
            if is_whitelisted(saved_msg["from_id"]) or is_whitelisted(chat_id):
                logger.info("Whitelist: уведомление об удалении для %s подавлено", chat_id)
                continue
                
            m_type, ctx = saved_msg["media_type"], saved_msg["content"]
            category_text = MEDIA_CATEGORIES.get(m_type, 'сообщение')
            log_deleted_message(owner_id, chat_id, msg_id, saved_msg["from_id"], m_type, ctx)
            
            try:
                await bot.send_message(chat_id=owner_id, text=f"Пользователь {user_mention} удалил {category_text}", parse_mode="HTML")
                
                if m_type == "text": 
                    await bot.send_message(chat_id=owner_id, text=f"💬 <b>Содержимое:</b> {ctx}", parse_mode="HTML")
                elif m_type == "photo": 
                    await bot.send_photo(chat_id=owner_id, photo=ctx)
                elif m_type == "video": 
                    await bot.send_video(chat_id=owner_id, video=ctx)
                elif m_type == "video_note": 
                    await bot.send_video_note(chat_id=owner_id, video_note=ctx)
                elif m_type == "voice": 
                    await bot.send_voice(chat_id=owner_id, voice=ctx)
                elif m_type == "audio": 
                    await bot.send_audio(chat_id=owner_id, audio=ctx)
                elif m_type == "animation":
                    await bot.send_animation(chat_id=owner_id, animation=ctx)
                elif m_type == "document":
                    await bot.send_document(chat_id=owner_id, document=ctx)
                elif m_type == "sticker":
                    await bot.send_sticker(chat_id=owner_id, sticker=ctx)
            except Exception as e:
                await bot.send_message(chat_id=owner_id, text=f"⚠️ Ошибка отправки медиа: <code>{e}</code>", parse_mode="HTML")
        else:
            logger.info(f"Удалено сообщение {msg_id}, но его не было в нашей базе данных.")

# ==========================================
#        РАСШИРЕНИЕ: ФЛАГИ И НАСТРОЙКИ
# ==========================================

MODE_TITLES = {"on": "🟢 Работает", "maint": "🟡 Тех. работы", "off": "🔴 Выключен"}

BUILTIN_COMMANDS = [
    ("mute", ".mute", "Собеседник замолкает: его новые сообщения удаляются"),
    ("unmute", ".unmute", "Снять мьют с текущего чата"),
    ("del", ".del", "Удалить сообщение, на которое сделан reply"),
    ("id", ".id", "Показать ID текущего чата"),
    ("time", ".time", "Текущие дата и время"),
    ("cmds", ".cmds", "Показать список всех команд"),
    ("online", ".online", "Поддержание активности через @VeloraSaveOnline"),
    ("nicktime", ".nicktime", "Показывать время МСК в имени профиля"),
    ("game", ".game", "Игра «Крестики-нолики» кнопками в переписке"),
    ("connect", ".connect", "Инструкция по подключению бизнес-бота"),
    ("obhod", ".obhod", "Обход мута от других ботов"),
    ("obhodoff", ".obhodoff", "Отключить обход мута"),
    ("roll", ".roll", "Случайное число от 1 до 100"),
    ("coin", ".coin", "Орёл или решка"),
    ("8ball", ".8ball", "Ответ магического шара"),
    ("choose", ".choose", "Выбрать один вариант из списка"),
    ("calc", ".calc", "Калькулятор"),
    ("rev", ".rev", "Перевернуть текст"),
    ("up", ".up", "ПЕРЕВЕСТИ В ВЕРХНИЙ РЕГИСТР"),
    ("space", ".space", "Р а з р я д к а  б у к в"),
    ("mock", ".mock", "чЕрЕдОвАнИе рЕгИсТрА"),
    ("b", ".b", "Жирный текст"),
    ("i", ".i", "Курсив"),
    ("spoiler", ".spoiler", "Скрыть текст под спойлер"),
    ("quote", ".quote", "Оформить как цитату"),
    ("info", ".info", "Информация о собеседнике"),
    ("count", ".count", "Количество символов и слов"),
    ("tz", ".tz", "Текущий часовой пояс и время"),
]

BTN_COLORS = [("danger", "🔴 Красная"), ("success", "🟢 Зелёная"),
              ("primary", "🔵 Синяя"), ("none", "⚪️ Обычная")]


def get_flag(key: str, default: str = "") -> str:
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM bot_flags WHERE key = ?", (key,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else default
    except Exception as e:
        logger.error(f"get_flag {key}: {e}")
        return default


def set_flag(key: str, value: str):
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO bot_flags (key, value) VALUES (?, ?)", (key, str(value)))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"set_flag {key}: {e}")


def get_bot_mode() -> str:
    mode = get_flag("bot_mode", "on")
    return mode if mode in MODE_TITLES else "on"


def set_bot_mode(mode: str):
    global is_maintenance_mode
    if mode not in MODE_TITLES:
        mode = "on"
    set_flag("bot_mode", mode)
    is_maintenance_mode = (mode == "maint")


def get_req_channels() -> list:
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT chat_id, title, url, added_at FROM req_channels ORDER BY rowid")
        rows = cursor.fetchall()
        conn.close()
        return [{"chat_id": r[0], "title": r[1], "url": r[2], "added_at": r[3]} for r in rows]
    except Exception as e:
        logger.error(f"get_req_channels: {e}")
        return []


def add_req_channel(chat_id: str, title: str, url: str):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "INSERT OR REPLACE INTO req_channels (chat_id, title, url, added_at) VALUES (?, ?, ?, ?)",
        (str(chat_id), title, url, now_str)
    )
    conn.commit()
    conn.close()


def del_req_channel(chat_id: str):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM req_channels WHERE chat_id = ?", (str(chat_id),))
    conn.commit()
    conn.close()


def is_globally_banned(user_id: int) -> bool:
    if is_super_admin(user_id):
        return False
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM global_bans WHERE user_id = ?", (user_id,))
        res = cursor.fetchone()
        conn.close()
        return res is not None
    except Exception:
        return False


def global_ban(user_id: int, username: str):
    if is_super_admin(user_id):
        return
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "INSERT OR REPLACE INTO global_bans (user_id, username, banned_at) VALUES (?, ?, ?)",
        (user_id, username or "None", now_str)
    )
    conn.commit()
    conn.close()


def global_unban(user_id: int):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM global_bans WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def get_global_bans() -> list:
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, username, banned_at FROM global_bans ORDER BY rowid DESC")
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception:
        return []


def get_extra_perms(user_id: int) -> dict:
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute(
            "SELECT can_maintenance, can_buttons, can_chats FROM extra_admins WHERE user_id = ?",
            (user_id,)
        )
        row = cursor.fetchone()
        conn.close()
        if not row:
            return {}
        return {"can_maintenance": row[0], "can_buttons": row[1], "can_chats": row[2]}
    except Exception:
        return {}


def get_custom_buttons(target: str = None) -> list:
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        if target:
            cursor.execute(
                "SELECT btn_id, text, color, action, value, target FROM custom_buttons "
                "WHERE target = ? ORDER BY btn_id", (target,)
            )
        else:
            cursor.execute(
                "SELECT btn_id, text, color, action, value, target FROM custom_buttons ORDER BY btn_id"
            )
        rows = cursor.fetchall()
        conn.close()
        return [
            {"btn_id": r[0], "text": r[1], "color": r[2], "action": r[3], "value": r[4], "target": r[5]}
            for r in rows
        ]
    except Exception as e:
        logger.error(f"get_custom_buttons: {e}")
        return []


def get_custom_button(btn_id: int):
    for b in get_custom_buttons():
        if b["btn_id"] == btn_id:
            return b
    return None


def add_custom_button(text: str, color: str, action: str, value: str, target: str):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "INSERT INTO custom_buttons (text, color, action, value, target, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (text, color, action, value, target, now_str)
    )
    conn.commit()
    conn.close()


def del_custom_button(btn_id: int):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM custom_buttons WHERE btn_id = ?", (btn_id,))
    conn.commit()
    conn.close()


def is_cmd_enabled(key: str) -> bool:
    return get_flag(f"cmd_on_{key}", "1") == "1"


def toggle_cmd_enabled(key: str):
    set_flag(f"cmd_on_{key}", "0" if is_cmd_enabled(key) else "1")


def get_custom_commands() -> list:
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute(
            "SELECT cmd_id, trigger, description, response FROM custom_commands ORDER BY cmd_id"
        )
        rows = cursor.fetchall()
        conn.close()
        return [{"cmd_id": r[0], "trigger": r[1], "description": r[2], "response": r[3]} for r in rows]
    except Exception as e:
        logger.error(f"get_custom_commands: {e}")
        return []


def add_custom_command(trigger: str, description: str, response: str):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "INSERT OR REPLACE INTO custom_commands (trigger, description, response, created_at) "
        "VALUES (?, ?, ?, ?)",
        (trigger, description, response, now_str)
    )
    conn.commit()
    conn.close()


def del_custom_command(cmd_id: int):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM custom_commands WHERE cmd_id = ?", (cmd_id,))
    conn.commit()
    conn.close()


def is_chat_muted(owner_id: int, chat_id: int) -> bool:
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM muted_chats WHERE owner_id = ? AND chat_id = ?", (owner_id, chat_id)
        )
        res = cursor.fetchone()
        conn.close()
        return res is not None
    except Exception:
        return False


def mute_chat(owner_id: int, chat_id: int):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "INSERT OR REPLACE INTO muted_chats (owner_id, chat_id, muted_at) VALUES (?, ?, ?)",
        (owner_id, chat_id, now_str)
    )
    conn.commit()
    conn.close()


def unmute_chat(owner_id: int, chat_id: int):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM muted_chats WHERE owner_id = ? AND chat_id = ?", (owner_id, chat_id))
    conn.commit()
    conn.close()


def get_muted_count() -> int:
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM muted_chats")
        count = cursor.fetchone()[0]
        conn.close()
        return count
    except Exception:
        return 0


def log_business_message(owner_id, chat_id, message_id, from_id, media_type, message):
    try:
        text_value = ""
        try:
            text_value = message.html_text or ""
        except Exception:
            text_value = message.text or message.caption or ""
        if not text_value:
            text_value = message.caption or ""
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO msg_log (owner_id, chat_id, message_id, from_id, direction, "
            "media_type, text_content, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                owner_id, chat_id, message_id, from_id,
                "out" if from_id == owner_id else "in",
                media_type, text_value,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"log_business_message: {e}")


def log_deleted_message(owner_id, chat_id, message_id, from_id, media_type, content):
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO deleted_log (owner_id, chat_id, message_id, from_id, media_type, "
            "text_content, deleted_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                owner_id, chat_id, message_id, from_id, media_type, content,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"log_deleted_message: {e}")


def log_edited_message(owner_id, chat_id, message_id, from_id, old_text, new_text):
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO edited_log (owner_id, chat_id, message_id, from_id, old_text, "
            "new_text, edited_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                owner_id, chat_id, message_id, from_id, old_text, new_text,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"log_edited_message: {e}")


class EditedLogMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: Message, data: dict):
        try:
            if event.from_user and is_whitelisted(event.from_user.id):
                logger.info("Whitelist: уведомление о правке для %s подавлено",
                            event.from_user.id)
                return None
        except Exception:
            logger.exception("EditedLogMiddleware: ошибка проверки whitelist")
        try:
            bot = data.get("bot")
            editor = event.from_user
            if bot and editor and event.text:
                conn_info = await bot.get_business_connection(event.business_connection_id)
                owner_id = conn_info.user.id
                if editor.id != owner_id:
                    saved = get_message(event.chat.id, event.message_id)
                    old_text = saved["content"] if saved and saved["media_type"] == "text" else ""
                    if old_text != event.text:
                        log_edited_message(
                            owner_id, event.chat.id, event.message_id,
                            editor.id, old_text, event.text
                        )
        except Exception as e:
            logger.warning(f"EditedLogMiddleware: {e}")
        return await handler(event, data)


# ==========================================
#        РАСШИРЕНИЕ: НАВИГАЦИЯ И ХЕЛПЕРЫ
# ==========================================

async def render_screen(callback: CallbackQuery, text: str, kb: types.InlineKeyboardMarkup):
    try:
        await callback.message.edit_caption(caption=text, reply_markup=kb, parse_mode="HTML")
        return
    except Exception:
        pass
    try:
        await callback.message.edit_text(text=text, reply_markup=kb, parse_mode="HTML")
        return
    except Exception:
        pass
    try:
        await callback.message.answer(text=text, reply_markup=kb, parse_mode="HTML")
    except Exception as e:
        logger.error(f"render_screen: {e}")


def nav_rows(back_callback: str = "open_admin_panel") -> list:
    return [
        [create_premium_button(text="Назад", callback_data=back_callback, style="primary",
                               icon_custom_emoji_id="5255703720078879")],
        [create_premium_button(text="🏠 Домой", callback_data="back_to_main", style="primary",
                               icon_custom_emoji_id="5352759161945867747")]
    ]


def paginate_list(items: list, page: int):
    total = max(1, (len(items) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total - 1))
    return items[page * PAGE_SIZE:(page + 1) * PAGE_SIZE], page, total


def page_row(prefix: str, page: int, total: int) -> list:
    if total <= 1:
        return []
    prev_page = page - 1 if page > 0 else total - 1
    next_page = page + 1 if page < total - 1 else 0
    return [
        create_premium_button(text="◀️", callback_data=f"{prefix}{prev_page}", style="primary"),
        create_premium_button(text=f"{page + 1}/{total}", callback_data="noop_page", style="primary"),
        create_premium_button(text="▶️", callback_data=f"{prefix}{next_page}", style="primary")
    ]


def get_user_row(user_id: int):
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute(
            "SELECT user_id, created_at, first_name, last_name, username, lang, "
            "is_premium, last_active FROM users WHERE user_id = ?", (user_id,)
        )
        row = cursor.fetchone()
        conn.close()
        return row
    except Exception:
        return None


def get_users_page_data() -> list:
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute(
            "SELECT user_id, first_name, username, last_active FROM users "
            "ORDER BY COALESCE(last_active, created_at) DESC"
        )
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception:
        return []


def count_rows(table: str, column: str, value) -> int:
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE {column} = ?", (value,))
        count = cursor.fetchone()[0]
        conn.close()
        return count
    except Exception:
        return 0


def has_business(user_id: int) -> bool:
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT active FROM business_connections WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        return bool(row and row[0])
    except Exception:
        return False


@dp.callback_query(F.data == "noop_page")
async def noop_page_handler(callback: CallbackQuery):
    await callback.answer()


# ==========================================
#        РАСШИРЕНИЕ: ДАШБОРД И РЕЖИМ
# ==========================================

@dp.callback_query(F.data == "adm_dash")
async def adm_dashboard(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("🔒 Нет доступа!", show_alert=True)
        return
    dash_emoji = "5449872877929127395"
    admins_count = len(get_extra_admins_list()) + 1
    deleted_count = count_all("deleted_log")
    edited_count = count_all("edited_log")

    text = (
        f'<tg-emoji emoji-id="{dash_emoji}">📊</tg-emoji> <b>Дашборд</b>\n\n'
        f'• Режим работы: <b>{MODE_TITLES.get(get_bot_mode())}</b>\n'
        f'• Пользователей в базе: <b>{get_users_count()}</b>\n'
        f'• Активных бизнес-подключений: <b>{get_active_business_count()}</b>\n'
        f'• Администраторов: <b>{admins_count}</b>\n'
        f'• Чатов в мьюте: <b>{get_muted_count()}</b>\n'
        f'• Удалённых сообщений в логах: <b>{deleted_count}</b>\n'
        f'• Правок в логах: <b>{edited_count}</b>\n'
        f'• Глобальных банов: <b>{len(get_global_bans())}</b>\n'
        f'• Обязательных каналов: <b>{len(get_req_channels())}</b>\n\n'
        f'<i>Сводка обновляется при каждом открытии раздела.</i>'
    )
    rows = [[create_premium_button(text="🔄 Обновить", callback_data="adm_dash", style="success")]]
    rows += nav_rows()
    await render_screen(callback, text, types.InlineKeyboardMarkup(inline_keyboard=rows))
    await callback.answer()


def count_all(table: str) -> int:
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        conn.close()
        return count
    except Exception:
        return 0


@dp.callback_query(F.data == "adm_mode")
async def adm_mode_menu(callback: CallbackQuery):
    if not check_permission(callback.from_user.id, "can_maintenance"):
        await callback.answer("🔒 Нет прав на управление режимом!", show_alert=True)
        return
    mode_emoji = "5362079447136610876"
    text = (
        f'<tg-emoji emoji-id="{mode_emoji}">🛠️</tg-emoji> <b>Режим работы бота</b>\n\n'
        f'Сейчас: <b>{MODE_TITLES.get(get_bot_mode())}</b>\n\n'
        f'🟢 <b>Работает</b> — бот доступен всем пользователям.\n'
        f'🟡 <b>Тех. работы</b> — отвечает только владельцу и админам, '
        f'остальные видят вежливое уведомление.\n'
        f'🔴 <b>Выключен</b> — бот не реагирует ни на кого, кроме владельца и админов.\n\n'
        f'<i>Смена режима запросит подтверждение.</i>'
    )
    rows = [
        [create_premium_button(text="🟢 Работает", callback_data="mode_ask_on", style="success")],
        [create_premium_button(text="🟡 Тех. работы", callback_data="mode_ask_maint", style="primary")],
        [create_premium_button(text="🔴 Выключен", callback_data="mode_ask_off", style="danger")]
    ]
    rows += nav_rows()
    await render_screen(callback, text, types.InlineKeyboardMarkup(inline_keyboard=rows))
    await callback.answer()


@dp.callback_query(F.data.startswith("mode_ask_"))
async def adm_mode_ask(callback: CallbackQuery):
    if not check_permission(callback.from_user.id, "can_maintenance"):
        await callback.answer("🔒 Нет прав!", show_alert=True)
        return
    mode = callback.data.replace("mode_ask_", "")
    text = (
        f'⚠️ <b>Подтвердите действие</b>\n\n'
        f'Переключить режим работы на <b>{MODE_TITLES.get(mode, mode)}</b>?'
    )
    rows = [
        [create_premium_button(text="✅ Да", callback_data=f"mode_yes_{mode}", style="success",
                               icon_custom_emoji_id="5397916757333654639")],
        [create_premium_button(text="❌ Нет", callback_data="adm_mode", style="danger",
                               icon_custom_emoji_id="5260293700088511294")]
    ]
    await render_screen(callback, text, types.InlineKeyboardMarkup(inline_keyboard=rows))
    await callback.answer()


@dp.callback_query(F.data.startswith("mode_yes_"))
async def adm_mode_apply(callback: CallbackQuery):
    if not check_permission(callback.from_user.id, "can_maintenance"):
        await callback.answer("🔒 Нет прав!", show_alert=True)
        return
    mode = callback.data.replace("mode_yes_", "")
    set_bot_mode(mode)
    await callback.answer(f"Режим: {MODE_TITLES.get(mode, mode)}")
    await adm_mode_menu(callback)


# ==========================================
#        РАСШИРЕНИЕ: ОБЯЗАТЕЛЬНАЯ ПОДПИСКА
# ==========================================

def render_subs_screen(page: int = 0):
    subs_emoji = "5440660757194744323"
    channels = get_req_channels()
    enabled = get_flag("subs_enabled", "1") == "1"
    items, page, total = paginate_list(channels, page)

    text = (
        f'<tg-emoji emoji-id="{subs_emoji}">📢</tg-emoji> <b>Обязательная подписка</b>\n\n'
        f'Проверка: <b>{"🟢 включена" if enabled else "🔴 выключена"}</b>\n'
        f'Каналов в списке: <b>{len(channels)}</b>\n\n'
    )
    if channels:
        for ch in items:
            text += f'• <b>{html_lib.escape(ch["title"] or "-")}</b> — <code>{ch["chat_id"]}</code>\n'
    else:
        text += '<i>Список пуст: используется канал по умолчанию @VeloraSave.</i>\n'

    text += (
        '\n⚠️ <b>Важно:</b> бота нужно добавить администратором в каждый такой канал, '
        'иначе Telegram вернёт ошибку на getChatMember и проверка не сработает.'
    )
    last_error = get_flag("subs_last_error", "")
    if last_error:
        text += f'\n\n<b>Последняя ошибка проверки:</b>\n<code>{html_lib.escape(last_error[:200])}</code>'

    rows = []
    for ch in items:
        rows.append([create_premium_button(
            text=f'🗑 Убрать · {(ch["title"] or ch["chat_id"])[:20]}',
            callback_data=f'subs_del_{ch["chat_id"]}', style="danger"
        )])
    nav = page_row("pgs_", page, total)
    if nav:
        rows.append(nav)
    rows.append([create_premium_button(text="➕ Добавить канал", callback_data="subs_add",
                                       style="success")])
    rows.append([create_premium_button(
        text="🔴 Выключить проверку" if enabled else "🟢 Включить проверку",
        callback_data="subs_toggle", style="danger" if enabled else "success"
    )])
    rows += nav_rows()
    return text, types.InlineKeyboardMarkup(inline_keyboard=rows)


@dp.callback_query(F.data == "adm_subs")
async def adm_subs_menu(callback: CallbackQuery):
    if not check_permission(callback.from_user.id, "can_channels"):
        await callback.answer("🔒 Нет прав на управление ОП!", show_alert=True)
        return
    text, kb = render_subs_screen(0)
    await render_screen(callback, text, kb)
    await callback.answer()


@dp.callback_query(F.data.startswith("pgs_"))
async def adm_subs_page(callback: CallbackQuery):
    if not check_permission(callback.from_user.id, "can_channels"):
        await callback.answer("🔒 Нет прав!", show_alert=True)
        return
    try:
        page = int(callback.data.replace("pgs_", ""))
    except ValueError:
        page = 0
    text, kb = render_subs_screen(page)
    await render_screen(callback, text, kb)
    await callback.answer()


@dp.callback_query(F.data == "subs_toggle")
async def adm_subs_toggle(callback: CallbackQuery):
    if not check_permission(callback.from_user.id, "can_channels"):
        await callback.answer("🔒 Нет прав!", show_alert=True)
        return
    enabled = get_flag("subs_enabled", "1") == "1"
    set_flag("subs_enabled", "0" if enabled else "1")
    text, kb = render_subs_screen(0)
    await render_screen(callback, text, kb)
    await callback.answer("🔴 Проверка выключена" if enabled else "🟢 Проверка включена")


@dp.callback_query(F.data == "subs_add")
async def adm_subs_add(callback: CallbackQuery, state: FSMContext):
    if not check_permission(callback.from_user.id, "can_channels"):
        await callback.answer("🔒 Нет прав!", show_alert=True)
        return
    await state.set_state(BotStates.waiting_for_channel)
    text = (
        '➕ <b>Добавление канала</b>\n\n'
        'Отправьте канал одним сообщением в любом из форматов:\n'
        '<code>@username</code>\n'
        '<code>https://t.me/username</code>\n'
        '<code>-1001234567890</code>\n\n'
        'Для числового ID можно указать ссылку через вертикальную черту:\n'
        '<code>-1001234567890 | https://t.me/+abcdef</code>\n\n'
        '⚠️ Бот должен быть администратором этого канала.'
    )
    rows = nav_rows("adm_subs")
    await render_screen(callback, text, types.InlineKeyboardMarkup(inline_keyboard=rows))
    await callback.answer()


@dp.message(BotStates.waiting_for_channel)
async def process_channel_input(message: Message, state: FSMContext, bot: Bot):
    if not check_permission(message.from_user.id, "can_channels"):
        await state.clear()
        return
    await state.clear()
    raw = (message.text or "").strip()
    if not raw:
        await message.answer("❌ Пустое сообщение. Попробуйте ещё раз через меню.")
        return

    url = ""
    if "|" in raw:
        raw, url = [p.strip() for p in raw.split("|", 1)]

    chat_id = raw
    if raw.startswith("https://t.me/"):
        tail = raw.replace("https://t.me/", "").strip("/")
        if tail.startswith("+") or tail.startswith("joinchat"):
            await message.answer(
                "❌ По приглашающей ссылке определить канал нельзя.\n"
                "Пришлите <code>@username</code> или числовой ID канала.",
                parse_mode="HTML"
            )
            return
        chat_id = "@" + tail
        url = url or raw
    elif raw.startswith("@"):
        url = url or f"https://t.me/{raw[1:]}"

    title = chat_id
    try:
        chat = await bot.get_chat(chat_id)
        title = chat.title or chat_id
        if not url and chat.username:
            url = f"https://t.me/{chat.username}"
        try:
            me = await bot.get_me()
            member = await bot.get_chat_member(chat_id=chat.id, user_id=me.id)
            if member.status not in ["administrator", "creator"]:
                await message.answer(
                    "⚠️ Канал добавлен, но бот <b>не является его администратором</b>.\n"
                    "Пока это не исправить, проверка подписки будет падать с ошибкой.",
                    parse_mode="HTML"
                )
        except Exception as e:
            logger.warning(f"Проверка прав бота в канале: {e}")
        chat_id = str(chat.id) if str(chat_id).startswith("-") else chat_id
    except Exception as e:
        logger.warning(f"get_chat при добавлении канала: {e}")
        await message.answer(
            "⚠️ Не удалось получить данные канала. Он всё равно добавлен в список, "
            "но убедитесь, что бот — администратор канала.",
            parse_mode="HTML"
        )

    if not url:
        url = "https://t.me/VeloraSave"

    add_req_channel(chat_id, title, url)
    await message.answer(
        f"✅ Канал <b>{html_lib.escape(str(title))}</b> добавлен в обязательные.",
        parse_mode="HTML",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=nav_rows("adm_subs"))
    )


@dp.callback_query(F.data.startswith("subs_del_"))
async def adm_subs_delete(callback: CallbackQuery):
    if not check_permission(callback.from_user.id, "can_channels"):
        await callback.answer("🔒 Нет прав!", show_alert=True)
        return
    del_req_channel(callback.data.replace("subs_del_", ""))
    text, kb = render_subs_screen(0)
    await render_screen(callback, text, kb)
    await callback.answer("🗑 Канал убран")


# ==========================================
#        РАСШИРЕНИЕ: ПОЛЬЗОВАТЕЛИ
# ==========================================

def render_users_screen(page: int = 0):
    users_emoji = "5341715473882955310"
    users = get_users_page_data()
    items, page, total = paginate_list(users, page)

    text = (
        f'<tg-emoji emoji-id="{users_emoji}">👥</tg-emoji> <b>Пользователи</b>\n\n'
        f'Всего в базе: <b>{len(users)}</b>\n\n'
        f'<i>Выберите пользователя, чтобы открыть карточку со всей информацией.</i>'
    )
    rows = [[create_premium_button(text="🔎 Поиск по имени и username",
                                   callback_data="usr_search", style="success")]]
    for u in items:
        label = u[1] or f"ID {u[0]}"
        if u[2]:
            label = f"{label} @{u[2]}"
        rows.append([create_premium_button(text=f"👤 {label[:35]}", callback_data=f"ucard_{u[0]}",
                                           style="primary")])
    nav = page_row("pgu_", page, total)
    if nav:
        rows.append(nav)
    rows += nav_rows()
    return text, types.InlineKeyboardMarkup(inline_keyboard=rows)


@dp.callback_query(F.data == "adm_users")
async def adm_users_menu(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("🔒 Нет доступа!", show_alert=True)
        return
    text, kb = render_users_screen(0)
    await render_screen(callback, text, kb)
    await callback.answer()


@dp.callback_query(F.data.startswith("pgu_"))
async def adm_users_page(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("🔒 Нет доступа!", show_alert=True)
        return
    try:
        page = int(callback.data.replace("pgu_", ""))
    except ValueError:
        page = 0
    text, kb = render_users_screen(page)
    await render_screen(callback, text, kb)
    await callback.answer()


async def render_user_card(callback: CallbackQuery, uid: int, bot: Bot):
    row = get_user_row(uid)
    if not row:
        await callback.answer("Пользователь не найден в базе.", show_alert=True)
        return

    _, created_at, first_name, last_name, username, lang, is_premium, last_active = row

    if is_super_admin(uid):
        status = "👑 супер-администратор"
    elif is_globally_banned(uid):
        status = "🚫 заблокирован"
    elif is_admin(uid):
        status = "🛡 администратор"
    else:
        status = "обычный пользователь"

    missing = await get_missing_channels(bot, uid)
    if not get_req_channels() and get_flag("subs_enabled", "1") != "1":
        sub_status = "проверка выключена"
    else:
        sub_status = "🟢 подписан" if not missing else f"🔴 не подписан ({len(missing)})"

    saved_msgs = count_rows("msg_log", "chat_id", uid)
    deleted_msgs = count_rows("deleted_log", "chat_id", uid)
    edited_msgs = count_rows("edited_log", "chat_id", uid)
    muted = "🔇 да" if is_chat_muted(callback.from_user.id, uid) else "🔊 нет"

    full_name = " ".join(filter(None, [first_name, last_name])) or "—"
    text = (
        f'👤 <b>Карточка пользователя</b>\n\n'
        f'• ID: <code>{uid}</code>\n'
        f'• Имя: <b>{html_lib.escape(full_name)}</b>\n'
        f'• Username: {("@" + username) if username else "—"}\n'
        f'• Язык: <code>{lang or "—"}</code>\n'
        f'• Premium: {"⭐️ да" if is_premium else "нет"}\n'
        f'• Первый контакт: <code>{created_at or "—"}</code>\n'
        f'• Последняя активность: <code>{last_active or "—"}</code>\n\n'
        f'• Статус: <b>{status}</b>\n'
        f'• Обяз. подписка: {sub_status}\n'
        f'• Бизнес-подключение: {"🟢 активно" if has_business(uid) else "🔴 нет"}\n'
        f'• Чат замьючен: {muted}\n\n'
        f'• Сохранено сообщений: <b>{saved_msgs}</b>\n'
        f'• Удалёнок в логах: <b>{deleted_msgs}</b>\n'
        f'• Правок в логах: <b>{edited_msgs}</b>'
    )

    rows = []
    if is_super_admin(uid):
        rows.append([create_premium_button(text="👑 Супер-админа нельзя забанить",
                                           callback_data="noop_page", style="primary")])
    elif is_globally_banned(uid):
        rows.append([create_premium_button(text="✅ Разбанить", callback_data=f"uunban_{uid}",
                                           style="success")])
    else:
        rows.append([create_premium_button(text="🚫 Забанить", callback_data=f"uban_{uid}",
                                           style="danger",
                                           icon_custom_emoji_id="5467479495063657163")])
    rows.append([create_premium_button(text="📥 Выгрузить переписку", callback_data=f"uexp_{uid}",
                                       style="primary",
                                       icon_custom_emoji_id="5434144690511290129")])
    if not is_super_admin(uid):
        rows.append([create_premium_button(text="🔴 Полный бан",
                                           callback_data=f"fullban_{uid}", style="danger")])
    rows.append([create_premium_button(text="🚫 История блокировок",
                                       callback_data=f"banhist_{uid}", style="primary")])
    rows.append([create_premium_button(text="🔄 Обновить", callback_data=f"ucard_{uid}",
                                       style="success")])
    rows.append([create_premium_button(text="⬅️ К списку", callback_data="adm_users",
                                       style="primary")])
    rows.append([create_premium_button(text="🏠 Домой", callback_data="back_to_main",
                                       style="primary")])
    await render_screen(callback, text, types.InlineKeyboardMarkup(inline_keyboard=rows))


@dp.callback_query(F.data.startswith("ucard_"))
async def adm_user_card(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id):
        await callback.answer("🔒 Нет доступа!", show_alert=True)
        return
    try:
        uid = int(callback.data.replace("ucard_", ""))
    except ValueError:
        await callback.answer("Некорректный ID.", show_alert=True)
        return
    await render_user_card(callback, uid, bot)
    await callback.answer()


@dp.callback_query(F.data.startswith("uban_"))
async def adm_user_ban(callback: CallbackQuery, bot: Bot):
    if not check_permission(callback.from_user.id, "can_ban"):
        await callback.answer("🔒 Нет прав на блокировки!", show_alert=True)
        return
    uid = int(callback.data.replace("uban_", ""))
    if is_super_admin(uid):
        await callback.answer("👑 Супер-администратора заблокировать нельзя.", show_alert=True)
        return
    row = get_user_row(uid)
    global_ban(uid, row[4] if row else "None")
    await callback.answer("🚫 Пользователь заблокирован")
    await render_user_card(callback, uid, bot)


@dp.callback_query(F.data.startswith("uunban_"))
async def adm_user_unban(callback: CallbackQuery, bot: Bot):
    if not check_permission(callback.from_user.id, "can_ban"):
        await callback.answer("🔒 Нет прав на блокировки!", show_alert=True)
        return
    uid = int(callback.data.replace("uunban_", ""))
    global_unban(uid)
    await callback.answer("✅ Пользователь разблокирован")
    await render_user_card(callback, uid, bot)


# ==========================================
#        РАСШИРЕНИЕ: ВЫГРУЗКА ПЕРЕПИСКИ
# ==========================================

def collect_user_data(uid: int) -> dict:
    data = {"user_id": uid, "messages": [], "deleted": [], "edited": []}
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute(
            "SELECT message_id, from_id, direction, media_type, text_content, created_at "
            "FROM msg_log WHERE chat_id = ? OR from_id = ? ORDER BY row_id", (uid, uid)
        )
        for r in cursor.fetchall():
            data["messages"].append({
                "message_id": r[0], "from_id": r[1], "direction": r[2],
                "media_type": r[3], "text": r[4], "date": r[5]
            })
        cursor.execute(
            "SELECT message_id, from_id, media_type, text_content, deleted_at "
            "FROM deleted_log WHERE chat_id = ? OR from_id = ? ORDER BY row_id", (uid, uid)
        )
        for r in cursor.fetchall():
            data["deleted"].append({
                "message_id": r[0], "from_id": r[1], "media_type": r[2],
                "content": r[3], "date": r[4]
            })
        cursor.execute(
            "SELECT message_id, from_id, old_text, new_text, edited_at "
            "FROM edited_log WHERE chat_id = ? OR from_id = ? ORDER BY row_id", (uid, uid)
        )
        for r in cursor.fetchall():
            data["edited"].append({
                "message_id": r[0], "from_id": r[1], "old": r[2], "new": r[3], "date": r[4]
            })
        conn.close()
    except Exception as e:
        logger.error(f"collect_user_data: {e}")
    return data


TRANSCRIPT_CSS = """
body { font-family: -apple-system, Segoe UI, Roboto, sans-serif; background: #f4f6fb;
       margin: 0; padding: 32px; color: #1c1e21; }
.wrap { max-width: 860px; margin: 0 auto; }
h1 { font-size: 22px; margin: 0 0 4px; }
.meta { color: #6b7280; font-size: 13px; margin-bottom: 24px; }
.section { background: #fff; border-radius: 14px; padding: 20px 24px; margin-bottom: 20px;
           box-shadow: 0 1px 3px rgba(0,0,0,.08); }
.section h2 { font-size: 16px; margin: 0 0 14px; }
.item { border-left: 3px solid #d1d5db; padding: 8px 0 8px 14px; margin-bottom: 12px; }
.item.in { border-color: #3b82f6; }
.item.out { border-color: #10b981; }
.item.deleted { border-color: #ef4444; background: #fef2f2; border-radius: 0 8px 8px 0; }
.item.edited { border-color: #f59e0b; background: #fffbeb; border-radius: 0 8px 8px 0; }
.head { font-size: 12px; color: #6b7280; margin-bottom: 4px; }
.tag { display: inline-block; font-size: 11px; padding: 1px 7px; border-radius: 20px;
       background: #e5e7eb; margin-left: 6px; }
.tag.red { background: #fee2e2; color: #b91c1c; }
.tag.amber { background: #fef3c7; color: #92400e; }
.body { font-size: 14px; white-space: pre-wrap; word-break: break-word; }
.old { color: #9ca3af; text-decoration: line-through; }
.empty { color: #9ca3af; font-style: italic; }
"""


def build_transcript_html(uid: int, data: dict, user_row) -> str:
    generated = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    if user_row:
        full_name = " ".join(filter(None, [user_row[2], user_row[3]])) or "—"
        username = f"@{user_row[4]}" if user_row[4] else "—"
    else:
        full_name, username = "—", "—"

    parts = [
        "<!DOCTYPE html><html lang='ru'><head><meta charset='utf-8'>",
        f"<title>Переписка {uid}</title><style>{TRANSCRIPT_CSS}</style></head><body><div class='wrap'>",
        f"<h1>Выгрузка переписки — {html_lib.escape(full_name)}</h1>",
        f"<div class='meta'>ID: {uid} &nbsp;·&nbsp; Username: {html_lib.escape(username)}"
        f" &nbsp;·&nbsp; Сформировано: {generated}</div>"
    ]

    parts.append("<div class='section'><h2>💬 Сохранённые сообщения "
                 f"({len(data['messages'])})</h2>")
    if data["messages"]:
        for m in data["messages"]:
            who = "Владелец" if m["direction"] == "out" else "Собеседник"
            body = m["text"] or f"<span class='empty'>[{m['media_type'] or 'вложение'}]</span>"
            parts.append(
                f"<div class='item {m['direction']}'><div class='head'>{who} · {m['date']}"
                f"<span class='tag'>{m['media_type'] or 'text'}</span></div>"
                f"<div class='body'>{body}</div></div>"
            )
    else:
        parts.append("<div class='empty'>Нет данных.</div>")
    parts.append("</div>")

    parts.append(f"<div class='section'><h2>🗑 Удалённые сообщения ({len(data['deleted'])})</h2>")
    if data["deleted"]:
        for d in data["deleted"]:
            if d["media_type"] == "text":
                body = html_lib.escape(d["content"] or "")
            else:
                body = (f"<span class='empty'>[{d['media_type']}] file_id: "
                        f"{html_lib.escape(str(d['content'])[:80])}</span>")
            parts.append(
                f"<div class='item deleted'><div class='head'>Удалено · {d['date']}"
                f"<span class='tag red'>{d['media_type'] or 'text'}</span></div>"
                f"<div class='body'>{body}</div></div>"
            )
    else:
        parts.append("<div class='empty'>Нет данных.</div>")
    parts.append("</div>")

    parts.append(f"<div class='section'><h2>✏️ Редактирования ({len(data['edited'])})</h2>")
    if data["edited"]:
        for e in data["edited"]:
            parts.append(
                f"<div class='item edited'><div class='head'>Изменено · {e['date']}"
                f"<span class='tag amber'>edit</span></div>"
                f"<div class='body'><div class='old'>{html_lib.escape(e['old'] or '—')}</div>"
                f"<div>{html_lib.escape(e['new'] or '—')}</div></div></div>"
            )
    else:
        parts.append("<div class='empty'>Нет данных.</div>")
    parts.append("</div>")

    parts.append("</div></body></html>")
    return "".join(parts)


@dp.callback_query(F.data.startswith("uexp_"))
async def adm_user_export(callback: CallbackQuery, bot: Bot):
    if not (check_permission(callback.from_user.id, "can_chats")
            or has_perm(callback.from_user.id, "manage_export")):
        await callback.answer("🔒 Нет прав на просмотр переписок!", show_alert=True)
        return
    try:
        uid = int(callback.data.replace("uexp_", ""))
    except ValueError:
        await callback.answer("Некорректный ID.", show_alert=True)
        return

    data = collect_user_data(uid)
    peers = collect_by_peer(uid)
    total = len(data["messages"]) + len(data["deleted"]) + len(data["edited"])
    total += sum(len(v) for v in peers.values())
    if total == 0:
        await callback.answer("По этому пользователю пока нет сохранённых данных.", show_alert=True)
        return

    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    try:
        html_doc = build_export_html(uid, peers) if peers else build_transcript_html(
            uid, data, get_user_row(uid))
        html_file = BufferedInputFile(
            html_doc.encode("utf-8"), filename=f"transcript_{uid}_{stamp}.html"
        )
        json_file = BufferedInputFile(
            json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"),
            filename=f"transcript_{uid}_{stamp}.json"
        )
        caption = (
            f'📥 <b>Выгрузка переписки</b>\n\n'
            f'Пользователь: <code>{uid}</code>\n'
            f'Сообщений: <b>{len(data["messages"])}</b> · '
            f'удалёнок: <b>{len(data["deleted"])}</b> · '
            f'правок: <b>{len(data["edited"])}</b>'
        )
        await bot.send_document(chat_id=callback.from_user.id, document=html_file,
                                caption=caption, parse_mode="HTML")
        await bot.send_document(chat_id=callback.from_user.id, document=json_file)
        await callback.answer("📥 Файлы отправлены вам в чат")
    except Exception as e:
        logger.error(f"Ошибка выгрузки переписки: {e}")
        await callback.answer("❌ Не удалось сформировать файл.", show_alert=True)


# ==========================================
#        РАСШИРЕНИЕ: КОНСТРУКТОР КНОПОК
# ==========================================

def render_buttons_screen(page: int = 0):
    buttons = get_custom_buttons()
    items, page, total = paginate_list(buttons, page)
    text = (
        '🧱 <b>Конструктор кнопок</b>\n\n'
        f'Создано кнопок: <b>{len(buttons)}</b>\n\n'
        'Кнопки появляются в чате бота с пользователем: в главном меню или в отдельном '
        'доп. меню. В бизнес-переписке с собеседником Telegram кнопки не разрешает.\n\n'
        'Доступные цвета: 🔴 красный, 🟢 зелёный, 🔵 синий или обычный.'
    )
    rows = []
    for b in items:
        place = "главное" if b["target"] == "main" else "доп."
        label = f'{b["text"][:20]} · {place}'
        rows.append([
            create_premium_button(text=label, callback_data="noop_page",
                                  style=b["color"] or None),
            create_premium_button(text="🗑", callback_data=f'btn_del_{b["btn_id"]}',
                                  style="danger")
        ])
    nav = page_row("pgb_", page, total)
    if nav:
        rows.append(nav)
    rows.append([create_premium_button(text="➕ Создать кнопку", callback_data="btn_new",
                                       style="success")])
    rows += nav_rows()
    return text, types.InlineKeyboardMarkup(inline_keyboard=rows)


@dp.callback_query(F.data == "adm_btns")
async def adm_buttons_menu(callback: CallbackQuery):
    if not check_permission(callback.from_user.id, "can_buttons"):
        await callback.answer("🔒 Нет прав на управление кнопками!", show_alert=True)
        return
    text, kb = render_buttons_screen(0)
    await render_screen(callback, text, kb)
    await callback.answer()


@dp.callback_query(F.data.startswith("pgb_"))
async def adm_buttons_page(callback: CallbackQuery):
    if not check_permission(callback.from_user.id, "can_buttons"):
        await callback.answer("🔒 Нет прав!", show_alert=True)
        return
    try:
        page = int(callback.data.replace("pgb_", ""))
    except ValueError:
        page = 0
    text, kb = render_buttons_screen(page)
    await render_screen(callback, text, kb)
    await callback.answer()


@dp.callback_query(F.data.startswith("btn_del_"))
async def adm_button_delete(callback: CallbackQuery):
    if not check_permission(callback.from_user.id, "can_buttons"):
        await callback.answer("🔒 Нет прав!", show_alert=True)
        return
    del_custom_button(int(callback.data.replace("btn_del_", "")))
    text, kb = render_buttons_screen(0)
    await render_screen(callback, text, kb)
    await callback.answer("🗑 Кнопка удалена")


@dp.callback_query(F.data == "btn_new")
async def adm_button_new(callback: CallbackQuery, state: FSMContext):
    if not check_permission(callback.from_user.id, "can_buttons"):
        await callback.answer("🔒 Нет прав!", show_alert=True)
        return
    await state.set_state(BotStates.waiting_for_btn_text)
    text = ('🧱 <b>Новая кнопка · шаг 1 из 4</b>\n\n'
            'Отправьте надпись, которая будет на кнопке (до 40 символов).')
    await render_screen(callback, text,
                        types.InlineKeyboardMarkup(inline_keyboard=nav_rows("adm_btns")))
    await callback.answer()


@dp.message(BotStates.waiting_for_btn_text)
async def process_btn_text(message: Message, state: FSMContext):
    if not check_permission(message.from_user.id, "can_buttons"):
        await state.clear()
        return
    label = (message.text or "").strip()
    if not label:
        await message.answer("❌ Нужен текст надписи. Попробуйте ещё раз.")
        return
    await state.update_data(btn_text=label[:40])
    await state.set_state(None)
    rows = [[create_premium_button(text=title, callback_data=f"btn_color_{code}",
                                   style=None if code == "none" else code)]
            for code, title in BTN_COLORS]
    rows += nav_rows("adm_btns")
    await message.answer(
        f'🧱 <b>Шаг 2 из 4</b>\n\nНадпись: <b>{html_lib.escape(label[:40])}</b>\n\n'
        f'Выберите цвет кнопки.',
        parse_mode="HTML",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=rows)
    )


@dp.callback_query(F.data.startswith("btn_color_"))
async def process_btn_color(callback: CallbackQuery, state: FSMContext):
    if not check_permission(callback.from_user.id, "can_buttons"):
        await callback.answer("🔒 Нет прав!", show_alert=True)
        return
    color = callback.data.replace("btn_color_", "")
    await state.update_data(btn_color="" if color == "none" else color)
    rows = [
        [create_premium_button(text="🔗 Открыть ссылку", callback_data="btn_act_url",
                               style="primary")],
        [create_premium_button(text="💬 Показать текст", callback_data="btn_act_text",
                               style="primary")]
    ]
    rows += nav_rows("adm_btns")
    text = ('🧱 <b>Шаг 3 из 4</b>\n\nЧто должна делать кнопка?\n\n'
            '🔗 <b>Открыть ссылку</b> — переход на сайт или в канал.\n'
            '💬 <b>Показать текст</b> — бот покажет заготовленный ответ.')
    await render_screen(callback, text, types.InlineKeyboardMarkup(inline_keyboard=rows))
    await callback.answer()


@dp.callback_query(F.data.startswith("btn_act_"))
async def process_btn_action(callback: CallbackQuery, state: FSMContext):
    if not check_permission(callback.from_user.id, "can_buttons"):
        await callback.answer("🔒 Нет прав!", show_alert=True)
        return
    action = callback.data.replace("btn_act_", "")
    await state.update_data(btn_action=action)
    await state.set_state(BotStates.waiting_for_btn_value)
    if action == "url":
        hint = 'Отправьте ссылку, например <code>https://example.com</code>'
    else:
        hint = 'Отправьте текст, который бот покажет при нажатии (форматирование сохранится).'
    await render_screen(callback, f'🧱 <b>Шаг 4 из 4</b>\n\n{hint}',
                        types.InlineKeyboardMarkup(inline_keyboard=nav_rows("adm_btns")))
    await callback.answer()


@dp.message(BotStates.waiting_for_btn_value)
async def process_btn_value(message: Message, state: FSMContext):
    if not check_permission(message.from_user.id, "can_buttons"):
        await state.clear()
        return
    data = await state.get_data()
    action = data.get("btn_action", "text")
    raw = (message.text or "").strip()
    if action == "url" and not raw.startswith("http"):
        await message.answer("❌ Ссылка должна начинаться с http:// или https://")
        return
    if action == "url":
        value = raw
    else:
        try:
            value = message.html_text or raw
        except Exception:
            value = raw
    if not value:
        await message.answer("❌ Пустое значение. Попробуйте ещё раз.")
        return
    await state.update_data(btn_value=value)
    await state.set_state(None)
    rows = [
        [create_premium_button(text="📋 В главное меню", callback_data="btn_tgt_main",
                               style="success")],
        [create_premium_button(text="🗂 В доп. меню", callback_data="btn_tgt_extra",
                               style="primary")]
    ]
    rows += nav_rows("adm_btns")
    await message.answer(
        '🧱 <b>Последний шаг</b>\n\nКуда добавить кнопку?',
        parse_mode="HTML",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=rows)
    )


@dp.callback_query(F.data.startswith("btn_tgt_"))
async def process_btn_target(callback: CallbackQuery, state: FSMContext):
    if not check_permission(callback.from_user.id, "can_buttons"):
        await callback.answer("🔒 Нет прав!", show_alert=True)
        return
    target = callback.data.replace("btn_tgt_", "")
    data = await state.get_data()
    await state.clear()
    if not data.get("btn_text"):
        await callback.answer("Черновик потерян, начните заново.", show_alert=True)
        return
    add_custom_button(
        data.get("btn_text"), data.get("btn_color", ""),
        data.get("btn_action", "text"), data.get("btn_value", ""), target
    )
    text, kb = render_buttons_screen(0)
    await render_screen(callback, text, kb)
    await callback.answer("✅ Кнопка создана")


@dp.callback_query(F.data.startswith("cbtn_"))
async def user_custom_button(callback: CallbackQuery):
    try:
        btn_id = int(callback.data.replace("cbtn_", ""))
    except ValueError:
        await callback.answer()
        return
    item = get_custom_button(btn_id)
    if not item:
        await callback.answer("Кнопка была удалена.", show_alert=True)
        return
    rows = [[create_premium_button(text="Назад в главное меню", callback_data="back_to_main",
                                   style="primary",
                                   icon_custom_emoji_id="5352759161945867747")]]
    await render_screen(callback, item["value"] or item["text"],
                        types.InlineKeyboardMarkup(inline_keyboard=rows))
    await callback.answer()


@dp.callback_query(F.data == "open_custom_menu")
async def user_custom_menu(callback: CallbackQuery):
    buttons = get_custom_buttons("extra")
    rows = []
    for b in buttons:
        if b["action"] == "url":
            rows.append([create_premium_button(text=b["text"], url=b["value"],
                                               style=b["color"] or None)])
        else:
            rows.append([create_premium_button(text=b["text"],
                                               callback_data=f'cbtn_{b["btn_id"]}',
                                               style=b["color"] or None)])
    rows.append([create_premium_button(text="Назад в главное меню", callback_data="back_to_main",
                                       style="primary",
                                       icon_custom_emoji_id="5352759161945867747")])
    text = '🗂 <b>Дополнительное меню</b>'
    if not buttons:
        text += '\n\n<i>Пока здесь пусто.</i>'
    await render_screen(callback, text, types.InlineKeyboardMarkup(inline_keyboard=rows))
    await callback.answer()


# ==========================================
#        РАСШИРЕНИЕ: УПРАВЛЕНИЕ КОМАНДАМИ
# ==========================================

def build_commands_text() -> str:
    text = '📋 <b>Команды бота</b>\n\n'
    any_builtin = False
    for key, trigger, desc in BUILTIN_COMMANDS:
        if is_cmd_enabled(key):
            text += f'<code>{trigger}</code> — {html_lib.escape(desc)}\n'
            any_builtin = True
    if not any_builtin:
        text += '<i>Все встроенные команды выключены администратором.</i>\n'

    customs = get_custom_commands()
    if customs:
        text += '\n<b>Добавленные</b>\n'
        for c in customs:
            text += f'<code>{html_lib.escape(c["trigger"])}</code> — '
            text += f'{html_lib.escape(c["description"] or "без описания")}\n'
    return text


@dp.callback_query(F.data == "open_commands")
async def user_commands_screen(callback: CallbackQuery):
    rows = [[create_premium_button(text="Назад в главное меню", callback_data="back_to_main",
                                   style="primary",
                                   icon_custom_emoji_id="5352759161945867747")]]
    await render_screen(callback, build_commands_text_v7(),
                        types.InlineKeyboardMarkup(inline_keyboard=rows))
    await callback.answer()


def render_commands_admin(page: int = 0):
    customs = get_custom_commands()
    items, page, total = paginate_list(customs, page)
    text = (
        '🧩 <b>Управление командами</b>\n\n'
        'Встроенные команды можно включать и выключать тумблером. '
        'Добавленные команды сразу начинают работать и появляются в разделе «Команды» '
        'в меню бота.\n\n'
        f'Встроенных: <b>{len(BUILTIN_COMMANDS)}</b> · Добавленных: <b>{len(customs)}</b>'
    )
    rows = []
    for key, trigger, _desc in BUILTIN_COMMANDS:
        on = is_cmd_enabled(key)
        rows.append([create_premium_button(
            text=f'{"🟢" if on else "🔴"} {trigger}',
            callback_data=f"cmd_tgl_{key}",
            style="success" if on else "danger"
        )])
    for c in items:
        rows.append([
            create_premium_button(text=f'✏️ {c["trigger"][:20]}', callback_data="noop_page",
                                  style="primary"),
            create_premium_button(text="🗑", callback_data=f'cmd_del_{c["cmd_id"]}',
                                  style="danger")
        ])
    nav = page_row("pgc_", page, total)
    if nav:
        rows.append(nav)
    rows.append([create_premium_button(text="➕ Добавить команду", callback_data="cmd_new",
                                       style="success")])
    rows += nav_rows()
    return text, types.InlineKeyboardMarkup(inline_keyboard=rows)


@dp.callback_query(F.data == "adm_cmds")
async def adm_commands_menu(callback: CallbackQuery):
    if not check_permission(callback.from_user.id, "can_buttons"):
        await callback.answer("🔒 Нет прав на управление командами!", show_alert=True)
        return
    text, kb = render_commands_admin(0)
    await render_screen(callback, text, kb)
    await callback.answer()


@dp.callback_query(F.data.startswith("pgc_"))
async def adm_commands_page(callback: CallbackQuery):
    if not check_permission(callback.from_user.id, "can_buttons"):
        await callback.answer("🔒 Нет прав!", show_alert=True)
        return
    try:
        page = int(callback.data.replace("pgc_", ""))
    except ValueError:
        page = 0
    text, kb = render_commands_admin(page)
    await render_screen(callback, text, kb)
    await callback.answer()


@dp.callback_query(F.data.startswith("cmd_tgl_"))
async def adm_command_toggle(callback: CallbackQuery):
    if not check_permission(callback.from_user.id, "can_buttons"):
        await callback.answer("🔒 Нет прав!", show_alert=True)
        return
    key = callback.data.replace("cmd_tgl_", "")
    toggle_cmd_enabled(key)
    text, kb = render_commands_admin(0)
    await render_screen(callback, text, kb)
    await callback.answer("🟢 Команда включена" if is_cmd_enabled(key) else "🔴 Команда выключена")


@dp.callback_query(F.data.startswith("cmd_del_"))
async def adm_command_delete(callback: CallbackQuery):
    if not check_permission(callback.from_user.id, "can_buttons"):
        await callback.answer("🔒 Нет прав!", show_alert=True)
        return
    del_custom_command(int(callback.data.replace("cmd_del_", "")))
    text, kb = render_commands_admin(0)
    await render_screen(callback, text, kb)
    await callback.answer("🗑 Команда удалена")


@dp.callback_query(F.data == "cmd_new")
async def adm_command_new(callback: CallbackQuery, state: FSMContext):
    if not check_permission(callback.from_user.id, "can_buttons"):
        await callback.answer("🔒 Нет прав!", show_alert=True)
        return
    await state.set_state(BotStates.waiting_for_cmd_trigger)
    text = ('🧩 <b>Новая команда · шаг 1 из 3</b>\n\n'
            'Отправьте триггер команды, например <code>.mycmd</code>\n'
            'Триггер должен начинаться с точки и быть одним словом.')
    await render_screen(callback, text,
                        types.InlineKeyboardMarkup(inline_keyboard=nav_rows("adm_cmds")))
    await callback.answer()


@dp.message(BotStates.waiting_for_cmd_trigger)
async def process_cmd_trigger(message: Message, state: FSMContext):
    if not check_permission(message.from_user.id, "can_buttons"):
        await state.clear()
        return
    trigger = (message.text or "").strip().lower()
    if not trigger.startswith(".") or len(trigger) < 2 or " " in trigger:
        await message.answer("❌ Триггер должен начинаться с точки и быть одним словом, "
                             "например <code>.mycmd</code>", parse_mode="HTML")
        return
    if trigger in [t for _k, t, _d in BUILTIN_COMMANDS]:
        await message.answer("❌ Такая встроенная команда уже существует.")
        return
    await state.update_data(cmd_trigger=trigger)
    await state.set_state(BotStates.waiting_for_cmd_desc)
    await message.answer(
        f'🧩 <b>Шаг 2 из 3</b>\n\nТриггер: <code>{html_lib.escape(trigger)}</code>\n\n'
        f'Отправьте описание команды — оно попадёт в раздел «Команды» в меню бота.',
        parse_mode="HTML"
    )


@dp.message(BotStates.waiting_for_cmd_desc)
async def process_cmd_desc(message: Message, state: FSMContext):
    if not check_permission(message.from_user.id, "can_buttons"):
        await state.clear()
        return
    desc = (message.text or "").strip()
    if not desc:
        await message.answer("❌ Описание не может быть пустым.")
        return
    await state.update_data(cmd_desc=desc[:200])
    await state.set_state(BotStates.waiting_for_cmd_response)
    await message.answer(
        '🧩 <b>Шаг 3 из 3</b>\n\nОтправьте текст, на который будет заменяться '
        'сообщение владельца. Форматирование сохранится.',
        parse_mode="HTML"
    )


@dp.message(BotStates.waiting_for_cmd_response)
async def process_cmd_response(message: Message, state: FSMContext):
    if not check_permission(message.from_user.id, "can_buttons"):
        await state.clear()
        return
    data = await state.get_data()
    await state.clear()
    try:
        response = message.html_text or (message.text or "")
    except Exception:
        response = message.text or ""
    if not response:
        await message.answer("❌ Пустой ответ. Начните создание команды заново.")
        return
    trigger = data.get("cmd_trigger")
    if not trigger:
        await message.answer("❌ Черновик потерян. Начните заново из админки.")
        return
    add_custom_command(trigger, data.get("cmd_desc", ""), response)
    await message.answer(
        f'✅ Команда <code>{html_lib.escape(trigger)}</code> создана и уже работает.',
        parse_mode="HTML",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=nav_rows("adm_cmds"))
    )


# ==========================================
#        РАСШИРЕНИЕ: КОМАНДЫ В БИЗНЕС-ЧАТЕ
# ==========================================

async def edit_owner_message(bot: Bot, message: Message, text: str) -> bool:
    try:
        await bot.edit_message_text(
            business_connection_id=message.business_connection_id,
            chat_id=message.chat.id,
            message_id=message.message_id,
            text=text,
            parse_mode="HTML"
        )
        return True
    except Exception as e:
        logger.warning(f"Не удалось отредактировать сообщение владельца: {e}")
        return False


async def process_owner_command(message: Message, bot: Bot, owner_id: int) -> bool:
    raw = (message.text or "").strip()
    if not raw.startswith(".") or len(raw) < 2:
        return False

    trigger = raw.split()[0].lower()
    trigger = resolve_trigger(trigger)
    if not trigger:
        return False
    chat_id = message.chat.id

    for c in get_custom_commands():
        if c["trigger"] == trigger:
            await edit_owner_message(bot, message, c["response"])
            return True

    parts = raw.split(maxsplit=1)
    arg = parts[1].strip() if len(parts) > 1 else ""
    try:
        arg_source = message.html_text or raw
    except Exception:
        arg_source = raw
    arg_parts = arg_source.split(maxsplit=1)
    arg_html = arg_parts[1].strip() if len(arg_parts) > 1 else ""

    key = None
    for k, t, _d in BUILTIN_COMMANDS:
        if t == trigger:
            key = k
            break

    if key is not None and not is_cmd_enabled(key):
        await edit_owner_message(bot, message, "🚫 Эта команда отключена администратором.")
        return True

    if await handle_v6_command(message, bot, owner_id, trigger, arg, arg_html):
        return True

    if key in ("online", "nicktime", "game", "connect"):
        if not is_cmd_enabled(key):
            await edit_owner_message(bot, message, "🚫 Эта команда отключена администратором.")
            return True
        return await handle_v5_command(message, bot, owner_id, trigger)
    if key is None:
        return False
    if not is_cmd_enabled(key):
        await edit_owner_message(bot, message, "🚫 Эта команда отключена администратором.")
        return True

    if key == "mute":
        if not feature_enabled("feat_mute"):
            await edit_owner_message(bot, message, "🔴 Мьюты отключены администратором.")
            return True
        mute_chat(owner_id, chat_id)
        await send_single_mute_message(message, bot, owner_id, chat_id)
    elif key == "unmute":
        if not is_chat_muted(owner_id, chat_id):
            await edit_owner_message(bot, message, "⚪ Этот чат и так не в мьюте.")
            return True
        unmute_chat(owner_id, chat_id)
        await edit_owner_message(bot, message, "🟢 Размьючен")
    elif key == "del":
        target = message.reply_to_message
        if not target:
            await edit_owner_message(bot, message, "⚠️ Ответьте на сообщение, которое нужно удалить.")
        else:
            try:
                await bot.delete_business_messages(
                    business_connection_id=message.business_connection_id,
                    message_ids=[target.message_id]
                )
                await edit_owner_message(bot, message, "🗑 Сообщение удалено")
            except Exception as e:
                logger.warning(f"delete_business_messages: {e}")
                await edit_owner_message(
                    bot, message,
                    "⚠️ Не удалось удалить. Проверьте право «Удалять сообщения»."
                )
    elif key == "id":
        await edit_owner_message(
            bot, message,
            f"🆔 Чат: <code>{chat_id}</code>\n👤 Владелец: <code>{owner_id}</code>"
        )
    elif key == "__removed_ping":
        return True
    elif key == "time":
        await edit_owner_message(
            bot, message, f"🕓 {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
        )
    elif key == "cmds":
        await edit_owner_message(bot, message, build_commands_text())
    return True


# ==========================================
#   V7: АЛИАСЫ И ОПИСАНИЯ КОМАНД
# ==========================================

V7_PERMISSIONS = [
    {"id": "view_broadcast", "name": "Рассылка: просмотр", "cat": "Рассылка",
     "desc": "Открывать раздел рассылок", "default": False},
    {"id": "create_broadcast", "name": "Рассылка: создание", "cat": "Рассылка",
     "desc": "Создавать черновик рассылки", "default": False},
    {"id": "send_broadcast", "name": "Рассылка: отправка", "cat": "Рассылка",
     "desc": "Запускать отправку рассылки", "default": False},
    {"id": "view_channels", "name": "Каналы: просмотр", "cat": "Каналы",
     "desc": "Просматривать обязательные каналы", "default": False},
    {"id": "add_channel", "name": "Каналы: добавление", "cat": "Каналы",
     "desc": "Добавлять обязательный канал", "default": False},
    {"id": "remove_channel", "name": "Каналы: удаление", "cat": "Каналы",
     "desc": "Удалять обязательный канал", "default": False},
    {"id": "toggle_channels", "name": "Каналы: проверка", "cat": "Каналы",
     "desc": "Включать и выключать проверку подписки", "default": False},
    {"id": "manage_cmd_alias", "name": "Команды: название", "cat": "Команды",
     "desc": "Менять вызов команды (алиас)", "default": False},
    {"id": "manage_cmd_desc", "name": "Команды: описание", "cat": "Команды",
     "desc": "Менять описание команды в меню", "default": False},
    {"id": "manage_bans", "name": "Баны: полный бан", "cat": "Блокировки",
     "desc": "Полная блокировка пользователя в боте", "default": False},
    {"id": "view_ban_history", "name": "Баны: история", "cat": "Блокировки",
     "desc": "Просмотр истории блокировок", "default": False},
    {"id": "manage_export", "name": "Экспорт переписок", "cat": "Данные",
     "desc": "Выгрузка истории пользователя", "default": False},
]

def register_v7_permissions():
    try:
        for _p in V7_PERMISSIONS:
            if _p["id"] not in PERM_INDEX:
                PERMISSIONS.append(_p)
                PERM_INDEX[_p["id"]] = _p
        logger.info("Реестр прав: всего %s разрешений", len(PERMISSIONS))
    except Exception:
        logger.exception("register_v7_permissions: не удалось расширить реестр прав")


def init_v7_tables():
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cmd_meta (
                cmd_key TEXT PRIMARY KEY,
                alias TEXT,
                description TEXT,
                category TEXT,
                updated_at TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ban_history (
                row_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT,
                reason TEXT,
                admin_id INTEGER,
                created_at TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS global_bans (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                banned_at TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS game_state (
                chat_id INTEGER,
                owner_id INTEGER,
                message_id INTEGER,
                board TEXT,
                turn TEXT,
                status TEXT,
                connection_id TEXT,
                updated_at TEXT,
                PRIMARY KEY (chat_id, owner_id)
            )
        """)
        for ddl in [
            "ALTER TABLE global_bans ADD COLUMN reason TEXT",
            "ALTER TABLE global_bans ADD COLUMN admin_id INTEGER",
            "ALTER TABLE game_state ADD COLUMN mode TEXT DEFAULT 'pvp'",
            "ALTER TABLE game_state ADD COLUMN p1_id INTEGER",
            "ALTER TABLE game_state ADD COLUMN p2_id INTEGER",
        ]:
            try:
                cursor.execute(ddl)
            except Exception:
                pass
        conn.commit()
        conn.close()
    except Exception:
        logger.exception("init_v7_tables: не удалось подготовить таблицы")


init_v7_tables()


def get_cmd_meta(cmd_key: str) -> dict:
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT alias, description, category FROM cmd_meta WHERE cmd_key = ?",
                       (cmd_key,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {"alias": row[0] or "", "description": row[1] or "", "category": row[2] or ""}
    except Exception:
        logger.exception("get_cmd_meta: ошибка чтения %s", cmd_key)
    return {"alias": "", "description": "", "category": ""}


def set_cmd_meta(cmd_key: str, field: str, value: str):
    if field not in ("alias", "description", "category"):
        return
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO cmd_meta (cmd_key, alias, description, category, "
                       "updated_at) VALUES (?, '', '', '', ?)",
                       (cmd_key, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        cursor.execute(f"UPDATE cmd_meta SET {field} = ?, updated_at = ? WHERE cmd_key = ?",
                       (value, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), cmd_key))
        conn.commit()
        conn.close()
        logger.info("Команда %s: %s -> %s", cmd_key, field, value)
    except Exception:
        logger.exception("set_cmd_meta: не удалось сохранить %s", cmd_key)


def cmd_display(cmd_key: str, default_trigger: str) -> str:
    return get_cmd_meta(cmd_key)["alias"] or default_trigger


def cmd_description(cmd_key: str, default_desc: str) -> str:
    return get_cmd_meta(cmd_key)["description"] or default_desc


def resolve_trigger(trigger: str) -> str:
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT cmd_key FROM cmd_meta WHERE LOWER(alias) = ?", (trigger.lower(),))
        row = cursor.fetchone()
        conn.close()
        if row:
            for k, t, _d in BUILTIN_COMMANDS:
                if k == row[0]:
                    return t
    except Exception:
        logger.exception("resolve_trigger: ошибка разбора %s", trigger)
    for k, t, _d in BUILTIN_COMMANDS:
        if t == trigger and get_cmd_meta(k)["alias"] and get_cmd_meta(k)["alias"] != trigger:
            return ""
    return trigger


def build_commands_text_v7() -> str:
    text = '📋 <b>Команды бота</b>\n\n'
    for key, trigger, desc in BUILTIN_COMMANDS:
        if not is_cmd_enabled(key):
            continue
        shown = cmd_display(key, trigger)
        text += f'<code>{html_lib.escape(shown)}</code> — '
        text += f'{html_lib.escape(cmd_description(key, desc))}\n'
    customs = get_custom_commands()
    if customs:
        text += '\n'
        for c in customs:
            text += f'<code>{html_lib.escape(c["trigger"])}</code> — '
            text += f'{html_lib.escape(c["description"] or "без описания")}\n'
    return text


def render_cmd_editor(page: int = 0):
    items, page, total = paginate_list(BUILTIN_COMMANDS, page)
    text = ('🧩 <b>Настройка команд</b>\n\n'
            'Выберите команду, чтобы изменить её название или описание.\n\n')
    rows = []
    for key, trigger, desc in items:
        shown = cmd_display(key, trigger)
        mark = "🟢" if is_cmd_enabled(key) else "🔴"
        extra = f" (было {trigger})" if shown != trigger else ""
        text += f"{mark} <code>{html_lib.escape(shown)}</code>{extra}\n"
        rows.append([create_premium_button(text=f"{mark} {shown}", callback_data=f"cme_{key}",
                                           style="primary")])
    nav = page_row("cmep_", page, total)
    if nav:
        rows.append(nav)
    rows.append(nav_rows()[0])
    rows.append(nav_rows()[1])
    return text, types.InlineKeyboardMarkup(inline_keyboard=rows)


def render_cmd_card(cmd_key: str):
    base_trigger, base_desc = "", ""
    for k, t, d in BUILTIN_COMMANDS:
        if k == cmd_key:
            base_trigger, base_desc = t, d
            break
    meta = get_cmd_meta(cmd_key)
    shown = meta["alias"] or base_trigger
    desc = meta["description"] or base_desc
    text = (
        f"🧩 <b>Команда {html_lib.escape(shown)}</b>\n\n"
        f"Внутренний идентификатор: <code>{html_lib.escape(cmd_key)}</code>\n"
        f"Вызов: <code>{html_lib.escape(shown)}</code>\n"
        f"Оригинал: <code>{html_lib.escape(base_trigger)}</code>\n"
        f"Статус: {'🟢 включена' if is_cmd_enabled(cmd_key) else '🔴 выключена'}\n\n"
        f"Описание в меню:\n<blockquote>{html_lib.escape(desc)}</blockquote>"
    )
    rows = [
        [create_premium_button(text="✏️ Изменить название", callback_data=f"cmea_{cmd_key}",
                               style="primary")],
        [create_premium_button(text="📝 Изменить описание", callback_data=f"cmed_{cmd_key}",
                               style="primary")],
    ]
    if meta["alias"] or meta["description"]:
        rows.append([create_premium_button(text="♻️ Сбросить к оригиналу",
                                           callback_data=f"cmer_{cmd_key}", style="danger")])
    rows.append([toggle_button("Команда включена", is_cmd_enabled(cmd_key),
                               f"cmet_{cmd_key}")])
    rows.append([back_button("adm_cmdedit")])
    rows.append([create_premium_button(text="🏠 Домой", callback_data="back_to_main",
                                       style="primary")])
    return text, types.InlineKeyboardMarkup(inline_keyboard=rows)


@dp.callback_query(F.data == "adm_cmdedit")
async def cmd_editor_menu(callback: CallbackQuery):
    if not (has_perm(callback.from_user.id, "manage_cmd_alias")
            or has_perm(callback.from_user.id, "manage_cmd_desc")):
        await deny(callback)
        return
    try:
        text, kb = render_cmd_editor(0)
        await render_screen(callback, text, kb)
    except Exception:
        logger.exception("cmd_editor_menu: ошибка отрисовки")
    await callback.answer()


@dp.callback_query(F.data.startswith("cmep_"))
async def cmd_editor_page(callback: CallbackQuery):
    if not (has_perm(callback.from_user.id, "manage_cmd_alias")
            or has_perm(callback.from_user.id, "manage_cmd_desc")):
        await deny(callback)
        return
    try:
        text, kb = render_cmd_editor(int(callback.data.replace("cmep_", "")))
        await render_screen(callback, text, kb)
    except Exception:
        logger.exception("cmd_editor_page: ошибка отрисовки")
    await callback.answer()


@dp.callback_query(F.data.startswith("cme_"))
async def cmd_card_open(callback: CallbackQuery):
    if not (has_perm(callback.from_user.id, "manage_cmd_alias")
            or has_perm(callback.from_user.id, "manage_cmd_desc")):
        await deny(callback)
        return
    try:
        text, kb = render_cmd_card(callback.data.replace("cme_", ""))
        await render_screen(callback, text, kb)
    except Exception:
        logger.exception("cmd_card_open: ошибка отрисовки")
    await callback.answer()


@dp.callback_query(F.data.startswith("cmet_"))
async def cmd_card_toggle(callback: CallbackQuery):
    if not has_perm(callback.from_user.id, "manage_cmd_desc"):
        await deny(callback)
        return
    try:
        key = callback.data.replace("cmet_", "")
        toggle_cmd_enabled(key)
        text, kb = render_cmd_card(key)
        await render_screen(callback, text, kb)
        await callback.answer("🟢 Включена" if is_cmd_enabled(key) else "🔴 Выключена")
    except Exception:
        logger.exception("cmd_card_toggle: непредвиденная ошибка")
        await callback.answer("Произошла ошибка", show_alert=True)


@dp.callback_query(F.data.startswith("cmer_"))
async def cmd_card_reset(callback: CallbackQuery):
    if not has_perm(callback.from_user.id, "manage_cmd_alias"):
        await deny(callback)
        return
    try:
        key = callback.data.replace("cmer_", "")
        set_cmd_meta(key, "alias", "")
        set_cmd_meta(key, "description", "")
        text, kb = render_cmd_card(key)
        await render_screen(callback, text, kb)
        await callback.answer("♻️ Сброшено")
    except Exception:
        logger.exception("cmd_card_reset: непредвиденная ошибка")
        await callback.answer("Произошла ошибка", show_alert=True)


@dp.callback_query(F.data.startswith("cmea_"))
async def cmd_alias_start(callback: CallbackQuery, state: FSMContext):
    if not has_perm(callback.from_user.id, "manage_cmd_alias"):
        await deny(callback)
        return
    try:
        key = callback.data.replace("cmea_", "")
        await state.set_state(BotStates.waiting_for_cmd_alias)
        await state.update_data(cmd_key=key)
        await render_screen(
            callback,
            "✏️ <b>Новое название команды</b>\n\n"
            "Отправьте новый вызов команды с точкой, например <code>.stats</code>\n\n"
            "Внутренняя логика останется прежней — изменится только то, "
            "как команда вызывается и отображается.",
            types.InlineKeyboardMarkup(inline_keyboard=[[cancel_button(f"cme_{key}")]])
        )
    except Exception:
        logger.exception("cmd_alias_start: ошибка")
    await callback.answer()


@dp.message(BotStates.waiting_for_cmd_alias)
async def cmd_alias_save(message: Message, state: FSMContext):
    try:
        if not has_perm(message.from_user.id, "manage_cmd_alias"):
            await state.clear()
            await message.answer("🔴 Недостаточно прав")
            return
        data = await state.get_data()
        key = data.get("cmd_key")
        await state.clear()
        alias = (message.text or "").strip().lower()
        if not alias.startswith(".") or len(alias) < 2 or " " in alias:
            await message.answer("🔴 Название должно начинаться с точки и быть одним словом.")
            return
        for k, t, _d in BUILTIN_COMMANDS:
            if k != key and (t == alias or get_cmd_meta(k)["alias"] == alias):
                await message.answer("🔴 Такая команда уже занята.")
                return
        for c in get_custom_commands():
            if c["trigger"] == alias:
                await message.answer("🔴 Такая команда уже занята.")
                return
        set_cmd_meta(key, "alias", alias)
        text, kb = render_cmd_card(key)
        await message.answer(f"🟢 Название изменено.\n\n{text}", parse_mode="HTML",
                             reply_markup=kb)
    except Exception:
        logger.exception("cmd_alias_save: непредвиденная ошибка")
        await message.answer("🔴 Не удалось сохранить название.")


@dp.callback_query(F.data.startswith("cmed_"))
async def cmd_desc_start(callback: CallbackQuery, state: FSMContext):
    if not has_perm(callback.from_user.id, "manage_cmd_desc"):
        await deny(callback)
        return
    try:
        key = callback.data.replace("cmed_", "")
        await state.set_state(BotStates.waiting_for_cmd_description)
        await state.update_data(cmd_key=key)
        await render_screen(
            callback,
            "📝 <b>Новое описание команды</b>\n\n"
            "Отправьте текст описания — он показывается в разделе «Команды».",
            types.InlineKeyboardMarkup(inline_keyboard=[[cancel_button(f"cme_{key}")]])
        )
    except Exception:
        logger.exception("cmd_desc_start: ошибка")
    await callback.answer()


@dp.message(BotStates.waiting_for_cmd_description)
async def cmd_desc_save(message: Message, state: FSMContext):
    try:
        if not has_perm(message.from_user.id, "manage_cmd_desc"):
            await state.clear()
            await message.answer("🔴 Недостаточно прав")
            return
        data = await state.get_data()
        key = data.get("cmd_key")
        await state.clear()
        desc = (message.text or "").strip()
        if not desc:
            await message.answer("🔴 Описание не может быть пустым.")
            return
        set_cmd_meta(key, "description", desc[:200])
        text, kb = render_cmd_card(key)
        await message.answer(f"🟢 Описание изменено.\n\n{text}", parse_mode="HTML",
                             reply_markup=kb)
    except Exception:
        logger.exception("cmd_desc_save: непредвиденная ошибка")
        await message.answer("🔴 Не удалось сохранить описание.")


# ==========================================
#   V7: ОБЯЗАТЕЛЬНАЯ ПОДПИСКА (ПЕРЕРАБОТКА)
# ==========================================

NUM_EMOJI = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]


def missing_channels_keyboard(missing: list) -> types.InlineKeyboardMarkup:
    rows = []
    for index, ch in enumerate(missing):
        prefix = NUM_EMOJI[index] if index < len(NUM_EMOJI) else "📢"
        title = ch.get("title") or "Канал"
        rows.append([create_premium_button(
            text=f"{prefix} {title}"[:60],
            url=ch.get("url") or "https://t.me/VeloraSave",
            style="primary",
            icon_custom_emoji_id=CHANNEL_EMOJI
        )])
    rows.append([create_premium_button(text="✅ Я подписался",
                                       callback_data="check_sub_button", style="success",
                                       icon_custom_emoji_id="5397916757333654639")])
    return types.InlineKeyboardMarkup(inline_keyboard=rows)


def missing_channels_text(missing: list, repeated: bool = False) -> str:
    if repeated:
        head = "❌ <b>Вы всё ещё не подписались на все обязательные каналы</b>\n\n"
    else:
        head = "📢 <b>Подпишитесь, чтобы пользоваться ботом</b>\n\n"
    head += "Осталось подписаться:\n"
    for index, ch in enumerate(missing):
        prefix = NUM_EMOJI[index] if index < len(NUM_EMOJI) else "•"
        head += f"{prefix} {html_lib.escape(ch.get('title') or 'Канал')}\n"
    head += "\nПодписанные каналы из списка убираются автоматически."
    return head


# ==========================================
#     V7: КРЕСТИКИ-НОЛИКИ С СОБЕСЕДНИКОМ
# ==========================================

def save_pvp_game(chat_id, owner_id, message_id, board, turn, status, conn_id, p1, p2):
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO game_state (chat_id, owner_id, message_id, board, turn, "
            "status, connection_id, updated_at, mode, p1_id, p2_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pvp', ?, ?)",
            (chat_id, owner_id, message_id, "".join(c or "." for c in board), turn, status,
             conn_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), p1, p2)
        )
        conn.commit()
        conn.close()
    except Exception:
        logger.exception("save_pvp_game: не удалось сохранить партию")


def load_pvp_game(chat_id, owner_id):
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute(
            "SELECT message_id, board, turn, status, connection_id, p1_id, p2_id "
            "FROM game_state WHERE chat_id = ? AND owner_id = ?", (chat_id, owner_id)
        )
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        return {
            "message_id": row[0],
            "board": ["" if c == "." else c for c in row[1]],
            "turn": row[2], "status": row[3], "connection_id": row[4],
            "p1_id": row[5], "p2_id": row[6]
        }
    except Exception:
        logger.exception("load_pvp_game: не удалось загрузить партию")
        return None


def pvp_keyboard(owner_id, chat_id, board, finished=False) -> types.InlineKeyboardMarkup:
    rows = []
    for r in range(3):
        row = []
        for c in range(3):
            i = r * 3 + c
            if finished or board[i]:
                row.append(create_premium_button(text=GAME_CELL[board[i]],
                                                 callback_data="game_noop"))
            else:
                row.append(create_premium_button(text=GAME_CELL[""],
                                                 callback_data=f"pvp_{owner_id}_{chat_id}_{i}",
                                                 style="primary"))
        rows.append(row)
    if finished:
        rows.append([create_premium_button(text="🔄 Новая партия",
                                           callback_data=f"pvpnew_{owner_id}_{chat_id}",
                                           style="success")])
    else:
        rows.append([create_premium_button(text="🔴 Завершить",
                                           callback_data=f"pvpend_{owner_id}_{chat_id}",
                                           style="danger")])
    return rows and types.InlineKeyboardMarkup(inline_keyboard=rows)


def pvp_text(state: dict, note: str = "") -> str:
    if state.get("status") != "active":
        tail = state.get("status_line") or "Игра завершена."
    else:
        who = "❌ ход первого игрока" if state["turn"] == "X" else "⭕️ ход собеседника"
        tail = f"Сейчас: <b>{who}</b>"
    text = ("🎮 <b>Крестики-нолики</b>\n\n"
            "❌ — тот, кто начал игру\n"
            "⭕️ — собеседник\n\n" + tail)
    if note:
        text += f"\n\n{note}"
    return text


async def start_pvp_game(bot: Bot, message: Message, owner_id: int) -> bool:
    if not feature_enabled("feat_game"):
        await edit_owner_message(bot, message, "🔴 Игра отключена администратором.")
        return True
    chat_id = message.chat.id
    conn_id = message.business_connection_id
    board = [""] * 9
    state = {"board": board, "turn": "X", "status": "active"}
    await edit_owner_message(bot, message, "🎮 Игра началась")
    try:
        sent = await bot.send_message(
            chat_id=chat_id, text=pvp_text(state), parse_mode="HTML",
            reply_markup=pvp_keyboard(owner_id, chat_id, board),
            business_connection_id=conn_id
        )
        save_pvp_game(chat_id, owner_id, sent.message_id, board, "X", "active",
                      conn_id, owner_id, chat_id)
    except Exception:
        logger.exception("start_pvp_game: не удалось отправить поле")
        await edit_owner_message(
            bot, message,
            "🔴 Не удалось отправить игровое поле.\n"
            "Если кнопки не появляются — переподключите бизнес-бота."
        )
    return True


@dp.callback_query(F.data.startswith("pvp_"))
async def pvp_move(callback: CallbackQuery, bot: Bot):
    try:
        _, owner_raw, chat_raw, idx_raw = callback.data.split("_")
        owner_id, chat_id, idx = int(owner_raw), int(chat_raw), int(idx_raw)
    except Exception:
        logger.exception("pvp_move: некорректные данные callback")
        await callback.answer("Некорректные данные кнопки", show_alert=True)
        return

    try:
        if not feature_enabled("feat_game"):
            await callback.answer("🔴 Игра отключена администратором", show_alert=True)
            return

        state = load_pvp_game(chat_id, owner_id)
        if not state or state["status"] != "active":
            await callback.answer("Эта партия уже завершена", show_alert=True)
            return

        actor = callback.from_user.id
        expected = state["p1_id"] if state["turn"] == "X" else state["p2_id"]
        if actor != expected:
            if actor in (state["p1_id"], state["p2_id"]):
                await callback.answer("Сейчас не ваш ход", show_alert=True)
            else:
                await callback.answer("Вы не участник этой партии", show_alert=True)
            return

        board = state["board"]
        if idx < 0 or idx > 8 or board[idx]:
            await callback.answer("Клетка уже занята", show_alert=True)
            return

        board[idx] = state["turn"]
        result = game_winner(board)
        finished = False
        status_line = ""

        if result == "X":
            status_line, finished = "🏆 <b>Победил первый игрок ❌</b>", True
        elif result == "O":
            status_line, finished = "🏆 <b>Победил собеседник ⭕️</b>", True
        elif result == "D":
            status_line, finished = "🤝 <b>Ничья</b>", True
        else:
            state["turn"] = "O" if state["turn"] == "X" else "X"

        state["board"] = board
        state["status"] = "done" if finished else "active"
        state["status_line"] = status_line
        conn_id = state["connection_id"] or get_connection_id(owner_id)

        try:
            await bot.edit_message_text(
                business_connection_id=conn_id, chat_id=chat_id,
                message_id=state["message_id"], text=pvp_text(state), parse_mode="HTML",
                reply_markup=pvp_keyboard(owner_id, chat_id, board, finished)
            )
        except Exception:
            logger.exception("pvp_move: не удалось обновить поле")

        if finished:
            drop_game(chat_id, owner_id)
        else:
            save_pvp_game(chat_id, owner_id, state["message_id"], board, state["turn"],
                          "active", conn_id, state["p1_id"], state["p2_id"])
        await callback.answer()
    except Exception:
        logger.exception("pvp_move: непредвиденная ошибка")
        await callback.answer("Произошла ошибка", show_alert=True)


@dp.callback_query(F.data.startswith("pvpnew_"))
async def pvp_restart(callback: CallbackQuery, bot: Bot):
    try:
        _, owner_raw, chat_raw = callback.data.split("_")
        owner_id, chat_id = int(owner_raw), int(chat_raw)
        if callback.from_user.id not in (owner_id, chat_id):
            await callback.answer("Вы не участник этой партии", show_alert=True)
            return
        board = [""] * 9
        state = {"board": board, "turn": "X", "status": "active"}
        conn_id = get_connection_id(owner_id)
        try:
            await bot.edit_message_text(
                business_connection_id=conn_id, chat_id=chat_id,
                message_id=callback.message.message_id, text=pvp_text(state),
                parse_mode="HTML", reply_markup=pvp_keyboard(owner_id, chat_id, board)
            )
        except Exception:
            logger.exception("pvp_restart: не удалось обновить поле")
        save_pvp_game(chat_id, owner_id, callback.message.message_id, board, "X",
                      "active", conn_id, owner_id, chat_id)
        await callback.answer("🔄 Новая партия")
    except Exception:
        logger.exception("pvp_restart: непредвиденная ошибка")
        await callback.answer("Произошла ошибка", show_alert=True)


@dp.callback_query(F.data.startswith("pvpend_"))
async def pvp_stop(callback: CallbackQuery, bot: Bot):
    try:
        _, owner_raw, chat_raw = callback.data.split("_")
        owner_id, chat_id = int(owner_raw), int(chat_raw)
        if callback.from_user.id not in (owner_id, chat_id):
            await callback.answer("Вы не участник этой партии", show_alert=True)
            return
        drop_game(chat_id, owner_id)
        try:
            await bot.edit_message_text(
                business_connection_id=get_connection_id(owner_id), chat_id=chat_id,
                message_id=callback.message.message_id,
                text="🎮 <b>Игра завершена.</b>", parse_mode="HTML"
            )
        except Exception:
            logger.exception("pvp_stop: не удалось обновить сообщение")
        await callback.answer("Игра завершена")
    except Exception:
        logger.exception("pvp_stop: непредвиденная ошибка")
        await callback.answer("Произошла ошибка", show_alert=True)


# ==========================================
#    V7: ИГРА С БОТОМ В МЕНЮ БОТА
# ==========================================

BOT_GAMES = {}


def bot_game_keyboard(board, finished=False) -> types.InlineKeyboardMarkup:
    rows = []
    for r in range(3):
        row = []
        for c in range(3):
            i = r * 3 + c
            if finished or board[i]:
                row.append(create_premium_button(text=GAME_CELL[board[i]],
                                                 callback_data="game_noop"))
            else:
                row.append(create_premium_button(text=GAME_CELL[""],
                                                 callback_data=f"tttb_mv_{i}", style="primary"))
        rows.append(row)
    rows.append([create_premium_button(text="🔄 Заново", callback_data="tttb_new",
                                       style="success")])
    rows.append([back_button("back_to_main")])
    return types.InlineKeyboardMarkup(inline_keyboard=rows)


@dp.callback_query(F.data == "tttb_new")
async def bot_game_new(callback: CallbackQuery):
    try:
        BOT_GAMES[callback.from_user.id] = [""] * 9
        await render_screen(
            callback,
            "🤖 <b>Крестики-нолики с ботом</b>\n\nВы играете ❌. Ваш ход.",
            bot_game_keyboard(BOT_GAMES[callback.from_user.id])
        )
        await callback.answer("Партия началась")
    except Exception:
        logger.exception("bot_game_new: непредвиденная ошибка")
        await callback.answer("Произошла ошибка", show_alert=True)


@dp.callback_query(F.data.startswith("tttb_mv_"))
async def bot_game_move(callback: CallbackQuery):
    try:
        idx = int(callback.data.replace("tttb_mv_", ""))
        board = BOT_GAMES.get(callback.from_user.id)
        if board is None:
            await callback.answer("Начните новую партию", show_alert=True)
            return
        if idx < 0 or idx > 8 or board[idx]:
            await callback.answer("Клетка занята", show_alert=True)
            return
        board[idx] = "X"
        status = "Ваш ход."
        finished = False
        result = game_winner(board)
        if not result:
            move = game_ai_move(board)
            if move is not None:
                board[move] = "O"
            result = game_winner(board)
        if result == "X":
            status, finished = "🏆 <b>Вы победили!</b>", True
        elif result == "O":
            status, finished = "🔴 <b>Победил бот.</b>", True
        elif result == "D":
            status, finished = "🤝 <b>Ничья.</b>", True
        BOT_GAMES[callback.from_user.id] = board
        await render_screen(
            callback,
            f"🤖 <b>Крестики-нолики с ботом</b>\n\nВы играете ❌.\n\n{status}",
            bot_game_keyboard(board, finished)
        )
        await callback.answer()
    except Exception:
        logger.exception("bot_game_move: непредвиденная ошибка")
        await callback.answer("Произошла ошибка", show_alert=True)


# ==========================================
#        V7: .ONLINE ПРЯМО В ПЕРЕПИСКЕ
# ==========================================

def online_chat_keyboard(owner_id: int, chat_id: int) -> types.InlineKeyboardMarkup:
    return types.InlineKeyboardMarkup(inline_keyboard=[[
        create_premium_button(text="🟢 Включить",
                              callback_data=f"onc_on_{owner_id}_{chat_id}", style="success"),
        create_premium_button(text="🔴 Выключить",
                              callback_data=f"onc_off_{owner_id}_{chat_id}", style="danger")
    ]])


@dp.callback_query(F.data.startswith("onc_"))
async def online_chat_controls(callback: CallbackQuery, bot: Bot):
    try:
        parts = callback.data.split("_")
        action, owner_id, chat_id = parts[1], int(parts[2]), int(parts[3])
    except Exception:
        logger.exception("online_chat_controls: некорректные данные callback")
        await callback.answer("Некорректные данные кнопки", show_alert=True)
        return

    if callback.from_user.id != owner_id:
        await callback.answer("🔴 Недостаточно прав", show_alert=True)
        return

    try:
        if not feature_enabled("feat_online"):
            await callback.answer("🔴 Функция отключена администратором", show_alert=True)
            return

        conn_id = get_connection_id(owner_id)
        if action == "on":
            save_online_state(owner_id, True, chat_id, conn_id)
            start_online_task(bot, owner_id)
            text = "🟢 <b>Онлайн активирован</b>"
            await callback.answer("🟢 Включено")
        else:
            save_online_state(owner_id, False, chat_id, conn_id)
            stop_online_task(owner_id)
            text = "🔴 <b>Онлайн выключен</b>"
            await callback.answer("🔴 Выключено")

        try:
            await bot.edit_message_text(
                business_connection_id=conn_id, chat_id=chat_id,
                message_id=callback.message.message_id, text=text, parse_mode="HTML",
                reply_markup=online_chat_keyboard(owner_id, chat_id)
            )
        except Exception:
            logger.exception("online_chat_controls: не удалось обновить сообщение")
    except Exception:
        logger.exception("online_chat_controls: непредвиденная ошибка")
        await callback.answer("Произошла ошибка", show_alert=True)


async def online_in_chat(message: Message, bot: Bot, owner_id: int) -> bool:
    if not feature_enabled("feat_online"):
        await edit_owner_message(bot, message, "🔴 Функция отключена администратором.")
        return True
    chat_id = message.chat.id
    conn_id = message.business_connection_id
    save_online_state(owner_id, get_online_state(owner_id)["enabled"], chat_id, conn_id)
    await edit_owner_message(bot, message, "🔵 Управление онлайном ниже")
    try:
        await bot.send_message(
            chat_id=chat_id, text="🔵 <b>Онлайн</b>\n\nВыберите действие.",
            parse_mode="HTML", business_connection_id=conn_id,
            reply_markup=online_chat_keyboard(owner_id, chat_id)
        )
    except Exception:
        logger.exception("online_in_chat: не удалось отправить управление")
        await edit_owner_message(
            bot, message,
            "🔴 Не удалось показать управление. Если кнопки не появляются — "
            "переподключите бизнес-бота."
        )
    return True


# ==========================================
#      V7: ПОЛНЫЙ БАН И ИСТОРИЯ
# ==========================================

def add_ban_history(user_id: int, action: str, reason: str, admin_id: int):
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO ban_history (user_id, action, reason, admin_id, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, action, reason, admin_id,
             datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        conn.commit()
        conn.close()
    except Exception:
        logger.exception("add_ban_history: не удалось записать историю")


def get_ban_history(user_id: int) -> list:
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute(
            "SELECT action, reason, admin_id, created_at FROM ban_history "
            "WHERE user_id = ? ORDER BY row_id DESC LIMIT 20", (user_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception:
        logger.exception("get_ban_history: ошибка чтения")
        return []


def get_ban_info(user_id: int) -> dict:
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute(
            "SELECT banned_at, reason, admin_id FROM global_bans WHERE user_id = ?",
            (user_id,)
        )
        row = cursor.fetchone()
        conn.close()
        if not row:
            return {}
        return {"banned_at": row[0], "reason": row[1] or "не указана", "admin_id": row[2]}
    except Exception:
        logger.exception("get_ban_info: ошибка чтения")
        return {}


def full_ban(user_id: int, reason: str, admin_id: int):
    if is_super_admin(user_id):
        return
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        row = get_user_row(user_id)
        cursor.execute(
            "INSERT OR REPLACE INTO global_bans (user_id, username, banned_at, reason, "
            "admin_id) VALUES (?, ?, ?, ?, ?)",
            (user_id, (row[4] if row else "None"),
             datetime.now().strftime("%Y-%m-%d %H:%M:%S"), reason, admin_id)
        )
        conn.commit()
        conn.close()
        add_ban_history(user_id, "ban", reason, admin_id)
        logger.info("Полный бан %s админом %s: %s", user_id, admin_id, reason)
    except Exception:
        logger.exception("full_ban: не удалось заблокировать")


def full_unban(user_id: int, admin_id: int):
    global_unban(user_id)
    add_ban_history(user_id, "unban", "", admin_id)


@dp.callback_query(F.data.startswith("banhist_"))
async def ban_history_screen(callback: CallbackQuery):
    if not has_perm(callback.from_user.id, "view_ban_history"):
        await deny(callback)
        return
    try:
        uid = int(callback.data.replace("banhist_", ""))
        info = get_ban_info(uid)
        history = get_ban_history(uid)
        text = f"🚫 <b>История блокировок</b>\n\n🆔 <code>{uid}</code>\n\n"
        if info:
            text += (f"Статус: 🔴 заблокирован\n"
                     f"Дата: <code>{info['banned_at']}</code>\n"
                     f"Причина: {html_lib.escape(str(info['reason']))}\n"
                     f"Кем: <code>{info.get('admin_id') or '—'}</code>\n\n")
        else:
            text += "Статус: 🟢 не заблокирован\n\n"
        if history:
            text += "<b>История</b>\n"
            for action, reason, admin_id, created in history:
                mark = "🔴 бан" if action == "ban" else "🟢 разбан"
                text += f"• {mark} · {created}"
                if reason:
                    text += f" · {html_lib.escape(str(reason))}"
                text += "\n"
        else:
            text += "<i>История пуста.</i>"
        rows = [[back_button(f"ucard_{uid}")],
                [create_premium_button(text="🏠 Домой", callback_data="back_to_main",
                                       style="primary")]]
        await render_screen(callback, text, types.InlineKeyboardMarkup(inline_keyboard=rows))
    except Exception:
        logger.exception("ban_history_screen: ошибка отрисовки")
    await callback.answer()


@dp.callback_query(F.data.startswith("fullban_"))
async def full_ban_start(callback: CallbackQuery, state: FSMContext):
    if not has_perm(callback.from_user.id, "manage_bans"):
        await deny(callback)
        return
    try:
        uid = int(callback.data.replace("fullban_", ""))
        if is_super_admin(uid):
            await callback.answer("👑 Главного администратора заблокировать нельзя",
                                  show_alert=True)
            return
        await state.set_state(BotStates.waiting_for_ban_reason)
        await state.update_data(ban_target=uid)
        await render_screen(
            callback,
            f"🔴 <b>Полная блокировка</b>\n\n🆔 <code>{uid}</code>\n\n"
            "Отправьте причину блокировки одним сообщением.\n"
            "Пользователь потеряет доступ ко всем функциям бота.",
            types.InlineKeyboardMarkup(inline_keyboard=[[cancel_button(f"ucard_{uid}")]])
        )
    except Exception:
        logger.exception("full_ban_start: ошибка")
    await callback.answer()


@dp.message(BotStates.waiting_for_ban_reason)
async def full_ban_reason(message: Message, state: FSMContext):
    try:
        if not has_perm(message.from_user.id, "manage_bans"):
            await state.clear()
            await message.answer("🔴 Недостаточно прав")
            return
        data = await state.get_data()
        uid = data.get("ban_target")
        await state.clear()
        reason = (message.text or "").strip() or "не указана"
        if not uid:
            await message.answer("🔴 Черновик потерян, откройте карточку заново.")
            return
        full_ban(int(uid), reason[:200], message.from_user.id)
        rows = [[create_premium_button(text="🚫 История блокировок",
                                       callback_data=f"banhist_{uid}", style="primary")],
                [back_button(f"ucard_{uid}")]]
        await message.answer(
            f"🔴 Пользователь <code>{uid}</code> полностью заблокирован.\n"
            f"Причина: {html_lib.escape(reason[:200])}",
            parse_mode="HTML",
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=rows)
        )
    except Exception:
        logger.exception("full_ban_reason: непредвиденная ошибка")
        await message.answer("🔴 Не удалось заблокировать пользователя.")


# ==========================================
#   V7: HTML-ЭКСПОРТ ПО СОБЕСЕДНИКАМ
# ==========================================

EXPORT_CSS = """
body { font-family: -apple-system, Segoe UI, Roboto, sans-serif; background: #eef1f7;
       margin: 0; padding: 24px; color: #14171a; }
.wrap { max-width: 900px; margin: 0 auto; }
h1 { font-size: 22px; margin: 0 0 6px; }
.meta { color: #6b7280; font-size: 13px; margin-bottom: 20px; }
.peer { background: #fff; border-radius: 14px; margin-bottom: 18px; overflow: hidden;
        box-shadow: 0 1px 4px rgba(0,0,0,.08); }
.peer > summary { cursor: pointer; padding: 16px 20px; font-weight: 600; font-size: 15px;
                  list-style: none; display: flex; justify-content: space-between; }
.peer > summary::-webkit-details-marker { display: none; }
.count { color: #6b7280; font-weight: 400; font-size: 13px; }
.chat { padding: 12px 20px 20px; background: #f7f9fc; }
.msg { max-width: 72%; padding: 9px 13px; border-radius: 14px; margin-bottom: 10px;
       font-size: 14px; word-break: break-word; }
.msg.in { background: #fff; border: 1px solid #e3e8ef; }
.msg.out { background: #d7f0d5; margin-left: auto; }
.msg .who { font-size: 11px; color: #6b7280; margin-bottom: 3px; }
.msg .time { font-size: 10px; color: #9ca3af; margin-top: 4px; text-align: right; }
.msg.deleted { background: #fee2e2; border: 1px solid #fca5a5; }
.msg.edited { background: #fef3c7; border: 1px solid #fcd34d; }
.att { display: inline-block; font-size: 12px; padding: 2px 8px; border-radius: 10px;
       background: #e5e7eb; color: #374151; }
.old { color: #9ca3af; text-decoration: line-through; }
.search { width: 100%; padding: 10px 14px; border-radius: 10px; border: 1px solid #d1d5db;
          margin-bottom: 18px; font-size: 14px; }
"""

EXPORT_JS = """
function filterPeers(){
  var q = document.getElementById('q').value.toLowerCase();
  document.querySelectorAll('.peer').forEach(function(p){
    p.style.display = p.innerText.toLowerCase().indexOf(q) >= 0 ? '' : 'none';
  });
}
"""

MEDIA_LABEL = {
    "photo": "🖼 фотография", "video": "🎬 видео", "animation": "🎞 GIF",
    "sticker": "🩵 стикер", "voice": "🎤 голосовое", "audio": "🎵 аудио",
    "video_note": "⭕ видеосообщение", "document": "📄 документ", "text": "",
}


def collect_by_peer(owner_id: int) -> dict:
    peers = {}
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute(
            "SELECT chat_id, from_id, direction, media_type, text_content, created_at "
            "FROM msg_log WHERE owner_id = ? ORDER BY row_id", (owner_id,)
        )
        for chat_id, from_id, direction, media_type, text, created in cursor.fetchall():
            peers.setdefault(chat_id, []).append({
                "kind": "msg", "from_id": from_id, "direction": direction,
                "media_type": media_type, "text": text, "date": created
            })
        cursor.execute(
            "SELECT chat_id, from_id, media_type, text_content, deleted_at "
            "FROM deleted_log WHERE owner_id = ? ORDER BY row_id", (owner_id,)
        )
        for chat_id, from_id, media_type, text, created in cursor.fetchall():
            peers.setdefault(chat_id, []).append({
                "kind": "deleted", "from_id": from_id, "direction": "in",
                "media_type": media_type, "text": text, "date": created
            })
        cursor.execute(
            "SELECT chat_id, from_id, old_text, new_text, edited_at "
            "FROM edited_log WHERE owner_id = ? ORDER BY row_id", (owner_id,)
        )
        for chat_id, from_id, old_text, new_text, created in cursor.fetchall():
            peers.setdefault(chat_id, []).append({
                "kind": "edited", "from_id": from_id, "direction": "in",
                "media_type": "text", "old": old_text, "text": new_text, "date": created
            })
        conn.close()
    except Exception:
        logger.exception("collect_by_peer: ошибка сбора данных")
    for chat_id in peers:
        peers[chat_id].sort(key=lambda item: item.get("date") or "")
    return peers


def peer_title(chat_id: int) -> str:
    row = get_user_row(chat_id)
    if row:
        name = " ".join(filter(None, [row[2], row[3]])) or f"ID {chat_id}"
        if row[4]:
            name += f" @{row[4]}"
        return name
    return f"ID {chat_id}"


def build_export_html(owner_id: int, peers: dict) -> str:
    generated = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    total = sum(len(v) for v in peers.values())
    parts = [
        "<!DOCTYPE html><html lang='ru'><head><meta charset='utf-8'>",
        f"<title>Переписки {owner_id}</title><style>{EXPORT_CSS}</style></head><body>",
        "<div class='wrap'>",
        f"<h1>Экспорт переписок — {html_lib.escape(peer_title(owner_id))}</h1>",
        f"<div class='meta'>Владелец: {owner_id} · Собеседников: {len(peers)} · "
        f"Записей: {total} · Сформировано: {generated}</div>",
        "<input class='search' id='q' oninput='filterPeers()' "
        "placeholder='Поиск по собеседникам и сообщениям...'>",
    ]

    if not peers:
        parts.append("<div class='peer'><summary>Данных пока нет</summary></div>")

    for chat_id, items in peers.items():
        parts.append(
            f"<details class='peer'><summary>👤 {html_lib.escape(peer_title(chat_id))}"
            f"<span class='count'>{len(items)} записей</span></summary><div class='chat'>"
        )
        for item in items:
            direction = "out" if item.get("direction") == "out" else "in"
            who = "Вы" if direction == "out" else html_lib.escape(peer_title(chat_id))
            css = direction
            body = ""
            if item["kind"] == "deleted":
                css += " deleted"
                who += " · удалено"
            elif item["kind"] == "edited":
                css += " edited"
                who += " · изменено"
                body += (f"<div class='old'>{html_lib.escape(item.get('old') or '—')}</div>")
            label = MEDIA_LABEL.get(item.get("media_type") or "text", "")
            if label:
                body += f"<div class='att'>{label}</div>"
            text_value = item.get("text") or ""
            if text_value and item.get("media_type") == "text":
                body += f"<div>{text_value}</div>"
            elif text_value and label:
                body += f"<div class='att'>{html_lib.escape(str(text_value)[:60])}</div>"
            if not body:
                body = "<div class='att'>без содержимого</div>"
            parts.append(
                f"<div class='msg {css}'><div class='who'>{who}</div>{body}"
                f"<div class='time'>{item.get('date') or ''}</div></div>"
            )
        parts.append("</div></details>")

    parts.append(f"</div><script>{EXPORT_JS}</script></body></html>")
    return "".join(parts)




async def send_single_mute_message(message: Message, bot: Bot, owner_id: int, chat_id: int):
    text = ("🔇 <b>Пользователь замьючен</b>\n\n"
            "Чтобы снять мут, используйте <code>.unmute</code>")
    kb = mute_keyboard(owner_id, chat_id)
    conn_id = message.business_connection_id
    try:
        await bot.edit_message_text(
            business_connection_id=conn_id, chat_id=chat_id,
            message_id=message.message_id, text=text, parse_mode="HTML", reply_markup=kb
        )
        return
    except Exception:
        logger.exception("mute: не удалось добавить кнопку в исходное сообщение")
    try:
        await bot.delete_business_messages(business_connection_id=conn_id,
                                           message_ids=[message.message_id])
        await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML",
                               business_connection_id=conn_id, reply_markup=kb)
        return
    except Exception:
        logger.exception("mute: не удалось заменить сообщение на сообщение с кнопкой")
    await edit_owner_message(bot, message, text)

# ==========================================
#   V6: ЕДИНЫЙ СТИЛЬ, ЭМОДЗИ, РАЗДЕЛЫ
# ==========================================

BACK_EMOJI = "5255703720078879"
CANCEL_EMOJI = "521095253167650451"
CHANNEL_EMOJI = "5427168083074628963"
CONNECT_URL = "tg://settings/edit"

SECTIONS = [
    ("main", "🏠 Главное меню"),
    ("profile", "👤 Профиль"),
    ("settings", "⚙️ Настройки"),
    ("instruction", "📘 Инструкция"),
    ("support", "🆘 Тех. поддержка"),
    ("commands", "📋 Команды"),
    ("connect", "🔌 Подключение бота"),
    ("admin", "👑 Админ-панель"),
    ("subscribe", "📢 Подписка"),
]
SECTION_NAMES = dict(SECTIONS)

TIMEZONES = [
    (2, "Калининград"), (3, "Москва"), (4, "Самара"), (5, "Екатеринбург"),
    (6, "Омск"), (7, "Красноярск"), (8, "Иркутск"), (9, "Якутск"),
    (10, "Владивосток"), (11, "Магадан"), (12, "Камчатка"),
    (0, "Лондон"), (1, "Берлин"),
]
TZ_NAMES = dict(TIMEZONES)


def back_button(callback_data: str) -> types.InlineKeyboardButton:
    return create_premium_button(text="Назад", callback_data=callback_data,
                                 style="primary", icon_custom_emoji_id=BACK_EMOJI)


def cancel_button(callback_data: str = "back_to_main",
                  label: str = "Отмена") -> types.InlineKeyboardButton:
    return create_premium_button(text=label, callback_data=callback_data,
                                 style="danger", icon_custom_emoji_id=CANCEL_EMOJI)


def copy_username_button() -> types.InlineKeyboardButton:
    data = {"text": "📋 Скопировать username",
            "copy_text": types.CopyTextButton(text=f"@{BOT_PUBLIC_USERNAME}")}
    try:
        return types.InlineKeyboardButton(style="primary", **data)
    except Exception:
        logger.exception("copy_username_button: style не поддержан")
        return types.InlineKeyboardButton(**data)


def connect_button() -> types.InlineKeyboardButton:
    return create_premium_button(text="➕ Подключить", url=CONNECT_URL, style="success")


def init_v6_tables():
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS menu_sections (
                key TEXT PRIMARY KEY,
                title TEXT,
                body TEXT,
                photo TEXT,
                enabled INTEGER DEFAULT 1
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS nicktime_state (
                owner_id INTEGER PRIMARY KEY,
                enabled INTEGER DEFAULT 0,
                base_first TEXT,
                base_last TEXT,
                connection_id TEXT,
                updated_at TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS obhod_state (
                owner_id INTEGER,
                chat_id INTEGER,
                enabled INTEGER DEFAULT 1,
                updated_at TEXT,
                PRIMARY KEY (owner_id, chat_id)
            )
        """)
        try:
            cursor.execute("ALTER TABLE nicktime_state ADD COLUMN tz_offset INTEGER DEFAULT 3")
        except Exception:
            pass
        for key, title in SECTIONS:
            cursor.execute(
                "INSERT OR IGNORE INTO menu_sections (key, title, body, photo, enabled) "
                "VALUES (?, ?, '', '', 1)", (key, title)
            )
        conn.commit()
        conn.close()
    except Exception:
        logger.exception("init_v6_tables: не удалось подготовить таблицы")


init_v6_tables()


def get_section(key: str) -> dict:
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT title, body, photo, enabled FROM menu_sections WHERE key = ?",
                       (key,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return {"title": SECTION_NAMES.get(key, key), "body": "", "photo": "",
                    "enabled": True}
        return {"title": row[0] or SECTION_NAMES.get(key, key), "body": row[1] or "",
                "photo": row[2] or "", "enabled": bool(row[3])}
    except Exception:
        logger.exception("get_section: ошибка чтения раздела %s", key)
        return {"title": SECTION_NAMES.get(key, key), "body": "", "photo": "", "enabled": True}


def set_section_field(key: str, field: str, value):
    if field not in ("title", "body", "photo", "enabled"):
        return
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO menu_sections (key, title, body, photo, enabled) "
            "VALUES (?, ?, '', '', 1)", (key, SECTION_NAMES.get(key, key))
        )
        cursor.execute(f"UPDATE menu_sections SET {field} = ? WHERE key = ?", (value, key))
        conn.commit()
        conn.close()
        logger.info("Раздел %s: поле %s обновлено", key, field)
    except Exception:
        logger.exception("set_section_field: не удалось сохранить раздел %s", key)


def section_photo(key: str, fallback: str = None) -> str:
    photo = get_section(key).get("photo")
    return photo or (fallback or START_IMAGE_URL)


# ==========================================
#      V6: ГЕЙТ ПОДКЛЮЧЕНИЯ БИЗНЕС-БОТА
# ==========================================

def gate_keyboard() -> types.InlineKeyboardMarkup:
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [copy_username_button(), connect_button()],
        [create_premium_button(text="🔄 Я подключил", callback_data="gate_check",
                               style="success")]
    ])


def gate_text() -> str:
    custom = get_section("connect").get("body")
    if custom:
        return custom
    return (
        "🔵 <b>Сначала подключите бота к аккаунту</b>\n\n"
        "1. Нажмите «📋 Скопировать».\n"
        "2. Нажмите «➕ Подключить».\n"
        "3. Откройте раздел «Чат-боты» / «Автоматизация чатов».\n"
        "4. Вставьте имя бота:\n\n"
        f"<code>@{BOT_PUBLIC_USERNAME}</code>\n\n"
        "5. Разрешите боту нужные права и вернитесь сюда.\n\n"
        "Если раздела нет — обновите Telegram до последней версии."
    )


def gate_passed(user_id: int) -> bool:
    try:
        if get_flag("gate_enabled", "1") != "1":
            return True
        if is_bot_admin(user_id):
            return True
        return bool(get_connection_id(user_id))
    except Exception:
        logger.exception("gate_passed: ошибка проверки подключения")
        return True


@dp.callback_query(F.data == "gate_check")
async def gate_check(callback: CallbackQuery):
    try:
        if gate_passed(callback.from_user.id):
            text, kb = get_main_menu_data(callback.from_user.id)
            await render_screen(callback, text, kb)
            await callback.answer("🟢 Подключение найдено")
            return
        await callback.answer(
            "🔴 Подключение не найдено. Добавьте бота в «Чат-боты» и повторите.",
            show_alert=True
        )
    except Exception:
        logger.exception("gate_check: непредвиденная ошибка")
        await callback.answer("Произошла ошибка", show_alert=True)


# ==========================================
#        V6: ЧАСОВОЙ ПОЯС ДЛЯ НИКА
# ==========================================

def get_tz_offset(owner_id: int) -> int:
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT tz_offset FROM nicktime_state WHERE owner_id = ?", (owner_id,))
        row = cursor.fetchone()
        conn.close()
        if row and row[0] is not None:
            return int(row[0])
    except Exception:
        logger.exception("get_tz_offset: ошибка чтения")
    return 3


def set_tz_offset(owner_id: int, offset: int):
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO nicktime_state (owner_id, enabled, base_first, base_last, "
            "connection_id, updated_at) VALUES (?, 0, '', '', '', ?)",
            (owner_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        cursor.execute("UPDATE nicktime_state SET tz_offset = ? WHERE owner_id = ?",
                       (offset, owner_id))
        conn.commit()
        conn.close()
        logger.info("Часовой пояс для %s -> UTC+%s", owner_id, offset)
    except Exception:
        logger.exception("set_tz_offset: не удалось сохранить пояс")


def tz_now(owner_id: int) -> datetime:
    return datetime.utcnow() + timedelta(hours=get_tz_offset(owner_id))


def timezone_keyboard(owner_id: int) -> types.InlineKeyboardMarkup:
    current = get_tz_offset(owner_id)
    rows, buf = [], []
    for offset, city in TIMEZONES:
        mark = "🟢" if offset == current else "⚪"
        buf.append(create_premium_button(
            text=f"{mark} UTC+{offset} {city}",
            callback_data=f"tzs_{owner_id}_{offset}",
            style="success" if offset == current else "primary"
        ))
        if len(buf) == 2:
            rows.append(buf)
            buf = []
    if buf:
        rows.append(buf)
    rows.append([back_button(f"ntm_panel_{owner_id}")])
    return types.InlineKeyboardMarkup(inline_keyboard=rows)


@dp.callback_query(F.data.startswith("tzs_"))
async def timezone_select(callback: CallbackQuery):
    try:
        _, owner_raw, offset_raw = callback.data.split("_")
        owner_id, offset = int(owner_raw), int(offset_raw)
    except Exception:
        logger.exception("timezone_select: некорректные данные callback")
        await callback.answer("Некорректные данные кнопки", show_alert=True)
        return
    if (callback.from_user.id != owner_id
            and not has_perm(callback.from_user.id, "manage_profile_time")):
        await deny(callback)
        return
    try:
        set_tz_offset(owner_id, offset)
        await render_screen(
            callback,
            f"🕒 <b>Часовой пояс</b>\n\nВыбран: <b>UTC+{offset} "
            f"({TZ_NAMES.get(offset, '')})</b>\nСейчас: "
            f"<code>{tz_now(owner_id).strftime('%H:%M')}</code>",
            timezone_keyboard(owner_id)
        )
        await callback.answer(f"🟢 UTC+{offset}")
    except Exception:
        logger.exception("timezone_select: непредвиденная ошибка")
        await callback.answer("Произошла ошибка", show_alert=True)


@dp.callback_query(F.data.startswith("tzopen_"))
async def timezone_open(callback: CallbackQuery):
    try:
        owner_id = int(callback.data.replace("tzopen_", ""))
        await render_screen(
            callback,
            f"🕒 <b>Часовой пояс</b>\n\nТекущий: <b>UTC+{get_tz_offset(owner_id)}</b>\n"
            f"Время сейчас: <code>{tz_now(owner_id).strftime('%H:%M')}</code>\n\n"
            "Выберите город или смещение.",
            timezone_keyboard(owner_id)
        )
    except Exception:
        logger.exception("timezone_open: ошибка отрисовки")
    await callback.answer()


@dp.callback_query(F.data.startswith("ntm_panel_"))
async def nicktime_panel(callback: CallbackQuery):
    try:
        owner_id = int(callback.data.replace("ntm_panel_", ""))
        await render_screen(callback, nicktime_panel_text(owner_id),
                            nicktime_keyboard_v6(owner_id))
    except Exception:
        logger.exception("nicktime_panel: ошибка отрисовки")
    await callback.answer()


def nicktime_panel_text(owner_id: int) -> str:
    state = get_nicktime_state(owner_id)
    base = state["base_first"] or "Имя"
    offset = get_tz_offset(owner_id)
    return (
        "🔵 <b>Время в имени</b>\n\n"
        f"Формат: <code>{html_lib.escape(base)} | "
        f"{tz_now(owner_id).strftime('%H:%M')}</code>\n"
        f"Часовой пояс: <b>UTC+{offset} ({TZ_NAMES.get(offset, '')})</b>\n"
        f"Статус: {'🟢 включено' if state['enabled'] else '🔴 выключено'}\n\n"
        "Имя обновляется примерно раз в минуту."
    )


def nicktime_keyboard_v6(owner_id: int) -> types.InlineKeyboardMarkup:
    state = get_nicktime_state(owner_id)
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [
            create_premium_button(text="🟢 Включить", callback_data=f"ntm_on_{owner_id}",
                                  style="success"),
            create_premium_button(text="🔴 Выключить", callback_data=f"ntm_off_{owner_id}",
                                  style="danger")
        ],
        [create_premium_button(text="🕒 Часовой пояс", callback_data=f"tzopen_{owner_id}",
                               style="primary")],
        [create_premium_button(
            text=f"🔵 Статус: {'включено' if state['enabled'] else 'выключено'}",
            callback_data=f"ntm_st_{owner_id}", style="primary")]
    ])


def permission_keyboard() -> types.InlineKeyboardMarkup:
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [create_premium_button(text="🟢 Выдать разрешение", url=CONNECT_URL, style="success")]
    ])


# ==========================================
#            V6: РЕДАКТОР РАЗДЕЛОВ
# ==========================================

def render_sections_screen(page: int = 0):
    items, page, total = paginate_list(SECTIONS, page)
    text = (
        "🖼 <b>Разделы бота</b>\n\n"
        "У каждого раздела можно поменять фотографию, текст и включить или выключить его.\n\n"
    )
    rows = []
    for key, title in items:
        sec = get_section(key)
        mark = "🟢" if sec["enabled"] else "🔴"
        has_photo = "🖼" if sec["photo"] else "⚪"
        text += f"{mark} {title} {has_photo}\n"
        rows.append([create_premium_button(text=f"{mark} {title}", callback_data=f"sec_{key}",
                                           style="primary")])
    nav = page_row("secp_", page, total)
    if nav:
        rows.append(nav)
    rows.append(nav_rows()[0])
    rows.append(nav_rows()[1])
    return text, types.InlineKeyboardMarkup(inline_keyboard=rows)


@dp.callback_query(F.data == "adm_sections")
async def sections_menu(callback: CallbackQuery):
    if not has_perm(callback.from_user.id, "manage_menu"):
        await deny(callback)
        return
    try:
        text, kb = render_sections_screen(0)
        await render_screen(callback, text, kb)
    except Exception:
        logger.exception("sections_menu: ошибка отрисовки")
    await callback.answer()


@dp.callback_query(F.data.startswith("secp_"))
async def sections_page(callback: CallbackQuery):
    if not has_perm(callback.from_user.id, "manage_menu"):
        await deny(callback)
        return
    try:
        text, kb = render_sections_screen(int(callback.data.replace("secp_", "")))
        await render_screen(callback, text, kb)
    except Exception:
        logger.exception("sections_page: ошибка отрисовки")
    await callback.answer()


def render_section_card(key: str):
    sec = get_section(key)
    text = (
        f"🖼 <b>{html_lib.escape(sec['title'])}</b>\n\n"
        f"Статус: {'🟢 включён' if sec['enabled'] else '🔴 выключен'}\n"
        f"Фото: {'🖼 задано' if sec['photo'] else '⚪ по умолчанию'}\n"
        f"Свой текст: {'✅ есть' if sec['body'] else '⚪ нет'}\n\n"
    )
    if sec["body"]:
        text += f"<blockquote>{sec['body'][:400]}</blockquote>"
    rows = [
        [create_premium_button(text="🖼 Изменить фото", callback_data=f"secph_{key}",
                               style="primary")],
        [create_premium_button(text="📝 Изменить текст", callback_data=f"sectx_{key}",
                               style="primary")],
    ]
    if sec["photo"]:
        rows.append([create_premium_button(text="🗑 Удалить фото",
                                           callback_data=f"secdel_{key}", style="danger")])
    rows.append([toggle_button("Раздел включён", sec["enabled"], f"sectg_{key}")])
    rows.append([back_button("adm_sections")])
    rows.append([create_premium_button(text="🏠 Домой", callback_data="back_to_main",
                                       style="primary")])
    return text, types.InlineKeyboardMarkup(inline_keyboard=rows)


@dp.callback_query(F.data.startswith("sec_"))
async def section_card(callback: CallbackQuery):
    if not has_perm(callback.from_user.id, "manage_menu"):
        await deny(callback)
        return
    try:
        key = callback.data.replace("sec_", "")
        text, kb = render_section_card(key)
        await render_screen(callback, text, kb)
    except Exception:
        logger.exception("section_card: ошибка отрисовки")
    await callback.answer()


@dp.callback_query(F.data.startswith("sectg_"))
async def section_toggle(callback: CallbackQuery):
    if not has_perm(callback.from_user.id, "manage_menu"):
        await deny(callback)
        return
    try:
        key = callback.data.replace("sectg_", "")
        sec = get_section(key)
        set_section_field(key, "enabled", 0 if sec["enabled"] else 1)
        text, kb = render_section_card(key)
        await render_screen(callback, text, kb)
        await callback.answer("🔴 Выключен" if sec["enabled"] else "🟢 Включён")
    except Exception:
        logger.exception("section_toggle: непредвиденная ошибка")
        await callback.answer("Произошла ошибка", show_alert=True)


@dp.callback_query(F.data.startswith("secdel_"))
async def section_photo_delete(callback: CallbackQuery):
    if not has_perm(callback.from_user.id, "manage_menu_photos"):
        await deny(callback)
        return
    try:
        key = callback.data.replace("secdel_", "")
        rows = [
            [create_premium_button(text="✅ Да, удалить", callback_data=f"secdelok_{key}",
                                   style="success")],
            [cancel_button(f"sec_{key}")]
        ]
        await render_screen(
            callback,
            "⚠️ <b>Вы уверены?</b>\n\nФото раздела будет удалено, вернётся изображение "
            "по умолчанию.",
            types.InlineKeyboardMarkup(inline_keyboard=rows)
        )
    except Exception:
        logger.exception("section_photo_delete: ошибка")
    await callback.answer()


@dp.callback_query(F.data.startswith("secdelok_"))
async def section_photo_delete_apply(callback: CallbackQuery):
    if not has_perm(callback.from_user.id, "manage_menu_photos"):
        await deny(callback)
        return
    try:
        key = callback.data.replace("secdelok_", "")
        set_section_field(key, "photo", "")
        text, kb = render_section_card(key)
        await render_screen(callback, text, kb)
        await callback.answer("🗑 Фото удалено")
    except Exception:
        logger.exception("section_photo_delete_apply: непредвиденная ошибка")
        await callback.answer("Произошла ошибка", show_alert=True)


@dp.callback_query(F.data.startswith("secph_"))
async def section_photo_start(callback: CallbackQuery, state: FSMContext):
    if not has_perm(callback.from_user.id, "manage_menu_photos"):
        await deny(callback)
        return
    try:
        key = callback.data.replace("secph_", "")
        await state.set_state(BotStates.waiting_for_section_photo)
        await state.update_data(section_key=key)
        await render_screen(
            callback,
            f"🖼 <b>Новое фото раздела</b>\n\n«{html_lib.escape(get_section(key)['title'])}»\n\n"
            "Отправьте фотографию или прямую ссылку на изображение.",
            types.InlineKeyboardMarkup(inline_keyboard=[[cancel_button(f"sec_{key}")]])
        )
    except Exception:
        logger.exception("section_photo_start: ошибка")
    await callback.answer()


@dp.message(BotStates.waiting_for_section_photo)
async def section_photo_save(message: Message, state: FSMContext):
    try:
        if not has_perm(message.from_user.id, "manage_menu_photos"):
            await state.clear()
            await message.answer("🔴 Недостаточно прав")
            return
        data = await state.get_data()
        key = data.get("section_key")
        await state.clear()
        value = ""
        if message.photo:
            value = message.photo[-1].file_id
        elif message.text and message.text.strip().startswith("http"):
            value = message.text.strip()
        if not value or not key:
            await message.answer("🔴 Пришлите фотографию или прямую ссылку на изображение.")
            return
        set_section_field(key, "photo", value)
        text, kb = render_section_card(key)
        await message.answer(f"🟢 Фото раздела обновлено.\n\n{text}", parse_mode="HTML",
                             reply_markup=kb)
    except Exception:
        logger.exception("section_photo_save: непредвиденная ошибка")
        await message.answer("🔴 Не удалось сохранить фото.")


@dp.callback_query(F.data.startswith("sectx_"))
async def section_text_start(callback: CallbackQuery, state: FSMContext):
    if not has_perm(callback.from_user.id, "manage_menu_text"):
        await deny(callback)
        return
    try:
        key = callback.data.replace("sectx_", "")
        await state.set_state(BotStates.waiting_for_section_text)
        await state.update_data(section_key=key)
        await render_screen(
            callback,
            f"📝 <b>Новый текст раздела</b>\n\n«{html_lib.escape(get_section(key)['title'])}»\n\n"
            "Отправьте текст. Форматирование сохранится.\n"
            "Отправьте «-», чтобы вернуть текст по умолчанию.",
            types.InlineKeyboardMarkup(inline_keyboard=[[cancel_button(f"sec_{key}")]])
        )
    except Exception:
        logger.exception("section_text_start: ошибка")
    await callback.answer()


@dp.message(BotStates.waiting_for_section_text)
async def section_text_save(message: Message, state: FSMContext):
    try:
        if not has_perm(message.from_user.id, "manage_menu_text"):
            await state.clear()
            await message.answer("🔴 Недостаточно прав")
            return
        data = await state.get_data()
        key = data.get("section_key")
        await state.clear()
        if not key:
            await message.answer("🔴 Черновик потерян, откройте раздел заново.")
            return
        raw = (message.text or "").strip()
        if raw == "-":
            set_section_field(key, "body", "")
        else:
            try:
                set_section_field(key, "body", message.html_text or raw)
            except Exception:
                set_section_field(key, "body", raw)
        text, kb = render_section_card(key)
        await message.answer(f"🟢 Текст раздела обновлён.\n\n{text}", parse_mode="HTML",
                             reply_markup=kb)
    except Exception:
        logger.exception("section_text_save: непредвиденная ошибка")
        await message.answer("🔴 Не удалось сохранить текст.")


# ==========================================
#          V6: ПОИСК ПОЛЬЗОВАТЕЛЕЙ
# ==========================================

def search_users(query: str) -> list:
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute(
            "SELECT user_id, first_name, username, last_active, last_name FROM users "
            "ORDER BY COALESCE(last_active, created_at) DESC"
        )
        rows = cursor.fetchall()
        conn.close()
        needle = query.lower().lstrip("@")
        found = []
        for r in rows:
            haystack = " ".join([
                str(r[0]), str(r[1] or ""), str(r[2] or ""), str(r[4] or "")
            ]).lower()
            if needle in haystack:
                found.append((r[0], r[1], r[2], r[3]))
            if len(found) >= 60:
                break
        return found
    except Exception:
        logger.exception("search_users: ошибка поиска")
        return []


@dp.callback_query(F.data == "usr_search")
async def user_search_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await deny(callback)
        return
    try:
        await state.set_state(BotStates.waiting_for_user_search)
        await render_screen(
            callback,
            "🔎 <b>Поиск пользователя</b>\n\n"
            "Отправьте имя, @username или ID.\n"
            "Поиск нестрогий: часть имени тоже подойдёт.",
            types.InlineKeyboardMarkup(inline_keyboard=[[cancel_button("adm_users")]])
        )
    except Exception:
        logger.exception("user_search_start: ошибка")
    await callback.answer()


@dp.message(BotStates.waiting_for_user_search)
async def user_search_process(message: Message, state: FSMContext):
    try:
        if not is_admin(message.from_user.id):
            await state.clear()
            return
        await state.clear()
        query = (message.text or "").strip().lstrip("@")
        if not query:
            await message.answer("🔴 Пустой запрос.")
            return
        found = search_users(query)
        if not found:
            await message.answer(
                f"⚪ По запросу «{html_lib.escape(query)}» никого не нашлось.",
                parse_mode="HTML",
                reply_markup=types.InlineKeyboardMarkup(
                    inline_keyboard=[[back_button("adm_users")]])
            )
            return
        text = f"🔎 <b>Результаты поиска</b> · найдено {len(found)}\n\n"
        rows = []
        for u in found[:10]:
            label = u[1] or f"ID {u[0]}"
            if u[2]:
                label += f" @{u[2]}"
            text += f"• {html_lib.escape(label)} — <code>{u[0]}</code>\n"
            rows.append([create_premium_button(text=f"👤 {label[:35]}",
                                               callback_data=f"ucard_{u[0]}", style="primary")])
        if len(found) > 10:
            text += f"\n<i>Показаны первые 10 из {len(found)}.</i>"
        rows.append([back_button("adm_users")])
        await message.answer(text, parse_mode="HTML",
                             reply_markup=types.InlineKeyboardMarkup(inline_keyboard=rows))
    except Exception:
        logger.exception("user_search_process: непредвиденная ошибка")
        await message.answer("🔴 Ошибка поиска.")


# ==========================================
#        V6: РАСШИРЕННАЯ СТАТИСТИКА
# ==========================================

def count_since(table: str, column: str, hours: int) -> int:
    try:
        border = (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE {column} >= ?", (border,))
        value = cursor.fetchone()[0]
        conn.close()
        return value
    except Exception:
        logger.exception("count_since: ошибка подсчёта по %s", table)
        return 0


@dp.callback_query(F.data == "adm_fullstats")
async def full_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await deny(callback)
        return
    try:
        text = (
            "📈 <b>Точная статистика</b>\n\n"
            "<b>Пользователи</b>\n"
            f"• Всего: <b>{get_users_count()}</b>\n"
            f"• Новых за 24 часа: <b>{count_since('users', 'created_at', 24)}</b>\n"
            f"• Новых за неделю: <b>{count_since('users', 'created_at', 168)}</b>\n"
            f"• Активных за 24 часа: <b>{count_since('users', 'last_active', 24)}</b>\n\n"
            "<b>Сообщения</b>\n"
            f"• Сохранено всего: <b>{count_all('msg_log')}</b>\n"
            f"• За 24 часа: <b>{count_since('msg_log', 'created_at', 24)}</b>\n"
            f"• Удалений в логах: <b>{count_all('deleted_log')}</b>\n"
            f"• Удалений за 24 часа: <b>{count_since('deleted_log', 'deleted_at', 24)}</b>\n"
            f"• Правок в логах: <b>{count_all('edited_log')}</b>\n"
            f"• Правок за 24 часа: <b>{count_since('edited_log', 'edited_at', 24)}</b>\n\n"
            "<b>Система</b>\n"
            f"• Бизнес-подключений: <b>{get_active_business_count()}</b>\n"
            f"• Чатов в мьюте: <b>{get_muted_count()}</b>\n"
            f"• Обход мута активен: <b>{count_all('obhod_state')}</b>\n"
            f"• Скрытых (whitelist): <b>{len(whitelist_all())}</b>\n"
            f"• Глобальных банов: <b>{len(get_global_bans())}</b>\n"
            f"• Обязательных каналов: <b>{len(get_req_channels())}</b>\n"
            f"• Активных фоновых задач: <b>{len(BG_TASKS)}</b>\n"
            f"• Кастомных команд: <b>{len(get_custom_commands())}</b>\n"
            f"• Кастомных кнопок: <b>{len(get_custom_buttons())}</b>\n"
            f"• Режим работы: <b>{MODE_TITLES.get(get_bot_mode())}</b>"
        )
        rows = [[create_premium_button(text="🔄 Обновить", callback_data="adm_fullstats",
                                       style="success")]]
        rows.append(nav_rows()[0])
        rows.append(nav_rows()[1])
        await render_screen(callback, text, types.InlineKeyboardMarkup(inline_keyboard=rows))
    except Exception:
        logger.exception("full_stats: ошибка отрисовки")
    await callback.answer()


# ==========================================
#          V6: ОБХОД МУТА (.obhod)
# ==========================================

def obhod_enabled(owner_id: int, chat_id: int) -> bool:
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute(
            "SELECT enabled FROM obhod_state WHERE owner_id = ? AND chat_id = ?",
            (owner_id, chat_id)
        )
        row = cursor.fetchone()
        conn.close()
        return bool(row and row[0])
    except Exception:
        logger.exception("obhod_enabled: ошибка чтения")
        return False


def set_obhod(owner_id: int, chat_id: int, enabled: bool):
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        if enabled:
            cursor.execute(
                "INSERT OR REPLACE INTO obhod_state (owner_id, chat_id, enabled, updated_at) "
                "VALUES (?, ?, 1, ?)",
                (owner_id, chat_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            )
        else:
            cursor.execute("DELETE FROM obhod_state WHERE owner_id = ? AND chat_id = ?",
                           (owner_id, chat_id))
        conn.commit()
        conn.close()
        logger.info("Обход мута для %s в чате %s -> %s", owner_id, chat_id, enabled)
    except Exception:
        logger.exception("set_obhod: не удалось сохранить состояние")


async def obhod_echo(message: Message, bot: Bot, owner_id: int):
    try:
        if not feature_enabled("feat_obhod"):
            return
        if not obhod_enabled(owner_id, message.chat.id):
            return
        raw = (message.text or "").strip()
        if not raw or raw.startswith("."):
            return
        try:
            body = message.html_text or raw
        except Exception:
            body = raw
        await bot.send_message(
            chat_id=message.chat.id,
            text=body,
            parse_mode="HTML",
            business_connection_id=message.business_connection_id
        )
    except Exception:
        logger.exception("obhod_echo: не удалось продублировать сообщение")


# ==========================================
#            V6: НОВЫЕ КОМАНДЫ
# ==========================================

EIGHT_BALL = [
    "Бесспорно", "Мне кажется — да", "Пока неясно, попробуй снова",
    "Даже не думай", "Определённо да", "Никаких сомнений",
    "Весьма сомнительно", "Знаки говорят — да", "Мой ответ — нет",
]


def safe_eval_expr(expr: str):
    import ast as _ast
    import operator as _op
    ops = {
        _ast.Add: _op.add, _ast.Sub: _op.sub, _ast.Mult: _op.mul,
        _ast.Div: _op.truediv, _ast.Pow: _op.pow, _ast.Mod: _op.mod,
        _ast.FloorDiv: _op.floordiv, _ast.USub: _op.neg, _ast.UAdd: _op.pos,
    }

    def walk(node):
        if isinstance(node, _ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, _ast.BinOp) and type(node.op) in ops:
            return ops[type(node.op)](walk(node.left), walk(node.right))
        if isinstance(node, _ast.UnaryOp) and type(node.op) in ops:
            return ops[type(node.op)](walk(node.operand))
        raise ValueError("bad expression")

    return walk(_ast.parse(expr, mode="eval").body)


async def handle_v6_command(message: Message, bot: Bot, owner_id: int, trigger: str,
                            arg: str, arg_html: str) -> bool:
    chat_id = message.chat.id
    try:
        if trigger == ".obhod":
            if not feature_enabled("feat_obhod"):
                await edit_owner_message(bot, message, "🔴 Функция отключена администратором.")
                return True
            set_obhod(owner_id, chat_id, True)
            await edit_owner_message(
                bot, message,
                "🟢 <b>Обход мута включён</b>\n\n"
                "Каждое ваше сообщение в этом чате будет продублировано ботом.\n"
                "Выключить: <code>.obhodoff</code>"
            )
            return True

        if trigger == ".obhodoff":
            set_obhod(owner_id, chat_id, False)
            await edit_owner_message(bot, message, "🔴 <b>Обход мута выключен</b>")
            return True

        if trigger == ".roll":
            await edit_owner_message(bot, message,
                                     f"🎲 Выпало: <b>{random.randint(1, 100)}</b>")
            return True

        if trigger == ".coin":
            await edit_owner_message(bot, message, random.choice(["🪙 Орёл", "🪙 Решка"]))
            return True

        if trigger == ".8ball":
            await edit_owner_message(bot, message, f"🎱 {random.choice(EIGHT_BALL)}")
            return True

        if trigger == ".choose":
            options = [o.strip() for o in arg.replace("|", ",").split(",") if o.strip()]
            if not options:
                await edit_owner_message(bot, message,
                                         "⚠️ Пример: <code>.choose кино | театр | дом</code>")
            else:
                await edit_owner_message(
                    bot, message,
                    f"🎯 Мой выбор: <b>{html_lib.escape(random.choice(options))}</b>")
            return True

        if trigger == ".calc":
            if not arg:
                await edit_owner_message(bot, message, "⚠️ Пример: <code>.calc 2+2*10</code>")
                return True
            try:
                await edit_owner_message(
                    bot, message,
                    f"🧮 {html_lib.escape(arg)} = <b>{safe_eval_expr(arg)}</b>")
            except Exception:
                await edit_owner_message(bot, message, "⚠️ Не удалось вычислить выражение.")
            return True

        if trigger == ".rev":
            await edit_owner_message(bot, message,
                                     html_lib.escape((arg or "нечего переворачивать")[::-1]))
            return True

        if trigger == ".up":
            await edit_owner_message(bot, message,
                                     html_lib.escape((arg or "текст").upper()))
            return True

        if trigger == ".space":
            await edit_owner_message(bot, message, html_lib.escape(" ".join(arg or "текст")))
            return True

        if trigger == ".mock":
            src = arg or "текст"
            await edit_owner_message(bot, message, html_lib.escape(
                "".join(c.upper() if i % 2 else c.lower() for i, c in enumerate(src))))
            return True

        if trigger == ".b":
            await edit_owner_message(bot, message, f"<b>{arg_html or 'жирный текст'}</b>")
            return True

        if trigger == ".i":
            await edit_owner_message(bot, message, f"<i>{arg_html or 'курсив'}</i>")
            return True

        if trigger == ".spoiler":
            await edit_owner_message(bot, message,
                                     f"<tg-spoiler>{arg_html or 'сюрприз'}</tg-spoiler>")
            return True

        if trigger == ".quote":
            await edit_owner_message(bot, message,
                                     f"<blockquote>{arg_html or 'цитата'}</blockquote>")
            return True

        if trigger == ".info":
            peer = message.chat
            name = " ".join(filter(None, [peer.first_name, peer.last_name])) or "—"
            uname = f"@{peer.username}" if peer.username else "—"
            await edit_owner_message(
                bot, message,
                "ℹ️ <b>Собеседник</b>\n"
                f"Имя: {html_lib.escape(name)}\n"
                f"Username: {html_lib.escape(uname)}\n"
                f"ID: <code>{peer.id}</code>\n"
                f"Мьют: {'🔇 да' if is_chat_muted(owner_id, chat_id) else '🔊 нет'}\n"
                f"Обход мута: {'🟢 да' if obhod_enabled(owner_id, chat_id) else '🔴 нет'}"
            )
            return True

        if trigger == ".count":
            src = arg or ""
            await edit_owner_message(
                bot, message,
                f"🔢 Символов: <b>{len(src)}</b>\n"
                f"🔤 Без пробелов: <b>{len(src.replace(' ', ''))}</b>\n"
                f"📝 Слов: <b>{len(src.split())}</b>"
            )
            return True

        if trigger == ".tz":
            await edit_owner_message(
                bot, message,
                f"🕒 Часовой пояс: <b>UTC+{get_tz_offset(owner_id)}</b>\n"
                f"Время: <code>{tz_now(owner_id).strftime('%H:%M')}</code>"
            )
            return True
    except Exception:
        logger.exception("handle_v6_command: ошибка команды %s", trigger)
        try:
            await edit_owner_message(bot, message, "🔴 Ошибка выполнения команды.")
        except Exception:
            logger.exception("handle_v6_command: не удалось сообщить об ошибке")
        return True
    return False


# ==========================================
#     V5: РЕЕСТР ПРАВ, ГЛАВНЫЙ АДМИН
# ==========================================

MSK_OFFSET = 3
ONLINE_TARGET_USERNAME = "VeloraSaveOnline"
BOT_PUBLIC_USERNAME = "VeloraSaveBot"

PERMISSIONS = [
    {"id": "manage_users", "name": "Пользователи", "cat": "Основное",
     "desc": "Просмотр карточек пользователей", "default": False},
    {"id": "manage_mutes", "name": "Мьюты", "cat": "Основное",
     "desc": "Мьют и размьют собеседников", "default": False},
    {"id": "manage_whitelist", "name": "Whitelist", "cat": "Приватность",
     "desc": "Просмотр списка скрытых пользователей", "default": False},
    {"id": "add_whitelist", "name": "Whitelist: добавить", "cat": "Приватность",
     "desc": "Добавление ID в список скрытых", "default": False},
    {"id": "remove_whitelist", "name": "Whitelist: удалить", "cat": "Приватность",
     "desc": "Удаление ID из списка скрытых", "default": False},
    {"id": "manage_whitelist_settings", "name": "Whitelist: настройки", "cat": "Приватность",
     "desc": "Включение и выключение whitelist", "default": False},
    {"id": "manage_online", "name": "Функция .online", "cat": "Функции",
     "desc": "Управление поддержанием активности", "default": False},
    {"id": "manage_profile_time", "name": "Время в имени", "cat": "Функции",
     "desc": "Управление часами в имени профиля", "default": False},
    {"id": "manage_games", "name": "Игры", "cat": "Функции",
     "desc": "Управление игрой в переписке", "default": False},
    {"id": "manage_menu", "name": "Главное меню", "cat": "Меню",
     "desc": "Доступ к редактору главного меню", "default": False},
    {"id": "manage_menu_buttons", "name": "Кнопки меню", "cat": "Меню",
     "desc": "Создание и удаление кнопок меню", "default": False},
    {"id": "manage_menu_text", "name": "Тексты меню", "cat": "Меню",
     "desc": "Изменение текстов разделов", "default": False},
    {"id": "manage_menu_photos", "name": "Фото меню", "cat": "Меню",
     "desc": "Изменение изображений разделов", "default": False},
    {"id": "manage_settings", "name": "Настройки бота", "cat": "Система",
     "desc": "Общие переключатели функций", "default": False},
    {"id": "manage_admins", "name": "Администраторы", "cat": "Система",
     "desc": "Назначение и снятие администраторов", "default": False},
    {"id": "manage_admin_permissions", "name": "Права админов", "cat": "Система",
     "desc": "Изменение прав других администраторов", "default": False},
]

PERM_INDEX = {p["id"]: p for p in PERMISSIONS}

FEATURES = [
    {"id": "feat_online", "name": "Функция .online", "default": "1"},
    {"id": "feat_profile_time", "name": "Время в имени", "default": "1"},
    {"id": "feat_game", "name": "Игра в переписке", "default": "1"},
    {"id": "feat_mute", "name": "Мьюты", "default": "1"},
    {"id": "feat_whitelist", "name": "Whitelist", "default": "1"},
    {"id": "feat_menu_custom", "name": "Кастомные кнопки меню", "default": "1"},
    {"id": "feat_obhod", "name": "Обход мута (.obhod)", "default": "1"},
    {"id": "gate_enabled", "name": "Требовать подключение бота", "default": "1"},
]

FEATURE_INDEX = {f["id"]: f for f in FEATURES}

BG_TASKS = {}


def init_v5_tables():
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admin_perms (
                user_id INTEGER,
                perm_id TEXT,
                allowed INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, perm_id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS whitelist (
                user_id INTEGER PRIMARY KEY,
                note TEXT,
                added_at TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS online_state (
                owner_id INTEGER PRIMARY KEY,
                enabled INTEGER DEFAULT 0,
                target_chat_id INTEGER,
                connection_id TEXT,
                updated_at TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS nicktime_state (
                owner_id INTEGER PRIMARY KEY,
                enabled INTEGER DEFAULT 0,
                base_first TEXT,
                base_last TEXT,
                connection_id TEXT,
                updated_at TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS game_state (
                chat_id INTEGER,
                owner_id INTEGER,
                message_id INTEGER,
                board TEXT,
                turn TEXT,
                status TEXT,
                connection_id TEXT,
                updated_at TEXT,
                PRIMARY KEY (chat_id, owner_id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS menu_sections (
                key TEXT PRIMARY KEY,
                title TEXT,
                body TEXT,
                photo TEXT,
                enabled INTEGER DEFAULT 1
            )
        """)
        for ddl in [
            "ALTER TABLE custom_buttons ADD COLUMN position INTEGER DEFAULT 100",
            "ALTER TABLE custom_buttons ADD COLUMN enabled INTEGER DEFAULT 1",
            "ALTER TABLE custom_buttons ADD COLUMN photo TEXT"
        ]:
            try:
                cursor.execute(ddl)
            except Exception:
                pass
        conn.commit()
        conn.close()
    except Exception:
        logger.exception("init_v5_tables: не удалось создать таблицы")


init_v5_tables()


def get_main_admin() -> int:
    raw = get_flag("main_admin_id", "")
    if raw:
        try:
            return int(raw)
        except ValueError:
            logger.exception("get_main_admin: некорректное значение флага")
    return MAIN_ADMIN_ID


def set_main_admin(user_id: int):
    set_flag("main_admin_id", str(user_id))
    logger.info("Главный администратор изменён на %s", user_id)


def is_main_admin(user_id: int) -> bool:
    return user_id == get_main_admin()


def has_perm(user_id: int, perm_id: str) -> bool:
    try:
        if is_main_admin(user_id):
            return True
        if not is_admin(user_id):
            return False
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute(
            "SELECT allowed FROM admin_perms WHERE user_id = ? AND perm_id = ?",
            (user_id, perm_id)
        )
        row = cursor.fetchone()
        conn.close()
        if row is not None:
            return bool(row[0])
        meta = PERM_INDEX.get(perm_id)
        return bool(meta and meta.get("default"))
    except Exception:
        logger.exception("has_perm: ошибка проверки права %s", perm_id)
        return False


def set_perm(user_id: int, perm_id: str, allowed: bool):
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO admin_perms (user_id, perm_id, allowed) VALUES (?, ?, ?)",
            (user_id, perm_id, 1 if allowed else 0)
        )
        conn.commit()
        conn.close()
        logger.info("Право %s для %s -> %s", perm_id, user_id, allowed)
    except Exception:
        logger.exception("set_perm: не удалось сохранить право")


def set_all_perms(user_id: int, allowed: bool):
    for p in PERMISSIONS:
        set_perm(user_id, p["id"], allowed)


def get_perm_map(user_id: int) -> dict:
    result = {}
    for p in PERMISSIONS:
        result[p["id"]] = has_perm(user_id, p["id"])
    return result


def feature_enabled(feature_id: str) -> bool:
    meta = FEATURE_INDEX.get(feature_id)
    default = meta["default"] if meta else "1"
    return get_flag(feature_id, default) == "1"


def set_feature(feature_id: str, enabled: bool):
    set_flag(feature_id, "1" if enabled else "0")
    logger.info("Функция %s -> %s", feature_id, "включена" if enabled else "выключена")


# ==========================================
#              V5: WHITELIST
# ==========================================

def is_whitelisted(user_id) -> bool:
    try:
        if not feature_enabled("feat_whitelist"):
            return False
        if get_flag("whitelist_enabled", "1") != "1":
            return False
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM whitelist WHERE user_id = ?", (int(user_id),))
        row = cursor.fetchone()
        conn.close()
        return row is not None
    except Exception:
        logger.exception("is_whitelisted: ошибка проверки")
        return False


def whitelist_add(user_id: int, note: str = ""):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO whitelist (user_id, note, added_at) VALUES (?, ?, ?)",
        (user_id, note, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    conn.commit()
    conn.close()
    logger.info("Whitelist: добавлен %s", user_id)


def whitelist_remove(user_id: int):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM whitelist WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    logger.info("Whitelist: удалён %s", user_id)


def whitelist_all() -> list:
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, note, added_at FROM whitelist ORDER BY rowid DESC")
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception:
        logger.exception("whitelist_all: ошибка чтения")
        return []


# ==========================================
#        V5: ЕДИНЫЙ СТИЛЬ КНОПОК
# ==========================================

def toggle_button(label: str, enabled: bool, callback: str) -> types.InlineKeyboardButton:
    mark = "🟢" if enabled else "🔴"
    return create_premium_button(
        text=f"{mark} {label}",
        callback_data=callback,
        style="success" if enabled else "danger"
    )


def confirm_rows(action_callback: str, cancel_callback: str) -> list:
    return [
        [create_premium_button(text="✅ Да, подтверждаю", callback_data=action_callback,
                               style="success")],
        [create_premium_button(text="Отмена", callback_data=cancel_callback,
                               style="danger", icon_custom_emoji_id="521095253167650451")]
    ]


async def deny(callback: CallbackQuery):
    try:
        await callback.answer("🔴 Недостаточно прав", show_alert=True)
    except Exception:
        logger.exception("deny: не удалось ответить на callback")


# ==========================================
#     V5: ПРОВЕРКА БИЗНЕС-ПОДКЛЮЧЕНИЯ
# ==========================================

def get_connection_id(owner_id: int) -> str:
    return get_flag(f"conn_id_{owner_id}", "")


def store_connection_id(owner_id: int, connection_id: str):
    set_flag(f"conn_id_{owner_id}", connection_id or "")


def connect_instructions_kb() -> types.InlineKeyboardMarkup:
    rows = [
        [types.InlineKeyboardButton(
            text="📋 Скопировать username",
            copy_text=types.CopyTextButton(text=BOT_PUBLIC_USERNAME)
        )],
        [create_premium_button(text="➕ Подключить бота", url="tg://settings/edit",
                               style="primary")],
        [create_premium_button(text="🔙 Назад", callback_data="back_to_main", style="primary")]
    ]
    return types.InlineKeyboardMarkup(inline_keyboard=rows)


def connect_instructions_text() -> str:
    return (
        "🔵 <b>Сначала подключите бота к аккаунту</b>\n\n"
        "1. Нажмите «📋 Скопировать».\n"
        "2. Добавьте бота в «Автоматизация чатов».\n"
        "3. Нажмите «➕ Подключить».\n"
        "4. Откройте раздел «Автоматизация чатов».\n"
        "5. Вставьте скопированное имя бота:\n\n"
        f"<code>{BOT_PUBLIC_USERNAME}</code>\n\n"
        "После подключения вернитесь в бота и повторите команду.\n\n"
        "Если раздела «Автоматизация чатов» нет, обновите Telegram до последней версии."
    )


async def require_connection(callback: CallbackQuery, owner_id: int) -> bool:
    if get_connection_id(owner_id):
        return True
    await render_screen(callback, connect_instructions_text(), connect_instructions_kb())
    await callback.answer()
    return False


@dp.callback_query(F.data == "show_connect_help")
async def show_connect_help(callback: CallbackQuery):
    try:
        await render_screen(callback, connect_instructions_text(), connect_instructions_kb())
    except Exception:
        logger.exception("show_connect_help: ошибка отрисовки")
    await callback.answer()


# ==========================================
#        V5: MUTE С КНОПКОЙ РАЗМУТА
# ==========================================

MUTE_NOTICE = (
    "🔴 <b>Замолчи!</b>\n\n"
    "Пользователь замьючен: его новые сообщения будут удаляться.\n"
    "Чтобы размутить пользователя, используй <code>.unmute</code>"
)


def mute_keyboard(owner_id: int, chat_id: int) -> types.InlineKeyboardMarkup:
    return types.InlineKeyboardMarkup(inline_keyboard=[[
        create_premium_button(text="🔓 Размутить", callback_data=f"unmute_{owner_id}_{chat_id}",
                              style="success")
    ]])


@dp.callback_query(F.data.startswith("unmute_"))
async def unmute_from_button(callback: CallbackQuery, bot: Bot):
    try:
        parts = callback.data.split("_")
        owner_id, chat_id = int(parts[1]), int(parts[2])
    except Exception:
        logger.exception("unmute_from_button: некорректные данные callback")
        await callback.answer("Некорректные данные кнопки", show_alert=True)
        return

    if callback.from_user.id != owner_id and not has_perm(callback.from_user.id, "manage_mutes"):
        await deny(callback)
        return

    try:
        if not is_chat_muted(owner_id, chat_id):
            await callback.answer("Пользователь уже размьючен", show_alert=True)
            return
        unmute_chat(owner_id, chat_id)
        conn_id = get_connection_id(owner_id)
        text = "🟢 <b>Размьючен</b>\n\nПользователь снова может писать."
        edited = False
        if conn_id and callback.message:
            try:
                await bot.edit_message_text(
                    business_connection_id=conn_id,
                    chat_id=callback.message.chat.id,
                    message_id=callback.message.message_id,
                    text=text,
                    parse_mode="HTML"
                )
                edited = True
            except Exception:
                logger.exception("unmute_from_button: не удалось изменить бизнес-сообщение")
        if not edited:
            try:
                await callback.message.edit_text(text, parse_mode="HTML")
            except Exception:
                logger.exception("unmute_from_button: не удалось изменить сообщение")
        await callback.answer("🔓 Размьючен")
    except Exception:
        logger.exception("unmute_from_button: непредвиденная ошибка")
        await callback.answer("Произошла ошибка", show_alert=True)


# ==========================================
#          V5: ИГРА В ПЕРЕПИСКЕ
# ==========================================

GAME_LINES = [(0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6),
              (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6)]
GAME_CELL = {"": "⬜️", "X": "❌", "O": "⭕️"}


def game_winner(board: list):
    for a, b, c in GAME_LINES:
        if board[a] and board[a] == board[b] == board[c]:
            return board[a]
    if all(board):
        return "D"
    return None


def game_ai_move(board: list):
    free = [i for i in range(9) if not board[i]]
    if not free:
        return None
    for mark in ("O", "X"):
        for i in free:
            probe = list(board)
            probe[i] = mark
            if game_winner(probe) == mark:
                return i
    if 4 in free:
        return 4
    corners = [i for i in (0, 2, 6, 8) if i in free]
    if corners:
        return random.choice(corners)
    return random.choice(free)


def save_game(chat_id, owner_id, message_id, board, turn, status, connection_id):
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO game_state (chat_id, owner_id, message_id, board, turn, "
            "status, connection_id, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (chat_id, owner_id, message_id, "".join(c or "." for c in board), turn, status,
             connection_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        conn.commit()
        conn.close()
    except Exception:
        logger.exception("save_game: не удалось сохранить партию")


def load_game(chat_id, owner_id):
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute(
            "SELECT message_id, board, turn, status, connection_id FROM game_state "
            "WHERE chat_id = ? AND owner_id = ?", (chat_id, owner_id)
        )
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        return {
            "message_id": row[0],
            "board": ["" if c == "." else c for c in row[1]],
            "turn": row[2],
            "status": row[3],
            "connection_id": row[4]
        }
    except Exception:
        logger.exception("load_game: не удалось загрузить партию")
        return None


def drop_game(chat_id, owner_id):
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("DELETE FROM game_state WHERE chat_id = ? AND owner_id = ?",
                       (chat_id, owner_id))
        conn.commit()
        conn.close()
    except Exception:
        logger.exception("drop_game: не удалось удалить партию")


def game_keyboard(chat_id, owner_id, board, finished=False) -> types.InlineKeyboardMarkup:
    rows = []
    for r in range(3):
        row = []
        for c in range(3):
            i = r * 3 + c
            if finished or board[i]:
                row.append(create_premium_button(text=GAME_CELL[board[i]],
                                                 callback_data="game_noop"))
            else:
                row.append(create_premium_button(
                    text=GAME_CELL[""], callback_data=f"gmv_{owner_id}_{chat_id}_{i}",
                    style="primary"
                ))
        rows.append(row)
    rows.append([
        create_premium_button(text="🔄 Заново", callback_data=f"gnew_{owner_id}_{chat_id}",
                              style="success"),
        create_premium_button(text="🔴 Завершить", callback_data=f"gend_{owner_id}_{chat_id}",
                              style="danger")
    ])
    return types.InlineKeyboardMarkup(inline_keyboard=rows)


def game_text(board, status_line: str) -> str:
    return (
        "🎮 <b>Крестики-нолики</b>\n\n"
        "Вы играете ❌, бот играет ⭕️.\n\n"
        f"{status_line}"
    )


@dp.callback_query(F.data == "game_noop")
async def game_noop(callback: CallbackQuery):
    await callback.answer("Эта клетка занята")


async def render_game(bot: Bot, owner_id, chat_id, conn_id, board, status_line,
                      message_id=None, finished=False):
    kb = game_keyboard(chat_id, owner_id, board, finished)
    text = game_text(board, status_line)
    if message_id:
        try:
            await bot.edit_message_text(
                business_connection_id=conn_id, chat_id=chat_id, message_id=message_id,
                text=text, parse_mode="HTML", reply_markup=kb
            )
            return message_id
        except Exception:
            logger.exception("render_game: не удалось изменить сообщение, отправляю новое")
    try:
        sent = await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML",
                                      reply_markup=kb, business_connection_id=conn_id)
        return sent.message_id
    except Exception:
        logger.exception("render_game: не удалось отправить сообщение игры")
        return None


async def start_game(bot: Bot, message: Message, owner_id: int) -> bool:
    if not feature_enabled("feat_game"):
        await edit_owner_message(bot, message, "🔴 Игра отключена администратором.")
        return True
    chat_id = message.chat.id
    conn_id = message.business_connection_id
    board = [""] * 9
    await edit_owner_message(bot, message, "🎮 Игра запущена")
    msg_id = await render_game(bot, owner_id, chat_id, conn_id, board, "Ваш ход.")
    if msg_id:
        save_game(chat_id, owner_id, msg_id, board, "X", "active", conn_id)
    else:
        await edit_owner_message(
            bot, message,
            "🔴 Не удалось отправить игровое поле.\n"
            "Возможно, бизнес-подключение не поддерживает кнопки — переподключите бота."
        )
    return True


@dp.callback_query(F.data.startswith("gmv_"))
async def game_move(callback: CallbackQuery, bot: Bot):
    try:
        _, owner_raw, chat_raw, idx_raw = callback.data.split("_")
        owner_id, chat_id, idx = int(owner_raw), int(chat_raw), int(idx_raw)
    except Exception:
        logger.exception("game_move: некорректные данные callback")
        await callback.answer("Некорректные данные кнопки", show_alert=True)
        return

    try:
        if not feature_enabled("feat_game"):
            await callback.answer("🔴 Игра отключена администратором", show_alert=True)
            return

        state = load_game(chat_id, owner_id)
        if not state or state["status"] != "active":
            await callback.answer("Эта партия уже завершена", show_alert=True)
            return

        board = state["board"]
        if idx < 0 or idx > 8 or board[idx]:
            await callback.answer("Клетка занята", show_alert=True)
            return

        board[idx] = "X"
        result = game_winner(board)
        status_line = "Ваш ход."
        finished = False

        if not result:
            ai = game_ai_move(board)
            if ai is not None:
                board[ai] = "O"
            result = game_winner(board)

        if result == "X":
            status_line, finished = "🏆 <b>Вы победили!</b>", True
        elif result == "O":
            status_line, finished = "🔴 <b>Победил бот.</b>", True
        elif result == "D":
            status_line, finished = "🟡 <b>Ничья.</b>", True

        conn_id = state["connection_id"] or get_connection_id(owner_id)
        await render_game(bot, owner_id, chat_id, conn_id, board, status_line,
                          state["message_id"], finished)

        if finished:
            drop_game(chat_id, owner_id)
        else:
            save_game(chat_id, owner_id, state["message_id"], board, "X", "active", conn_id)
        await callback.answer()
    except Exception:
        logger.exception("game_move: непредвиденная ошибка")
        await callback.answer("Произошла ошибка", show_alert=True)


@dp.callback_query(F.data.startswith("gnew_"))
async def game_restart(callback: CallbackQuery, bot: Bot):
    try:
        _, owner_raw, chat_raw = callback.data.split("_")
        owner_id, chat_id = int(owner_raw), int(chat_raw)
        if not feature_enabled("feat_game"):
            await callback.answer("🔴 Игра отключена администратором", show_alert=True)
            return
        state = load_game(chat_id, owner_id)
        conn_id = (state or {}).get("connection_id") or get_connection_id(owner_id)
        msg_id = (state or {}).get("message_id") or callback.message.message_id
        board = [""] * 9
        new_id = await render_game(bot, owner_id, chat_id, conn_id, board, "Ваш ход.", msg_id)
        save_game(chat_id, owner_id, new_id or msg_id, board, "X", "active", conn_id)
        await callback.answer("🔄 Новая партия")
    except Exception:
        logger.exception("game_restart: непредвиденная ошибка")
        await callback.answer("Произошла ошибка", show_alert=True)


@dp.callback_query(F.data.startswith("gend_"))
async def game_finish(callback: CallbackQuery, bot: Bot):
    try:
        _, owner_raw, chat_raw = callback.data.split("_")
        owner_id, chat_id = int(owner_raw), int(chat_raw)
        state = load_game(chat_id, owner_id)
        drop_game(chat_id, owner_id)
        conn_id = (state or {}).get("connection_id") or get_connection_id(owner_id)
        msg_id = (state or {}).get("message_id") or callback.message.message_id
        try:
            await bot.edit_message_text(
                business_connection_id=conn_id, chat_id=chat_id, message_id=msg_id,
                text="🎮 <b>Игра завершена.</b>", parse_mode="HTML"
            )
        except Exception:
            logger.exception("game_finish: не удалось изменить сообщение")
        await callback.answer("Игра завершена")
    except Exception:
        logger.exception("game_finish: непредвиденная ошибка")
        await callback.answer("Произошла ошибка", show_alert=True)


# ==========================================
#          V5: .ONLINE (АКТИВНОСТЬ)
# ==========================================

def get_online_state(owner_id: int) -> dict:
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute(
            "SELECT enabled, target_chat_id, connection_id FROM online_state WHERE owner_id = ?",
            (owner_id,)
        )
        row = cursor.fetchone()
        conn.close()
        if not row:
            return {"enabled": False, "target_chat_id": None, "connection_id": ""}
        return {"enabled": bool(row[0]), "target_chat_id": row[1], "connection_id": row[2]}
    except Exception:
        logger.exception("get_online_state: ошибка чтения")
        return {"enabled": False, "target_chat_id": None, "connection_id": ""}


def save_online_state(owner_id: int, enabled: bool, target_chat_id, connection_id: str):
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO online_state (owner_id, enabled, target_chat_id, "
            "connection_id, updated_at) VALUES (?, ?, ?, ?, ?)",
            (owner_id, 1 if enabled else 0, target_chat_id, connection_id,
             datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        conn.commit()
        conn.close()
    except Exception:
        logger.exception("save_online_state: не удалось сохранить состояние")


def remember_online_target(owner_id: int, chat_id: int, connection_id: str):
    state = get_online_state(owner_id)
    save_online_state(owner_id, state["enabled"], chat_id, connection_id)
    logger.info("Найден чат с @%s для владельца %s", ONLINE_TARGET_USERNAME, owner_id)


async def online_loop(bot: Bot, owner_id: int):
    logger.info("online_loop: запущен для %s", owner_id)
    failures = 0
    try:
        while True:
            if not feature_enabled("feat_online"):
                logger.info("online_loop: функция выключена глобально, останавливаюсь")
                break
            state = get_online_state(owner_id)
            if not state["enabled"] or not state["target_chat_id"]:
                logger.info("online_loop: остановлен для %s", owner_id)
                break
            conn_id = state["connection_id"] or get_connection_id(owner_id)
            if not conn_id:
                logger.warning("online_loop: нет бизнес-подключения для %s", owner_id)
                save_online_state(owner_id, False, state["target_chat_id"], "")
                break
            try:
                sent = await bot.send_message(
                    chat_id=state["target_chat_id"], text="⏳",
                    business_connection_id=conn_id
                )
                failures = 0
                await asyncio.sleep(1)
                try:
                    await bot.delete_business_messages(
                        business_connection_id=conn_id, message_ids=[sent.message_id]
                    )
                except Exception:
                    logger.exception("online_loop: не удалось удалить сообщение")
            except Exception as e:
                failures += 1
                logger.exception("online_loop: ошибка отправки (%s подряд)", failures)
                retry_after = getattr(e, "retry_after", None)
                if retry_after:
                    logger.warning("online_loop: FloodWait %s сек", retry_after)
                    await asyncio.sleep(int(retry_after) + 1)
                if failures >= 5:
                    logger.error("online_loop: 5 ошибок подряд, отключаю функцию для %s",
                                 owner_id)
                    save_online_state(owner_id, False, state["target_chat_id"], conn_id)
                    try:
                        await bot.send_message(
                            owner_id,
                            "🔴 Функция <code>.online</code> отключена: "
                            "несколько ошибок отправки подряд.",
                            parse_mode="HTML"
                        )
                    except Exception:
                        logger.exception("online_loop: не удалось уведомить владельца")
                    break
            await asyncio.sleep(10)
    except asyncio.CancelledError:
        logger.info("online_loop: отменён для %s", owner_id)
        raise
    except Exception:
        logger.exception("online_loop: критическая ошибка для %s", owner_id)
    finally:
        BG_TASKS.pop(("online", owner_id), None)


def start_online_task(bot: Bot, owner_id: int):
    key = ("online", owner_id)
    task = BG_TASKS.get(key)
    if task and not task.done():
        logger.info("start_online_task: задача уже запущена для %s", owner_id)
        return
    BG_TASKS[key] = asyncio.create_task(online_loop(bot, owner_id))


def stop_online_task(owner_id: int):
    task = BG_TASKS.pop(("online", owner_id), None)
    if task and not task.done():
        task.cancel()


def online_keyboard(owner_id: int) -> types.InlineKeyboardMarkup:
    state = get_online_state(owner_id)
    rows = [[
        create_premium_button(text="🟢 Включить", callback_data=f"onl_on_{owner_id}",
                              style="success"),
        create_premium_button(text="🔴 Выключить", callback_data=f"onl_off_{owner_id}",
                              style="danger")
    ]]
    rows.append([create_premium_button(
        text=f"🔵 Статус: {'включено' if state['enabled'] else 'выключено'}",
        callback_data=f"onl_st_{owner_id}", style="primary")])
    return types.InlineKeyboardMarkup(inline_keyboard=rows)


@dp.callback_query(F.data.startswith("onl_"))
async def online_controls(callback: CallbackQuery, bot: Bot):
    try:
        parts = callback.data.split("_")
        action, owner_id = parts[1], int(parts[2])
    except Exception:
        logger.exception("online_controls: некорректные данные callback")
        await callback.answer("Некорректные данные кнопки", show_alert=True)
        return

    if callback.from_user.id != owner_id and not has_perm(callback.from_user.id, "manage_online"):
        await deny(callback)
        return

    try:
        if not feature_enabled("feat_online"):
            await callback.answer("🔴 Функция отключена администратором", show_alert=True)
            return

        state = get_online_state(owner_id)
        if action == "st":
            await callback.answer(
                f"Статус: {'🟢 включено' if state['enabled'] else '🔴 выключено'}",
                show_alert=True
            )
            return

        if action == "on":
            if not state["target_chat_id"]:
                await callback.answer(
                    f"Сначала напишите @{ONLINE_TARGET_USERNAME}, затем повторите .online",
                    show_alert=True
                )
                return
            conn_id = state["connection_id"] or get_connection_id(owner_id)
            save_online_state(owner_id, True, state["target_chat_id"], conn_id)
            start_online_task(bot, owner_id)
            await callback.answer("🟢 Включено")
        else:
            save_online_state(owner_id, False, state["target_chat_id"],
                              state["connection_id"])
            stop_online_task(owner_id)
            await callback.answer("🔴 Выключено")

        try:
            await callback.message.edit_reply_markup(reply_markup=online_keyboard(owner_id))
        except Exception:
            logger.exception("online_controls: не удалось обновить клавиатуру")
    except Exception:
        logger.exception("online_controls: непредвиденная ошибка")
        await callback.answer("Произошла ошибка", show_alert=True)


# ==========================================
#        V5: ВРЕМЯ В ИМЕНИ (МСК)
# ==========================================

def msk_now() -> datetime:
    return datetime.utcnow() + timedelta(hours=MSK_OFFSET)


def get_nicktime_state(owner_id: int) -> dict:
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute(
            "SELECT enabled, base_first, base_last, connection_id FROM nicktime_state "
            "WHERE owner_id = ?", (owner_id,)
        )
        row = cursor.fetchone()
        conn.close()
        if not row:
            return {"enabled": False, "base_first": "", "base_last": "", "connection_id": ""}
        return {"enabled": bool(row[0]), "base_first": row[1] or "",
                "base_last": row[2] or "", "connection_id": row[3] or ""}
    except Exception:
        logger.exception("get_nicktime_state: ошибка чтения")
        return {"enabled": False, "base_first": "", "base_last": "", "connection_id": ""}


def save_nicktime_state(owner_id: int, enabled: bool, base_first: str, base_last: str,
                        connection_id: str):
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO nicktime_state (owner_id, enabled, base_first, base_last, "
            "connection_id, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (owner_id, 1 if enabled else 0, base_first, base_last, connection_id,
             datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        conn.commit()
        conn.close()
    except Exception:
        logger.exception("save_nicktime_state: не удалось сохранить состояние")


async def check_name_right(bot: Bot, conn_id: str) -> bool:
    try:
        info = await bot.get_business_connection(conn_id)
        rights = getattr(info, "rights", None)
        if rights is None:
            return bool(getattr(info, "can_reply", False))
        return bool(getattr(rights, "can_edit_name", False))
    except Exception:
        logger.exception("check_name_right: не удалось получить права подключения")
        return False


async def apply_nick_time(bot: Bot, owner_id: int, state: dict) -> bool:
    conn_id = state["connection_id"] or get_connection_id(owner_id)
    if not conn_id:
        return False
    stamp = tz_now(owner_id).strftime("%H:%M")
    first = f"{state['base_first']} | {stamp}".strip()
    try:
        setter = getattr(bot, "set_business_account_name", None)
        if setter is None:
            logger.error("apply_nick_time: библиотека не поддерживает setBusinessAccountName")
            return False
        await setter(business_connection_id=conn_id, first_name=first[:64],
                     last_name=state["base_last"][:64] or None)
        return True
    except Exception:
        logger.exception("apply_nick_time: не удалось изменить имя")
        return False


async def nicktime_loop(bot: Bot, owner_id: int):
    logger.info("nicktime_loop: запущен для %s", owner_id)
    failures = 0
    try:
        while True:
            if not feature_enabled("feat_profile_time"):
                logger.info("nicktime_loop: функция выключена глобально, останавливаюсь")
                break
            state = get_nicktime_state(owner_id)
            if not state["enabled"]:
                logger.info("nicktime_loop: остановлен для %s", owner_id)
                break
            ok = await apply_nick_time(bot, owner_id, state)
            if ok:
                failures = 0
            else:
                failures += 1
                if failures >= 3:
                    logger.error("nicktime_loop: нет прав или ошибки, отключаю для %s", owner_id)
                    save_nicktime_state(owner_id, False, state["base_first"],
                                        state["base_last"], state["connection_id"])
                    try:
                        await bot.send_message(
                            owner_id,
                            "🔴 Обновление имени остановлено.\n\n"
                            "Выдайте боту необходимые разрешения: в разделе "
                            "«Автоматизация чатов» разрешите изменение имени. "
                            "После этого повторите команду.",
                            parse_mode="HTML"
                        )
                    except Exception:
                        logger.exception("nicktime_loop: не удалось уведомить владельца")
                    break
            await asyncio.sleep(60)
    except asyncio.CancelledError:
        logger.info("nicktime_loop: отменён для %s", owner_id)
        raise
    except Exception:
        logger.exception("nicktime_loop: критическая ошибка для %s", owner_id)
    finally:
        BG_TASKS.pop(("nicktime", owner_id), None)


def start_nicktime_task(bot: Bot, owner_id: int):
    key = ("nicktime", owner_id)
    task = BG_TASKS.get(key)
    if task and not task.done():
        logger.info("start_nicktime_task: задача уже запущена для %s", owner_id)
        return
    BG_TASKS[key] = asyncio.create_task(nicktime_loop(bot, owner_id))


def stop_nicktime_task(owner_id: int):
    task = BG_TASKS.pop(("nicktime", owner_id), None)
    if task and not task.done():
        task.cancel()


def nicktime_keyboard(owner_id: int) -> types.InlineKeyboardMarkup:
    state = get_nicktime_state(owner_id)
    return types.InlineKeyboardMarkup(inline_keyboard=[[
        create_premium_button(text="🟢 Включить", callback_data=f"ntm_on_{owner_id}",
                              style="success"),
        create_premium_button(text="🔴 Выключить", callback_data=f"ntm_off_{owner_id}",
                              style="danger")
    ], [
        create_premium_button(
            text=f"🔵 Статус: {'включено' if state['enabled'] else 'выключено'}",
            callback_data=f"ntm_st_{owner_id}", style="primary")
    ]])


@dp.callback_query(F.data.startswith("ntm_"))
async def nicktime_controls(callback: CallbackQuery, bot: Bot):
    try:
        parts = callback.data.split("_")
        if parts[1] == "panel":
            return
        action, owner_id = parts[1], int(parts[2])
    except Exception:
        logger.exception("nicktime_controls: некорректные данные callback")
        await callback.answer("Некорректные данные кнопки", show_alert=True)
        return

    if (callback.from_user.id != owner_id
            and not has_perm(callback.from_user.id, "manage_profile_time")):
        await deny(callback)
        return

    try:
        if not feature_enabled("feat_profile_time"):
            await callback.answer("🔴 Функция отключена администратором", show_alert=True)
            return

        state = get_nicktime_state(owner_id)
        if action == "st":
            await callback.answer(
                f"Статус: {'🟢 включено' if state['enabled'] else '🔴 выключено'}",
                show_alert=True
            )
            return

        if action == "on":
            conn_id = state["connection_id"] or get_connection_id(owner_id)
            if not conn_id:
                await callback.answer("Сначала подключите бота к аккаунту", show_alert=True)
                return
            if not await check_name_right(bot, conn_id):
                await callback.answer(
                    "Выдайте боту разрешение на изменение имени, затем повторите.",
                    show_alert=True
                )
                try:
                    await callback.message.answer(
                        "🔴 <b>Нет разрешения на изменение имени</b>\n\n"
                        "Нажмите кнопку ниже и разрешите боту изменение имени.",
                        parse_mode="HTML",
                        reply_markup=permission_keyboard()
                    )
                except Exception:
                    logger.exception("nicktime_controls: не удалось отправить кнопку")
                return
            save_nicktime_state(owner_id, True, state["base_first"], state["base_last"], conn_id)
            start_nicktime_task(bot, owner_id)
            await callback.answer("🟢 Включено")
        else:
            save_nicktime_state(owner_id, False, state["base_first"], state["base_last"],
                                state["connection_id"])
            stop_nicktime_task(owner_id)
            if state["base_first"]:
                try:
                    setter = getattr(bot, "set_business_account_name", None)
                    if setter:
                        await setter(
                            business_connection_id=state["connection_id"]
                            or get_connection_id(owner_id),
                            first_name=state["base_first"][:64],
                            last_name=state["base_last"][:64] or None
                        )
                except Exception:
                    logger.exception("nicktime_controls: не удалось вернуть имя")
            await callback.answer("🔴 Выключено")

        try:
            await callback.message.edit_reply_markup(
                reply_markup=nicktime_keyboard_v6(owner_id))
        except Exception:
            logger.exception("nicktime_controls: не удалось обновить клавиатуру")
    except Exception:
        logger.exception("nicktime_controls: непредвиденная ошибка")
        await callback.answer("Произошла ошибка", show_alert=True)


# ==========================================
#      V5: ВОССТАНОВЛЕНИЕ ФОНОВЫХ ЗАДАЧ
# ==========================================

async def restore_background_tasks(bot: Bot):
    restored = 0
    try:
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT owner_id FROM online_state WHERE enabled = 1")
        online_owners = [r[0] for r in cursor.fetchall()]
        cursor.execute("SELECT owner_id FROM nicktime_state WHERE enabled = 1")
        nick_owners = [r[0] for r in cursor.fetchall()]
        conn.close()
    except Exception:
        logger.exception("restore_background_tasks: не удалось прочитать состояния")
        return

    if feature_enabled("feat_online"):
        for owner_id in online_owners:
            try:
                start_online_task(bot, owner_id)
                restored += 1
            except Exception:
                logger.exception("restore: не удалось запустить online для %s", owner_id)
    else:
        logger.info("restore: функция .online выключена, задачи не запускаются")

    if feature_enabled("feat_profile_time"):
        for owner_id in nick_owners:
            try:
                start_nicktime_task(bot, owner_id)
                restored += 1
            except Exception:
                logger.exception("restore: не удалось запустить nicktime для %s", owner_id)
    else:
        logger.info("restore: время в имени выключено, задачи не запускаются")

    logger.info("restore_background_tasks: восстановлено задач: %s", restored)


# ==========================================
#        V5: АДМИНКА — ПРАВА И WHITELIST
# ==========================================

def render_perm_screen(target_id: int, viewer_id: int):
    perms = get_perm_map(target_id)
    user = STATE_USER_CACHE.get(target_id) if "STATE_USER_CACHE" in globals() else None
    row = get_user_row(target_id)
    name = (row[2] if row else None) or str(target_id)

    text = (
        f"🔐 <b>Права администратора</b>\n\n"
        f"👤 {html_lib.escape(str(name))}\n"
        f"🆔 <code>{target_id}</code>\n\n"
        "Нажмите на разрешение, чтобы переключить его."
    )
    if is_main_admin(target_id):
        text += "\n\n👑 Это главный администратор: у него всегда полный доступ."

    rows = []
    current_cat = None
    for p in PERMISSIONS:
        if p["cat"] != current_cat:
            current_cat = p["cat"]
            rows.append([create_premium_button(text=f"— {current_cat} —",
                                               callback_data="perm_noop", style="primary")])
        rows.append([toggle_button(p["name"], perms[p["id"]],
                                   f"ptg_{target_id}_{p['id']}")])
    if is_main_admin(viewer_id) and not is_main_admin(target_id):
        rows.append([
            create_premium_button(text="🟢 Разрешить всё", callback_data=f"pall_{target_id}",
                                  style="success"),
            create_premium_button(text="🔴 Запретить всё", callback_data=f"pnone_{target_id}",
                                  style="danger")
        ])
    rows.append([create_premium_button(text="🔙 Назад", callback_data="admin_rights_list",
                                       style="primary")])
    return text, types.InlineKeyboardMarkup(inline_keyboard=rows)


@dp.callback_query(F.data == "perm_noop")
async def perm_noop(callback: CallbackQuery):
    await callback.answer()


@dp.callback_query(F.data.startswith("pgrant_"))
async def perm_open(callback: CallbackQuery):
    if not has_perm(callback.from_user.id, "manage_admin_permissions"):
        await deny(callback)
        return
    try:
        target_id = int(callback.data.replace("pgrant_", ""))
        text, kb = render_perm_screen(target_id, callback.from_user.id)
        await render_screen(callback, text, kb)
    except Exception:
        logger.exception("perm_open: ошибка отрисовки")
    await callback.answer()


@dp.callback_query(F.data.startswith("ptg_"))
async def perm_toggle(callback: CallbackQuery):
    if not has_perm(callback.from_user.id, "manage_admin_permissions"):
        await deny(callback)
        return
    try:
        rest = callback.data[len("ptg_"):]
        target_raw, perm_id = rest.split("_", 1)
        target_id = int(target_raw)
        if is_main_admin(target_id):
            await callback.answer("👑 Права главного администратора изменить нельзя",
                                  show_alert=True)
            return
        if perm_id not in PERM_INDEX:
            await callback.answer("Неизвестное разрешение", show_alert=True)
            return
        new_value = not has_perm(target_id, perm_id)
        set_perm(target_id, perm_id, new_value)
        text, kb = render_perm_screen(target_id, callback.from_user.id)
        await render_screen(callback, text, kb)
        await callback.answer("🟢 Разрешено" if new_value else "🔴 Запрещено")
    except Exception:
        logger.exception("perm_toggle: непредвиденная ошибка")
        await callback.answer("Произошла ошибка", show_alert=True)


@dp.callback_query(F.data.startswith("pall_"))
async def perm_allow_all(callback: CallbackQuery):
    if not is_main_admin(callback.from_user.id):
        await callback.answer("👑 Только для главного администратора", show_alert=True)
        return
    try:
        target_id = int(callback.data.replace("pall_", ""))
        set_all_perms(target_id, True)
        text, kb = render_perm_screen(target_id, callback.from_user.id)
        await render_screen(callback, text, kb)
        await callback.answer("🟢 Все права выданы")
    except Exception:
        logger.exception("perm_allow_all: непредвиденная ошибка")
        await callback.answer("Произошла ошибка", show_alert=True)


@dp.callback_query(F.data.startswith("pnone_"))
async def perm_deny_all(callback: CallbackQuery):
    if not is_main_admin(callback.from_user.id):
        await callback.answer("👑 Только для главного администратора", show_alert=True)
        return
    try:
        target_id = int(callback.data.replace("pnone_", ""))
        set_all_perms(target_id, False)
        text, kb = render_perm_screen(target_id, callback.from_user.id)
        await render_screen(callback, text, kb)
        await callback.answer("🔴 Все права отозваны")
    except Exception:
        logger.exception("perm_deny_all: непредвиденная ошибка")
        await callback.answer("Произошла ошибка", show_alert=True)


def render_whitelist_screen(page: int = 0):
    items_all = whitelist_all()
    items, page, total = paginate_list(items_all, page)
    enabled = get_flag("whitelist_enabled", "1") == "1"

    text = (
        "👁 <b>Скрытые пользователи (whitelist)</b>\n\n"
        f"Статус: {'🟢 включён' if enabled else '🔴 выключен'}\n"
        f"В списке: <b>{len(items_all)}</b>\n\n"
        "Пользователям из списка бот не отправляет уведомления об удалении "
        "и изменении их сообщений.\n\n"
    )
    if items:
        for r in items:
            text += f"• <code>{r[0]}</code> · {r[2]}\n"
    else:
        text += "<i>Список пуст.</i>"

    rows = []
    for r in items:
        rows.append([create_premium_button(text=f"🗑 Удалить {r[0]}",
                                           callback_data=f"wldel_{r[0]}", style="danger")])
    nav = page_row("wlp_", page, total)
    if nav:
        rows.append(nav)
    rows.append([
        create_premium_button(text="➕ Добавить ID", callback_data="wladd", style="success"),
        create_premium_button(text="🔎 Проверить ID", callback_data="wlcheck", style="primary")
    ])
    rows.append([toggle_button("Whitelist", enabled, "wltoggle")])
    rows.append(nav_rows()[0])
    rows.append(nav_rows()[1])
    return text, types.InlineKeyboardMarkup(inline_keyboard=rows)


@dp.callback_query(F.data == "adm_whitelist")
async def whitelist_menu(callback: CallbackQuery):
    if not has_perm(callback.from_user.id, "manage_whitelist"):
        await deny(callback)
        return
    try:
        text, kb = render_whitelist_screen(0)
        await render_screen(callback, text, kb)
    except Exception:
        logger.exception("whitelist_menu: ошибка отрисовки")
    await callback.answer()


@dp.callback_query(F.data.startswith("wlp_"))
async def whitelist_page(callback: CallbackQuery):
    if not has_perm(callback.from_user.id, "manage_whitelist"):
        await deny(callback)
        return
    try:
        page = int(callback.data.replace("wlp_", ""))
        text, kb = render_whitelist_screen(page)
        await render_screen(callback, text, kb)
    except Exception:
        logger.exception("whitelist_page: ошибка отрисовки")
    await callback.answer()


@dp.callback_query(F.data == "wltoggle")
async def whitelist_toggle(callback: CallbackQuery):
    if not has_perm(callback.from_user.id, "manage_whitelist_settings"):
        await deny(callback)
        return
    try:
        enabled = get_flag("whitelist_enabled", "1") == "1"
        set_flag("whitelist_enabled", "0" if enabled else "1")
        logger.info("Whitelist переключён -> %s", not enabled)
        text, kb = render_whitelist_screen(0)
        await render_screen(callback, text, kb)
        await callback.answer("🔴 Выключен" if enabled else "🟢 Включён")
    except Exception:
        logger.exception("whitelist_toggle: непредвиденная ошибка")
        await callback.answer("Произошла ошибка", show_alert=True)


@dp.callback_query(F.data == "wladd")
async def whitelist_add_start(callback: CallbackQuery, state: FSMContext):
    if not has_perm(callback.from_user.id, "add_whitelist"):
        await deny(callback)
        return
    try:
        await state.set_state(BotStates.waiting_for_whitelist_add)
        await render_screen(
            callback,
            "➕ <b>Добавление в whitelist</b>\n\nОтправьте Telegram ID пользователя одним "
            "сообщением, например <code>123456789</code>",
            types.InlineKeyboardMarkup(inline_keyboard=nav_rows("adm_whitelist"))
        )
    except Exception:
        logger.exception("whitelist_add_start: ошибка")
    await callback.answer()


@dp.message(BotStates.waiting_for_whitelist_add)
async def whitelist_add_process(message: Message, state: FSMContext):
    try:
        if not has_perm(message.from_user.id, "add_whitelist"):
            await state.clear()
            await message.answer("🔴 Недостаточно прав")
            return
        await state.clear()
        raw = (message.text or "").strip()
        if not raw.isdigit():
            await message.answer("🔴 Нужен числовой ID. Откройте раздел и попробуйте снова.")
            return
        whitelist_add(int(raw))
        text, kb = render_whitelist_screen(0)
        await message.answer(f"🟢 ID <code>{raw}</code> добавлен в whitelist.",
                             parse_mode="HTML", reply_markup=kb)
    except Exception:
        logger.exception("whitelist_add_process: непредвиденная ошибка")
        await message.answer("🔴 Не удалось добавить ID.")


@dp.callback_query(F.data == "wlcheck")
async def whitelist_check_start(callback: CallbackQuery, state: FSMContext):
    if not has_perm(callback.from_user.id, "manage_whitelist"):
        await deny(callback)
        return
    try:
        await state.set_state(BotStates.waiting_for_whitelist_check)
        await render_screen(
            callback,
            "🔎 <b>Проверка ID</b>\n\nОтправьте Telegram ID, чтобы узнать, есть ли он в списке.",
            types.InlineKeyboardMarkup(inline_keyboard=nav_rows("adm_whitelist"))
        )
    except Exception:
        logger.exception("whitelist_check_start: ошибка")
    await callback.answer()


@dp.message(BotStates.waiting_for_whitelist_check)
async def whitelist_check_process(message: Message, state: FSMContext):
    try:
        await state.clear()
        raw = (message.text or "").strip()
        if not raw.isdigit():
            await message.answer("🔴 Нужен числовой ID.")
            return
        found = any(r[0] == int(raw) for r in whitelist_all())
        await message.answer(
            f"{'🟢 Найден' if found else '⚪ Не найден'}: <code>{raw}</code>",
            parse_mode="HTML",
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=nav_rows("adm_whitelist"))
        )
    except Exception:
        logger.exception("whitelist_check_process: непредвиденная ошибка")
        await message.answer("🔴 Ошибка проверки.")


@dp.callback_query(F.data.startswith("wldel_"))
async def whitelist_del_confirm(callback: CallbackQuery):
    if not has_perm(callback.from_user.id, "remove_whitelist"):
        await deny(callback)
        return
    try:
        target = callback.data.replace("wldel_", "")
        rows = confirm_rows(f"wldelok_{target}", "adm_whitelist")
        await render_screen(
            callback,
            f"⚠️ <b>Вы уверены?</b>\n\nID <code>{target}</code> будет удалён из whitelist.",
            types.InlineKeyboardMarkup(inline_keyboard=rows)
        )
    except Exception:
        logger.exception("whitelist_del_confirm: ошибка")
    await callback.answer()


@dp.callback_query(F.data.startswith("wldelok_"))
async def whitelist_del_apply(callback: CallbackQuery):
    if not has_perm(callback.from_user.id, "remove_whitelist"):
        await deny(callback)
        return
    try:
        whitelist_remove(int(callback.data.replace("wldelok_", "")))
        text, kb = render_whitelist_screen(0)
        await render_screen(callback, text, kb)
        await callback.answer("🗑 Удалён")
    except Exception:
        logger.exception("whitelist_del_apply: непредвиденная ошибка")
        await callback.answer("Произошла ошибка", show_alert=True)


# ==========================================
#     V5: АДМИНКА — ГЛАВНЫЙ АДМИН, ФУНКЦИИ
# ==========================================

def render_features_screen():
    text = (
        "🔧 <b>Функции бота</b>\n\n"
        "Выключенная функция не запускается даже после перезапуска бота.\n\n"
    )
    rows = []
    for f in FEATURES:
        enabled = feature_enabled(f["id"])
        text += f"{'🟢' if enabled else '🔴'} {f['name']}\n"
        rows.append([toggle_button(f["name"], enabled, f"ftg_{f['id']}")])
    rows.append(nav_rows()[0])
    rows.append(nav_rows()[1])
    return text, types.InlineKeyboardMarkup(inline_keyboard=rows)


@dp.callback_query(F.data == "adm_features")
async def features_menu(callback: CallbackQuery):
    if not has_perm(callback.from_user.id, "manage_settings"):
        await deny(callback)
        return
    try:
        text, kb = render_features_screen()
        await render_screen(callback, text, kb)
    except Exception:
        logger.exception("features_menu: ошибка отрисовки")
    await callback.answer()


@dp.callback_query(F.data.startswith("ftg_"))
async def feature_toggle(callback: CallbackQuery):
    if not has_perm(callback.from_user.id, "manage_settings"):
        await deny(callback)
        return
    try:
        feature_id = callback.data.replace("ftg_", "")
        if feature_id not in FEATURE_INDEX:
            await callback.answer("Неизвестная функция", show_alert=True)
            return
        new_value = not feature_enabled(feature_id)
        set_feature(feature_id, new_value)
        if not new_value:
            if feature_id == "feat_online":
                for key in [k for k in BG_TASKS if k[0] == "online"]:
                    stop_online_task(key[1])
            if feature_id == "feat_profile_time":
                for key in [k for k in BG_TASKS if k[0] == "nicktime"]:
                    stop_nicktime_task(key[1])
        text, kb = render_features_screen()
        await render_screen(callback, text, kb)
        await callback.answer("🟢 Включено" if new_value else "🔴 Выключено")
    except Exception:
        logger.exception("feature_toggle: непредвиденная ошибка")
        await callback.answer("Произошла ошибка", show_alert=True)


@dp.callback_query(F.data == "adm_mainadmin")
async def main_admin_menu(callback: CallbackQuery):
    if not is_main_admin(callback.from_user.id):
        await callback.answer("👑 Только для главного администратора", show_alert=True)
        return
    try:
        text = (
            "👑 <b>Главный администратор</b>\n\n"
            f"Текущий: <code>{get_main_admin()}</code>\n\n"
            "Главный администратор назначает и снимает других администраторов, "
            "управляет их правами и массовыми действиями.\n\n"
            "⚠️ После смены вы потеряете доступ к этим действиям."
        )
        rows = [
            [create_premium_button(text="🔧 Сменить главного администратора",
                                   callback_data="mainadm_change", style="danger")],
            nav_rows()[0],
            nav_rows()[1]
        ]
        await render_screen(callback, text, types.InlineKeyboardMarkup(inline_keyboard=rows))
    except Exception:
        logger.exception("main_admin_menu: ошибка отрисовки")
    await callback.answer()


@dp.callback_query(F.data == "mainadm_change")
async def main_admin_change_start(callback: CallbackQuery, state: FSMContext):
    if not is_main_admin(callback.from_user.id):
        await callback.answer("👑 Только для главного администратора", show_alert=True)
        return
    try:
        await state.set_state(BotStates.waiting_for_main_admin)
        await render_screen(
            callback,
            "🔧 <b>Смена главного администратора</b>\n\n"
            "Отправьте Telegram ID нового главного администратора.",
            types.InlineKeyboardMarkup(inline_keyboard=nav_rows("adm_mainadmin"))
        )
    except Exception:
        logger.exception("main_admin_change_start: ошибка")
    await callback.answer()


@dp.message(BotStates.waiting_for_main_admin)
async def main_admin_change_input(message: Message, state: FSMContext):
    try:
        if not is_main_admin(message.from_user.id):
            await state.clear()
            await message.answer("🔴 Недостаточно прав")
            return
        raw = (message.text or "").strip()
        if not raw.isdigit():
            await message.answer("🔴 Нужен числовой ID.")
            return
        await state.clear()
        rows = confirm_rows(f"mainadmok_{raw}", "adm_mainadmin")
        await message.answer(
            f"⚠️ <b>Вы уверены?</b>\n\nГлавным администратором станет <code>{raw}</code>.\n"
            "Вы потеряете доступ к управлению администраторами.",
            parse_mode="HTML",
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=rows)
        )
    except Exception:
        logger.exception("main_admin_change_input: непредвиденная ошибка")
        await message.answer("🔴 Ошибка обработки.")


@dp.callback_query(F.data.startswith("mainadmok_"))
async def main_admin_change_apply(callback: CallbackQuery):
    if not is_main_admin(callback.from_user.id):
        await callback.answer("👑 Только для главного администратора", show_alert=True)
        return
    try:
        new_id = int(callback.data.replace("mainadmok_", ""))
        set_main_admin(new_id)
        add_extra_admin(new_id)
        set_all_perms(new_id, True)
        await render_screen(
            callback,
            f"🟢 <b>Готово</b>\n\nГлавный администратор: <code>{new_id}</code>",
            types.InlineKeyboardMarkup(inline_keyboard=[nav_rows()[1]])
        )
        await callback.answer("Главный администратор изменён")
    except Exception:
        logger.exception("main_admin_change_apply: непредвиденная ошибка")
        await callback.answer("Произошла ошибка", show_alert=True)


# ==========================================
#      V5: КОМАНДЫ .ONLINE / .TIME / .GAME
# ==========================================

async def handle_v5_command(message: Message, bot: Bot, owner_id: int, trigger: str) -> bool:
    try:
        if trigger == ".online":
            return await online_in_chat(message, bot, owner_id)

        if trigger == ".online_legacy":
            state = get_online_state(owner_id)
            if not state["target_chat_id"]:
                await edit_owner_message(
                    bot, message,
                    "🟡 <b>Нет подключения</b>\n\n"
                    f"Сначала напишите что-нибудь пользователю @{ONLINE_TARGET_USERNAME}, "
                    "затем повторите команду <code>.online</code>."
                )
                return True
            await edit_owner_message(
                bot, message,
                "🔵 <b>Поддержание активности</b>\n\n"
                "Панель управления отправлена вам в чат с ботом."
            )
            try:
                await bot.send_message(
                    owner_id,
                    "🔵 <b>Функция .online</b>\n\n"
                    "Бот примерно раз в 10 секунд отправляет служебное сообщение "
                    "и сразу удаляет его.",
                    parse_mode="HTML",
                    reply_markup=online_keyboard(owner_id)
                )
            except Exception:
                logger.exception("handle_v5_command: не удалось отправить панель .online")
            return True

        if trigger == ".nicktime":
            if not feature_enabled("feat_profile_time"):
                await edit_owner_message(bot, message, "🔴 Функция отключена администратором.")
                return True
            conn_id = message.business_connection_id
            if not await check_name_right(bot, conn_id):
                await edit_owner_message(
                    bot, message,
                    "🔴 Выдайте боту необходимые разрешения: в разделе «Автоматизация чатов» "
                    "разрешите изменение имени. После этого повторите команду."
                )
                try:
                    await bot.send_message(
                        owner_id,
                        "🔴 <b>Нет разрешения на изменение имени</b>\n\n"
                        "Нажмите кнопку ниже, откройте «Чат-боты» и разрешите боту "
                        "изменение имени. Затем повторите команду "
                        "<code>.nicktime</code>.",
                        parse_mode="HTML",
                        reply_markup=permission_keyboard()
                    )
                except Exception:
                    logger.exception("nicktime: не удалось отправить кнопку разрешения")
                return True
            state = get_nicktime_state(owner_id)
            base_first = state["base_first"]
            if not base_first:
                try:
                    info = await bot.get_business_connection(conn_id)
                    base_first = info.user.first_name or "Имя"
                except Exception:
                    logger.exception("handle_v5_command: не удалось получить имя владельца")
                    base_first = "Имя"
            save_nicktime_state(owner_id, state["enabled"], base_first,
                                state["base_last"], conn_id)
            await edit_owner_message(
                bot, message,
                "🔵 <b>Время в имени</b>\n\nПанель управления отправлена вам в чат с ботом."
            )
            try:
                await bot.send_message(
                    owner_id,
                    nicktime_panel_text(owner_id),
                    parse_mode="HTML",
                    reply_markup=nicktime_keyboard_v6(owner_id)
                )
            except Exception:
                logger.exception("handle_v5_command: не удалось отправить панель времени")
            return True

        if trigger == ".game":
            return await start_pvp_game(bot, message, owner_id)

        if trigger == ".connect":
            await edit_owner_message(bot, message, connect_instructions_text())
            return True
    except Exception:
        logger.exception("handle_v5_command: ошибка команды %s", trigger)
        try:
            await edit_owner_message(bot, message, "🔴 Ошибка выполнения команды.")
        except Exception:
            logger.exception("handle_v5_command: не удалось сообщить об ошибке")
        return True
    return False



# ==========================================
#     ОТРЕДАКТИРОВАННЫЕ БИЗНЕС-СООБЩЕНИЯ
# ==========================================

edited_router = Router()


@edited_router.edited_business_message()
async def handle_edited_business_message(message: Message, bot: Bot):
    try:
        conn_info = await bot.get_business_connection(message.business_connection_id)
        owner_id = conn_info.user.id
    except Exception:
        logger.exception("handle_edited_business_message: ошибка бизнес-соединения")
        return

    if not await is_subscribed(bot, owner_id):
        return

    chat_id = message.chat.id
    msg_id = message.message_id
    editor = message.from_user

    if not message.text or not editor:
        return

    if editor.id == owner_id:
        save_message(chat_id, msg_id, editor.id, "text", message.text)
        return

    saved_msg = get_message(chat_id, msg_id)

    if saved_msg and saved_msg["media_type"] == "text":
        old_text = saved_msg["content"]
        if old_text == message.text:
            return
    else:
        old_text = "<i>[Сообщение отсутствует в базе данных бота]</i>"

    new_text = message.text

    first_name = editor.first_name or "Пользователь"
    if editor.username:
        user_mention = f"@{editor.username}"
    else:
        user_mention = f'<a href="tg://user?id={editor.id}">{first_name}</a>'

    notify_text = (
        f'✏️ <b>Пользователь {user_mention} (ID: <code>{editor.id}</code>) '
        f'отредактировал сообщение</b>\n\n'
        f'<b>Было:</b> {old_text}\n'
        f'<b>Стало:</b> {new_text}'
    )

    try:
        await bot.send_message(chat_id=owner_id, text=notify_text, parse_mode="HTML")
    except Exception:
        logger.exception("handle_edited_business_message: ошибка отправки уведомления")

    save_message(chat_id, msg_id, editor.id, "text", new_text)


register_v7_permissions()


async def main():
    if not BOT_TOKEN:
        raise SystemExit("Вставьте BOT_TOKEN в первую строку файла bot.py")

    bot = Bot(token=BOT_TOKEN)

    dp.edited_business_message.middleware(EditedLogMiddleware())

    try:
        await restore_background_tasks(bot)
    except Exception:
        logger.exception("main: не удалось восстановить фоновые задачи")

    # Подключаем роутер обработки редактирований
    dp.include_router(edited_router)

    await bot.set_my_commands([BotCommand(command="start", description="Главное меню")])
    await bot.delete_webhook(drop_pending_updates=True)

    allowed_updates = [
        "message", 
        "callback_query", 
        "business_connection", 
        "business_message", 
        "deleted_business_messages", 
        "edited_business_message"
    ]
    logger.info("Бот запущен. Главный администратор: %s", get_main_admin())
    await dp.start_polling(bot, allowed_updates=allowed_updates)

if __name__ == "__main__":
    asyncio.run(main())
