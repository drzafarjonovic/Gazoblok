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
            [KeyboardButton(text="🗑️ Oxirgi sotuvni o'chirish")],
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
    try:
        goods = await db.get_finished_goods()
        text = "Qaysi blok sotildi?\n\n"
        text += "📦 Joriy tayyor mahsulot:\n"
        for g in goods:
            text += f"   {g[0]} blok: {g[1]} ta\n"
        await state.set_state(SalesState.block_type)
        await message.answer(text, reply_markup=block_type_menu())
    except Exception as e:
        await message.answer(f"❌ Xatolik: {str(e)}", reply_markup=sales_menu())

@router.message(SalesState.block_type)
async def sotuv_block_type(message: Message, state: FSMContext):
    if message.text == "🏠 Asosiy menyu":
        await state.clear()
        return
    if message.text not in ["A blok (60×20×30)", "B blok (60×10×30)"]:
        await message.answer("❌ Tugmalardan birini tanlang!")
        return
    block_type = "A" if "A blok" in message.text else "B"
    await state.update_data(block_type=block_type)
    await state.set_state(SalesState.miqdor)

    goods = await db.get_finished_goods()
    qoldiq = next((g[1] for g in goods if g[0] == block_type), 0)
    await message.answer(
        f"📦 {block_type} blokdan nechta sotildi?\n"
        f"Mavjud: {qoldiq} ta\n\n"
        f"Misol: 100"
    )

@router.message(SalesState.miqdor)
async def sotuv_miqdor(message: Message, state: FSMContext):
    try:
        miqdor = int(message.text.strip())
        if miqdor <= 0:
            raise ValueError
        data = await state.get_data()
        block_type = data["block_type"]
        bugun = str(date.today())
        user_id = message.from_user.id

        muvaffaqiyat, xabar = await db.add_sales_log(
            bugun, block_type, miqdor, user_id
        )

        await state.clear()

        if not muvaffaqiyat:
            await message.answer(xabar, reply_markup=sales_menu())
            return

        # Audit log
        user = await db.get_user(user_id)
        await db.add_audit_log(
            user_id,
            user["ism"] if user else str(user_id),
            user["rol"] if user else "-",
            "Sotuv kiritildi",
            f"{block_type} blok: {miqdor} ta sotildi"
        )

        # Yangilangan qoldiq
        goods = await db.get_finished_goods()
        yangi_qoldiq = next((g[1] for g in goods if g[0] == block_type), 0)

        await message.answer(
            f"✅ Sotuv kiritildi!\n\n"
            f"🧱 {block_type} blok: {miqdor} ta sotildi\n"
            f"📦 Qoldi: {yangi_qoldiq} ta",
            reply_markup=sales_menu()
        )
    except ValueError:
        await message.answer("❌ Faqat musbat son kiriting! Misol: 100")
    except Exception as e:
        await state.clear()
        await message.answer(
            f"❌ Xatolik: {str(e)}",
            reply_markup=sales_menu()
        )

# ── Oxirgi sotuvni o'chirish ──
@router.message(F.text == "🗑️ Oxirgi sotuvni o'chirish")
async def oxirgi_sotuv_ochirish(message: Message):
    try:
        user = await db.get_user(message.from_user.id)
        natija = await db.delete_last_sale()
        if natija:
            await db.add_audit_log(
                message.from_user.id,
                user["ism"] if user else str(message.from_user.id),
                user["rol"] if user else "-",
                "Sotuv o'chirildi",
                "Oxirgi sotuv yozuvi o'chirildi va omborga qaytarildi"
            )
            await message.answer(
                "✅ Oxirgi sotuv o'chirildi!\n"
                "📦 Mahsulot omborga qaytarildi.",
                reply_markup=sales_menu()
            )
        else:
            await message.answer(
                "❌ O'chiriladigan yozuv yo'q!",
                reply_markup=sales_menu()
            )
    except Exception as e:
        await message.answer(
            f"❌ Xatolik: {str(e)}",
            reply_markup=sales_menu()
        )

# ── Bugungi sotuv ──
@router.message(F.text == "📋 Bugungi sotuv")
async def bugungi_sotuv(message: Message):
    try:
        bugun = str(date.today())
        logs = await db.get_sales_by_date(bugun)

        if not logs:
            await message.answer(
                "📋 Bugun hali sotuv kiritilmagan.",
                reply_markup=sales_menu()
            )
            return

        A_jami = sum(log[1] for log in logs if log[0] == "A")
        B_jami = sum(log[1] for log in logs if log[0] == "B")

        goods = await db.get_finished_goods()
        qoldiq_text = ""
        for g in goods:
            qoldiq_text += f"   {g[0]} blok: {g[1]} ta\n"

        text = (
            f"📋 Bugungi sotuv:\n\n"
            f"🧱 A blok: {A_jami} ta\n"
            f"🧱 B blok: {B_jami} ta\n"
            f"📦 Jami sotildi: {A_jami + B_jami} ta\n\n"
            f"🏬 Tayyor mahsulot qoldig'i:\n"
            f"{qoldiq_text}"
        )
        await message.answer(text, reply_markup=sales_menu())
    except Exception as e:
        await message.answer(
            f"❌ Xatolik: {str(e)}",
            reply_markup=sales_menu()
)
