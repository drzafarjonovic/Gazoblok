from aiogram import Router
from aiogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import database as db
import valyuta as val
from translation import Tkey, say, say_error, build_keyboard, t

router = Router()


class MaterialNarxState(StatesGroup):
    qiymat = State()


class QolKursState(StatesGroup):
    qiymat = State()


class SotuvNarxState(StatesGroup):
    qiymat = State()


class IshchiHaqiState(StatesGroup):
    qiymat = State()


class QoshimchaState(StatesGroup):
    qiymat = State()


class OverrideState(StatesGroup):
    qiymat = State()


async def narxlar_menu(user_id):
    return await build_keyboard(user_id, [
        ["💱 Valyuta"],
        ["📦 Material narxlari"],
        ["🏷 Mahsulot narxlari"],
        ["🏠 Asosiy menyu"],
    ])


async def _faqat_superadmin(message: Message, user=None) -> bool:
    if user is None:
        user = await db.get_user(message.from_user.id)
    if not user or not user["faol"]:
        await say(message, "❌ Ruxsat yo'q!")
        return False
    if await db.has_permission(message.from_user.id, user["rol"], "sozlama_boshqaruv"):
        return True
    await say(message, "❌ Sizda narxlarni boshqarish huquqi yo'q!")
    return False


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


def valyuta_keyboard():
    keyboard, row = [], []
    for kod, (nomi, belgi) in val.VALYUTALAR.items():
        row.append(InlineKeyboardButton(text=f"{belgi} {kod}", callback_data=f"cur_{kod}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# ── Asosiy kirish ──
@router.message(Tkey("💵 Narxlar va valyuta"))
async def narxlar(message: Message, user: dict = None):
    if not await _faqat_superadmin(message, user):
        return
    kod = await val.get_active()
    await say(
        message,
        f"💵 Narxlar va valyuta\nFaol valyuta: {val.belgi(kod)} ({kod})",
        reply_markup=await narxlar_menu(message.from_user.id)
    )


# ── Valyuta tanlash ──
@router.message(Tkey("💱 Valyuta"))
async def valyuta_tanlash(message: Message, user: dict = None):
    if not await _faqat_superadmin(message, user):
        return
    kod = await val.get_active()
    await say(
        message,
        f"💱 Joriy valyuta: {val.belgi(kod)} ({kod})\n\n"
        f"Yangi valyutani tanlang.\n"
        f"Narxlar shu valyutada ko'rsatiladi (ichkarida so'mda saqlanadi).",
        reply_markup=valyuta_keyboard()
    )


@router.message(Tkey("✍️ Qo'lda kurs kiritish"))
async def qol_kurs(message: Message, state: FSMContext, user: dict = None):
    if not await _faqat_superadmin(message, user):
        return
    await state.clear()
    await state.set_state(QolKursState.qiymat)
    await say(
        message,
        "✍️ Qo'lda kurs kiriting (1 birlik necha so'm).\n"
        "Format: KOD QIYMAT\nMisol: USD 12600"
    )


@router.message(QolKursState.qiymat)
async def qol_kurs_saqlash(message: Message, state: FSMContext):
    try:
        parts = message.text.strip().split()
        if len(parts) < 2:
            raise ValueError
        kod = parts[0].upper()
        if kod not in val.VALYUTALAR:
            await say(message, "❌ Noma'lum valyuta kodi! Misol: USD 12600")
            return
        kurs = float(parts[1].replace(",", "."))
        if kurs <= 0:
            raise ValueError
        await db.set_kurs(kod, kurs)
        await state.clear()
        await say(
            message,
            f"✅ Kurs saqlandi: 1 {kod} = {val.format_pul(kurs, 'UZS')}",
            reply_markup=await narxlar_menu(message.from_user.id)
        )
    except ValueError:
        await say(message, "❌ Noto'g'ri format! Misol: USD 12600")


@router.callback_query(lambda c: c.data and c.data.startswith("cur_"))
async def valyuta_callback(callback: CallbackQuery):
    user = await db.get_user(callback.from_user.id)
    if not user or user["rol"] != "superadmin":
        await callback.answer("❌ Ruxsat yo'q!", show_alert=True)
        return
    kod = callback.data.split("_", 1)[1]
    if kod not in val.VALYUTALAR:
        await callback.answer()
        return
    await db.set_bot_setting("valyuta", kod)
    await callback.answer()

    matn = f"✅ Valyuta o'zgartirildi: {val.belgi(kod)} ({kod})"
    if kod != val.ASOS:
        r = await val.get_rate(kod)
        if r:
            matn += f"\nKurs: 1 {kod} = {val.format_pul(r, 'UZS')}"
        else:
            matn += ("\n⚠️ Onlayn kurs topilmadi! "
                     "'✍️ Qo'lda kurs kiritish' orqali kiriting.")
    xabar = await t(matn, callback.from_user.id)
    await callback.message.edit_text(xabar)
    kb = await build_keyboard(callback.from_user.id, [
        ["✍️ Qo'lda kurs kiritish"],
        ["🏠 Asosiy menyu"],
    ])
    await callback.message.answer(
        await t("Tayyor.", callback.from_user.id), reply_markup=kb)


# ── Material narxlari (tanlab tahrirlash — inline) ──
async def _material_narx_kb(user_id):
    materials = await db.get_materials()
    narxlar = await db.get_material_narxlar()
    kb = []
    for m in materials:
        nb = narxlar.get(m[0], 0) or 0
        if nb > 0:
            per = nb * db.birlikni_asosiyga(1, m[4])[0]
            belgi = await val.format_uzs(per)
        else:
            belgi = "—"
        kb.append([InlineKeyboardButton(
            text=f"{m[1]}: {belgi}/{m[4]}", callback_data=f"mnarx:{m[0]}")])
    kb.append([InlineKeyboardButton(text="✅ Tayyor", callback_data="mnarx_done")])
    return InlineKeyboardMarkup(inline_keyboard=kb), materials


@router.message(Tkey("📦 Material narxlari"))
async def material_narxlari(message: Message, state: FSMContext, user: dict = None):
    if not await _faqat_superadmin(message, user):
        return
    await state.clear()
    kb, materials = await _material_narx_kb(message.from_user.id)
    if not materials:
        await say(message, "❌ Avval material qo'shing!",
                  reply_markup=await narxlar_menu(message.from_user.id))
        return
    kod = await val.get_active()
    await say(message,
              f"📦 Material narxlari (valyuta: {kod})\n"
              f"O'zgartirish uchun materialni tanlang:", reply_markup=kb)


@router.callback_query(lambda c: c.data == "mnarx_done")
async def mnarx_done(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await callback.message.edit_text(await t("✅ Tayyor.", callback.from_user.id))
    except Exception:
        pass
    await callback.message.answer(
        await t("💵 Narxlar va valyuta:", callback.from_user.id),
        reply_markup=await narxlar_menu(callback.from_user.id))
    await callback.answer()


@router.callback_query(lambda c: c.data == "mnarx_back")
async def mnarx_back(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    kb, _ = await _material_narx_kb(callback.from_user.id)
    try:
        await callback.message.edit_text(
            await t("📦 Material narxlari — materialni tanlang:", callback.from_user.id),
            reply_markup=kb)
    except Exception:
        pass
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("mnarx:"))
async def mnarx_cb(callback: CallbackQuery, state: FSMContext):
    if not await _cb_ok(callback):
        return
    mid = int(callback.data.split(":", 1)[1])
    materials = await db.get_materials()
    m = next((x for x in materials if x[0] == mid), None)
    if not m:
        await callback.answer("❌", show_alert=True)
        return
    await state.update_data(narx_mid=mid, narx_nomi=m[1], narx_birlik=m[4])
    await state.set_state(MaterialNarxState.qiymat)
    kod = await val.get_active()
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="❌ Bekor", callback_data="mnarx_back")]])
    try:
        await callback.message.edit_text(await t(
            f"📦 {m[1]} narxi? (valyuta: {kod})\n"
            f"1 birlik narxi va birligini yozing.\n"
            f"Misol: 800000 {m[4]}  yoki  800 kg\n"
            f"(0 = narxni o'chirish)", callback.from_user.id), reply_markup=kb)
    except Exception:
        pass
    await callback.answer()


@router.message(MaterialNarxState.qiymat)
async def material_narx_saqlash(message: Message, state: FSMContext):
    data = await state.get_data()
    if "narx_mid" not in data:
        await state.clear()
        return
    mid, nomi, asl_birlik = data["narx_mid"], data["narx_nomi"], data["narx_birlik"]
    text = message.text.strip()
    try:
        if text == "0":
            narx_base_uzs = 0.0
        else:
            parts = text.split()
            if len(parts) < 2:
                await say(message, "❌ Format: <narx> <birlik>\nMisol: 800000 tonna\n(yoki 0)")
                return
            narx = float(parts[0].replace(",", "."))
            birlik = parts[1].lower()
            if narx < 0:
                raise ValueError
            if (not db.birlik_qollab_quvvatlanadimi(birlik)
                    or db.birlik_bazasi(birlik) != db.birlik_bazasi(asl_birlik)):
                await say(message,
                          f"❌ Birlik '{nomi}' o'lchamiga mos emas (ombor: {asl_birlik}).\n"
                          f"Qaytadan:")
                return
            unit_factor = db.birlikni_asosiyga(1, birlik)[0]
            narx_base_active = narx / unit_factor if unit_factor else narx
            narx_base_uzs = await val.active_to_uzs(narx_base_active)
            if narx_base_uzs is None:
                await say(message, "❌ Valyuta kursi topilmadi! Avval '✍️ Qo'lda kurs kiritish'.")
                return

        await db.set_material_narx(mid, narx_base_uzs)
        user = await db.get_user(message.from_user.id)
        await db.add_audit_log(
            message.from_user.id, user["ism"] if user else str(message.from_user.id),
            user["rol"] if user else "-", "Material narxi yangilandi", nomi)
        await state.clear()
        kb, _ = await _material_narx_kb(message.from_user.id)
        await say(message, f"✅ {nomi} narxi saqlandi.\nYana o'zgartirish uchun tanlang:",
                  reply_markup=kb)
    except ValueError:
        await say(message, "❌ Faqat musbat son! Misol: 800000 tonna")
    except Exception as e:
        await state.clear()
        await say_error(message, e, reply_markup=await narxlar_menu(message.from_user.id))


# ════════════════════════════════════════════════════════════════════
# 🏷 MAHSULOT NARXLARI (product-aware, inline)
# ════════════════════════════════════════════════════════════════════
async def _mahsulot_narx_kb():
    prods = await db.get_mahsulotlar(faqat_faol=False)
    kb = []
    for p in prods:
        belgi = "" if p["faol"] else " (arxiv)"
        kb.append([InlineKeyboardButton(
            text=f"{p['emoji']} {p['nomi']}{belgi}",
            callback_data=f"pr_p:{p['id']}")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


async def _mahsulot_narx_detail(pid):
    p = await db.get_mahsulot(pid)
    if not p:
        return "❌ Mahsulot topilmadi.", InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Ortga", callback_data="pr_root")]])
    ti = await db.tannarx_hisobla(pid)
    text = f"🏷 {p['emoji']} {p['nomi']} narxlari\n\n"
    text += f"👷 Ish haqi (1 qolip): {await val.format_uzs(ti['ishchi'])}\n"
    text += f"🛠 Qo'shimcha (1 qolip): {await val.format_uzs(ti['qoshimcha'])}\n"
    text += f"📦 Material (1 qolip): {await val.format_uzs(ti['material'])}\n"
    text += f"💠 1 qolip tannarxi: {await val.format_uzs(ti['qolip'])}\n\n"
    text += "🧱 Bloklar (tannarx | sotuv):\n"
    bloklar = await db.get_bloklar(pid)
    narx_map = {b["kod"]: b["sotuv_narx"] for b in bloklar}
    for b in ti["bloklar"]:
        belgi = " (override)" if b["override"] is not None else ""
        sotuv = narx_map.get(b["kod"], 0) or 0
        text += (f"   {b['nomi']}: {await val.format_uzs(b['final'])}{belgi} | "
                 f"sotuv {await val.format_uzs(sotuv)}\n")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧱 Sotuv narxlari", callback_data=f"pr_sn:{pid}")],
        [InlineKeyboardButton(text="👷 Ish haqi", callback_data=f"pr_ish:{pid}"),
         InlineKeyboardButton(text="🛠 Qo'shimcha", callback_data=f"pr_qsh:{pid}")],
        [InlineKeyboardButton(text="🎯 Tannarx override", callback_data=f"pr_ov:{pid}")],
        [InlineKeyboardButton(text="⬅️ Ortga", callback_data="pr_root")],
    ])
    return text, kb


@router.message(Tkey("🏷 Mahsulot narxlari"))
async def mahsulot_narxlari(message: Message, state: FSMContext, user: dict = None):
    if not await _faqat_superadmin(message, user):
        return
    await state.clear()
    prods = await db.get_mahsulotlar(faqat_faol=False)
    if not prods:
        await say(message, "❌ Avval mahsulot qo'shing!\n"
                           "⚙️ Sozlamalar → 🏭 Mahsulot boshqaruvi",
                  reply_markup=await narxlar_menu(message.from_user.id))
        return
    kod = await val.get_active()
    await message.answer(
        await t(f"🏷 Mahsulot narxlari\nFaol valyuta: {kod}\nMahsulotni tanlang:",
                message.from_user.id),
        reply_markup=await _mahsulot_narx_kb())


@router.callback_query(lambda c: c.data and c.data.startswith("pr_"))
async def pr_callback(callback: CallbackQuery, state: FSMContext):
    if not await _cb_ok(callback):
        return
    action, _, arg = callback.data.partition(":")
    pid = int(arg) if arg.isdigit() else None

    if action == "pr_root":
        await state.clear()
        await callback.message.edit_text(
            await t("🏷 Mahsulot narxlari\nMahsulotni tanlang:", callback.from_user.id),
            reply_markup=await _mahsulot_narx_kb())
        await callback.answer()
        return

    if action == "pr_p":
        await state.clear()
        text, kb = await _mahsulot_narx_detail(pid)
        await callback.message.edit_text(text, reply_markup=kb)
        await callback.answer()
        return

    if action == "pr_sn":
        bloklar = await db.get_bloklar(pid)
        if not bloklar:
            await callback.answer("❌ Avval blok qo'shing!", show_alert=True)
            return
        await state.clear()
        await state.update_data(pid=pid, bloklar=bloklar, index=0, rejim="sotuv")
        await state.set_state(SotuvNarxState.qiymat)
        await _blok_narx_sorov(callback.message, callback.from_user.id, bloklar[0], "sotuv")
        await callback.answer()
        return

    if action == "pr_ov":
        bloklar = await db.get_bloklar(pid)
        if not bloklar:
            await callback.answer("❌ Avval blok qo'shing!", show_alert=True)
            return
        await state.clear()
        await state.update_data(pid=pid, bloklar=bloklar, index=0, rejim="override")
        await state.set_state(OverrideState.qiymat)
        await _blok_narx_sorov(callback.message, callback.from_user.id, bloklar[0], "override")
        await callback.answer()
        return

    if action == "pr_ish":
        await state.clear()
        await state.update_data(pid=pid)
        await state.set_state(IshchiHaqiState.qiymat)
        p = await db.get_mahsulot(pid)
        kod = await val.get_active()
        joriy = await val.format_uzs(p["ishchi_haqi"]) if p else "—"
        await callback.message.answer(await t(
            f"👷 1 qolipga ishchi haqi?\n(Faol valyuta: {kod})\nJoriy: {joriy}\nMisol: 5000",
            callback.from_user.id))
        await callback.answer()
        return

    if action == "pr_qsh":
        await state.clear()
        await state.update_data(pid=pid)
        await state.set_state(QoshimchaState.qiymat)
        p = await db.get_mahsulot(pid)
        kod = await val.get_active()
        joriy = await val.format_uzs(p["qoshimcha_xarajat"]) if p else "—"
        await callback.message.answer(await t(
            f"🛠 1 qolipga qo'shimcha xarajat?\n(Faol valyuta: {kod})\n"
            f"Joriy: {joriy}\nMisol: 2000", callback.from_user.id))
        await callback.answer()
        return

    await callback.answer()


async def _blok_narx_sorov(message, user_id, blok, rejim):
    kod = await val.get_active()
    if rejim == "override":
        joriy = (await val.format_uzs(blok["tannarx_override"])
                 if blok["tannarx_override"] is not None else "avtomatik")
        await message.answer(await t(
            f"🎯 {blok['nomi']} tannarx override?\n"
            f"(Faol valyuta: {kod}; joriy: {joriy})\n"
            f"Avtomatga qaytarish: 0\nMisol: 9000", user_id))
    else:
        joriy = await val.format_uzs(blok["sotuv_narx"]) if blok["sotuv_narx"] else "belgilanmagan"
        await message.answer(await t(
            f"🧱 {blok['nomi']} sotuv narxi? (1 dona)\n"
            f"(Faol valyuta: {kod})\nJoriy: {joriy}\nMisol: 12000", user_id))


async def _narx_menu_msg(message, user_id):
    await say(message, "✅ Saqlandi!", reply_markup=await narxlar_menu(user_id))


# ── Sotuv narxi (bloklar bo'ylab) ──
@router.message(SotuvNarxState.qiymat)
async def sotuv_narx_saqlash(message: Message, state: FSMContext):
    user_id = message.from_user.id
    try:
        qiymat = float(message.text.replace(",", "."))
        if qiymat < 0:
            raise ValueError
    except ValueError:
        await say(message, "❌ Faqat musbat son! Misol: 12000")
        return
    uzs = await val.active_to_uzs(qiymat)
    if uzs is None:
        await say(message, "❌ Valyuta kursi topilmadi! Avval '✍️ Qo'lda kurs kiritish'.")
        return
    data = await state.get_data()
    bloklar = data["bloklar"]
    index = data["index"]
    await db.set_blok_sotuv_narx(bloklar[index]["id"], uzs)
    index += 1
    if index < len(bloklar):
        await state.update_data(index=index)
        await _blok_narx_sorov(message, user_id, bloklar[index], "sotuv")
    else:
        await state.clear()
        await say(message, "✅ Sotuv narxlari saqlandi!",
                  reply_markup=await narxlar_menu(user_id))


# ── Tannarx override (bloklar bo'ylab) ──
@router.message(OverrideState.qiymat)
async def override_saqlash(message: Message, state: FSMContext):
    user_id = message.from_user.id
    try:
        qiymat = float(message.text.replace(",", "."))
        if qiymat < 0:
            raise ValueError
    except ValueError:
        await say(message, "❌ Faqat son! (0 = avtomat)")
        return
    data = await state.get_data()
    bloklar = data["bloklar"]
    index = data["index"]
    if qiymat == 0:
        await db.set_blok_override(bloklar[index]["id"], None)
    else:
        uzs = await val.active_to_uzs(qiymat)
        if uzs is None:
            await say(message, "❌ Valyuta kursi topilmadi! Avval '✍️ Qo'lda kurs kiritish'.")
            return
        await db.set_blok_override(bloklar[index]["id"], uzs)
    index += 1
    if index < len(bloklar):
        await state.update_data(index=index)
        await _blok_narx_sorov(message, user_id, bloklar[index], "override")
    else:
        await state.clear()
        await say(message, "✅ Override saqlandi!",
                  reply_markup=await narxlar_menu(user_id))


# ── Ish haqi ──
@router.message(IshchiHaqiState.qiymat)
async def ishchi_haqi_saqlash(message: Message, state: FSMContext):
    user_id = message.from_user.id
    try:
        qiymat = float(message.text.replace(",", "."))
        if qiymat < 0:
            raise ValueError
    except ValueError:
        await say(message, "❌ Faqat musbat son! Misol: 5000")
        return
    uzs = await val.active_to_uzs(qiymat)
    if uzs is None:
        await say(message, "❌ Valyuta kursi topilmadi! Avval '✍️ Qo'lda kurs kiritish'.")
        return
    data = await state.get_data()
    await db.set_mahsulot_ishchi_haqi(data["pid"], uzs)
    await state.clear()
    await say(message, "✅ Ishchi haqi saqlandi!",
              reply_markup=await narxlar_menu(user_id))


# ── Qo'shimcha xarajat ──
@router.message(QoshimchaState.qiymat)
async def qoshimcha_saqlash(message: Message, state: FSMContext):
    user_id = message.from_user.id
    try:
        qiymat = float(message.text.replace(",", "."))
        if qiymat < 0:
            raise ValueError
    except ValueError:
        await say(message, "❌ Faqat musbat son! Misol: 2000")
        return
    uzs = await val.active_to_uzs(qiymat)
    if uzs is None:
        await say(message, "❌ Valyuta kursi topilmadi! Avval '✍️ Qo'lda kurs kiritish'.")
        return
    data = await state.get_data()
    await db.set_mahsulot_qoshimcha(data["pid"], uzs)
    await state.clear()
    await say(message, "✅ Qo'shimcha xarajat saqlandi!",
              reply_markup=await narxlar_menu(user_id))
