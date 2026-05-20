#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

load_dotenv()

# ==================== КОНФИГУРАЦИЯ ====================
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не задан в переменных окружения")

ADMIN_ID = 8793207271
SUPPORT_CONTACT = "@notorepa"

PRICES = {
    "easy": 25,
    "medium": 50,
    "hard": 75
}

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ==================== КЛАВИАТУРЫ ====================
def main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 ЗАКАЗАТЬ ЭДИТ", callback_data="order")],
        [InlineKeyboardButton(text="ℹ️ О МАГАЗИНЕ", callback_data="about")]
    ])

def plans_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✨ ЛЁГКИЙ (25 ★)", callback_data="plan_easy")],
        [InlineKeyboardButton(text="⚡ СРЕДНИЙ (50 ★)", callback_data="plan_medium")],
        [InlineKeyboardButton(text="🔥 СЛОЖНЫЙ (75 ★)", callback_data="plan_hard")],
        [InlineKeyboardButton(text="◀ НАЗАД", callback_data="back_to_main")]
    ])

# ==================== ОБРАБОТЧИКИ ====================
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "🎬 *EDIT SHOP*\n\n"
        "Выберите действие:",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )

@dp.callback_query(F.data == "back_to_main")
async def back_to_main(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "🎬 *EDIT SHOP*\n\nВыберите действие:",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )
    await callback.answer()

@dp.callback_query(F.data == "about")
async def about_shop(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "ℹ️ *О магазине*\n\n"
        "• Лёгкий эдит – 25 ★\n"
        "• Средний эдит – 50 ★\n"
        "• Сложный эдит – 75 ★\n\n"
        "По вопросам: @notorepa",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀ НАЗАД", callback_data="back_to_main")]
        ])
    )
    await callback.answer()

@dp.callback_query(F.data == "order")
async def order_start(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "🎬 *Выберите сложность:*",
        parse_mode="Markdown",
        reply_markup=plans_keyboard()
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("plan_"))
async def plan_chosen(callback: types.CallbackQuery):
    plan_type = callback.data.split("_")[1]
    amount = PRICES[plan_type]
    plan_names = {
        "easy": "Лёгкий эдит",
        "medium": "Средний эдит",
        "hard": "Сложный эдит"
    }
    plan_title = plan_names[plan_type]

    await bot.send_invoice(
        chat_id=callback.message.chat.id,
        title=f"{plan_title}",
        description=f"Покупка {plan_title.lower()}",
        payload=f"edit_{plan_type}_{callback.from_user.id}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=plan_title, amount=amount)],
        start_parameter="edit_shop"
    )
    await callback.answer()

@dp.pre_checkout_query()
async def pre_checkout_handler(pre_checkout: types.PreCheckoutQuery):
    await pre_checkout.answer(ok=True)

@dp.message(types.ContentType.SUCCESSFUL_PAYMENT)
async def successful_payment(message: types.Message):
    payment = message.successful_payment
    payload = payment.invoice_payload
    try:
        _, plan_type, _ = payload.split("_")
    except:
        plan_type = "unknown"

    amount = payment.total_amount

    await message.answer(
        f"✅ *Оплачено!*\n\n"
        f"🎬 Вы приобрели *{plan_type.upper()}* эдит за {amount} ★\n\n"
        f"📞 *Контакт для получения:*\n{SUPPORT_CONTACT}\n\n"
        f"👉 Напишите @notorepa для получения эдита.\n\n"
        f"Спасибо за покупку! 🎉",
        parse_mode="Markdown"
    )

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
