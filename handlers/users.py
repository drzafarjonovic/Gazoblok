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

class UserAddState(StatesGroup):
    user_id = State()
    ism = State()
    rol = State()

class UserEditState(StatesGroup):
    user_id = State()
    rol = State()

def users_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👥 Foydalanuvchilar ro'yxati")],
            [KeyboardButton(text="➕ Foydalanuvchi qo'shish")],
            [KeyboardButton(text="✏️ Rol o'zgartirish")],
            [KeyboardButton(text="🗑️ Foydalanuvchini o'chirish")],
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

ROL_MAP = {
    "👔 Direktor": "direktor",
    "📦 Omborchi": "omborchi",
    "🔨 Ishchi": "ishchi",
    "💰 Sotuvchi": "sotuvchi",
    "📊 Hisobchi": "hisobchi",
}

@router.message(F.text == "👥 Foydalanuvchilar")
async def foydalanuvchilar(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user or user["rol"] != "superadmin":
        await message.answer("❌ Sizda bu bo'limga kirish huquqi yo'q!")
        return
    await message.answer(
        "👥 Foydalanuvchilar boshqaruvi:",
        reply_markup=users_menu()
    )

# ── Foydalanuvchilar ro'yxati ──
@router.message(F.text == "👥 Foydalanuvchilar ro'yxati")
async def users_royxati(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user or user["rol"] != "superadmin":
        await message.answer("❌ Ruxsat yo'q!")
        return
    users = await db.get_all_users()
    if not users:
        await message.answer("❌ Hali foydalanuvchi yo'q!")
        return
    text = "👥 Foydalanuvchilar:\n\n"
    for u in users:
        status = "✅" if u["faol"] else "❌"
        rol_nomi = ROLLAR_NOMI.get(u["rol"], u["rol"])
        text += (
            f"{status} {u['ism']}\n"
            f"   ID: {u['id']}\n"
            f"   Rol: {rol_nomi}\n"
            f"   Username: @{u['username'] or 'yoq'}\n\n"
        )
    await message.answer(text)

# ── Foydalanuvchi qo'shish ──
@router.message(F.text == "➕ Foydalanuvchi qo'shish")
async def user_qoshish(message: Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    if not user or user["rol"] != "superadmin":
        await message.answer("❌ Ruxsat yo'q!")
        return
    await state.set_state(UserAddState.user_id)
    await message.answer(
        "Yangi foydalanuvchining Telegram ID sini kiriting:\n\n"
        "💡 Foydalanuvchi @userinfobot ga yozsa ID sini bilib oladi."
    )

@router.message(UserAddState.user_id)
async def user_id_kiritish(message: Message, state: FSMContext):
    try:
        user_id = int(message.text.strip())
        await state.update_data(user_id=user_id)
        await state.set_state(UserAddState.ism)
        await message.answer("Foydalanuvchi ismini kiriting:\nMisol: Ahmadjon")
    except ValueError:
        await message.answer("❌ Faqat raqam kiriting! Misol: 123456789")

@router.message(UserAddState.ism)
async def user_ism_kiritish(message: Message, state: FSMContext):
    await state.update_data(ism=message.text)
    await state.set_state(UserAddState.rol)
    await message.answer(
        "Rol tanlang:",
        reply_markup=rol_menu()
    )

@router.message(UserAddState.rol)
async def user_rol_kiritish(message: Message, state: FSMContext):
    if message.text not in ROL_MAP:
        await message.answer("❌ Tugmalardan birini tanlang!")
        return
    rol = ROL_MAP[message.text]
    data = await state.get_data()
    await db.add_user(data["user_id"], data["ism"], None, rol)

    # Audit log
    admin = await db.get_user(message.from_user.id)
    await db.add_audit_log(
        message.from_user.id,
        admin["ism"],
        admin["rol"],
        "Foydalanuvchi qo'shildi",
        f"{data['ism']} (ID: {data['user_id']}) → {rol}"
    )
    await state.clear()
    await message.answer(
        f"✅ Foydalanuvchi qo'shildi!\n"
        f"👤 {data['ism']}\n"
        f"🔑 Rol: {ROLLAR_NOMI[rol]}",
        reply_markup=users_menu()
    )

# ── Rol o'zgartirish ──
@router.message(F.text == "✏️ Rol o'zgartirish")
async def rol_ozgartirish(message: Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    if not user or user["rol"] != "superadmin":
        await message.answer("❌ Ruxsat yo'q!")
        return
    users = await db.get_all_users()
    if not users:
        await message.answer("❌ Foydalanuvchi yo'q!")
        return
    text = "Qaysi foydalanuvchi rolini o'zgartirish?\nID raqamini kiriting:\n\n"
    for u in users:
        if u["faol"] and u["rol"] != "superadmin":
            rol_nomi = ROLLAR_NOMI.get(u["rol"], u["rol"])
            text += f"🔹 {u['id']} — {u['ism']} ({rol_nomi})\n"
    await state.set_state(UserEditState.user_id)
    await message.answer(text)

@router.message(UserEditState.user_id)
async def rol_ozgartirish_id(message: Message, state: FSMContext):
    try:
        user_id = int(message.text.strip())
        target = await db.get_user(user_id)
        if not target:
            await message.answer("❌ Bunday foydalanuvchi topilmadi!")
            await state.clear()
            return
        await state.update_data(user_id=user_id, ism=target["ism"])
        await state.set_state(UserEditState.rol)
        await message.answer(
            f"👤 {target['ism']} uchun yangi rol tanlang:",
            reply_markup=rol_menu()
        )
    except ValueError:
        await message.answer("❌ Faqat raqam kiriting!")
        await state.clear()

@router.message(UserEditState.rol)
async def rol_ozgartirish_rol(message: Message, state: FSMContext):
    if message.text not in ROL_MAP:
        await message.answer("❌ Tugmalardan birini tanlang!")
        return
    rol = ROL_MAP[message.text]
    data = await state.get_data()
    await db.update_user_rol(data["user_id"], rol)

    admin = await db.get_user(message.from_user.id)
    await db.add_audit_log(
        message.from_user.id,
        admin["ism"],
        admin["rol"],
        "Rol o'zgartirildi",
        f"{data['ism']} (ID: {data['user_id']}) → {rol}"
    )
    await state.clear()
    await message.answer(
        f"✅ Rol yangilandi!\n"
        f"👤 {data['ism']}\n"
        f"🔑 Yangi rol: {ROLLAR_NOMI[rol]}",
        reply_markup=users_menu()
    )

# ── Foydalanuvchini o'chirish ──
@router.message(F.text == "🗑️ Foydalanuvchini o'chirish")
async def user_ochirish(message: Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    if not user or user["rol"] != "superadmin":
        await message.answer("❌ Ruxsat yo'q!")
        return
    users = await db.get_all_users()
    text = "Qaysi foydalanuvchini o'chirish?\nID raqamini kiriting:\n\n"
    for u in users:
        if u["faol"] and u["rol"] != "superadmin":
            rol_nomi = ROLLAR_NOMI.get(u["rol"], u["rol"])
            text += f"🔹 {u['id']} — {u['ism']} ({rol_nomi})\n"
    await message.answer(text)

# ── Audit log ──
@router.message(F.text == "📋 Audit log")
async def audit_log(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user or user["rol"] != "superadmin":
        await message.answer("❌ Ruxsat yo'q!")
        return
    logs = await db.get_audit_log(30)
    if not logs:
        await message.answer("📋 Audit log bo'sh.")
        return
    text = "📋 Oxirgi 30 ta amal:\n\n"
    for log in logs:
        vaqt = log["vaqt"].strftime("%d.%m %H:%M")
        text += (
            f"🕐 {vaqt}\n"
            f"👤 {log['ism']} ({log['rol']})\n"
            f"📌 {log['amal']}\n"
            f"📝 {log['tafsilot']}\n\n"
        )
    # Telegram 4096 belgi chegarasi
    if len(text) > 4000:
        text = text[:4000] + "\n..."
    await message.answer(text, reply_markup=users_menu())
