"""Sales 8.9 — `SalesCertificationForm`."""
from django import forms
from django.apps import apps

from apps.accounts.models import User
from apps.core.forms import TenantModelForm
from apps.sales.forms._common import TenantUniqueMixin, _reject_foreign
from apps.sales.models.SalesEnablement.SalesCertifications import SalesCertification


class SalesCertificationForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = SalesCertification
        fields = [
            "curriculum_name",
            "category",
            "rep",
            "status",
            "score_percent",
            "passing_score_percent",
            "certified_by",
            "certified_at",
            "expires_at",
            "accreditation_notes",
            "hrm_course",
        ]
        widgets = {
            "curriculum_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Enterprise Cloud Solution Architecture v2"}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "rep": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "score_percent": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "placeholder": "85.00"}),
            "passing_score_percent": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "placeholder": "80.00"}),
            "certified_by": forms.Select(attrs={"class": "form-select"}),
            "certified_at": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "expires_at": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "accreditation_notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Evaluator feedback, exam credential verification ID, or panel review notes"}),
            "hrm_course": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["rep"].queryset = User.objects.filter(tenant=self.tenant, is_active=True)
            self.fields["certified_by"].queryset = User.objects.filter(tenant=self.tenant, is_active=True)
            TrainingCourse = apps.get_model("hrm", "TrainingCourse", require_ready=False)
            if TrainingCourse:
                self.fields["hrm_course"].queryset = TrainingCourse.objects.filter(tenant=self.tenant, is_active=True)
            else:
                self.fields["hrm_course"].queryset = self.fields["hrm_course"].queryset.none()
        else:
            self.fields["rep"].queryset = User.objects.none()
            self.fields["certified_by"].queryset = User.objects.none()
            self.fields["hrm_course"].queryset = self.fields["hrm_course"].queryset.none()

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["rep", "certified_by", "hrm_course"])
        return cleaned
