"""Sales 8.13 — Forms for `MarketingEvent` and `EventRegistration`."""
from django import forms

from apps.accounts.models import User
from apps.accounting.models import Currency
from apps.core.forms import TenantModelForm
from apps.core.models import Party
from apps.crm.models import Campaign, Lead, Opportunity
from apps.sales.forms._common import TenantUniqueMixin, _reject_foreign
from apps.sales.models.MarketingAlignment.MarketingEvents import (
    EventRegistration,
    MarketingEvent,
)


class MarketingEventForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = MarketingEvent
        fields = [
            "name",
            "event_type",
            "status",
            "start_at",
            "end_at",
            "timezone_name",
            "venue",
            "virtual_url",
            "capacity",
            "budget",
            "currency",
            "owner",
            "campaign",
            "description",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. Q3 Revenue Ops Webinar"}
            ),
            "event_type": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "timezone_name": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. Europe/London"}
            ),
            "venue": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. Head Office, Room 4B"}
            ),
            "virtual_url": forms.URLInput(
                attrs={"class": "form-input", "placeholder": "https://..."}
            ),
            "capacity": forms.NumberInput(
                attrs={"class": "form-input", "min": 0, "placeholder": "0 = unlimited"}
            ),
            "budget": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": 0}),
            "currency": forms.Select(attrs={"class": "form-select"}),
            "owner": forms.Select(attrs={"class": "form-select"}),
            "campaign": forms.Select(attrs={"class": "form-select"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["owner"].queryset = User.objects.filter(
                tenant=self.tenant
            ).order_by("username")
            self.fields["campaign"].queryset = Campaign.objects.filter(
                tenant=self.tenant
            ).order_by("name")
            self.fields["currency"].queryset = Currency.objects.order_by("code")

    def clean(self):
        cleaned_data = super().clean()
        _reject_foreign(self, cleaned_data, ["owner", "campaign", "currency"])
        end_at = cleaned_data.get("end_at")
        start_at = cleaned_data.get("start_at")
        if end_at and start_at and end_at < start_at:
            self.add_error("end_at", "The event cannot end before it starts.")
        return cleaned_data


class EventRegistrationForm(TenantModelForm):
    class Meta:
        model = EventRegistration
        fields = [
            "event",
            "lead",
            "account",
            "campaign",
            "registrant_name",
            "registrant_email",
            "registration_status",
            "source_channel",
            "registered_at",
            "followup_status",
            "followup_notes",
            "engagement_score",
            "revenue_attributed",
            "opportunity",
        ]
        widgets = {
            "event": forms.Select(attrs={"class": "form-select"}),
            "lead": forms.Select(attrs={"class": "form-select"}),
            "account": forms.Select(attrs={"class": "form-select"}),
            "campaign": forms.Select(attrs={"class": "form-select"}),
            "registrant_name": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. Jordan Blake"}
            ),
            "registrant_email": forms.EmailInput(
                attrs={"class": "form-input", "placeholder": "jordan@example.com"}
            ),
            "registration_status": forms.Select(attrs={"class": "form-select"}),
            "source_channel": forms.Select(attrs={"class": "form-select"}),
            "followup_status": forms.Select(attrs={"class": "form-select"}),
            "followup_notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
            "engagement_score": forms.NumberInput(
                attrs={"class": "form-input", "min": 0, "max": 100}
            ),
            "revenue_attributed": forms.NumberInput(
                attrs={"class": "form-input", "step": "0.01", "min": 0}
            ),
            "opportunity": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["event"].queryset = MarketingEvent.objects.filter(
                tenant=self.tenant
            ).order_by("-start_at")
            self.fields["lead"].queryset = Lead.objects.filter(
                tenant=self.tenant
            ).order_by("name")
            self.fields["account"].queryset = (
                Party.objects.filter(tenant=self.tenant, roles__role="customer")
                .distinct()
                .order_by("name")
            )
            self.fields["campaign"].queryset = Campaign.objects.filter(
                tenant=self.tenant
            ).order_by("name")
            self.fields["opportunity"].queryset = Opportunity.objects.filter(
                tenant=self.tenant
            ).order_by("-created_at")

    def clean(self):
        cleaned_data = super().clean()
        _reject_foreign(
            self,
            cleaned_data,
            ["event", "lead", "account", "campaign", "opportunity"],
        )
        return cleaned_data
