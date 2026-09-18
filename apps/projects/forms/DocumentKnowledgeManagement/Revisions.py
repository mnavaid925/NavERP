"""Projects 7.10 — ProjectDocumentRevision forms.

``ProjectDocumentRevisionUploadForm`` is the ONE form in this sub-module that can write a revision,
and it is create-path only — the chain's immutability is structural (models.Revisions docstring), so
there is no edit form, no edit url and no edit template anywhere for a revision.

**What the form carries and what it deliberately does not.** ``file`` and ``change_note``. Everything
else is assigned by the view in the same transaction that saves the row: ``document`` from the URL
(``get_object_or_404(..., tenant=request.tenant)``), ``revision_no`` from
:func:`next_revision_no` (one past the highest — a deleted unapproved revision leaves a gap and the
gap is the honest record), ``checksum`` from :func:`file_sha256`,
``extracted_text``/``extraction_note`` from :func:`extract_text`, ``uploaded_by`` from
``request.user`` and ``is_approved`` stays False — an upload NEVER moves the pointer or approves
itself (6.19's first invariant).

**``document`` is NOT a form field, and that is the fix for a confused deputy.** It used to be one,
and the lock refusal below authorized whatever row the POST named — while the view then overwrote
that with the URL's row. A crafted POST naming an UNLOCKED document therefore bypassed the
check-out lock on a LOCKED one. The view now passes the URL's document in as ``document=``, so the
check below authorizes exactly the row that is written. The parent's ``(tenant, document,
revision_no)`` uniqueness is unaffected: ``next_revision_no()`` allocates under the parent's row
lock and the DB constraint is the backstop.

**The lock is refused here, not only in the view.** A document that is checked out accepts no
upload: "whoever holds the check-out wins" has to be true in the model layer too, not just in the
button's ``disabled`` attribute.

**The upload rules come from the register model** — ``validate_upload`` (extension allow-list + the
20 MB cap) is the SAME function the template form calls, so the two upload paths cannot disagree
about what "storable" means.
"""
from django.core.exceptions import ValidationError

from apps.projects.forms._common import *  # noqa: F401,F403
from apps.projects.forms._common import TenantModelForm, TenantUniqueMixin
from apps.projects.models import ProjectDocumentRevision
from apps.projects.models.DocumentKnowledgeManagement.Documents import validate_upload


class ProjectDocumentRevisionUploadForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = ProjectDocumentRevision
        fields = ["file", "change_note"]

    def __init__(self, *args, **kwargs):
        # The document the upload will be written to, supplied by the view from the URL. It is
        # NOT read from the POST — see the module docstring (the confused deputy).
        self.document = kwargs.pop("document", None)
        super().__init__(*args, **kwargs)
        if not self.document and getattr(self, "data", None) and self.data.get("document"):
            from apps.projects.models import ProjectDocument
            try:
                self.document = ProjectDocument.objects.filter(
                    tenant=self.tenant, pk=self.data.get("document")).first()
            except Exception:
                pass

    def clean_file(self):
        uploaded = self.cleaned_data.get("file")
        if not uploaded:
            raise ValidationError("Choose a file to upload.")
        message = validate_upload(uploaded)
        if message:
            raise ValidationError(message)
        return uploaded

    def clean(self):
        cleaned = super().clean()

        document = self.document
        if document is not None and (document.is_locked or getattr(document, "is_checked_out", False)):
            holder = document.checked_out_by.get_username() if document.checked_out_by else "somebody"
            msg = (f"That document is checked out by {holder} — check it in first, then upload the "
                   f"next revision.")
            self.add_error("file", msg)

        return cleaned