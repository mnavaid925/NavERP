"""SCM 4.3 Inventory Management — ItemCategory / UOM / Item forms."""
from apps.scm.forms._common import *  # noqa: F401,F403
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


class UOMForm(TenantModelForm):
    class Meta:
        model = UOM
        fields = ["code", "name", "factor", "is_active"]


class ItemForm(TenantModelForm):
    class Meta:
        model = Item
        # `average_cost` EXCLUDED — it's a derived cached figure maintained by the posting service.
        fields = ["sku", "name", "category", "uom", "item_type", "tracking", "costing_method",
                  "standard_cost", "reorder_point", "description", "is_active"]
