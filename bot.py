import asyncio
import os
from aiogram import Bot, Dispatcher, BaseMiddleware, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, TelegramObject, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import CommandStart
from dotenv import load_dotenv
from typing import Callable, Dict, Any, Awaitable
import database as db
from translation import t, TIL_NOMLARI, TILLAR
from handlers import (settings, production, sales, warehouse,
                      reports, finished_goods, users, permissions, inventory)

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Til tanlash klaviaturasi
def til_tanlash_keyboard():
    """Til tanlash uchun InlineKeyboard"""
    keyboard = []
    row = []
    for i, (til_kod, til_nomi) in enumerate(TIL_NOMLARI.items()):
        row.append(InlineKeyboardButton(text=til_nomi, callback_data=f"til_{til_kod}"))
        if len(row) == 2:  # 2 ta tugma bir qatorda
            keyboard.append(row)
            row = []
    if row:  # Oxirgi qator
        keyboard.append(row)
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# Permission → tugma matni
PERMISSION_TUGMALAR = {
    "ishlab_chiqarish_kiritish": "🏭 Ishlab chiqarish",
    "ishlab_chiqarish_korish": "🏭 Ishlab chiqarish",
    "sotuv_kiritish": "💰 Sotuv",
    "sotuv_korish": "💰 Sotuv",
    "ombor_kiritish": "🏪 Ombor",
    "ombor_korish": "🏪 Ombor",
    "tayyor_mahsulot_korish": "🏬 Tayyor mahsulot",
    "tayyor_mahsulot_tahrirlash": "🏬 Tayyor mahsulot",
    "hisobot_korish": "📊 Hisobot",
    "excel_hisobot": "📊 Hisobot",
}

async def get_menu(user_id, rol):
    """Dinamik menyu — foydalanuvchi permissionlariga qarab"""
    if rol == "superadmin":
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🏭 Ishlab chiqarish")],
                [KeyboardButton(text="💰 Sotuv")],
                [KeyboardButton(text="🏪 Ombor")],
                [KeyboardButton(text="🏬 Tayyor mahsulot")],
                [KeyboardButton(text="📊 Hisobot")],
                [KeyboardButton(text="📋 Inventarizatsiya")],
                [KeyboardButton(text="⚙️ Sozlamalar")],
                [KeyboardButton(text="👥 Foydalanuvchilar")],
            ],
            resize_keyboard=True
        )

    perms = await db.get_user_permissions(user_id, rol)
    tugmalar = set()

    if perms.get("ishlab_chiqarish_kiritish") or perms.get("ishlab_chiqarish_korish"):
        tugmalar.add("🏭 Ishlab chiqarish")
    if perms.get("sotuv_kiritish") or perms.get("sotuv_korish"):
        tugmalar.add("💰 Sotuv")
    if perms.get("ombor_kiritish") or perms.get("ombor_korish"):
        tugmalar.add("🏪 Ombor")
    if perms.get("tayyor_mahsulot_korish") or perms.get("tayyor_mahsulot_tahrirlash"):
        tugmalar.add("🏬 Tayyor mahsulot")
    if perms.get("hisobot_korish") or perms.get("excel_hisobot"):
        tugmalar.add("📊 Hisobot")
    if perms.get("tayyor_mahsulot_tahrirlash"):
        tugmalar.add("📋 Inventarizatsiya")

    keyboard = [[KeyboardButton(text=t)] for t in sorted(tugmalar)]
    if not keyboard:
        keyboard = [[KeyboardButton(text="🏠 Asosiy menyu")]]

    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

# ── Middleware ──
class PermissionMiddleware(BaseMiddleware):
    # Tugma → kerakli permission
    TUGMA_PERMISSION = {
        "🏭 Ishlab chiqarishni kiritish": "ishlab_chiqarish_kiritish",
        "📋 Bugungi ishlab chiqarish": "ishlab_chiqarish_korish",
        "🗑️ Oxirgi yozuvni o'chirish": "ishlab_chiqarish_kiritish",
        "💰 Sotuv kiritish": "sotuv_kiritish",
        "📋 Bugungi sotuv": "sotuv_korish",
        "🗑️ Oxirgi sotuvni o'chirish": "sotuv_kiritish",
        "📥 Xom ashyo kirim": "ombor_kiritish",
        "🏪 Joriy qoldiqlar": "ombor_korish",
        "📦 Tayyor mahsulot qoldig'i": "tayyor_mahsulot_korish",
        "✏️ Dastlabki qoldiqni kiritish": "tayyor_mahsulot_tahrirlash",
        "📊 Kunlik hisobot": "hisobot_korish",
        "📊 Haftalik hisobot": "hisobot_korish",
        "📊 Oylik hisobot": "hisobot_korish",
        "📥 Excel hisobot": "excel_hisobot",
        "📋 Inventarizatsiya": "tayyor_mahsulot_tahrirlash",
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
            await event.answer("⛔ Sizning hisobingiz bloklangan!")
            return

        # Superadmin hamma narsaga kirishi mumkin
        if user["rol"] == "superadmin":
            data["user"] = user
            return await handler(event, data)

        # Permission tekshiruvi
        if event.text in self.TUGMA_PERMISSION:
            kerakli_perm = self.TUGMA_PERMISSION[event.text]
            ruxsat = await db.has_permission(event.from_user.id, user["rol"], kerakli_perm)
            if not ruxsat:
                await event.answer(
                    f"⛔ Sizda bu bo'limga kirish huquqi yo'q!\n"
                    f"Rol: {db.ROLLAR.get(user['rol'], user['rol'])}"
                )
                return

        data["user"] = user
        return await handler(event, data)

# ── Routerlar ──
dp.message.middleware(PermissionMiddleware())
dp.include_router(users.router)
dp.include_router(permissions.router)
dp.include_router(inventory.router)
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

    # 1. Birinchi superadmin
    superadmin_bor = await db.superadmin_bormi()
    if not superadmin_bor:
        # Til tanlash
        await message.answer(
            "🌐 Tilni tanlang / Choose your language:",
            reply_markup=til_tanlash_keyboard()
        )
        # user_id ni state ga saqlaymiz (keyingi callback uchun)
        return

    # 2. Mavjud user
    user = await db.get_user(user_id)
    
    # 3. Yangi user (admin tomonidan qo'shilmagan)
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

    # 4. Bloklangan user
    if not user["faol"]:
        await message.answer("⛔ Sizning hisobingiz bloklangan!")
        return

    # 5. Til tanlanmaganmi? (mavjud userlar uchun)
    if not user.get("til"):
        await message.answer(
            "🌐 Tilni tanlang / Choose your language:",
            reply_markup=til_tanlash_keyboard()
        )
        return

    # 6. Oddiy /start (til tanlangan, faol user)
    menu = await get_menu(user_id, user["rol"])
    rol_nomi = db.ROLLAR.get(user["rol"], user["rol"])
    xabar = await t(f"Salom, {ism}! 👋\nRol: {rol_nomi}", user_id)
    await message.answer(xabar, reply_markup=menu)

# ── Til tanlash callback ──
@dp.callback_query(lambda c: c.data.startswith("til_"))
async def til_tanlash_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    ism = callback.from_user.full_name
    username = callback.from_user.username
    
    # til_uz → uz, til_zh-CN → zh-CN
    til_kod = callback.data.split("_", 1)[1]
    
    # Superadmin yaratish (agar birinchi user bo'lsa)
    superadmin_bor = await db.superadmin_bormi()
    if not superadmin_bor:
        await db.add_user(user_id, ism, username, "superadmin")
        await db.update_user_til(user_id, til_kod)
        await db.set_bot_setting("admin_chat_id", str(user_id))
        menu = await get_menu(user_id, "superadmin")
        xabar = await t(
            f"👑 Salom, {ism}!\n"
            f"Siz Super Admin sifatida ro'yxatdan o'tdingiz!\n\n"
            f"🧱 GazoBot — Gazoblok ishlab chiqarish boshqaruvi",
            user_id
        )
        await callback.message.edit_text(xabar)
        await callback.message.answer("Menu:", reply_markup=menu)
        await callback.answer()
        return
    
    # Mavjud user uchun tilni saqlash
    await db.update_user_til(user_id, til_kod)
    
    # Tasdiqlash xabari (tanlangan tilda)
    xabar_tasdiqlash = await t("✅ Til o'zgartirildi!", user_id)
    
    user = await db.get_user(user_id)
    if user and user["faol"]:
        menu = await get_menu(user_id, user["rol"])
        rol_nomi = db.ROLLAR.get(user["rol"], user["rol"])
        xabar = await t(f"Salom, {ism}! 👋\nRol: {rol_nomi}", user_id)
        await callback.message.edit_text(xabar_tasdiqlash)
        await callback.message.answer(xabar, reply_markup=menu)
    else:
        await callback.message.edit_text(xabar_tasdiqlash)
    
    await callback.answer()

# ── Asosiy menyu ──
@dp.message(lambda m: m.text == "🏠 Asosiy menyu")
async def asosiy(message: Message):
    user = await db.get_user(message.from_user.id)
    if user and user["faol"]:
        menu = await get_menu(message.from_user.id, user["rol"])
        await message.answer("🏠 Asosiy menyu:", reply_markup=menu)

# ── Scheduler ──
async def hisobot_scheduler():
    last_sent_minute = -1
    while True:
        try:
            # GMT+5 (Toshkent) vaqtini ishlatamiz
            hozir = db.hozirgi_vaqt()
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
