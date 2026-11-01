from django import forms
from django.contrib.auth import get_user_model

from apps.ecommerce.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.ecommerce.models.CustomerProfile.CustomerAccountProfiles import CustomerAccountProfile
from apps.ecommerce.models.CustomerSupport.CustomerSatisfactionSurveys import CustomerSatisfactionSurvey
from apps.ecommerce.models.CustomerSupport.CustomerSupportTickets import CustomerSupportTicket
from apps.ecommerce.models.OrderManagement.EcommerceOrders import EcommerceOrder

User = get_user_model()


class CustomerSatisfactionSurveyForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = CustomerSatisfactionSurvey
        fields = [
            "ticket",
            "order",
            "customer",
            "survey_type",
            "rating_score",
            "sentiment",
            "feedback_comment",
            "agent_rated",
            "follow_up_status",
            "follow_up_notes",
            "reviewed_by",
        ]
        widgets = {
            "ticket": forms.Select(attrs={"class": "form-select"}),
            "order": forms.Select(attrs={"class": "form-select"}),
            "customer": forms.Select(attrs={"class": "form-select"}),
            "survey_type": forms.Select(attrs={"class": "form-select"}),
            "rating_score": forms.NumberInput(attrs={"class": "form-input", "min": 0, "max": 10}),
            "sentiment": forms.Select(attrs={"class": "form-select"}),
            "feedback_comment": forms.Textarea(
                attrs={"class": "form-textarea", "rows": 4, "placeholder": "Shopper feedback details and customer verbatim quotes..."}
            ),
            "agent_rated": forms.Select(attrs={"class": "form-select"}),
            "follow_up_status": forms.Select(attrs={"class": "form-select"}),
            "follow_up_notes": forms.Textarea(
                attrs={"class": "form-textarea", "rows": 3, "placeholder": "Closed-loop detractor recovery action notes..."}
            ),
            "reviewed_by": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["ticket"].queryset = CustomerSupportTicket.objects.filter(tenant=self.tenant)
            self.fields["order"].queryset = EcommerceOrder.objects.filter(tenant=self.tenant).select_related("customer")
            self.fields["customer"].queryset = CustomerAccountProfile.objects.filter(tenant=self.tenant).select_related("customer")
        self.fields["agent_rated"].queryset = User.objects.filter(is_active=True).order_by("username")
        self.fields["reviewed_by"].queryset = User.objects.filter(is_active=True).order_by("username")
        self.fields["ticket"].required = False
        self.fields["order"].required = False
        self.fields["customer"].required = False
        self.fields["agent_rated"].required = False
        self.fields["feedback_comment"].required = False
        self.fields["follow_up_notes"].required = False
        self.fields["reviewed_by"].required = False

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["ticket", "order", "customer"])
        survey_type = cleaned.get("survey_type")
        rating = cleaned.get("rating_score")
        if survey_type in ["ticket_csat", "order_delivery_csat"] and rating is not None:
            if rating < 1 or rating > 5:
                self.add_error("rating_score", "CSAT surveys require a rating score between 1 and 5.")
        elif survey_type == "storefront_nps" and rating is not None:
            if rating < 0 or rating > 10:
                self.add_error("rating_score", "NPS surveys require a rating score between 0 and 10.")
        return cleaned
