"""Template helpers for Asset Analytics & BI currency and signed number formatting."""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django import template

register = template.Library()

ZERO = Decimal("0")


def _currency_prefix(currency):
    """Return display symbol/prefix for an accounting.Currency object or fallback '$'."""
    if currency is None:
        return "$"
    if isinstance(currency, str):
        val = currency.strip()
        return f"{val} " if (len(val) > 1 and val.isalpha()) else (val or "$")
    symbol = (getattr(currency, "symbol", "") or "").strip()
    if symbol:
        return symbol
    code = (getattr(currency, "code", "") or "").strip()
    if code:
        return f"{code} " if code.isalpha() else code
    return "$"


@register.simple_tag
def fmt_money(amount, currency=None, decimals=2, negate=False):
    """Format an amount with dynamic currency prefix and leading minus sign (e.g. -$1,234.56)."""
    if amount is None or amount == "":
        dec = ZERO
    else:
        try:
            dec = amount if isinstance(amount, Decimal) else Decimal(str(amount))
        except (InvalidOperation, ValueError, TypeError):
            dec = ZERO

    if negate:
        dec = -dec

    dp = max(0, int(decimals))
    quant = Decimal("1") if dp == 0 else Decimal(f"1.{'0' * dp}")
    dec = dec.quantize(quant, rounding=ROUND_HALF_UP)
    if dec == ZERO:
        dec = ZERO  # normalize -0.00 to 0.00
    sign = "-" if dec < ZERO else ""
    formatted = f"{abs(dec):,.{dp}f}"
    prefix = _currency_prefix(currency)
    return f"{sign}{prefix}{formatted}"
