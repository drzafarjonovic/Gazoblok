"""Ombor (xom ashyo) — inline oqim (v2.2)."""
from aiogram import Router
from aiogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import database as db
from translation import Tkey, say, t, log_exc
from .nav import cb_guard, menu_kb, show, send
from .callbacks import CB

router = Router()

OGIRLIK_BIRLIK = ["kg", "tonna", "meshok", "g"]
HAJM_BIRLIK = ["litr", "ml", "m3"]
P_KIRITISH = "ombor_kiritish"
P_KORISH = "ombor_korish"


class WarehouseState(StatesGroup):
    miqdor = State()


async def _root_kb(user_id):
    return await menu_kb(user_id, [
        [("📥 Xom ashyo kirim", CB.WH_INPUT)],
        [("🏪 Joriy qoldiqlar", CB.WH_STOCK)],
    ])


async def _material_kb(user_id):
    """Materiallarni inline tugmalar qilib chiqaradi (ID yozish yo'q)."""
    materials = await db.get_materials()
    dyn = []
    for m in materials:
        qoldiq_asl = db.asosiydan_birlikga(m[2], m[4])
        dyn.append([(f"{m[1]} — {qoldiq_asl:.0f} {m[4]}", f"{CB.WH_MAT}:{m[0]}")])
    kb = await menu_kb(user_id, [[("⬅️ Ortga", CB.WH_ROOT)]], dyn)
    return kb, materials


def _bekor_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data=CB.WH_CANCEL)]
    ])


def _birlik_kb(asl_birlik):
    baza = db.birlik_bazasi(asl_birlik)
    birliklar = OGIRLIK_BIRLIK if baza == "kg" else HAJM_BIRLIK
    kb, row = [], []
    for b in birliklar:
        row.append(InlineKeyboardButton(text=b, callback_data=f"{CB.WH_UNIT}:{b}"))
        if len(row) == 2:
            kb.append(row)
            row = []
    if row:
        kb.append(row)
    kb.append([InlineKeyboardButton(text="❌ Bekor qilish", callback_data=CB.WH_CANCEL)])
    return InlineKeyboardMarkup(inline_keyboard=kb)


# ── Kirish (Reply main menu) ──
@router.message(Tkey("🏪 Ombor"))
async def ombor(message: Message, state: FSMContext):
    await state.clear()
    await send(message, "🏪 Ombor bo'limi:", await _root_kb(message.from_user.id))


@router.callback_query(lambda c: c.data == CB.WH_ROOT)
async def wh_root(callback: CallbackQuery, state: FSMContext):
    if not await cb_guard(callback):
        return
    await state.clear()
    await show(callback, "🏪 Ombor bo'limi:", await _root_kb(callback.from_user.id))
    await callback.answer()


# ── Joriy qoldiqlar ──
@router.callback_query(lambda c: c.data == CB.WH_STOCK)
async def wh_stock(callback: CallbackQuery):
    if not await cb_guard(callback, P_KORISH, P_KIRITISH):
        return
    materials = await db.get_materials()
    if not materials:
        await show(callback, "❌ Hali material kiritilmagan!",
                   await _root_kb(callback.from_user.id))
        await callback.answer()
        return
    all_settings = await db.get_settings()
    min_map = {s[3]: s[1] for s in all_settings}
    text = "🏪 Joriy qoldiqlar:\n\n"
    ogohlar = []
    for m in materials:
        material_id, nomi, qoldiq_asosiy, _, asl_birlik = m[0], m[1], m[2], m[3], m[4]
        qoldiq_asl = db.asosiydan_birlikga(qoldiq_asosiy, asl_birlik)
        min_ch = min_map.get(material_id)
        past = bool(min_ch and qoldiq_asosiy <= min_ch)
        status = "⚠️" if past else "✅"
        text += f"{status} {nomi}: {qoldiq_asl:.2f} {asl_birlik}\n"
        if min_ch and min_ch > 0:
            min_asl = db.asosiydan_birlikga(min_ch, asl_birlik)
            text += f"   Min chegara: {min_asl:.2f} {asl_birlik}\n"
        if past:
            ogohlar.append(nomi)
    if ogohlar:
        text += f"\n❗ Past qoldiq: {', '.join(ogohlar)}"
    kb = await menu_kb(callback.from_user.id, [[("⬅️ Ortga", CB.WH_ROOT)]])
    await show(callback, text, kb)
    await callback.answer()


# ── Xom ashyo kirim ──
@router.callback_query(lambda c: c.data == CB.WH_INPUT)
async def wh_input(callback: CallbackQuery, state: FSMContext):
    if not await cb_guard(callback, P_KIRITISH):
        return
    await state.clear()
    materials = await db.get_materials()
    if not materials:
        await show(callback,
                   "❌ Avval material qo'shing!\n⚙️ Sozlamalar → 📦 Materiallar",
                   await _root_kb(callback.from_user.id))
        await callback.answer()
        return
    kb, _ = await _material_kb(callback.from_user.id)
    await show(callback, "📥 Qaysi material keldi?\nTugmadan tanlang:", kb)
    await callback.answer()


@router.callback_query(lambda c: c.data == CB.WH_CANCEL)
async def wh_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await show(callback, "🏪 Ombor bo'limi:", await _root_kb(callback.from_user.id))
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith(f"{CB.WH_MAT}:"))
async def wh_mat(callback: CallbackQuery, state: FSMContext):
    if not await cb_guard(callback, P_KIRITISH):
        return
    material_id = int(callback.data.split(":", 1)[1])
    materials = await db.get_materials()
    material = next((m for m in materials if m[0] == material_id), None)
    if not material:
        await callback.answer("❌ Material topilmadi", show_alert=True)
        return
    await state.update_data(
        material_id=material_id, material_nomi=material[1], asl_birlik=material[4])
    await state.set_state(WarehouseState.miqdor)
    matn = await t(f"📥 {material[1]} dan qancha keldi?\nSonni kiriting (masalan: 10)",
                   callback.from_user.id)
    try:
        await callback.message.edit_text(matn, reply_markup=_bekor_kb())
    except Exception:
        await callback.message.answer(matn, reply_markup=_bekor_kb())
    await callback.answer()


@router.message(WarehouseState.miqdor)
async def kirim_miqdor(message: Message, state: FSMContext):
    try:
        miqdor = float(message.text.replace(",", "."))
        if miqdor <= 0:
            raise ValueError
    except (ValueError, AttributeError):
        await say(message, "❌ Faqat musbat son kiriting! Misol: 10",
                  reply_markup=_bekor_kb())
        return
    data = await state.get_data()
    await state.update_data(miqdor=miqdor)
    matn = await t(
        f"📏 {data['material_nomi']}: {miqdor}\nBirligini tanlang:", message.from_user.id)
    await message.answer(matn, reply_markup=_birlik_kb(data["asl_birlik"]))


@router.callback_query(lambda c: c.data and c.data.startswith(f"{CB.WH_UNIT}:"))
async def wh_unit(callback: CallbackQuery, state: FSMContext):
    user = await cb_guard(callback, P_KIRITISH)
    if not user:
        return
    birlik = callback.data.split(":", 1)[1]
    data = await state.get_data()
    if "miqdor" not in data or "material_id" not in data:
        await callback.answer()
        return
    try:
        if db.birlik_bazasi(birlik) != db.birlik_bazasi(data["asl_birlik"]):
            await callback.answer("❌ Birlik mos emas", show_alert=True)
            return
        miqdor = data["miqdor"]
        kirim_asosiy, _ = db.birlikni_asosiyga(miqdor, birlik)
        materials = await db.get_materials()
        material = next((m for m in materials if m[0] == data["material_id"]), None)
        joriy = material[2] if material else 0
        yangi = joriy + kirim_asosiy
        await db.update_material_qoldiq(data["material_id"], yangi)

        await db.add_audit_log(
            callback.from_user.id, user["ism"], user["rol"], "Xom ashyo kirim",
            f"{data['material_nomi']}: +{miqdor} {birlik}")

        await state.clear()
        yangi_asl = db.asosiydan_birlikga(yangi, data["asl_birlik"])
        matn = await t(
            f"✅ Kirim kiritildi!\n\n📦 {data['material_nomi']}\n"
            f"   Kirim: +{miqdor} {birlik}\n"
            f"   Yangi qoldiq: {yangi_asl:.2f} {data['asl_birlik']}",
            callback.from_user.id)
        kb = await _root_kb(callback.from_user.id)
        try:
            await callback.message.edit_text(matn, reply_markup=kb)
        except Exception:
            await callback.message.answer(matn, reply_markup=kb)
        await callback.answer("✅")
    except Exception as e:
        await state.clear()
        log_exc("wh_unit", e)
        await callback.answer("❌ Xatolik", show_alert=True)
