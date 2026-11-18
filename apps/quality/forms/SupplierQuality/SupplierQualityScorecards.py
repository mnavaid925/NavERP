from django import forms
from django.contrib.auth import get_user_model

from apps.core.forms import TenantModelForm
from apps.core.models import Party
from apps.quality.forms._common import TenantUniqueMixin, reject_foreign
from apps.quality.models.SupplierQuality.SupplierQualityScorecards import (
    SupplierQualityScorecard,
)

User = get_user_model()


class SupplierQualityScorecardForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = SupplierQualityScorecard
        fields = [
            "supplier",
            "cadence",
            "period_start",
            "period_end",
            "status",
            "lot_acceptance_rate_score",
            "defect_ppm_score",
            "scar_responsiveness_score",
            "audit_compliance_score",
            "documentation_coa_score",
            "total_lots_received",
            "lots_rejected",
            "total_scars_issued",
            "evaluated_by",
            "is_manual_override",
            "override_justification",
            "evaluation_notes",
        ]
        widgets = {
            "supplier": forms.Select(attrs={"class": "form-select"}),
            "cadence": forms.Select(attrs={"class": "form-select"}),
            "period_start": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "period_end": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "lot_acceptance_rate_score": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0", "max": "100"}),
            "defect_ppm_score": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0", "max": "100"}),
            "scar_responsiveness_score": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0", "max": "100"}),
            "audit_compliance_score": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0", "max": "100"}),
            "documentation_coa_score": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0", "max": "100"}),
            "total_lots_received": forms.NumberInput(attrs={"class": "form-input", "min": "0"}),
            "lots_rejected": forms.NumberInput(attrs={"class": "form-input", "min": "0"}),
            "total_scars_issued": forms.NumberInput(attrs={"class": "form-input", "min": "0"}),
            "evaluated_by": forms.Select(attrs={"class": "form-select"}),
            "is_manual_override": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "override_justification": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
            "evaluation_notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
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
            self.fields["evaluated_by"].queryset = User.objects.filter(
                tenant=self.tenant
            ).order_by("first_name", "last_name", "email")

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["supplier", "evaluated_by"])
        is_override = cleaned_data.get("is_manual_override")
        justification = cleaned_data.get("override_justification", "").strip()
        if is_override and not justification:
            self.add_error("override_justification", "Override justification is mandatory when manual override is enabled.")
        return cleaned_data
