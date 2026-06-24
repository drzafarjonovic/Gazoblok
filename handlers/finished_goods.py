from aiogram import Router
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import database as db
from translation import (
    Tkey, eq, say, say_error, build_keyboard, build_mixed_keyboard,
)

router = Router()


class FinishedGoodsState(StatesGroup):
    mahsulot_tanlash = State()
    block_tanlash = State()
    miqdor = State()


async def finished_menu(user_id):
    return await build_keyboard(user_id, [
        ["📦 Tayyor mahsulot qoldig'i"],
        ["✏️ Dastlabki qoldiqni kiritish"],
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


@router.message(Tkey("🏬 Tayyor mahsulot"))
async def tayyor_mahsulot(message: Message):
    await say(message, "🏬 Tayyor mahsulot ombori:",
              reply_markup=await finished_menu(message.from_user.id))


@router.message(Tkey("📦 Tayyor mahsulot qoldig'i"))
async def tayyor_qoldiq(message: Message):
    try:
        goods = await db.get_all_finished_goods()
        if not goods:
            await say(message, "❌ Hali mahsulot/blok kiritilmagan!",
                      reply_markup=await finished_menu(message.from_user.id))
            return
        text = "📦 Tayyor mahsulot ombori:\n"
        jami = 0
        joriy_pid = None
        for g in goods:
            if g["product_id"] != joriy_pid:
                joriy_pid = g["product_id"]
                text += f"\n{g['emoji']} {g['product_nomi']}\n"
            text += f"   🧱 {g['nomi']}: {g['qoldiq']} ta\n"
            jami += g["qoldiq"]
        text += f"\n📊 Umumiy jami: {jami} ta"
        await say(message, text, reply_markup=await finished_menu(message.from_user.id))
    except Exception as e:
        await say_error(message, e, reply_markup=await finished_menu(message.from_user.id))


@router.message(Tkey("✏️ Dastlabki qoldiqni kiritish"))
async def dastlabki_qoldiq(message: Message, state: FSMContext, user: dict = None):
    user_id = message.from_user.id
    if user is None:
        user = await db.get_user(user_id)
    if not user or not await db.has_permission(
            user_id, user["rol"], "tayyor_mahsulot_tahrirlash"):
        await say(message, "❌ Sizda bu amalni bajarish huquqi yo'q!",
                  reply_markup=await finished_menu(user_id))
        return
    prods = await db.get_mahsulotlar(faqat_faol=True)
    if not prods:
        await say(message, "❌ Mahsulot yo'q.", reply_markup=await finished_menu(user_id))
        return
    await state.clear()
    if len(prods) == 1:
        await _block_sorov(message, state, prods[0])
        return
    kb, _ = await _mahsulot_keyboard(user_id)
    await state.set_state(FinishedGoodsState.mahsulot_tanlash)
    await say(message, "📦 Qaysi mahsulot?", reply_markup=kb)


async def _block_sorov(message, state, mahsulot):
    user_id = message.from_user.id
    bloklar = await db.get_finished_goods(mahsulot["id"])
    if not bloklar:
        await state.clear()
        await say(message, f"❌ '{mahsulot['nomi']}' uchun blok yo'q!",
                  reply_markup=await finished_menu(user_id))
        return
    await state.update_data(pid=mahsulot["id"], mahsulot_nomi=mahsulot["nomi"], bloklar=bloklar)
    await state.set_state(FinishedGoodsState.block_tanlash)
    text = "Qaysi blok uchun qoldiq kiritasiz?\n\nJoriy qoldiq:\n"
    for b in bloklar:
        text += f"   {b['nomi']}: {b['qoldiq']} ta\n"
    rows = [[b["nomi"]] for b in bloklar]
    await say(message, text, reply_markup=await _kb(user_id, rows, [["🏠 Asosiy menyu"]]))


@router.message(FinishedGoodsState.mahsulot_tanlash)
async def fg_mahsulot(message: Message, state: FSMContext):
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


@router.message(FinishedGoodsState.block_tanlash)
async def fg_block(message: Message, state: FSMContext):
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
    await state.update_data(block_kod=tanlangan["kod"], block_nomi=tanlangan["nomi"])
    await state.set_state(FinishedGoodsState.miqdor)
    await say(message,
              f"🧱 {tanlangan['nomi']} uchun yangi qoldiqni kiriting:\n"
              f"Hozirgi qoldiq: {tanlangan['qoldiq']} ta\n\nMisol: 500")


@router.message(FinishedGoodsState.miqdor)
async def fg_miqdor(message: Message, state: FSMContext, user: dict = None):
    user_id = message.from_user.id
    try:
        miqdor = int(message.text.strip())
        if miqdor < 0:
            raise ValueError
    except (ValueError, AttributeError):
        await say(message, "❌ Faqat musbat son kiriting! Misol: 500")
        return
    data = await state.get_data()
    pid = data["pid"]
    block_kod = data["block_kod"]
    block_nomi = data.get("block_nomi", block_kod)

    bloklar = await db.get_finished_goods(pid)
    eski = next((b["qoldiq"] for b in bloklar if b["kod"] == block_kod), 0)
    await db.set_finished_goods(pid, block_kod, miqdor)

    if user is None:
        user = await db.get_user(user_id)
    await db.add_audit_log(
        user_id, user["ism"] if user else str(user_id),
        user["rol"] if user else "-", "Tayyor mahsulot qoldig'i yangilandi",
        f"{data.get('mahsulot_nomi','')} | {block_nomi}: {eski} → {miqdor} ta")
    await state.clear()
    await say(message,
              f"✅ {block_nomi} qoldig'i yangilandi!\n\n"
              f"   Eski: {eski} ta\n   Yangi: {miqdor} ta",
              reply_markup=await finished_menu(user_id))
