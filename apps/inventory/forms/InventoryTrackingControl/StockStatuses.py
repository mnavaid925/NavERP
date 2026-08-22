"""Inventory 5.6 Inventory Tracking & Control — StockStatus form."""
from django.db.models import Sum

from apps.inventory.forms._common import TenantModelForm, _reject_foreign
from apps.inventory.models import StockStatus


class StockStatusForm(TenantModelForm):
    """One classification claim.

    ``TenantUniqueMixin`` is deliberately NOT mixed in: this model has no
    ``unique_together`` (several claims legitimately classify different slices of one
    spot), but the mixin's second role still matters — it stamps ``instance.tenant``
    during ``full_clean()`` on CREATE so ``StockStatus.clean()``'s foreign-workspace
    checks see a tenant before the CRUD helper assigns the real one. That stamping is
    reproduced here by hand instead of dragging in a uniqueness validation that would
    never fire.
    """

    class Meta:
        model = StockStatus
        fields = ["item", "location", "lot_serial", "status", "quantity", "reason",
                  "effective_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None and self.instance.tenant_id is None:
            self.instance.tenant = self.tenant
        # Lots are item-specific. Narrowed by the posted item on a re-render and by the
        # instance's item when editing; clean() below still re-checks the pairing on
        # every submit, because a narrowed <select> is UX, not an authorization boundary.
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
        # The ceiling check lives HERE, not in model.clean(), per the SalesOrderAllocation
        # split: a model's clean() has no business aggregating the ledger, but the form is
        # where a user-facing field error can be raised.
        #
        # Every existing claim at the same spot counts against the same ceiling — an
        # 'active' claim is as much a statement about specific units as 'damaged' is — so
        # Σ(classifications at spot) may never exceed what the ledger says is there.
        # Excluding THIS row keeps the check honest on edit.
        if item and location and quantity and self.instance.tenant_id is not None:
            moves = item.stock_moves.filter(location=location)
            if lot is not None:
                moves = moves.filter(lot_serial=lot)
            on_hand = moves.aggregate(q=Sum("quantity"))["q"] or 0
            already = (StockStatus.objects.filter(
                tenant=self.instance.tenant, item=item, location=location,
                lot_serial=lot).exclude(pk=self.instance.pk)
                .aggregate(s=Sum("quantity"))["s"] or 0)
            claimed = already + quantity
            if quantity > on_hand or claimed > on_hand:
                where = f"{location.code}" + (f" (lot {lot.number})" if lot else "")
                self.add_error(
                    "quantity",
                    f"Only {on_hand} unit(s) of {item.sku} sit at {where}; "
                    f"{already} already classified there — cannot classify {quantity}.")
        return cleaned
