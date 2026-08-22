"""Inventory 5.6 Inventory Tracking & Control — form boundary.

Two soft-claim forms over the append-only ``scm.StockMove`` ledger:

* ``StockStatusForm`` — a classification claim. The CEILING rule lives in the form's
  ``clean()`` (per the SalesOrderAllocation split: model.clean() doesn't aggregate the
  ledger): Σ claims at one spot may never exceed what the ledger says is there, with
  the row's own pk excluded so edits stay honest.
* ``InventoryReservationForm`` — an ATP lock. Available = ledger on-hand − other ACTIVE
  claims (this module's reservations AND 4.5's SalesOrderAllocations) − non-sellable
  classifications, with the conservative lot union keeping unlotted whole-pool claims in
  scope when a lot is named.

The security boundary is the vendor-log trio again: tenant-scoped dropdowns refusing
foreign pks at choice-validation, ``_reject_foreign`` beneath them as belt-and-braces —
field errors, never exceptions — and workspace identity never being a form field.
"""
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.inventory.forms import InventoryReservationForm, StockStatusForm
from apps.inventory.models import InventoryReservation, StockStatus

pytestmark = pytest.mark.django_db


# ------------------------------------------------------------------ helpers


def _tracking_seed_stock(tenant, item, location, quantity=Decimal("10"), lot=None):
    """One receipt into the append-only ledger — on-hand is always DERIVED from these."""
    from apps.scm.models import StockMove
    return StockMove.objects.create(
        tenant=tenant, item=item, location=location, lot_serial=lot,
        quantity=Decimal(quantity), unit_cost=Decimal("0"),
        move_type="receipt", moved_at=timezone.now())


def _tracking_lot(tenant, item, number="LOT-TRK"):
    from apps.scm.models import LotSerial
    return LotSerial.objects.create(tenant=tenant, item=item, number=number)


def _tracking_item(tenant, sku, item_type="stock"):
    from apps.scm.models import Item
    return Item.objects.create(tenant=tenant, sku=sku, name=f"{sku} master",
                               item_type=item_type)


def _tracking_status_data(item, location, **overrides):
    # Values are STRINGS, as a real QueryDict POST would carry them — the forms read
    # self.data back with .strip()/isdecimal().
    data = {
        "item": str(item.pk), "location": str(location.pk), "lot_serial": "",
        "status": "damaged", "quantity": "3", "reason": "fork puncture",
        "effective_at": "2026-08-21T09:00",
    }
    data.update(overrides)
    return data


def _tracking_reservation_data(item, location, **overrides):
    data = {
        "item": str(item.pk), "location": str(location.pk), "lot_serial": "",
        "purpose": "sales_order", "reference": "SO-00031",
        "quantity": "5", "notes": "",
    }
    data.update(overrides)
    return data


# ------------------------------------------------------------------ fixtures


@pytest.fixture
def trk_loc_a(db, tenant_a):
    """A stock spot on the SCM spine, tenant_a."""
    from apps.scm.models import Location
    return Location.objects.create(tenant=tenant_a, code="TRK-BIN-A", name="Tracking bin A")


@pytest.fixture
def trk_loc_b(db, tenant_b):
    """Same code as trk_loc_a but in ANOTHER workspace — the foreign FK target."""
    from apps.scm.models import Location
    return Location.objects.create(tenant=tenant_b, code="TRK-BIN-B", name="Globex tracking bin")


@pytest.fixture
def service_item_a(db, tenant_a):
    """A service SKU — nothing physical, so no reservation may ever name it."""
    return _tracking_item(tenant_a, "SVC-TRK-1", item_type="service")


# ------------------------------------------------------------------ StockStatusForm


class TestTrackingStockStatusForm:
    def test_tracking_stock_status_valid_create_stamps_tenant_and_saves(
            self, tenant_a, item_a, trk_loc_a):
        """instance.tenant is stamped during __init__ BEFORE validation, so the model's
        clean() sees a workspace instead of falsely rejecting every create as cross-tenant."""
        _tracking_seed_stock(tenant_a, item_a, trk_loc_a)
        form = StockStatusForm(data=_tracking_status_data(item_a, trk_loc_a), tenant=tenant_a)
        assert form.is_valid(), form.errors          # model clean ran without raising
        assert form.instance.tenant_id == tenant_a.pk
        obj = form.save()
        assert obj.tenant_id == tenant_a.pk
        assert StockStatus.objects.filter(pk=obj.pk).exists()

    def test_tracking_stock_status_ceiling_blocks_claim_past_on_hand(
            self, tenant_a, item_a, trk_loc_a):
        """With 10 on hand and 8 already classified at the spot, a third claim of 3 would
        promise 11 units out of 10 — refused with the on-hand figure named."""
        _tracking_seed_stock(tenant_a, item_a, trk_loc_a, quantity=Decimal("10"))
        StockStatus.objects.create(
            tenant=tenant_a, item=item_a, location=trk_loc_a,
            status="on_hold", quantity=Decimal("8"))
        form = StockStatusForm(
            data=_tracking_status_data(item_a, trk_loc_a, quantity="3"), tenant=tenant_a)
        assert not form.is_valid()
        assert "quantity" in form.errors
        assert "Only 10 unit(s)" in form.errors["quantity"][0]
        assert "cannot classify 3" in form.errors["quantity"][0]

    def test_tracking_stock_status_edit_excludes_own_row_from_ceiling(
            self, tenant_a, item_a, trk_loc_a):
        """Editing the 8-unit claim judges the new quantity against an empty 'already' —
        its own row is excluded — so growing into the free headroom passes while any
        overshoot still refuses."""
        _tracking_seed_stock(tenant_a, item_a, trk_loc_a, quantity=Decimal("10"))
        existing = StockStatus.objects.create(
            tenant=tenant_a, item=item_a, location=trk_loc_a,
            status="damaged", quantity=Decimal("8"))
        grown = StockStatusForm(
            data=_tracking_status_data(item_a, trk_loc_a, quantity="9"),
            instance=existing, tenant=tenant_a)
        assert grown.is_valid(), grown.errors       # 0 (self excluded) + 9 ≤ 10
        too_far = StockStatusForm(
            data=_tracking_status_data(item_a, trk_loc_a, quantity="11"),
            instance=existing, tenant=tenant_a)
        assert not too_far.is_valid()
        assert "quantity" in too_far.errors
        assert "Only 10 unit(s)" in too_far.errors["quantity"][0]

    def test_tracking_stock_status_rejects_lot_of_another_item(
            self, tenant_a, item_a, service_item_a, trk_loc_a):
        """Lots are item-specific: naming a lot that belongs to a different SKU is an
        error ON lot_serial — the scoped <select> narrows it away and clean() re-checks
        the pairing beneath, so either layer lands the rejection on the field."""
        _tracking_seed_stock(tenant_a, item_a, trk_loc_a)
        wrong_item_lot = _tracking_lot(tenant_a, service_item_a, number="LOT-SVC")
        form = StockStatusForm(
            data=_tracking_status_data(item_a, trk_loc_a, lot_serial=str(wrong_item_lot.pk)),
            tenant=tenant_a)
        assert not form.is_valid()
        assert "lot_serial" in form.errors
        assert StockStatus.objects.count() == 0

    def test_tracking_stock_status_rejects_foreign_item(
            self, tenant_a, tenant_b, item_b, trk_loc_a):
        """A crafted POST naming another workspace's item is a FIELD error, not a 500."""
        form = StockStatusForm(
            data=_tracking_status_data(item_b, trk_loc_a), tenant=tenant_a)
        assert not form.is_valid()
        assert form.errors["item"]
        assert StockStatus.objects.count() == 0

    def test_tracking_stock_status_rejects_foreign_location(
            self, tenant_a, tenant_b, item_a, trk_loc_b):
        form = StockStatusForm(
            data=_tracking_status_data(item_a, trk_loc_b), tenant=tenant_a)
        assert not form.is_valid()
        assert form.errors["location"]
        assert StockStatus.objects.count() == 0

    def test_tracking_stock_status_rejects_foreign_lot(
            self, tenant_a, tenant_b, item_a, item_b, trk_loc_a):
        _tracking_seed_stock(tenant_a, item_a, trk_loc_a)
        foreign_lot = _tracking_lot(tenant_b, item_b, number="LOT-GLO")
        form = StockStatusForm(
            data=_tracking_status_data(item_a, trk_loc_a, lot_serial=str(foreign_lot.pk)),
            tenant=tenant_a)
        assert not form.is_valid()
        assert form.errors["lot_serial"]
        assert StockStatus.objects.count() == 0


# ------------------------------------------------------------------ InventoryReservationForm


class TestTrackingInventoryReservationForm:
    def test_tracking_reservation_reserved_by_is_not_a_form_field(
            self, tenant_a, item_a, trk_loc_a):
        """``reserved_by`` stays off the form (the view stamps request.user); ``status``
        and ``number`` move only through actions/save — none can be mass-assigned."""
        _tracking_seed_stock(tenant_a, item_a, trk_loc_a)
        form = InventoryReservationForm(
            data=_tracking_reservation_data(item_a, trk_loc_a, quantity="2"),
            tenant=tenant_a)
        assert form.is_valid(), form.errors
        assert "reserved_by" not in form.fields
        assert "status" not in form.fields
        assert "number" not in form.fields
        obj = form.save()
        assert obj.reserved_by_id is None
        assert obj.status == "reserved"
        assert obj.number.startswith("RSV")

    def test_tracking_reservation_atp_allows_exactly_on_hand(
            self, tenant_a, item_a, trk_loc_a):
        """No claims anywhere: the whole on-hand is reservable and one unit more is not."""
        _tracking_seed_stock(tenant_a, item_a, trk_loc_a, quantity=Decimal("10"))
        full = InventoryReservationForm(
            data=_tracking_reservation_data(item_a, trk_loc_a, quantity="10"),
            tenant=tenant_a)
        assert full.is_valid(), full.errors
        over = InventoryReservationForm(
            data=_tracking_reservation_data(item_a, trk_loc_a, quantity="11"),
            tenant=tenant_a)
        assert not over.is_valid()
        assert "quantity" in over.errors
        assert "Only 10 of 10" in over.errors["quantity"][0]

    def test_tracking_reservation_active_claim_drops_availability_self_excluded_on_edit(
            self, tenant_a, item_a, trk_loc_a):
        """An ACTIVE reservation of 4 leaves 6; a fresh claim of 7 refuses while 6 passes.
        Editing the holding ROW itself excludes its own quantity, so raising it to 7 is
        judged against the full pool — and 11 still refuses."""
        _tracking_seed_stock(tenant_a, item_a, trk_loc_a, quantity=Decimal("10"))
        held = InventoryReservation.objects.create(
            tenant=tenant_a, item=item_a, location=trk_loc_a,
            purpose="sales_order", quantity=Decimal("4"))

        seven = InventoryReservationForm(
            data=_tracking_reservation_data(item_a, trk_loc_a, quantity="7"),
            tenant=tenant_a)
        assert not seven.is_valid()
        assert "Only 6 of 10" in seven.errors["quantity"][0]
        six = InventoryReservationForm(
            data=_tracking_reservation_data(item_a, trk_loc_a, quantity="6"),
            tenant=tenant_a)
        assert six.is_valid(), six.errors

        edited = InventoryReservationForm(
            data=_tracking_reservation_data(item_a, trk_loc_a, quantity="7"),
            instance=held, tenant=tenant_a)
        assert edited.is_valid(), edited.errors    # own 4 not counted twice
        runaway = InventoryReservationForm(
            data=_tracking_reservation_data(item_a, trk_loc_a, quantity="11"),
            instance=held, tenant=tenant_a)
        assert not runaway.is_valid()

    def test_tracking_reservation_cancelled_and_consumed_claims_free_availability(
            self, tenant_a, item_a, trk_loc_a):
        """Only reserved/released hold stock back — cancelled and consumed rows are
            history, so the full on-hand is reservable again."""
        _tracking_seed_stock(tenant_a, item_a, trk_loc_a, quantity=Decimal("10"))
        InventoryReservation.objects.create(
            tenant=tenant_a, item=item_a, location=trk_loc_a,
            purpose="sales_order", quantity=Decimal("10"), status="cancelled")
        InventoryReservation.objects.create(
            tenant=tenant_a, item=item_a, location=trk_loc_a,
            purpose="job", quantity=Decimal("10"), status="consumed")
        form = InventoryReservationForm(
            data=_tracking_reservation_data(item_a, trk_loc_a, quantity="10"),
            tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_tracking_reservation_non_sellable_classification_reduces_atp(
            self, tenant_a, item_a, trk_loc_a):
        """Damaged stock stops promising itself: a 3-unit damaged classification turns
        10 on hand into 7 reservable."""
        _tracking_seed_stock(tenant_a, item_a, trk_loc_a, quantity=Decimal("10"))
        StockStatus.objects.create(
            tenant=tenant_a, item=item_a, location=trk_loc_a,
            status="damaged", quantity=Decimal("3"))
        seven = InventoryReservationForm(
            data=_tracking_reservation_data(item_a, trk_loc_a, quantity="7"),
            tenant=tenant_a)
        assert seven.is_valid(), seven.errors
        eight = InventoryReservationForm(
            data=_tracking_reservation_data(item_a, trk_loc_a, quantity="8"),
            tenant=tenant_a)
        assert not eight.is_valid()
        assert "Only 7 of 10" in eight.errors["quantity"][0]

    def test_tracking_reservation_spine_allocation_competes_for_atp(
            self, tenant_a, item_a, trk_loc_a):
        """4.5's SalesOrderAllocation is the OTHER claimant on the same pool — a
        released-or-reserved spine claim of 2 docks availability even though it posted
        no move of its own."""
        from apps.core.models import Party
        from apps.scm.models import SalesOrder, SalesOrderAllocation, SalesOrderLine
        _tracking_seed_stock(tenant_a, item_a, trk_loc_a, quantity=Decimal("10"))
        customer = Party.objects.create(
            tenant=tenant_a, name="Acme Retail Co", kind="organization")
        order = SalesOrder.objects.create(tenant=tenant_a, customer=customer)
        line = SalesOrderLine.objects.create(
            sales_order=order, item=item_a, quantity_ordered=Decimal("5"))
        SalesOrderAllocation.objects.create(
            tenant=tenant_a, sales_order_line=line, location=trk_loc_a,
            quantity=Decimal("2"), status="reserved")

        eight = InventoryReservationForm(
            data=_tracking_reservation_data(item_a, trk_loc_a, quantity="8"),
            tenant=tenant_a)
        assert eight.is_valid(), eight.errors
        nine = InventoryReservationForm(
            data=_tracking_reservation_data(item_a, trk_loc_a, quantity="9"),
            tenant=tenant_a)
        assert not nine.is_valid()
        assert "Only 8 of 10" in nine.errors["quantity"][0]

    def test_tracking_reservation_item_queryset_excludes_service_items(
            self, tenant_a, tenant_b, item_a, item_b, service_item_a):
        """Only things that physically sit somewhere can be locked: the dropdown offers
        stock/consumable SKUs of THIS workspace — services and foreign items stay out."""
        consumable = _tracking_item(tenant_a, "CON-TRK-1", item_type="consumable")
        qs = InventoryReservationForm(tenant=tenant_a).fields["item"].queryset
        assert item_a in qs
        assert consumable in qs
        assert service_item_a not in qs
        assert item_b not in qs

    def test_tracking_reservation_lot_named_atp_counts_unlotted_claims(
            self, tenant_a, item_a, trk_loc_a):
        """Conservative union: an UNLOTTED active claim competes for every unit at the
        spot — its units may legally be consumed by any lot — so a lot-named reservation
        is judged against it instead of quietly over-promising lot L's five."""
        lot = _tracking_lot(tenant_a, item_a, number="LOT-T1")
        _tracking_seed_stock(tenant_a, item_a, trk_loc_a, quantity=Decimal("5"), lot=lot)
        InventoryReservation.objects.create(
            tenant=tenant_a, item=item_a, location=trk_loc_a,
            purpose="job", quantity=Decimal("4"))          # unlotted whole-pool claim

        two_against_lot = InventoryReservationForm(
            data=_tracking_reservation_data(
                item_a, trk_loc_a, lot_serial=str(lot.pk), quantity="2"),
            tenant=tenant_a)
        assert not two_against_lot.is_valid()
        assert "quantity" in two_against_lot.errors
        assert "Only 1 of 5" in two_against_lot.errors["quantity"][0]

        one_against_lot = InventoryReservationForm(
            data=_tracking_reservation_data(
                item_a, trk_loc_a, lot_serial=str(lot.pk), quantity="1"),
            tenant=tenant_a)
        assert one_against_lot.is_valid(), one_against_lot.errors
