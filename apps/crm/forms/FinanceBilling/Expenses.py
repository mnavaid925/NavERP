"""CRM 1.7 Finance & Billing Management — Expenses forms (split from apps/crm/forms.py)."""
from apps.crm.forms._common import *  # noqa: F401,F403
from apps.crm.models import (
    Expense,
)


class ExpenseForm(TenantModelForm):
    class Meta:
        model = Expense
        # WARNING: status/submitted_by/approved_by are system-managed and MUST NOT be here —
        # submitted_by is set in the view; status/approved_by only by the
        # @tenant_admin_required approve/reject actions. Accepting them from POST would let any
        # member self-approve an expense.
        fields = ["opportunity", "project", "category", "amount", "currency_code",
                  "expense_date", "is_billable", "description", "receipt"]

    def clean_receipt(self):
        # WARNING: without an extension allowlist + size cap, a member could upload .html/.svg
        # and have it served same-origin from MEDIA_ROOT (stored XSS). Mirrors core.DocumentForm.
        f = self.cleaned_data.get("receipt")
        if f and hasattr(f, "name"):
            ext = os.path.splitext(f.name)[1].lower()
            if ext not in ALLOWED_DOC_EXTENSIONS:
                raise forms.ValidationError(f"File type '{ext}' is not allowed.")
            if getattr(f, "size", 0) and f.size > MAX_UPLOAD_BYTES:
                raise forms.ValidationError("File exceeds the 20 MB limit.")
        return f
