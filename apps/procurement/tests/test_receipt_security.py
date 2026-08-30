"""Procurement 6.12 Goods Receipt & Inspection — isolation & hardening tests.

The defensive half of the 6.12 suite. Every test here asks the same question from a different
angle: *can a user reach a row, a field or a state transition the product never meant to give
them?*

Laid out in six sections:

1. **Cross-tenant IDOR** — every pk-scoped 6.12 route (tolerance policy, discrepancy, return to
   vendor, and the console's two ASN verbs) aimed at another workspace's pk returns **404**, and
   the target rows come back byte-identical.
2. **Register & board isolation** — none of the three registers and none of the three computed
   boards ever renders another workspace's rows, and a tenant-less superuser gets an empty (or
   refused) page rather than everybody's data.
3. **The authz ladder** — anonymous redirects to the login page; a plain member is refused on the
   seven ``@tenant_admin_required`` routes and *allowed* everywhere else (the deliberate 6.12
   split, in which ``receiving_console_book`` stays member-visible); CSRF is enforced on every
   POST; a GET on a ``@require_POST`` verb is 405 and mutates nothing.
4. **Mass assignment** — the crafted-POST surface: another workspace's pk in every FK field on
   all four write forms plus the line formset, a forged ``status`` / ``number`` / ``tenant`` /
   ``created_by`` / verb-stamp block, the ``goods_receipt`` field the discrepancy form *pops* on
   edit, and a ``qty_<pk>`` crafted for a line that is not on the posted shipment.
5. **Hostile input** — junk FK filter params, junk enum params, page junk, and the decimal family
   (``NaN`` / ``Infinity`` / garbage / negative / over-``max_digits``) on both hand-parsed number
   surfaces: the discrepancy prefill and the console's dynamic quantity fields (L11 / L35).
6. **Absent prerequisites are REJECTED, never fallen through** (L35) — no quantity, no receipt;
   no remedy, no resolution; no reason, no cancellation; not authorized, no despatch; not a
   draft, no delete.

Every negative case is paired with the POSITIVE path proving the guard did not simply break the
feature (L44). All dates derive from ``timezone.localdate()`` (never ``date.today()``) so nothing
here flakes in the hours after local midnight (L16).
"""
import datetime
from decimal import Decimal

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.accounting.models import JournalEntry
from apps.core.models import AuditLog
from apps.core.utils import write_audit_log
from apps.procurement.models import (
    ReceiptDiscrepancy,
    ReceiptTolerancePolicy,
    ReturnToVendor,
    ReturnToVendorLine,
)
from apps.scm.models import GoodsReceiptLine, GoodsReceiptNote, LotSerial, StockMove

pytestmark = pytest.mark.django_db


# ------------------------------------------------------------------ helpers (module-private)
def _receipt_iso(offset_days=0):
    """A date string relative to TODAY as the CODE sees it — ``timezone.localdate()`` (L16)."""
    return (timezone.localdate() + datetime.timedelta(days=offset_days)).isoformat()


def _receipt_policy_payload(**overrides):
    """A complete, valid ``ReceiptTolerancePolicyForm`` POST body.

    ``priority`` is not optional: the model default (10) makes the FORM field required with an
    initial, not blankable. ``over_receipt_pct`` satisfies the model's "declare at least one
    band" rule.
    """
    payload = {
        "name": "Crafted band",
        "item": "",
        "category": "",
        "vendor": "",
        "over_receipt_pct": "5",
        "under_receipt_pct": "",
        "over_receipt_qty": "",
        "early_receipt_days": "",
        "late_receipt_days": "",
        "action": "warn",
        "price_variance_pct": "",
        "priority": "10",
        "is_active": "on",
        "notes": "",
    }
    payload.update(overrides)
    return payload


def _receipt_discrepancy_payload(**overrides):
    """A complete, valid ``ReceiptDiscrepancyForm`` POST body (``goods_receipt`` supplied by the
    caller — the EDIT form pops that field out of ``self.fields`` entirely)."""
    payload = {
        "goods_receipt_line": "",
        "kind": "short_shipment",
        "severity": "major",
        "quantity_affected": "2",
        "item_description": "",
        "sku_hint": "",
        "lot_number": "",
        "serial_number": "",
        "expiry_date": "",
        "description": "Crafted finding.",
        "evidence_url": "",
        "remedy": "pending",
        "vendor_reference": "",
        "nonconformance": "",
        "quarantine_order": "",
        "return_to_vendor": "",
    }
    payload.update(overrides)
    return payload


def _receipt_rtv_payload(**overrides):
    """A complete, valid ``ReturnToVendorForm`` POST body."""
    payload = {
        "vendor": "",
        "purchase_order": "",
        "goods_receipt": "",
        "discrepancy": "",
        "reason": "damaged",
        "reason_note": "",
        "remedy": "credit",
        "supplier_rma_number": "",
        "carrier_name": "",
        "tracking_number": "",
        "expected_return_date": "",
        "credit_note_ref": "",
        "notes": "",
    }
    payload.update(overrides)
    return payload


def _receipt_rtv_lines_payload(rows=(), initial=0, total=None):
    """``ReturnToVendorLineFormSet`` management form + rows. POST prefix is ``lines`` (pinned)."""
    payload = {
        "lines-TOTAL_FORMS": str(len(rows) if total is None else total),
        "lines-INITIAL_FORMS": str(initial),
        "lines-MIN_NUM_FORMS": "0",
        "lines-MAX_NUM_FORMS": "50",
    }
    for index, row in enumerate(rows):
        for key, value in row.items():
            payload["lines-%d-%s" % (index, key)] = value
    return payload


def _receipt_book_payload(quantities=None, **overrides):
    """A ``ReceivingConsoleBookForm`` POST body. ``quantities`` is ``{asn_line_pk: value}`` and
    becomes the dynamic ``qty_<pk>`` inputs — the byte-for-byte contract with the template."""
    payload = {"receipt_date": _receipt_iso(), "location": "", "notes": ""}
    for line_pk, value in (quantities or {}).items():
        payload["qty_%s" % line_pk] = value
    payload.update(overrides)
    return payload


def _receipt_policy_state(obj):
    """Every column a crafted request might move on a tolerance rule — the freeze probe."""
    obj.refresh_from_db()
    return (obj.tenant_id, obj.name, obj.item_id, obj.category_id, obj.vendor_id,
            obj.over_receipt_pct, obj.under_receipt_pct, obj.over_receipt_qty,
            obj.allow_unlimited_over_receipt, obj.early_receipt_days, obj.late_receipt_days,
            obj.action, obj.price_variance_pct, obj.priority, obj.is_active, obj.notes)


def _receipt_discrepancy_state(obj):
    obj.refresh_from_db()
    return (obj.tenant_id, obj.status, obj.number, obj.goods_receipt_id,
            obj.goods_receipt_line_id, obj.kind, obj.severity, obj.quantity_affected,
            obj.description, obj.remedy, obj.vendor_reference, obj.vendor_notified_on,
            obj.resolved_at, obj.resolved_by_id, obj.resolution_notes, obj.nonconformance_id,
            obj.quarantine_order_id, obj.return_to_vendor_id, obj.created_by_id)


def _receipt_rtv_state(obj):
    obj.refresh_from_db()
    return (obj.tenant_id, obj.status, obj.number, obj.vendor_id, obj.purchase_order_id,
            obj.goods_receipt_id, obj.discrepancy_id, obj.reason, obj.reason_note, obj.remedy,
            obj.supplier_rma_number, obj.carrier_name, obj.tracking_number, obj.shipped_on,
            obj.expected_return_date, obj.credit_note_ref, obj.authorized_by_id,
            obj.authorized_at, obj.closed_at, obj.cancelled_at, obj.cancellation_reason,
            obj.created_by_id)


#: Every 6.12 page that RENDERS: (url name, needs a pk).
_RECEIPT_READ_ROUTES = (
    ("procurement:tolerancepolicy_list", False),
    ("procurement:tolerancepolicy_create", False),
    ("procurement:tolerancepolicy_detail", True),
    ("procurement:tolerancepolicy_edit", True),
    ("procurement:discrepancy_list", False),
    ("procurement:discrepancy_create", False),
    ("procurement:discrepancy_detail", True),
    ("procurement:discrepancy_edit", True),
    ("procurement:rtv_list", False),
    ("procurement:rtv_create", False),
    ("procurement:rtv_detail", True),
    ("procurement:rtv_edit", True),
    ("procurement:receiving_console", False),
    ("procurement:tolerance_exceptions", False),
    ("procurement:receipt_audit", False),
)

#: The six pages that page rows. Registers use ``crud_list``'s default 15; the three computed
#: boards use ``ReceiptBoards.BOARD_PER_PAGE`` (30).
_RECEIPT_PAGED_ROUTES = (
    "procurement:tolerancepolicy_list",
    "procurement:discrepancy_list",
    "procurement:rtv_list",
    "procurement:receiving_console",
    "procurement:tolerance_exceptions",
    "procurement:receipt_audit",
)

#: Every POST-only verb in 6.12, with a body that would otherwise succeed.
_RECEIPT_VERB_ROUTES = (
    ("procurement:tolerancepolicy_delete", "policy", {}),
    ("procurement:discrepancy_delete", "discrepancy", {}),
    ("procurement:discrepancy_notify_vendor", "discrepancy", {"vendor_reference": "SUP-1"}),
    ("procurement:discrepancy_resolve", "discrepancy",
     {"remedy": "credit", "resolution_notes": "crafted"}),
    ("procurement:discrepancy_cancel", "discrepancy", {"resolution_notes": "crafted"}),
    ("procurement:rtv_delete", "rtv", {}),
    ("procurement:rtv_authorize", "rtv", {}),
    ("procurement:rtv_ship", "rtv", {"carrier_name": "crafted"}),
    ("procurement:rtv_close", "rtv", {"credit_note_ref": "CN-CRAFT"}),
    ("procurement:rtv_cancel", "rtv", {"cancellation_reason": "crafted"}),
    ("procurement:receiving_console_book", "asn", {}),
    ("procurement:receiving_console_mint_lots", "asn", {}),
)

#: The seven routes ``@tenant_admin_required`` guards in 6.12.
_RECEIPT_ADMIN_ONLY_ROUTES = (
    ("procurement:tolerancepolicy_create", "none", "GET"),
    ("procurement:tolerancepolicy_edit", "policy", "GET"),
    ("procurement:tolerancepolicy_delete", "policy", "POST"),
    ("procurement:discrepancy_delete", "discrepancy", "POST"),
    ("procurement:rtv_delete", "rtv", "POST"),
    ("procurement:rtv_authorize", "rtv", "POST"),
    ("procurement:receiving_console_mint_lots", "asn", "POST"),
)


# ================================================================== 1. cross-tenant IDOR
def test_receipt_cross_tenant_pks_404_on_every_scoped_route(
        client_a, receipt_policy_b, receipt_discrepancy_b, receipt_rtv_b, receipt_asn_b,
        receipt_grn_b):
    """Tenant A's admin aiming any pk-scoped 6.12 route at a tenant-B row gets 404 — reads,
    edits, deletes and every workflow verb alike — and every tenant-B row is byte-identical
    afterwards. No lot/serial is minted out of B's declaration and no receipt is booked from it.
    """
    policy_b, disc_b, rtv_b, asn_b = (receipt_policy_b, receipt_discrepancy_b, receipt_rtv_b,
                                      receipt_asn_b)
    before = (_receipt_policy_state(policy_b), _receipt_discrepancy_state(disc_b),
              _receipt_rtv_state(rtv_b))
    grn_before = GoodsReceiptNote.objects.count()
    lots_before = LotSerial.objects.count()

    probes = [
        # --- ReceiptTolerancePolicy
        ("GET", "procurement:tolerancepolicy_detail", policy_b.pk, None),
        ("GET", "procurement:tolerancepolicy_edit", policy_b.pk, None),
        ("POST", "procurement:tolerancepolicy_edit", policy_b.pk,
         _receipt_policy_payload(name="hijacked")),
        ("POST", "procurement:tolerancepolicy_delete", policy_b.pk, None),
        # --- ReceiptDiscrepancy
        ("GET", "procurement:discrepancy_detail", disc_b.pk, None),
        ("GET", "procurement:discrepancy_edit", disc_b.pk, None),
        ("POST", "procurement:discrepancy_edit", disc_b.pk,
         _receipt_discrepancy_payload(description="hijacked")),
        ("POST", "procurement:discrepancy_delete", disc_b.pk, None),
        ("POST", "procurement:discrepancy_notify_vendor", disc_b.pk,
         {"vendor_reference": "STOLEN-CASE"}),
        ("POST", "procurement:discrepancy_resolve", disc_b.pk,
         {"remedy": "credit", "resolution_notes": "not yours"}),
        ("POST", "procurement:discrepancy_cancel", disc_b.pk, {"resolution_notes": "not yours"}),
        # --- ReturnToVendor
        ("GET", "procurement:rtv_detail", rtv_b.pk, None),
        ("GET", "procurement:rtv_edit", rtv_b.pk, None),
        ("POST", "procurement:rtv_edit", rtv_b.pk,
         dict(_receipt_rtv_payload(vendor=str(rtv_b.vendor_id)),
              **_receipt_rtv_lines_payload())),
        ("POST", "procurement:rtv_delete", rtv_b.pk, None),
        ("POST", "procurement:rtv_authorize", rtv_b.pk, None),
        ("POST", "procurement:rtv_ship", rtv_b.pk, {"carrier_name": "hijacked"}),
        ("POST", "procurement:rtv_close", rtv_b.pk, {"credit_note_ref": "CN-STOLEN"}),
        ("POST", "procurement:rtv_cancel", rtv_b.pk, {"cancellation_reason": "not yours"}),
        # --- the receiving console's two ASN verbs (the pk is the ASN's, not a receipt's)
        ("POST", "procurement:receiving_console_book", asn_b.pk, _receipt_book_payload({})),
        ("POST", "procurement:receiving_console_mint_lots", asn_b.pk, None),
    ]
    for method, name, pk, payload in probes:
        url = reverse(name, args=[pk])
        resp = client_a.post(url, payload or {}) if method == "POST" else client_a.get(url)
        assert resp.status_code == 404, (method, name)

    assert (_receipt_policy_state(policy_b), _receipt_discrepancy_state(disc_b),
            _receipt_rtv_state(rtv_b)) == before
    assert GoodsReceiptNote.objects.count() == grn_before
    assert LotSerial.objects.count() == lots_before
    assert ReceiptTolerancePolicy.objects.filter(pk=policy_b.pk).exists()
    assert ReceiptDiscrepancy.objects.filter(pk=disc_b.pk).exists()
    assert ReturnToVendor.objects.filter(pk=rtv_b.pk).exists()


def test_receipt_own_tenant_rows_reachable_on_the_same_routes(
        client_a, receipt_policy_catchall_a, receipt_discrepancy_open_a, receipt_rtv_draft_a):
    """L44 pair for the IDOR matrix: the identical routes against tenant A's OWN rows render —
    the 404s above are tenant scoping, not a broken URLconf or a missing template."""
    for name, obj in (
            ("procurement:tolerancepolicy_detail", receipt_policy_catchall_a),
            ("procurement:tolerancepolicy_edit", receipt_policy_catchall_a),
            ("procurement:discrepancy_detail", receipt_discrepancy_open_a),
            ("procurement:discrepancy_edit", receipt_discrepancy_open_a),
            ("procurement:rtv_detail", receipt_rtv_draft_a),
            ("procurement:rtv_edit", receipt_rtv_draft_a)):
        resp = client_a.get(reverse(name, args=[obj.pk]))
        assert resp.status_code == 200, name


# ================================================================== 2. register & board isolation
def test_receipt_registers_never_render_another_workspaces_rows(
        client_a, receipt_policy_catchall_a, receipt_discrepancy_open_a, receipt_rtv_draft_a,
        receipt_policy_b, receipt_discrepancy_b, receipt_rtv_b):
    """All three 6.12 registers, in one pass: tenant A's own row is present (positive) and tenant
    B's row is absent (negative) in the SAME response."""
    checks = (
        ("procurement:tolerancepolicy_list", receipt_policy_catchall_a.pk, receipt_policy_b.pk),
        ("procurement:discrepancy_list", receipt_discrepancy_open_a.pk,
         receipt_discrepancy_b.pk),
        ("procurement:rtv_list", receipt_rtv_draft_a.pk, receipt_rtv_b.pk),
    )
    for name, mine, theirs in checks:
        resp = client_a.get(reverse(name))
        assert resp.status_code == 200, name
        pks = [row.pk for row in resp.context["object_list"]]
        assert mine in pks, name
        assert theirs not in pks, name


def test_receipt_boards_never_render_another_workspaces_rows(
        client_a, receipt_asn_a, receipt_asn_line_a, receipt_grn_line_a, receipt_asn_b,
        receipt_grn_line_b, receipt_po_line_b):
    """The receiving console and the tolerance-exceptions board are COMPUTED — nothing narrows
    them but the tenant scoping itself, so a slip here shows another workspace's inbound freight
    and receipt lines on this dock's worklist.

    Tenant B's receipt line is pushed to 9 against 6 ordered first, so it genuinely qualifies for
    the ``over`` bucket: a row that dropped out for being in-tolerance would prove nothing.
    """
    GoodsReceiptLine.objects.filter(pk=receipt_grn_line_b.pk).update(
        quantity_received=Decimal("9"))

    resp = client_a.get(reverse("procurement:receiving_console"))
    assert resp.status_code == 200
    console_pks = [row.pk for row in resp.context["object_list"]]
    assert receipt_asn_a.pk in console_pks
    assert receipt_asn_b.pk not in console_pks
    assert all(row["asn"].tenant_id == receipt_asn_a.tenant_id for row in resp.context["rows"])

    resp = client_a.get(reverse("procurement:tolerance_exceptions"), {"bucket": "over"})
    assert resp.status_code == 200
    line_pks = [row.pk for row in resp.context["object_list"]]
    assert receipt_grn_line_a.pk in line_pks
    assert receipt_grn_line_b.pk not in line_pks


def test_receipt_audit_board_never_renders_another_workspaces_trail(
        client_a, admin_user, admin_b, receipt_discrepancy_open_a, receipt_discrepancy_b):
    """The audit board is a NARROWING of the shared ``core.AuditLog`` — the one 6.12 page whose
    rows are not tenant-scoped through their own table's FK chain, so it gets its own probe."""
    mine = write_audit_log(admin_user, receipt_discrepancy_open_a, "create")
    theirs = write_audit_log(admin_b, receipt_discrepancy_b, "create")
    assert theirs.tenant_id != mine.tenant_id

    resp = client_a.get(reverse("procurement:receipt_audit"))
    assert resp.status_code == 200
    pks = [row.pk for row in resp.context["object_list"]]
    assert mine.pk in pks
    assert theirs.pk not in pks
    assert list(resp.context["entries"]) == list(resp.context["object_list"])

    # A foreign ?grn= resolves to nothing rather than widening onto tenant B's receipt.
    resp = client_a.get(reverse("procurement:receipt_audit"),
                        {"grn": str(receipt_discrepancy_b.goods_receipt_id)})
    assert resp.status_code == 200
    assert resp.context["grn"] is None
    assert theirs.pk not in [row.pk for row in resp.context["object_list"]]


def test_receipt_tenantless_superuser_sees_nobodys_rows(
        db, receipt_policy_catchall_a, receipt_discrepancy_open_a, receipt_rtv_draft_a,
        receipt_policy_b):
    """The superuser carries ``tenant=None`` by design: the three registers come back EMPTY
    (never every workspace's rows), and every page that would WRITE refuses with a redirect to
    the dashboard rather than rendering a form that mints orphan rows."""
    from apps.accounts.models import User
    root = User.objects.create_superuser(email="root@naverp.test", username="root_receipt",
                                         password="TestPass123!")
    assert root.tenant is None
    c = Client()
    c.force_login(root)

    for name in ("procurement:tolerancepolicy_list", "procurement:discrepancy_list",
                 "procurement:rtv_list"):
        resp = c.get(reverse(name))
        assert resp.status_code == 200, name
        assert list(resp.context["object_list"]) == [], name

    home = reverse("dashboard:home")
    for name in ("procurement:receiving_console", "procurement:tolerance_exceptions",
                 "procurement:receipt_audit", "procurement:tolerancepolicy_create",
                 "procurement:discrepancy_create", "procurement:rtv_create"):
        resp = c.get(reverse(name))
        assert resp.status_code == 302, name
        assert resp["Location"] == home, name

    # …and a tenant-scoped detail is a 404 for them too — not a back door into either workspace.
    for name, obj in (("procurement:tolerancepolicy_detail", receipt_policy_catchall_a),
                      ("procurement:discrepancy_detail", receipt_discrepancy_open_a),
                      ("procurement:rtv_detail", receipt_rtv_draft_a)):
        assert c.get(reverse(name, args=[obj.pk])).status_code == 404, name


# ================================================================== 3. the authz ladder
def test_receipt_anonymous_redirected_to_login_on_every_route(
        db, receipt_policy_catchall_a, receipt_discrepancy_open_a, receipt_rtv_draft_a,
        receipt_asn_a, receipt_asn_line_a):
    """No 6.12 URL — page or verb — answers an unauthenticated request; each one bounces to the
    accounts login, and every row is untouched afterwards."""
    anon = Client()
    login_prefix = reverse("accounts:login")
    before = (_receipt_policy_state(receipt_policy_catchall_a),
              _receipt_discrepancy_state(receipt_discrepancy_open_a),
              _receipt_rtv_state(receipt_rtv_draft_a))
    grn_before = GoodsReceiptNote.objects.count()

    pk_for = {
        "policy": receipt_policy_catchall_a.pk,
        "discrepancy": receipt_discrepancy_open_a.pk,
        "rtv": receipt_rtv_draft_a.pk,
        "asn": receipt_asn_a.pk,
    }
    detail_pk = {
        "procurement:tolerancepolicy_detail": pk_for["policy"],
        "procurement:tolerancepolicy_edit": pk_for["policy"],
        "procurement:discrepancy_detail": pk_for["discrepancy"],
        "procurement:discrepancy_edit": pk_for["discrepancy"],
        "procurement:rtv_detail": pk_for["rtv"],
        "procurement:rtv_edit": pk_for["rtv"],
    }
    for name, needs_pk in _RECEIPT_READ_ROUTES:
        url = reverse(name, args=[detail_pk[name]]) if needs_pk else reverse(name)
        resp = anon.get(url)
        assert resp.status_code == 302, name
        assert resp["Location"].startswith(login_prefix), name

    for name, kind, body in _RECEIPT_VERB_ROUTES:
        resp = anon.post(reverse(name, args=[pk_for[kind]]), body)
        assert resp.status_code == 302, name
        assert resp["Location"].startswith(login_prefix), name

    assert (_receipt_policy_state(receipt_policy_catchall_a),
            _receipt_discrepancy_state(receipt_discrepancy_open_a),
            _receipt_rtv_state(receipt_rtv_draft_a)) == before
    assert GoodsReceiptNote.objects.count() == grn_before


def test_receipt_member_refused_on_every_admin_only_route(
        member_client, receipt_policy_catchall_a, receipt_discrepancy_open_a,
        receipt_rtv_draft_a, receipt_asn_a, receipt_asn_line_a):
    """``@tenant_admin_required`` guards exactly seven 6.12 routes — the tolerance master's three
    writes (a rule decides what the WHOLE workspace flags), the two deletes that remove a row
    from the receiving trail, the RTV authorization signature, and lot minting. A plain workspace
    member gets PermissionDenied (403) on all seven and nothing moves."""
    pk_for = {
        "policy": receipt_policy_catchall_a.pk,
        "discrepancy": receipt_discrepancy_open_a.pk,
        "rtv": receipt_rtv_draft_a.pk,
        "asn": receipt_asn_a.pk,
    }
    before = (_receipt_policy_state(receipt_policy_catchall_a),
              _receipt_discrepancy_state(receipt_discrepancy_open_a),
              _receipt_rtv_state(receipt_rtv_draft_a))
    lots_before = LotSerial.objects.count()

    for name, kind, method in _RECEIPT_ADMIN_ONLY_ROUTES:
        url = reverse(name) if kind == "none" else reverse(name, args=[pk_for[kind]])
        resp = member_client.post(url, {}) if method == "POST" else member_client.get(url)
        assert resp.status_code == 403, name

    assert (_receipt_policy_state(receipt_policy_catchall_a),
            _receipt_discrepancy_state(receipt_discrepancy_open_a),
            _receipt_rtv_state(receipt_rtv_draft_a)) == before
    assert LotSerial.objects.count() == lots_before
    assert ReceiptTolerancePolicy.objects.filter(pk=receipt_policy_catchall_a.pk).exists()
    assert ReceiptDiscrepancy.objects.filter(pk=receipt_discrepancy_open_a.pk).exists()
    assert ReturnToVendor.objects.filter(pk=receipt_rtv_draft_a.pk).exists()


def test_receipt_member_may_use_every_other_route(
        member_client, receipt_policy_catchall_a, receipt_discrepancy_open_a,
        receipt_rtv_shipped_a, receipt_asn_a, receipt_asn_line_a, receipt_grn_line_a):
    """L44 pair for the admin gate: 6.12 is deliberately open to any workspace member everywhere
    else — the person on the dock is the person who saw the pallet. Every read renders, a finding
    can be worked, a shipped return can be closed, and — the one the gate must NOT catch — the
    receiving console's BOOK verb stays member-visible."""
    for name in ("procurement:tolerancepolicy_list", "procurement:discrepancy_list",
                 "procurement:rtv_list", "procurement:receiving_console",
                 "procurement:tolerance_exceptions", "procurement:receipt_audit",
                 "procurement:discrepancy_create", "procurement:rtv_create"):
        assert member_client.get(reverse(name)).status_code == 200, name
    assert member_client.get(reverse("procurement:tolerancepolicy_detail",
                                     args=[receipt_policy_catchall_a.pk])).status_code == 200

    resp = member_client.post(
        reverse("procurement:discrepancy_notify_vendor", args=[receipt_discrepancy_open_a.pk]),
        {"vendor_reference": "SUP-CASE-42"})
    assert resp.status_code == 302
    receipt_discrepancy_open_a.refresh_from_db()
    assert receipt_discrepancy_open_a.status == "vendor_notified"

    resp = member_client.post(reverse("procurement:rtv_close", args=[receipt_rtv_shipped_a.pk]),
                              {"credit_note_ref": "CN-7788"})
    assert resp.status_code == 302
    receipt_rtv_shipped_a.refresh_from_db()
    assert receipt_rtv_shipped_a.status == "closed"

    grn_before = GoodsReceiptNote.objects.count()
    resp = member_client.post(
        reverse("procurement:receiving_console_book", args=[receipt_asn_a.pk]),
        _receipt_book_payload({receipt_asn_line_a.pk: "5"}))
    assert resp.status_code == 302
    assert GoodsReceiptNote.objects.count() == grn_before + 1


def test_receipt_csrf_enforced_on_every_post_route(
        admin_user, receipt_policy_catchall_a, receipt_discrepancy_open_a, receipt_rtv_draft_a,
        receipt_asn_a, receipt_asn_line_a, receipt_grn_a, receipt_vendor_a):
    """A logged-in session is not enough: every mutating 6.12 POST needs a CSRF token. Without
    one each is rejected 403 and nothing is created, moved or deleted."""
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(admin_user)

    before = (_receipt_policy_state(receipt_policy_catchall_a),
              _receipt_discrepancy_state(receipt_discrepancy_open_a),
              _receipt_rtv_state(receipt_rtv_draft_a))
    counts = {model: model.objects.count() for model in
              (ReceiptTolerancePolicy, ReceiptDiscrepancy, ReturnToVendor, ReturnToVendorLine,
               GoodsReceiptNote, GoodsReceiptLine, LotSerial)}

    posts = [
        (reverse("procurement:tolerancepolicy_create"), _receipt_policy_payload()),
        (reverse("procurement:tolerancepolicy_edit", args=[receipt_policy_catchall_a.pk]),
         _receipt_policy_payload()),
        (reverse("procurement:tolerancepolicy_delete", args=[receipt_policy_catchall_a.pk]), {}),
        (reverse("procurement:discrepancy_create"),
         _receipt_discrepancy_payload(goods_receipt=str(receipt_grn_a.pk))),
        (reverse("procurement:discrepancy_edit", args=[receipt_discrepancy_open_a.pk]),
         _receipt_discrepancy_payload()),
        (reverse("procurement:discrepancy_delete", args=[receipt_discrepancy_open_a.pk]), {}),
        (reverse("procurement:discrepancy_notify_vendor",
                 args=[receipt_discrepancy_open_a.pk]), {"vendor_reference": "NO-TOKEN"}),
        (reverse("procurement:discrepancy_resolve", args=[receipt_discrepancy_open_a.pk]),
         {"remedy": "credit", "resolution_notes": "no token"}),
        (reverse("procurement:discrepancy_cancel", args=[receipt_discrepancy_open_a.pk]),
         {"resolution_notes": "no token"}),
        (reverse("procurement:rtv_create"),
         _receipt_rtv_payload(vendor=str(receipt_vendor_a.pk))),
        (reverse("procurement:rtv_edit", args=[receipt_rtv_draft_a.pk]),
         dict(_receipt_rtv_payload(vendor=str(receipt_vendor_a.pk)),
              **_receipt_rtv_lines_payload())),
        (reverse("procurement:rtv_delete", args=[receipt_rtv_draft_a.pk]), {}),
        (reverse("procurement:rtv_authorize", args=[receipt_rtv_draft_a.pk]), {}),
        (reverse("procurement:rtv_ship", args=[receipt_rtv_draft_a.pk]), {}),
        (reverse("procurement:rtv_close", args=[receipt_rtv_draft_a.pk]), {}),
        (reverse("procurement:rtv_cancel", args=[receipt_rtv_draft_a.pk]),
         {"cancellation_reason": "no token"}),
        (reverse("procurement:receiving_console_book", args=[receipt_asn_a.pk]),
         _receipt_book_payload({receipt_asn_line_a.pk: "5"})),
        (reverse("procurement:receiving_console_mint_lots", args=[receipt_asn_a.pk]), {}),
    ]
    for url, body in posts:
        assert csrf_client.post(url, body).status_code == 403, url

    assert (_receipt_policy_state(receipt_policy_catchall_a),
            _receipt_discrepancy_state(receipt_discrepancy_open_a),
            _receipt_rtv_state(receipt_rtv_draft_a)) == before
    for model, count in counts.items():
        assert model.objects.count() == count, model.__name__

    # L44 pair: the SAME csrf-enforcing session reads happily — only unsafe methods are gated.
    assert csrf_client.get(
        reverse("procurement:rtv_detail", args=[receipt_rtv_draft_a.pk])).status_code == 200


def test_receipt_get_on_post_only_verbs_is_405_and_never_mutates(
        client_a, receipt_policy_catchall_a, receipt_discrepancy_open_a, receipt_rtv_draft_a,
        receipt_asn_a, receipt_asn_line_a):
    """``@require_POST`` fires before ``crud_delete``'s own self-defence: a GET on any 6.12 verb
    URL is refused outright and every row survives untouched."""
    pk_for = {
        "policy": receipt_policy_catchall_a.pk,
        "discrepancy": receipt_discrepancy_open_a.pk,
        "rtv": receipt_rtv_draft_a.pk,
        "asn": receipt_asn_a.pk,
    }
    before = (_receipt_policy_state(receipt_policy_catchall_a),
              _receipt_discrepancy_state(receipt_discrepancy_open_a),
              _receipt_rtv_state(receipt_rtv_draft_a))
    counts = {model: model.objects.count() for model in
              (ReceiptTolerancePolicy, ReceiptDiscrepancy, ReturnToVendor, GoodsReceiptNote,
               LotSerial)}

    for name, kind, _body in _RECEIPT_VERB_ROUTES:
        resp = client_a.get(reverse(name, args=[pk_for[kind]]))
        assert resp.status_code == 405, name

    assert (_receipt_policy_state(receipt_policy_catchall_a),
            _receipt_discrepancy_state(receipt_discrepancy_open_a),
            _receipt_rtv_state(receipt_rtv_draft_a)) == before
    for model, count in counts.items():
        assert model.objects.count() == count, model.__name__


# ================================================================== 4. mass assignment
def test_receipt_policy_create_rejects_another_workspaces_foreign_keys(
        client_a, receipt_item_b, receipt_category_b, receipt_vendor_b):
    """A narrowed ``<select>`` is UX, not a boundary: a hand-crafted POST naming tenant B's item,
    category or supplier lands as a FIELD error and saves nothing. Each scope is posted on its
    own — the model refuses item+category together for a different reason."""
    before = ReceiptTolerancePolicy.objects.count()
    url = reverse("procurement:tolerancepolicy_create")

    for field, value in (("item", receipt_item_b.pk), ("category", receipt_category_b.pk),
                         ("vendor", receipt_vendor_b.pk)):
        resp = client_a.post(url, _receipt_policy_payload(**{field: str(value)}))
        assert resp.status_code == 200, field
        assert field in resp.context["form"].errors, field
    assert ReceiptTolerancePolicy.objects.count() == before


def test_receipt_policy_create_stamps_the_request_tenant_and_ignores_a_forged_one(
        client_a, tenant_a, tenant_b, receipt_item_a, receipt_vendor_a):
    """L44 pair + mass-assignment probe: the legitimate create SUCCEEDS with tenant-A scopes, and
    the posted ``tenant`` is dropped on the floor — the rule lands on the REQUEST's workspace."""
    resp = client_a.post(reverse("procurement:tolerancepolicy_create"), _receipt_policy_payload(
        name="Legitimate band", item=str(receipt_item_a.pk), vendor=str(receipt_vendor_a.pk),
        tenant=str(tenant_b.pk), id="999999",
    ))
    assert resp.status_code == 302
    obj = ReceiptTolerancePolicy.objects.get(name="Legitimate band")
    assert obj.tenant_id == tenant_a.pk
    assert obj.item_id == receipt_item_a.pk
    assert obj.vendor_id == receipt_vendor_a.pk


def test_receipt_discrepancy_create_rejects_another_workspaces_foreign_keys(
        client_a, receipt_grn_a, receipt_grn_b, receipt_grn_line_b, receipt_nonconformance_b,
        receipt_quarantine_b, receipt_rtv_b):
    """Every tenant-scoped FK on the finding form, crafted at tenant B: the receipt itself, the
    receipt LINE (whose model carries no tenant column at all and is scoped through its header),
    and the three registers a finding escalates into."""
    before = ReceiptDiscrepancy.objects.count()
    url = reverse("procurement:discrepancy_create")

    crafted = (
        ("goods_receipt", _receipt_discrepancy_payload(goods_receipt=str(receipt_grn_b.pk))),
        ("goods_receipt_line", _receipt_discrepancy_payload(
            goods_receipt=str(receipt_grn_a.pk),
            goods_receipt_line=str(receipt_grn_line_b.pk))),
        ("nonconformance", _receipt_discrepancy_payload(
            goods_receipt=str(receipt_grn_a.pk),
            nonconformance=str(receipt_nonconformance_b.pk))),
        ("quarantine_order", _receipt_discrepancy_payload(
            goods_receipt=str(receipt_grn_a.pk),
            quarantine_order=str(receipt_quarantine_b.pk))),
        ("return_to_vendor", _receipt_discrepancy_payload(
            goods_receipt=str(receipt_grn_a.pk), return_to_vendor=str(receipt_rtv_b.pk))),
    )
    for field, body in crafted:
        resp = client_a.post(url, body)
        assert resp.status_code == 200, field
        assert field in resp.context["form"].errors, field
    assert ReceiptDiscrepancy.objects.count() == before


def test_receipt_discrepancy_create_ignores_forged_workflow_and_system_fields(
        client_a, tenant_a, tenant_b, admin_user, admin_b, receipt_grn_a, receipt_grn_line2_a):
    """L44 pair + the mass-assignment probe: the legitimate create SUCCEEDS, while ``status`` /
    ``number`` / ``tenant`` / ``created_by`` and the whole notify + closure stamp block are
    ignored — not one of them is a form field, so a crafted POST cannot open a finding that is
    already 'resolved by' somebody else."""
    resp = client_a.post(reverse("procurement:discrepancy_create"), _receipt_discrepancy_payload(
        goods_receipt=str(receipt_grn_a.pk),
        goods_receipt_line=str(receipt_grn_line2_a.pk),
        description="Three cartons short on the pallet.",
        # every one of these is server-owned and must be dropped on the floor
        tenant=str(tenant_b.pk),
        status="resolved",
        number="RDS-99999",
        created_by=str(admin_b.pk),
        resolved_by=str(admin_b.pk),
        resolved_at="2020-01-01T10:00",
        resolution_notes="forged agreement",
        vendor_notified_on="2020-01-01",
    ))
    assert resp.status_code == 302
    obj = ReceiptDiscrepancy.objects.filter(tenant=tenant_a).latest("id")
    assert obj.tenant_id == tenant_a.pk
    assert obj.status == "open"                     # lifecycle is verb-only
    assert obj.number != "RDS-99999"
    assert obj.number.startswith("RDS-")
    assert obj.created_by_id == admin_user.pk       # the signed-in user, not the posted one
    assert obj.resolved_by_id is None
    assert obj.resolved_at is None
    assert obj.resolution_notes == ""
    assert obj.vendor_notified_on is None


def test_receipt_discrepancy_edit_cannot_repoint_the_receipt(
        client_a, receipt_discrepancy_open_a, receipt_grn_a, receipt_grn_b,
        receipt_grn_line2_a):
    """The edit form POPS ``goods_receipt`` out of ``self.fields`` entirely — re-pointing a saved
    finding would orphan its ``goods_receipt_line``. A POST naming another workspace's receipt is
    therefore not rejected but IGNORED, and the finding keeps its own origin."""
    resp = client_a.post(
        reverse("procurement:discrepancy_edit", args=[receipt_discrepancy_open_a.pk]),
        _receipt_discrepancy_payload(goods_receipt=str(receipt_grn_b.pk),
                                     goods_receipt_line=str(receipt_grn_line2_a.pk),
                                     description="Corrected: two cartons short."))
    assert resp.status_code == 302
    receipt_discrepancy_open_a.refresh_from_db()
    assert receipt_discrepancy_open_a.goods_receipt_id == receipt_grn_a.pk
    # L44 pair: the edit really did land — the guard did not simply refuse the whole POST.
    assert receipt_discrepancy_open_a.description == "Corrected: two cartons short."


def test_receipt_rtv_create_rejects_another_workspaces_foreign_keys(
        client_a, receipt_vendor_a, receipt_vendor_b, receipt_po_b, receipt_grn_b,
        receipt_discrepancy_b):
    """All four tenant-scoped FKs on the return header, crafted at tenant B."""
    before = ReturnToVendor.objects.count()
    url = reverse("procurement:rtv_create")

    crafted = (
        ("vendor", _receipt_rtv_payload(vendor=str(receipt_vendor_b.pk))),
        ("purchase_order", _receipt_rtv_payload(vendor=str(receipt_vendor_a.pk),
                                                purchase_order=str(receipt_po_b.pk))),
        ("goods_receipt", _receipt_rtv_payload(vendor=str(receipt_vendor_a.pk),
                                               goods_receipt=str(receipt_grn_b.pk))),
        ("discrepancy", _receipt_rtv_payload(vendor=str(receipt_vendor_a.pk),
                                             discrepancy=str(receipt_discrepancy_b.pk))),
    )
    for field, body in crafted:
        resp = client_a.post(url, body)
        assert resp.status_code == 200, field
        assert field in resp.context["form"].errors, field
    assert ReturnToVendor.objects.count() == before


def test_receipt_rtv_create_rejects_a_same_tenant_counterparty_mismatch(
        client_a, receipt_vendor_other_a, receipt_po_a):
    """Tenancy is not the whole boundary: returning goods to a supplier OTHER than the one the
    order was placed with is refused even though both rows live in this workspace — the credit
    would otherwise be quoted off another supplier's prices."""
    before = ReturnToVendor.objects.count()
    resp = client_a.post(reverse("procurement:rtv_create"), _receipt_rtv_payload(
        vendor=str(receipt_vendor_other_a.pk), purchase_order=str(receipt_po_a.pk)))
    assert resp.status_code == 200
    assert resp.context["form"].errors
    assert ReturnToVendor.objects.count() == before


def test_receipt_rtv_create_ignores_forged_workflow_and_system_fields(
        client_a, tenant_a, tenant_b, admin_user, admin_b, receipt_vendor_a, receipt_po_a,
        receipt_grn_a):
    """L44 pair + mass-assignment probe: the legitimate return is raised, while ``status`` /
    ``number`` / ``tenant`` / ``created_by`` and every verb stamp (``authorized_by``,
    ``shipped_on``, ``closed_at``, ``cancellation_reason``) are ignored. A crafted POST must not
    be able to mint a return that is already authorized by somebody else."""
    resp = client_a.post(reverse("procurement:rtv_create"), _receipt_rtv_payload(
        vendor=str(receipt_vendor_a.pk),
        purchase_order=str(receipt_po_a.pk),
        goods_receipt=str(receipt_grn_a.pk),
        supplier_rma_number="RMA-LEGIT",
        tenant=str(tenant_b.pk),
        status="closed",
        number="RTV-99999",
        created_by=str(admin_b.pk),
        authorized_by=str(admin_b.pk),
        authorized_at="2020-01-01T10:00",
        shipped_on="2020-01-01",
        closed_at="2020-01-01T10:00",
        cancellation_reason="forged",
    ))
    assert resp.status_code == 302
    obj = ReturnToVendor.objects.get(tenant=tenant_a, supplier_rma_number="RMA-LEGIT")
    assert obj.tenant_id == tenant_a.pk
    assert obj.status == "draft"                    # lifecycle is verb-only
    assert obj.number != "RTV-99999"
    assert obj.number.startswith("RTV-")
    assert obj.created_by_id == admin_user.pk
    assert obj.authorized_by_id is None
    assert obj.authorized_at is None
    assert obj.shipped_on is None
    assert obj.closed_at is None
    assert obj.cancellation_reason == ""


def test_receipt_rtv_line_formset_rejects_another_workspaces_lines(
        client_a, receipt_rtv_draft_a, receipt_vendor_a, receipt_po_a, receipt_grn_a,
        receipt_grn_line_b, receipt_po_line_b):
    """``scm.GoodsReceiptLine`` and ``scm.PurchaseOrderLine`` carry NO tenant column, so the line
    formset scopes both through their headers. A crafted row naming tenant B's receipt line or
    ordered line lands as a FIELD error on that row and saves nothing."""
    before = ReturnToVendorLine.objects.count()
    url = reverse("procurement:rtv_edit", args=[receipt_rtv_draft_a.pk])
    header = _receipt_rtv_payload(vendor=str(receipt_vendor_a.pk),
                                  purchase_order=str(receipt_po_a.pk),
                                  goods_receipt=str(receipt_grn_a.pk),
                                  supplier_rma_number="RMA-77")

    for field, row in (("goods_receipt_line",
                        {"goods_receipt_line": str(receipt_grn_line_b.pk),
                         "quantity_returned": "1"}),
                       ("po_line",
                        {"po_line": str(receipt_po_line_b.pk), "quantity_returned": "1"})):
        resp = client_a.post(url, dict(header, **_receipt_rtv_lines_payload([row])))
        assert resp.status_code == 200, field
        assert field in resp.context["formset"].errors[0], field
    assert ReturnToVendorLine.objects.count() == before


def test_receipt_rtv_line_formset_accepts_this_workspaces_own_line(
        client_a, receipt_rtv_draft_a, receipt_vendor_a, receipt_po_a, receipt_po_line_a,
        receipt_grn_a):
    """L44 pair for the formset boundary: tenant A's OWN ordered line saves, and the expected
    credit is DERIVED from it (3 x 25.00) rather than stored on the header."""
    body = dict(
        _receipt_rtv_payload(vendor=str(receipt_vendor_a.pk),
                             purchase_order=str(receipt_po_a.pk),
                             goods_receipt=str(receipt_grn_a.pk),
                             supplier_rma_number="RMA-77"),
        **_receipt_rtv_lines_payload([{"po_line": str(receipt_po_line_a.pk),
                                       "quantity_returned": "3"}]))
    resp = client_a.post(reverse("procurement:rtv_edit", args=[receipt_rtv_draft_a.pk]), body)
    assert resp.status_code == 302
    receipt_rtv_draft_a.refresh_from_db()
    assert receipt_rtv_draft_a.lines.count() == 1
    assert receipt_rtv_draft_a.expected_credit_value == Decimal("75.00")


def test_receipt_console_book_rejects_another_workspaces_location(
        client_a, receipt_asn_a, receipt_asn_line_a, receipt_location_b):
    """``location`` is a ``ModelChoiceField`` whose queryset IS the authorization boundary: a
    crafted POST cannot land tenant A's receipt in tenant B's warehouse. The console has nowhere
    to render a bound form, so the refusal is a message + redirect — and NO receipt is minted."""
    before = GoodsReceiptNote.objects.count()
    resp = client_a.post(
        reverse("procurement:receiving_console_book", args=[receipt_asn_a.pk]),
        _receipt_book_payload({receipt_asn_line_a.pk: "5"},
                              location=str(receipt_location_b.pk)))
    assert resp.status_code == 302
    assert resp["Location"] == reverse("procurement:receiving_console")
    assert GoodsReceiptNote.objects.count() == before


def test_receipt_console_book_accepts_this_workspaces_own_location(
        client_a, tenant_a, admin_user, receipt_asn_a, receipt_asn_line_a, receipt_location_a):
    """L44 pair: the same POST with tenant A's OWN dock books a DRAFT receipt, stamped with the
    request's tenant, the signed-in receiver and the shipment's delivery-note key."""
    resp = client_a.post(
        reverse("procurement:receiving_console_book", args=[receipt_asn_a.pk]),
        _receipt_book_payload({receipt_asn_line_a.pk: "5"},
                              location=str(receipt_location_a.pk)))
    assert resp.status_code == 302
    receipt = GoodsReceiptNote.objects.get(delivery_note_ref="NW-DN-7001")
    assert resp["Location"] == reverse("scm:goodsreceipt_detail", args=[receipt.pk])
    assert receipt.tenant_id == tenant_a.pk
    assert receipt.status == "draft"           # booking the STOCK stays scm:goodsreceipt_receive
    assert receipt.location_id == receipt_location_a.pk
    assert receipt.received_by_id == admin_user.pk
    assert receipt.lines.count() == 1


def test_receipt_console_book_drops_a_quantity_crafted_for_another_shipments_line(
        client_a, receipt_asn_a, receipt_asn_line_a, receipt_asn_no_reference_a):
    """The dynamic ``qty_<pk>`` fields are declared from THIS shipment's own lines, so a crafted
    quantity for another ASN's line is a field the form does not have: it is dropped rather than
    applied. With this shipment's own line left blank the total is zero, the declaration is
    refused, and no GRN number is burned."""
    foreign_line = receipt_asn_no_reference_a.lines.order_by("id").first()
    assert foreign_line is not None and foreign_line.asn_id != receipt_asn_a.pk
    before = GoodsReceiptNote.objects.count()

    resp = client_a.post(
        reverse("procurement:receiving_console_book", args=[receipt_asn_a.pk]),
        _receipt_book_payload({receipt_asn_line_a.pk: "", foreign_line.pk: "5"}))
    assert resp.status_code == 302
    assert resp["Location"] == reverse("procurement:receiving_console")
    assert GoodsReceiptNote.objects.count() == before
    # …and the foreign shipment's ordered line gained no receipt line either.
    assert not GoodsReceiptLine.objects.filter(
        po_line_id=foreign_line.po_line_id,
        goods_receipt__delivery_note_ref="NW-DN-7001").exists()


# ================================================================== 5. hostile input
def test_receipt_junk_fk_filter_params_never_500_on_any_page(
        client_a, receipt_policy_catchall_a, receipt_discrepancy_open_a, receipt_rtv_draft_a,
        receipt_asn_a, receipt_asn_line_a, receipt_grn_line_a):
    """L11 across the whole lane: a non-numeric, over-64-bit or Unicode-superscript pk in any FK
    filter param must SKIP the filter, never reach the driver. ``²`` is the sharp one —
    ``isdigit()`` is True for it but ``int()`` refuses it."""
    junk = ("abc", "999999999999999999999", "²", "-1", "1.5", "", "' OR 1=1--")
    probes = (
        ("procurement:tolerancepolicy_list", ("item", "vendor")),
        ("procurement:discrepancy_list", ("grn", "vendor")),
        ("procurement:rtv_list", ("vendor", "po")),
        ("procurement:receiving_console", ("vendor", "po")),
        ("procurement:tolerance_exceptions", ("vendor",)),
        ("procurement:receipt_audit", ("grn",)),
    )
    for name, params in probes:
        for param in params:
            for value in junk:
                resp = client_a.get(reverse(name), {param: value})
                assert resp.status_code == 200, (name, param, value)


def test_receipt_junk_enum_params_are_sanitized_and_echoed_back(
        client_a, receipt_policy_catchall_a, receipt_discrepancy_open_a, receipt_rtv_draft_a,
        receipt_asn_a, receipt_asn_line_a, receipt_grn_line_a):
    """A hand-edited enum must never render an empty page under a widget that still reads "All".
    Every closed vocabulary in 6.12 sanitizes to its own fallback and echoes THAT back."""
    resp = client_a.get(reverse("procurement:tolerancepolicy_list"),
                        {"scope": "zzz", "action": "zzz", "active": "abc"})
    assert resp.status_code == 200
    assert resp.context["scope"] == ""

    for params in ({"status": "zzz"}, {"kind": "zzz"}, {"severity": "zzz"}, {"remedy": "zzz"}):
        assert client_a.get(reverse("procurement:discrepancy_list"),
                            params).status_code == 200, params
    for params in ({"status": "zzz"}, {"reason": "zzz"}, {"remedy": "zzz"}):
        assert client_a.get(reverse("procurement:rtv_list"), params).status_code == 200, params

    # The console hides draft/cancelled, so even a REAL-but-unshowable status is sanitized away.
    for value in ("zzz", "draft", "cancelled"):
        resp = client_a.get(reverse("procurement:receiving_console"), {"status": value})
        assert resp.status_code == 200, value
        assert resp.context["status"] == "", value
    resp = client_a.get(reverse("procurement:receiving_console"), {"arrival": "zzz"})
    assert resp.status_code == 200
    assert resp.context["arrival"] == ""

    resp = client_a.get(reverse("procurement:tolerance_exceptions"), {"bucket": "zzz"})
    assert resp.status_code == 200
    assert resp.context["bucket"] == "over"        # DEFAULT_BUCKET, never an accidental blank

    resp = client_a.get(reverse("procurement:receipt_audit"), {"action": "zzz"})
    assert resp.status_code == 200
    assert resp.context["action"] == ""


def test_receipt_real_filter_values_still_narrow(
        client_a, receipt_policy_catchall_a, receipt_policy_item_a, receipt_item_a,
        receipt_discrepancy_open_a, receipt_discrepancy_resolved_a, receipt_rtv_draft_a,
        receipt_rtv_shipped_a, receipt_asn_a, receipt_asn_line_a, receipt_grn_line_a,
        receipt_grn_line2_a):
    """L44 pair for the whole sanitizing layer: the guards skip JUNK, not everything. Each filter
    below narrows to exactly the rows it names."""
    resp = client_a.get(reverse("procurement:tolerancepolicy_list"),
                        {"item": str(receipt_item_a.pk)})
    assert [row.pk for row in resp.context["object_list"]] == [receipt_policy_item_a.pk]

    resp = client_a.get(reverse("procurement:tolerancepolicy_list"), {"scope": "catchall"})
    assert resp.context["scope"] == "catchall"
    assert receipt_policy_item_a.pk not in [row.pk for row in resp.context["object_list"]]

    resp = client_a.get(reverse("procurement:discrepancy_list"), {"status": "resolved"})
    pks = [row.pk for row in resp.context["object_list"]]
    assert receipt_discrepancy_resolved_a.pk in pks
    assert receipt_discrepancy_open_a.pk not in pks

    resp = client_a.get(reverse("procurement:rtv_list"), {"status": "shipped"})
    pks = [row.pk for row in resp.context["object_list"]]
    assert receipt_rtv_shipped_a.pk in pks
    assert receipt_rtv_draft_a.pk not in pks

    resp = client_a.get(reverse("procurement:receiving_console"), {"arrival": "today"})
    assert resp.context["arrival"] == "today"
    assert receipt_asn_a.pk in [row.pk for row in resp.context["object_list"]]

    resp = client_a.get(reverse("procurement:tolerance_exceptions"), {"bucket": "short"})
    assert resp.context["bucket"] == "short"
    pks = [row.pk for row in resp.context["object_list"]]
    assert receipt_grn_line2_a.pk in pks           # 1 received against 4 ordered
    assert receipt_grn_line_a.pk not in pks        # 12 against 10 is the OVER bucket


def test_receipt_cancelled_receipts_are_excluded_from_every_bucket(
        client_a, receipt_grn_cancelled_a, receipt_grn_line_a, receipt_asn_a,
        receipt_asn_line_a):
    """A cancelled receipt never happened: none of its lines may appear in any tolerance bucket,
    whatever the arithmetic would otherwise say about them."""
    cancelled_line = receipt_grn_cancelled_a.lines.order_by("id").first()
    for bucket in ("over", "short", "early", "late"):
        resp = client_a.get(reverse("procurement:tolerance_exceptions"), {"bucket": bucket})
        assert resp.status_code == 200, bucket
        assert cancelled_line.pk not in [row.pk for row in resp.context["object_list"]], bucket


def test_receipt_page_junk_and_page_past_the_end_are_always_200(
        client_a, receipt_policy_catchall_a, receipt_discrepancy_open_a, receipt_rtv_draft_a,
        receipt_asn_a, receipt_asn_line_a, receipt_grn_line_a):
    """L9: ``?page=`` is user input. A junk token, a negative, a zero and a page far past the end
    all clamp to a real page rather than raising ``EmptyPage``."""
    for name in _RECEIPT_PAGED_ROUTES:
        for value in ("abc", "999", "0", "-3", "", "1e5"):
            resp = client_a.get(reverse(name), {"page": value})
            assert resp.status_code == 200, (name, value)


def test_receipt_page_two_renders_when_rows_exceed_the_page_size(
        client_a, tenant_a, receipt_policy_catchall_a):
    """L44 pair for the pagination guard: with 16 rows against ``crud_list``'s default 15, page 2
    is a real page carrying the sixteenth row — the clamp above did not break paging."""
    for index in range(15):
        ReceiptTolerancePolicy.objects.create(
            tenant=tenant_a, name="Bulk band %02d" % index, over_receipt_pct=Decimal("1"),
            priority=20 + index)
    assert ReceiptTolerancePolicy.objects.filter(tenant=tenant_a).count() == 16

    resp = client_a.get(reverse("procurement:tolerancepolicy_list"), {"page": "2"})
    assert resp.status_code == 200
    page = resp.context["page_obj"]
    assert page.number == 2
    assert page.paginator.num_pages == 2
    assert len(resp.context["object_list"]) == 1
    assert resp.context["stats"]["total"] == 16


def test_receipt_discrepancy_prefill_refuses_every_hostile_quantity(client_a, receipt_grn_a):
    """L35 / L11, decimal edition. ``?quantity_affected=`` is hand-parsed from the query string:
    ``NaN`` and ``Infinity`` PARSE cleanly and it is the comparison (or the save) that then dies.
    Every one of these must render a 200 with the field left unprefilled."""
    url = reverse("procurement:discrepancy_create")
    hostile = ("NaN", "nan", "Infinity", "-Infinity", "1e400", "abc", "-5", "0",
               "1" * 32, "0.00000", " ", "1,5", "null")
    for value in hostile:
        resp = client_a.get(url, {"goods_receipt": str(receipt_grn_a.pk),
                                  "quantity_affected": value})
        assert resp.status_code == 200, value
        assert resp.context["form"].initial.get("quantity_affected") is None, value


def test_receipt_discrepancy_prefill_accepts_a_sane_quantity(
        client_a, receipt_grn_a, receipt_grn_line_a):
    """L44 pair: the exceptions board's real hand-off DOES prefill — receipt, line, kind and a
    finite in-range quantity all land on the form."""
    resp = client_a.get(reverse("procurement:discrepancy_create"), {
        "goods_receipt": str(receipt_grn_a.pk),
        "goods_receipt_line": str(receipt_grn_line_a.pk),
        "kind": "over_shipment",
        "quantity_affected": "2.5",
    })
    assert resp.status_code == 200
    initial = resp.context["form"].initial
    assert initial["goods_receipt"] == receipt_grn_a.pk
    assert initial["goods_receipt_line"] == receipt_grn_line_a.pk
    assert initial["kind"] == "over_shipment"
    assert initial["quantity_affected"] == Decimal("2.5")


def test_receipt_prefill_params_drop_another_workspaces_pks(
        client_a, receipt_grn_b, receipt_grn_line_b, receipt_discrepancy_b,
        receipt_discrepancy_open_a):
    """A query string is never an authorization path: both prefill surfaces re-check every pk
    against the request's workspace and simply leave a foreign one out, junk kinds included."""
    resp = client_a.get(reverse("procurement:discrepancy_create"), {
        "goods_receipt": str(receipt_grn_b.pk),
        "goods_receipt_line": str(receipt_grn_line_b.pk),
        "kind": "zzz",
    })
    assert resp.status_code == 200
    initial = resp.context["form"].initial
    assert "goods_receipt" not in initial
    assert "goods_receipt_line" not in initial
    assert "kind" not in initial

    resp = client_a.get(reverse("procurement:rtv_create"),
                        {"discrepancy": str(receipt_discrepancy_b.pk)})
    assert resp.status_code == 200
    assert resp.context["form"].initial == {}

    # L44 pair: tenant A's OWN finding prefills the return it hands off to.
    resp = client_a.get(reverse("procurement:rtv_create"),
                        {"discrepancy": str(receipt_discrepancy_open_a.pk)})
    assert resp.status_code == 200
    assert resp.context["form"].initial["discrepancy"] == receipt_discrepancy_open_a.pk


def test_receipt_console_book_refuses_every_hostile_quantity(
        client_a, receipt_asn_a, receipt_asn_line_a):
    """L35 on the console's dynamic ``qty_<pk>`` fields: non-finite, garbage, negative and
    over-``max_digits`` figures are FIELD errors flattened into a message, never a 500 and never
    a receipt. Each probe is checked against the same count so no GRN number is burned."""
    url = reverse("procurement:receiving_console_book", args=[receipt_asn_a.pk])
    before = GoodsReceiptNote.objects.count()
    hostile = ("NaN", "Infinity", "-Infinity", "abc", "-5", "1" * 20, "1e400", "null", "1,5")
    for value in hostile:
        resp = client_a.post(url, _receipt_book_payload({receipt_asn_line_a.pk: value}))
        assert resp.status_code == 302, value
        assert resp["Location"] == reverse("procurement:receiving_console"), value
        assert GoodsReceiptNote.objects.count() == before, value

    # A missing or garbage receipt_date is the other half of the same form and behaves the same.
    for value in ("", "not-a-date", "31/02/2026"):
        resp = client_a.post(url, _receipt_book_payload({receipt_asn_line_a.pk: "5"},
                                                        receipt_date=value))
        assert resp.status_code == 302, value
        assert GoodsReceiptNote.objects.count() == before, value


def test_receipt_console_book_books_a_sane_quantity(
        client_a, receipt_asn_a, receipt_asn_line_a):
    """L44 pair for the decimal guard: a finite, positive, in-range quantity books the draft
    receipt and its one line — the hardening above did not break the console's only write."""
    before = GoodsReceiptNote.objects.count()
    resp = client_a.post(
        reverse("procurement:receiving_console_book", args=[receipt_asn_a.pk]),
        _receipt_book_payload({receipt_asn_line_a.pk: "4.5"}))
    assert resp.status_code == 302
    assert GoodsReceiptNote.objects.count() == before + 1
    receipt = GoodsReceiptNote.objects.get(delivery_note_ref="NW-DN-7001")
    line = receipt.lines.get()
    assert line.quantity_received == Decimal("4.5")
    assert line.po_line_id == receipt_asn_line_a.po_line_id


# ============================================= 6. absent prerequisites are REJECTED (L35)
def test_receipt_console_book_refuses_an_empty_declaration(
        client_a, receipt_asn_a, receipt_asn_line_a):
    """A receipt with nothing on it is not a receipt. A zero (or all-blank) declaration is
    REFUSED — it must never fall through and mint an empty draft GRN, burning a number."""
    url = reverse("procurement:receiving_console_book", args=[receipt_asn_a.pk])
    before = GoodsReceiptNote.objects.count()
    for quantities in ({}, {receipt_asn_line_a.pk: ""}, {receipt_asn_line_a.pk: "0"},
                       {receipt_asn_line_a.pk: "0.0000"}):
        resp = client_a.post(url, _receipt_book_payload(quantities))
        assert resp.status_code == 302, quantities
        assert resp["Location"] == reverse("procurement:receiving_console"), quantities
        assert GoodsReceiptNote.objects.count() == before, quantities


def test_receipt_console_verbs_refuse_a_shipment_that_is_not_declared(
        client_a, receipt_asn_draft_a, receipt_asn_a, receipt_asn_line_a):
    """A DRAFT ASN is not a commitment and never appears on the console — so neither of its two
    verbs may act on one either. Hiding a row does not stop a direct POST."""
    grn_before = GoodsReceiptNote.objects.count()
    lots_before = LotSerial.objects.count()

    resp = client_a.post(
        reverse("procurement:receiving_console_book", args=[receipt_asn_draft_a.pk]),
        _receipt_book_payload({}))
    assert resp.status_code == 302
    assert resp["Location"] == reverse("procurement:receiving_console")
    assert GoodsReceiptNote.objects.count() == grn_before

    resp = client_a.post(
        reverse("procurement:receiving_console_mint_lots", args=[receipt_asn_draft_a.pk]))
    assert resp.status_code == 302
    assert LotSerial.objects.count() == lots_before

    # …and the draft is not on the board that would offer those buttons.
    board = client_a.get(reverse("procurement:receiving_console"))
    assert receipt_asn_draft_a.pk not in [row.pk for row in board.context["object_list"]]


def test_receipt_console_mint_lots_adopts_rather_than_duplicating(
        client_a, tenant_a, receipt_asn_a, receipt_asn_line_a, receipt_item_a):
    """L44 pair for the mint guard: a DECLARED shipment does mint its lot, and a second POST
    adopts the existing row instead of raising on the model's own unique_together."""
    resp = client_a.post(
        reverse("procurement:receiving_console_mint_lots", args=[receipt_asn_a.pk]))
    assert resp.status_code == 302
    lot = LotSerial.objects.get(tenant=tenant_a, number="LOT-A1")
    assert lot.item_id == receipt_item_a.pk
    assert lot.kind == "lot"

    resp = client_a.post(
        reverse("procurement:receiving_console_mint_lots", args=[receipt_asn_a.pk]))
    assert resp.status_code == 302
    assert LotSerial.objects.filter(tenant=tenant_a, number="LOT-A1").count() == 1


def test_receipt_discrepancy_resolve_without_a_remedy_changes_nothing(
        client_a, receipt_discrepancy_open_a):
    """L35: the remedy is the whole point of closing a claim. A POST missing it — or carrying a
    remedy outside the vocabulary — is refused, and the finding stays OPEN rather than falling
    through to 'resolved, reason unknown'."""
    url = reverse("procurement:discrepancy_resolve", args=[receipt_discrepancy_open_a.pk])
    before = _receipt_discrepancy_state(receipt_discrepancy_open_a)
    for body in ({}, {"resolution_notes": "agreed"}, {"remedy": "credit"},
                 {"remedy": "zzz", "resolution_notes": "agreed"},
                 {"remedy": "credit", "resolution_notes": "   "}):
        resp = client_a.post(url, body)
        assert resp.status_code == 302, body
        assert _receipt_discrepancy_state(receipt_discrepancy_open_a) == before, body


def test_receipt_discrepancy_resolve_with_a_remedy_closes_the_finding(
        client_a, admin_user, receipt_discrepancy_open_a):
    """L44 pair: a complete POST does close it, stamping the remedy, the moment and the actor."""
    resp = client_a.post(
        reverse("procurement:discrepancy_resolve", args=[receipt_discrepancy_open_a.pk]),
        {"remedy": "replacement", "resolution_notes": "Supplier shipping the balance Monday."})
    assert resp.status_code == 302
    receipt_discrepancy_open_a.refresh_from_db()
    assert receipt_discrepancy_open_a.status == "resolved"
    assert receipt_discrepancy_open_a.remedy == "replacement"
    assert receipt_discrepancy_open_a.resolved_by_id == admin_user.pk
    assert receipt_discrepancy_open_a.resolved_at is not None


def test_receipt_discrepancy_verbs_refuse_a_closed_finding(
        client_a, receipt_discrepancy_resolved_a, receipt_discrepancy_notified_a):
    """A resolved finding is the record of what was agreed with the supplier: edit, notify,
    resolve and cancel all no-op on it. And ``notify_vendor`` no-ops a SECOND time on an
    already-notified one rather than resetting the clock a supplier SLA is measured from."""
    resolved = receipt_discrepancy_resolved_a
    frozen = _receipt_discrepancy_state(resolved)

    resp = client_a.get(reverse("procurement:discrepancy_edit", args=[resolved.pk]))
    assert resp.status_code == 302
    assert resp["Location"] == reverse("procurement:discrepancy_detail", args=[resolved.pk])
    for name, body in (("procurement:discrepancy_notify_vendor", {}),
                       ("procurement:discrepancy_resolve",
                        {"remedy": "scrap", "resolution_notes": "re-closing"}),
                       ("procurement:discrepancy_cancel", {"resolution_notes": "withdraw"})):
        resp = client_a.post(reverse(name, args=[resolved.pk]), body)
        assert resp.status_code == 302, name
        assert _receipt_discrepancy_state(resolved) == frozen, name

    notified = receipt_discrepancy_notified_a
    stamped = _receipt_discrepancy_state(notified)
    resp = client_a.post(
        reverse("procurement:discrepancy_notify_vendor", args=[notified.pk]),
        {"vendor_reference": "SECOND-CASE", "vendor_notified_on": _receipt_iso(3)})
    assert resp.status_code == 302
    assert _receipt_discrepancy_state(notified) == stamped


def test_receipt_rtv_cancel_without_a_reason_changes_nothing(client_a, receipt_rtv_draft_a):
    """L35: an abandoned return with no explanation is indistinguishable from a data error, so
    ``cancellation_reason`` is REQUIRED. A blank POST is refused and the draft stays a draft."""
    url = reverse("procurement:rtv_cancel", args=[receipt_rtv_draft_a.pk])
    before = _receipt_rtv_state(receipt_rtv_draft_a)
    for body in ({}, {"cancellation_reason": ""}, {"cancellation_reason": "   "}):
        resp = client_a.post(url, body)
        assert resp.status_code == 302, body
        assert _receipt_rtv_state(receipt_rtv_draft_a) == before, body

    # L44 pair: with a reason it does cancel, and the reason is recorded.
    resp = client_a.post(url, {"cancellation_reason": "Supplier collected it directly."})
    assert resp.status_code == 302
    receipt_rtv_draft_a.refresh_from_db()
    assert receipt_rtv_draft_a.status == "cancelled"
    assert receipt_rtv_draft_a.cancellation_reason == "Supplier collected it directly."


def test_receipt_rtv_verbs_refuse_an_out_of_order_transition(
        client_a, receipt_rtv_draft_a, receipt_rtv_authorized_a, receipt_rtv_shipped_a):
    """Every RTV verb re-checks its own guard inside the model, so a direct POST cannot jump the
    ladder: a draft cannot be shipped or closed, an authorized return cannot be closed without
    despatch or re-authorized, and a shipped one can no longer be cancelled."""
    frozen = {
        "draft": (receipt_rtv_draft_a, _receipt_rtv_state(receipt_rtv_draft_a)),
        "authorized": (receipt_rtv_authorized_a, _receipt_rtv_state(receipt_rtv_authorized_a)),
        "shipped": (receipt_rtv_shipped_a, _receipt_rtv_state(receipt_rtv_shipped_a)),
    }
    probes = (
        ("draft", "procurement:rtv_ship", {"carrier_name": "DHL"}),
        ("draft", "procurement:rtv_close", {"credit_note_ref": "CN-1"}),
        ("authorized", "procurement:rtv_authorize", {}),
        ("authorized", "procurement:rtv_close", {"credit_note_ref": "CN-2"}),
        ("shipped", "procurement:rtv_authorize", {}),
        ("shipped", "procurement:rtv_ship", {"carrier_name": "UPS"}),
        ("shipped", "procurement:rtv_cancel", {"cancellation_reason": "changed our mind"}),
    )
    for key, name, body in probes:
        obj, before = frozen[key]
        resp = client_a.post(reverse(name, args=[obj.pk]), body)
        assert resp.status_code == 302, (key, name)
        assert _receipt_rtv_state(obj) == before, (key, name)


def test_receipt_rtv_ship_leaves_a_blank_carrier_unchanged(client_a, receipt_rtv_authorized_a):
    """L44 pair for the ladder guards, plus the "blank means unchanged" rule: an authorized
    return DOES ship, and an empty carrier/tracking keeps whatever the RMA already carried rather
    than erasing it."""
    ReturnToVendor.objects.filter(pk=receipt_rtv_authorized_a.pk).update(
        carrier_name="Northwind Freight", tracking_number="TRK-KEEP")
    resp = client_a.post(reverse("procurement:rtv_ship", args=[receipt_rtv_authorized_a.pk]),
                         {"carrier_name": "", "tracking_number": "", "shipped_on": ""})
    assert resp.status_code == 302
    receipt_rtv_authorized_a.refresh_from_db()
    assert receipt_rtv_authorized_a.status == "shipped"
    assert receipt_rtv_authorized_a.carrier_name == "Northwind Freight"
    assert receipt_rtv_authorized_a.tracking_number == "TRK-KEEP"
    assert receipt_rtv_authorized_a.shipped_on == timezone.localdate()


def test_receipt_rtv_delete_refuses_a_non_draft_return(
        client_a, receipt_rtv_authorized_a, receipt_rtv_shipped_a, receipt_rtv_draft_a):
    """Deleting removes the trail entirely, so it is drafts only — an authorized or shipped
    return has been declared to the supplier and must be CANCELLED instead. Both rows survive."""
    for obj in (receipt_rtv_authorized_a, receipt_rtv_shipped_a):
        resp = client_a.post(reverse("procurement:rtv_delete", args=[obj.pk]))
        assert resp.status_code == 302
        assert resp["Location"] == reverse("procurement:rtv_detail", args=[obj.pk])
        assert ReturnToVendor.objects.filter(pk=obj.pk).exists()

    # L44 pair: a draft really is deletable, so the guard is a status rule and not a dead route.
    resp = client_a.post(reverse("procurement:rtv_delete", args=[receipt_rtv_draft_a.pk]))
    assert resp.status_code == 302
    assert resp["Location"] == reverse("procurement:rtv_list")
    assert not ReturnToVendor.objects.filter(pk=receipt_rtv_draft_a.pk).exists()


def test_receipt_rtv_edit_refuses_a_non_draft_return(
        client_a, receipt_rtv_authorized_a, receipt_vendor_a):
    """Re-writing the lines under an issued RMA is how a disputed credit starts — the edit page
    is refused server-side for anything past draft, GET and POST alike."""
    url = reverse("procurement:rtv_edit", args=[receipt_rtv_authorized_a.pk])
    before = _receipt_rtv_state(receipt_rtv_authorized_a)
    detail = reverse("procurement:rtv_detail", args=[receipt_rtv_authorized_a.pk])

    resp = client_a.get(url)
    assert resp.status_code == 302 and resp["Location"] == detail

    body = dict(_receipt_rtv_payload(vendor=str(receipt_vendor_a.pk),
                                     supplier_rma_number="RMA-REWRITTEN"),
                **_receipt_rtv_lines_payload())
    resp = client_a.post(url, body)
    assert resp.status_code == 302 and resp["Location"] == detail
    assert _receipt_rtv_state(receipt_rtv_authorized_a) == before


def test_receipt_rtv_lifecycle_posts_nothing_to_stock_or_the_ledger(
        client_a, receipt_rtv_draft_a, receipt_rtv_line_a):
    """The 6.12 non-posting invariant, asserted through the HTTP verbs rather than the model:
    authorizing, shipping and closing a return creates ZERO ``scm.StockMove`` and ZERO
    ``accounting.JournalEntry`` rows. Rejected quantity never entered stock, and the AP credit is
    a free-text REFERENCE — anything else would double-post."""
    moves_before = StockMove.objects.count()
    entries_before = JournalEntry.objects.count()

    for name, body, expected in (
            ("procurement:rtv_authorize", {}, "authorized"),
            ("procurement:rtv_ship", {"carrier_name": "DHL", "tracking_number": "TRK-9"},
             "shipped"),
            ("procurement:rtv_close", {"credit_note_ref": "CN-4242"}, "closed")):
        resp = client_a.post(reverse(name, args=[receipt_rtv_draft_a.pk]), body)
        assert resp.status_code == 302, name
        receipt_rtv_draft_a.refresh_from_db()
        assert receipt_rtv_draft_a.status == expected, name

    assert StockMove.objects.count() == moves_before
    assert JournalEntry.objects.count() == entries_before
    assert receipt_rtv_draft_a.credit_note_ref == "CN-4242"
    # The expected credit stays DERIVED — recorded on the audit row, never stored on the header.
    assert receipt_rtv_draft_a.expected_credit_value == Decimal("75.00")
    closing = (AuditLog.objects.filter(action="update", object_id=receipt_rtv_draft_a.pk)
               .order_by("-id").first())
    assert closing is not None and closing.changes.get("expected_credit") == "75.00"
