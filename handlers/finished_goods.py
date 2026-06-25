"""Tayyor mahsulot — inline edit-in-place oqim (v2.2)."""
from aiogram import Router
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import database as db
from translation import Tkey, say, t
from .nav import cb_guard, menu_kb, show, send
from .callbacks import CB

router = Router()

P_KORISH = "tayyor_mahsulot_korish"
P_EDIT = "tayyor_mahsulot_tahrirlash"


class FinishedGoodsState(StatesGroup):
    miqdor = State()


def _label(p):
    return f"{p['emoji']} {p['nomi']}"


async def _root_kb(user_id):
    return await menu_kb(user_id, [
        [("📦 Tayyor mahsulot qoldig'i", CB.FG_QOLDIQ)],
        [("✏️ Dastlabki qoldiqni kiritish", CB.FG_EDIT)],
    ])


@router.message(Tkey("🏬 Tayyor mahsulot"))
async def tayyor_mahsulot(message: Message, state: FSMContext):
    await state.clear()
    await send(message, "🏬 Tayyor mahsulot ombori:", await _root_kb(message.from_user.id))


@router.callback_query(lambda c: c.data == CB.FG_ROOT)
async def fg_root(callback: CallbackQuery, state: FSMContext):
    if not await cb_guard(callback):
        return
    await state.clear()
    await show(callback, "🏬 Tayyor mahsulot ombori:", await _root_kb(callback.from_user.id))
    await callback.answer()


# ── Qoldiq ko'rish ──
@router.callback_query(lambda c: c.data == CB.FG_QOLDIQ)
async def fg_qoldiq(callback: CallbackQuery):
    if not await cb_guard(callback, P_KORISH, P_EDIT):
        return
    goods = await db.get_all_finished_goods()
    if not goods:
        await show(callback, "❌ Hali mahsulot/blok kiritilmagan!",
                   await _root_kb(callback.from_user.id))
        await callback.answer()
        return
    text = "📦 Tayyor mahsulot ombori:\n"
    jami = 0
    joriy = None
    for g in goods:
        if g["product_id"] != joriy:
            joriy = g["product_id"]
            text += f"\n{g['emoji']} {g['product_nomi']}\n"
        text += f"   🧱 {g['nomi']}: {g['qoldiq']} ta\n"
        jami += g["qoldiq"]
    text += f"\n📊 Umumiy jami: {jami} ta"
    kb = await menu_kb(callback.from_user.id, [[("⬅️ Ortga", CB.FG_ROOT)]])
    await show(callback, text, kb)
    await callback.answer()


# ── Dastlabki qoldiq ──
@router.callback_query(lambda c: c.data == CB.FG_EDIT)
async def fg_edit(callback: CallbackQuery, state: FSMContext):
    if not await cb_guard(callback, P_EDIT):
        return
    await state.clear()
    prods = await db.get_mahsulotlar(faqat_faol=True)
    if not prods:
        await show(callback, "❌ Mahsulot yo'q.", await _root_kb(callback.from_user.id))
        await callback.answer()
        return
    if len(prods) == 1:
        await _show_blocks(callback, state, prods[0])
        await callback.answer()
        return
    dyn = [[(_label(p), f"{CB.FG_PROD}:{p['id']}")] for p in prods]
    kb = await menu_kb(callback.from_user.id, [[("⬅️ Ortga", CB.FG_ROOT)]], dyn)
    await show(callback, "📦 Qaysi mahsulot?", kb)
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith(f"{CB.FG_PROD}:"))
async def fg_prod(callback: CallbackQuery, state: FSMContext):
    if not await cb_guard(callback, P_EDIT):
        return
    pid = int(callback.data.split(":", 1)[1])
    mahsulot = await db.get_mahsulot(pid)
    if not mahsulot:
        await callback.answer("❌ Topilmadi", show_alert=True)
        return
    await _show_blocks(callback, state, mahsulot)
    await callback.answer()


async def _show_blocks(callback, state, mahsulot):
    pid = mahsulot["id"]
    bloklar = await db.get_finished_goods(pid)
    if not bloklar:
        await show(callback, f"❌ '{mahsulot['nomi']}' uchun blok yo'q!",
                   await _root_kb(callback.from_user.id))
        return
    await state.set_state(None)
    await state.update_data(pid=pid, mahsulot_nomi=mahsulot["nomi"], bloklar=bloklar)
    text = "Qaysi blok uchun qoldiq kiritasiz?\n\nJoriy qoldiq:\n"
    for b in bloklar:
        text += f"   {b['nomi']}: {b['qoldiq']} ta\n"
    dyn = [[(b["nomi"], f"{CB.FG_BLK}:{i}")] for i, b in enumerate(bloklar)]
    kb = await menu_kb(callback.from_user.id, [[("⬅️ Ortga", CB.FG_EDIT)]], dyn)
    await show(callback, text, kb)


@router.callback_query(lambda c: c.data and c.data.startswith(f"{CB.FG_BLK}:"))
async def fg_blk(callback: CallbackQuery, state: FSMContext):
    if not await cb_guard(callback, P_EDIT):
        return
    data = await state.get_data()
    bloklar = data.get("bloklar", [])
    idx = int(callback.data.split(":", 1)[1])
    if idx < 0 or idx >= len(bloklar):
        await callback.answer("❌", show_alert=True)
        return
    b = bloklar[idx]
    await state.update_data(block_kod=b["kod"], block_nomi=b["nomi"],
                            nav_chat=callback.message.chat.id,
                            nav_msg=callback.message.message_id)
    await state.set_state(FinishedGoodsState.miqdor)
    kb = await menu_kb(callback.from_user.id, [[("⬅️ Ortga", f"{CB.FG_PROD}:{data['pid']}")]])
    await show(callback,
               f"🧱 {b['nomi']} uchun yangi qoldiqni kiriting:\n"
               f"Hozirgi qoldiq: {b['qoldiq']} ta\n\nMisol: 500", kb)
    await callback.answer()


@router.message(FinishedGoodsState.miqdor)
async def fg_miqdor(message: Message, state: FSMContext):
    uid = message.from_user.id
    try:
        miqdor = int(message.text.strip())
        if miqdor < 0:
            raise ValueError
    except (ValueError, AttributeError):
        await say(message, "❌ Faqat musbat son kiriting! Misol: 500")
        return
    data = await state.get_data()
    if "pid" not in data:
        await state.clear()
        return
    pid = data["pid"]
    block_kod = data["block_kod"]
    block_nomi = data.get("block_nomi", block_kod)

    bloklar = await db.get_finished_goods(pid)
    eski = next((b["qoldiq"] for b in bloklar if b["kod"] == block_kod), 0)
    await db.set_finished_goods(pid, block_kod, miqdor)
    user = await db.get_user(uid)
    await db.add_audit_log(
        uid, user["ism"] if user else str(uid), user["rol"] if user else "-",
        "Tayyor mahsulot qoldig'i yangilandi",
        f"{data.get('mahsulot_nomi','')} | {block_nomi}: {eski} → {miqdor} ta")
    await state.clear()
    text = (f"✅ {block_nomi} qoldig'i yangilandi!\n\n"
            f"   Eski: {eski} ta\n   Yangi: {miqdor} ta")
    kb = await _root_kb(uid)
    chat, msg = data.get("nav_chat"), data.get("nav_msg")
    edited = False
    if chat and msg:
        try:
            await message.bot.edit_message_text(
                await t(text, uid), chat_id=chat, message_id=msg, reply_markup=kb)
            edited = True
        except Exception:
            edited = False
    if not edited:
        await send(message, text, kb)
