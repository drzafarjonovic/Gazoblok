import asyncio
import os
from aiogram import Bot, Dispatcher, BaseMiddleware
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, TelegramObject
from aiogram.filters import CommandStart
from dotenv import load_dotenv
from typing import Callable, Dict, Any, Awaitable
import database as db
from handlers import settings, production, sales, warehouse, reports, finished_goods, users

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()

# ── Rol bo'yicha menyular ──
def get_menu(rol):
    if rol == "superadmin":
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🏭 Ishlab chiqarish")],
                [KeyboardButton(text="💰 Sotuv")],
                [KeyboardButton(text="🏪 Ombor")],
                [KeyboardButton(text="🏬 Tayyor mahsulot")],
                [KeyboardButton(text="📊 Hisobot")],
                [KeyboardButton(text="⚙️ Sozlamalar")],
                [KeyboardButton(text="👥 Foydalanuvchilar")],
            ],
            resize_keyboard=True
        )
    elif rol == "direktor":
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🏪 Ombor")],
                [KeyboardButton(text="🏬 Tayyor mahsulot")],
                [KeyboardButton(text="📊 Hisobot")],
            ],
            resize_keyboard=True
        )
    elif rol == "omborchi":
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🏪 Ombor")],
                [KeyboardButton(text="🏬 Tayyor mahsulot")],
                [KeyboardButton(text="📊 Hisobot")],
            ],
            resize_keyboard=True
        )
    elif rol == "ishchi":
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🏭 Ishlab chiqarish")],
                [KeyboardButton(text="🏪 Ombor")],
            ],
            resize_keyboard=True
        )
    elif rol == "sotuvchi":
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="💰 Sotuv")],
                [KeyboardButton(text="🏬 Tayyor mahsulot")],
            ],
            resize_keyboard=True
        )
    elif rol == "hisobchi":
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="📊 Hisobot")],
                [KeyboardButton(text="🏪 Ombor")],
                [KeyboardButton(text="🏬 Tayyor mahsulot")],
            ],
            resize_keyboard=True
        )
    else:
        return ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="🏠 Asosiy menyu")]],
            resize_keyboard=True
        )

# ── Middleware — Rol tekshiruvi ──
class RolMiddleware(BaseMiddleware):
    # Bu bo'limlarga kirish uchun rol tekshiriladi
    ROL_HUQUQLAR = {
        "🏭 Ishlab chiqarish": ["superadmin", "ishchi"],
        "🏭 Ishlab chiqarishni kiritish": ["superadmin", "ishchi"],
        "📋 Bugungi ishlab chiqarish": ["superadmin", "ishchi", "direktor"],
        "💰 Sotuv": ["superadmin", "sotuvchi"],
        "💰 Sotuv kiritish": ["superadmin", "sotuvchi"],
        "📋 Bugungi sotuv": ["superadmin", "sotuvchi", "direktor"],
        "🏪 Ombor": ["superadmin", "omborchi", "ishchi", "direktor", "hisobchi"],
        "📥 Xom ashyo kirim": ["superadmin", "omborchi"],
        "🏪 Joriy qoldiqlar": ["superadmin", "omborchi", "direktor", "hisobchi", "ishchi"],
        "🏬 Tayyor mahsulot": ["superadmin", "omborchi", "sotuvchi", "direktor", "hisobchi"],
        "📊 Hisobot": ["superadmin", "direktor", "hisobchi"],
        "📊 Kunlik hisobot": ["superadmin", "direktor", "hisobchi"],
        "📊 Haftalik hisobot": ["superadmin", "direktor", "hisobchi"],
        "📊 Oylik hisobot": ["superadmin", "direktor", "hisobchi"],
        "📥 Excel hisobot": ["superadmin", "direktor", "hisobchi"],
        "⚙️ Sozlamalar": ["superadmin"],
        "👥 Foydalanuvchilar": ["superadmin"],
    }

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        if not isinstance(event, Message):
            return await handler(event, data)

        # /start buyrug'i har doim o'tadi
        if event.text and event.text.startswith("/start"):
            return await handler(event, data)

        user = await db.get_user(event.from_user.id)

        # Ro'yxatdan o'tmagan
        if not user:
            await event.answer(
                "⛔ Siz ro'yxatdan o'tmagansiz!\n\n"
                "Admindan ruxsat so'rang.\n"
                f"Sizning ID: <code>{event.from_user.id}</code>",
                parse_mode="HTML"
            )
            return

        # Faol emas
        if not user["faol"]:
            await event.answer("⛔ Sizning hisobingiz bloklangan. Adminга murojaat qiling.")
            return

        # Huquq tekshiruvi
        if event.text in self.ROL_HUQUQLAR:
            ruxsat_rollar = self.ROL_HUQUQLAR[event.text]
            if user["rol"] not in ruxsat_rollar:
                await event.answer("⛔ Sizda bu bo'limga kirish huquqi yo'q!")
                return

        return await handler(event, data)

# ── Routerlarni ulash ──
dp.message.middleware(RolMiddleware())
dp.include_router(users.router)
dp.include_router(settings.router)
dp.include_router(production.router)
dp.include_router(sales.router)
dp.include_router(warehouse.router)
dp.include_router(reports.router)
dp.include_router(finished_goods.router)

# ── /start ──
@dp.message(CommandStart())
async def start(message: Message):
    user_id = message.from_user.id
    ism = message.from_user.full_name
    username = message.from_user.username

    # Birinchi superadmin
    superadmin_bor = await db.superadmin_bormi()
    if not superadmin_bor:
        await db.add_user(user_id, ism, username, "superadmin")
        await db.set_bot_setting("admin_chat_id", str(user_id))
        await message.answer(
            f"👑 Siz Super Admin sifatida ro'yxatdan o'tdingiz!\n\n"
            f"🧱 GazoBot — Gazoblok ishlab chiqarish boshqaruvi",
            reply_markup=get_menu("superadmin")
        )
        return

    user = await db.get_user(user_id)
    if not user:
        # Superadminga xabar
        admin_id = await db.get_bot_setting("admin_chat_id")
        if admin_id:
            try:
                await bot.send_message(
                    int(admin_id),
                    f"🔔 Yangi foydalanuvchi kirmoqchi:\n"
                    f"👤 Ism: {ism}\n"
                    f"🆔 ID: <code>{user_id}</code>\n"
                    f"@{username or 'username yoq'}\n\n"
                    f"👥 Foydalanuvchilar → ➕ Foydalanuvchi qo'shish",
                    parse_mode="HTML"
                )
            except Exception:
                pass
        await message.answer(
            f"⛔ Siz ro'yxatdan o'tmagansiz!\n\n"
            f"Admin sizni tizimga qo'shishini kuting.\n"
            f"Sizning ID: <code>{user_id}</code>",
            parse_mode="HTML"
        )
        return

    await message.answer(
        f"Salom, {ism}! 👋\n"
        f"Rol: {db.ROLLAR.get(user['rol'], user['rol'])}",
        reply_markup=get_menu(user["rol"])
    )

# ── Asosiy menyu ──
@dp.message(lambda m: m.text == "🏠 Asosiy menyu")
async def asosiy(message: Message):
    user = await db.get_user(message.from_user.id)
    if user:
        await message.answer(
            "🏠 Asosiy menyu:",
            reply_markup=get_menu(user["rol"])
        )

# ── Avtomatik hisobot scheduler ──
async def hisobot_scheduler():
    while True:
        try:
            from datetime import datetime
            vaqt = await db.get_bot_setting("hisobot_vaqti")
            if vaqt:
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
    asyncio.create_task(hisobot_scheduler())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
