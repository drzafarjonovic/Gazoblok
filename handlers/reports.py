from aiogram import Router
from aiogram.types import (
    Message, BufferedInputFile,
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import date, timedelta, timezone, datetime
import io
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
import database as db
import valyuta as val
from translation import (
    Tkey, say, say_error, build_keyboard, t, log_exc, GENERIC_ERROR,
    foydalanuvchi_tili, tarjima_qil, register_ui,
)

# GMT+5 timezone
TOSHKENT_TZ = timezone(timedelta(hours=5))

router = Router()

# Davr tugmalari (kanonik o'zbekcha) — pre-warm uchun ro'yxatga olamiz
DAVRLAR = [
    ("bugun", "Bugun"),
    ("kecha", "Kecha"),
    ("hafta", "Shu hafta"),
    ("ohafta", "O'tgan hafta"),
    ("oy", "Shu oy"),
    ("ooy", "O'tgan oy"),
    ("yil", "Shu yil"),
    ("7kun", "Oxirgi 7 kun"),
    ("30kun", "Oxirgi 30 kun"),
    ("custom", "📅 Ixtiyoriy davr"),
]
register_ui(*[label for _, label in DAVRLAR], "📅 Davrni tanlang:")


class CustomRange(StatesGroup):
    sana = State()


async def reports_menu(user_id):
    return await build_keyboard(user_id, [
        ["📊 Umumiy hisobot"],
        ["📊 Tafsilotli hisobot"],
        ["👷 Ishchilar hisoboti"],
        ["💰 Moliya hisoboti"],
        ["📈 Taqqoslash"],
        ["📥 Excel hisobot"],
        ["🏠 Asosiy menyu"],
    ])


# ── Davr oralig'i ──
def davr_oraligi(kod):
    """(boshliq, oxiri, sarlavha) qaytaradi."""
    bugun = db.bugungi_sana()
    if kod == "bugun":
        return bugun, bugun, "Bugun"
    if kod == "kecha":
        y = bugun - timedelta(days=1)
        return y, y, "Kecha"
    if kod == "hafta":
        start = bugun - timedelta(days=bugun.weekday())
        return start, bugun, "Shu hafta"
    if kod == "ohafta":
        this_mon = bugun - timedelta(days=bugun.weekday())
        last_sun = this_mon - timedelta(days=1)
        last_mon = this_mon - timedelta(days=7)
        return last_mon, last_sun, "O'tgan hafta"
    if kod == "oy":
        return bugun.replace(day=1), bugun, "Shu oy"
    if kod == "ooy":
        first_this = bugun.replace(day=1)
        last_prev = first_this - timedelta(days=1)
        return last_prev.replace(day=1), last_prev, "O'tgan oy"
    if kod == "yil":
        return bugun.replace(month=1, day=1), bugun, "Shu yil"
    if kod == "7kun":
        return bugun - timedelta(days=6), bugun, "Oxirgi 7 kun"
    if kod == "30kun":
        return bugun - timedelta(days=29), bugun, "Oxirgi 30 kun"
    return bugun, bugun, "Bugun"


def oldingi_davr(boshliq, oxiri):
    """Joriy davrga teng uzunlikdagi oldingi davr."""
    uzunlik = (oxiri - boshliq).days + 1
    prev_oxiri = boshliq - timedelta(days=1)
    prev_boshliq = prev_oxiri - timedelta(days=uzunlik - 1)
    return prev_boshliq, prev_oxiri


async def davr_keyboard(user_id, rtype):
    """Davr tanlash uchun tarjima qilingan inline klaviatura."""
    til = await foydalanuvchi_tili(user_id)
    kb, row = [], []
    for kod, label in DAVRLAR:
        matn = label if til == "uz" else await tarjima_qil(label, til)
        row.append(InlineKeyboardButton(text=matn, callback_data=f"rep:{rtype}:{kod}"))
        if len(row) == 2:
            kb.append(row)
            row = []
    if row:
        kb.append(row)
    return InlineKeyboardMarkup(inline_keyboard=kb)


# ── Hisoblash yordamchilari ──
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


def _vaqt_str(vaqt, fmt="%d.%m %H:%M"):
    if hasattr(vaqt, "strftime"):
        if vaqt.tzinfo is None:
            vaqt = vaqt.replace(tzinfo=timezone.utc).astimezone(TOSHKENT_TZ)
        return vaqt.strftime(fmt)
    return str(vaqt)[:16]


def _delta(cur, prev):
    """O'sish/pasayish foizi (matn)."""
    if prev == 0:
        return "(▲ yangi)" if cur > 0 else ""
    p = (cur - prev) / prev * 100
    arrow = "▲" if p >= 0 else "▼"
    return f"({arrow} {abs(p):.1f}%)"


# ── Hisobot matnlari (generatorlar) ──
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


async def gen_tafsil(boshliq, oxiri, sarlavha):
    prod_detail = await db.get_production_detail_range(boshliq, oxiri)
    sales_detail = await db.get_sales_detail_range(boshliq, oxiri)
    chiqim = await db.get_material_chiqim_range(boshliq, oxiri)

    text = f"📊 Tafsilotli hisobot ({sarlavha})\n📅 {boshliq} — {oxiri}\n━━━━━━━━━━━━━━━━\n\n"
    text += "🏭 ISHLAB CHIQARISH:\n"
    if prod_detail:
        for p in prod_detail[:15]:
            shablon_nomi = {1: "A(12ta)", 2: "B(24ta)", 3: "11A+2B"}.get(p["shablon"], "?")
            text += (
                f"   {_vaqt_str(p['vaqt'])} | {p.get('user_ism') or 'Nomalum'}\n"
                f"   Shablon {p['shablon']}({shablon_nomi}): {p['qolip_soni']} qolip\n"
            )
    else:
        text += "   Ma'lumot yo'q\n"

    text += "\n💰 SOTUV:\n"
    if sales_detail:
        for s in sales_detail[:15]:
            text += (
                f"   {_vaqt_str(s['vaqt'])} | {s.get('user_ism') or 'Nomalum'}\n"
                f"   {s['block_type']} blok: {s['miqdor']} ta\n"
            )
    else:
        text += "   Ma'lumot yo'q\n"

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
    return text


async def gen_moliya(boshliq, oxiri, sarlavha):
    rev = await db.get_sales_revenue_range(boshliq, oxiri)
    ti = await db.tannarx_hisobla()
    A_qty, A_rev = rev["A"]
    B_qty, B_rev = rev["B"]
    daromad = A_rev + B_rev
    cogs = A_qty * ti["A"] + B_qty * ti["B"]
    foyda = daromad - cogs
    foyda_foiz = (foyda / daromad * 100) if daromad > 0 else 0.0

    xom = await db.ombor_xom_qiymati()
    goods = await db.get_finished_goods()
    A_qoldiq = next((g[1] for g in goods if g[0] == "A"), 0)
    B_qoldiq = next((g[1] for g in goods if g[0] == "B"), 0)
    tayyor_tannarx = A_qoldiq * ti["A"] + B_qoldiq * ti["B"]
    sotuv_A = float(await db.get_bot_setting("sotuv_narx_A") or 0)
    sotuv_B = float(await db.get_bot_setting("sotuv_narx_B") or 0)
    tayyor_sotuv = A_qoldiq * sotuv_A + B_qoldiq * sotuv_B
    kod = await val.get_active()

    return (
        f"💰 Moliya hisoboti ({sarlavha})\n"
        f"📅 {boshliq} — {oxiri}\n"
        f"💱 Valyuta: {val.belgi(kod)} ({kod})\n"
        f"━━━━━━━━━━━━━━━━\n\n"
        f"📈 SOTUV:\n"
        f"   A: {A_qty} ta = {await val.format_uzs(A_rev)}\n"
        f"   B: {B_qty} ta = {await val.format_uzs(B_rev)}\n"
        f"   Daromad: {await val.format_uzs(daromad)}\n\n"
        f"📉 Tannarx (COGS): {await val.format_uzs(cogs)}\n"
        f"💵 Sof foyda: {await val.format_uzs(foyda)} ({foyda_foiz:.1f}%)\n\n"
        f"🧱 1 blok tannarxi:\n"
        f"   A: {await val.format_uzs(ti['A'])} | sotuv: {await val.format_uzs(sotuv_A)}\n"
        f"   B: {await val.format_uzs(ti['B'])} | sotuv: {await val.format_uzs(sotuv_B)}\n\n"
        f"🏪 Ombor qiymati (xom ashyo): {await val.format_uzs(xom)}\n"
        f"🏬 Tayyor mahsulot:\n"
        f"   Tannarxda: {await val.format_uzs(tayyor_tannarx)}\n"
        f"   Sotuv narxida: {await val.format_uzs(tayyor_sotuv)}"
    )


async def gen_ishchi(boshliq, oxiri, sarlavha):
    prod = await db.get_production_by_user_range(boshliq, oxiri)
    sales = await db.get_sales_by_user_range(boshliq, oxiri)
    ishchi_haqi = float(await db.get_bot_setting("ishchi_haqi_qolip") or 0)

    text = (
        f"👷 Ishchilar hisoboti ({sarlavha})\n"
        f"📅 {boshliq} — {oxiri}\n"
        f"━━━━━━━━━━━━━━━━\n\n"
        f"🏭 ISHLAB CHIQARISH (ishbay haq):\n"
    )
    if prod:
        for p in prod:
            haq = p["qolip"] * ishchi_haqi
            text += (
                f"   {p['ism']}: {p['qolip']} qolip "
                f"(A:{p['A']} B:{p['B']})\n"
                f"      💵 Ish haqi: {await val.format_uzs(haq)}\n"
            )
    else:
        text += "   Ma'lumot yo'q\n"

    text += "\n💰 SOTUV (kim sotdi):\n"
    if sales:
        for s in sales:
            text += f"   {s['ism']}: {s['qty']} ta = {await val.format_uzs(s['rev'])}\n"
    else:
        text += "   Ma'lumot yo'q\n"
    return text


async def _metrikalar(boshliq, oxiri):
    prod = await db.get_production_range(boshliq, oxiri)
    jami_qolip, A, B, _, _, _ = hisobla_production(prod)
    rev = await db.get_sales_revenue_range(boshliq, oxiri)
    ti = await db.tannarx_hisobla()
    A_qty, A_rev = rev["A"]
    B_qty, B_rev = rev["B"]
    daromad = A_rev + B_rev
    cogs = A_qty * ti["A"] + B_qty * ti["B"]
    return {
        "qolip": jami_qolip, "A": A, "B": B,
        "sotuv": A_qty + B_qty, "daromad": daromad, "foyda": daromad - cogs,
    }


async def gen_taqqos(boshliq, oxiri, sarlavha):
    pb, po = oldingi_davr(boshliq, oxiri)
    cur = await _metrikalar(boshliq, oxiri)
    prev = await _metrikalar(pb, po)
    return (
        f"📈 Taqqoslash: {sarlavha}\n"
        f"📅 {boshliq} — {oxiri}\n"
        f"   (oldingi davr: {pb} — {po})\n"
        f"━━━━━━━━━━━━━━━━\n\n"
        f"🏭 Jami qolip: {cur['qolip']} {_delta(cur['qolip'], prev['qolip'])}\n"
        f"   A ishlab ch.: {cur['A']} {_delta(cur['A'], prev['A'])}\n"
        f"   B ishlab ch.: {cur['B']} {_delta(cur['B'], prev['B'])}\n\n"
        f"💰 Sotuv (dona): {cur['sotuv']} {_delta(cur['sotuv'], prev['sotuv'])}\n"
        f"   Daromad: {await val.format_uzs(cur['daromad'])} "
        f"{_delta(cur['daromad'], prev['daromad'])}\n"
        f"   Foyda: {await val.format_uzs(cur['foyda'])} "
        f"{_delta(cur['foyda'], prev['foyda'])}"
    )


# ── Excel ──
async def _excel_yubor(target, user_id, boshliq, oxiri):
    prod_logs = await db.get_production_range(boshliq, oxiri)
    sales_logs = await db.get_sales_range(boshliq, oxiri)
    materials = await db.get_materials()
    goods = await db.get_finished_goods()
    audit_logs = await db.get_audit_log(200)
    prod_detail = await db.get_production_detail_range(boshliq, oxiri)
    sales_detail = await db.get_sales_detail_range(boshliq, oxiri)
    chiqim_logs = await db.get_material_chiqim_range(boshliq, oxiri)

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

    ws1 = wb.active
    ws1.title = "Ishlab chiqarish"
    sarlavha_qo(ws1, 1, ["Sana", "Shablon 1", "Shablon 2", "Shablon 3", "Jami qolip", "A blok", "B blok"])
    ws1.column_dimensions["A"].width = 14
    sanalar = {}
    for log in prod_logs:
        sana = log[0]
        sanalar.setdefault(sana, [0, 0, 0])
        idx = log[1] - 1
        if 0 <= idx <= 2:
            sanalar[sana][idx] += log[2]
    for sana, counts in sorted(sanalar.items()):
        s1, s2, s3 = counts
        ws1.append([sana, s1, s2, s3, s1 + s2 + s3, s1 * 12 + s3 * 11, s2 * 24 + s3 * 2])

    ws2 = wb.create_sheet("Ishlab chiqarish (tafsilot)")
    sarlavha_qo(ws2, 1, ["Vaqt", "Foydalanuvchi", "Rol", "Shablon", "Qolip soni", "A blok", "B blok"])
    ws2.column_dimensions["A"].width = 18
    ws2.column_dimensions["B"].width = 16
    for p in prod_detail:
        shablon = p["shablon"]
        qolip = p["qolip_soni"]
        A = qolip * 12 if shablon == 1 else (qolip * 11 if shablon == 3 else 0)
        B = qolip * 24 if shablon == 2 else (qolip * 2 if shablon == 3 else 0)
        ws2.append([_vaqt_str(p["vaqt"], "%d.%m.%Y %H:%M"), p["user_ism"] or "Nomalum",
                    p["user_rol"] or "-", shablon, qolip, A, B])

    ws3 = wb.create_sheet("Sotuv")
    sarlavha_qo(ws3, 1, ["Sana", "A blok", "B blok", "Jami"])
    ws3.column_dimensions["A"].width = 14
    sotuv_sanalar = {}
    for log in sales_logs:
        sana = log[0]
        sotuv_sanalar.setdefault(sana, {"A": 0, "B": 0})
        sotuv_sanalar[sana][log[1]] += log[2]
    for sana, counts in sorted(sotuv_sanalar.items()):
        A = counts.get("A", 0)
        B = counts.get("B", 0)
        ws3.append([sana, A, B, A + B])

    ws4 = wb.create_sheet("Sotuv (tafsilot)")
    sarlavha_qo(ws4, 1, ["Vaqt", "Foydalanuvchi", "Rol", "Blok turi", "Miqdor"])
    ws4.column_dimensions["A"].width = 18
    ws4.column_dimensions["B"].width = 16
    for s in sales_detail:
        ws4.append([_vaqt_str(s["vaqt"], "%d.%m.%Y %H:%M"), s["user_ism"] or "Nomalum",
                    s["user_rol"] or "-", s["block_type"], s["miqdor"]])

    ws5 = wb.create_sheet("Xom ashyo sarfi")
    sarlavha_qo(ws5, 1, ["Sana", "Material", "Ketgan miqdor", "Birlik"])
    ws5.column_dimensions["A"].width = 14
    ws5.column_dimensions["B"].width = 20
    for ch in chiqim_logs:
        asl = db.asosiydan_birlikga(float(ch["jami"]), ch["birlik"])
        ws5.append([ch["sana"], ch["material_nomi"], round(asl, 2), ch["birlik"]])

    ws6 = wb.create_sheet("Ombor qoldiqlari")
    sarlavha_qo(ws6, 1, ["Material", "Qoldiq", "Birlik"])
    ws6.column_dimensions["A"].width = 20
    for m in materials:
        ws6.append([m[1], round(db.asosiydan_birlikga(m[2], m[4]), 2), m[4]])
    ws6.append([])
    ws6.append(["── Tayyor mahsulot ──", "", ""])
    for g in goods:
        ws6.append([f"{g[0]} blok", g[1], "ta"])

    ws7 = wb.create_sheet("Audit log")
    sarlavha_qo(ws7, 1, ["Vaqt", "Foydalanuvchi", "Rol", "Amal", "Tafsilot"])
    ws7.column_dimensions["A"].width = 18
    ws7.column_dimensions["B"].width = 16
    ws7.column_dimensions["D"].width = 25
    ws7.column_dimensions["E"].width = 40
    for log in audit_logs:
        ws7.append([_vaqt_str(log["vaqt"], "%d.%m.%Y %H:%M"), log["ism"] or "",
                    log["rol"] or "", log["amal"] or "", log["tafsilot"] or ""])

    ws8 = wb.create_sheet("Moliya")
    sarlavha_qo(ws8, 1, ["Ko'rsatkich", "Qiymat (so'm)"])
    ws8.column_dimensions["A"].width = 28
    ws8.column_dimensions["B"].width = 20
    rev = await db.get_sales_revenue_range(boshliq, oxiri)
    ti = await db.tannarx_hisobla()
    A_qty, A_rev = rev["A"]
    B_qty, B_rev = rev["B"]
    daromad = A_rev + B_rev
    cogs = A_qty * ti["A"] + B_qty * ti["B"]
    xom = await db.ombor_xom_qiymati()
    A_q = next((g[1] for g in goods if g[0] == "A"), 0)
    B_q = next((g[1] for g in goods if g[0] == "B"), 0)
    sotuv_A = float(await db.get_bot_setting("sotuv_narx_A") or 0)
    sotuv_B = float(await db.get_bot_setting("sotuv_narx_B") or 0)
    for nomi_q, qiymat in [
        ("A sotuv (dona)", A_qty), ("A daromad", round(A_rev)),
        ("B sotuv (dona)", B_qty), ("B daromad", round(B_rev)),
        ("Jami daromad", round(daromad)), ("Tannarx (COGS)", round(cogs)),
        ("Sof foyda", round(daromad - cogs)),
        ("1 A blok tannarxi", round(ti["A"])), ("1 B blok tannarxi", round(ti["B"])),
        ("A sotuv narxi", round(sotuv_A)), ("B sotuv narxi", round(sotuv_B)),
        ("Ombor (xom ashyo) qiymati", round(xom)),
        ("Tayyor mahsulot (tannarx)", round(A_q * ti["A"] + B_q * ti["B"])),
        ("Tayyor mahsulot (sotuv)", round(A_q * sotuv_A + B_q * sotuv_B)),
    ]:
        ws8.append([nomi_q, qiymat])

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    fayl_nomi = f"gazobot_{boshliq}_{oxiri}.xlsx"
    caption = await t(f"📥 Excel hisobot\n📅 {boshliq} — {oxiri}\n8 ta varaq", user_id)
    await target.answer_document(
        BufferedInputFile(buffer.read(), filename=fayl_nomi), caption=caption
    )


# ── Umumiy yuborish ──
async def _yubor(target, user_id, matn):
    tt = await t(matn, user_id)
    if len(tt) > 4096:
        tt = tt[:4095] + "…"
    await target.answer(tt)


async def _generate(target, user_id, rtype, boshliq, oxiri, sarlavha):
    try:
        if rtype == "excel":
            await _excel_yubor(target, user_id, boshliq, oxiri)
            return
        if rtype == "umumiy":
            matn = await hisobot_matni(boshliq, oxiri, f"📊 {sarlavha}")
        elif rtype == "tafsil":
            matn = await gen_tafsil(boshliq, oxiri, sarlavha)
        elif rtype == "moliya":
            matn = await gen_moliya(boshliq, oxiri, sarlavha)
        elif rtype == "ishchi":
            matn = await gen_ishchi(boshliq, oxiri, sarlavha)
        elif rtype == "taqqos":
            matn = await gen_taqqos(boshliq, oxiri, sarlavha)
        else:
            matn = await hisobot_matni(boshliq, oxiri, sarlavha)
        await _yubor(target, user_id, matn)
    except Exception as e:
        log_exc("report_generate", e)
        await _yubor(target, user_id, GENERIC_ERROR)


async def _ruxsat(user_id, rtype):
    user = await db.get_user(user_id)
    if not user or not user["faol"]:
        return False
    if user["rol"] == "superadmin":
        return True
    perm = "excel_hisobot" if rtype == "excel" else "hisobot_korish"
    return await db.has_permission(user_id, user["rol"], perm)


# ── Kirish (reply tugmalari → davr tanlovchi) ──
@router.message(Tkey("📊 Hisobot"))
async def hisobot(message: Message):
    await say(message, "📊 Hisobotlar:", reply_markup=await reports_menu(message.from_user.id))


async def _davr_sorov(message, rtype):
    await say(
        message, "📅 Davrni tanlang:",
        reply_markup=await davr_keyboard(message.from_user.id, rtype)
    )


@router.message(Tkey("📊 Umumiy hisobot"))
async def umumiy_entry(message: Message):
    await _davr_sorov(message, "umumiy")


@router.message(Tkey("📊 Tafsilotli hisobot"))
async def tafsil_entry(message: Message):
    await _davr_sorov(message, "tafsil")


@router.message(Tkey("👷 Ishchilar hisoboti"))
async def ishchi_entry(message: Message):
    await _davr_sorov(message, "ishchi")


@router.message(Tkey("💰 Moliya hisoboti"))
async def moliya_entry(message: Message):
    await _davr_sorov(message, "moliya")


@router.message(Tkey("📈 Taqqoslash"))
async def taqqos_entry(message: Message):
    await _davr_sorov(message, "taqqos")


@router.message(Tkey("📥 Excel hisobot"))
async def excel_entry(message: Message):
    await _davr_sorov(message, "excel")


# ── Davr callback ──
@router.callback_query(lambda c: c.data and c.data.startswith("rep:"))
async def rep_callback(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    rtype = parts[1] if len(parts) > 1 else "umumiy"
    period = parts[2] if len(parts) > 2 else "bugun"

    if not await _ruxsat(callback.from_user.id, rtype):
        await callback.answer("⛔", show_alert=False)
        return
    await callback.answer()

    if period == "custom":
        await state.clear()
        await state.update_data(rtype=rtype)
        await state.set_state(CustomRange.sana)
        xabar = await t(
            "📅 Davrni kiriting (YYYY-MM-DD YYYY-MM-DD):\nMisol: 2026-06-01 2026-06-15",
            callback.from_user.id
        )
        await callback.message.answer(xabar)
        return

    boshliq, oxiri, sarlavha = davr_oraligi(period)
    await _generate(callback.message, callback.from_user.id, rtype, boshliq, oxiri, sarlavha)


@router.message(CustomRange.sana)
async def custom_sana(message: Message, state: FSMContext):
    try:
        parts = message.text.strip().split()
        if len(parts) != 2:
            raise ValueError
        b = datetime.strptime(parts[0], "%Y-%m-%d").date()
        o = datetime.strptime(parts[1], "%Y-%m-%d").date()
        if b > o:
            b, o = o, b
        data = await state.get_data()
        rtype = data.get("rtype", "umumiy")
        await state.clear()
        await _generate(message, message.from_user.id, rtype, b, o, f"{b} — {o}")
    except ValueError:
        await say(
            message,
            "❌ Format: YYYY-MM-DD YYYY-MM-DD\nMisol: 2026-06-01 2026-06-15"
        )


async def avtomatik_hisobot(bot, chat_id):
    try:
        bugun = db.bugungi_sana()
        text = await hisobot_matni(bugun, bugun, "🔔 Avtomatik kunlik hisobot")
        text = await t(text, chat_id)
        await bot.send_message(chat_id, text)
    except Exception as e:
        log_exc("avtomatik_hisobot", e)
