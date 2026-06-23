# O'zgarishlar tarixi

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
