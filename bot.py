import asyncio
import os
from aiogram import Bot, Dispatcher
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart
from dotenv import load_dotenv
import database as db
from handlers import settings, production, sales, warehouse, reports, finished_goods

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()

dp.include_router(settings.router)
dp.include_router(production.router)
dp.include_router(sales.router)
dp.include_router(warehouse.router)
dp.include_router(reports.router)
dp.include_router(finished_goods.router)

def asosiy_menyu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏭 Ishlab chiqarish")],
            [KeyboardButton(text="💰 Sotuv")],
            [KeyboardButton(text="🏪 Ombor")],
            [KeyboardButton(text="🏬 Tayyor mahsulot")],
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

# ── Avtomatik hisobot scheduler ──
async def hisobot_scheduler():
    while True:
        try:
            vaqt = await db.get_bot_setting("hisobot_vaqti")
            if vaqt:
                from datetime import datetime
                hozir = datetime.now()
                parts = vaqt.split(":")
                soat = int(parts[0])
                daqiqa = int(parts[1])
                if hozir.hour == soat and hozir.minute == daqiqa:
                    chat_id = await db.get_bot_setting("admin_chat_id")
                    if chat_id:
                        await reports.avtomatik_hisobot(bot, int(chat_id))
        except Exception:
            pass
        await asyncio.sleep(60)

async def main():
    await db.init_db()

    # Admin chat_id ni saqlash
    @dp.message(CommandStart())
    async def start_with_id(message: Message):
        await db.set_bot_setting("admin_chat_id", str(message.from_user.id))
        await message.answer(
            f"Salom! 👋\n\n"
            f"🧱 GazoBot — Gazoblok ishlab chiqarish boshqaruvi\n\n"
            f"Quyidagi bo'limlardan birini tanlang:",
            reply_markup=asosiy_menyu()
        )

    asyncio.create_task(hisobot_scheduler())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
