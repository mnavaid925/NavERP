from django import forms
from django.contrib.auth import get_user_model

from apps.accounting.models import FixedAsset
from apps.assets.forms._common import TenantUniqueMixin, reject_foreign
from apps.assets.models.AssetMaintenance.AssetMaintenanceRequests import AssetMaintenanceRequest
from apps.core.models import OrgUnit, Party
from apps.scm.models import Asset, MaintenanceWorkOrder

User = get_user_model()


class AssetMaintenanceRequestForm(TenantUniqueMixin, forms.ModelForm):
    class Meta:
        model = AssetMaintenanceRequest
        fields = [
            "title",
            "fixed_asset",
            "operational_asset",
            "requester",
            "department",
            "request_type",
            "urgency",
            "is_breakdown",
            "downtime_started_at",
            "symptom_description",
        ]
        exclude = [
            "tenant",
            "number",
            "status",
            "triage_notes",
            "assigned_technician",
            "assigned_vendor",
            "service_contract",
            "dispatched_work_order",
            "resolution_summary",
            "resolved_at",
            "resolved_by",
            "created_at",
            "updated_at",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "Brief issue summary..."}),
            "fixed_asset": forms.Select(attrs={"class": "form-select"}),
            "operational_asset": forms.Select(attrs={"class": "form-select"}),
            "requester": forms.Select(attrs={"class": "form-select"}),
            "department": forms.Select(attrs={"class": "form-select"}),
            "request_type": forms.Select(attrs={"class": "form-select"}),
            "urgency": forms.Select(attrs={"class": "form-select"}),
            "is_breakdown": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "downtime_started_at": forms.DateTimeInput(attrs={"class": "form-input", "type": "datetime-local"}),
            "symptom_description": forms.Textarea(attrs={"class": "form-textarea", "rows": 4, "placeholder": "Detailed description of malfunction, noises, visual leaks, or error codes..."}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tenant = getattr(self, "tenant", None) or getattr(self.instance, "tenant", None)
        if tenant:
            self.fields["fixed_asset"].queryset = FixedAsset.objects.filter(tenant=tenant)
            self.fields["operational_asset"].queryset = Asset.objects.filter(tenant=tenant)
            self.fields["department"].queryset = OrgUnit.objects.filter(tenant=tenant)
            self.fields["requester"].queryset = User.objects.filter(tenant=tenant)

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["fixed_asset", "operational_asset", "department"])
        if cleaned.get("is_breakdown") and not cleaned.get("downtime_started_at"):
            # Set default downtime started if breakdown marked
            pass
        return cleaned


class AssetMaintenanceRequestTriageForm(forms.Form):
    urgency = forms.ChoiceField(
        choices=AssetMaintenanceRequest.URGENCY_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    triage_notes = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Triage notes, safety warnings, and initial inspection..."}),
        required=False,
    )


class AssetMaintenanceRequestDispatchForm(forms.Form):
    assigned_technician = forms.ModelChoiceField(
        queryset=User.objects.none(),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    assigned_vendor = forms.ModelChoiceField(
        queryset=Party.objects.none(),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    dispatched_work_order = forms.ModelChoiceField(
        queryset=MaintenanceWorkOrder.objects.none(),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, tenant, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if tenant:
            self.fields["assigned_technician"].queryset = User.objects.filter(tenant=tenant)
            self.fields["assigned_vendor"].queryset = Party.objects.filter(tenant=tenant)
            self.fields["dispatched_work_order"].queryset = MaintenanceWorkOrder.objects.filter(tenant=tenant)


class AssetMaintenanceRequestResolveForm(forms.Form):
    resolution_summary = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 4, "placeholder": "Summary of repair actions taken, parts replaced, and return-to-service test..."}),
        required=True,
    )


class AssetMaintenanceRequestRejectForm(forms.Form):
    rejection_reason = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Justification for ticket rejection (e.g. duplicate, operator error, not an asset)..."}),
        required=True,
    )
