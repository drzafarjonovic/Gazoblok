"""Inventarizatsiya — inline edit-in-place oqim (v2.2)."""
from aiogram import Router
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import timezone, timedelta
import database as db
from translation import Tkey, say, say_error
from .nav import cb_guard, menu_kb, show, send
from .callbacks import CB

router = Router()

TOSHKENT_TZ = timezone(timedelta(hours=5))
P_INV = "inventarizatsiya"


class InventarizatsiyaState(StatesGroup):
    real_hisob = State()
    izoh = State()


def _label(p):
    return f"{p['emoji']} {p['nomi']}"


async def _root_kb(user_id):
    return await menu_kb(user_id, [
        [("📊 Inventarizatsiya kiritish", CB.IV_INPUT)],
        [("📋 Inventarizatsiya tarixi", CB.IV_HIST)],
    ])


@router.message(Tkey("📋 Inventarizatsiya"))
async def inventarizatsiya(message: Message, state: FSMContext):
    await state.clear()
    await send(message, "📋 Inventarizatsiya:", await _root_kb(message.from_user.id))


@router.callback_query(lambda c: c.data == CB.IV_ROOT)
async def iv_root(callback: CallbackQuery, state: FSMContext):
    if not await cb_guard(callback):
        return
    await state.clear()
    await show(callback, "📋 Inventarizatsiya:", await _root_kb(callback.from_user.id))
    await callback.answer()


# ── Kiritish ──
@router.callback_query(lambda c: c.data == CB.IV_INPUT)
async def iv_input(callback: CallbackQuery, state: FSMContext):
    if not await cb_guard(callback, P_INV):
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
    dyn = [[(_label(p), f"{CB.IV_PROD}:{p['id']}")] for p in prods]
    kb = await menu_kb(callback.from_user.id, [[("⬅️ Ortga", CB.IV_ROOT)]], dyn)
    await show(callback, "📦 Qaysi mahsulot?", kb)
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith(f"{CB.IV_PROD}:"))
async def iv_prod(callback: CallbackQuery, state: FSMContext):
    if not await cb_guard(callback, P_INV):
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
    text = "📦 Joriy bot hisob:\n\n"
    for b in bloklar:
        text += f"   {b['nomi']}: {b['qoldiq']} ta\n"
    text += "\nQaysi blok uchun inventarizatsiya?"
    dyn = [[(b["nomi"], f"{CB.IV_BLK}:{i}")] for i, b in enumerate(bloklar)]
    kb = await menu_kb(callback.from_user.id, [[("⬅️ Ortga", CB.IV_INPUT)]], dyn)
    await show(callback, text, kb)


@router.callback_query(lambda c: c.data and c.data.startswith(f"{CB.IV_BLK}:"))
async def iv_blk(callback: CallbackQuery, state: FSMContext):
    if not await cb_guard(callback, P_INV):
        return
    data = await state.get_data()
    bloklar = data.get("bloklar", [])
    idx = int(callback.data.split(":", 1)[1])
    if idx < 0 or idx >= len(bloklar):
        await callback.answer("❌", show_alert=True)
        return
    b = bloklar[idx]
    await state.update_data(block_kod=b["kod"], block_nomi=b["nomi"], bot_hisob=b["qoldiq"])
    await state.set_state(InventarizatsiyaState.real_hisob)
    await show(callback,
               f"🧱 {b['nomi']}\nBot hisob: {b['qoldiq']} ta\n\nReal (haqiqiy) soni nechta?",
               None)
    await callback.answer()


@router.message(InventarizatsiyaState.real_hisob)
async def iv_real(message: Message, state: FSMContext):
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
async def iv_izoh(message: Message, state: FSMContext, user: dict = None):
    uid = message.from_user.id
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
            pid, db.bugungi_sana(), block_kod, bot_hisob, real_hisob, izoh, uid)

        if user is None:
            user = await db.get_user(uid)
        await db.add_audit_log(
            uid, user["ism"] if user else str(uid), user["rol"] if user else "-",
            "Inventarizatsiya kiritildi",
            f"{data.get('mahsulot_nomi','')} | {block_nomi}: "
            f"bot={bot_hisob}, real={real_hisob}, farq={farq}")
        await state.clear()
        farq_text = f"+{farq}" if farq > 0 else str(farq)
        await send(message,
                   f"✅ Inventarizatsiya saqlandi!\n\n"
                   f"🧱 {block_nomi}\n"
                   f"   Bot hisob: {bot_hisob} ta\n"
                   f"   Real hisob: {real_hisob} ta\n"
                   f"   Farq: {farq_text} ta\n"
                   f"   Bot yangilandi: {real_hisob} ta",
                   await _root_kb(uid))
    except Exception as e:
        await state.clear()
        await say_error(message, e)


# ── Tarix ──
@router.callback_query(lambda c: c.data == CB.IV_HIST)
async def iv_hist(callback: CallbackQuery):
    if not await cb_guard(callback, P_INV):
        return
    logs = await db.get_inventarizatsiya_tarixi(20)
    if not logs:
        await show(callback, "📋 Inventarizatsiya tarixi bo'sh.",
                   await _root_kb(callback.from_user.id))
        await callback.answer()
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
        text += (f"📅 {vaqt_str} | {prod} | {log['block_type']}\n"
                 f"   Bot: {log['bot_hisob']} | Real: {log['real_hisob']} | Farq: {farq_text}\n"
                 f"   {log['user_ism'] or 'Nomalum'}\n")
        if log["izoh"]:
            text += f"   📝 {log['izoh']}\n"
        text += "\n"
    if len(text) > 3800:
        text = text[:3800] + "\n..."
    kb = await menu_kb(callback.from_user.id, [[("⬅️ Ortga", CB.IV_ROOT)]])
    await show(callback, text, kb)
    await callback.answer()
