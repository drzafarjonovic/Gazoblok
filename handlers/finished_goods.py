from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import database as db

router = Router()

class FinishedGoodsState(StatesGroup):
    block_type = State()
    miqdor = State()

def finished_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📦 Tayyor mahsulot qoldig'i")],
            [KeyboardButton(text="✏️ Dastlabki qoldiqni kiritish")],
            [KeyboardButton(text="🏠 Asosiy menyu")],
        ],
        resize_keyboard=True
    )

def block_type_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="A blok")],
            [KeyboardButton(text="B blok")],
            [KeyboardButton(text="🏠 Asosiy menyu")],
        ],
        resize_keyboard=True
    )

@router.message(F.text == "🏬 Tayyor mahsulot")
async def tayyor_mahsulot(message: Message):
    await message.answer(
        "🏬 Tayyor mahsulot ombori:",
        reply_markup=finished_menu()
    )

@router.message(F.text == "📦 Tayyor mahsulot qoldig'i")
async def tayyor_qoldiq(message: Message):
    goods = await db.get_finished_goods()
    if not goods:
        await message.answer("❌ Ma'lumot yo'q!")
        return
    text = "📦 Tayyor mahsulot ombori:\n\n"
    jami = 0
    for g in goods:
        text += f"🧱 {g[0]} blok: {g[1]} ta\n"
        jami += g[1]
    text += f"\n📊 Jami: {jami} ta"
    await message.answer(text, reply_markup=finished_menu())

@router.message(F.text == "✏️ Dastlabki qoldiqni kiritish")
async def dastlabki_qoldiq(message: Message, state: FSMContext):
    # Faqat superadmin va omborchi
    user = await db.get_user(message.from_user.id)
    if not user or user["rol"] not in ["superadmin", "omborchi"]:
        await message.answer("❌ Sizda bu amalni bajarish huquqi yo'q!")
        return
    await state.set_state(FinishedGoodsState.block_type)
    await message.answer(
        "Qaysi blok uchun qoldiq kiritasiz?",
        reply_markup=block_type_menu()
    )

@router.message(FinishedGoodsState.block_type)
async def finished_block_type(message: Message, state: FSMContext):
    if message.text not in ["A blok", "B blok"]:
        await message.answer("❌ Tugmalardan birini tanlang!")
        return
    block_type = "A" if message.text == "A blok" else "B"
    await state.update_data(block_type=block_type)
    await state.set_state(FinishedGoodsState.miqdor)

    goods = await db.get_finished_goods()
    joriy = next((g[1] for g in goods if g[0] == block_type), 0)
    await message.answer(
        f"{block_type} blok uchun qoldiq kiritish:\n"
        f"Hozirgi qoldiq: {joriy} ta\n\n"
        f"Yangi qoldiqni kiriting:\nMisol: 500"
    )

@router.message(FinishedGoodsState.miqdor)
async def finished_miqdor(message: Message, state: FSMContext):
    try:
        miqdor = int(message.text)
        if miqdor < 0:
            raise ValueError
        data = await state.get_data()
        block_type = data["block_type"]

        # Eski qoldiqni olish
        goods = await db.get_finished_goods()
        eski_qoldiq = next((g[1] for g in goods if g[0] == block_type), 0)

        await db.set_finished_goods(block_type, miqdor)

        # Audit log
        user = await db.get_user(message.from_user.id)
        await db.add_audit_log(
            message.from_user.id,
            user["ism"] if user else "Noma'lum",
            user["rol"] if user else "-",
            "Tayyor mahsulot qoldig'i yangilandi",
            f"{block_type} blok: {eski_qoldiq} → {miqdor} ta"
        )

        await state.clear()
        await message.answer(
            f"✅ {block_type} blok qoldig'i yangilandi!\n"
            f"   Eski: {eski_qoldiq} ta\n"
            f"   Yangi: {miqdor} ta",
            reply_markup=finished_menu()
        )
    except ValueError:
        await message.answer("❌ Faqat musbat son kiriting! Misol: 500")
