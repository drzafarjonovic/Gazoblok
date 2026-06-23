from aiogram import Router
from aiogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery,
    BufferedInputFile,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import timezone, timedelta
import csv
import io
import database as db
import valyuta as val
from translation import Tkey, canon, say, say_error, esc, build_keyboard, t

router = Router()

TOSHKENT_TZ = timezone(timedelta(hours=5))

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


class UserRestoreState(StatesGroup):
    user_id = State()


class UserNameState(StatesGroup):
    user_id = State()
    ism = State()


class UserProfileState(StatesGroup):
    user_id = State()


class UserSearchState(StatesGroup):
    q = State()


class SuperTransferState(StatesGroup):
    user_id = State()
    confirm = State()


def _vaqt(v, fmt="%d.%m.%Y %H:%M"):
    if hasattr(v, "strftime"):
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc).astimezone(TOSHKENT_TZ)
        return v.strftime(fmt)
    return "—"


async def users_menu(user_id):
    return await build_keyboard(user_id, [
        ["👥 Foydalanuvchilar ro'yxati"],
        ["➕ Foydalanuvchi qo'shish"],
        ["📋 Kutilayotgan so'rovlar"],
        ["👤 Foydalanuvchi profili"],
        ["🔎 Qidirish"],
        ["✏️ Rol o'zgartirish"],
        ["✏️ Ismni o'zgartirish"],
        ["🗑️ Foydalanuvchini bloklash"],
        ["♻️ Bloklangani tiklash"],
        ["🔐 Huquqlar boshqaruvi"],
        ["🔁 Superadminlikni o'tkazish"],
        ["📋 Audit log"],
        ["📄 Audit CSV"],
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


async def _ruxsat(message: Message) -> bool:
    """'foydalanuvchi_boshqaruv' huquqi (superadmin doim ega)."""
    user = await db.get_user(message.from_user.id)
    if not user or not user["faol"]:
        await say(message, "❌ Ruxsat yo'q!")
        return False
    if await db.has_permission(message.from_user.id, user["rol"], "foydalanuvchi_boshqaruv"):
        return True
    await say(message, "❌ Sizda foydalanuvchilarni boshqarish huquqi yo'q!")
    return False


async def _cb_ruxsat(callback: CallbackQuery) -> bool:
    user = await db.get_user(callback.from_user.id)
    if not user or not await db.has_permission(
            callback.from_user.id, user["rol"], "foydalanuvchi_boshqaruv"):
        await callback.answer("⛔ Ruxsat yo'q!", show_alert=True)
        return False
    return True


async def _xabar_ber(bot, uid, matn):
    """Foydalanuvchiga uning tilida xabar yuborish (xato bo'lsa jim)."""
    try:
        await bot.send_message(uid, await t(matn, uid))
    except Exception:
        pass


async def _audit(message, amal, tafsilot):
    admin = await db.get_user(message.from_user.id)
    await db.add_audit_log(
        message.from_user.id,
        admin["ism"] if admin else str(message.from_user.id),
        admin["rol"] if admin else "-",
        amal, tafsilot
    )


@router.message(Tkey("👥 Foydalanuvchilar"))
async def foydalanuvchilar(message: Message):
    if not await _ruxsat(message):
        return
    await say(message, "👥 Foydalanuvchilar boshqaruvi:",
              reply_markup=await users_menu(message.from_user.id))


@router.message(Tkey("👥 Foydalanuvchilar ro'yxati"))
async def users_royxati(message: Message):
    if not await _ruxsat(message):
        return
    try:
        users = await db.get_all_users()
        if not users:
            await say(message, "❌ Hali foydalanuvchi yo'q!",
                      reply_markup=await users_menu(message.from_user.id))
            return
        text = "👥 Foydalanuvchilar:\n\n"
        for u in users:
            status = "✅" if u["faol"] else "🚫"
            rol_nomi = ROLLAR_NOMI.get(u["rol"], u["rol"])
            text += (
                f"{status} {esc(u['ism'])} — {rol_nomi}\n"
                f"   <code>{u['id']}</code> @{esc(u['username']) if u['username'] else 'yoq'}\n"
            )
        if len(text) > 4000:
            text = text[:4000] + "\n..."
        await say(message, text, parse_mode="HTML",
                  reply_markup=await users_menu(message.from_user.id))
    except Exception as e:
        await say_error(message, e)


# ── Qo'lda qo'shish ──
@router.message(Tkey("➕ Foydalanuvchi qo'shish"))
async def user_qoshish(message: Message, state: FSMContext):
    if not await _ruxsat(message):
        return
    await state.clear()
    await state.set_state(UserAddState.user_id)
    await say(message, "Yangi foydalanuvchining Telegram ID sini kiriting:\n\n"
                       "💡 U /start bosganida bot sizga ID yuboradi.")


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
        await db.remove_pending(data["user_id"])
        await _audit(message, "Foydalanuvchi qo'shildi",
                     f"{data['ism']} (ID: {data['user_id']}) → {rol}")
        await state.clear()
        await _xabar_ber(message.bot, data["user_id"],
                         "✅ Siz tizimga qo'shildingiz! /start bosing.")
        await say(message,
                  f"✅ Foydalanuvchi qo'shildi!\n👤 {data['ism']}\n"
                  f"🆔 {data['user_id']}\n🔑 {ROLLAR_NOMI[rol]}",
                  reply_markup=await users_menu(message.from_user.id))
    except Exception as e:
        await state.clear()
        await say_error(message, e, reply_markup=await users_menu(message.from_user.id))


# ── Kutilayotgan so'rovlar + onboarding callbacklar ──
@router.message(Tkey("📋 Kutilayotgan so'rovlar"))
async def kutilayotgan(message: Message):
    if not await _ruxsat(message):
        return
    pending = await db.get_pending()
    if not pending:
        await say(message, "✅ Kutilayotgan so'rov yo'q.",
                  reply_markup=await users_menu(message.from_user.id))
        return
    await say(message, f"📋 Kutilayotgan so'rovlar: {len(pending)} ta")
    for p in pending:
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"appr:{p['user_id']}"),
            InlineKeyboardButton(text="❌ Rad etish", callback_data=f"rej:{p['user_id']}"),
        ]])
        await message.answer(
            f"👤 {esc(p['ism'])}\n🆔 <code>{p['user_id']}</code>\n"
            f"@{esc(p['username']) if p['username'] else 'yoq'}",
            parse_mode="HTML", reply_markup=kb
        )


@router.callback_query(lambda c: c.data and c.data.startswith("appr:"))
async def approve_cb(callback: CallbackQuery):
    if not await _cb_ruxsat(callback):
        return
    uid = int(callback.data.split(":")[1])
    p = await db.get_pending_one(uid)
    if not p:
        await callback.answer("So'rov topilmadi", show_alert=True)
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        return
    rows = [[InlineKeyboardButton(text=nomi, callback_data=f"setrol:{uid}:{rol}")]
            for nomi, rol in ROL_MAP.items()]
    await callback.message.edit_text(
        f"👤 {p['ism']} uchun rol tanlang:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows)
    )
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("setrol:"))
async def setrol_cb(callback: CallbackQuery):
    if not await _cb_ruxsat(callback):
        return
    _, uid_s, rol = callback.data.split(":")
    uid = int(uid_s)
    p = await db.get_pending_one(uid)
    ism = p["ism"] if p else str(uid)
    username = p["username"] if p else None
    await db.add_user(uid, ism, username, rol)
    await db.remove_pending(uid)
    admin = await db.get_user(callback.from_user.id)
    await db.add_audit_log(callback.from_user.id, admin["ism"] if admin else str(callback.from_user.id),
                           admin["rol"] if admin else "-", "Foydalanuvchi tasdiqlandi",
                           f"{ism} (ID:{uid}) → {rol}")
    await callback.message.edit_text(f"✅ {ism} qo'shildi: {ROLLAR_NOMI.get(rol, rol)}")
    await callback.answer("✅")
    await _xabar_ber(callback.bot, uid, "✅ Siz tizimga qo'shildingiz! /start bosing.")


@router.callback_query(lambda c: c.data and c.data.startswith("rej:"))
async def reject_cb(callback: CallbackQuery):
    if not await _cb_ruxsat(callback):
        return
    uid = int(callback.data.split(":")[1])
    await db.remove_pending(uid)
    await callback.message.edit_text("❌ So'rov rad etildi.")
    await callback.answer()
    await _xabar_ber(callback.bot, uid, "❌ Ro'yxatdan o'tish so'rovingiz rad etildi.")


# ── Profil ──
@router.message(Tkey("👤 Foydalanuvchi profili"))
async def profil_boshla(message: Message, state: FSMContext):
    if not await _ruxsat(message):
        return
    await state.clear()
    await state.set_state(UserProfileState.user_id)
    await say(message, "Foydalanuvchi ID sini kiriting:")


@router.message(UserProfileState.user_id)
async def profil_korsat(message: Message, state: FSMContext):
    try:
        uid = int(message.text.strip())
    except ValueError:
        await say(message, "❌ Faqat raqam kiriting!")
        return
    await state.clear()
    u = await db.get_user(uid)
    if not u:
        # bloklangan bo'lishi mumkin
        blocked = await db.get_blocked_users()
        u = next((x for x in blocked if x["id"] == uid), None)
    if not u:
        await say(message, "❌ Foydalanuvchi topilmadi!",
                  reply_markup=await users_menu(message.from_user.id))
        return
    s = await db.get_user_stats(uid)
    status = "✅ Faol" if u["faol"] else "🚫 Bloklangan"
    text = (
        f"👤 Profil\n━━━━━━━━━━━━━━━━\n"
        f"Ism: {esc(u['ism'])}\n"
        f"ID: <code>{u['id']}</code>\n"
        f"Username: @{esc(u['username']) if u['username'] else 'yoq'}\n"
        f"Rol: {ROLLAR_NOMI.get(u['rol'], u['rol'])}\n"
        f"Holat: {status}\n"
        f"Qo'shilgan: {_vaqt(u.get('qoshilgan_vaqt'))}\n"
        f"Oxirgi faollik: {_vaqt(u.get('oxirgi_faollik'))}\n\n"
        f"📊 Statistika:\n"
        f"   Ishlab chiqarish: {s['qolip']} qolip (A:{s['A']} B:{s['B']})\n"
        f"   Sotuv: {s['sotuv_qty']} ta = {await val.format_uzs(s['sotuv_rev'])}"
    )
    await say(message, text, parse_mode="HTML",
              reply_markup=await users_menu(message.from_user.id))


# ── Rol o'zgartirish ──
@router.message(Tkey("✏️ Rol o'zgartirish"))
async def rol_ozgartirish(message: Message, state: FSMContext):
    if not await _ruxsat(message):
        return
    try:
        await state.clear()
        users = await db.get_all_users()
        faol_users = [u for u in users if u["faol"] and u["rol"] != "superadmin"]
        if not faol_users:
            await say(message, "❌ O'zgartirish mumkin bo'lgan foydalanuvchi yo'q!",
                      reply_markup=await users_menu(message.from_user.id))
            return
        text = "✏️ Qaysi foydalanuvchi rolini o'zgartirish?\nID raqamini kiriting:\n\n"
        for u in faol_users:
            text += f"🔹 <code>{u['id']}</code> — {esc(u['ism'])} ({ROLLAR_NOMI.get(u['rol'], u['rol'])})\n"
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
        await say(message, f"👤 {target['ism']} uchun yangi rol tanlang:",
                  reply_markup=await rol_menu(message.from_user.id))
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
        await _audit(message, "Rol o'zgartirildi",
                     f"{data['ism']} (ID: {data['user_id']}) → {rol}")
        await state.clear()
        await _xabar_ber(message.bot, data["user_id"],
                         f"🔑 Sizning rolingiz o'zgartirildi: {ROLLAR_NOMI[rol]}")
        await say(message,
                  f"✅ Rol yangilandi!\n👤 {data['ism']}\n🔑 {ROLLAR_NOMI[rol]}",
                  reply_markup=await users_menu(message.from_user.id))
    except Exception as e:
        await state.clear()
        await say_error(message, e, reply_markup=await users_menu(message.from_user.id))


# ── Ismni o'zgartirish ──
@router.message(Tkey("✏️ Ismni o'zgartirish"))
async def ism_ozgartirish(message: Message, state: FSMContext):
    if not await _ruxsat(message):
        return
    await state.clear()
    await state.set_state(UserNameState.user_id)
    await say(message, "Ismi o'zgartiriladigan foydalanuvchi ID sini kiriting:")


@router.message(UserNameState.user_id)
async def ism_ozgartirish_id(message: Message, state: FSMContext):
    try:
        uid = int(message.text.strip())
    except ValueError:
        await say(message, "❌ Faqat raqam kiriting!")
        return
    target = await db.get_user(uid)
    if not target:
        await say(message, "❌ Foydalanuvchi topilmadi!")
        await state.clear()
        return
    await state.update_data(user_id=uid, eski=target["ism"])
    await state.set_state(UserNameState.ism)
    await say(message, f"Yangi ism kiriting:\n(Hozirgi: {target['ism']})")


@router.message(UserNameState.ism)
async def ism_ozgartirish_saqlash(message: Message, state: FSMContext):
    yangi = message.text.strip()
    data = await state.get_data()
    await db.update_user_ism(data["user_id"], yangi)
    await _audit(message, "Ism o'zgartirildi", f"{data['eski']} → {yangi}")
    await state.clear()
    await say(message, f"✅ Ism yangilandi: {yangi}",
              reply_markup=await users_menu(message.from_user.id))


# ── Bloklash ──
@router.message(Tkey("🗑️ Foydalanuvchini bloklash"))
async def user_ochirish(message: Message, state: FSMContext):
    if not await _ruxsat(message):
        return
    try:
        await state.clear()
        users = await db.get_all_users()
        faol_users = [u for u in users if u["faol"] and u["rol"] != "superadmin"]
        if not faol_users:
            await say(message, "❌ Bloklash mumkin bo'lgan foydalanuvchi yo'q!",
                      reply_markup=await users_menu(message.from_user.id))
            return
        text = "🗑️ Qaysi foydalanuvchini bloklash?\nID raqamini kiriting:\n\n"
        for u in faol_users:
            text += f"🔹 <code>{u['id']}</code> — {esc(u['ism'])} ({ROLLAR_NOMI.get(u['rol'], u['rol'])})\n"
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
            await say(message, "❌ Super Admin ni bloklab bo'lmaydi!")
            await state.clear()
            return
        await db.delete_user(user_id)
        await _audit(message, "Foydalanuvchi bloklandi",
                     f"{target['ism']} (ID: {user_id})")
        await state.clear()
        await _xabar_ber(message.bot, user_id, "🚫 Sizning hisobingiz bloklandi.")
        await say(message, f"✅ {target['ism']} bloklandi!",
                  reply_markup=await users_menu(message.from_user.id))
    except ValueError:
        await say(message, "❌ Faqat raqam kiriting!")
        await state.clear()
    except Exception as e:
        await state.clear()
        await say_error(message, e, reply_markup=await users_menu(message.from_user.id))


# ── Tiklash ──
@router.message(Tkey("♻️ Bloklangani tiklash"))
async def user_tiklash(message: Message, state: FSMContext):
    if not await _ruxsat(message):
        return
    await state.clear()
    blocked = await db.get_blocked_users()
    if not blocked:
        await say(message, "✅ Bloklangan foydalanuvchi yo'q.",
                  reply_markup=await users_menu(message.from_user.id))
        return
    text = "♻️ Qaysi foydalanuvchini tiklash?\nID raqamini kiriting:\n\n"
    for u in blocked:
        text += f"🔹 <code>{u['id']}</code> — {esc(u['ism'])} ({ROLLAR_NOMI.get(u['rol'], u['rol'])})\n"
    await state.set_state(UserRestoreState.user_id)
    await say(message, text, parse_mode="HTML")


@router.message(UserRestoreState.user_id)
async def user_tiklash_id(message: Message, state: FSMContext):
    try:
        uid = int(message.text.strip())
    except ValueError:
        await say(message, "❌ Faqat raqam kiriting!")
        await state.clear()
        return
    await db.unblock_user(uid)
    await _audit(message, "Foydalanuvchi tiklandi", f"ID: {uid}")
    await state.clear()
    await _xabar_ber(message.bot, uid, "✅ Hisobingiz qayta tiklandi! /start bosing.")
    await say(message, f"✅ {uid} tiklandi!",
              reply_markup=await users_menu(message.from_user.id))


# ── Audit log ──
@router.message(Tkey("📋 Audit log"))
async def audit_log(message: Message):
    if not await _ruxsat(message):
        return
    try:
        logs = await db.get_audit_log(30)
        if not logs:
            await say(message, "📋 Audit log bo'sh.",
                      reply_markup=await users_menu(message.from_user.id))
            return
        text = "📋 Oxirgi 30 ta amal:\n\n"
        for log in logs:
            vaqt = _vaqt(log["vaqt"], "%d.%m %H:%M")
            rol_nomi = ROLLAR_NOMI.get(log["rol"], log["rol"])
            text += (
                f"🕐 {vaqt} | {esc(log['ism'] or '')} ({rol_nomi})\n"
                f"📌 {log['amal']}\n📝 {esc(log['tafsilot'] or '')}\n\n"
            )
        if len(text) > 4000:
            text = text[:4000] + "\n..."
        await say(message, text, parse_mode="HTML",
                  reply_markup=await users_menu(message.from_user.id))
    except Exception as e:
        await say_error(message, e)



# ── Qidirish ──
@router.message(Tkey("🔎 Qidirish"))
async def qidirish(message: Message, state: FSMContext):
    if not await _ruxsat(message):
        return
    await state.clear()
    await state.set_state(UserSearchState.q)
    await say(message, "🔎 Ism, username yoki ID bo'yicha qidiring:")


@router.message(UserSearchState.q)
async def qidirish_natija(message: Message, state: FSMContext):
    q = message.text.strip().lower()
    await state.clear()
    users = await db.get_all_users()
    natija = []
    for u in users:
        if (q in (u["ism"] or "").lower()
                or q in (u["username"] or "").lower()
                or q in str(u["id"])):
            natija.append(u)
    if not natija:
        await say(message, "❌ Hech narsa topilmadi.",
                  reply_markup=await users_menu(message.from_user.id))
        return
    text = f"🔎 Natija: {len(natija)} ta\n\n"
    for u in natija[:30]:
        status = "✅" if u["faol"] else "🚫"
        text += (f"{status} {esc(u['ism'])} — {ROLLAR_NOMI.get(u['rol'], u['rol'])}\n"
                 f"   <code>{u['id']}</code> @{esc(u['username']) if u['username'] else 'yoq'}\n")
    await say(message, text, parse_mode="HTML",
              reply_markup=await users_menu(message.from_user.id))


# ── Audit CSV ──
@router.message(Tkey("📄 Audit CSV"))
async def audit_csv(message: Message):
    if not await _ruxsat(message):
        return
    logs = await db.get_audit_log(500)
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["Vaqt", "Foydalanuvchi", "Rol", "Amal", "Tafsilot"])
    for log in logs:
        w.writerow([_vaqt(log["vaqt"]), log["ism"] or "", log["rol"] or "",
                    log["amal"] or "", log["tafsilot"] or ""])
    data = ("\ufeff" + out.getvalue()).encode("utf-8")
    cap = await t("📄 Audit log (CSV)", message.from_user.id)
    await message.answer_document(
        BufferedInputFile(data, "audit_log.csv"), caption=cap)


# ── Superadminlikni o'tkazish (faqat superadmin) ──
@router.message(Tkey("🔁 Superadminlikni o'tkazish"))
async def super_transfer(message: Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    if not user or user["rol"] != "superadmin":
        await say(message, "❌ Bu amal faqat Super Admin uchun!")
        return
    await state.clear()
    await state.set_state(SuperTransferState.user_id)
    await say(message,
              "🔁 Yangi Super Admin ID sini kiriting:\n"
              "⚠️ Siz Direktor roliga o'tasiz!")


@router.message(SuperTransferState.user_id)
async def super_transfer_id(message: Message, state: FSMContext):
    try:
        uid = int(message.text.strip())
    except ValueError:
        await say(message, "❌ Faqat raqam kiriting!")
        return
    target = await db.get_user(uid)
    if not target:
        await say(message, "❌ Foydalanuvchi topilmadi!")
        await state.clear()
        return
    if target["rol"] == "superadmin":
        await say(message, "❌ U allaqachon Super Admin!")
        await state.clear()
        return
    await state.update_data(uid=uid, ism=target["ism"])
    await state.set_state(SuperTransferState.confirm)
    kb = await build_keyboard(message.from_user.id, [
        ["✅ Ha, o'tkazish"], ["❌ Yo'q, bekor qilish"]])
    await say(message,
              f"⚠️ DIQQAT!\n{target['ism']} Super Admin bo'ladi, "
              f"siz Direktor bo'lib qolasiz.\nTasdiqlaysizmi?",
              reply_markup=kb)


@router.message(SuperTransferState.confirm)
async def super_transfer_confirm(message: Message, state: FSMContext):
    uz = await canon(message, ["✅ Ha, o'tkazish", "❌ Yo'q, bekor qilish"])
    data = await state.get_data()
    await state.clear()
    if uz != "✅ Ha, o'tkazish":
        await say(message, "❌ Bekor qilindi.",
                  reply_markup=await users_menu(message.from_user.id))
        return
    uid = data["uid"]
    await db.update_user_rol(uid, "superadmin")
    await db.update_user_rol(message.from_user.id, "direktor")
    await db.set_bot_setting("admin_chat_id", str(uid))
    await _audit(message, "Superadminlik o'tkazildi",
                 f"{data['ism']} (ID: {uid}) → superadmin")
    await _xabar_ber(message.bot, uid,
                     "👑 Sizga Super Admin huquqi berildi! /start bosing.")
    await say(message,
              f"✅ Superadminlik {data['ism']} ga o'tkazildi.\n"
              f"Siz endi Direktor. /start bosing.")
