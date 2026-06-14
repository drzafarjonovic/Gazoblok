import asyncio
import os
from aiogram import Bot, Dispatcher, BaseMiddleware
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, TelegramObject
from aiogram.filters import CommandStart
from dotenv import load_dotenv
from typing import Callable, Dict, Any, Awaitable
import database as db
from handlers import (settings, production, sales, warehouse,
                      reports, finished_goods, users, permissions, inventory)

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()

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

    superadmin_bor = await db.superadmin_bormi()
    if not superadmin_bor:
        await db.add_user(user_id, ism, username, "superadmin")
        await db.set_bot_setting("admin_chat_id", str(user_id))
        menu = await get_menu(user_id, "superadmin")
        await message.answer(
            f"👑 Salom, {ism}!\n"
            f"Siz Super Admin sifatida ro'yxatdan o'tdingiz!\n\n"
            f"🧱 GazoBot — Gazoblok ishlab chiqarish boshqaruvi",
            reply_markup=menu
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
        await message.answer("⛔ Sizning hisobingiz bloklangan!")
        return

    menu = await get_menu(user_id, user["rol"])
    rol_nomi = db.ROLLAR.get(user["rol"], user["rol"])
    await message.answer(
        f"Salom, {ism}! 👋\n"
        f"Rol: {rol_nomi}",
        reply_markup=menu
    )

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


========================================
FAYL: handlers/production.py
Mavjud faylni o'chirib, quyidagini yozing
========================================

from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import date
import database as db

router = Router()

class ProductionState(StatesGroup):
    shablon1 = State()
    shablon2 = State()
    shablon3 = State()

def production_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏭 Ishlab chiqarishni kiritish")],
            [KeyboardButton(text="📋 Bugungi ishlab chiqarish")],
            [KeyboardButton(text="🗑️ Oxirgi yozuvni o'chirish")],
            [KeyboardButton(text="🏠 Asosiy menyu")],
        ],
        resize_keyboard=True
    )

@router.message(F.text == "🏭 Ishlab chiqarish")
async def production(message: Message):
    await message.answer("🏭 Ishlab chiqarish bo'limi:", reply_markup=production_menu())

@router.message(F.text == "🏭 Ishlab chiqarishni kiritish")
async def production_kiritish(message: Message, state: FSMContext):
    formula = await db.get_qolip_formula()
    if not formula:
        await message.answer(
            "❌ Avval qolip formulasini kiriting!\n"
            "⚙️ Sozlamalar → 📋 Qolip formulasi"
        )
        return
    await state.set_state(ProductionState.shablon1)
    await message.answer(
        "📦 Shablon 1 (faqat A: 12 ta/qolip)\n"
        "Nechta qolip quyildi?\n"
        "Agar yo'q bo'lsa: 0"
    )

@router.message(ProductionState.shablon1)
async def shablon1_kiritish(message: Message, state: FSMContext):
    try:
        soni = int(message.text.strip())
        if soni < 0:
            raise ValueError
        await state.update_data(shablon1=soni)
        await state.set_state(ProductionState.shablon2)
        await message.answer(
            "📦 Shablon 2 (faqat B: 24 ta/qolip)\n"
            "Nechta qolip quyildi?\n"
            "Agar yo'q bo'lsa: 0"
        )
    except ValueError:
        await message.answer("❌ Faqat musbat son kiriting! Misol: 5")

@router.message(ProductionState.shablon2)
async def shablon2_kiritish(message: Message, state: FSMContext):
    try:
        soni = int(message.text.strip())
        if soni < 0:
            raise ValueError
        await state.update_data(shablon2=soni)
        await state.set_state(ProductionState.shablon3)
        await message.answer(
            "📦 Shablon 3 (aralash: 11A + 2B/qolip)\n"
            "Nechta qolip quyildi?\n"
            "Agar yo'q bo'lsa: 0"
        )
    except ValueError:
        await message.answer("❌ Faqat musbat son kiriting! Misol: 3")

@router.message(ProductionState.shablon3)
async def shablon3_kiritish(message: Message, state: FSMContext):
    try:
        soni = int(message.text.strip())
        if soni < 0:
            raise ValueError

        data = await state.get_data()
        s1 = data.get("shablon1", 0)
        s2 = data.get("shablon2", 0)
        s3 = soni
        jami_qolip = s1 + s2 + s3

        if jami_qolip == 0:
            await state.clear()
            await message.answer("❌ Hech qolip kiritilmadi!", reply_markup=production_menu())
            return

        # Material tekshiruvi
        yetishmaydi = await db.check_material_yetarli(jami_qolip)
        if yetishmaydi:
            await state.clear()
            text = "⛔ Ishlab chiqarish mumkin emas!\nMateriallar yetarli emas:\n\n"
            text += "\n".join(yetishmaydi)
            await message.answer(text, reply_markup=production_menu())
            return

        A_blok = s1 * 12 + s3 * 11
        B_blok = s2 * 24 + s3 * 2
        bugun = str(date.today())
        user_id = message.from_user.id

        # Bazaga yozish va ID larini olish
        prod_ids = []
        if s1 > 0:
            pid = await db.add_production_log(bugun, 1, s1, user_id)
            prod_ids.append((pid, 1, s1))
        if s2 > 0:
            pid = await db.add_production_log(bugun, 2, s2, user_id)
            prod_ids.append((pid, 2, s2))
        if s3 > 0:
            pid = await db.add_production_log(bugun, 3, s3, user_id)
            prod_ids.append((pid, 3, s3))

        # Xom ashyoni kamaytirish va chiqim log
        formula = await db.get_qolip_formula()
        ogohlantirish = []
        sarflar = []

        for f in formula:
            nomi = f[0]
            miqdor_asosiy = f[6]
            qoldiq_asosiy = f[3]
            asl_birlik = f[7]
            material_id = f[5]

            ketgan_asosiy = miqdor_asosiy * jami_qolip
            yangi_qoldiq = max(0.0, qoldiq_asosiy - ketgan_asosiy)

            await db.update_material_qoldiq(material_id, yangi_qoldiq)

            # Chiqim logga yozish (har bir production_log uchun)
            for pid, shablon, qolip_soni in prod_ids:
                ketgan_bu_log = miqdor_asosiy * qolip_soni
                await db.add_material_chiqim_log(
                    pid, material_id, nomi,
                    ketgan_bu_log, "kg", bugun
                )

            ketgan_asl = db.asosiydan_birlikga(ketgan_asosiy, asl_birlik)
            qoldiq_asl = db.asosiydan_birlikga(yangi_qoldiq, asl_birlik)
            sarflar.append(
                f"   {nomi}: -{ketgan_asl:.2f} {asl_birlik} "
                f"(qoldi: {qoldiq_asl:.2f} {asl_birlik})"
            )

            all_settings = await db.get_settings()
            for s in all_settings:
                if s[3] == material_id and yangi_qoldiq <= s[1]:
                    min_asl = db.asosiydan_birlikga(s[1], asl_birlik)
                    ogohlantirish.append(
                        f"⚠️ {nomi} kam qoldi!\n"
                        f"   Qoldiq: {qoldiq_asl:.2f} {asl_birlik}\n"
                        f"   Minimum: {min_asl:.2f} {asl_birlik}"
                    )

        # Tayyor mahsulot omboriga qo'shish
        if A_blok > 0:
            await db.update_finished_goods("A", A_blok)
        if B_blok > 0:
            await db.update_finished_goods("B", B_blok)

        # Audit log
        user = await db.get_user(user_id)
        await db.add_audit_log(
            user_id,
            user["ism"] if user else str(user_id),
            user["rol"] if user else "-",
            "Ishlab chiqarish kiritildi",
            f"Qolip: {jami_qolip} ta | A: {A_blok} ta | B: {B_blok} ta"
        )

        await state.clear()

        sarflar_text = "\n".join(sarflar)
        text = (
            f"✅ Ishlab chiqarish kiritildi!\n\n"
            f"📦 Jami qolip: {jami_qolip} ta\n"
            f"   Shablon 1: {s1} | Shablon 2: {s2} | Shablon 3: {s3}\n\n"
            f"🧱 Tayyor bloklar:\n"
            f"   A blok: +{A_blok} ta\n"
            f"   B blok: +{B_blok} ta\n\n"
            f"📉 Sarflangan:\n{sarflar_text}"
        )
        await message.answer(text, reply_markup=production_menu())

        if ogohlantirish:
            await message.answer("\n\n".join(ogohlantirish))

    except ValueError:
        await message.answer("❌ Faqat musbat son kiriting!")
    except Exception as e:
        await state.clear()
        await message.answer(
            f"❌ Xatolik: {str(e)}\nQaytadan urinib ko'ring.",
            reply_markup=production_menu()
        )

@router.message(F.text == "📋 Bugungi ishlab chiqarish")
async def bugungi_production(message: Message):
    bugun = str(date.today())
    logs = await db.get_production_by_date(bugun)
    if not logs:
        await message.answer("📋 Bugun hali ishlab chiqarish kiritilmagan.", reply_markup=production_menu())
        return
    s1 = s2 = s3 = 0
    for log in logs:
        if log[0] == 1: s1 += log[1]
        elif log[0] == 2: s2 += log[1]
        elif log[0] == 3: s3 += log[1]
    jami_qolip = s1 + s2 + s3
    A_blok = s1 * 12 + s3 * 11
    B_blok = s2 * 24 + s3 * 2
    text = (
        f"📋 Bugungi ishlab chiqarish:\n\n"
        f"📦 Jami qolip: {jami_qolip} ta\n"
        f"   Shablon 1: {s1} | Shablon 2: {s2} | Shablon 3: {s3}\n\n"
        f"🧱 Tayyor bloklar:\n"
        f"   A blok: {A_blok} ta\n"
        f"   B blok: {B_blok} ta\n"
    )
    await message.answer(text, reply_markup=production_menu())

@router.message(F.text == "🗑️ Oxirgi yozuvni o'chirish")
async def oxirgi_ochirish(message: Message):
    try:
        user = await db.get_user(message.from_user.id)
        muvaffaqiyat, tafsilot = await db.delete_last_production_with_restore()
        if muvaffaqiyat:
            await db.add_audit_log(
                message.from_user.id,
                user["ism"] if user else str(message.from_user.id),
                user["rol"] if user else "-",
                "Ishlab chiqarish o'chirildi",
                tafsilot
            )
            await message.answer(
                f"✅ Oxirgi yozuv o'chirildi!\n\n{tafsilot}",
                reply_markup=production_menu()
            )
        else:
            await message.answer(tafsilot, reply_markup=production_menu())
    except Exception as e:
        await message.answer(f"❌ Xatolik: {str(e)}", reply_markup=production_menu())


