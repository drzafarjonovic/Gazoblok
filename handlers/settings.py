from aiogram import Router
from aiogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
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


async def sozlamalar_menu(user_id):
    return await build_keyboard(user_id, [
        ["🌐 Tilni o'zgartirish"],
        ["💵 Narxlar va valyuta"],
        ["➕ Material qo'shish"],
        ["📦 Materiallar ro'yxati"],
        ["✏️ Materialni tahrirlash"],
        ["🗑️ Materialni o'chirish"],
        ["📋 Qolip formulasi"],
        ["⚠️ Minimum chegara"],
        ["🔔 Avtomatik hisobot vaqti"],
        ["🗑️ Barcha ma'lumotlarni tozalash"],
        ["🏠 Asosiy menyu"],
    ])


async def _faqat_superadmin(message: Message) -> bool:
    """Sozlamalar bo'limi faqat superadmin uchun."""
    user = await db.get_user(message.from_user.id)
    if not user or user["rol"] != "superadmin":
        await say(message, "❌ Ruxsat yo'q! Bu bo'lim faqat Super Admin uchun.")
        return False
    return True


@router.message(Tkey("⚙️ Sozlamalar"))
async def sozlamalar(message: Message):
    if not await _faqat_superadmin(message):
        return
    await say(
        message,
        "⚙️ Sozlamalar bo'limi:",
        reply_markup=await sozlamalar_menu(message.from_user.id)
    )


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
@router.message(Tkey("✏️ Materialni tahrirlash"))
async def material_tahrirlash(message: Message, state: FSMContext):
    if not await _faqat_superadmin(message):
        return
    try:
        await state.clear()
        materials = await db.get_materials()
        if not materials:
            await say(
                message,
                "❌ Hali material kiritilmagan!",
                reply_markup=await sozlamalar_menu(message.from_user.id)
            )
            return
        text = "✏️ Qaysi materialni tahrirlash?\nRaqamini kiriting:\n\n"
        for m in materials:
            qoldiq_asl = db.asosiydan_birlikga(m[2], m[4])
            text += f"{m[0]}. {m[1]} — {qoldiq_asl:.2f} {m[4]}\n"
        await state.update_data(materials=[(m[0], m[1], m[2], m[3], m[4]) for m in materials])
        await state.set_state(MaterialEditState.material_id)
        await say(message, text)
    except Exception as e:
        await say_error(message, e)


@router.message(MaterialEditState.material_id)
async def material_tahrirlash_id(message: Message, state: FSMContext):
    try:
        material_id = int(message.text.strip())
        data = await state.get_data()
        materials = data["materials"]
        material = next((m for m in materials if m[0] == material_id), None)
        if not material:
            await say(message, "❌ Bunday raqam yo'q! Qaytadan kiriting.")
            return
        await state.update_data(
            material_id=material_id,
            eski_nomi=material[1]
        )
        await state.set_state(MaterialEditState.nomi)
        await say(
            message,
            f"Yangi nom kiriting:\n"
            f"(Hozirgi: {material[1]})"
        )
    except ValueError:
        await say(message, "❌ Faqat raqam kiriting!")


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
    try:
        await state.clear()
        materials = await db.get_materials()
        if not materials:
            await say(
                message,
                "❌ Hali material kiritilmagan!",
                reply_markup=await sozlamalar_menu(message.from_user.id)
            )
            return
        text = "🗑️ Qaysi materialni o'chirish?\nRaqamini kiriting:\n\n"
        for m in materials:
            qoldiq_asl = db.asosiydan_birlikga(m[2], m[4])
            text += f"{m[0]}. {m[1]} — {qoldiq_asl:.2f} {m[4]}\n"
        await state.update_data(
            materials=[(m[0], m[1], m[2], m[3], m[4]) for m in materials]
        )
        await state.set_state(MaterialDeleteState.material_id)
        await say(message, text)
    except Exception as e:
        await say_error(message, e)


@router.message(MaterialDeleteState.material_id)
async def material_ochirish_id(message: Message, state: FSMContext):
    try:
        material_id = int(message.text.strip())
        data = await state.get_data()
        materials = data["materials"]
        material = next((m for m in materials if m[0] == material_id), None)
        if not material:
            await say(message, "❌ Bunday raqam yo'q!")
            await state.clear()
            return
        await db.delete_material(material_id)
        user = await db.get_user(message.from_user.id)
        await db.add_audit_log(
            message.from_user.id,
            user["ism"] if user else str(message.from_user.id),
            user["rol"] if user else "-",
            "Material o'chirildi",
            f"{material[1]} o'chirildi"
        )
        await state.clear()
        await say(
            message,
            f"✅ {material[1]} o'chirildi!",
            reply_markup=await sozlamalar_menu(message.from_user.id)
        )
    except ValueError:
        await say(message, "❌ Faqat raqam kiriting!")
        await state.clear()
    except Exception as e:
        await state.clear()
        await say_error(
            message, e,
            reply_markup=await sozlamalar_menu(message.from_user.id)
        )


# ── Qolip formulasi ──
@router.message(Tkey("📋 Qolip formulasi"))
async def qolip_formulasi(message: Message):
    if not await _faqat_superadmin(message):
        return
    try:
        formula = await db.get_qolip_formula()
        keyboard = await build_keyboard(message.from_user.id, [
            ["✏️ Formulani yangilash"],
            ["🏠 Asosiy menyu"],
        ])
        if not formula:
            await say(
                message,
                "❌ Formula kiritilmagan!\n"
                "✏️ Formulani yangilash tugmasini bosing.",
                reply_markup=keyboard
            )
            return
        text = "📋 1 qolipga ketadigan materiallar:\n\n"
        for f in formula:
            text += f"🔹 {f[0]}: {f[1]} {f[2]}\n"
        await say(message, text, reply_markup=keyboard)
    except Exception as e:
        await say_error(message, e)


@router.message(Tkey("✏️ Formulani yangilash"))
async def formula_yangilash(message: Message, state: FSMContext):
    if not await _faqat_superadmin(message):
        return
    try:
        await state.clear()
        materials = await db.get_materials()
        if not materials:
            await say(
                message,
                "❌ Avval material qo'shing!",
                reply_markup=await sozlamalar_menu(message.from_user.id)
            )
            return
        await db.clear_qolip_formula()
        await state.update_data(
            materials=[(m[0], m[1], m[2], m[3], m[4]) for m in materials],
            index=0
        )
        await state.set_state(FormulaState.miqdor)
        m = materials[0]
        await say(
            message,
            f"1 qolipga {m[1]} dan qancha ketadi?\n"
            f"(Ombordagi birlik: {m[4]})\n"
            f"Misol: 110"
        )
    except Exception as e:
        await state.clear()
        await say_error(message, e)


@router.message(FormulaState.miqdor)
async def formula_miqdor(message: Message, state: FSMContext):
    try:
        miqdor = float(message.text.replace(",", "."))
        if miqdor <= 0:
            raise ValueError
        await state.update_data(miqdor=miqdor)
        await state.set_state(FormulaState.birlik)
        data = await state.get_data()
        materials = data["materials"]
        index = data["index"]
        m = materials[index]
        await say(
            message,
            f"{m[1]} uchun birlikni kiriting:\n"
            f"Misol: kg, g, litr, ml\n"
            f"(Omborda: {m[4]})"
        )
    except ValueError:
        await say(message, "❌ Faqat musbat son kiriting! Misol: 110")


@router.message(FormulaState.birlik)
async def formula_birlik(message: Message, state: FSMContext):
    try:
        data = await state.get_data()
        materials = data["materials"]
        index = data["index"]
        miqdor = data["miqdor"]
        birlik = message.text.strip()
        m = materials[index]
        # Birlik material o'lchamiga (kg/litr) mos kelishini tekshiramiz
        if (not db.birlik_qollab_quvvatlanadimi(birlik)
                or db.birlik_bazasi(birlik) != db.birlik_bazasi(m[4])):
            await say(
                message,
                f"❌ Birlik '{m[1]}' o'lchamiga mos emas "
                f"(ombor birligi: {m[4]}).\n"
                f"Bir xil o'lchamdagi birlik kiriting. Qaytadan:"
            )
            return
        await db.add_qolip_formula(m[0], miqdor, birlik)
        index += 1
        if index < len(materials):
            await state.update_data(index=index)
            await state.set_state(FormulaState.miqdor)
            next_m = materials[index]
            await say(
                message,
                f"1 qolipga {next_m[1]} dan qancha ketadi?\n"
                f"(Ombordagi birlik: {next_m[4]})\n"
                f"Misol: 50"
            )
        else:
            user = await db.get_user(message.from_user.id)
            await db.add_audit_log(
                message.from_user.id,
                user["ism"] if user else str(message.from_user.id),
                user["rol"] if user else "-",
                "Qolip formulasi yangilandi",
                f"{len(materials)} ta material formulasi saqlandi"
            )
            await state.clear()
            await say(
                message,
                "✅ Formula saqlandi!",
                reply_markup=await sozlamalar_menu(message.from_user.id)
            )
    except Exception as e:
        await state.clear()
        await say_error(
            message, e,
            reply_markup=await sozlamalar_menu(message.from_user.id)
        )


# ── Minimum chegara ──
@router.message(Tkey("⚠️ Minimum chegara"))
async def min_chegara(message: Message, state: FSMContext):
    if not await _faqat_superadmin(message):
        return
    try:
        await state.clear()
        materials = await db.get_materials()
        if not materials:
            await say(
                message,
                "❌ Avval material qo'shing!",
                reply_markup=await sozlamalar_menu(message.from_user.id)
            )
            return
        await state.update_data(
            materials=[(m[0], m[1], m[2], m[3], m[4]) for m in materials],
            index=0
        )
        await state.set_state(MinChegaraState.miqdor)
        m = materials[0]
        await say(
            message,
            f"{m[1]} uchun minimum chegara qancha?\n"
            f"(Birlik: {m[4]})\n"
            f"0 kiriting — chegara o'chiriladi\n"
            f"Misol: 5"
        )
    except Exception as e:
        await say_error(message, e)


@router.message(MinChegaraState.miqdor)
async def min_chegara_miqdor(message: Message, state: FSMContext):
    try:
        miqdor = float(message.text.replace(",", "."))
        if miqdor < 0:
            raise ValueError
        data = await state.get_data()
        materials = data["materials"]
        index = data["index"]
        m = materials[index]
        # Asosiy birlikka o'tkazib saqlaymiz
        min_asosiy, _ = db.birlikni_asosiyga(miqdor, m[4])
        await db.set_min_chegara(m[0], min_asosiy)
        index += 1
        if index < len(materials):
            await state.update_data(index=index)
            next_m = materials[index]
            await say(
                message,
                f"{next_m[1]} uchun minimum chegara qancha?\n"
                f"(Birlik: {next_m[4]})\n"
                f"0 kiriting — chegara o'chiriladi\n"
                f"Misol: 5"
            )
        else:
            await state.clear()
            await say(
                message,
                "✅ Minimum chegaralar saqlandi!",
                reply_markup=await sozlamalar_menu(message.from_user.id)
            )
    except ValueError:
        await say(message, "❌ Faqat musbat son kiriting!")


# ── Avtomatik hisobot ──
@router.message(Tkey("🔔 Avtomatik hisobot vaqti"))
async def avto_hisobot(message: Message, state: FSMContext):
    if not await _faqat_superadmin(message):
        return
    try:
        await state.clear()
        joriy = await db.get_bot_setting("hisobot_vaqti")
        joriy_text = f"Hozirgi vaqt: {joriy}" if joriy else "Hali belgilanmagan"
        await state.set_state(AutoHisobotState.vaqt)
        await say(
            message,
            f"🔔 Avtomatik hisobot vaqtini kiriting:\n"
            f"{joriy_text}\n\n"
            f"Format: HH:MM\n"
            f"Misol: 21:00\n\n"
            f"O'chirish uchun: 0"
        )
    except Exception as e:
        await say_error(message, e)


@router.message(AutoHisobotState.vaqt)
async def avto_hisobot_saqlash(message: Message, state: FSMContext):
    try:
        text = message.text.strip()
        if text == "0":
            await db.set_bot_setting("hisobot_vaqti", "")
            await state.clear()
            await say(
                message,
                "✅ Avtomatik hisobot o'chirildi!",
                reply_markup=await sozlamalar_menu(message.from_user.id)
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
        await db.set_bot_setting("hisobot_vaqti", vaqt)
        await state.clear()
        await say(
            message,
            f"✅ Avtomatik hisobot belgilandi!\n"
            f"⏰ Har kuni soat {vaqt} da hisobot keladi.",
            reply_markup=await sozlamalar_menu(message.from_user.id)
        )
    except ValueError:
        await say(
            message,
            "❌ Noto'g'ri format!\n"
            "To'g'ri: 21:00 yoki 08:30"
        )


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
