from aiogram import Router
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import database as db
from translation import Tkey, canon, say, say_error, esc, build_keyboard

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


async def users_menu(user_id):
    return await build_keyboard(user_id, [
        ["👥 Foydalanuvchilar ro'yxati"],
        ["➕ Foydalanuvchi qo'shish"],
        ["✏️ Rol o'zgartirish"],
        ["🗑️ Foydalanuvchini o'chirish"],
        ["🔐 Huquqlar boshqaruvi"],
        ["📋 Audit log"],
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


async def _faqat_superadmin(message: Message) -> bool:
    """'foydalanuvchi_boshqaruv' huquqi (superadmin doim ega)."""
    user = await db.get_user(message.from_user.id)
    if not user or not user["faol"]:
        await say(message, "❌ Ruxsat yo'q!")
        return False
    if await db.has_permission(message.from_user.id, user["rol"], "foydalanuvchi_boshqaruv"):
        return True
    await say(message, "❌ Sizda foydalanuvchilarni boshqarish huquqi yo'q!")
    return False


@router.message(Tkey("👥 Foydalanuvchilar"))
async def foydalanuvchilar(message: Message):
    if not await _faqat_superadmin(message):
        return
    await say(message, "👥 Foydalanuvchilar boshqaruvi:", reply_markup=await users_menu(message.from_user.id))


@router.message(Tkey("👥 Foydalanuvchilar ro'yxati"))
async def users_royxati(message: Message):
    if not await _faqat_superadmin(message):
        return
    try:
        users = await db.get_all_users()
        if not users:
            await say(message, "❌ Hali foydalanuvchi yo'q!", reply_markup=await users_menu(message.from_user.id))
            return
        text = "👥 Foydalanuvchilar:\n\n"
        for u in users:
            status = "✅" if u["faol"] else "❌"
            rol_nomi = ROLLAR_NOMI.get(u["rol"], u["rol"])
            text += (
                f"{status} {esc(u['ism'])}\n"
                f"   ID: <code>{u['id']}</code>\n"
                f"   Rol: {rol_nomi}\n"
                f"   @{esc(u['username']) if u['username'] else 'username yoq'}\n\n"
            )
        if len(text) > 4000:
            text = text[:4000] + "\n..."
        await say(message, text, parse_mode="HTML", reply_markup=await users_menu(message.from_user.id))
    except Exception as e:
        await say_error(message, e)


@router.message(Tkey("➕ Foydalanuvchi qo'shish"))
async def user_qoshish(message: Message, state: FSMContext):
    if not await _faqat_superadmin(message):
        return
    await state.clear()
    await state.set_state(UserAddState.user_id)
    await say(
        message,
        "Yangi foydalanuvchining Telegram ID sini kiriting:\n\n"
        "💡 Foydalanuvchi /start bosganida bot sizga xabar yuboradi."
    )


@router.message(UserAddState.user_id)
async def user_id_kiritish(message: Message, state: FSMContext):
    try:
        user_id = int(message.text.strip())
        await state.update_data(user_id=user_id)
        await state.set_state(UserAddState.ism)
        await say(message, "Foydalanuvchi ismini kiriting:\nMisol: Ahmadjon")
    except ValueError:
        await say(message, "❌ Faqat raqam kiriting!")


@router.message(UserAddState.ism)
async def user_ism_kiritish(message: Message, state: FSMContext):
    await state.update_data(ism=message.text.strip())
    await state.set_state(UserAddState.rol)
    await say(message, "Rol tanlang:", reply_markup=await rol_menu(message.from_user.id))


@router.message(UserAddState.rol)
async def user_rol_kiritish(message: Message, state: FSMContext):
    uz = await canon(message, list(ROL_MAP.keys()))
    if not uz:
        await say(message, "❌ Tugmalardan birini tanlang!")
        return
    try:
        rol = ROL_MAP[uz]
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
        await say(
            message,
            f"✅ Foydalanuvchi qo'shildi!\n"
            f"👤 {data['ism']}\n"
            f"🆔 ID: {data['user_id']}\n"
            f"🔑 Rol: {ROLLAR_NOMI[rol]}",
            reply_markup=await users_menu(message.from_user.id)
        )
    except Exception as e:
        await state.clear()
        await say_error(message, e, reply_markup=await users_menu(message.from_user.id))


@router.message(Tkey("✏️ Rol o'zgartirish"))
async def rol_ozgartirish(message: Message, state: FSMContext):
    if not await _faqat_superadmin(message):
        return
    try:
        await state.clear()
        users = await db.get_all_users()
        faol_users = [u for u in users if u["faol"] and u["rol"] != "superadmin"]
        if not faol_users:
            await say(message, "❌ O'zgartirish mumkin bo'lgan foydalanuvchi yo'q!", reply_markup=await users_menu(message.from_user.id))
            return
        text = "✏️ Qaysi foydalanuvchi rolini o'zgartirish?\nID raqamini kiriting:\n\n"
        for u in faol_users:
            rol_nomi = ROLLAR_NOMI.get(u["rol"], u["rol"])
            text += f"🔹 <code>{u['id']}</code> — {esc(u['ism'])} ({rol_nomi})\n"
        await state.set_state(UserEditState.user_id)
        await say(message, text, parse_mode="HTML")
    except Exception as e:
        await say_error(message, e)


@router.message(UserEditState.user_id)
async def rol_ozgartirish_id(message: Message, state: FSMContext):
    try:
        user_id = int(message.text.strip())
        target = await db.get_user(user_id)
        if not target:
            await say(message, "❌ Foydalanuvchi topilmadi!")
            await state.clear()
            return
        if target["rol"] == "superadmin":
            await say(message, "❌ Super Admin rolini o'zgartirib bo'lmaydi!")
            await state.clear()
            return
        await state.update_data(user_id=user_id, ism=target["ism"])
        await state.set_state(UserEditState.rol)
        await say(message, f"👤 {target['ism']} uchun yangi rol tanlang:", reply_markup=await rol_menu(message.from_user.id))
    except ValueError:
        await say(message, "❌ Faqat raqam kiriting!")
        await state.clear()


@router.message(UserEditState.rol)
async def rol_ozgartirish_rol(message: Message, state: FSMContext):
    uz = await canon(message, list(ROL_MAP.keys()))
    if not uz:
        await say(message, "❌ Tugmalardan birini tanlang!")
        return
    try:
        rol = ROL_MAP[uz]
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
        await say(
            message,
            f"✅ Rol yangilandi!\n👤 {data['ism']}\n🔑 Yangi rol: {ROLLAR_NOMI[rol]}",
            reply_markup=await users_menu(message.from_user.id)
        )
    except Exception as e:
        await state.clear()
        await say_error(message, e, reply_markup=await users_menu(message.from_user.id))


@router.message(Tkey("🗑️ Foydalanuvchini o'chirish"))
async def user_ochirish(message: Message, state: FSMContext):
    if not await _faqat_superadmin(message):
        return
    try:
        await state.clear()
        users = await db.get_all_users()
        faol_users = [u for u in users if u["faol"] and u["rol"] != "superadmin"]
        if not faol_users:
            await say(message, "❌ O'chirish mumkin bo'lgan foydalanuvchi yo'q!", reply_markup=await users_menu(message.from_user.id))
            return
        text = "🗑️ Qaysi foydalanuvchini o'chirish?\nID raqamini kiriting:\n\n"
        for u in faol_users:
            rol_nomi = ROLLAR_NOMI.get(u["rol"], u["rol"])
            text += f"🔹 <code>{u['id']}</code> — {esc(u['ism'])} ({rol_nomi})\n"
        await state.set_state(UserDeleteState.user_id)
        await say(message, text, parse_mode="HTML")
    except Exception as e:
        await say_error(message, e)


@router.message(UserDeleteState.user_id)
async def user_ochirish_id(message: Message, state: FSMContext):
    try:
        user_id = int(message.text.strip())
        target = await db.get_user(user_id)
        if not target:
            await say(message, "❌ Foydalanuvchi topilmadi!")
            await state.clear()
            return
        if target["rol"] == "superadmin":
            await say(message, "❌ Super Admin ni o'chirib bo'lmaydi!")
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
        await say(message, f"✅ {target['ism']} tizimdan chiqarildi!", reply_markup=await users_menu(message.from_user.id))
    except ValueError:
        await say(message, "❌ Faqat raqam kiriting!")
        await state.clear()
    except Exception as e:
        await state.clear()
        await say_error(message, e, reply_markup=await users_menu(message.from_user.id))


@router.message(Tkey("📋 Audit log"))
async def audit_log(message: Message):
    if not await _faqat_superadmin(message):
        return
    try:
        logs = await db.get_audit_log(30)
        if not logs:
            await say(message, "📋 Audit log bo'sh.", reply_markup=await users_menu(message.from_user.id))
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
        await say(message, text, reply_markup=await users_menu(message.from_user.id))
    except Exception as e:
        await say_error(message, e)
