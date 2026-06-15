from aiogram import Router
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import database as db
from translation import Tkey, eq, canon, say, say_error, build_keyboard

router = Router()

BLOCK_BUTTONS = {"A blok": "A", "B blok": "B"}


class FinishedGoodsState(StatesGroup):
    block_type = State()
    miqdor = State()


async def finished_menu(user_id):
    return await build_keyboard(user_id, [
        ["📦 Tayyor mahsulot qoldig'i"],
        ["✏️ Dastlabki qoldiqni kiritish"],
        ["🏠 Asosiy menyu"],
    ])


async def block_type_menu(user_id):
    return await build_keyboard(user_id, [
        ["A blok"],
        ["B blok"],
        ["🏠 Asosiy menyu"],
    ])


@router.message(Tkey("🏬 Tayyor mahsulot"))
async def tayyor_mahsulot(message: Message):
    await say(
        message,
        "🏬 Tayyor mahsulot ombori:",
        reply_markup=await finished_menu(message.from_user.id)
    )


@router.message(Tkey("📦 Tayyor mahsulot qoldig'i"))
async def tayyor_qoldiq(message: Message):
    try:
        goods = await db.get_finished_goods()
        if not goods:
            await say(
                message,
                "❌ Ma'lumot yo'q!",
                reply_markup=await finished_menu(message.from_user.id)
            )
            return
        text = "📦 Tayyor mahsulot ombori:\n\n"
        jami = 0
        for g in goods:
            text += f"🧱 {g[0]} blok: {g[1]} ta\n"
            jami += g[1]
        text += f"\n📊 Jami: {jami} ta"
        await say(message, text, reply_markup=await finished_menu(message.from_user.id))
    except Exception as e:
        await say_error(
            message, e,
            reply_markup=await finished_menu(message.from_user.id)
        )


@router.message(Tkey("✏️ Dastlabki qoldiqni kiritish"))
async def dastlabki_qoldiq(message: Message, state: FSMContext):
    try:
        user = await db.get_user(message.from_user.id)
        if not user or not await db.has_permission(
                message.from_user.id, user["rol"], "tayyor_mahsulot_tahrirlash"):
            await say(
                message,
                "❌ Sizda bu amalni bajarish huquqi yo'q!",
                reply_markup=await finished_menu(message.from_user.id)
            )
            return
        await state.clear()
        await state.set_state(FinishedGoodsState.block_type)

        goods = await db.get_finished_goods()
        text = "Qaysi blok uchun qoldiq kiritasiz?\n\n"
        text += "Joriy qoldiq:\n"
        for g in goods:
            text += f"   {g[0]} blok: {g[1]} ta\n"

        await say(message, text, reply_markup=await block_type_menu(message.from_user.id))
    except Exception as e:
        await say_error(
            message, e,
            reply_markup=await finished_menu(message.from_user.id)
        )


@router.message(FinishedGoodsState.block_type)
async def finished_block_type(message: Message, state: FSMContext):
    if await eq(message, "🏠 Asosiy menyu"):
        await state.clear()
        return
    uz = await canon(message, list(BLOCK_BUTTONS.keys()))
    if not uz:
        await say(message, "❌ Tugmalardan birini tanlang!")
        return
    try:
        block_type = BLOCK_BUTTONS[uz]
        await state.update_data(block_type=block_type)
        await state.set_state(FinishedGoodsState.miqdor)

        goods = await db.get_finished_goods()
        joriy = next((g[1] for g in goods if g[0] == block_type), 0)
        await say(
            message,
            f"🧱 {block_type} blok uchun yangi qoldiqni kiriting:\n"
            f"Hozirgi qoldiq: {joriy} ta\n\n"
            f"Misol: 500"
        )
    except Exception as e:
        await state.clear()
        await say_error(
            message, e,
            reply_markup=await finished_menu(message.from_user.id)
        )


@router.message(FinishedGoodsState.miqdor)
async def finished_miqdor(message: Message, state: FSMContext):
    try:
        miqdor = int(message.text.strip())
        if miqdor < 0:
            raise ValueError
        data = await state.get_data()
        block_type = data["block_type"]

        goods = await db.get_finished_goods()
        eski_qoldiq = next((g[1] for g in goods if g[0] == block_type), 0)

        await db.set_finished_goods(block_type, miqdor)

        user = await db.get_user(message.from_user.id)
        await db.add_audit_log(
            message.from_user.id,
            user["ism"] if user else str(message.from_user.id),
            user["rol"] if user else "-",
            "Tayyor mahsulot qoldig'i yangilandi",
            f"{block_type} blok: {eski_qoldiq} → {miqdor} ta"
        )
        await state.clear()
        await say(
            message,
            f"✅ {block_type} blok qoldig'i yangilandi!\n\n"
            f"   Eski: {eski_qoldiq} ta\n"
            f"   Yangi: {miqdor} ta",
            reply_markup=await finished_menu(message.from_user.id)
        )
    except ValueError:
        await say(message, "❌ Faqat musbat son kiriting! Misol: 500")
    except Exception as e:
        await state.clear()
        await say_error(
            message, e,
            reply_markup=await finished_menu(message.from_user.id)
        )
