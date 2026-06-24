from aiogram import Router
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import asyncio
import database as db
from translation import (
    Tkey, eq, say, say_error, build_keyboard, build_mixed_keyboard,
)

router = Router()


class SalesState(StatesGroup):
    mahsulot_tanlash = State()
    block_tanlash = State()
    miqdor = State()
    ochirish_mahsulot = State()


async def sales_menu(user_id):
    return await build_keyboard(user_id, [
        ["💰 Sotuv kiritish"],
        ["📋 Bugungi sotuv"],
        ["🗑️ Oxirgi sotuvni o'chirish"],
        ["🏠 Asosiy menyu"],
    ])


async def _kb(user_id, dinamik_rows, static_rows):
    return await build_mixed_keyboard(user_id, dinamik_rows, static_rows)


def _label(p):
    return f"{p['emoji']} {p['nomi']}"


def _block_label(b):
    """Sotuv blok tugmasi yorlig'i — qoldiq bilan (UX: tanlashdan oldin ko'rinadi)."""
    return f"{b['nomi']} ({b['qoldiq']} ta)"


async def _mahsulot_keyboard(user_id):
    prods = await db.get_mahsulotlar(faqat_faol=True)
    rows = [[_label(p)] for p in prods]
    return await _kb(user_id, rows, [["🏠 Asosiy menyu"]]), prods


async def _block_keyboard(user_id, bloklar):
    rows = [[_block_label(b)] for b in bloklar]
    return await _kb(user_id, rows, [["🏠 Asosiy menyu"]])


@router.message(Tkey("💰 Sotuv"))
async def sotuv(message: Message):
    await say(message, "💰 Sotuv bo'limi:", reply_markup=await sales_menu(message.from_user.id))


@router.message(Tkey("💰 Sotuv kiritish"))
async def sotuv_kiritish(message: Message, state: FSMContext):
    user_id = message.from_user.id
    prods = await db.get_mahsulotlar(faqat_faol=True)
    if not prods:
        await say(message, "❌ Mahsulot yo'q.", reply_markup=await sales_menu(user_id))
        return
    await state.clear()
    if len(prods) == 1:
        await _block_sorov(message, state, prods[0])
        return
    kb, _ = await _mahsulot_keyboard(user_id)
    await state.set_state(SalesState.mahsulot_tanlash)
    await say(message, "📦 Qaysi mahsulot sotildi?", reply_markup=kb)


async def _block_sorov(message, state, mahsulot):
    user_id = message.from_user.id
    pid = mahsulot["id"]
    bloklar = await db.get_finished_goods(pid)
    if not bloklar:
        await state.clear()
        await say(message, f"❌ '{mahsulot['nomi']}' uchun blok turi yo'q!",
                  reply_markup=await sales_menu(user_id))
        return
    await state.update_data(pid=pid, mahsulot_nomi=mahsulot["nomi"], bloklar=bloklar)
    await state.set_state(SalesState.block_tanlash)
    text = f"📦 {mahsulot['nomi']} — joriy tayyor mahsulot:\n"
    for b in bloklar:
        text += f"   {b['nomi']}: {b['qoldiq']} ta\n"
    text += "\nQaysi blok sotildi?"
    await say(message, text, reply_markup=await _block_keyboard(user_id, bloklar))


@router.message(SalesState.mahsulot_tanlash)
async def sotuv_mahsulot(message: Message, state: FSMContext):
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


@router.message(SalesState.block_tanlash)
async def sotuv_block(message: Message, state: FSMContext):
    if await eq(message, "🏠 Asosiy menyu"):
        await state.clear()
        return
    data = await state.get_data()
    bloklar = data.get("bloklar", [])
    text = (message.text or "").strip()
    tanlangan = next((b for b in bloklar if _block_label(b) == text), None)
    if not tanlangan:
        await say(message, "❌ Tugmalardan birini tanlang!")
        return
    await state.update_data(block_kod=tanlangan["kod"], block_nomi=tanlangan["nomi"])
    await state.set_state(SalesState.miqdor)
    await say(message,
              f"📦 {tanlangan['nomi']} dan nechta sotildi?\n"
              f"Mavjud: {tanlangan['qoldiq']} ta\n\nMisol: 100")


@router.message(SalesState.miqdor)
async def sotuv_miqdor(message: Message, state: FSMContext, user: dict = None):
    user_id = message.from_user.id
    try:
        miqdor = int(message.text.strip())
        if miqdor <= 0:
            raise ValueError
    except (ValueError, AttributeError):
        await say(message, "❌ Faqat musbat son kiriting! Misol: 100")
        return

    data = await state.get_data()
    pid = data["pid"]
    block_kod = data["block_kod"]
    block_nomi = data.get("block_nomi", block_kod)

    muvaffaqiyat, xabar = await db.add_sales_log(pid, block_kod, miqdor, user_id)
    await state.clear()
    if not muvaffaqiyat:
        await say(message, xabar, reply_markup=await sales_menu(user_id))
        return

    if user is None:
        user = await db.get_user(user_id)
    await db.add_audit_log(
        user_id, user["ism"] if user else str(user_id),
        user["rol"] if user else "-", "Sotuv kiritildi",
        f"{data.get('mahsulot_nomi','')} | {block_nomi}: {miqdor} ta")

    bloklar = await db.get_finished_goods(pid)
    yangi_qoldiq = next((b["qoldiq"] for b in bloklar if b["kod"] == block_kod), 0)
    await say(message,
              f"✅ Sotuv kiritildi!\n\n"
              f"🧱 {block_nomi}: {miqdor} ta sotildi\n"
              f"📦 Qoldi: {yangi_qoldiq} ta",
              reply_markup=await sales_menu(user_id))


@router.message(Tkey("🗑️ Oxirgi sotuvni o'chirish"))
async def oxirgi_sotuv_ochirish(message: Message, state: FSMContext):
    user_id = message.from_user.id
    prods = await db.get_mahsulotlar(faqat_faol=True)
    if not prods:
        await say(message, "❌ Mahsulot yo'q.", reply_markup=await sales_menu(user_id))
        return
    await state.clear()
    if len(prods) == 1:
        await _sotuv_ochir(message, prods[0]["id"])
        return
    kb, _ = await _mahsulot_keyboard(user_id)
    await state.set_state(SalesState.ochirish_mahsulot)
    await say(message, "📦 Qaysi mahsulotning oxirgi sotuvini o'chirasiz?", reply_markup=kb)


@router.message(SalesState.ochirish_mahsulot)
async def oxirgi_sotuv_tanla(message: Message, state: FSMContext):
    if await eq(message, "🏠 Asosiy menyu"):
        await state.clear()
        return
    prods = await db.get_mahsulotlar(faqat_faol=True)
    text = (message.text or "").strip()
    tanlangan = next((p for p in prods if _label(p) == text), None)
    if not tanlangan:
        await say(message, "❌ Tugmalardan birini tanlang!")
        return
    await state.clear()
    await _sotuv_ochir(message, tanlangan["id"])


async def _sotuv_ochir(message, pid):
    user_id = message.from_user.id
    try:
        user = await db.get_user(user_id)
        natija = await db.delete_last_sale(pid)
        if natija:
            await db.add_audit_log(
                user_id, user["ism"] if user else str(user_id),
                user["rol"] if user else "-", "Sotuv o'chirildi",
                "Oxirgi sotuv yozuvi o'chirildi va omborga qaytarildi")
            await say(message, "✅ Oxirgi sotuv o'chirildi!\n📦 Mahsulot omborga qaytarildi.",
                      reply_markup=await sales_menu(user_id))
        else:
            await say(message, "❌ O'chiriladigan yozuv yo'q!",
                      reply_markup=await sales_menu(user_id))
    except Exception as e:
        await say_error(message, e, reply_markup=await sales_menu(user_id))


@router.message(Tkey("📋 Bugungi sotuv"))
async def bugungi_sotuv(message: Message):
    user_id = message.from_user.id
    prods = await db.get_mahsulotlar(faqat_faol=True)
    if not prods:
        await say(message, "❌ Mahsulot yo'q.", reply_markup=await sales_menu(user_id))
        return
    text = "📋 Bugungi sotuv:\n"
    bor = False
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
    await say(message, text, reply_markup=await sales_menu(user_id))
