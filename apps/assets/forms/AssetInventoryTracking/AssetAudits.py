from django import forms
from django.contrib.auth import get_user_model

from apps.assets.forms._common import TenantUniqueMixin, reject_foreign
from apps.assets.models.AssetInventoryTracking.AssetAudits import AssetAudit
from apps.core.models import OrgUnit
from apps.scm.models import Location

User = get_user_model()


class AssetAuditForm(TenantUniqueMixin, forms.ModelForm):
    class Meta:
        model = AssetAudit
        fields = [
            "title",
            "audit_type",
            "target_location",
            "target_org_unit",
            "asset_category",
            "lead_auditor",
            "supervisor",
            "scheduled_date",
            "is_blind_count",
            "expected_asset_count",
            "scanned_asset_count",
            "matched_asset_count",
            "missing_asset_count",
            "discrepancy_count",
            "discrepancy_notes",
            "notes",
        ]
        exclude = [
            "tenant",
            "number",
            "status",
            "created_at",
            "updated_at",
            "started_at",
            "completed_at",
            "reconciliation_action",
            "reconciled_by",
            "reconciled_at",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Q4 Plant Wall-to-Wall Physical Audit"}),
            "audit_type": forms.Select(attrs={"class": "form-select"}),
            "target_location": forms.Select(attrs={"class": "form-select"}),
            "target_org_unit": forms.Select(attrs={"class": "form-select"}),
            "asset_category": forms.TextInput(attrs={"class": "form-input", "placeholder": "Machinery, Tooling, IT Hardware (optional filter)"}),
            "lead_auditor": forms.Select(attrs={"class": "form-select"}),
            "supervisor": forms.Select(attrs={"class": "form-select"}),
            "scheduled_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "is_blind_count": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "expected_asset_count": forms.NumberInput(attrs={"class": "form-input", "min": "0"}),
            "scanned_asset_count": forms.NumberInput(attrs={"class": "form-input", "min": "0"}),
            "matched_asset_count": forms.NumberInput(attrs={"class": "form-input", "min": "0"}),
            "missing_asset_count": forms.NumberInput(attrs={"class": "form-input", "min": "0"}),
            "discrepancy_count": forms.NumberInput(attrs={"class": "form-input", "min": "0"}),
            "discrepancy_notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Discrepancy observations, tag condition, missing serial numbers..."}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Auditor notes and instructions..."}),
        }

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)

        if self.tenant:
            self.fields["target_location"].queryset = Location.objects.filter(tenant=self.tenant, is_active=True).order_by("name")
            self.fields["target_org_unit"].queryset = OrgUnit.objects.filter(tenant=self.tenant).order_by("name")
            tenant_users = User.objects.filter(tenant=self.tenant, is_active=True).order_by("username")
            self.fields["lead_auditor"].queryset = tenant_users
            self.fields["supervisor"].queryset = tenant_users

    def clean(self):
        cleaned_data = super().clean()
        if self.tenant:
            reject_foreign(self, cleaned_data, ["target_location", "target_org_unit", "lead_auditor", "supervisor"])

        # Count sanity validation
        expected = cleaned_data.get("expected_asset_count") or 0
        scanned = cleaned_data.get("scanned_asset_count") or 0
        matched = cleaned_data.get("matched_asset_count") or 0
        missing = cleaned_data.get("missing_asset_count") or 0
        discrepancy = cleaned_data.get("discrepancy_count") or 0

        for field_name, val in [
            ("expected_asset_count", expected),
            ("scanned_asset_count", scanned),
            ("matched_asset_count", matched),
            ("missing_asset_count", missing),
            ("discrepancy_count", discrepancy),
        ]:
            if val < 0:
                self.add_error(field_name, "Count cannot be negative.")

        return cleaned_data
