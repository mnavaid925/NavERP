"""Form definitions for ProductBundleOption model."""
from django import forms
from apps.sales.forms._common import TenantModelForm
from apps.sales.models.QuoteProposalCPQ.ProductBundles import ProductBundleOption
from apps.crm.models import Product
from apps.scm.models.InventoryManagement.Items import Item


class ProductBundleOptionForm(TenantModelForm):
    """Form to create and edit product bundle configuration options."""

    class Meta:
        model = ProductBundleOption
        fields = [
            "name",
            "bundle_product",
            "component_product",
            "component_item",
            "option_group",
            "is_required",
            "is_default",
            "min_quantity",
            "max_quantity",
            "default_quantity",
            "unit_price_override",
            "discount_pct_override",
            "compatibility_rule",
            "depends_on_product",
            "sort_order",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g., Enterprise Server Rack Component"}),
            "bundle_product": forms.Select(attrs={"class": "form-select"}),
            "component_product": forms.Select(attrs={"class": "form-select"}),
            "component_item": forms.Select(attrs={"class": "form-select"}),
            "option_group": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g., Hardware, Software, Support"}),
            "is_required": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "is_default": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "min_quantity": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "max_quantity": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "default_quantity": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "unit_price_override": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "placeholder": "Optional fixed price"}),
            "discount_pct_override": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "placeholder": "Optional discount %"}),
            "compatibility_rule": forms.Select(attrs={"class": "form-select"}),
            "depends_on_product": forms.Select(attrs={"class": "form-select"}),
            "sort_order": forms.NumberInput(attrs={"class": "form-input", "min": "1"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["bundle_product"].queryset = Product.objects.filter(tenant=self.tenant, is_active=True)
            self.fields["component_product"].queryset = Product.objects.filter(tenant=self.tenant, is_active=True)
            self.fields["depends_on_product"].queryset = Product.objects.filter(tenant=self.tenant, is_active=True)
            self.fields["component_item"].queryset = Item.objects.filter(tenant=self.tenant, is_active=True)
