"""Inventory 5.3 — security.

Cross-tenant IDOR on every 5.3 route shape (rule CRUD, tier verbs, dispatch log), privilege
gates (tier decisions + policy writes are tenant-admin only), crafted-FK injection (foreign
PO / ReorderRule / OrgUnit pks in a POST body), provenance integrity (decided_by/tier are
server-stamped, never read from the body), audit completeness (every mutation lands in
core.AuditLog), escaping of attacker-controlled text, and the POST-only destructive verb.
"""
from decimal import Decimal

import pytest
from django.contrib.contenttypes.models import ContentType
from django.test import Client
from django.urls import reverse

from apps.core.models import AuditLog, OrgUnit
from apps.inventory.models import (
    PurchaseOrderApproval,
    PurchaseOrderApprovalRule,
    PurchaseOrderDispatch,
)
from apps.scm.models import Location, PurchaseOrder, ReorderRule

pytestmark = pytest.mark.django_db


def _audit_logs(obj):
    """Every core.AuditLog row written about ``obj`` (object_id filtered as a string)."""
    ct = ContentType.objects.get_for_model(type(obj))
    return AuditLog.objects.filter(content_type=ct, object_id=str(obj.pk))


def _audit_changes(obj):
    """The ``changes['action']`` value of each audit row about ``obj``, oldest first."""
    return [log.changes.get("action") for log in _audit_logs(obj).order_by("id")]


# ---- 1. Tenant isolation (IDOR) -----------------------------------------------------------------

def test_po_cross_tenant_rule_pages_404(client_b, approval_rule_std_a):
    for name in ["approvalrule_detail", "approvalrule_edit"]:
        assert client_b.get(reverse(f"inventory:{name}",
                                    args=[approval_rule_std_a.pk])).status_code == 404


def test_po_cross_tenant_rule_edit_post_cannot_rewrite(client_b, approval_rule_std_a):
    response = client_b.post(
        reverse("inventory:approvalrule_edit", args=[approval_rule_std_a.pk]),
        data={"name": "Hijacked", "min_amount": "0", "max_amount": "", "tier_count": "1"})
    assert response.status_code == 404
    approval_rule_std_a.refresh_from_db()
    assert approval_rule_std_a.name != "Hijacked"


def test_po_cross_tenant_rule_delete_post_survives(client_b, approval_rule_std_a):
    """The money gate itself must not be deletable from another workspace."""
    response = client_b.post(reverse("inventory:approvalrule_delete",
                                     args=[approval_rule_std_a.pk]))
    assert response.status_code == 404
    approval_rule_std_a.refresh_from_db()  # raises if deleted — the real assertion


def test_po_cross_tenant_dispatch_detail_and_delete_404(client_b, po_dispatch_a):
    assert client_b.get(reverse("inventory:dispatch_detail",
                                args=[po_dispatch_a.pk])).status_code == 404
    assert client_b.post(reverse("inventory:dispatch_delete",
                                 args=[po_dispatch_a.pk])).status_code == 404
    po_dispatch_a.refresh_from_db()


def test_po_cross_tenant_tier_decisions_404_write_nothing(client_b, po_pending_a):
    """admin_b deciding tenant_a's order must neither see it nor leave a trace: no decision
    row anywhere, and the order stays exactly where it was in its lifecycle."""
    approve = client_b.post(reverse("inventory:approval_tier_approve",
                                    args=[po_pending_a.pk, 1]))
    reject = client_b.post(reverse("inventory:approval_tier_reject",
                                   args=[po_pending_a.pk, 1]))
    assert approve.status_code == 404
    assert reject.status_code == 404
    assert PurchaseOrderApproval.objects.count() == 0
    po_pending_a.refresh_from_db()
    assert po_pending_a.status == "pending_approval"


# ---- 2. Privilege gates -------------------------------------------------------------------------

def test_po_member_cannot_decide_tiers(member_client, po_pending_a):
    """Clearing a tier commits tenant money — members get PermissionDenied and zero rows,
    even with a hand-typed note trying to look like a real sign-off."""
    for name in ["approval_tier_approve", "approval_tier_reject"]:
        response = member_client.post(reverse(f"inventory:{name}", args=[po_pending_a.pk, 1]),
                                      data={"note": "self-approved"})
        assert response.status_code == 403
    assert PurchaseOrderApproval.objects.count() == 0
    po_pending_a.refresh_from_db()
    assert po_pending_a.status == "pending_approval"


def test_po_member_cannot_write_approval_rules(member_client, approval_rule_std_a):
    """A rule IS the money gate, so create/edit/delete carry the admin privilege too."""
    assert member_client.post(reverse("inventory:approvalrule_create"), data={
        "name": "Sneaky band", "min_amount": "0", "max_amount": "",
        "tier_count": "1", "is_active": "on"}).status_code == 403
    assert member_client.post(reverse("inventory:approvalrule_edit",
                                      args=[approval_rule_std_a.pk]),
                              data={"name": "Hijacked", "min_amount": "0", "max_amount": "",
                                    "tier_count": "1"}).status_code == 403
    assert member_client.post(reverse("inventory:approvalrule_delete",
                                      args=[approval_rule_std_a.pk])).status_code == 403
    approval_rule_std_a.refresh_from_db()
    assert approval_rule_std_a.name != "Hijacked"
    assert not PurchaseOrderApprovalRule.objects.filter(name="Sneaky band").exists()


def test_po_anonymous_redirected_on_po_pages(client):
    for name in ["approvalrule_list", "approval_queue", "dispatch_list", "reorderdraft"]:
        response = client.get(reverse(f"inventory:{name}"))
        assert response.status_code == 302
        assert "/login" in response.url or response.url.endswith("login")


# ---- 3. Cross-tenant reference injection --------------------------------------------------------

def test_po_dispatch_create_rejects_foreign_order(client_b, po_sent_a):
    """A narrowed <select> is UX, not a boundary: posting tenant_a's SENT order pk (a status
    that would be perfectly selectable in its own workspace) must field-error, not record."""
    response = client_b.post(reverse("inventory:dispatch_create"), data={
        "purchase_order": str(po_sent_a.pk), "channel": "email",
        "recipient": "buyer@globex.example", "reference": "CRAFTED",
        "dispatched_at": "2026-08-21T09:30", "note": ""})
    assert response.status_code == 200
    assert "purchase_order" in response.context["form"].errors
    assert not PurchaseOrderDispatch.objects.exists()
    po_sent_a.refresh_from_db()
    assert po_sent_a.status == "sent"


def test_po_reorderdraft_foreign_rule_drafts_nothing(client_a, item_b, tenant_b):
    """select=<foreign ReorderRule pk> is silently dropped by the tenant-scoped query — no
    order may appear under EITHER workspace."""
    dock_b = Location.objects.create(tenant=tenant_b, code="GDOCK-1", name="Globex dock")
    foreign = ReorderRule.objects.create(
        tenant=tenant_b, item=item_b, location=dock_b,
        reorder_point=Decimal("999999"), safety_stock=Decimal("10"),
        reorder_quantity=Decimal("0"))
    response = client_a.post(reverse("inventory:reorderdraft"), data={
        "select": str(foreign.pk), f"vendor_{foreign.pk}": "1"})
    assert response.status_code == 302
    assert not PurchaseOrder.objects.exists()


def test_po_rule_create_rejects_foreign_org_unit(client_a, tenant_b):
    """The department scope must resolve inside this workspace only."""
    ou_b = OrgUnit.objects.create(tenant=tenant_b, kind="department", name="Globex Ops")
    response = client_a.post(reverse("inventory:approvalrule_create"), data={
        "name": "Crafted band", "min_amount": "0", "max_amount": "5000",
        "org_unit": str(ou_b.pk), "tier_count": "1", "is_active": "on"})
    assert response.status_code == 200
    assert "org_unit" in response.context["form"].errors
    assert not PurchaseOrderApprovalRule.objects.filter(name="Crafted band").exists()


# ---- 4. Provenance integrity --------------------------------------------------------------------

def test_po_tier_decision_server_stamped_fields(client_a, admin_user, member_user,
                                                po_pending_a, approval_rule_cap_a):
    """decided_by/tier are never form inputs: posting crafted values alongside approve must
    be ignored — the tier comes from the URL, the signature from the session, the timestamp
    from the server clock."""
    response = client_a.post(
        reverse("inventory:approval_tier_approve", args=[po_pending_a.pk, 1]),
        data={"note": "cleared", "decided_by": str(member_user.pk), "tier": "9"})
    assert response.status_code == 302
    row = PurchaseOrderApproval.objects.get(purchase_order=po_pending_a)
    assert row.tier == 1  # NOT the crafted tier=9 from the body
    assert row.decided_by_id == admin_user.pk  # NOT the forged member pk
    assert row.decided_at is not None
    assert row.decision == "approved"
    assert PurchaseOrderApproval.objects.count() == 1


# ---- 5. Audit completeness ----------------------------------------------------------------------

def test_po_tier_approve_writes_audit(client_a, po_pending_a):
    client_a.post(reverse("inventory:approval_tier_approve", args=[po_pending_a.pk, 1]),
                  data={})
    row = PurchaseOrderApproval.objects.get(purchase_order=po_pending_a)
    assert ("create", "tier_approve") in [
        (log.action, log.changes.get("action")) for log in _audit_logs(row)]


def test_po_final_tier_flips_status_and_audits_approve(client_a, admin_user, po_pending_a,
                                                       approval_rule_cap_a):
    """250k resolves to the 3-tier Capital band: clearing the LAST tier performs the spine's
    own transition and stamps its own audit row on the ORDER."""
    for tier in (1, 2, 3):
        response = client_a.post(reverse("inventory:approval_tier_approve",
                                         args=[po_pending_a.pk, tier]), data={})
        assert response.status_code == 302
    po_pending_a.refresh_from_db()
    assert po_pending_a.status == "approved"
    assert po_pending_a.approved_by_id == admin_user.pk
    assert "approve" in _audit_changes(po_pending_a)
    assert PurchaseOrderApproval.objects.filter(purchase_order=po_pending_a).count() == 3


def test_po_reject_returns_to_draft_and_audits_reject(client_a, po_pending_a):
    client_a.post(reverse("inventory:approval_tier_reject", args=[po_pending_a.pk, 1]),
                  data={"note": "no budget line"})
    po_pending_a.refresh_from_db()
    assert po_pending_a.status == "draft"
    row = PurchaseOrderApproval.objects.get(purchase_order=po_pending_a)
    assert row.decision == "rejected"
    assert "reject" in _audit_changes(po_pending_a)


def test_po_dispatch_audit_create_and_send_flip(client_a, po_pending_a, po_sent_a,
                                                approval_rule_cap_a):
    """The first dispatch of an APPROVED order flips it to sent (+send audit); a re-send of
    an already-sent order records proof and writes ONLY the create audit."""
    for tier in (1, 2, 3):
        client_a.post(reverse("inventory:approval_tier_approve",
                              args=[po_pending_a.pk, tier]), data={})
    payload = {"channel": "email", "recipient": "orders@acme.example",
               "dispatched_at": "2026-08-21T09:30", "note": ""}
    response = client_a.post(reverse("inventory:dispatch_create"),
                             data={**payload, "reference": "MSG-1",
                                   "purchase_order": str(po_pending_a.pk)})
    assert response.status_code == 302
    po_pending_a.refresh_from_db()
    assert po_pending_a.status == "sent"
    dispatch = PurchaseOrderDispatch.objects.get(reference="MSG-1")
    assert any(log.action == "create" for log in _audit_logs(dispatch))
    assert "send" in _audit_changes(po_pending_a)

    response = client_a.post(reverse("inventory:dispatch_create"),
                             data={**payload, "reference": "MSG-2",
                                   "purchase_order": str(po_sent_a.pk)})
    assert response.status_code == 302
    resend = PurchaseOrderDispatch.objects.get(reference="MSG-2")
    assert any(log.action == "create" for log in _audit_logs(resend))
    assert "send" not in _audit_changes(po_sent_a)
    po_sent_a.refresh_from_db()
    assert po_sent_a.status == "sent"


def test_po_reorderdraft_writes_auto_draft_audit(client_a, tenant_a, vendor_party_a,
                                                 reorder_below_a):
    response = client_a.post(reverse("inventory:reorderdraft"), data={
        "select": str(reorder_below_a.pk),
        f"vendor_{reorder_below_a.pk}": str(vendor_party_a.pk)})
    assert response.status_code == 302
    po = PurchaseOrder.objects.get(tenant=tenant_a)
    assert po.status == "draft"
    assert "auto_draft_reorder" in _audit_changes(po)


# ---- 6. XSS hygiene -----------------------------------------------------------------------------

def test_po_rule_name_escaped_on_list_and_detail(client_a):
    """Autoescape is the only sanitizer a free-text rule name may rely on."""
    probe = "<script>alert(1)</script>"
    response = client_a.post(reverse("inventory:approvalrule_create"), data={
        "name": probe, "min_amount": "0", "max_amount": "",
        "tier_count": "1", "is_active": "on"})
    assert response.status_code == 302
    rule = PurchaseOrderApprovalRule.objects.get(name=probe)
    pages = [client_a.get(reverse("inventory:approvalrule_list")),
             client_a.get(reverse("inventory:approvalrule_detail", args=[rule.pk]))]
    for page in pages:
        html = page.content.decode()
        assert "&lt;script&gt;" in html
        assert probe not in html


def test_po_dispatch_fields_escaped_on_list_and_detail(client_a, po_sent_a):
    """The transmission log stores what the buyer typed — reference/note render as text."""
    probe = "<script>alert(1)</script>"
    response = client_a.post(reverse("inventory:dispatch_create"), data={
        "purchase_order": str(po_sent_a.pk), "channel": "print", "recipient": "",
        "reference": probe, "note": probe, "dispatched_at": "2026-08-21T09:30"})
    assert response.status_code == 302
    row = PurchaseOrderDispatch.objects.get(note=probe)
    pages = [client_a.get(reverse("inventory:dispatch_list")),
             client_a.get(reverse("inventory:dispatch_detail", args=[row.pk]))]
    for page in pages:
        html = page.content.decode()
        assert "&lt;script&gt;" in html
        assert probe not in html


# ---- 7. Safety net ------------------------------------------------------------------------------

def test_po_deletes_are_post_only(client_a, approval_rule_std_a, po_dispatch_a):
    """Destructive verbs refuse the method a link/pre-fetch could trigger."""
    assert client_a.get(reverse("inventory:approvalrule_delete",
                                args=[approval_rule_std_a.pk])).status_code == 405
    assert client_a.get(reverse("inventory:dispatch_delete",
                                args=[po_dispatch_a.pk])).status_code == 405
    approval_rule_std_a.refresh_from_db()
    po_dispatch_a.refresh_from_db()
