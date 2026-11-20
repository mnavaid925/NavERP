from django import forms
from django.contrib.auth import get_user_model

from apps.core.models import OrgUnit
from apps.quality.forms._common import TenantModelForm, reject_foreign
from apps.quality.models.ManagementReview.ManagementReviews import ManagementReview

User = get_user_model()


class ManagementReviewForm(TenantModelForm):
    class Meta:
        model = ManagementReview
        fields = [
            "title",
            "cadence",
            "period_start",
            "period_end",
            "scheduled_date",
            "location",
            "executive_sponsor",
            "lead_facilitator",
            "org_unit",
            "notes",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Q1 2026 Executive Management Review"}),
            "cadence": forms.Select(attrs={"class": "form-select"}),
            "period_start": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "period_end": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "scheduled_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "location": forms.TextInput(attrs={"class": "form-input", "placeholder": "Boardroom / Microsoft Teams Link"}),
            "executive_sponsor": forms.Select(attrs={"class": "form-select"}),
            "lead_facilitator": forms.Select(attrs={"class": "form-select"}),
            "org_unit": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 2}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        if self.tenant:
            user_qs = User.objects.filter(tenant=self.tenant, is_active=True).order_by("first_name", "last_name", "username")
            self.fields["executive_sponsor"].queryset = user_qs
            self.fields["lead_facilitator"].queryset = user_qs
            self.fields["org_unit"].queryset = OrgUnit.objects.filter(tenant=self.tenant).order_by("name")

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["executive_sponsor", "lead_facilitator", "org_unit"])
        period_start = cleaned_data.get("period_start")
        period_end = cleaned_data.get("period_end")
        if period_start and period_end and period_start > period_end:
            self.add_error("period_end", "Period end date cannot precede period start date.")
        return cleaned_data


class ManagementReviewMinutesForm(forms.ModelForm):
    class Meta:
        model = ManagementReview
        fields = [
            "actual_meeting_date",
            "attendees_roster",
            "quorum_met",
            "qms_suitability_conclusion",
            "executive_summary",
            "minutes_discussion",
            "resource_decisions",
            "notes",
        ]
        widgets = {
            "actual_meeting_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "attendees_roster": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "List of attendees, roles, and departments present"}),
            "quorum_met": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "qms_suitability_conclusion": forms.Select(attrs={"class": "form-select"}),
            "executive_summary": forms.Textarea(attrs={"class": "form-textarea", "rows": 4, "placeholder": "Executive overview of QMS performance and continuing adequacy"}),
            "minutes_discussion": forms.Textarea(attrs={"class": "form-textarea", "rows": 6, "placeholder": "Detailed proceedings, review topic findings, and discussion notes"}),
            "resource_decisions": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Resource allocation commitments, staffing, capital, or facility investments"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 2}),
        }


class ManagementReviewApproveForm(forms.Form):
    comment = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Executive approval remarks or sign-off commentary"}),
    )
    confirm_suitability = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        label="I formally certify that Management with Executive Responsibility has reviewed the compiled inputs and endorses the recorded QMS suitability conclusion.",
    )
