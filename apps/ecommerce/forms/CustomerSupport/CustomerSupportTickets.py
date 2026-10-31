from django import forms
from django.contrib.auth import get_user_model

from apps.ecommerce.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.ecommerce.models.CustomerProfile.CustomerAccountProfiles import CustomerAccountProfile
from apps.ecommerce.models.CustomerSupport.CustomerSupportTickets import CustomerSupportTicket
from apps.ecommerce.models.OrderManagement.EcommerceOrders import EcommerceOrder

User = get_user_model()


class CustomerSupportTicketForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = CustomerSupportTicket
        fields = [
            "customer",
            "order",
            "assigned_agent",
            "subject",
            "customer_name",
            "customer_email",
            "customer_phone",
            "channel",
            "category",
            "priority",
            "status",
            "initial_message",
            "resolution_summary",
            "internal_notes",
            "is_bot_handled",
            "bot_handoff_reason",
        ]
        widgets = {
            "customer": forms.Select(attrs={"class": "form-select"}),
            "order": forms.Select(attrs={"class": "form-select"}),
            "assigned_agent": forms.Select(attrs={"class": "form-select"}),
            "subject": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "Brief description of the customer issue"}
            ),
            "customer_name": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "Customer or guest name"}
            ),
            "customer_email": forms.EmailInput(
                attrs={"class": "form-input", "placeholder": "customer@example.com"}
            ),
            "customer_phone": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "+1 (555) 000-0000"}
            ),
            "channel": forms.Select(attrs={"class": "form-select"}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "priority": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "initial_message": forms.Textarea(
                attrs={"class": "form-textarea", "rows": 4, "placeholder": "Customer inquiry text"}
            ),
            "resolution_summary": forms.Textarea(
                attrs={"class": "form-textarea", "rows": 3, "placeholder": "Resolution details provided to customer"}
            ),
            "internal_notes": forms.Textarea(
                attrs={"class": "form-textarea", "rows": 3, "placeholder": "Internal staff notes (hidden from customer)"}
            ),
            "is_bot_handled": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "bot_handoff_reason": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "Reason for handoff to human agent"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["customer"].queryset = CustomerAccountProfile.objects.filter(tenant=self.tenant).select_related("customer")
            self.fields["order"].queryset = EcommerceOrder.objects.filter(tenant=self.tenant).select_related("customer")
        self.fields["assigned_agent"].queryset = User.objects.filter(is_active=True).order_by("username")
        self.fields["customer"].required = False
        self.fields["order"].required = False
        self.fields["assigned_agent"].required = False
        self.fields["customer_phone"].required = False
        self.fields["resolution_summary"].required = False
        self.fields["internal_notes"].required = False
        self.fields["bot_handoff_reason"].required = False

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, "customer", self.tenant)
        reject_foreign(self, "order", self.tenant)
        return cleaned
