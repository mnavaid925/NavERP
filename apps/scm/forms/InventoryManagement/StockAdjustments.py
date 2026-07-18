"""SCM 4.3 Inventory Management — StockAdjustment form + line formset."""
from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.models import StockAdjustment, StockAdjustmentLine


class StockAdjustmentForm(TenantModelForm):
    class Meta:
        model = StockAdjustment
        # `status` EXCLUDED — advances via the post/cancel actions.
        fields = ["location", "reason", "adjustment_date", "notes"]

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("reason") == "other" and not (cleaned.get("notes") or "").strip():
            self.add_error("notes", "Give a note explaining an 'Other' adjustment.")
        return cleaned


class StockAdjustmentLineForm(TenantModelForm):
    class Meta:
        model = StockAdjustmentLine
        fields = ["item", "lot_serial", "quantity_delta", "unit_cost"]

    def clean(self):
        cleaned = super().clean()
        item, lot = cleaned.get("item"), cleaned.get("lot_serial")
        # A zero delta is a no-op row — reject it so a blank line isn't posted as a StockMove.
        if item and not cleaned.get("quantity_delta"):
            self.add_error("quantity_delta", "Enter a non-zero adjustment quantity.")
        # A lot belonging to a different item would corrupt both items' lot history (code review).
        if item and lot and lot.item_id != item.pk:
            self.add_error("lot_serial", f"{lot.number} belongs to {lot.item.sku}, not {item.sku}.")
        return cleaned


StockAdjustmentLineFormSet = inlineformset_factory(
    StockAdjustment, StockAdjustmentLine, form=StockAdjustmentLineForm, extra=3, can_delete=True,
)
