from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import database as db

router = Router()

class WarehouseState(StatesGroup):
    material_id = State()
    miqdor = State()
    birlik = State()

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
        qoldiq_asosiy = m[2]
        asosiy_birlik = m[3]
        asl_birlik = m[4]

        # Asl birlikda ko'rsatish
        qoldiq_asl = db.asosiydan_birlikga(qoldiq_asosiy, asl_birlik)

        min_ch = min_map.get(material_id)
        if min_ch and qoldiq_asosiy <= min_ch:
            status = "⚠️"
        else:
            status = "✅"

        text += f"{status} {nomi}: {qoldiq_asl:.2f} {asl_birlik}\n"

        if min_ch:
            min_asl = db.asosiydan_birlikga(min_ch, asl_birlik)
            text += f"   Min chegara: {min_asl:.2f} {asl_birlik}\n"

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
        text += f"{m[0]}. {m[1]} ({m[4]})\n"

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
            asl_birlik=material[4],
            joriy_qoldiq_asosiy=material[2]
        )
        await state.set_state(WarehouseState.miqdor)
        await message.answer(
            f"📥 {material[1]} dan qancha keldi?\n"
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
        await state.update_data(miqdor=miqdor)
        await state.set_state(WarehouseState.birlik)
        data = await state.get_data()
        await message.answer(
            f"Birligini kiriting:\n"
            f"Misol: tonna, kg, g, litr, ml\n"
            f"(Odatdagi: {data['asl_birlik']})"
        )
    except ValueError:
        await message.answer("❌ Faqat musbat son kiriting! Misol: 10")

@router.message(WarehouseState.birlik)
async def kirim_birlik(message: Message, state: FSMContext):
    data = await state.get_data()
    birlik = message.text.strip()
    miqdor = data["miqdor"]
    asl_birlik = data["asl_birlik"]
    joriy_qoldiq_asosiy = data["joriy_qoldiq_asosiy"]

    # Kirimni asosiy birlikka o'tkazamiz
    kirim_asosiy, _ = db.birlikni_asosiyga(miqdor, birlik)
    yangi_qoldiq_asosiy = joriy_qoldiq_asosiy + kirim_asosiy

    await db.update_material_qoldiq(data["material_id"], yangi_qoldiq_asosiy)
    await state.clear()

    # Asl birlikda ko'rsatamiz
    yangi_qoldiq_asl = db.asosiydan_birlikga(yangi_qoldiq_asosiy, asl_birlik)

    await message.answer(
        f"✅ Kirim kiritildi!\n\n"
        f"📦 {data['material_nomi']}\n"
        f"   Kirim: +{miqdor} {birlik}\n"
        f"   Yangi qoldiq: {yangi_qoldiq_asl:.2f} {asl_birlik}",
        reply_markup=warehouse_menu()
        )
