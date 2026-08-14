"""SCM 4.3 Inventory Management — ItemCategory / UOM / Item forms."""
from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.forms._common import TenantUniqueMixin
from apps.scm.models import Item, ItemCategory, UOM


class ItemCategoryForm(TenantModelForm):
    class Meta:
        model = ItemCategory
        fields = ["name", "parent", "description", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Don't let a category be its own parent (a self-cycle). parent is tenant-scoped by the base.
        if self.instance.pk and "parent" in self.fields:
            self.fields["parent"].queryset = self.fields["parent"].queryset.exclude(pk=self.instance.pk)


class UOMForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = UOM
        fields = ["code", "name", "factor", "is_active"]


class ItemForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = Item
        # `average_cost` EXCLUDED — it's a derived cached figure maintained by the posting service.
        # `is_spare_part` is 4.13's MRO marker and is the SOLE selector for the spare-parts
        # storeroom page (`views/AssetManagement/Reports.py` `sparepart_list`). Without it on this
        # whitelist no tenant user could ever flag a part, so that page would be permanently empty
        # outside `seed_scm` and the Django admin — a live feature reachable only by staff.
        # `storage_condition` is 4.15's temperature class and is here for exactly that reason: it is
        # the SOLE selector for the Cold Storage Inventory report (`scm:cold_storage_report`), whose
        # own empty state tells the admin to "set the class on your items" and links back to this
        # page. Off the whitelist that instruction is unfollowable and four of the report's five
        # sections stay permanently empty.
        # `owner_client` is 4.17's client-attribution column and it sits on this whitelist for the
        # same reason `is_spare_part` and `storage_condition` do: it is the SOLE selector for the
        # Client Inventory Segregation report (`scm:client_inventory_report`) and for every client
        # stock figure in 4.17, whose empty state tells the admin to "assign an owner to your items"
        # and links back to this page. Off the whitelist that instruction is unfollowable, every
        # client's on-hand is permanently zero, and every billing run that measures stock bills
        # nothing — the column could only ever be set by `seed_scm` and the Django admin.
        # `weight_kg` / `volume_cbm` are 4.18's landed-cost bases and they join this whitelist for
        # precisely the reason the three flags above did: `LandedCostVoucher.allocate()` spreads
        # freight by weight and insurance by volume, and both bases FALL BACK to quantity when the
        # received items carry neither. Off the whitelist no tenant user could ever populate them,
        # so allocate-by-weight and allocate-by-volume would be reachable only through `seed_scm`
        # and the Django admin — a live feature that silently degrades to the fallback for every
        # real workspace, with a plausible number to show for it.
        fields = ["sku", "name", "category", "uom", "item_type", "tracking", "costing_method",
                  "standard_cost", "reorder_point", "weight_kg", "volume_cbm", "is_spare_part",
                  "storage_condition", "owner_client", "description", "is_active"]
