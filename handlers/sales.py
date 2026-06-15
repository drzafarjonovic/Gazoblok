from aiogram import Router
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import database as db
from translation import Tkey, eq, canon, say, say_error, build_keyboard

router = Router()

# Blok turi tugmalari (kanonik o'zbekcha)
BLOCK_BUTTONS = {
    "A blok (60×20×30)": "A",
    "B blok (60×10×30)": "B",
}


class SalesState(StatesGroup):
    block_type = State()
    miqdor = State()


async def sales_menu(user_id):
    return await build_keyboard(user_id, [
        ["💰 Sotuv kiritish"],
        ["📋 Bugungi sotuv"],
        ["🗑️ Oxirgi sotuvni o'chirish"],
        ["🏠 Asosiy menyu"],
    ])


async def block_type_menu(user_id):
    return await build_keyboard(user_id, [
        ["A blok (60×20×30)"],
        ["B blok (60×10×30)"],
        ["🏠 Asosiy menyu"],
    ])


@router.message(Tkey("💰 Sotuv"))
async def sotuv(message: Message):
    await say(
        message,
        "💰 Sotuv bo'limi:",
        reply_markup=await sales_menu(message.from_user.id)
    )


@router.message(Tkey("💰 Sotuv kiritish"))
async def sotuv_kiritish(message: Message, state: FSMContext):
    try:
        goods = await db.get_finished_goods()
        text = "Qaysi blok sotildi?\n\n"
        text += "📦 Joriy tayyor mahsulot:\n"
        for g in goods:
            text += f"   {g[0]} blok: {g[1]} ta\n"
        await state.set_state(SalesState.block_type)
        await say(message, text, reply_markup=await block_type_menu(message.from_user.id))
    except Exception as e:
        await say_error(message, e, reply_markup=await sales_menu(message.from_user.id))


@router.message(SalesState.block_type)
async def sotuv_block_type(message: Message, state: FSMContext):
    if await eq(message, "🏠 Asosiy menyu"):
        await state.clear()
        return
    uz = await canon(message, list(BLOCK_BUTTONS.keys()))
    if not uz:
        await say(message, "❌ Tugmalardan birini tanlang!")
        return
    block_type = BLOCK_BUTTONS[uz]
    await state.update_data(block_type=block_type)
    await state.set_state(SalesState.miqdor)

    goods = await db.get_finished_goods()
    qoldiq = next((g[1] for g in goods if g[0] == block_type), 0)
    await say(
        message,
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
        bugun = db.bugungi_sana()
        user_id = message.from_user.id

        muvaffaqiyat, xabar = await db.add_sales_log(
            bugun, block_type, miqdor, user_id
        )

        await state.clear()

        if not muvaffaqiyat:
            await say(message, xabar, reply_markup=await sales_menu(user_id))
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

        await say(
            message,
            f"✅ Sotuv kiritildi!\n\n"
            f"🧱 {block_type} blok: {miqdor} ta sotildi\n"
            f"📦 Qoldi: {yangi_qoldiq} ta",
            reply_markup=await sales_menu(user_id)
        )
    except ValueError:
        await say(message, "❌ Faqat musbat son kiriting! Misol: 100")
    except Exception as e:
        await state.clear()
        await say_error(
            message, e,
            reply_markup=await sales_menu(message.from_user.id)
        )


# ── Oxirgi sotuvni o'chirish ──
@router.message(Tkey("🗑️ Oxirgi sotuvni o'chirish"))
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
            await say(
                message,
                "✅ Oxirgi sotuv o'chirildi!\n"
                "📦 Mahsulot omborga qaytarildi.",
                reply_markup=await sales_menu(message.from_user.id)
            )
        else:
            await say(
                message,
                "❌ O'chiriladigan yozuv yo'q!",
                reply_markup=await sales_menu(message.from_user.id)
            )
    except Exception as e:
        await say_error(
            message, e,
            reply_markup=await sales_menu(message.from_user.id)
        )


# ── Bugungi sotuv ──
@router.message(Tkey("📋 Bugungi sotuv"))
async def bugungi_sotuv(message: Message):
    try:
        bugun = db.bugungi_sana()
        logs = await db.get_sales_by_date(bugun)

        if not logs:
            await say(
                message,
                "📋 Bugun hali sotuv kiritilmagan.",
                reply_markup=await sales_menu(message.from_user.id)
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
        await say(message, text, reply_markup=await sales_menu(message.from_user.id))
    except Exception as e:
        await say_error(
            message, e,
            reply_markup=await sales_menu(message.from_user.id)
        )
