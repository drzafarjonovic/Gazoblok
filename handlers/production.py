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


class ProductionState(StatesGroup):
    mahsulot_tanlash = State()
    shablon_tanlash = State()
    miqdor_kiritish = State()
    ochirish_mahsulot = State()


async def production_menu(user_id):
    return await build_keyboard(user_id, [
        ["🏭 Ishlab chiqarishni kiritish"],
        ["📋 Bugungi ishlab chiqarish"],
        ["🗑️ Oxirgi yozuvni o'chirish"],
        ["🏠 Asosiy menyu"],
    ])


async def _kb(user_id, dinamik_rows, static_rows):
    """Dinamik + statik tugmalar (markazlashgan helper'ga ko'prik)."""
    return await build_mixed_keyboard(user_id, dinamik_rows, static_rows)


async def _mahsulot_keyboard(user_id, static_rows):
    prods = await db.get_mahsulotlar(faqat_faol=True)
    rows = [[f"{p['emoji']} {p['nomi']}"] for p in prods]
    return await _kb(user_id, rows, static_rows), prods


def _label(p):
    return f"{p['emoji']} {p['nomi']}"


async def _shablon_keyboard(user_id, shablonlar):
    rows = [[sh["nomi"]] for sh in shablonlar]
    return await _kb(user_id, rows,
                     [["✅ Tayyor — Saqlash"], ["❌ Bekor qilish"]])


def _status_text(mahsulot_nomi, shablonlar, kiritilganlar):
    lines = [f"🏭 {mahsulot_nomi}", "", "📊 Joriy holat:"]
    blok_jami = {}
    jami_qolip = 0
    for sh in shablonlar:
        soni = int(kiritilganlar.get(sh["id"], 0))
        jami_qolip += soni
        if soni:
            for c in sh["chiqim"]:
                blok_jami[c["block_kod"]] = blok_jami.get(c["block_kod"], 0) + c["soni"] * soni
        lines.append(f"   {sh['nomi']}: {soni} qolip")
    lines.append(f"   Jami qolip: {jami_qolip}")
    if blok_jami:
        lines.append("   Bloklar: " + ", ".join(f"{v}×{k}" for k, v in blok_jami.items()))
    lines.append("\nShablon tanlab miqdor kiriting yoki ✅ Tayyor bosing.")
    return "\n".join(lines)


@router.message(Tkey("🏭 Ishlab chiqarish"))
async def production(message: Message):
    await say(
        message,
        "🏭 Ishlab chiqarish bo'limi:",
        reply_markup=await production_menu(message.from_user.id)
    )


@router.message(Tkey("🏭 Ishlab chiqarishni kiritish"))
async def production_kiritish(message: Message, state: FSMContext):
    user_id = message.from_user.id
    prods = await db.get_mahsulotlar(faqat_faol=True)
    if not prods:
        await say(message, "❌ Avval mahsulot qo'shing!\n"
                           "⚙️ Sozlamalar → 🏭 Mahsulot boshqaruvi",
                  reply_markup=await production_menu(user_id))
        return
    await state.clear()
    if len(prods) == 1:
        await _boshla_shablon(message, state, prods[0])
        return
    kb, _ = await _mahsulot_keyboard(user_id, [["❌ Bekor qilish"]])
    await state.set_state(ProductionState.mahsulot_tanlash)
    await say(message, "📦 Qaysi mahsulot ishlab chiqarildi?", reply_markup=kb)


async def _boshla_shablon(message, state, mahsulot):
    user_id = message.from_user.id
    pid = mahsulot["id"]
    formula = await db.get_qolip_formula(pid)
    if not formula:
        await state.clear()
        await say(message,
                  f"❌ '{mahsulot['nomi']}' uchun qolip formulasi kiritilmagan!\n"
                  f"⚙️ Sozlamalar → 🏭 Mahsulot boshqaruvi → 📋 Formula",
                  reply_markup=await production_menu(user_id))
        return
    shablonlar = await db.get_shablonlar(pid, faqat_faol=True)
    shablonlar = [s for s in shablonlar if s["chiqim"]]
    if not shablonlar:
        await state.clear()
        await say(message,
                  f"❌ '{mahsulot['nomi']}' uchun shablon kiritilmagan!\n"
                  f"⚙️ Sozlamalar → 🏭 Mahsulot boshqaruvi → 📦 Shablonlar",
                  reply_markup=await production_menu(user_id))
        return
    await state.update_data(
        pid=pid, mahsulot_nomi=mahsulot["nomi"],
        shablonlar=shablonlar, kiritilganlar={})
    await state.set_state(ProductionState.shablon_tanlash)
    await say(message, _status_text(mahsulot["nomi"], shablonlar, {}),
              reply_markup=await _shablon_keyboard(user_id, shablonlar))


@router.message(ProductionState.mahsulot_tanlash)
async def mahsulot_tanlash(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if await eq(message, "❌ Bekor qilish"):
        await state.clear()
        await say(message, "❌ Bekor qilindi.", reply_markup=await production_menu(user_id))
        return
    prods = await db.get_mahsulotlar(faqat_faol=True)
    text = (message.text or "").strip()
    tanlangan = next((p for p in prods if _label(p) == text), None)
    if not tanlangan:
        kb, _ = await _mahsulot_keyboard(user_id, [["❌ Bekor qilish"]])
        await say(message, "❌ Tugmalardan birini tanlang!", reply_markup=kb)
        return
    await _boshla_shablon(message, state, tanlangan)


@router.message(ProductionState.shablon_tanlash)
async def shablon_tanlash(message: Message, state: FSMContext):
    user_id = message.from_user.id
    data = await state.get_data()
    shablonlar = data.get("shablonlar", [])
    kiritilganlar = data.get("kiritilganlar", {})

    if await eq(message, "❌ Bekor qilish"):
        await state.clear()
        await say(message, "❌ Bekor qilindi.", reply_markup=await production_menu(user_id))
        return

    if await eq(message, "✅ Tayyor — Saqlash"):
        ok, payload = await db.add_production(data["pid"], kiritilganlar, user_id)
        if not ok:
            if payload.get("bosh"):
                await say(message, "❌ Hech qolip kiritilmadi!\nAvval shablon tanlang.",
                          reply_markup=await _shablon_keyboard(user_id, shablonlar))
                return
            await state.clear()
            if payload.get("formula_yoq"):
                await say(message, "❌ Qolip formulasi kiritilmagan!",
                          reply_markup=await production_menu(user_id))
                return
            if payload.get("shablon_yoq"):
                await say(message, "❌ Shablon topilmadi!",
                          reply_markup=await production_menu(user_id))
                return
            text = "⛔ Ishlab chiqarish mumkin emas!\nMateriallar yetarli emas:\n\n"
            text += "\n".join(
                f"❌ {x['nomi']}: kerak {x['kerak_asl']:.2f} {x['birlik']}, "
                f"bor {x['bor_asl']:.2f} {x['birlik']}"
                for x in payload["yetishmaydi"])
            await say(message, text, reply_markup=await production_menu(user_id))
            return

        await state.clear()
        sarflar_text = "\n".join(
            f"   {x['nomi']}: -{x['ketgan_asl']:.2f} {x['birlik']} "
            f"(qoldi: {x['qoldiq_asl']:.2f} {x['birlik']})"
            for x in payload["sarflar"])
        bloklar_text = "\n".join(f"   {nomi}: +{soni} ta"
                                 for nomi, soni in payload["bloklar"].items())
        shablon_text = " | ".join(f"{s['nomi']}: {s['soni']}"
                                  for s in payload["shablonlar"])
        result = (
            f"✅ Ishlab chiqarish kiritildi!\n\n"
            f"🏭 {payload['mahsulot_nomi']}\n"
            f"📦 Jami qolip: {payload['jami_qolip']} ta\n"
            f"   {shablon_text}\n\n"
            f"🧱 Tayyor bloklar:\n{bloklar_text}\n\n"
            f"📉 Sarflangan:\n{sarflar_text}")
        await say(message, result, reply_markup=await production_menu(user_id))

        if payload["ogohlantirish"]:
            ogoh_text = "\n\n".join(
                f"⚠️ {x['nomi']} kam qoldi!\n"
                f"   Qoldiq: {x['qoldiq_asl']:.2f} {x['birlik']}\n"
                f"   Minimum: {x['min_asl']:.2f} {x['birlik']}"
                for x in payload["ogohlantirish"])
            await say(message, ogoh_text)
        return

    # Shablon tanlash
    text = (message.text or "").strip()
    tanlangan = next((s for s in shablonlar if s["nomi"] == text), None)
    if tanlangan is None:
        await say(message, "❌ Tugmalardan birini tanlang!",
                  reply_markup=await _shablon_keyboard(user_id, shablonlar))
        return
    await state.update_data(tanlangan_shablon=tanlangan["id"])
    await state.set_state(ProductionState.miqdor_kiritish)
    joriy = int(kiritilganlar.get(tanlangan["id"], 0))
    ch = ", ".join(f"{c['soni']}×{c['block_kod']}" for c in tanlangan["chiqim"])
    await say(message,
              f"📦 {tanlangan['nomi']} (1 qolip: {ch})\n\n"
              f"Nechta qolip? (Hozir: {joriy} ta)\nMisol: 5\n"
              f"💡 0 = bu shablonni ro'yxatdan olib tashlash")


@router.message(ProductionState.miqdor_kiritish)
async def miqdor_kiritish(message: Message, state: FSMContext):
    user_id = message.from_user.id
    try:
        miqdor = int(message.text.strip())
        if miqdor < 0:
            raise ValueError
    except (ValueError, AttributeError):
        await say(message, "❌ Faqat musbat son kiriting! Misol: 5")
        return

    data = await state.get_data()
    shablon_id = data.get("tanlangan_shablon")
    kiritilganlar = data.get("kiritilganlar", {})
    shablonlar = data.get("shablonlar", [])
    mahsulot_nomi = data.get("mahsulot_nomi", "")

    if miqdor == 0:
        kiritilganlar.pop(shablon_id, None)
    else:
        kiritilganlar[shablon_id] = miqdor

    await state.update_data(kiritilganlar=kiritilganlar)
    await state.set_state(ProductionState.shablon_tanlash)
    await say(message, _status_text(mahsulot_nomi, shablonlar, kiritilganlar),
              reply_markup=await _shablon_keyboard(user_id, shablonlar))


@router.message(Tkey("📋 Bugungi ishlab chiqarish"))
async def bugungi_production(message: Message):
    user_id = message.from_user.id
    prods = await db.get_mahsulotlar(faqat_faol=True)
    if not prods:
        await say(message, "❌ Mahsulot yo'q.", reply_markup=await production_menu(user_id))
        return
    bloklar_bor = False
    text = "📋 Bugungi ishlab chiqarish:\n"
    infos = await asyncio.gather(*(db.get_production_today(p["id"]) for p in prods))
    for p, info in zip(prods, infos):
        if info["jami_qolip"] <= 0:
            continue
        bloklar_bor = True
        text += f"\n🏭 {p['emoji']} {p['nomi']}\n"
        text += f"   Jami qolip: {info['jami_qolip']} ta\n"
        for sh in info["shablonlar"]:
            text += f"   {sh['nomi']}: {sh['soni']}\n"
        if info["bloklar"]:
            text += "   🧱 " + ", ".join(f"{nomi}: {soni}"
                                          for nomi, soni in info["bloklar"].items()) + "\n"
    if not bloklar_bor:
        text = "📋 Bugun hali ishlab chiqarish kiritilmagan."
    await say(message, text, reply_markup=await production_menu(user_id))


@router.message(Tkey("🗑️ Oxirgi yozuvni o'chirish"))
async def oxirgi_ochirish(message: Message, state: FSMContext):
    user_id = message.from_user.id
    prods = await db.get_mahsulotlar(faqat_faol=True)
    if not prods:
        await say(message, "❌ Mahsulot yo'q.", reply_markup=await production_menu(user_id))
        return
    await state.clear()
    if len(prods) == 1:
        await _ochir(message, prods[0]["id"])
        return
    kb, _ = await _mahsulot_keyboard(user_id, [["❌ Bekor qilish"]])
    await state.set_state(ProductionState.ochirish_mahsulot)
    await say(message, "📦 Qaysi mahsulotning oxirgi yozuvini o'chirasiz?", reply_markup=kb)


@router.message(ProductionState.ochirish_mahsulot)
async def oxirgi_ochirish_tanla(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if await eq(message, "❌ Bekor qilish"):
        await state.clear()
        await say(message, "❌ Bekor qilindi.", reply_markup=await production_menu(user_id))
        return
    prods = await db.get_mahsulotlar(faqat_faol=True)
    text = (message.text or "").strip()
    tanlangan = next((p for p in prods if _label(p) == text), None)
    if not tanlangan:
        kb, _ = await _mahsulot_keyboard(user_id, [["❌ Bekor qilish"]])
        await say(message, "❌ Tugmalardan birini tanlang!", reply_markup=kb)
        return
    await state.clear()
    await _ochir(message, tanlangan["id"])


async def _ochir(message, pid):
    user_id = message.from_user.id
    try:
        user = await db.get_user(user_id)
        muvaffaqiyat, tafsilot = await db.delete_last_production_with_restore(pid)
        if muvaffaqiyat:
            await db.add_audit_log(
                user_id, user["ism"] if user else str(user_id),
                user["rol"] if user else "-",
                "Ishlab chiqarish o'chirildi", tafsilot)
            await say(message, f"✅ Oxirgi yozuv o'chirildi!\n\n{tafsilot}",
                      reply_markup=await production_menu(user_id))
        else:
            await say(message, tafsilot, reply_markup=await production_menu(user_id))
    except Exception as e:
        await say_error(message, e, reply_markup=await production_menu(user_id))
