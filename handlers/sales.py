"""Sotuv — inline edit-in-place oqim (v2.2)."""
from aiogram import Router
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import asyncio
import database as db
from translation import Tkey, say, say_error, t
from .nav import cb_guard, menu_kb, show, send
from .callbacks import CB

router = Router()

P_KIRITISH = "sotuv_kiritish"
P_KORISH = "sotuv_korish"


class SalesState(StatesGroup):
    miqdor = State()


def _label(p):
    return f"{p['emoji']} {p['nomi']}"


def _block_label(b):
    return f"{b['nomi']} ({b['qoldiq']} ta)"


async def _root_kb(user_id):
    return await menu_kb(user_id, [
        [("➕ Sotuv kiritish", CB.SL_INPUT)],
        [("📋 Bugungi sotuv", CB.SL_TODAY)],
        [("🗑️ Oxirgi sotuvni o'chirish", CB.SL_DELLAST)],
    ])


# ── Kirish (Reply main menu) ──
@router.message(Tkey("💰 Sotuv"))
async def sotuv(message: Message, state: FSMContext):
    await state.clear()
    await send(message, "💰 Sotuv bo'limi:", await _root_kb(message.from_user.id))


@router.callback_query(lambda c: c.data == CB.SL_ROOT)
async def sl_root(callback: CallbackQuery, state: FSMContext):
    if not await cb_guard(callback):
        return
    await state.clear()
    await show(callback, "💰 Sotuv bo'limi:", await _root_kb(callback.from_user.id))
    await callback.answer()


# ── Sotuv kiritish: mahsulot tanlash ──
@router.callback_query(lambda c: c.data == CB.SL_INPUT)
async def sl_input(callback: CallbackQuery, state: FSMContext):
    if not await cb_guard(callback, P_KIRITISH):
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
    dyn = [[(_label(p), f"{CB.SL_PROD}:{p['id']}")] for p in prods]
    kb = await menu_kb(callback.from_user.id, [[("⬅️ Ortga", CB.SL_ROOT)]], dyn)
    await show(callback, "📦 Qaysi mahsulot sotildi?", kb)
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith(f"{CB.SL_PROD}:"))
async def sl_prod(callback: CallbackQuery, state: FSMContext):
    if not await cb_guard(callback, P_KIRITISH):
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
        await show(callback, f"❌ '{mahsulot['nomi']}' uchun blok turi yo'q!",
                   await _root_kb(callback.from_user.id))
        return
    await state.set_state(None)
    await state.update_data(pid=pid, mahsulot_nomi=mahsulot["nomi"], bloklar=bloklar)
    dyn = [[(_block_label(b), f"{CB.SL_BLK}:{i}")] for i, b in enumerate(bloklar)]
    kb = await menu_kb(callback.from_user.id, [[("⬅️ Ortga", CB.SL_INPUT)]], dyn)
    await show(callback, f"📦 {mahsulot['nomi']} — qaysi blok sotildi?", kb)


@router.callback_query(lambda c: c.data and c.data.startswith(f"{CB.SL_BLK}:"))
async def sl_blk(callback: CallbackQuery, state: FSMContext):
    if not await cb_guard(callback, P_KIRITISH):
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
    await state.set_state(SalesState.miqdor)
    kb = await menu_kb(callback.from_user.id, [[("⬅️ Ortga", f"{CB.SL_PROD}:{data['pid']}")]])
    await show(callback,
               f"📦 {b['nomi']} dan nechta sotildi?\nMavjud: {b['qoldiq']} ta\n\nMisol: 100", kb)
    await callback.answer()


@router.message(SalesState.miqdor)
async def sl_miqdor(message: Message, state: FSMContext):
    uid = message.from_user.id
    try:
        miqdor = int(message.text.strip())
        if miqdor <= 0:
            raise ValueError
    except (ValueError, AttributeError):
        await say(message, "❌ Faqat musbat son kiriting! Misol: 100")
        return
    data = await state.get_data()
    if "pid" not in data:
        await state.clear()
        return
    pid = data["pid"]
    block_kod = data["block_kod"]
    block_nomi = data.get("block_nomi", block_kod)

    ok, xabar = await db.add_sales_log(pid, block_kod, miqdor, uid)
    await state.clear()
    if not ok:
        await send(message, xabar, await _root_kb(uid))
        return
    user = await db.get_user(uid)
    await db.add_audit_log(
        uid, user["ism"] if user else str(uid), user["rol"] if user else "-",
        "Sotuv kiritildi", f"{data.get('mahsulot_nomi','')} | {block_nomi}: {miqdor} ta")
    bloklar = await db.get_finished_goods(pid)
    yangi = next((b["qoldiq"] for b in bloklar if b["kod"] == block_kod), 0)
    text = (f"✅ Sotuv kiritildi!\n\n🧱 {block_nomi}: {miqdor} ta sotildi\n"
            f"📦 Qoldi: {yangi} ta")
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


# ── Bugungi sotuv ──
@router.callback_query(lambda c: c.data == CB.SL_TODAY)
async def sl_today(callback: CallbackQuery):
    if not await cb_guard(callback, P_KORISH, P_KIRITISH):
        return
    prods = await db.get_mahsulotlar(faqat_faol=True)
    text = "📋 Bugungi sotuv:\n"
    bor = False
    if prods:
        infos = await asyncio.gather(*(db.get_sales_today(p["id"]) for p in prods))
        for p, info in zip(prods, infos):
            if info["jami"] <= 0:
                continue
            bor = True
            text += f"\n💰 {p['emoji']} {p['nomi']}\n"
            for b in info["bloklar"]:
                text += f"   {b['nomi'] or b['kod']}: {b['qty']} ta\n"
            text += f"   Jami: {info['jami']} ta\n"
    if not bor:
        text = "📋 Bugun hali sotuv kiritilmagan."
    kb = await menu_kb(callback.from_user.id, [[("⬅️ Ortga", CB.SL_ROOT)]])
    await show(callback, text, kb)
    await callback.answer()


# ── Oxirgi sotuvni o'chirish ──
@router.callback_query(lambda c: c.data == CB.SL_DELLAST)
async def sl_dellast(callback: CallbackQuery, state: FSMContext):
    if not await cb_guard(callback, P_KIRITISH):
        return
    await state.clear()
    prods = await db.get_mahsulotlar(faqat_faol=True)
    if not prods:
        await show(callback, "❌ Mahsulot yo'q.", await _root_kb(callback.from_user.id))
        await callback.answer()
        return
    if len(prods) == 1:
        await _del_confirm(callback, prods[0]["id"], prods[0]["nomi"])
        await callback.answer()
        return
    dyn = [[(_label(p), f"{CB.SL_DELPROD}:{p['id']}")] for p in prods]
    kb = await menu_kb(callback.from_user.id, [[("⬅️ Ortga", CB.SL_ROOT)]], dyn)
    await show(callback, "📦 Qaysi mahsulotning oxirgi sotuvini o'chirasiz?", kb)
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith(f"{CB.SL_DELPROD}:"))
async def sl_delprod(callback: CallbackQuery):
    if not await cb_guard(callback, P_KIRITISH):
        return
    pid = int(callback.data.split(":", 1)[1])
    p = await db.get_mahsulot(pid)
    await _del_confirm(callback, pid, p["nomi"] if p else "?")
    await callback.answer()


async def _del_confirm(callback, pid, nomi):
    kb = await menu_kb(callback.from_user.id, [
        [("✅ Ha, o'chirish", f"{CB.SL_DELOK}:{pid}")],
        [("⬅️ Yo'q", CB.SL_ROOT)],
    ])
    await show(callback, f"🗑️ '{nomi}' oxirgi sotuvi o'chirilsinmi?\n"
                         f"(Mahsulot omborga qaytariladi)", kb)


@router.callback_query(lambda c: c.data and c.data.startswith(f"{CB.SL_DELOK}:"))
async def sl_delok(callback: CallbackQuery):
    user = await cb_guard(callback, P_KIRITISH)
    if not user:
        return
    pid = int(callback.data.split(":", 1)[1])
    try:
        natija = await db.delete_last_sale(pid)
        if natija:
            await db.add_audit_log(
                callback.from_user.id, user["ism"], user["rol"], "Sotuv o'chirildi",
                "Oxirgi sotuv yozuvi o'chirildi va omborga qaytarildi")
            await show(callback, "✅ Oxirgi sotuv o'chirildi!\n📦 Mahsulot omborga qaytarildi.",
                       await _root_kb(callback.from_user.id))
        else:
            await show(callback, "❌ O'chiriladigan yozuv yo'q!",
                       await _root_kb(callback.from_user.id))
        await callback.answer()
    except Exception as e:
        await say_error(callback.message, e)
        await callback.answer("❌", show_alert=True)
