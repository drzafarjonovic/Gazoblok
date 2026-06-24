from aiogram import Router
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import timezone, timedelta
import database as db
from translation import (
    Tkey, eq, say, say_error, build_keyboard, build_mixed_keyboard,
)

router = Router()

# GMT+5 timezone
TOSHKENT_TZ = timezone(timedelta(hours=5))


class InventarizatsiyaState(StatesGroup):
    mahsulot_tanlash = State()
    block_tanlash = State()
    real_hisob = State()
    izoh = State()


async def inventory_menu(user_id):
    return await build_keyboard(user_id, [
        ["📊 Inventarizatsiya kiritish"],
        ["📋 Inventarizatsiya tarixi"],
        ["🏠 Asosiy menyu"],
    ])


async def _kb(user_id, dinamik_rows, static_rows):
    return await build_mixed_keyboard(user_id, dinamik_rows, static_rows)


def _label(p):
    return f"{p['emoji']} {p['nomi']}"


async def _mahsulot_keyboard(user_id):
    prods = await db.get_mahsulotlar(faqat_faol=True)
    rows = [[_label(p)] for p in prods]
    return await _kb(user_id, rows, [["🏠 Asosiy menyu"]]), prods


@router.message(Tkey("📋 Inventarizatsiya"))
async def inventarizatsiya(message: Message):
    await say(message, "📋 Inventarizatsiya:",
              reply_markup=await inventory_menu(message.from_user.id))


@router.message(Tkey("📊 Inventarizatsiya kiritish"))
async def inv_kiritish(message: Message, state: FSMContext):
    user_id = message.from_user.id
    prods = await db.get_mahsulotlar(faqat_faol=True)
    if not prods:
        await say(message, "❌ Mahsulot yo'q.", reply_markup=await inventory_menu(user_id))
        return
    await state.clear()
    if len(prods) == 1:
        await _block_sorov(message, state, prods[0])
        return
    kb, _ = await _mahsulot_keyboard(user_id)
    await state.set_state(InventarizatsiyaState.mahsulot_tanlash)
    await say(message, "📦 Qaysi mahsulot?", reply_markup=kb)


async def _block_sorov(message, state, mahsulot):
    user_id = message.from_user.id
    bloklar = await db.get_finished_goods(mahsulot["id"])
    if not bloklar:
        await state.clear()
        await say(message, f"❌ '{mahsulot['nomi']}' uchun blok yo'q!",
                  reply_markup=await inventory_menu(user_id))
        return
    await state.update_data(pid=mahsulot["id"], mahsulot_nomi=mahsulot["nomi"], bloklar=bloklar)
    await state.set_state(InventarizatsiyaState.block_tanlash)
    text = "📦 Joriy bot hisob:\n\n"
    for b in bloklar:
        text += f"   {b['nomi']}: {b['qoldiq']} ta\n"
    text += "\nQaysi blok uchun inventarizatsiya?"
    rows = [[b["nomi"]] for b in bloklar]
    await say(message, text, reply_markup=await _kb(user_id, rows, [["🏠 Asosiy menyu"]]))


@router.message(InventarizatsiyaState.mahsulot_tanlash)
async def inv_mahsulot(message: Message, state: FSMContext):
    if await eq(message, "🏠 Asosiy menyu"):
        await state.clear()
        return
    prods = await db.get_mahsulotlar(faqat_faol=True)
    text = (message.text or "").strip()
    tanlangan = next((p for p in prods if _label(p) == text), None)
    if not tanlangan:
        await say(message, "❌ Tugmalardan birini tanlang!")
        return
    await _block_sorov(message, state, tanlangan)


@router.message(InventarizatsiyaState.block_tanlash)
async def inv_block(message: Message, state: FSMContext):
    if await eq(message, "🏠 Asosiy menyu"):
        await state.clear()
        return
    data = await state.get_data()
    bloklar = data.get("bloklar", [])
    text = (message.text or "").strip()
    tanlangan = next((b for b in bloklar if b["nomi"] == text), None)
    if not tanlangan:
        await say(message, "❌ Tugmalardan birini tanlang!")
        return
    await state.update_data(block_kod=tanlangan["kod"], block_nomi=tanlangan["nomi"],
                            bot_hisob=tanlangan["qoldiq"])
    await state.set_state(InventarizatsiyaState.real_hisob)
    await say(message,
              f"🧱 {tanlangan['nomi']}\n"
              f"Bot hisob: {tanlangan['qoldiq']} ta\n\nReal (haqiqiy) soni nechta?")


@router.message(InventarizatsiyaState.real_hisob)
async def inv_real_hisob(message: Message, state: FSMContext):
    try:
        real_hisob = int(message.text.strip())
        if real_hisob < 0:
            raise ValueError
    except (ValueError, AttributeError):
        await say(message, "❌ Faqat musbat son kiriting!")
        return
    await state.update_data(real_hisob=real_hisob)
    await state.set_state(InventarizatsiyaState.izoh)
    data = await state.get_data()
    farq = real_hisob - data["bot_hisob"]
    farq_text = f"+{farq}" if farq > 0 else str(farq)
    await say(message,
              f"📊 Farq: {farq_text} ta\n\n"
              f"Izoh kiriting (ixtiyoriy):\nMisol: Hisobdan kam chiqdi\nYoki: 0 (izohsiz)")


@router.message(InventarizatsiyaState.izoh)
async def inv_izoh(message: Message, state: FSMContext, user: dict = None):
    user_id = message.from_user.id
    try:
        izoh = message.text.strip()
        if izoh == "0":
            izoh = ""
        data = await state.get_data()
        pid = data["pid"]
        block_kod = data["block_kod"]
        block_nomi = data.get("block_nomi", block_kod)
        bot_hisob = data["bot_hisob"]
        real_hisob = data["real_hisob"]

        farq = await db.add_inventarizatsiya(
            pid, db.bugungi_sana(), block_kod, bot_hisob, real_hisob, izoh, user_id)

        if user is None:
            user = await db.get_user(user_id)
        await db.add_audit_log(
            user_id, user["ism"] if user else str(user_id),
            user["rol"] if user else "-", "Inventarizatsiya kiritildi",
            f"{data.get('mahsulot_nomi','')} | {block_nomi}: "
            f"bot={bot_hisob}, real={real_hisob}, farq={farq}")
        await state.clear()
        farq_text = f"+{farq}" if farq > 0 else str(farq)
        await say(message,
                  f"✅ Inventarizatsiya saqlandi!\n\n"
                  f"🧱 {block_nomi}\n"
                  f"   Bot hisob: {bot_hisob} ta\n"
                  f"   Real hisob: {real_hisob} ta\n"
                  f"   Farq: {farq_text} ta\n"
                  f"   Bot yangilandi: {real_hisob} ta",
                  reply_markup=await inventory_menu(user_id))
    except Exception as e:
        await state.clear()
        await say_error(message, e, reply_markup=await inventory_menu(user_id))


@router.message(Tkey("📋 Inventarizatsiya tarixi"))
async def inv_tarixi(message: Message):
    try:
        logs = await db.get_inventarizatsiya_tarixi(20)
        if not logs:
            await say(message, "📋 Inventarizatsiya tarixi bo'sh.",
                      reply_markup=await inventory_menu(message.from_user.id))
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
            prod = log.get("product_nomi") or ""
            text += (
                f"📅 {vaqt_str} | {prod} | {log['block_type']}\n"
                f"   Bot: {log['bot_hisob']} | Real: {log['real_hisob']} | Farq: {farq_text}\n"
                f"   {log['user_ism'] or 'Noma`lum'}\n")
            if log["izoh"]:
                text += f"   📝 {log['izoh']}\n"
            text += "\n"
        if len(text) > 4000:
            text = text[:4000] + "\n..."
        await say(message, text, reply_markup=await inventory_menu(message.from_user.id))
    except Exception as e:
        await say_error(message, e)
