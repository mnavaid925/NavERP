"""Inventory 5.5 Warehousing & Bin Management — security.

Adversarial multi-tenancy around the BinCapacity CRUD and the CrossDockOrder document
plus its receive/ship/cancel verbs: cross-tenant IDOR on every route shape (GET pages,
destructive POSTs, lifecycle POSTs), server-side lifecycle guards that must hold even
when the UI hides the buttons (edit/delete against a received order), crafted-POST FK
injection against each foreign pointer (bin location / item / dock / lot), anonymous
walls, POST-only verbs, tenant-less superuser isolation, and ledger integrity — no
foreign session may ever grow another workspace's StockMove book.
"""
from decimal import Decimal

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.inventory.models import BinCapacity, CrossDockOrder
from apps.scm.models import StockMove

pytestmark = pytest.mark.django_db

#: Markers minted exclusively for ONE workspace. Codes/SKUs are deliberately unique per
#: tenant here because XD- numbers collide across workspaces (both tenants' first order
#: reads XD-00001) and must never be used as isolation probes on rendered pages.
_MARKERS_A = ["WA-BIN-A", "WA-DOCK-A", "WH-SKU-A"]
_MARKERS_B = ["WB-BIN-B", "WB-DOCK-B", "WH-SKU-B"]


# ---- module helpers ------------------------------------------------------------------------------


def _warehousing_location(tenant, code, location_type="bin"):
    """A location on SCM 4.3's spine (bin by default; pass 'staging' for docks)."""
    from apps.scm.models import Location
    return Location.objects.create(
        tenant=tenant, code=code, name=f"Area {code}", location_type=location_type)


def _warehousing_item(tenant, sku):
    """A stock item on the SCM spine with a non-zero cost basis."""
    from apps.scm.models import Item
    return Item.objects.create(
        tenant=tenant, sku=sku, name=f"Warehouse {sku}",
        item_type="stock", standard_cost=Decimal("8.00"))


def _warehousing_lot(tenant, item, number):
    """A lot/batch row for a tracked item."""
    from apps.scm.models import LotSerial
    return LotSerial.objects.create(tenant=tenant, item=item, kind="lot", number=number)


def _warehousing_capacity(location, **limits):
    """A BinCapacity envelope; the tenant always follows the location's spine row."""
    return BinCapacity.objects.create(
        tenant_id=location.tenant_id, location=location, **limits)


def _warehousing_xd(tenant, item, dock, quantity="10"):
    """A draft CrossDockOrder; save() mints its XD- number."""
    return CrossDockOrder.objects.create(
        tenant=tenant, item=item, dock_location=dock,
        quantity=Decimal(quantity), unit_cost=Decimal("2.50"),
        scheduled_date=timezone.localdate())


def _warehousing_xd_payload(item_pk, dock_pk, **overrides):
    """A minimal VALID cross-dock POST body; overrides carry the adversarial bits."""
    data = {"item": str(item_pk), "lot_serial": "", "dock_location": str(dock_pk),
            "quantity": "6", "unit_cost": "2.50", "scheduled_date": "2026-08-23",
            "inbound_reference": "GRN-X", "outbound_reference": "SHP-X", "notes": ""}
    data.update(overrides)
    return data


def _warehousing_capacity_payload(**overrides):
    data = {"location": "", "max_weight_kg": "500", "max_volume_m3": "",
            "max_quantity": "250", "notes": ""}
    data.update(overrides)
    return data


def _warehousing_assert_login_redirect(response):
    assert response.status_code == 302
    assert "/login" in response.url or response.url.endswith("login")


# ---- local fixtures ---------------------------------------------------------------------------


@pytest.fixture
def _warehousing_bin_a(db, tenant_a):
    return _warehousing_location(tenant_a, "WA-BIN-A")


@pytest.fixture
def _warehousing_dock_a(db, tenant_a):
    return _warehousing_location(tenant_a, "WA-DOCK-A", "staging")


@pytest.fixture
def _warehousing_item_a(db, tenant_a):
    return _warehousing_item(tenant_a, "WH-SKU-A")


@pytest.fixture
def _warehousing_bin_b(db, tenant_b):
    return _warehousing_location(tenant_b, "WB-BIN-B")


@pytest.fixture
def _warehousing_dock_b(db, tenant_b):
    return _warehousing_location(tenant_b, "WB-DOCK-B", "staging")


@pytest.fixture
def _warehousing_item_b(db, tenant_b):
    return _warehousing_item(tenant_b, "WH-SKU-B")


@pytest.fixture
def _warehousing_lot_b(db, tenant_b, _warehousing_item_b):
    """Globex's lot on Globex's item — the foreign pairing probe."""
    return _warehousing_lot(tenant_b, _warehousing_item_b, "WH-LOT-B")


@pytest.fixture
def _warehousing_capacity_a(db, _warehousing_bin_a):
    return _warehousing_capacity(_warehousing_bin_a, max_quantity=Decimal("100"))


@pytest.fixture
def _warehousing_capacity_b(db, _warehousing_bin_b):
    """The foreign capacity envelope IDOR/deletes are aimed at."""
    return _warehousing_capacity(_warehousing_bin_b, max_quantity=Decimal("200"))


@pytest.fixture
def _warehousing_xd_draft_a(db, tenant_a, _warehousing_item_a, _warehousing_dock_a):
    return _warehousing_xd(tenant_a, _warehousing_item_a, _warehousing_dock_a)


@pytest.fixture
def _warehousing_xd_received_a(db, tenant_a, admin_user, _warehousing_item_a,
                               _warehousing_dock_a):
    """Acme's received order — its receipt leg posted through the REAL receive()."""
    return _warehousing_xd(tenant_a, _warehousing_item_a, _warehousing_dock_a).receive(admin_user)


@pytest.fixture
def _warehousing_xd_draft_b(db, tenant_b, _warehousing_item_b, _warehousing_dock_b):
    """Globex's still-draft order — receive() from a foreign session must refuse it."""
    return _warehousing_xd(tenant_b, _warehousing_item_b, _warehousing_dock_b)


@pytest.fixture
def _warehousing_xd_received_b(db, tenant_b, admin_b, _warehousing_item_b,
                               _warehousing_dock_b):
    """Globex's received order with ONE posted StockMove leg via the real lifecycle."""
    return _warehousing_xd(tenant_b, _warehousing_item_b, _warehousing_dock_b).receive(admin_b)


@pytest.fixture
def _warehousing_tenantless_superuser(db):
    """The platform superuser: tenant=None BY DESIGN — it owns no workspace at all."""
    from apps.accounts.models import User
    return User.objects.create_user(
        email="wh-super@naverp.test", username="wh_superuser_admin",
        password="TestPass123!", tenant=None, is_superuser=True, is_staff=True)


@pytest.fixture
def _warehousing_super_client(_warehousing_tenantless_superuser):
    c = Client()
    c.force_login(_warehousing_tenantless_superuser)
    return c


# ---- 1. IDOR: GET pages -------------------------------------------------------------------------


def test_warehousing_idor_gets_on_foreign_pks_return_404(
        client_a, _warehousing_capacity_b, _warehousing_xd_received_b):
    for name, pk in [("bincapacity_detail", _warehousing_capacity_b.pk),
                     ("bincapacity_edit", _warehousing_capacity_b.pk),
                     ("crossdockorder_detail", _warehousing_xd_received_b.pk),
                     ("crossdockorder_edit", _warehousing_xd_received_b.pk)]:
        assert client_a.get(reverse(f"inventory:{name}", args=[pk])).status_code == 404


# ---- 2. IDOR: writes -----------------------------------------------------------------------------


def test_warehousing_idor_delete_posts_cannot_touch_foreign_rows(
        client_a, _warehousing_capacity_b, _warehousing_xd_received_b):
    """The destructive verb is where an IDOR would do damage: a foreign pk must 404 on
    POST and leave the other workspace's row exactly where it was."""
    response = client_a.post(reverse("inventory:bincapacity_delete",
                                     args=[_warehousing_capacity_b.pk]))
    assert response.status_code == 404
    _warehousing_capacity_b.refresh_from_db()  # raises if deleted — the real assertion

    response = client_a.post(reverse("inventory:crossdockorder_delete",
                                     args=[_warehousing_xd_received_b.pk]))
    assert response.status_code == 404
    _warehousing_xd_received_b.refresh_from_db()


def test_warehousing_idor_lifecycle_verbs_leave_foreign_orders_alone(
        client_a, _warehousing_xd_draft_b, _warehousing_xd_received_b):
    cases = [("crossdockorder_receive", _warehousing_xd_draft_b, "draft"),
             ("crossdockorder_ship", _warehousing_xd_received_b, "received"),
             ("crossdockorder_cancel", _warehousing_xd_received_b, "received")]
    for name, order, expected_status in cases:
        response = client_a.post(reverse(f"inventory:{name}", args=[order.pk]))
        assert response.status_code == 404
        order.refresh_from_db()
        assert order.status == expected_status
        expected_legs = 0 if expected_status == "draft" else 1
        assert order.ledger_moves().count() == expected_legs


# ---- 3. Server-side lifecycle guards (owning tenant; review fixes I1/I2) --------------------------


def test_warehousing_edit_guard_blocks_posted_order_even_when_ui_hides_edit(
        client_b, _warehousing_xd_received_b):
    """Regression I1: the template hides Edit once ledger legs exist, but a crafted
    owning-tenant POST must not re-open quantity/item/dock beneath posted moves."""
    response = client_b.post(
        reverse("inventory:crossdockorder_edit", args=[_warehousing_xd_received_b.pk]),
        data=_warehousing_xd_payload(_warehousing_xd_received_b.item_id,
                                     _warehousing_xd_received_b.dock_location_id,
                                     quantity="999"))
    assert response.status_code == 302  # refused with a flash, never a form save
    _warehousing_xd_received_b.refresh_from_db()
    assert _warehousing_xd_received_b.quantity == Decimal("10")
    assert _warehousing_xd_received_b.status == "received"


def test_warehousing_delete_guard_keeps_received_order_alive(
        client_b, _warehousing_xd_received_b):
    """Regression I2: delete is draft-only even when the UI is bypassed — deleting the
    document would orphan its immutable StockMove legs' provenance."""
    response = client_b.post(reverse("inventory:crossdockorder_delete",
                                     args=[_warehousing_xd_received_b.pk]))
    assert response.status_code == 302  # refused with a flash, never removed
    _warehousing_xd_received_b.refresh_from_db()  # raises if deleted
    assert _warehousing_xd_received_b.status == "received"
    assert _warehousing_xd_received_b.ledger_moves().count() == 1


def test_warehousing_delete_still_removes_own_draft(client_b, _warehousing_xd_draft_b):
    """The guard narrows to non-drafts only: a legitimate own draft delete still works."""
    response = client_b.post(reverse("inventory:crossdockorder_delete",
                                     args=[_warehousing_xd_draft_b.pk]))
    assert response.status_code == 302
    assert not CrossDockOrder.objects.filter(pk=_warehousing_xd_draft_b.pk).exists()


# ---- 4. Crafted-FK containment ---------------------------------------------------------------------


def test_warehousing_capacity_create_rejects_foreign_location(
        client_a, _warehousing_bin_a, _warehousing_bin_b):
    """A narrowed <select> is UX, not an authorization boundary: posting Globex's bin pk
    into Acme's profile form must end as THAT field's error, never a 500 or a row."""
    total_before = BinCapacity.objects.count()
    response = client_a.post(reverse("inventory:bincapacity_create"),
                             data=_warehousing_capacity_payload(
                                 location=_warehousing_bin_b.pk))
    assert response.status_code == 200
    assert "location" in response.context["form"].errors
    assert BinCapacity.objects.count() == total_before


@pytest.mark.parametrize("field_name,foreign_fixture", [
    ("item", "_warehousing_item_b"),
    ("dock_location", "_warehousing_dock_b"),
    ("lot_serial", "_warehousing_lot_b"),  # B's lot paired with A's OWN item
])
def test_warehousing_crossdock_create_rejects_each_foreign_fk(
        client_a, _warehousing_item_a, _warehousing_dock_a, field_name, foreign_fixture,
        request):
    foreign = request.getfixturevalue(foreign_fixture)
    data = _warehousing_xd_payload(_warehousing_item_a.pk, _warehousing_dock_a.pk)
    data[field_name] = foreign.pk

    total_before = CrossDockOrder.objects.count()
    response = client_a.post(reverse("inventory:crossdockorder_create"), data=data)
    assert response.status_code == 200
    assert field_name in response.context["form"].errors
    assert CrossDockOrder.objects.count() == total_before


# ---- 5. Auth walls ----------------------------------------------------------------------------------


def test_warehousing_anonymous_redirected_on_every_route(
        client, _warehousing_capacity_a, _warehousing_xd_received_a):
    plain_routes = ["bincapacity_list", "bincapacity_create", "warehousemap",
                    "crossdockorder_list", "crossdockorder_create"]
    argged_routes = ["bincapacity_detail", "crossdockorder_detail"]
    for name in plain_routes:
        response = client.get(reverse(f"inventory:{name}"))
        _warehousing_assert_login_redirect(response)
    for name in argged_routes:
        pk = (_warehousing_capacity_a.pk if name.startswith("bincapacity")
              else _warehousing_xd_received_a.pk)
        response = client.get(reverse(f"inventory:{name}", args=[pk]))
        _warehousing_assert_login_redirect(response)
    # one state-changing verb too — login_required wraps require_POST on every action
    _warehousing_assert_login_redirect(client.get(reverse(
        "inventory:crossdockorder_receive", args=[_warehousing_xd_received_a.pk])))


# ---- 6. Verb discipline ---------------------------------------------------------------------------


def test_warehousing_state_changing_verbs_reject_get(client_a, _warehousing_capacity_a,
                                                     _warehousing_xd_draft_a,
                                                     _warehousing_xd_received_a):
    for name, pk in [("bincapacity_delete", _warehousing_capacity_a.pk),
                     ("crossdockorder_delete", _warehousing_xd_draft_a.pk),
                     ("crossdockorder_receive", _warehousing_xd_draft_a.pk),
                     ("crossdockorder_ship", _warehousing_xd_received_a.pk),
                     ("crossdockorder_cancel", _warehousing_xd_received_a.pk)]:
        assert client_a.get(reverse(f"inventory:{name}", args=[pk])).status_code == 405


# ---- 7. Superuser isolation -------------------------------------------------------------------------


def test_warehousing_tenantless_superuser_sees_zero_workspace_objects(
        _warehousing_super_client, _warehousing_capacity_a, _warehousing_capacity_b,
        _warehousing_xd_received_a, _warehousing_xd_received_b):
    """tenant=None means NO workspace: list pages and the map render with zero rows from
    either tenant — asserted on markers each fixture mints exclusively for one side."""
    for name in ["bincapacity_list", "crossdockorder_list", "warehousemap"]:
        response = _warehousing_super_client.get(reverse(f"inventory:{name}"))
        assert response.status_code == 200
        html = response.content.decode()
        for marker in _MARKERS_A + _MARKERS_B:
            assert marker not in html


# ---- 8. Ledger integrity across attempts --------------------------------------------------------------


def test_warehousing_no_foreign_session_grows_the_ledger(
        client_a, _warehousing_capacity_b, _warehousing_xd_draft_b,
        _warehousing_xd_received_b):
    """Every hostile verb tenant_a can aim at Globex's documents, fired as one battery:
    the StockMove book keyed to B's XD number ends exactly where it started."""
    received = _warehousing_xd_received_b
    legs_before = received.ledger_moves().count()
    tenant_b_moves_before = StockMove.objects.filter(tenant_id=received.tenant_id).count()

    client_a.post(reverse("inventory:crossdockorder_edit", args=[received.pk]),
                  data=_warehousing_xd_payload(received.item_id,
                                               received.dock_location_id))
    client_a.post(reverse("inventory:crossdockorder_delete", args=[received.pk]))
    client_a.post(reverse("inventory:crossdockorder_receive",
                          args=[_warehousing_xd_draft_b.pk]))
    client_a.post(reverse("inventory:crossdockorder_ship", args=[received.pk]))
    client_a.post(reverse("inventory:crossdockorder_cancel", args=[received.pk]))
    client_a.post(reverse("inventory:bincapacity_delete",
                          args=[_warehousing_capacity_b.pk]))

    assert received.ledger_moves().count() == legs_before == 1
    assert StockMove.objects.filter(tenant_id=received.tenant_id).count() \
        == tenant_b_moves_before
    received.refresh_from_db()
    assert received.status == "received"
    _warehousing_xd_draft_b.refresh_from_db()
    assert _warehousing_xd_draft_b.status == "draft"
    assert _warehousing_xd_draft_b.ledger_moves().count() == 0
