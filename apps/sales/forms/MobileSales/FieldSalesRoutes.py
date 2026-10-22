"""Sales 8.16 — FieldSalesRoute forms."""
from django import forms

from apps.accounts.models import User
from apps.core.forms import TenantModelForm
from apps.sales.forms._common import tenant_users
from apps.sales.models.MobileSales.FieldSalesRoutes import (
    OPTIMIZATION_STATUS_CHOICES,
    ROUTE_STATUS_CHOICES,
    FieldSalesRoute,
)


class FieldSalesRouteForm(TenantModelForm):
    class Meta:
        model = FieldSalesRoute
        fields = [
            "name",
            "sales_rep",
            "route_date",
            "status",
            "start_location",
            "end_location",
            "total_stops",
            "planned_distance_km",
            "actual_distance_km",
            "estimated_duration_minutes",
            "actual_duration_minutes",
            "optimization_status",
            "notes",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Downtown Retail Corridor"}),
            "sales_rep": forms.Select(attrs={"class": "form-select"}),
            "route_date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "start_location": forms.TextInput(attrs={"class": "form-input", "placeholder": "HQ Office or Depot"}),
            "end_location": forms.TextInput(attrs={"class": "form-input", "placeholder": "Return depot or Final stop"}),
            "total_stops": forms.NumberInput(attrs={"class": "form-input", "min": 0}),
            "planned_distance_km": forms.NumberInput(attrs={"class": "form-input", "step": "0.1", "min": 0}),
            "actual_distance_km": forms.NumberInput(attrs={"class": "form-input", "step": "0.1", "min": 0}),
            "estimated_duration_minutes": forms.NumberInput(attrs={"class": "form-input", "min": 0}),
            "actual_duration_minutes": forms.NumberInput(attrs={"class": "form-input", "min": 0}),
            "optimization_status": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Dispatcher / route notes..."}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["sales_rep"].queryset = tenant_users(self.tenant)


class FieldSalesRouteFilterForm(forms.Form):
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "Search by route name, number..."}),
    )
    status = forms.ChoiceField(
        choices=[("", "All Statuses")] + list(ROUTE_STATUS_CHOICES),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    sales_rep = forms.ModelChoiceField(
        queryset=User.objects.none(),
        required=False,
        empty_label="All Sales Reps",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    route_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-input"}),
    )

    def __init__(self, *args, **kwargs):
        tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)
        if tenant is not None:
            self.fields["sales_rep"].queryset = tenant_users(tenant)
