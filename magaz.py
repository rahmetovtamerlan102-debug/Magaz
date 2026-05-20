#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import logging
import os
import sqlite3
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

load_dotenv()

# ==================== КОНФИГУРАЦИЯ ====================
TELEGRAM_TOKEN = os.getenv("BOT_TOKEN")
if not TELEGRAM_TOKEN:
    raise ValueError("❌ BOT_TOKEN не задан")

ADMIN_ID = 8793207271

PRICES = {
    "easy": 25,
    "medium": 50,
    "hard": 75
}

SUPPORT_CONTACT = "@notorepa"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ==================== БАЗА ДАННЫХ ====================
DB_PATH = "shop.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            plan TEXT,
            amount INTEGER,
            purchased_at INTEGER
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def save_purchase(user_id: int, plan: str, amount: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO purchases (user_id, plan, amount, purchased_at) VALUES (?, ?, ?, ?)",
        (user_id, plan, amount, int(datetime.now().timestamp()))
    )
    conn.commit()
    conn.close()

# ==================== КЛАВИАТУРЫ ====================
def main_keyboard():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 ЗАКАЗАТЬ ЭДИТ", callback_data="order")],
        [InlineKeyboardButton(text="ℹ️ О МАГАЗИНЕ", callback_data="about")]
    ])
    return kb

def plans_keyboard():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✨ ЛЁГКИЙ (25 ★)", callback_data="plan_easy")],
        [InlineKeyboardButton(text="⚡ СРЕДНИЙ (50 ★)", callback_data="plan_medium")],
        [InlineKeyboardButton(text="🔥 СЛОЖНЫЙ (75 ★)", callback_data="plan_hard")],
        [InlineKeyboardButton(text="◀ НАЗАД", callback_data="back_to_main")]
    ])
    return kb

# ==================== ОБРАБОТЧИКИ ====================
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "🎬 *EDIT SHOP - BRAZILIA*\n\n"
        "🛒 *Как сделать заказ:*\n"
        "1. Нажмите «ЗАКАЗАТЬ ЭДИТ»\n"
        "2. Выберите сложность\n"
        "3. Оплатите через Telegram Stars\n"
        "4. После оплаты получите контакт для получения эдита\n\n"
        "👇 *Выберите действие:*",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )

@dp.callback_query(F.data == "back_to_main")
async def back_to_main(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "🎬 *EDIT SHOP - BRAZILIA*\n\nВыберите действие:",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )
    await callback.answer()

@dp.callback_query(F.data == "about")
async def about_shop(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "ℹ️ *О магазине*\n\n"
        "• *Лёгкий эдит* — 25 ★\n"
        "• *Средний эдит* — 50 ★\n"
        "• *Сложный эдит* — 75 ★\n\n"
        "После оплаты вы получите контакт для получения эдита.\n\n"
        "По всем вопросам: @notorepa",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀ НАЗАД", callback_data="back_to_main")]
        ])
    )
    await callback.answer()

@dp.callback_query(F.data == "order")
async def order_start(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "🎬 *Выберите сложность эдита:*\n\n"
        "• *Лёгкий* – 25 ★\n"
        "• *Средний* – 50 ★\n"
        "• *Сложный* – 75 ★\n\n"
        "👇 *Нажмите на нужный вариант:*",
        parse_mode="Markdown",
        reply_markup=plans_keyboard()
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("plan_"))
async def plan_chosen(callback: types.CallbackQuery):
    plan_type = callback.data.split("_")[1]  # easy, medium, hard
    amount = PRICES[plan_type]
    
    plan_names = {
        "easy": "Лёгкий эдит",
        "medium": "Средний эдит",
        "hard": "Сложный эдит"
    }
    plan_title = plan_names[plan_type]
    
    # Отправляем инвойс для оплаты звёздами
    await bot.send_invoice(
        chat_id=callback.message.chat.id,
        title=f"Эдит - {plan_title}",
        description=f"Покупка эдита сложности «{plan_title}». После оплаты вы получите контакт.",
        payload=f"edit_{plan_type}_{callback.from_user.id}",
        provider_token="",  # для звёзд оставляем пустым
        currency="XTR",
        prices=[LabeledPrice(label=plan_title, amount=amount)],
        start_parameter="edit_shop",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀ Отмена", callback_data="back_to_main")]
        ])
    )
    await callback.answer()

@dp.pre_checkout_query()
async def pre_checkout_handler(pre_checkout: types.PreCheckoutQuery):
    await pre_checkout.answer(ok=True)

@dp.message(F.successful_payment)
async def successful_payment(message: types.Message):
    payment = message.successful_payment
    payload = payment.invoice_payload
    try:
        _, plan_type, user_id = payload.split("_")
    except:
        plan_type = "unknown"
    
    amount = payment.total_amount
    
    # Сохраняем покупку
    save_purchase(message.from_user.id, plan_type, amount)
    
    # Отправляем контакт
    await message.answer(
        f"✅ *Оплата прошла успешно!*\n\n"
        f"🎬 Вы приобрели *{plan_type.upper()}* эдит за {amount} ★.\n\n"
        f"📞 *Контакт для получения эдита:*\n{SUPPORT_CONTACT}\n\n"
        f"👉 Напишите @notorepa, укажите свой Telegram ID и какой эдит вы купили.\n\n"
        f"Спасибо за покупку! 🎉",
        parse_mode="Markdown"
    )
    
    # Уведомление админу
    await bot.send_message(
        ADMIN_ID,
        f"🛒 *Новая покупка!*\n"
        f"👤 Пользователь: {message.from_user.id} (@{message.from_user.username})\n"
        f"🎬 Товар: {plan_type.upper()} эдит\n"
        f"💰 Сумма: {amount} ★",
        parse_mode="Markdown"
    )

# ==================== ЗАПУСК ====================
async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Бот магазина эдитов запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
