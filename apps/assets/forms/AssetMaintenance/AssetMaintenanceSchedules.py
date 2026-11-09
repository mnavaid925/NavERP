from django import forms
from django.apps import apps
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.accounting.models import FixedAsset
from apps.assets.forms._common import TenantUniqueMixin, reject_foreign
from apps.assets.models.AssetClassification.AssetCategories import AssetCategory
from apps.assets.models.AssetMaintenance.AssetMaintenanceSchedules import AssetMaintenanceSchedule
from apps.core.models import Party
from apps.scm.models import Asset

User = get_user_model()


class AssetMaintenanceScheduleForm(TenantUniqueMixin, forms.ModelForm):
    class Meta:
        model = AssetMaintenanceSchedule
        fields = [
            "name",
            "fixed_asset",
            "operational_asset",
            "asset_category",
            "schedule_type",
            "frequency_interval",
            "frequency_unit",
            "meter_trigger_threshold",
            "lead_time_days",
            "assigned_technician",
            "preferred_vendor",
            "service_contract",
            "service_checklist",
            "is_mandatory",
            "is_active",
            "notes",
        ]
        exclude = [
            "tenant",
            "number",
            "status",
            "last_service_date",
            "last_service_meter",
            "next_due_date",
            "next_due_meter",
            "created_at",
            "updated_at",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Monthly Hydraulic System Inspection"}),
            "fixed_asset": forms.Select(attrs={"class": "form-select"}),
            "operational_asset": forms.Select(attrs={"class": "form-select"}),
            "asset_category": forms.Select(attrs={"class": "form-select"}),
            "schedule_type": forms.Select(attrs={"class": "form-select"}),
            "frequency_interval": forms.NumberInput(attrs={"class": "form-input", "min": "1"}),
            "frequency_unit": forms.Select(attrs={"class": "form-select"}),
            "meter_trigger_threshold": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "placeholder": "e.g. 250.00 hours"}),
            "lead_time_days": forms.NumberInput(attrs={"class": "form-input", "min": "0"}),
            "assigned_technician": forms.Select(attrs={"class": "form-select"}),
            "preferred_vendor": forms.Select(attrs={"class": "form-select"}),
            "service_contract": forms.Select(attrs={"class": "form-select"}),
            "service_checklist": forms.Textarea(attrs={"class": "form-textarea", "rows": 4, "placeholder": "Enter checklist steps, one per line:\n- Check oil pressure\n- Inspect hydraulic hose for leaks\n- Clean intake filter"}),
            "is_mandatory": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Additional operational guidelines..."}),
        }

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)
        tenant = self.tenant or getattr(self.instance, "tenant", None)
        if tenant:
            self.fields["fixed_asset"].queryset = FixedAsset.objects.filter(tenant=tenant)
            self.fields["operational_asset"].queryset = Asset.objects.filter(tenant=tenant)
            self.fields["asset_category"].queryset = AssetCategory.objects.filter(tenant=tenant)
            self.fields["assigned_technician"].queryset = User.objects.filter(tenant=tenant)
            self.fields["preferred_vendor"].queryset = Party.objects.filter(tenant=tenant)
            try:
                ServiceContractModel = apps.get_model("assets", "AssetServiceContract")
                if ServiceContractModel:
                    self.fields["service_contract"].queryset = ServiceContractModel.objects.filter(tenant=tenant)
            except LookupError:
                pass

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["fixed_asset", "operational_asset", "asset_category", "preferred_vendor", "service_contract"])
        assigned_tech = cleaned.get("assigned_technician")
        tenant = self.tenant or getattr(self.instance, "tenant", None)
        if assigned_tech and tenant and getattr(assigned_tech, "tenant_id", None) != tenant.pk:
            self.add_error("assigned_technician", "Assigned technician belongs to another workspace.")
        return cleaned


class AssetMaintenanceScheduleCompletionForm(forms.Form):
    completion_date = forms.DateField(
        initial=timezone.now,
        widget=forms.DateInput(attrs={"class": "form-input", "type": "date"}),
    )
    completion_meter = forms.DecimalField(
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "placeholder": "Current asset meter reading..."}),
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Service completion remarks..."}),
    )
