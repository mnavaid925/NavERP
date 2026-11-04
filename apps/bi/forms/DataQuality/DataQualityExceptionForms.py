from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q

from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.DataQuality.DataQualityExceptions import DataQualityException
from apps.bi.models.DataQuality.DataQualityProfiles import DataQualityProfile
from apps.bi.models.DataQuality.DataQualityRules import DataQualityRule
from apps.bi.models.DataWarehouse.WarehouseTables import WarehouseTable
from apps.bi.models.SemanticLayer.SemanticModels import SemanticModel
from apps.core.forms import TenantModelForm


class DataQualityExceptionForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = DataQualityException
        fields = [
            "rule",
            "profile",
            "warehouse_table",
            "semantic_model",
            "record_identifier",
            "target_column",
            "invalid_value",
            "expected_condition",
            "exception_type",
            "severity",
            "status",
            "remediation_action",
            "proposed_value",
            "remediated_value",
            "assigned_steward",
            "resolution_notes",
            "is_active",
        ]
        widgets = {
            "rule": forms.Select(attrs={"class": "form-select"}),
            "profile": forms.Select(attrs={"class": "form-select"}),
            "warehouse_table": forms.Select(attrs={"class": "form-select"}),
            "semantic_model": forms.Select(attrs={"class": "form-select"}),
            "record_identifier": forms.TextInput(attrs={"class": "form-input font-mono text-sm", "placeholder": "e.g. CUST-00941 or ID 108"}),
            "target_column": forms.TextInput(attrs={"class": "form-input font-mono text-sm", "placeholder": "e.g. email or total_amount"}),
            "invalid_value": forms.Textarea(attrs={"class": "form-textarea font-mono text-xs", "rows": 2, "placeholder": "Offending value captured"}),
            "expected_condition": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Valid RFC 5322 email address"}),
            "exception_type": forms.Select(attrs={"class": "form-select"}),
            "severity": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "remediation_action": forms.Select(attrs={"class": "form-select"}),
            "proposed_value": forms.Textarea(attrs={"class": "form-textarea font-mono text-xs", "rows": 2, "placeholder": "Suggested corrected value"}),
            "remediated_value": forms.Textarea(attrs={"class": "form-textarea font-mono text-xs", "rows": 2, "placeholder": "Final approved value applied"}),
            "assigned_steward": forms.Select(attrs={"class": "form-select"}),
            "resolution_notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Investigation findings and remediation audit notes"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["rule"].queryset = DataQualityRule.objects.filter(tenant=self.tenant).order_by("name")
            self.fields["profile"].queryset = DataQualityProfile.objects.filter(tenant=self.tenant).order_by("name")
            self.fields["warehouse_table"].queryset = WarehouseTable.objects.filter(tenant=self.tenant).order_by("name")
            self.fields["semantic_model"].queryset = SemanticModel.objects.filter(tenant=self.tenant).order_by("name")
            user_qs = get_user_model().objects.filter(tenant=self.tenant)
            steward_filter = Q(is_active=True)
            if self.instance and self.instance.pk and self.instance.assigned_steward_id:
                steward_filter |= Q(pk=self.instance.assigned_steward_id)
            self.fields["assigned_steward"].queryset = user_qs.filter(steward_filter).order_by("first_name", "username")

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["rule", "profile", "warehouse_table", "semantic_model", "assigned_steward"])
        return cleaned


class DataQualityExceptionRemediationForm(TenantModelForm):
    class Meta:
        model = DataQualityException
        fields = [
            "status",
            "remediation_action",
            "proposed_value",
            "remediated_value",
            "assigned_steward",
            "resolution_notes",
        ]
        widgets = {
            "status": forms.Select(attrs={"class": "form-select"}),
            "remediation_action": forms.Select(attrs={"class": "form-select"}),
            "proposed_value": forms.Textarea(attrs={"class": "form-textarea font-mono text-xs", "rows": 2}),
            "remediated_value": forms.Textarea(attrs={"class": "form-textarea font-mono text-xs", "rows": 2}),
            "assigned_steward": forms.Select(attrs={"class": "form-select"}),
            "resolution_notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        if self.tenant is not None:
            user_qs = get_user_model().objects.filter(tenant=self.tenant)
            steward_filter = Q(is_active=True)
            if self.instance and self.instance.pk and self.instance.assigned_steward_id:
                steward_filter |= Q(pk=self.instance.assigned_steward_id)
            self.fields["assigned_steward"].queryset = user_qs.filter(steward_filter).order_by("first_name", "username")

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["assigned_steward"])
        return cleaned
