"""HRM 3.25 Personal Information — BankAccountChanges forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    EmployeeBankAccount,
)
from apps.hrm.forms.PersonalInformation._helpers import _ThemedForm


class BankAccountChangeForm(_ThemedForm):
    """Employee proposes a new bank account, or an edit to one of their existing accounts."""

    existing_account = forms.ModelChoiceField(
        queryset=EmployeeBankAccount.objects.none(), required=False,
        empty_label="-- Propose a new account --",
        help_text="Leave blank to add a new account; pick one to edit it.")
    bank_name = forms.CharField(max_length=255)
    account_holder_name = forms.CharField(max_length=255)
    account_number = forms.CharField(max_length=64)
    routing_number = forms.CharField(max_length=20, required=False)
    account_type = forms.ChoiceField(choices=EmployeeBankAccount.ACCOUNT_TYPE_CHOICES)
    split_percentage = forms.DecimalField(max_digits=5, decimal_places=2, required=False,
                                          min_value=0, max_value=100)
    reason = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, employee=None, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        if employee is not None:
            self.fields["existing_account"].queryset = EmployeeBankAccount.objects.filter(
                tenant=tenant, employee=employee).order_by("bank_name")
