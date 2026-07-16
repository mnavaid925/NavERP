"""core — Document forms (split from apps/core/forms.py)."""
from apps.core.forms._common import *  # noqa: F401,F403
from apps.core.models import (
    Document,
)


class DocumentForm(TenantModelForm):
    class Meta:
        model = Document
        fields = ["file", "name", "classification", "version"]

    def clean_file(self):
        f = self.cleaned_data.get("file")
        if f and hasattr(f, "name"):
            ext = os.path.splitext(f.name)[1].lower()
            if ext not in ALLOWED_DOC_EXTENSIONS:
                raise forms.ValidationError(f"File type '{ext}' is not allowed.")
            if getattr(f, "size", 0) and f.size > MAX_UPLOAD_BYTES:
                raise forms.ValidationError("File exceeds the 20 MB limit.")
        return f
