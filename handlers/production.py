from aiogram import Router
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import database as db
from translation import Tkey, eq, say, say_error, build_keyboard, foydalanuvchi_tili, tarjima_qil, t, register_ui

router = Router()

# Shablon tugmalarining statik qismi (kanonik o'zbekcha)
SHABLON_LABEL = {
    1: "📦 Shablon 1 — 12A",
    2: "📦 Shablon 2 — 24B",
    3: "📦 Shablon 3 — 11A+2B",
}

# Shablon yorliqlari va "qolip" so'zini pre-warm katalogiga qo'shamiz
register_ui(*SHABLON_LABEL.values(), "qolip")


class ProductionState(StatesGroup):
    shablon_tanlash = State()
    miqdor_kiritish = State()


async def production_menu(user_id):
    return await build_keyboard(user_id, [
        ["🏭 Ishlab chiqarishni kiritish"],
        ["📋 Bugungi ishlab chiqarish"],
        ["🗑️ Oxirgi yozuvni o'chirish"],
        ["🏠 Asosiy menyu"],
    ])


async def shablon_menu(user_id, kiritilganlar):
    """Kiritilgan shablonlarni ko'rsatib, tarjima qilingan tugmalar chiqaradi."""
    til = await foydalanuvchi_tili(user_id)
    qolip_so = "qolip" if til == "uz" else await tarjima_qil("qolip", til)
    rows = []
    for n in (1, 2, 3):
        soni = kiritilganlar.get(n, 0)
        label = SHABLON_LABEL[n] if til == "uz" else await tarjima_qil(SHABLON_LABEL[n], til)
        rows.append([f"{label} ({soni} {qolip_so})"])
    rows.append(["✅ Tayyor — Saqlash"])
    rows.append(["❌ Bekor qilish"])
    return await build_keyboard(user_id, rows)


async def _shablon_aniqla(message: Message):
    """Kelgan matn qaysi shablonga tegishli ekanini aniqlaydi (til-aware)."""
    til = await foydalanuvchi_tili(message.from_user.id)
    text = message.text or ""
    for n in (1, 2, 3):
        label = SHABLON_LABEL[n] if til == "uz" else await tarjima_qil(SHABLON_LABEL[n], til)
        if label in text:
            return n
    return None


@router.message(Tkey("🏭 Ishlab chiqarish"))
async def production(message: Message):
    await say(
        message,
        "🏭 Ishlab chiqarish bo'limi:",
        reply_markup=await production_menu(message.from_user.id)
    )


@router.message(Tkey("🏭 Ishlab chiqarishni kiritish"))
async def production_kiritish(message: Message, state: FSMContext):
    formula = await db.get_qolip_formula()
    if not formula:
        await say(
            message,
            "❌ Avval qolip formulasini kiriting!\n"
            "⚙️ Sozlamalar → 📋 Qolip formulasi"
        )
        return

    await state.clear()
    await state.update_data(kiritilganlar={})
    await state.set_state(ProductionState.shablon_tanlash)

    await say(
        message,
        "📦 Qaysi shablondan nechta qolip quyildi?\n\n"
        "Shablonni tanlang va miqdor kiriting.\n"
        "Bir necha shablon kiritsa ham bo'ladi.\n"
        "Oxirida ✅ Tayyor bosing.",
        reply_markup=await shablon_menu(message.from_user.id, {})
    )


@router.message(ProductionState.shablon_tanlash)
async def shablon_tanlash(message: Message, state: FSMContext):
    user_id = message.from_user.id

    if await eq(message, "❌ Bekor qilish"):
        await state.clear()
        await say(
            message,
            "❌ Bekor qilindi.",
            reply_markup=await production_menu(user_id)
        )
        return

    if await eq(message, "✅ Tayyor — Saqlash"):
        data = await state.get_data()
        kiritilganlar = data.get("kiritilganlar", {})

        # Butun jarayon bitta atomik tranzaksiyada (race-condition'siz)
        ok, payload = await db.add_production(kiritilganlar, user_id)

        if not ok:
            if payload.get("bosh"):
                await say(
                    message,
                    "❌ Hech qolip kiritilmadi!\nAvval shablon tanlang.",
                    reply_markup=await shablon_menu(user_id, {})
                )
                return
            await state.clear()
            if payload.get("formula_yoq"):
                await say(
                    message,
                    "❌ Qolip formulasi kiritilmagan!",
                    reply_markup=await production_menu(user_id)
                )
                return
            text = "⛔ Ishlab chiqarish mumkin emas!\nMateriallar yetarli emas:\n\n"
            text += "\n".join(
                f"❌ {x['nomi']}: kerak {x['kerak_asl']:.2f} {x['birlik']}, "
                f"bor {x['bor_asl']:.2f} {x['birlik']}"
                for x in payload["yetishmaydi"]
            )
            await say(message, text, reply_markup=await production_menu(user_id))
            return

        await state.clear()

        sarflar_text = "\n".join(
            f"   {x['nomi']}: -{x['ketgan_asl']:.2f} {x['birlik']} "
            f"(qoldi: {x['qoldiq_asl']:.2f} {x['birlik']})"
            for x in payload["sarflar"]
        )
        result = (
            f"✅ Ishlab chiqarish kiritildi!\n\n"
            f"📦 Jami qolip: {payload['jami_qolip']} ta\n"
            f"   Shablon 1: {payload['s1']} | Shablon 2: {payload['s2']} | "
            f"Shablon 3: {payload['s3']}\n\n"
            f"🧱 Tayyor bloklar:\n"
            f"   A blok: +{payload['A_blok']} ta\n"
            f"   B blok: +{payload['B_blok']} ta\n\n"
            f"📉 Sarflangan:\n{sarflar_text}"
        )
        await say(message, result, reply_markup=await production_menu(user_id))

        if payload["ogohlantirish"]:
            ogoh_text = "\n\n".join(
                f"⚠️ {x['nomi']} kam qoldi!\n"
                f"   Qoldiq: {x['qoldiq_asl']:.2f} {x['birlik']}\n"
                f"   Minimum: {x['min_asl']:.2f} {x['birlik']}"
                for x in payload["ogohlantirish"]
            )
            await say(message, ogoh_text)
        return

    # Shablon tanlash
    shablon = await _shablon_aniqla(message)
    if shablon is None:
        await say(
            message,
            "❌ Tugmalardan birini tanlang!",
            reply_markup=await shablon_menu(
                user_id, (await state.get_data()).get("kiritilganlar", {})
            )
        )
        return

    await state.update_data(tanlangan_shablon=shablon)
    await state.set_state(ProductionState.miqdor_kiritish)

    shablon_info = {
        1: "Shablon 1 (faqat A: 12 ta/qolip)",
        2: "Shablon 2 (faqat B: 24 ta/qolip)",
        3: "Shablon 3 (aralash: 11A + 2B/qolip)",
    }
    data = await state.get_data()
    joriy = data.get("kiritilganlar", {}).get(shablon, 0)

    await say(
        message,
        f"📦 {shablon_info[shablon]}\n\n"
        f"Nechta qolip? (Hozir: {joriy} ta)\n"
        f"Misol: 5"
    )


@router.message(ProductionState.miqdor_kiritish)
async def miqdor_kiritish(message: Message, state: FSMContext):
    try:
        miqdor = int(message.text.strip())
        if miqdor < 0:
            raise ValueError

        data = await state.get_data()
        shablon = data.get("tanlangan_shablon")
        kiritilganlar = data.get("kiritilganlar", {})

        if miqdor == 0:
            # 0 kiritilsa o'chirish
            kiritilganlar.pop(shablon, None)
        else:
            kiritilganlar[shablon] = miqdor

        await state.update_data(kiritilganlar=kiritilganlar)
        await state.set_state(ProductionState.shablon_tanlash)

        # Joriy holat
        s1 = kiritilganlar.get(1, 0)
        s2 = kiritilganlar.get(2, 0)
        s3 = kiritilganlar.get(3, 0)
        jami = s1 + s2 + s3
        A_blok = s1 * 12 + s3 * 11
        B_blok = s2 * 24 + s3 * 2

        status = (
            f"📊 Joriy holat:\n"
            f"   Sh1: {s1} | Sh2: {s2} | Sh3: {s3}\n"
            f"   Jami qolip: {jami} ta\n"
            f"   A blok: {A_blok} ta | B blok: {B_blok} ta\n\n"
            f"Yana shablon qo'shing yoki ✅ Tayyor bosing."
        )
        await say(message, status, reply_markup=await shablon_menu(message.from_user.id, kiritilganlar))

    except ValueError:
        await say(message, "❌ Faqat musbat son kiriting! Misol: 5")


@router.message(Tkey("📋 Bugungi ishlab chiqarish"))
async def bugungi_production(message: Message):
    bugun = db.bugungi_sana()
    logs = await db.get_production_by_date(bugun)
    if not logs:
        await say(
            message,
            "📋 Bugun hali ishlab chiqarish kiritilmagan.",
            reply_markup=await production_menu(message.from_user.id)
        )
        return

    s1 = s2 = s3 = 0
    for log in logs:
        if log[0] == 1: s1 += log[1]
        elif log[0] == 2: s2 += log[1]
        elif log[0] == 3: s3 += log[1]

    jami_qolip = s1 + s2 + s3
    A_blok = s1 * 12 + s3 * 11
    B_blok = s2 * 24 + s3 * 2

    text = (
        f"📋 Bugungi ishlab chiqarish:\n\n"
        f"📦 Jami qolip: {jami_qolip} ta\n"
        f"   Shablon 1: {s1} | Shablon 2: {s2} | Shablon 3: {s3}\n\n"
        f"🧱 Tayyor bloklar:\n"
        f"   A blok: {A_blok} ta\n"
        f"   B blok: {B_blok} ta\n"
    )
    await say(message, text, reply_markup=await production_menu(message.from_user.id))


@router.message(Tkey("🗑️ Oxirgi yozuvni o'chirish"))
async def oxirgi_ochirish(message: Message):
    try:
        user = await db.get_user(message.from_user.id)
        muvaffaqiyat, tafsilot = await db.delete_last_production_with_restore()
        if muvaffaqiyat:
            await db.add_audit_log(
                message.from_user.id,
                user["ism"] if user else str(message.from_user.id),
                user["rol"] if user else "-",
                "Ishlab chiqarish o'chirildi",
                tafsilot
            )
            await say(
                message,
                f"✅ Oxirgi yozuv o'chirildi!\n\n{tafsilot}",
                reply_markup=await production_menu(message.from_user.id)
            )
        else:
            await say(message, tafsilot, reply_markup=await production_menu(message.from_user.id))
    except Exception as e:
        await say_error(
            message, e,
            reply_markup=await production_menu(message.from_user.id)
        )
