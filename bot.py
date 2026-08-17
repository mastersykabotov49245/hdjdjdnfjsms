import asyncio
import logging
from datetime import datetime
from typing import Dict, Set

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import (
    InlineKeyboardMarkup, 
    InlineKeyboardButton,
    Message
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from sqlalchemy import create_engine, Column, Integer, String, DateTime, BigInteger, Text
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker as async_sessionmaker
from sqlalchemy import select

# === НАСТРОЙКИ ===
BOT_TOKEN = "8677123574:AAFzqoXF10O8dTkFFgefnWPaan8ZRkY1yRw"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === БАЗА ДАННЫХ ===
DATABASE_URL = "sqlite+aiosqlite:///mute_bot.db"
engine = create_async_engine(DATABASE_URL, echo=True)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()

class MutedUser(Base):
    __tablename__ = "muted_users"
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, unique=True, nullable=False)
    muted_at = Column(DateTime, default=datetime.utcnow)

class DeletedMessage(Base):
    __tablename__ = "deleted_messages"
    id = Column(Integer, primary_key=True)
    chat_id = Column(BigInteger, nullable=False)
    message_id = Column(Integer, nullable=False)
    user_id = Column(BigInteger, nullable=False)
    text = Column(Text, nullable=True)
    deleted_at = Column(DateTime, default=datetime.utcnow)

class EditedMessage(Base):
    __tablename__ = "edited_messages"
    id = Column(Integer, primary_key=True)
    chat_id = Column(BigInteger, nullable=False)
    message_id = Column(Integer, nullable=False)
    user_id = Column(BigInteger, nullable=False)
    old_text = Column(Text, nullable=True)
    new_text = Column(Text, nullable=True)
    edited_at = Column(DateTime, default=datetime.utcnow)

# === СОСТОЯНИЯ ДЛЯ FSM ===
class MuteStates(StatesGroup):
    waiting_for_mute = State()
    waiting_for_unmute = State()

# === ИНИЦИАЛИЗАЦИЯ ===
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# === ХРАНИЛИЩЕ В ПАМЯТИ (для быстрых операций) ===
muted_cache: Set[int] = set()
deleted_cache: Dict[int, Dict[int, str]] = {}  # chat_id -> {message_id: text}

# === КНОПКИ ===
def get_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔇 Замутить", callback_data="mute"),
                InlineKeyboardButton(text="🔊 Размутить", callback_data="unmute")
            ],
            [
                InlineKeyboardButton(text="📊 Показать муты", callback_data="list_mutes"),
                InlineKeyboardButton(text="🗑️ Очистить муты", callback_data="clear_mutes")
            ],
            [
                InlineKeyboardButton(text="📝 Последние удалённые", callback_data="last_deleted"),
                InlineKeyboardButton(text="✏️ Последние правки", callback_data="last_edits")
            ]
        ]
    )

# === РАБОТА С БАЗОЙ ДАННЫХ ===
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def add_muted_user(user_id: int) -> bool:
    async with async_session() as session:
        # Проверяем, есть ли уже
        result = await session.execute(
            select(MutedUser).where(MutedUser.user_id == user_id)
        )
        if result.scalar_one_or_none():
            return False
        
        muted = MutedUser(user_id=user_id)
        session.add(muted)
        await session.commit()
        muted_cache.add(user_id)
        return True

async def remove_muted_user(user_id: int) -> bool:
    async with async_session() as session:
        result = await session.execute(
            select(MutedUser).where(MutedUser.user_id == user_id)
        )
        muted = result.scalar_one_or_none()
        if not muted:
            return False
        
        await session.delete(muted)
        await session.commit()
        muted_cache.discard(user_id)
        return True

async def get_muted_users() -> list:
    async with async_session() as session:
        result = await session.execute(select(MutedUser))
        return result.scalars().all()

async def save_deleted_message(chat_id: int, message_id: int, user_id: int, text: str = None):
    async with async_session() as session:
        deleted = DeletedMessage(
            chat_id=chat_id,
            message_id=message_id,
            user_id=user_id,
            text=text
        )
        session.add(deleted)
        await session.commit()

async def save_edited_message(chat_id: int, message_id: int, user_id: int, old_text: str, new_text: str):
    async with async_session() as session:
        edited = EditedMessage(
            chat_id=chat_id,
            message_id=message_id,
            user_id=user_id,
            old_text=old_text,
            new_text=new_text
        )
        session.add(edited)
        await session.commit()

async def get_last_deleted(chat_id: int, limit: int = 10) -> list:
    async with async_session() as session:
        result = await session.execute(
            select(DeletedMessage)
            .where(DeletedMessage.chat_id == chat_id)
            .order_by(DeletedMessage.deleted_at.desc())
            .limit(limit)
        )
        return result.scalars().all()

async def get_last_edits(chat_id: int, limit: int = 10) -> list:
    async with async_session() as session:
        result = await session.execute(
            select(EditedMessage)
            .where(EditedMessage.chat_id == chat_id)
            .order_by(EditedMessage.edited_at.desc())
            .limit(limit)
        )
        return result.scalars().all()

# === ЗАГРУЗКА КЭША ПРИ СТАРТЕ ===
async def load_muted_cache():
    async with async_session() as session:
        result = await session.execute(select(MutedUser))
        muted_users = result.scalars().all()
        muted_cache.clear()
        for user in muted_users:
            muted_cache.add(user.user_id)

# === ХЭНДЛЕРЫ ===
@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "👋 Привет! Я бот для управления перепиской в личных сообщениях.\n\n"
        "📌 Команды:\n"
        "• `.mute` — замутить собеседника\n"
        "• `.unmute` — размутить собеседника\n"
        "• `.status` — проверить статус\n"
        "• `.history` — показать последние удалённые сообщения\n\n"
        "Или используй кнопки ниже 👇",
        reply_markup=get_main_keyboard()
    )
    # Уведомление о подключении
    await message.answer("✅ Бот успешно подключён и готов к работе!")

@dp.message(Command("mute"))
async def cmd_mute(message: Message):
    user_id = message.from_user.id
    
    # Удаляем команду
    try:
        await message.delete()
    except:
        pass
    
    # Проверяем, не замучен ли уже
    if user_id in muted_cache:
        await message.answer("🔇 Ты уже в муте!")
        return
    
    # Добавляем в мут
    if await add_muted_user(user_id):
        await message.answer("🔇 Замолчи", reply_to_message_id=message.message_id)
        await message.answer(f"✅ Ты замучен! Все твои сообщения будут удаляться.")
        logger.info(f"User {user_id} was muted")
    else:
        await message.answer("❌ Что-то пошло не так")

@dp.message(Command("unmute"))
async def cmd_unmute(message: Message):
    user_id = message.from_user.id
    
    # Удаляем команду
    try:
        await message.delete()
    except:
        pass
    
    if user_id not in muted_cache:
        await message.answer("🔊 Ты и так размучен!")
        return
    
    if await remove_muted_user(user_id):
        await message.answer("🔊 Ты размучен. Сообщения больше не удаляются.")
        logger.info(f"User {user_id} was unmuted")
    else:
        await message.answer("❌ Что-то пошло не так")

@dp.message(Command("status"))
async def cmd_status(message: Message):
    user_id = message.from_user.id
    
    if user_id in muted_cache:
        await message.answer(f"🔇 Статус: **Замучен**\nТвои сообщения удаляются.")
    else:
        await message.answer(f"🔊 Статус: **Размучен**\nТвои сообщения НЕ удаляются.")

@dp.message(Command("history"))
async def cmd_history(message: Message):
    chat_id = message.chat.id
    deleted = await get_last_deleted(chat_id, limit=5)
    
    if not deleted:
        await message.answer("📭 Нет удалённых сообщений в этом чате.")
        return
    
    text = "📝 **Последние удалённые сообщения:**\n\n"
    for i, msg in enumerate(deleted, 1):
        text += f"{i}. От {msg.user_id}: `{msg.text or '[без текста]'}`\n"
        text += f"   🕐 {msg.deleted_at.strftime('%H:%M:%S %d.%m.%Y')}\n\n"
    
    await message.answer(text)

# === ГЛАВНЫЙ ПЕРЕХВАТЧИК СООБЩЕНИЙ ===
@dp.message()
async def handle_all_messages(message: Message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    message_id = message.message_id
    
    # Проверяем, замучен ли пользователь
    if user_id in muted_cache:
        # Сохраняем в кэш для бизнес-режима
        if chat_id not in deleted_cache:
            deleted_cache[chat_id] = {}
        deleted_cache[chat_id][message_id] = message.text or "[медиа/файл]"
        
        # Удаляем сообщение
        try:
            await message.delete()
            # Сохраняем в БД
            await save_deleted_message(
                chat_id=chat_id,
                message_id=message_id,
                user_id=user_id,
                text=message.text or "[медиа/файл]"
            )
            logger.info(f"Deleted message {message_id} from muted user {user_id}")
        except Exception as e:
            logger.error(f"Failed to delete message: {e}")

# === ОБРАБОТКА РЕДАКТИРОВАНИЙ (бизнес-режим) ===
@dp.edited_message()
async def handle_edited_message(message: Message):
    if not message.text:
        return
    
    # Сохраняем старый текст из кэша
    chat_id = message.chat.id
    message_id = message.message_id
    user_id = message.from_user.id
    
    if chat_id in deleted_cache and message_id in deleted_cache[chat_id]:
        old_text = deleted_cache[chat_id][message_id]
        new_text = message.text
        
        # Сохраняем правку
        await save_edited_message(
            chat_id=chat_id,
            message_id=message_id,
            user_id=user_id,
            old_text=old_text,
            new_text=new_text
        )
        
        # Обновляем кэш
        deleted_cache[chat_id][message_id] = new_text
        
        logger.info(f"Message {message_id} was edited by {user_id}")

# === ОБРАБОТКА УДАЛЕНИЙ (бизнес-режим) ===
@dp.deleted_messages()
async def handle_deleted_messages(deleted_messages: Dict):
    # Это работает только в бизнес-режиме
    for chat_id, messages in deleted_messages.items():
        for msg in messages:
            if chat_id in deleted_cache and msg.message_id in deleted_cache[chat_id]:
                text = deleted_cache[chat_id].pop(msg.message_id)
                await save_deleted_message(
                    chat_id=chat_id,
                    message_id=msg.message_id,
                    user_id=msg.from_user.id,
                    text=text
                )

# === ОБРАБОТКА КНОПОК ===
@dp.callback_query()
async def handle_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    if callback.data == "mute":
        await cmd_mute(callback.message)
        await callback.answer("✅ Команда выполнена")
    
    elif callback.data == "unmute":
        await cmd_unmute(callback.message)
        await callback.answer("✅ Команда выполнена")
    
    elif callback.data == "list_mutes":
        muted_users = await get_muted_users()
        if not muted_users:
            await callback.message.answer("📭 Нет замученных пользователей.")
        else:
            text = "🔇 **Замученные пользователи:**\n\n"
            for user in muted_users:
                text += f"• ID: {user.user_id}\n"
                text += f"  🕐 {user.muted_at.strftime('%H:%M:%S %d.%m.%Y')}\n\n"
            await callback.message.answer(text)
        await callback.answer()
    
    elif callback.data == "clear_mutes":
        # Очищаем все муты
        async with async_session() as session:
            await session.execute(MutedUser.__table__.delete())
            await session.commit()
            muted_cache.clear()
        await callback.message.answer("🗑️ Все муты очищены!")
        await callback.answer()
    
    elif callback.data == "last_deleted":
        chat_id = callback.message.chat.id
        deleted = await get_last_deleted(chat_id, limit=5)
        if not deleted:
            await callback.message.answer("📭 Нет удалённых сообщений.")
        else:
            text = "📝 **Последние удалённые:**\n\n"
            for i, msg in enumerate(deleted, 1):
                text += f"{i}. От `{msg.user_id}`: {msg.text or '[медиа]'}\n"
                text += f"   🕐 {msg.deleted_at.strftime('%H:%M:%S')}\n\n"
            await callback.message.answer(text)
        await callback.answer()
    
    elif callback.data == "last_edits":
        chat_id = callback.message.chat.id
        edits = await get_last_edits(chat_id, limit=5)
        if not edits:
            await callback.message.answer("📭 Нет отредактированных сообщений.")
        else:
            text = "✏️ **Последние правки:**\n\n"
            for i, msg in enumerate(edits, 1):
                text += f"{i}. От `{msg.user_id}`:\n"
                text += f"   Было: {msg.old_text or '[пусто]'}\n"
                text += f"   Стало: {msg.new_text or '[пусто]'}\n"
                text += f"   🕐 {msg.edited_at.strftime('%H:%M:%S')}\n\n"
            await callback.message.answer(text)
        await callback.answer()

# === ЗАПУСК ===
async def main():
    await init_db()
    await load_muted_cache()
    
    # Уведомление о запуске
    logger.info("🚀 Бот запущен!")
    logger.info(f"📊 Загружено {len(muted_cache)} замученных пользователей")
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
