from django import forms
from django.contrib.auth import get_user_model

from apps.quality.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.quality.models.RiskManagement.RiskManagementPlans import RiskManagementPlan
from apps.quality.models.RiskManagement.RiskReviewRecords import RiskReviewRecord

User = get_user_model()


class RiskReviewRecordForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = RiskReviewRecord
        fields = [
            "plan",
            "review_title",
            "review_type",
            "review_date",
            "review_period_start",
            "review_period_end",
            "pms_sources_reviewed",
            "new_hazards_identified",
            "risk_profile_changed",
            "overall_residual_risk_reconfirmed",
            "findings_summary",
            "action_items_required",
            "status",
            "lead_reviewer",
        ]
        widgets = {
            "plan": forms.Select(attrs={"class": "form-select"}),
            "review_title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Annual Periodic Risk Review & Post-Market Evaluation"}),
            "review_type": forms.Select(attrs={"class": "form-select"}),
            "review_date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "review_period_start": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "review_period_end": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "pms_sources_reviewed": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Complaints, non-conformances, CAPAs, adverse event databases (FDA MAUDE, EUDAMED), and clinical literature reviewed..."}),
            "new_hazards_identified": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "risk_profile_changed": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "overall_residual_risk_reconfirmed": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "findings_summary": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Detailed conclusions, assessment of residual risk acceptability, and comparison against previous period..."}),
            "action_items_required": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Follow-up CAPAs, design change orders, or labeling revisions initiated..."}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "lead_reviewer": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "status" in self.fields:
            self.fields["status"].choices = [
                ("draft", "Draft"),
                ("under_review", "Under Review"),
            ]
        if hasattr(self, "tenant") and self.tenant is not None:
            self.fields["plan"].queryset = RiskManagementPlan.objects.filter(tenant=self.tenant)
            self.fields["lead_reviewer"].queryset = User.objects.filter(tenant=self.tenant, is_active=True).order_by("username")
        else:
            self.fields["plan"].queryset = RiskManagementPlan.objects.none()
            self.fields["lead_reviewer"].queryset = User.objects.none()

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["plan", "lead_reviewer"])
        status = cleaned.get("status")
        if status and status not in ("draft", "under_review"):
            self.add_error("status", "Review status can only be Draft or Under Review. Formal approval requires the Approve action.")
        return cleaned
