import asyncio
import os
from aiogram import Bot, Dispatcher
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart
from dotenv import load_dotenv
import database as db
from handlers import settings, production, sales, warehouse, reports

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()

dp.include_router(settings.router)
dp.include_router(production.router)
dp.include_router(sales.router)
dp.include_router(warehouse.router)
dp.include_router(reports.router)

def asosiy_menyu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏭 Ishlab chiqarish")],
            [KeyboardButton(text="💰 Sotuv")],
            [KeyboardButton(text="🏪 Ombor")],
            [KeyboardButton(text="📊 Hisobot")],
            [KeyboardButton(text="⚙️ Sozlamalar")],
        ],
        resize_keyboard=True
    )

@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        f"Salom! 👋\n\n"
        f"🧱 GazoBot — Gazoblok ishlab chiqarish boshqaruvi\n\n"
        f"Quyidagi bo'limlardan birini tanlang:",
        reply_markup=asosiy_menyu()
    )

@dp.message(lambda m: m.text == "🏠 Asosiy menyu")
async def asosiy(message: Message):
    await message.answer(
        "🏠 Asosiy menyu:",
        reply_markup=asosiy_menyu()
    )

async def main():
    await db.init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
