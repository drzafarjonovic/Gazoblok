from aiogram import Router
from aiogram.types import Message, BufferedInputFile
from datetime import timedelta, timezone
import io
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
import database as db
from translation import Tkey, say, say_error, build_keyboard, t, log_exc, GENERIC_ERROR

# GMT+5 timezone
TOSHKENT_TZ = timezone(timedelta(hours=5))

router = Router()


async def reports_menu(user_id):
    return await build_keyboard(user_id, [
        ["📊 Kunlik hisobot"],
        ["📊 Haftalik hisobot"],
        ["📊 Oylik hisobot"],
        ["📊 Tafsilotli hisobot"],
        ["📥 Excel hisobot"],
        ["🏠 Asosiy menyu"],
    ])


def hisobla_production(logs):
    s1 = s2 = s3 = 0
    for log in logs:
        if log[1] == 1: s1 += log[2]
        elif log[1] == 2: s2 += log[2]
        elif log[1] == 3: s3 += log[2]
    jami_qolip = s1 + s2 + s3
    A_blok = s1 * 12 + s3 * 11
    B_blok = s2 * 24 + s3 * 2
    return jami_qolip, A_blok, B_blok, s1, s2, s3


def hisobla_sales(logs):
    A = sum(log[2] for log in logs if log[1] == "A")
    B = sum(log[2] for log in logs if log[1] == "B")
    return A, B


async def ombor_holati():
    try:
        materials = await db.get_materials()
        if not materials:
            return "   Ma'lumot yo'q\n"
        text = ""
        for m in materials:
            qoldiq_asl = db.asosiydan_birlikga(m[2], m[4])
            text += f"   {m[1]}: {qoldiq_asl:.2f} {m[4]}\n"
        return text
    except Exception:
        return "   Xatolik\n"


async def tayyor_holati():
    try:
        goods = await db.get_finished_goods()
        if not goods:
            return "   Ma'lumot yo'q\n"
        text = ""
        jami = 0
        for g in goods:
            text += f"   {g[0]} blok: {g[1]} ta\n"
            jami += g[1]
        text += f"   Jami: {jami} ta\n"
        return text
    except Exception:
        return "   Xatolik\n"


async def hisobot_matni(boshliq, oxiri, sarlavha):
    try:
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
            f"   Sh1: {s1} | Sh2: {s2} | Sh3: {s3}\n"
            f"   A blok: {A_blok} ta\n"
            f"   B blok: {B_blok} ta\n\n"
            f"💰 Sotuv:\n"
            f"   A blok: {A_sotuv} ta\n"
            f"   B blok: {B_sotuv} ta\n"
            f"   Jami: {A_sotuv + B_sotuv} ta\n\n"
            f"🏬 Tayyor mahsulot:\n{tayyor}\n"
            f"🏪 Xom ashyo qoldig'i:\n{ombor}"
        )
    except Exception as e:
        log_exc("hisobot_matni", e)
        return GENERIC_ERROR


@router.message(Tkey("📊 Hisobot"))
async def hisobot(message: Message):
    await say(message, "📊 Hisobotlar:", reply_markup=await reports_menu(message.from_user.id))


@router.message(Tkey("📊 Kunlik hisobot"))
async def kunlik_hisobot(message: Message):
    bugun = db.bugungi_sana()
    text = await hisobot_matni(bugun, bugun, "📊 Kunlik hisobot")
    await say(message, text, reply_markup=await reports_menu(message.from_user.id))


@router.message(Tkey("📊 Haftalik hisobot"))
async def haftalik_hisobot(message: Message):
    bugun = db.bugungi_sana()
    boshliq = bugun - timedelta(days=7)
    text = await hisobot_matni(boshliq, bugun, "📊 Haftalik hisobot")
    await say(message, text, reply_markup=await reports_menu(message.from_user.id))


@router.message(Tkey("📊 Oylik hisobot"))
async def oylik_hisobot(message: Message):
    bugun = db.bugungi_sana()
    boshliq = bugun.replace(day=1)
    text = await hisobot_matni(boshliq, bugun, "📊 Oylik hisobot")
    await say(message, text, reply_markup=await reports_menu(message.from_user.id))


@router.message(Tkey("📊 Tafsilotli hisobot"))
async def tafsilotli_hisobot(message: Message):
    try:
        bugun = db.bugungi_sana()
        boshliq = bugun.replace(day=1)

        # Ishlab chiqarish tafsiloti
        prod_detail = await db.get_production_detail_range(boshliq, bugun)
        # Sotuv tafsiloti
        sales_detail = await db.get_sales_detail_range(boshliq, bugun)
        # Xom ashyo sarfi
        chiqim = await db.get_material_chiqim_range(boshliq, bugun)

        text = f"📊 Tafsilotli hisobot\n📅 {boshliq} — {bugun}\n━━━━━━━━━━━━━━━━\n\n"

        # Ishlab chiqarish
        text += "🏭 ISHLAB CHIQARISH:\n"
        if prod_detail:
            for p in prod_detail[:10]:
                vaqt = p["vaqt"]
                # PostgreSQL vaqtini GMT+5 ga o'girish
                if hasattr(vaqt, "strftime"):
                    if vaqt.tzinfo is None:
                        vaqt = vaqt.replace(tzinfo=timezone.utc).astimezone(TOSHKENT_TZ)
                    vaqt_str = vaqt.strftime("%d.%m %H:%M")
                else:
                    vaqt_str = str(vaqt)[:16]
                shablon_nomi = {1: "A(12ta)", 2: "B(24ta)", 3: "11A+2B"}.get(p["shablon"], "?")
                text += (
                    f"   {vaqt_str} | {p.get('user_ism') or 'Noma lum'}\n"
                    f"   Shablon {p['shablon']}({shablon_nomi}): {p['qolip_soni']} qolip\n"
                )
        else:
            text += "   Ma'lumot yo'q\n"

        # Sotuv
        text += "\n💰 SOTUV:\n"
        if sales_detail:
            for s in sales_detail[:10]:
                vaqt = s["vaqt"]
                if hasattr(vaqt, "strftime"):
                    if vaqt.tzinfo is None:
                        vaqt = vaqt.replace(tzinfo=timezone.utc).astimezone(TOSHKENT_TZ)
                    vaqt_str = vaqt.strftime("%d.%m %H:%M")
                else:
                    vaqt_str = str(vaqt)[:16]
                text += (
                    f"   {vaqt_str} | {s.get('user_ism') or 'Noma lum'}\n"
                    f"   {s['block_type']} blok: {s['miqdor']} ta\n"
                )
        else:
            text += "   Ma'lumot yo'q\n"

        # Xom ashyo sarfi
        text += "\n📉 XOM ASHYO SARFI:\n"
        if chiqim:
            sarfi_dict = {}
            for ch in chiqim:
                nomi = ch["material_nomi"]
                if nomi not in sarfi_dict:
                    sarfi_dict[nomi] = {"jami": 0, "birlik": ch["birlik"]}
                sarfi_dict[nomi]["jami"] += float(ch["jami"])
            for nomi, info in sarfi_dict.items():
                asl = db.asosiydan_birlikga(info["jami"], info["birlik"])
                text += f"   {nomi}: {asl:.2f} {info['birlik']}\n"
        else:
            text += "   Ma'lumot yo'q\n"

        if len(text) > 4000:
            text = text[:4000] + "\n..."
        await say(message, text, reply_markup=await reports_menu(message.from_user.id))
    except Exception as e:
        await say_error(message, e)


@router.message(Tkey("📥 Excel hisobot"))
async def excel_hisobot(message: Message):
    try:
        bugun = db.bugungi_sana()
        boshliq = bugun.replace(day=1)

        prod_logs = await db.get_production_range(boshliq, bugun)
        sales_logs = await db.get_sales_range(boshliq, bugun)
        materials = await db.get_materials()
        goods = await db.get_finished_goods()
        formula = await db.get_qolip_formula()
        audit_logs = await db.get_audit_log(200)
        prod_detail = await db.get_production_detail_range(boshliq, bugun)
        sales_detail = await db.get_sales_detail_range(boshliq, bugun)
        chiqim_logs = await db.get_material_chiqim_range(boshliq, bugun)

        wb = openpyxl.Workbook()
        sarlavha_font = Font(bold=True, size=11, color="FFFFFF")
        sarlavha_fill = PatternFill("solid", fgColor="2E75B6")
        markaz = Alignment(horizontal="center", vertical="center")

        def sarlavha_qo(ws, qator, ustunlar):
            for col, text in enumerate(ustunlar, 1):
                cell = ws.cell(row=qator, column=col, value=text)
                cell.font = sarlavha_font
                cell.fill = sarlavha_fill
                cell.alignment = markaz

        # 1. Ishlab chiqarish xulosasi
        ws1 = wb.active
        ws1.title = "Ishlab chiqarish"
        sarlavha_qo(ws1, 1, ["Sana", "Shablon 1", "Shablon 2", "Shablon 3", "Jami qolip", "A blok", "B blok"])
        ws1.column_dimensions["A"].width = 14
        sanalar = {}
        for log in prod_logs:
            sana = log[0]
            if sana not in sanalar:
                sanalar[sana] = [0, 0, 0]
            idx = log[1] - 1
            if 0 <= idx <= 2:
                sanalar[sana][idx] += log[2]
        for sana, counts in sorted(sanalar.items()):
            s1, s2, s3 = counts
            A = s1 * 12 + s3 * 11
            B = s2 * 24 + s3 * 2
            ws1.append([sana, s1, s2, s3, s1 + s2 + s3, A, B])

        # 2. Ishlab chiqarish tafsiloti (kim kiritdi)
        ws2 = wb.create_sheet("Ishlab chiqarish (tafsilot)")
        sarlavha_qo(ws2, 1, ["Vaqt", "Foydalanuvchi", "Rol", "Shablon", "Qolip soni", "A blok", "B blok"])
        ws2.column_dimensions["A"].width = 18
        ws2.column_dimensions["B"].width = 16
        for p in prod_detail:
            vaqt = p["vaqt"]
            if hasattr(vaqt, "strftime"):
                if vaqt.tzinfo is None:
                    vaqt = vaqt.replace(tzinfo=timezone.utc).astimezone(TOSHKENT_TZ)
                vaqt_str = vaqt.strftime("%d.%m.%Y %H:%M")
            else:
                vaqt_str = str(vaqt)[:16]
            shablon = p["shablon"]
            qolip = p["qolip_soni"]
            A = qolip * 12 if shablon == 1 else (qolip * 11 if shablon == 3 else 0)
            B = qolip * 24 if shablon == 2 else (qolip * 2 if shablon == 3 else 0)
            ws2.append([vaqt_str, p["user_ism"] or "Noma'lum", p["user_rol"] or "-", shablon, qolip, A, B])

        # 3. Sotuv xulosasi
        ws3 = wb.create_sheet("Sotuv")
        sarlavha_qo(ws3, 1, ["Sana", "A blok", "B blok", "Jami"])
        ws3.column_dimensions["A"].width = 14
        sotuv_sanalar = {}
        for log in sales_logs:
            sana = log[0]
            if sana not in sotuv_sanalar:
                sotuv_sanalar[sana] = {"A": 0, "B": 0}
            sotuv_sanalar[sana][log[1]] += log[2]
        for sana, counts in sorted(sotuv_sanalar.items()):
            A = counts.get("A", 0)
            B = counts.get("B", 0)
            ws3.append([sana, A, B, A + B])

        # 4. Sotuv tafsiloti (kim sotdi)
        ws4 = wb.create_sheet("Sotuv (tafsilot)")
        sarlavha_qo(ws4, 1, ["Vaqt", "Foydalanuvchi", "Rol", "Blok turi", "Miqdor"])
        ws4.column_dimensions["A"].width = 18
        ws4.column_dimensions["B"].width = 16
        for s in sales_detail:
            vaqt = s["vaqt"]
            if hasattr(vaqt, "strftime"):
                if vaqt.tzinfo is None:
                    vaqt = vaqt.replace(tzinfo=timezone.utc).astimezone(TOSHKENT_TZ)
                vaqt_str = vaqt.strftime("%d.%m.%Y %H:%M")
            else:
                vaqt_str = str(vaqt)[:16]
            ws4.append([vaqt_str, s["user_ism"] or "Noma'lum", s["user_rol"] or "-", s["block_type"], s["miqdor"]])

        # 5. Xom ashyo sarfi
        ws5 = wb.create_sheet("Xom ashyo sarfi")
        sarlavha_qo(ws5, 1, ["Sana", "Material", "Ketgan miqdor", "Birlik"])
        ws5.column_dimensions["A"].width = 14
        ws5.column_dimensions["B"].width = 20
        for ch in chiqim_logs:
            asl = db.asosiydan_birlikga(float(ch["jami"]), ch["birlik"])
            ws5.append([ch["sana"], ch["material_nomi"], round(asl, 2), ch["birlik"]])

        # 6. Ombor qoldiqlari
        ws6 = wb.create_sheet("Ombor qoldiqlari")
        sarlavha_qo(ws6, 1, ["Material", "Qoldiq", "Birlik"])
        ws6.column_dimensions["A"].width = 20
        for m in materials:
            qoldiq_asl = db.asosiydan_birlikga(m[2], m[4])
            ws6.append([m[1], round(qoldiq_asl, 2), m[4]])
        ws6.append([])
        ws6.append(["── Tayyor mahsulot ──", "", ""])
        for g in goods:
            ws6.append([f"{g[0]} blok", g[1], "ta"])

        # 7. Audit log
        ws7 = wb.create_sheet("Audit log")
        sarlavha_qo(ws7, 1, ["Vaqt", "Foydalanuvchi", "Rol", "Amal", "Tafsilot"])
        ws7.column_dimensions["A"].width = 18
        ws7.column_dimensions["B"].width = 16
        ws7.column_dimensions["D"].width = 25
        ws7.column_dimensions["E"].width = 40
        for log in audit_logs:
            vaqt = log["vaqt"]
            if hasattr(vaqt, "strftime"):
                if vaqt.tzinfo is None:
                    vaqt = vaqt.replace(tzinfo=timezone.utc).astimezone(TOSHKENT_TZ)
                vaqt_str = vaqt.strftime("%d.%m.%Y %H:%M")
            else:
                vaqt_str = str(vaqt)[:16]
            ws7.append([vaqt_str, log["ism"] or "", log["rol"] or "", log["amal"] or "", log["tafsilot"] or ""])

        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)

        fayl_nomi = f"gazobot_{boshliq}_{bugun}.xlsx"
        caption = await t(
            f"📥 Excel hisobot\n📅 {boshliq} — {bugun}\n"
            f"7 ta varaq: Ishlab chiqarish, Tafsilot, "
            f"Sotuv, Sotuv tafsilot, Xom ashyo, Ombor, Audit",
            message.from_user.id
        )
        await message.answer_document(
            BufferedInputFile(buffer.read(), filename=fayl_nomi),
            caption=caption
        )
    except Exception as e:
        await say_error(message, e)


async def avtomatik_hisobot(bot, chat_id):
    try:
        bugun = db.bugungi_sana()
        text = await hisobot_matni(bugun, bugun, "🔔 Avtomatik kunlik hisobot")
        # Admin tilida yuborish (chat_id = admin user_id)
        text = await t(text, chat_id)
        await bot.send_message(chat_id, text)
    except Exception as e:
        log_exc("avtomatik_hisobot", e)
