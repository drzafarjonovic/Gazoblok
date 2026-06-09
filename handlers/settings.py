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

class FormulaState(StatesGroup):
    material_id = State()
    miqdor = State()
    birlik = State()

class MinChegaraState(StatesGroup):
    material_id = State()
    miqdor = State()

def sozlamalar_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Material qo'shish")],
            [KeyboardButton(text="📋 Qolip formulasi")],
            [KeyboardButton(text="⚠️ Minimum chegara")],
            [KeyboardButton(text="📦 Materiallar ro'yxati")],
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
        await message.answer("Birligini kiriting:\nMisol: tonna yoki kg yoki litr")
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
        text += f"🔹 {m[0]}. {m[1]} — {m[2]} {m[3]}\n"
    await message.answer(text)

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
        f"(Birlik: {m[3]})\nMisol: 110"
    )

@router.message(FormulaState.miqdor)
async def formula_miqdor(message: Message, state: FSMContext):
    try:
        miqdor = float(message.text.replace(",", "."))
        data = await state.get_data()
        materials = data["materials"]
        index = data["index"]
        m = materials[index]
        await db.add_qolip_formula(m[0], miqdor, m[3])
        index += 1
        if index < len(materials):
            await state.update_data(index=index)
            next_m = materials[index]
            await message.answer(
                f"1 qolipga {next_m[1]} dan qancha ketadi?\n"
                f"(Birlik: {next_m[3]})\nMisol: 50"
            )
        else:
            await state.clear()
            await message.answer(
                "✅ Formula saqlandi!",
                reply_markup=sozlamalar_menu()
            )
    except ValueError:
        await message.answer("❌ Faqat son kiriting! Misol: 110")

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
        f"(Birlik: {m[3]})\nMisol: 5"
    )

@router.message(MinChegaraState.miqdor)
async def min_chegara_miqdor(message: Message, state: FSMContext):
    try:
        miqdor = float(message.text.replace(",", "."))
        data = await state.get_data()
        materials = data["materials"]
        index = data["index"]
        m = materials[index]
        await db.set_min_chegara(m[0], miqdor)
        index += 1
        if index < len(materials):
            await state.update_data(index=index)
            next_m = materials[index]
            await message.answer(
                f"{next_m[1]} uchun minimum chegara qancha?\n"
                f"(Birlik: {next_m[3]})\nMisol: 5"
            )
        else:
            await state.clear()
            await message.answer(
                "✅ Minimum chegaralar saqlandi!",
                reply_markup=sozlamalar_menu()
            )
    except ValueError:
        await message.answer("❌ Faqat son kiriting!")
