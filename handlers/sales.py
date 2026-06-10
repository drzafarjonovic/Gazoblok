from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import date
import database as db

router = Router()

class SalesState(StatesGroup):
    block_type = State()
    miqdor = State()

def sales_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💰 Sotuv kiritish")],
            [KeyboardButton(text="📋 Bugungi sotuv")],
            [KeyboardButton(text="🏠 Asosiy menyu")],
        ],
        resize_keyboard=True
    )

def block_type_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="A blok (60×20×30)")],
            [KeyboardButton(text="B blok (60×10×30)")],
            [KeyboardButton(text="🏠 Asosiy menyu")],
        ],
        resize_keyboard=True
    )

@router.message(F.text == "💰 Sotuv")
async def sotuv(message: Message):
    await message.answer(
        "💰 Sotuv bo'limi:",
        reply_markup=sales_menu()
    )

@router.message(F.text == "💰 Sotuv kiritish")
async def sotuv_kiritish(message: Message, state: FSMContext):
    await state.set_state(SalesState.block_type)
    await message.answer(
        "Qaysi blok sotildi?",
        reply_markup=block_type_menu()
    )

@router.message(SalesState.block_type)
async def sotuv_block_type(message: Message, state: FSMContext):
    if message.text not in ["A blok (60×20×30)", "B blok (60×10×30)"]:
        await message.answer("❌ Tugmalardan birini tanlang!")
        return
    block_type = "A" if "A blok" in message.text else "B"
    await state.update_data(block_type=block_type)
    await state.set_state(SalesState.miqdor)
    await message.answer(
        f"{'A' if block_type == 'A' else 'B'} blokdan nechta sotildi?\n"
        f"Misol: 100"
    )

@router.message(SalesState.miqdor)
async def sotuv_miqdor(message: Message, state: FSMContext):
    try:
        miqdor = int(message.text)
        if miqdor <= 0:
            raise ValueError
        data = await state.get_data()
        block_type = data["block_type"]
        bugun = str(date.today())
        await db.add_sales_log(bugun, block_type, miqdor)
        await state.clear()
        await message.answer(
            f"✅ Sotuv kiritildi!\n\n"
            f"🧱 {block_type} blok: {miqdor} ta sotildi",
            reply_markup=sales_menu()
        )
    except ValueError:
        await message.answer("❌ Faqat musbat son kiriting! Misol: 100")

@router.message(F.text == "📋 Bugungi sotuv")
async def bugungi_sotuv(message: Message):
    bugun = str(date.today())
    logs = await db.get_sales_by_date(bugun)

    if not logs:
        await message.answer("📋 Bugun hali sotuv kiritilmagan.")
        return

    A_jami = sum(log[1] for log in logs if log[0] == "A")
    B_jami = sum(log[1] for log in logs if log[0] == "B")

    text = (
        f"📋 Bugungi sotuv:\n\n"
        f"🧱 A blok: {A_jami} ta\n"
        f"🧱 B blok: {B_jami} ta\n"
        f"📦 Jami: {A_jami + B_jami} ta"
    )
    await message.answer(text, reply_markup=sales_menu())
