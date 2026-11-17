from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.quality.models._base import TenantNumbered


class CapaAction(TenantNumbered):
    NUMBER_PREFIX = "QACT"

    ACTION_TYPE_CHOICES = (
        ("containment", "Containment Action (Immediate)"),
        ("corrective", "Corrective Action (Root Cause Removal)"),
        ("preventive", "Preventive Action (Systemic Prevention)"),
    )

    STATUS_CHOICES = (
        ("pending", "Pending Assignment"),
        ("in_progress", "In Progress"),
        ("implemented", "Implemented / Executed"),
        ("verified", "Verified by Quality"),
        ("cancelled", "Cancelled / Superseded"),
    )

    ACTION_TYPE_CSS = {
        "containment": "badge-amber",
        "corrective": "badge-info",
        "preventive": "badge-purple",
    }

    STATUS_CSS = {
        "pending": "badge-slate",
        "in_progress": "badge-info",
        "implemented": "badge-amber",
        "verified": "badge-green",
        "cancelled": "badge-muted",
    }

    capa = models.ForeignKey(
        "quality.CapaInvestigation",
        on_delete=models.CASCADE,
        related_name="actions"
    )
    root_cause = models.ForeignKey(
        "quality.RootCauseAnalysis",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="actions"
    )
    action_type = models.CharField(max_length=24, choices=ACTION_TYPE_CHOICES, default="corrective", db_index=True)
    title = models.CharField(max_length=255)
    description = models.TextField(help_text="Detailed action instructions, scope, and expected outcome")
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="assigned_capa_actions"
    )
    department = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="capa_actions"
    )
    due_date = models.DateField(db_index=True)
    completion_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default="pending", db_index=True)
    implementation_notes = models.TextField(blank=True, help_text="Summary of actions taken and physical evidence of completion")

    controlled_document = models.ForeignKey(
        "quality.ControlledDocument",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="capa_actions"
    )
    change_order = models.ForeignKey(
        "quality.DocumentChangeOrder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="capa_actions"
    )
    design_project = models.ForeignKey(
        "quality.DesignProject",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="capa_actions"
    )

    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verified_capa_actions"
    )
    verified_on = models.DateField(null=True, blank=True)
    verification_evidence = models.TextField(blank=True, help_text="Independent quality verification notes confirming physical execution")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "CAPA Action"
        verbose_name_plural = "CAPA Actions"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="quality_qact_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "capa"], name="idx_qact_ten_capa"),
            models.Index(fields=["tenant", "action_type"], name="idx_qact_ten_act_type"),
            models.Index(fields=["tenant", "status"], name="idx_qact_ten_status"),
            models.Index(fields=["tenant", "due_date"], name="idx_qact_ten_due_date"),
            models.Index(fields=["tenant", "-created_at"], name="idx_qact_ten_created"),
        ]

    def __str__(self):
        capa_num = self.capa.number if self.capa_id else "Unassigned"
        return f"{self.number or 'New'}: {self.title} ({capa_num})"

    @property
    def action_type_badge(self):
        return self.ACTION_TYPE_CSS.get(self.action_type, "badge-slate")

    @property
    def status_badge(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def is_overdue(self):
        return bool(
            self.due_date
            and self.due_date < timezone.now().date()
            and self.status not in ["implemented", "verified", "cancelled"]
        )

    @property
    def is_verified(self):
        return self.status == "verified" and self.verified_by is not None
