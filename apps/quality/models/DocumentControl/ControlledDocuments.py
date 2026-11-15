from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.quality.models._base import TenantNumbered


class ControlledDocument(TenantNumbered):
    NUMBER_PREFIX = "QDOC"

    DOCUMENT_TYPE_CHOICES = [
        ("sop", "Standard Operating Procedure (SOP)"),
        ("wi", "Work Instruction (WI)"),
        ("policy", "Corporate Policy (POL)"),
        ("manual", "Quality Manual (QM)"),
        ("spec", "Product / Material Specification (SPEC)"),
        ("form", "Form / Template (FORM)"),
        ("protocol", "Validation Protocol / Plan (PROT)"),
        ("record", "Quality Record / Report (REC)"),
    ]

    LIFECYCLE_STATE_CHOICES = [
        ("draft", "Draft"),
        ("in_review", "In Review"),
        ("pending_approval", "Pending Approval"),
        ("approved", "Approved"),
        ("effective", "Effective"),
        ("superseded", "Superseded"),
        ("obsolete", "Obsolete"),
        ("archived", "Archived"),
    ]

    CLASSIFICATION_CHOICES = [
        ("public", "Public"),
        ("internal", "Internal Quality Controlled"),
        ("confidential", "Confidential"),
        ("restricted", "Restricted GxP"),
    ]

    LIFECYCLE_CSS = {
        "draft": "badge-slate",
        "in_review": "badge-amber",
        "pending_approval": "badge-info",
        "approved": "badge-info",
        "effective": "badge-green",
        "superseded": "badge-amber",
        "obsolete": "badge-red",
        "archived": "badge-muted",
    }

    CLASSIFICATION_CSS = {
        "public": "badge-slate",
        "internal": "badge-info",
        "confidential": "badge-amber",
        "restricted": "badge-red",
    }

    DOCUMENT_TYPE_CSS = {
        "sop": "badge-info",
        "wi": "badge-slate",
        "policy": "badge-purple",
        "manual": "badge-blue",
        "spec": "badge-green",
        "form": "badge-slate",
        "protocol": "badge-amber",
        "record": "badge-slate",
    }

    LOCKED_STATES = {"superseded", "obsolete", "archived"}

    title = models.CharField(max_length=255)
    document_type = models.CharField(max_length=24, choices=DOCUMENT_TYPE_CHOICES, default="sop")
    department = models.ForeignKey(
        "core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="controlled_documents"
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="owned_controlled_documents"
    )
    revision = models.CharField(max_length=20, default="1.0")
    is_latest_revision = models.BooleanField(default=True, db_index=True)
    lifecycle_state = models.CharField(max_length=28, choices=LIFECYCLE_STATE_CHOICES, default="draft", db_index=True)
    classification = models.CharField(max_length=24, choices=CLASSIFICATION_CHOICES, default="internal")
    file = models.FileField(upload_to="quality/documents/%Y/%m/", blank=True, null=True)
    description = models.TextField(blank=True)
    change_summary = models.TextField(blank=True)
    effective_date = models.DateField(null=True, blank=True)
    review_interval_months = models.PositiveIntegerField(default=12)
    next_review_date = models.DateField(null=True, blank=True)
    retention_years = models.PositiveIntegerField(default=10)
    supersedes = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="superseded_by_set"
    )
    superseded_by = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="supersedes_set"
    )
    is_template = models.BooleanField(default=False)
    archived_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["-is_latest_revision", "number", "-created_at"]
        verbose_name = "Controlled Document"
        verbose_name_plural = "Controlled Documents"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="quality_qdoc_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "lifecycle_state"], name="idx_qdoc_ten_state"),
            models.Index(fields=["tenant", "document_type"], name="idx_qdoc_ten_dtype"),
            models.Index(fields=["tenant", "is_latest_revision"], name="idx_qdoc_ten_latest"),
            models.Index(fields=["tenant", "effective_date"], name="idx_qdoc_ten_effdate"),
            models.Index(fields=["tenant", "next_review_date"], name="idx_qdoc_ten_revdate"),
            models.Index(fields=["tenant", "title"], name="idx_qdoc_ten_title"),
        ]

    def __str__(self):
        return f"{self.number} Rev {self.revision} - {self.title}"

    @property
    def watermark_text(self):
        watermarks = {
            "draft": "DRAFT",
            "in_review": "IN REVIEW",
            "pending_approval": "PENDING APPROVAL",
            "approved": "APPROVED",
            "effective": "EFFECTIVE - CONTROLLED COPY",
            "superseded": "SUPERSEDED - UNCONTROLLED",
            "obsolete": "OBSOLETE - DO NOT USE",
            "archived": "ARCHIVED",
        }
        return watermarks.get(self.lifecycle_state, "CONTROLLED DOCUMENT")

    @property
    def is_effective(self):
        return self.lifecycle_state == "effective"

    @property
    def is_locked(self):
        return self.lifecycle_state in self.LOCKED_STATES

    @property
    def is_overdue_review(self):
        if self.next_review_date and self.is_effective:
            return self.next_review_date < timezone.now().date()
        return False
