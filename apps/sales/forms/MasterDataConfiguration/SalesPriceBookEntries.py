"""Form for SalesPriceBookEntry model."""
import json
from django import forms
from django.core.exceptions import ValidationError

from apps.core.forms import TenantModelForm
from apps.crm.models import PriceBook, Product
from apps.sales.models.MasterDataConfiguration.SalesPriceBookEntries import SalesPriceBookEntry


class SalesPriceBookEntryForm(TenantModelForm):
    """Form to create and update price book entries."""

    volume_tier_breaks_raw = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-textarea font-mono text-sm",
                "rows": 3,
                "placeholder": '[{"min_qty": 10, "discount_pct": 5.0, "unit_price": 95.0}]',
            }
        ),
        label="Volume Tier Breaks (JSON)",
        help_text="Optional JSON list of volume tier discount breaks.",
    )

    class Meta:
        model = SalesPriceBookEntry
        fields = [
            "price_book",
            "product",
            "item",
            "sku_code",
            "currency_code",
            "list_price",
            "floor_price",
            "pricing_model",
            "min_quantity",
            "valid_from",
            "valid_to",
            "is_active",
            "notes",
        ]
        widgets = {
            "price_book": forms.Select(attrs={"class": "form-select"}),
            "product": forms.Select(attrs={"class": "form-select"}),
            "item": forms.Select(attrs={"class": "form-select"}),
            "sku_code": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. SKU-ENT-1001"}),
            "currency_code": forms.TextInput(attrs={"class": "form-input uppercase", "maxlength": "3", "placeholder": "USD"}),
            "list_price": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "floor_price": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "pricing_model": forms.Select(attrs={"class": "form-select"}),
            "min_quantity": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0.01"}),
            "valid_from": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "valid_to": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Pricing notes and terms..."}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["price_book"].queryset = PriceBook.objects.filter(tenant=self.tenant)
            self.fields["product"].queryset = Product.objects.filter(tenant=self.tenant)
            try:
                from apps.scm.models.InventoryCatalog.Items import Item
                self.fields["item"].queryset = Item.objects.filter(tenant=self.tenant)
            except Exception:
                self.fields["item"].queryset = self.fields["item"].queryset.none()

        if self.instance and self.instance.pk and self.instance.volume_tier_breaks:
            self.fields["volume_tier_breaks_raw"].initial = json.dumps(self.instance.volume_tier_breaks, indent=2)

    def clean_currency_code(self):
        curr = self.cleaned_data.get("currency_code", "").strip().upper()
        if not curr:
            return "USD"
        return curr

    def clean_volume_tier_breaks_raw(self):
        raw = self.cleaned_data.get("volume_tier_breaks_raw", "").strip()
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
            if not isinstance(parsed, list):
                raise ValidationError("Must be a JSON array of tier objects.")
            return parsed
        except json.JSONDecodeError as exc:
            raise ValidationError(f"Invalid JSON format: {exc}")

    def clean(self):
        cleaned_data = super().clean()
        tier_breaks = cleaned_data.get("volume_tier_breaks_raw")
        if tier_breaks is not None:
            self.instance.volume_tier_breaks = tier_breaks
        return cleaned_data
