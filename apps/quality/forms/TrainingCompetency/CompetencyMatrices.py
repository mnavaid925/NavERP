from django import forms
from django.contrib.auth import get_user_model

from apps.core.models.OrgUnit import OrgUnit
from apps.quality.forms._common import reject_foreign
from apps.quality.models.TrainingCompetency.CompetencyMatrices import CompetencyMatrix

User = get_user_model()


class CompetencyMatrixForm(forms.ModelForm):
    class Meta:
        model = CompetencyMatrix
        fields = [
            "title",
            "role_title",
            "qualification_tier",
            "department",
            "criticality",
            "revision",
            "minimum_passing_score",
            "validity_period_months",
            "prerequisite_experience_months",
            "description",
            "notes",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Aseptic Fill Line Operator Competency Matrix"}),
            "role_title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Cleanroom Technician / Operator"}),
            "qualification_tier": forms.Select(attrs={"class": "form-select"}),
            "department": forms.Select(attrs={"class": "form-select"}),
            "criticality": forms.Select(attrs={"class": "form-select"}),
            "revision": forms.TextInput(attrs={"class": "form-input", "placeholder": "1.0"}),
            "minimum_passing_score": forms.NumberInput(attrs={"class": "form-input", "min": 0, "max": 100}),
            "validity_period_months": forms.NumberInput(attrs={"class": "form-input", "min": 1}),
            "prerequisite_experience_months": forms.NumberInput(attrs={"class": "form-input", "min": 0}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 4, "placeholder": "Curriculum overview, role competencies, and qualification scope..."}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Additional regulatory compliance or curriculum notes..."}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        self.tenant = tenant or getattr(kwargs.get("instance"), "tenant", None)
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["department"].queryset = OrgUnit.objects.filter(tenant=self.tenant)

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["department"])
        return cleaned_data
