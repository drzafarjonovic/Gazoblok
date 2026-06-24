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


class UserNameState(StatesGroup):
    ism = State()


class UserSearchState(StatesGroup):
    q = State()


def _vaqt(v, fmt="%d.%m.%Y %H:%M"):
    if hasattr(v, "strftime"):
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc).astimezone(TOSHKENT_TZ)
        return v.strftime(fmt)
    return "—"


async def users_menu(user_id):
    return await build_keyboard(user_id, [
        ["👤 Foydalanuvchilar"],
        ["➕ Foydalanuvchi qo'shish"],
        ["📋 Kutilayotgan so'rovlar"],
        ["🔐 Huquqlar boshqaruvi"],
        ["🔎 Qidirish"],
        ["📋 Audit log"],
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
    try:
        await bot.send_message(uid, await t(matn, uid))
    except Exception:
        pass


async def _audit(message, amal, tafsilot, admin=None):
    if admin is None:
        admin = await db.get_user(message.from_user.id)
    await db.add_audit_log(
        message.from_user.id,
        admin["ism"] if admin else str(message.from_user.id),
        admin["rol"] if admin else "-", amal, tafsilot)


async def _cb_audit(callback, amal, tafsilot):
    admin = await db.get_user(callback.from_user.id)
    await db.add_audit_log(
        callback.from_user.id, admin["ism"] if admin else "-",
        admin["rol"] if admin else "-", amal, tafsilot)


async def _profil_text(uid):
    u = await db.get_user(uid)
    if not u:
        blocked = await db.get_blocked_users()
        u = next((x for x in blocked if x["id"] == uid), None)
    if not u:
        return None
    s = await db.get_user_stats(uid)
    status = "✅ Faol" if u["faol"] else "🚫 Bloklangan"
    return (
        f"👤 Profil\n━━━━━━━━━━━━━━━━\n"
        f"Ism: {esc(u['ism'])}\n"
        f"ID: <code>{u['id']}</code>\n"
        f"Username: @{esc(u['username']) if u['username'] else 'yoq'}\n"
        f"Rol: {ROLLAR_NOMI.get(u['rol'], u['rol'])}\n"
        f"Holat: {status}\n"
        f"Qo'shilgan: {_vaqt(u.get('qoshilgan_vaqt'))}\n"
        f"Oxirgi faollik: {_vaqt(u.get('oxirgi_faollik'))}\n\n"
        f"📊 Statistika:\n"
        f"   Ishlab chiqarish: {s['qolip']} qolip\n"
        f"   Sotuv: {s['sotuv_qty']} ta = {await val.format_uzs(s['sotuv_rev'])}"
    )


@router.message(Tkey("👥 Foydalanuvchilar"))
async def foydalanuvchilar(message: Message, user: dict = None):
    if not await _ruxsat(message, user):
        return
    await say(message, "👥 Foydalanuvchilar boshqaruvi:",
              reply_markup=await users_menu(message.from_user.id))


async def _uview_list_kb():
    users = await db.get_all_users()
    kb = []
    for u in users[:60]:
        belgi = "" if u["faol"] else "🚫 "
        kb.append([InlineKeyboardButton(
            text=f"{belgi}{u['ism']} · {ROLLAR_NOMI.get(u['rol'], u['rol'])}",
            callback_data=f"uview:{u['id']}")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


async def _uview_panel(uid, viewer_id):
    text = await _profil_text(uid)
    if not text:
        return None, None
    u = await db.get_user(uid)
    if not u:
        blocked = await db.get_blocked_users()
        u = next((x for x in blocked if x["id"] == uid), None)
    viewer = await db.get_user(viewer_id)
    is_super = bool(viewer and viewer["rol"] == "superadmin")
    rows = []
    agar_oddiy = u["rol"] != "superadmin"
    pair = []
    if agar_oddiy:
        pair.append(InlineKeyboardButton(text="✏️ Rol", callback_data=f"usr:rol:{uid}"))
    pair.append(InlineKeyboardButton(text="✏️ Ism", callback_data=f"usr:ism:{uid}"))
    rows.append(pair)
    if u["faol"] and agar_oddiy:
        rows.append([InlineKeyboardButton(text="🗑️ Bloklash", callback_data=f"usr:blok:{uid}")])
    if not u["faol"]:
        rows.append([InlineKeyboardButton(text="♻️ Tiklash", callback_data=f"usr:tikla:{uid}")])
    if is_super and agar_oddiy and u["faol"]:
        rows.append([InlineKeyboardButton(
            text="🔁 Superadmin qilish", callback_data=f"usr:super:{uid}")])
    rows.append([InlineKeyboardButton(text="⬅️ Ro'yxat", callback_data="uview_list")])
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(Tkey("👤 Foydalanuvchilar"))
async def foydalanuvchilar_royxati(message: Message, user: dict = None):
    if not await _ruxsat(message, user):
        return
    users = await db.get_all_users()
    if not users:
        await say(message, "❌ Hali foydalanuvchi yo'q!",
                  reply_markup=await users_menu(message.from_user.id))
        return
    await say(message, "👤 Foydalanuvchini tanlang (ko'rish/boshqarish):",
              reply_markup=await _uview_list_kb())


@router.callback_query(lambda c: c.data and c.data.startswith("uview:"))
async def uview_cb(callback: CallbackQuery):
    if not await _cb_ruxsat(callback):
        return
    uid = int(callback.data.split(":")[1])
    text, kb = await _uview_panel(uid, callback.from_user.id)
    if not text:
        await callback.answer("❌ Topilmadi", show_alert=True)
        return
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        pass
    await callback.answer()


@router.callback_query(lambda c: c.data == "uview_list")
async def uview_list_cb(callback: CallbackQuery):
    if not await _cb_ruxsat(callback):
        return
    try:
        await callback.message.edit_text(
            await t("👤 Foydalanuvchini tanlang:", callback.from_user.id),
            reply_markup=await _uview_list_kb())
    except Exception:
        pass
    await callback.answer()


# ── Qo'lda qo'shish (Telegram ID kerak — tashqi foydalanuvchi) ──
@router.message(Tkey("➕ Foydalanuvchi qo'shish"))
async def user_qoshish(message: Message, state: FSMContext, user: dict = None):
    if not await _ruxsat(message, user):
        return
    await state.clear()
    await state.set_state(UserAddState.user_id)
    await say(message, "Yangi foydalanuvchining Telegram ID sini kiriting:\n\n"
                       "💡 U /start bosganida bot ID ni ko'rsatadi.")


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


async def rol_menu(user_id):
    return await build_keyboard(user_id, [
        ["👔 Direktor"], ["📦 Omborchi"], ["🔨 Ishchi"],
        ["💰 Sotuvchi"], ["📊 Hisobchi"], ["🏠 Asosiy menyu"],
    ])


@router.message(UserAddState.rol)
async def user_rol_kiritish(message: Message, state: FSMContext, user: dict = None):
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
                     f"{data['ism']} (ID: {data['user_id']}) → {rol}", admin=user)
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


# ── Kutilayotgan so'rovlar + onboarding ──
@router.message(Tkey("📋 Kutilayotgan so'rovlar"))
async def kutilayotgan(message: Message, user: dict = None):
    if not await _ruxsat(message, user):
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
            parse_mode="HTML", reply_markup=kb)


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
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
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
    await _cb_audit(callback, "Foydalanuvchi tasdiqlandi", f"{ism} (ID:{uid}) → {rol}")
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


# ── Foydalanuvchi paneli amallari (profil panelidan chaqiriladi) ──
@router.callback_query(lambda c: c.data and c.data.startswith("usr:"))
async def usr_cb(callback: CallbackQuery, state: FSMContext):
    if not await _cb_ruxsat(callback):
        return
    _, action, uid_s = callback.data.split(":")
    uid = int(uid_s)

    if action == "profil":
        text = await _profil_text(uid)
        if not text:
            await callback.answer("❌ Topilmadi", show_alert=True)
            return
        try:
            await callback.message.edit_text(text, parse_mode="HTML")
        except Exception:
            pass
        await callback.answer()
        return

    if action == "rol":
        target = await db.get_user(uid)
        if not target or target["rol"] == "superadmin":
            await callback.answer("❌", show_alert=True)
            return
        rows = [[InlineKeyboardButton(text=nomi, callback_data=f"setrol2:{uid}:{rol}")]
                for nomi, rol in ROL_MAP.items()]
        await callback.message.edit_text(
            await t(f"👤 {target['ism']} uchun yangi rol:", callback.from_user.id),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
        await callback.answer()
        return

    if action == "ism":
        target = await db.get_user(uid)
        if not target:
            await callback.answer("❌", show_alert=True)
            return
        await state.update_data(user_id=uid, eski=target["ism"])
        await state.set_state(UserNameState.ism)
        await callback.message.edit_text(
            await t(f"✏️ {target['ism']}\nYangi ism kiriting:", callback.from_user.id))
        await callback.answer()
        return

    if action == "blok":
        target = await db.get_user(uid)
        if not target or target["rol"] == "superadmin":
            await callback.answer("❌", show_alert=True)
            return
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Ha, bloklash", callback_data=f"usrblokok:{uid}"),
            InlineKeyboardButton(text="❌ Yo'q", callback_data="usrcancel"),
        ]])
        await callback.message.edit_text(
            await t(f"🗑 {target['ism']} bloklansinmi?", callback.from_user.id), reply_markup=kb)
        await callback.answer()
        return

    if action == "tikla":
        await db.unblock_user(uid)
        await _cb_audit(callback, "Foydalanuvchi tiklandi", f"ID: {uid}")
        await _xabar_ber(callback.bot, uid, "✅ Hisobingiz qayta tiklandi! /start bosing.")
        await callback.message.edit_text(await t("✅ Tiklandi!", callback.from_user.id))
        await callback.answer("✅")
        return

    if action == "super":
        user = await db.get_user(callback.from_user.id)
        if not user or user["rol"] != "superadmin":
            await callback.answer("❌ Faqat Super Admin", show_alert=True)
            return
        target = await db.get_user(uid)
        if not target or target["rol"] == "superadmin":
            await callback.answer("❌", show_alert=True)
            return
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Ha, o'tkazish", callback_data=f"usrsuperok:{uid}"),
            InlineKeyboardButton(text="❌ Yo'q", callback_data="usrcancel"),
        ]])
        await callback.message.edit_text(
            await t(f"⚠️ {target['ism']} Super Admin bo'ladi, siz Direktor bo'lasiz.\n"
                    f"Tasdiqlaysizmi?", callback.from_user.id), reply_markup=kb)
        await callback.answer()
        return

    await callback.answer()


@router.callback_query(lambda c: c.data == "usrcancel")
async def usrcancel_cb(callback: CallbackQuery):
    try:
        await callback.message.edit_text(await t("❌ Bekor qilindi.", callback.from_user.id))
    except Exception:
        pass
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("setrol2:"))
async def setrol2_cb(callback: CallbackQuery):
    if not await _cb_ruxsat(callback):
        return
    _, uid_s, rol = callback.data.split(":")
    uid = int(uid_s)
    target = await db.get_user(uid)
    if not target or target["rol"] == "superadmin":
        await callback.answer("❌", show_alert=True)
        return
    await db.update_user_rol(uid, rol)
    await _cb_audit(callback, "Rol o'zgartirildi", f"{target['ism']} → {rol}")
    await _xabar_ber(callback.bot, uid,
                     f"🔑 Rolingiz o'zgartirildi: {ROLLAR_NOMI.get(rol, rol)}")
    await callback.message.edit_text(
        await t(f"✅ {target['ism']} → {ROLLAR_NOMI.get(rol, rol)}", callback.from_user.id))
    await callback.answer("✅")


@router.callback_query(lambda c: c.data and c.data.startswith("usrblokok:"))
async def usrblokok_cb(callback: CallbackQuery):
    if not await _cb_ruxsat(callback):
        return
    uid = int(callback.data.split(":")[1])
    target = await db.get_user(uid)
    if target and target["rol"] != "superadmin":
        await db.delete_user(uid)
        await _cb_audit(callback, "Foydalanuvchi bloklandi", f"{target['ism']} (ID:{uid})")
        await _xabar_ber(callback.bot, uid, "🚫 Sizning hisobingiz bloklandi.")
        await callback.message.edit_text(
            await t(f"✅ {target['ism']} bloklandi!", callback.from_user.id))
    else:
        await callback.message.edit_text(await t("❌ Bajarilmadi.", callback.from_user.id))
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("usrsuperok:"))
async def usrsuperok_cb(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user or user["rol"] != "superadmin":
        await callback.answer("❌ Faqat Super Admin", show_alert=True)
        return
    uid = int(callback.data.split(":")[1])
    target = await db.get_user(uid)
    if not target or target["rol"] == "superadmin":
        await callback.answer("❌", show_alert=True)
        return
    await db.update_user_rol(uid, "superadmin")
    await db.update_user_rol(callback.from_user.id, "direktor")
    await db.set_bot_setting("admin_chat_id", str(uid))
    await _cb_audit(callback, "Superadminlik o'tkazildi", f"{target['ism']} (ID:{uid})")
    await _xabar_ber(callback.bot, uid, "👑 Sizga Super Admin huquqi berildi! /start bosing.")
    await callback.message.edit_text(
        await t(f"✅ Superadminlik {target['ism']} ga o'tkazildi. Siz endi Direktor.",
                callback.from_user.id))
    await callback.answer("✅")


@router.message(UserNameState.ism)
async def ism_ozgartirish_saqlash(message: Message, state: FSMContext, user: dict = None):
    yangi = message.text.strip()
    data = await state.get_data()
    if "user_id" not in data:
        await state.clear()
        return
    await db.update_user_ism(data["user_id"], yangi)
    await _audit(message, "Ism o'zgartirildi", f"{data.get('eski', '')} → {yangi}", admin=user)
    await state.clear()
    await say(message, f"✅ Ism yangilandi: {yangi}",
              reply_markup=await users_menu(message.from_user.id))


# ── Qidirish ──
@router.message(Tkey("🔎 Qidirish"))
async def qidirish(message: Message, state: FSMContext, user: dict = None):
    if not await _ruxsat(message, user):
        return
    await state.clear()
    await state.set_state(UserSearchState.q)
    await say(message, "🔎 Ism, username yoki ID bo'yicha qidiring:")


@router.message(UserSearchState.q)
async def qidirish_natija(message: Message, state: FSMContext):
    q = message.text.strip().lower()
    await state.clear()
    users = await db.get_all_users()
    natija = [u for u in users if (q in (u["ism"] or "").lower()
                                   or q in (u["username"] or "").lower()
                                   or q in str(u["id"]))]
    if not natija:
        await say(message, "❌ Hech narsa topilmadi.",
                  reply_markup=await users_menu(message.from_user.id))
        return
    text = f"🔎 Natija: {len(natija)} ta\n\n"
    for u in natija[:30]:
        status = "✅" if u["faol"] else "🚫"
        text += (f"{status} {esc(u['ism'])} — {ROLLAR_NOMI.get(u['rol'], u['rol'])}\n"
                 f"   <code>{u['id']}</code> "
                 f"@{esc(u['username']) if u['username'] else 'yoq'}\n")
    await say(message, text, parse_mode="HTML",
              reply_markup=await users_menu(message.from_user.id))


# ── Audit log ──
@router.message(Tkey("📋 Audit log"))
async def audit_log(message: Message, user: dict = None):
    if not await _ruxsat(message, user):
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
            text += (f"🕐 {vaqt} | {esc(log['ism'] or '')} ({rol_nomi})\n"
                     f"📌 {log['amal']}\n📝 {esc(log['tafsilot'] or '')}\n\n")
        if len(text) > 4000:
            text = text[:4000] + "\n..."
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="📄 CSV yuklab olish", callback_data="auditcsv")]])
        await say(message, text, parse_mode="HTML", reply_markup=kb)
    except Exception as e:
        await say_error(message, e)


@router.callback_query(lambda c: c.data == "auditcsv")
async def auditcsv_cb(callback: CallbackQuery):
    if not await _cb_ruxsat(callback):
        return
    logs = await db.get_audit_log(500)
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["Vaqt", "Foydalanuvchi", "Rol", "Amal", "Tafsilot"])
    for log in logs:
        w.writerow([_vaqt(log["vaqt"]), log["ism"] or "", log["rol"] or "",
                    log["amal"] or "", log["tafsilot"] or ""])
    data = ("\ufeff" + out.getvalue()).encode("utf-8")
    cap = await t("📄 Audit log (CSV)", callback.from_user.id)
    await callback.message.answer_document(
        BufferedInputFile(data, "audit_log.csv"), caption=cap)
    await callback.answer()
