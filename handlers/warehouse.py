from aiogram import Router
from aiogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import database as db
from translation import Tkey, say, say_error, build_keyboard, t, register_ui, log_exc

router = Router()

# Birlik tugmalari (o'lcham bo'yicha)
OGIRLIK_BIRLIK = ["kg", "tonna", "meshok", "g"]
HAJM_BIRLIK = ["litr", "ml", "m3"]

register_ui("📥 Xom ashyo kirim", "🏪 Joriy qoldiqlar", "❌ Bekor qilish")


class WarehouseState(StatesGroup):
    miqdor = State()


async def warehouse_menu(user_id):
    return await build_keyboard(user_id, [
        ["📥 Xom ashyo kirim"],
        ["🏪 Joriy qoldiqlar"],
        ["🏠 Asosiy menyu"],
    ])


async def _ombor_kiritish_ok(user_id):
    user = await db.get_user(user_id)
    if not user or not user["faol"]:
        return False
    return (user["rol"] == "superadmin"
            or await db.has_permission(user_id, user["rol"], "ombor_kiritish"))


def _bekor_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="wh_cancel")]
    ])


async def _material_kb(user_id):
    """Materiallarni inline tugmalar qilib chiqaradi (ID yozish yo'q)."""
    materials = await db.get_materials()
    kb = []
    for m in materials:
        qoldiq_asl = db.asosiydan_birlikga(m[2], m[4])
        kb.append([InlineKeyboardButton(
            text=f"{m[1]} — {qoldiq_asl:.0f} {m[4]}",
            callback_data=f"wh_mat:{m[0]}")])
    kb.append([InlineKeyboardButton(text="❌ Bekor qilish", callback_data="wh_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=kb), materials


def _birlik_kb(asl_birlik):
    """Material o'lchamiga mos birlik tugmalari."""
    baza = db.birlik_bazasi(asl_birlik)
    birliklar = OGIRLIK_BIRLIK if baza == "kg" else HAJM_BIRLIK
    kb, row = [], []
    for b in birliklar:
        row.append(InlineKeyboardButton(text=b, callback_data=f"wh_unit:{b}"))
        if len(row) == 2:
            kb.append(row)
            row = []
    if row:
        kb.append(row)
    kb.append([InlineKeyboardButton(text="❌ Bekor qilish", callback_data="wh_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


@router.message(Tkey("🏪 Ombor"))
async def ombor(message: Message):
    await say(message, "🏪 Ombor bo'limi:",
              reply_markup=await warehouse_menu(message.from_user.id))


@router.message(Tkey("🏪 Joriy qoldiqlar"))
async def joriy_qoldiqlar(message: Message):
    try:
        materials = await db.get_materials()
        if not materials:
            await say(message, "❌ Hali material kiritilmagan!",
                      reply_markup=await warehouse_menu(message.from_user.id))
            return
        all_settings = await db.get_settings()
        min_map = {s[3]: s[1] for s in all_settings}
        text = "🏪 Joriy qoldiqlar:\n\n"
        for m in materials:
            material_id, nomi, qoldiq_asosiy, _, asl_birlik = m[0], m[1], m[2], m[3], m[4]
            qoldiq_asl = db.asosiydan_birlikga(qoldiq_asosiy, asl_birlik)
            min_ch = min_map.get(material_id)
            status = "⚠️" if (min_ch and qoldiq_asosiy <= min_ch) else "✅"
            text += f"{status} {nomi}: {qoldiq_asl:.2f} {asl_birlik}\n"
            if min_ch and min_ch > 0:
                min_asl = db.asosiydan_birlikga(min_ch, asl_birlik)
                text += f"   Min chegara: {min_asl:.2f} {asl_birlik}\n"
        await say(message, text, reply_markup=await warehouse_menu(message.from_user.id))
    except Exception as e:
        await say_error(message, e, reply_markup=await warehouse_menu(message.from_user.id))


@router.message(Tkey("📥 Xom ashyo kirim"))
async def xom_ashyo_kirim(message: Message, state: FSMContext):
    user_id = message.from_user.id
    materials = await db.get_materials()
    if not materials:
        await say(message,
                  "❌ Avval material qo'shing!\n⚙️ Sozlamalar → ➕ Material qo'shish",
                  reply_markup=await warehouse_menu(user_id))
        return
    await state.clear()
    kb, _ = await _material_kb(user_id)
    await say(message, "📥 Qaysi material keldi?\nTugmadan tanlang:", reply_markup=kb)


@router.callback_query(lambda c: c.data == "wh_cancel")
async def wh_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await callback.message.edit_text(await t("❌ Bekor qilindi.", callback.from_user.id))
    except Exception:
        pass
    await callback.message.answer(
        await t("🏪 Ombor bo'limi:", callback.from_user.id),
        reply_markup=await warehouse_menu(callback.from_user.id))
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("wh_mat:"))
async def wh_mat(callback: CallbackQuery, state: FSMContext):
    if not await _ombor_kiritish_ok(callback.from_user.id):
        await callback.answer("❌ Ruxsat yo'q!", show_alert=True)
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


@router.callback_query(lambda c: c.data and c.data.startswith("wh_unit:"))
async def wh_unit(callback: CallbackQuery, state: FSMContext):
    if not await _ombor_kiritish_ok(callback.from_user.id):
        await callback.answer("❌ Ruxsat yo'q!", show_alert=True)
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
        # Hozirgi qoldiqni yangilab olamiz va atomik qo'shamiz
        kirim_asosiy, _ = db.birlikni_asosiyga(miqdor, birlik)
        materials = await db.get_materials()
        material = next((m for m in materials if m[0] == data["material_id"]), None)
        joriy = material[2] if material else 0
        yangi = joriy + kirim_asosiy
        await db.update_material_qoldiq(data["material_id"], yangi)

        user = await db.get_user(callback.from_user.id)
        await db.add_audit_log(
            callback.from_user.id, user["ism"] if user else "-",
            user["rol"] if user else "-", "Xom ashyo kirim",
            f"{data['material_nomi']}: +{miqdor} {birlik}")

        await state.clear()
        yangi_asl = db.asosiydan_birlikga(yangi, data["asl_birlik"])
        matn = await t(
            f"✅ Kirim kiritildi!\n\n📦 {data['material_nomi']}\n"
            f"   Kirim: +{miqdor} {birlik}\n"
            f"   Yangi qoldiq: {yangi_asl:.2f} {data['asl_birlik']}",
            callback.from_user.id)
        try:
            await callback.message.edit_text(matn)
        except Exception:
            pass
        await callback.message.answer(
            await t("🏪 Ombor bo'limi:", callback.from_user.id),
            reply_markup=await warehouse_menu(callback.from_user.id))
        await callback.answer("✅")
    except Exception as e:
        await state.clear()
        log_exc("wh_unit", e)
        await callback.answer("❌ Xatolik", show_alert=True)
        await callback.message.answer(
            await t("❌ Xatolik yuz berdi.", callback.from_user.id),
            reply_markup=await warehouse_menu(callback.from_user.id))
