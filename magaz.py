#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import logging
import os
import sqlite3
import aiohttp
from datetime import datetime
from threading import Thread
from flask import Flask
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
PORT = int(os.getenv("PORT", "8080"))

PRICES = {"easy": 25, "medium": 50, "hard": 75}
SUPPORT_CONTACT = "@notorepa"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ==================== FLASK + SELF-PING ====================
flask_app = Flask(__name__)

@flask_app.route('/')
def health_check():
    return "Bot is running", 200

def run_flask():
    flask_app.run(host='0.0.0.0', port=PORT)

async def self_pinger():
    url = f"http://localhost:{PORT}/"
    while True:
        await asyncio.sleep(240)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as resp:
                    if resp.status == 200:
                        logger.info("🏓 Self-ping отправлен")
        except Exception as e:
            logger.error(f"Self-ping ошибка: {e}")

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
def menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 ЗАКАЗАТЬ ЭДИТ", callback_data="order")],
        [InlineKeyboardButton(text="ℹ️ О МАГАЗИНЕ", callback_data="about")]
    ])

def plans():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✨ ЛЁГКИЙ (25 ★)", callback_data="plan_easy")],
        [InlineKeyboardButton(text="⚡ СРЕДНИЙ (50 ★)", callback_data="plan_medium")],
        [InlineKeyboardButton(text="🔥 СЛОЖНЫЙ (75 ★)", callback_data="plan_hard")],
        [InlineKeyboardButton(text="◀ НАЗАД", callback_data="back")]
    ])

# ==================== ОБРАБОТЧИКИ ====================
@dp.message(Command("start"))
async def start(m):
    await m.answer("🎬 EDIT SHOP\n\nВыберите действие:", reply_markup=menu())

@dp.callback_query(F.data == "back")
async def back(call):
    await call.message.edit_text("🎬 EDIT SHOP\n\nВыберите действие:", reply_markup=menu())
    await call.answer()

@dp.callback_query(F.data == "about")
async def about(call):
    await call.message.edit_text(
        "Лёгкий – 25★\nСредний – 50★\nСложный – 75★\n\nПо вопросам: @notorepa",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀ НАЗАД", callback_data="back")]])
    )
    await call.answer()

@dp.callback_query(F.data == "order")
async def order(call):
    await call.message.edit_text("Выберите сложность:", reply_markup=plans())
    await call.answer()

@dp.callback_query(F.data.startswith("plan_"))
async def pay(call):
    plan = call.data.split("_")[1]
    amount = PRICES[plan]
    name = {"easy": "Лёгкий эдит", "medium": "Средний эдит", "hard": "Сложный эдит"}[plan]
    
    await bot.send_invoice(
        chat_id=call.message.chat.id,
        title=name,
        description=f"Покупка {name.lower()}",
        payload=f"edit_{plan}_{call.from_user.id}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=name, amount=amount)],
        start_parameter="edit_shop"
    )
    await call.answer()

@dp.pre_checkout_query()
async def pre_checkout(pre):
    await pre.answer(ok=True)

@dp.message(types.ContentType.SUCCESSFUL_PAYMENT)
async def paid(m):
    payment = m.successful_payment
    payload = payment.invoice_payload
    try:
        _, plan_type, _ = payload.split("_")
    except:
        plan_type = "unknown"
    
    amount = payment.total_amount
    save_purchase(m.from_user.id, plan_type, amount)
    
    await m.answer(
        f"✅ *Оплачено!*\n\n"
        f"🎬 Вы приобрели {plan_type.upper()} эдит за {amount} ★\n\n"
        f"📞 Контакт: {SUPPORT_CONTACT}\n"
        f"Напишите @notorepa для получения эдита.",
        parse_mode="Markdown"
    )
    
    await bot.send_message(
        ADMIN_ID,
        f"🛒 *Новая покупка!*\n"
        f"👤 {m.from_user.id} (@{m.from_user.username})\n"
        f"🎬 {plan_type.upper()} эдит\n"
        f"💰 {amount} ★",
        parse_mode="Markdown"
    )

# ==================== ЗАПУСК ====================
async def main():
    Thread(target=run_flask, daemon=True).start()
    asyncio.create_task(self_pinger())
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Бот магазина эдитов запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
