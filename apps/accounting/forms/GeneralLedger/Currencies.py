"""Accounting 2.2 General Ledger — Currencies forms (split from forms.py/forms_advanced.py)."""
from apps.accounting.forms._common import *  # noqa: F401,F403
from apps.accounting.models import (
    Currency,
)


class CurrencyForm(forms.ModelForm):
    # Currency is global (no tenant) — plain ModelForm, not TenantModelForm.
    class Meta:
        model = Currency
        fields = ["code", "name", "symbol", "is_active"]
        widgets = {
            "code": forms.TextInput(attrs={"class": "form-input"}),
            "name": forms.TextInput(attrs={"class": "form-input"}),
            "symbol": forms.TextInput(attrs={"class": "form-input"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check"}),
        }
