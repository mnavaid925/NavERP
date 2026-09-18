"""Projects 7.10 — ProjectDocumentRevision [PDV-]: one immutable version of one project document.

Realizes bullet **3's revision half**. This module is deliberately a small, strict machine:

**The chain is linear and it only moves forward.** Uploading a revision NEVER moves the parent's
``current_revision_no`` — a new revision lands ``is_approved=False`` and sits behind the current one
until somebody approves it. Approval refuses any revision whose number is at or below the pointer,
which is the single rule that keeps the chain linear; and an older approved revision KEEPS
``is_approved=True`` for ever, because it *was* approved and rewriting that would be a lie. "Only one
version is current" is expressed by the parent's integer pointer landing on exactly one row, never by
un-approving history. (Every one of these invariants is copied verbatim from procurement 6.19, which
paid for them: a re-allocated number once put an unapproved file on the record.)

**Immutability is structural, not a ``save()`` guard.** There is no edit url, no edit view and no
edit template; every column except ``change_note`` is ``editable=False``, so no ``ModelForm`` can
surface one; the only form is ``ProjectDocumentRevisionUploadForm`` and it is create-path only. A
wrong revision is superseded by the next upload, never amended in place.

**The check-out lock is the parent's, not this row's.** 7.10 refuses an upload while the parent is
checked out (models.Documents.clean() is the guard), so "whoever holds the check-out wins" is the
whole conflict-resolution story — there is no merge tool here (13.2 owns branching/redlining).

**There is no ``uploaded_at`` column.** ``TenantOwned.created_at`` IS the upload moment — this row is
created by the upload and by nothing else. Do not invent a second name for the same fact.

**Text extraction is honest about its limits and bounded in three ways.** Text is read from PDFs that
carry a text layer and from plain-text uploads; a scanned image simply has no text to read, and
``extraction_note`` says so on the row rather than leaving a silently empty column that looks like a
bug. The read is capped by pages AND by characters, and it never raises: this runs synchronously
inside a request, on a file somebody uploaded.
"""
import hashlib
import os

from apps.projects.models._base import *  # noqa: F401,F403
from apps.projects.models._base import models, settings


#: Ceiling on stored extracted text. A 400-page specification is worth searching; a whole dictionary
#: of it is a TextField nobody reads and an `icontains` sweep nobody enjoys. The revision's own text
#: and the copy pushed up to the parent are both truncated to this.
EXTRACT_MAX_CHARS = 200_000

#: How many pages of a PDF are parsed at most — the other half of the bound.
MAX_EXTRACT_PAGES = 60

#: Extensions read straight off disk as text. Everything else is either a PDF (handled below) or a
#: format with no text layer to read.
PLAIN_TEXT_EXTENSIONS = {".txt", ".csv", ".md"}

NOTE_UNREADABLE_PATH = "The stored file could not be reached on disk."
NOTE_NO_EXTRACTOR = "PDF text extraction is not installed on this server (pdfplumber)."
NOTE_NO_TEXT_LAYER = ("No text layer to read — a scanned image or a binary document "
                      "(the file is stored and downloadable).")
NOTE_BAD_FILE = "The file could not be read (malformed, encrypted or truncated)."


class ProjectDocumentRevision(TenantOwned):
    #: No number of its own: a revision is identified by its parent's number plus `revision_no`
    #: (the 6.19 shape — a second per-tenant sequence would be a second thing to keep in step).
    document = models.ForeignKey(
        "projects.ProjectDocument", on_delete=models.CASCADE, related_name="revisions")
    revision_no = models.PositiveSmallIntegerField(default=1)
    file = models.FileField(upload_to="projects/documents/%Y/%m/")
    #: SHA-256 of the stored BYTES, taken once at ingest. It is what makes "same file?" answerable
    #: without reading either one, and it is shown on the history panel beside the change note.
    checksum = models.CharField(max_length=64, blank=True, editable=False)
    change_note = models.CharField(
        max_length=255, blank=True, help_text="What changed in this revision.")
    #: VERB-WRITTEN by `pdv_approve` ONLY.
    is_approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="+")
    approved_at = models.DateTimeField(null=True, blank=True, editable=False)
    #: THE TEXT OF RECORD for this revision. The parent carries a denormalized search COPY of
    #: whichever revision it currently points at; `extraction_note` records why a read failed.
    extracted_text = models.TextField(blank=True, editable=False)
    extraction_note = models.CharField(max_length=255, blank=True, editable=False)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="+")

    class Meta:
        ordering = ["-revision_no", "-id"]
        unique_together = (("tenant", "document", "revision_no"),)
        indexes = [
            models.Index(fields=["tenant", "document"], name="pdv_tnt_document_idx"),
        ]

    def __str__(self):
        return f"{self.document.number if self.document_id else 'PDV'} v{self.revision_no}"

    # -- presentation helpers --------------------------------------------------------------------

    @property
    def is_current(self):
        """Number-equality ONLY, deliberately (the 6.19 rule 6).

        The pointer is the authority on "current"; this answers "is this the row the pointer is
        aimed at". Templates guard the green *Current* badge with ``is_current AND is_approved`` —
        do not "unify" the two halves, because both are asserted.
        """
        if not self.document_id:
            return False
        return self.revision_no == self.document.current_revision_no

    @property
    def is_editable(self):
        """Always False, and it says why: immutability is structural."""
        return False

    # -- validation ------------------------------------------------------------------------------

    def clean(self):
        super().clean()
        errors = {}

        if self.revision_no is not None and self.revision_no < 1:
            errors["revision_no"] = "Revision numbers start at 1."

        tenant_id = getattr(self, "tenant_id", None)
        if tenant_id and getattr(self, "document_id", None):
            # Cross-tenant backstop: `_id` FIRST so an unset FK cannot raise
            # RelatedObjectDoesNotExist, and the parent's tenant is compared against ours.
            if getattr(self.document, "tenant_id", None) != tenant_id:
                errors["document"] = "That document belongs to another workspace."
            elif self.is_approved and self.document.is_legal_hold:
                # A hold freezes the record; approving a NEW revision onto a held document would
                # change what the hold is holding.
                errors["is_approved"] = ("This document is under legal hold — a new revision may "
                                         "not be approved onto it.")
            elif self.is_approved and getattr(self.document, "is_archived", False):
                errors["is_approved"] = ("This document is archived — unarchive it before approving "
                                         "a revision onto it.")
            elif not self.pk and getattr(self.document, "is_checked_out", False):
                errors["document"] = (
                    f"That document is checked out by {self.document.checked_out_by or 'another member'}."
                )

        if errors:
            raise ValidationError(errors)

    def delete(self, *args, **kwargs):
        """Refuse to destroy a revision while its parent is under legal hold.

        ``clean()`` is NOT invoked on a delete path, so the hold rule cannot live there — this is the
        mirror of the ``is_approved``-under-hold guard in ``clean()`` above, in the one hook a delete
        actually runs. ``pdv_delete`` guards before it gets here; this layer stops a future caller (or
        an ad-hoc shell) from doing what the view refuses. Queryset deletes (``--flush``,
        ``delete_queryset``) bypass this deliberately — the hold is an in-app control, not a database
        constraint.
        """
        if self.document_id and self.document.is_legal_hold:
            raise ValidationError(
                "This document is under legal hold — a revision may not be deleted from it.")
        return super().delete(*args, **kwargs)


# ------------------------------------------------------------------------------------------------
# Module-level helpers. Both are used by the view verbs and by the seeder; neither reads the chain
# through a prefetched attribute, so a caller that already has the rows pays nothing extra.
# ------------------------------------------------------------------------------------------------

def next_revision_no(document):
    """The number the NEXT revision of ``document`` takes — one past the highest, or 1.

    Deliberately `Max()`-based: revision numbers are never reused, so deleting an unapproved revision
    leaves a gap and the hole is the honest record of what happened.
    """
    if not document or not document.pk:
        return 1
    highest = document.revisions.aggregate(top=Max("revision_no"))["top"] or 0
    return highest + 1


def file_sha256(stored_file):
    """Hex SHA-256 of an uploaded file, streamed a chunk at a time.

    Streamed rather than `read()`-whole because this runs on a file a user just uploaded, and the
    upload-size cap is a policy, not a guarantee about what reaches the view.
    """
    if not stored_file:
        return ""
    digest = hashlib.sha256()
    try:
        for chunk in stored_file.chunks():
            digest.update(chunk)
    except Exception:
        return ""
    finally:
        # Rewind so the same handle can still be saved / re-read by the caller.
        try:
            stored_file.seek(0)
        except Exception:
            pass
    return digest.hexdigest()


def extract_text(stored_file):
    """``(text, note)`` read out of a stored file. **Never raises.**

    Both branches are BOUNDED, not merely non-raising: the plain-text branch reads a fixed prefix and
    the PDF branch stops at `MAX_EXTRACT_PAGES` or as soon as `EXTRACT_MAX_CHARS` is met, freeing each
    page's parse cache as it goes. `pdfplumber` is imported lazily INSIDE the function, so a server
    without it still runs every other page in this sub-module and nothing pays the import cost until
    somebody uploads a PDF.
    """
    if not stored_file:
        return "", NOTE_UNREADABLE_PATH

    # `FieldFile.path` is a property that RAISES on a storage backend with no local path (object
    # storage), so it is read defensively rather than with a bare getattr default.
    try:
        path = stored_file.path
    except Exception:
        path = None
    if not path or not os.path.exists(path):
        return "", NOTE_UNREADABLE_PATH

    extension = os.path.splitext(getattr(stored_file, "name", "") or "")[1].lower()

    if extension in PLAIN_TEXT_EXTENSIONS:
        try:
            with open(path, "rb") as handle:
                # A bounded prefix, not the whole file: the cap is on stored CHARACTERS, so 4 bytes
                # per character is a generous ceiling for any UTF-8 text and keeps a mis-named 2 GB
                # file from becoming a memory event.
                raw = handle.read(EXTRACT_MAX_CHARS * 4)
        except Exception:
            return "", NOTE_BAD_FILE
        # errors="replace": a CSV exported as latin-1 must still be searchable, and one undecodable
        # byte is not a reason to lose the other 200,000 characters.
        text = raw.decode("utf-8", errors="replace")
        if not text.strip():
            return "", NOTE_NO_TEXT_LAYER
        return text[:EXTRACT_MAX_CHARS], ""

    if extension == ".pdf":
        try:
            import pdfplumber
        except ImportError:
            pdfplumber = None
        if pdfplumber is None:
            return "", NOTE_NO_EXTRACTOR
        pieces, budget = [], 0
        try:
            with pdfplumber.open(path) as pdf:
                for index, page in enumerate(pdf.pages):
                    if index >= MAX_EXTRACT_PAGES or budget >= EXTRACT_MAX_CHARS:
                        break
                    piece = page.extract_text() or ""
                    pieces.append(piece)
                    budget += len(piece) + 1
                    page.flush_cache()
        except Exception:          # malformed / encrypted / truncated PDF — a note, not a 500
            return "", NOTE_BAD_FILE
        text = "\n".join(pieces)
        if not text.strip():
            return "", NOTE_NO_TEXT_LAYER
        return text[:EXTRACT_MAX_CHARS], ""

    # An image, an archive, a word-processor binary: accepted by the allow-list, stored, linked and
    # downloadable — simply not readable as text by this server.
    return "", NOTE_NO_TEXT_LAYER