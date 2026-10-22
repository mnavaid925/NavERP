"""Sales 8.16 — FieldCheckIn forms."""
from django import forms

from apps.accounts.models import User
from apps.core.forms import TenantModelForm
from apps.core.models import Document, Party
from apps.crm.models import Opportunity
from apps.sales.forms._common import tenant_users
from apps.sales.models.MobileSales.FieldCheckIns import (
    VERIFICATION_STATUS_CHOICES,
    VISIT_OUTCOME_CHOICES,
    VISIT_PURPOSE_CHOICES,
    FieldCheckIn,
)
from apps.sales.models.MobileSales.FieldSalesRoutes import FieldSalesRoute
from apps.sales.models.QuoteProposalCPQ.CPQQuotes import CPQQuote


class FieldCheckInForm(TenantModelForm):
    class Meta:
        model = FieldCheckIn
        fields = [
            "route",
            "stop_number",
            "party",
            "contact",
            "opportunity",
            "sales_rep",
            "check_in_lat",
            "check_in_lng",
            "target_lat",
            "target_lng",
            "geofence_radius_m",
            "verification_status",
            "visit_purpose",
            "outcome",
            "notes",
            "next_step",
            "next_step_due",
            "photo_document",
            "resulting_quote",
        ]
        widgets = {
            "route": forms.Select(attrs={"class": "form-select"}),
            "stop_number": forms.NumberInput(attrs={"class": "form-input", "min": 1}),
            "party": forms.Select(attrs={"class": "form-select"}),
            "contact": forms.Select(attrs={"class": "form-select"}),
            "opportunity": forms.Select(attrs={"class": "form-select"}),
            "sales_rep": forms.Select(attrs={"class": "form-select"}),
            "check_in_lat": forms.NumberInput(attrs={"class": "form-input", "step": "0.000001", "placeholder": "e.g. 40.712776"}),
            "check_in_lng": forms.NumberInput(attrs={"class": "form-input", "step": "0.000001", "placeholder": "e.g. -74.005974"}),
            "target_lat": forms.NumberInput(attrs={"class": "form-input", "step": "0.000001", "placeholder": "Target account lat"}),
            "target_lng": forms.NumberInput(attrs={"class": "form-input", "step": "0.000001", "placeholder": "Target account lng"}),
            "geofence_radius_m": forms.NumberInput(attrs={"class": "form-input", "min": 10}),
            "verification_status": forms.Select(attrs={"class": "form-select"}),
            "visit_purpose": forms.Select(attrs={"class": "form-select"}),
            "outcome": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Summary of discussions..."}),
            "next_step": forms.TextInput(attrs={"class": "form-input", "placeholder": "Actionable follow-up"}),
            "next_step_due": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "photo_document": forms.Select(attrs={"class": "form-select"}),
            "resulting_quote": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["route"].queryset = FieldSalesRoute.objects.filter(tenant=self.tenant)
            self.fields["party"].queryset = Party.objects.filter(tenant=self.tenant)
            self.fields["contact"].queryset = Party.objects.filter(tenant=self.tenant)
            self.fields["opportunity"].queryset = Opportunity.objects.filter(tenant=self.tenant)
            self.fields["sales_rep"].queryset = tenant_users(self.tenant)
            self.fields["photo_document"].queryset = Document.objects.filter(tenant=self.tenant)
            self.fields["resulting_quote"].queryset = CPQQuote.objects.filter(tenant=self.tenant)


class FieldCheckOutForm(forms.ModelForm):
    class Meta:
        model = FieldCheckIn
        fields = [
            "check_out_lat",
            "check_out_lng",
            "outcome",
            "notes",
            "next_step",
            "next_step_due",
        ]
        widgets = {
            "check_out_lat": forms.NumberInput(attrs={"class": "form-input", "step": "0.000001", "placeholder": "Departure lat"}),
            "check_out_lng": forms.NumberInput(attrs={"class": "form-input", "step": "0.000001", "placeholder": "Departure lng"}),
            "outcome": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Final meeting notes before departure..."}),
            "next_step": forms.TextInput(attrs={"class": "form-input", "placeholder": "Next action item"}),
            "next_step_due": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
        }


class FieldCheckInFilterForm(forms.Form):
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "Search customer, number..."}),
    )
    verification_status = forms.ChoiceField(
        choices=[("", "All Verification Statuses")] + list(VERIFICATION_STATUS_CHOICES),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    visit_purpose = forms.ChoiceField(
        choices=[("", "All Visit Purposes")] + list(VISIT_PURPOSE_CHOICES),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    outcome = forms.ChoiceField(
        choices=[("", "All Outcomes")] + list(VISIT_OUTCOME_CHOICES),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    sales_rep = forms.ModelChoiceField(
        queryset=User.objects.none(),
        required=False,
        empty_label="All Sales Reps",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args, **kwargs):
        tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)
        if tenant is not None:
            self.fields["sales_rep"].queryset = tenant_users(tenant)
