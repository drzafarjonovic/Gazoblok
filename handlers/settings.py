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

class FormulaState(StatesGroup):
    miqdor = State()
    birlik = State()

class MinChegaraState(StatesGroup):
    miqdor = State()

class ClearConfirmState(StatesGroup):
    tasdiqlash = State()

class AutoHisobotState(StatesGroup):
    vaqt = State()

def sozlamalar_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Material qo'shish")],
            [KeyboardButton(text="📋 Qolip formulasi")],
            [KeyboardButton(text="⚠️ Minimum chegara")],
            [KeyboardButton(text="📦 Materiallar ro'yxati")],
            [KeyboardButton(text="✏️ Materialni tahrirlash")],
            [KeyboardButton(text="🗑️ Materialni o'chirish")],
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
    await state.set_state(MaterialState.nomi)
    await message.answer("Material nomini kiriting:\nMisol: Sement")

@router.message(MaterialState.nomi)
async def material_nomi(message: Message, state: FSMContext):
    await state.update_data(nomi=message.text)
    await state.set_state(MaterialState.qoldiq)
    await message.answer("Hozir omborda qancha bor?\nMisol: 30")

@router.message(MaterialState.qoldiq)
async def material_qoldiq(message: Message, state: FSMContext):
    try:
        qoldiq = float(message.text.replace(",", "."))
        await state.update_data(qoldiq=qoldiq)
        await state.set_state(MaterialState.birlik)
        await message.answer(
            "Birligini kiriting:\n"
            "Misol: tonna, kg, litr, meshok"
        )
    except ValueError:
        await message.answer("❌ Faqat son kiriting! Misol: 30")

@router.message(MaterialState.birlik)
async def material_birlik(message: Message, state: FSMContext):
    data = await state.get_data()
    await db.add_material(data["nomi"], data["qoldiq"], message.text)
    await state.clear()
    await message.answer(
        f"✅ {data['nomi']} qo'shildi!\n"
        f"Miqdor: {data['qoldiq']} {message.text}",
        reply_markup=sozlamalar_menu()
    )

# ── Materiallar ro'yxati ──
@router.message(F.text == "📦 Materiallar ro'yxati")
async def materiallar_royxati(message: Message):
    materials = await db.get_materials()
    if not materials:
        await message.answer("❌ Hali material kiritilmagan!")
        return
    text = "📦 Materiallar:\n\n"
    for m in materials:
        qoldiq_asl = db.asosiydan_birlikga(m[2], m[4])
        text += f"🔹 {m[0]}. {m[1]} — {qoldiq_asl:.2f} {m[4]}\n"
    await message.answer(text)

# ── Materialni tahrirlash ──
@router.message(F.text == "✏️ Materialni tahrirlash")
async def material_tahrirlash(message: Message, state: FSMContext):
    materials = await db.get_materials()
    if not materials:
        await message.answer("❌ Hali material kiritilmagan!")
        return
    text = "✏️ Qaysi materialni tahrirlash?\nRaqamini kiriting:\n\n"
    for m in materials:
        qoldiq_asl = db.asosiydan_birlikga(m[2], m[4])
        text += f"{m[0]}. {m[1]} — {qoldiq_asl:.2f} {m[4]}\n"
    await state.update_data(materials=materials)
    await state.set_state(MaterialEditState.material_id)
    await message.answer(text)

@router.message(MaterialEditState.material_id)
async def material_tahrirlash_id(message: Message, state: FSMContext):
    try:
        material_id = int(message.text)
        data = await state.get_data()
        materials = data["materials"]
        material = next((m for m in materials if m[0] == material_id), None)
        if not material:
            await message.answer("❌ Bunday raqam yo'q!")
            return
        await state.update_data(material_id=material_id)
        await state.set_state(MaterialEditState.nomi)
        await message.answer(
            f"Yangi nom kiriting:\n"
            f"(Hozirgi: {material[1]})"
        )
    except ValueError:
        await message.answer("❌ Faqat raqam kiriting!")

@router.message(MaterialEditState.nomi)
async def material_tahrirlash_nomi(message: Message, state: FSMContext):
    await state.update_data(nomi=message.text)
    await state.set_state(MaterialEditState.qoldiq)
    await message.answer("Yangi qoldiq miqdorini kiriting:\nMisol: 25")

@router.message(MaterialEditState.qoldiq)
async def material_tahrirlash_qoldiq(message: Message, state: FSMContext):
    try:
        qoldiq = float(message.text.replace(",", "."))
        await state.update_data(qoldiq=qoldiq)
        await state.set_state(MaterialEditState.birlik)
        await message.answer("Yangi birlikni kiriting:\nMisol: tonna, kg, litr")
    except ValueError:
        await message.answer("❌ Faqat son kiriting!")

@router.message(MaterialEditState.birlik)
async def material_tahrirlash_birlik(message: Message, state: FSMContext):
    data = await state.get_data()
    await db.update_material(
        data["material_id"],
        data["nomi"],
        data["qoldiq"],
        message.text
    )
    await state.clear()
    await message.answer(
        f"✅ Material yangilandi!\n"
        f"{data['nomi']} — {data['qoldiq']} {message.text}",
        reply_markup=sozlamalar_menu()
    )

# ── Materialni o'chirish ──
@router.message(F.text == "🗑️ Materialni o'chirish")
async def material_ochirish(message: Message, state: FSMContext):
    materials = await db.get_materials()
    if not materials:
        await message.answer("❌ Hali material kiritilmagan!")
        return
    text = "🗑️ Qaysi materialni o'chirish?\nRaqamini kiriting:\n\n"
    for m in materials:
        qoldiq_asl = db.asosiydan_birlikga(m[2], m[4])
        text += f"{m[0]}. {m[1]} — {qoldiq_asl:.2f} {m[4]}\n"
    await state.update_data(materials=materials)
    await state.set_state(ClearConfirmState.tasdiqlash)
    await message.answer(text)

@router.message(ClearConfirmState.tasdiqlash)
async def material_ochirish_tasdiqlash(message: Message, state: FSMContext):
    try:
        material_id = int(message.text)
        data = await state.get_data()
        materials = data["materials"]
        material = next((m for m in materials if m[0] == material_id), None)
        if not material:
            await message.answer("❌ Bunday raqam yo'q!")
            await state.clear()
            return
        await db.delete_material(material_id)
        await state.clear()
        await message.answer(
            f"✅ {material[1]} o'chirildi!",
            reply_markup=sozlamalar_menu()
        )
    except ValueError:
        await message.answer("❌ Faqat raqam kiriting!")
        await state.clear()

# ── Avtomatik hisobot vaqti ──
@router.message(F.text == "🔔 Avtomatik hisobot vaqti")
async def avto_hisobot_vaqti(message: Message, state: FSMContext):
    joriy_vaqt = await db.get_bot_setting("hisobot_vaqti")
    if joriy_vaqt:
        joriy_text = f"Hozirgi vaqt: {joriy_vaqt}"
    else:
        joriy_text = "Hali belgilanmagan"
    await state.set_state(AutoHisobotState.vaqt)
    await message.answer(
        f"🔔 Avtomatik kunlik hisobot vaqtini kiriting:\n"
        f"{joriy_text}\n\n"
        f"Format: HH:MM\n"
        f"Misol: 21:00 yoki 08:30\n\n"
        f"O'chirish uchun: 0"
    )

@router.message(AutoHisobotState.vaqt)
async def avto_hisobot_vaqti_saqlash(message: Message, state: FSMContext):
    text = message.text.strip()
    if text == "0":
        await db.set_bot_setting("hisobot_vaqti", "")
        await state.clear()
        await message.answer(
            "✅ Avtomatik hisobot o'chirildi!",
            reply_markup=sozlamalar_menu()
        )
        return
    try:
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
            f"✅ Avtomatik hisobot vaqti belgilandi!\n"
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
async def barchani_tozalash(message: Message):
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
async def barchani_tozalash_tasdiqlash(message: Message):
    await db.clear_all_data()
    await message.answer(
        "✅ Barcha ma'lumotlar tozalandi!",
        reply_markup=sozlamalar_menu()
    )

@router.message(F.text == "❌ Yo'q, bekor qilish")
async def barchani_tozalash_bekor(message: Message):
    await message.answer(
        "❌ Bekor qilindi!",
        reply_markup=sozlamalar_menu()
    )

# ── Qolip formulasi ──
@router.message(F.text == "📋 Qolip formulasi")
async def qolip_formulasi(message: Message):
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

@router.message(F.text == "✏️ Formulani yangilash")
async def formula_yangilash(message: Message, state: FSMContext):
    materials = await db.get_materials()
    if not materials:
        await message.answer("❌ Avval material qo'shing!")
        return
    await db.clear_qolip_formula()
    await state.update_data(materials=materials, index=0)
    await state.set_state(FormulaState.miqdor)
    m = materials[0]
    await message.answer(
        f"1 qolipga {m[1]} dan qancha ketadi?\n"
        f"(Ombordagi birlik: {m[4]})\n"
        f"Misol: 110"
    )

@router.message(FormulaState.miqdor)
async def formula_miqdor(message: Message, state: FSMContext):
    try:
        miqdor = float(message.text.replace(",", "."))
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
        await message.answer("❌ Faqat son kiriting! Misol: 110")

@router.message(FormulaState.birlik)
async def formula_birlik(message: Message, state: FSMContext):
    data = await state.get_data()
    materials = data["materials"]
    index = data["index"]
    miqdor = data["miqdor"]
    m = materials[index]
    await db.add_qolip_formula(m[0], miqdor, message.text)
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
        await state.clear()
        await message.answer(
            "✅ Formula saqlandi!",
            reply_markup=sozlamalar_menu()
        )

# ── Minimum chegara ──
@router.message(F.text == "⚠️ Minimum chegara")
async def min_chegara(message: Message, state: FSMContext):
    materials = await db.get_materials()
    if not materials:
        await message.answer("❌ Avval material qo'shing!")
        return
    await state.update_data(materials=materials, index=0)
    await state.set_state(MinChegaraState.miqdor)
    m = materials[0]
    await message.answer(
        f"{m[1]} uchun minimum chegara qancha?\n"
        f"(Birlik: {m[4]})\n"
        f"Misol: 5"
    )

@router.message(MinChegaraState.miqdor)
async def min_chegara_miqdor(message: Message, state: FSMContext):
    try:
        miqdor = float(message.text.replace(",", "."))
        data = await state.get_data()
        materials = data["materials"]
        index = data["index"]
        m = materials[index]
        min_asosiy, _ = db.birlikni_asosiyga(miqdor, m[4])
        await db.set_min_chegara(m[0], min_asosiy)
        index += 1
        if index < len(materials):
            await state.update_data(index=index)
            next_m = materials[index]
            await message.answer(
                f"{next_m[1]} uchun minimum chegara qancha?\n"
                f"(Birlik: {next_m[4]})\n"
                f"Misol: 5"
            )
        else:
            await state.clear()
            await message.answer(
                "✅ Minimum chegaralar saqlandi!",
                reply_markup=sozlamalar_menu()
            )
    except ValueError:
        await message.answer("❌ Faqat son kiriting!")
