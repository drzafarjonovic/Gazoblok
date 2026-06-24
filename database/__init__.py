"""
database paketi — ilgari bitta 2000+ qatorli database.py edi.

Endi mantiqiy submodullarga bo'lingan:
  • core      — pool, kesh, birlik konversiyasi, rol/permission ta'riflari, init_db, migratsiya
  • users     — foydalanuvchilar, rol/permission, audit, lifecycle, PIN, stats
  • materials — xom ashyo ombori, minimum chegara, material narxlari
  • products  — mahsulot/blok/shablon/formula, tayyor mahsulot, tannarx
  • production — ishlab chiqarish (atomik)
  • sales     — sotuv (atomik) + inventarizatsiya
  • reports   — hisobot agregatlari + hisobot obunachilari
  • settings  — bot sozlamalari, tarjimalar keshi, valyuta kurslari

Barcha public nomlar shu yerda re-export qilinadi, shuning uchun mavjud
`import database as db; db.get_user(...)` chaqiruvlari o'zgarishsiz ishlaydi.
"""
from .core import *        # noqa: F401,F403
from .users import *       # noqa: F401,F403
from .materials import *   # noqa: F401,F403
from .products import *    # noqa: F401,F403
from .production import *  # noqa: F401,F403
from .sales import *       # noqa: F401,F403
from .reports import *     # noqa: F401,F403
from .settings import *    # noqa: F401,F403
