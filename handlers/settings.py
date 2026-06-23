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

router = Router()


class MaterialState(StatesGroup):
    nomi = State()
    qoldiq = State()
    birlik = State()


class MaterialEditState(StatesGroup):
    material_id = State()
    nomi = State()
    qoldiq = State()
    birlik = State()


class MaterialDeleteState(StatesGroup):
    material_id = State()


class FormulaState(StatesGroup):
    miqdor = State()
    birlik = State()


class MinChegaraState(StatesGroup):
    miqdor = State()


class AutoHisobotState(StatesGroup):
    vaqt = State()


class ObunaState(StatesGroup):
    qoshish = State()
    ochirish = State()


class PinState(StatesGroup):
    kod = State()


class PinTimeoutState(StatesGroup):
    qiymat = State()


async def sozlamalar_menu(user_id):
    return await build_keyboard(user_id, [
        ["🏭 Mahsulot boshqaruvi"],
        ["📦 Materiallar"],
        ["💵 Narxlar va valyuta"],
        ["🔔 Hisobot jadvali"],
        ["🔒 PIN kod"],
        ["🌐 Tilni o'zgartirish"],
        ["🗑️ Barcha ma'lumotlarni tozalash"],
        ["🏠 Asosiy menyu"],
    ])


async def materiallar_submenu(user_id):
    return await build_keyboard(user_id, [
        ["➕ Material qo'shish"],
        ["📦 Materiallar ro'yxati"],
        ["✏️ Materialni tahrirlash"],
        ["🗑️ Materialni o'chirish"],
        ["⚠️ Minimum chegara"],
        ["⬅️ Sozlamalar"],
    ])


async def _faqat_superadmin(message: Message) -> bool:
    """Sozlamalar — 'sozlama_boshqaruv' huquqi (superadmin doim ega)."""
    user = await db.get_user(message.from_user.id)
    if not user or not user["faol"]:
        await say(message, "❌ Ruxsat yo'q!")
        return False
    if await db.has_permission(message.from_user.id, user["rol"], "sozlama_boshqaruv"):
        return True
    await say(message, "❌ Sizda sozlamalarni boshqarish huquqi yo'q!")
    return False


@router.message(Tkey("⚙️ Sozlamalar"))
async def sozlamalar(message: Message):
    if not await _faqat_superadmin(message):
        return
    await say(
        message,
        "⚙️ Sozlamalar bo'limi:",
        reply_markup=await sozlamalar_menu(message.from_user.id)
    )


@router.message(Tkey("📦 Materiallar"))
async def materiallar_bolimi(message: Message):
    if not await _faqat_superadmin(message):
        return
    await say(message, "📦 Materiallar bo'limi:",
              reply_markup=await materiallar_submenu(message.from_user.id))


@router.message(Tkey("⬅️ Sozlamalar"))
async def orqaga_sozlamalar(message: Message):
    if not await _faqat_superadmin(message):
        return
    await say(message, "⚙️ Sozlamalar bo'limi:",
              reply_markup=await sozlamalar_menu(message.from_user.id))


# ── Material qo'shish ──
@router.message(Tkey("➕ Material qo'shish"))
async def material_qoshish(message: Message, state: FSMContext):
    if not await _faqat_superadmin(message):
        return
    await state.clear()
    await state.set_state(MaterialState.nomi)
    await say(message, "Material nomini kiriting:\nMisol: Sement")


@router.message(MaterialState.nomi)
async def material_nomi(message: Message, state: FSMContext):
    await state.update_data(nomi=message.text.strip())
    await state.set_state(MaterialState.qoldiq)
    await say(message, "Hozir omborda qancha bor?\nMisol: 30")


@router.message(MaterialState.qoldiq)
async def material_qoldiq(message: Message, state: FSMContext):
    try:
        qoldiq = float(message.text.replace(",", "."))
        if qoldiq < 0:
            raise ValueError
        await state.update_data(qoldiq=qoldiq)
        await state.set_state(MaterialState.birlik)
        await say(
            message,
            "Birligini kiriting:\n"
            "Misol: tonna, kg, g, litr, ml, meshok"
        )
    except ValueError:
        await say(message, "❌ Faqat musbat son kiriting! Misol: 30")


@router.message(MaterialState.birlik)
async def material_birlik(message: Message, state: FSMContext):
    try:
        birlik = message.text.strip()
        if not db.birlik_qollab_quvvatlanadimi(birlik):
            await say(
                message,
                "❌ Birlik tanilmadi!\n"
                "Og'irlik: tonna, kg, g, gramm, mg, meshok\n"
                "Hajm: litr, ml, m3, kubometr\n\n"
                "Qaytadan kiriting:"
            )
            return
        data = await state.get_data()
        await db.add_material(data["nomi"], data["qoldiq"], birlik)

        user = await db.get_user(message.from_user.id)
        await db.add_audit_log(
            message.from_user.id,
            user["ism"] if user else str(message.from_user.id),
            user["rol"] if user else "-",
            "Material qo'shildi",
            f"{data['nomi']}: {data['qoldiq']} {birlik}"
        )
        await state.clear()
        await say(
            message,
            f"✅ {data['nomi']} qo'shildi!\n"
            f"Miqdor: {data['qoldiq']} {birlik}",
            reply_markup=await sozlamalar_menu(message.from_user.id)
        )
    except Exception as e:
        await state.clear()
        await say_error(
            message, e,
            reply_markup=await sozlamalar_menu(message.from_user.id)
        )


# ── Materiallar ro'yxati ──
@router.message(Tkey("📦 Materiallar ro'yxati"))
async def materiallar_royxati(message: Message):
    if not await _faqat_superadmin(message):
        return
    try:
        materials = await db.get_materials()
        if not materials:
            await say(
                message,
                "❌ Hali material kiritilmagan!",
                reply_markup=await sozlamalar_menu(message.from_user.id)
            )
            return
        text = "📦 Materiallar:\n\n"
        for m in materials:
            qoldiq_asl = db.asosiydan_birlikga(m[2], m[4])
            text += f"🔹 {m[0]}. {m[1]} — {qoldiq_asl:.2f} {m[4]}\n"
        await say(message, text, reply_markup=await sozlamalar_menu(message.from_user.id))
    except Exception as e:
        await say_error(message, e)


# ── Materialni tahrirlash ──
async def _material_inline(prefix):
    """Materiallar ro'yxati inline tugmalar sifatida."""
    materials = await db.get_materials()
    kb = []
    for m in materials:
        qoldiq_asl = db.asosiydan_birlikga(m[2], m[4])
        kb.append([InlineKeyboardButton(
            text=f"{m[1]} — {qoldiq_asl:.0f} {m[4]}",
            callback_data=f"{prefix}:{m[0]}")])
    return InlineKeyboardMarkup(inline_keyboard=kb), materials


@router.message(Tkey("✏️ Materialni tahrirlash"))
async def material_tahrirlash(message: Message, state: FSMContext):
    if not await _faqat_superadmin(message):
        return
    await state.clear()
    kb, materials = await _material_inline("matedit")
    if not materials:
        await say(message, "❌ Hali material kiritilmagan!",
                  reply_markup=await sozlamalar_menu(message.from_user.id))
        return
    await say(message, "✏️ Qaysi materialni tahrirlash?", reply_markup=kb)


@router.callback_query(lambda c: c.data and c.data.startswith("matedit:"))
async def matedit_cb(callback: CallbackQuery, state: FSMContext):
    if not await _cb_ok(callback):
        return
    material_id = int(callback.data.split(":", 1)[1])
    materials = await db.get_materials()
    material = next((m for m in materials if m[0] == material_id), None)
    if not material:
        await callback.answer("❌ Topilmadi", show_alert=True)
        return
    await state.update_data(material_id=material_id, eski_nomi=material[1])
    await state.set_state(MaterialEditState.nomi)
    try:
        await callback.message.edit_text(await t(
            f"✏️ {material[1]}\nYangi nomni kiriting:", callback.from_user.id))
    except Exception:
        pass
    await callback.answer()


@router.message(MaterialEditState.nomi)
async def material_tahrirlash_nomi(message: Message, state: FSMContext):
    await state.update_data(nomi=message.text.strip())
    await state.set_state(MaterialEditState.qoldiq)
    await say(message, "Yangi qoldiq miqdorini kiriting:\nMisol: 25")


@router.message(MaterialEditState.qoldiq)
async def material_tahrirlash_qoldiq(message: Message, state: FSMContext):
    try:
        qoldiq = float(message.text.replace(",", "."))
        if qoldiq < 0:
            raise ValueError
        await state.update_data(qoldiq=qoldiq)
        await state.set_state(MaterialEditState.birlik)
        await say(message, "Yangi birlikni kiriting:\nMisol: tonna, kg, litr")
    except ValueError:
        await say(message, "❌ Faqat musbat son kiriting!")


@router.message(MaterialEditState.birlik)
async def material_tahrirlash_birlik(message: Message, state: FSMContext):
    try:
        birlik = message.text.strip()
        if not db.birlik_qollab_quvvatlanadimi(birlik):
            await say(
                message,
                "❌ Birlik tanilmadi!\n"
                "Og'irlik: tonna, kg, g, gramm, mg, meshok\n"
                "Hajm: litr, ml, m3, kubometr\n\n"
                "Qaytadan kiriting:"
            )
            return
        data = await state.get_data()
        await db.update_material(
            data["material_id"],
            data["nomi"],
            data["qoldiq"],
            birlik
        )
        user = await db.get_user(message.from_user.id)
        await db.add_audit_log(
            message.from_user.id,
            user["ism"] if user else str(message.from_user.id),
            user["rol"] if user else "-",
            "Material tahrirlandi",
            f"{data['eski_nomi']} → {data['nomi']}: {data['qoldiq']} {birlik}"
        )
        await state.clear()
        await say(
            message,
            f"✅ Material yangilandi!\n"
            f"{data['nomi']} — {data['qoldiq']} {birlik}",
            reply_markup=await sozlamalar_menu(message.from_user.id)
        )
    except Exception as e:
        await state.clear()
        await say_error(
            message, e,
            reply_markup=await sozlamalar_menu(message.from_user.id)
        )


# ── Materialni o'chirish ──
@router.message(Tkey("🗑️ Materialni o'chirish"))
async def material_ochirish(message: Message, state: FSMContext):
    if not await _faqat_superadmin(message):
        return
    await state.clear()
    kb, materials = await _material_inline("matdel")
    if not materials:
        await say(message, "❌ Hali material kiritilmagan!",
                  reply_markup=await sozlamalar_menu(message.from_user.id))
        return
    await say(message, "🗑️ Qaysi materialni o'chirish?", reply_markup=kb)


@router.callback_query(lambda c: c.data and c.data.startswith("matdel:"))
async def matdel_cb(callback: CallbackQuery):
    if not await _cb_ok(callback):
        return
    mid = int(callback.data.split(":", 1)[1])
    materials = await db.get_materials()
    material = next((m for m in materials if m[0] == mid), None)
    if not material:
        await callback.answer("❌ Topilmadi", show_alert=True)
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Ha, o'chirish", callback_data=f"matdelok:{mid}"),
        InlineKeyboardButton(text="❌ Yo'q", callback_data="matdelno"),
    ]])
    try:
        await callback.message.edit_text(await t(
            f"🗑️ '{material[1]}' o'chirilsinmi?\n"
            f"(Formuladagi ishlatilishi ham olib tashlanadi)", callback.from_user.id),
            reply_markup=kb)
    except Exception:
        pass
    await callback.answer()


@router.callback_query(lambda c: c.data == "matdelno")
async def matdelno_cb(callback: CallbackQuery):
    try:
        await callback.message.edit_text(await t("❌ Bekor qilindi.", callback.from_user.id))
    except Exception:
        pass
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("matdelok:"))
async def matdelok_cb(callback: CallbackQuery):
    if not await _cb_ok(callback):
        return
    mid = int(callback.data.split(":", 1)[1])
    materials = await db.get_materials()
    material = next((m for m in materials if m[0] == mid), None)
    if material:
        await db.delete_material(mid)
        user = await db.get_user(callback.from_user.id)
        await db.add_audit_log(
            callback.from_user.id, user["ism"] if user else "-",
            user["rol"] if user else "-", "Material o'chirildi",
            f"{material[1]} o'chirildi")
        msg = await t(f"✅ {material[1]} o'chirildi!", callback.from_user.id)
    else:
        msg = await t("❌ Material topilmadi.", callback.from_user.id)
    try:
        await callback.message.edit_text(msg)
    except Exception:
        pass
    await callback.answer()


# (Eski global "Qolip formulasi" olib tashlandi — endi har mahsulot uchun
#  "🏭 Mahsulot boshqaruvi" bo'limida (fayl oxirida) sozlanadi.)


# ── Minimum chegara (tanlab tahrirlash — inline) ──
async def _minch_kb(user_id):
    materials = await db.get_materials()
    settings_rows = await db.get_settings()
    minmap = {s[3]: s[1] for s in settings_rows}
    kb = []
    for m in materials:
        min_base = minmap.get(m[0])
        if min_base and min_base > 0:
            asl = db.asosiydan_birlikga(min_base, m[4])
            belgi = f"{asl:.0f} {m[4]}"
        else:
            belgi = "—"
        kb.append([InlineKeyboardButton(
            text=f"{m[1]}: {belgi}", callback_data=f"minch:{m[0]}")])
    kb.append([InlineKeyboardButton(text="✅ Tayyor", callback_data="minch_done")])
    return InlineKeyboardMarkup(inline_keyboard=kb), materials


@router.message(Tkey("⚠️ Minimum chegara"))
async def min_chegara(message: Message, state: FSMContext):
    if not await _faqat_superadmin(message):
        return
    await state.clear()
    kb, materials = await _minch_kb(message.from_user.id)
    if not materials:
        await say(message, "❌ Avval material qo'shing!",
                  reply_markup=await materiallar_submenu(message.from_user.id))
        return
    await say(message,
              "⚠️ Minimum chegara\nO'zgartirish uchun materialni tanlang:",
              reply_markup=kb)


@router.callback_query(lambda c: c.data == "minch_done")
async def minch_done(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await callback.message.edit_text(await t("✅ Tayyor.", callback.from_user.id))
    except Exception:
        pass
    await callback.message.answer(
        await t("📦 Materiallar bo'limi:", callback.from_user.id),
        reply_markup=await materiallar_submenu(callback.from_user.id))
    await callback.answer()


@router.callback_query(lambda c: c.data == "minch_back")
async def minch_back(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    kb, _ = await _minch_kb(callback.from_user.id)
    try:
        await callback.message.edit_text(
            await t("⚠️ Minimum chegara — materialni tanlang:", callback.from_user.id),
            reply_markup=kb)
    except Exception:
        pass
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("minch:"))
async def minch_cb(callback: CallbackQuery, state: FSMContext):
    if not await _cb_ok(callback):
        return
    mid = int(callback.data.split(":", 1)[1])
    materials = await db.get_materials()
    m = next((x for x in materials if x[0] == mid), None)
    if not m:
        await callback.answer("❌", show_alert=True)
        return
    await state.update_data(minch_mid=mid, minch_nomi=m[1], minch_birlik=m[4])
    await state.set_state(MinChegaraState.miqdor)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="❌ Bekor", callback_data="minch_back")]])
    try:
        await callback.message.edit_text(await t(
            f"⚠️ {m[1]} uchun minimum chegara?\n"
            f"(Birlik: {m[4]}; 0 = chegara o'chiriladi)\nMisol: 5",
            callback.from_user.id), reply_markup=kb)
    except Exception:
        pass
    await callback.answer()


@router.message(MinChegaraState.miqdor)
async def min_chegara_miqdor(message: Message, state: FSMContext):
    data = await state.get_data()
    if "minch_mid" not in data:
        await state.clear()
        return
    try:
        miqdor = float(message.text.replace(",", "."))
        if miqdor < 0:
            raise ValueError
    except (ValueError, AttributeError):
        await say(message, "❌ Faqat musbat son kiriting! Misol: 5")
        return
    min_asosiy, _ = db.birlikni_asosiyga(miqdor, data["minch_birlik"])
    await db.set_min_chegara(data["minch_mid"], min_asosiy)
    await state.clear()
    kb, _ = await _minch_kb(message.from_user.id)
    await say(message,
              f"✅ {data['minch_nomi']} chegarasi saqlandi.\nYana o'zgartirish uchun tanlang:",
              reply_markup=kb)


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
async def hisobot_jadvali(message: Message):
    if not await _faqat_superadmin(message):
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
async def kunlik_vaqt(message: Message, state: FSMContext):
    if not await _faqat_superadmin(message):
        return
    await _vaqt_sorov(message, state, "hisobot_vaqti", "Kunlik hisobot")


@router.message(Tkey("📅 Haftalik vaqt"))
async def haftalik_vaqt(message: Message, state: FSMContext):
    if not await _faqat_superadmin(message):
        return
    await _vaqt_sorov(message, state, "hisobot_haftalik", "Haftalik hisobot (dushanba)")


@router.message(Tkey("🗓 Oylik vaqt"))
async def oylik_vaqt(message: Message, state: FSMContext):
    if not await _faqat_superadmin(message):
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
async def obunachilar(message: Message):
    if not await _faqat_superadmin(message):
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
async def meni_qoshish(message: Message):
    if not await _faqat_superadmin(message):
        return
    await db.add_hisobot_obunachi(message.from_user.id)
    await say(message, "✅ Siz obunachilar ro'yxatiga qo'shildingiz!",
              reply_markup=await obuna_menu(message.from_user.id))


@router.message(Tkey("➖ Meni o'chirish"))
async def meni_ochirish(message: Message):
    if not await _faqat_superadmin(message):
        return
    await db.remove_hisobot_obunachi(message.from_user.id)
    await say(message, "✅ Siz ro'yxatdan o'chirildingiz!",
              reply_markup=await obuna_menu(message.from_user.id))


@router.message(Tkey("➕ Obunachi qo'shish"))
async def obunachi_qoshish(message: Message, state: FSMContext):
    if not await _faqat_superadmin(message):
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
async def obunachi_ochirish(message: Message, state: FSMContext):
    if not await _faqat_superadmin(message):
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


async def _faqat_super(message: Message) -> bool:
    user = await db.get_user(message.from_user.id)
    if not user or user["rol"] != "superadmin":
        await say(message, "❌ Bu amal faqat Super Admin uchun!")
        return False
    return True


@router.message(Tkey("🔒 PIN kod"))
async def pin_kod(message: Message):
    if not await _faqat_super(message):
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
async def pin_ornatish(message: Message, state: FSMContext):
    if not await _faqat_super(message):
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
async def pin_timeout(message: Message, state: FSMContext):
    if not await _faqat_super(message):
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
async def pin_ochirish(message: Message):
    if not await _faqat_super(message):
        return
    await db.set_bot_setting("pin_hash", "")
    await _audit_pin(message, "PIN o'chirildi")
    await say(message, "✅ PIN kod o'chirildi (qulf o'chiq).",
              reply_markup=await pin_menu(message.from_user.id))


async def _audit_pin(message, amal):
    user = await db.get_user(message.from_user.id)
    await db.add_audit_log(message.from_user.id, user["ism"] if user else "-",
                           user["rol"] if user else "-", amal, "")


# ── Barcha ma'lumotlarni tozalash ──
@router.message(Tkey("🗑️ Barcha ma'lumotlarni tozalash"))
async def barchani_tozalash(message: Message, state: FSMContext):
    if not await _faqat_superadmin(message):
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
        if len(row) == 2:  # 2 ta tugma bir qatorda
            keyboard.append(row)
            row = []
    if row:  # Oxirgi qator
        keyboard.append(row)
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


@router.message(Tkey("🌐 Tilni o'zgartirish"))
async def til_ozgartirish(message: Message):
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

    # Tilni saqlash
    await db.update_user_til(user_id, til_kod)
    invalidate_til_cache(user_id)
    await prewarm(til_kod)

    # Tasdiqlash (yangi tilda)
    xabar = await t("✅ Til o'zgartirildi!", user_id)

    await callback.message.edit_text(xabar)
    sozlamalar_matn = await t("⚙️ Sozlamalar:", user_id)
    await callback.message.answer(
        sozlamalar_matn,
        reply_markup=await sozlamalar_menu(user_id)
    )
    await callback.answer()



# ════════════════════════════════════════════════════════════════════
# 🏭 MAHSULOT BOSHQARUVI (to'liq dinamik)
# ════════════════════════════════════════════════════════════════════
class MahsulotState(StatesGroup):
    nomi = State()
    emoji = State()


class MahsulotRename(StatesGroup):
    nomi = State()
    emoji = State()


class BlokState(StatesGroup):
    kod = State()
    nomi = State()
    olcham = State()
    dona = State()


class ShablonState(StatesGroup):
    nomi = State()
    chiqim = State()


def _slug(s):
    out = []
    for ch in (s or "").lower():
        if ch.isalnum() and ord(ch) < 128:
            out.append(ch)
        elif out and out[-1] != "_":
            out.append("_")
    res = "".join(out).strip("_")
    return res or "mahsulot"


async def _unique_kod(base):
    kod = base
    i = 1
    while await db.get_mahsulot_by_kod(kod):
        i += 1
        kod = f"{base}{i}"
    return kod


async def _cb_ok(callback: CallbackQuery) -> bool:
    user = await db.get_user(callback.from_user.id)
    if not user or not user["faol"]:
        await callback.answer("❌", show_alert=True)
        return False
    if user["rol"] == "superadmin" or await db.has_permission(
            callback.from_user.id, user["rol"], "sozlama_boshqaruv"):
        return True
    await callback.answer("❌ Ruxsat yo'q!", show_alert=True)
    return False


async def _mb_root_kb():
    prods = await db.get_mahsulotlar(faqat_faol=False)
    kb = []
    for p in prods:
        belgi = "" if p["faol"] else " (arxiv)"
        kb.append([InlineKeyboardButton(
            text=f"{p['emoji']} {p['nomi']}{belgi}",
            callback_data=f"mb_open:{p['id']}")])
    kb.append([InlineKeyboardButton(text="➕ Yangi mahsulot", callback_data="mb_add")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


async def _mb_detail(pid):
    p = await db.get_mahsulot(pid)
    if not p:
        return "❌ Mahsulot topilmadi.", InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Ortga", callback_data="mb_root")]])
    bloklar = await db.get_bloklar(pid)
    shablonlar = await db.get_shablonlar(pid)
    formula = await db.get_qolip_formula(pid)

    text = f"{p['emoji']} {p['nomi']}"
    text += "" if p["faol"] else "  (arxivlangan)"
    text += "\n\n👷 Ish haqi (1 qolip): " + f"{p['ishchi_haqi']:.0f} so'm\n"
    text += f"🛠 Qo'shimcha (1 qolip): {p['qoshimcha_xarajat']:.0f} so'm\n"
    text += "   (narxlar 💵 Narxlar va valyuta bo'limida)\n\n"

    text += "🧱 Bloklar:\n"
    if bloklar:
        for b in bloklar:
            text += (f"   • {b['nomi']} [{b['kod']}] — 1 qolipga "
                     f"{b['qolip_dona']:.0f} dona\n")
    else:
        text += "   (yo'q)\n"

    text += "\n📦 Shablonlar:\n"
    if shablonlar:
        for s in shablonlar:
            ch = ", ".join(f"{c['soni']}×{c['block_kod']}" for c in s["chiqim"])
            text += f"   • {s['nomi']}: {ch or 'bo`sh'}\n"
    else:
        text += "   (yo'q)\n"

    text += "\n📋 Formula (1 qolipga):\n"
    if formula:
        for f in formula:
            text += f"   • {f[0]}: {f[1]} {f[2]}\n"
    else:
        text += "   (yo'q)\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧱 Bloklar", callback_data=f"mb_blk:{pid}"),
         InlineKeyboardButton(text="📦 Shablonlar", callback_data=f"mb_shb:{pid}")],
        [InlineKeyboardButton(text="📋 Formula", callback_data=f"mb_frm:{pid}")],
        [InlineKeyboardButton(text="✏️ Nomi", callback_data=f"mb_ren:{pid}"),
         InlineKeyboardButton(
             text=("🗑 Arxivlash" if p["faol"] else "♻️ Faollashtirish"),
             callback_data=f"mb_arch:{pid}")],
        [InlineKeyboardButton(text="⬅️ Ortga", callback_data="mb_root")],
    ])
    return text, kb


async def _mb_blk_view(pid):
    bloklar = await db.get_bloklar(pid)
    text = "🧱 Bloklar (o'chirish uchun bosing):\n\n"
    if not bloklar:
        text += "   (yo'q)\n"
    kb = []
    for b in bloklar:
        kb.append([InlineKeyboardButton(
            text=f"🗑 {b['nomi']} [{b['kod']}]",
            callback_data=f"mb_blkdel:{b['id']}")])
    kb.append([InlineKeyboardButton(text="➕ Blok qo'shish", callback_data=f"mb_blkadd:{pid}")])
    kb.append([InlineKeyboardButton(text="⬅️ Ortga", callback_data=f"mb_open:{pid}")])
    return text, InlineKeyboardMarkup(inline_keyboard=kb)


async def _mb_shb_view(pid):
    shablonlar = await db.get_shablonlar(pid)
    text = "📦 Shablonlar (o'chirish uchun bosing):\n\n"
    if not shablonlar:
        text += "   (yo'q)\n"
    kb = []
    for s in shablonlar:
        ch = ", ".join(f"{c['soni']}×{c['block_kod']}" for c in s["chiqim"])
        kb.append([InlineKeyboardButton(
            text=f"🗑 {s['nomi']} ({ch or 'bo`sh'})",
            callback_data=f"mb_shbdel:{s['id']}")])
    kb.append([InlineKeyboardButton(text="➕ Shablon qo'shish", callback_data=f"mb_shbadd:{pid}")])
    kb.append([InlineKeyboardButton(text="⬅️ Ortga", callback_data=f"mb_open:{pid}")])
    return text, InlineKeyboardMarkup(inline_keyboard=kb)


@router.message(Tkey("🏭 Mahsulot boshqaruvi"))
async def mahsulot_boshqaruvi(message: Message, state: FSMContext):
    if not await _faqat_superadmin(message):
        return
    await state.clear()
    xabar = await t("🏭 Mahsulot boshqaruvi\nMahsulotni tanlang yoki yangi qo'shing:",
                    message.from_user.id)
    await message.answer(xabar, reply_markup=await _mb_root_kb())


@router.callback_query(lambda c: c.data and c.data.startswith("mb_"))
async def mb_callback(callback: CallbackQuery, state: FSMContext):
    if not await _cb_ok(callback):
        return
    action, _, arg = callback.data.partition(":")
    aid = int(arg) if arg.isdigit() else None

    if action == "mb_root":
        await state.clear()
        await callback.message.edit_text(
            "🏭 Mahsulot boshqaruvi\nMahsulotni tanlang yoki yangi qo'shing:",
            reply_markup=await _mb_root_kb())
        await callback.answer()
        return

    if action == "mb_open":
        await state.clear()
        text, kb = await _mb_detail(aid)
        await callback.message.edit_text(text, reply_markup=kb)
        await callback.answer()
        return

    if action == "mb_blk":
        text, kb = await _mb_blk_view(aid)
        await callback.message.edit_text(text, reply_markup=kb)
        await callback.answer()
        return

    if action == "mb_shb":
        text, kb = await _mb_shb_view(aid)
        await callback.message.edit_text(text, reply_markup=kb)
        await callback.answer()
        return

    if action == "mb_arch":
        p = await db.get_mahsulot(aid)
        if p:
            await db.set_mahsulot_faol(aid, not p["faol"])
        text, kb = await _mb_detail(aid)
        await callback.message.edit_text(text, reply_markup=kb)
        await callback.answer("✅")
        return

    if action == "mb_blkdel":
        blok = await db.get_blok_by_id(aid)
        if not blok:
            await callback.answer("❌", show_alert=True)
            return
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Ha, o'chirish", callback_data=f"mb_blkdelok:{aid}"),
            InlineKeyboardButton(text="⬅️ Yo'q", callback_data=f"mb_blk:{blok['product_id']}"),
        ]])
        await callback.message.edit_text(
            await t(f"🗑 '{blok['nomi']}' blokini o'chirasizmi?", callback.from_user.id),
            reply_markup=kb)
        await callback.answer()
        return

    if action == "mb_blkdelok":
        blok = await db.get_blok_by_id(aid)
        pid = blok["product_id"] if blok else None
        await db.delete_blok(aid)
        if pid:
            text, kb = await _mb_blk_view(pid)
            await callback.message.edit_text(text, reply_markup=kb)
        await callback.answer("🗑 O'chirildi")
        return

    if action == "mb_shbdel":
        sh = await db.get_shablon(aid)
        if not sh:
            await callback.answer("❌", show_alert=True)
            return
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Ha, o'chirish", callback_data=f"mb_shbdelok:{aid}"),
            InlineKeyboardButton(text="⬅️ Yo'q", callback_data=f"mb_shb:{sh['product_id']}"),
        ]])
        await callback.message.edit_text(
            await t(f"🗑 '{sh['nomi']}' shablonini o'chirasizmi?", callback.from_user.id),
            reply_markup=kb)
        await callback.answer()
        return

    if action == "mb_shbdelok":
        sh = await db.get_shablon(aid)
        pid = sh["product_id"] if sh else None
        await db.delete_shablon(aid)
        if pid:
            text, kb = await _mb_shb_view(pid)
            await callback.message.edit_text(text, reply_markup=kb)
        await callback.answer("🗑 O'chirildi")
        return

    # ── FSM boshlovchi amallar ──
    if action == "mb_add":
        await state.clear()
        await state.set_state(MahsulotState.nomi)
        await callback.message.answer(
            await t("➕ Yangi mahsulot nomini kiriting:\nMisol: Polistirol blok",
                    callback.from_user.id))
        await callback.answer()
        return

    if action == "mb_ren":
        await state.clear()
        await state.update_data(pid=aid)
        await state.set_state(MahsulotRename.nomi)
        await callback.message.answer(
            await t("✏️ Yangi nom kiriting:", callback.from_user.id))
        await callback.answer()
        return

    if action == "mb_blkadd":
        await state.clear()
        await state.update_data(pid=aid)
        await state.set_state(BlokState.kod)
        await callback.message.answer(
            await t("🧱 Blok kodini kiriting (qisqa):\nMisol: P  yoki  A",
                    callback.from_user.id))
        await callback.answer()
        return

    if action == "mb_shbadd":
        bloklar = await db.get_bloklar(aid)
        if not bloklar:
            await callback.answer("❌ Avval blok qo'shing!", show_alert=True)
            return
        await state.clear()
        await state.update_data(pid=aid)
        await state.set_state(ShablonState.nomi)
        await callback.message.answer(
            await t("📦 Shablon nomini kiriting:\nMisol: Standart  yoki  Shablon 1",
                    callback.from_user.id))
        await callback.answer()
        return

    if action == "mb_frm":
        materials = await db.get_materials()
        if not materials:
            await callback.answer("❌ Avval material qo'shing!", show_alert=True)
            return
        await state.clear()
        text, kb = await _frm_editor(aid)
        await callback.message.edit_text(text, reply_markup=kb)
        await callback.answer()
        return

    await callback.answer()


# ── Mahsulot qo'shish (FSM) ──
@router.message(MahsulotState.nomi)
async def mb_add_nomi(message: Message, state: FSMContext):
    nomi = message.text.strip()
    if not nomi:
        await say(message, "❌ Nom bo'sh bo'lmasin!")
        return
    await state.update_data(nomi=nomi)
    await state.set_state(MahsulotState.emoji)
    await say(message, "Emoji kiriting (ixtiyoriy):\nMisol: 🧊\nO'tkazib yuborish: 0")


@router.message(MahsulotState.emoji)
async def mb_add_emoji(message: Message, state: FSMContext):
    data = await state.get_data()
    emoji = message.text.strip()
    if emoji == "0" or not emoji:
        emoji = "📦"
    nomi = data["nomi"]
    kod = await _unique_kod(_slug(nomi))
    pid = await db.add_mahsulot(kod, nomi, emoji)
    user = await db.get_user(message.from_user.id)
    await db.add_audit_log(
        message.from_user.id, user["ism"] if user else "-",
        user["rol"] if user else "-", "Mahsulot qo'shildi", f"{nomi} ({kod})")
    await state.clear()
    await say(message,
              f"✅ '{nomi}' qo'shildi!\n\n"
              f"Endi 🧱 Bloklar, 📦 Shablonlar va 📋 Formulani sozlang.",
              reply_markup=await sozlamalar_menu(message.from_user.id))
    text, kb = await _mb_detail(pid)
    await message.answer(text, reply_markup=kb)


# ── Nomni o'zgartirish (FSM) ──
@router.message(MahsulotRename.nomi)
async def mb_ren_nomi(message: Message, state: FSMContext):
    nomi = message.text.strip()
    if not nomi:
        await say(message, "❌ Nom bo'sh bo'lmasin!")
        return
    await state.update_data(nomi=nomi)
    await state.set_state(MahsulotRename.emoji)
    await say(message, "Emoji kiriting (ixtiyoriy):\nO'zgartirmaslik: 0")


@router.message(MahsulotRename.emoji)
async def mb_ren_emoji(message: Message, state: FSMContext):
    data = await state.get_data()
    pid = data["pid"]
    p = await db.get_mahsulot(pid)
    emoji = message.text.strip()
    if emoji == "0" or not emoji:
        emoji = p["emoji"] if p else "📦"
    await db.update_mahsulot(pid, data["nomi"], emoji)
    await state.clear()
    await say(message, "✅ Yangilandi!",
              reply_markup=await sozlamalar_menu(message.from_user.id))
    text, kb = await _mb_detail(pid)
    await message.answer(text, reply_markup=kb)


# ── Blok qo'shish (FSM) ──
@router.message(BlokState.kod)
async def mb_blk_kod(message: Message, state: FSMContext):
    kod = message.text.strip()
    if not kod or len(kod) > 16:
        await say(message, "❌ Kod 1–16 belgidan iborat bo'lsin!")
        return
    data = await state.get_data()
    mavjud = await db.get_blok(data["pid"], kod)
    if mavjud:
        await say(message, "❌ Bu kod allaqachon mavjud! Boshqa kod kiriting:")
        return
    await state.update_data(kod=kod)
    await state.set_state(BlokState.nomi)
    await say(message, "Blok to'liq nomini kiriting:\nMisol: Polistirol blok")


@router.message(BlokState.nomi)
async def mb_blk_nomi(message: Message, state: FSMContext):
    await state.update_data(nomi=message.text.strip())
    await state.set_state(BlokState.olcham)
    await say(message, "O'lchamini kiriting (ixtiyoriy):\nMisol: 30×60×20\nO'tkazib yuborish: 0")


@router.message(BlokState.olcham)
async def mb_blk_olcham(message: Message, state: FSMContext):
    olcham = message.text.strip()
    if olcham == "0":
        olcham = ""
    await state.update_data(olcham=olcham)
    await state.set_state(BlokState.dona)
    await say(message,
              "Tannarx uchun: 1 qolipdan shu blokdan nechta chiqadi?\n"
              "(1 blok tannarxi = qolip tannarxi ÷ shu son)\nMisol: 30")


@router.message(BlokState.dona)
async def mb_blk_dona(message: Message, state: FSMContext):
    try:
        dona = float(message.text.replace(",", "."))
        if dona <= 0:
            raise ValueError
    except ValueError:
        await say(message, "❌ Faqat musbat son kiriting! Misol: 30")
        return
    data = await state.get_data()
    await db.add_blok(data["pid"], data["kod"], data["nomi"], data["olcham"], dona, 0)
    user = await db.get_user(message.from_user.id)
    await db.add_audit_log(
        message.from_user.id, user["ism"] if user else "-",
        user["rol"] if user else "-", "Blok qo'shildi",
        f"{data['nomi']} [{data['kod']}]")
    await state.clear()
    await say(message, f"✅ Blok qo'shildi: {data['nomi']}\n"
                       f"💡 Sotuv narxini 💵 Narxlar bo'limidan kiriting.",
              reply_markup=await sozlamalar_menu(message.from_user.id))
    text, kb = await _mb_blk_view(data["pid"])
    await message.answer(text, reply_markup=kb)


# ── Shablon qo'shish (FSM) ──
@router.message(ShablonState.nomi)
async def mb_shb_nomi(message: Message, state: FSMContext):
    nomi = message.text.strip()
    if not nomi:
        await say(message, "❌ Nom bo'sh bo'lmasin!")
        return
    data = await state.get_data()
    bloklar = await db.get_bloklar(data["pid"])
    await state.update_data(
        nomi=nomi,
        bloklar=[(b["kod"], b["nomi"]) for b in bloklar],
        b_index=0, chiqim=[])
    await state.set_state(ShablonState.chiqim)
    b = bloklar[0]
    await say(message,
              f"📦 '{nomi}' shabloni:\n\n"
              f"1 qolipga nechta '{b['nomi']}' [{b['kod']}] chiqadi?\n"
              f"Yo'q bo'lsa: 0")


@router.message(ShablonState.chiqim)
async def mb_shb_chiqim(message: Message, state: FSMContext):
    try:
        soni = int(message.text.strip())
        if soni < 0:
            raise ValueError
    except ValueError:
        await say(message, "❌ Faqat butun son kiriting! (yo'q bo'lsa 0)")
        return
    data = await state.get_data()
    bloklar = data["bloklar"]
    b_index = data["b_index"]
    chiqim = data["chiqim"]
    kod, _nomi = bloklar[b_index]
    if soni > 0:
        chiqim.append((kod, soni))
    b_index += 1
    if b_index < len(bloklar):
        await state.update_data(b_index=b_index, chiqim=chiqim)
        bk, bn = bloklar[b_index]
        await say(message, f"1 qolipga nechta '{bn}' [{bk}] chiqadi?\nYo'q bo'lsa: 0")
        return
    # Tugadi
    if not chiqim:
        await state.clear()
        await say(message, "❌ Shablon bo'sh — saqlanmadi (kamida 1 blok kerak).",
                  reply_markup=await sozlamalar_menu(message.from_user.id))
        return
    pid = data["pid"]
    mavjud = await db.get_shablonlar(pid)
    kod = str(len(mavjud) + 1)
    sid = await db.add_shablon(pid, kod, data["nomi"])
    await db.set_shablon_chiqim(sid, chiqim)
    user = await db.get_user(message.from_user.id)
    await db.add_audit_log(
        message.from_user.id, user["ism"] if user else "-",
        user["rol"] if user else "-", "Shablon qo'shildi",
        f"{data['nomi']}: " + ", ".join(f"{s}×{k}" for k, s in chiqim))
    await state.clear()
    await say(message, f"✅ Shablon qo'shildi: {data['nomi']}",
              reply_markup=await sozlamalar_menu(message.from_user.id))
    text, kb = await _mb_shb_view(pid)
    await message.answer(text, reply_markup=kb)


# ── Formula (tanlab tahrirlash — inline) ──
_FRM_OGIRLIK = ["kg", "tonna", "meshok", "g"]
_FRM_HAJM = ["litr", "ml", "m3"]


async def _frm_editor(pid):
    p = await db.get_mahsulot(pid)
    formula = await db.get_qolip_formula(pid)
    inframe = {f[5]: (f[1], f[2]) for f in formula}
    materials = await db.get_materials()
    text = (f"📋 {p['nomi'] if p else ''} — formula (1 qolipga)\n\n"
            f"Materialni tanlab miqdor kiriting.\n✅ = formulada bor.")
    kb = []
    for m in materials:
        mid = m[0]
        if mid in inframe:
            q, u = inframe[mid]
            label = f"✅ {m[1]}: {q} {u}"
        else:
            label = f"➕ {m[1]}"
        kb.append([InlineKeyboardButton(text=label, callback_data=f"frm:{pid}:{mid}")])
    kb.append([InlineKeyboardButton(text="✅ Tayyor", callback_data=f"frm_done:{pid}")])
    return text, InlineKeyboardMarkup(inline_keyboard=kb)


def _frm_units_kb(asl_birlik, pid):
    baza = db.birlik_bazasi(asl_birlik)
    birliklar = _FRM_OGIRLIK if baza == "kg" else _FRM_HAJM
    kb, row = [], []
    for b in birliklar:
        row.append(InlineKeyboardButton(text=b, callback_data=f"frmunit:{b}"))
        if len(row) == 2:
            kb.append(row)
            row = []
    if row:
        kb.append(row)
    kb.append([InlineKeyboardButton(text="⬅️ Ortga", callback_data=f"frm_back:{pid}")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


@router.callback_query(lambda c: c.data and c.data.startswith("frm:"))
async def frm_pick(callback: CallbackQuery, state: FSMContext):
    if not await _cb_ok(callback):
        return
    _, pid, mid = callback.data.split(":")
    pid, mid = int(pid), int(mid)
    materials = await db.get_materials()
    m = next((x for x in materials if x[0] == mid), None)
    if not m:
        await callback.answer("❌", show_alert=True)
        return
    await state.update_data(frm_pid=pid, frm_mid=mid, frm_nomi=m[1], frm_birlik=m[4])
    await state.set_state(FormulaState.miqdor)
    formula = await db.get_qolip_formula(pid)
    bor = next((f for f in formula if f[5] == mid), None)
    izoh = f"\nHozir: {bor[1]} {bor[2]}" if bor else ""
    rows = []
    if bor:
        rows.append([InlineKeyboardButton(
            text="🗑 Formuladan olib tashlash", callback_data=f"frm_del:{pid}:{mid}")])
    rows.append([InlineKeyboardButton(text="⬅️ Ortga", callback_data=f"frm_back:{pid}")])
    try:
        await callback.message.edit_text(await t(
            f"📋 {m[1]} — 1 qolipga qancha ketadi?{izoh}\n"
            f"Sonni kiriting (masalan: 110)", callback.from_user.id),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    except Exception:
        pass
    await callback.answer()


@router.message(FormulaState.miqdor)
async def frm_miqdor(message: Message, state: FSMContext):
    try:
        miqdor = float(message.text.replace(",", "."))
        if miqdor <= 0:
            raise ValueError
    except (ValueError, AttributeError):
        await say(message, "❌ Faqat musbat son kiriting! Misol: 110")
        return
    data = await state.get_data()
    if "frm_mid" not in data:
        await state.clear()
        return
    await state.update_data(frm_miqdor=miqdor)
    await say(message,
              f"📏 {data['frm_nomi']}: {miqdor}\nBirlikni tanlang:",
              reply_markup=_frm_units_kb(data["frm_birlik"], data["frm_pid"]))


@router.callback_query(lambda c: c.data and c.data.startswith("frmunit:"))
async def frm_unit(callback: CallbackQuery, state: FSMContext):
    if not await _cb_ok(callback):
        return
    birlik = callback.data.split(":", 1)[1]
    data = await state.get_data()
    if "frm_mid" not in data or "frm_miqdor" not in data:
        await callback.answer()
        return
    if db.birlik_bazasi(birlik) != db.birlik_bazasi(data["frm_birlik"]):
        await callback.answer("❌ Birlik mos emas", show_alert=True)
        return
    await db.set_qolip_formula_item(
        data["frm_pid"], data["frm_mid"], data["frm_miqdor"], birlik)
    pid = data["frm_pid"]
    await state.clear()
    text, kb = await _frm_editor(pid)
    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except Exception:
        await callback.message.answer(text, reply_markup=kb)
    await callback.answer("✅ Saqlandi")


@router.callback_query(lambda c: c.data and c.data.startswith("frm_del:"))
async def frm_del(callback: CallbackQuery, state: FSMContext):
    if not await _cb_ok(callback):
        return
    _, pid, mid = callback.data.split(":")
    pid, mid = int(pid), int(mid)
    await db.remove_qolip_formula_item(pid, mid)
    await state.clear()
    text, kb = await _frm_editor(pid)
    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except Exception:
        pass
    await callback.answer("🗑 Olib tashlandi")


@router.callback_query(lambda c: c.data and c.data.startswith("frm_back:"))
async def frm_back(callback: CallbackQuery, state: FSMContext):
    if not await _cb_ok(callback):
        return
    pid = int(callback.data.split(":", 1)[1])
    await state.clear()
    text, kb = await _frm_editor(pid)
    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except Exception:
        pass
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("frm_done:"))
async def frm_done(callback: CallbackQuery, state: FSMContext):
    if not await _cb_ok(callback):
        return
    pid = int(callback.data.split(":", 1)[1])
    await state.clear()
    text, kb = await _mb_detail(pid)
    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except Exception:
        pass
    await callback.answer()
