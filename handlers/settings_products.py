"""Sozlamalar → 🏭 Mahsulot boshqaruvi (to'liq dinamik): bloklar, shablonlar, formula."""
from aiogram import Router
from aiogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import database as db
from translation import Tkey, say, t
from .settings_common import (
    sozlamalar_menu,
    faqat_superadmin as _faqat_superadmin,
    cb_ok as _cb_ok,
)

router = Router()


class MahsulotState(StatesGroup):
    nomi = State()
    emoji = State()


class MahsulotRename(StatesGroup):
    nomi = State()
    emoji = State()


class BlokState(StatesGroup):
    kod = State()
    nomi = State()
    olcham = State()
    dona = State()


class ShablonState(StatesGroup):
    nomi = State()
    chiqim = State()


class FormulaState(StatesGroup):
    miqdor = State()
    birlik = State()


def _slug(s):
    out = []
    for ch in (s or "").lower():
        if ch.isalnum() and ord(ch) < 128:
            out.append(ch)
        elif out and out[-1] != "_":
            out.append("_")
    res = "".join(out).strip("_")
    return res or "mahsulot"


async def _unique_kod(base):
    kod = base
    i = 1
    while await db.get_mahsulot_by_kod(kod):
        i += 1
        kod = f"{base}{i}"
    return kod


async def _mb_root_kb():
    prods = await db.get_mahsulotlar(faqat_faol=False)
    kb = []
    for p in prods:
        belgi = "" if p["faol"] else " (arxiv)"
        kb.append([InlineKeyboardButton(
            text=f"{p['emoji']} {p['nomi']}{belgi}",
            callback_data=f"mb_open:{p['id']}")])
    kb.append([InlineKeyboardButton(text="➕ Yangi mahsulot", callback_data="mb_add")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


async def _mb_detail(pid):
    p = await db.get_mahsulot(pid)
    if not p:
        return "❌ Mahsulot topilmadi.", InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Ortga", callback_data="mb_root")]])
    bloklar = await db.get_bloklar(pid)
    shablonlar = await db.get_shablonlar(pid)
    formula = await db.get_qolip_formula(pid)

    text = f"{p['emoji']} {p['nomi']}"
    text += "" if p["faol"] else "  (arxivlangan)"
    text += "\n\n👷 Ish haqi (1 qolip): " + f"{p['ishchi_haqi']:.0f} so'm\n"
    text += f"🛠 Qo'shimcha (1 qolip): {p['qoshimcha_xarajat']:.0f} so'm\n"
    text += "   (narxlar 💵 Narxlar va valyuta bo'limida)\n\n"

    text += "🧱 Bloklar:\n"
    if bloklar:
        for b in bloklar:
            text += (f"   • {b['nomi']} [{b['kod']}] — 1 qolipga "
                     f"{b['qolip_dona']:.0f} dona\n")
    else:
        text += "   (yo'q)\n"

    text += "\n📦 Shablonlar:\n"
    if shablonlar:
        for s in shablonlar:
            ch = ", ".join(f"{c['soni']}×{c['block_kod']}" for c in s["chiqim"])
            text += f"   • {s['nomi']}: {ch or 'bo`sh'}\n"
    else:
        text += "   (yo'q)\n"

    text += "\n📋 Formula (1 qolipga):\n"
    if formula:
        for f in formula:
            text += f"   • {f[0]}: {f[1]} {f[2]}\n"
    else:
        text += "   (yo'q)\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧱 Bloklar", callback_data=f"mb_blk:{pid}"),
         InlineKeyboardButton(text="📦 Shablonlar", callback_data=f"mb_shb:{pid}")],
        [InlineKeyboardButton(text="📋 Formula", callback_data=f"mb_frm:{pid}")],
        [InlineKeyboardButton(text="✏️ Nomi", callback_data=f"mb_ren:{pid}"),
         InlineKeyboardButton(
             text=("🗑 Arxivlash" if p["faol"] else "♻️ Faollashtirish"),
             callback_data=f"mb_arch:{pid}")],
        [InlineKeyboardButton(text="⬅️ Ortga", callback_data="mb_root")],
    ])
    return text, kb


async def _mb_blk_view(pid):
    bloklar = await db.get_bloklar(pid)
    text = "🧱 Bloklar (o'chirish uchun bosing):\n\n"
    if not bloklar:
        text += "   (yo'q)\n"
    kb = []
    for b in bloklar:
        kb.append([InlineKeyboardButton(
            text=f"🗑 {b['nomi']} [{b['kod']}]",
            callback_data=f"mb_blkdel:{b['id']}")])
    kb.append([InlineKeyboardButton(text="➕ Blok qo'shish", callback_data=f"mb_blkadd:{pid}")])
    kb.append([InlineKeyboardButton(text="⬅️ Ortga", callback_data=f"mb_open:{pid}")])
    return text, InlineKeyboardMarkup(inline_keyboard=kb)


async def _mb_shb_view(pid):
    shablonlar = await db.get_shablonlar(pid)
    text = "📦 Shablonlar (o'chirish uchun bosing):\n\n"
    if not shablonlar:
        text += "   (yo'q)\n"
    kb = []
    for s in shablonlar:
        ch = ", ".join(f"{c['soni']}×{c['block_kod']}" for c in s["chiqim"])
        kb.append([InlineKeyboardButton(
            text=f"🗑 {s['nomi']} ({ch or 'bo`sh'})",
            callback_data=f"mb_shbdel:{s['id']}")])
    kb.append([InlineKeyboardButton(text="➕ Shablon qo'shish", callback_data=f"mb_shbadd:{pid}")])
    kb.append([InlineKeyboardButton(text="⬅️ Ortga", callback_data=f"mb_open:{pid}")])
    return text, InlineKeyboardMarkup(inline_keyboard=kb)


@router.message(Tkey("🏭 Mahsulot boshqaruvi"))
async def mahsulot_boshqaruvi(message: Message, state: FSMContext, user: dict = None):
    if not await _faqat_superadmin(message, user):
        return
    await state.clear()
    xabar = await t("🏭 Mahsulot boshqaruvi\nMahsulotni tanlang yoki yangi qo'shing:",
                    message.from_user.id)
    await message.answer(xabar, reply_markup=await _mb_root_kb())


@router.callback_query(lambda c: c.data and c.data.startswith("mb_"))
async def mb_callback(callback: CallbackQuery, state: FSMContext):
    if not await _cb_ok(callback):
        return
    action, _, arg = callback.data.partition(":")
    aid = int(arg) if arg.isdigit() else None

    if action == "mb_root":
        await state.clear()
        await callback.message.edit_text(
            "🏭 Mahsulot boshqaruvi\nMahsulotni tanlang yoki yangi qo'shing:",
            reply_markup=await _mb_root_kb())
        await callback.answer()
        return

    if action == "mb_open":
        await state.clear()
        text, kb = await _mb_detail(aid)
        await callback.message.edit_text(text, reply_markup=kb)
        await callback.answer()
        return

    if action == "mb_blk":
        text, kb = await _mb_blk_view(aid)
        await callback.message.edit_text(text, reply_markup=kb)
        await callback.answer()
        return

    if action == "mb_shb":
        text, kb = await _mb_shb_view(aid)
        await callback.message.edit_text(text, reply_markup=kb)
        await callback.answer()
        return

    if action == "mb_arch":
        p = await db.get_mahsulot(aid)
        if p:
            await db.set_mahsulot_faol(aid, not p["faol"])
        text, kb = await _mb_detail(aid)
        await callback.message.edit_text(text, reply_markup=kb)
        await callback.answer("✅")
        return

    if action == "mb_blkdel":
        blok = await db.get_blok_by_id(aid)
        if not blok:
            await callback.answer("❌", show_alert=True)
            return
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Ha, o'chirish", callback_data=f"mb_blkdelok:{aid}"),
            InlineKeyboardButton(text="⬅️ Yo'q", callback_data=f"mb_blk:{blok['product_id']}"),
        ]])
        await callback.message.edit_text(
            await t(f"🗑 '{blok['nomi']}' blokini o'chirasizmi?", callback.from_user.id),
            reply_markup=kb)
        await callback.answer()
        return

    if action == "mb_blkdelok":
        blok = await db.get_blok_by_id(aid)
        pid = blok["product_id"] if blok else None
        await db.delete_blok(aid)
        if pid:
            text, kb = await _mb_blk_view(pid)
            await callback.message.edit_text(text, reply_markup=kb)
        await callback.answer("🗑 O'chirildi")
        return

    if action == "mb_shbdel":
        sh = await db.get_shablon(aid)
        if not sh:
            await callback.answer("❌", show_alert=True)
            return
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Ha, o'chirish", callback_data=f"mb_shbdelok:{aid}"),
            InlineKeyboardButton(text="⬅️ Yo'q", callback_data=f"mb_shb:{sh['product_id']}"),
        ]])
        await callback.message.edit_text(
            await t(f"🗑 '{sh['nomi']}' shablonini o'chirasizmi?", callback.from_user.id),
            reply_markup=kb)
        await callback.answer()
        return

    if action == "mb_shbdelok":
        sh = await db.get_shablon(aid)
        pid = sh["product_id"] if sh else None
        await db.delete_shablon(aid)
        if pid:
            text, kb = await _mb_shb_view(pid)
            await callback.message.edit_text(text, reply_markup=kb)
        await callback.answer("🗑 O'chirildi")
        return

    # ── FSM boshlovchi amallar ──
    if action == "mb_add":
        await state.clear()
        await state.set_state(MahsulotState.nomi)
        await callback.message.answer(
            await t("➕ Yangi mahsulot nomini kiriting:\nMisol: Polistirol blok",
                    callback.from_user.id))
        await callback.answer()
        return

    if action == "mb_ren":
        await state.clear()
        await state.update_data(pid=aid)
        await state.set_state(MahsulotRename.nomi)
        await callback.message.answer(
            await t("✏️ Yangi nom kiriting:", callback.from_user.id))
        await callback.answer()
        return

    if action == "mb_blkadd":
        await state.clear()
        await state.update_data(pid=aid)
        await state.set_state(BlokState.kod)
        await callback.message.answer(
            await t("🧱 Blok kodini kiriting (qisqa):\nMisol: P  yoki  A",
                    callback.from_user.id))
        await callback.answer()
        return

    if action == "mb_shbadd":
        bloklar = await db.get_bloklar(aid)
        if not bloklar:
            await callback.answer("❌ Avval blok qo'shing!", show_alert=True)
            return
        await state.clear()
        await state.update_data(pid=aid)
        await state.set_state(ShablonState.nomi)
        await callback.message.answer(
            await t("📦 Shablon nomini kiriting:\nMisol: Standart  yoki  Shablon 1",
                    callback.from_user.id))
        await callback.answer()
        return

    if action == "mb_frm":
        materials = await db.get_materials()
        if not materials:
            await callback.answer("❌ Avval material qo'shing!", show_alert=True)
            return
        await state.clear()
        text, kb = await _frm_editor(aid)
        await callback.message.edit_text(text, reply_markup=kb)
        await callback.answer()
        return

    await callback.answer()


# ── Mahsulot qo'shish (FSM) ──
@router.message(MahsulotState.nomi)
async def mb_add_nomi(message: Message, state: FSMContext):
    nomi = message.text.strip()
    if not nomi:
        await say(message, "❌ Nom bo'sh bo'lmasin!")
        return
    await state.update_data(nomi=nomi)
    await state.set_state(MahsulotState.emoji)
    await say(message, "Emoji kiriting (ixtiyoriy):\nMisol: 🧊\nO'tkazib yuborish: 0")


@router.message(MahsulotState.emoji)
async def mb_add_emoji(message: Message, state: FSMContext):
    data = await state.get_data()
    emoji = message.text.strip()
    if emoji == "0" or not emoji:
        emoji = "📦"
    nomi = data["nomi"]
    kod = await _unique_kod(_slug(nomi))
    pid = await db.add_mahsulot(kod, nomi, emoji)
    user = await db.get_user(message.from_user.id)
    await db.add_audit_log(
        message.from_user.id, user["ism"] if user else "-",
        user["rol"] if user else "-", "Mahsulot qo'shildi", f"{nomi} ({kod})")
    await state.clear()
    await say(message,
              f"✅ '{nomi}' qo'shildi!\n\n"
              f"Endi 🧱 Bloklar, 📦 Shablonlar va 📋 Formulani sozlang.",
              reply_markup=await sozlamalar_menu(message.from_user.id))
    text, kb = await _mb_detail(pid)
    await message.answer(text, reply_markup=kb)


# ── Nomni o'zgartirish (FSM) ──
@router.message(MahsulotRename.nomi)
async def mb_ren_nomi(message: Message, state: FSMContext):
    nomi = message.text.strip()
    if not nomi:
        await say(message, "❌ Nom bo'sh bo'lmasin!")
        return
    await state.update_data(nomi=nomi)
    await state.set_state(MahsulotRename.emoji)
    await say(message, "Emoji kiriting (ixtiyoriy):\nO'zgartirmaslik: 0")


@router.message(MahsulotRename.emoji)
async def mb_ren_emoji(message: Message, state: FSMContext):
    data = await state.get_data()
    pid = data["pid"]
    p = await db.get_mahsulot(pid)
    emoji = message.text.strip()
    if emoji == "0" or not emoji:
        emoji = p["emoji"] if p else "📦"
    await db.update_mahsulot(pid, data["nomi"], emoji)
    await state.clear()
    await say(message, "✅ Yangilandi!",
              reply_markup=await sozlamalar_menu(message.from_user.id))
    text, kb = await _mb_detail(pid)
    await message.answer(text, reply_markup=kb)


# ── Blok qo'shish (FSM) ──
@router.message(BlokState.kod)
async def mb_blk_kod(message: Message, state: FSMContext):
    kod = message.text.strip()
    if not kod or len(kod) > 16:
        await say(message, "❌ Kod 1–16 belgidan iborat bo'lsin!")
        return
    data = await state.get_data()
    mavjud = await db.get_blok(data["pid"], kod)
    if mavjud:
        await say(message, "❌ Bu kod allaqachon mavjud! Boshqa kod kiriting:")
        return
    await state.update_data(kod=kod)
    await state.set_state(BlokState.nomi)
    await say(message, "Blok to'liq nomini kiriting:\nMisol: Polistirol blok")


@router.message(BlokState.nomi)
async def mb_blk_nomi(message: Message, state: FSMContext):
    await state.update_data(nomi=message.text.strip())
    await state.set_state(BlokState.olcham)
    await say(message, "O'lchamini kiriting (ixtiyoriy):\nMisol: 30×60×20\nO'tkazib yuborish: 0")


@router.message(BlokState.olcham)
async def mb_blk_olcham(message: Message, state: FSMContext):
    olcham = message.text.strip()
    if olcham == "0":
        olcham = ""
    await state.update_data(olcham=olcham)
    await state.set_state(BlokState.dona)
    await say(message,
              "Tannarx uchun: 1 qolipdan shu blokdan nechta chiqadi?\n"
              "(1 blok tannarxi = qolip tannarxi ÷ shu son)\nMisol: 30")


@router.message(BlokState.dona)
async def mb_blk_dona(message: Message, state: FSMContext):
    try:
        dona = float(message.text.replace(",", "."))
        if dona <= 0:
            raise ValueError
    except ValueError:
        await say(message, "❌ Faqat musbat son kiriting! Misol: 30")
        return
    data = await state.get_data()
    await db.add_blok(data["pid"], data["kod"], data["nomi"], data["olcham"], dona, 0)
    user = await db.get_user(message.from_user.id)
    await db.add_audit_log(
        message.from_user.id, user["ism"] if user else "-",
        user["rol"] if user else "-", "Blok qo'shildi",
        f"{data['nomi']} [{data['kod']}]")
    await state.clear()
    await say(message, f"✅ Blok qo'shildi: {data['nomi']}\n"
                       f"💡 Sotuv narxini 💵 Narxlar bo'limidan kiriting.",
              reply_markup=await sozlamalar_menu(message.from_user.id))
    text, kb = await _mb_blk_view(data["pid"])
    await message.answer(text, reply_markup=kb)


# ── Shablon qo'shish (FSM) ──
@router.message(ShablonState.nomi)
async def mb_shb_nomi(message: Message, state: FSMContext):
    nomi = message.text.strip()
    if not nomi:
        await say(message, "❌ Nom bo'sh bo'lmasin!")
        return
    data = await state.get_data()
    bloklar = await db.get_bloklar(data["pid"])
    await state.update_data(
        nomi=nomi,
        bloklar=[(b["kod"], b["nomi"]) for b in bloklar],
        b_index=0, chiqim=[])
    await state.set_state(ShablonState.chiqim)
    b = bloklar[0]
    await say(message,
              f"📦 '{nomi}' shabloni:\n\n"
              f"1 qolipga nechta '{b['nomi']}' [{b['kod']}] chiqadi?\n"
              f"Yo'q bo'lsa: 0")


@router.message(ShablonState.chiqim)
async def mb_shb_chiqim(message: Message, state: FSMContext):
    try:
        soni = int(message.text.strip())
        if soni < 0:
            raise ValueError
    except ValueError:
        await say(message, "❌ Faqat butun son kiriting! (yo'q bo'lsa 0)")
        return
    data = await state.get_data()
    bloklar = data["bloklar"]
    b_index = data["b_index"]
    chiqim = data["chiqim"]
    kod, _nomi = bloklar[b_index]
    if soni > 0:
        chiqim.append((kod, soni))
    b_index += 1
    if b_index < len(bloklar):
        await state.update_data(b_index=b_index, chiqim=chiqim)
        bk, bn = bloklar[b_index]
        await say(message, f"1 qolipga nechta '{bn}' [{bk}] chiqadi?\nYo'q bo'lsa: 0")
        return
    # Tugadi
    if not chiqim:
        await state.clear()
        await say(message, "❌ Shablon bo'sh — saqlanmadi (kamida 1 blok kerak).",
                  reply_markup=await sozlamalar_menu(message.from_user.id))
        return
    pid = data["pid"]
    mavjud = await db.get_shablonlar(pid)
    kod = str(len(mavjud) + 1)
    sid = await db.add_shablon(pid, kod, data["nomi"])
    await db.set_shablon_chiqim(sid, chiqim)
    user = await db.get_user(message.from_user.id)
    await db.add_audit_log(
        message.from_user.id, user["ism"] if user else "-",
        user["rol"] if user else "-", "Shablon qo'shildi",
        f"{data['nomi']}: " + ", ".join(f"{s}×{k}" for k, s in chiqim))
    await state.clear()
    await say(message, f"✅ Shablon qo'shildi: {data['nomi']}",
              reply_markup=await sozlamalar_menu(message.from_user.id))
    text, kb = await _mb_shb_view(pid)
    await message.answer(text, reply_markup=kb)


# ── Formula (tanlab tahrirlash — inline) ──
_FRM_OGIRLIK = ["kg", "tonna", "meshok", "g"]
_FRM_HAJM = ["litr", "ml", "m3"]


async def _frm_editor(pid):
    p = await db.get_mahsulot(pid)
    formula = await db.get_qolip_formula(pid)
    inframe = {f[5]: (f[1], f[2]) for f in formula}
    materials = await db.get_materials()
    text = (f"📋 {p['nomi'] if p else ''} — formula (1 qolipga)\n\n"
            f"Materialni tanlab miqdor kiriting.\n✅ = formulada bor.")
    kb = []
    for m in materials:
        mid = m[0]
        if mid in inframe:
            q, u = inframe[mid]
            label = f"✅ {m[1]}: {q} {u}"
        else:
            label = f"➕ {m[1]}"
        kb.append([InlineKeyboardButton(text=label, callback_data=f"frm:{pid}:{mid}")])
    kb.append([InlineKeyboardButton(text="✅ Tayyor", callback_data=f"frm_done:{pid}")])
    return text, InlineKeyboardMarkup(inline_keyboard=kb)


def _frm_units_kb(asl_birlik, pid):
    baza = db.birlik_bazasi(asl_birlik)
    birliklar = _FRM_OGIRLIK if baza == "kg" else _FRM_HAJM
    kb, row = [], []
    for b in birliklar:
        row.append(InlineKeyboardButton(text=b, callback_data=f"frmunit:{b}"))
        if len(row) == 2:
            kb.append(row)
            row = []
    if row:
        kb.append(row)
    kb.append([InlineKeyboardButton(text="⬅️ Ortga", callback_data=f"frm_back:{pid}")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


@router.callback_query(lambda c: c.data and c.data.startswith("frm:"))
async def frm_pick(callback: CallbackQuery, state: FSMContext):
    if not await _cb_ok(callback):
        return
    _, pid, mid = callback.data.split(":")
    pid, mid = int(pid), int(mid)
    materials = await db.get_materials()
    m = next((x for x in materials if x[0] == mid), None)
    if not m:
        await callback.answer("❌", show_alert=True)
        return
    await state.update_data(frm_pid=pid, frm_mid=mid, frm_nomi=m[1], frm_birlik=m[4])
    await state.set_state(FormulaState.miqdor)
    formula = await db.get_qolip_formula(pid)
    bor = next((f for f in formula if f[5] == mid), None)
    izoh = f"\nHozir: {bor[1]} {bor[2]}" if bor else ""
    rows = []
    if bor:
        rows.append([InlineKeyboardButton(
            text="🗑 Formuladan olib tashlash", callback_data=f"frm_del:{pid}:{mid}")])
    rows.append([InlineKeyboardButton(text="⬅️ Ortga", callback_data=f"frm_back:{pid}")])
    try:
        await callback.message.edit_text(await t(
            f"📋 {m[1]} — 1 qolipga qancha ketadi?{izoh}\n"
            f"Sonni kiriting (masalan: 110)", callback.from_user.id),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    except Exception:
        pass
    await callback.answer()


@router.message(FormulaState.miqdor)
async def frm_miqdor(message: Message, state: FSMContext):
    try:
        miqdor = float(message.text.replace(",", "."))
        if miqdor <= 0:
            raise ValueError
    except (ValueError, AttributeError):
        await say(message, "❌ Faqat musbat son kiriting! Misol: 110")
        return
    data = await state.get_data()
    if "frm_mid" not in data:
        await state.clear()
        return
    await state.update_data(frm_miqdor=miqdor)
    await say(message,
              f"📏 {data['frm_nomi']}: {miqdor}\nBirlikni tanlang:",
              reply_markup=_frm_units_kb(data["frm_birlik"], data["frm_pid"]))


@router.callback_query(lambda c: c.data and c.data.startswith("frmunit:"))
async def frm_unit(callback: CallbackQuery, state: FSMContext):
    if not await _cb_ok(callback):
        return
    birlik = callback.data.split(":", 1)[1]
    data = await state.get_data()
    if "frm_mid" not in data or "frm_miqdor" not in data:
        await callback.answer()
        return
    if db.birlik_bazasi(birlik) != db.birlik_bazasi(data["frm_birlik"]):
        await callback.answer("❌ Birlik mos emas", show_alert=True)
        return
    await db.set_qolip_formula_item(
        data["frm_pid"], data["frm_mid"], data["frm_miqdor"], birlik)
    pid = data["frm_pid"]
    await state.clear()
    text, kb = await _frm_editor(pid)
    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except Exception:
        await callback.message.answer(text, reply_markup=kb)
    await callback.answer("✅ Saqlandi")


@router.callback_query(lambda c: c.data and c.data.startswith("frm_del:"))
async def frm_del(callback: CallbackQuery, state: FSMContext):
    if not await _cb_ok(callback):
        return
    _, pid, mid = callback.data.split(":")
    pid, mid = int(pid), int(mid)
    await db.remove_qolip_formula_item(pid, mid)
    await state.clear()
    text, kb = await _frm_editor(pid)
    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except Exception:
        pass
    await callback.answer("🗑 Olib tashlandi")


@router.callback_query(lambda c: c.data and c.data.startswith("frm_back:"))
async def frm_back(callback: CallbackQuery, state: FSMContext):
    if not await _cb_ok(callback):
        return
    pid = int(callback.data.split(":", 1)[1])
    await state.clear()
    text, kb = await _frm_editor(pid)
    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except Exception:
        pass
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("frm_done:"))
async def frm_done(callback: CallbackQuery, state: FSMContext):
    if not await _cb_ok(callback):
        return
    pid = int(callback.data.split(":", 1)[1])
    await state.clear()
    text, kb = await _mb_detail(pid)
    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except Exception:
        pass
    await callback.answer()
