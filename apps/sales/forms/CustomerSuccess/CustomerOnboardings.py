"""Sales 8.11 — Forms for `CustomerOnboarding`."""
from django import forms

from apps.accounts.models import User
from apps.core.forms import TenantModelForm
from apps.core.models import Party
from apps.sales.forms._common import TenantUniqueMixin, _reject_foreign
from apps.sales.models.CustomerSuccess.CustomerOnboardings import CustomerOnboarding
from apps.scm.models import SalesOrder


class CustomerOnboardingForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = CustomerOnboarding
        fields = [
            "account",
            "lead_csm",
            "sales_order",
            "title",
            "playbook_template",
            "stage",
            "status",
            "kickoff_date",
            "target_go_live_date",
            "actual_go_live_date",
            "time_to_value_days",
            "progress_pct",
            "executive_sponsor_name",
            "executive_sponsor_email",
            "blockers",
            "success_criteria",
        ]
        widgets = {
            "account": forms.Select(attrs={"class": "form-select"}),
            "lead_csm": forms.Select(attrs={"class": "form-select"}),
            "sales_order": forms.Select(attrs={"class": "form-select"}),
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Acme Corp Enterprise Platform Launch"}),
            "playbook_template": forms.Select(attrs={"class": "form-select"}),
            "stage": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "kickoff_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "target_go_live_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "actual_go_live_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "time_to_value_days": forms.NumberInput(attrs={"class": "form-input", "min": 0}),
            "progress_pct": forms.NumberInput(attrs={"class": "form-input", "min": 0, "max": 100}),
            "executive_sponsor_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "Client executive sponsor name"}),
            "executive_sponsor_email": forms.EmailInput(attrs={"class": "form-input", "placeholder": "sponsor@client.com"}),
            "blockers": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Roadblocks or impediments"}),
            "success_criteria": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Acceptance criteria and business objectives"}),
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
            self.fields["sales_order"].queryset = (
                SalesOrder.objects.filter(tenant=self.tenant)
                .select_related("customer")
                .order_by("-order_date")
            )

    def clean(self):
        cleaned_data = super().clean()
        _reject_foreign(self, cleaned_data, ["account", "lead_csm", "sales_order"])
        return cleaned_data
