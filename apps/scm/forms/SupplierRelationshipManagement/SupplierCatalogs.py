"""SCM 4.2 SRM — SupplierCatalog form + item formset."""
from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.forms._common import _active_currencies, _supplier_parties
from apps.scm.models import SupplierCatalog, SupplierCatalogItem


class SupplierCatalogForm(TenantModelForm):
    class Meta:
        model = SupplierCatalog
        # `status`/`number` EXCLUDED.
        fields = ["party", "name", "currency", "valid_from", "valid_until", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _active_currencies(self)
        if "party" in self.fields:
            self.fields["party"].queryset = _supplier_parties(self.tenant)

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("valid_from"), cleaned.get("valid_until")
        if start and end and end < start:
            self.add_error("valid_until", "Valid-until cannot be before valid-from.")
        return cleaned


class SupplierCatalogItemForm(TenantModelForm):
    class Meta:
        model = SupplierCatalogItem
        fields = ["item_name", "sku", "uom", "unit_price", "lead_time_days", "min_order_qty", "is_active"]


SupplierCatalogItemFormSet = inlineformset_factory(
    SupplierCatalog, SupplierCatalogItem, form=SupplierCatalogItemForm, extra=3, can_delete=True,
)
