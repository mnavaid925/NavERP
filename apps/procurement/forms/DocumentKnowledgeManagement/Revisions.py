"""Procurement 6.19 Document & Knowledge Management — the revision upload form.

One shape, ``ProcurementDocumentRevisionUploadForm``, and it is the ONLY way bytes enter this
sub-module. Two fields — the file and a one-line change note — because a revision is immutable
and every other column on the model is machine-written:

* ``document`` — comes from the URL pk, **never a POST field**. A ``<select>`` of documents here
  would let a crafted POST attach a revision to a record the uploader was never shown, and the
  upload view already fetched and tenant-scoped the parent before this form is even built.
* ``revision_no`` — allocated by the view under a ``select_for_update()`` lock on the parent.
  A number chosen by the client is a number two clients can choose at once.
* ``original_filename`` / ``file_size`` / ``sha256`` — measured from the upload itself.
* ``is_approved`` / ``approved_by`` / ``approved_at`` — the approve verb's stamp, gated on a
  tenant administrator. A form field would let an upload approve itself and skip the gate.
* ``extracted_text`` / ``extraction_note`` — read off the stored file, never typed.
* ``uploaded_by`` — an authorship stamp, not an input.
* ``tenant`` — stamped by ``TenantUniqueMixin`` and re-stamped by the view.
* ``created_at`` / ``updated_at`` — the ``TenantOwned`` base timestamps (L22). ``created_at`` IS
  the upload moment; there is no second column for it.

**There is no edit form and no edit view.** A wrong revision is superseded by the next upload,
never amended in place — the ``CostForecast`` / ``SpendReportSnapshot`` exemption. This class is
create-path only, which is why it is named ``…UploadForm`` rather than ``…Form``.
"""
from apps.procurement.forms._common import *  # noqa: F401,F403
from apps.procurement.forms._common import TenantUniqueMixin
# NOT-YET-WIRED entity of this SAME sub-module: import the entity MODULE directly, never
# ``from apps.procurement.models import X`` — the sub-package is not wired until the Integrator
# lands it, and a package-level re-export would be a star-import cycle at URLconf import time.
from apps.procurement.models.DocumentKnowledgeManagement.Revisions import (
    ProcurementDocumentRevision)


class ProcurementDocumentRevisionUploadForm(TenantUniqueMixin, TenantModelForm):
    """Upload the next version of a document's file.

    ``TenantUniqueMixin`` comes FIRST so ``instance.tenant`` is stamped before ``full_clean()``
    runs: ``ProcurementDocumentRevision.clean()`` compares the parent document's owning tenant
    against ``self.tenant_id``, and without the stamp every upload would be falsely rejected as
    cross-tenant.

    There is no ``__init__`` narrowing pass here and that is not an omission — the form carries
    no ``ModelChoiceField`` at all, so there is no queryset to scope. The one FK this model has,
    ``document``, is supplied by the view from the URL after its own tenant-scoped fetch.
    """

    class Meta:
        model = ProcurementDocumentRevision
        fields = ["file", "change_note"]
        widgets = {
            "change_note": forms.TextInput(
                attrs={"class": "form-input",
                       "placeholder": "e.g. Renewed cover through 2027, section 4 rewritten"}),
        }

    def clean_file(self):
        """Extension allow-list, then size cap. The house rule for every upload in this app.

        WARNING — why the two constants are imported HERE and not at module level:
        ``apps/procurement/forms/CatalogManagement/UploadBatches.py`` defines its OWN
        ``MAX_UPLOAD_BYTES`` (2 MB, for a CSV catalogue import). If either constant were pulled
        through ``apps.procurement.forms``, which limit applied to a document revision would
        depend on package import order — a size cap that changes with the wind is not a control.
        The function-local import from ``apps.core.forms._common`` names the 20 MB document
        limit and the 13-extension document allow-list unambiguously, exactly as
        ``ReceiptDiscrepancies.clean_evidence`` and ``SupplierInvoices`` do.

        WARNING — the allow-list is the mitigation for the storage layout, not a formality.
        ``MEDIA_ROOT`` is ``BASE_DIR / "media"``, which on this deployment sits under the web
        server's document root, so anything stored there is reachable as a same-origin URL. The
        allow-list admits no ``.php``, no ``.html``, no ``.htm`` and no ``.svg``, which is what
        keeps an upload from executing on the server or scripting on this origin. Secure
        alternative for production, stated on the model's ``file`` help_text as well: move
        ``MEDIA_ROOT`` outside any executable path and serve every media response with
        ``Content-Disposition: attachment`` and ``X-Content-Type-Options: nosniff``. Never render
        an uploaded file inline — the templates link to it and let the browser decide.

        The extension is not proof of content and this is not pretending otherwise: it is the
        cheap first gate, and the file is never executed, never interpreted and never embedded.
        """
        import os

        from apps.core.forms._common import ALLOWED_DOC_EXTENSIONS, MAX_UPLOAD_BYTES

        upload = self.cleaned_data.get("file")
        if upload and hasattr(upload, "name"):
            ext = os.path.splitext(upload.name)[1].lower()
            if ext not in ALLOWED_DOC_EXTENSIONS:
                raise forms.ValidationError(f"File type '{ext}' is not allowed.")
            if getattr(upload, "size", 0) and upload.size > MAX_UPLOAD_BYTES:
                raise forms.ValidationError(
                    f"File exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit.")
        return upload
