from django import forms
from django.contrib.auth import get_user_model

from apps.quality.forms._common import reject_foreign
from apps.quality.models.CapaManagement.CapaActions import CapaAction
from apps.quality.models.DocumentControl.DocumentChangeOrders import DocumentChangeOrder
from apps.quality.models.TrainingCompetency.QualityTrainingCourses import QualityTrainingCourse
from apps.quality.models.TrainingCompetency.TrainingEnrollments import TrainingEnrollment

User = get_user_model()


class TrainingEnrollmentForm(forms.ModelForm):
    class Meta:
        model = TrainingEnrollment
        fields = [
            "course",
            "trainee",
            "assignment_reason",
            "document_change_order",
            "capa_action",
            "assigned_date",
            "due_date",
            "notes",
        ]
        widgets = {
            "course": forms.Select(attrs={"class": "form-select"}),
            "trainee": forms.Select(attrs={"class": "form-select"}),
            "assignment_reason": forms.Select(attrs={"class": "form-select"}),
            "document_change_order": forms.Select(attrs={"class": "form-select"}),
            "capa_action": forms.Select(attrs={"class": "form-select"}),
            "assigned_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "due_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Assignment instructions or special conditions..."}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        self.tenant = tenant or getattr(kwargs.get("instance"), "tenant", None)
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["course"].queryset = QualityTrainingCourse.objects.filter(tenant=self.tenant, status="active")
            self.fields["trainee"].queryset = User.objects.filter(tenant=self.tenant, is_active=True)
            self.fields["document_change_order"].queryset = DocumentChangeOrder.objects.filter(tenant=self.tenant)
            self.fields["capa_action"].queryset = CapaAction.objects.filter(tenant=self.tenant)

    def clean(self):
        cleaned_data = super().clean()
        assigned = cleaned_data.get("assigned_date")
        due = cleaned_data.get("due_date")
        if assigned and due and due < assigned:
            self.add_error("due_date", "Due date cannot be earlier than assigned date.")
        reject_foreign(self, cleaned_data, ["course", "trainee", "document_change_order", "capa_action"])
        return cleaned_data


class TrainingCompletionForm(forms.Form):
    score = forms.DecimalField(
        max_digits=5,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-input", "placeholder": "e.g. 95.00", "min": "0", "max": "100"}),
        help_text="Exam score percentage achieved (if exam was administered).",
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Completion remarks or exam feedback..."}),
    )


class PracticalVerificationForm(forms.Form):
    practical_rating = forms.ChoiceField(
        choices=TrainingEnrollment.PRACTICAL_RATING_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
        help_text="Supervisor practical proficiency rating.",
    )
    practical_evaluation_notes = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 4, "placeholder": "Demonstrated competencies, technique observations, and qualification evaluation..."}),
        help_text="Detailed notes from the hands-on observation.",
    )


class TrainingWaiverForm(forms.Form):
    waiver_reason = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 4, "placeholder": "Regulatory justification, equivalent prior experience, or exemption rationale..."}),
        help_text="Formal regulatory justification for waiver or exemption.",
    )
