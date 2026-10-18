"""Sales 8.9 — `CoachingScorecardForm`."""
from django import forms

from apps.accounts.models import User
from apps.core.forms import TenantModelForm
from apps.crm.models.ActivityManagement.CommunicationLogs import CommunicationLog
from apps.sales.forms._common import TenantUniqueMixin, _reject_foreign
from apps.sales.models.SalesActivityTaskManagement.ActivityLogs import ActivityLog
from apps.sales.models.SalesEnablement.CoachingScorecards import CoachingScorecard


class CoachingScorecardForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = CoachingScorecard
        fields = [
            "communication_log",
            "activity_log",
            "coach",
            "coachee",
            "recording_url",
            "discovery_score",
            "value_prop_score",
            "objection_handling_score",
            "next_steps_score",
            "talk_listen_ratio_percent",
            "call_sentiment",
            "transcript_summary",
            "key_strengths",
            "areas_for_improvement",
            "action_items",
            "review_status",
            "evaluated_on",
        ]
        widgets = {
            "communication_log": forms.Select(attrs={"class": "form-select"}),
            "activity_log": forms.Select(attrs={"class": "form-select"}),
            "coach": forms.Select(attrs={"class": "form-select"}),
            "coachee": forms.Select(attrs={"class": "form-select"}),
            "recording_url": forms.URLInput(attrs={"class": "form-input", "placeholder": "https://zoom.us/rec/... or Loom link"}),
            "discovery_score": forms.Select(choices=[(i, f"{i} / 5") for i in range(1, 6)], attrs={"class": "form-select"}),
            "value_prop_score": forms.Select(choices=[(i, f"{i} / 5") for i in range(1, 6)], attrs={"class": "form-select"}),
            "objection_handling_score": forms.Select(choices=[(i, f"{i} / 5") for i in range(1, 6)], attrs={"class": "form-select"}),
            "next_steps_score": forms.Select(choices=[(i, f"{i} / 5") for i in range(1, 6)], attrs={"class": "form-select"}),
            "talk_listen_ratio_percent": forms.NumberInput(attrs={"class": "form-input", "placeholder": "e.g. 46"}),
            "call_sentiment": forms.Select(attrs={"class": "form-select"}),
            "transcript_summary": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Key discussion points, customer questions, and notable moments"}),
            "key_strengths": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Effective questions asked, strong rapport, confident value framing"}),
            "areas_for_improvement": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Missed budget confirmation, spoke too fast during pricing"}),
            "action_items": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Send follow-up one-pager, practice objection drill"}),
            "review_status": forms.Select(attrs={"class": "form-select"}),
            "evaluated_on": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["communication_log"].queryset = CommunicationLog.objects.filter(
                tenant=self.tenant
            ).order_by("-occurred_at")
            self.fields["activity_log"].queryset = (
                ActivityLog.objects.filter(tenant=self.tenant)
                .select_related("communication_log")
                .order_by("-created_at")
            )
            self.fields["coach"].queryset = User.objects.filter(tenant=self.tenant, is_active=True)
            self.fields["coachee"].queryset = User.objects.filter(tenant=self.tenant, is_active=True)
        else:
            self.fields["communication_log"].queryset = CommunicationLog.objects.none()
            self.fields["activity_log"].queryset = ActivityLog.objects.none()
            self.fields["coach"].queryset = User.objects.none()
            self.fields["coachee"].queryset = User.objects.none()

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["communication_log", "activity_log", "coach", "coachee"])
        return cleaned
