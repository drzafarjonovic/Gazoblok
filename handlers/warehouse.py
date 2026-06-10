from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import database as db

router = Router()

class WarehouseState(StatesGroup):
    material_id = State()
    miqdor = State()

def warehouse_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📥 Xom ashyo kirim")],
            [KeyboardButton(text="🏪 Joriy qoldiqlar")],
            [KeyboardButton(text="🏠 Asosiy menyu")],
        ],
        resize_keyboard=True
    )

@router.message(F.text == "🏪 Ombor")
async def ombor(message: Message):
    await message.answer(
        "🏪 Ombor bo'limi:",
        reply_markup=warehouse_menu()
    )

@router.message(F.text == "🏪 Joriy qoldiqlar")
async def joriy_qoldiqlar(message: Message):
    materials = await db.get_materials()
    if not materials:
        await message.answer("❌ Hali material kiritilmagan!")
        return

    settings = await db.get_settings()
    min_map = {s[3]: s[1] for s in settings}

    text = "🏪 Joriy qoldiqlar:\n\n"
    for m in materials:
        material_id = m[0]
        nomi = m[1]
        qoldiq = m[2]
        birlik = m[3]
        min_ch = min_map.get(material_id)

        if min_ch and qoldiq <= min_ch:
            status = "⚠️"
        else:
            status = "✅"

        text += f"{status} {nomi}: {qoldiq:.2f} {birlik}\n"
        if min_ch:
            text += f"   Min chegara: {min_ch} {birlik}\n"

    await message.answer(text)

@router.message(F.text == "📥 Xom ashyo kirim")
async def xom_ashyo_kirim(message: Message, state: FSMContext):
    materials = await db.get_materials()
    if not materials:
        await message.answer(
            "❌ Avval material qo'shing!\n"
            "⚙️ Sozlamalar → ➕ Material qo'shish"
        )
        return

    text = "📦 Qaysi material keldi?\nRaqamini kiriting:\n\n"
    for m in materials:
        text += f"{m[0]}. {m[1]} ({m[3]})\n"

    await state.update_data(materials=materials)
    await state.set_state(WarehouseState.material_id)
    await message.answer(text)

@router.message(WarehouseState.material_id)
async def kirim_material(message: Message, state: FSMContext):
    try:
        material_id = int(message.text)
        data = await state.get_data()
        materials = data["materials"]
        material = next((m for m in materials if m[0] == material_id), None)

        if not material:
            await message.answer("❌ Bunday raqam yo'q! Qaytadan kiriting.")
            return

        await state.update_data(
            material_id=material_id,
            material_nomi=material[1],
            material_birlik=material[3],
            joriy_qoldiq=material[2]
        )
        await state.set_state(WarehouseState.miqdor)
        await message.answer(
            f"📥 {material[1]} dan qancha keldi?\n"
            f"(Birlik: {material[3]})\n"
            f"Misol: 10"
        )
    except ValueError:
        await message.answer("❌ Faqat raqam kiriting! Misol: 1")

@router.message(WarehouseState.miqdor)
async def kirim_miqdor(message: Message, state: FSMContext):
    try:
        miqdor = float(message.text.replace(",", "."))
        if miqdor <= 0:
            raise ValueError
        data = await state.get_data()

        yangi_qoldiq = data["joriy_qoldiq"] + miqdor
        await db.update_material_qoldiq(data["material_id"], yangi_qoldiq)
        await state.clear()

        await message.answer(
            f"✅ Kirim kiritildi!\n\n"
            f"📦 {data['material_nomi']}\n"
            f"   Kirim: +{miqdor} {data['material_birlik']}\n"
            f"   Yangi qoldiq: {yangi_qoldiq:.2f} {data['material_birlik']}",
            reply_markup=warehouse_menu()
        )
    except ValueError:
        await message.answer("❌ Faqat musbat son kiriting! Misol: 10")
