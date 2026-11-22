from django.conf import settings
from django.db import models

from apps.documents.models._base import TenantNumbered


class DocumentBranch(TenantNumbered):
    """Parallel revision stream and what-if scenario tracking with merge-back capabilities."""

    NUMBER_PREFIX = "DBRN"

    BRANCH_TYPE_CHOICES = (
        ("what_if", "What-If Scenario Draft"),
        ("variant", "Regional / Market Variant"),
        ("draft_revision", "Alternative Revision Draft"),
    )

    STATUS_CHOICES = (
        ("active", "Active Branch"),
        ("merged", "Merged into Mainline"),
        ("abandoned", "Abandoned / Closed"),
    )

    MERGE_STRATEGY_CHOICES = (
        ("new_major_version", "Merge as New Major Version"),
        ("new_minor_version", "Merge as New Minor Version"),
        ("replace_content", "Direct Content Overwrite"),
    )

    STATUS_CSS = {
        "active": "badge-amber",
        "merged": "badge-green",
        "abandoned": "badge-muted",
    }

    BRANCH_TYPE_CSS = {
        "what_if": "badge-info",
        "variant": "badge-slate",
        "draft_revision": "badge-amber",
    }

    document = models.ForeignKey(
        "documents.Document",
        on_delete=models.CASCADE,
        related_name="branches",
    )
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    base_version = models.ForeignKey(
        "documents.DocumentVersion",
        on_delete=models.PROTECT,
        related_name="branched_children",
    )
    branch_type = models.CharField(
        max_length=20,
        choices=BRANCH_TYPE_CHOICES,
        default="what_if",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="active",
        db_index=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_document_branches",
    )
    merged_at = models.DateTimeField(null=True, blank=True)
    merged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="merged_document_branches",
    )
    merged_into_version = models.ForeignKey(
        "documents.DocumentVersion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="originating_branch",
    )
    merge_strategy = models.CharField(
        max_length=30,
        choices=MERGE_STRATEGY_CHOICES,
        default="new_major_version",
    )
    merge_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at", "name"]
        verbose_name = "Document Branch"
        verbose_name_plural = "Document Branches"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="doc_dbrn_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "document", "status"], name="idx_dbrn_ten_doc_stat"),
        ]

    def __str__(self):
        return f"{self.name} ({self.document.number}) [{self.get_status_display()}]"

    @property
    def status_badge_class(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def branch_type_badge_class(self):
        return self.BRANCH_TYPE_CSS.get(self.branch_type, "badge-slate")
