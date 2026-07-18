"""SCM 4.4 Warehouse Management — PutawayTask form."""
from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.models import PutawayTask


class PutawayTaskForm(TenantModelForm):
    class Meta:
        model = PutawayTask
        # `status`/`completed_at` EXCLUDED — they advance via the start/complete/cancel actions.
        fields = ["goods_receipt", "item", "lot_serial", "from_location", "to_location",
                  "quantity", "strategy", "assigned_to", "notes"]
        # goods_receipt/item/lot_serial/from_location/to_location all target tenant-scoped models,
        # so TenantModelForm scopes every dropdown.

    def clean(self):
        cleaned = super().clean()
        src, dst = cleaned.get("from_location"), cleaned.get("to_location")
        item, lot = cleaned.get("item"), cleaned.get("lot_serial")
        if src and dst and src == dst:
            self.add_error("to_location", "Putaway source and destination must be different.")
        # A lot belonging to a different item would corrupt both items' lot history, since
        # LotSerial.on_hand() sums by lot alone.
        if item and lot and lot.item_id != item.pk:
            self.add_error("lot_serial", f"{lot.number} belongs to {lot.item.sku}, not {item.sku}.")
        return cleaned
