from django.conf import settings
from django.db import models
from django.urls import reverse

from apps.documents.models._base import TenantNumbered


class DocumentApprovalWorkflow(TenantNumbered):
    NUMBER_PREFIX = "DWF"

    WORKFLOW_TYPE_CHOICES = [
        ("sequential", "Sequential (Step-by-Step)"),
        ("parallel", "Parallel (All Reviewers Simultaneously)"),
        ("conditional", "Conditional (Rules & Criteria Based)"),
        ("hybrid", "Hybrid Multi-Tier"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft Definition"),
        ("pending", "In Progress / Pending Approvals"),
        ("approved", "Fully Approved"),
        ("rejected", "Rejected"),
        ("escalated", "Escalated"),
        ("bypassed", "Emergency Bypassed"),
        ("cancelled", "Cancelled"),
    ]

    URGENCY_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium / Standard"),
        ("high", "High"),
        ("urgent", "Critical / Expedited"),
    ]

    STATUS_CSS = {
        "draft": "badge-slate",
        "pending": "badge-amber",
        "approved": "badge-green",
        "rejected": "badge-red",
        "escalated": "badge-amber",
        "bypassed": "badge-info",
        "cancelled": "badge-muted",
    }

    URGENCY_CSS = {
        "low": "badge-muted",
        "medium": "badge-info",
        "high": "badge-amber",
        "urgent": "badge-red",
    }

    WORKFLOW_TYPE_CSS = {
        "sequential": "badge-info",
        "parallel": "badge-slate",
        "conditional": "badge-amber",
        "hybrid": "badge-green",
    }

    document = models.ForeignKey(
        "documents.Document",
        on_delete=models.CASCADE,
        related_name="approval_workflows",
        db_index=True,
    )
    version = models.ForeignKey(
        "documents.DocumentVersion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approval_workflows",
    )
    title = models.CharField(max_length=255)
    workflow_type = models.CharField(
        max_length=30,
        choices=WORKFLOW_TYPE_CHOICES,
        default="sequential",
        db_index=True,
    )
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="draft",
        db_index=True,
    )
    urgency = models.CharField(
        max_length=20,
        choices=URGENCY_CHOICES,
        default="medium",
        db_index=True,
    )
    current_stage = models.PositiveIntegerField(default=1)
    total_stages = models.PositiveIntegerField(default=1)
    target_turnaround_hours = models.PositiveIntegerField(
        default=48,
        help_text="SLA hours allowed for complete workflow",
    )
    initiator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="initiated_document_workflows",
    )
    department = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="document_approval_workflows",
    )
    due_date = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    requires_all_comments_resolved = models.BooleanField(
        default=True,
        help_text="Blocks final approval until all review comments are marked resolved",
    )
    allow_emergency_bypass = models.BooleanField(
        default=False,
        help_text="Permits authorized managers to bypass remaining approval stages",
    )
    bypass_reason = models.TextField(blank=True)
    bypassed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bypassed_document_workflows",
    )
    definition_json = models.TextField(
        blank=True,
        default="{}",
        help_text="Visual workflow designer serialized JSON node graph",
    )

    class Meta:
        ordering = ["-created_at", "title"]
        verbose_name = "Document Approval Workflow"
        verbose_name_plural = "Document Approval Workflows"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="doc_dwf_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="doc_dwf_tnt_stat_idx"),
            models.Index(fields=["tenant", "document", "status"], name="doc_dwf_tnt_doc_stat_idx"),
            models.Index(fields=["tenant", "initiator"], name="doc_dwf_tnt_init_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.title} ({self.get_status_display()})"

    def get_absolute_url(self):
        return reverse("documents:workflow_detail", kwargs={"pk": self.pk})

    @property
    def status_css_class(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def urgency_css_class(self):
        return self.URGENCY_CSS.get(self.urgency, "badge-muted")

    @property
    def workflow_type_css_class(self):
        return self.WORKFLOW_TYPE_CSS.get(self.workflow_type, "badge-slate")
