"""Inventory 5.5 — Warehousing & Bin Management views.

BinCapacity CRUD (with its ledger-derived over-capacity filter), CrossDockOrder CRUD
plus the receive/ship/cancel lifecycle verbs and their server-side guards, and the
computed Warehouse Map. Every route renders for its own tenant; the map renders an
honest empty state for the tenant-less superuser.
"""
import datetime
from decimal import Decimal

import pytest
from django.db.models import Sum
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.inventory.models import BinCapacity, CrossDockOrder

# Workaround while the in-flight 5.6/5.8 build lands: its views import constants
# (APPLIES_TO_CHOICES, SCOPE_*) from ``apps.inventory.models`` before the package
# root re-exports them, which breaks the URLconf import for EVERY inventory view
# test. Back-fill anything the sub-packages already export; guarded -> inert once
# the real exports exist.
import apps.inventory.models as _inv_models
from apps.inventory.models import LotSerialTracking as _lst_pkg
from apps.inventory.models import StockMovementTransfers as _smt_pkg

for _pkg in (_smt_pkg, _lst_pkg):
    for _name in getattr(_pkg, "__all__", []):
        if not hasattr(_inv_models, _name):
            setattr(_inv_models, _name, getattr(_pkg, _name))

pytestmark = pytest.mark.django_db


# -- helpers ------------------------------------------------------------------------------------

def _warehousing_location(tenant, code, **fields):
    """get_or_create-safe by the spine's (tenant, code) uniqueness."""
    from apps.scm.models import Location
    loc, _created = Location.objects.get_or_create(
        tenant=tenant, code=code, defaults={"name": f"Area {code}", **fields})
    return loc


def _warehousing_tree(tenant):
    """warehouse > bin A / bin B / staging dock - the layout every page here reads."""
    suffix = tenant.slug[:4].upper()
    warehouse = _warehousing_location(tenant, f"WH-{suffix}", location_type="warehouse")
    bin_a = _warehousing_location(tenant, f"{suffix}-A-01", location_type="bin",
                                  parent=warehouse)
    bin_b = _warehousing_location(tenant, f"{suffix}-B-02", location_type="bin",
                                  parent=warehouse)
    dock = _warehousing_location(tenant, f"{suffix}-DOCK", location_type="staging",
                                 parent=warehouse, is_pickable=False)
    return {"warehouse": warehouse, "bin_a": bin_a, "bin_b": bin_b, "dock": dock}


def _warehousing_item(tenant, sku):
    from apps.scm.models import Item
    item, _created = Item.objects.get_or_create(
        tenant=tenant, sku=sku,
        defaults={"name": f"Widget {sku}", "standard_cost": Decimal("5.00"),
                  "item_type": "stock"})
    return item


def _warehousing_move(tenant, item, location, quantity, reference=""):
    from apps.scm.models import StockMove
    return StockMove.objects.create(
        tenant=tenant, item=item, location=location, quantity=Decimal(quantity),
        unit_cost=Decimal("2.00"), move_type="receipt", reason="seed",
        reference=reference, moved_at=timezone.now())


def _warehousing_profile(tenant, location, **limits):
    from apps.inventory.models import BinCapacity
    profile, _created = BinCapacity.objects.get_or_create(
        tenant=tenant, location=location, defaults=limits)
    return profile


def _warehousing_order(tenant, item, dock, *, quantity="10", status=None, **fields):
    from apps.inventory.models import CrossDockOrder
    order = CrossDockOrder.objects.create(
        tenant=tenant, item=item, dock_location=dock, quantity=Decimal(quantity),
        scheduled_date=datetime.date(2026, 8, 25), **fields)
    if status and status != "draft":
        CrossDockOrder.objects.filter(pk=order.pk).update(status=status)
        order.refresh_from_db()
    return order


def _warehousing_root_client(db):
    """A logged-in SUPERUSER - ``request.tenant is None`` by design. The root conftest
    ships no tenant-less client, so this builds one inline."""
    from apps.accounts.models import User
    user = User.objects.create_superuser(email="root55@naverp.test", username="root55",
                                         password="TestPass123!")
    client = Client()
    client.force_login(user)
    return client


# -- BinCapacity list ---------------------------------------------------------------------------

def test_warehousing_bincapacity_list_renders_seeded_bin(client_a, tenant_a):
    tree = _warehousing_tree(tenant_a)
    profile = _warehousing_profile(tenant_a, tree["bin_a"], max_quantity=Decimal("500"))
    response = client_a.get(reverse("inventory:bincapacity_list"))
    assert response.status_code == 200
    assert b"Bin Capacity Management" in response.content
    assert tree["bin_a"].code.encode() in response.content
    assert profile in response.context["object_list"]


def test_warehousing_bincapacity_list_location_filter_narrows(client_a, tenant_a):
    tree = _warehousing_tree(tenant_a)
    profile_a = _warehousing_profile(tenant_a, tree["bin_a"], max_quantity=Decimal("100"))
    profile_b = _warehousing_profile(tenant_a, tree["bin_b"], max_weight_kg=Decimal("800"))
    hit = client_a.get(reverse("inventory:bincapacity_list") + f"?location={tree['bin_a'].pk}")
    assert hit.status_code == 200
    assert {row.pk for row in hit.context["object_list"]} == {profile_a.pk}
    hit_b = client_a.get(reverse("inventory:bincapacity_list") + f"?location={tree['bin_b'].pk}")
    assert {row.pk for row in hit_b.context["object_list"]} == {profile_b.pk}


def test_warehousing_bincapacity_utilisation_over_matches_ledger(client_a, tenant_a):
    """?utilisation=over returns EXACTLY the profiles whose live StockMove sum is
    >= max_quantity - asserted against an independently ORM-computed set."""
    from apps.inventory.models import BinCapacity
    from apps.scm.models import StockMove

    tree = _warehousing_tree(tenant_a)
    item = _warehousing_item(tenant_a, "UTIL-1")
    full = _warehousing_profile(tenant_a, tree["bin_a"], max_quantity=Decimal("100"))
    near = _warehousing_profile(tenant_a, tree["bin_b"], max_quantity=Decimal("100"))
    unbounded = _warehousing_profile(tenant_a, tree["dock"])   # no limits declared
    _warehousing_move(tenant_a, item, tree["bin_a"], "150")     # >= limit -> over
    _warehousing_move(tenant_a, item, tree["bin_b"], "99.99")   # just under -> not over

    totals = {row["location_id"]: row["q"]
              for row in StockMove.objects.values("location_id").annotate(q=Sum("quantity"))}
    expected = {bc.pk for bc in BinCapacity.objects.filter(tenant=tenant_a)
                if bc.max_quantity is not None
                and totals.get(bc.location_id) is not None
                and totals[bc.location_id] >= bc.max_quantity}

    plain = client_a.get(reverse("inventory:bincapacity_list"))
    assert plain.status_code == 200
    assert full.pk in {row.pk for row in plain.context["object_list"]}
    over = client_a.get(reverse("inventory:bincapacity_list") + "?utilisation=over")
    assert over.status_code == 200
    shown = {row.pk for row in over.context["object_list"]}
    assert shown == expected == {full.pk}
    assert near.pk not in shown
    assert unbounded.pk not in shown


def test_warehousing_bincapacity_junk_get_params_degrade_not_500(client_a):
    base = reverse("inventory:bincapacity_list")
    junk = "?location=abc&page=99&q=zzz&utilisation=over"
    assert client_a.get(base + junk).status_code == 200


# -- BinCapacity create -------------------------------------------------------------------------

def test_warehousing_bincapacity_create_get_and_post_valid(client_a, tenant_a):
    tree = _warehousing_tree(tenant_a)
    url = reverse("inventory:bincapacity_create")
    form_page = client_a.get(url)
    assert form_page.status_code == 200
    for field in ("location", "max_weight_kg", "max_volume_m3", "max_quantity", "notes"):
        assert f'name="{field}"'.encode() in form_page.content

    response = client_a.post(url, data={
        "location": tree["bin_b"].pk, "max_weight_kg": "1200.00", "max_volume_m3": "",
        "max_quantity": "400", "notes": "heavy rack",
    })
    assert response.status_code == 302
    assert response.url == reverse("inventory:bincapacity_list")
    row = _warehousing_profile(tenant_a, tree["bin_b"])
    row.refresh_from_db()
    assert row.max_quantity == Decimal("400")
    assert row.max_weight_kg == Decimal("1200")


def test_warehousing_bincapacity_create_all_blank_limits_rerenders_with_error(
        client_a, tenant_a):
    tree = _warehousing_tree(tenant_a)
    response = client_a.post(reverse("inventory:bincapacity_create"), data={
        "location": tree["bin_a"].pk, "max_weight_kg": "", "max_volume_m3": "",
        "max_quantity": "", "notes": "",
    })
    assert response.status_code == 200
    assert b"Set at least one limit" in response.content
    assert not BinCapacity.objects.filter(tenant=tenant_a).exists()


# -- BinCapacity detail / edit / delete ---------------------------------------------------------

def test_warehousing_bincapacity_detail_shows_code_limit_and_on_hand(client_a, tenant_a):
    tree = _warehousing_tree(tenant_a)
    item = _warehousing_item(tenant_a, "DET-1")
    profile = _warehousing_profile(tenant_a, tree["bin_a"], max_weight_kg=Decimal("900"),
                                   max_quantity=Decimal("100"))
    _warehousing_move(tenant_a, item, tree["bin_a"], "25.50")
    content = client_a.get(reverse("inventory:bincapacity_detail", args=[profile.pk])).content
    assert tree["bin_a"].code.encode() in content      # the bin code renders
    assert b"900 kg" in content                        # weight limit renders
    assert b"100 units" in content                     # quantity limit renders
    assert b"25.50" in content                         # live ledger on-hand figure


def test_warehousing_bincapacity_edit_prefilled_and_persists(client_a, tenant_a):
    tree = _warehousing_tree(tenant_a)
    profile = _warehousing_profile(tenant_a, tree["bin_a"], max_weight_kg=Decimal("900"),
                                   max_quantity=Decimal("100"))
    edit_url = reverse("inventory:bincapacity_edit", args=[profile.pk])
    page = client_a.get(edit_url)
    assert page.status_code == 200
    assert page.context["form"].initial["max_quantity"] == Decimal("100")

    response = client_a.post(edit_url, data={
        "location": tree["bin_a"].pk, "max_weight_kg": "900", "max_volume_m3": "",
        "max_quantity": "250", "notes": "",
    })
    assert response.status_code == 302
    profile.refresh_from_db()
    assert profile.max_quantity == Decimal("250")       # the changed limit persisted
    assert profile.max_weight_kg == Decimal("900")      # untouched limit stayed


def test_warehousing_bincapacity_delete_refuses_get_and_deletes_on_post(client_a, tenant_a):
    tree = _warehousing_tree(tenant_a)
    profile = _warehousing_profile(tenant_a, tree["bin_a"], max_quantity=Decimal("10"))
    delete_url = reverse("inventory:bincapacity_delete", args=[profile.pk])
    assert client_a.get(delete_url).status_code == 405   # GET is refused...
    assert client_a.post(delete_url).status_code == 302  # ...POST deletes
    assert not BinCapacity.objects.filter(pk=profile.pk).exists()


# -- CrossDock list -----------------------------------------------------------------------------

def test_warehousing_crossdockorder_list_renders_number(client_a, tenant_a):
    tree = _warehousing_tree(tenant_a)
    item = _warehousing_item(tenant_a, "XD-1")
    order = _warehousing_order(tenant_a, item, tree["dock"])
    response = client_a.get(reverse("inventory:crossdockorder_list"))
    assert response.status_code == 200
    assert b"Cross-Docking" in response.content
    assert order.number.encode() in response.content
    assert order in response.context["object_list"]


def test_warehousing_crossdockorder_list_status_filter_narrows(client_a, tenant_a):
    tree = _warehousing_tree(tenant_a)
    item = _warehousing_item(tenant_a, "XD-1")
    draft = _warehousing_order(tenant_a, item, tree["dock"])
    received = _warehousing_order(tenant_a, item, tree["dock"], status="received")
    hit = client_a.get(reverse("inventory:crossdockorder_list") + "?status=draft")
    assert hit.status_code == 200
    assert {row.pk for row in hit.context["object_list"]} == {draft.pk}
    hit_r = client_a.get(reverse("inventory:crossdockorder_list") + "?status=received")
    assert {row.pk for row in hit_r.context["object_list"]} == {received.pk}


def test_warehousing_crossdockorder_list_dock_filter_narrows(client_a, tenant_a):
    tree = _warehousing_tree(tenant_a)
    item = _warehousing_item(tenant_a, "XD-1")
    other_dock = _warehousing_location(tenant_a, f"{tenant_a.slug[:4].upper()}-DOCK2",
                                       location_type="staging", parent=tree["warehouse"])
    order_here = _warehousing_order(tenant_a, item, tree["dock"])
    order_there = _warehousing_order(tenant_a, item, other_dock)
    hit = client_a.get(reverse("inventory:crossdockorder_list") + f"?dock={other_dock.pk}")
    assert hit.status_code == 200
    shown = {row.pk for row in hit.context["object_list"]}
    assert shown == {order_there.pk}
    assert order_here.pk not in shown


def test_warehousing_crossdockorder_junk_get_params_degrade_not_500(client_a):
    base = reverse("inventory:crossdockorder_list")
    junk = "?status=bogus&dock=abc&page=99&q=zzz"
    assert client_a.get(base + junk).status_code == 200


# -- CrossDock create ---------------------------------------------------------------------------

def test_warehousing_crossdockorder_create_get_and_valid_post_assigns_number(
        client_a, tenant_a):
    tree = _warehousing_tree(tenant_a)
    item = _warehousing_item(tenant_a, "XD-NEW")
    url = reverse("inventory:crossdockorder_create")
    form_page = client_a.get(url)
    assert form_page.status_code == 200
    for field in ("item", "dock_location", "quantity", "scheduled_date"):
        assert f'name="{field}"'.encode() in form_page.content

    response = client_a.post(url, data={
        "item": item.pk, "lot_serial": "", "dock_location": tree["dock"].pk,
        "quantity": "12.5", "unit_cost": "3.25", "scheduled_date": "2026-08-28",
        "inbound_reference": "GRN-77", "outbound_reference": "SO-31", "notes": "",
    })
    assert response.status_code == 302
    assert response.url == reverse("inventory:crossdockorder_list")
    created = CrossDockOrder.objects.get(tenant=tenant_a, inbound_reference="GRN-77")
    assert created.number.startswith("XD-")
    assert created.status == "draft"
    assert created.quantity == Decimal("12.5")


def test_warehousing_crossdockorder_create_invalid_rerenders_with_errors(client_a, tenant_a):
    tree = _warehousing_tree(tenant_a)
    response = client_a.post(reverse("inventory:crossdockorder_create"), data={
        "item": "", "lot_serial": "", "dock_location": tree["dock"].pk,
        "quantity": "0", "unit_cost": "", "scheduled_date": "",
        "inbound_reference": "", "outbound_reference": "", "notes": "",
    })
    assert response.status_code == 200
    form = response.context["form"]
    assert "item" in form.errors         # missing item
    assert "quantity" in form.errors     # quantity 0 < the 0.0001 minimum
    assert not CrossDockOrder.objects.filter(tenant=tenant_a).exists()


# -- CrossDock detail / edit --------------------------------------------------------------------

def test_warehousing_crossdockorder_detail_renders_number_badge_and_moves_header(
        client_a, tenant_a):
    tree = _warehousing_tree(tenant_a)
    item = _warehousing_item(tenant_a, "XD-DET")
    order = _warehousing_order(tenant_a, item, tree["dock"])
    content = client_a.get(reverse("inventory:crossdockorder_detail", args=[order.pk])).content
    assert order.number.encode() in content
    assert b">Draft<" in content                 # status badge text
    assert b"Ledger Moves" in content            # ledger-moves table header


def test_warehousing_crossdockorder_edit_on_draft_prefills_and_persists(client_a, tenant_a):
    tree = _warehousing_tree(tenant_a)
    item = _warehousing_item(tenant_a, "XD-EDIT")
    order = _warehousing_order(tenant_a, item, tree["dock"], quantity="10")
    edit_url = reverse("inventory:crossdockorder_edit", args=[order.pk])
    page = client_a.get(edit_url)
    assert page.status_code == 200
    assert page.context["form"].initial["quantity"] == Decimal("10")

    response = client_a.post(edit_url, data={
        "item": item.pk, "lot_serial": "", "dock_location": tree["dock"].pk,
        "quantity": "42", "unit_cost": "3.25", "scheduled_date": "2026-08-28",
        "inbound_reference": "", "outbound_reference": "", "notes": "",
    })
    assert response.status_code == 302
    order.refresh_from_db()
    assert order.quantity == Decimal("42")
    assert order.status == "draft"               # editing never moves status


# -- CrossDock lifecycle regressions -------------------------------------------------------------

class TestWarehousingCrossDockLifecycle:
    """The POST-only verbs and their server-side guards — these pin recent fixes."""

    def _order(self, tenant_a, sku="XD-LIFE"):
        tree = _warehousing_tree(tenant_a)
        item = _warehousing_item(tenant_a, sku)
        return tree, _warehousing_order(tenant_a, item, tree["dock"], quantity="10")

    def test_receive_on_draft_posts_one_receipt_leg(self, client_a, tenant_a):
        from apps.scm.models import StockMove

        tree, order = self._order(tenant_a)
        response = client_a.post(reverse("inventory:crossdockorder_receive",
                                         args=[order.pk]))
        assert response.status_code == 302
        assert response.url == reverse("inventory:crossdockorder_detail", args=[order.pk])
        order.refresh_from_db()
        assert order.status == "received"
        legs = StockMove.objects.filter(tenant=tenant_a, reference=order.number)
        assert legs.count() == 1
        leg = legs.get()
        assert leg.move_type == "receipt"
        assert leg.quantity == Decimal("10")
        assert leg.location_id == tree["dock"].pk

    def test_ship_posts_outbound_leg_netting_zero(self, client_a, admin_user, tenant_a):
        from apps.scm.models import StockMove

        _tree, order = self._order(tenant_a)
        order.receive(admin_user)
        response = client_a.post(reverse("inventory:crossdockorder_ship", args=[order.pk]))
        assert response.status_code == 302
        order.refresh_from_db()
        assert order.status == "shipped"
        legs = StockMove.objects.filter(tenant=tenant_a, reference=order.number)
        assert legs.count() == 2
        assert set(legs.values_list("move_type", flat=True)) == {"receipt", "issue"}
        assert legs.aggregate(net=Sum("quantity"))["net"] == Decimal("0")

    def test_edit_on_received_is_refused_with_fields_unchanged(
            self, client_a, admin_user, tenant_a):
        """Guard I1: a crafted POST must not rewrite quantity/item beneath posted legs."""
        tree, order = self._order(tenant_a)
        order.receive(admin_user)
        before_item = order.item_id
        response = client_a.post(reverse("inventory:crossdockorder_edit",
                                         args=[order.pk]), data={
            "item": order.item_id, "lot_serial": "",
            "dock_location": tree["dock"].pk, "quantity": "999", "unit_cost": "3.25",
            "scheduled_date": "2026-08-28", "inbound_reference": "",
            "outbound_reference": "", "notes": "",
        })
        assert response.status_code == 302
        assert response.url == reverse("inventory:crossdockorder_detail", args=[order.pk])
        followed = client_a.get(response.url)
        assert b"can no longer be edited" in followed.content   # flash, not a silent no-op
        order.refresh_from_db()
        assert order.quantity == Decimal("10")                  # UNCHANGED
        assert order.item_id == before_item

    def test_delete_on_received_is_refused_row_survives(
            self, client_a, admin_user, tenant_a):
        """Guard I2: a received order's number is written into immutable ledger legs."""
        _tree, order = self._order(tenant_a)
        order.receive(admin_user)
        response = client_a.post(reverse("inventory:crossdockorder_delete", args=[order.pk]))
        assert response.status_code == 302
        assert CrossDockOrder.objects.filter(pk=order.pk).exists()   # STILL EXISTS
        followed = client_a.get(response.url)
        assert b"cannot be deleted" in followed.content

    def test_delete_on_draft_removes_row(self, client_a, tenant_a):
        _tree, order = self._order(tenant_a)
        response = client_a.post(reverse("inventory:crossdockorder_delete", args=[order.pk]))
        assert response.status_code == 302
        assert response.url == reverse("inventory:crossdockorder_list")
        assert not CrossDockOrder.objects.filter(pk=order.pk).exists()

    def test_cancel_on_shipped_is_refused_status_unchanged(
            self, client_a, admin_user, tenant_a):
        from apps.scm.models import StockMove

        _tree, order = self._order(tenant_a)
        order.receive(admin_user)
        order.ship(admin_user)
        moves_before = StockMove.objects.filter(reference=order.number).count()
        response = client_a.post(reverse("inventory:crossdockorder_cancel", args=[order.pk]))
        assert response.status_code == 302
        order.refresh_from_db()
        assert order.status == "shipped"                     # refused, unchanged
        assert StockMove.objects.filter(reference=order.number).count() == moves_before
        followed = client_a.get(response.url)
        assert b"cannot be cancelled" in followed.content

    def test_action_verbs_refuse_get(self, client_a, tenant_a):
        _tree, order = self._order(tenant_a)
        for verb in ("receive", "ship", "cancel"):
            url = reverse(f"inventory:crossdockorder_{verb}", args=[order.pk])
            assert client_a.get(url).status_code == 405


# -- Warehouse Map -------------------------------------------------------------------------------

def test_warehousing_warehousemap_renders_warehouse_section_and_bin(client_a, tenant_a):
    tree = _warehousing_tree(tenant_a)
    item = _warehousing_item(tenant_a, "MAP-1")
    _warehousing_move(tenant_a, item, tree["bin_a"], "20")
    _warehousing_profile(tenant_a, tree["bin_a"], max_quantity=Decimal("100"))
    response = client_a.get(reverse("inventory:warehousemap"))
    assert response.status_code == 200
    assert b"Warehouse Map" in response.content
    # one section per warehouse head, its bins indented beneath it
    assert tree["warehouse"].code.encode() in response.content
    assert tree["bin_a"].code.encode() in response.content


def test_warehousing_warehousemap_superuser_sees_empty_state_not_foreign_data(
        db, tenant_a):
    tree = _warehousing_tree(tenant_a)      # acme data EXISTS on this database
    root = _warehousing_root_client(db)
    response = root.get(reverse("inventory:warehousemap"))
    assert response.status_code == 200
    assert b"No locations yet" in response.content          # the honest empty state
    assert tree["bin_a"].code.encode() not in response.content
    assert tree["warehouse"].code.encode() not in response.content


# -- Pagination includes -------------------------------------------------------------------------

def test_warehousing_bincapacity_list_pagination_renders(client_a, tenant_a):
    suffix = tenant_a.slug[:4].upper()
    for i in range(16):                      # per_page is 15
        loc = _warehousing_location(tenant_a, f"{suffix}-P{i:02d}", location_type="bin")
        _warehousing_profile(tenant_a, loc, max_quantity=Decimal("10"))
    page_one = client_a.get(reverse("inventory:bincapacity_list"))
    assert page_one.status_code == 200
    assert len(page_one.context["object_list"]) == 15
    assert b'class="pagination"' in page_one.content
    page_two = client_a.get(reverse("inventory:bincapacity_list") + "?page=2")
    assert page_two.status_code == 200
    assert len(page_two.context["object_list"]) == 1


def test_warehousing_crossdockorder_list_pagination_renders(client_a, tenant_a):
    tree = _warehousing_tree(tenant_a)
    item = _warehousing_item(tenant_a, "XD-BULK")
    for i in range(16):                      # per_page is 15
        _warehousing_order(tenant_a, item, tree["dock"],
                           inbound_reference=f"BULK-{i:02d}")
    page_one = client_a.get(reverse("inventory:crossdockorder_list"))
    assert page_one.status_code == 200
    assert len(page_one.context["object_list"]) == 15
    assert b'class="pagination"' in page_one.content
    page_two = client_a.get(reverse("inventory:crossdockorder_list") + "?page=2")
    assert page_two.status_code == 200
    assert len(page_two.context["object_list"]) == 1
