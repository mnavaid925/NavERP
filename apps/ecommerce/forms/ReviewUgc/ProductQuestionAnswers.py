from django import forms
from django.utils import timezone

from apps.ecommerce.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.ecommerce.models.CustomerProfile.CustomerAccountProfiles import CustomerAccountProfile
from apps.ecommerce.models.ProductCatalog.CatalogProducts import CatalogProduct
from apps.ecommerce.models.ReviewUgc.ProductQuestionAnswers import ProductQuestionAnswer


class ProductQuestionAnswerForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = ProductQuestionAnswer
        fields = [
            "product",
            "author_name",
            "author_email",
            "customer",
            "question_text",
        ]
        widgets = {
            "product": forms.Select(attrs={"class": "form-select"}),
            "author_name": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. Alex Morgan"}
            ),
            "author_email": forms.EmailInput(
                attrs={"class": "form-input", "placeholder": "alex@example.com"}
            ),
            "customer": forms.Select(attrs={"class": "form-select"}),
            "question_text": forms.Textarea(
                attrs={"class": "form-textarea", "rows": 3, "placeholder": "What would you like to know about this item?"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["product"].queryset = CatalogProduct.objects.filter(tenant=self.tenant)
            self.fields["customer"].queryset = CustomerAccountProfile.objects.filter(tenant=self.tenant).select_related("customer")
        self.fields["customer"].required = False

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["product", "customer"])
        return cleaned


class ProductQuestionAnswerResponseForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = ProductQuestionAnswer
        fields = [
            "status",
            "answer_text",
            "answered_by_name",
            "is_staff_answer",
            "is_pinned",
        ]
        widgets = {
            "status": forms.Select(attrs={"class": "form-select"}),
            "answer_text": forms.Textarea(
                attrs={"class": "form-textarea", "rows": 4, "placeholder": "Type official staff answer..."}
            ),
            "answered_by_name": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "Display name of answering agent"}
            ),
            "is_staff_answer": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "is_pinned": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["answer_text"].required = True
