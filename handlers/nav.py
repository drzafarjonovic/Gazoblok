"""
nav.py — inline navigatsiya uchun umumiy yordamchilar (v2.2).

Bot UI inline-birinchi: asosiy menyu Reply bo'lib qoladi (doimo ekran pastida),
undan keyingi barcha bo'lim navigatsiyasi va tanlash inline klaviaturada,
xabar joyida tahrirlanadi (edit-in-place).

Inline callback'lar bot.py dagi PermissionMiddleware'dan o'tmaydi (u faqat
Message'ni tekshiradi), shuning uchun ruxsat shu yerdagi `cb_guard` orqali
har bir navigatsiya callback'ida tekshiriladi.
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import database as db
from translation import t, tarjima_qil, foydalanuvchi_tili


async def cb_guard(callback, *perms):
    """Inline callback ruxsati. user dict qaytaradi yoki None (alert ko'rsatib).

    perms bo'sh bo'lsa — faqat faollik tekshiriladi.
    Berilgan bo'lsa — superadmin yoki perm'lardan KAMIDA BITTASI bo'lsa kifoya.
    """
    user = await db.get_user(callback.from_user.id)
    if not user or not user["faol"]:
        await callback.answer("⛔", show_alert=True)
        return None
    if not perms or user["rol"] == "superadmin":
        return user
    for p in perms:
        if await db.has_permission(callback.from_user.id, user["rol"], p):
            return user
    await callback.answer("⛔ Ruxsat yo'q!", show_alert=True)
    return None


async def tlabel(label: str, til: str) -> str:
    """Statik (kanonik o'zbekcha) tugma matnini foydalanuvchi tiliga o'giradi."""
    return label if til == "uz" else await tarjima_qil(label, til)


async def menu_kb(user_id, static_rows, dynamic_rows=None):
    """
    Inline klaviatura quradi.
      static_rows  — [[(uz_label, callback_data), ...], ...]  (tarjima qilinadi)
      dynamic_rows — [[(raw_label, callback_data), ...], ...] (tarjimasiz: nomlar)
    dynamic_rows static'dan OLDIN joylashtiriladi.
    """
    til = await foydalanuvchi_tili(user_id)
    kb = []
    for row in (dynamic_rows or []):
        kb.append([InlineKeyboardButton(text=lbl, callback_data=cd) for lbl, cd in row])
    for row in static_rows:
        line = []
        for lbl, cd in row:
            line.append(InlineKeyboardButton(text=await tlabel(lbl, til), callback_data=cd))
        kb.append(line)
    return InlineKeyboardMarkup(inline_keyboard=kb)


async def show(callback, text, kb=None):
    """Callback xabarini joyida tahrirlaydi (matn tarjima qilinadi). Bo'lmasa — yangi xabar."""
    tt = await t(text, callback.from_user.id)
    if tt and len(tt) > 4096:
        tt = tt[:4095] + "…"
    try:
        await callback.message.edit_text(tt, reply_markup=kb)
    except Exception:
        try:
            await callback.message.answer(tt, reply_markup=kb)
        except Exception:
            pass


async def send(message, text, kb=None):
    """Yangi inline xabar yuboradi (matn tarjima qilinadi)."""
    tt = await t(text, message.from_user.id)
    if tt and len(tt) > 4096:
        tt = tt[:4095] + "…"
    return await message.answer(tt, reply_markup=kb)
