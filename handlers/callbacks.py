"""
Markazlashtirilgan callback_data prefikslari (CB).

MUAMMO: ilgari callback_data qatorlari ("mb_open", "pr_ov", "wh_mat" ...)
butun loyiha bo'ylab tarqalган "sehrli qatorlar" edi — ularning ma'nosini
bilish qiyin va xato yozilsa tugma jim ishlamay qolardi.

YECHIM: barcha prefikslar shu yerda bitta joyda, izohlar bilan e'lon qilinadi.
Qiymatlar joriy ishlatilayotgan literal qatorlarga AYNAN teng — shuning uchun
ulardan foydalanish mavjud xulq-atvorni o'zgartirmaydi.

FOYDALANISH:
    from handlers.callbacks import CB
    # filtr:
    @router.callback_query(lambda c: c.data and c.data.startswith(CB.WH_MAT + ":"))
    # quruvchi:
    InlineKeyboardButton(text=..., callback_data=f"{CB.WH_MAT}:{material_id}")
"""


class CB:
    # ── Til tanlash / PIN (bot.py) ──
    TIL = "til_"          # til_<kod>  (masalan til_uz, til_zh-CN)
    PIN = "pin_"          # pin_d_<n>, pin_del, pin_ok
    SETPIN = "setpin_"    # setpin_d_<n>, setpin_del, setpin_ok (settings)
    SLANG = "slang_"      # sozlamalardagi til o'zgartirish (settings)

    # ── Foydalanuvchi onboarding (users.py / bot.py) ──
    APPROVE = "appr"      # appr:<uid>  — so'rovni tasdiqlash
    REJECT = "rej"        # rej:<uid>   — so'rovni rad etish
    SET_ROL = "setrol"    # setrol:<uid>:<rol> — onboardingda rol
    SET_ROL2 = "setrol2"  # setrol2:<uid>:<rol> — mavjud userga rol

    # ── Foydalanuvchi paneli (users.py) ──
    UVIEW = "uview"            # uview:<uid>
    UVIEW_LIST = "uview_list"  # ro'yxatga qaytish
    USR = "usr"                # usr:<action>:<uid>
    USR_CANCEL = "usrcancel"
    USR_BLOK_OK = "usrblokok"  # usrblokok:<uid>
    USR_SUPER_OK = "usrsuperok"  # usrsuperok:<uid>
    AUDIT_CSV = "auditcsv"

    # ── Huquqlar (permissions.py) ──
    PERM_USER = "permu"   # permu:<uid>
    PRM = "prm"           # prm:r|u:<target>[:perm]

    # ── Ombor (warehouse.py) ──
    WH_CANCEL = "wh_cancel"
    WH_MAT = "wh_mat"     # wh_mat:<material_id>
    WH_UNIT = "wh_unit"   # wh_unit:<birlik>

    # ── Hisobot (reports.py) ──
    REP = "rep"           # rep:<rtype>:<pid>:<period>
    REP_PROD = "repp"     # repp:<rtype>:<pid|all>

    # ── Materiallar (settings.py) ──
    MAT_EDIT = "matedit"      # matedit:<mid>
    MAT_DEL = "matdel"        # matdel:<mid>
    MAT_DEL_NO = "matdelno"
    MAT_DEL_OK = "matdelok"   # matdelok:<mid>
    MINCH = "minch"           # minch:<mid>
    MINCH_DONE = "minch_done"
    MINCH_BACK = "minch_back"

    # ── Obunachilar (settings.py) ──
    OB_ADD = "obadd"      # obadd:<uid>
    OB_DEL = "obdel"      # obdel:<uid>
    OB_DONE = "ob_done"

    # ── Mahsulot boshqaruvi (settings.py) ──
    MB = "mb_"            # mb_open, mb_blk, mb_shb, mb_frm, mb_arch, mb_add ...
    MB_ROOT = "mb_root"
    MB_OPEN = "mb_open"
    MB_BLK = "mb_blk"
    MB_SHB = "mb_shb"
    MB_FORMULA = "mb_frm"
    MB_ARCHIVE = "mb_arch"
    MB_RENAME = "mb_ren"
    MB_ADD = "mb_add"
    MB_BLK_ADD = "mb_blkadd"
    MB_BLK_DEL = "mb_blkdel"
    MB_BLK_DEL_OK = "mb_blkdelok"
    MB_SHB_ADD = "mb_shbadd"
    MB_SHB_DEL = "mb_shbdel"
    MB_SHB_DEL_OK = "mb_shbdelok"

    # ── Formula (settings.py) ──
    FRM = "frm"           # frm:<pid>:<mid>
    FRM_UNIT = "frmunit"  # frmunit:<birlik>
    FRM_DEL = "frm_del"   # frm_del:<pid>:<mid>
    FRM_BACK = "frm_back"  # frm_back:<pid>
    FRM_DONE = "frm_done"  # frm_done:<pid>

    # ── Narxlar (prices.py) ──
    CUR = "cur_"          # cur_<KOD>
    MNARX = "mnarx"       # mnarx:<mid>
    MNARX_DONE = "mnarx_done"
    MNARX_BACK = "mnarx_back"
    PR = "pr_"            # pr_root, pr_p, pr_sn, pr_ov, pr_ish, pr_qsh

    # ── Qo'llanma (qollanma.py) ──
    QN = "qn"             # qn:<kalit>

    # ════════════════════════════════════════════════════════════════
    # Inline navigatsiya (v2.2) — operational flows.
    # Prefikslar boshqalardan farqli: production=pd, sales=sl,
    # finished=fg, inventory=iv (prices pr_ bilan to'qnashmasligi uchun).
    # ════════════════════════════════════════════════════════════════
    # Ishlab chiqarish (production.py)
    PD_ROOT = "pd_root"
    PD_INPUT = "pd_in"
    PD_TODAY = "pd_today"
    PD_DELLAST = "pd_dellast"
    PD_PROD = "pd_prod"        # pd_prod:<pid>
    PD_TPL = "pd_tpl"          # pd_tpl:<sid>
    PD_BOARD = "pd_board"      # holatga qaytish
    PD_SAVE = "pd_save"
    PD_CANCEL = "pd_cancel"
    PD_DELPROD = "pd_delp"     # pd_delp:<pid>
    PD_DELOK = "pd_delok"      # pd_delok:<pid>

    # Sotuv (sales.py)
    SL_ROOT = "sl_root"
    SL_INPUT = "sl_in"
    SL_TODAY = "sl_today"
    SL_DELLAST = "sl_dellast"
    SL_PROD = "sl_prod"        # sl_prod:<pid>
    SL_BLK = "sl_blk"          # sl_blk:<index>
    SL_CANCEL = "sl_cancel"
    SL_DELPROD = "sl_delp"     # sl_delp:<pid>
    SL_DELOK = "sl_delok"      # sl_delok:<pid>

    # Tayyor mahsulot (finished_goods.py)
    FG_ROOT = "fg_root"
    FG_QOLDIQ = "fg_q"
    FG_EDIT = "fg_edit"
    FG_PROD = "fg_prod"        # fg_prod:<pid>
    FG_BLK = "fg_blk"          # fg_blk:<index>
    FG_CANCEL = "fg_cancel"

    # Inventarizatsiya (inventory.py)
    IV_ROOT = "iv_root"
    IV_INPUT = "iv_in"
    IV_HIST = "iv_hist"
    IV_PROD = "iv_prod"        # iv_prod:<pid>
    IV_BLK = "iv_blk"          # iv_blk:<index>
    IV_CANCEL = "iv_cancel"

    # Ombor (warehouse.py) — menyu
    WH_ROOT = "wh_root"
    WH_INPUT = "wh_in"
    WH_STOCK = "wh_stock"

    # Hisobot (reports.py) — sub-menyu navigatsiya
    REP_MENU = "repmenu"       # repmenu:<bo'lim>

    # Foydalanuvchilar (users.py) — sub-menyu navigatsiya
    USR_MENU = "usrmenu"       # usrmenu:<bo'lim>

    # Huquqlar (permissions.py) — sub-menyu navigatsiya
    PERM_MENU = "permmenu"     # permmenu:<bo'lim>

    # Sozlamalar (settings.py) — sub-menyu navigatsiya
    SET_MENU = "setmenu"       # setmenu:<bo'lim>
