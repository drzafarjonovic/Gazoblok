from aiogram import Router
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import database as db
from translation import Tkey, eq, say, build_keyboard, foydalanuvchi_tili, tarjima_qil, t, register_ui

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

        s1 = kiritilganlar.get(1, 0)
        s2 = kiritilganlar.get(2, 0)
        s3 = kiritilganlar.get(3, 0)
        jami_qolip = s1 + s2 + s3

        if jami_qolip == 0:
            await say(
                message,
                "❌ Hech qolip kiritilmadi!\n"
                "Avval shablon tanlang.",
                reply_markup=await shablon_menu(user_id, {})
            )
            return

        # Material tekshiruvi
        yetishmaydi = await db.check_material_yetarli(jami_qolip)
        if yetishmaydi:
            await state.clear()
            text = "⛔ Ishlab chiqarish mumkin emas!\nMateriallar yetarli emas:\n\n"
            text += "\n".join(yetishmaydi)
            await say(message, text, reply_markup=await production_menu(user_id))
            return

        A_blok = s1 * 12 + s3 * 11
        B_blok = s2 * 24 + s3 * 2
        bugun = db.bugungi_sana()

        # Bazaga yozish
        prod_ids = []
        if s1 > 0:
            pid = await db.add_production_log(bugun, 1, s1, user_id)
            prod_ids.append((pid, 1, s1))
        if s2 > 0:
            pid = await db.add_production_log(bugun, 2, s2, user_id)
            prod_ids.append((pid, 2, s2))
        if s3 > 0:
            pid = await db.add_production_log(bugun, 3, s3, user_id)
            prod_ids.append((pid, 3, s3))

        # Xom ashyoni kamaytirish
        formula = await db.get_qolip_formula()
        ogohlantirish = []
        sarflar = []
        min_settings = await db.get_settings()
        min_map = {s[3]: s[1] for s in min_settings}

        for f in formula:
            nomi = f[0]
            miqdor_asosiy = f[6]
            qoldiq_asosiy = f[3]
            asl_birlik = f[7]
            material_id = f[5]

            ketgan_asosiy = miqdor_asosiy * jami_qolip
            yangi_qoldiq = max(0.0, qoldiq_asosiy - ketgan_asosiy)
            await db.update_material_qoldiq(material_id, yangi_qoldiq)

            # Chiqim log (asosiy birlikda — asl_birlik turiga mos)
            for pid, shablon, qolip_soni in prod_ids:
                ketgan_bu_log = miqdor_asosiy * qolip_soni
                await db.add_material_chiqim_log(
                    pid, material_id, nomi,
                    ketgan_bu_log, asl_birlik, bugun
                )

            ketgan_asl = db.asosiydan_birlikga(ketgan_asosiy, asl_birlik)
            qoldiq_asl = db.asosiydan_birlikga(yangi_qoldiq, asl_birlik)
            sarflar.append(
                f"   {nomi}: -{ketgan_asl:.2f} {asl_birlik} "
                f"(qoldi: {qoldiq_asl:.2f} {asl_birlik})"
            )

            min_ch = min_map.get(material_id)
            if min_ch and yangi_qoldiq <= min_ch:
                min_asl = db.asosiydan_birlikga(min_ch, asl_birlik)
                ogohlantirish.append(
                    f"⚠️ {nomi} kam qoldi!\n"
                    f"   Qoldiq: {qoldiq_asl:.2f} {asl_birlik}\n"
                    f"   Minimum: {min_asl:.2f} {asl_birlik}"
                )

        # Tayyor mahsulot omboriga qo'shish
        if A_blok > 0:
            await db.update_finished_goods("A", A_blok)
        if B_blok > 0:
            await db.update_finished_goods("B", B_blok)

        # Audit log
        user = await db.get_user(user_id)
        await db.add_audit_log(
            user_id,
            user["ism"] if user else str(user_id),
            user["rol"] if user else "-",
            "Ishlab chiqarish kiritildi",
            f"Qolip: {jami_qolip} ta | A: {A_blok} ta | B: {B_blok} ta"
        )

        await state.clear()

        sarflar_text = "\n".join(sarflar)
        result = (
            f"✅ Ishlab chiqarish kiritildi!\n\n"
            f"📦 Jami qolip: {jami_qolip} ta\n"
            f"   Shablon 1: {s1} | Shablon 2: {s2} | Shablon 3: {s3}\n\n"
            f"🧱 Tayyor bloklar:\n"
            f"   A blok: +{A_blok} ta\n"
            f"   B blok: +{B_blok} ta\n\n"
            f"📉 Sarflangan:\n{sarflar_text}"
        )
        await say(message, result, reply_markup=await production_menu(user_id))

        if ogohlantirish:
            await say(message, "\n\n".join(ogohlantirish))
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
        await say(
            message,
            f"❌ Xatolik: {str(e)}",
            reply_markup=await production_menu(message.from_user.id)
        )
