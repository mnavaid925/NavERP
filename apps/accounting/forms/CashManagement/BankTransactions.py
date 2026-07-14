"""Accounting 2.5 Cash Management — BankTransactions forms (split from forms.py/forms_advanced.py)."""
from apps.accounting.forms._common import *  # noqa: F401,F403
from apps.accounting.models import (
    BankAccount,
    BankTransaction,
)


class BankTransactionForm(TenantModelForm):
    class Meta:
        model = BankTransaction
        # `source` EXCLUDED — a manual entry must not be self-labelled "bank_feed"/"csv_import"
        # (audit-trail integrity, security review M1). Model default "manual" applies on create;
        # the CSV importer sets "csv_import" explicitly.
        fields = ["bank_account", "transaction_date", "description", "amount", "direction",
                  "external_ref"]


class CsvImportForm(forms.Form):
    """Bank-statement CSV upload (2.5). Columns: date, description, amount, direction."""

    bank_account = forms.ModelChoiceField(queryset=BankAccount.objects.none(),
                                           widget=forms.Select(attrs={"class": "form-select"}))
    csv_file = forms.FileField(widget=forms.ClearableFileInput(attrs={"class": "form-input", "accept": ".csv"}))

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        if tenant is not None:
            self.fields["bank_account"].queryset = BankAccount.objects.filter(tenant=tenant)

    def clean_csv_file(self):
        f = self.cleaned_data.get("csv_file")
        if f and not f.name.lower().endswith(".csv"):
            raise forms.ValidationError("Only .csv files are allowed.")
        if f and getattr(f, "size", 0) > 5 * 1024 * 1024:
            raise forms.ValidationError("File exceeds the 5 MB limit.")
        return f
