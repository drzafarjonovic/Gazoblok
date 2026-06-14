from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import date
import database as db

router = Router()

class InventarizatsiyaState(StatesGroup):
    block_type = State()
    real_hisob = State()
    izoh = State()

def inventory_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Inventarizatsiya kiritish")],
            [KeyboardButton(text="📋 Inventarizatsiya tarixi")],
            [KeyboardButton(text="🏠 Asosiy menyu")],
        ],
        resize_keyboard=True
    )

def block_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="A blok")],
            [KeyboardButton(text="B blok")],
            [KeyboardButton(text="🏠 Asosiy menyu")],
        ],
        resize_keyboard=True
    )

@router.message(F.text == "📋 Inventarizatsiya")
async def inventarizatsiya(message: Message):
    await message.answer("📋 Inventarizatsiya:", reply_markup=inventory_menu())

@router.message(F.text == "📊 Inventarizatsiya kiritish")
async def inv_kiritish(message: Message, state: FSMContext):
    await state.clear()
    goods = await db.get_finished_goods()
    text = "📦 Joriy bot hisob:\n\n"
    for g in goods:
        text += f"   {g[0]} blok: {g[1]} ta\n"
    text += "\nQaysi blok uchun inventarizatsiya?"
    await state.set_state(InventarizatsiyaState.block_type)
    await message.answer(text, reply_markup=block_menu())

@router.message(InventarizatsiyaState.block_type)
async def inv_block_type(message: Message, state: FSMContext):
    if message.text not in ["A blok", "B blok"]:
        await message.answer("❌ Tugmalardan birini tanlang!")
        return
    block_type = "A" if message.text == "A blok" else "B"
    goods = await db.get_finished_goods()
    bot_hisob = next((g[1] for g in goods if g[0] == block_type), 0)
    await state.update_data(block_type=block_type, bot_hisob=bot_hisob)
    await state.set_state(InventarizatsiyaState.real_hisob)
    await message.answer(
        f"🧱 {block_type} blok\n"
        f"Bot hisob: {bot_hisob} ta\n\n"
        f"Real (haqiqiy) soni nechta?"
    )

@router.message(InventarizatsiyaState.real_hisob)
async def inv_real_hisob(message: Message, state: FSMContext):
    try:
        real_hisob = int(message.text.strip())
        if real_hisob < 0:
            raise ValueError
        await state.update_data(real_hisob=real_hisob)
        await state.set_state(InventarizatsiyaState.izoh)
        data = await state.get_data()
        farq = real_hisob - data["bot_hisob"]
        farq_text = f"+{farq}" if farq > 0 else str(farq)
        await message.answer(
            f"📊 Farq: {farq_text} ta\n\n"
            f"Izoh kiriting (ixtiyoriy):\n"
            f"Misol: Hisobdan ko'ra kam chiqdi\n"
            f"Yoki: 0 (izohsiz)"
        )
    except ValueError:
        await message.answer("❌ Faqat musbat son kiriting!")

@router.message(InventarizatsiyaState.izoh)
async def inv_izoh(message: Message, state: FSMContext):
    try:
        izoh = message.text.strip()
        if izoh == "0":
            izoh = ""
        data = await state.get_data()
        block_type = data["block_type"]
        bot_hisob = data["bot_hisob"]
        real_hisob = data["real_hisob"]

        farq = await db.add_inventarizatsiya(
            str(date.today()), block_type,
            bot_hisob, real_hisob, izoh,
            message.from_user.id
        )

        user = await db.get_user(message.from_user.id)
        await db.add_audit_log(
            message.from_user.id,
            user["ism"] if user else str(message.from_user.id),
            user["rol"] if user else "-",
            "Inventarizatsiya kiritildi",
            f"{block_type} blok: bot={bot_hisob}, real={real_hisob}, farq={farq}"
        )
        await state.clear()
        farq_text = f"+{farq}" if farq > 0 else str(farq)
        await message.answer(
            f"✅ Inventarizatsiya saqlandi!\n\n"
            f"🧱 {block_type} blok\n"
            f"   Bot hisob: {bot_hisob} ta\n"
            f"   Real hisob: {real_hisob} ta\n"
            f"   Farq: {farq_text} ta\n"
            f"   Bot yangilandi: {real_hisob} ta",
            reply_markup=inventory_menu()
        )
    except Exception as e:
        await state.clear()
        await message.answer(f"❌ Xatolik: {str(e)}", reply_markup=inventory_menu())

@router.message(F.text == "📋 Inventarizatsiya tarixi")
async def inv_tarixi(message: Message):
    try:
        logs = await db.get_inventarizatsiya_tarixi(20)
        if not logs:
            await message.answer("📋 Inventarizatsiya tarixi bo'sh.", reply_markup=inventory_menu())
            return
        text = "📋 Inventarizatsiya tarixi:\n\n"
        for log in logs:
            vaqt = log["vaqt"]
            vaqt_str = vaqt.strftime("%d.%m.%Y") if hasattr(vaqt, "strftime") else str(vaqt)[:10]
            farq = log["farq"]
            farq_text = f"+{farq}" if farq > 0 else str(farq)
            text += (
                f"📅 {vaqt_str} | {log['block_type']} blok\n"
                f"   Bot: {log['bot_hisob']} | Real: {log['real_hisob']} | Farq: {farq_text}\n"
                f"   {log['user_ism'] or 'Noma lum'}\n"
            )
            if log["izoh"]:
                text += f"   📝 {log['izoh']}\n"
            text += "\n"
        if len(text) > 4000:
            text = text[:4000] + "\n..."
        await message.answer(text, reply_markup=inventory_menu())
    except Exception as e:
        await message.answer(f"❌ Xatolik: {str(e)}")


========================================
FAYL: handlers/users.py
Mavjud faylni o'chirib, quyidagini yozing
========================================

from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import database as db

router = Router()

ROLLAR_NOMI = {
    "superadmin": "👑 Super Admin",
    "direktor": "👔 Direktor",
    "omborchi": "📦 Omborchi",
    "ishchi": "🔨 Ishchi",
    "sotuvchi": "💰 Sotuvchi",
    "hisobchi": "📊 Hisobchi",
}

ROL_MAP = {
    "👔 Direktor": "direktor",
    "📦 Omborchi": "omborchi",
    "🔨 Ishchi": "ishchi",
    "💰 Sotuvchi": "sotuvchi",
    "📊 Hisobchi": "hisobchi",
}

class UserAddState(StatesGroup):
    user_id = State()
    ism = State()
    rol = State()

class UserEditState(StatesGroup):
    user_id = State()
    rol = State()

class UserDeleteState(StatesGroup):
    user_id = State()

def users_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👥 Foydalanuvchilar ro'yxati")],
            [KeyboardButton(text="➕ Foydalanuvchi qo'shish")],
            [KeyboardButton(text="✏️ Rol o'zgartirish")],
            [KeyboardButton(text="🗑️ Foydalanuvchini o'chirish")],
            [KeyboardButton(text="🔐 Huquqlar boshqaruvi")],
            [KeyboardButton(text="📋 Audit log")],
            [KeyboardButton(text="🏠 Asosiy menyu")],
        ],
        resize_keyboard=True
    )

def rol_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👔 Direktor")],
            [KeyboardButton(text="📦 Omborchi")],
            [KeyboardButton(text="🔨 Ishchi")],
            [KeyboardButton(text="💰 Sotuvchi")],
            [KeyboardButton(text="📊 Hisobchi")],
            [KeyboardButton(text="🏠 Asosiy menyu")],
        ],
        resize_keyboard=True
    )

@router.message(F.text == "👥 Foydalanuvchilar")
async def foydalanuvchilar(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user or user["rol"] != "superadmin":
        await message.answer("❌ Ruxsat yo'q!")
        return
    await message.answer("👥 Foydalanuvchilar boshqaruvi:", reply_markup=users_menu())

@router.message(F.text == "👥 Foydalanuvchilar ro'yxati")
async def users_royxati(message: Message):
    try:
        users = await db.get_all_users()
        if not users:
            await message.answer("❌ Hali foydalanuvchi yo'q!", reply_markup=users_menu())
            return
        text = "👥 Foydalanuvchilar:\n\n"
        for u in users:
            status = "✅" if u["faol"] else "❌"
            rol_nomi = ROLLAR_NOMI.get(u["rol"], u["rol"])
            text += (
                f"{status} {u['ism']}\n"
                f"   ID: <code>{u['id']}</code>\n"
                f"   Rol: {rol_nomi}\n"
                f"   @{u['username'] or 'username yoq'}\n\n"
            )
        if len(text) > 4000:
            text = text[:4000] + "\n..."
        await message.answer(text, parse_mode="HTML", reply_markup=users_menu())
    except Exception as e:
        await message.answer(f"❌ Xatolik: {str(e)}")

@router.message(F.text == "➕ Foydalanuvchi qo'shish")
async def user_qoshish(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(UserAddState.user_id)
    await message.answer(
        "Yangi foydalanuvchining Telegram ID sini kiriting:\n\n"
        "💡 Foydalanuvchi /start bosganida bot sizga xabar yuboradi."
    )

@router.message(UserAddState.user_id)
async def user_id_kiritish(message: Message, state: FSMContext):
    try:
        user_id = int(message.text.strip())
        await state.update_data(user_id=user_id)
        await state.set_state(UserAddState.ism)
        await message.answer("Foydalanuvchi ismini kiriting:\nMisol: Ahmadjon")
    except ValueError:
        await message.answer("❌ Faqat raqam kiriting!")

@router.message(UserAddState.ism)
async def user_ism_kiritish(message: Message, state: FSMContext):
    await state.update_data(ism=message.text.strip())
    await state.set_state(UserAddState.rol)
    await message.answer("Rol tanlang:", reply_markup=rol_menu())

@router.message(UserAddState.rol)
async def user_rol_kiritish(message: Message, state: FSMContext):
    if message.text not in ROL_MAP:
        await message.answer("❌ Tugmalardan birini tanlang!")
        return
    try:
        rol = ROL_MAP[message.text]
        data = await state.get_data()
        await db.add_user(data["user_id"], data["ism"], None, rol)
        admin = await db.get_user(message.from_user.id)
        await db.add_audit_log(
            message.from_user.id,
            admin["ism"] if admin else str(message.from_user.id),
            admin["rol"] if admin else "-",
            "Foydalanuvchi qo'shildi",
            f"{data['ism']} (ID: {data['user_id']}) → {rol}"
        )
        await state.clear()
        await message.answer(
            f"✅ Foydalanuvchi qo'shildi!\n"
            f"👤 {data['ism']}\n"
            f"🆔 ID: {data['user_id']}\n"
            f"🔑 Rol: {ROLLAR_NOMI[rol]}",
            reply_markup=users_menu()
        )
    except Exception as e:
        await state.clear()
        await message.answer(f"❌ Xatolik: {str(e)}", reply_markup=users_menu())

@router.message(F.text == "✏️ Rol o'zgartirish")
async def rol_ozgartirish(message: Message, state: FSMContext):
    try:
        await state.clear()
        users = await db.get_all_users()
        faol_users = [u for u in users if u["faol"] and u["rol"] != "superadmin"]
        if not faol_users:
            await message.answer("❌ O'zgartirish mumkin bo'lgan foydalanuvchi yo'q!", reply_markup=users_menu())
            return
        text = "✏️ Qaysi foydalanuvchi rolini o'zgartirish?\nID raqamini kiriting:\n\n"
        for u in faol_users:
            rol_nomi = ROLLAR_NOMI.get(u["rol"], u["rol"])
            text += f"🔹 <code>{u['id']}</code> — {u['ism']} ({rol_nomi})\n"
        await state.set_state(UserEditState.user_id)
        await message.answer(text, parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Xatolik: {str(e)}")

@router.message(UserEditState.user_id)
async def rol_ozgartirish_id(message: Message, state: FSMContext):
    try:
        user_id = int(message.text.strip())
        target = await db.get_user(user_id)
        if not target:
            await message.answer("❌ Foydalanuvchi topilmadi!")
            await state.clear()
            return
        if target["rol"] == "superadmin":
            await message.answer("❌ Super Admin rolini o'zgartirib bo'lmaydi!")
            await state.clear()
            return
        await state.update_data(user_id=user_id, ism=target["ism"])
        await state.set_state(UserEditState.rol)
        await message.answer(f"👤 {target['ism']} uchun yangi rol tanlang:", reply_markup=rol_menu())
    except ValueError:
        await message.answer("❌ Faqat raqam kiriting!")
        await state.clear()

@router.message(UserEditState.rol)
async def rol_ozgartirish_rol(message: Message, state: FSMContext):
    if message.text not in ROL_MAP:
        await message.answer("❌ Tugmalardan birini tanlang!")
        return
    try:
        rol = ROL_MAP[message.text]
        data = await state.get_data()
        await db.update_user_rol(data["user_id"], rol)
        admin = await db.get_user(message.from_user.id)
        await db.add_audit_log(
            message.from_user.id,
            admin["ism"] if admin else str(message.from_user.id),
            admin["rol"] if admin else "-",
            "Rol o'zgartirildi",
            f"{data['ism']} (ID: {data['user_id']}) → {rol}"
        )
        await state.clear()
        await message.answer(
            f"✅ Rol yangilandi!\n👤 {data['ism']}\n🔑 Yangi rol: {ROLLAR_NOMI[rol]}",
            reply_markup=users_menu()
        )
    except Exception as e:
        await state.clear()
        await message.answer(f"❌ Xatolik: {str(e)}", reply_markup=users_menu())

@router.message(F.text == "🗑️ Foydalanuvchini o'chirish")
async def user_ochirish(message: Message, state: FSMContext):
    try:
        await state.clear()
        users = await db.get_all_users()
        faol_users = [u for u in users if u["faol"] and u["rol"] != "superadmin"]
        if not faol_users:
            await message.answer("❌ O'chirish mumkin bo'lgan foydalanuvchi yo'q!", reply_markup=users_menu())
            return
        text = "🗑️ Qaysi foydalanuvchini o'chirish?\nID raqamini kiriting:\n\n"
        for u in faol_users:
            rol_nomi = ROLLAR_NOMI.get(u["rol"], u["rol"])
            text += f"🔹 <code>{u['id']}</code> — {u['ism']} ({rol_nomi})\n"
        await state.set_state(UserDeleteState.user_id)
        await message.answer(text, parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Xatolik: {str(e)}")

@router.message(UserDeleteState.user_id)
async def user_ochirish_id(message: Message, state: FSMContext):
    try:
        user_id = int(message.text.strip())
        target = await db.get_user(user_id)
        if not target:
            await message.answer("❌ Foydalanuvchi topilmadi!")
            await state.clear()
            return
        if target["rol"] == "superadmin":
            await message.answer("❌ Super Admin ni o'chirib bo'lmaydi!")
            await state.clear()
            return
        await db.delete_user(user_id)
        admin = await db.get_user(message.from_user.id)
        await db.add_audit_log(
            message.from_user.id,
            admin["ism"] if admin else str(message.from_user.id),
            admin["rol"] if admin else "-",
            "Foydalanuvchi o'chirildi",
            f"{target['ism']} (ID: {user_id}) bloklandi"
        )
        await state.clear()
        await message.answer(f"✅ {target['ism']} tizimdan chiqarildi!", reply_markup=users_menu())
    except ValueError:
        await message.answer("❌ Faqat raqam kiriting!")
        await state.clear()
    except Exception as e:
        await state.clear()
        await message.answer(f"❌ Xatolik: {str(e)}", reply_markup=users_menu())

@router.message(F.text == "📋 Audit log")
async def audit_log(message: Message):
    try:
        logs = await db.get_audit_log(30)
        if not logs:
            await message.answer("📋 Audit log bo'sh.", reply_markup=users_menu())
            return
        text = "📋 Oxirgi 30 ta amal:\n\n"
        for log in logs:
            vaqt = log["vaqt"]
            vaqt_str = vaqt.strftime("%d.%m %H:%M") if hasattr(vaqt, "strftime") else str(vaqt)[:16]
            rol_nomi = ROLLAR_NOMI.get(log["rol"], log["rol"])
            text += (
                f"🕐 {vaqt_str}\n"
                f"👤 {log['ism']} ({rol_nomi})\n"
                f"📌 {log['amal']}\n"
                f"📝 {log['tafsilot']}\n\n"
            )
        if len(text) > 4000:
            text = text[:4000] + "\n..."
        await message.answer(text, reply_markup=users_menu())
    except Exception as e:
        await message.answer(f"❌ Xatolik: {str(e)}")

