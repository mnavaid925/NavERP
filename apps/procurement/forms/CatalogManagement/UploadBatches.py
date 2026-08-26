"""Procurement 6.9 Catalog Management — CatalogUploadBatch forms.

The upload form is deliberately three fields: the supplier the file belongs to, the file
itself, and free-text notes. Everything else on the batch — status, counters, error log,
validation stamps — is produced by ``validate_and_stage()`` and is editable=False, so no form
can ever write it.
"""
from apps.procurement.forms._common import *  # noqa: F401,F403
from apps.procurement.forms._common import TenantUniqueMixin, _reject_foreign
from apps.procurement.models import CatalogUploadBatch

#: Resource limit (OWASP A05): one catalog file may weigh at most 2 MB on the wire.
MAX_UPLOAD_BYTES = 2 * 1024 * 1024


class CatalogUploadBatchForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = CatalogUploadBatch
        # EXCLUDED and why: ``number`` is assigned by TenantNumbered.save(); original_filename
        # auto-stamps from the uploaded file; status/counters/error_log/validated_* move only
        # through the guarded validate/publish/reject actions.
        fields = ["party", "file", "notes"]
        help_texts = {
            "file": "CSV only (.csv), max 2 MB. Required columns: "
                    "name, supplier_part_no, unit_price, uom_code, category_text.",
        }

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["party"])
        upload = cleaned.get("file")
        if upload is not None and getattr(upload, "name", ""):
            if getattr(upload, "size", 0) and upload.size > MAX_UPLOAD_BYTES:
                self.add_error("file",
                               f"Catalog files are limited to {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")
            name = upload.name.lower()
            if not any(name.endswith(ext) for ext in CatalogUploadBatch.ALLOWED_EXTENSIONS):
                self.add_error("file",
                               "CSV only (.csv) — export Excel/XML to CSV first.")
        return cleaned
