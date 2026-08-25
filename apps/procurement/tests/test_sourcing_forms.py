"""Procurement 6.5 - Sourcing & Tendering form tests.

The forms are the crafted-POST boundary: tenant-scoped FKs are re-checked where they render,
a new bid only targets an OPEN event, a non-compliant bid must say why, and the evaluation
matrix refuses weights that would push the score above its own 100-point scale.
"""
import pytest

from apps.procurement.forms import (
    EventCriterionFormSet,
    SourcingBidForm,
    SourcingEventForm,
)

pytestmark = pytest.mark.django_db


def _with_supplier_role(party):
    """The bid form scopes suppliers to PartyRole supplier/vendor — grant it for the test."""
    from apps.core.models import PartyRole
    PartyRole.objects.get_or_create(party=party, tenant=party.tenant,
                                    defaults={"role": "supplier"})
    return party


# -- event + matrix ----------------------------------------------------------------------------------

def test_sourcing_event_form_valid_minimal(sourcing_event_open_a):
    form = SourcingEventForm(
        {"title": "Lab consumables tender", "event_type": "rfp", "rules": "Score on price."},
        tenant=sourcing_event_open_a.tenant)
    assert form.is_valid(), form.errors


def test_sourcing_event_form_rejects_deadline_before_open(sourcing_event_open_a):
    import datetime

    from django.utils import timezone
    now = timezone.now()
    form = SourcingEventForm(
        {"title": "Backwards window", "event_type": "tender",
         "opens_at": (now + datetime.timedelta(days=2)).strftime("%Y-%m-%dT%H:%M"),
         "closes_at": now.strftime("%Y-%m-%dT%H:%M")},
        tenant=sourcing_event_open_a.tenant)
    assert not form.is_valid()
    assert "closes_at" in form.errors


def test_sourcing_criterion_formset_rejects_weight_over_100(sourcing_event_open_a):
    data = {
        "criteria-TOTAL_FORMS": "2", "criteria-INITIAL_FORMS": "0",
        "criteria-MIN_NUM_FORMS": "0", "criteria-MAX_NUM_FORMS": "20",
        "criteria-0-name": "Price", "criteria-0-weight_pct": "70",
        "criteria-0-max_score": "10",
        "criteria-1-name": "Delivery", "criteria-1-weight_pct": "40",
        "criteria-1-max_score": "10",
    }
    formset = EventCriterionFormSet(data, instance=sourcing_event_open_a)
    assert not formset.is_valid()
    assert any("100%" in message for message in formset.non_form_errors())


def test_sourcing_criterion_formset_allows_partial_coverage(sourcing_event_open_a):
    data = {
        "criteria-TOTAL_FORMS": "1", "criteria-INITIAL_FORMS": "0",
        "criteria-MIN_NUM_FORMS": "0", "criteria-MAX_NUM_FORMS": "20",
        "criteria-0-name": "Price only", "criteria-0-weight_pct": "60",
        "criteria-0-max_score": "10",
    }
    formset = EventCriterionFormSet(data, instance=sourcing_event_open_a)
    assert formset.is_valid(), formset.errors


# -- bids ---------------------------------------------------------------------------------------------

def test_sourcing_bid_form_valid_and_scopes_suppliers(sourcing_event_open_a, supplier_a):
    party = _with_supplier_role(supplier_a[1])
    form = SourcingBidForm(
        {"event": str(sourcing_event_open_a.pk), "supplier": str(party.pk),
         "total_price": "9100.00", "is_compliant": "on"},
        tenant=sourcing_event_open_a.tenant)
    assert form.is_valid(), form.errors


def test_sourcing_bid_form_refuses_closed_event_for_new_bid(db, tenant_a, admin_user,
                                                            supplier_a,
                                                            sourcing_event_closed_a):
    party = _with_supplier_role(supplier_a[1])
    form = SourcingBidForm(
        {"event": str(sourcing_event_closed_a.pk), "supplier": str(party.pk),
         "total_price": "500.00", "is_compliant": "on"},
        tenant=tenant_a)
    assert not form.is_valid()
    assert "event" in form.errors


def test_sourcing_bid_form_requires_compliance_note_when_not_compliant(
        sourcing_event_open_a, supplier_a):
    party = _with_supplier_role(supplier_a[1])
    form = SourcingBidForm(
        {"event": str(sourcing_event_open_a.pk), "supplier": str(party.pk),
         "total_price": "9100.00"},
        tenant=sourcing_event_open_a.tenant)
    assert not form.is_valid()
    assert "compliance_note" in form.errors


def test_sourcing_bid_form_rejects_foreign_supplier(sourcing_event_open_a, supplier_b):
    _, foreign_party = supplier_b
    form = SourcingBidForm(
        {"event": str(sourcing_event_open_a.pk), "supplier": str(foreign_party.pk),
         "total_price": "9100.00", "is_compliant": "on"},
        tenant=sourcing_event_open_a.tenant)
    assert not form.is_valid()
    assert "supplier" in form.errors


def test_sourcing_bid_form_rejects_foreign_event(sourcing_event_closed_a, supplier_a,
                                                 tenant_b, admin_b):
    party = _with_supplier_role(supplier_a[1])
    form = SourcingBidForm(
        {"event": str(sourcing_event_closed_a.pk), "supplier": str(party.pk),
         "total_price": "9100.00", "is_compliant": "on"},
        tenant=tenant_b)
    assert not form.is_valid()


def test_sourcing_bid_form_status_not_mass_assignable(sourcing_event_open_a, supplier_a):
    party = _with_supplier_role(supplier_a[1])
    form = SourcingBidForm(
        {"event": str(sourcing_event_open_a.pk), "supplier": str(party.pk),
         "total_price": "9100.00", "is_compliant": "on", "status": "won",
         "submitted_by": "1"},
        tenant=sourcing_event_open_a.tenant)
    assert form.is_valid(), form.errors
    bid = form.save(commit=False)
    assert bid.status == "draft"          # excluded fields never reach the instance via POST
    assert bid.submitted_by_id is None
