"""Procurement 6.19 Document & Knowledge Management — ProcurementDocument + reminder engine.

**What it is.** The procurement-scoped document repository row: one controlled record (a warranty,
a certificate of insurance, a specification, a statement of work) with a title, a classification,
an owner, life-cycle dates and up to four real links back into the spine — the supplier
``core.Party``, the ``scm.SupplierContract``, the ``scm.PurchaseOrder`` and the
``procurement.SourcingEvent`` it belongs to. Bullets **1 Central Document Repository**,
**2 Version Control** (the parent half) and **5 Full-Text Search & Indexing**.

**What it is NOT.** It is not ``core.Document`` and it does not touch it: that table is the
generic per-record attachment every module hangs off a ``GenericForeignKey``, and it has no
revision chain, no approval, no expiry and no procurement links. It is also not Module 13: folder
hierarchies (13.4), redlining and branching (13.2), permission matrices / watermarking / DRM
(13.7), semantic search and auto-tagging (13.5/13.6) and retention auto-destruction / legal hold
(13.9/13.14) all stay there. ``retention_until`` here is a FLAG a human reads, never an action —
nothing in this sub-module deletes anything on a schedule.

**Four real columns, deliberately not a GenericForeignKey.** A GFK cannot be tenant-filtered at
the queryset level (``.filter(tenant=…)`` cannot reach through ``content_type``/``object_id``),
which makes it an IDOR surface the moment a register lists it; and the register has to FACET on
these links, which a GFK cannot do either. Every cross-app FK is declared **by string** so this
module imports no peer app at import time.

**``current_revision_no`` is an integer pointer, not a circular FK.** ``0`` means "no approved
revision yet". The one place that resolves it to a row is
:attr:`ProcurementDocument.current_revision`, through the ``revisions`` reverse accessor — so
this module never imports its own child model and there is no cycle to unpick.

**``extracted_text`` here is a denormalized SEARCH COPY.** The text of record lives on the
approved ``ProcurementDocumentRevision``; this column is refreshed by exactly two writers — the
revision-approve verb and the re-index verb — so one ``icontains`` sweep over the register can
match file contents without joining the revision table on every keystroke. Do not "fix" this into
a live join: the copy is the feature.

**Text extraction is honest about its limits.** Text is read from PDFs that carry a text layer and
from plain-text uploads. A scanned image has no text to read, and no page, label, help text or
empty state in 6.19 pretends otherwise.

**The reminder engine is module-level, not a fifth model.** There is no scheduler and no mail
worker in this codebase (the 6.3 escalation ruling), so "automated expiry notification" means one
idempotent Run action that raises ``ProcurementAlert`` rows into the 6.1 inbox — see
:func:`run_document_reminders` below.
"""
from datetime import timedelta

from apps.procurement.models._base import *  # noqa: F401,F403

from apps.core.utils import write_audit_log


# ---------------------------------------------------------------------------------------------
# Vocabulary. Defined at module level so the seeder, the views and the reminder engine can read
# it, and ALSO re-exposed on the class below — which is how templates and tests reach it, since
# the *_CHOICES tuples are deliberately NOT hoisted into apps/procurement/models/__init__.py
# (the 6.14/6.15 rule).
# ---------------------------------------------------------------------------------------------

DOC_TYPE_CHOICES = [
    ("quote", "Quote"),
    ("specification", "Specification"),
    ("warranty", "Warranty"),
    ("certificate", "Certificate"),
    ("insurance", "Certificate of Insurance"),
    ("sow", "Statement of Work"),
    ("drawing", "Drawing"),
    ("correspondence", "Correspondence"),
    ("policy", "Policy Document"),
    ("template", "Template"),
    ("other", "Other"),
]

#: The first three are ``core.Document.CLASSIFICATION_CHOICES`` VERBATIM — a procurement document
#: and a generic attachment must not disagree about what "confidential" means. ``restricted`` is
#: the one addition: the tier above confidential, for records only a named few may read.
CLASSIFICATION_CHOICES = [
    ("public", "Public"),
    ("internal", "Internal"),
    ("confidential", "Confidential"),
    ("restricted", "Restricted"),
]

STATUS_CHOICES = [
    ("draft", "Draft"),
    ("active", "Active"),
    ("superseded", "Superseded"),
    ("archived", "Archived"),
]

#: A REGISTER FACET, not a column. Every value maps to a date comparison in the list view's
#: pre-narrow; an unrecognised value skips the filter rather than emptying the register (L11).
EXPIRY_FILTER_CHOICES = [
    ("expiring", "Expiring soon"),
    ("expired", "Expired"),
    ("review_due", "Review due"),
    ("over_retention", "Past retention"),
]

#: "Soon" for the expiring facet and the expiring stat tile.
EXPIRY_WARN_DAYS = 30

#: How far ahead the reminder scan looks. The same 30 days, named separately because the two
#: answer different questions and a later tuning pass should be able to move one without the
#: other.
REMINDER_WINDOW_DAYS = 30

#: Ceiling on one re-index Run, sized to a REQUEST rather than to "a lot of documents". The
#: verb parses files off disk one at a time and a PDF parse runs 0.1-2 s, so 200 rows is 30-400
#: seconds — through both the gunicorn worker timeout (30 s) and nginx proxy_read_timeout
#: (60 s). 25 keeps the worst case inside a request; the Run is repeatable and reports how many
#: candidates remain, which is what makes a small cap the right answer rather than a limitation.
REINDEX_ROW_CAP = 25

#: theme.css ships ONLY badge-green / badge-red / badge-amber / badge-info / badge-muted /
#: badge-slate (L33) — a semantic badge-success/-warning/-danger renders completely unstyled.
STATUS_CSS = {
    "draft": "badge-muted",
    "active": "badge-green",
    "superseded": "badge-amber",
    "archived": "badge-slate",
}
CLASSIFICATION_CSS = {
    "public": "badge-info",
    "internal": "badge-slate",
    "confidential": "badge-amber",
    "restricted": "badge-red",
}


def normalize_tags(raw):
    """``"Warranty, HVAC ,warranty"`` becomes ``"warranty, hvac"``.

    Lower-cased, stripped, de-duplicated, first-seen order preserved, re-joined with ``", "``.
    Tags are a CharField and not a Tag table on purpose: 6.19 owns keyword search and 13.6 owns
    taxonomy. ``KnowledgeResource`` normalizes through this same function, so one tag typed on
    a document and on a guide is one tag.
    """
    seen, out = set(), []
    for tag in (raw or "").split(","):
        tag = tag.strip().lower()
        if tag and tag not in seen:
            seen.add(tag)
            out.append(tag)
    return ", ".join(out)


class ProcurementDocument(TenantNumbered):
    """One controlled procurement record [PDOC-] with a linear approved-revision chain."""

    NUMBER_PREFIX = "PDOC"

    # Re-exposed on the class so views, templates and tests reach the vocabulary through the
    # model rather than through a module path.
    DOC_TYPE_CHOICES = DOC_TYPE_CHOICES
    CLASSIFICATION_CHOICES = CLASSIFICATION_CHOICES
    STATUS_CHOICES = STATUS_CHOICES
    EXPIRY_FILTER_CHOICES = EXPIRY_FILTER_CHOICES
    EXPIRY_WARN_DAYS = EXPIRY_WARN_DAYS
    STATUS_CSS = STATUS_CSS
    CLASSIFICATION_CSS = CLASSIFICATION_CSS

    title = models.CharField(max_length=200)
    doc_type = models.CharField(max_length=16, choices=DOC_TYPE_CHOICES, default="other")
    description = models.TextField(blank=True)
    tags = models.CharField(max_length=255, blank=True, help_text="Comma-separated keywords")
    classification = models.CharField(max_length=14, choices=CLASSIFICATION_CHOICES,
                                      default="internal")
    # Verb-driven and therefore NOT on the form: draft -> active happens when a revision is
    # approved, and supersede/archive are explicit POST-only actions with their own audit rows.
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="draft")

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                              null=True, blank=True,
                              related_name="procurement_documents_owned",
                              help_text="Who is answerable for keeping this document current")
    supplier_visible = models.BooleanField(
        default=False,
        help_text="Vendors may see this in the 6.4 portal when that page ships")

    effective_date = models.DateField(null=True, blank=True)
    expires_on = models.DateField(null=True, blank=True)
    review_on = models.DateField(null=True, blank=True)
    retention_until = models.DateField(
        null=True, blank=True,
        help_text="Hold until this date. Nothing is deleted automatically.")

    # Integer POINTER at the approved revision, not a circular FK. 0 = nothing approved yet.
    current_revision_no = models.PositiveSmallIntegerField(default=0, editable=False)

    # Advisory lock only: it tells the next person somebody is already working on a new
    # revision. It is not an authorization boundary — the upload guard reads it and a tenant
    # admin can force a release, which is exactly what an advisory lock should allow.
    checked_out_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                       null=True, blank=True, editable=False,
                                       related_name="+")
    checked_out_at = models.DateTimeField(null=True, blank=True, editable=False)

    # DENORMALIZED search copy of the current approved revision's text — see the module
    # docstring. Machine-written; never typed, never on a form.
    extracted_text = models.TextField(blank=True, editable=False)

    supplier = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="procurement_documents")
    contract = models.ForeignKey("scm.SupplierContract", on_delete=models.SET_NULL,
                                 null=True, blank=True, related_name="procurement_documents")
    # The SCM order spine (apps/scm/models/ProcurementManagement/PurchaseOrders.py) — never the
    # legacy crm.PurchaseOrder, which is a different table with a different owner.
    purchase_order = models.ForeignKey("scm.PurchaseOrder", on_delete=models.SET_NULL,
                                       null=True, blank=True,
                                       related_name="procurement_documents")
    sourcing_event = models.ForeignKey("procurement.SourcingEvent", on_delete=models.SET_NULL,
                                       null=True, blank=True, related_name="documents")

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                   null=True, blank=True, editable=False, related_name="+")

    class Meta:
        ordering = ["-created_at", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="prc_pdoc_tnt_status_idx"),
            models.Index(fields=["tenant", "doc_type"], name="prc_pdoc_tnt_type_idx"),
            models.Index(fields=["tenant", "expires_on"], name="prc_pdoc_tnt_expiry_idx"),
            # Filtered by the ?expiry=review_due facet and by the review branch of the reminder
            # scan. Without it EXPLAIN reports type=ALL, key=None, rows=2021, Using filesort on
            # both paths — a full tenant scan every time either is used.
            models.Index(fields=["tenant", "review_on"], name="prc_pdoc_tnt_review_idx"),
            models.Index(fields=["tenant", "supplier"], name="prc_pdoc_tnt_sup_idx"),
        ]
        verbose_name = "Procurement Document"
        verbose_name_plural = "Procurement Documents"

    def __str__(self):
        # Guarded on ``number``: an UNSAVED instance (a ModelForm rendering its own errors) has
        # not been through TenantNumbered.save() yet, and a validation page must never read as
        # " · Title".
        return f"{self.number or 'PDOC'} · {self.title}"

    # -- presentation helpers -------------------------------------------------------------

    @property
    def tag_list(self):
        """The normalized tags as a list, for badge rendering."""
        return [tag for tag in (self.tags or "").split(", ") if tag.strip()]

    @property
    def status_css(self):
        return STATUS_CSS.get(self.status, "badge-slate")

    @property
    def classification_css(self):
        return CLASSIFICATION_CSS.get(self.classification, "badge-slate")

    # -- life-cycle questions -------------------------------------------------------------
    # Computed against ``timezone.localdate()`` rather than stored, so a row cannot go stale
    # sitting in the database. The register runs the same comparisons in SQL.

    @property
    def is_expired(self):
        return bool(self.expires_on and self.expires_on < timezone.localdate())

    @property
    def is_expiring(self):
        """Inside the warning window and not yet past it — expired is a different state."""
        if not self.expires_on:
            return False
        today = timezone.localdate()
        return today <= self.expires_on <= today + timedelta(days=EXPIRY_WARN_DAYS)

    @property
    def is_review_due(self):
        return bool(self.review_on and self.review_on <= timezone.localdate())

    @property
    def is_over_retention(self):
        """Past its retention date. A FLAG only — nothing in 6.19 destroys anything."""
        return bool(self.retention_until and self.retention_until < timezone.localdate())

    @property
    def is_checked_out(self):
        # ``_id``, not the object: reading ``self.checked_out_by`` would fetch a user row to
        # answer a question the column already in hand answers.
        return self.checked_out_by_id is not None

    @property
    def current_revision(self):
        """The one approved revision this document currently points at, or ``None``.

        Resolved through the ``revisions`` REVERSE accessor, so this module never imports its
        own child model — the pointer stays an integer and there is no import cycle to unpick.

        ``is_approved=True`` is part of the question, not belt-and-braces. The pointer is only
        ever moved by the approve verb, so the two agree by construction on every path that
        exists today; but a pointer that has been left naming an UNAPPROVED row (a revision
        deleted out from under it and the number re-allocated by the next upload, an admin
        reparent) must not make that row the document of record. Resolving it here means every
        read surface — the detail page, the re-index sweep, and any vendor-portal view that
        later filters ``supplier_visible`` — gets ``None`` and says "no approved revision yet"
        rather than presenting a file nobody approved.
        """
        if not self.current_revision_no:
            return None
        return self.revisions.filter(revision_no=self.current_revision_no,
                                     is_approved=True).first()

    # -- validation -----------------------------------------------------------------------

    def clean(self):
        super().clean()
        errors = {}

        self.tags = normalize_tags(self.tags)

        tenant_id = getattr(self, "tenant_id", None)
        if tenant_id:
            # Cross-tenant backstop on every spine link. The narrowed <select> on the form is
            # UX; a crafted POST never goes near it, and each of these FKs would otherwise pull
            # another workspace's supplier / contract / order / event into this register.
            # ``_id`` is tested FIRST so an unset FK cannot raise RelatedObjectDoesNotExist.
            for field in ("supplier", "contract", "purchase_order", "sourcing_event"):
                if not getattr(self, f"{field}_id", None):
                    continue
                if getattr(getattr(self, field, None), "tenant_id", None) != tenant_id:
                    errors[field] = "That record belongs to another workspace."

        if self.effective_date and self.expires_on and self.expires_on < self.effective_date:
            errors["expires_on"] = "The expiry date cannot be before the effective date."

        if errors:
            raise ValidationError(errors)


# ---------------------------------------------------------------------------------------------
# Expiry / review reminder engine — module-level, NOT a fifth model.
#
# There is NO scheduler and NO mail worker in this codebase (the 6.3 escalation ruling, and the
# 6.8 renewal engine's ruling before it). "Automated notification" here means a user presses Run
# on the register and the scan raises ProcurementAlert rows into the 6.1 Task & Alert Center —
# the alert inbox IS the channel. Re-running is safe: an in-flight alert for the same document
# is skipped rather than duplicated.
# ---------------------------------------------------------------------------------------------


def _alert_link(document_pk):
    """The exact INTERNAL path a document alert carries (6.1 renders hrefs from these).

    ``ProcurementAlert.clean()`` rejects absolute, scheme-relative and backslash-bearing values,
    so this must stay a single-slash same-site path — never a full URL.
    """
    return f"/procurement/documents/{document_pk}/"


def expiring_documents(tenant, *, on=None):
    """Documents whose expiry or review date is inside the reminder window, or already past.

    Returns ``[{"document", "days_left", "reason"}]`` soonest first, where ``reason`` is
    ``"expires"`` or ``"review"`` and ``days_left`` goes negative once the date is behind us.
    Only LIVE documents are scanned: a superseded or archived record has already been dealt
    with, and nagging about it is noise.

    Expiry outranks review on the same row — an expiring warranty is the more urgent fact, and
    one alert per document is the contract the dedupe below depends on.
    """
    if tenant is None:
        return []
    today = on or timezone.localdate()
    horizon = today + timedelta(days=REMINDER_WINDOW_DAYS)
    # NULL dates drop out of the comparison itself (SQL: NULL <= x is never true), which is
    # exactly right — a document with no dates never expires and never comes up for review.
    rows = []
    qs = (ProcurementDocument.objects
          .filter(tenant=tenant, status__in=("draft", "active"))
          .filter(Q(expires_on__lte=horizon) | Q(review_on__lte=horizon))
          # No select_related and no full rows: neither this function nor the engine below
          # reads supplier or owner, and a document carries a machine-written extracted_text
          # that runs to 200,000 characters — 800 in-window rows would be ~24 MB resident to
          # answer a question about two dates. The alert text is built from a freshly locked
          # row, so these columns only have to carry the scan itself and identify the document.
          .only("id", "tenant_id", "number", "title", "status", "expires_on", "review_on")
          .order_by("expires_on", "review_on", "id"))
    for document in qs:
        if document.expires_on is not None and document.expires_on <= horizon:
            rows.append({"document": document,
                         "days_left": (document.expires_on - today).days,
                         "reason": "expires"})
        elif document.review_on is not None and document.review_on <= horizon:
            rows.append({"document": document,
                         "days_left": (document.review_on - today).days,
                         "reason": "review"})
    return rows


def run_document_reminders(tenant, user):
    """Raise one alert per in-window document; idempotent against OPEN duplicates.

    Returns ``{"raised": n, "skipped_open": n}`` — the same shape as the 6.3 escalation engine
    and the 6.8 renewal engine, so all three Run buttons report identically.

    The open-alert set is read ONCE, before the loop, and the row lock is taken only where a
    write is actually going to happen. A second press over an unchanged workspace is therefore
    two queries and no locks rather than four queries per in-window document.

    ``user`` is accepted for signature parity with those engines; the audit row is written by
    :func:`run_document_reminders_audited`, which is what the view verb actually calls.
    """
    from apps.procurement.models import ProcurementAlert

    rows = expiring_documents(tenant)
    if not rows:
        return {"raised": 0, "skipped_open": 0}

    # ONE query for the whole dedupe instead of an EXISTS per row. The button advertises that it
    # is safe to press twice, so the all-skipped path is the COMMON one: a workspace where every
    # in-window document already has an open alert used to cost 4 queries per row (savepoint,
    # locking SELECT, EXISTS, release) and write nothing — ~3,200 of them at 800 documents. It
    # now costs the scan plus this set: two queries, and no row lock is taken where no row will
    # be written. ``link_url`` is this module's own /procurement/documents/<pk>/ path, which is
    # what makes one open-alert set answer the question for every document at once.
    open_links = set(ProcurementAlert.objects
                     .filter(tenant=tenant, kind="deadline",
                             status__in=ProcurementAlert.OPEN_STATUSES)
                     .values_list("link_url", flat=True))

    raised = skipped = 0
    for row in rows:
        document = row["document"]
        link = _alert_link(document.pk)
        if link in open_links:
            skipped += 1
            continue
        # Dedupe is check-then-create, so two concurrent Runs could both find no open alert and
        # both raise. Taking the DOCUMENT row lock makes one document's check+create sequential
        # against every other Run scanning that row (the 6.8 posture, verbatim). The set above
        # is a snapshot taken before the loop, so the authoritative check stays INSIDE the lock
        # — the set removes the queries that would have found nothing, never the guarantee.
        with transaction.atomic():
            locked = (ProcurementDocument.objects.select_for_update()
                      .get(pk=document.pk, tenant=tenant))
            if ProcurementAlert.objects.filter(
                    tenant=tenant, kind="deadline", link_url=link,
                    status__in=ProcurementAlert.OPEN_STATUSES).exists():
                skipped += 1
                continue

            days = row["days_left"]
            if row["reason"] == "expires":
                verb, when = "expires", locked.expires_on
            else:
                verb, when = "is due for review", locked.review_on
            timing = f"{abs(days)} day(s) ago" if days < 0 else f"in {days} day(s)"
            ProcurementAlert.objects.create(
                tenant=tenant,
                kind="deadline",
                # Critical once the date is a week out or already behind us.
                severity="critical" if days <= 7 else "warning",
                status="open",
                title=f"{locked.number} {verb} on {when:%d %b %Y}",
                message=(f"{locked.title} {verb} {timing}. Upload a replacement revision, push "
                         f"the date out, or archive the document if it no longer applies."),
                link_url=link,
                due_at=None,
            )
            raised += 1
        # Recorded only after the transaction that wrote it committed, so a rolled-back attempt
        # cannot make the rest of this Run think an alert exists.
        open_links.add(link)
    return {"raised": raised, "skipped_open": skipped}


@transaction.atomic
def run_document_reminders_audited(tenant, user):
    """Transactional wrapper the view verb calls: run the scan, then write the audit row."""
    summary = run_document_reminders(tenant, user)
    write_audit_log(user, None, "document_reminders_run",
                    {"raised": summary["raised"], "skipped_open": summary["skipped_open"]})
    return summary
