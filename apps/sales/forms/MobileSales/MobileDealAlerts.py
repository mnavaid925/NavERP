"""Sales 8.16 — MobileDealAlert forms."""
from django import forms

from apps.accounts.models import User
from apps.core.forms import TenantModelForm
from apps.crm.models import Opportunity
from apps.sales.forms._common import tenant_users
from apps.sales.models.MobileSales.FieldSalesRoutes import FieldSalesRoute
from apps.sales.models.MobileSales.MobileDealAlerts import (
    ALERT_TYPE_CHOICES,
    URGENCY_CHOICES,
    MobileDealAlert,
)
from apps.sales.models.MobileSales.MobileDeviceSessions import MobileDeviceSession
from apps.sales.models.QuoteProposalCPQ.CPQQuotes import CPQQuote


class MobileDealAlertForm(TenantModelForm):
    class Meta:
        model = MobileDealAlert
        fields = [
            "recipient",
            "device",
            "alert_type",
            "title",
            "message",
            "urgency",
            "related_opportunity",
            "related_quote",
            "related_route",
        ]
        widgets = {
            "recipient": forms.Select(attrs={"class": "form-select"}),
            "device": forms.Select(attrs={"class": "form-select"}),
            "alert_type": forms.Select(attrs={"class": "form-select"}),
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Urgent: Quote Discount Approval Requested"}),
            "message": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Notification content body..."}),
            "urgency": forms.Select(attrs={"class": "form-select"}),
            "related_opportunity": forms.Select(attrs={"class": "form-select"}),
            "related_quote": forms.Select(attrs={"class": "form-select"}),
            "related_route": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["recipient"].queryset = tenant_users(self.tenant)
            self.fields["device"].queryset = MobileDeviceSession.objects.filter(tenant=self.tenant)
            self.fields["related_opportunity"].queryset = Opportunity.objects.filter(tenant=self.tenant)
            self.fields["related_quote"].queryset = CPQQuote.objects.filter(tenant=self.tenant)
            self.fields["related_route"].queryset = FieldSalesRoute.objects.filter(tenant=self.tenant)


class MobileDealAlertFilterForm(forms.Form):
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "Search title, message..."}),
    )
    alert_type = forms.ChoiceField(
        choices=[("", "All Alert Types")] + list(ALERT_TYPE_CHOICES),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    urgency = forms.ChoiceField(
        choices=[("", "All Urgencies")] + list(URGENCY_CHOICES),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    is_read = forms.ChoiceField(
        choices=[("", "All Statuses"), ("0", "Unread Only"), ("1", "Read Only")],
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    recipient = forms.ModelChoiceField(
        queryset=User.objects.none(),
        required=False,
        empty_label="All Recipients",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args, **kwargs):
        tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)
        if tenant is not None:
            self.fields["recipient"].queryset = tenant_users(tenant)
