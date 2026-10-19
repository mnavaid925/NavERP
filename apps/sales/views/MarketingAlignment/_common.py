"""Sales 8.13 — shared helpers for the MarketingAlignment view modules.

Kept at the sub-module level (not in `apps/sales/views/_helpers.py`) because it is used only
by 8.13's own entity modules, and it is the sub-module's analogue of `forms/_common.py`.
"""
from apps.sales.views._common import *  # noqa: F401,F403

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
