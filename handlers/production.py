"""Ishlab chiqarish — inline edit-in-place oqim (v2.2).

Asosiy menyudagi "🏭 Ishlab chiqarish" (Reply) bosilganda inline bo'lim ochiladi;
undan keyingi barcha navigatsiya/tanlash inline, miqdor esa matn bilan kiritiladi.
"""
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

P_KIRITISH = "ishlab_chiqarish_kiritish"
P_KORISH = "ishlab_chiqarish_korish"


class ProductionState(StatesGroup):
    miqdor_kiritish = State()


def _label(p):
    return f"{p['emoji']} {p['nomi']}"


def _status_text(mahsulot_nomi, shablonlar, kiritilganlar):
    lines = [f"🏭 {mahsulot_nomi}", "", "📊 Joriy holat:"]
    blok_jami = {}
    jami_qolip = 0
    for sh in shablonlar:
        soni = int(kiritilganlar.get(str(sh["id"]), kiritilganlar.get(sh["id"], 0)))
        jami_qolip += soni
        if soni:
            for c in sh["chiqim"]:
                blok_jami[c["block_kod"]] = blok_jami.get(c["block_kod"], 0) + c["soni"] * soni
        lines.append(f"   {sh['nomi']}: {soni} qolip")
    lines.append(f"   Jami qolip: {jami_qolip}")
    if blok_jami:
        lines.append("   Bloklar: " + ", ".join(f"{v}×{k}" for k, v in blok_jami.items()))
    lines.append("\nShablon tanlab miqdor kiriting yoki ✅ Saqlang.")
    return "\n".join(lines)


async def _root_kb(user_id):
    return await menu_kb(user_id, [
        [("➕ Ishlab chiqarishni kiritish", CB.PD_INPUT)],
        [("📋 Bugungi ishlab chiqarish", CB.PD_TODAY)],
        [("🗑️ Oxirgi yozuvni o'chirish", CB.PD_DELLAST)],
    ])


async def _board_kb(user_id, shablonlar):
    dyn = [[(sh["nomi"], f"{CB.PD_TPL}:{sh['id']}")] for sh in shablonlar]
    return await menu_kb(user_id, [
        [("✅ Saqlash", CB.PD_SAVE), ("❌ Bekor qilish", CB.PD_CANCEL)],
    ], dyn)


# ── Kirish (Reply main menu) ──
@router.message(Tkey("🏭 Ishlab chiqarish"))
async def production(message: Message, state: FSMContext):
    await state.clear()
    await send(message, "🏭 Ishlab chiqarish bo'limi:",
               await _root_kb(message.from_user.id))


@router.callback_query(lambda c: c.data == CB.PD_ROOT)
async def pd_root(callback: CallbackQuery, state: FSMContext):
    if not await cb_guard(callback):
        return
    await state.clear()
    await show(callback, "🏭 Ishlab chiqarish bo'limi:",
               await _root_kb(callback.from_user.id))
    await callback.answer()


# ── Kiritish: mahsulot tanlash ──
@router.callback_query(lambda c: c.data == CB.PD_INPUT)
async def pd_input(callback: CallbackQuery, state: FSMContext):
    if not await cb_guard(callback, P_KIRITISH):
        return
    await state.clear()
    prods = await db.get_mahsulotlar(faqat_faol=True)
    if not prods:
        await show(callback, "❌ Avval mahsulot qo'shing!\n"
                             "⚙️ Sozlamalar → 🏭 Mahsulot boshqaruvi",
                   await _root_kb(callback.from_user.id))
        await callback.answer()
        return
    if len(prods) == 1:
        await _start_board(callback, state, prods[0])
        await callback.answer()
        return
    dyn = [[(_label(p), f"{CB.PD_PROD}:{p['id']}")] for p in prods]
    kb = await menu_kb(callback.from_user.id, [[("⬅️ Ortga", CB.PD_ROOT)]], dyn)
    await show(callback, "📦 Qaysi mahsulot ishlab chiqarildi?", kb)
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith(f"{CB.PD_PROD}:"))
async def pd_prod(callback: CallbackQuery, state: FSMContext):
    if not await cb_guard(callback, P_KIRITISH):
        return
    pid = int(callback.data.split(":", 1)[1])
    mahsulot = await db.get_mahsulot(pid)
    if not mahsulot:
        await callback.answer("❌ Topilmadi", show_alert=True)
        return
    await _start_board(callback, state, mahsulot)
    await callback.answer()


async def _start_board(callback, state, mahsulot):
    pid = mahsulot["id"]
    formula = await db.get_qolip_formula(pid)
    if not formula:
        await show(callback,
                   f"❌ '{mahsulot['nomi']}' uchun qolip formulasi kiritilmagan!\n"
                   f"⚙️ Sozlamalar → 🏭 Mahsulot boshqaruvi → 📋 Formula",
                   await _root_kb(callback.from_user.id))
        return
    shablonlar = await db.get_shablonlar(pid, faqat_faol=True)
    shablonlar = [s for s in shablonlar if s["chiqim"]]
    if not shablonlar:
        await show(callback,
                   f"❌ '{mahsulot['nomi']}' uchun shablon kiritilmagan!\n"
                   f"⚙️ Sozlamalar → 🏭 Mahsulot boshqaruvi → 📦 Shablonlar",
                   await _root_kb(callback.from_user.id))
        return
    await state.set_state(None)
    await state.update_data(
        pid=pid, mahsulot_nomi=mahsulot["nomi"], shablonlar=shablonlar,
        kiritilganlar={},
        nav_chat=callback.message.chat.id, nav_msg=callback.message.message_id)
    await show(callback, _status_text(mahsulot["nomi"], shablonlar, {}),
               await _board_kb(callback.from_user.id, shablonlar))


@router.callback_query(lambda c: c.data == CB.PD_BOARD)
async def pd_board(callback: CallbackQuery, state: FSMContext):
    if not await cb_guard(callback, P_KIRITISH):
        return
    data = await state.get_data()
    if "pid" not in data:
        await pd_root(callback, state)
        return
    await state.set_state(None)
    await show(callback, _status_text(data["mahsulot_nomi"], data["shablonlar"],
                                      data.get("kiritilganlar", {})),
               await _board_kb(callback.from_user.id, data["shablonlar"]))
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith(f"{CB.PD_TPL}:"))
async def pd_tpl(callback: CallbackQuery, state: FSMContext):
    if not await cb_guard(callback, P_KIRITISH):
        return
    data = await state.get_data()
    shablonlar = data.get("shablonlar", [])
    sid = int(callback.data.split(":", 1)[1])
    tanlangan = next((s for s in shablonlar if s["id"] == sid), None)
    if not tanlangan:
        await callback.answer("❌", show_alert=True)
        return
    await state.update_data(tanlangan_shablon=sid)
    await state.set_state(ProductionState.miqdor_kiritish)
    joriy = int(data.get("kiritilganlar", {}).get(str(sid),
                data.get("kiritilganlar", {}).get(sid, 0)))
    ch = ", ".join(f"{c['soni']}×{c['block_kod']}" for c in tanlangan["chiqim"])
    kb = await menu_kb(callback.from_user.id, [[("⬅️ Ortga", CB.PD_BOARD)]])
    await show(callback,
               f"📦 {tanlangan['nomi']} (1 qolip: {ch})\n\n"
               f"Nechta qolip? (Hozir: {joriy} ta)\nMisol: 5\n"
               f"💡 0 = bu shablonni ro'yxatdan olib tashlash", kb)
    await callback.answer()


@router.message(ProductionState.miqdor_kiritish)
async def pd_miqdor(message: Message, state: FSMContext):
    uid = message.from_user.id
    try:
        miqdor = int(message.text.strip())
        if miqdor < 0:
            raise ValueError
    except (ValueError, AttributeError):
        await say(message, "❌ Faqat musbat son kiriting! Misol: 5")
        return
    data = await state.get_data()
    sid = data.get("tanlangan_shablon")
    kiritilganlar = data.get("kiritilganlar", {})
    shablonlar = data.get("shablonlar", [])
    if miqdor == 0:
        kiritilganlar.pop(str(sid), None)
        kiritilganlar.pop(sid, None)
    else:
        kiritilganlar[str(sid)] = miqdor
    await state.update_data(kiritilganlar=kiritilganlar)
    await state.set_state(None)

    text = _status_text(data.get("mahsulot_nomi", ""), shablonlar, kiritilganlar)
    kb = await _board_kb(uid, shablonlar)
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
        sent = await send(message, text, kb)
        if sent:
            await state.update_data(nav_chat=sent.chat.id, nav_msg=sent.message_id)


@router.callback_query(lambda c: c.data == CB.PD_SAVE)
async def pd_save(callback: CallbackQuery, state: FSMContext):
    user = await cb_guard(callback, P_KIRITISH)
    if not user:
        return
    data = await state.get_data()
    if "pid" not in data:
        await callback.answer("❌ Sessiya tugagan", show_alert=True)
        return
    kiritilganlar = data.get("kiritilganlar", {})
    ok, payload = await db.add_production(data["pid"], kiritilganlar, callback.from_user.id)
    if not ok:
        if payload.get("bosh"):
            await callback.answer("❌ Hech qolip kiritilmadi! Avval shablon tanlang.",
                                  show_alert=True)
            return
        await state.clear()
        if payload.get("formula_yoq"):
            await show(callback, "❌ Qolip formulasi kiritilmagan!",
                       await _root_kb(callback.from_user.id))
            await callback.answer()
            return
        if payload.get("shablon_yoq"):
            await show(callback, "❌ Shablon topilmadi!",
                       await _root_kb(callback.from_user.id))
            await callback.answer()
            return
        text = "⛔ Ishlab chiqarish mumkin emas!\nMateriallar yetarli emas:\n\n"
        text += "\n".join(
            f"❌ {x['nomi']}: kerak {x['kerak_asl']:.2f} {x['birlik']}, "
            f"bor {x['bor_asl']:.2f} {x['birlik']}" for x in payload["yetishmaydi"])
        await show(callback, text, await _root_kb(callback.from_user.id))
        await callback.answer()
        return

    await state.clear()
    sarflar_text = "\n".join(
        f"   {x['nomi']}: -{x['ketgan_asl']:.2f} {x['birlik']} "
        f"(qoldi: {x['qoldiq_asl']:.2f} {x['birlik']})" for x in payload["sarflar"])
    bloklar_text = "\n".join(f"   {nomi}: +{soni} ta"
                             for nomi, soni in payload["bloklar"].items())
    shablon_text = " | ".join(f"{s['nomi']}: {s['soni']}" for s in payload["shablonlar"])
    result = (
        f"✅ Ishlab chiqarish kiritildi!\n\n"
        f"🏭 {payload['mahsulot_nomi']}\n"
        f"📦 Jami qolip: {payload['jami_qolip']} ta\n   {shablon_text}\n\n"
        f"🧱 Tayyor bloklar:\n{bloklar_text}\n\n"
        f"📉 Sarflangan:\n{sarflar_text}")
    await show(callback, result, await _root_kb(callback.from_user.id))
    await callback.answer("✅")

    if payload["ogohlantirish"]:
        ogoh_text = "\n\n".join(
            f"⚠️ {x['nomi']} kam qoldi!\n"
            f"   Qoldiq: {x['qoldiq_asl']:.2f} {x['birlik']}\n"
            f"   Minimum: {x['min_asl']:.2f} {x['birlik']}"
            for x in payload["ogohlantirish"])
        await send(callback.message, ogoh_text)


@router.callback_query(lambda c: c.data == CB.PD_CANCEL)
async def pd_cancel(callback: CallbackQuery, state: FSMContext):
    if not await cb_guard(callback):
        return
    await state.clear()
    await show(callback, "❌ Bekor qilindi.", await _root_kb(callback.from_user.id))
    await callback.answer()


# ── Bugungi ishlab chiqarish ──
@router.callback_query(lambda c: c.data == CB.PD_TODAY)
async def pd_today(callback: CallbackQuery):
    if not await cb_guard(callback, P_KORISH, P_KIRITISH):
        return
    prods = await db.get_mahsulotlar(faqat_faol=True)
    text = "📋 Bugungi ishlab chiqarish:\n"
    bor = False
    if prods:
        infos = await asyncio.gather(*(db.get_production_today(p["id"]) for p in prods))
        for p, info in zip(prods, infos):
            if info["jami_qolip"] <= 0:
                continue
            bor = True
            text += f"\n🏭 {p['emoji']} {p['nomi']}\n   Jami qolip: {info['jami_qolip']} ta\n"
            for sh in info["shablonlar"]:
                text += f"   {sh['nomi']}: {sh['soni']}\n"
            if info["bloklar"]:
                text += "   🧱 " + ", ".join(f"{n}: {s}"
                                              for n, s in info["bloklar"].items()) + "\n"
    if not bor:
        text = "📋 Bugun hali ishlab chiqarish kiritilmagan."
    kb = await menu_kb(callback.from_user.id, [[("⬅️ Ortga", CB.PD_ROOT)]])
    await show(callback, text, kb)
    await callback.answer()


# ── Oxirgi yozuvni o'chirish ──
@router.callback_query(lambda c: c.data == CB.PD_DELLAST)
async def pd_dellast(callback: CallbackQuery, state: FSMContext):
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
    dyn = [[(_label(p), f"{CB.PD_DELPROD}:{p['id']}")] for p in prods]
    kb = await menu_kb(callback.from_user.id, [[("⬅️ Ortga", CB.PD_ROOT)]], dyn)
    await show(callback, "📦 Qaysi mahsulotning oxirgi yozuvini o'chirasiz?", kb)
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith(f"{CB.PD_DELPROD}:"))
async def pd_delprod(callback: CallbackQuery):
    if not await cb_guard(callback, P_KIRITISH):
        return
    pid = int(callback.data.split(":", 1)[1])
    p = await db.get_mahsulot(pid)
    await _del_confirm(callback, pid, p["nomi"] if p else "?")
    await callback.answer()


async def _del_confirm(callback, pid, nomi):
    kb = await menu_kb(callback.from_user.id, [
        [("✅ Ha, o'chirish", f"{CB.PD_DELOK}:{pid}")],
        [("⬅️ Yo'q", CB.PD_ROOT)],
    ])
    await show(callback, f"🗑️ '{nomi}' oxirgi ishlab chiqarish yozuvi o'chirilsinmi?\n"
                         f"(Materiallar va bloklar omborga qaytariladi)", kb)


@router.callback_query(lambda c: c.data and c.data.startswith(f"{CB.PD_DELOK}:"))
async def pd_delok(callback: CallbackQuery):
    user = await cb_guard(callback, P_KIRITISH)
    if not user:
        return
    pid = int(callback.data.split(":", 1)[1])
    try:
        ok, tafsilot = await db.delete_last_production_with_restore(pid)
        if ok:
            await db.add_audit_log(
                callback.from_user.id, user["ism"], user["rol"],
                "Ishlab chiqarish o'chirildi", tafsilot)
            await show(callback, f"✅ Oxirgi yozuv o'chirildi!\n\n{tafsilot}",
                       await _root_kb(callback.from_user.id))
        else:
            await show(callback, tafsilot, await _root_kb(callback.from_user.id))
        await callback.answer()
    except Exception as e:
        await say_error(callback.message, e)
        await callback.answer("❌", show_alert=True)
