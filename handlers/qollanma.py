from aiogram import Router
from aiogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery,
)
from translation import Tkey, say, t, foydalanuvchi_tili, tarjima_qil, register_ui

router = Router()

# Qo'llanma bo'limlari: kalit -> (sarlavha, matn)
BOLIMLAR = {
    "boshlash": (
        "🚀 Boshlash (birinchi sozlash)",
        "🚀 BIRINCHI SOZLASH\n\n"
        "Botni ishlatishdan oldin quyidagilarni bir marta sozlang:\n\n"
        "1️⃣ ⚙️ Sozlamalar → ➕ Material qo'shish\n"
        "   Ombordagi barcha xom ashyolarni kiriting (sement, qum, suv...).\n\n"
        "2️⃣ ⚙️ Sozlamalar → 🏭 Mahsulot boshqaruvi → ➕ Yangi mahsulot\n"
        "   Mahsulot yarating (masalan «Gazoblok» yoki «Polistirol blok»).\n\n"
        "3️⃣ O'sha mahsulot ichida:\n"
        "   • 🧱 Bloklar — qanday bloklar chiqishini qo'shing\n"
        "   • 📦 Shablonlar — har shablon nechtadan blok berishini kiriting\n"
        "   • 📋 Formula — 1 qolipga ketadigan materiallarni kiriting\n\n"
        "4️⃣ 💵 Narxlar va valyuta → 🏷 Mahsulot narxlari\n"
        "   Sotuv narxi, ish haqi va qo'shimcha xarajatni kiriting.\n\n"
        "✅ Tayyor! Endi ishlab chiqarish va sotuvni kiritishingiz mumkin."
    ),
    "mahsulot": (
        "🏭 Mahsulot sozlash",
        "🏭 MAHSULOT BOSHQARUVI\n"
        "(⚙️ Sozlamalar → 🏭 Mahsulot boshqaruvi)\n\n"
        "Bu yerda har bir mahsulotni to'liq o'zingiz sozlaysiz:\n\n"
        "🧱 BLOKLAR — mahsulotdan qanday bloklar chiqadi:\n"
        "   • kod (qisqa belgi, masalan P yoki A)\n"
        "   • nomi va o'lchami (masalan 30×60×20)\n"
        "   • «1 qolipdagi dona» — tannarx uchun (1 blok = qolip tannarxi ÷ shu son)\n\n"
        "📦 SHABLONLAR — 1 qolipdan nima chiqadi:\n"
        "   Har shablon uchun har blokdan nechtadan chiqishini kiritasiz\n"
        "   (masalan «11×A + 2×B», yoki «30×P»). Cheklov yo'q.\n\n"
        "📋 FORMULA — 1 qolipga ketadigan materiallar (umumiy ombordan).\n\n"
        "💡 Mahsulotni arxivlash mumkin — tarix saqlanadi, ro'yxatdan yashiriladi."
    ),
    "ishlab": (
        "📥 Ishlab chiqarish",
        "🏭 ISHLAB CHIQARISH\n\n"
        "📥 Ishlab chiqarishni kiritish:\n"
        "   1. Mahsulotni tanlang (bitta bo'lsa avtomatik)\n"
        "   2. Shablonni tanlab, nechta qolip quyilganini kiriting\n"
        "   3. Bir necha shablon qo'shsangiz ham bo'ladi\n"
        "   4. ✅ Tayyor — Saqlash\n\n"
        "Tizim avtomatik: materiallarni ombordan yechadi, tayyor mahsulotga "
        "bloklarni qo'shadi va sarfni yozadi.\n\n"
        "📋 Bugungi ishlab chiqarish — bugungi yakuniy hisob.\n"
        "🗑️ Oxirgi yozuvni o'chirish — xato kiritsangiz, materiallar va "
        "bloklar avtomatik qaytariladi.\n\n"
        "⚠️ Material yetmasa, tizim ogohlantiradi va kiritishga yo'l qo'ymaydi."
    ),
    "sotuv": (
        "💰 Sotuv",
        "💰 SOTUV\n\n"
        "💰 Sotuv kiritish:\n"
        "   1. Mahsulotni tanlang\n"
        "   2. Blok turini tanlang\n"
        "   3. Nechta sotilganini kiriting\n\n"
        "Tizim mavjud qoldiqdan ortiq sotishga yo'l qo'ymaydi. Sotuv narxi "
        "o'sha paytdagi narxda saqlanadi (tarixiy aniqlik uchun).\n\n"
        "📋 Bugungi sotuv — bugungi yakun.\n"
        "🗑️ Oxirgi sotuvni o'chirish — mahsulot omborga qaytariladi."
    ),
    "ombor": (
        "🏪 Ombor",
        "🏪 OMBOR (xom ashyo)\n\n"
        "📥 Xom ashyo kirim — yangi kelgan materialni qo'shing "
        "(materialni tugmadan tanlab, miqdor va birlikni kiriting).\n\n"
        "🏪 Joriy qoldiqlar — barcha materiallar qoldig'i. Minimal chegaradan "
        "past bo'lsa ⚠️ belgi chiqadi.\n\n"
        "💡 Birlik avtomatik o'giriladi (kg, tonna, litr, m³, meshok...). "
        "Material o'lchamiga mos birlik kiriting."
    ),
    "tayyor": (
        "🏬 Tayyor mahsulot va inventarizatsiya",
        "🏬 TAYYOR MAHSULOT\n"
        "   📦 Qoldiq — barcha mahsulot bloklari soni.\n"
        "   ✏️ Dastlabki qoldiq — boshlang'ich sonni kiritish.\n\n"
        "📋 INVENTARIZATSIYA\n"
        "   Real (qo'lda sanagan) sonni kiritasiz, tizim bot hisobi bilan "
        "farqni ko'rsatadi va bot hisobini real songa moslaydi.\n"
        "   📋 Tarix — barcha inventarizatsiyalar."
    ),
    "narx": (
        "💵 Narx va tannarx",
        "💵 NARXLAR VA VALYUTA\n\n"
        "💱 Valyuta — narxlarni qaysi valyutada kiritish/ko'rish (ichkarida "
        "so'mda saqlanadi). Onlayn kurs yoki qo'lda kurs.\n\n"
        "📦 Material narxlari — har materialning 1 birlik narxi.\n\n"
        "🏷 Mahsulot narxlari (mahsulotni tanlab):\n"
        "   • 🧱 Sotuv narxlari (har blok)\n"
        "   • 👷 Ish haqi (1 qolipga)\n"
        "   • 🛠 Qo'shimcha xarajat (1 qolipga)\n"
        "   • 🎯 Tannarx override (qo'lda, 0 = avtomatga qaytarish)\n\n"
        "📐 TANNARX AVTOMATIK:\n"
        "   1 qolip = materiallar (formuladan) + ish haqi + qo'shimcha\n"
        "   1 blok = 1 qolip tannarxi ÷ «1 qolipdagi dona»"
    ),
    "hisobot": (
        "📊 Hisobotlar",
        "📊 HISOBOTLAR\n\n"
        "Avval mahsulot (yoki «Hammasi»), so'ng davrni tanlaysiz.\n\n"
        "   📊 Umumiy / Tafsilotli — ishlab chiqarish, sotuv, qoldiq\n"
        "   💰 Moliya — daromad, tannarx (COGS), sof foyda\n"
        "   👷 Ishchilar — kim qancha ishlab chiqardi/sotdi\n"
        "   🧱 Material sarfi\n"
        "   📈 Taqqoslash — oldingi davr bilan\n"
        "   📉 Grafiklar\n"
        "   📥 Excel / 📄 CSV / 📄 PDF eksport\n\n"
        "🔔 Avtomatik hisobot: ⚙️ Sozlamalar → 🔔 Hisobot jadvali "
        "(kunlik/haftalik/oylik vaqt va obunachilar)."
    ),
    "users": (
        "👥 Foydalanuvchilar va huquqlar",
        "👥 FOYDALANUVCHILAR\n\n"
        "Yangi odam /start bossa, so'rovi adminга keladi — tasdiqlaysiz yoki "
        "rad etasiz. Rol berasiz (Direktor, Omborchi, Ishchi, Sotuvchi, "
        "Hisobchi).\n\n"
        "🔐 Huquqlar boshqaruvi — har rolga yoki aniq foydalanuvchiga kerakli "
        "bo'limlarni yoqish/o'chirish. Individual huquq roldan ustun turadi.\n\n"
        "👑 Super Admin — barcha imkoniyatlarga ega; superadminlikni boshqa "
        "kishiga o'tkazishi mumkin."
    ),
    "pin": (
        "🔒 PIN xavfsizlik",
        "🔒 PIN KOD\n"
        "(⚙️ Sozlamalar → 🔒 PIN kod)\n\n"
        "Nofaollikdan so'ng bot qulflanadi va ochish uchun PIN so'raydi. PIN "
        "raqamli tugmalar orqali kiritiladi — chatda ko'rinmaydi, xavfsiz.\n\n"
        "   🔑 PIN o'rnatish — yangi PIN (4–8 raqam)\n"
        "   ⏱ Qulflanish vaqti — necha daqiqa nofaollikdan keyin\n"
        "   🔓 PIN o'chirish — qulfni o'chirish"
    ),
    "til": (
        "🌐 Til",
        "🌐 TIL\n\n"
        "/til buyrug'i yoki ⚙️ Sozlamalar → 🌐 Tilni o'zgartirish orqali har "
        "kim o'z tilini tanlaydi: o'zbek, ingliz, rus, arab, turk, xitoy, "
        "nemis.\n\n"
        "Barcha tugma va xabarlar tanlangan tilda ko'rsatiladi."
    ),
}


# Pre-warm uchun sarlavhalarni ro'yxatga olamiz
register_ui("❓ Qo'llanma", "📖 Qo'llanma — mavzuni tanlang:", "⬅️ Orqaga")
register_ui(*[s for s, _ in BOLIMLAR.values()])


async def _menu_kb(user_id):
    """Mavzular ro'yxati (inline)."""
    til = await foydalanuvchi_tili(user_id)
    kb = []
    row = []
    for kalit, (sarlavha, _) in BOLIMLAR.items():
        matn = sarlavha if til == "uz" else await tarjima_qil(sarlavha, til)
        row.append(InlineKeyboardButton(text=matn, callback_data=f"qn:{kalit}"))
        if len(row) == 1:  # har qatorda 1 ta (uzun sarlavhalar)
            kb.append(row)
            row = []
    if row:
        kb.append(row)
    return InlineKeyboardMarkup(inline_keyboard=kb)


@router.message(Tkey("❓ Qo'llanma"))
async def qollanma(message: Message):
    await say(
        message,
        "📖 Qo'llanma — mavzuni tanlang:",
        reply_markup=await _menu_kb(message.from_user.id),
    )


@router.callback_query(lambda c: c.data and c.data.startswith("qn:"))
async def qollanma_cb(callback: CallbackQuery):
    kalit = callback.data.split(":", 1)[1]
    user_id = callback.from_user.id

    if kalit == "menu":
        matn = await t("📖 Qo'llanma — mavzuni tanlang:", user_id)
        try:
            await callback.message.edit_text(matn, reply_markup=await _menu_kb(user_id))
        except Exception:
            pass
        await callback.answer()
        return

    bolim = BOLIMLAR.get(kalit)
    if not bolim:
        await callback.answer()
        return

    matn = await t(bolim[1], user_id)
    orqaga = await t("⬅️ Orqaga", user_id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=orqaga, callback_data="qn:menu")]
    ])
    try:
        await callback.message.edit_text(matn, reply_markup=kb)
    except Exception:
        pass
    await callback.answer()
