from aiogram import Router
from aiogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import database as db
import valyuta as val
from translation import Tkey, eq, say, say_error, build_keyboard, t

router = Router()


class MaterialNarxState(StatesGroup):
    qiymat = State()


class SotuvNarxState(StatesGroup):
    qiymat = State()


class IshchiHaqiState(StatesGroup):
    qiymat = State()


class QoshimchaState(StatesGroup):
    qiymat = State()


class OverrideState(StatesGroup):
    qiymat = State()


class QolKursState(StatesGroup):
    qiymat = State()


async def narxlar_menu(user_id):
    return await build_keyboard(user_id, [
        ["💱 Valyuta"],
        ["📦 Material narxlari"],
        ["🧱 Sotuv narxlari"],
        ["👷 Ishchi haqi"],
        ["🛠 Qo'shimcha xarajat"],
        ["🎯 Tannarx override"],
        ["📊 Hisoblangan tannarx"],
        ["🏠 Asosiy menyu"],
    ])


async def _faqat_superadmin(message: Message) -> bool:
    user = await db.get_user(message.from_user.id)
    if not user or not user["faol"]:
        await say(message, "❌ Ruxsat yo'q!")
        return False
    if await db.has_permission(message.from_user.id, user["rol"], "sozlama_boshqaruv"):
        return True
    await say(message, "❌ Sizda narxlarni boshqarish huquqi yo'q!")
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
async def narxlar(message: Message):
    if not await _faqat_superadmin(message):
        return
    kod = await val.get_active()
    await say(
        message,
        f"💵 Narxlar va valyuta\nFaol valyuta: {val.belgi(kod)} ({kod})",
        reply_markup=await narxlar_menu(message.from_user.id)
    )


# ── Valyuta tanlash ──
@router.message(Tkey("💱 Valyuta"))
async def valyuta_tanlash(message: Message):
    if not await _faqat_superadmin(message):
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
async def qol_kurs(message: Message, state: FSMContext):
    if not await _faqat_superadmin(message):
        return
    await state.clear()
    await state.set_state(QolKursState.qiymat)
    await say(
        message,
        "✍️ Qo'lda kurs kiriting (1 birlik necha so'm).\n"
        "Format: KOD QIYMAT\n"
        "Misol: USD 12600"
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
    # Qo'lda kurs imkoni bilan menyu
    kb = await build_keyboard(callback.from_user.id, [
        ["✍️ Qo'lda kurs kiritish"],
        ["🏠 Asosiy menyu"],
    ])
    await callback.message.answer(
        await t("Tayyor.", callback.from_user.id), reply_markup=kb
    )


# ── Material narxlari (materiallar bo'ylab aylanish) ──
@router.message(Tkey("📦 Material narxlari"))
async def material_narxlari(message: Message, state: FSMContext):
    if not await _faqat_superadmin(message):
        return
    await state.clear()
    materials = await db.get_materials()
    if not materials:
        await say(
            message, "❌ Avval material qo'shing!",
            reply_markup=await narxlar_menu(message.from_user.id)
        )
        return
    narxlar = await db.get_material_narxlar()
    kod = await val.get_active()
    await state.update_data(
        materials=[(m[0], m[1], m[2], m[3], m[4]) for m in materials],
        index=0
    )
    await state.set_state(MaterialNarxState.qiymat)
    await _material_narx_sorov(message, materials[0], narxlar, kod)


async def _material_narx_sorov(message, m, narxlar, kod):
    narx_base = narxlar.get(m[0], 0) or 0
    if narx_base > 0:
        # 1 asl_birlik narxi = narx_base * (1 asl_birlik necha baza)
        per_display = narx_base * db.birlikni_asosiyga(1, m[4])[0]
        joriy = await val.format_uzs(per_display) + f" / {m[4]}"
    else:
        joriy = "belgilanmagan"
    await say(
        message,
        f"📦 {m[1]} narxi?\n"
        f"1 birlik narxini va birlikni yozing.\n"
        f"Misol: 800000 {m[4]}  yoki  800 kg\n"
        f"(Faol valyuta: {kod}; o'tkazib yuborish: 0)\n"
        f"Joriy: {joriy}"
    )


@router.message(MaterialNarxState.qiymat)
async def material_narx_saqlash(message: Message, state: FSMContext):
    try:
        data = await state.get_data()
        materials = data["materials"]
        index = data["index"]
        m = materials[index]
        text = message.text.strip()

        if text == "0":
            narx_base_uzs = 0.0
        else:
            parts = text.split()
            if len(parts) < 2:
                await say(
                    message,
                    "❌ Format: <narx> <birlik>\nMisol: 800000 tonna\n(yoki 0)"
                )
                return
            narx = float(parts[0].replace(",", "."))
            birlik = parts[1].lower()
            if narx < 0:
                raise ValueError
            if (not db.birlik_qollab_quvvatlanadimi(birlik)
                    or db.birlik_bazasi(birlik) != db.birlik_bazasi(m[4])):
                await say(
                    message,
                    f"❌ Birlik '{m[1]}' o'lchamiga mos emas (ombor: {m[4]}).\n"
                    f"Qaytadan:"
                )
                return
            # 1 birlik necha baza -> 1 baza narxi (faol valyuta) -> UZS
            unit_factor = db.birlikni_asosiyga(1, birlik)[0]
            narx_base_active = narx / unit_factor if unit_factor else narx
            narx_base_uzs = await val.active_to_uzs(narx_base_active)
            if narx_base_uzs is None:
                await say(
                    message,
                    "❌ Valyuta kursi topilmadi! Avval '✍️ Qo'lda kurs kiritish'."
                )
                return

        await db.set_material_narx(m[0], narx_base_uzs)

        index += 1
        if index < len(materials):
            await state.update_data(index=index)
            narxlar = await db.get_material_narxlar()
            kod = await val.get_active()
            await _material_narx_sorov(message, materials[index], narxlar, kod)
        else:
            user = await db.get_user(message.from_user.id)
            await db.add_audit_log(
                message.from_user.id,
                user["ism"] if user else str(message.from_user.id),
                user["rol"] if user else "-",
                "Material narxlari yangilandi",
                f"{len(materials)} ta material narxi saqlandi"
            )
            await state.clear()
            await say(
                message, "✅ Material narxlari saqlandi!",
                reply_markup=await narxlar_menu(message.from_user.id)
            )
    except ValueError:
        await say(message, "❌ Faqat musbat son! Misol: 800000 tonna")
    except Exception as e:
        await state.clear()
        await say_error(message, e, reply_markup=await narxlar_menu(message.from_user.id))


# ── Sotuv narxlari (A keyin B) ──
@router.message(Tkey("🧱 Sotuv narxlari"))
async def sotuv_narxlari(message: Message, state: FSMContext):
    if not await _faqat_superadmin(message):
        return
    await state.clear()
    kod = await val.get_active()
    joriy = await db.get_bot_setting("sotuv_narx_A")
    joriy_t = await val.format_uzs(float(joriy)) if joriy else "belgilanmagan"
    await state.update_data(step="A")
    await state.set_state(SotuvNarxState.qiymat)
    await say(
        message,
        f"🧱 A blok sotuv narxi? (1 dona)\n"
        f"(Faol valyuta: {kod})\nJoriy: {joriy_t}\nMisol: 12000"
    )


@router.message(SotuvNarxState.qiymat)
async def sotuv_narx_saqlash(message: Message, state: FSMContext):
    try:
        qiymat = float(message.text.replace(",", "."))
        if qiymat < 0:
            raise ValueError
        uzs = await val.active_to_uzs(qiymat)
        if uzs is None:
            await say(message, "❌ Valyuta kursi topilmadi! Avval '✍️ Qo'lda kurs kiritish'.")
            return
        data = await state.get_data()
        step = data.get("step", "A")
        if step == "A":
            await db.set_bot_setting("sotuv_narx_A", str(uzs))
            await state.update_data(step="B")
            kod = await val.get_active()
            joriy = await db.get_bot_setting("sotuv_narx_B")
            joriy_t = await val.format_uzs(float(joriy)) if joriy else "belgilanmagan"
            await say(
                message,
                f"🧱 B blok sotuv narxi? (1 dona)\n"
                f"(Faol valyuta: {kod})\nJoriy: {joriy_t}\nMisol: 7000"
            )
        else:
            await db.set_bot_setting("sotuv_narx_B", str(uzs))
            user = await db.get_user(message.from_user.id)
            await db.add_audit_log(
                message.from_user.id,
                user["ism"] if user else str(message.from_user.id),
                user["rol"] if user else "-",
                "Sotuv narxlari yangilandi", "A va B blok narxi"
            )
            await state.clear()
            await say(
                message, "✅ Sotuv narxlari saqlandi!",
                reply_markup=await narxlar_menu(message.from_user.id)
            )
    except ValueError:
        await say(message, "❌ Faqat musbat son! Misol: 12000")
    except Exception as e:
        await state.clear()
        await say_error(message, e, reply_markup=await narxlar_menu(message.from_user.id))


# ── Ishchi haqi (1 qolipga) ──
@router.message(Tkey("👷 Ishchi haqi"))
async def ishchi_haqi(message: Message, state: FSMContext):
    if not await _faqat_superadmin(message):
        return
    await state.clear()
    kod = await val.get_active()
    joriy = await db.get_bot_setting("ishchi_haqi_qolip")
    joriy_t = await val.format_uzs(float(joriy)) if joriy else "belgilanmagan"
    await state.set_state(IshchiHaqiState.qiymat)
    await say(
        message,
        f"👷 1 qolipga ishchi haqi?\n(Faol valyuta: {kod})\n"
        f"Joriy: {joriy_t}\nMisol: 5000"
    )


@router.message(IshchiHaqiState.qiymat)
async def ishchi_haqi_saqlash(message: Message, state: FSMContext):
    try:
        qiymat = float(message.text.replace(",", "."))
        if qiymat < 0:
            raise ValueError
        uzs = await val.active_to_uzs(qiymat)
        if uzs is None:
            await say(message, "❌ Valyuta kursi topilmadi! Avval '✍️ Qo'lda kurs kiritish'.")
            return
        await db.set_bot_setting("ishchi_haqi_qolip", str(uzs))
        await state.clear()
        await say(
            message, "✅ Ishchi haqi saqlandi!",
            reply_markup=await narxlar_menu(message.from_user.id)
        )
    except ValueError:
        await say(message, "❌ Faqat musbat son! Misol: 5000")
    except Exception as e:
        await state.clear()
        await say_error(message, e, reply_markup=await narxlar_menu(message.from_user.id))


# ── Qo'shimcha xarajat (1 qolipga) ──
@router.message(Tkey("🛠 Qo'shimcha xarajat"))
async def qoshimcha(message: Message, state: FSMContext):
    if not await _faqat_superadmin(message):
        return
    await state.clear()
    kod = await val.get_active()
    joriy = await db.get_bot_setting("qoshimcha_xarajat_qolip")
    joriy_t = await val.format_uzs(float(joriy)) if joriy else "belgilanmagan"
    await state.set_state(QoshimchaState.qiymat)
    await say(
        message,
        f"🛠 1 qolipga qo'shimcha xarajat? (elektr, suv va h.k.)\n"
        f"(Faol valyuta: {kod})\nJoriy: {joriy_t}\nMisol: 2000"
    )


@router.message(QoshimchaState.qiymat)
async def qoshimcha_saqlash(message: Message, state: FSMContext):
    try:
        qiymat = float(message.text.replace(",", "."))
        if qiymat < 0:
            raise ValueError
        uzs = await val.active_to_uzs(qiymat)
        if uzs is None:
            await say(message, "❌ Valyuta kursi topilmadi! Avval '✍️ Qo'lda kurs kiritish'.")
            return
        await db.set_bot_setting("qoshimcha_xarajat_qolip", str(uzs))
        await state.clear()
        await say(
            message, "✅ Qo'shimcha xarajat saqlandi!",
            reply_markup=await narxlar_menu(message.from_user.id)
        )
    except ValueError:
        await say(message, "❌ Faqat musbat son! Misol: 2000")
    except Exception as e:
        await state.clear()
        await say_error(message, e, reply_markup=await narxlar_menu(message.from_user.id))


# ── Tannarx override (A keyin B) ──
@router.message(Tkey("🎯 Tannarx override"))
async def override_boshla(message: Message, state: FSMContext):
    if not await _faqat_superadmin(message):
        return
    await state.clear()
    t_info = await db.tannarx_hisobla()
    kod = await val.get_active()
    avto = await val.format_uzs(t_info["A_auto"])
    await state.update_data(step="A")
    await state.set_state(OverrideState.qiymat)
    await say(
        message,
        f"🎯 A blok tannarx override?\n"
        f"(Faol valyuta: {kod}; avtomatik: {avto})\n"
        f"Avtomatga qaytarish: 0\nMisol: 9000"
    )


@router.message(OverrideState.qiymat)
async def override_saqlash(message: Message, state: FSMContext):
    try:
        qiymat = float(message.text.replace(",", "."))
        if qiymat < 0:
            raise ValueError
        data = await state.get_data()
        step = data.get("step", "A")
        kalit = "tannarx_override_A" if step == "A" else "tannarx_override_B"
        if qiymat == 0:
            await db.set_bot_setting(kalit, "")  # avtomatga qaytarish
        else:
            uzs = await val.active_to_uzs(qiymat)
            if uzs is None:
                await say(message, "❌ Valyuta kursi topilmadi! Avval '✍️ Qo'lda kurs kiritish'.")
                return
            await db.set_bot_setting(kalit, str(uzs))

        if step == "A":
            t_info = await db.tannarx_hisobla()
            kod = await val.get_active()
            avto = await val.format_uzs(t_info["B_auto"])
            await state.update_data(step="B")
            await say(
                message,
                f"🎯 B blok tannarx override?\n"
                f"(Faol valyuta: {kod}; avtomatik: {avto})\n"
                f"Avtomatga qaytarish: 0\nMisol: 5000"
            )
        else:
            await state.clear()
            await say(
                message, "✅ Override saqlandi!",
                reply_markup=await narxlar_menu(message.from_user.id)
            )
    except ValueError:
        await say(message, "❌ Faqat son! (0 = avtomat)")
    except Exception as e:
        await state.clear()
        await say_error(message, e, reply_markup=await narxlar_menu(message.from_user.id))


# ── Hisoblangan tannarx (faqat ko'rish) ──
@router.message(Tkey("📊 Hisoblangan tannarx"))
async def hisoblangan_tannarx(message: Message):
    if not await _faqat_superadmin(message):
        return
    try:
        ti = await db.tannarx_hisobla()
        sotuv_A = await db.get_bot_setting("sotuv_narx_A")
        sotuv_B = await db.get_bot_setting("sotuv_narx_B")
        sotuv_A = float(sotuv_A) if sotuv_A else 0.0
        sotuv_B = float(sotuv_B) if sotuv_B else 0.0

        text = "📊 Hisoblangan tannarx (1 qolip):\n\n"
        for d in ti["tafsil"]:
            text += f"   {d['nomi']}: {await val.format_uzs(d['summa'])}\n"
        text += f"\n   Material: {await val.format_uzs(ti['material'])}\n"
        text += f"   Ishchi haqi: {await val.format_uzs(ti['ishchi'])}\n"
        text += f"   Qo'shimcha: {await val.format_uzs(ti['qoshimcha'])}\n"
        text += f"   ─────\n   1 qolip tannarxi: {await val.format_uzs(ti['qolip'])}\n\n"

        a_belgi = " (override)" if ti["A_override"] is not None else ""
        b_belgi = " (override)" if ti["B_override"] is not None else ""
        text += f"🧱 1 A blok tannarxi: {await val.format_uzs(ti['A'])}{a_belgi}\n"
        text += f"🧱 1 B blok tannarxi: {await val.format_uzs(ti['B'])}{b_belgi}\n\n"

        text += f"💰 Sotuv narxi A: {await val.format_uzs(sotuv_A)}\n"
        text += f"💰 Sotuv narxi B: {await val.format_uzs(sotuv_B)}\n"
        text += f"📈 Foyda A: {await val.format_uzs(sotuv_A - ti['A'])}\n"
        text += f"📈 Foyda B: {await val.format_uzs(sotuv_B - ti['B'])}"

        await say(message, text, reply_markup=await narxlar_menu(message.from_user.id))
    except Exception as e:
        await say_error(message, e, reply_markup=await narxlar_menu(message.from_user.id))
