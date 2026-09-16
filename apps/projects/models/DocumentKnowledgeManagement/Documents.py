"""Projects 7.10 — ProjectDocument [PDM-]: the project document register + its life-cycle flags.

Realizes bullets **1** (the register, metadata tagging, the "expected" placeholder state),
**3's parent half** (which revision is current, who holds the edit lock) and **5** (retention intent,
archiving, a legal hold that BLOCKS).

**What it is NOT.** Not ``core.Document``: that table is the generic per-record attachment every
module hangs off a ``GenericForeignKey``, and it can carry none of this — no project FK, no doc type,
no status, no owner, a flat ``version`` CharField instead of a chain, and a GFK cannot be
``.filter(tenant=...)``-ed, joined or faceted, which makes it an IDOR surface the moment a register
lists it (procurement 6.19's recorded rejection, inherited here). ``core.Document`` is **not touched**
by this sub-module: no import, no FK, no migration. 7.9's ``DocumentShare`` (which DOES FK
``core.Document``) keeps working untouched and is shown on this page as a read-only lens.

**Real link FKs, deliberately not a GenericForeignKey.** ``milestone`` and ``task`` are declared by
string, so this package imports no sibling app at import time and the register can FACET on them.

**The revision pointer.** ``current_revision_no`` is an INTEGER POINTER (``0`` = nothing approved
yet), never a circular FK — so this module never imports its child model. The one place that resolves
it to a row is :attr:`current_revision`, through the ``revisions`` reverse accessor, and it filters
``is_approved=True``: without that filter a re-allocated number can put an unapproved file on the
record and the register would render a green *Current* badge beside *Not approved*. That was
reproduced three ways in 6.19 and is the reason the filter exists.

**``extracted_text`` is a denormalized SEARCH COPY.** The text of record lives on the approved
revision; this column is refreshed by exactly two writers — the revision-approve verb and the
re-index Run — so one ``icontains`` sweep over the register can match file contents without joining
the revision table on every keystroke. Do not "fix" this into a live join: the copy is the feature.

**The check-out lock is cooperative, and every page says so.** ``is_checked_out`` +
``checked_out_by``/``checked_out_at`` are verb-written by ``pdm_checkout``/``pdm_checkin`` alone. It
is an in-app lock — "somebody in this installation is editing this" — not an OS-level file lock.

**Retention here is an INTENT a human reads, never an action.** ``retention_months`` feeds the
computed ``retain_until``/``is_retention_due``; ``review_on`` feeds ``is_review_due``. Nothing in
7.10 deletes anything on a schedule — automatic destruction and legal-hold ENFORCEMENT are Module
13.9/13.14's (the 6.19 ruling, restated).

**No money column.** A document is not priced; cost lives on 7.4's registers (L29).
"""
from datetime import timedelta

from apps.projects.models._base import *  # noqa: F401,F403
from apps.projects.models._base import models, settings

# The house allow-list, reached through the module that owns it rather than through the package
# re-export (the 6.19 precedent) so the model import graph stays off `core.forms`' entity modules.
from apps.core.forms._common import ALLOWED_DOC_EXTENSIONS as _HOUSE_ALLOWED_DOC_EXTENSIONS


#: The one tag normalizer both 7.10 registers share (`KnowledgeEntry.tags` too), so one tag typed on
#: a document and on a playbook is ONE tag and a facet cannot hold "HVAC" and "hvac" side by side.
def normalize_tags(raw):
    """"Warranty,  HVAC ,warranty" -> "hvac, warranty"."""
    seen, out = set(), []
    for piece in (raw or "").split(","):
        tag = " ".join(piece.split()).strip().lower()
        if tag and tag not in seen:
            seen.add(tag)
            out.append(tag)
    return ", ".join(out)


#: Badge classes that actually exist in `theme.css` (colour-named only — semantic
#: `-success`/`-danger` names do NOT exist, L33).
STATUS_CSS = {
    "draft": "badge-slate",
    "expected": "badge-amber",
    "in_review": "badge-info",
    "approved": "badge-green",
    "superseded": "badge-muted",
    "archived": "badge-muted",
}

#: The repository's upload rules, defined ONCE and applied by every upload path in this sub-module
#: (the revision upload form and the template form), so "what may be stored here" has one answer.
#: The extension list is an allow-list, not a deny-list: a deny-list is a moving target, and every
#: extension not listed is simply not accepted.
#:
#: The house list (`core.forms.ALLOWED_DOC_EXTENSIONS`) is IMPORTED and EXTENDED, never forked: 7.10
#: needs `.ppt`/`.pptx` (a deck is a legitimate project deliverable) and `.md` (plain text, read by
#: the extractor), and adds exactly those three. The previous fork also admitted `.svg` — the one
#: SCRIPTABLE extension the house list deliberately omits — plus `.dwg`/`.dxf`, which no browser
#: renders. Since `/media/` is served unauthenticated with `Content-Disposition: inline`, an `.svg`
#: upload ran script on this origin for any visitor, including anonymous ones.
ALLOWED_FILE_EXTENSIONS = _HOUSE_ALLOWED_DOC_EXTENSIONS | {".ppt", ".pptx", ".md"}

#: 20 MB. The cap is enforced in `validate_upload` and it is deliberately the same number the 6.19
#: repository uses, so the two document shelves cannot disagree about what "too big" means.
MAX_UPLOAD_BYTES = 20 * 1024 * 1024


def upload_extension(uploaded_file):
    """The lower-cased extension of an uploaded file ("" when there is none)."""
    name = getattr(uploaded_file, "name", "") or ""
    dot = name.rfind(".")
    return name[dot:].lower() if dot > -1 else ""


def validate_upload(uploaded_file, label="file"):
    """Return a user-facing error string for an unacceptable upload, or ``None`` when it may pass.

    Never raises, so both forms can call it from ``clean()`` and attach the message to the right
    field. A file with no extension at all is refused: it cannot be typed, previewed or trusted.
    """
    if not uploaded_file:
        return None
    extension = upload_extension(uploaded_file)
    if extension not in ALLOWED_FILE_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_FILE_EXTENSIONS))
        return f"That file type is not accepted here. Allowed: {allowed}."
    size = getattr(uploaded_file, "size", None)
    if size and size > MAX_UPLOAD_BYTES:
        return f"That file is larger than the 20 MB cap ({size // (1024 * 1024)} MB)."
    return None


def purge_stored_files(model, names):
    """Unlink stored payloads that no row of ``model`` references any more; return what went.

    Django never removes a ``FileField``'s bytes when its row goes, so without this every delete
    leaves the payload on disk at a URL the media handler keeps serving — and this sub-module's
    whole point is documents classified ``confidential`` and payloads under legal hold.

    The purge is REFERENCE-COUNTED on purpose: ``pdv_restore`` deliberately re-uploads an older
    revision's file by assigning the SAME ``FieldFile`` (two rows, one path), so a bare
    ``instance.file.delete()`` would blank the payload out from under the surviving row. Call it
    AFTER the row(s) have been deleted, so the row being removed does not count as a reference to
    itself.
    """
    from django.core.files.storage import default_storage

    purged = []
    for name in {candidate for candidate in names if candidate}:
        if model.objects.filter(file=name).exists():
            continue
        default_storage.delete(name)
        purged.append(name)
    return purged


class ProjectDocument(TenantNumbered):
    NUMBER_PREFIX = "PDM"

    DOC_TYPE_CHOICES = [
        ("charter", "Charter"),
        ("plan", "Plan"),
        ("schedule", "Schedule"),
        ("report", "Report"),
        ("status_update", "Status Update"),
        ("minutes", "Minutes"),
        ("specification", "Specification"),
        ("drawing", "Drawing"),
        ("test_result", "Test Result"),
        ("handover", "Handover"),
        ("other", "Other"),
    ]

    #: `expected` is the Deltek PIM *document placeholder*: a named slot created BEFORE the file
    #: arrives, matched on upload, and deletable only while nothing has been issued against it.
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("expected", "Expected"),
        ("in_review", "In Review"),
        ("approved", "Approved"),
        ("superseded", "Superseded"),
        ("archived", "Archived"),
    ]

    #: The `core.Document` vocabulary, reused on purpose: the same three words mean the same three
    #: things wherever a file is classified in this codebase.
    CLASSIFICATION_CHOICES = [
        ("public", "Public"),
        ("internal", "Internal"),
        ("confidential", "Confidential"),
    ]

    #: Statuses in which a document is still live work. The register's default lens and the
    #: retention board both read this rather than repeating the tuple.
    LIVE_STATUSES = ("draft", "expected", "in_review", "approved")
    OPEN_STATUSES = LIVE_STATUSES

    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="documents")
    #: PROTECT — deleting a folder that still holds a document is refused (the 6.19 container rule),
    #: so a document can never be orphaned out of the repository by a folder delete.
    folder = models.ForeignKey(
        "projects.ProjectFolder", on_delete=models.PROTECT, related_name="documents")
    title = models.CharField(max_length=255)
    document_type = models.CharField(max_length=20, choices=DOC_TYPE_CHOICES, default="other")
    classification = models.CharField(
        max_length=20, choices=CLASSIFICATION_CHOICES, default="internal")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="owned_project_documents")
    #: The same normalized CharField both 7.10 registers share — a facet, never a taxonomy table.
    tags = models.CharField(max_length=255, blank=True, help_text="Comma-separated keywords.")
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")

    #: Real link FKs (never a GFK), nullable: the milestone and the task this document evidences.
    milestone = models.ForeignKey(
        "projects.ProjectMilestone", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="documents")
    task = models.ForeignKey(
        "projects.ProjectTask", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="documents")

    #: VERB-WRITTEN by `pdm_checkout`/`pdm_checkin` ONLY — the cooperative single-editor lock.
    is_checked_out = models.BooleanField(default=False)
    checked_out_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="+")
    checked_out_at = models.DateTimeField(null=True, blank=True, editable=False)

    #: RETENTION INTENT — read by the retention board, acted on by nobody in this sub-module.
    retention_months = models.PositiveSmallIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(600)],
        help_text="How long this record is kept, in months. A flag a human reads — nothing in "
                  "7.10 deletes anything on a schedule (Module 13 enforces retention).")
    review_on = models.DateField(
        null=True, blank=True, help_text="The date somebody should look at this again.")

    #: VERB-WRITTEN by `pdm_archive` (a Toggle) and `pdm_hold`/`pdm_release` (a Toggle) ONLY.
    is_archived = models.BooleanField(default=False)
    archived_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="+")
    archived_at = models.DateTimeField(null=True, blank=True, editable=False)
    #: The status the row carried BEFORE `pdm_archive` stamped it ``archived``. Stored rather than
    #: re-derived, because un-archiving used to GUESS ("approved if a revision is current, else
    #: draft") — which brought an ``in_review`` or ``superseded`` document back as **Approved**
    #: with no approval action behind it, overstating the register, its ``?status=`` lens and
    #: ``doc_repository``'s ``approved`` figure.
    pre_archive_status = models.CharField(max_length=20, blank=True, editable=False)
    is_legal_hold = models.BooleanField(
        default=False, help_text="While held, this record may not be archived or deleted.")
    hold_reason = models.CharField(max_length=255, blank=True)
    held_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="+")
    held_at = models.DateTimeField(null=True, blank=True, editable=False)

    #: The integer pointer to the current APPROVED revision (0 = none yet) and the denormalized
    #: search copy of its text. Both are written by the revision verbs, never by a form.
    current_revision_no = models.PositiveSmallIntegerField(default=0, editable=False)
    extracted_text = models.TextField(blank=True, editable=False)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="+")

    class Meta:
        ordering = ["-created_at", "-id"]
        unique_together = (("tenant", "number"),)
        indexes = [
            models.Index(fields=["tenant", "project"], name="pdm_tnt_project_idx"),
            models.Index(fields=["tenant", "folder"], name="pdm_tnt_folder_idx"),
            models.Index(fields=["tenant", "status"], name="pdm_tnt_status_idx"),
            models.Index(fields=["tenant", "document_type"], name="pdm_tnt_type_idx"),
            models.Index(fields=["tenant", "is_archived"], name="pdm_tnt_archived_idx"),
        ]

    def __str__(self):
        return f"{self.number or 'PDM'} — {self.title}"

    # -- derived presentation helpers (never columns) -------------------------------------------

    @property
    def status_css(self):
        return STATUS_CSS.get(self.status, "badge-slate")

    @property
    def tag_list(self):
        return [tag for tag in (self.tags or "").split(", ") if tag.strip()]

    @property
    def is_expected(self):
        """The placeholder state: a named slot waiting for a file."""
        return self.status == "expected"

    @property
    def is_locked(self):
        """"Somebody is editing this right now" — the cooperative check-out."""
        return self.is_checked_out and self.checked_out_at is not None

    @property
    def is_live(self):
        return self.status in self.LIVE_STATUSES

    # -- life-cycle questions, computed against today (a stored flag would go stale) ------------

    @property
    def retain_until(self):
        """The computed retention date: the month window applied to the creation date.

        ``None`` when no window is set — the honest answer, never "today".
        """
        if not self.retention_months or not self.created_at:
            return None
        # 30-day months: this is the figure the register prints, and it must not drift with the
        # calendar (a "1 month" window landing on the 28th in February is not a retention policy).
        return (self.created_at + timedelta(days=30 * self.retention_months)).date()

    @property
    def is_retention_due(self):
        return bool(self.retain_until and self.retain_until <= timezone.localdate())

    @property
    def is_review_due(self):
        return bool(self.review_on and self.review_on <= timezone.localdate())

    @property
    def current_revision(self):
        """The current APPROVED revision, or ``None``.

        Filters ``is_approved=True`` deliberately (the 6.19 rule 5): the pointer is a number, and a
        number alone would let an unapproved upload become "current". Guarded on
        ``current_revision_no`` so an unapproved-only document resolves to ``None`` without a query
        for a row that cannot exist.
        """
        if not self.current_revision_no:
            return None
        return self.revisions.filter(is_approved=True,
                                     revision_no=self.current_revision_no).first()

    # -- validation ------------------------------------------------------------------------------

    def clean(self):
        super().clean()
        errors = {}

        self.tags = normalize_tags(self.tags)
        title = (self.title or "").strip()
        self.title = title

        # A placeholder is created BEFORE the file exists, so it is the one state with nothing to
        # describe yet; every other state is a document somebody has to find by title later.
        if not title and self.status != "expected":
            errors["title"] = "A document needs a title."

        if self.is_legal_hold and self.is_archived:
            errors["is_archived"] = ("A record under legal hold may not be archived — the hold "
                                     "outranks the archive.")

        tenant_id = getattr(self, "tenant_id", None)
        if tenant_id:
            # Cross-tenant backstop on the three tenant-scoped links this row carries. `_id` is
            # tested FIRST so an unset FK cannot raise RelatedObjectDoesNotExist. The narrowed
            # <select> on the form is UX; a crafted POST never goes near it.
            for field, label in (("folder", "folder"), ("milestone", "milestone"), ("task", "task")):
                if getattr(self, f"{field}_id", None):
                    related = getattr(self, field, None)
                    if getattr(related, "tenant_id", None) != tenant_id:
                        errors[field] = f"That {label} belongs to another workspace."
            if self.folder_id and getattr(self, "project_id", None):
                if self.folder.project_id != self.project_id:
                    errors["folder"] = "That folder belongs to another project."

        if errors:
            raise ValidationError(errors)