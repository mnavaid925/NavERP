"""Sales 8.13 — shared helpers for the MarketingAlignment view modules.

Kept at the sub-module level (not in `apps/sales/views/_helpers.py`) because it is used only
by 8.13's own entity modules, and it is the sub-module's analogue of `forms/_common.py`.
"""
from apps.sales.views._common import *  # noqa: F401,F403

from apps.accounting.models import Currency

# A Django primary key is a 64-bit signed integer. A GET parameter is arbitrary text, and
# `.isdigit()` alone is NOT enough to make it safe:
#
#     "?campaign=999999999999999999999"  ->  isdigit() is True  ->  int() succeeds
#     ->  the DB driver raises OverflowError on SQLite
#         ("Python int too large to convert to SQLite INTEGER")  ->  a 500 on hostile input.
#
# The same value is harmless on MariaDB, so the bug hides in production and surfaces only
# under the SQLite test database. Anything outside the int64 range is therefore ignored and
# the filter falls back to the unfiltered list, which is the same outcome as an unknown id.
MAX_PK = 2**63 - 1
MIN_PK = -(2**63)


def pk_from_param(value):
    """Return an int pk for a GET parameter, or None when it cannot possibly be one.

    None means "do not filter by this parameter" -- an empty value, a non-numeric value, or
    a value outside the int64 range. It never raises.
    """
    if value in (None, ""):
        return None
    try:
        pk = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    if pk < MIN_PK or pk > MAX_PK:
        return None
    return pk


def enum_filter(qs, request, param, field, choices):
    """Filter a queryset by a closed-vocabulary GET parameter.

    A GET parameter is arbitrary text, so `?status=bogus` must not narrow the register to a
    value no row can hold: the list would render EMPTY with all-zero stat cards, because the
    stats are computed over the filtered queryset. An unknown value therefore narrows NOTHING
    and the page falls back to the unfiltered list -- the same outcome as an empty parameter.

    Returns `(raw_value, queryset)`. The RAW value is returned (not the sanitised one) so the
    template's `active_filters` still reflects exactly what the user asked for.
    """
    value = request.GET.get(param, "").strip()
    if value and value in {code for code, _label in choices}:
        qs = qs.filter(**{field: value})
    return value, qs


def avg_response_hours(queryset):
    """Mean hours between the handoff and the sales response, over the ANSWERED handoffs.

    Returns None when nothing has been answered yet.

    The mean is computed in Python rather than as a SQL duration expression on purpose: a
    portable duration expression differs between MySQL/MariaDB and SQLite, and this runs on
    both. The responded subset is bounded by real sales activity, not by the row count of the
    table.
    """
    response_pairs = list(
        queryset.filter(responded_at__isnull=False).values_list("responded_at", "handoff_at")
    )
    response_hours = [
        (responded - handed).total_seconds() / 3600
        for responded, handed in response_pairs
        if responded is not None and handed is not None
    ]
    if not response_hours:
        return None
    return round(sum(response_hours) / len(response_hours), 2)


def single_currency(queryset, field="currency"):
    """The ONE currency the rows are denominated in, or None when that is not unambiguous.

    A page total is a sum over rows. Adding euros to dollars is meaningless, so a symbol is
    only shown when EVERY row uses the SAME currency; when the rows are mixed (or have no
    currency at all) the total is rendered without a symbol rather than mislabelled.

    `field` is the path to the currency FK, e.g. "currency" or "touchpoint__currency" for a
    model that carries it on its parent.
    """
    currency_ids = set(
        queryset.exclude(**{f"{field}__isnull": True}).values_list(
            f"{field}_id", flat=True
        )
    )
    if len(currency_ids) != 1:
        return None
    return Currency.objects.filter(pk=currency_ids.pop()).first()
