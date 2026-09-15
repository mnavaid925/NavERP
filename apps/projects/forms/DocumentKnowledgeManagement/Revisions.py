"""Projects 7.10 — ProjectDocumentRevision forms.

``ProjectDocumentRevisionUploadForm`` is the ONE form in this sub-module that can write a revision,
and it is create-path only — the chain's immutability is structural (models.Revisions docstring), so
there is no edit form, no edit url and no edit template anywhere for a revision.

**What the form carries and what it deliberately does not.** ``document``, ``file`` and
``change_note``. Everything else is assigned by the view in the same transaction that saves the row:
``revision_no`` comes from :func:`next_revision_no` (one past the highest — a deleted unapproved
revision leaves a gap and the gap is the honest record), ``checksum`` from
:func:`file_sha256`, ``extracted_text``/``extraction_note`` from :func:`extract_text`,
``uploaded_by`` from ``request.user`` and ``is_approved`` stays False — an upload NEVER moves the
pointer or approves itself (6.19's first invariant).

**The lock is refused here, not only in the view.** A document that is checked out accepts no
upload: "whoever holds the check-out wins" has to be true in the model layer too, not just in the
button's ``disabled`` attribute.

**The upload rules come from the register model** — ``validate_upload`` (extension allow-list + the
20 MB cap) is the SAME function the template form calls, so the two upload paths cannot disagree
about what "storable" means.
"""
from django.core.exceptions import ValidationError

from apps.projects.forms._common import *  # noqa: F401,F403
from apps.projects.forms._common import TenantModelForm, TenantUniqueMixin, _reject_foreign
from apps.projects.models import ProjectDocumentRevision
from apps.projects.models.DocumentKnowledgeManagement.Documents import validate_upload


class ProjectDocumentRevisionUploadForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = ProjectDocumentRevision
        fields = ["document", "file", "change_note"]

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

        _reject_foreign(self, cleaned, ["document"])

        document = cleaned.get("document")
        if document is not None and document.is_locked:
            holder = document.checked_out_by.get_username() if document.checked_out_by else "somebody"
            self.add_error(
                "file",
                f"That document is checked out by {holder} — check it in first, then upload the "
                f"next revision.")

        return cleaned