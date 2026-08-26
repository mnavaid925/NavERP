"""Procurement 6.4 Vendor Management — model tests."""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.procurement.models import (
    VendorInvoiceSubmission,
    VendorPortalAccess,
    VendorSuspension,
)
from apps.core.models import Party
from apps.scm.models import PurchaseOrder

pytestmark = pytest.mark.django_db


def _party(tenant, name):
    return Party.objects.create(tenant=tenant, name=name, kind="organization")


def _po(tenant, vendor):
    return PurchaseOrder.objects.create(
        tenant=tenant, vendor=vendor, status="approved",
        order_date=timezone.localdate())


def _vsu(tenant, supplier, **overrides):
    fields = dict(tenant=tenant, supplier=supplier, reason="Late deliveries.",
                  starts_on=timezone.localdate(), status="requested")
    fields.update(overrides)
    return VendorSuspension.objects.create(**fields)


def _vis(tenant, supplier, **overrides):
    """An UNSAVED submission — callers decide between full_clean() and save()."""
    fields = dict(tenant=tenant, supplier=supplier, invoice_ref="INV-100",
                  amount=Decimal("250.00"))
    fields.update(overrides)
    return VendorInvoiceSubmission(**fields)


# ------------------------------------------------------------------ VendorPortalAccess [VPA-]

def test_vpa_number_auto_assigned_and_defaults(tenant_a, admin_user, member_user,
                                              supplier_a):
    _, party = supplier_a
    vpa = VendorPortalAccess.objects.create(
        tenant=tenant_a, supplier=party, portal_user=admin_user,
        invited_by=admin_user, note="AP inbox login")
    assert vpa.number == "VPA-00001"
    assert vpa.is_active is True
    # Several logins MAY bind to the same supplier company on purpose.
    second = VendorPortalAccess.objects.create(
        tenant=tenant_a, supplier=party, portal_user=member_user)
    assert second.number == "VPA-00002"


def test_vpa_for_user_answers_only_active_rows(vpa_a, tenant_a, admin_user):
    hit = VendorPortalAccess.for_user(tenant_a, admin_user)
    assert hit is not None and hit.pk == vpa_a.pk
    # Switch off instead of delete — and the gate stops answering.
    VendorPortalAccess.objects.filter(pk=vpa_a.pk).update(is_active=False)
    assert VendorPortalAccess.for_user(tenant_a, admin_user) is None


def test_vpa_for_user_is_tenant_scoped(vpa_a, tenant_a, tenant_b, admin_user,
                                       member_user, supplier_b):
    _, party_b = supplier_b
    there = VendorPortalAccess.objects.create(
        tenant=tenant_b, supplier=party_b, portal_user=member_user)
    hit = VendorPortalAccess.for_user(tenant_b, member_user)
    assert hit is not None and hit.pk == there.pk
    # The workspace-B binding does NOT leak into workspace A's lookup.
    assert VendorPortalAccess.for_user(tenant_a, member_user) is None
    assert VendorPortalAccess.for_user(tenant_a, admin_user).pk == vpa_a.pk


# ------------------------------------------------------------------ VendorSuspension [VSU-]

def test_vsu_number_auto_assigned_and_str_label(tenant_a, supplier_a):
    _, party = supplier_a
    vsu = _vsu(tenant_a, party, kind="blacklist", reason_category="quality")
    assert vsu.number == "VSU-00001"
    text = str(vsu)
    assert vsu.number in text
    assert party.name in text
    assert "Requested" in text  # status label, not raw slug
    active = _vsu(tenant_a, party, status="active", decided_at=timezone.now())
    assert active.number == "VSU-00002"
    assert "In force" in str(active)


def test_vsu_status_truth_table(tenant_a, supplier_a):
    _, party = supplier_a
    today = timezone.localdate()
    future = _vsu(tenant_a, party, status="active",
                  ends_on=today + timedelta(days=7))
    assert future.is_blocking and not future.is_expired and future.is_current
    past = _vsu(tenant_a, party, status="active",
                ends_on=today - timedelta(days=7))
    assert past.is_blocking and past.is_expired and not past.is_current
    open_ended = _vsu(tenant_a, party, status="active")
    assert open_ended.is_blocking and not open_ended.is_expired \
        and open_ended.is_current
    requested = _vsu(tenant_a, party)
    assert not requested.is_blocking and not requested.is_expired \
        and not requested.is_current


def test_blocking_for_ignores_non_active_statuses(tenant_a, supplier_a):
    _, party = supplier_a
    for status in ("requested", "rejected", "lifted"):
        _vsu(tenant_a, party, status=status)
    assert VendorSuspension.blocking_for(tenant_a, party.pk) is None
    active = _vsu(tenant_a, party, status="active", decided_at=timezone.now())
    hit = VendorSuspension.blocking_for(tenant_a, party.pk)
    assert hit is not None and hit.pk == active.pk


def test_blocking_for_expiry_and_explicit_today_boundary(tenant_a, supplier_a):
    _, party = supplier_a
    today = timezone.localdate()
    expired = _vsu(tenant_a, party, status="active", decided_at=timezone.now(),
                   ends_on=today - timedelta(days=1))
    assert expired.is_expired
    assert VendorSuspension.blocking_for(tenant_a, party.pk) is None
    bounded = _vsu(tenant_a, party, status="active", decided_at=timezone.now(),
                   ends_on=today + timedelta(days=3))
    # Explicit today on BOTH sides of the boundary...
    hit = VendorSuspension.blocking_for(tenant_a, party.pk,
                                        today=today + timedelta(days=3))
    assert hit is not None and hit.pk == bounded.pk
    assert VendorSuspension.blocking_for(tenant_a, party.pk,
                                         today=today + timedelta(days=4)) is None
    # ...and ends_on == today still blocks (gte, not gt).
    hit = VendorSuspension.blocking_for(tenant_a, party.pk)
    assert hit is not None and hit.pk == bounded.pk


def test_vsu_clean_rejects_ends_before_starts(tenant_a, supplier_a):
    _, party = supplier_a
    today = timezone.localdate()
    vsu = VendorSuspension(tenant=tenant_a, supplier=party, reason="x",
                           status="active", starts_on=today,
                           ends_on=today - timedelta(days=1))
    with pytest.raises(ValidationError) as exc:
        vsu.full_clean()
    assert "ends_on" in exc.value.message_dict
    assert "Ends before it starts." in exc.value.message_dict["ends_on"]


def test_vsu_clean_rejects_cross_tenant_records(tenant_a, tenant_b, supplier_a):
    _, party = supplier_a
    foreign_party = _party(tenant_b, "Foreign Parts GmbH")
    bad_supplier = VendorSuspension(tenant=tenant_a, supplier=foreign_party,
                                    reason="x")
    with pytest.raises(ValidationError) as exc:
        bad_supplier.full_clean()
    assert "supplier" in exc.value.message_dict
    assert "another workspace" in exc.value.message_dict["supplier"][0]

    foreign_po = _po(tenant_b, foreign_party)
    bad_po = VendorSuspension(tenant=tenant_a, supplier=party, reason="x",
                              po_reference=foreign_po)
    with pytest.raises(ValidationError) as exc:
        bad_po.full_clean()
    assert "po_reference" in exc.value.message_dict


# ------------------------------------------------------------------ VendorInvoiceSubmission [VIS-]

def test_vis_number_auto_assigned_and_amount_clamped_on_save(tenant_a, supplier_a):
    _, party = supplier_a
    vis = _vis(tenant_a, party, invoice_ref="INV-A1", amount=Decimal("1.005"))
    vis.save()
    assert vis.number == "VIS-00001"
    # Clamped to the column's 2dp shape before persisting.
    assert vis.amount == Decimal("1.00")
    big = _vis(tenant_a, party, invoice_ref="INV-BIG",
               amount=Decimal("99999999999.99"))
    big.save()
    assert big.amount == Decimal("9999999999.99")  # DecimalField(14, 2) ceiling


def test_vis_clean_rejects_non_positive_amounts(tenant_a, supplier_a):
    _, party = supplier_a
    for bad in (Decimal("0"), Decimal("-5.00")):
        vis = _vis(tenant_a, party, amount=bad)
        with pytest.raises(ValidationError) as exc:
            vis.full_clean()
        assert "amount" in exc.value.message_dict
        assert exc.value.message_dict["amount"]


def test_vis_clean_po_rules(tenant_a, supplier_a, po_a):
    _, party = supplier_a
    rival = _party(tenant_a, "Same-Workspace Rival Co")
    rival_po = _po(tenant_a, rival)

    mismatch = _vis(tenant_a, party, purchase_order=rival_po)
    with pytest.raises(ValidationError) as exc:
        mismatch.full_clean()
    assert "purchase_order" in exc.value.message_dict
    assert "different supplier" in exc.value.message_dict["purchase_order"][0]

    # A PO issued to the SAME supplier of the SAME tenant accepts cleanly.
    ok = _vis(tenant_a, party, invoice_ref="INV-MATCH", purchase_order=po_a)
    ok.full_clean()
    ok.save()
    assert ok.number.startswith("VIS-")


def test_vis_clean_rejects_cross_tenant_records(tenant_a, tenant_b, supplier_a):
    _, party = supplier_a
    foreign_party = _party(tenant_b, "Globex Foreign Co")
    bad_supplier = _vis(tenant_a, foreign_party)
    with pytest.raises(ValidationError) as exc:
        bad_supplier.full_clean()
    assert "supplier" in exc.value.message_dict
    assert "another workspace" in exc.value.message_dict["supplier"][0]

    foreign_po = _po(tenant_b, foreign_party)
    bad_po = _vis(tenant_a, party, purchase_order=foreign_po)
    with pytest.raises(ValidationError) as exc:
        bad_po.full_clean()
    assert "purchase_order" in exc.value.message_dict


# ------------------------------------------------------------------ str methods

def test_str_methods_contain_expected_fragments(vpa_a, vsu_requested_a,
                                                vis_submitted_a):
    assert vpa_a.supplier.name in str(vpa_a)
    assert vsu_requested_a.number in str(vsu_requested_a)
    assert "Requested" in str(vsu_requested_a)
    assert vis_submitted_a.invoice_ref in str(vis_submitted_a)
