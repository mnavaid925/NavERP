"""Projects 7.10 — DocumentTemplate [DTM-]: the standards library (bullet 2).

Realizes bullet **2**. One row per FILE-BACKED standard: the charter template, the project-plan
format, the status-report format, the minutes format, the handover checklist. Deltek PIM calls this
"publishing a template" (a template goes into one or more pools with a version and a comment);
Confluence calls it a page template with a category. Here it is a small tenant-wide register.

**Tenant-wide, with NO project FK — deliberately.** A standard belongs to the PMO, not to one
project; `ProjectDocument.project` is REQUIRED and this model has no project column at all. That
asymmetry is the design, not an oversight: it is what stops "the standard PMO charter format" from
becoming 40 copies of itself, one per project.

**What it is NOT.** It is not the authoring engine: nothing here stamps project data into the
standard (Deltek's merge fields), and `is_format_locked` records an INTENT a human reads — no code
enforces authorship, so no page, label or help text may claim the format is locked. Generating a
document FROM a template, rich-text co-editing and locked formatting are Module 13.1's, and report
formats as generated output are 7.16's.

**Content-only standards live in `KnowledgeEntry.kind="template"`, not here.** This register exists
for artifacts with a file and a publishable version; a written standard that is prose belongs to the
knowledge library (Ruling 4), so the two registers do not both hold "how we write a charter".

**No version chain.** `version` is a CharField the publisher types, and re-publishing edits the row —
a standard is not a controlled project record, so it has no revision chain, no approval and no
retention. Attaching one to a project copies it into the repository as a `ProjectDocument`, where
the chain and the retention then apply to the copy.
"""
from apps.projects.models._base import *  # noqa: F401,F403
from apps.projects.models._base import models, settings


class DocumentTemplate(TenantNumbered):
    NUMBER_PREFIX = "DTM"

    #: Grouped so the register is browsable by what the artifact is FOR. The vocabulary mirrors
    #: `ProjectDocument.DOC_TYPE_CHOICES` where the two overlap on purpose — a template of type
    #: `report` is the format for a document of type `report`.
    CATEGORY_CHOICES = [
        ("charter", "Charter"),
        ("plan", "Plan"),
        ("schedule", "Schedule"),
        ("report", "Report"),
        ("status_update", "Status Update"),
        ("minutes", "Minutes"),
        ("register", "Register"),
        ("checklist", "Checklist"),
        ("other", "Other"),
    ]

    name = models.CharField(max_length=200)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="other")
    #: The document type this standard is used to produce — the same words as the register, so the
    #: register's create page can offer "start from the standard for this type".
    document_type = models.CharField(max_length=20, blank=True)
    description = models.TextField(blank=True)
    #: The published version, typed by the publisher (the Deltek "publish a template" version).
    #: A CharField, not an integer: real template versions read "2026.1" or "v3 (brand refresh)".
    version = models.CharField(max_length=20, default="1.0")
    file = models.FileField(upload_to="projects/templates/%Y/%m/", blank=True, null=True)
    #: VERB-WRITTEN by `dtm_publish` ONLY (a Toggle) — retiring keeps the row readable but takes it
    #: off the "start from this" list.
    is_active = models.BooleanField(default=True)
    #: An INTENT a human reads. Nothing in this sub-module enforces formatting or authorship.
    is_format_locked = models.BooleanField(
        default=False,
        help_text="Records that this format is frozen by policy. It is an intent, not an "
                  "enforcement — authoring and lockdown are Module 13's.")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="owned_document_templates")
    review_on = models.DateField(
        null=True, blank=True, help_text="The date somebody should look at the standard again.")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="+")

    class Meta:
        ordering = ["category", "name", "-id"]
        unique_together = (
            ("tenant", "number"),
            ("tenant", "name", "version"),
        )
        indexes = [
            models.Index(fields=["tenant", "category"], name="dtm_tnt_category_idx"),
            models.Index(fields=["tenant", "is_active"], name="dtm_tnt_active_idx"),
        ]

    def __str__(self):
        return f"{self.number or 'DTM'} — {self.name} v{self.version}"

    @property
    def is_review_due(self):
        """Computed against today rather than stored, so a row cannot go stale in the database."""
        return bool(self.review_on and self.review_on <= timezone.localdate())

    @property
    def status_css(self):
        return "badge-green" if self.is_active else "badge-muted"

    def clean(self):
        super().clean()
        errors = {}

        name = (self.name or "").strip()
        if not name:
            errors["name"] = "A standard needs a name."
        self.name = name
        self.version = (self.version or "").strip() or "1.0"

        if errors:
            raise ValidationError(errors)