from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import database as db

router = Router()

# Qo'llab-quvvatlanadigan birliklar
BARCHA_BIRLIKLAR = [
    "tonna", "ton", "t", "kg", "g", "gramm", "gr", "mg",
    "quintal", "sentner", "meshok", "qop",
    "litr", "l", "ml", "millilitr", "m3", "kubometr", "kub", "dl", "cl"
]

class WarehouseState(StatesGroup):
    material_id = State()
    miqdor = State()
    birlik = State()

def warehouse_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📥 Xom ashyo kirim")],
            [KeyboardButton(text="🏪 Joriy qoldiqlar")],
            [KeyboardButton(text="🏠 Asosiy menyu")],
        ],
        resize_keyboard=True
    )

@router.message(F.text == "🏪 Ombor")
async def ombor(message: Message):
    await message.answer(
        "🏪 Ombor bo'limi:",
        reply_markup=warehouse_menu()
    )

@router.message(F.text == "🏪 Joriy qoldiqlar")
async def joriy_qoldiqlar(message: Message):
    try:
        materials = await db.get_materials()
        if not materials:
            await message.answer(
                "❌ Hali material kiritilmagan!",
                reply_markup=warehouse_menu()
            )
            return

        all_settings = await db.get_settings()
        # s[3] = material_id, s[1] = min_chegara (asosiy birlikda)
        min_map = {s[3]: s[1] for s in all_settings}

        text = "🏪 Joriy qoldiqlar:\n\n"
        for m in materials:
            material_id = m[0]
            nomi = m[1]
            qoldiq_asosiy = m[2]
            asosiy_birlik = m[3]
            asl_birlik = m[4]

            qoldiq_asl = db.asosiydan_birlikga(qoldiq_asosiy, asl_birlik)
            min_ch = min_map.get(material_id)

            if min_ch and qoldiq_asosiy <= min_ch:
                status = "⚠️"
            else:
                status = "✅"

            text += f"{status} {nomi}: {qoldiq_asl:.2f} {asl_birlik}\n"

            if min_ch and min_ch > 0:
                min_asl = db.asosiydan_birlikga(min_ch, asl_birlik)
                text += f"   Min chegara: {min_asl:.2f} {asl_birlik}\n"

        await message.answer(text, reply_markup=warehouse_menu())
    except Exception as e:
        await message.answer(
            f"❌ Xatolik: {str(e)}",
            reply_markup=warehouse_menu()
        )

@router.message(F.text == "📥 Xom ashyo kirim")
async def xom_ashyo_kirim(message: Message, state: FSMContext):
    try:
        await state.clear()
        materials = await db.get_materials()
        if not materials:
            await message.answer(
                "❌ Avval material qo'shing!\n"
                "⚙️ Sozlamalar → ➕ Material qo'shish",
                reply_markup=warehouse_menu()
            )
            return

        text = "📦 Qaysi material keldi?\nRaqamini kiriting:\n\n"
        for m in materials:
            qoldiq_asl = db.asosiydan_birlikga(m[2], m[4])
            text += f"{m[0]}. {m[1]} — {qoldiq_asl:.2f} {m[4]}\n"

        await state.update_data(
            materials=[(m[0], m[1], m[2], m[3], m[4]) for m in materials]
        )
        await state.set_state(WarehouseState.material_id)
        await message.answer(text)
    except Exception as e:
        await message.answer(
            f"❌ Xatolik: {str(e)}",
            reply_markup=warehouse_menu()
        )

@router.message(WarehouseState.material_id)
async def kirim_material(message: Message, state: FSMContext):
    try:
        material_id = int(message.text.strip())
        data = await state.get_data()
        materials = data["materials"]
        material = next((m for m in materials if m[0] == material_id), None)

        if not material:
            await message.answer(
                "❌ Bunday raqam yo'q!\n"
                "Qaytadan kiriting:"
            )
            return

        await state.update_data(
            material_id=material_id,
            material_nomi=material[1],
            asl_birlik=material[4],
            joriy_qoldiq_asosiy=material[2]
        )
        await state.set_state(WarehouseState.miqdor)
        await message.answer(
            f"📥 {material[1]} dan qancha keldi?\n"
            f"Misol: 10"
        )
    except ValueError:
        await message.answer("❌ Faqat raqam kiriting! Misol: 1")
    except Exception as e:
        await state.clear()
        await message.answer(
            f"❌ Xatolik: {str(e)}",
            reply_markup=warehouse_menu()
        )

@router.message(WarehouseState.miqdor)
async def kirim_miqdor(message: Message, state: FSMContext):
    try:
        miqdor = float(message.text.replace(",", "."))
        if miqdor <= 0:
            raise ValueError
        await state.update_data(miqdor=miqdor)
        await state.set_state(WarehouseState.birlik)
        data = await state.get_data()
        asl_birlik = data["asl_birlik"]

        # Qo'llab-quvvatlanadigan birliklarni ko'rsatamiz
        og_birliklar = "tonna, kg, g, gramm, mg, meshok"
        hajm_birliklar = "litr, ml, m3, kubometr"

        await message.answer(
            f"Birligini kiriting:\n"
            f"(Ombordagi birlik: {asl_birlik})\n\n"
            f"Og'irlik: {og_birliklar}\n"
            f"Hajm: {hajm_birliklar}"
        )
    except ValueError:
        await message.answer("❌ Faqat musbat son kiriting! Misol: 10")
    except Exception as e:
        await state.clear()
        await message.answer(
            f"❌ Xatolik: {str(e)}",
            reply_markup=warehouse_menu()
        )

@router.message(WarehouseState.birlik)
async def kirim_birlik(message: Message, state: FSMContext):
    try:
        birlik = message.text.strip().lower()

        # Birlik to'g'riligini tekshirish
        if birlik not in BARCHA_BIRLIKLAR:
            await message.answer(
                f"❌ '{birlik}' birlik tanilmadi!\n\n"
                f"Og'irlik uchun: tonna, kg, g, gramm, mg, meshok\n"
                f"Hajm uchun: litr, ml, m3, kubometr\n\n"
                f"Qaytadan kiriting:"
            )
            return

        data = await state.get_data()
        miqdor = data["miqdor"]
        asl_birlik = data["asl_birlik"]
        joriy_qoldiq_asosiy = data["joriy_qoldiq_asosiy"]

        # Hozirgi qoldiqni bazadan yangilab olamiz (stale data oldini olish)
        materials = await db.get_materials()
        material = next(
            (m for m in materials if m[0] == data["material_id"]), None
        )
        if material:
            joriy_qoldiq_asosiy = material[2]

        # Kirimni asosiy birlikka o'tkazamiz
        kirim_asosiy, kirim_birlik_asosiy = db.birlikni_asosiyga(miqdor, birlik)
        yangi_qoldiq_asosiy = joriy_qoldiq_asosiy + kirim_asosiy

        await db.update_material_qoldiq(data["material_id"], yangi_qoldiq_asosiy)

        # Audit log
        user = await db.get_user(message.from_user.id)
        await db.add_audit_log(
            message.from_user.id,
            user["ism"] if user else str(message.from_user.id),
            user["rol"] if user else "-",
            "Xom ashyo kirim",
            f"{data['material_nomi']}: +{miqdor} {birlik}"
        )

        await state.clear()

        yangi_qoldiq_asl = db.asosiydan_birlikga(yangi_qoldiq_asosiy, asl_birlik)
        await message.answer(
            f"✅ Kirim kiritildi!\n\n"
            f"📦 {data['material_nomi']}\n"
            f"   Kirim: +{miqdor} {birlik}\n"
            f"   Yangi qoldiq: {yangi_qoldiq_asl:.2f} {asl_birlik}",
            reply_markup=warehouse_menu()
        )
    except Exception as e:
        await state.clear()
        await message.answer(
            f"❌ Xatolik: {str(e)}",
            reply_markup=warehouse_menu()
        )
