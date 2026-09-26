"""Form definitions for CPQQuote model, approval actions, and portal signing."""
from decimal import Decimal
from django import forms
from apps.sales.forms._common import TenantModelForm
from apps.sales.models.QuoteProposalCPQ.CPQQuotes import CPQQuote
from apps.crm.models import Opportunity, PriceBook, DocTemplate
from apps.core.models import Party
from apps.accounting.models import Currency
from apps.accounts.models import User


class CPQQuoteForm(TenantModelForm):
    """Form to create and edit CPQQuote headers."""

    class Meta:
        model = CPQQuote
        fields = [
            "name",
            "opportunity",
            "account",
            "contact",
            "price_book",
            "currency",
            "valid_until",
            "is_primary",
            "header_discount_pct",
            "proposal_template",
            "terms_and_conditions",
            "notes",
            "owner",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g., Enterprise Software & Hardware Package"}),
            "opportunity": forms.Select(attrs={"class": "form-select"}),
            "account": forms.Select(attrs={"class": "form-select"}),
            "contact": forms.Select(attrs={"class": "form-select"}),
            "price_book": forms.Select(attrs={"class": "form-select"}),
            "currency": forms.Select(attrs={"class": "form-select"}),
            "valid_until": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "is_primary": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "header_discount_pct": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0", "max": "100"}),
            "proposal_template": forms.Select(attrs={"class": "form-select"}),
            "terms_and_conditions": forms.Textarea(attrs={"class": "form-textarea", "rows": 4, "placeholder": "Payment terms, SLA guarantees, validity terms..."}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Internal deal notes..."}),
            "owner": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        if self.tenant:
            self.fields["opportunity"].queryset = Opportunity.objects.filter(tenant=self.tenant)
            self.fields["account"].queryset = Party.objects.filter(tenant=self.tenant)
            self.fields["contact"].queryset = Party.objects.filter(tenant=self.tenant)
            self.fields["price_book"].queryset = PriceBook.objects.filter(tenant=self.tenant, is_active=True)
            self.fields["currency"].queryset = Currency.objects.filter(is_active=True)
            self.fields["proposal_template"].queryset = DocTemplate.objects.filter(tenant=self.tenant)
            self.fields["owner"].queryset = User.objects.filter(tenant=self.tenant, is_active=True)

        # Only a tenant admin may hand a quote to someone else; for anyone else the
        # owner is pinned to themselves and the field is disabled, matching
        # AccountPlanForm. Ownership is an assignment right, not a free-text field.
        if user is not None and not (
            getattr(user, "is_superuser", False) or getattr(user, "is_tenant_admin", False)
        ):
            self.fields["owner"].queryset = User.objects.filter(
                pk=user.pk, tenant=self.tenant, is_active=True
            )
            self.fields["owner"].disabled = True
            if not self.instance.pk:
                self.initial["owner"] = user.pk

        if "header_discount_pct" in self.fields:
            self.fields["header_discount_pct"].required = False

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("header_discount_pct") is None:
            cleaned_data["header_discount_pct"] = Decimal("0.00")
        # Belt and braces: a disabled field still arrives in cleaned_data, so pin it
        # back to the acting user rather than trusting the posted value.
        if self.user is not None and not (
            getattr(self.user, "is_superuser", False) or getattr(self.user, "is_tenant_admin", False)
        ):
            cleaned_data["owner"] = self.user
        return cleaned_data


class CPQQuoteApprovalActionForm(forms.Form):
    """Manager form for approving or rejecting a CPQQuote."""

    ACTION_CHOICES = [
        ("approved", "Approve Quote"),
        ("rejected", "Reject / Request Revision"),
    ]

    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        widget=forms.RadioSelect(attrs={"class": "form-radio"}),
    )
    note = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            "class": "form-textarea",
            "rows": 3,
            "placeholder": "Provide feedback or reason for rejection/approval...",
        }),
    )

    def clean(self):
        cleaned_data = super().clean()
        action = cleaned_data.get("action")
        note = cleaned_data.get("note", "").strip()
        if action == "rejected" and not note:
            self.add_error("note", "A reason note is required when rejecting a quote.")
        return cleaned_data


class CPQPortalSignForm(forms.Form):
    """Public customer portal acceptance and e-signature form."""

    signer_name = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "Full Legal Name"}),
    )
    signer_title = forms.CharField(
        max_length=120,
        widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g., VP of Procurement / CTO"}),
    )
    signer_email = forms.EmailField(
        widget=forms.EmailInput(attrs={"class": "form-input", "placeholder": "name@company.com"}),
    )
    signature_data = forms.CharField(
        widget=forms.TextInput(attrs={"class": "form-input font-serif text-lg", "placeholder": "Type full signature"}),
    )
    agree_terms = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        label="I confirm I am authorized to bind my organization to this commercial proposal and accept all stated terms.",
    )
