"""Sales 8.11 — Forms for `CustomerBusinessReview`."""
from django import forms

from apps.accounts.models import User
from apps.core.forms import TenantModelForm
from apps.core.models import Party
from apps.sales.forms._common import TenantUniqueMixin, _reject_foreign
from apps.sales.models.ContactAccountManagement.AccountPlans import AccountPlan
from apps.sales.models.CustomerSuccess.CustomerBusinessReviews import CustomerBusinessReview


class CustomerBusinessReviewForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = CustomerBusinessReview
        fields = [
            "account",
            "lead_csm",
            "account_plan",
            "title",
            "review_period",
            "review_year",
            "scheduled_date",
            "completed_date",
            "status",
            "template_type",
            "executive_sponsor_attended",
            "client_attendees",
            "internal_attendees",
            "health_score_at_review",
            "key_achievements",
            "challenges_and_risks",
            "is_referenceable",
            "case_study_status",
            "testimonial_quote",
            "notes",
        ]
        widgets = {
            "account": forms.Select(attrs={"class": "form-select"}),
            "lead_csm": forms.Select(attrs={"class": "form-select"}),
            "account_plan": forms.Select(attrs={"class": "form-select"}),
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Acme Corp Q3 2026 Executive Business Review"}),
            "review_period": forms.Select(attrs={"class": "form-select"}),
            "review_year": forms.NumberInput(attrs={"class": "form-input", "min": 2020, "max": 2035}),
            "scheduled_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "completed_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "template_type": forms.Select(attrs={"class": "form-select"}),
            "executive_sponsor_attended": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "client_attendees": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Client VP Eng, Director IT, etc."}),
            "internal_attendees": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "CSM, Solutions Architect, Account Exec"}),
            "health_score_at_review": forms.NumberInput(attrs={"class": "form-input", "min": 0, "max": 100}),
            "key_achievements": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Quantified value, milestones, metrics"}),
            "challenges_and_risks": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Risks, blockers, product requests"}),
            "is_referenceable": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "case_study_status": forms.Select(attrs={"class": "form-select"}),
            "testimonial_quote": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Approved client quote"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["account"].queryset = (
                Party.objects.filter(tenant=self.tenant, roles__role="customer")
                .distinct()
                .order_by("name")
            )
            self.fields["lead_csm"].queryset = (
                User.objects.filter(tenant=self.tenant)
                .order_by("username")
            )
            self.fields["account_plan"].queryset = (
                AccountPlan.objects.filter(tenant=self.tenant)
                .order_by("-period_start")
            )

    def clean(self):
        cleaned_data = super().clean()
        _reject_foreign(self, cleaned_data, ["account", "lead_csm", "account_plan"])
        return cleaned_data
