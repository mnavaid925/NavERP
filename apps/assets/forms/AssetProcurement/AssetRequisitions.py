from decimal import Decimal

from django import forms

from apps.accounting.models import Currency
from apps.assets.forms._common import TenantUniqueMixin, reject_foreign
from apps.assets.models.AssetProcurement.AssetRequisitions import AssetRequisition
from apps.core.models import OrgUnit, Party
from apps.scm.models import Location, PurchaseOrder


class AssetRequisitionForm(TenantUniqueMixin, forms.ModelForm):
    class Meta:
        model = AssetRequisition
        exclude = [
            "tenant",
            "number",
            "status",
            "rejection_reason",
            "created_at",
            "updated_at",
            "submitted_by",
            "submitted_at",
            "approved_by",
            "approved_at",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. CNC 5-Axis Milling Machine"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Technical specifications, capacity, voltage..."}),
            "business_justification": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Explain business need, expected utilization, ROI justification..."}),
            "asset_category": forms.Select(attrs={"class": "form-select"}),
            "priority": forms.Select(attrs={"class": "form-select"}),
            "estimated_cost": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "currency": forms.Select(attrs={"class": "form-select"}),
            "budget_code": forms.TextInput(attrs={"class": "form-input", "placeholder": "CAPEX-2026-ENG-04"}),
            "proposed_vendor": forms.Select(attrs={"class": "form-select"}),
            "proposed_manufacturer": forms.TextInput(attrs={"class": "form-input", "placeholder": "Haas Automation / DMG Mori"}),
            "proposed_model": forms.TextInput(attrs={"class": "form-input", "placeholder": "VF-4SS"}),
            "required_delivery_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "target_org_unit": forms.Select(attrs={"class": "form-select"}),
            "target_location": forms.Select(attrs={"class": "form-select"}),
            "purchase_order": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)

        if self.tenant:
            self.fields["currency"].queryset = Currency.objects.filter(is_active=True)
            self.fields["proposed_vendor"].queryset = Party.objects.filter(
                tenant=self.tenant, roles__role__in=["vendor", "supplier"]
            ).distinct()
            self.fields["target_org_unit"].queryset = OrgUnit.objects.filter(tenant=self.tenant)
            self.fields["target_location"].queryset = Location.objects.filter(tenant=self.tenant, is_active=True)
            self.fields["purchase_order"].queryset = PurchaseOrder.objects.filter(tenant=self.tenant).select_related("vendor")

    def clean_estimated_cost(self):
        cost = self.cleaned_data.get("estimated_cost")
        if cost is not None and cost < Decimal("0.00"):
            raise forms.ValidationError("Estimated cost cannot be negative.")
        return cost

    def clean(self):
        cleaned_data = super().clean()
        if self.tenant:
            reject_foreign(
                self,
                cleaned_data,
                ["proposed_vendor", "target_org_unit", "target_location", "purchase_order"],
            )
        return cleaned_data
