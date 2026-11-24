from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.documents.models._base import TenantNumbered


class DocumentProcessInstance(TenantNumbered):
    """Live BPM process execution instance with node telemetry and process mining trace."""

    NUMBER_PREFIX = "DPIN"

    STATUS_CHOICES = (
        ("queued", "Queued"),
        ("running", "Running / Active"),
        ("waiting_approval", "Waiting on Approval"),
        ("waiting_timer", "Waiting on Timer"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
        ("sla_breached", "SLA Breached"),
    )

    STATUS_CSS = {
        "queued": "badge-slate",
        "running": "badge-info",
        "waiting_approval": "badge-amber",
        "waiting_timer": "badge-amber",
        "completed": "badge-green",
        "failed": "badge-red",
        "cancelled": "badge-muted",
        "sla_breached": "badge-red",
    }

    process_definition = models.ForeignKey(
        "documents.DocumentProcessDefinition",
        on_delete=models.PROTECT,
        related_name="instances",
    )
    document = models.ForeignKey(
        "documents.Document",
        on_delete=models.CASCADE,
        related_name="process_instances",
    )
    version = models.ForeignKey(
        "documents.DocumentVersion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="process_instances",
    )
    triggered_by_rule = models.ForeignKey(
        "documents.DocumentRoutingRule",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="triggered_instances",
    )
    approval_workflow = models.ForeignKey(
        "documents.DocumentApprovalWorkflow",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bpm_process_instances",
    )
    department = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dms_process_instances",
    )
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="initiated_dms_process_instances",
    )
    current_assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_dms_process_instances",
    )
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="queued",
        db_index=True,
    )
    current_node_id = models.CharField(max_length=80, blank=True)
    current_node_label = models.CharField(max_length=160, blank=True)
    started_at = models.DateTimeField(default=timezone.now, editable=False)
    due_at = models.DateTimeField(null=True, blank=True, editable=False)
    completed_at = models.DateTimeField(null=True, blank=True, editable=False)
    cycle_time_minutes = models.PositiveIntegerField(null=True, blank=True, editable=False)
    rework_count = models.PositiveSmallIntegerField(default=0, editable=False)
    is_sla_breached = models.BooleanField(default=False, editable=False, db_index=True)
    is_conformant = models.BooleanField(default=True, editable=False)
    variant_signature = models.CharField(max_length=500, blank=True, editable=False)
    step_trace_json = models.JSONField(default=list, blank=True)
    context_variables_json = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ["-started_at", "-id"]
        verbose_name = "Document Process Instance"
        verbose_name_plural = "Document Process Instances"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="doc_dpin_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="doc_dpin_tnt_sts_idx"),
            models.Index(fields=["tenant", "process_definition"], name="doc_dpin_tnt_prc_idx"),
            models.Index(fields=["tenant", "document"], name="doc_dpin_tnt_doc_idx"),
            models.Index(fields=["tenant", "is_sla_breached"], name="doc_dpin_tnt_sla_idx"),
            models.Index(fields=["tenant", "-started_at"], name="doc_dpin_tnt_str_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.process_definition.code} ({self.get_status_display()})"

    @property
    def status_badge(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def sla_badge(self):
        if self.is_sla_breached or self.status == "sla_breached":
            return "badge-red"
        return "badge-green"

    @property
    def conformance_badge(self):
        return "badge-green" if self.is_conformant else "badge-amber"

    @property
    def step_count(self):
        return len(self.step_trace_json) if isinstance(self.step_trace_json, list) else 0

    @property
    def duration_display(self):
        if self.cycle_time_minutes is None:
            return "In Progress"
        hours, mins = divmod(self.cycle_time_minutes, 60)
        if hours:
            return f"{hours}h {mins}m"
        return f"{mins}m"
