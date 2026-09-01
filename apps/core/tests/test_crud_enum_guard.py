"""The ``crud_list`` junk-value guards — an unusable filter value is IGNORED, never applied.

Two of them share this file because they are the same bug in two shapes: an unrecognised CHOICES
value (the enum guard, below) and a pk of 0 (the zero-pk guard, at the end). Both parse cleanly,
both narrow to zero rows, and both empty a register that should have rendered in full.

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

from apps.core.crud import _enum_values, _is_pk_lookup, crud_list
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


# -- the zero-pk guard -----------------------------------------------------------------------------
# The same L11 shape one field over, and the reason this file grew a second section. `?vendor=0` is
# decimal AND inside the column's range, so ``as_db_int`` hands it straight through, and
# ``.filter(vendor_id=0)`` then matches nothing and silently EMPTIES the register — for a value
# anyone can type into the address bar. An AutoField starts at 1, so 0 can never BE a pk. It is
# junk, and junk is ignored. But only for a PK lookup: 0 is a real value for a plain int column,
# which is why the guard is keyed on the lookup name rather than on the number.

@pytest.mark.parametrize("lookup", ["pk", "id", "vendor_id", "invoice_id", "assigned_to_id"])
def test_core_is_pk_lookup_recognises_a_primary_key_lookup(lookup):
    assert _is_pk_lookup(lookup) is True


@pytest.mark.parametrize("lookup", ["year", "is_active", "quantity", "discount_grace_days"])
def test_core_is_pk_lookup_leaves_a_plain_int_column_alone(lookup):
    """``?year=`` (hrm leave allocations) and ``?active=`` (procurement clauses) are the app's two
    non-pk int filters — 0 is a legitimate value for both, so neither may be swallowed."""
    assert _is_pk_lookup(lookup) is False


class _CoreRecordingQuerySet(list):
    """The smallest thing ``crud_list`` can drive — it records every ``.filter()`` it is handed.

    A ``list`` subclass so ``Paginator`` can count and slice it, which keeps these tests DB-free
    like the rest of the file while still exercising the real ``crud_list`` loop rather than a
    reimplementation of it.
    """

    model = SupplierInvoice

    def __init__(self, *rows):
        super().__init__(rows)
        self.filters = []

    def filter(self, **kwargs):
        self.filters.append(kwargs)
        return self


def test_core_crud_list_skips_a_zero_pk_but_keeps_a_zero_on_a_plain_int(monkeypatch, rf):
    """Both sides of the guard in ONE request: ``?vendor=0`` is dropped, ``?year=0`` is applied."""
    monkeypatch.setattr("apps.core.crud.render", lambda request, template, ctx: ctx)
    qs = _CoreRecordingQuerySet(object())

    ctx = crud_list(rf.get("/", {"vendor": "0", "year": "0"}), qs, "unused.html",
                    filters=[("vendor", "vendor_id", True), ("year", "year", True)])

    assert qs.filters == [{"year": 0}]
    # ...and the register still renders its rows rather than an empty page.
    assert list(ctx["page_obj"].object_list) == list(qs)


def test_core_crud_list_still_narrows_on_a_real_pk(monkeypatch, rf):
    """The guard suppresses 0 and nothing else — a genuine pk must still narrow."""
    monkeypatch.setattr("apps.core.crud.render", lambda request, template, ctx: ctx)
    qs = _CoreRecordingQuerySet(object())

    crud_list(rf.get("/", {"vendor": "7"}), qs, "unused.html",
              filters=[("vendor", "vendor_id", True)])

    assert qs.filters == [{"vendor_id": 7}]
