from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import database as db

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

def sozlamalar_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Material qo'shish")],
            [KeyboardButton(text="📦 Materiallar ro'yxati")],
            [KeyboardButton(text="✏️ Materialni tahrirlash")],
            [KeyboardButton(text="🗑️ Materialni o'chirish")],
            [KeyboardButton(text="📋 Qolip formulasi")],
            [KeyboardButton(text="⚠️ Minimum chegara")],
            [KeyboardButton(text="🔔 Avtomatik hisobot vaqti")],
            [KeyboardButton(text="🗑️ Barcha ma'lumotlarni tozalash")],
            [KeyboardButton(text="🏠 Asosiy menyu")],
        ],
        resize_keyboard=True
    )

@router.message(F.text == "⚙️ Sozlamalar")
async def sozlamalar(message: Message):
    await message.answer(
        "⚙️ Sozlamalar bo'limi:",
        reply_markup=sozlamalar_menu()
    )

# ── Material qo'shish ──
@router.message(F.text == "➕ Material qo'shish")
async def material_qoshish(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(MaterialState.nomi)
    await message.answer(
        "Material nomini kiriting:\nMisol: Sement"
    )

@router.message(MaterialState.nomi)
async def material_nomi(message: Message, state: FSMContext):
    await state.update_data(nomi=message.text.strip())
    await state.set_state(MaterialState.qoldiq)
    await message.answer(
        "Hozir omborda qancha bor?\nMisol: 30"
    )

@router.message(MaterialState.qoldiq)
async def material_qoldiq(message: Message, state: FSMContext):
    try:
        qoldiq = float(message.text.replace(",", "."))
        if qoldiq < 0:
            raise ValueError
        await state.update_data(qoldiq=qoldiq)
        await state.set_state(MaterialState.birlik)
        await message.answer(
            "Birligini kiriting:\n"
            "Misol: tonna, kg, g, litr, ml, meshok"
        )
    except ValueError:
        await message.answer("❌ Faqat musbat son kiriting! Misol: 30")

@router.message(MaterialState.birlik)
async def material_birlik(message: Message, state: FSMContext):
    try:
        data = await state.get_data()
        birlik = message.text.strip()
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
        await message.answer(
            f"✅ {data['nomi']} qo'shildi!\n"
            f"Miqdor: {data['qoldiq']} {birlik}",
            reply_markup=sozlamalar_menu()
        )
    except Exception as e:
        await state.clear()
        await message.answer(
            f"❌ Xatolik: {str(e)}",
            reply_markup=sozlamalar_menu()
        )

# ── Materiallar ro'yxati ──
@router.message(F.text == "📦 Materiallar ro'yxati")
async def materiallar_royxati(message: Message):
    try:
        materials = await db.get_materials()
        if not materials:
            await message.answer(
                "❌ Hali material kiritilmagan!",
                reply_markup=sozlamalar_menu()
            )
            return
        text = "📦 Materiallar:\n\n"
        for m in materials:
            qoldiq_asl = db.asosiydan_birlikga(m[2], m[4])
            text += f"🔹 {m[0]}. {m[1]} — {qoldiq_asl:.2f} {m[4]}\n"
        await message.answer(text, reply_markup=sozlamalar_menu())
    except Exception as e:
        await message.answer(f"❌ Xatolik: {str(e)}")

# ── Materialni tahrirlash ──
@router.message(F.text == "✏️ Materialni tahrirlash")
async def material_tahrirlash(message: Message, state: FSMContext):
    try:
        await state.clear()
        materials = await db.get_materials()
        if not materials:
            await message.answer(
                "❌ Hali material kiritilmagan!",
                reply_markup=sozlamalar_menu()
            )
            return
        text = "✏️ Qaysi materialni tahrirlash?\nRaqamini kiriting:\n\n"
        for m in materials:
            qoldiq_asl = db.asosiydan_birlikga(m[2], m[4])
            text += f"{m[0]}. {m[1]} — {qoldiq_asl:.2f} {m[4]}\n"
        await state.update_data(materials=[(m[0], m[1], m[2], m[3], m[4]) for m in materials])
        await state.set_state(MaterialEditState.material_id)
        await message.answer(text)
    except Exception as e:
        await message.answer(f"❌ Xatolik: {str(e)}")

@router.message(MaterialEditState.material_id)
async def material_tahrirlash_id(message: Message, state: FSMContext):
    try:
        material_id = int(message.text.strip())
        data = await state.get_data()
        materials = data["materials"]
        material = next((m for m in materials if m[0] == material_id), None)
        if not material:
            await message.answer("❌ Bunday raqam yo'q! Qaytadan kiriting.")
            return
        await state.update_data(
            material_id=material_id,
            eski_nomi=material[1]
        )
        await state.set_state(MaterialEditState.nomi)
        await message.answer(
            f"Yangi nom kiriting:\n"
            f"(Hozirgi: {material[1]})"
        )
    except ValueError:
        await message.answer("❌ Faqat raqam kiriting!")

@router.message(MaterialEditState.nomi)
async def material_tahrirlash_nomi(message: Message, state: FSMContext):
    await state.update_data(nomi=message.text.strip())
    await state.set_state(MaterialEditState.qoldiq)
    await message.answer("Yangi qoldiq miqdorini kiriting:\nMisol: 25")

@router.message(MaterialEditState.qoldiq)
async def material_tahrirlash_qoldiq(message: Message, state: FSMContext):
    try:
        qoldiq = float(message.text.replace(",", "."))
        if qoldiq < 0:
            raise ValueError
        await state.update_data(qoldiq=qoldiq)
        await state.set_state(MaterialEditState.birlik)
        await message.answer(
            "Yangi birlikni kiriting:\nMisol: tonna, kg, litr"
        )
    except ValueError:
        await message.answer("❌ Faqat musbat son kiriting!")

@router.message(MaterialEditState.birlik)
async def material_tahrirlash_birlik(message: Message, state: FSMContext):
    try:
        data = await state.get_data()
        birlik = message.text.strip()
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
        await message.answer(
            f"✅ Material yangilandi!\n"
            f"{data['nomi']} — {data['qoldiq']} {birlik}",
            reply_markup=sozlamalar_menu()
        )
    except Exception as e:
        await state.clear()
        await message.answer(
            f"❌ Xatolik: {str(e)}",
            reply_markup=sozlamalar_menu()
        )

# ── Materialni o'chirish ──
@router.message(F.text == "🗑️ Materialni o'chirish")
async def material_ochirish(message: Message, state: FSMContext):
    try:
        await state.clear()
        materials = await db.get_materials()
        if not materials:
            await message.answer(
                "❌ Hali material kiritilmagan!",
                reply_markup=sozlamalar_menu()
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
        await message.answer(text)
    except Exception as e:
        await message.answer(f"❌ Xatolik: {str(e)}")

@router.message(MaterialDeleteState.material_id)
async def material_ochirish_id(message: Message, state: FSMContext):
    try:
        material_id = int(message.text.strip())
        data = await state.get_data()
        materials = data["materials"]
        material = next((m for m in materials if m[0] == material_id), None)
        if not material:
            await message.answer("❌ Bunday raqam yo'q!")
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
        await message.answer(
            f"✅ {material[1]} o'chirildi!",
            reply_markup=sozlamalar_menu()
        )
    except ValueError:
        await message.answer("❌ Faqat raqam kiriting!")
        await state.clear()
    except Exception as e:
        await state.clear()
        await message.answer(
            f"❌ Xatolik: {str(e)}",
            reply_markup=sozlamalar_menu()
        )

# ── Qolip formulasi ──
@router.message(F.text == "📋 Qolip formulasi")
async def qolip_formulasi(message: Message):
    try:
        formula = await db.get_qolip_formula()
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="✏️ Formulani yangilash")],
                [KeyboardButton(text="🏠 Asosiy menyu")],
            ],
            resize_keyboard=True
        )
        if not formula:
            await message.answer(
                "❌ Formula kiritilmagan!\n"
                "✏️ Formulani yangilash tugmasini bosing.",
                reply_markup=keyboard
            )
            return
        text = "📋 1 qolipga ketadigan materiallar:\n\n"
        for f in formula:
            text += f"🔹 {f[0]}: {f[1]} {f[2]}\n"
        await message.answer(text, reply_markup=keyboard)
    except Exception as e:
        await message.answer(f"❌ Xatolik: {str(e)}")

@router.message(F.text == "✏️ Formulani yangilash")
async def formula_yangilash(message: Message, state: FSMContext):
    try:
        await state.clear()
        materials = await db.get_materials()
        if not materials:
            await message.answer(
                "❌ Avval material qo'shing!",
                reply_markup=sozlamalar_menu()
            )
            return
        await db.clear_qolip_formula()
        await state.update_data(
            materials=[(m[0], m[1], m[2], m[3], m[4]) for m in materials],
            index=0
        )
        await state.set_state(FormulaState.miqdor)
        m = materials[0]
        await message.answer(
            f"1 qolipga {m[1]} dan qancha ketadi?\n"
            f"(Ombordagi birlik: {m[4]})\n"
            f"Misol: 110"
        )
    except Exception as e:
        await state.clear()
        await message.answer(f"❌ Xatolik: {str(e)}")

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
        await message.answer(
            f"{m[1]} uchun birlikni kiriting:\n"
            f"Misol: kg, g, litr, ml\n"
            f"(Omborda: {m[4]})"
        )
    except ValueError:
        await message.answer("❌ Faqat musbat son kiriting! Misol: 110")

@router.message(FormulaState.birlik)
async def formula_birlik(message: Message, state: FSMContext):
    try:
        data = await state.get_data()
        materials = data["materials"]
        index = data["index"]
        miqdor = data["miqdor"]
        birlik = message.text.strip()
        m = materials[index]
        await db.add_qolip_formula(m[0], miqdor, birlik)
        index += 1
        if index < len(materials):
            await state.update_data(index=index)
            await state.set_state(FormulaState.miqdor)
            next_m = materials[index]
            await message.answer(
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
            await message.answer(
                "✅ Formula saqlandi!",
                reply_markup=sozlamalar_menu()
            )
    except Exception as e:
        await state.clear()
        await message.answer(
            f"❌ Xatolik: {str(e)}",
            reply_markup=sozlamalar_menu()
        )

# ── Minimum chegara ──
@router.message(F.text == "⚠️ Minimum chegara")
async def min_chegara(message: Message, state: FSMContext):
    try:
        await state.clear()
        materials = await db.get_materials()
        if not materials:
            await message.answer(
                "❌ Avval material qo'shing!",
                reply_markup=sozlamalar_menu()
            )
            return
        await state.update_data(
            materials=[(m[0], m[1], m[2], m[3], m[4]) for m in materials],
            index=0
        )
        await state.set_state(MinChegaraState.miqdor)
        m = materials[0]
        await message.answer(
            f"{m[1]} uchun minimum chegara qancha?\n"
            f"(Birlik: {m[4]})\n"
            f"0 kiriting — chegara o'chiriladi\n"
            f"Misol: 5"
        )
    except Exception as e:
        await message.answer(f"❌ Xatolik: {str(e)}")

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
            await message.answer(
                f"{next_m[1]} uchun minimum chegara qancha?\n"
                f"(Birlik: {next_m[4]})\n"
                f"0 kiriting — chegara o'chiriladi\n"
                f"Misol: 5"
            )
        else:
            await state.clear()
            await message.answer(
                "✅ Minimum chegaralar saqlandi!",
                reply_markup=sozlamalar_menu()
            )
    except ValueError:
        await message.answer("❌ Faqat musbat son kiriting!")

# ── Avtomatik hisobot ──
@router.message(F.text == "🔔 Avtomatik hisobot vaqti")
async def avto_hisobot(message: Message, state: FSMContext):
    try:
        await state.clear()
        joriy = await db.get_bot_setting("hisobot_vaqti")
        joriy_text = f"Hozirgi vaqt: {joriy}" if joriy else "Hali belgilanmagan"
        await state.set_state(AutoHisobotState.vaqt)
        await message.answer(
            f"🔔 Avtomatik hisobot vaqtini kiriting:\n"
            f"{joriy_text}\n\n"
            f"Format: HH:MM\n"
            f"Misol: 21:00\n\n"
            f"O'chirish uchun: 0"
        )
    except Exception as e:
        await message.answer(f"❌ Xatolik: {str(e)}")

@router.message(AutoHisobotState.vaqt)
async def avto_hisobot_saqlash(message: Message, state: FSMContext):
    try:
        text = message.text.strip()
        if text == "0":
            await db.set_bot_setting("hisobot_vaqti", "")
            await state.clear()
            await message.answer(
                "✅ Avtomatik hisobot o'chirildi!",
                reply_markup=sozlamalar_menu()
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
        await message.answer(
            f"✅ Avtomatik hisobot belgilandi!\n"
            f"⏰ Har kuni soat {vaqt} da hisobot keladi.",
            reply_markup=sozlamalar_menu()
        )
    except ValueError:
        await message.answer(
            "❌ Noto'g'ri format!\n"
            "To'g'ri: 21:00 yoki 08:30"
        )

# ── Barcha ma'lumotlarni tozalash ──
@router.message(F.text == "🗑️ Barcha ma'lumotlarni tozalash")
async def barchani_tozalash(message: Message, state: FSMContext):
    await state.clear()
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Ha, tozalash")],
            [KeyboardButton(text="❌ Yo'q, bekor qilish")],
        ],
        resize_keyboard=True
    )
    await message.answer(
        "⚠️ DIQQAT!\n\n"
        "Barcha materiallar, formula, ishlab chiqarish "
        "va sotuv ma'lumotlari o'chib ketadi!\n\n"
        "Davom etasizmi?",
        reply_markup=keyboard
    )

@router.message(F.text == "✅ Ha, tozalash")
async def barchani_tozalash_ha(message: Message):
    try:
        user = await db.get_user(message.from_user.id)
        if not user or user["rol"] != "superadmin":
            await message.answer("❌ Faqat Super Admin tozalashi mumkin!")
            return
        await db.clear_all_data()
        await db.add_audit_log(
            message.from_user.id,
            user["ism"],
            user["rol"],
            "Barcha ma'lumotlar tozalandi",
            "To'liq tizim tozalash"
        )
        await message.answer(
            "✅ Barcha ma'lumotlar tozalandi!",
            reply_markup=sozlamalar_menu()
        )
    except Exception as e:
        await message.answer(f"❌ Xatolik: {str(e)}")

@router.message(F.text == "❌ Yo'q, bekor qilish")
async def barchani_tozalash_yoq(message: Message):
    await message.answer(
        "❌ Bekor qilindi!",
        reply_markup=sozlamalar_menu()
    )
