"""HRM 3.27 Communication Hub — ExpenseClaimLines forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    ExpenseClaimLine,
)
from apps.hrm.forms.CandidateManagement._helpers import _validate_upload


class ExpenseClaimLineForm(TenantModelForm):
    # claim / tenant are set by the view; multipart for the receipt upload.
    class Meta:
        model = ExpenseClaimLine
        fields = ["category", "expense_date", "merchant", "description", "amount", "receipt"]
        widgets = {"description": forms.Textarea(attrs={"rows": 2})}

    def clean_amount(self):
        amount = self.cleaned_data.get("amount")
        if amount is not None and amount <= 0:
            raise forms.ValidationError("Amount must be greater than zero.")
        return amount

    def clean_receipt(self):
        return _validate_upload(self.cleaned_data.get("receipt"),
                                allowed_ext=ALLOWED_ONBOARDING_DOC_EXTENSIONS,
                                max_bytes=MAX_ONBOARDING_DOC_BYTES, label="Receipt")
