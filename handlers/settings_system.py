"""Sozlamalar → ⚙️ Tizim: hisobot jadvali, obunachilar, PIN, til, tozalash."""
from aiogram import Router
from aiogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import hashlib
import database as db
from translation import (
    Tkey, say, say_error, build_keyboard, t, invalidate_til_cache, prewarm, TIL_NOMLARI,
)
from .settings_common import (
    sozlamalar_menu,
    faqat_superadmin as _faqat_superadmin,
    cb_ok as _cb_ok,
)

router = Router()


class AutoHisobotState(StatesGroup):
    vaqt = State()


class PinTimeoutState(StatesGroup):
    qiymat = State()


async def tizim_submenu(user_id):
    return await build_keyboard(user_id, [
        ["🔔 Hisobot jadvali"],
        ["🔒 PIN kod"],
        ["🌐 Tilni o'zgartirish"],
        ["🗑️ Barcha ma'lumotlarni tozalash"],
        ["⬅️ Sozlamalar"],
    ])


@router.message(Tkey("⚙️ Tizim sozlamalari"))
async def tizim_bolimi(message: Message, user: dict = None):
    if not await _faqat_superadmin(message, user):
        return
    await say(message, "⚙️ Tizim sozlamalari:",
              reply_markup=await tizim_submenu(message.from_user.id))


# ── Hisobot jadvali (avtomatik hisobot) ──
async def hisobot_jadvali_menu(user_id):
    return await build_keyboard(user_id, [
        ["🕐 Kunlik vaqt"],
        ["📅 Haftalik vaqt"],
        ["🗓 Oylik vaqt"],
        ["📨 Obunachilar"],
        ["🏠 Asosiy menyu"],
    ])


async def obuna_menu(user_id):
    return await build_keyboard(user_id, [
        ["➕ Meni qo'shish"],
        ["➖ Meni o'chirish"],
        ["➕ Obunachi qo'shish"],
        ["➖ Obunachi o'chirish"],
        ["🏠 Asosiy menyu"],
    ])


@router.message(Tkey("🔔 Hisobot jadvali"))
async def hisobot_jadvali(message: Message, user: dict = None):
    if not await _faqat_superadmin(message, user):
        return
    kunlik = await db.get_bot_setting("hisobot_vaqti")
    haftalik = await db.get_bot_setting("hisobot_haftalik")
    oylik = await db.get_bot_setting("hisobot_oylik")
    obuna = len(await db.get_hisobot_obunachilar())
    await say(
        message,
        f"🔔 Hisobot jadvali:\n"
        f"🕐 Kunlik: {kunlik or '—'}\n"
        f"📅 Haftalik (dushanba): {haftalik or '—'}\n"
        f"🗓 Oylik (1-kun): {oylik or '—'}\n"
        f"📨 Qo'shimcha obunachilar: {obuna} ta\n\n"
        f"O'zgartirish uchun tanlang:",
        reply_markup=await hisobot_jadvali_menu(message.from_user.id)
    )


async def _vaqt_sorov(message, state, kalit, nomi):
    joriy = await db.get_bot_setting(kalit)
    joriy_text = f"Hozirgi: {joriy}" if joriy else "Belgilanmagan"
    await state.clear()
    await state.update_data(kalit=kalit, nomi=nomi)
    await state.set_state(AutoHisobotState.vaqt)
    await say(
        message,
        f"🔔 {nomi} vaqtini kiriting:\n{joriy_text}\n\n"
        f"Format: HH:MM (masalan 21:00)\nO'chirish uchun: 0"
    )


@router.message(Tkey("🕐 Kunlik vaqt"))
async def kunlik_vaqt(message: Message, state: FSMContext, user: dict = None):
    if not await _faqat_superadmin(message, user):
        return
    await _vaqt_sorov(message, state, "hisobot_vaqti", "Kunlik hisobot")


@router.message(Tkey("📅 Haftalik vaqt"))
async def haftalik_vaqt(message: Message, state: FSMContext, user: dict = None):
    if not await _faqat_superadmin(message, user):
        return
    await _vaqt_sorov(message, state, "hisobot_haftalik", "Haftalik hisobot (dushanba)")


@router.message(Tkey("🗓 Oylik vaqt"))
async def oylik_vaqt(message: Message, state: FSMContext, user: dict = None):
    if not await _faqat_superadmin(message, user):
        return
    await _vaqt_sorov(message, state, "hisobot_oylik", "Oylik hisobot (1-kun)")


@router.message(AutoHisobotState.vaqt)
async def vaqt_saqlash(message: Message, state: FSMContext):
    data = await state.get_data()
    kalit = data.get("kalit", "hisobot_vaqti")
    nomi = data.get("nomi", "Hisobot")
    try:
        text = message.text.strip()
        if text == "0":
            await db.set_bot_setting(kalit, "")
            await state.clear()
            await say(
                message, f"✅ {nomi} o'chirildi!",
                reply_markup=await hisobot_jadvali_menu(message.from_user.id)
            )
            return
        parts = text.split(":")
        if len(parts) != 2:
            raise ValueError
        soat = int(parts[0])
        daqiqa = int(parts[1])
        if not (0 <= soat <= 23 and 0 <= daqiqa <= 59):
            raise ValueError
        vaqt = f"{soat:02d}:{daqiqa:02d}"
        await db.set_bot_setting(kalit, vaqt)
        await state.clear()
        await say(
            message,
            f"✅ {nomi} belgilandi!\n⏰ Soat {vaqt} da yuboriladi.",
            reply_markup=await hisobot_jadvali_menu(message.from_user.id)
        )
    except ValueError:
        await say(message, "❌ Noto'g'ri format!\nTo'g'ri: 21:00 yoki 08:30")


# ── Obunachilar ──
@router.message(Tkey("📨 Obunachilar"))
async def obunachilar(message: Message, user: dict = None):
    if not await _faqat_superadmin(message, user):
        return
    ids = await db.get_hisobot_obunachilar()
    users = await db.get_all_users()
    umap = {u["id"]: u["ism"] for u in users}
    text = "📨 Qo'shimcha obunachilar:\n\n"
    if ids:
        for uid in ids:
            text += f"  • {umap.get(uid, 'Noma`lum')} (<code>{uid}</code>)\n"
    else:
        text += "  (bo'sh)\n"
    text += "\nℹ️ Admin doim hisobot oladi."
    await say(message, text, parse_mode="HTML",
              reply_markup=await obuna_menu(message.from_user.id))


@router.message(Tkey("➕ Meni qo'shish"))
async def meni_qoshish(message: Message, user: dict = None):
    if not await _faqat_superadmin(message, user):
        return
    await db.add_hisobot_obunachi(message.from_user.id)
    await say(message, "✅ Siz obunachilar ro'yxatiga qo'shildingiz!",
              reply_markup=await obuna_menu(message.from_user.id))


@router.message(Tkey("➖ Meni o'chirish"))
async def meni_ochirish(message: Message, user: dict = None):
    if not await _faqat_superadmin(message, user):
        return
    await db.remove_hisobot_obunachi(message.from_user.id)
    await say(message, "✅ Siz ro'yxatdan o'chirildingiz!",
              reply_markup=await obuna_menu(message.from_user.id))


@router.message(Tkey("➕ Obunachi qo'shish"))
async def obunachi_qoshish(message: Message, state: FSMContext, user: dict = None):
    if not await _faqat_superadmin(message, user):
        return
    await state.clear()
    obunalar = set(await db.get_hisobot_obunachilar())
    users = [u for u in await db.get_all_users() if u["faol"] and u["id"] not in obunalar]
    if not users:
        await say(message, "✅ Qo'shish uchun foydalanuvchi yo'q (hammasi obuna).",
                  reply_markup=await obuna_menu(message.from_user.id))
        return
    kb = [[InlineKeyboardButton(text=u["ism"], callback_data=f"obadd:{u['id']}")]
          for u in users[:60]]
    kb.append([InlineKeyboardButton(text="✅ Tayyor", callback_data="ob_done")])
    await message.answer(
        await t("➕ Obunachi qo'shish — foydalanuvchini tanlang:", message.from_user.id),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))


@router.message(Tkey("➖ Obunachi o'chirish"))
async def obunachi_ochirish(message: Message, state: FSMContext, user: dict = None):
    if not await _faqat_superadmin(message, user):
        return
    await state.clear()
    obunalar = await db.get_hisobot_obunachilar()
    if not obunalar:
        await say(message, "📭 Obunachilar yo'q.",
                  reply_markup=await obuna_menu(message.from_user.id))
        return
    users = {u["id"]: u["ism"] for u in await db.get_all_users()}
    kb = [[InlineKeyboardButton(text=str(users.get(uid, uid)), callback_data=f"obdel:{uid}")]
          for uid in obunalar[:60]]
    kb.append([InlineKeyboardButton(text="✅ Tayyor", callback_data="ob_done")])
    await message.answer(
        await t("➖ Obunachini o'chirish — tanlang:", message.from_user.id),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))


@router.callback_query(lambda c: c.data and c.data.startswith("obadd:"))
async def obadd_cb(callback: CallbackQuery):
    if not await _cb_ok(callback):
        return
    uid = int(callback.data.split(":")[1])
    await db.add_hisobot_obunachi(uid)
    obunalar = set(await db.get_hisobot_obunachilar())
    users = [u for u in await db.get_all_users() if u["faol"] and u["id"] not in obunalar]
    kb = [[InlineKeyboardButton(text=u["ism"], callback_data=f"obadd:{u['id']}")]
          for u in users[:60]]
    kb.append([InlineKeyboardButton(text="✅ Tayyor", callback_data="ob_done")])
    try:
        await callback.message.edit_text(
            await t("➕ Obunachi qo'shish (yoki ✅ Tayyor):", callback.from_user.id),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    except Exception:
        pass
    await callback.answer("✅ Qo'shildi")


@router.callback_query(lambda c: c.data and c.data.startswith("obdel:"))
async def obdel_cb(callback: CallbackQuery):
    if not await _cb_ok(callback):
        return
    uid = int(callback.data.split(":")[1])
    await db.remove_hisobot_obunachi(uid)
    obunalar = await db.get_hisobot_obunachilar()
    users = {u["id"]: u["ism"] for u in await db.get_all_users()}
    kb = [[InlineKeyboardButton(text=str(users.get(x, x)), callback_data=f"obdel:{x}")]
          for x in obunalar[:60]]
    kb.append([InlineKeyboardButton(text="✅ Tayyor", callback_data="ob_done")])
    try:
        await callback.message.edit_text(
            await t("➖ Obunachini o'chirish (yoki ✅ Tayyor):", callback.from_user.id),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    except Exception:
        pass
    await callback.answer("✅ O'chirildi")


@router.callback_query(lambda c: c.data == "ob_done")
async def ob_done_cb(callback: CallbackQuery):
    try:
        await callback.message.edit_text(await t("✅ Tayyor.", callback.from_user.id))
    except Exception:
        pass
    await callback.answer()


# ── PIN kod (qulf) — faqat superadmin ──
async def pin_menu(user_id):
    return await build_keyboard(user_id, [
        ["🔑 PIN o'rnatish"],
        ["⏱ Qulflanish vaqti"],
        ["🔓 PIN o'chirish"],
        ["🏠 Asosiy menyu"],
    ])


async def _faqat_super(message: Message, user=None) -> bool:
    if user is None:
        user = await db.get_user(message.from_user.id)
    if not user or user["rol"] != "superadmin":
        await say(message, "❌ Bu amal faqat Super Admin uchun!")
        return False
    return True


@router.message(Tkey("🔒 PIN kod"))
async def pin_kod(message: Message, user: dict = None):
    if not await _faqat_super(message, user):
        return
    bor = await db.get_bot_setting("pin_hash")
    timeout = await db.get_bot_setting("pin_timeout") or "5"
    holat = (f"✅ Yoqilgan (qulflanish: {timeout} daqiqa nofaollik)"
             if bor else "❌ O'chirilgan")
    await say(
        message,
        f"🔒 PIN kod\nHolat: {holat}\n\n"
        f"Nofaollikdan so'ng bot qulflanadi va PIN so'raydi.",
        reply_markup=await pin_menu(message.from_user.id)
    )


# ── PIN o'rnatish (inline keypad — PIN chatda qolmaydi) ──
_setpin = {}  # {user_id: kiritilayotgan raqamlar}


def _setpin_markup():
    def b(matn, kod):
        return InlineKeyboardButton(text=matn, callback_data=kod)
    return InlineKeyboardMarkup(inline_keyboard=[
        [b("1", "setpin_d_1"), b("2", "setpin_d_2"), b("3", "setpin_d_3")],
        [b("4", "setpin_d_4"), b("5", "setpin_d_5"), b("6", "setpin_d_6")],
        [b("7", "setpin_d_7"), b("8", "setpin_d_8"), b("9", "setpin_d_9")],
        [b("⌫", "setpin_del"), b("0", "setpin_d_0"), b("✅", "setpin_ok")],
    ])


async def _setpin_text(uid, entered):
    base = await t("🔑 Yangi PIN (4–8 raqam) — tugmalardan kiriting:", uid)
    dots = ("● " * len(entered)).strip() or "— — — —"
    return f"{base}\n\n{dots}"


@router.message(Tkey("🔑 PIN o'rnatish"))
async def pin_ornatish(message: Message, state: FSMContext, user: dict = None):
    if not await _faqat_super(message, user):
        return
    await state.clear()
    _setpin[message.from_user.id] = ""
    await message.answer(
        await _setpin_text(message.from_user.id, ""),
        reply_markup=_setpin_markup())


@router.callback_query(lambda c: c.data and c.data.startswith("setpin_"))
async def setpin_cb(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user or user["rol"] != "superadmin":
        await callback.answer("❌ Ruxsat yo'q!", show_alert=True)
        return
    uid = callback.from_user.id
    entered = _setpin.get(uid, "")
    data = callback.data

    if data.startswith("setpin_d_"):
        if len(entered) < 8:
            entered += data.rsplit("_", 1)[-1]
    elif data == "setpin_del":
        entered = entered[:-1]
    elif data == "setpin_ok":
        if not (4 <= len(entered) <= 8):
            await callback.answer("❌ PIN 4–8 raqam bo'lsin!", show_alert=True)
            return
        pin_h = hashlib.sha256(entered.encode("utf-8")).hexdigest()
        await db.set_bot_setting("pin_hash", pin_h)
        if not await db.get_bot_setting("pin_timeout"):
            await db.set_bot_setting("pin_timeout", "5")
        # Yangi PIN — saqlangan qulf holatini tozalaymiz (qaytadan so'ralsin)
        try:
            await db.clear_pin_active()
        except Exception:
            pass
        _setpin.pop(uid, None)
        u = await db.get_user(uid)
        await db.add_audit_log(uid, u["ism"] if u else "-",
                               u["rol"] if u else "-",
                               "PIN o'rnatildi/yangilandi", "")
        try:
            await callback.message.edit_text(await t("✅ PIN kod o'rnatildi!", uid))
        except Exception:
            pass
        await callback.message.answer(
            await t("🔒 PIN kod:", uid), reply_markup=await pin_menu(uid))
        await callback.answer()
        return

    _setpin[uid] = entered
    try:
        await callback.message.edit_text(
            await _setpin_text(uid, entered), reply_markup=_setpin_markup())
    except Exception:
        pass
    await callback.answer()


@router.message(Tkey("⏱ Qulflanish vaqti"))
async def pin_timeout(message: Message, state: FSMContext, user: dict = None):
    if not await _faqat_super(message, user):
        return
    joriy = await db.get_bot_setting("pin_timeout") or "5"
    await state.clear()
    await state.set_state(PinTimeoutState.qiymat)
    await say(message, f"Nofaollik vaqtini kiriting (daqiqa, 1–1440):\n"
                       f"Hozirgi: {joriy} daqiqa")


@router.message(PinTimeoutState.qiymat)
async def pin_timeout_saqlash(message: Message, state: FSMContext):
    try:
        m = int(message.text.strip())
        if not (1 <= m <= 1440):
            raise ValueError
        await db.set_bot_setting("pin_timeout", str(m))
        await state.clear()
        await say(message, f"✅ Qulflanish vaqti: {m} daqiqa",
                  reply_markup=await pin_menu(message.from_user.id))
    except ValueError:
        await say(message, "❌ 1 dan 1440 gacha son kiriting!")


@router.message(Tkey("🔓 PIN o'chirish"))
async def pin_ochirish(message: Message, user: dict = None):
    if not await _faqat_super(message, user):
        return
    await db.set_bot_setting("pin_hash", "")
    try:
        await db.clear_pin_active()
    except Exception:
        pass
    await _audit_pin(message, "PIN o'chirildi")
    await say(message, "✅ PIN kod o'chirildi (qulf o'chiq).",
              reply_markup=await pin_menu(message.from_user.id))


async def _audit_pin(message, amal):
    user = await db.get_user(message.from_user.id)
    await db.add_audit_log(message.from_user.id, user["ism"] if user else "-",
                           user["rol"] if user else "-", amal, "")


# ── Barcha ma'lumotlarni tozalash ──
@router.message(Tkey("🗑️ Barcha ma'lumotlarni tozalash"))
async def barchani_tozalash(message: Message, state: FSMContext, user: dict = None):
    if not await _faqat_superadmin(message, user):
        return
    await state.clear()
    keyboard = await build_keyboard(message.from_user.id, [
        ["✅ Ha, tozalash"],
        ["❌ Yo'q, bekor qilish"],
    ])
    await say(
        message,
        "⚠️ DIQQAT!\n\n"
        "Barcha materiallar, formula, ishlab chiqarish "
        "va sotuv ma'lumotlari o'chib ketadi!\n\n"
        "Davom etasizmi?",
        reply_markup=keyboard
    )


@router.message(Tkey("✅ Ha, tozalash"))
async def barchani_tozalash_ha(message: Message):
    try:
        user = await db.get_user(message.from_user.id)
        if not user or user["rol"] != "superadmin":
            await say(message, "❌ Faqat Super Admin tozalashi mumkin!")
            return
        await db.clear_all_data()
        await db.add_audit_log(
            message.from_user.id,
            user["ism"],
            user["rol"],
            "Barcha ma'lumotlar tozalandi",
            "To'liq tizim tozalash"
        )
        await say(
            message,
            "✅ Barcha ma'lumotlar tozalandi!",
            reply_markup=await sozlamalar_menu(message.from_user.id)
        )
    except Exception as e:
        await say_error(message, e)


@router.message(Tkey("❌ Yo'q, bekor qilish"))
async def barchani_tozalash_yoq(message: Message):
    await say(
        message,
        "❌ Bekor qilindi!",
        reply_markup=await sozlamalar_menu(message.from_user.id)
    )


# ── Til o'zgartirish ──
def til_tanlash_keyboard():
    """Til tanlash uchun InlineKeyboard (sozlamalar uchun — slang_ prefiksi)."""
    keyboard = []
    row = []
    for til_kod, til_nomi in TIL_NOMLARI.items():
        row.append(InlineKeyboardButton(text=til_nomi, callback_data=f"slang_{til_kod}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


@router.message(Tkey("🌐 Tilni o'zgartirish"))
async def til_ozgartirish(message: Message, user: dict = None):
    if user is None:
        user = await db.get_user(message.from_user.id)
    hozirgi_til = user.get("til", "uz") if user else "uz"
    til_nomi = TIL_NOMLARI.get(hozirgi_til, "🇺🇿 O'zbek")

    await say(
        message,
        f"🌐 Hozirgi til: {til_nomi}\n\n"
        f"Yangi tilni tanlang:",
        reply_markup=til_tanlash_keyboard()
    )


@router.callback_query(lambda c: c.data and c.data.startswith("slang_"))
async def til_ozgartirish_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    til_kod = callback.data.split("_", 1)[1]

    await db.update_user_til(user_id, til_kod)
    invalidate_til_cache(user_id)
    await prewarm(til_kod)

    xabar = await t("✅ Til o'zgartirildi!", user_id)

    await callback.message.edit_text(xabar)
    sozlamalar_matn = await t("⚙️ Sozlamalar:", user_id)
    await callback.message.answer(
        sozlamalar_matn,
        reply_markup=await sozlamalar_menu(user_id)
    )
    await callback.answer()
