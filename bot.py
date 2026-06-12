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
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🏠 Asosiy menyu")]],
        resize_keyboard=True
    )

# ── Middleware ──
class RolMiddleware(BaseMiddleware):
    ROL_HUQUQLAR = {
        "🏭 Ishlab chiqarish": ["superadmin", "ishchi"],
        "🏭 Ishlab chiqarishni kiritish": ["superadmin", "ishchi"],
        "📋 Bugungi ishlab chiqarish": ["superadmin", "ishchi", "direktor"],
        "🗑️ Oxirgi yozuvni o'chirish": ["superadmin"],
        "💰 Sotuv": ["superadmin", "sotuvchi"],
        "💰 Sotuv kiritish": ["superadmin", "sotuvchi"],
        "📋 Bugungi sotuv": ["superadmin", "sotuvchi", "direktor"],
        "🗑️ Oxirgi sotuvni o'chirish": ["superadmin"],
        "🏪 Ombor": ["superadmin", "omborchi", "ishchi", "direktor", "hisobchi"],
        "📥 Xom ashyo kirim": ["superadmin", "omborchi"],
        "🏪 Joriy qoldiqlar": ["superadmin", "omborchi", "direktor", "hisobchi", "ishchi"],
        "🏬 Tayyor mahsulot": ["superadmin", "omborchi", "sotuvchi", "direktor", "hisobchi"],
        "📦 Tayyor mahsulot qoldig'i": ["superadmin", "omborchi", "sotuvchi", "direktor", "hisobchi"],
        "✏️ Dastlabki qoldiqni kiritish": ["superadmin", "omborchi"],
        "📊 Hisobot": ["superadmin", "direktor", "hisobchi"],
        "📊 Kunlik hisobot": ["superadmin", "direktor", "hisobchi"],
        "📊 Haftalik hisobot": ["superadmin", "direktor", "hisobchi"],
        "📊 Oylik hisobot": ["superadmin", "direktor", "hisobchi"],
        "📥 Excel hisobot": ["superadmin", "direktor", "hisobchi"],
        "⚙️ Sozlamalar": ["superadmin"],
        "👥 Foydalanuvchilar": ["superadmin"],
        "👥 Foydalanuvchilar ro'yxati": ["superadmin"],
        "➕ Foydalanuvchi qo'shish": ["superadmin"],
        "✏️ Rol o'zgartirish": ["superadmin"],
        "🗑️ Foydalanuvchini o'chirish": ["superadmin"],
        "📋 Audit log": ["superadmin"],
    }

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        if not isinstance(event, Message):
            return await handler(event, data)

        if event.text and event.text.startswith("/start"):
            return await handler(event, data)

        user = await db.get_user(event.from_user.id)

        if not user:
            await event.answer(
                "⛔ Siz ro'yxatdan o'tmagansiz!\n\n"
                "Admindan ruxsat so'rang.\n"
                f"Sizning ID: <code>{event.from_user.id}</code>",
                parse_mode="HTML"
            )
            return

        if not user["faol"]:
            await event.answer(
                "⛔ Sizning hisobingiz bloklangan!\n"
                "Adminга murojaat qiling."
            )
            return

        if event.text in self.ROL_HUQUQLAR:
            ruxsat_rollar = self.ROL_HUQUQLAR[event.text]
            if user["rol"] not in ruxsat_rollar:
                await event.answer(
                    "⛔ Sizda bu bo'limga kirish huquqi yo'q!\n"
                    f"Sizning rol: {db.ROLLAR.get(user['rol'], user['rol'])}"
                )
                return

        # User ma'lumotini data ga qo'shamiz
        data["user"] = user
        return await handler(event, data)

# ── Routerlar ──
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

    superadmin_bor = await db.superadmin_bormi()
    if not superadmin_bor:
        await db.add_user(user_id, ism, username, "superadmin")
        await db.set_bot_setting("admin_chat_id", str(user_id))
        await message.answer(
            f"👑 Salom, {ism}!\n"
            f"Siz Super Admin sifatida ro'yxatdan o'tdingiz!\n\n"
            f"🧱 GazoBot — Gazoblok ishlab chiqarish boshqaruvi",
            reply_markup=get_menu("superadmin")
        )
        return

    user = await db.get_user(user_id)
    if not user:
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
            f"⛔ Salom, {ism}!\n\n"
            f"Siz hali ro'yxatdan o'tmagansiz.\n"
            f"Admin sizni tizimga qo'shishini kuting.\n\n"
            f"Sizning ID: <code>{user_id}</code>",
            parse_mode="HTML"
        )
        return

    if not user["faol"]:
        await message.answer("⛔ Sizning hisobingiz bloklangan. Adminга murojaat qiling.")
        return

    rol_nomi = db.ROLLAR.get(user["rol"], user["rol"])
    await message.answer(
        f"Salom, {ism}! 👋\n"
        f"Rol: {rol_nomi}\n\n"
        f"Quyidagi bo'limlardan birini tanlang:",
        reply_markup=get_menu(user["rol"])
    )

# ── Asosiy menyu ──
@dp.message(lambda m: m.text == "🏠 Asosiy menyu")
async def asosiy(message: Message):
    user = await db.get_user(message.from_user.id)
    if user and user["faol"]:
        await message.answer(
            "🏠 Asosiy menyu:",
            reply_markup=get_menu(user["rol"])
        )

# ── Avtomatik hisobot scheduler ──
async def hisobot_scheduler():
    last_sent_minute = -1
    while True:
        try:
            from datetime import datetime
            hozir = datetime.now()
            vaqt = await db.get_bot_setting("hisobot_vaqti")
            if vaqt:
                parts = vaqt.split(":")
                soat = int(parts[0])
                daqiqa = int(parts[1])
                joriy_minut = hozir.hour * 60 + hozir.minute
                kerakli_minut = soat * 60 + daqiqa
                if joriy_minut == kerakli_minut and last_sent_minute != joriy_minut:
                    chat_id = await db.get_bot_setting("admin_chat_id")
                    if chat_id:
                        await reports.avtomatik_hisobot(bot, int(chat_id))
                    last_sent_minute = joriy_minut
        except Exception as e:
            print(f"Scheduler xato: {e}")
        await asyncio.sleep(30)

async def main():
    await db.init_db()
    asyncio.create_task(hisobot_scheduler())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
