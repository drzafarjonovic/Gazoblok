"""Sozlamalar → Materiallar: CRUD + minimum chegara."""
from aiogram import Router
from aiogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import database as db
from translation import Tkey, say, say_error, build_keyboard, t
from .settings_common import (
    sozlamalar_menu,
    faqat_superadmin as _faqat_superadmin,
    cb_ok as _cb_ok,
)
from .callbacks import CB

router = Router()


class MaterialState(StatesGroup):
    nomi = State()
    qoldiq = State()
    birlik = State()


class MaterialEditState(StatesGroup):
    material_id = State()
    nomi = State()
    qoldiq = State()
    birlik = State()


class MinChegaraState(StatesGroup):
    miqdor = State()


async def materiallar_submenu(user_id):
    return await build_keyboard(user_id, [
        ["➕ Material qo'shish"],
        ["📦 Materiallar ro'yxati"],
        ["✏️ Materialni tahrirlash"],
        ["🗑️ Materialni o'chirish"],
        ["⚠️ Minimum chegara"],
        ["⬅️ Sozlamalar"],
    ])


@router.message(Tkey("📦 Materiallar"))
async def materiallar_bolimi(message: Message, user: dict = None):
    if not await _faqat_superadmin(message, user):
        return
    await say(message, "📦 Materiallar bo'limi:",
              reply_markup=await materiallar_submenu(message.from_user.id))


# ── Material qo'shish ──
@router.message(Tkey("➕ Material qo'shish"))
async def material_qoshish(message: Message, state: FSMContext, user: dict = None):
    if not await _faqat_superadmin(message, user):
        return
    await state.clear()
    await state.set_state(MaterialState.nomi)
    await say(message, "Material nomini kiriting:\nMisol: Sement")


@router.message(MaterialState.nomi)
async def material_nomi(message: Message, state: FSMContext):
    await state.update_data(nomi=message.text.strip())
    await state.set_state(MaterialState.qoldiq)
    await say(message, "Hozir omborda qancha bor?\nMisol: 30")


@router.message(MaterialState.qoldiq)
async def material_qoldiq(message: Message, state: FSMContext):
    try:
        qoldiq = float(message.text.replace(",", "."))
        if qoldiq < 0:
            raise ValueError
        await state.update_data(qoldiq=qoldiq)
        await state.set_state(MaterialState.birlik)
        await say(
            message,
            "Birligini kiriting:\n"
            "Misol: tonna, kg, g, litr, ml, meshok"
        )
    except ValueError:
        await say(message, "❌ Faqat musbat son kiriting! Misol: 30")


@router.message(MaterialState.birlik)
async def material_birlik(message: Message, state: FSMContext, user: dict = None):
    try:
        birlik = message.text.strip()
        if not db.birlik_qollab_quvvatlanadimi(birlik):
            await say(
                message,
                "❌ Birlik tanilmadi!\n"
                "Og'irlik: tonna, kg, g, gramm, mg, meshok\n"
                "Hajm: litr, ml, m3, kubometr\n\n"
                "Qaytadan kiriting:"
            )
            return
        data = await state.get_data()
        await db.add_material(data["nomi"], data["qoldiq"], birlik)

        if user is None:
            user = await db.get_user(message.from_user.id)
        await db.add_audit_log(
            message.from_user.id,
            user["ism"] if user else str(message.from_user.id),
            user["rol"] if user else "-",
            "Material qo'shildi",
            f"{data['nomi']}: {data['qoldiq']} {birlik}"
        )
        await state.clear()
        await say(
            message,
            f"✅ {data['nomi']} qo'shildi!\n"
            f"Miqdor: {data['qoldiq']} {birlik}",
            reply_markup=await sozlamalar_menu(message.from_user.id)
        )
    except Exception as e:
        await state.clear()
        await say_error(
            message, e,
            reply_markup=await sozlamalar_menu(message.from_user.id)
        )


# ── Materiallar ro'yxati ──
@router.message(Tkey("📦 Materiallar ro'yxati"))
async def materiallar_royxati(message: Message, user: dict = None):
    if not await _faqat_superadmin(message, user):
        return
    try:
        materials = await db.get_materials()
        if not materials:
            await say(
                message,
                "❌ Hali material kiritilmagan!",
                reply_markup=await sozlamalar_menu(message.from_user.id)
            )
            return
        text = "📦 Materiallar:\n\n"
        for m in materials:
            qoldiq_asl = db.asosiydan_birlikga(m[2], m[4])
            text += f"🔹 {m[0]}. {m[1]} — {qoldiq_asl:.2f} {m[4]}\n"
        await say(message, text, reply_markup=await sozlamalar_menu(message.from_user.id))
    except Exception as e:
        await say_error(message, e)


# ── Materialni tahrirlash ──
async def _material_inline(prefix):
    """Materiallar ro'yxati inline tugmalar sifatida."""
    materials = await db.get_materials()
    kb = []
    for m in materials:
        qoldiq_asl = db.asosiydan_birlikga(m[2], m[4])
        kb.append([InlineKeyboardButton(
            text=f"{m[1]} — {qoldiq_asl:.0f} {m[4]}",
            callback_data=f"{prefix}:{m[0]}")])
    return InlineKeyboardMarkup(inline_keyboard=kb), materials


@router.message(Tkey("✏️ Materialni tahrirlash"))
async def material_tahrirlash(message: Message, state: FSMContext, user: dict = None):
    if not await _faqat_superadmin(message, user):
        return
    await state.clear()
    kb, materials = await _material_inline(CB.MAT_EDIT)
    if not materials:
        await say(message, "❌ Hali material kiritilmagan!",
                  reply_markup=await sozlamalar_menu(message.from_user.id))
        return
    await say(message, "✏️ Qaysi materialni tahrirlash?", reply_markup=kb)


@router.callback_query(lambda c: c.data and c.data.startswith(f"{CB.MAT_EDIT}:"))
async def matedit_cb(callback: CallbackQuery, state: FSMContext):
    if not await _cb_ok(callback):
        return
    material_id = int(callback.data.split(":", 1)[1])
    materials = await db.get_materials()
    material = next((m for m in materials if m[0] == material_id), None)
    if not material:
        await callback.answer("❌ Topilmadi", show_alert=True)
        return
    await state.update_data(material_id=material_id, eski_nomi=material[1])
    await state.set_state(MaterialEditState.nomi)
    try:
        await callback.message.edit_text(await t(
            f"✏️ {material[1]}\nYangi nomni kiriting:", callback.from_user.id))
    except Exception:
        pass
    await callback.answer()


@router.message(MaterialEditState.nomi)
async def material_tahrirlash_nomi(message: Message, state: FSMContext):
    await state.update_data(nomi=message.text.strip())
    await state.set_state(MaterialEditState.qoldiq)
    await say(message, "Yangi qoldiq miqdorini kiriting:\nMisol: 25")


@router.message(MaterialEditState.qoldiq)
async def material_tahrirlash_qoldiq(message: Message, state: FSMContext):
    try:
        qoldiq = float(message.text.replace(",", "."))
        if qoldiq < 0:
            raise ValueError
        await state.update_data(qoldiq=qoldiq)
        await state.set_state(MaterialEditState.birlik)
        await say(message, "Yangi birlikni kiriting:\nMisol: tonna, kg, litr")
    except ValueError:
        await say(message, "❌ Faqat musbat son kiriting!")


@router.message(MaterialEditState.birlik)
async def material_tahrirlash_birlik(message: Message, state: FSMContext, user: dict = None):
    try:
        birlik = message.text.strip()
        if not db.birlik_qollab_quvvatlanadimi(birlik):
            await say(
                message,
                "❌ Birlik tanilmadi!\n"
                "Og'irlik: tonna, kg, g, gramm, mg, meshok\n"
                "Hajm: litr, ml, m3, kubometr\n\n"
                "Qaytadan kiriting:"
            )
            return
        data = await state.get_data()
        await db.update_material(
            data["material_id"],
            data["nomi"],
            data["qoldiq"],
            birlik
        )
        if user is None:
            user = await db.get_user(message.from_user.id)
        await db.add_audit_log(
            message.from_user.id,
            user["ism"] if user else str(message.from_user.id),
            user["rol"] if user else "-",
            "Material tahrirlandi",
            f"{data['eski_nomi']} → {data['nomi']}: {data['qoldiq']} {birlik}"
        )
        await state.clear()
        await say(
            message,
            f"✅ Material yangilandi!\n"
            f"{data['nomi']} — {data['qoldiq']} {birlik}",
            reply_markup=await sozlamalar_menu(message.from_user.id)
        )
    except Exception as e:
        await state.clear()
        await say_error(
            message, e,
            reply_markup=await sozlamalar_menu(message.from_user.id)
        )


# ── Materialni o'chirish ──
@router.message(Tkey("🗑️ Materialni o'chirish"))
async def material_ochirish(message: Message, state: FSMContext, user: dict = None):
    if not await _faqat_superadmin(message, user):
        return
    await state.clear()
    kb, materials = await _material_inline(CB.MAT_DEL)
    if not materials:
        await say(message, "❌ Hali material kiritilmagan!",
                  reply_markup=await sozlamalar_menu(message.from_user.id))
        return
    await say(message, "🗑️ Qaysi materialni o'chirish?", reply_markup=kb)


@router.callback_query(lambda c: c.data and c.data.startswith(f"{CB.MAT_DEL}:"))
async def matdel_cb(callback: CallbackQuery):
    if not await _cb_ok(callback):
        return
    mid = int(callback.data.split(":", 1)[1])
    materials = await db.get_materials()
    material = next((m for m in materials if m[0] == mid), None)
    if not material:
        await callback.answer("❌ Topilmadi", show_alert=True)
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Ha, o'chirish", callback_data=f"{CB.MAT_DEL_OK}:{mid}"),
        InlineKeyboardButton(text="❌ Yo'q", callback_data=CB.MAT_DEL_NO),
    ]])
    try:
        await callback.message.edit_text(await t(
            f"🗑️ '{material[1]}' o'chirilsinmi?\n"
            f"(Formuladagi ishlatilishi ham olib tashlanadi)", callback.from_user.id),
            reply_markup=kb)
    except Exception:
        pass
    await callback.answer()


@router.callback_query(lambda c: c.data == CB.MAT_DEL_NO)
async def matdelno_cb(callback: CallbackQuery):
    try:
        await callback.message.edit_text(await t("❌ Bekor qilindi.", callback.from_user.id))
    except Exception:
        pass
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith(f"{CB.MAT_DEL_OK}:"))
async def matdelok_cb(callback: CallbackQuery):
    if not await _cb_ok(callback):
        return
    mid = int(callback.data.split(":", 1)[1])
    materials = await db.get_materials()
    material = next((m for m in materials if m[0] == mid), None)
    if material:
        await db.delete_material(mid)
        user = await db.get_user(callback.from_user.id)
        await db.add_audit_log(
            callback.from_user.id, user["ism"] if user else "-",
            user["rol"] if user else "-", "Material o'chirildi",
            f"{material[1]} o'chirildi")
        msg = await t(f"✅ {material[1]} o'chirildi!", callback.from_user.id)
    else:
        msg = await t("❌ Material topilmadi.", callback.from_user.id)
    try:
        await callback.message.edit_text(msg)
    except Exception:
        pass
    await callback.answer()


# ── Minimum chegara (tanlab tahrirlash — inline) ──
async def _minch_kb(user_id):
    materials = await db.get_materials()
    settings_rows = await db.get_settings()
    minmap = {s[3]: s[1] for s in settings_rows}
    kb = []
    for m in materials:
        min_base = minmap.get(m[0])
        if min_base and min_base > 0:
            asl = db.asosiydan_birlikga(min_base, m[4])
            belgi = f"{asl:.0f} {m[4]}"
        else:
            belgi = "—"
        kb.append([InlineKeyboardButton(
            text=f"{m[1]}: {belgi}", callback_data=f"{CB.MINCH}:{m[0]}")])
    kb.append([InlineKeyboardButton(text="✅ Tayyor", callback_data=CB.MINCH_DONE)])
    return InlineKeyboardMarkup(inline_keyboard=kb), materials


@router.message(Tkey("⚠️ Minimum chegara"))
async def min_chegara(message: Message, state: FSMContext, user: dict = None):
    if not await _faqat_superadmin(message, user):
        return
    await state.clear()
    kb, materials = await _minch_kb(message.from_user.id)
    if not materials:
        await say(message, "❌ Avval material qo'shing!",
                  reply_markup=await materiallar_submenu(message.from_user.id))
        return
    await say(message,
              "⚠️ Minimum chegara\nO'zgartirish uchun materialni tanlang:",
              reply_markup=kb)


@router.callback_query(lambda c: c.data == CB.MINCH_DONE)
async def minch_done(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await callback.message.edit_text(await t("✅ Tayyor.", callback.from_user.id))
    except Exception:
        pass
    await callback.message.answer(
        await t("📦 Materiallar bo'limi:", callback.from_user.id),
        reply_markup=await materiallar_submenu(callback.from_user.id))
    await callback.answer()


@router.callback_query(lambda c: c.data == CB.MINCH_BACK)
async def minch_back(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    kb, _ = await _minch_kb(callback.from_user.id)
    try:
        await callback.message.edit_text(
            await t("⚠️ Minimum chegara — materialni tanlang:", callback.from_user.id),
            reply_markup=kb)
    except Exception:
        pass
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith(f"{CB.MINCH}:"))
async def minch_cb(callback: CallbackQuery, state: FSMContext):
    if not await _cb_ok(callback):
        return
    mid = int(callback.data.split(":", 1)[1])
    materials = await db.get_materials()
    m = next((x for x in materials if x[0] == mid), None)
    if not m:
        await callback.answer("❌", show_alert=True)
        return
    await state.update_data(minch_mid=mid, minch_nomi=m[1], minch_birlik=m[4])
    await state.set_state(MinChegaraState.miqdor)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="❌ Bekor", callback_data=CB.MINCH_BACK)]])
    try:
        await callback.message.edit_text(await t(
            f"⚠️ {m[1]} uchun minimum chegara?\n"
            f"(Birlik: {m[4]}; 0 = chegara o'chiriladi)\nMisol: 5",
            callback.from_user.id), reply_markup=kb)
    except Exception:
        pass
    await callback.answer()


@router.message(MinChegaraState.miqdor)
async def min_chegara_miqdor(message: Message, state: FSMContext):
    data = await state.get_data()
    if "minch_mid" not in data:
        await state.clear()
        return
    try:
        miqdor = float(message.text.replace(",", "."))
        if miqdor < 0:
            raise ValueError
    except (ValueError, AttributeError):
        await say(message, "❌ Faqat musbat son kiriting! Misol: 5")
        return
    min_asosiy, _ = db.birlikni_asosiyga(miqdor, data["minch_birlik"])
    await db.set_min_chegara(data["minch_mid"], min_asosiy)
    await state.clear()
    kb, _ = await _minch_kb(message.from_user.id)
    await say(message,
              f"✅ {data['minch_nomi']} chegarasi saqlandi.\nYana o'zgartirish uchun tanlang:",
              reply_markup=kb)
