"""Procurement 6.11 Order Fulfillment & Tracking — isolation & hardening tests.

The defensive half of the 6.11 suite. Everything here asks one question from a different angle:
*can a user reach a row, a field or a state transition the product never meant to give them?*

Coverage, in the order the file is laid out:

1. **Cross-tenant IDOR** — every pk-scoped route (ASN, delivery schedule, backorder) requested
   with another workspace's pk returns **404**, and the target rows come back byte-identical.
2. **Register isolation** — none of the five 6.11 boards ever renders another workspace's rows,
   and a tenant-less superuser gets an empty (or refused) board rather than everybody's data.
3. **The authz ladder** — anonymous redirects to the login page; a plain member is refused on the
   two ``@tenant_admin_required`` deletes and *allowed* everywhere else (the deliberate 6.11
   split); CSRF is enforced on every POST route; GET never mutates.
4. **Mass assignment** — the crafted-POST surface: another workspace's pk in an FK field, a
   forged ``status`` / ``number`` / ``created_by`` / ``reschedule_count`` / proof-of-delivery
   block, and the two fields the forms deliberately *pop* on edit (``purchase_order``,
   ``revised_promise_date``).
5. **Hostile input** — junk FK filter params, page junk, SQL metacharacters and the decimal
   family (``NaN`` / ``Infinity`` / negative / over-``max_digits``) never 500 (L11).
6. **Absent prerequisites are REJECTED, never fallen through** (L35) — no reason, no cancel; no
   note, no reschedule; not in flight, no proof-of-delivery stamp; fully covered, no split.

Every negative case is paired with the POSITIVE path that proves the guard did not simply break
the feature (L44). All dates derive from ``timezone.localdate()`` (never ``date.today()``) so the
assertions cannot flake in the hours after local midnight (L16).
"""
import datetime
from decimal import Decimal

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.procurement.models import (
    AdvancedShipmentNotice,
    AsnLine,
    Backorder,
    DeliverySchedule,
    ProcurementAlert,
)

pytestmark = pytest.mark.django_db


# ------------------------------------------------------------------ helpers (module-private)
def _fulfillment_iso(offset_days):
    """A date string relative to TODAY as the CODE sees it — ``timezone.localdate()`` (L16)."""
    return (timezone.localdate() + datetime.timedelta(days=offset_days)).isoformat()


def _fulfillment_asn_payload(**overrides):
    """A complete, valid ``AdvancedShipmentNoticeForm`` POST body.

    ``purchase_order`` is deliberately absent: the create tests add it, and the EDIT form pops the
    field out of ``self.fields`` entirely.
    """
    payload = {
        "supplier_reference": "",
        "source": "manual",
        "ship_date": "",
        "expected_delivery_date": "",
        "carrier": "",
        "carrier_name": "Northwind Express",
        "tracking_number": "",
        "shipment": "",
        "bill_of_lading_ref": "",
        "container_ref": "",
        "freight_terms": "",
        "package_count": "",
        "pallet_count": "",
        "gross_weight_kg": "",
        "volume_cbm": "",
        "notes": "",
    }
    payload.update(overrides)
    return payload


def _fulfillment_lines_payload(rows=(), initial=0, total=None):
    """``AsnLineFormSet`` management form + rows. The POST prefix is ``lines`` (pinned)."""
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


def _fulfillment_schedule_payload(**overrides):
    payload = {
        "po_line": "",
        "sequence": "1",
        "scheduled_quantity": "2",
        "need_by_date": _fulfillment_iso(7),
        "promised_quantity": "",
        "promised_date": "",
        "status": "planned",
        "ship_to": "",
        "delivery_mode": "",
        "asn": "",
        "change_reason": "",
        "notes": "",
    }
    payload.update(overrides)
    return payload


def _fulfillment_backorder_payload(**overrides):
    payload = {
        "po_line": "",
        "delivery_schedule": "",
        "asn": "",
        "quantity_backordered": "1",
        "reason": "out_of_stock",
        "reason_note": "",
        "original_promise_date": "",
        "revised_promise_date": "",
        "notes": "",
    }
    payload.update(overrides)
    return payload


def _fulfillment_split_payload(**overrides):
    payload = {
        "po_line": "",
        "instalments": "2",
        "first_date": _fulfillment_iso(3),
        "interval_days": "7",
    }
    payload.update(overrides)
    return payload


def _fulfillment_asn_state(obj):
    """Every field a crafted request might move on an ASN — the freeze probe."""
    obj.refresh_from_db()
    return (obj.status, obj.number, obj.supplier_reference, obj.purchase_order_id,
            obj.carrier_id, obj.shipment_id, obj.tracking_number, obj.expected_delivery_date,
            obj.submitted_at, obj.delivered_at, obj.arrival_condition, obj.pod_reference,
            obj.received_signature_name, obj.confirmed_by_id, obj.cancelled_at,
            obj.cancellation_reason)


def _fulfillment_schedule_state(obj):
    obj.refresh_from_db()
    return (obj.status, obj.number, obj.sequence, obj.scheduled_quantity, obj.need_by_date,
            obj.promised_quantity, obj.promised_date, obj.ship_to_id, obj.delivery_mode,
            obj.asn_id, obj.po_line_id)


def _fulfillment_backorder_state(obj):
    obj.refresh_from_db()
    return (obj.status, obj.number, obj.quantity_backordered, obj.reason, obj.reason_note,
            obj.original_promise_date, obj.revised_promise_date, obj.reschedule_count,
            obj.closed_at, obj.closure_note, obj.alert_id, obj.po_line_id)


#: Every 6.11 page that RENDERS: (url name, needs a pk).
_FULFILLMENT_READ_ROUTES = (
    ("procurement:asn_list", False),
    ("procurement:asn_create", False),
    ("procurement:asn_detail", True),
    ("procurement:asn_edit", True),
    ("procurement:deliveryschedule_list", False),
    ("procurement:deliveryschedule_create", False),
    ("procurement:deliveryschedule_split", False),
    ("procurement:deliveryschedule_detail", True),
    ("procurement:deliveryschedule_edit", True),
    ("procurement:backorder_list", False),
    ("procurement:backorder_create", False),
    ("procurement:backorder_detail", True),
    ("procurement:backorder_edit", True),
    ("procurement:inbound_tracking", False),
    ("procurement:delivery_confirmation", False),
)

#: Every POST-only verb in 6.11 and a body that would otherwise succeed.
_FULFILLMENT_VERB_ROUTES = (
    ("procurement:asn_delete", {}),
    ("procurement:asn_submit", {}),
    ("procurement:asn_mark_in_transit", {}),
    ("procurement:asn_confirm_delivery", {"arrival_condition": "good"}),
    ("procurement:asn_cancel", {"cancellation_reason": "crafted"}),
    ("procurement:deliveryschedule_delete", {}),
    ("procurement:backorder_delete", {}),
    ("procurement:backorder_reschedule", {"reason_note": "crafted"}),
    ("procurement:backorder_fulfil", {}),
    ("procurement:backorder_cancel", {}),
    ("procurement:backorder_raise_alert", {}),
)


# ================================================================== 1. cross-tenant IDOR
def test_fulfillment_cross_tenant_pks_404_on_every_scoped_route(
        client_a, fulfillment_asn_b, fulfillment_schedule_b, fulfillment_backorder_b):
    """Tenant A's admin aiming any pk-scoped 6.11 route at a tenant-B row gets 404 — reads,
    writes and deletes alike — and every tenant-B row comes back byte-identical."""
    asn_b, sched_b, bko_b = fulfillment_asn_b, fulfillment_schedule_b, fulfillment_backorder_b
    before = (_fulfillment_asn_state(asn_b), _fulfillment_schedule_state(sched_b),
              _fulfillment_backorder_state(bko_b))
    alerts_before = ProcurementAlert.objects.count()

    asn_edit_body = _fulfillment_asn_payload(carrier_name="hijacked")
    asn_edit_body.update(_fulfillment_lines_payload())

    probes = [
        # --- AdvancedShipmentNotice
        ("GET", "procurement:asn_detail", asn_b.pk, None),
        ("GET", "procurement:asn_edit", asn_b.pk, None),
        ("POST", "procurement:asn_edit", asn_b.pk, asn_edit_body),
        ("POST", "procurement:asn_delete", asn_b.pk, None),
        ("POST", "procurement:asn_submit", asn_b.pk, None),
        ("POST", "procurement:asn_mark_in_transit", asn_b.pk, None),
        ("POST", "procurement:asn_confirm_delivery", asn_b.pk,
         {"arrival_condition": "good", "pod_reference": "STOLEN-POD"}),
        ("POST", "procurement:asn_cancel", asn_b.pk, {"cancellation_reason": "not yours"}),
        # --- DeliverySchedule
        ("GET", "procurement:deliveryschedule_detail", sched_b.pk, None),
        ("GET", "procurement:deliveryschedule_edit", sched_b.pk, None),
        ("POST", "procurement:deliveryschedule_edit", sched_b.pk,
         _fulfillment_schedule_payload(po_line=str(sched_b.po_line_id), status="received")),
        ("POST", "procurement:deliveryschedule_delete", sched_b.pk, None),
        # --- Backorder
        ("GET", "procurement:backorder_detail", bko_b.pk, None),
        ("GET", "procurement:backorder_edit", bko_b.pk, None),
        ("POST", "procurement:backorder_edit", bko_b.pk,
         _fulfillment_backorder_payload(po_line=str(bko_b.po_line_id))),
        ("POST", "procurement:backorder_delete", bko_b.pk, None),
        # backorder_reschedule validates its FORM before fetching the row, so the cross-tenant
        # 404 only shows with a VALID body — an invalid one redirects instead. Pin the real 404.
        ("POST", "procurement:backorder_reschedule", bko_b.pk,
         {"revised_promise_date": _fulfillment_iso(9), "reason_note": "crafted"}),
        ("POST", "procurement:backorder_fulfil", bko_b.pk, {"closure_note": "crafted"}),
        ("POST", "procurement:backorder_cancel", bko_b.pk, {"closure_note": "crafted"}),
        ("POST", "procurement:backorder_raise_alert", bko_b.pk, None),
    ]
    for method, name, pk, payload in probes:
        url = reverse(name, args=[pk])
        resp = (client_a.post(url, payload or {}) if method == "POST" else client_a.get(url))
        assert resp.status_code == 404, (method, name)

    assert (_fulfillment_asn_state(asn_b), _fulfillment_schedule_state(sched_b),
            _fulfillment_backorder_state(bko_b)) == before
    # raise_alert must not have escalated another workspace's shortfall into anyone's inbox.
    assert ProcurementAlert.objects.count() == alerts_before


def test_fulfillment_own_tenant_rows_reachable_on_the_same_routes(
        client_a, fulfillment_asn_draft_a, fulfillment_schedule_a,
        fulfillment_backorder_open_a):
    """L44 pair for the IDOR matrix: the identical routes against tenant A's OWN rows render —
    the 404s above are tenant scoping, not a broken URLconf."""
    for name, obj in (("procurement:asn_detail", fulfillment_asn_draft_a),
                      ("procurement:asn_edit", fulfillment_asn_draft_a),
                      ("procurement:deliveryschedule_detail", fulfillment_schedule_a),
                      ("procurement:deliveryschedule_edit", fulfillment_schedule_a),
                      ("procurement:backorder_detail", fulfillment_backorder_open_a),
                      ("procurement:backorder_edit", fulfillment_backorder_open_a)):
        resp = client_a.get(reverse(name, args=[obj.pk]))
        assert resp.status_code == 200, name


# ================================================================== 2. register isolation
def test_fulfillment_registers_never_render_another_workspaces_rows(
        client_a, fulfillment_asn_draft_a, fulfillment_asn_in_transit_a,
        fulfillment_schedule_a, fulfillment_backorder_open_a,
        fulfillment_asn_b, fulfillment_schedule_b, fulfillment_backorder_b):
    """All five 6.11 registers, in one pass: tenant A's own row is present (positive) and tenant
    B's row is absent (negative) in the SAME response."""
    # Put B's ASN in flight and due tomorrow so it WOULD qualify for both boards if the tenant
    # scoping were missing — a draft would drop out for the wrong reason. ``.update()`` is used
    # deliberately: ``status`` is editable=False and moves only through the verbs.
    AdvancedShipmentNotice.objects.filter(pk=fulfillment_asn_b.pk).update(
        status="in_transit",
        expected_delivery_date=timezone.localdate() + datetime.timedelta(days=1))

    checks = [
        ("procurement:asn_list", {}, fulfillment_asn_draft_a.pk, fulfillment_asn_b.pk),
        ("procurement:inbound_tracking", {}, fulfillment_asn_in_transit_a.pk,
         fulfillment_asn_b.pk),
        ("procurement:delivery_confirmation", {"due": "awaiting"},
         fulfillment_asn_in_transit_a.pk, fulfillment_asn_b.pk),
        ("procurement:deliveryschedule_list", {}, fulfillment_schedule_a.pk,
         fulfillment_schedule_b.pk),
        ("procurement:backorder_list", {}, fulfillment_backorder_open_a.pk,
         fulfillment_backorder_b.pk),
    ]
    for name, params, mine, theirs in checks:
        resp = client_a.get(reverse(name), params)
        assert resp.status_code == 200, name
        pks = [row.pk for row in resp.context["object_list"]]
        assert mine in pks, name
        assert theirs not in pks, name


def test_fulfillment_tenantless_superuser_sees_nobodys_rows(
        db, fulfillment_asn_draft_a, fulfillment_schedule_a, fulfillment_backorder_open_a,
        fulfillment_asn_b):
    """The superuser has ``tenant=None`` by design: the registers come back EMPTY (never every
    workspace's rows), and the boards/create pages refuse with a redirect instead of showing an
    unexplained blank page or minting orphan rows."""
    from apps.accounts.models import User
    root = User.objects.create_superuser(email="root@naverp.test", username="root_probe",
                                         password="TestPass123!")
    assert root.tenant is None
    c = Client()
    c.force_login(root)

    for name in ("procurement:asn_list", "procurement:deliveryschedule_list",
                 "procurement:backorder_list"):
        resp = c.get(reverse(name))
        assert resp.status_code == 200, name
        assert list(resp.context["object_list"]) == [], name

    home = reverse("dashboard:home")
    for name in ("procurement:inbound_tracking", "procurement:delivery_confirmation",
                 "procurement:asn_create", "procurement:deliveryschedule_create",
                 "procurement:deliveryschedule_split", "procurement:backorder_create"):
        resp = c.get(reverse(name))
        assert resp.status_code == 302, name
        assert resp["Location"] == home, name


# ================================================================== 3. authz ladder
def test_fulfillment_anonymous_redirected_to_login_on_every_route(
        db, fulfillment_asn_draft_a, fulfillment_schedule_a, fulfillment_backorder_open_a):
    """No 6.11 URL — page or verb — answers an unauthenticated request; each one bounces to the
    accounts login. The rows are untouched afterwards."""
    anon = Client()
    login_prefix = reverse("accounts:login")
    before = (_fulfillment_asn_state(fulfillment_asn_draft_a),
              _fulfillment_schedule_state(fulfillment_schedule_a),
              _fulfillment_backorder_state(fulfillment_backorder_open_a))

    pk_for = {
        "procurement:asn_detail": fulfillment_asn_draft_a.pk,
        "procurement:asn_edit": fulfillment_asn_draft_a.pk,
        "procurement:deliveryschedule_detail": fulfillment_schedule_a.pk,
        "procurement:deliveryschedule_edit": fulfillment_schedule_a.pk,
        "procurement:backorder_detail": fulfillment_backorder_open_a.pk,
        "procurement:backorder_edit": fulfillment_backorder_open_a.pk,
    }
    for name, needs_pk in _FULFILLMENT_READ_ROUTES:
        url = reverse(name, args=[pk_for[name]]) if needs_pk else reverse(name)
        resp = anon.get(url)
        assert resp.status_code == 302, name
        assert resp["Location"].startswith(login_prefix), name

    verb_pk = {
        "procurement:deliveryschedule_delete": fulfillment_schedule_a.pk,
    }
    for name, body in _FULFILLMENT_VERB_ROUTES:
        pk = verb_pk.get(name, fulfillment_backorder_open_a.pk
                         if name.startswith("procurement:backorder")
                         else fulfillment_asn_draft_a.pk)
        resp = anon.post(reverse(name, args=[pk]), body)
        assert resp.status_code == 302, name
        assert resp["Location"].startswith(login_prefix), name

    assert (_fulfillment_asn_state(fulfillment_asn_draft_a),
            _fulfillment_schedule_state(fulfillment_schedule_a),
            _fulfillment_backorder_state(fulfillment_backorder_open_a)) == before


def test_fulfillment_member_refused_on_the_two_admin_only_deletes(
        member_client, fulfillment_asn_draft_a, fulfillment_backorder_open_a):
    """``@tenant_admin_required`` guards exactly two 6.11 routes. A plain workspace member gets
    PermissionDenied (403) on both, and both rows survive."""
    for name, obj, model in (
            ("procurement:asn_delete", fulfillment_asn_draft_a, AdvancedShipmentNotice),
            ("procurement:backorder_delete", fulfillment_backorder_open_a, Backorder)):
        resp = member_client.post(reverse(name, args=[obj.pk]))
        assert resp.status_code == 403, name
        assert model.objects.filter(pk=obj.pk).exists(), name


def test_fulfillment_member_may_use_every_other_route(
        member_client, fulfillment_asn_draft_a, fulfillment_schedule_a,
        fulfillment_backorder_open_a):
    """L44 pair for the admin gate: 6.11 is deliberately open to any workspace member everywhere
    else — the registers read, an ASN verb moves the notice, and a plan row can be dropped
    (``deliveryschedule_delete`` is NOT admin-gated, by design)."""
    for name in ("procurement:asn_list", "procurement:deliveryschedule_list",
                 "procurement:backorder_list", "procurement:inbound_tracking",
                 "procurement:delivery_confirmation"):
        assert member_client.get(reverse(name)).status_code == 200, name

    resp = member_client.post(
        reverse("procurement:asn_submit", args=[fulfillment_asn_draft_a.pk]))
    assert resp.status_code == 302
    fulfillment_asn_draft_a.refresh_from_db()
    assert fulfillment_asn_draft_a.status == "submitted"

    resp = member_client.post(
        reverse("procurement:backorder_fulfil", args=[fulfillment_backorder_open_a.pk]),
        {"closure_note": "Arrived with the next truck."})
    assert resp.status_code == 302
    fulfillment_backorder_open_a.refresh_from_db()
    assert fulfillment_backorder_open_a.status == "fulfilled"

    resp = member_client.post(
        reverse("procurement:deliveryschedule_delete", args=[fulfillment_schedule_a.pk]))
    assert resp.status_code == 302
    assert not DeliverySchedule.objects.filter(pk=fulfillment_schedule_a.pk).exists()


def test_fulfillment_csrf_enforced_on_every_post_route(
        admin_user, fulfillment_asn_draft_a, fulfillment_asn_in_transit_a,
        fulfillment_schedule_a, fulfillment_backorder_open_a, fulfillment_po_a,
        fulfillment_po_line_a):
    """A logged-in session is not enough: every mutating 6.11 POST needs a CSRF token. Without
    one each is rejected 403 and nothing is created, moved or deleted."""
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(admin_user)

    before = (_fulfillment_asn_state(fulfillment_asn_draft_a),
              _fulfillment_asn_state(fulfillment_asn_in_transit_a),
              _fulfillment_schedule_state(fulfillment_schedule_a),
              _fulfillment_backorder_state(fulfillment_backorder_open_a))
    counts = {model: model.objects.count()
              for model in (AdvancedShipmentNotice, DeliverySchedule, Backorder,
                            ProcurementAlert)}

    asn_pk = fulfillment_asn_draft_a.pk
    posts = [
        (reverse("procurement:asn_create"),
         _fulfillment_asn_payload(purchase_order=str(fulfillment_po_a.pk))),
        (reverse("procurement:asn_edit", args=[asn_pk]), _fulfillment_asn_payload()),
        (reverse("procurement:asn_delete", args=[asn_pk]), {}),
        (reverse("procurement:asn_submit", args=[asn_pk]), {}),
        (reverse("procurement:asn_mark_in_transit", args=[asn_pk]), {}),
        (reverse("procurement:asn_confirm_delivery",
                 args=[fulfillment_asn_in_transit_a.pk]), {"arrival_condition": "good"}),
        (reverse("procurement:asn_cancel", args=[asn_pk]), {"cancellation_reason": "no token"}),
        (reverse("procurement:deliveryschedule_create"),
         _fulfillment_schedule_payload(po_line=str(fulfillment_po_line_a.pk))),
        (reverse("procurement:deliveryschedule_edit", args=[fulfillment_schedule_a.pk]),
         _fulfillment_schedule_payload(po_line=str(fulfillment_po_line_a.pk))),
        (reverse("procurement:deliveryschedule_delete", args=[fulfillment_schedule_a.pk]), {}),
        (reverse("procurement:deliveryschedule_split"),
         _fulfillment_split_payload(po_line=str(fulfillment_po_line_a.pk))),
        (reverse("procurement:backorder_create"),
         _fulfillment_backorder_payload(po_line=str(fulfillment_po_line_a.pk))),
        (reverse("procurement:backorder_edit", args=[fulfillment_backorder_open_a.pk]),
         _fulfillment_backorder_payload(po_line=str(fulfillment_po_line_a.pk))),
        (reverse("procurement:backorder_delete", args=[fulfillment_backorder_open_a.pk]), {}),
        (reverse("procurement:backorder_reschedule", args=[fulfillment_backorder_open_a.pk]),
         {"revised_promise_date": _fulfillment_iso(11), "reason_note": "no token"}),
        (reverse("procurement:backorder_fulfil", args=[fulfillment_backorder_open_a.pk]), {}),
        (reverse("procurement:backorder_cancel", args=[fulfillment_backorder_open_a.pk]), {}),
        (reverse("procurement:backorder_raise_alert",
                 args=[fulfillment_backorder_open_a.pk]), {}),
    ]
    for url, body in posts:
        resp = csrf_client.post(url, body)
        assert resp.status_code == 403, url

    assert (_fulfillment_asn_state(fulfillment_asn_draft_a),
            _fulfillment_asn_state(fulfillment_asn_in_transit_a),
            _fulfillment_schedule_state(fulfillment_schedule_a),
            _fulfillment_backorder_state(fulfillment_backorder_open_a)) == before
    for model, count in counts.items():
        assert model.objects.count() == count, model.__name__

    # L44 pair: the SAME csrf-enforcing session reads happily — only unsafe methods are gated.
    assert csrf_client.get(reverse("procurement:asn_detail", args=[asn_pk])).status_code == 200


def test_fulfillment_get_on_post_only_verbs_is_405_and_never_mutates(
        client_a, fulfillment_asn_draft_a, fulfillment_schedule_a,
        fulfillment_backorder_open_a):
    """``@require_POST`` fires before ``crud_delete``'s own self-defence: a GET on any verb URL
    is refused outright and every row survives untouched."""
    before = (_fulfillment_asn_state(fulfillment_asn_draft_a),
              _fulfillment_schedule_state(fulfillment_schedule_a),
              _fulfillment_backorder_state(fulfillment_backorder_open_a))
    counts = {model: model.objects.count()
              for model in (AdvancedShipmentNotice, DeliverySchedule, Backorder,
                            ProcurementAlert)}

    for name, _body in _FULFILLMENT_VERB_ROUTES:
        if name.startswith("procurement:backorder"):
            pk = fulfillment_backorder_open_a.pk
        elif name.startswith("procurement:deliveryschedule"):
            pk = fulfillment_schedule_a.pk
        else:
            pk = fulfillment_asn_draft_a.pk
        resp = client_a.get(reverse(name, args=[pk]))
        assert resp.status_code == 405, name

    assert (_fulfillment_asn_state(fulfillment_asn_draft_a),
            _fulfillment_schedule_state(fulfillment_schedule_a),
            _fulfillment_backorder_state(fulfillment_backorder_open_a)) == before
    for model, count in counts.items():
        assert model.objects.count() == count, model.__name__


# ================================================================== 4. mass assignment
def test_fulfillment_asn_create_rejects_another_workspaces_foreign_keys(
        client_a, tenant_a, fulfillment_po_a, fulfillment_po_b, fulfillment_carrier_b,
        fulfillment_shipment_inbound_b):
    """A narrowed ``<select>`` is UX, not a boundary: a hand-crafted POST naming tenant B's
    purchase order, carrier or shipment renders a field error and saves nothing."""
    before = AdvancedShipmentNotice.objects.count()
    url = reverse("procurement:asn_create")

    crafted = [
        ("purchase_order", _fulfillment_asn_payload(
            purchase_order=str(fulfillment_po_b.pk))),
        ("carrier", _fulfillment_asn_payload(
            purchase_order=str(fulfillment_po_a.pk), carrier=str(fulfillment_carrier_b.pk))),
        ("shipment", _fulfillment_asn_payload(
            purchase_order=str(fulfillment_po_a.pk),
            shipment=str(fulfillment_shipment_inbound_b.pk))),
    ]
    for field, body in crafted:
        resp = client_a.post(url, body)
        assert resp.status_code == 200, field
        assert field in resp.context["form"].errors, field
    assert AdvancedShipmentNotice.objects.count() == before


def test_fulfillment_asn_create_stamps_request_tenant_and_ignores_forged_system_fields(
        client_a, tenant_a, admin_user, admin_b, fulfillment_po_a):
    """L44 pair + mass-assignment probe in one: the legitimate create SUCCEEDS and lands on the
    REQUEST's tenant, while ``status`` / ``number`` / ``created_by`` and the whole
    proof-of-delivery block are ignored — none of them is a form field."""
    resp = client_a.post(reverse("procurement:asn_create"), _fulfillment_asn_payload(
        purchase_order=str(fulfillment_po_a.pk),
        supplier_reference="NW-DN-CRAFT-1",
        # every one of these is server-owned and must be dropped on the floor
        tenant=str(admin_b.tenant_id),
        status="delivered",
        number="ASN-99999",
        created_by=str(admin_b.pk),
        confirmed_by=str(admin_b.pk),
        delivered_at="2020-01-01T10:00",
        submitted_at="2020-01-01T10:00",
        arrival_condition="damaged",
        pod_reference="FORGED-POD",
        received_signature_name="Forged Signature",
        cancellation_reason="forged",
    ))
    assert resp.status_code == 302
    obj = AdvancedShipmentNotice.objects.filter(tenant=tenant_a).latest("id")
    assert obj.tenant_id == tenant_a.pk
    assert obj.status == "draft"                     # lifecycle is verb-only
    assert obj.number != "ASN-99999"
    assert obj.number.startswith("ASN-")
    assert obj.created_by_id == admin_user.pk        # the signed-in user, not the posted one
    assert obj.confirmed_by_id is None
    assert obj.delivered_at is None and obj.submitted_at is None
    assert obj.arrival_condition == ""
    assert obj.pod_reference == "" and obj.received_signature_name == ""
    assert obj.cancellation_reason == ""


def test_fulfillment_asn_edit_ignores_a_posted_purchase_order(
        client_a, fulfillment_asn_draft_a, fulfillment_po_a, fulfillment_po_b):
    """``purchase_order`` is POPPED off the edit form (re-pointing an ASN would orphan every
    declared line). Posting one — even another workspace's — changes nothing, and the edit
    itself still goes through (L44)."""
    body = _fulfillment_asn_payload(carrier_name="Re-routed courier",
                                    purchase_order=str(fulfillment_po_b.pk))
    body.update(_fulfillment_lines_payload())
    resp = client_a.post(reverse("procurement:asn_edit", args=[fulfillment_asn_draft_a.pk]),
                         body)
    assert resp.status_code == 302
    fulfillment_asn_draft_a.refresh_from_db()
    assert fulfillment_asn_draft_a.purchase_order_id == fulfillment_po_a.pk
    assert fulfillment_asn_draft_a.carrier_name == "Re-routed courier"


def test_fulfillment_asn_line_formset_refuses_a_foreign_po_line(
        client_a, fulfillment_asn_draft_a, fulfillment_po_line_a, fulfillment_po_line_b):
    """The line formset narrows ``po_line`` to the parent ASN's own order AND re-checks it: a
    crafted row naming tenant B's line is a field error and saves nothing, while the legitimate
    row against this order's own line saves (L44)."""
    url = reverse("procurement:asn_edit", args=[fulfillment_asn_draft_a.pk])

    body = _fulfillment_asn_payload()
    body.update(_fulfillment_lines_payload(rows=[
        {"po_line": str(fulfillment_po_line_b.pk), "quantity_shipped": "6",
         "item_description": "", "sku_hint": "", "uom_hint": "", "package_ref": "",
         "lot_number": "", "serial_number": "", "expiry_date": "", "country_of_origin": "",
         "notes": "", "id": ""},
    ]))
    resp = client_a.post(url, body)
    assert resp.status_code == 200
    assert "po_line" in resp.context["formset"].forms[0].errors
    assert AsnLine.objects.filter(asn=fulfillment_asn_draft_a).count() == 0

    body = _fulfillment_asn_payload()
    body.update(_fulfillment_lines_payload(rows=[
        {"po_line": str(fulfillment_po_line_a.pk), "quantity_shipped": "10",
         "item_description": "", "sku_hint": "", "uom_hint": "", "package_ref": "",
         "lot_number": "", "serial_number": "", "expiry_date": "", "country_of_origin": "",
         "notes": "", "id": ""},
    ]))
    resp = client_a.post(url, body)
    assert resp.status_code == 302
    line = AsnLine.objects.get(asn=fulfillment_asn_draft_a)
    assert line.po_line_id == fulfillment_po_line_a.pk
    assert line.quantity_shipped == Decimal("10")


def test_fulfillment_asn_line_formset_caps_a_crafted_management_form(
        client_a, fulfillment_asn_draft_a):
    """``validate_max=True`` with ``max_num=50``: a management form claiming 51 rows is refused
    as a whole rather than accepted as 51 writes."""
    body = _fulfillment_asn_payload()
    body.update(_fulfillment_lines_payload(rows=(), total=51))
    resp = client_a.post(reverse("procurement:asn_edit", args=[fulfillment_asn_draft_a.pk]),
                         body)
    assert resp.status_code == 200
    assert resp.context["formset"].non_form_errors()
    assert AsnLine.objects.filter(asn=fulfillment_asn_draft_a).count() == 0


def test_fulfillment_deliveryschedule_create_rejects_another_workspaces_foreign_keys(
        client_a, tenant_a, fulfillment_po_line2_a, fulfillment_po_line_b, org_unit_b,
        fulfillment_asn_b):
    """``po_line`` / ``ship_to`` / ``asn`` are each re-checked against the request tenant —
    ``scm.PurchaseOrderLine`` has no tenant column of its own, so its check is explicit."""
    before = DeliverySchedule.objects.count()
    url = reverse("procurement:deliveryschedule_create")

    crafted = [
        ("po_line", _fulfillment_schedule_payload(po_line=str(fulfillment_po_line_b.pk))),
        ("ship_to", _fulfillment_schedule_payload(po_line=str(fulfillment_po_line2_a.pk),
                                                  ship_to=str(org_unit_b.pk))),
        ("asn", _fulfillment_schedule_payload(po_line=str(fulfillment_po_line2_a.pk),
                                              asn=str(fulfillment_asn_b.pk))),
    ]
    for field, body in crafted:
        resp = client_a.post(url, body)
        assert resp.status_code == 200, field
        assert field in resp.context["form"].errors, field
    assert DeliverySchedule.objects.count() == before


def test_fulfillment_deliveryschedule_create_stamps_tenant_and_ignores_forged_fields(
        client_a, tenant_a, admin_user, admin_b, fulfillment_po_line2_a):
    """L44 pair: the honest instalment saves against the REQUEST tenant, and the posted
    ``tenant`` / ``number`` / ``created_by`` are ignored (they are not form fields)."""
    resp = client_a.post(reverse("procurement:deliveryschedule_create"),
                         _fulfillment_schedule_payload(
                             po_line=str(fulfillment_po_line2_a.pk),
                             tenant=str(admin_b.tenant_id),
                             number="DSC-99999",
                             created_by=str(admin_b.pk)))
    assert resp.status_code == 302
    obj = DeliverySchedule.objects.filter(tenant=tenant_a).latest("id")
    assert obj.tenant_id == tenant_a.pk
    assert obj.po_line_id == fulfillment_po_line2_a.pk
    assert obj.number != "DSC-99999" and obj.number.startswith("DSC-")
    assert obj.created_by_id == admin_user.pk


def test_fulfillment_backorder_create_rejects_another_workspaces_foreign_keys(
        client_a, tenant_a, fulfillment_po_line_a, fulfillment_po_line_b,
        fulfillment_schedule_b, fulfillment_asn_b):
    before = Backorder.objects.count()
    url = reverse("procurement:backorder_create")

    crafted = [
        ("po_line", _fulfillment_backorder_payload(po_line=str(fulfillment_po_line_b.pk))),
        ("delivery_schedule", _fulfillment_backorder_payload(
            po_line=str(fulfillment_po_line_a.pk),
            delivery_schedule=str(fulfillment_schedule_b.pk))),
        ("asn", _fulfillment_backorder_payload(po_line=str(fulfillment_po_line_a.pk),
                                               asn=str(fulfillment_asn_b.pk))),
    ]
    for field, body in crafted:
        resp = client_a.post(url, body)
        assert resp.status_code == 200, field
        assert field in resp.context["form"].errors, field
    assert Backorder.objects.count() == before


def test_fulfillment_backorder_create_ignores_forged_workflow_fields(
        client_a, tenant_a, admin_user, admin_b, fulfillment_po_line_a):
    """The whole verb-owned block — ``status`` / ``reschedule_count`` / ``closed_at`` /
    ``closure_note`` / ``alert`` / ``number`` / ``created_by`` — is off the form, so a crafted
    POST cannot mint a pre-closed backorder with its slip count typed down."""
    resp = client_a.post(reverse("procurement:backorder_create"),
                         _fulfillment_backorder_payload(
                             po_line=str(fulfillment_po_line_a.pk),
                             quantity_backordered="2",
                             tenant=str(admin_b.tenant_id),
                             status="fulfilled",
                             number="BKO-99999",
                             reschedule_count="9",
                             closed_at="2020-01-01T10:00",
                             closure_note="forged closure",
                             created_by=str(admin_b.pk)))
    assert resp.status_code == 302
    obj = Backorder.objects.filter(tenant=tenant_a).latest("id")
    assert obj.tenant_id == tenant_a.pk
    assert obj.status == "open"
    assert obj.number != "BKO-99999" and obj.number.startswith("BKO-")
    assert obj.reschedule_count == 0
    assert obj.closed_at is None and obj.closure_note == ""
    assert obj.alert_id is None
    assert obj.created_by_id == admin_user.pk


def test_fulfillment_backorder_edit_cannot_move_the_promise_without_counting_the_slip(
        client_a, fulfillment_backorder_open_a, fulfillment_po_line_a):
    """``revised_promise_date`` is POPPED off the EDIT form: the promise may only move through
    ``reschedule()``, which counts the slip. A posted date is ignored while the rest of the edit
    still lands (L44)."""
    original = fulfillment_backorder_open_a.revised_promise_date
    resp = client_a.post(
        reverse("procurement:backorder_edit", args=[fulfillment_backorder_open_a.pk]),
        _fulfillment_backorder_payload(po_line=str(fulfillment_po_line_a.pk),
                                       quantity_backordered="3",
                                       reason="logistics",
                                       reason_note="Carrier re-plan",
                                       revised_promise_date=_fulfillment_iso(60)))
    assert resp.status_code == 302
    fulfillment_backorder_open_a.refresh_from_db()
    assert fulfillment_backorder_open_a.revised_promise_date == original
    assert fulfillment_backorder_open_a.reschedule_count == 0
    assert fulfillment_backorder_open_a.reason == "logistics"     # the honest edit went through


def test_fulfillment_split_console_refuses_a_foreign_po_line(
        client_a, tenant_a, tenant_b, fulfillment_po_line_b, fulfillment_po_line2_a):
    """The split console's ``po_line`` queryset is narrowed to the workspace, so tenant B's line
    is an invalid choice — no instalment is ever minted against another workspace's order. The
    same POST shape against tenant A's own line splits normally (L44)."""
    url = reverse("procurement:deliveryschedule_split")

    resp = client_a.post(url, _fulfillment_split_payload(
        po_line=str(fulfillment_po_line_b.pk), instalments="3"))
    assert resp.status_code == 200
    assert "po_line" in resp.context["form"].errors
    assert DeliverySchedule.objects.filter(po_line=fulfillment_po_line_b).count() == 0

    resp = client_a.post(url, _fulfillment_split_payload(
        po_line=str(fulfillment_po_line2_a.pk), instalments="2"))
    assert resp.status_code == 302
    rows = DeliverySchedule.objects.filter(tenant=tenant_a, po_line=fulfillment_po_line2_a)
    assert rows.count() == 2
    assert sum(row.scheduled_quantity for row in rows) == fulfillment_po_line2_a.quantity


# ================================================================== 5. hostile input (L11)
def test_fulfillment_registers_survive_junk_filter_and_page_params(
        client_a, fulfillment_asn_draft_a, fulfillment_schedule_a,
        fulfillment_backorder_open_a):
    """Junk FK filter values, unknown choice values, unknown tab names and page junk all render
    200 — never a 500 (L11). The over-range integer is the ``as_db_int`` case that passes
    ``isdecimal()`` and then dies inside the driver."""
    hostile = [
        {"q": "'; DROP TABLE procurement_advancedshipmentnotice;--"},
        {"q": "%' OR '1'='1"},
        {"carrier": "abc"}, {"carrier": "²"}, {"carrier": "999999999999999999999"},
        {"po": "abc"}, {"po": "-1"}, {"po": "999999999999999999999"},
        {"status": "zzz"}, {"source": "zzz"}, {"mode": "zzz"}, {"reason": "zzz"},
        {"risk": "zzz"}, {"due": "zzz"}, {"late": "yes"},
        {"page": "0"}, {"page": "-1"}, {"page": "abc"}, {"page": "999"},
        {"page": "999999999999999999999"},
    ]
    registers = ("procurement:asn_list", "procurement:deliveryschedule_list",
                 "procurement:backorder_list", "procurement:inbound_tracking",
                 "procurement:delivery_confirmation")
    for name in registers:
        url = reverse(name)
        for params in hostile:
            resp = client_a.get(url, params)
            assert resp.status_code == 200, (name, params)
    # The DROP TABLE above was a bound string, not an execution: every register still serves.
    for name in registers:
        assert client_a.get(reverse(name)).status_code == 200, name


def test_fulfillment_valid_filters_still_narrow_after_the_junk_guard(
        client_a, fulfillment_asn_draft_a, fulfillment_asn_late_a, fulfillment_po_a,
        fulfillment_schedule_a, fulfillment_backorder_open_a,
        fulfillment_backorder_past_due_a):
    """L44 pair for the L11 guard: skipping a junk filter must not mean skipping every filter."""
    resp = client_a.get(reverse("procurement:asn_list"), {"status": "in_transit"})
    pks = [row.pk for row in resp.context["object_list"]]
    assert fulfillment_asn_late_a.pk in pks
    assert fulfillment_asn_draft_a.pk not in pks

    resp = client_a.get(reverse("procurement:asn_list"), {"po": str(fulfillment_po_a.pk)})
    assert fulfillment_asn_draft_a.pk in [row.pk for row in resp.context["object_list"]]

    resp = client_a.get(reverse("procurement:asn_list"), {"late": "1"})
    pks = [row.pk for row in resp.context["object_list"]]
    assert fulfillment_asn_late_a.pk in pks and fulfillment_asn_draft_a.pk not in pks

    resp = client_a.get(reverse("procurement:backorder_list"), {"risk": "past_due"})
    pks = [row.pk for row in resp.context["object_list"]]
    assert fulfillment_backorder_past_due_a.pk in pks
    assert fulfillment_backorder_open_a.pk not in pks

    resp = client_a.get(reverse("procurement:deliveryschedule_list"), {"status": "planned"})
    assert fulfillment_schedule_a.pk in [row.pk for row in resp.context["object_list"]]


def test_fulfillment_pagination_guards_hold_past_the_last_page(
        client_a, tenant_a, fulfillment_po_a, fulfillment_asn_draft_a):
    """17 rows over a page size of 15: page 2 renders the overflow, and a page past the end (or
    a non-numeric one) falls back to a real page instead of raising (L9)."""
    for _ in range(16):
        AdvancedShipmentNotice.objects.create(tenant=tenant_a,
                                              purchase_order=fulfillment_po_a)
    total = AdvancedShipmentNotice.objects.filter(tenant=tenant_a).count()
    assert total == 17

    url = reverse("procurement:asn_list")
    first = client_a.get(url)
    assert first.status_code == 200
    assert len(first.context["object_list"]) == 15
    assert first.context["page_obj"].paginator.num_pages == 2

    second = client_a.get(url, {"page": "2"})
    assert second.status_code == 200
    assert len(second.context["object_list"]) == 2
    assert second.context["page_obj"].number == 2

    for junk in ("999", "abc", "0", "-4"):
        resp = client_a.get(url, {"page": junk})
        assert resp.status_code == 200, junk
        assert resp.context["page_obj"].number in (1, 2), junk


def test_fulfillment_backorder_create_prefill_survives_the_decimal_family(
        client_a, fulfillment_po_line_a, fulfillment_po_line_b, fulfillment_asn_b):
    """``?quantity=`` is parsed by hand, so it gets the full L11 decimal treatment: ``NaN`` and
    ``Infinity`` PARSE cleanly and blow up on the later comparison, garbage raises
    ``InvalidOperation``, and a negative is not a shortfall. All of them render 200 with the
    field left BLANK — never a 500, never a nonsense prefill. Foreign ``?po_line=``/``?asn=``
    pks are dropped the same way: a query string is not an authorization path."""
    url = reverse("procurement:backorder_create")
    for raw in ("NaN", "nan", "Infinity", "-Infinity", "abc", "-5", "0",
                "1e999", "99999999999999999999.12345", "", " "):
        resp = client_a.get(url, {"quantity": raw})
        assert resp.status_code == 200, raw
        if raw not in ("1e999", "99999999999999999999.12345"):
            assert not resp.context["form"].initial.get("quantity_backordered"), raw

    resp = client_a.get(url, {"po_line": str(fulfillment_po_line_b.pk),
                              "asn": str(fulfillment_asn_b.pk),
                              "quantity": "NaN"})
    assert resp.status_code == 200
    initial = resp.context["form"].initial
    assert not initial.get("po_line")
    assert not initial.get("asn")

    for raw in ("abc", "-1", "999999999999999999999"):
        resp = client_a.get(url, {"po_line": raw})
        assert resp.status_code == 200, raw
        assert not resp.context["form"].initial.get("po_line"), raw

    # L44 pair: an honest prefill still prefills.
    resp = client_a.get(url, {"po_line": str(fulfillment_po_line_a.pk), "quantity": "3"})
    assert resp.status_code == 200
    assert resp.context["form"].initial["po_line"] == fulfillment_po_line_a.pk
    assert resp.context["form"].initial["quantity_backordered"] == Decimal("3")


def test_fulfillment_backorder_post_rejects_out_of_range_quantities_without_500(
        client_a, tenant_a, fulfillment_po_line_a):
    """The POST side of the same decimal family: over-``max_digits``, zero, negative and
    non-numeric quantities come back as friendly field errors with nothing saved."""
    before = Backorder.objects.count()
    url = reverse("procurement:backorder_create")
    for raw in ("99999999999999999999.12345", "0", "-3", "abc", "NaN", "Infinity", "1e999"):
        resp = client_a.post(url, _fulfillment_backorder_payload(
            po_line=str(fulfillment_po_line_a.pk), quantity_backordered=raw))
        assert resp.status_code == 200, raw
        assert "quantity_backordered" in resp.context["form"].errors, raw
    # And the model's own ceiling: never more than the line actually ordered.
    resp = client_a.post(url, _fulfillment_backorder_payload(
        po_line=str(fulfillment_po_line_a.pk), quantity_backordered="99"))
    assert resp.status_code == 200
    assert "quantity_backordered" in resp.context["form"].errors
    assert Backorder.objects.count() == before


def test_fulfillment_split_console_rejects_hostile_numbers_without_500(
        client_a, tenant_a, fulfillment_po_line2_a):
    """The split console hand-builds N rows from two integers: junk, zero, negative and
    over-cap values all land as form errors with a 200, and NOTHING is created."""
    url = reverse("procurement:deliveryschedule_split")
    hostile = [
        {"instalments": "NaN"}, {"instalments": "abc"}, {"instalments": "0"},
        {"instalments": "1"}, {"instalments": "-3"}, {"instalments": "13"},
        {"instalments": "999999999999999999999"},
        {"interval_days": "0"}, {"interval_days": "-7"}, {"interval_days": "abc"},
        {"interval_days": "999"},
        {"first_date": ""}, {"first_date": "not-a-date"}, {"first_date": "31/02/2026"},
    ]
    for override in hostile:
        resp = client_a.post(url, _fulfillment_split_payload(
            po_line=str(fulfillment_po_line2_a.pk), **override))
        assert resp.status_code == 200, override
        assert resp.context["form"].errors, override
    assert DeliverySchedule.objects.filter(po_line=fulfillment_po_line2_a).count() == 0


# ================================================================== 6. absent prerequisites (L35)
def test_fulfillment_confirm_delivery_refused_when_not_in_flight(
        client_a, fulfillment_asn_draft_a, fulfillment_asn_delivered_a,
        fulfillment_asn_in_transit_a):
    """A DRAFT notice has not shipped and a DELIVERED one is already closed: neither may be
    stamped with a proof of delivery. The in-flight one can (L44), and confirming it TWICE does
    not re-stamp it."""
    draft_before = _fulfillment_asn_state(fulfillment_asn_draft_a)
    delivered_before = _fulfillment_asn_state(fulfillment_asn_delivered_a)

    for obj in (fulfillment_asn_draft_a, fulfillment_asn_delivered_a):
        resp = client_a.post(reverse("procurement:asn_confirm_delivery", args=[obj.pk]),
                             {"arrival_condition": "damaged", "pod_reference": "SNEAKY",
                              "received_signature_name": "Nobody"})
        assert resp.status_code == 302
    assert _fulfillment_asn_state(fulfillment_asn_draft_a) == draft_before
    assert _fulfillment_asn_state(fulfillment_asn_delivered_a) == delivered_before

    resp = client_a.post(
        reverse("procurement:asn_confirm_delivery", args=[fulfillment_asn_in_transit_a.pk]),
        {"arrival_condition": "good", "pod_reference": "POD-OK",
         "received_signature_name": "R. Keeper"})
    assert resp.status_code == 302
    fulfillment_asn_in_transit_a.refresh_from_db()
    assert fulfillment_asn_in_transit_a.status == "delivered"
    assert fulfillment_asn_in_transit_a.pod_reference == "POD-OK"
    stamped = _fulfillment_asn_state(fulfillment_asn_in_transit_a)

    resp = client_a.post(
        reverse("procurement:asn_confirm_delivery", args=[fulfillment_asn_in_transit_a.pk]),
        {"arrival_condition": "refused", "pod_reference": "SECOND-POD"})
    assert resp.status_code == 302
    assert _fulfillment_asn_state(fulfillment_asn_in_transit_a) == stamped


def test_fulfillment_confirm_delivery_never_honours_an_arbitrary_redirect_target(
        client_a, fulfillment_asn_in_transit_a, fulfillment_asn_late_a):
    """``next`` accepts exactly one literal (``confirmation``) and ``due`` is whitelisted against
    the board's own tab keys — an attacker-supplied URL is simply ignored, so the verb can never
    become an open redirect."""
    resp = client_a.post(
        reverse("procurement:asn_confirm_delivery", args=[fulfillment_asn_in_transit_a.pk]),
        {"arrival_condition": "good", "next": "https://evil.example/steal",
         "due": "https://evil.example/steal"})
    assert resp.status_code == 302
    assert resp["Location"] == reverse("procurement:asn_detail",
                                       args=[fulfillment_asn_in_transit_a.pk])

    # L44 pair: the ONE honoured literal still returns to the board, on its sanitized tab.
    resp = client_a.post(
        reverse("procurement:asn_confirm_delivery", args=[fulfillment_asn_late_a.pk]),
        {"arrival_condition": "good", "next": "confirmation", "due": "overdue"})
    assert resp.status_code == 302
    assert resp["Location"] == reverse("procurement:delivery_confirmation") + "?due=overdue"


def test_fulfillment_asn_cancel_requires_a_reason(client_a, fulfillment_asn_draft_a,
                                                  fulfillment_asn_in_transit_a):
    """A cancelled notice with no reason is indistinguishable from a data error: a blank POST is
    REJECTED (status untouched) rather than falling through to a cancellation."""
    before = _fulfillment_asn_state(fulfillment_asn_draft_a)
    for body in ({}, {"cancellation_reason": ""}, {"cancellation_reason": "   "}):
        resp = client_a.post(
            reverse("procurement:asn_cancel", args=[fulfillment_asn_draft_a.pk]), body)
        assert resp.status_code == 302
    assert _fulfillment_asn_state(fulfillment_asn_draft_a) == before

    resp = client_a.post(
        reverse("procurement:asn_cancel", args=[fulfillment_asn_in_transit_a.pk]),
        {"cancellation_reason": "Supplier withdrew the shipment."})
    assert resp.status_code == 302
    fulfillment_asn_in_transit_a.refresh_from_db()
    assert fulfillment_asn_in_transit_a.status == "cancelled"
    assert fulfillment_asn_in_transit_a.cancelled_at is not None


def test_fulfillment_asn_delete_is_drafts_only_even_for_an_admin(
        client_a, fulfillment_asn_in_transit_a, fulfillment_asn_delivered_a,
        fulfillment_asn_draft_a):
    """Admin rights are not a bypass for the status gate: an in-flight or delivered notice is
    part of the receiving trail and survives the delete POST. A draft still deletes (L44)."""
    for obj in (fulfillment_asn_in_transit_a, fulfillment_asn_delivered_a):
        resp = client_a.post(reverse("procurement:asn_delete", args=[obj.pk]))
        assert resp.status_code == 302
        assert resp["Location"] == reverse("procurement:asn_detail", args=[obj.pk])
        assert AdvancedShipmentNotice.objects.filter(pk=obj.pk).exists()

    resp = client_a.post(reverse("procurement:asn_delete", args=[fulfillment_asn_draft_a.pk]))
    assert resp.status_code == 302
    assert not AdvancedShipmentNotice.objects.filter(pk=fulfillment_asn_draft_a.pk).exists()


def test_fulfillment_asn_edit_refused_once_the_notice_is_closed(
        client_a, fulfillment_asn_delivered_a):
    """A delivered notice is a closed receiving record — the edit page refuses it server-side,
    not merely by hiding a button."""
    before = _fulfillment_asn_state(fulfillment_asn_delivered_a)
    detail = reverse("procurement:asn_detail", args=[fulfillment_asn_delivered_a.pk])

    resp = client_a.get(reverse("procurement:asn_edit", args=[fulfillment_asn_delivered_a.pk]))
    assert resp.status_code == 302 and resp["Location"] == detail

    body = _fulfillment_asn_payload(carrier_name="Edited after delivery")
    body.update(_fulfillment_lines_payload())
    resp = client_a.post(reverse("procurement:asn_edit",
                                 args=[fulfillment_asn_delivered_a.pk]), body)
    assert resp.status_code == 302 and resp["Location"] == detail
    assert _fulfillment_asn_state(fulfillment_asn_delivered_a) == before


def test_fulfillment_backorder_reschedule_requires_both_date_and_reason(
        client_a, fulfillment_backorder_open_a):
    """A promise that slips without a stated reason is exactly what this register exists to make
    visible: a half-filled POST changes nothing and does not increment the slip count."""
    before = _fulfillment_backorder_state(fulfillment_backorder_open_a)
    url = reverse("procurement:backorder_reschedule", args=[fulfillment_backorder_open_a.pk])
    for body in ({}, {"revised_promise_date": _fulfillment_iso(20)},
                 {"reason_note": "supplier called"},
                 {"revised_promise_date": "not-a-date", "reason_note": "supplier called"}):
        resp = client_a.post(url, body)
        assert resp.status_code == 302
    assert _fulfillment_backorder_state(fulfillment_backorder_open_a) == before

    resp = client_a.post(url, {"revised_promise_date": _fulfillment_iso(20),
                               "reason_note": "Foundry slot moved."})
    assert resp.status_code == 302
    fulfillment_backorder_open_a.refresh_from_db()
    assert fulfillment_backorder_open_a.reschedule_count == 1
    assert fulfillment_backorder_open_a.status == "rescheduled"
    assert fulfillment_backorder_open_a.revised_promise_date.isoformat() == _fulfillment_iso(20)


def test_fulfillment_closed_backorder_refuses_every_verb_and_the_edit_page(
        client_a, fulfillment_backorder_closed_a, fulfillment_po_line_a):
    """A closed shortfall is the record of what happened: edit, reschedule, fulfil, cancel and
    escalate are all refused, and no alert is minted."""
    before = _fulfillment_backorder_state(fulfillment_backorder_closed_a)
    alerts_before = ProcurementAlert.objects.count()
    pk = fulfillment_backorder_closed_a.pk
    detail = reverse("procurement:backorder_detail", args=[pk])

    resp = client_a.get(reverse("procurement:backorder_edit", args=[pk]))
    assert resp.status_code == 302 and resp["Location"] == detail
    resp = client_a.post(reverse("procurement:backorder_edit", args=[pk]),
                         _fulfillment_backorder_payload(po_line=str(fulfillment_po_line_a.pk),
                                                        reason="logistics"))
    assert resp.status_code == 302 and resp["Location"] == detail

    for name, body in (("procurement:backorder_reschedule",
                        {"revised_promise_date": _fulfillment_iso(5),
                         "reason_note": "reopen attempt"}),
                       ("procurement:backorder_fulfil", {"closure_note": "again"}),
                       ("procurement:backorder_cancel", {"closure_note": "again"}),
                       ("procurement:backorder_raise_alert", {})):
        resp = client_a.post(reverse(name, args=[pk]), body)
        assert resp.status_code == 302, name

    assert _fulfillment_backorder_state(fulfillment_backorder_closed_a) == before
    assert ProcurementAlert.objects.count() == alerts_before


def test_fulfillment_raise_alert_is_idempotent_and_stays_in_the_workspace(
        client_a, tenant_a, fulfillment_backorder_past_due_a):
    """L44 pair for the escalation guard: an OPEN shortfall does raise an alert, the second POST
    reuses it rather than flooding the inbox, and the alert lands in the raiser's workspace with
    an internal-only link (never an absolute URL)."""
    url = reverse("procurement:backorder_raise_alert",
                  args=[fulfillment_backorder_past_due_a.pk])
    before = ProcurementAlert.objects.count()

    assert client_a.post(url).status_code == 302
    fulfillment_backorder_past_due_a.refresh_from_db()
    alert = fulfillment_backorder_past_due_a.alert
    assert alert is not None
    assert ProcurementAlert.objects.count() == before + 1
    assert alert.tenant_id == tenant_a.pk
    assert alert.kind == "delivery"
    assert alert.link_url == reverse("procurement:backorder_detail",
                                     args=[fulfillment_backorder_past_due_a.pk])
    assert alert.link_url.startswith("/") and not alert.link_url.startswith("//")

    assert client_a.post(url).status_code == 302
    fulfillment_backorder_past_due_a.refresh_from_db()
    assert fulfillment_backorder_past_due_a.alert_id == alert.pk
    assert ProcurementAlert.objects.count() == before + 1


def test_fulfillment_split_refuses_a_line_already_fully_covered(
        client_a, tenant_a, fulfillment_po_line2_a, admin_user):
    """L35, split edition: the prerequisite for a split is uncommitted quantity. A fully covered
    line is REJECTED with a non-field error at 200 — it never falls through to minting
    instalments that would over-commit the order."""
    DeliverySchedule.objects.create(tenant=tenant_a, po_line=fulfillment_po_line2_a,
                                    sequence=1,
                                    scheduled_quantity=fulfillment_po_line2_a.quantity,
                                    need_by_date=timezone.localdate() + datetime.timedelta(days=5),
                                    created_by=admin_user)
    resp = client_a.post(reverse("procurement:deliveryschedule_split"),
                         _fulfillment_split_payload(po_line=str(fulfillment_po_line2_a.pk),
                                                    instalments="3"))
    assert resp.status_code == 200
    errors = resp.context["form"].non_field_errors()
    assert errors and "fully covered" in " ".join(errors)
    assert DeliverySchedule.objects.filter(po_line=fulfillment_po_line2_a).count() == 1


def test_fulfillment_delivery_schedule_cannot_be_pushed_past_the_ordered_quantity(
        client_a, tenant_a, fulfillment_po_line2_a, fulfillment_schedule_a,
        fulfillment_po_line_a):
    """The over-commitment block is a HARD one and lives in the model, so a direct POST hits it
    too: instalments summing above the ordered quantity are a field error, nothing is saved, and
    an honest under-covering instalment still saves (L44)."""
    before = DeliverySchedule.objects.filter(po_line=fulfillment_po_line_a).count()
    resp = client_a.post(reverse("procurement:deliveryschedule_create"),
                         _fulfillment_schedule_payload(
                             po_line=str(fulfillment_po_line_a.pk),
                             sequence="9", scheduled_quantity="99"))
    assert resp.status_code == 200
    assert "scheduled_quantity" in resp.context["form"].errors
    assert DeliverySchedule.objects.filter(po_line=fulfillment_po_line_a).count() == before

    resp = client_a.post(reverse("procurement:deliveryschedule_create"),
                         _fulfillment_schedule_payload(
                             po_line=str(fulfillment_po_line_a.pk),
                             sequence="9", scheduled_quantity="2"))
    assert resp.status_code == 302
    assert DeliverySchedule.objects.filter(po_line=fulfillment_po_line_a).count() == before + 1
