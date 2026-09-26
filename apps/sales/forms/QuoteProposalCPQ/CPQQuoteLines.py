"""Form definitions for CPQQuoteLine model."""
from django import forms
from apps.sales.forms._common import TenantModelForm
from apps.sales.models.QuoteProposalCPQ.CPQQuoteLines import CPQQuoteLine
from apps.crm.models import Product
from apps.scm.models.InventoryManagement.Items import Item, UOM
from apps.accounting.models import TaxCode


class CPQQuoteLineForm(TenantModelForm):
    """Form to add and edit quote line items."""

    class Meta:
        model = CPQQuoteLine
        fields = [
            "parent_line",
            "line_type",
            "product",
            "item",
            "uom",
            "description",
            "quantity",
            "list_price",
            "discount_pct",
            "unit_price",
            "tax_code",
            "tax_pct",
            "unit_cost",
            "is_optional",
            "is_selected",
            "sequence",
        ]
        widgets = {
            "parent_line": forms.Select(attrs={"class": "form-select"}),
            "line_type": forms.Select(attrs={"class": "form-select"}),
            "product": forms.Select(attrs={"class": "form-select"}),
            "item": forms.Select(attrs={"class": "form-select"}),
            "uom": forms.Select(attrs={"class": "form-select"}),
            "description": forms.TextInput(attrs={"class": "form-input", "placeholder": "Item description..."}),
            "quantity": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0.01"}),
            "list_price": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "discount_pct": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0", "max": "100"}),
            "unit_price": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "tax_code": forms.Select(attrs={"class": "form-select"}),
            "tax_pct": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0", "max": "100"}),
            "unit_cost": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "is_optional": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "is_selected": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "sequence": forms.NumberInput(attrs={"class": "form-input", "min": "1"}),
        }

    def __init__(self, *args, quote=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.quote = quote or (self.instance.quote if self.instance.pk else None)
        if self.tenant:
            if self.quote:
                self.fields["parent_line"].queryset = CPQQuoteLine.objects.filter(
                    tenant=self.tenant, quote=self.quote, parent_line__isnull=True
                )
                if self.instance.pk:
                    self.fields["parent_line"].queryset = self.fields["parent_line"].queryset.exclude(pk=self.instance.pk)
            else:
                self.fields["parent_line"].queryset = CPQQuoteLine.objects.none()

            self.fields["product"].queryset = Product.objects.filter(tenant=self.tenant, is_active=True)
            self.fields["item"].queryset = Item.objects.filter(tenant=self.tenant, is_active=True)
            self.fields["uom"].queryset = UOM.objects.filter(tenant=self.tenant, is_active=True)
            self.fields["tax_code"].queryset = TaxCode.objects.filter(tenant=self.tenant, is_active=True)
