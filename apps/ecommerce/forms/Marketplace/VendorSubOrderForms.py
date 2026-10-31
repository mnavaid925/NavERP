from django import forms

from apps.core.forms import TenantModelForm
from apps.ecommerce.forms._common import TenantUniqueMixin
from apps.ecommerce.models.Marketplace.MarketplaceVendors import MarketplaceVendor
from apps.ecommerce.models.Marketplace.VendorPayouts import VendorPayout
from apps.ecommerce.models.Marketplace.VendorSubOrders import VendorSubOrder
from apps.ecommerce.models.OrderManagement.Orders import EcommerceOrder


class VendorSubOrderForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = VendorSubOrder
        exclude = [
            "tenant",
            "number",
            "commission_amount",
            "net_vendor_amount",
            "rated_at",
            "dispute_resolved_at",
            "created_at",
            "updated_at",
        ]
        widgets = {
            "vendor": forms.Select(attrs={"class": "form-select"}),
            "order": forms.Select(attrs={"class": "form-select"}),
            "payout": forms.Select(attrs={"class": "form-select"}),
            "fulfillment_status": forms.Select(attrs={"class": "form-select"}),
            "sla_status": forms.Select(attrs={"class": "form-select"}),
            "payout_status": forms.Select(attrs={"class": "form-select"}),
            "subtotal_amount": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "shipping_amount": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "commission_rate": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "carrier_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. FedEx, DHL, USPS"}),
            "tracking_number": forms.TextInput(attrs={"class": "form-input", "placeholder": "Tracking #"}),
            "tracking_url": forms.URLInput(attrs={"class": "form-input", "placeholder": "https://..."}),
            "promised_dispatch_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "dispatched_at": forms.DateTimeInput(attrs={"class": "form-input", "type": "datetime-local"}),
            "delivered_at": forms.DateTimeInput(attrs={"class": "form-input", "type": "datetime-local"}),
            "customer_rating": forms.NumberInput(attrs={"class": "form-input", "min": 1, "max": 5}),
            "customer_feedback": forms.Textarea(attrs={"class": "form-textarea", "rows": 2}),
            "seller_response": forms.Textarea(attrs={"class": "form-textarea", "rows": 2}),
            "dispute_status": forms.Select(attrs={"class": "form-select"}),
            "dispute_reason": forms.TextInput(attrs={"class": "form-input", "placeholder": "Reason if disputed"}),
            "dispute_notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["vendor"].queryset = MarketplaceVendor.objects.filter(tenant=self.tenant).order_by("store_name")
            self.fields["order"].queryset = EcommerceOrder.objects.filter(tenant=self.tenant).order_by("-created_at")
            self.fields["payout"].queryset = VendorPayout.objects.filter(tenant=self.tenant).order_by("-period_end")


class SubOrderFulfillmentForm(forms.Form):
    fulfillment_status = forms.ChoiceField(
        choices=VendorSubOrder.FULFILLMENT_STATUS_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    carrier_name = forms.CharField(
        max_length=80,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. FedEx Express, UPS, DHL"}),
    )
    tracking_number = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "Tracking Number"}),
    )
    tracking_url = forms.URLField(
        required=False,
        widget=forms.URLInput(attrs={"class": "form-input", "placeholder": "https://..."}),
    )


class SubOrderDisputeForm(forms.Form):
    dispute_status = forms.ChoiceField(
        choices=VendorSubOrder.DISPUTE_STATUS_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    dispute_reason = forms.CharField(
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Damaged package on arrival"}),
    )
    dispute_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Investigation notes, customer statements..."}),
    )


class SubOrderReviewForm(forms.Form):
    customer_rating = forms.IntegerField(
        min_value=1,
        max_value=5,
        widget=forms.NumberInput(attrs={"class": "form-input", "min": 1, "max": 5}),
    )
    customer_feedback = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Feedback regarding seller fulfillment..."}),
    )
    seller_response = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Vendor public response..."}),
    )
