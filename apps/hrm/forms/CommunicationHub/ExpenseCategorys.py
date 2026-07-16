"""HRM 3.27 Communication Hub — ExpenseCategorys forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    ExpenseCategory,
)


class ExpenseCategoryForm(TenantModelForm):
    class Meta:
        model = ExpenseCategory
        fields = ["name", "code", "description", "per_claim_limit", "monthly_limit",
                  "requires_receipt_above", "gl_account_hint", "is_active"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def clean(self):
        cleaned = super().clean()
        for f in ("per_claim_limit", "monthly_limit", "requires_receipt_above"):
            v = cleaned.get(f)
            if v is not None and v < 0:
                self.add_error(f, "Must be zero or greater.")
        return cleaned
