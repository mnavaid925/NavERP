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
        fields = ["sku", "name", "category", "uom", "item_type", "tracking", "costing_method",
                  "standard_cost", "reorder_point", "is_spare_part", "description", "is_active"]
