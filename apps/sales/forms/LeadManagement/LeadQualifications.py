from django import forms

from apps.sales.forms._common import TenantActionForm, TenantModelForm, TenantUniqueMixin, _reject_foreign, tenant_leads
from apps.sales.models import LeadQualification


class LeadQualificationForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = LeadQualification
        fields = [
            "lead", "framework", "country_code", "region", "city", "industry", "employee_count",
            "seniority", "budget_status", "budget_amount", "budget_currency", "authority_level",
            "need_summary", "expected_purchase_on", "economic_buyer", "decision_criteria",
            "decision_process", "technical_requirements", "pain_points", "success_metrics",
            "next_review_on", "notes",
        ]

    def __init__(self, *args, tenant=None, leads=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        self.fields["lead"].queryset = leads if leads is not None else tenant_leads(tenant)
        if self.instance.pk:
            self.fields["lead"].disabled = True

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["lead"])
        if self.instance.pk and self.instance.status == "archived":
            self.add_error(None, "Archived assessments cannot be edited.")
        return cleaned


class LeadQualificationDecisionForm(TenantActionForm):
    status = forms.ChoiceField(choices=[
        ("partially_qualified", "Partially Qualified"),
        ("qualified", "Qualified"),
        ("disqualified", "Disqualified"),
        ("archived", "Archived"),
    ])
    disqualification_reason = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("status") == "disqualified" and not cleaned.get("disqualification_reason", "").strip():
            self.add_error("disqualification_reason", "A reason is required for a disqualified lead.")
        return cleaned
