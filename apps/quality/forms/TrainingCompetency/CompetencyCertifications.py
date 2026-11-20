from django import forms
from django.contrib.auth import get_user_model

from apps.quality.forms._common import reject_foreign
from apps.quality.models.TrainingCompetency.CompetencyCertifications import CompetencyCertification
from apps.quality.models.TrainingCompetency.CompetencyMatrices import CompetencyMatrix
from apps.quality.models.TrainingCompetency.QualityTrainingCourses import QualityTrainingCourse
from apps.quality.models.TrainingCompetency.TrainingEnrollments import TrainingEnrollment

User = get_user_model()


class CompetencyCertificationForm(forms.ModelForm):
    class Meta:
        model = CompetencyCertification
        fields = [
            "enrollment",
            "trainee",
            "course",
            "competency_matrix",
            "qualification_title",
            "qualification_level",
            "issue_date",
            "valid_until",
            "renewal_interval_months",
            "authorized_work_centers",
            "certified_by",
            "notes",
        ]
        widgets = {
            "enrollment": forms.Select(attrs={"class": "form-select"}),
            "trainee": forms.Select(attrs={"class": "form-select"}),
            "course": forms.Select(attrs={"class": "form-select"}),
            "competency_matrix": forms.Select(attrs={"class": "form-select"}),
            "qualification_title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Certified Aseptic Fill Suite Level 2 Independent Operator"}),
            "qualification_level": forms.Select(attrs={"class": "form-select"}),
            "issue_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "valid_until": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "renewal_interval_months": forms.NumberInput(attrs={"class": "form-input", "min": 1}),
            "authorized_work_centers": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Specific cleanroom suites, production lines, or equipment IDs authorized..."}),
            "certified_by": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Certification credentials, examination remarks, or special limitations..."}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        self.tenant = tenant or getattr(kwargs.get("instance"), "tenant", None)
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["enrollment"].queryset = TrainingEnrollment.objects.filter(tenant=self.tenant)
            self.fields["trainee"].queryset = User.objects.filter(tenant=self.tenant, is_active=True)
            self.fields["course"].queryset = QualityTrainingCourse.objects.filter(tenant=self.tenant)
            self.fields["competency_matrix"].queryset = CompetencyMatrix.objects.filter(tenant=self.tenant)
            self.fields["certified_by"].queryset = User.objects.filter(tenant=self.tenant, is_active=True)

    def clean(self):
        cleaned_data = super().clean()
        issue = cleaned_data.get("issue_date")
        valid = cleaned_data.get("valid_until")
        if issue and valid and valid < issue:
            self.add_error("valid_until", "Expiration date cannot be earlier than issue date.")
        reject_foreign(self, cleaned_data, ["enrollment", "trainee", "course", "competency_matrix", "certified_by"])
        return cleaned_data


class CertificationSuspensionForm(forms.Form):
    suspension_reason = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 4, "placeholder": "Documented quality rationale, incident reference, or re-training requirement..."}),
        help_text="Detailed documented rationale for suspension or revocation.",
    )
