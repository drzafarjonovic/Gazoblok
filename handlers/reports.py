from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.types import BufferedInputFile
from datetime import date, timedelta
import io
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
import database as db

router = Router()

def reports_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Kunlik hisobot")],
            [KeyboardButton(text="📊 Haftalik hisobot")],
            [KeyboardButton(text="📊 Oylik hisobot")],
            [KeyboardButton(text="📥 Excel hisobot")],
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
    return jami_qolip, A_blok, B_blok, s1, s2, s3

def hisobla_sales(logs):
    A = sum(log[2] for log in logs if log[1] == "A")
    B = sum(log[2] for log in logs if log[1] == "B")
    return A, B

async def ombor_holati():
    materials = await db.get_materials()
    text = ""
    for m in materials:
        qoldiq_asl = db.asosiydan_birlikga(m[2], m[4])
        text += f"   {m[1]}: {qoldiq_asl:.2f} {m[4]}\n"
    return text if text else "   Ma'lumot yo'q\n"

async def tayyor_holati():
    goods = await db.get_finished_goods()
    text = ""
    jami = 0
    for g in goods:
        text += f"   {g[0]} blok: {g[1]} ta\n"
        jami += g[1]
    text += f"   Jami: {jami} ta\n"
    return text

async def hisobot_matni(boshliq, oxiri, sarlavha):
    prod_logs = await db.get_production_range(boshliq, oxiri)
    sales_logs = await db.get_sales_range(boshliq, oxiri)

    jami_qolip, A_blok, B_blok, s1, s2, s3 = hisobla_production(prod_logs)
    A_sotuv, B_sotuv = hisobla_sales(sales_logs)
    ombor = await ombor_holati()
    tayyor = await tayyor_holati()

    return (
        f"{sarlavha}\n"
        f"📅 {boshliq} — {oxiri}\n"
        f"━━━━━━━━━━━━━━━━\n\n"
        f"🏭 Ishlab chiqarish:\n"
        f"   Jami qolip: {jami_qolip} ta\n"
        f"   Shablon 1: {s1} | 2: {s2} | 3: {s3}\n"
        f"   A blok: {A_blok} ta\n"
        f"   B blok: {B_blok} ta\n\n"
        f"💰 Sotuv:\n"
        f"   A blok: {A_sotuv} ta\n"
        f"   B blok: {B_sotuv} ta\n"
        f"   Jami: {A_sotuv + B_sotuv} ta\n\n"
        f"🏬 Tayyor mahsulot ombori:\n"
        f"{tayyor}\n"
        f"🏪 Xom ashyo qoldig'i:\n"
        f"{ombor}"
    )

@router.message(F.text == "📊 Hisobot")
async def hisobot(message: Message):
    await message.answer(
        "📊 Hisobotlar:",
        reply_markup=reports_menu()
    )

@router.message(F.text == "📊 Kunlik hisobot")
async def kunlik_hisobot(message: Message):
    bugun = str(date.today())
    text = await hisobot_matni(bugun, bugun, "📊 Kunlik hisobot")
    await message.answer(text, reply_markup=reports_menu())

@router.message(F.text == "📊 Haftalik hisobot")
async def haftalik_hisobot(message: Message):
    bugun = date.today()
    boshliq = str(bugun - timedelta(days=7))
    oxiri = str(bugun)
    text = await hisobot_matni(boshliq, oxiri, "📊 Haftalik hisobot")
    await message.answer(text, reply_markup=reports_menu())

@router.message(F.text == "📊 Oylik hisobot")
async def oylik_hisobot(message: Message):
    bugun = date.today()
    boshliq = str(bugun.replace(day=1))
    oxiri = str(bugun)
    text = await hisobot_matni(boshliq, oxiri, "📊 Oylik hisobot")
    await message.answer(text, reply_markup=reports_menu())

# ── Excel hisobot ──
@router.message(F.text == "📥 Excel hisobot")
async def excel_hisobot(message: Message):
    bugun = date.today()
    boshliq = str(bugun.replace(day=1))
    oxiri = str(bugun)

    prod_logs = await db.get_production_range(boshliq, oxiri)
    sales_logs = await db.get_sales_range(boshliq, oxiri)
    materials = await db.get_materials()
    goods = await db.get_finished_goods()

    wb = openpyxl.Workbook()

    # Sarlavha uslubi
    sarlavha_font = Font(bold=True, size=12, color="FFFFFF")
    sarlavha_fill = PatternFill("solid", fgColor="2E75B6")
    markaz = Alignment(horizontal="center")

    def sarlavha_qo(ws, qator, ustunlar):
        for col, text in enumerate(ustunlar, 1):
            cell = ws.cell(row=qator, column=col, value=text)
            cell.font = sarlavha_font
            cell.fill = sarlavha_fill
            cell.alignment = markaz

    # ── 1. Ishlab chiqarish varag'i ──
    ws1 = wb.active
    ws1.title = "Ishlab chiqarish"
    sarlavha_qo(ws1, 1, ["Sana", "Shablon 1", "Shablon 2", "Shablon 3",
                          "Jami qolip", "A blok", "B blok"])
    ws1.column_dimensions["A"].width = 14

    sanalar = {}
    for log in prod_logs:
        sana = log[0]
        if sana not in sanalar:
            sanalar[sana] = [0, 0, 0]
        sanalar[sana][log[1] - 1] += log[2]

    for i, (sana, counts) in enumerate(sorted(sanalar.items()), 2):
        s1, s2, s3 = counts
        A = s1 * 12 + s3 * 11
        B = s2 * 24 + s3 * 2
        ws1.append([sana, s1, s2, s3, s1+s2+s3, A, B])

    # ── 2. Sotuv varag'i ──
    ws2 = wb.create_sheet("Sotuv")
    sarlavha_qo(ws2, 1, ["Sana", "A blok", "B blok", "Jami"])
    ws2.column_dimensions["A"].width = 14

    sotuv_sanalar = {}
    for log in sales_logs:
        sana = log[0]
        if sana not in sotuv_sanalar:
            sotuv_sanalar[sana] = {"A": 0, "B": 0}
        sotuv_sanalar[sana][log[1]] += log[2]

    for sana, counts in sorted(sotuv_sanalar.items()):
        A = counts.get("A", 0)
        B = counts.get("B", 0)
        ws2.append([sana, A, B, A + B])

    # ── 3. Ombor qoldiqlari varag'i ──
    ws3 = wb.create_sheet("Ombor qoldiqlari")
    sarlavha_qo(ws3, 1, ["Material", "Qoldiq", "Birlik"])
    ws3.column_dimensions["A"].width = 20
    ws3.column_dimensions["B"].width = 14

    for m in materials:
        qoldiq_asl = db.asosiydan_birlikga(m[2], m[4])
        ws3.append([m[1], round(qoldiq_asl, 2), m[4]])

    ws3.append([])
    ws3.append(["Tayyor mahsulot", "", ""])
    for g in goods:
        ws3.append([f"{g[0]} blok", g[1], "ta"])

    # ── 4. Xom ashyo sarfi varag'i ──
    ws4 = wb.create_sheet("Xom ashyo sarfi")
    sarlavha_qo(ws4, 1, ["Material", "Sarflangan", "Birlik"])
    ws4.column_dimensions["A"].width = 20

    formula = await db.get_qolip_formula()
    jami_qolip = sum(
        log[2] for log in prod_logs
    )

    for f in formula:
        nomi = f[0]
        miqdor_asosiy = f[6]
        asl_birlik = f[7]
        ketgan_asosiy = miqdor_asosiy * jami_qolip
        ketgan_asl = db.asosiydan_birlikga(ketgan_asosiy, asl_birlik)
        ws4.append([nomi, round(ketgan_asl, 2), asl_birlik])

    # Faylni xotiraga yozamiz
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    fayl_nomi = f"gazobot_{boshliq}_{oxiri}.xlsx"
    await message.answer_document(
        BufferedInputFile(buffer.read(), filename=fayl_nomi),
        caption=f"📥 Excel hisobot\n📅 {boshliq} — {oxiri}"
    )

# ── Avtomatik kunlik hisobot (tashqaridan chaqiriladi) ──
async def avtomatik_hisobot(bot, chat_id):
    bugun = str(date.today())
    text = await hisobot_matni(bugun, bugun, "🔔 Avtomatik kunlik hisobot")
    await bot.send_message(chat_id, text)
