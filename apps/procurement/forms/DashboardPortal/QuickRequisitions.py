"""Procurement 6.1 User Dashboard & Portal — Quick Requisition form.

**Quick Requisition Entry** bullet: a fast-track, ONE-screen form for frequent low-value or
catalog purchases. It is deliberately a plain ``Form``, not a ModelForm over
``scm.PurchaseRequisition`` + its line formset: the fast track is exactly ONE line by definition,
and the view (not the user) assembles the header + line pair inside one transaction before handing
off to 4.1's requisition detail page for submit/approve.

The spine stays scm's (L36) — this module declares no requisition table of its own.
"""
from decimal import Decimal

from django import forms
from django.core.validators import MaxValueValidator

from apps.accounting.models import Currency, GLAccount
from apps.core.models import OrgUnit

from apps.procurement.forms._common import *  # noqa: F401,F403
from apps.procurement.forms._common import _reject_foreign

#: Ceilings mirroring scm.PurchaseRequisitionLine's Decimal(14,4)/(14,2) columns — without an
#: upper bound a huge crafted value passes validation here and dies as a driver DataError 500
#: at save time instead of a field error.
MAX_QTY = Decimal("9999999999.9999")
MAX_PRICE = Decimal("999999999999.99")


class QuickRequisitionForm(forms.Form):
    """Everything the fast track asks for — one item, one price, one need-by date."""

    title = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={"class": "form-input",
                                      "placeholder": "e.g. Office printer paper — monthly"}),
        help_text="A short name the approval inbox will recognise")
    item_description = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={"class": "form-input",
                                      "placeholder": "What exactly is being bought"}))
    quantity = forms.DecimalField(
        min_value=0.0001, initial=1, decimal_places=4,
        validators=[MaxValueValidator(MAX_QTY)],
        widget=forms.NumberInput(attrs={"class": "form-input", "step": "any", "min": "0"}))
    estimated_unit_price = forms.DecimalField(
        min_value=0, initial=0, decimal_places=2, required=False,
        validators=[MaxValueValidator(MAX_PRICE)],
        widget=forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
        help_text="Best known unit price; 0 if unknown")
    uom_hint = forms.CharField(max_length=32, required=False,
                               widget=forms.TextInput(attrs={"class": "form-input",
                                                             "placeholder": "each / box / kg"}))
    sku_hint = forms.CharField(max_length=64, required=False,
                               widget=forms.TextInput(attrs={"class": "form-input",
                                                             "placeholder": "Catalog / vendor code"}),
                               help_text="Optional — vendor or catalog code")
    currency = forms.ModelChoiceField(
        queryset=Currency.objects.none(), required=False, empty_label="Workspace default",
        help_text="Leave blank for the default currency")
    gl_account = forms.ModelChoiceField(queryset=GLAccount.objects.none(), required=False,
                                        empty_label="— Unassigned —",
                                        help_text="Expense account to charge")
    org_unit = forms.ModelChoiceField(queryset=OrgUnit.objects.none(), required=False,
                                      empty_label="— None —",
                                      help_text="Requesting department / cost centre")
    required_by = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-input"}, format="%Y-%m-%d"),
        help_text="When it must arrive")
    justification = forms.CharField(required=False, widget=forms.Textarea(attrs={
        "class": "form-textarea", "rows": 3, "placeholder": "Why this purchase is needed"}))

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tenant = tenant
        # Tenant scoping is done BY HAND here because this is a plain Form — TenantModelForm's
        # automatic scoping does not apply. Both targets carry a tenant FK, so an unscoped
        # dropdown would offer every workspace's rows to a crafted POST.
        self.fields["currency"].queryset = Currency.objects.filter(is_active=True)
        if tenant is not None:
            self.fields["gl_account"].queryset = (GLAccount.objects
                                                  .filter(tenant=tenant, is_active=True)
                                                  .order_by("code", "name"))
            self.fields["org_unit"].queryset = OrgUnit.objects.filter(tenant=tenant).order_by("name")

    def clean(self):
        cleaned = super().clean()
        # Same crafted-POST re-check as every ModelChoiceField this form renders: the scoped
        # <select> is UX; a hand-posted foreign pk must land as a field error, not a leak.
        _reject_foreign(self, cleaned, ["gl_account", "org_unit"])
        return cleaned
