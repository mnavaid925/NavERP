"""Procurement 6.9 Catalog Management — CatalogUploadBatch forms.

The upload form is deliberately three fields: the supplier the file belongs to, the file
itself, and free-text notes. Everything else on the batch — status, counters, error log,
validation stamps — is produced by ``validate_and_stage()`` and is editable=False, so no form
can ever write it.
"""
from apps.procurement.forms._common import *  # noqa: F401,F403
from apps.procurement.forms._common import TenantUniqueMixin, _reject_foreign
from apps.procurement.models.CatalogManagement.UploadBatches import CatalogUploadBatch


class CatalogUploadBatchForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = CatalogUploadBatch
        # EXCLUDED and why: ``number`` is assigned by TenantNumbered.save(); original_filename
        # auto-stamps from the uploaded file; status/counters/error_log/validated_* move only
        # through the guarded validate/publish/reject actions.
        fields = ["party", "file", "notes"]
        help_texts = {
            "file": "CSV (.csv), Excel (.xls/.xlsx) or XML (.xml). CSV columns: "
                    "name, supplier_part_no, unit_price, uom_code, category_text.",
        }

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["party"])
        upload = cleaned.get("file")
        if upload is not None and getattr(upload, "name", ""):
            name = upload.name.lower()
            if not any(name.endswith(ext) for ext in CatalogUploadBatch.ALLOWED_EXTENSIONS):
                self.add_error("file",
                               "Allowed file types: .csv, .xls, .xlsx, .xml.")
        return cleaned
