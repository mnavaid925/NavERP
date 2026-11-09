from django import forms
from django.contrib.auth import get_user_model

from apps.accounting.models import FixedAsset
from apps.assets.forms._common import TenantUniqueMixin, reject_foreign
from apps.assets.models.AssetMaintenance.AssetMaintenanceRequests import AssetMaintenanceRequest
from apps.assets.models.AssetPerformance.AssetDowntimeLogs import AssetDowntimeLog
from apps.core.models import OrgUnit
from apps.scm.models import Asset, MaintenanceWorkOrder

User = get_user_model()


class AssetDowntimeLogForm(TenantUniqueMixin, forms.ModelForm):
    class Meta:
        model = AssetDowntimeLog
        fields = [
            "fixed_asset",
            "operational_asset",
            "maintenance_request",
            "work_order",
            "downtime_category",
            "impact_level",
            "root_cause_code",
            "failure_description",
            "started_at",
            "ended_at",
            "hourly_cost_rate",
            "is_mtbf_failure",
            "logged_by",
            "department",
            "status",
            "resolution_notes",
        ]
        exclude = [
            "tenant",
            "number",
            "duration_minutes",
            "total_downtime_cost",
            "created_at",
            "updated_at",
        ]
        widgets = {
            "fixed_asset": forms.Select(attrs={"class": "form-select"}),
            "operational_asset": forms.Select(attrs={"class": "form-select"}),
            "maintenance_request": forms.Select(attrs={"class": "form-select"}),
            "work_order": forms.Select(attrs={"class": "form-select"}),
            "downtime_category": forms.Select(attrs={"class": "form-select"}),
            "impact_level": forms.Select(attrs={"class": "form-select"}),
            "root_cause_code": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. ISO-14224 MECH-BEAR-SEIZE"}),
            "failure_description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Describe what failed and observable symptoms..."}),
            "started_at": forms.DateTimeInput(attrs={"class": "form-input", "type": "datetime-local"}),
            "ended_at": forms.DateTimeInput(attrs={"class": "form-input", "type": "datetime-local"}),
            "hourly_cost_rate": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "is_mtbf_failure": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "logged_by": forms.Select(attrs={"class": "form-select"}),
            "department": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "resolution_notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Repairs performed, parts swapped, restart check..."}),
        }

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)
        tenant = self.tenant or getattr(self.instance, "tenant", None)
        if tenant:
            self.fields["fixed_asset"].queryset = FixedAsset.objects.filter(tenant=tenant).order_by("name")
            self.fields["operational_asset"].queryset = Asset.objects.filter(tenant=tenant).order_by("name")
            self.fields["maintenance_request"].queryset = AssetMaintenanceRequest.objects.filter(tenant=tenant).order_by("-id")
            self.fields["work_order"].queryset = MaintenanceWorkOrder.objects.filter(tenant=tenant).order_by("-id")
            self.fields["department"].queryset = OrgUnit.objects.filter(tenant=tenant).order_by("name")
            self.fields["logged_by"].queryset = User.objects.filter(tenant_memberships__tenant=tenant).distinct().order_by("first_name", "last_name", "username")

    def clean(self):
        cleaned = super().clean()
        reject_foreign(
            self,
            cleaned,
            ["fixed_asset", "operational_asset", "maintenance_request", "work_order", "department"],
        )
        started = cleaned.get("started_at")
        ended = cleaned.get("ended_at")
        if started and ended and ended < started:
            self.add_error("ended_at", "Stoppage end time cannot be earlier than start time.")
        return cleaned


class AssetDowntimeLogResolveForm(forms.ModelForm):
    class Meta:
        model = AssetDowntimeLog
        fields = [
            "ended_at",
            "hourly_cost_rate",
            "resolution_notes",
        ]
        widgets = {
            "ended_at": forms.DateTimeInput(attrs={"class": "form-input", "type": "datetime-local"}),
            "hourly_cost_rate": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "resolution_notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 4, "placeholder": "Action taken to resume production..."}),
        }

    def clean(self):
        cleaned = super().clean()
        ended = cleaned.get("ended_at")
        started = getattr(self.instance, "started_at", None)
        if started and ended and ended < started:
            self.add_error("ended_at", "Resumed time cannot be earlier than stoppage start time.")
        return cleaned
