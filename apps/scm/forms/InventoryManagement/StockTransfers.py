"""SCM 4.3 Inventory Management — StockTransfer form + line formset."""
from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.models import StockTransfer, StockTransferLine


class StockTransferForm(TenantModelForm):
    class Meta:
        model = StockTransfer
        # `status` EXCLUDED — advances via the complete/cancel actions.
        fields = ["from_location", "to_location", "transfer_date", "notes"]

    def clean(self):
        cleaned = super().clean()
        src, dst = cleaned.get("from_location"), cleaned.get("to_location")
        if src and dst and src == dst:
            self.add_error("to_location", "The source and destination must be different locations.")
        return cleaned


class StockTransferLineForm(TenantModelForm):
    class Meta:
        model = StockTransferLine
        # item + lot_serial target tenant-scoped models, so the base class scopes both dropdowns.
        fields = ["item", "lot_serial", "quantity"]


StockTransferLineFormSet = inlineformset_factory(
    StockTransfer, StockTransferLine, form=StockTransferLineForm, extra=3, can_delete=True,
)
