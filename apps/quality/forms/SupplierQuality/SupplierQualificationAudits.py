from django import forms
from django.contrib.auth import get_user_model

from apps.core.forms import TenantModelForm
from apps.core.models import Party
from apps.quality.forms._common import TenantUniqueMixin, reject_foreign
from apps.quality.models import ControlledDocument
from apps.quality.models.SupplierQuality.SupplierQualificationAudits import (
    SupplierQualificationAudit,
)

User = get_user_model()


class SupplierQualificationAuditForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = SupplierQualificationAudit
        fields = [
            "supplier",
            "assessment_type",
            "criticality_tier",
            "audit_method",
            "qualification_status",
            "scope_commodities",
            "score",
            "audit_result",
            "critical_findings",
            "major_findings",
            "minor_findings",
            "lead_auditor",
            "audit_date",
            "qualified_date",
            "next_audit_due_date",
            "certificate_expiry_date",
            "dock_to_stock_eligible",
            "skip_lot_approved",
            "requires_coa",
            "quality_agreement",
            "notes",
        ]
        widgets = {
            "supplier": forms.Select(attrs={"class": "form-select"}),
            "assessment_type": forms.Select(attrs={"class": "form-select"}),
            "criticality_tier": forms.Select(attrs={"class": "form-select"}),
            "audit_method": forms.Select(attrs={"class": "form-select"}),
            "qualification_status": forms.Select(attrs={"class": "form-select"}),
            "scope_commodities": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
            "score": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0", "max": "100"}),
            "audit_result": forms.Select(attrs={"class": "form-select"}),
            "critical_findings": forms.NumberInput(attrs={"class": "form-input", "min": "0"}),
            "major_findings": forms.NumberInput(attrs={"class": "form-input", "min": "0"}),
            "minor_findings": forms.NumberInput(attrs={"class": "form-input", "min": "0"}),
            "lead_auditor": forms.Select(attrs={"class": "form-select"}),
            "audit_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "qualified_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "next_audit_due_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "certificate_expiry_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "dock_to_stock_eligible": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "skip_lot_approved": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "requires_coa": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "quality_agreement": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            suppliers = Party.objects.filter(
                tenant=self.tenant, roles__role__in=("supplier", "vendor")
            ).distinct().order_by("name")
            if not suppliers.exists():
                suppliers = Party.objects.filter(tenant=self.tenant).order_by("name")
            self.fields["supplier"].queryset = suppliers
            self.fields["lead_auditor"].queryset = User.objects.filter(
                tenant=self.tenant
            ).order_by("first_name", "last_name", "email")
            self.fields["quality_agreement"].queryset = ControlledDocument.objects.filter(
                tenant=self.tenant
            ).order_by("title")

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["supplier", "lead_auditor", "quality_agreement"])
        return cleaned_data
