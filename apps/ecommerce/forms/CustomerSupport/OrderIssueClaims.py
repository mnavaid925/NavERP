from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model

from apps.ecommerce.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.ecommerce.models.CustomerProfile.CustomerAccountProfiles import CustomerAccountProfile
from apps.ecommerce.models.CustomerSupport.CustomerSupportTickets import CustomerSupportTicket
from apps.ecommerce.models.CustomerSupport.OrderIssueClaims import OrderIssueClaim
from apps.ecommerce.models.OrderManagement.EcommerceOrders import EcommerceOrder

User = get_user_model()


class OrderIssueClaimForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = OrderIssueClaim
        fields = [
            "order",
            "customer",
            "ticket",
            "claim_type",
            "status",
            "claimed_amount",
            "approved_amount",
            "resolution_action",
            "carrier_tracking_number",
            "photo_evidence_url",
            "customer_notes",
            "decision_notes",
            "reviewed_by",
        ]
        widgets = {
            "order": forms.Select(attrs={"class": "form-select"}),
            "customer": forms.Select(attrs={"class": "form-select"}),
            "ticket": forms.Select(attrs={"class": "form-select"}),
            "claim_type": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "claimed_amount": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "approved_amount": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "resolution_action": forms.Select(attrs={"class": "form-select"}),
            "carrier_tracking_number": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. 1Z9999999999999999"}
            ),
            "photo_evidence_url": forms.URLInput(
                attrs={"class": "form-input", "placeholder": "https://storage.example.com/claims/damage1.jpg"}
            ),
            "customer_notes": forms.Textarea(
                attrs={"class": "form-textarea", "rows": 4, "placeholder": "Describe what was damaged, missing, or wrong..."}
            ),
            "decision_notes": forms.Textarea(
                attrs={"class": "form-textarea", "rows": 3, "placeholder": "Internal staff review justification and resolution reasoning"}
            ),
            "reviewed_by": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["order"].queryset = EcommerceOrder.objects.filter(tenant=self.tenant).select_related("customer")
            self.fields["customer"].queryset = CustomerAccountProfile.objects.filter(tenant=self.tenant).select_related("customer")
            self.fields["ticket"].queryset = CustomerSupportTicket.objects.filter(tenant=self.tenant)
        self.fields["reviewed_by"].queryset = User.objects.filter(is_active=True).order_by("username")
        self.fields["customer"].required = False
        self.fields["ticket"].required = False
        self.fields["approved_amount"].required = False
        self.fields["carrier_tracking_number"].required = False
        self.fields["photo_evidence_url"].required = False
        self.fields["decision_notes"].required = False
        self.fields["reviewed_by"].required = False

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["order", "customer", "ticket"])
        claimed = cleaned.get("claimed_amount")
        if claimed is not None and claimed < Decimal("0.00"):
            self.add_error("claimed_amount", "Claimed amount cannot be negative.")
        approved = cleaned.get("approved_amount")
        if approved is not None and approved < Decimal("0.00"):
            self.add_error("approved_amount", "Approved amount cannot be negative.")
        return cleaned
