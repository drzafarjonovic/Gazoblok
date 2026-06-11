from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import date
import database as db

router = Router()

class ProductionState(StatesGroup):
    shablon1 = State()
    shablon2 = State()
    shablon3 = State()

def production_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏭 Ishlab chiqarishni kiritish")],
            [KeyboardButton(text="📋 Bugungi ishlab chiqarish")],
            [KeyboardButton(text="🗑️ Oxirgi yozuvni o'chirish")],
            [KeyboardButton(text="🏠 Asosiy menyu")],
        ],
        resize_keyboard=True
    )

@router.message(F.text == "🏭 Ishlab chiqarish")
async def production(message: Message):
    await message.answer(
        "🏭 Ishlab chiqarish bo'limi:",
        reply_markup=production_menu()
    )

@router.message(F.text == "🏭 Ishlab chiqarishni kiritish")
async def production_kiritish(message: Message, state: FSMContext):
    formula = await db.get_qolip_formula()
    if not formula:
        await message.answer(
            "❌ Avval qolip formulasini kiriting!\n"
            "⚙️ Sozlamalar → 📋 Qolip formulasi"
        )
        return
    await state.set_state(ProductionState.shablon1)
    await message.answer(
        "📦 Shablon 1 (faqat A: 12 ta/qolip)\n"
        "Nechta qolip quyildi?\n"
        "Agar yo'q bo'lsa: 0"
    )

@router.message(ProductionState.shablon1)
async def shablon1_kiritish(message: Message, state: FSMContext):
    try:
        soni = int(message.text)
        if soni < 0:
            raise ValueError
        await state.update_data(shablon1=soni)
        await state.set_state(ProductionState.shablon2)
        await message.answer(
            "📦 Shablon 2 (faqat B: 24 ta/qolip)\n"
            "Nechta qolip quyildi?\n"
            "Agar yo'q bo'lsa: 0"
        )
    except ValueError:
        await message.answer("❌ Faqat musbat son kiriting! Misol: 5")

@router.message(ProductionState.shablon2)
async def shablon2_kiritish(message: Message, state: FSMContext):
    try:
        soni = int(message.text)
        if soni < 0:
            raise ValueError
        await state.update_data(shablon2=soni)
        await state.set_state(ProductionState.shablon3)
        await message.answer(
            "📦 Shablon 3 (aralash: 11A + 2B/qolip)\n"
            "Nechta qolip quyildi?\n"
            "Agar yo'q bo'lsa: 0"
        )
    except ValueError:
        await message.answer("❌ Faqat musbat son kiriting! Misol: 3")

@router.message(ProductionState.shablon3)
async def shablon3_kiritish(message: Message, state: FSMContext):
    try:
        soni = int(message.text)
        if soni < 0:
            raise ValueError
        data = await state.get_data()
        await state.clear()

        s1 = data["shablon1"]
        s2 = data["shablon2"]
        s3 = soni
        jami_qolip = s1 + s2 + s3

        if jami_qolip == 0:
            await message.answer("❌ Hech qolip kiritilmadi!")
            return

        # ── Minus qoldiq tekshiruvi ──
        yetishmaydi = await db.check_material_yetarli(jami_qolip)
        if yetishmaydi:
            text = (
                "⛔ Ishlab chiqarish mumkin emas!\n"
                "Materiallar yetarli emas:\n\n"
            )
            text += "\n".join(yetishmaydi)
            await message.answer(text)
            return

        # Bloklar hisobi
        A_blok = s1 * 12 + s3 * 11
        B_blok = s2 * 24 + s3 * 2

        # Bazaga yozish
        bugun = str(date.today())
        user_id = message.from_user.id
        if s1 > 0:
            await db.add_production_log(bugun, 1, s1, user_id)
        if s2 > 0:
            await db.add_production_log(bugun, 2, s2, user_id)
        if s3 > 0:
            await db.add_production_log(bugun, 3, s3, user_id)

        # Xom ashyoni kamaytirish
        formula = await db.get_qolip_formula()
        ogohlantirish = []
        sarflar = []

        for f in formula:
            nomi = f[0]
            miqdor_asosiy = f[6]
            qoldiq_asosiy = f[3]
            asl_birlik = f[7]
            material_id = f[5]

            ketgan_asosiy = miqdor_asosiy * jami_qolip
            yangi_qoldiq = max(0, qoldiq_asosiy - ketgan_asosiy)

            await db.update_material_qoldiq(material_id, yangi_qoldiq)

            ketgan_asl = db.asosiydan_birlikga(ketgan_asosiy, asl_birlik)
            qoldiq_asl = db.asosiydan_birlikga(yangi_qoldiq, asl_birlik)

            sarflar.append(
                f"   {nomi}: -{ketgan_asl:.2f} {asl_birlik} "
                f"(qoldi: {qoldiq_asl:.2f} {asl_birlik})"
            )

            settings = await db.get_settings()
            for s in settings:
                if s[3] == material_id and yangi_qoldiq <= s[1]:
                    ogohlantirish.append(
                        f"⚠️ {nomi} kam qoldi!\n"
                        f"   Qoldiq: {qoldiq_asl:.2f} {asl_birlik}\n"
                        f"   Minimum: "
                        f"{db.asosiydan_birlikga(s[1], asl_birlik):.2f} {asl_birlik}"
                    )

        # Tayyor mahsulot omboriga qo'shish
        await db.update_finished_goods("A", A_blok)
        await db.update_finished_goods("B", B_blok)

        # Audit log
        user = await db.get_user(user_id)
        await db.add_audit_log(
            user_id,
            user["ism"] if user else "Noma'lum",
            user["rol"] if user else "-",
            "Ishlab chiqarish kiritildi",
            f"Qolip: {jami_qolip} ta | A: {A_blok} ta | B: {B_blok} ta"
        )

        sarflar_text = "\n".join(sarflar)
        text = (
            f"✅ Ishlab chiqarish kiritildi!\n\n"
            f"📦 Jami qolip: {jami_qolip} ta\n"
            f"   Shablon 1: {s1} | Shablon 2: {s2} | Shablon 3: {s3}\n\n"
            f"🧱 Tayyor bloklar:\n"
            f"   A blok: +{A_blok} ta\n"
            f"   B blok: +{B_blok} ta\n\n"
            f"📉 Sarflangan:\n"
            f"{sarflar_text}"
        )
        await message.answer(text, reply_markup=production_menu())

        if ogohlantirish:
            await message.answer("\n\n".join(ogohlantirish))

    except ValueError:
        await message.answer("❌ Faqat musbat son kiriting!")

# ── Bugungi ishlab chiqarish ──
@router.message(F.text == "📋 Bugungi ishlab chiqarish")
async def bugungi_production(message: Message):
    bugun = str(date.today())
    logs = await db.get_production_by_date(bugun)

    if not logs:
        await message.answer("📋 Bugun hali ishlab chiqarish kiritilmagan.")
        return

    s1 = s2 = s3 = 0
    for log in logs:
        if log[0] == 1:
            s1 += log[1]
        elif log[0] == 2:
            s2 += log[1]
        elif log[0] == 3:
            s3 += log[1]

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
    await message.answer(text)

# ── Oxirgi yozuvni o'chirish ──
@router.message(F.text == "🗑️ Oxirgi yozuvni o'chirish")
async def oxirgi_ochirish(message: Message):
    user = await db.get_user(message.from_user.id)
    natija = await db.delete_last_production()
    if natija:
        await db.add_audit_log(
            message.from_user.id,
            user["ism"] if user else "Noma'lum",
            user["rol"] if user else "-",
            "Ishlab chiqarish o'chirildi",
            "Oxirgi yozuv o'chirildi"
        )
        await message.answer(
            "✅ Oxirgi yozuv o'chirildi!",
            reply_markup=production_menu()
        )
    else:
        await message.answer(
            "❌ O'chiriladigan yozuv yo'q!",
            reply_markup=production_menu()
    )
