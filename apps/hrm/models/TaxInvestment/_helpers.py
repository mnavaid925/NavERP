"""HRM 3.16 Tax & Investment — _helpers models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


def _progressive_tax(taxable, bands):
    """Sum bracket-by-bracket tax over ``bands`` = ordered iterable of
    ``(income_from, income_to_or_None, rate_percent)`` Decimals (a top band has ``income_to=None``)."""
    tax = ZERO
    for lo, hi, rate in bands:
        if taxable <= lo:
            break
        upper = taxable if hi is None else min(taxable, hi)
        tax += (upper - lo) * rate / Decimal("100")
    return tax.quantize(Decimal("0.01"))
