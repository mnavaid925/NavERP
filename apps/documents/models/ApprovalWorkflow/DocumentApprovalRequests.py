from django.conf import settings
from django.db import models
from django.urls import reverse

from apps.documents.models._base import TenantNumbered


class DocumentApprovalRequest(TenantNumbered):
    NUMBER_PREFIX = "DAPR"

    STAGE_TYPE_CHOICES = [
        ("sequential", "Sequential Step"),
        ("parallel_all", "Parallel - Unanimous (All Must Approve)"),
        ("parallel_first", "Parallel - First to Respond"),
        ("peer_review", "Peer Review & Critique"),
        ("final_signoff", "Final Executive Sign-Off"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending Action"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("delegated", "Delegated to Peer"),
        ("escalated", "Escalated on Timeout"),
        ("bypassed", "Bypassed"),
        ("cancelled", "Cancelled"),
    ]

    STATUS_CSS = {
        "pending": "badge-amber",
        "approved": "badge-green",
        "rejected": "badge-red",
        "delegated": "badge-info",
        "escalated": "badge-amber",
        "bypassed": "badge-slate",
        "cancelled": "badge-muted",
    }

    STAGE_TYPE_CSS = {
        "sequential": "badge-info",
        "parallel_all": "badge-slate",
        "parallel_first": "badge-amber",
        "peer_review": "badge-info",
        "final_signoff": "badge-green",
    }

    workflow = models.ForeignKey(
        "documents.DocumentApprovalWorkflow",
        on_delete=models.CASCADE,
        related_name="approval_requests",
        db_index=True,
    )
    stage_number = models.PositiveIntegerField(default=1, db_index=True)
    stage_name = models.CharField(max_length=120, default="Review & Approval")
    stage_type = models.CharField(
        max_length=30,
        choices=STAGE_TYPE_CHOICES,
        default="sequential",
    )
    order = models.PositiveIntegerField(default=1)
    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="document_approval_requests",
    )
    approver_role = models.ForeignKey(
        "accounts.Role",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="document_approval_requests",
    )
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="pending",
        db_index=True,
    )
    decision_comments = models.TextField(blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    due_date = models.DateTimeField(null=True, blank=True)

    # Delegation fields
    delegated_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="delegated_document_approval_requests",
    )
    delegation_reason = models.TextField(blank=True)
    delegated_at = models.DateTimeField(null=True, blank=True)

    # Escalation fields
    is_escalated = models.BooleanField(default=False, db_index=True)
    escalated_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="escalated_document_approval_requests",
    )
    escalation_reason = models.TextField(blank=True)
    escalated_at = models.DateTimeField(null=True, blank=True)

    # Notification & Reminders
    reminder_sent_count = models.PositiveIntegerField(default=0)
    last_reminder_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["workflow", "stage_number", "order", "-created_at"]
        verbose_name = "Document Approval Request"
        verbose_name_plural = "Document Approval Requests"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="doc_dapr_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="doc_dapr_tnt_stat_idx"),
            models.Index(fields=["tenant", "approver", "status"], name="doc_dapr_tnt_appr_stat_idx"),
            models.Index(fields=["tenant", "delegated_to", "status"], name="doc_dapr_tnt_dlg_stat_idx"),
            models.Index(fields=["tenant", "workflow", "stage_number"], name="doc_dapr_tnt_wf_stg_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.workflow.title} [Stage {self.stage_number}: {self.approver.username}] ({self.get_status_display()})"

    def get_absolute_url(self):
        return reverse("documents:approval_request_detail", kwargs={"pk": self.pk})

    @property
    def status_css_class(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def stage_type_css_class(self):
        return self.STAGE_TYPE_CSS.get(self.stage_type, "badge-slate")
