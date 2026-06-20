"""Accounting forms. Every form extends ``apps.core.forms.TenantModelForm`` so FK dropdowns
auto-scope to the active tenant, theme widget classes apply, and date fields round-trip (L22).

Excluded from EVERY form (set by the view / derived — never user-editable, per L22 + CLAUDE.md
mass-assignment rules): ``tenant``, auto ``number``, the ``*_at``/``*_by`` system fields, the
posting ``journal_entry`` link, ``normal_balance`` and all stored ``subtotal``/``tax_total``/
``total``/``line_total`` aggregates. Those are ``editable=False`` on the model, so simply listing
the user fields here keeps them out.
"""
from django import forms
from django.forms import inlineformset_factory

from apps.core.forms import TenantModelForm
from apps.core.models import Party

from .models import (
    BankAccount,
    BankTransaction,
    Bill,
    BillLine,
    Currency,
    CustomerProfile,
    ExchangeRate,
    FiscalPeriod,
    GLAccount,
    Invoice,
    InvoiceLine,
    JournalEntry,
    JournalLine,
    Payment,
    PaymentAllocation,
    PaymentTerm,
    ReconciliationMatch,
    VendorProfile,
)


def _active_currencies(form):
    """Constrain any ``currency`` field to active currencies (Currency is global, so the
    TenantModelForm base does not scope it)."""
    if "currency" in form.fields:
        form.fields["currency"].queryset = Currency.objects.filter(is_active=True)


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


class ExchangeRateForm(TenantModelForm):
    class Meta:
        model = ExchangeRate
        fields = ["currency", "rate_date", "rate", "source"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _active_currencies(self)


class GLAccountForm(TenantModelForm):
    class Meta:
        model = GLAccount
        fields = ["code", "name", "account_type", "parent", "is_active", "description"]


class FiscalPeriodForm(TenantModelForm):
    class Meta:
        model = FiscalPeriod
        # `status` is intentionally EXCLUDED — a period is opened on create (model default) and
        # only ever transitions to closed via the @tenant_admin_required `fiscal_period_close`
        # action. Leaving it on this @login_required edit form would let any member close/lock a
        # period and bypass the admin gate (code-review finding).
        fields = ["name", "period_type", "start_date", "end_date"]


class JournalEntryForm(TenantModelForm):
    class Meta:
        model = JournalEntry
        # status/posted_at/created_by/approved_by/reversal_of are controlled by the action views.
        fields = ["entry_type", "entry_date", "description", "reference", "fiscal_period"]


class JournalLineForm(TenantModelForm):
    class Meta:
        model = JournalLine
        fields = ["gl_account", "debit", "credit", "description", "party", "org_unit",
                  "currency", "amount_foreign", "exchange_rate"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _active_currencies(self)


class PaymentTermForm(TenantModelForm):
    class Meta:
        model = PaymentTerm
        fields = ["name", "days_due", "discount_pct", "discount_days", "is_active"]


class VendorProfileForm(TenantModelForm):
    class Meta:
        model = VendorProfile
        fields = ["party", "payment_terms", "default_expense_account", "currency", "is_1099",
                  "is_active", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _active_currencies(self)
        if self.tenant is not None:
            self.fields["party"].queryset = (
                Party.objects.filter(tenant=self.tenant, roles__role="vendor").distinct()
            )


class CustomerProfileForm(TenantModelForm):
    class Meta:
        model = CustomerProfile
        fields = ["party", "payment_terms", "credit_limit", "ar_account", "currency",
                  "credit_on_hold", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _active_currencies(self)
        if self.tenant is not None:
            self.fields["party"].queryset = (
                Party.objects.filter(tenant=self.tenant, roles__role="customer").distinct()
            )


class BankAccountForm(TenantModelForm):
    class Meta:
        model = BankAccount
        fields = ["name", "account_number_last4", "bank_name", "currency", "gl_account",
                  "opening_balance", "opening_balance_date", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _active_currencies(self)


class InvoiceForm(TenantModelForm):
    class Meta:
        model = Invoice
        fields = ["kind", "party", "payment_terms", "issue_date", "due_date", "status",
                  "currency", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _active_currencies(self)
        if self.tenant is not None:
            self.fields["party"].queryset = (
                Party.objects.filter(tenant=self.tenant, roles__role="customer").distinct()
            )


class InvoiceLineForm(TenantModelForm):
    class Meta:
        model = InvoiceLine
        fields = ["description", "quantity", "unit_price", "tax_rate_pct", "gl_account"]


class BillForm(TenantModelForm):
    class Meta:
        model = Bill
        fields = ["party", "payment_terms", "bill_date", "due_date", "status", "currency",
                  "document", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _active_currencies(self)
        if self.tenant is not None:
            self.fields["party"].queryset = (
                Party.objects.filter(tenant=self.tenant, roles__role="vendor").distinct()
            )


class BillLineForm(TenantModelForm):
    class Meta:
        model = BillLine
        fields = ["description", "quantity", "unit_price", "tax_rate_pct", "gl_account"]


class PaymentForm(TenantModelForm):
    class Meta:
        model = Payment
        fields = ["direction", "party", "bank_account", "payment_method", "payment_date",
                  "amount", "currency", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _active_currencies(self)


class PaymentAllocationForm(TenantModelForm):
    class Meta:
        model = PaymentAllocation
        fields = ["payment", "invoice", "bill", "allocated_amount", "discount_taken"]


class BankTransactionForm(TenantModelForm):
    class Meta:
        model = BankTransaction
        fields = ["bank_account", "transaction_date", "description", "amount", "direction",
                  "source", "external_ref"]


class ReconciliationMatchForm(TenantModelForm):
    class Meta:
        model = ReconciliationMatch
        fields = ["bank_transaction", "payment", "journal_line", "is_confirmed"]


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


# Inline line-item formsets (create + edit share these). ``form_kwargs={'tenant': ...}`` is passed
# by the view so each child form scopes its own FK dropdowns to the tenant.
JournalLineFormSet = inlineformset_factory(
    JournalEntry, JournalLine, form=JournalLineForm, extra=2, can_delete=True,
)
InvoiceLineFormSet = inlineformset_factory(
    Invoice, InvoiceLine, form=InvoiceLineForm, extra=2, can_delete=True,
)
BillLineFormSet = inlineformset_factory(
    Bill, BillLine, form=BillLineForm, extra=2, can_delete=True,
)
