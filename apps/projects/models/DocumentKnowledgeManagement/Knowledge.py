"""Projects 7.10 — KnowledgeEntry [KNE-]: the reusable-insight library (bullet 4).

Realizes bullet **4** — and, for content-only standards, bullet **2's** prose half (Ruling 4). One
row per piece of reusable project guidance: the lesson learned, the retrospective takeaway, the
delivery playbook, the readiness checklist, the worked example, the written standard.

**What it is NOT — and this is the point of the model.** A knowledge entry is CONTENT people read,
not machinery that runs, and it is not a second `lessons_learned` column: 7.5's risk register and
7.6's inspection/defect rows each keep their own `lessons_learned` FIELD on the row where the lesson
was dispositioned (both ruled that at build time). This library is where a lesson becomes FINDABLE
and REUSABLE across projects — the 7.5/7.6 ruling quoted back at itself. Nothing here raises a risk,
opens an issue or schedules a review; no view executes anything stored on this row.

**Also not Module 13.** Wikis and co-authored pages (13.17), semantic search / auto-tagging
(13.5/13.6) and AI summaries (Module 23) stay there. `tags` here is the same normalized CharField the
document register carries — one normalizer, so one tag is one tag — not a taxonomy table.

**The attached artifact is a `ProjectDocument`, deliberately — there is no FileField here.** A
playbook PDF or a scorecard workbook is chosen through the `document` FK, so it goes through the
repository's extension allow-list, size cap, checksum, text read and revision chain. A second upload
path on this model would skip all five and leave the library holding an unversioned copy of a file
that also exists, differently, on a document row. One artifact, one place, one history.

**`usage_count` is a CLICK COUNTER, never a derived metric and never an audit trail.** It counts
presses of the "use this" button and nothing else: it does not know who pressed it, it is not
evidence that a lesson was applied, and it can never be reconciled against anything. Per-user usage
ledgers are Module 13 territory. It is incremented with an atomic ``F("usage_count") + 1`` in the
view verb, so two people opening the same playbook in the same second both count — a
read-modify-write would silently drop one of them.

**`is_featured` is a shelf, not a permission.** It decides what surfaces first on the register —
nothing more. It is not "approved for use", it gates nothing, and no code may branch on it to
authorize a thing. The ordering below puts featured rows first and then falls back to `-created_at`
and the unique `-id`, which is what makes paging deterministic: without the `id` tiebreak two rows
created in the same second could swap places between page 1 and page 2.
"""
from django.core.validators import MaxLengthValidator

from apps.projects.models._base import *  # noqa: F401,F403
from apps.projects.models._base import models, settings

# The tag normalizer is SHARED with the document register on purpose: one tag typed on a document and
# on a playbook has to be the SAME tag, or a facet lists "hvac" twice.
from apps.projects.models.DocumentKnowledgeManagement.Documents import normalize_tags

#: The prose cap. `body` is the one TextField in this sub-module that had no bound at all, while
#: `kne_search` sweeps it with `icontains` — so an unbounded body is an unbounded scan, and it is
#: also what `kne_list`/`kne_search` used to drag off every row. The number matches the document
#: search copy's cap (`EXTRACT_MAX_CHARS`), so the two text columns in 7.10 are bounded identically.
BODY_MAX_CHARS = 200_000


class KnowledgeEntry(TenantNumbered):
    NUMBER_PREFIX = "KNE"

    KIND_CHOICES = [
        ("lesson_learned", "Lesson Learned"),
        ("retrospective", "Retrospective"),
        ("playbook", "Playbook"),
        ("checklist", "Checklist"),
        ("best_practice", "Best Practice"),
        ("template", "Template (content only)"),
        ("standard", "Standard (content only)"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("published", "Published"),
        ("retired", "Retired"),
    ]

    STATUS_CSS = {
        "draft": "badge-slate",
        "published": "badge-green",
        "retired": "badge-muted",
    }

    title = models.CharField(max_length=255)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default="lesson_learned")
    summary = models.CharField(
        max_length=255, blank=True, help_text="One line somebody can scan in the register.")
    body = models.TextField(
        blank=True, validators=[MaxLengthValidator(BODY_MAX_CHARS)],
        help_text="The insight itself, in plain text.")
    category = models.CharField(max_length=120, blank=True)
    #: The same normalized CharField the document register carries — see `normalize_tags`.
    tags = models.CharField(max_length=255, blank=True, help_text="Comma-separated keywords.")
    #: NULLABLE: an insight outlives the project it came from, and SET_NULL is what lets the project
    #: be deleted without destroying the lesson learned on it.
    source_project = models.ForeignKey(
        "projects.Project", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="knowledge_entries")
    #: The artifact behind a playbook/checklist — a repository document, never a second upload path.
    document = models.ForeignKey(
        "projects.ProjectDocument", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="knowledge_entries")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="owned_knowledge_entries")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    review_on = models.DateField(
        null=True, blank=True, help_text="The date somebody should re-read this.")
    #: A CLICK COUNTER (see the module docstring) — incremented atomically by `kne_use`.
    usage_count = models.PositiveIntegerField(default=0, editable=False)
    #: A SHELF, never a permission.
    is_featured = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="+")

    class Meta:
        # Featured first — that IS the shelf — then newest, then the unique id. The id tiebreak is
        # not decoration: `-is_featured, -created_at` alone leaves rows created in the same second in
        # an order the database is free to choose per query, and an unstable sort under a Paginator
        # silently repeats one row on page 2 while dropping another entirely.
        ordering = ["-is_featured", "-created_at", "-id"]
        unique_together = (("tenant", "number"),)
        indexes = [
            models.Index(fields=["tenant", "kind"], name="kne_tnt_kind_idx"),
            models.Index(fields=["tenant", "status"], name="kne_tnt_status_idx"),
            # Serves the shelf query (tenant + is_featured + status) and the featured facet.
            models.Index(fields=["tenant", "is_featured"], name="kne_tnt_feat_idx"),
        ]

    def __str__(self):
        # Guarded on `number`: an UNSAVED instance (a ModelForm rendering its own errors) has not
        # been through TenantNumbered.save() yet, and a validation page must never read " · Title".
        return f"{self.number or 'KNE'} · {self.title}"

    # -- presentation helpers --------------------------------------------------------------------

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def tag_list(self):
        """The normalized tags as a list, for badge rendering — identical to the document's because
        the two columns are normalized by the same function."""
        return [tag for tag in (self.tags or "").split(", ") if tag.strip()]

    @property
    def is_review_due(self):
        """Computed against today rather than stored, so a row cannot go stale in the database."""
        return bool(self.review_on and self.review_on <= timezone.localdate())

    # -- validation ------------------------------------------------------------------------------

    def clean(self):
        super().clean()
        errors = {}

        self.tags = normalize_tags(self.tags)
        title = (self.title or "").strip()
        if not title:
            errors["title"] = "A knowledge entry needs a title."
        self.title = title

        # A library row with neither prose nor an artifact is an empty card nobody can use, so it is
        # refused up front rather than shipped as an unsearchable stub.
        if not (self.summary or "").strip() and not (self.body or "").strip() and not self.document_id:
            errors["summary"] = ("Give the entry a summary, some body text, or a document — "
                                 "otherwise there is nothing to read.")

        tenant_id = getattr(self, "tenant_id", None)
        if tenant_id and getattr(self, "document_id", None):
            # Cross-tenant backstop on the one tenant-scoped link this model carries: the narrowed
            # <select> on the form is UX, and a crafted POST never goes near it. `_id` is tested
            # FIRST so an unset FK cannot raise RelatedObjectDoesNotExist.
            if getattr(self.document, "tenant_id", None) != tenant_id:
                errors["document"] = "That document belongs to another workspace."

        if errors:
            raise ValidationError(errors)