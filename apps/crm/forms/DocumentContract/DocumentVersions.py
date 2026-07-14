"""CRM 1.9 Document & Contract Management — DocumentVersions forms (split from apps/crm/forms.py)."""
from apps.crm.forms._common import *  # noqa: F401,F403
from apps.crm.models import (
    DocumentVersion,
)


class DocumentVersionForm(TenantModelForm):
    """Upload a contract revision (1.9 File Repository). version_no / contract / body_snapshot /
    created_by are set in the view; this form only takes the uploaded file + a change note."""

    class Meta:
        model = DocumentVersion
        fields = ["file", "change_note"]

    def clean_file(self):
        # Mirror ExpenseForm.clean_receipt — extension allowlist + size cap (blocks .html/.svg XSS).
        f = self.cleaned_data.get("file")
        if f and hasattr(f, "name"):
            ext = os.path.splitext(f.name)[1].lower()
            if ext not in ALLOWED_DOC_EXTENSIONS:
                raise forms.ValidationError(f"File type '{ext}' is not allowed.")
            if getattr(f, "size", 0) and f.size > MAX_UPLOAD_BYTES:
                raise forms.ValidationError("File exceeds the 20 MB limit.")
        return f

    def clean(self):
        # A revision needs at least a file or a note — no empty version rows (code-review).
        cleaned = super().clean()
        if not cleaned.get("file") and not (cleaned.get("change_note") or "").strip():
            raise forms.ValidationError("Provide an uploaded file or a change note (or both).")
        return cleaned
