from aiogram import Router
from aiogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import database as db
from translation import Tkey, canon, say, build_keyboard

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
    "inventarizatsiya": "📋 Inventarizatsiya",
    "hisobot_korish": "📊 Hisobot ko'rish",
    "moliya_korish": "💵 Moliya / ishbay haq",
    "excel_hisobot": "📥 Eksport (Excel/CSV/PDF)",
    "sozlama_boshqaruv": "⚙️ Sozlamalar boshqaruvi",
    "foydalanuvchi_boshqaruv": "👥 Foydalanuvchi boshqaruvi",
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


class RolPermState(StatesGroup):
    rol = State()


class UserPermState(StatesGroup):
    user_id = State()


async def permissions_menu(user_id):
    return await build_keyboard(user_id, [
        ["🔐 Rol huquqlari"],
        ["👤 Foydalanuvchi huquqlari"],
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


async def _ruxsat(message: Message, user=None) -> bool:
    if user is None:
        user = await db.get_user(message.from_user.id)
    if not user or not user["faol"]:
        await say(message, "❌ Ruxsat yo'q!")
        return False
    if await db.has_permission(message.from_user.id, user["rol"], "foydalanuvchi_boshqaruv"):
        return True
    await say(message, "❌ Sizda huquqlarni boshqarish huquqi yo'q!")
    return False


def _qatorlar(effektiv, is_super, callback_prefix, indiv=None):
    """Huquqlar uchun inline tugmalar (✅/❌ toggle)."""
    kb = []
    for p, nomi in PERMISSION_NOMI.items():
        if p in db.ADMIN_PERMISSIONLAR and not is_super:
            continue
        belgi = "✅" if effektiv.get(p) else "❌"
        qoshimcha = " •" if (indiv is not None and p in indiv) else ""
        kb.append([InlineKeyboardButton(
            text=f"{belgi} {nomi}{qoshimcha}",
            callback_data=f"{callback_prefix}:{p}"
        )])
    return kb


async def rol_perm_keyboard(is_super, rol):
    perms = await db.get_rol_permissions(rol)
    kb = _qatorlar(perms, is_super, f"prm:r:{rol}")
    kb.append([
        InlineKeyboardButton(text="✅ Hammasi", callback_data=f"prm:r:{rol}:__all"),
        InlineKeyboardButton(text="❌ Hech biri", callback_data=f"prm:r:{rol}:__none"),
    ])
    kb.append([InlineKeyboardButton(text="🔙 Yopish", callback_data="prm:close")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


async def user_perm_keyboard(is_super, uid):
    target = await db.get_user(uid)
    rol = target["rol"] if target else "ishchi"
    eff = await db.get_user_permissions(uid, rol)
    indiv = await db.get_user_individual_permissions(uid)
    kb = _qatorlar(eff, is_super, f"prm:u:{uid}", indiv=indiv)
    kb.append([InlineKeyboardButton(text="♻️ Rolga qaytarish",
                                    callback_data=f"prm:u:{uid}:__reset")])
    kb.append([InlineKeyboardButton(text="🔙 Yopish", callback_data="prm:close")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


# ── Kirish ──
@router.message(Tkey("🔐 Huquqlar boshqaruvi"))
async def huquqlar(message: Message, user: dict = None):
    if not await _ruxsat(message, user):
        return
    await say(message, "🔐 Huquqlar boshqaruvi:",
              reply_markup=await permissions_menu(message.from_user.id))


# ── Rol huquqlari ──
@router.message(Tkey("🔐 Rol huquqlari"))
async def rol_huquqlari(message: Message, state: FSMContext, user: dict = None):
    if not await _ruxsat(message, user):
        return
    await state.clear()
    await state.set_state(RolPermState.rol)
    await say(message, "Qaysi rol uchun huquqlar?",
              reply_markup=await rol_menu(message.from_user.id))


@router.message(RolPermState.rol)
async def rol_tanlash(message: Message, state: FSMContext, user: dict = None):
    uz = await canon(message, list(ROL_MAP.keys()))
    if not uz:
        await say(message, "❌ Tugmalardan birini tanlang!")
        return
    rol = ROL_MAP[uz]
    await state.clear()
    if user is None:
        user = await db.get_user(message.from_user.id)
    is_super = bool(user and user["rol"] == "superadmin")
    kb = await rol_perm_keyboard(is_super, rol)
    await say(
        message,
        f"📋 {ROLLAR_NOMI.get(rol, rol)} huquqlari:\n"
        f"Tugmani bosib bering/oling.",
        reply_markup=kb
    )


# ── Foydalanuvchi individual huquqlari ──
@router.message(Tkey("👤 Foydalanuvchi huquqlari"))
async def user_huquqlari(message: Message, state: FSMContext, user: dict = None):
    if not await _ruxsat(message, user):
        return
    await state.clear()
    users = await db.get_all_users()
    faol_users = [u for u in users if u["faol"] and u["rol"] != "superadmin"]
    if not faol_users:
        await say(message, "❌ Foydalanuvchi yo'q!",
                  reply_markup=await permissions_menu(message.from_user.id))
        return
    kb = [[InlineKeyboardButton(
        text=f"{u['ism']} · {ROLLAR_NOMI.get(u['rol'], u['rol'])}",
        callback_data=f"permu:{u['id']}")] for u in faol_users[:60]]
    await say(message, "👤 Huquqlarini o'zgartirish uchun foydalanuvchini tanlang:",
              reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))


@router.callback_query(lambda c: c.data and c.data.startswith("permu:"))
async def permu_cb(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user or not await db.has_permission(
            callback.from_user.id, user["rol"], "foydalanuvchi_boshqaruv"):
        await callback.answer("⛔ Ruxsat yo'q!", show_alert=True)
        return
    uid = int(callback.data.split(":")[1])
    target = await db.get_user(uid)
    if not target:
        await callback.answer("❌ Topilmadi", show_alert=True)
        return
    if target["rol"] == "superadmin":
        await callback.answer("❌ Superadmin huquqlari o'zgartirilmaydi", show_alert=True)
        return
    is_super = user["rol"] == "superadmin"
    kb = await user_perm_keyboard(is_super, uid)
    try:
        await callback.message.edit_text(
            f"👤 {target['ism']} ({target['rol']}) huquqlari:\n"
            f"Tugmani bosib o'zgartiring. (• = individual)", reply_markup=kb)
    except Exception:
        pass
    await callback.answer()


# ── Toggle callback ──
@router.callback_query(lambda c: c.data and c.data.startswith("prm:"))
async def prm_callback(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user or not await db.has_permission(
            callback.from_user.id, user["rol"], "foydalanuvchi_boshqaruv"):
        await callback.answer("⛔ Ruxsat yo'q!", show_alert=True)
        return

    parts = callback.data.split(":")
    if parts[1] == "close":
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        await callback.answer("Yopildi")
        return

    typ = parts[1]          # r | u
    target = parts[2]       # rol nomi yoki user_id
    perm = parts[3]         # permission yoki __all/__none/__reset
    is_super = user["rol"] == "superadmin"

    # Administrativ huquqlarni faqat superadmin o'zgartiradi
    if perm in db.ADMIN_PERMISSIONLAR and not is_super:
        await callback.answer("⛔ Faqat superadmin", show_alert=True)
        return

    try:
        if typ == "r":
            rol = target
            cur = await db.get_rol_permissions(rol)
            if perm == "__all":
                for p in db.BARCHA_PERMISSIONLAR:
                    if p in db.ADMIN_PERMISSIONLAR and not is_super:
                        continue
                    await db.set_rol_permission(rol, p, True)
                tafsilot = f"{rol}: barchasi yoqildi"
            elif perm == "__none":
                for p in db.BARCHA_PERMISSIONLAR:
                    if p in db.ADMIN_PERMISSIONLAR and not is_super:
                        continue
                    await db.set_rol_permission(rol, p, False)
                tafsilot = f"{rol}: barchasi o'chirildi"
            else:
                yangi = not cur.get(perm, False)
                await db.set_rol_permission(rol, perm, yangi)
                tafsilot = f"{rol} → {perm}: {'✅' if yangi else '❌'}"
            kb = await rol_perm_keyboard(is_super, rol)
        else:  # u
            uid = int(target)
            tgt = await db.get_user(uid)
            if tgt and tgt["rol"] == "superadmin":
                await callback.answer("⛔ Superadmin", show_alert=True)
                return
            if perm == "__reset":
                await db.clear_user_permissions(uid)
                tafsilot = f"user {uid}: individual huquqlar tozalandi"
            else:
                rol = tgt["rol"] if tgt else "ishchi"
                eff = await db.get_user_permissions(uid, rol)
                yangi = not eff.get(perm, False)
                await db.set_user_permission(uid, perm, yangi)
                tafsilot = f"user {uid} → {perm}: {'✅' if yangi else '❌'}"
            kb = await user_perm_keyboard(is_super, uid)

        await callback.message.edit_reply_markup(reply_markup=kb)
        await callback.answer("✔️")
        await db.add_audit_log(
            callback.from_user.id, user["ism"], user["rol"],
            "Huquq o'zgartirildi", tafsilot
        )
    except Exception as e:
        from translation import log_exc
        log_exc("prm_callback", e)
        await callback.answer("❌ Xatolik", show_alert=True)
