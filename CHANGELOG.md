# O'zgarishlar tarixi

## v2.1.0

Qulaylik (UX) yangilanishi — barcha imkoniyatlar saqlangan holda ishlatish ancha qulay qilindi.

### Yangi
- **📖 Qo'llanma bo'limi** — bot ichida inline navigatsiyali to'liq yo'riqnoma (11 mavzu: boshlash, mahsulot sozlash, ishlab chiqarish, sotuv, ombor, tayyor mahsulot/inventarizatsiya, narx/tannarx, hisobotlar, foydalanuvchilar, PIN, til). Har bir menyuda `❓ Qo'llanma` tugmasi.

### Yaxshilanishlar
- **ID/raqam yozish yo'qoldi.** Ombor kirimida material va birlik, shuningdek materialni tahrirlash/o'chirish endi inline tugmalardan tanlanadi — faqat haqiqiy son yoziladi.
- **O'chirishda tasdiqlash.** Material, blok va shablonni o'chirishda «Ha/Yo'q» so'raladi (tasodifan o'chirib yuborishning oldi olinadi).
- **Sozlamalar menyusi guruhlandi.** 12 ta tekis tugma o'rniga bo'limlar; «Materiallar» alohida ichki menyuda, «⬅️ Sozlamalar» bilan qaytish.
- **Narx, minimum chegara va formulani tanlab tahrirlash.** Material narxlari, minimum chegaralar va mahsulot formulasi endi hammasini ketma-ket so'ramaydi — kerakli materialni tugmadan tanlab o'zgartirasiz (formuladan olib tashlash ham mumkin).
- Inline oqimlarda «❌ Bekor» tugmasi va alohida ruxsat tekshiruvi.

## v2.0.0

Bu yirik versiya — bot **bitta mahsulot (gazoblok)** dan **to'liq dinamik ko'p-mahsulotli** ishlab chiqarish boshqaruv tizimiga o'tdi.

### Yangi imkoniyatlar
- **To'liq dinamik mahsulotlar.** Kodda hech qanday mahsulot/blok/shablon qattiq yozilmagan. Admin bot ichidan istalgancha mahsulot yaratadi, tahrirlaydi va arxivlaydi.
- **Mahsulot boshqaruvi** (⚙️ Sozlamalar → 🏭 Mahsulot boshqaruvi):
  - Mahsulot qo'shish / nomini o'zgartirish / arxivlash
  - Blok turlari (kod, nomi, o'lcham, 1 qolipdagi dona)
  - Shablonlar — har shablon qaysi blokdan nechtadan beradi (dinamik chiqim)
  - Qolip formulasi (har mahsulotga alohida, umumiy ombordan)
- **Mahsulotga xos narxlar** (💵 Narxlar → 🏷 Mahsulot narxlari): sotuv narxi, ish haqi, qo'shimcha xarajat, tannarx override.
- **Avtomatik tannarx:** material qismi formuladan + ish haqi + qo'shimcha; 1 blok = qolip tannarxi ÷ qolip dona (yoki override).
- **Mahsulot bo'yicha hisobotlar:** Hammasi yoki aniq mahsulot; Excel/CSV/PDF/grafik dinamik bloklar bilan.
- Ishlab chiqarish / sotuv / tayyor mahsulot / inventarizatsiya — mahsulot tanlash bilan.

### Xavfsizlik
- **PIN inline keypad.** PIN endi chatga matn sifatida yozilmaydi (raqamli inline klaviatura), kiritilgan raqamlar maskalanadi.
- Bot qulflanganda foydalanuvchi yozgan matn avtomatik o'chiriladi (chatda iz qolmaydi).

### Tezlik (performans)
- Foydalanuvchi, sozlama, huquq va mahsulot ta'riflari uchun xotira keshi (har-xabar DB aylanishlari ~0 ga tushdi).
- `touch_user` yozuvi cheklandi (har xabarda emas).
- N+1 so'rovlar yo'qotildi (shablonlar, bugungi ishlab chiqarish).
- Tannarx xaritasi to'plamli so'rov + kesh bilan hisoblanadi.
- Hisobotlardagi mustaqil so'rovlar parallel (asyncio.gather).
- DB indekslari qo'shildi (sana/mahsulot bo'yicha so'rovlar uchun).

### Migratsiya
- Mavjud gazoblok ma'lumotlari (A/B bloklar, 3 shablon, narxlar, butun tarix) bot birinchi ishga tushganda avtomatik **"Gazoblok"** mahsulotiga ko'chiriladi. Hech narsa yo'qolmaydi (idempotent).
