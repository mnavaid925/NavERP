"""Inventory 5.18 Accounting & Financial Integration — forms.

Two config entities only — the AP/AR sync and JE automation are computed pages with
POST verbs, so they have no ModelForms.
"""
from django import forms

from apps.inventory.forms._common import TenantModelForm, TenantUniqueMixin, _reject_foreign
from apps.inventory.models import GLPostRule, TaxRule


class TaxRuleForm(TenantUniqueMixin, TenantModelForm):
    """Product scope × country → TaxCode. The mixin validates (tenant, name) and stamps
    instance.tenant for clean()'s foreign-item/category checks on create."""

    class Meta:
        model = TaxRule
        fields = ["name", "item", "category", "country", "tax_code", "priority",
                  "is_active", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            from apps.scm.models import Item, ItemCategory

            self.fields["item"].queryset = Item.objects.filter(tenant=self.tenant).order_by("sku")
            self.fields["category"].queryset = (
                ItemCategory.objects.filter(tenant=self.tenant).order_by("name"))
            # TaxCode carries its own tenant FK, so the base scopes it; keep it active-only.
            self.fields["tax_code"].queryset = (
                self.fields["tax_code"].queryset.filter(is_active=True))

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["item", "category", "tax_code"])
        return cleaned


class GLPostRuleForm(TenantUniqueMixin, TenantModelForm):
    """One account pair per event type. The mixin validates the per-tenant event-type
    uniqueness that ``unique_together`` alone would let die as an IntegrityError."""

    class Meta:
        model = GLPostRule
        fields = ["event_type", "name", "inventory_account", "offset_account",
                  "is_active", "notes"]
        help_texts = {
            "offset_account": ("Adjustments: the found-stock gain / write-off account · "
                               "COGS: the COGS expense account."),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            from apps.accounting.models import GLAccount

            self.fields["inventory_account"].queryset = (
                GLAccount.objects.filter(tenant=self.tenant).order_by("code"))
            self.fields["offset_account"].queryset = (
                GLAccount.objects.filter(tenant=self.tenant).order_by("code"))

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["inventory_account", "offset_account"])
        return cleaned
