"""Procurement 6.19 Document & Knowledge Management — ProcurementDocumentRevision.

**What it is.** One version of one :class:`~apps.procurement.models.ProcurementDocument`: the
stored bytes, their checksum, who uploaded them, whether the version was approved, and the text
that was read out of the file at ingest. Bullet **2 Version Control**.

**The chain is linear and it only moves forward.** Uploading a revision NEVER moves the parent's
``current_revision_no`` — a new revision lands ``is_approved=False`` and sits behind the current
one until somebody approves it. That is the literal NavERP bullet: only the latest *approved*
version is the accessible one. Approval refuses any revision whose number is at or below the
pointer, which is the single rule that keeps the chain linear; and an older approved revision
KEEPS ``is_approved=True`` for ever, because it *was* approved and rewriting that would be a lie.
"Only one version is current" is expressed by the parent's integer pointer landing on exactly one
row, never by un-approving history.

**Immutability is structural, not a ``save()`` guard.** There is no edit url, no edit view and no
edit template; every column except ``change_note`` is ``editable=False``, so no ``ModelForm`` can
surface one; the only form is ``ProcurementDocumentRevisionUploadForm`` and it is create-path
only; and the only write after creation is the approve verb's
``save(update_fields=["is_approved", "approved_by", "approved_at"])`` plus the one-shot
extraction stamp at ingest. A wrong revision is superseded by the next upload, never amended in
place, so the stored file always means what it meant when it was approved.

**There is no ``uploaded_at`` column.** ``TenantOwned.created_at`` IS the upload moment — the row
is created by the upload and by nothing else. Templates read ``created_at``; do not invent a
second name for the same fact.

**``extracted_text`` here is the TEXT OF RECORD.** The parent carries a denormalized *search
copy* of whichever revision it currently points at, refreshed by exactly two writers — the
approve verb below and the re-index Run. Do not "fix" the parent into a live join on this table:
the copy is what lets one ``icontains`` sweep over the register match file contents.

**Text extraction is honest about its limits.** Text is read from PDFs that carry a text layer
and from plain-text uploads. A scanned image simply has no text to read, and
``extraction_note`` says so on the row rather than leaving a silently empty column that looks
like a bug. No page, label, help text or empty state in 6.19 claims more than that.
"""
import hashlib
import os

from django.db.models import Max

from apps.procurement.models._base import *  # noqa: F401,F403

# Sibling entity module of this SAME sub-module. The FK below is declared BY STRING, so this
# import exists only for the cross-tenant lookup in ``clean()`` — and it cannot cycle, because
# ``Documents.py`` reaches this file's helpers through a function-local import inside the
# re-index verb and never at module level.
from apps.procurement.models.DocumentKnowledgeManagement.Documents import ProcurementDocument


#: Ceiling on stored extracted text. A 400-page specification is worth searching; a whole
#: dictionary of it is a TextField nobody reads and an ``icontains`` sweep nobody enjoys. Both
#: the revision's own text and the copy pushed up to the parent are truncated to this.
EXTRACT_MAX_CHARS = 200_000

#: Extensions read straight off disk as text. Everything else is either a PDF (handled below) or
#: a format with no text layer to read.
PLAIN_TEXT_EXTENSIONS = {".txt", ".csv"}

#: The four honest outcomes of a read attempt, kept as constants so the view, the templates and
#: the tests all quote the same words and none of them can drift into over-claiming.
NOTE_NO_EXTRACTOR = ("Text extraction is not installed on this server - this file is searchable "
                     "by its title, description and tags only.")
NOTE_UNREADABLE_PATH = "The stored file could not be read back."
NOTE_BAD_FILE = "That file could not be read."
NOTE_NO_TEXT_LAYER = "This file has no text layer, so there is no text to search."


class ProcurementDocumentRevision(TenantOwned):
    """One immutable version of a procurement document's file.

    A child row with no number of its own: it is identified by its parent and its
    ``revision_no``, which is why ``unique_together`` is ``(tenant, document, revision_no)`` and
    why the allocation that assigns it runs under a lock on the PARENT row.
    """

    document = models.ForeignKey("procurement.ProcurementDocument", on_delete=models.CASCADE,
                                 related_name="revisions")
    # Allocated under a select_for_update() lock on the parent document (see
    # ``next_revision_no`` below); the unique_together in Meta is the database backstop for the
    # race the lock is there to prevent.
    revision_no = models.PositiveSmallIntegerField(default=1, editable=False)

    file = models.FileField(
        upload_to="procurement/documents/%Y/%m/",
        help_text="Serve with Content-Disposition: attachment and keep MEDIA_ROOT outside any "
                  "executable path.")
    # The name the browser sent, kept for display only. WARNING: never join this onto a
    # filesystem path — it is attacker-controlled and "../../etc/passwd" is a valid filename to
    # a client. Django's storage layer derives the real path from ``upload_to`` and sanitizes
    # it; this column exists so a person recognises the file they uploaded, nothing more.
    original_filename = models.CharField(max_length=255, blank=True, editable=False)
    file_size = models.PositiveIntegerField(default=0, editable=False)
    # WARNING: this is a CHECKSUM, not tamper-proofing. It is computed once over the bytes that
    # arrived and stored; nothing in 6.19 re-verifies it when the file is served, so it detects
    # accidental corruption and an after-the-fact substitution only if somebody actually
    # re-hashes the stored file and compares. Secure alternative, when integrity has to be
    # ENFORCED rather than recorded: re-hash on read and refuse to serve on a mismatch, and put
    # the bytes in an append-only / object-locked store (13.14) — an ordinary filesystem plus a
    # column in the same database is not a write-once medium, and this page never says it is.
    sha256 = models.CharField(max_length=64, blank=True, editable=False,
                              help_text="Integrity checksum of the stored bytes")

    #: The ONLY user-typed column on this model — everything else is machine-written, which is
    #: what makes the immutability structural rather than a rule somebody has to remember.
    change_note = models.CharField(max_length=255, blank=True,
                                   help_text="What changed in this version, in one line")

    is_approved = models.BooleanField(default=False, editable=False)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, blank=True, editable=False, related_name="+")
    approved_at = models.DateTimeField(null=True, blank=True, editable=False)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, blank=True, editable=False, related_name="+")

    # The text of record — see the module docstring. Written once at ingest and never rewritten
    # here; the parent's copy is what the re-index Run refreshes.
    extracted_text = models.TextField(blank=True, editable=False)
    extraction_note = models.CharField(max_length=255, blank=True, editable=False)

    class Meta:
        ordering = ["-revision_no", "-id"]
        # The database backstop for the allocation race. The lock in ``pdocument_revision_upload``
        # serializes the ordinary path; this constraint is what makes the pathological one
        # (a lock that was not taken, a replica that lagged) an IntegrityError the upload retries
        # rather than two rows both claiming to be r3.
        unique_together = ("tenant", "document", "revision_no")
        indexes = [
            models.Index(fields=["tenant", "document"], name="prc_pdrev_tnt_doc_idx"),
            models.Index(fields=["tenant", "is_approved"], name="prc_pdrev_tnt_appr_idx"),
        ]
        verbose_name = "Procurement Document Revision"
        verbose_name_plural = "Procurement Document Revisions"

    def __str__(self):
        # Guarded on ``document_id``: an UNSAVED instance (an upload form rendering its own
        # validation errors) has no parent attached yet, and reading ``self.document`` would
        # raise RelatedObjectDoesNotExist while trying to draw an error page.
        number = self.document.number if self.document_id else "PDOC"
        return f"{number} r{self.revision_no}"

    @property
    def is_current(self):
        """True when the parent's pointer lands on exactly this revision.

        This — not ``is_approved`` — is what "the accessible version" means. An older approved
        revision keeps ``is_approved=True`` and answers False here, which is precisely the
        distinction the chain badges render (green Current / amber Superseded / muted Pending).
        """
        if not self.document_id:
            return False
        return self.revision_no == self.document.current_revision_no

    def clean(self):
        super().clean()
        errors = {}

        tenant_id = getattr(self, "tenant_id", None)
        if tenant_id and self.document_id:
            # Cross-tenant backstop. Deliberately an explicit VALUES lookup on ``document_id``
            # rather than ``self.document.tenant_id``: the ``_id`` is tested first so an unset FK
            # cannot raise RelatedObjectDoesNotExist, and the lookup asks the database who owns
            # the parent instead of trusting an object that a crafted POST supplied.
            owner_tenant_id = (ProcurementDocument.objects
                               .filter(pk=self.document_id)
                               .values_list("tenant_id", flat=True)
                               .first())
            if owner_tenant_id != tenant_id:
                errors["document"] = "That record belongs to another workspace."

        if errors:
            raise ValidationError(errors)


# ---------------------------------------------------------------------------------------------
# Module-level helpers. All three are pure functions on purpose: the upload view calls them in a
# fixed order (allocate under the lock, checksum before the save, read text after it), and a
# function that can be called from a test without a request is a function whose contract can
# actually be asserted.
# ---------------------------------------------------------------------------------------------


def next_revision_no(document):
    """The number the NEXT revision of ``document`` takes — one past the highest, or 1.

    **Call this only with the parent row already locked.** It is one ``MAX()`` aggregate, so on
    its own it is a read that another uploader can interleave with; what makes the allocation
    safe is the ``select_for_update()`` the caller holds on the document row, which serializes
    every allocation for that document. ``unique_together (tenant, document, revision_no)`` is
    the backstop underneath both.

    ``Max`` is imported at the top of this module rather than taken from
    ``models/_base.py``'s star import, which exports only ``F``, ``Q`` and ``Sum``.
    """
    highest = document.revisions.aggregate(highest=Max("revision_no"))["highest"]
    return (highest or 0) + 1


def file_sha256(upload):
    """Hex SHA-256 of an uploaded file, streamed a chunk at a time.

    Streamed rather than ``upload.read()`` because a 20 MB upload read whole is 20 MB of
    resident memory per concurrent request for no reason.

    The two ``seek(0)`` calls are load-bearing: reading the chunks consumes the file pointer, so
    without the seek AFTERWARDS Django would store a zero-byte file, and without the seek BEFORE
    a caller who already peeked at the upload would checksum only the tail.
    """
    if upload is None:
        return ""
    digest = hashlib.sha256()
    seek = getattr(upload, "seek", None)
    if callable(seek):
        upload.seek(0)
    for chunk in upload.chunks():
        digest.update(chunk)
    if callable(seek):
        upload.seek(0)
    return digest.hexdigest()


def extract_document_text(revision):
    """``(text, note)`` read out of a revision's stored file. **Never raises.**

    Same posture as the 6.13 invoice capture helper it is modelled on: every failure mode comes
    back as ``("", <a sentence a person can act on>)`` rather than a traceback, because this runs
    inside a user-pressed upload and inside the re-index Run, and neither may 500 on a file the
    allow-list already accepted.

    What it can read: PDFs that carry a text layer, and plain-text uploads (``.txt``, ``.csv``).
    What it cannot: a scanned image, a word-processor or spreadsheet binary, an archive. Those
    come back empty with the honest note, and the document stays findable by its title,
    description and tags — which is exactly what the register tells people.

    ``pdfplumber`` is imported lazily INSIDE the function so a server without it still runs every
    other page in this sub-module, and so nothing pays the import cost until somebody uploads a
    PDF.
    """
    stored = getattr(revision, "file", None) if revision is not None else None
    if not stored:
        return "", NOTE_UNREADABLE_PATH

    # ``FieldFile.path`` is a property that RAISES on a storage backend with no local path
    # (object storage), so it is read defensively rather than with a bare getattr default.
    try:
        path = stored.path
    except Exception:
        path = None
    if not path:
        return "", NOTE_UNREADABLE_PATH

    extension = os.path.splitext(getattr(stored, "name", "") or "")[1].lower()

    if extension in PLAIN_TEXT_EXTENSIONS:
        try:
            with open(path, "rb") as handle:
                # Read a bounded prefix, not the whole file: the cap is on stored characters, so
                # 4 bytes per character is a generous ceiling for any UTF-8 text and keeps a
                # mis-named 2 GB file from becoming a memory event.
                raw = handle.read(EXTRACT_MAX_CHARS * 4)
        except Exception:
            return "", NOTE_BAD_FILE
        # errors="replace": a CSV exported as latin-1 must still be searchable, and one
        # undecodable byte is not a reason to lose the other 200,000 characters.
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
        try:
            with pdfplumber.open(path) as pdf:
                text = "\n".join((page.extract_text() or "") for page in pdf.pages)
        except Exception:            # malformed / encrypted / truncated PDF — a note, not a 500
            return "", NOTE_BAD_FILE
        if not (text or "").strip():
            return "", NOTE_NO_TEXT_LAYER
        return text[:EXTRACT_MAX_CHARS], ""

    # An image, an archive, a word-processor binary: accepted by the allow-list, stored, linked
    # and downloadable — simply not readable as text by this server.
    return "", NOTE_NO_TEXT_LAYER
