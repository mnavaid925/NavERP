"""Shared private helpers for the 8.12 Sales Analytics views package.

These are used by MORE THAN ONE entity in this sub-module (all four list views filter
on integer foreign keys), so they live here rather than being duplicated in each
entity module.

``_pk_filter`` guards the integer FK filters on every 8.12 list view.
"""
from apps.core.crud import as_db_int


def _pk_filter(value):
    """Return the int pk a GET parameter names, or ``None`` when it is junk.

    Delegates to the house helper ``apps.core.crud.as_db_int``, which closes all
    three holes at once (L11 / I12):

    * ``?x=abc`` — a non-numeric value is refused;
    * ``?x=999999999999999999999`` — a value wider than a 64-bit column converts
      cleanly and then 500s inside the database driver, so it is refused too;
    * ``?x=²`` / ``?x=①`` — ``str.isdigit()`` returns ``True`` for superscript and
      circled digits that ``int()`` refuses, so a bare ``isdigit()`` guard raises
      ``ValueError`` and 500s the page. ``as_db_int`` uses ``isdecimal()``, which
      rejects them.

    Such a value can never match a real pk, so it is **ignored** rather than
    allowed to raise — the 8.12 smoke gate requires
    ``?opportunity=999999999999999999999`` to render, not to 500.
    """
    return as_db_int(value)
