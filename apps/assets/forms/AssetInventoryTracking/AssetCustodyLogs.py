from django import forms
from django.contrib.auth import get_user_model

from apps.assets.forms._common import TenantUniqueMixin, reject_foreign
from apps.assets.models.AssetInventoryTracking.AssetCustodyLogs import AssetCustodyLog
from apps.core.models import Party
from apps.scm.models import Asset

User = get_user_model()


class AssetCustodyLogForm(TenantUniqueMixin, forms.ModelForm):
    class Meta:
        model = AssetCustodyLog
        fields = [
            "asset",
            "action_type",
            "borrower",
            "borrower_name",
            "crib_attendant",
            "purpose",
            "work_order_reference",
            "project_reference",
            "checkout_date",
            "expected_return_date",
            "checkout_condition",
            "condition_notes",
            "borrower_signature_acknowledged",
            "notes",
        ]
        exclude = [
            "tenant",
            "number",
            "status",
            "created_at",
            "updated_at",
            "actual_return_date",
            "return_condition",
        ]
        widgets = {
            "asset": forms.Select(attrs={"class": "form-select"}),
            "action_type": forms.Select(attrs={"class": "form-select"}),
            "borrower": forms.Select(attrs={"class": "form-select"}),
            "borrower_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "Individual name or badge ID"}),
            "crib_attendant": forms.Select(attrs={"class": "form-select"}),
            "purpose": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Line 2 Emergency Pump Overhaul"}),
            "work_order_reference": forms.TextInput(attrs={"class": "form-input", "placeholder": "MWO-00104 / Task #5"}),
            "project_reference": forms.TextInput(attrs={"class": "form-input", "placeholder": "CAPEX-2026-01"}),
            "checkout_date": forms.DateTimeInput(attrs={"class": "form-input", "type": "datetime-local"}),
            "expected_return_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "checkout_condition": forms.Select(attrs={"class": "form-select"}),
            "condition_notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Pre-loan tool condition, accessories included, case intact..."}),
            "borrower_signature_acknowledged": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Special handling, safety certifications required..."}),
        }

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)

        if self.tenant:
            self.fields["asset"].queryset = Asset.objects.filter(tenant=self.tenant).order_by("number")
            self.fields["borrower"].queryset = Party.objects.filter(tenant=self.tenant).order_by("name")
            self.fields["crib_attendant"].queryset = User.objects.filter(tenant=self.tenant, is_active=True).order_by("username")

    def clean(self):
        cleaned_data = super().clean()
        if self.tenant:
            reject_foreign(self, cleaned_data, ["asset", "borrower", "crib_attendant"])

        return cleaned_data
