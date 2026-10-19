"""Shared private helpers for the 8.12 Sales Analytics views package.

These are used by MORE THAN ONE entity in this sub-module (all four list views filter
on integer foreign keys), so they live here rather than being duplicated in each
entity module.

``MAX_PK`` / ``_pk_filter`` guard the integer FK filters on every 8.12 list view.
"""

#: The widest value a 64-bit signed integer column can hold (MySQL BIGINT / SQLite INTEGER).
MAX_PK = 2**63 - 1


def _pk_filter(value):
    """Return the int pk a GET parameter names, or ``None`` when it is junk.

    ``.isdigit()`` alone is not enough: a hand-edited URL can carry an integer wider
    than a 64-bit column, which raises ``OverflowError`` on SQLite and is rejected
    outright by MySQL. Such a value can never match a real pk, so it is **ignored**
    rather than allowed to raise (L11) — the 8.12 smoke gate requires
    ``?opportunity=999999999999999999999`` to render, not to 500.
    """
    if not value or not value.isdigit():
        return None
    parsed = int(value)
    if parsed > MAX_PK:
        return None
    return parsed
