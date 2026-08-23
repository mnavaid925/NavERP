"""Inventory 5.5 Warehousing & Bin Management — form boundary.

The security boundary is the vendor-log trio again, over SCM 4.3's spine: tenant-scoped
dropdowns refusing a foreign pk at choice-validation, ``_reject_foreign`` beneath them
(so a narrowed ``<select>`` stays UX, never the authorization boundary), and workspace
identity never being a form field.

* ``BinCapacityForm`` — one bin's three-dimensional envelope. At least ONE limit must be
  declared (blank means unlimited, so all-three-blank declares nothing), and
  ``(tenant, location)`` uniqueness validates AT the form boundary via
  ``TenantUniqueMixin`` instead of dying as an IntegrityError on ``save()``.
* ``CrossDockOrderForm`` — the bypass-storage document. ``number`` is minted only in
  ``save()``; ``status`` and the received/shipped stamps move solely through the
  receive/ship/cancel actions, so none is a form field. Items narrow to what physically
  flows (stock/consumable), docks to this workspace's ACTIVE locations, and lots to the
  posted item's own lots — with clean() re-checking the item↔lot pairing beneath.
"""
from decimal import Decimal

import pytest

from apps.inventory.forms import BinCapacityForm, CrossDockOrderForm
from apps.inventory.models import BinCapacity, CrossDockOrder
from apps.scm.models import Item, Location, LotSerial

pytestmark = pytest.mark.django_db


# ------------------------------------------------------------------ helpers


def _warehousing_item(tenant, sku, item_type="stock"):
    """A stock-type SCM item master with a cost basis (pass item_type='service'/'consumable')."""
    return Item.objects.create(
        tenant=tenant, sku=sku, name=f"Warehouse {sku}",
        item_type=item_type, standard_cost=Decimal("8.00"),
    )


def _warehousing_location(tenant, code, location_type="bin", **fields):
    """A location on the SCM spine (bin by default; pass 'staging' for docks)."""
    return Location.objects.create(
        tenant=tenant, code=code, name=f"Area {code}",
        location_type=location_type, **fields,
    )


def _warehousing_lot(tenant, item, number):
    """A lot/batch row for a tracked item."""
    return LotSerial.objects.create(tenant=tenant, item=item, kind="lot", number=number)


def _warehousing_capacity_data(location, **overrides):
    # Values are STRINGS, as a real QueryDict POST would carry them.
    data = {
        "location": str(location.pk),
        "max_weight_kg": "",
        "max_volume_m3": "",
        "max_quantity": "",
        "notes": "",
    }
    data.update(overrides)
    return data


def _warehousing_xd_data(item, dock, **overrides):
    data = {
        "item": str(item.pk),
        "lot_serial": "",
        "dock_location": str(dock.pk),
        "quantity": "10",
        "unit_cost": "2.50",
        "scheduled_date": "2026-08-25",
        "inbound_reference": "GRN-00012",
        "outbound_reference": "SHP-00004",
        "notes": "",
    }
    data.update(overrides)
    return data


# ------------------------------------------------------------------ fixtures


@pytest.fixture
def wh_bin_a(db, tenant_a):
    """A storage bin of tenant_a."""
    return _warehousing_location(tenant_a, "XD-BIN-A")


@pytest.fixture
def wh_bin_b(db, tenant_b):
    """Globex's bin — the foreign-workspace target for guard tests."""
    return _warehousing_location(tenant_b, "XD-BIN-B")


@pytest.fixture
def wh_dock_a(db, tenant_a):
    """An active staging dock of tenant_a."""
    return _warehousing_location(tenant_a, "XD-DOCK-A", location_type="staging")


@pytest.fixture
def wh_dock_b(db, tenant_b):
    """Globex's active staging dock — the foreign dock FK target."""
    return _warehousing_location(tenant_b, "XD-DOCK-B", location_type="staging")


# ------------------------------------------------------------------ BinCapacityForm


class TestWarehousingBinCapacityForm:
    def test_warehousing_capacity_all_limits_blank_and_notes_only_rejected(
            self, tenant_a, wh_bin_a):
        """A profile with no limit at all is not a declaration, it is an empty row —
        refused with an error that says to set AT LEAST ONE limit, notes notwithstanding."""
        for overrides in ({}, {"notes": "just words, no numbers"}):
            form = BinCapacityForm(
                data=_warehousing_capacity_data(wh_bin_a, **overrides), tenant=tenant_a)
            assert not form.is_valid()
            assert "at least one" in " ".join(form.non_field_errors())

    @pytest.mark.parametrize("slug,limits", [
        ("w", {"max_weight_kg": "500.00"}),
        ("v", {"max_volume_m3": "2.500"}),
        ("q", {"max_quantity": "250"}),
        ("all", {"max_weight_kg": "1.00", "max_volume_m3": "2.00", "max_quantity": "3"}),
    ], ids=["weight-only", "volume-only", "quantity-only", "all-three"])
    def test_warehousing_capacity_accepts_each_limit_alone_or_together(
            self, tenant_a, slug, limits):
        """Any single dimension alone is a valid envelope, and all three together too;
        whatever was given persists, untouched dimensions stay unlimited (None)."""
        loc = _warehousing_location(tenant_a, f"XD-CAP-{slug.upper()}")
        form = BinCapacityForm(
            data=_warehousing_capacity_data(loc, **limits), tenant=tenant_a)
        assert form.is_valid(), form.errors
        obj = form.save()
        assert obj.tenant_id == tenant_a.pk
        assert (obj.max_weight_kg or Decimal("0")) == Decimal(limits.get("max_weight_kg") or "0")
        assert (obj.max_volume_m3 or Decimal("0")) == Decimal(limits.get("max_volume_m3") or "0")
        assert (obj.max_quantity or Decimal("0")) == Decimal(limits.get("max_quantity") or "0")

    def test_warehousing_capacity_rejects_foreign_tenant_location(
            self, tenant_a, wh_bin_b):
        """A crafted POST naming ANOTHER WORKSPACE'S bin is a FIELD error on location,
        never a 500: the scoped dropdown refuses it at choice-validation and
        _reject_foreign/model clean stand beneath it — either message is a rejection."""
        before = BinCapacity.objects.count()
        form = BinCapacityForm(
            data=_warehousing_capacity_data(wh_bin_b, max_quantity="100"), tenant=tenant_a)
        assert not form.is_valid()
        joined = " ".join(form.errors["location"]).lower()
        assert "workspace" in joined or "choice" in joined
        assert BinCapacity.objects.count() == before

    def test_warehousing_capacity_duplicate_profile_surfaces_unique_together_as_form_error(
            self, tenant_a, wh_bin_a):
        """(tenant, location) admits exactly one envelope: TenantUniqueMixin pulls tenant
        back INTO validate_unique, so a second profile for the same bin renders as a form
        error instead of passing is_valid() and 500ing on save()."""
        BinCapacity.objects.create(tenant=tenant_a, location=wh_bin_a, max_quantity="10")
        before = BinCapacity.objects.count()
        form = BinCapacityForm(
            data=_warehousing_capacity_data(wh_bin_a, max_quantity="99"), tenant=tenant_a)
        assert not form.is_valid()
        assert "__all__" in form.errors  # unique_together reports on non-field errors
        assert BinCapacity.objects.count() == before


# ------------------------------------------------------------------ CrossDockOrderForm


class TestWarehousingCrossDockOrderForm:
    def test_warehousing_xd_meta_fields_exclude_lifecycle_columns(self):
        """Exactly nine fields: status moves through receive/ship/cancel, received_at/
        shipped_at are stamped by those actions, number is minted in save() — none can be
        mass-assigned through a crafted POST."""
        assert set(CrossDockOrderForm._meta.fields) == {
            "item", "lot_serial", "dock_location", "quantity", "unit_cost",
            "scheduled_date", "inbound_reference", "outbound_reference", "notes"}
        for name in ("status", "number", "received_at", "shipped_at"):
            assert name not in CrossDockOrderForm._meta.fields
            assert name not in CrossDockOrderForm.base_fields

    def test_warehousing_xd_item_dropdown_physical_flow_only_tenant_scoped(
            self, tenant_a, tenant_b, item_a, item_b):
        """Only what physically flows may cross-dock: stock and consumable SKUs of THIS
        workspace — services have nothing to put on a trailer, foreign items stay out."""
        service = _warehousing_item(tenant_a, "XD-SVC", item_type="service")
        consumable = _warehousing_item(tenant_a, "XD-CON", item_type="consumable")
        qs = CrossDockOrderForm(tenant=tenant_a).fields["item"].queryset
        assert item_a in qs        # stock type
        assert consumable in qs    # consumable flows too
        assert service not in qs
        assert item_b not in qs    # another workspace

    def test_warehousing_xd_dock_dropdown_active_locations_of_the_tenant_only(
            self, tenant_a, tenant_b, wh_dock_a, wh_dock_b):
        inactive = _warehousing_location(
            tenant_a, "XD-DOCK-OFF", location_type="staging", is_active=False)
        qs = CrossDockOrderForm(tenant=tenant_a).fields["dock_location"].queryset
        assert wh_dock_a in qs
        assert inactive not in qs
        assert wh_dock_b not in qs  # another workspace

    def test_warehousing_xd_lot_queryset_unbound_empty_without_tenant_narrowed_by_instance(
            self, tenant_a, wh_dock_a, item_a):
        """Unbound: a tenant-less render offers NO lots at all, while editing narrows the
        <select> to the order's own item's lots — UX, never the boundary."""
        assert not CrossDockOrderForm(tenant=None).fields["lot_serial"].queryset.exists()

        other_item = _warehousing_item(tenant_a, "XD-LOTB")
        draft = CrossDockOrder(item=item_a, dock_location=wh_dock_a)  # unsaved edit target
        lot_qs = CrossDockOrderForm(instance=draft, tenant=tenant_a).fields["lot_serial"].queryset
        assert _warehousing_lot(tenant_a, item_a, "L-A1") in lot_qs
        assert _warehousing_lot(tenant_a, other_item, "L-B1") not in lot_qs

    def test_warehousing_xd_lot_queryset_bound_narrows_to_posted_items_lots(
            self, tenant_a, wh_dock_a, item_a):
        """Once item A is posted, the lot choices are A's lots only — item B's lots vanish
        from the <select> entirely."""
        other_item = _warehousing_item(tenant_a, "XD-PAIR-B")
        lot_a = _warehousing_lot(tenant_a, item_a, "L-A2")
        lot_b = _warehousing_lot(tenant_a, other_item, "L-B2")
        form = CrossDockOrderForm(
            data=_warehousing_xd_data(item_a, wh_dock_a, lot_serial=str(lot_a.pk)),
            tenant=tenant_a)
        choices = form.fields["lot_serial"].queryset
        assert lot_a in choices
        assert lot_b not in choices
        assert form.is_valid(), form.errors

    def test_warehousing_xd_pairing_with_other_items_lot_refused_on_lot_serial(
            self, tenant_a, wh_dock_a, item_a):
        """Posting item A with another SKU's lot id is refused ON lot_serial — the narrowed
        <select> hides B's lots at choice-validation and clean()'s pairing re-check beneath
        adds its own 'different item' error; either layer lands the rejection on the field."""
        other_item = _warehousing_item(tenant_a, "XD-LOTB")
        wrong_lot = _warehousing_lot(tenant_a, other_item, "L-WRONG")
        form = CrossDockOrderForm(
            data=_warehousing_xd_data(item_a, wh_dock_a, lot_serial=str(wrong_lot.pk)),
            tenant=tenant_a)
        assert not form.is_valid()
        assert "lot_serial" in form.errors
        assert CrossDockOrder.objects.count() == 0

    def test_warehousing_xd_crafted_post_foreign_item_is_field_error(
            self, tenant_a, item_b, wh_dock_a):
        form = CrossDockOrderForm(
            data=_warehousing_xd_data(item_b, wh_dock_a), tenant=tenant_a)
        assert not form.is_valid()
        assert form.errors["item"]
        assert CrossDockOrder.objects.count() == 0

    def test_warehousing_xd_crafted_post_foreign_dock_is_field_error(
            self, tenant_a, item_a, wh_dock_b):
        form = CrossDockOrderForm(
            data=_warehousing_xd_data(item_a, wh_dock_b), tenant=tenant_a)
        assert not form.is_valid()
        assert form.errors["dock_location"]
        assert CrossDockOrder.objects.count() == 0

    def test_warehousing_xd_crafted_post_foreign_lot_is_field_error(
            self, tenant_a, tenant_b, item_a, item_b, wh_dock_a):
        foreign_lot = _warehousing_lot(tenant_b, item_b, "L-GLO")
        form = CrossDockOrderForm(
            data=_warehousing_xd_data(item_a, wh_dock_a, lot_serial=str(foreign_lot.pk)),
            tenant=tenant_a)
        assert not form.is_valid()
        assert form.errors["lot_serial"]
        assert CrossDockOrder.objects.count() == 0

    def test_warehousing_xd_valid_save_mints_number_crud_create_pattern(
            self, tenant_a, item_a, wh_dock_a):
        """The crud_create flow: Form(data, tenant=t) → is_valid → save(commit=False) →
        stamp tenant → save(). The XD- number exists only after save() mints it."""
        form = CrossDockOrderForm(
            data=_warehousing_xd_data(item_a, wh_dock_a, quantity="6"), tenant=tenant_a)
        assert form.is_valid(), form.errors
        obj = form.save(commit=False)
        obj.tenant = tenant_a
        assert not obj.number            # empty until save()
        obj.save()
        assert obj.number.startswith("XD-")
        assert obj.status == "draft"     # lifecycle starts outside the form
        assert CrossDockOrder.objects.filter(pk=obj.pk, tenant_id=tenant_a.pk).exists()
