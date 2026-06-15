from aiogram import Router
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import database as db
from translation import Tkey, canon, say, say_error, esc, build_keyboard

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

ROL_MAP = {
    "👔 Direktor": "direktor",
    "📦 Omborchi": "omborchi",
    "🔨 Ishchi": "ishchi",
    "💰 Sotuvchi": "sotuvchi",
    "📊 Hisobchi": "hisobchi",
}

RUXSAT_BUTTONS = {"✅ Ruxsat berish": True, "❌ Ruxsatni olish": False}


class RolPermState(StatesGroup):
    rol = State()
    permission = State()
    ruxsat = State()


class UserPermState(StatesGroup):
    user_id = State()
    permission = State()
    ruxsat = State()


async def permissions_menu(user_id):
    return await build_keyboard(user_id, [
        ["🔐 Rol huquqlari"],
        ["👤 Foydalanuvchi huquqlari"],
        ["📋 Huquqlar ro'yxati"],
        ["🏠 Asosiy menyu"],
    ])


async def rol_menu(user_id):
    return await build_keyboard(user_id, [
        ["👔 Direktor"],
        ["📦 Omborchi"],
        ["🔨 Ishchi"],
        ["💰 Sotuvchi"],
        ["📊 Hisobchi"],
        ["🏠 Asosiy menyu"],
    ])


async def ruxsat_menu(user_id):
    return await build_keyboard(user_id, [
        ["✅ Ruxsat berish"],
        ["❌ Ruxsatni olish"],
        ["🏠 Asosiy menyu"],
    ])


async def _faqat_superadmin(message: Message) -> bool:
    user = await db.get_user(message.from_user.id)
    if not user or user["rol"] != "superadmin":
        await say(message, "❌ Ruxsat yo'q!")
        return False
    return True


@router.message(Tkey("🔐 Huquqlar boshqaruvi"))
async def huquqlar(message: Message):
    if not await _faqat_superadmin(message):
        return
    await say(message, "🔐 Huquqlar boshqaruvi:", reply_markup=await permissions_menu(message.from_user.id))


# ── Rol huquqlari ──
@router.message(Tkey("🔐 Rol huquqlari"))
async def rol_huquqlari(message: Message, state: FSMContext):
    if not await _faqat_superadmin(message):
        return
    await state.clear()
    await state.set_state(RolPermState.rol)
    await say(message, "Qaysi rol uchun huquqlarni o'zgartirish?", reply_markup=await rol_menu(message.from_user.id))


@router.message(RolPermState.rol)
async def rol_tanlash(message: Message, state: FSMContext):
    uz = await canon(message, list(ROL_MAP.keys()))
    if not uz:
        await say(message, "❌ Tugmalardan birini tanlang!")
        return
    rol = ROL_MAP[uz]
    await state.update_data(rol=rol)

    # Hozirgi huquqlarni ko'rsatish
    perms = await db.get_rol_permissions(rol)
    text = f"📋 {ROLLAR_NOMI[rol]} uchun hozirgi huquqlar:\n\n"
    for p, nomi in PERMISSION_NOMI.items():
        status = "✅" if perms.get(p, False) else "❌"
        text += f"{status} {nomi}\n"

    text += "\nQaysi huquqni o'zgartirish?\nRaqamini kiriting:\n\n"
    for i, (p, nomi) in enumerate(PERMISSION_NOMI.items(), 1):
        text += f"{i}. {nomi}\n"

    await state.update_data(permissions_list=list(PERMISSION_NOMI.keys()))
    await state.set_state(RolPermState.permission)
    await say(message, text)


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
        await say(
            message,
            f"📌 {PERMISSION_NOMI[perm]}\n\n"
            f"Ruxsat bering yoki oling:",
            reply_markup=await ruxsat_menu(message.from_user.id)
        )
    except ValueError:
        await say(message, "❌ To'g'ri raqam kiriting!")


@router.message(RolPermState.ruxsat)
async def rol_ruxsat_berish(message: Message, state: FSMContext):
    uz = await canon(message, list(RUXSAT_BUTTONS.keys()))
    if uz is None:
        await say(message, "❌ Tugmalardan birini tanlang!")
        return
    ruxsat = RUXSAT_BUTTONS[uz]
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
    await say(
        message,
        f"{status}!\n"
        f"Rol: {ROLLAR_NOMI.get(rol, rol)}\n"
        f"Huquq: {PERMISSION_NOMI[permission]}",
        reply_markup=await permissions_menu(message.from_user.id)
    )


# ── Foydalanuvchi individual huquqlari ──
@router.message(Tkey("👤 Foydalanuvchi huquqlari"))
async def user_huquqlari(message: Message, state: FSMContext):
    if not await _faqat_superadmin(message):
        return
    await state.clear()
    users = await db.get_all_users()
    faol_users = [u for u in users if u["faol"] and u["rol"] != "superadmin"]
    if not faol_users:
        await say(message, "❌ Foydalanuvchi yo'q!", reply_markup=await permissions_menu(message.from_user.id))
        return
    text = "👤 Qaysi foydalanuvchi?\nID raqamini kiriting:\n\n"
    for u in faol_users:
        text += f"🔹 <code>{u['id']}</code> — {esc(u['ism'])} ({u['rol']})\n"
    await state.set_state(UserPermState.user_id)
    await say(message, text, parse_mode="HTML")


@router.message(UserPermState.user_id)
async def user_id_tanlash(message: Message, state: FSMContext):
    try:
        user_id = int(message.text.strip())
        target = await db.get_user(user_id)
        if not target:
            await say(message, "❌ Foydalanuvchi topilmadi!")
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
        await say(message, text)
    except ValueError:
        await say(message, "❌ Faqat raqam kiriting!")
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
        await say(
            message,
            f"👤 {data['user_ism']}\n"
            f"📌 {PERMISSION_NOMI[perm]}\n\n"
            f"Ruxsat bering yoki oling:",
            reply_markup=await ruxsat_menu(message.from_user.id)
        )
    except ValueError:
        await say(message, "❌ To'g'ri raqam kiriting!")


@router.message(UserPermState.ruxsat)
async def user_ruxsat_berish(message: Message, state: FSMContext):
    uz = await canon(message, list(RUXSAT_BUTTONS.keys()))
    if uz is None:
        await say(message, "❌ Tugmalardan birini tanlang!")
        return
    ruxsat = RUXSAT_BUTTONS[uz]
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
    await say(
        message,
        f"{status}!\n"
        f"👤 {data['user_ism']}\n"
        f"📌 {PERMISSION_NOMI[permission]}",
        reply_markup=await permissions_menu(message.from_user.id)
    )


# ── Huquqlar ro'yxati ──
@router.message(Tkey("📋 Huquqlar ro'yxati"))
async def huquqlar_royxati(message: Message):
    if not await _faqat_superadmin(message):
        return
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
        await say(message, text, reply_markup=await permissions_menu(message.from_user.id))
    except Exception as e:
        await say_error(message, e)
