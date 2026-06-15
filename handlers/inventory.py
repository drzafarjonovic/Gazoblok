from aiogram import Router
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import timezone, timedelta
import database as db
from translation import Tkey, canon, say, build_keyboard

router = Router()

# GMT+5 timezone
TOSHKENT_TZ = timezone(timedelta(hours=5))

BLOCK_BUTTONS = {"A blok": "A", "B blok": "B"}


class InventarizatsiyaState(StatesGroup):
    block_type = State()
    real_hisob = State()
    izoh = State()


async def inventory_menu(user_id):
    return await build_keyboard(user_id, [
        ["📊 Inventarizatsiya kiritish"],
        ["📋 Inventarizatsiya tarixi"],
        ["🏠 Asosiy menyu"],
    ])


async def block_menu(user_id):
    return await build_keyboard(user_id, [
        ["A blok"],
        ["B blok"],
        ["🏠 Asosiy menyu"],
    ])


@router.message(Tkey("📋 Inventarizatsiya"))
async def inventarizatsiya(message: Message):
    await say(message, "📋 Inventarizatsiya:", reply_markup=await inventory_menu(message.from_user.id))


@router.message(Tkey("📊 Inventarizatsiya kiritish"))
async def inv_kiritish(message: Message, state: FSMContext):
    await state.clear()
    goods = await db.get_finished_goods()
    text = "📦 Joriy bot hisob:\n\n"
    for g in goods:
        text += f"   {g[0]} blok: {g[1]} ta\n"
    text += "\nQaysi blok uchun inventarizatsiya?"
    await state.set_state(InventarizatsiyaState.block_type)
    await say(message, text, reply_markup=await block_menu(message.from_user.id))


@router.message(InventarizatsiyaState.block_type)
async def inv_block_type(message: Message, state: FSMContext):
    uz = await canon(message, list(BLOCK_BUTTONS.keys()))
    if not uz:
        await say(message, "❌ Tugmalardan birini tanlang!")
        return
    block_type = BLOCK_BUTTONS[uz]
    goods = await db.get_finished_goods()
    bot_hisob = next((g[1] for g in goods if g[0] == block_type), 0)
    await state.update_data(block_type=block_type, bot_hisob=bot_hisob)
    await state.set_state(InventarizatsiyaState.real_hisob)
    await say(
        message,
        f"🧱 {block_type} blok\n"
        f"Bot hisob: {bot_hisob} ta\n\n"
        f"Real (haqiqiy) soni nechta?"
    )


@router.message(InventarizatsiyaState.real_hisob)
async def inv_real_hisob(message: Message, state: FSMContext):
    try:
        real_hisob = int(message.text.strip())
        if real_hisob < 0:
            raise ValueError
        await state.update_data(real_hisob=real_hisob)
        await state.set_state(InventarizatsiyaState.izoh)
        data = await state.get_data()
        farq = real_hisob - data["bot_hisob"]
        farq_text = f"+{farq}" if farq > 0 else str(farq)
        await say(
            message,
            f"📊 Farq: {farq_text} ta\n\n"
            f"Izoh kiriting (ixtiyoriy):\n"
            f"Misol: Hisobdan ko'ra kam chiqdi\n"
            f"Yoki: 0 (izohsiz)"
        )
    except ValueError:
        await say(message, "❌ Faqat musbat son kiriting!")


@router.message(InventarizatsiyaState.izoh)
async def inv_izoh(message: Message, state: FSMContext):
    try:
        izoh = message.text.strip()
        if izoh == "0":
            izoh = ""
        data = await state.get_data()
        block_type = data["block_type"]
        bot_hisob = data["bot_hisob"]
        real_hisob = data["real_hisob"]

        farq = await db.add_inventarizatsiya(
            db.bugungi_sana(), block_type,
            bot_hisob, real_hisob, izoh,
            message.from_user.id
        )

        user = await db.get_user(message.from_user.id)
        await db.add_audit_log(
            message.from_user.id,
            user["ism"] if user else str(message.from_user.id),
            user["rol"] if user else "-",
            "Inventarizatsiya kiritildi",
            f"{block_type} blok: bot={bot_hisob}, real={real_hisob}, farq={farq}"
        )
        await state.clear()
        farq_text = f"+{farq}" if farq > 0 else str(farq)
        await say(
            message,
            f"✅ Inventarizatsiya saqlandi!\n\n"
            f"🧱 {block_type} blok\n"
            f"   Bot hisob: {bot_hisob} ta\n"
            f"   Real hisob: {real_hisob} ta\n"
            f"   Farq: {farq_text} ta\n"
            f"   Bot yangilandi: {real_hisob} ta",
            reply_markup=await inventory_menu(message.from_user.id)
        )
    except Exception as e:
        await state.clear()
        await say(message, f"❌ Xatolik: {str(e)}", reply_markup=await inventory_menu(message.from_user.id))


@router.message(Tkey("📋 Inventarizatsiya tarixi"))
async def inv_tarixi(message: Message):
    try:
        logs = await db.get_inventarizatsiya_tarixi(20)
        if not logs:
            await say(message, "📋 Inventarizatsiya tarixi bo'sh.", reply_markup=await inventory_menu(message.from_user.id))
            return
        text = "📋 Inventarizatsiya tarixi:\n\n"
        for log in logs:
            vaqt = log["vaqt"]
            if hasattr(vaqt, "strftime"):
                if vaqt.tzinfo is None:
                    vaqt = vaqt.replace(tzinfo=timezone.utc).astimezone(TOSHKENT_TZ)
                vaqt_str = vaqt.strftime("%d.%m.%Y")
            else:
                vaqt_str = str(vaqt)[:10]
            farq = log["farq"]
            farq_text = f"+{farq}" if farq > 0 else str(farq)
            text += (
                f"📅 {vaqt_str} | {log['block_type']} blok\n"
                f"   Bot: {log['bot_hisob']} | Real: {log['real_hisob']} | Farq: {farq_text}\n"
                f"   {log['user_ism'] or 'Noma lum'}\n"
            )
            if log["izoh"]:
                text += f"   📝 {log['izoh']}\n"
            text += "\n"
        if len(text) > 4000:
            text = text[:4000] + "\n..."
        await say(message, text, reply_markup=await inventory_menu(message.from_user.id))
    except Exception as e:
        await say(message, f"❌ Xatolik: {str(e)}")
