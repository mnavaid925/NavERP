"""Inventory 5.6 Inventory Tracking & Control — InventoryReservation form."""
from django.db.models import Sum

from apps.inventory.forms._common import TenantUniqueMixin, TenantModelForm, _reject_foreign
from apps.inventory.models import InventoryReservation


def _stock_locations(tenant):
    """Locations a reservation can legitimately hold stock at, tenant-scoped.

    ``.none()`` for the tenant-less superuser. Any active location is offered — a
    reservation is a claim about units somewhere on the floor, not only in a pick face.
    """
    from apps.scm.models import Location
    if tenant is None:
        return Location.objects.none()
    return (Location.objects.filter(tenant=tenant, is_active=True)
            .order_by("location_type", "code"))


class InventoryReservationForm(TenantUniqueMixin, TenantModelForm):
    """One soft lock. ``number`` is auto-assigned in ``save()`` and ``status`` moves
    only through the release/consume/cancel actions, so neither is a form field."""

    class Meta:
        model = InventoryReservation
        fields = ["item", "location", "lot_serial", "purpose", "reference", "quantity",
                  "reserved_by", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["location"].queryset = _stock_locations(self.tenant)
        # Only things that physically sit somewhere can be locked — a service SKU has no
        # units to hold. (TenantModelForm has already scoped this queryset to tenant.)
        self.fields["item"].queryset = (self.fields["item"].queryset
                                        .filter(item_type__in=("stock", "consumable")))
        # Lots are item-specific; narrowed by posted item / instance, re-checked in clean().
        self.fields["lot_serial"].queryset = self._lot_queryset()

    def _lot_queryset(self):
        from apps.scm.models import LotSerial
        if self.tenant is None:
            return LotSerial.objects.none()
        qs = LotSerial.objects.filter(tenant=self.tenant).select_related("item")
        item_id = None
        if self.is_bound:
            raw = (self.data.get("item") or "").strip()
            if raw.isdecimal():
                item_id = int(raw)
        elif self.instance.item_id:
            item_id = self.instance.item_id
        if item_id:
            qs = qs.filter(item_id=item_id)
        return qs

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["item", "location", "lot_serial"])
        item = cleaned.get("item")
        location = cleaned.get("location")
        lot = cleaned.get("lot_serial") or None
        quantity = cleaned.get("quantity")
        if item and lot and lot.item_id != item.pk:
            self.add_error("lot_serial", "That lot/serial belongs to a different item.")
        # The ATP check lives HERE, per the SalesOrderAllocation split: model.clean() has
        # no business aggregating the ledger. Available at the spot = ledger on-hand minus
        # every OTHER active claim on it (4.5's allocations AND this module's reservations)
        # minus non-sellable classifications — the same formula the Real-Time Stock Levels
        # page renders; keep the two in step.
        if item and location and quantity and self.instance.tenant_id is not None:
            moves = item.stock_moves.filter(location=location)
            if lot is not None:
                moves = moves.filter(lot_serial=lot)
            on_hand = moves.aggregate(q=Sum("quantity"))["q"] or 0
            held = (
                _active_held(InventoryReservation.objects.filter(
                    tenant=self.instance.tenant, item=item, location=location,
                    status__in=InventoryReservation.ACTIVE_STATUSES), lot)
                + _active_allocations(item, location)
                + _unsellable_classified(self.instance.tenant, item, location, lot))
            available = on_hand - held
            if quantity > available:
                self.add_error(
                    "quantity",
                    f"Only {available} of {on_hand} unit(s) of {item.sku} at "
                    f"{location.code} still unclaimed — cannot reserve {quantity}.")
        return cleaned


def _active_held(reservations, lot):
    """Σ quantity over ``reservations``, narrowed to the lot when there is one."""
    qs = reservations
    if lot is not None:
        qs = qs.filter(lot_serial=lot)
    return qs.aggregate(s=Sum("quantity"))["s"] or 0


def _unsellable_classified(tenant, item, location, lot):
    """Σ non-sellable StockStatus classifications at this spot — damaged/expired/on-hold
    stock must not promise itself to a reservation any more than to an order."""
    from apps.inventory.models import StockStatus
    qs = StockStatus.objects.filter(tenant=tenant, item=item, location=location).exclude(
        status__in=StockStatus.SELLABLE_STATUSES)
    if lot is not None:
        qs = qs.filter(lot_serial=lot)
    return qs.aggregate(s=Sum("quantity"))["s"] or 0


def _active_allocations(item, location):
    """Σ quantity over 4.5's ACTIVE SalesOrderAllocations at this spot.

    Lot-blind BY DESIGN: the spine's allocations carry no lot column, so their claim is
    against the location pool as a whole — it competes with a lot-specific reservation
    just the same. Released counts too: released means a pick exists for it (the spine's
    own semantics), so those units are as spoken-for as a fresh reservation's.
    """
    from apps.scm.models import SalesOrderAllocation
    # The line carries the item FK and NO tenant of its own — scoping runs through the
    # parent order's tenant (the scm sibling convention).
    return (SalesOrderAllocation.objects.filter(
        status__in=SalesOrderAllocation.ACTIVE_STATUSES,
        sales_order_line__item_id=item.pk,
        sales_order_line__sales_order__tenant_id=item.tenant_id,
        location=location)
        .aggregate(s=Sum("quantity"))["s"] or 0)
