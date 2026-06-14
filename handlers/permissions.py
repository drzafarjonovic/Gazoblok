from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import database as db

router = Router()

PERMISSION_NOMI = {
    "ishlab_chiqarish_kiritish": "🏭 Ishlab chiqarish kiritish",
    "ishlab_chiqarish_korish": "👁 Ishlab chiqarish ko'rish",
    "sotuv_kiritish": "💰 Sotuv kiritish",
    "sotuv_korish": "👁 Sotuv ko'rish",
    "ombor_kiritish": "📥 Ombor kirim",
    "ombor_korish": "👁 Ombor ko'rish",
    "tayyor_mahsulot_korish": "👁 Tayyor mahsulot ko'rish",
    "tayyor_mahsulot_tahrirlash": "✏️ Tayyor mahsulot tahrirlash",
    "hisobot_korish": "📊 Hisobot ko'rish",
    "excel_hisobot": "📥 Excel hisobot",
}

ROLLAR_NOMI = {
    "direktor": "👔 Direktor",
    "omborchi": "📦 Omborchi",
    "ishchi": "🔨 Ishchi",
    "sotuvchi": "💰 Sotuvchi",
    "hisobchi": "📊 Hisobchi",
}

class RolPermState(StatesGroup):
    rol = State()
    permission = State()
    ruxsat = State()

class UserPermState(StatesGroup):
    user_id = State()
    permission = State()
    ruxsat = State()

def permissions_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔐 Rol huquqlari")],
            [KeyboardButton(text="👤 Foydalanuvchi huquqlari")],
            [KeyboardButton(text="📋 Huquqlar ro'yxati")],
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

def ruxsat_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Ruxsat berish")],
            [KeyboardButton(text="❌ Ruxsatni olish")],
            [KeyboardButton(text="🏠 Asosiy menyu")],
        ],
        resize_keyboard=True
    )

@router.message(F.text == "🔐 Huquqlar boshqaruvi")
async def huquqlar(message: Message):
    user = await db.get_user(message.from_user.id)
    if not user or user["rol"] != "superadmin":
        await message.answer("❌ Ruxsat yo'q!")
        return
    await message.answer("🔐 Huquqlar boshqaruvi:", reply_markup=permissions_menu())

# ── Rol huquqlari ──
@router.message(F.text == "🔐 Rol huquqlari")
async def rol_huquqlari(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(RolPermState.rol)
    await message.answer("Qaysi rol uchun huquqlarni o'zgartirish?", reply_markup=rol_menu())

@router.message(RolPermState.rol)
async def rol_tanlash(message: Message, state: FSMContext):
    if message.text not in ROL_MAP:
        await message.answer("❌ Tugmalardan birini tanlang!")
        return
    rol = ROL_MAP[message.text]
    await state.update_data(rol=rol)

    # Hozirgi huquqlarni ko'rsatish
    perms = await db.get_rol_permissions(rol)
    text = f"📋 {ROLLAR_NOMI[message.text]} uchun hozirgi huquqlar:\n\n"
    for p, nomi in PERMISSION_NOMI.items():
        status = "✅" if perms.get(p, False) else "❌"
        text += f"{status} {nomi}\n"

    text += "\nQaysi huquqni o'zgartirish?\nRaqamini kiriting:\n\n"
    for i, (p, nomi) in enumerate(PERMISSION_NOMI.items(), 1):
        text += f"{i}. {nomi}\n"

    await state.update_data(permissions_list=list(PERMISSION_NOMI.keys()))
    await state.set_state(RolPermState.permission)
    await message.answer(text)

@router.message(RolPermState.permission)
async def permission_tanlash(message: Message, state: FSMContext):
    try:
        idx = int(message.text.strip()) - 1
        data = await state.get_data()
        perms_list = data["permissions_list"]
        if idx < 0 or idx >= len(perms_list):
            raise ValueError
        perm = perms_list[idx]
        await state.update_data(permission=perm)
        await state.set_state(RolPermState.ruxsat)
        await message.answer(
            f"📌 {PERMISSION_NOMI[perm]}\n\n"
            f"Ruxsat bering yoki oling:",
            reply_markup=ruxsat_menu()
        )
    except ValueError:
        await message.answer("❌ To'g'ri raqam kiriting!")

@router.message(RolPermState.ruxsat)
async def rol_ruxsat_berish(message: Message, state: FSMContext):
    if message.text not in ["✅ Ruxsat berish", "❌ Ruxsatni olish"]:
        await message.answer("❌ Tugmalardan birini tanlang!")
        return
    ruxsat = message.text == "✅ Ruxsat berish"
    data = await state.get_data()
    rol = data["rol"]
    permission = data["permission"]

    await db.set_rol_permission(rol, permission, ruxsat)

    admin = await db.get_user(message.from_user.id)
    await db.add_audit_log(
        message.from_user.id,
        admin["ism"] if admin else str(message.from_user.id),
        "superadmin",
        "Rol huquqi o'zgartirildi",
        f"{rol} → {permission}: {'ruxsat' if ruxsat else 'taqiqlandi'}"
    )
    await state.clear()
    status = "✅ Ruxsat berildi" if ruxsat else "❌ Ruxsat olindi"
    await message.answer(
        f"{status}!\n"
        f"Rol: {ROLLAR_NOMI.get('👔 ' + rol.capitalize(), rol)}\n"
        f"Huquq: {PERMISSION_NOMI[permission]}",
        reply_markup=permissions_menu()
    )

# ── Foydalanuvchi individual huquqlari ──
@router.message(F.text == "👤 Foydalanuvchi huquqlari")
async def user_huquqlari(message: Message, state: FSMContext):
    await state.clear()
    users = await db.get_all_users()
    faol_users = [u for u in users if u["faol"] and u["rol"] != "superadmin"]
    if not faol_users:
        await message.answer("❌ Foydalanuvchi yo'q!", reply_markup=permissions_menu())
        return
    text = "👤 Qaysi foydalanuvchi?\nID raqamini kiriting:\n\n"
    for u in faol_users:
        text += f"🔹 <code>{u['id']}</code> — {u['ism']} ({u['rol']})\n"
    await state.set_state(UserPermState.user_id)
    await message.answer(text, parse_mode="HTML")

@router.message(UserPermState.user_id)
async def user_id_tanlash(message: Message, state: FSMContext):
    try:
        user_id = int(message.text.strip())
        target = await db.get_user(user_id)
        if not target:
            await message.answer("❌ Foydalanuvchi topilmadi!")
            await state.clear()
            return

        # Hozirgi huquqlarni ko'rsatish
        perms = await db.get_user_permissions(user_id, target["rol"])
        indiv = await db.get_user_individual_permissions(user_id)

        text = f"👤 {target['ism']} ({target['rol']})\n\n"
        text += "📋 Hozirgi huquqlar (rol + individual):\n"
        for p, nomi in PERMISSION_NOMI.items():
            status = "✅" if perms.get(p, False) else "❌"
            ind = " (individual)" if p in indiv else ""
            text += f"{status} {nomi}{ind}\n"

        text += "\nQaysi huquqni o'zgartirish?\nRaqamini kiriting:\n\n"
        for i, (p, nomi) in enumerate(PERMISSION_NOMI.items(), 1):
            text += f"{i}. {nomi}\n"

        await state.update_data(
            user_id=user_id,
            user_ism=target["ism"],
            permissions_list=list(PERMISSION_NOMI.keys())
        )
        await state.set_state(UserPermState.permission)
        await message.answer(text)
    except ValueError:
        await message.answer("❌ Faqat raqam kiriting!")
        await state.clear()

@router.message(UserPermState.permission)
async def user_permission_tanlash(message: Message, state: FSMContext):
    try:
        idx = int(message.text.strip()) - 1
        data = await state.get_data()
        perms_list = data["permissions_list"]
        if idx < 0 or idx >= len(perms_list):
            raise ValueError
        perm = perms_list[idx]
        await state.update_data(permission=perm)
        await state.set_state(UserPermState.ruxsat)
        await message.answer(
            f"👤 {data['user_ism']}\n"
            f"📌 {PERMISSION_NOMI[perm]}\n\n"
            f"Ruxsat bering yoki oling:",
            reply_markup=ruxsat_menu()
        )
    except ValueError:
        await message.answer("❌ To'g'ri raqam kiriting!")

@router.message(UserPermState.ruxsat)
async def user_ruxsat_berish(message: Message, state: FSMContext):
    if message.text not in ["✅ Ruxsat berish", "❌ Ruxsatni olish"]:
        await message.answer("❌ Tugmalardan birini tanlang!")
        return
    ruxsat = message.text == "✅ Ruxsat berish"
    data = await state.get_data()
    user_id = data["user_id"]
    permission = data["permission"]

    await db.set_user_permission(user_id, permission, ruxsat)

    admin = await db.get_user(message.from_user.id)
    await db.add_audit_log(
        message.from_user.id,
        admin["ism"] if admin else str(message.from_user.id),
        "superadmin",
        "Foydalanuvchi huquqi o'zgartirildi",
        f"{data['user_ism']} (ID:{user_id}) → {permission}: {'ruxsat' if ruxsat else 'taqiqlandi'}"
    )
    await state.clear()
    status = "✅ Ruxsat berildi" if ruxsat else "❌ Ruxsat olindi"
    await message.answer(
        f"{status}!\n"
        f"👤 {data['user_ism']}\n"
        f"📌 {PERMISSION_NOMI[permission]}",
        reply_markup=permissions_menu()
    )

# ── Huquqlar ro'yxati ──
@router.message(F.text == "📋 Huquqlar ro'yxati")
async def huquqlar_royxati(message: Message):
    try:
        text = "📋 Barcha rollar huquqlari:\n\n"
        for rol in ["direktor", "omborchi", "ishchi", "sotuvchi", "hisobchi"]:
            perms = await db.get_rol_permissions(rol)
            text += f"── {ROLLAR_NOMI.get(rol, rol)} ──\n"
            for p, nomi in PERMISSION_NOMI.items():
                status = "✅" if perms.get(p, False) else "❌"
                text += f"  {status} {nomi}\n"
            text += "\n"
        if len(text) > 4000:
            text = text[:4000] + "\n..."
        await message.answer(text, reply_markup=permissions_menu())
    except Exception as e:
        await message.answer(f"❌ Xatolik: {str(e)}")
      
