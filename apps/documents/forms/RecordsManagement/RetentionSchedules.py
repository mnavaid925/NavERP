from django import forms

from apps.core.forms import TenantModelForm
from apps.core.models import OrgUnit
from apps.documents.forms._common import TenantUniqueMixin, reject_foreign
from apps.documents.models.RecordsManagement.RetentionSchedules import RetentionSchedule


class RetentionScheduleForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = RetentionSchedule
        fields = [
            "name",
            "code",
            "description",
            "retention_period_years",
            "retention_period_months",
            "is_permanent",
            "trigger_type",
            "cutoff_rule",
            "disposition_action",
            "compliance_framework",
            "retention_mode",
            "legal_citation",
            "department",
            "is_active",
            "notes",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Accounting Tax Records"}),
            "code": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. FIN-TAX-01"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
            "retention_period_years": forms.NumberInput(attrs={"class": "form-input", "min": 0}),
            "retention_period_months": forms.NumberInput(attrs={"class": "form-input", "min": 0, "max": 11}),
            "is_permanent": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "trigger_type": forms.Select(attrs={"class": "form-select"}),
            "cutoff_rule": forms.Select(attrs={"class": "form-select"}),
            "disposition_action": forms.Select(attrs={"class": "form-select"}),
            "compliance_framework": forms.Select(attrs={"class": "form-select"}),
            "retention_mode": forms.Select(attrs={"class": "form-select"}),
            "legal_citation": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. 26 U.S. Code § 6501 / IRS Pub 583"}),
            "department": forms.Select(attrs={"class": "form-select"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["department"].queryset = OrgUnit.objects.filter(tenant=self.tenant)
        else:
            self.fields["department"].queryset = OrgUnit.objects.none()

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["department"])

        code = cleaned_data.get("code")
        if code and self.tenant:
            qs = RetentionSchedule.objects.filter(tenant=self.tenant, code__iexact=code.strip())
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error("code", "A retention schedule with this file plan code already exists in your workspace.")

        is_permanent = cleaned_data.get("is_permanent")
        years = cleaned_data.get("retention_period_years") or 0
        months = cleaned_data.get("retention_period_months") or 0
        retention_mode = cleaned_data.get("retention_mode")

        if retention_mode == "regulatory_worm" and not is_permanent and years == 0 and months == 0:
            self.add_error(
                "retention_mode",
                "Regulatory WORM schedules must have a retention duration greater than 0, or be marked permanent.",
            )

        return cleaned_data
