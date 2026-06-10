from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from datetime import date, timedelta
import database as db

router = Router()

def reports_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Kunlik hisobot")],
            [KeyboardButton(text="📊 Haftalik hisobot")],
            [KeyboardButton(text="📊 Oylik hisobot")],
            [KeyboardButton(text="🏠 Asosiy menyu")],
        ],
        resize_keyboard=True
    )

def hisobla_production(logs):
    s1 = s2 = s3 = 0
    for log in logs:
        if log[1] == 1:
            s1 += log[2]
        elif log[1] == 2:
            s2 += log[2]
        elif log[1] == 3:
            s3 += log[2]
    jami_qolip = s1 + s2 + s3
    A_blok = s1 * 12 + s3 * 11
    B_blok = s2 * 24 + s3 * 2
    return jami_qolip, A_blok, B_blok

def hisobla_sales(logs):
    A = sum(log[2] for log in logs if log[1] == "A")
    B = sum(log[2] for log in logs if log[1] == "B")
    return A, B

@router.message(F.text == "📊 Hisobot")
async def hisobot(message: Message):
    await message.answer(
        "📊 Hisobotlar:",
        reply_markup=reports_menu()
    )

@router.message(F.text == "📊 Kunlik hisobot")
async def kunlik_hisobot(message: Message):
    bugun = str(date.today())
    prod_logs = await db.get_production_range(bugun, bugun)
    sales_logs = await db.get_sales_range(bugun, bugun)

    jami_qolip, A_blok, B_blok = hisobla_production(prod_logs)
    A_sotuv, B_sotuv = hisobla_sales(sales_logs)

    materials = await db.get_materials()
    ombor_text = ""
    for m in materials:
        ombor_text += f"   {m[1]}: {m[2]:.2f} {m[3]}\n"

    text = (
        f"📊 Kunlik hisobot — {bugun}\n"
        f"━━━━━━━━━━━━━━━━\n\n"
        f"🏭 Ishlab chiqarish:\n"
        f"   Jami qolip: {jami_qolip} ta\n"
        f"   A blok: {A_blok} ta\n"
        f"   B blok: {B_blok} ta\n\n"
        f"💰 Sotuv:\n"
        f"   A blok: {A_sotuv} ta\n"
        f"   B blok: {B_sotuv} ta\n"
        f"   Jami: {A_sotuv + B_sotuv} ta\n\n"
        f"🏪 Ombor qoldig'i:\n"
        f"{ombor_text}"
    )
    await message.answer(text, reply_markup=reports_menu())

@router.message(F.text == "📊 Haftalik hisobot")
async def haftalik_hisobot(message: Message):
    bugun = date.today()
    boshliq = str(bugun - timedelta(days=7))
    oxiri = str(bugun)

    prod_logs = await db.get_production_range(boshliq, oxiri)
    sales_logs = await db.get_sales_range(boshliq, oxiri)

    jami_qolip, A_blok, B_blok = hisobla_production(prod_logs)
    A_sotuv, B_sotuv = hisobla_sales(sales_logs)

    text = (
        f"📊 Haftalik hisobot\n"
        f"📅 {boshliq} — {oxiri}\n"
        f"━━━━━━━━━━━━━━━━\n\n"
        f"🏭 Ishlab chiqarish:\n"
        f"   Jami qolip: {jami_qolip} ta\n"
        f"   A blok: {A_blok} ta\n"
        f"   B blok: {B_blok} ta\n\n"
        f"💰 Sotuv:\n"
        f"   A blok: {A_sotuv} ta\n"
        f"   B blok: {B_sotuv} ta\n"
        f"   Jami: {A_sotuv + B_sotuv} ta\n"
    )
    await message.answer(text, reply_markup=reports_menu())

@router.message(F.text == "📊 Oylik hisobot")
async def oylik_hisobot(message: Message):
    bugun = date.today()
    boshliq = str(bugun.replace(day=1))
    oxiri = str(bugun)

    prod_logs = await db.get_production_range(boshliq, oxiri)
    sales_logs = await db.get_sales_range(boshliq, oxiri)

    jami_qolip, A_blok, B_blok = hisobla_production(prod_logs)
    A_sotuv, B_sotuv = hisobla_sales(sales_logs)

    text = (
        f"📊 Oylik hisobot\n"
        f"📅 {boshliq} — {oxiri}\n"
        f"━━━━━━━━━━━━━━━━\n\n"
        f"🏭 Ishlab chiqarish:\n"
        f"   Jami qolip: {jami_qolip} ta\n"
        f"   A blok: {A_blok} ta\n"
        f"   B blok: {B_blok} ta\n\n"
        f"💰 Sotuv:\n"
        f"   A blok: {A_sotuv} ta\n"
        f"   B blok: {B_sotuv} ta\n"
        f"   Jami: {A_sotuv + B_sotuv} ta\n"
    )
    await message.answer(text, reply_markup=reports_menu())
