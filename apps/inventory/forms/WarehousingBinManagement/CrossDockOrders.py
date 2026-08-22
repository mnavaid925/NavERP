"""Inventory 5.5 Warehousing & Bin Management — CrossDockOrder form."""
from apps.inventory.forms._common import *  # noqa: F401,F403
from apps.inventory.forms._common import TenantUniqueMixin, _reject_foreign
from apps.inventory.models import CrossDockOrder


def _dock_locations(tenant):
    """Locations a cross-dock can legitimately use, dock/staging areas listed first.

    Tenant-scoped (``.none()`` for the tenant-less superuser). Any active location is
    offered, not just ``staging``: a small operation may legitimately cross-dock across
    its single receiving floor — the point of the document is that NO storage bin sits
    between the two legs.
    """
    from apps.scm.models import Location
    if tenant is None:
        return Location.objects.none()
    return (Location.objects.filter(tenant=tenant, is_active=True)
            .order_by("location_type", "code"))


class CrossDockOrderForm(TenantUniqueMixin, TenantModelForm):
    """One bypass-storage flow. ``number`` is auto-assigned in ``save()``; status and the
    received/shipped stamps move only through the receive/ship/cancel actions, so none is
    a form field."""

    class Meta:
        model = CrossDockOrder
        fields = ["item", "lot_serial", "dock_location", "quantity", "unit_cost",
                  "scheduled_date", "inbound_reference", "outbound_reference", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["dock_location"].queryset = _dock_locations(self.tenant)
        # Only things that physically flow can cross-dock — a service SKU has nothing to
        # put on a trailer. (TenantModelForm has already scoped this queryset to tenant.)
        self.fields["item"].queryset = (self.fields["item"].queryset
                                        .filter(item_type__in=("stock", "consumable")))
        # Lots are item-specific. Narrowed by the posted item on a re-render (so a
        # validation error doesn't show unrelated lots) and by the instance's item when
        # editing; clean() below still re-checks the pairing on every submit, because a
        # narrowed <select> is UX, not an authorization boundary.
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
        _reject_foreign(self, cleaned, ["item", "lot_serial", "dock_location"])
        item = cleaned.get("item")
        lot = cleaned.get("lot_serial")
        if item and lot and lot.item_id != item.pk:
            self.add_error("lot_serial", "That lot/serial belongs to a different item.")
        return cleaned
