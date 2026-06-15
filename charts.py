"""
Gazoblok Bot - Grafik moduli (matplotlib, Agg backend).
matplotlib o'rnatilmagan bo'lsa MATPLOTLIB=False bo'ladi va funksiyalar
None qaytaradi (bot ishlashda davom etadi).
"""
import io
import logging

logger = logging.getLogger("gazobot")

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    MATPLOTLIB = True
except Exception as e:  # pragma: no cover
    logger.warning("matplotlib mavjud emas: %r", e)
    MATPLOTLIB = False

_RANG_A = "#2E75B6"
_RANG_B = "#ED7D31"
_RANG_FOYDA = "#70AD47"


def _png(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def trend_chart(labels, qolip_vals, sotuv_vals, sarlavha="Trend"):
    """Ishlab chiqarish (qolip) va sotuv (dona) chiziqli grafigi."""
    if not MATPLOTLIB:
        return None
    try:
        fig, ax = plt.subplots(figsize=(9, 4.5))
        ax.plot(labels, qolip_vals, marker="o", color=_RANG_A, label="Ishlab chiqarish (qolip)")
        ax.plot(labels, sotuv_vals, marker="s", color=_RANG_B, label="Sotuv (dona)")
        ax.set_title(sarlavha)
        ax.grid(True, alpha=0.3)
        ax.legend()
        if len(labels) > 10:
            for lbl in ax.get_xticklabels():
                lbl.set_rotation(45)
                lbl.set_ha("right")
        return _png(fig)
    except Exception as e:
        logger.warning("trend_chart xato: %r", e)
        return None


def pie_chart(a, b, sarlavha="A / B"):
    """A va B taqsimoti (pie)."""
    if not MATPLOTLIB:
        return None
    if (a or 0) + (b or 0) <= 0:
        return None
    try:
        fig, ax = plt.subplots(figsize=(6, 5))
        ax.pie(
            [a, b],
            labels=[f"A ({a})", f"B ({b})"],
            colors=[_RANG_A, _RANG_B],
            autopct="%1.1f%%",
            startangle=90,
        )
        ax.set_title(sarlavha)
        ax.axis("equal")
        return _png(fig)
    except Exception as e:
        logger.warning("pie_chart xato: %r", e)
        return None


def finance_bar(labels, rev_vals, profit_vals, valyuta="so'm", sarlavha="Daromad va foyda"):
    """Kunlik daromad va foyda ustun grafigi."""
    if not MATPLOTLIB:
        return None
    if not labels:
        return None
    try:
        import numpy as np
        x = np.arange(len(labels))
        w = 0.4
        fig, ax = plt.subplots(figsize=(9, 4.5))
        ax.bar(x - w / 2, rev_vals, w, color=_RANG_A, label="Daromad")
        ax.bar(x + w / 2, profit_vals, w, color=_RANG_FOYDA, label="Foyda")
        ax.set_title(f"{sarlavha} ({valyuta})")
        ax.set_xticks(x)
        ax.set_xticklabels(labels)
        ax.grid(True, axis="y", alpha=0.3)
        ax.legend()
        if len(labels) > 10:
            for lbl in ax.get_xticklabels():
                lbl.set_rotation(45)
                lbl.set_ha("right")
        return _png(fig)
    except Exception as e:
        logger.warning("finance_bar xato: %r", e)
        return None
