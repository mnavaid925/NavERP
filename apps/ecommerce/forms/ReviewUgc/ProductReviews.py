from django import forms
from django.utils import timezone

from apps.ecommerce.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.ecommerce.models.CustomerProfile.CustomerAccountProfiles import CustomerAccountProfile
from apps.ecommerce.models.OrderManagement.EcommerceOrders import EcommerceOrder
from apps.ecommerce.models.ProductCatalog.CatalogProducts import CatalogProduct
from apps.ecommerce.models.ProductCatalog.ProductVariants import ProductVariant
from apps.ecommerce.models.ReviewUgc.ProductReviews import ProductReview


class ProductReviewForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = ProductReview
        fields = [
            "product",
            "variant",
            "customer",
            "order",
            "reviewer_name",
            "reviewer_email",
            "rating",
            "title",
            "body",
            "is_featured",
        ]
        widgets = {
            "product": forms.Select(attrs={"class": "form-select"}),
            "variant": forms.Select(attrs={"class": "form-select"}),
            "customer": forms.Select(attrs={"class": "form-select"}),
            "order": forms.Select(attrs={"class": "form-select"}),
            "reviewer_name": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. Jane Doe"}
            ),
            "reviewer_email": forms.EmailInput(
                attrs={"class": "form-input", "placeholder": "jane@example.com"}
            ),
            "rating": forms.Select(attrs={"class": "form-select"}),
            "title": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. Outstanding craftsmanship and fit"}
            ),
            "body": forms.Textarea(
                attrs={"class": "form-textarea", "rows": 4, "placeholder": "Share detailed impressions of the product..."}
            ),
            "is_featured": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["product"].queryset = CatalogProduct.objects.filter(tenant=self.tenant)
            self.fields["variant"].queryset = ProductVariant.objects.filter(tenant=self.tenant)
            self.fields["customer"].queryset = CustomerAccountProfile.objects.filter(tenant=self.tenant).select_related("customer")
            self.fields["order"].queryset = EcommerceOrder.objects.filter(tenant=self.tenant).select_related("customer")
        self.fields["variant"].required = False
        self.fields["customer"].required = False
        self.fields["order"].required = False

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["product", "variant", "customer", "order"])
        product = cleaned.get("product")
        variant = cleaned.get("variant")
        if variant and product and variant.product_id != product.pk:
            self.add_error("variant", "The selected variant does not belong to the selected product.")
        order = cleaned.get("order")
        product = cleaned.get("product")
        if order and product:
            # Check if order belongs to the same product to grant verified purchase
            if order.lines.filter(product=product).exists():
                self.instance.is_verified_purchase = True
            else:
                self.instance.is_verified_purchase = False
        return cleaned


class ProductReviewModerationForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = ProductReview
        fields = [
            "status",
            "sentiment",
            "is_featured",
            "merchant_response",
            "moderation_note",
        ]
        widgets = {
            "status": forms.Select(attrs={"class": "form-select"}),
            "sentiment": forms.Select(attrs={"class": "form-select"}),
            "is_featured": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "merchant_response": forms.Textarea(
                attrs={"class": "form-textarea", "rows": 3, "placeholder": "Official merchant response..."}
            ),
            "moderation_note": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "Reason for approval, rejection, or spam flagging"}
            ),
        }
