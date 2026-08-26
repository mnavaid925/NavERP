"""Procurement 6.4 Vendor Management — security tests.

Covers the register's authz split (any member files a block REQUEST, admins decide),
IDOR scoping on every detail/action route, server-forced origin on portal writes,
portal scope narrowing (a binding sees ONE supplier, never NULL-widened), the
blocked-supplier submission ban, and POST-only enforcement on state-changing routes.
"""
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.procurement.models import (
    VendorInvoiceSubmission,
    VendorPortalAccess,
    VendorSuspension,
)

pytestmark = pytest.mark.django_db


# ------------------------------------------------------------------ builders
def _party(tenant, name):
    from apps.core.models import Party
    return Party.objects.create(tenant=tenant, name=name, kind="organization")


def _po(tenant, vendor):
    from apps.scm.models import PurchaseOrder
    return PurchaseOrder.objects.create(
        tenant=tenant, vendor=vendor, status="approved",
        order_date=timezone.localdate())


def _vpa(tenant, portal_user, invited_by, supplier=None):
    return VendorPortalAccess.objects.create(
        tenant=tenant, supplier=supplier, portal_user=portal_user,
        invited_by=invited_by)


def _vsu(tenant, supplier, requested_by, **overrides):
    fields = dict(
        tenant=tenant, supplier=supplier, kind="suspension",
        reason_category="delivery", reason="Late deliveries twice running.",
        status="requested", requested_by=requested_by)
    fields.update(overrides)
    return VendorSuspension.objects.create(**fields)


def _vis(tenant, supplier, submitted_by, ref="INV-SEC-1"):
    return VendorInvoiceSubmission.objects.create(
        tenant=tenant, supplier=supplier, invoice_ref=ref,
        amount=Decimal("120.00"), status="submitted", submitted_by=submitted_by)


def _vsu_payload(supplier_pk, **extra):
    fields = {
        "supplier": str(supplier_pk),
        "kind": "suspension",
        "reason_category": "delivery",
        "reason": "Repeated late deliveries against PO evidence.",
        "starts_on": timezone.localdate().isoformat(),
    }
    fields.update(extra)
    return fields


def _invoice_payload(**extra):
    fields = {"invoice_ref": "INV-CRAFT-1", "amount": "120.00"}
    fields.update(extra)
    return fields


# ------------------------------------------------------------------ fixtures
@pytest.fixture
def vsu_b(db, tenant_b, admin_b, supplier_b):
    _, party = supplier_b
    return _vsu(tenant_b, party, admin_b)


@pytest.fixture
def vis_b(db, tenant_b, admin_b, supplier_b):
    _, party = supplier_b
    return _vis(tenant_b, party, admin_b, ref="INV-GLOBEX-1")


@pytest.fixture
def vpa_b(db, tenant_b, admin_b, supplier_b):
    _, party = supplier_b
    return _vpa(tenant_b, admin_b, admin_b, supplier=party)


@pytest.fixture
def vsu_active_a(db, tenant_a, admin_user, supplier_a):
    _, party = supplier_a
    return _vsu(tenant_a, party, admin_user, status="active",
                decision_note="Pattern of failures.", decided_by=admin_user,
                decided_at=timezone.now())


@pytest.fixture
def portal_binding(db, tenant_a, member_user, admin_user, supplier_a):
    _, party = supplier_a
    return _vpa(tenant_a, member_user, admin_user, supplier=party)


@pytest.fixture
def other_party_a(db, tenant_a):
    """A SECOND supplier in tenant_a — the one the portal login must never see."""
    return _party(tenant_a, "Initech Components")


# ------------------------------------------------------------------ 1. IDOR
def test_idor_tenant_b_rows_404(client_a, tenant_b, vsu_b, vis_b, vpa_b):
    assert client_a.get(reverse("procurement:vsu_detail",
                                args=[vsu_b.pk])).status_code == 404
    assert client_a.get(reverse("procurement:vsu_edit",
                                args=[vsu_b.pk])).status_code == 404
    assert client_a.get(reverse("procurement:vpa_detail",
                                args=[vpa_b.pk])).status_code == 404
    assert client_a.get(reverse("procurement:vis_detail",
                                args=[vis_b.pk])).status_code == 404
    # Action routes scope identically, GET or POST.
    assert client_a.post(reverse("procurement:vsu_approve", args=[vsu_b.pk]),
                         {"note": "mine now"}).status_code == 404
    assert client_a.post(reverse("procurement:vsu_lift", args=[vsu_b.pk]),
                         {"lift_note": "unblocked"}).status_code == 404
    assert client_a.post(reverse("procurement:vis_accept", args=[vis_b.pk]),
                         {"review_note": "accepted across tenants"}).status_code == 404
    assert client_a.post(reverse("procurement:vpa_edit", args=[vpa_b.pk]),
                         {"note": "hijacked"}).status_code == 404
    # Nothing moved.
    vsu_b.refresh_from_db()
    vis_b.refresh_from_db()
    assert vsu_b.status == "requested" and vsu_b.decided_by_id is None
    assert vis_b.status == "submitted"
    assert VendorPortalAccess.objects.filter(tenant=tenant_b).count() == 1


# ------------------------------------------------------------------ 2. member authz
def test_member_write_gating(member_client, tenant_a, supplier_a,
                             vsu_requested_a, vsu_active_a, vis_submitted_a, vpa_a):
    _, party = supplier_a
    before_vsu = VendorSuspension.objects.filter(tenant=tenant_a).count()
    before_vis = VendorInvoiceSubmission.objects.filter(tenant=tenant_a).count()
    before_vpa = VendorPortalAccess.objects.filter(tenant=tenant_a).count()

    # Suspension decisions / edits / deletes are admin-only.
    assert member_client.post(reverse("procurement:vsu_approve",
                                      args=[vsu_requested_a.pk]),
                              {"note": "self-approve"}).status_code in (302, 403)
    assert member_client.post(reverse("procurement:vsu_reject",
                                      args=[vsu_requested_a.pk]),
                              {"note": "no"}).status_code in (302, 403)
    assert member_client.post(reverse("procurement:vsu_lift",
                                      args=[vsu_active_a.pk]),
                              {"lift_note": "trust me"}).status_code in (302, 403)
    assert member_client.post(reverse("procurement:vsu_edit",
                                      args=[vsu_requested_a.pk]),
                              _vsu_payload(party.pk)).status_code in (302, 403)
    assert member_client.post(reverse("procurement:vsu_delete",
                                      args=[vsu_requested_a.pk])).status_code in (302, 403)
    # Submission review is staff-only.
    assert member_client.post(reverse("procurement:vis_accept",
                                      args=[vis_submitted_a.pk]),
                              {"review_note": "ok"}).status_code in (302, 403)
    assert member_client.post(reverse("procurement:vis_reject",
                                      args=[vis_submitted_a.pk]),
                              {"review_note": "no"}).status_code in (302, 403)
    assert member_client.post(reverse("procurement:vis_start_review",
                                      args=[vis_submitted_a.pk])).status_code in (302, 403)
    assert member_client.post(reverse("procurement:vis_delete",
                                      args=[vis_submitted_a.pk])).status_code in (302, 403)
    # Binding writes are admin-only too.
    assert member_client.post(reverse("procurement:vpa_create"),
                              {"note": "grant myself portal"}).status_code in (302, 403)
    assert member_client.post(reverse("procurement:vpa_edit", args=[vpa_a.pk]),
                              {"note": "retarget binding"}).status_code in (302, 403)
    assert member_client.post(reverse("procurement:vpa_delete",
                                      args=[vpa_a.pk])).status_code in (302, 403)

    # Nothing was written or mutated.
    assert VendorSuspension.objects.filter(tenant=tenant_a).count() == before_vsu
    assert VendorInvoiceSubmission.objects.filter(tenant=tenant_a).count() == before_vis
    assert VendorPortalAccess.objects.filter(tenant=tenant_a).count() == before_vpa == 1
    vsu_requested_a.refresh_from_db()
    assert vsu_requested_a.status == "requested"
    assert vsu_requested_a.decided_by_id is None
    vsu_active_a.refresh_from_db()
    assert vsu_active_a.status == "active" and vsu_active_a.lifted_at is None
    vis_submitted_a.refresh_from_db()
    assert vis_submitted_a.status == "submitted"
    assert vis_submitted_a.reviewed_by_id is None


# ------------------------------------------------------------------ 3. member CAN file
def test_member_files_request_and_cannot_self_activate(member_client, tenant_a,
                                                       member_user, supplier_a):
    _, party = supplier_a
    before = VendorSuspension.objects.filter(tenant=tenant_a).count()
    resp = member_client.post(reverse("procurement:vsu_create"),
                              _vsu_payload(party.pk, status="active"))
    assert resp.status_code == 302
    obj = VendorSuspension.objects.filter(tenant=tenant_a).latest("id")
    assert VendorSuspension.objects.filter(tenant=tenant_a).count() == before + 1
    # The POST's status override was ignored — filings always START pending.
    assert obj.status == "requested"
    assert obj.requested_by_id == member_user.pk
    assert obj.tenant_id == tenant_a.id
    assert obj.decided_by_id is None


# ------------------------------------------------------------------ 4. mass assignment
def test_vsuc_create_mass_assignment_ignored(member_client, tenant_a, supplier_a,
                                             admin_user):
    _, party = supplier_a
    resp = member_client.post(
        reverse("procurement:vsu_create"),
        _vsu_payload(party.pk, decided_by=str(admin_user.pk),
                     lifted_at="2026-01-01 10:30", decision_note="forged"))
    assert resp.status_code == 302
    obj = VendorSuspension.objects.filter(tenant=tenant_a).latest("id")
    assert obj.decided_by_id is None
    assert obj.lifted_at is None
    assert obj.decision_note == ""
    assert obj.status == "requested"


def test_vendor_invoice_supplier_hidden_field_overridden(member_client, tenant_a,
                                                         member_user, portal_binding,
                                                         supplier_a, other_party_a):
    own_party, foreign = supplier_a[1], other_party_a
    _po(tenant_a, foreign)  # the PO the crafted payload tries to steer toward
    before = VendorInvoiceSubmission.objects.filter(tenant=tenant_a).count()
    resp = member_client.post(reverse("procurement:vendor_invoice_new"),
                              _invoice_payload(supplier=str(foreign.pk)))
    assert resp.status_code == 302
    obj = VendorInvoiceSubmission.objects.filter(tenant=tenant_a).latest("id")
    assert VendorInvoiceSubmission.objects.filter(tenant=tenant_a).count() == before + 1
    # Origin stays server-forced: the hidden supplier field was thrown away.
    assert obj.supplier_id == own_party.pk
    assert obj.submitted_by_id == member_user.pk
    assert obj.status == "submitted"


# ------------------------------------------------------------------ 5. portal scope
def test_portal_home_scopes_pos_to_bound_supplier(member_client, tenant_a,
                                                  portal_binding, supplier_a,
                                                  other_party_a):
    _, own_party = supplier_a
    own_po = _po(tenant_a, own_party)
    foreign_po = _po(tenant_a, other_party_a)
    resp = member_client.get(reverse("procurement:vendor_portal_home"))
    assert resp.status_code == 200
    html = resp.content.decode()
    assert own_po.number in html          # my supplier's orders are visible
    assert foreign_po.number not in html  # the neighbour supplier's are NOT


def test_null_supplier_access_row_widens_nothing(member_client, tenant_a,
                                                 member_user, admin_user):
    _vpa(tenant_a, member_user, admin_user, supplier=None)
    resp = member_client.get(reverse("procurement:vendor_portal_home"))
    assert resp.status_code == 302
    assert "vendor-portal" not in resp["Location"]
    # The refusal happened before any data touch.
    assert VendorInvoiceSubmission.objects.filter(tenant=tenant_a).count() == 0


# ------------------------------------------------------------------ 6. blocked supplier
def test_blocked_supplier_cannot_submit(member_client, tenant_a, portal_binding,
                                        vsu_active_a):
    before = VendorInvoiceSubmission.objects.filter(tenant=tenant_a).count()
    resp = member_client.get(reverse("procurement:vendor_invoice_new"))
    assert resp.status_code == 200
    html = resp.content.decode()
    assert "Account suspended" in html
    assert 'name="invoice_ref"' not in html  # no form offered while blocked
    resp = member_client.post(reverse("procurement:vendor_invoice_new"),
                              _invoice_payload())
    assert resp.status_code == 302
    assert VendorInvoiceSubmission.objects.filter(tenant=tenant_a).count() == before


# ------------------------------------------------------------------ 7. POST-only routes
def test_get_to_post_only_views_never_mutates(client_a, vsu_requested_a,
                                              vsu_active_a, vis_submitted_a, vpa_a):
    before_vsu = VendorSuspension.objects.count()
    before_vis = VendorInvoiceSubmission.objects.count()
    targets = [
        (("procurement:vsu_approve", vsu_requested_a.pk), "requested"),
        (("procurement:vsu_reject", vsu_requested_a.pk), "requested"),
        (("procurement:vsu_lift", vsu_active_a.pk), "active"),
        (("procurement:vsu_delete", vsu_requested_a.pk), "requested"),
        (("procurement:vis_accept", vis_submitted_a.pk), "submitted"),
        (("procurement:vis_reject", vis_submitted_a.pk), "submitted"),
        (("procurement:vis_start_review", vis_submitted_a.pk), "submitted"),
        (("procurement:vis_delete", vis_submitted_a.pk), "submitted"),
        (("procurement:vpa_delete", vpa_a.pk), None),
    ]
    for (name, pk), _ in targets:
        resp = client_a.get(reverse(name, args=[pk]))
        assert resp.status_code in (400, 403, 405), name
    vsu_requested_a.refresh_from_db()
    vsu_active_a.refresh_from_db()
    vis_submitted_a.refresh_from_db()
    assert vsu_requested_a.status == "requested"
    assert vsu_active_a.status == "active"
    assert vis_submitted_a.status == "submitted"
    assert VendorSuspension.objects.count() == before_vsu
    assert VendorInvoiceSubmission.objects.count() == before_vis
    assert VendorPortalAccess.objects.filter(pk=vpa_a.pk).exists()


# ------------------------------------------------------------------ 8. cross-tenant FK
def test_vsuc_create_cross_tenant_supplier_rejected(client_a, tenant_a, supplier_b):
    _, foreign_party = supplier_b
    before_local = VendorSuspension.objects.filter(tenant=tenant_a).count()
    before_total = VendorSuspension.objects.count()
    resp = client_a.post(reverse("procurement:vsu_create"),
                         _vsu_payload(foreign_party.pk))
    # The form refuses the foreign FK — re-rendered with a field error, nothing filed.
    assert resp.status_code == 200
    assert VendorSuspension.objects.filter(tenant=tenant_a).count() == before_local
    assert VendorSuspension.objects.count() == before_total


# ------------------------------------------------------------------ house-style sanity
def test_login_required_everywhere(client, db):
    for name in ("procurement:vsu_list", "procurement:vis_list",
                 "procurement:vpa_list", "procurement:vendor_portal_home",
                 "procurement:vendor_invoice_new"):
        assert client.get(reverse(name)).status_code in (302, 403)
