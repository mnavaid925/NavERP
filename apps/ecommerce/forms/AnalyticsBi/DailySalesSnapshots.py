from django import forms

from apps.ecommerce.forms._common import TenantModelForm
from apps.ecommerce.models.AnalyticsBi.DailySalesSnapshots import DailySalesSnapshot


class DailySalesSnapshotForm(TenantModelForm):
    class Meta:
        model = DailySalesSnapshot
        fields = [
            "snapshot_date",
            "currency",
            "gross_sales",
            "discounts_total",
            "refunds_total",
            "net_sales",
            "shipping_collected",
            "taxes_collected",
            "cost_of_goods_sold",
            "gross_profit",
            "orders_count",
            "units_sold",
            "average_order_value",
            "carts_created",
            "carts_abandoned",
            "conversion_rate_pct",
            "is_finalized",
            "notes",
        ]
        widgets = {
            "snapshot_date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "currency": forms.TextInput(attrs={"class": "form-input", "maxlength": 3}),
            "gross_sales": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "discounts_total": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "refunds_total": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "net_sales": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "shipping_collected": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "taxes_collected": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "cost_of_goods_sold": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "gross_profit": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "orders_count": forms.NumberInput(attrs={"class": "form-input"}),
            "units_sold": forms.NumberInput(attrs={"class": "form-input"}),
            "average_order_value": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "carts_created": forms.NumberInput(attrs={"class": "form-input"}),
            "carts_abandoned": forms.NumberInput(attrs={"class": "form-input"}),
            "conversion_rate_pct": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "is_finalized": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "notes": forms.TextInput(attrs={"class": "form-input"}),
        }
