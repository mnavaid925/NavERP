from django import forms
from django.contrib.auth import get_user_model

from apps.assets.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.assets.models.AssetCompliance.AssetComplianceAudits import AssetComplianceAudit
from apps.assets.models.AssetCompliance.AssetComplianceFrameworks import AssetComplianceFramework
from apps.core.models import Party
from apps.scm.models import Asset

User = get_user_model()


class AssetComplianceAuditForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = AssetComplianceAudit
        fields = [
            "title",
            "framework",
            "asset",
            "audit_type",
            "lead_auditor_user",
            "auditor_party",
            "audit_date",
            "scope_description",
            "total_checkpoints",
            "passed_checkpoints",
            "minor_findings_count",
            "major_findings_count",
            "critical_findings_count",
            "compliance_rating",
            "summary_findings",
            "status",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Annual Plant 1 OSHA Machine Guarding Inspection"}),
            "framework": forms.Select(attrs={"class": "form-select"}),
            "asset": forms.Select(attrs={"class": "form-select"}),
            "audit_type": forms.Select(attrs={"class": "form-select"}),
            "lead_auditor_user": forms.Select(attrs={"class": "form-select"}),
            "auditor_party": forms.Select(attrs={"class": "form-select"}),
            "audit_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "scope_description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Specific plant areas, machines, and operational procedures covered..."}),
            "total_checkpoints": forms.NumberInput(attrs={"class": "form-input", "min": "0"}),
            "passed_checkpoints": forms.NumberInput(attrs={"class": "form-input", "min": "0"}),
            "minor_findings_count": forms.NumberInput(attrs={"class": "form-input", "min": "0"}),
            "major_findings_count": forms.NumberInput(attrs={"class": "form-input", "min": "0"}),
            "critical_findings_count": forms.NumberInput(attrs={"class": "form-input", "min": "0"}),
            "compliance_rating": forms.Select(attrs={"class": "form-select"}),
            "summary_findings": forms.Textarea(attrs={"class": "form-textarea", "rows": 4, "placeholder": "Executive summary of auditor findings, non-conformances, and observations..."}),
            "status": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, "tenant") and self.tenant is not None:
            self.fields["framework"].queryset = AssetComplianceFramework.objects.filter(tenant=self.tenant)
            self.fields["asset"].queryset = Asset.objects.filter(tenant=self.tenant)
            self.fields["auditor_party"].queryset = Party.objects.filter(tenant=self.tenant)
            self.fields["lead_auditor_user"].queryset = User.objects.filter(tenant=self.tenant)

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["framework", "asset", "auditor_party"])
        return cleaned
