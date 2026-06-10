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

        A_blok = s1 * 12 + s3 * 11
        B_blok = s2 * 24 + s3 * 2

        bugun = str(date.today())
        if s1 > 0:
            await db.add_production_log(bugun, 1, s1)
        if s2 > 0:
            await db.add_production_log(bugun, 2, s2)
        if s3 > 0:
            await db.add_production_log(bugun, 3, s3)

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
                        f"   Minimum: {db.asosiydan_birlikga(s[1], asl_birlik):.2f} {asl_birlik}"
                    )

        sarflar_text = "\n".join(sarflar)
        text = (
            f"✅ Ishlab chiqarish kiritildi!\n\n"
            f"📦 Jami qolip: {jami_qolip} ta\n"
            f"   Shablon 1: {s1} | Shablon 2: {s2} | Shablon 3: {s3}\n\n"
            f"🧱 Tayyor bloklar:\n"
            f"   A blok: {A_blok} ta\n"
            f"   B blok: {B_blok} ta\n\n"
            f"📉 Sarflangan:\n"
            f"{sarflar_text}"
        )
        await message.answer(text, reply_markup=production_menu())

        if ogohlantirish:
            await message.answer("\n\n".join(ogohlantirish))

    except ValueError:
        await message.answer("❌ Faqat musbat son kiriting! Misol: 2")

@router.message(F.text == "🗑️ Oxirgi yozuvni o'chirish")
async def oxirgi_production_ochirish(message: Message):
    natija = await db.delete_last_production()
    if natija:
        await message.answer(
            "✅ Oxirgi ishlab chiqarish yozuvi o'chirildi!",
            reply_markup=production_menu()
        )
    else:
        await message.answer(
            "❌ O'chiriladigan yozuv yo'q!",
            reply_markup=production_menu()
        )

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
