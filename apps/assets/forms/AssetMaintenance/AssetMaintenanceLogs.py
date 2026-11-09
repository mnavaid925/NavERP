from django import forms
from django.contrib.auth import get_user_model

from apps.accounting.models import FixedAsset, GLAccount
from apps.assets.forms._common import TenantUniqueMixin, reject_foreign
from apps.assets.models.AssetMaintenance.AssetMaintenanceLogs import AssetMaintenanceLog
from apps.assets.models.AssetMaintenance.AssetMaintenanceRequests import AssetMaintenanceRequest
from apps.assets.models.AssetMaintenance.AssetMaintenanceSchedules import AssetMaintenanceSchedule
from apps.assets.models.AssetMaintenance.AssetServiceContracts import AssetServiceContract
from apps.core.models import Party
from apps.scm.models import Asset, MaintenanceWorkOrder

User = get_user_model()


class AssetMaintenanceLogForm(TenantUniqueMixin, forms.ModelForm):
    class Meta:
        model = AssetMaintenanceLog
        fields = [
            "fixed_asset",
            "operational_asset",
            "maintenance_request",
            "maintenance_schedule",
            "service_contract",
            "work_order",
            "service_date",
            "completion_date",
            "maintenance_type",
            "failure_code",
            "downtime_hours",
            "meter_reading",
            "lead_technician",
            "service_vendor",
            "labor_hours",
            "labor_cost",
            "parts_consumed_summary",
            "parts_cost",
            "vendor_invoice_cost",
            "expense_account",
            "root_cause_analysis",
            "action_taken",
        ]
        exclude = [
            "tenant",
            "number",
            "status",
            "total_cost",
            "approved_by",
            "approved_at",
            "created_at",
            "updated_at",
        ]
        widgets = {
            "fixed_asset": forms.Select(attrs={"class": "form-select"}),
            "operational_asset": forms.Select(attrs={"class": "form-select"}),
            "maintenance_request": forms.Select(attrs={"class": "form-select"}),
            "maintenance_schedule": forms.Select(attrs={"class": "form-select"}),
            "service_contract": forms.Select(attrs={"class": "form-select"}),
            "work_order": forms.Select(attrs={"class": "form-select"}),
            "service_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "completion_date": forms.DateTimeInput(attrs={"class": "form-input", "type": "datetime-local"}),
            "maintenance_type": forms.Select(attrs={"class": "form-select"}),
            "failure_code": forms.Select(attrs={"class": "form-select"}),
            "downtime_hours": forms.NumberInput(attrs={"class": "form-input", "step": "0.1", "min": "0"}),
            "meter_reading": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "placeholder": "Current runtime meter"}),
            "lead_technician": forms.Select(attrs={"class": "form-select"}),
            "service_vendor": forms.Select(attrs={"class": "form-select"}),
            "labor_hours": forms.NumberInput(attrs={"class": "form-input", "step": "0.1", "min": "0"}),
            "labor_cost": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "parts_consumed_summary": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Itemize parts and quantities used (e.g. 2x O-Ring #OR-22, 1x V-Belt #VB-40)..."}),
            "parts_cost": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "vendor_invoice_cost": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "expense_account": forms.Select(attrs={"class": "form-select"}),
            "root_cause_analysis": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Underlying root cause, wear pattern, or operating anomaly..."}),
            "action_taken": forms.Textarea(attrs={"class": "form-textarea", "rows": 4, "placeholder": "Narrative of repair actions, torque checks, replacements, and operational test run..."}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tenant = getattr(self, "tenant", None) or getattr(self.instance, "tenant", None)
        if tenant:
            self.fields["fixed_asset"].queryset = FixedAsset.objects.filter(tenant=tenant)
            self.fields["operational_asset"].queryset = Asset.objects.filter(tenant=tenant)
            self.fields["maintenance_request"].queryset = AssetMaintenanceRequest.objects.filter(tenant=tenant)
            self.fields["maintenance_schedule"].queryset = AssetMaintenanceSchedule.objects.filter(tenant=tenant)
            self.fields["service_contract"].queryset = AssetServiceContract.objects.filter(tenant=tenant)
            self.fields["work_order"].queryset = MaintenanceWorkOrder.objects.filter(tenant=tenant)
            self.fields["lead_technician"].queryset = User.objects.filter(tenant=tenant)
            self.fields["service_vendor"].queryset = Party.objects.filter(tenant=tenant)
            self.fields["expense_account"].queryset = GLAccount.objects.filter(tenant=tenant)

    def clean(self):
        cleaned = super().clean()
        reject_foreign(
            self,
            cleaned,
            [
                "fixed_asset",
                "operational_asset",
                "maintenance_request",
                "maintenance_schedule",
                "service_contract",
                "work_order",
                "service_vendor",
                "expense_account",
            ],
        )
        return cleaned
