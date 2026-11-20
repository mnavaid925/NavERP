from django import forms
from django.contrib.auth import get_user_model

from apps.core.models.Party import Party
from apps.quality.forms._common import reject_foreign
from apps.quality.models.DocumentControl.ControlledDocuments import ControlledDocument
from apps.quality.models.TrainingCompetency.CompetencyMatrices import CompetencyMatrix
from apps.quality.models.TrainingCompetency.QualityTrainingCourses import QualityTrainingCourse

User = get_user_model()


class QualityTrainingCourseForm(forms.ModelForm):
    class Meta:
        model = QualityTrainingCourse
        fields = [
            "title",
            "competency_matrix",
            "course_code",
            "category",
            "delivery_method",
            "assessment_method",
            "controlled_document",
            "document_revision",
            "retrain_on_revision",
            "duration_hours",
            "passing_score",
            "ojt_checklist_criteria",
            "syllabus_summary",
            "external_provider",
            "instructor",
            "notes",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. SOP-0042 Aseptic Gowning and Cleanroom Entry Protocol"}),
            "competency_matrix": forms.Select(attrs={"class": "form-select"}),
            "course_code": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. TRN-SOP-042"}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "delivery_method": forms.Select(attrs={"class": "form-select"}),
            "assessment_method": forms.Select(attrs={"class": "form-select"}),
            "controlled_document": forms.Select(attrs={"class": "form-select"}),
            "document_revision": forms.TextInput(attrs={"class": "form-input", "placeholder": "Rev C"}),
            "retrain_on_revision": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "duration_hours": forms.NumberInput(attrs={"class": "form-input", "step": "0.25", "min": "0.25"}),
            "passing_score": forms.NumberInput(attrs={"class": "form-input", "min": 0, "max": 100}),
            "ojt_checklist_criteria": forms.Textarea(attrs={"class": "form-textarea", "rows": 4, "placeholder": "Demonstration steps, observation criteria, and sign-off prerequisites..."}),
            "syllabus_summary": forms.Textarea(attrs={"class": "form-textarea", "rows": 4, "placeholder": "Learning outcomes, training modules, and study references..."}),
            "external_provider": forms.Select(attrs={"class": "form-select"}),
            "instructor": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Additional course guidelines or administrative notes..."}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        self.tenant = tenant or getattr(kwargs.get("instance"), "tenant", None)
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["competency_matrix"].queryset = CompetencyMatrix.objects.filter(tenant=self.tenant)
            self.fields["controlled_document"].queryset = ControlledDocument.objects.filter(tenant=self.tenant)
            self.fields["external_provider"].queryset = Party.objects.filter(tenant=self.tenant)
            self.fields["instructor"].queryset = User.objects.filter(tenant=self.tenant, is_active=True)

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["competency_matrix", "controlled_document", "external_provider", "instructor"])
        return cleaned_data
