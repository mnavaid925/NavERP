from django import forms
from django.contrib.auth import get_user_model

from apps.accounting.models import FixedAsset
from apps.assets.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.assets.models.AssetMaintenance.AssetMaintenanceRequests import AssetMaintenanceRequest
from apps.assets.models.MobileAssetManagement.FieldWorkOrders import FieldWorkOrder
from apps.scm.models import Asset

User = get_user_model()


class FieldWorkOrderForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = FieldWorkOrder
        fields = [
            "title",
            "work_order_type",
            "priority",
            "status",
            "asset",
            "fixed_asset",
            "assigned_technician",
            "maintenance_request",
            "scheduled_start",
            "scheduled_end",
            "labor_wrench_minutes",
            "safety_lockout_confirmed",
            "parts_requisition_notes",
            "estimated_parts_cost",
            "work_performed_notes",
            "signature_name",
            "signature_designation",
            "dispatch_latitude",
            "dispatch_longitude",
            "completion_latitude",
            "completion_longitude",
            "client_sync_id",
            "is_offline_captured",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Field Hydraulic Cylinder Replacement & Line Bleed"}),
            "work_order_type": forms.Select(attrs={"class": "form-select"}),
            "priority": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "asset": forms.Select(attrs={"class": "form-select"}),
            "fixed_asset": forms.Select(attrs={"class": "form-select"}),
            "assigned_technician": forms.Select(attrs={"class": "form-select"}),
            "maintenance_request": forms.Select(attrs={"class": "form-select"}),
            "scheduled_start": forms.DateTimeInput(attrs={"class": "form-input", "type": "datetime-local"}),
            "scheduled_end": forms.DateTimeInput(attrs={"class": "form-input", "type": "datetime-local"}),
            "labor_wrench_minutes": forms.NumberInput(attrs={"class": "form-input", "min": "0", "placeholder": "Minutes"}),
            "safety_lockout_confirmed": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "parts_requisition_notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Itemized replacement parts, part numbers, fluids..."}),
            "estimated_parts_cost": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "placeholder": "0.00"}),
            "work_performed_notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 4, "placeholder": "Technician diagnosis, repair actions taken, and verification tests..."}),
            "signature_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "Signee full name"}),
            "signature_designation": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Plant Supervisor / Site Manager"}),
            "dispatch_latitude": forms.NumberInput(attrs={"class": "form-input", "step": "0.000001", "placeholder": "Dispatch Lat"}),
            "dispatch_longitude": forms.NumberInput(attrs={"class": "form-input", "step": "0.000001", "placeholder": "Dispatch Long"}),
            "completion_latitude": forms.NumberInput(attrs={"class": "form-input", "step": "0.000001", "placeholder": "Completion Lat"}),
            "completion_longitude": forms.NumberInput(attrs={"class": "form-input", "step": "0.000001", "placeholder": "Completion Long"}),
            "client_sync_id": forms.TextInput(attrs={"class": "form-input", "placeholder": "Client UUID"}),
            "is_offline_captured": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, "tenant") and self.tenant is not None:
            self.fields["asset"].queryset = Asset.objects.filter(tenant=self.tenant)
            self.fields["fixed_asset"].queryset = FixedAsset.objects.filter(tenant=self.tenant)
            self.fields["assigned_technician"].queryset = User.objects.filter(tenant=self.tenant)
            self.fields["maintenance_request"].queryset = AssetMaintenanceRequest.objects.filter(tenant=self.tenant)
        self.fields["fixed_asset"].required = False
        self.fields["maintenance_request"].required = False
        self.fields["scheduled_end"].required = False
        self.fields["parts_requisition_notes"].required = False
        self.fields["work_performed_notes"].required = False
        self.fields["signature_name"].required = False
        self.fields["signature_designation"].required = False
        self.fields["dispatch_latitude"].required = False
        self.fields["dispatch_longitude"].required = False
        self.fields["completion_latitude"].required = False
        self.fields["completion_longitude"].required = False
        self.fields["client_sync_id"].required = False

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["asset", "fixed_asset", "maintenance_request"])
        return cleaned_data
