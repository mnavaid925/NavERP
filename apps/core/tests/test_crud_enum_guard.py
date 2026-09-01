"""The ``crud_list`` enum guard — an unrecognised CHOICES value is IGNORED, never applied.

Why this file exists. ``crud_list`` already guarded the two *parseable* junk cases: an int FK via
``as_db_int`` (L11) and a BooleanField via the ``ValidationError`` raised inside ``.filter()``. An
unrecognised CHOICES value is neither — it is a plain string, so ``.filter(status="nope")`` raises
nothing and narrows nothing, matching zero rows and silently EMPTYING the register for a value
anyone can type into the address bar (a stale bookmark, a hand-edited URL, a renamed choice value).

The contract is not new: ``apps/scm/tests/test_security.py`` already asserted it by name
(``..._is_skipped_rather_than_matched``, ``..._falls_back_to_the_default_view_not_to_an_empty_page``).
It was simply implemented per-view and never centralized, so ~360 filter specs across 8 apps each had
to remember it. These tests pin the central behaviour.

The guard is deliberately narrow, and the bail-out cases matter as much as the guarded one: each
leaves the filter behaving exactly as it did before, so the only value the guard can ever suppress is
one that could not have matched a row anyway. A regression that widened it would silently disarm
real filters app-wide.

Scope note: this file unit-tests the HELPER only — no DB, no fixtures — because the request-level
behaviour is already asserted where the fixtures live, beside the registers it protects:
``apps/procurement/tests/test_spend_views.py`` (junk enum ignored **and** a valid enum still
narrows), ``apps/procurement/tests/test_receipt_views.py`` (discrepancy + RTV registers) and
``apps/scm/tests/test_security.py`` (the original contract).
"""
import pytest

from apps.core.crud import _enum_values
from apps.procurement.models import MaverickSpendFinding, SupplierInvoice
from apps.scm.models import PurchaseOrder


# -- the helper's contract ------------------------------------------------------------------------

def test_core_enum_values_returns_the_choice_set_for_a_plain_enum_field():
    values = _enum_values(MaverickSpendFinding, "reason")
    assert values is not None
    assert "no_contract" in values
    assert "nope" not in values
    # Every declared REASON_CHOICES value is present — the guard must never suppress a real one.
    assert values == {value for value, _ in MaverickSpendFinding.REASON_CHOICES}


@pytest.mark.parametrize("model,lookup,why", [
    (SupplierInvoice, "vendor__name", "a relation hop is out of scope"),
    (SupplierInvoice, "status__in", "a lookup suffix is out of scope"),
    (SupplierInvoice, "not_a_field_at_all", "an unresolvable field cannot be introspected"),
    (SupplierInvoice, "vendor", "an FK has no choices"),
    (MaverickSpendFinding, "is_addressable", "a BooleanField has no choices"),
    (MaverickSpendFinding, "detail", "a free-text field has no choices"),
])
def test_core_enum_guard_does_not_apply_and_leaves_the_filter_untouched(model, lookup, why):
    """Returning None means 'behave exactly as before' — these must never be guarded."""
    assert _enum_values(model, lookup) is None, why


def test_core_enum_guard_skips_an_int_valued_enum():
    """An int-valued enum belongs on the is_int path, where as_db_int already guards it.

    Comparing a raw GET string against int choices would suppress every legitimate value, so the
    helper bails out rather than half-guarding it.
    """
    for field in PurchaseOrder._meta.get_fields():
        choices = getattr(field, "choices", None)
        if choices and not all(isinstance(value, str) for value, _ in choices):
            assert _enum_values(PurchaseOrder, field.name) is None
            break
