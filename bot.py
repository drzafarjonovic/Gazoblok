import asyncio
import os
import sys  # Tizimdan chiqib ketish uchun qo'shildi
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode  # ixtiyoriy, lekin foydali
from aiogram.client.default import DefaultBotProperties
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart
from dotenv import load_dotenv
import database as db
from handlers import settings, production, sales, warehouse, reports

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

# --- XATOLIKNI ANIQLASH UCHUN TEKSHIRUV ---
if not TOKEN:
    print("XATO: BOT_TOKEN muhitdan o'qilmadi! Railway Variables qismini tekshiring.")
    sys.exit(1)
else:
    # Token uzunligini tekshirish (Telegram tokenlari odatda 43-46 belgidan uzun bo'ladi)
    print(f"Token muvaffaqiyatli o'qildi. Uzunligi: {len(TOKEN)} ta belgi.")
# ------------------------------------------

# aiogram 3.x uchun eng to'g'ri va xavfsiz ob'ekt olish usuli:
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# Routerlar
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
    # Keraksiz eski update'larni o'chirib yuborish (Polling barqaror ishlashi uchun)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
    
