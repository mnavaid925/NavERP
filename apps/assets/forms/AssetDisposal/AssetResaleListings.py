from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model

from apps.accounting.models import FixedAsset
from apps.assets.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.assets.models.AssetDisposal.AssetDisposalRequests import AssetDisposalRequest
from apps.assets.models.AssetDisposal.AssetResaleListings import AssetResaleListing
from apps.core.models import Document, Party

User = get_user_model()


class AssetResaleListingForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = AssetResaleListing
        fields = [
            "disposal_request",
            "fixed_asset",
            "listing_channel",
            "listing_reference",
            "listing_date",
            "closing_date",
            "reserve_price",
            "asking_price",
            "highest_bid_amount",
            "buyer",
            "broker_auctioneer",
            "managed_by",
            "bill_of_sale_document",
            "buyer_contact_name",
            "buyer_contact_email",
            "buyer_contact_phone",
            "gross_sale_proceeds",
            "commission_rate_percent",
            "tax_amount",
            "terms_and_conditions",
        ]
        widgets = {
            "disposal_request": forms.Select(attrs={"class": "form-select"}),
            "fixed_asset": forms.Select(attrs={"class": "form-select"}),
            "listing_channel": forms.Select(attrs={"class": "form-select"}),
            "listing_reference": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. LOT-2026-AUG-8821"}),
            "listing_date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "closing_date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "reserve_price": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "asking_price": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "highest_bid_amount": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "buyer": forms.Select(attrs={"class": "form-select"}),
            "broker_auctioneer": forms.Select(attrs={"class": "form-select"}),
            "managed_by": forms.Select(attrs={"class": "form-select"}),
            "bill_of_sale_document": forms.Select(attrs={"class": "form-select"}),
            "buyer_contact_name": forms.TextInput(attrs={"class": "form-input"}),
            "buyer_contact_email": forms.EmailInput(attrs={"class": "form-input"}),
            "buyer_contact_phone": forms.TextInput(attrs={"class": "form-input"}),
            "gross_sale_proceeds": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "commission_rate_percent": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "tax_amount": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "terms_and_conditions": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "As-is where-is, freight terms, buyer premium stipulations..."}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in ["highest_bid_amount", "gross_sale_proceeds", "commission_rate_percent", "tax_amount"]:
            if f in self.fields:
                self.fields[f].required = False
                if self.fields[f].initial is None:
                    self.fields[f].initial = Decimal("0.00")
        if self.tenant:
            self.fields["disposal_request"].queryset = AssetDisposalRequest.objects.filter(tenant=self.tenant)
            self.fields["fixed_asset"].queryset = FixedAsset.objects.filter(tenant=self.tenant)
            party_qs = Party.objects.filter(tenant=self.tenant)
            self.fields["buyer"].queryset = party_qs
            self.fields["broker_auctioneer"].queryset = party_qs
            self.fields["managed_by"].queryset = User.objects.filter(tenant=self.tenant, is_active=True).order_by("username")
            self.fields["bill_of_sale_document"].queryset = Document.objects.filter(tenant=self.tenant)

    def clean(self):
        cleaned = super().clean()
        for f in ["highest_bid_amount", "gross_sale_proceeds", "commission_rate_percent", "tax_amount"]:
            if cleaned.get(f) is None:
                cleaned[f] = Decimal("0.00")
        reject_foreign(
            self,
            cleaned,
            ["disposal_request", "fixed_asset", "buyer", "broker_auctioneer", "managed_by", "bill_of_sale_document"],
        )
        return cleaned


class AssetResaleBidForm(forms.Form):
    bid_amount = forms.DecimalField(
        max_digits=16,
        decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
        required=True,
    )
    bidder_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "Bidder Company or Individual Name"}),
        required=True,
    )
    bidder_email = forms.EmailField(
        widget=forms.EmailInput(attrs={"class": "form-input"}),
        required=False,
    )
    bidder_phone = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={"class": "form-input"}),
        required=False,
    )


class AssetResaleAcceptForm(forms.Form):
    final_sale_amount = forms.DecimalField(
        max_digits=16,
        decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
        required=True,
    )
    commission_rate_percent = forms.DecimalField(
        max_digits=5,
        decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
        required=False,
        initial=Decimal("0.00"),
    )
    buyer = forms.ModelChoiceField(
        queryset=Party.objects.none(),
        widget=forms.Select(attrs={"class": "form-select"}),
        required=False,
    )
    buyer_contact_name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={"class": "form-input"}),
        required=False,
    )

    def __init__(self, tenant, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tenant = tenant
        if tenant:
            self.fields["buyer"].queryset = Party.objects.filter(tenant=tenant)
