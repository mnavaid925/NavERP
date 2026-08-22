"""Inventory 5.6 Inventory Tracking & Control — security.

Cross-tenant IDOR on every route shape of the tracking layer (StockStatus CRUD,
InventoryReservation CRUD + the release/consume/cancel lifecycle verbs), list isolation,
crafted-POST FK injection against the two create forms, POST-only destructive verbs,
anonymous access, CSRF enforcement, Real-Time Stock Levels isolation under a query that
matches BOTH workspaces' SKUs, and the audit trail left by a lifecycle verb.
"""
from decimal import Decimal

import pytest
from django.contrib.contenttypes.models import ContentType
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.core.models import AuditLog
from apps.inventory.models import InventoryReservation, StockStatus
from apps.scm.models import Location, StockMove

pytestmark = pytest.mark.django_db

#: Both workspaces' items share the SKU ``CAT-1`` (see tests/conftest), so isolation is
#: asserted on strings that are unique PER ROW: classification reasons, reservation
#: references and the per-tenant location codes/names these fixtures mint.
FOREIGN_MARKERS = ["TRK-B1", "Globex Tracking Dock B", "GLOBEX expired batch B7",
                   "JOB-GLOBEX-99"]
OWN_MARKERS = ["TRK-A1", "Tracking Dock A"]


# ---- local fixtures: one owned + one foreign spot per surface ---------------------------------

@pytest.fixture
def _tracking_loc_a(db, tenant_a):
    return Location.objects.create(tenant=tenant_a, code="TRK-A1", name="Tracking Dock A")


@pytest.fixture
def _tracking_loc_b(db, tenant_b):
    return Location.objects.create(tenant=tenant_b, code="TRK-B1",
                                   name="Globex Tracking Dock B")


@pytest.fixture
def _tracking_move_a(db, tenant_a, item_a, _tracking_loc_a):
    return StockMove.objects.create(
        tenant=tenant_a, item=item_a, location=_tracking_loc_a, quantity=Decimal("10"),
        unit_cost=Decimal("0"), move_type="receipt", moved_at=timezone.now())


@pytest.fixture
def _tracking_move_b(db, tenant_b, item_b, _tracking_loc_b):
    return StockMove.objects.create(
        tenant=tenant_b, item=item_b, location=_tracking_loc_b, quantity=Decimal("10"),
        unit_cost=Decimal("0"), move_type="receipt", moved_at=timezone.now())


@pytest.fixture
def _tracking_status_a(db, tenant_a, item_a, _tracking_loc_a):
    """Acme's own damaged claim — the legitimate target for method/CSRF checks."""
    return StockStatus.objects.create(
        tenant=tenant_a, item=item_a, location=_tracking_loc_a, status="damaged",
        quantity=Decimal("2"), reason="fork puncture case A")


@pytest.fixture
def _tracking_status_b(db, tenant_b, item_b, _tracking_loc_b):
    """Globex's expired claim — the foreign target every IDOR probe must fail against."""
    return StockStatus.objects.create(
        tenant=tenant_b, item=item_b, location=_tracking_loc_b, status="expired",
        quantity=Decimal("3"), reason="GLOBEX expired batch B7")


@pytest.fixture
def _tracking_resv_a(db, tenant_a, item_a, _tracking_loc_a):
    """An active Acme lock worth 4 — leaves 10 − 4 − 2(classified) = 4 available."""
    return InventoryReservation.objects.create(
        tenant=tenant_a, item=item_a, location=_tracking_loc_a, purpose="sales_order",
        reference="SO-ACME-77", quantity=Decimal("4"))


@pytest.fixture
def _tracking_resv_b(db, tenant_b, item_b, _tracking_loc_b):
    """Globex's active lock — still 'reserved' after every cross-tenant attempt."""
    return InventoryReservation.objects.create(
        tenant=tenant_b, item=item_b, location=_tracking_loc_b, purpose="job",
        reference="JOB-GLOBEX-99", quantity=Decimal("5"))


@pytest.fixture
def _tracking_csrf_client(admin_user):
    strict = Client(enforce_csrf_checks=True)
    strict.force_login(admin_user)
    return strict


# ---- module-level helpers ---------------------------------------------------------------------

def _tracking_assert_login_redirect(response):
    assert response.status_code == 302
    assert "/login" in response.url or response.url.endswith("login")


def _tracking_assert_no_foreign_marker(content):
    html = content.decode() if isinstance(content, bytes) else content
    for marker in FOREIGN_MARKERS:
        assert marker not in html


# ---- IDOR reads --------------------------------------------------------------------------------

def test_tracking_idor_stockstatus_read_and_edit_404(client_a, _tracking_status_b):
    for name in ["stockstatus_detail", "stockstatus_edit"]:
        url = reverse(f"inventory:{name}", args=[_tracking_status_b.pk])
        assert client_a.get(url).status_code == 404


def test_tracking_idor_reservation_read_and_edit_404(client_a, _tracking_resv_b):
    for name in ["reservation_detail", "reservation_edit"]:
        url = reverse(f"inventory:{name}", args=[_tracking_resv_b.pk])
        assert client_a.get(url).status_code == 404


# ---- list isolation -----------------------------------------------------------------------------

def test_tracking_foreign_rows_never_leak_into_lists(client_a, _tracking_status_b,
                                                     _tracking_resv_b):
    """No foreign marker anywhere on either list page — including when the search box is
    handed the SKU BOTH workspaces share (only Acme's rows may answer it; a probe string
    unique to Globex would merely be echoed back as the query value, never as row data)."""
    for name in ["stockstatus_list", "reservation_list"]:
        base = reverse(f"inventory:{name}")
        plain = client_a.get(base)
        assert plain.status_code == 200
        _tracking_assert_no_foreign_marker(plain.content)
        probed = client_a.get(base + "?q=CAT-1")
        assert probed.status_code == 200
        _tracking_assert_no_foreign_marker(probed.content)


# ---- IDOR mutations ------------------------------------------------------------------------------

def test_tracking_idor_stockstatus_delete_post_404_and_survives(client_a, _tracking_status_b):
    response = client_a.post(reverse("inventory:stockstatus_delete",
                                     args=[_tracking_status_b.pk]))
    assert response.status_code == 404
    _tracking_status_b.refresh_from_db()  # raises if deleted — the real assertion
    assert _tracking_status_b.status == "expired"


def test_tracking_idor_reservation_delete_post_404_and_survives(client_a, _tracking_resv_b):
    response = client_a.post(reverse("inventory:reservation_delete",
                                     args=[_tracking_resv_b.pk]))
    assert response.status_code == 404
    _tracking_resv_b.refresh_from_db()
    assert _tracking_resv_b.status == "reserved"


@pytest.mark.parametrize("verb,target", [
    ("release", "released"),
    ("consume", "consumed"),
    ("cancel", "cancelled"),
])
def test_tracking_idor_lifecycle_verbs_404_and_unchanged(client_a, _tracking_resv_b,
                                                         verb, target):
    """The destructive verbs are where an IDOR would move someone else's stock: a foreign
    pk must 404 on POST and leave the claim's lifecycle exactly where it was."""
    response = client_a.post(reverse(f"inventory:reservation_{verb}",
                                     args=[_tracking_resv_b.pk]))
    assert response.status_code == 404
    _tracking_resv_b.refresh_from_db()
    assert _tracking_resv_b.status != target
    assert _tracking_resv_b.status == "reserved"


# ---- crafted-POST FK injection --------------------------------------------------------------------

def test_tracking_crafted_post_cannot_classify_foreign_item_or_location(
        client_a, tenant_a, tenant_b, item_b, _tracking_loc_b):
    """A stock-status form POST pointing item/location at Globex rows must come back as a
    re-rendered form with errors, create NOTHING in either workspace, and leak none of the
    foreign rows' data through the error text."""
    response = client_a.post(reverse("inventory:stockstatus_create"), data={
        "item": item_b.pk, "location": _tracking_loc_b.pk, "lot_serial": "",
        "status": "damaged", "quantity": "1", "reason": "crafted-classification",
        "effective_at": "2026-08-20T10:00"})
    assert response.status_code == 200
    html = response.content.decode()
    assert ("not one of the available choices" in html
            or "That record belongs to another workspace." in html)
    _tracking_assert_no_foreign_marker(response.content)
    assert not StockStatus.objects.filter(reason="crafted-classification").exists()


def test_tracking_crafted_post_cannot_reserve_foreign_item_or_location(
        client_a, item_b, _tracking_loc_b):
    """Same injection against the hand-rolled reservation create: rejected as field errors,
    zero rows written anywhere."""
    response = client_a.post(reverse("inventory:reservation_create"), data={
        "item": item_b.pk, "location": _tracking_loc_b.pk, "lot_serial": "",
        "purpose": "sales_order", "reference": "CRAFTED-RSV", "quantity": "1",
        "notes": ""})
    assert response.status_code == 200
    html = response.content.decode()
    assert ("not one of the available choices" in html
            or "That record belongs to another workspace." in html)
    _tracking_assert_no_foreign_marker(response.content)
    assert not InventoryReservation.objects.filter(reference="CRAFTED-RSV").exists()


# ---- method discipline ------------------------------------------------------------------------

def test_tracking_deletes_reject_get(client_a, _tracking_status_a, _tracking_resv_a):
    for name, obj in [("stockstatus_delete", _tracking_status_a),
                      ("reservation_delete", _tracking_resv_a)]:
        url = reverse(f"inventory:{name}", args=[obj.pk])
        assert client_a.get(url).status_code == 405


@pytest.mark.parametrize("verb", ["release", "consume", "cancel"])
def test_tracking_lifecycle_verbs_reject_get(client_a, _tracking_resv_a, verb):
    url = reverse(f"inventory:reservation_{verb}", args=[_tracking_resv_a.pk])
    assert client_a.get(url).status_code == 405


# ---- auth --------------------------------------------------------------------------------------

def test_tracking_anonymous_redirected_on_every_page_incl_verbs(client, _tracking_status_a,
                                                                _tracking_resv_a):
    for name in ["stocklevels", "stockstatus_list", "stockstatus_create"]:
        _tracking_assert_login_redirect(client.get(reverse(f"inventory:{name}")))
    for name in ["reservation_list", "reservation_create"]:
        _tracking_assert_login_redirect(client.get(reverse(f"inventory:{name}")))
    for name, obj in [("stockstatus_detail", _tracking_status_a),
                      ("stockstatus_edit", _tracking_status_a),
                      ("stockstatus_delete", _tracking_status_a),
                      ("reservation_detail", _tracking_resv_a),
                      ("reservation_edit", _tracking_resv_a),
                      ("reservation_delete", _tracking_resv_a)]:
        _tracking_assert_login_redirect(client.get(reverse(f"inventory:{name}", args=[obj.pk])))
    for verb in ["release", "consume", "cancel"]:
        url = reverse(f"inventory:reservation_{verb}", args=[_tracking_resv_a.pk])
        _tracking_assert_login_redirect(client.get(url))


# ---- CSRF ---------------------------------------------------------------------------------------

def test_tracking_csrf_refused_on_create_and_delete(_tracking_csrf_client, item_a,
                                                    _tracking_loc_a, _tracking_resv_a):
    create = _tracking_csrf_client.post(reverse("inventory:stockstatus_create"), data={
        "item": item_a.pk, "location": _tracking_loc_a.pk, "lot_serial": "",
        "status": "damaged", "quantity": "1", "reason": "csrf-probe",
        "effective_at": "2026-08-20T10:00"})
    delete = _tracking_csrf_client.post(reverse("inventory:reservation_delete",
                                                args=[_tracking_resv_a.pk]))
    assert create.status_code == 403
    assert delete.status_code == 403
    assert not StockStatus.objects.filter(reason="csrf-probe").exists()
    _tracking_resv_a.refresh_from_db()  # nothing was deleted despite the valid session


# ---- Real-Time Stock Levels isolation -----------------------------------------------------------

def test_tracking_levels_page_isolates_tenants_even_when_q_matches_both(
        client_a, _tracking_move_a, _tracking_move_b):
    """``q=cat`` matches BOTH workspaces' SKUs (both read CAT-1) — the page may only ever
    merge Acme's ledger rows, and the shortage view cannot be tricked into leaking either."""
    page = client_a.get(reverse("inventory:stocklevels") + "?q=cat")
    assert page.status_code == 200
    html = page.content.decode()
    for marker in OWN_MARKERS:  # the workspace's own combo renders
        assert marker in html
    _tracking_assert_no_foreign_marker(html)

    shortage = client_a.get(reverse("inventory:stocklevels") +
                            "?view=shortage&q=CAT-1")
    assert shortage.status_code == 200
    short_html = shortage.content.decode()
    # Acme's row has 10 − 4 − 2 = 4 available (> 0), so the shortage filter empties the
    # table entirely ("No stock levels yet" empty state) — and the foreign workspace
    # contributes nothing at all (the dropdown may still list Acme's OWN locations).
    assert "No stock levels yet" in short_html
    _tracking_assert_no_foreign_marker(shortage.content)


# ---- audit trail --------------------------------------------------------------------------------

def test_tracking_release_writes_audit_log_attributed_to_actor(client_a, admin_user,
                                                               _tracking_resv_a):
    response = client_a.post(reverse("inventory:reservation_release",
                                     args=[_tracking_resv_a.pk]))
    assert response.status_code == 302
    log = AuditLog.objects.filter(
        content_type=ContentType.objects.get_for_model(InventoryReservation),
        object_id=_tracking_resv_a.pk, action="released").order_by("-pk").first()
    assert log is not None
    assert log.user_id == admin_user.pk
    assert log.tenant_id == _tracking_resv_a.tenant_id
