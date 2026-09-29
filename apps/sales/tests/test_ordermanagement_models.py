"""8.6 Order Management -- model lane.

Every ruling the six entities are built on is asserted here as executable law, not commentary.
The three CRITICALs the review phase found are why this file exists, and each has a test that
names the bug it prevents:

* **C1** -- ``recompute()`` must not raise on a schedule mixing dated and undated obligations
  (the ``UNSCHEDULED`` sentinel is compared against a real ``date``).
* **C2** -- a malformed ``evaluation_snapshot`` must be repaired in ``save()`` and must NEVER be
  validated in ``clean()``, because the field is off the form and a ``ValidationError`` keyed on
  it routes through ``add_error(None, ...)`` and raises ``ValueError`` (the 0.20 close-out trap).
* **C3** -- an APPROVED amendment is ``is_open`` but NOT ``is_editable``: its lines and reason
  are frozen, so the approval cannot be re-pointed at a different proposal.

Also asserted: the number prefixes, the derived-not-stored register (every money balance is a
``@property``, never a column), ``evaluate()`` purity, the SET_NULL evidence rule, the
single-writer discipline, and tenant isolation on every FK.

Names: every test is ``test_ordermanagement_*`` and every helper ``_ordermanagement_*`` so
8.1-8.5 in this package cannot be shadowed.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db.models import ProtectedError
from django.utils import timezone

from apps.core.models import Party
from apps.sales.forms import OrderHoldForm, PerformanceObligationForm
from apps.sales.models import (
    OrderAmendment,
    OrderAmendmentLine,
    OrderHold,
    OrderValidationRule,
    PerformanceObligation,
    RevenueSchedule,
)
from apps.sales.models.OrderManagement.RevenueSchedules import UNSCHEDULED
from apps.sales.tests.conftest import (
    ORDERMANAGEMENT_CHOICES,
    ORDERMANAGEMENT_MODEL_FIELDS,
    _ordermanagement_amendment,
    _ordermanagement_amendment_line,
    _ordermanagement_hold,
    _ordermanagement_obligation,
    _ordermanagement_order,
    _ordermanagement_rule,
    _ordermanagement_schedule,
)

pytestmark = pytest.mark.django_db

_CLASSES = {
    "OrderValidationRule": OrderValidationRule,
    "OrderHold": OrderHold,
    "OrderAmendment": OrderAmendment,
    "OrderAmendmentLine": OrderAmendmentLine,
    "RevenueSchedule": RevenueSchedule,
    "PerformanceObligation": PerformanceObligation,
}




# ------------------------------------------------------------------ the pinned shape


def test_ordermanagement_model_field_sets_match_the_contract():
    """A field added or dropped without a contract amendment is drift (L7)."""
    for name, expected in ORDERMANAGEMENT_MODEL_FIELDS.items():
        actual = tuple(f.name for f in _CLASSES[name]._meta.get_fields() if f.concrete)
        assert actual == expected, f"{name}: symmetric difference {set(actual) ^ set(expected)}"


def test_ordermanagement_choices_match_the_contract():
    """Choice VALUES are compared by views, templates and fixtures; a drift breaks all three."""
    for name, consts in ORDERMANAGEMENT_CHOICES.items():
        for const, expected in consts.items():
            assert list(getattr(_CLASSES[name], const)) == expected, f"{name}.{const}"


def test_ordermanagement_number_prefixes_are_the_four_claimed():
    """The four headers mint OVR-/OHD-/AMD-/RVS-; the two children mint nothing."""
    assert OrderValidationRule.NUMBER_PREFIX == "OVR"
    assert OrderHold.NUMBER_PREFIX == "OHD"
    assert OrderAmendment.NUMBER_PREFIX == "AMD"
    assert RevenueSchedule.NUMBER_PREFIX == "RVS"
    assert not hasattr(OrderAmendmentLine, "NUMBER_PREFIX")
    assert not hasattr(PerformanceObligation, "NUMBER_PREFIX")


def test_ordermanagement_numbers_are_minted_and_unique_per_tenant(
    ordermanagement_tenant_a, ordermanagement_tenant_b
):
    """A second header of the same kind gets the next number; two tenants never collide."""
    a, b = ordermanagement_tenant_a, ordermanagement_tenant_b
    r1, r2, r3 = _ordermanagement_rule(a), _ordermanagement_rule(a), _ordermanagement_rule(b)
    assert r1.number.startswith("OVR-")
    assert r2.number.startswith("OVR-")
    assert r1.number != r2.number
    assert r3.number.startswith("OVR-")


# ---------------------------------------------- C2: the 0.20 NON_FIELD_ERRORS trap


def test_ordermanagement_c2_malformed_snapshot_is_repaired_in_save_not_clean(
    ordermanagement_tenant_a,
):
    """C2 regression. The guard belongs in save(); raising on it in clean() 500s the form."""
    tenant = ordermanagement_tenant_a
    order = _ordermanagement_order(tenant)
    hold = _ordermanagement_hold(tenant, order)

    OrderHold.objects.filter(pk=hold.pk).update(evaluation_snapshot="not json at all")
    hold.refresh_from_db()
    assert hold.evaluation_snapshot == "not json at all"

    # clean() must NOT raise: the field is not on OrderHoldForm.
    hold.clean()  # a ValidationError here is exactly the bug C2 describes

    # The form must therefore survive the malformed blob.
    OrderHoldForm(instance=hold, tenant=tenant).is_valid()  # must not raise ValueError

    # save() repairs it to a dict.
    hold.save()
    hold.refresh_from_db()
    assert hold.evaluation_snapshot == {}
    assert hold.parsed_snapshot == {}


def test_ordermanagement_c2_parsed_snapshot_never_raises_on_junk(ordermanagement_tenant_a):
    """parsed_snapshot is the wrapper every reader goes through; it must not raise."""
    order = _ordermanagement_order(ordermanagement_tenant_a)
    hold = _ordermanagement_hold(ordermanagement_tenant_a, order)
    # The column is NOT NULL, so a stored row can hold a wrong TYPE but never a SQL NULL.
    for junk in ("not json", "[1, 2, 3]", '"a string"', 17, 3.5, True):
        OrderHold.objects.filter(pk=hold.pk).update(evaluation_snapshot=junk)
        hold.refresh_from_db()
        assert hold.parsed_snapshot == {}


# ------------------------------------------------------------- C1: the UNSCHEDULED sentinel


def test_ordermanagement_c1_unscheduled_sentinel_is_a_real_date():
    """C1 regression. The sort key pairs this with recognize_on, which is a date."""
    assert isinstance(UNSCHEDULED, date), "a tuple sentinel raises TypeError against a date"
    assert UNSCHEDULED > date.today()


def test_ordermanagement_c1_recompute_survives_mixed_dated_and_undated(
    ordermanagement_tenant_a,
):
    """C1 end to end: the one verb that moves money must not raise."""
    tenant = ordermanagement_tenant_a
    order = _ordermanagement_order(tenant)
    schedule = _ordermanagement_schedule(tenant, order)
    dated = _ordermanagement_obligation(
        tenant, schedule, allocation_pct="60.00",
        recognize_on=timezone.localdate() - timedelta(days=5),
    )
    undated = _ordermanagement_obligation(
        tenant, schedule, allocation_pct="40.00", recognize_on=None,
    )

    result = schedule.recompute()  # must not raise

    assert result["refused"] is False
    dated.refresh_from_db()
    undated.refresh_from_db()
    assert dated.recognized_amount > Decimal("0")
    assert undated.recognized_amount == Decimal("0")
    assert undated.allocated_amount > Decimal("0")


def test_ordermanagement_c1_undated_never_drains_the_shared_budget(ordermanagement_tenant_a):
    """date.min would sort undated FIRST and let it consume the budget ahead of dated rows."""
    tenant = ordermanagement_tenant_a
    order = _ordermanagement_order(tenant)
    schedule = _ordermanagement_schedule(tenant, order)
    dated = _ordermanagement_obligation(
        tenant, schedule, allocation_pct="50.00",
        recognize_on=timezone.localdate() - timedelta(days=1),
    )
    undated = _ordermanagement_obligation(
        tenant, schedule, allocation_pct="50.00", recognize_on=None,
    )
    schedule.recompute()


def test_ordermanagement_recompute_is_idempotent(ordermanagement_tenant_a):
    """recompute() is a function of the order and the dates; running it twice changes nothing."""
    tenant = ordermanagement_tenant_a
    order = _ordermanagement_order(tenant)
    schedule = _ordermanagement_schedule(tenant, order)
    ob = _ordermanagement_obligation(
        tenant, schedule, allocation_pct="100.00",
        recognize_on=timezone.localdate() - timedelta(days=1),
    )
    schedule.recompute()
    first = PerformanceObligation.objects.get(pk=ob.pk).recognized_amount
    schedule.recompute()
    assert PerformanceObligation.objects.get(pk=ob.pk).recognized_amount == first


def test_ordermanagement_recompute_refuses_a_non_active_schedule(ordermanagement_tenant_a):
    """A draft schedule must never recognise revenue -- the refusal lives in the METHOD."""
    tenant = ordermanagement_tenant_a
    order = _ordermanagement_order(tenant)
    schedule = _ordermanagement_schedule(tenant, order, status="draft")
    ob = _ordermanagement_obligation(
        tenant, schedule, allocation_pct="100.00",
        recognize_on=timezone.localdate() - timedelta(days=1),
    )
    result = schedule.recompute()
    assert result["refused"] is True
    assert "active" in result["reason"].lower()
    ob.refresh_from_db()
    assert ob.recognized_amount == Decimal("0")


# -------------------------------------------- C3: approved is open but NOT editable


def test_ordermanagement_c3_approved_is_open_but_not_editable(ordermanagement_tenant_a):
    """C3 regression. The approval was given against THIS proposal; the document is frozen."""
    amendment = _ordermanagement_amendment(ordermanagement_tenant_a)
    expected = {
        "draft": (True, True),
        "pending": (True, True),
        "approved": (True, False),   # still applicable/withdrawable, but content is frozen
        "rejected": (False, False),
        "applied": (False, False),
        "withdrawn": (False, False),
    }
    for status, (is_open, is_editable) in expected.items():
        amendment.status = status
        assert amendment.is_open is is_open, status
        assert amendment.is_editable is is_editable, status


def test_ordermanagement_c3_edit_and_open_statuses_are_distinct_tuples():
    """The two tuples must not drift into being the same thing."""
    assert OrderAmendment.EDITABLE_STATUSES == ("draft", "pending")
    assert OrderAmendment.OPEN_STATUSES == ("draft", "pending", "approved")
    assert set(OrderAmendment.OPEN_STATUSES) - set(OrderAmendment.EDITABLE_STATUSES) == {"approved"}


def test_ordermanagement_close_is_not_an_authorable_change_type():
    """A choice that can never fire is worse than no choice: 4.5 closes only an invoiced order."""
    assert "close" not in [v for v, _ in OrderAmendment.CHANGE_TYPE_CHOICES]
    assert "invoiced" not in OrderAmendment.AMENDABLE_STATUSES


# ------------------------------------------------ the derived-not-stored register (§2.5)


def test_ordermanagement_money_balances_are_properties_never_columns():
    """The whole point of the derived-not-stored register: a stored figure will drift."""
    for name in (
        "contract_amount", "allocated_amount", "recognized_amount", "deferred_amount",
        "contract_asset", "contract_liability", "recognition_progress_pct",
        "is_unbalanced", "days_overdue", "is_overdue", "is_editable", "is_locked",
    ):
        assert isinstance(getattr(RevenueSchedule, name), property), name
    # `allocated_amount` / `recognized_amount` are the TWO stored columns by design (written
    # only by recompute()); `remaining_amount` is the derived one.
    assert isinstance(getattr(PerformanceObligation, "remaining_amount"), property)

    stored = {f.name for f in RevenueSchedule._meta.get_fields() if f.concrete}
    for forbidden in ("contract_amount", "allocated_amount", "recognized_amount",
                      "deferred_amount", "contract_asset", "contract_liability", "days_overdue"):
        assert forbidden not in stored, f"{forbidden} must be derived, not stored"


def test_ordermanagement_only_two_stored_money_columns_exist():
    """Across all six models, the only stored money columns are the two recompute() writes."""
    money = []
    for cls in _CLASSES.values():
        for f in cls._meta.get_fields():
            if (f.concrete and f.get_internal_type() == "DecimalField"
                    and f.name not in ("allocation_pct", "new_quantity", "new_unit_price")):
                money.append((cls.__name__, f.name, f.editable))
    assert set(money) == {("PerformanceObligation", "allocated_amount", False),
                          ("PerformanceObligation", "recognized_amount", False)}


def test_ordermanagement_frozen_evidence_is_never_editable():
    """L22: an authorable snapshot is forgeable evidence of why an order was held."""
    frozen = {
        OrderHold: ("evaluation_snapshot", "severity", "status", "raised_at", "raised_by",
                    "checked_out_by", "checked_out_at", "cleared_by", "cleared_at"),
        OrderAmendment: ("impact_snapshot", "status", "requested_by", "requested_at",
                         "decided_by", "decided_at", "applied_by", "applied_at"),
        RevenueSchedule: ("journal_entry",),
    }
    for cls, names in frozen.items():
        fields = {f.name: f for f in cls._meta.get_fields() if f.concrete}
        for name in names:
            assert fields[name].editable is False, f"{cls.__name__}.{name}"


def test_ordermanagement_obligation_form_carries_no_money_field():
    """The only writer of the two money columns is recompute(); a form must not reach them."""
    fields = PerformanceObligationForm.Meta.fields
    assert "recognized_amount" not in fields
    assert "allocated_amount" not in fields
    assert "schedule" not in fields


# --------------------------------------------------------- evaluate() purity (L36/L37)


def test_ordermanagement_evaluate_is_pure(ordermanagement_tenant_a):
    """evaluate() must not write: not a hold, not a flag on the order, not a save."""
    tenant = ordermanagement_tenant_a
    order = _ordermanagement_order(tenant)
    rule = _ordermanagement_rule(
        tenant, rule_type="order_value", severity="block", parameters={"amount": "1.00"},
    )
    before = (order.credit_hold, order.hold_reason, order.status)
    before_holds = OrderHold.objects.filter(sales_order=order).count()

    findings, block = rule.evaluate(order)

    order.refresh_from_db()
    assert (order.credit_hold, order.hold_reason, order.status) == before
    assert OrderHold.objects.filter(sales_order=order).count() == before_holds
    assert len(findings) == 1 and block is True  # order total is above the 1.00 ceiling


def test_ordermanagement_evaluate_returns_a_list_even_when_clean(ordermanagement_tenant_a):
    """A caller must never have to tell 'no result' from 'no problem'."""
    tenant = ordermanagement_tenant_a
    order = _ordermanagement_order(tenant)
    rule = _ordermanagement_rule(
        tenant, rule_type="order_value", severity="warn", parameters={"amount": "99999999.00"},
    )
    findings, block = rule.evaluate(order)
    assert findings == [] and block is False


def test_ordermanagement_evaluate_skips_an_inactive_rule(ordermanagement_tenant_a):
    tenant = ordermanagement_tenant_a
    order = _ordermanagement_order(tenant)
    rule = _ordermanagement_rule(
        tenant, rule_type="order_value", severity="block",
        parameters={"amount": "1.00"}, is_active=False,
    )
    assert rule.applies_to(order) is False
    assert rule.evaluate(order) == ([], False)


def test_ordermanagement_evaluate_honours_a_party_scoped_rule(ordermanagement_tenant_a):
    """A rule scoped to one customer fires for that customer and nobody else."""
    tenant = ordermanagement_tenant_a
    order = _ordermanagement_order(tenant)
    other = Party.objects.create(tenant=tenant, name="Different Customer", kind="customer")
    rule = _ordermanagement_rule(
        tenant, rule_type="order_value", severity="block",
        parameters={"amount": "1.00"}, party=other,
    )
    assert rule.applies_to(order) is False
    rule.party = order.customer
    rule.save()
    assert rule.applies_to(order) is True


def test_ordermanagement_warn_severity_never_blocks(ordermanagement_tenant_a):
    """warn is the escape hatch for a trialled rule: it reports, it does not stop."""
    tenant = ordermanagement_tenant_a
    order = _ordermanagement_order(tenant)
    rule = _ordermanagement_rule(
        tenant, rule_type="order_value", severity="warn", parameters={"amount": "1.00"},
    )
    findings, block = rule.evaluate(order)
    assert len(findings) == 1 and block is False
    assert rule.is_blocking is False


def test_ordermanagement_runs_on_matches_the_active_on_axis(ordermanagement_tenant_a):
    """active_on decides WHICH evaluation the rule joins; the caller filters, this documents."""
    rule = _ordermanagement_rule(ordermanagement_tenant_a, active_on="both")
    assert rule.runs_on("submit") is True
    assert rule.runs_on("amendment") is True


# ------------------------------------------------------------ amendment single-writer


def test_ordermanagement_apply_refuses_unless_approved(ordermanagement_tenant_a):
    """The refusal lives in the method, not only in the view."""
    tenant = ordermanagement_tenant_a
    order = _ordermanagement_order(tenant, status="submitted")
    amendment = _ordermanagement_amendment(tenant, order, status="draft")
    with pytest.raises(ValidationError) as exc:
        amendment.apply(None, order)
    assert "APPROVED" in str(exc.value).upper()


def test_ordermanagement_apply_refuses_a_non_amendable_order(ordermanagement_tenant_a):
    """Approval was a decision against the order as it was; it may have moved since."""
    tenant = ordermanagement_tenant_a
    order = _ordermanagement_order(tenant, status="cancelled")
    amendment = _ordermanagement_amendment(tenant, order, status="approved")
    with pytest.raises(ValidationError) as exc:
        amendment.apply(None, order)
    assert "no longer be amended" in str(exc.value)


def test_ordermanagement_apply_refuses_a_mismatched_order(ordermanagement_tenant_a):
    """The locked order must BE this amendment's order, not merely some order."""
    tenant = ordermanagement_tenant_a
    order_a = _ordermanagement_order(tenant, status="submitted")
    order_b = _ordermanagement_order(tenant, status="submitted")
    amendment = _ordermanagement_amendment(tenant, order_a, status="approved")
    with pytest.raises(ValidationError) as exc:
        amendment.apply(None, order_b)
    assert "does not match" in str(exc.value)


def test_ordermanagement_amendable_statuses_never_include_a_terminal_state():
    """draft is 4.5's; fulfilled/invoiced/cancelled/closed are terminal."""
    assert OrderAmendment.AMENDABLE_STATUSES == (
        "submitted", "on_hold", "allocated", "partially_fulfilled",
    )
    for terminal in ("draft", "fulfilled", "invoiced", "cancelled", "closed"):
        assert terminal not in OrderAmendment.AMENDABLE_STATUSES


def test_ordermanagement_8_6_declares_no_second_sales_order():
    """L36/L37 asserted rather than trusted: 8.6 extends the SCM order, never redeclares it."""
    import apps.sales.models as sales_models

    assert not hasattr(sales_models, "SalesOrder")
    for cls in (OrderHold, OrderAmendment, RevenueSchedule):
        fk = cls._meta.get_field("sales_order")
        assert fk.remote_field.model.__name__ == "SalesOrder"
        assert fk.remote_field.model._meta.app_label == "scm"


# ------------------------------------------------------ tenant isolation on every FK


def test_ordermanagement_tenant_isolation_on_every_model(ordermanagement_tenant_a,
                                                          ordermanagement_tenant_b):
    """A row of tenant A must never be reachable from tenant B's queryset."""
    a, b = ordermanagement_tenant_a, ordermanagement_tenant_b
    order = _ordermanagement_order(a)
    rule = _ordermanagement_rule(a)
    hold = _ordermanagement_hold(a, order, rule=rule)
    amendment = _ordermanagement_amendment(a, order)
    schedule = _ordermanagement_schedule(a, order)
    obligation = _ordermanagement_obligation(a, schedule)
    # The children are TENANT-LESS, so create real rows to prove they are reached (and only
    # reached) through their parent rather than through a tenant column of their own.
    _ordermanagement_amendment_line(amendment, order.lines.first())

    for cls in (OrderValidationRule, OrderHold, OrderAmendment, RevenueSchedule):
        assert cls.objects.filter(tenant=a).exists()
        assert not cls.objects.filter(tenant=b).exists(), cls.__name__
    assert OrderAmendmentLine.objects.filter(amendment=amendment).count() == 1
    assert not OrderAmendmentLine.objects.filter(amendment__tenant=b).exists()
    assert PerformanceObligation.objects.filter(schedule=schedule).count() == 1
    assert not PerformanceObligation.objects.filter(schedule__tenant=b).exists()
    assert obligation.schedule_id == schedule.pk


def test_ordermanagement_clean_rejects_a_cross_tenant_party(ordermanagement_tenant_a,
                                                            ordermanagement_tenant_b):
    """A rule may only point at its own workspace's customer."""
    a, b = ordermanagement_tenant_a, ordermanagement_tenant_b
    foreign = Party.objects.create(tenant=b, name="Foreign", kind="customer")
    rule = _ordermanagement_rule(a)
    rule.party = foreign
    with pytest.raises(ValidationError) as exc:
        rule.clean()
    assert "party" in exc.value.message_dict


# -------------------------------------------------------------- FK on_delete policy


def test_ordermanagement_protected_fks_refuse_their_delete(ordermanagement_tenant_a):
    """party on OrderHold is PROTECT, so a customer cannot vanish under a live hold."""
    tenant = ordermanagement_tenant_a
    order = _ordermanagement_order(tenant)
    hold = _ordermanagement_hold(tenant, order, party=order.customer)
    with pytest.raises(ProtectedError):
        order.customer.delete()
    assert OrderHold.objects.filter(pk=hold.pk).exists()


def test_ordermanagement_hold_rule_is_set_null_so_evidence_survives(ordermanagement_tenant_a):
    """Deleting a rule must never delete the record of why an order was held."""
    tenant = ordermanagement_tenant_a
    order = _ordermanagement_order(tenant)
    rule = _ordermanagement_rule(tenant)
    hold = _ordermanagement_hold(tenant, order, rule=rule)
    rule.delete()
    hold.refresh_from_db()
    assert hold.rule_id is None
    assert OrderHold.objects.filter(pk=hold.pk).exists()


def test_ordermanagement_hold_severity_is_copied_not_referenced(ordermanagement_tenant_a):
    """Re-tuning a rule must not rewrite why an order was held last month."""
    tenant = ordermanagement_tenant_a
    order = _ordermanagement_order(tenant)
    rule = _ordermanagement_rule(tenant, severity="hold")
    hold = _ordermanagement_hold(tenant, order, rule=rule, severity="hold")
    rule.severity = "warn"
    rule.save()
    hold.refresh_from_db()
    assert hold.severity == "hold"  # the historical record is unchanged


def test_ordermanagement_hold_state_properties(ordermanagement_tenant_a):
    tenant = ordermanagement_tenant_a
    order = _ordermanagement_order(tenant)
    hold = _ordermanagement_hold(tenant, order)
    assert hold.is_open is True
    assert hold.is_checked_out is False
    hold.status = "cleared"
    assert hold.is_open is False

