from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.quality.models._base import TenantNumbered


class ManagementReviewAction(TenantNumbered):
    NUMBER_PREFIX = "QMRA"

    ACTION_TYPE_CHOICES = [
        ("qms_improvement", "QMS Continual Improvement"),
        ("product_improvement", "Product Quality / Safety Enhancement"),
        ("resource_allocation", "Resource & Infrastructure Allocation"),
        ("capa_initiation", "Formal CAPA Initiation"),
        ("procedure_revision", "SOP / Quality Plan Revision"),
        ("training_competency", "Training & Education Initiative"),
        ("regulatory_filing", "Regulatory Notification / Filing"),
    ]

    PRIORITY_CHOICES = [
        ("critical", "Critical"),
        ("high", "High"),
        ("medium", "Medium"),
        ("low", "Low"),
    ]

    STATUS_CHOICES = [
        ("open", "Open"),
        ("in_progress", "In Progress"),
        ("pending_verification", "Pending QA Verification"),
        ("completed", "Verified & Closed"),
        ("cancelled", "Cancelled / Superseded"),
    ]

    ACTION_TYPE_CSS = {
        "qms_improvement": "badge-green",
        "product_improvement": "badge-info",
        "resource_allocation": "badge-amber",
        "capa_initiation": "badge-red",
        "procedure_revision": "badge-slate",
        "training_competency": "badge-info",
        "regulatory_filing": "badge-amber",
    }

    PRIORITY_CSS = {
        "critical": "badge-red",
        "high": "badge-amber",
        "medium": "badge-info",
        "low": "badge-slate",
    }

    STATUS_CSS = {
        "open": "badge-info",
        "in_progress": "badge-amber",
        "pending_verification": "badge-amber",
        "completed": "badge-green",
        "cancelled": "badge-slate",
    }

    management_review = models.ForeignKey(
        "quality.ManagementReview",
        on_delete=models.CASCADE,
        related_name="actions",
    )
    title = models.CharField(max_length=255)
    action_type = models.CharField(max_length=32, choices=ACTION_TYPE_CHOICES, default="qms_improvement", db_index=True)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default="medium", db_index=True)
    description = models.TextField()

    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="assigned_management_actions",
    )
    due_date = models.DateField(db_index=True)
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default="open", db_index=True)
    budget_allocated = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    spawned_capa = models.ForeignKey(
        "quality.CapaInvestigation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="spawned_management_actions",
    )
    spawned_change_order = models.ForeignKey(
        "quality.DocumentChangeOrder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="spawned_management_actions",
    )

    completion_date = models.DateField(null=True, blank=True)
    resolution_summary = models.TextField(blank=True)

    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verified_management_actions",
    )
    verification_notes = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["due_date", "-created_at"]
        verbose_name = "Management Review Action"
        verbose_name_plural = "Management Review Actions"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="qmra_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "management_review"], name="idx_qmra_ten_mrv"),
            models.Index(fields=["tenant", "status"], name="idx_qmra_ten_status"),
            models.Index(fields=["tenant", "priority"], name="idx_qmra_ten_pri"),
            models.Index(fields=["tenant", "due_date"], name="idx_qmra_ten_duedate"),
            models.Index(fields=["tenant", "-created_at"], name="idx_qmra_ten_created"),
            models.Index(fields=["tenant", "status", "due_date"], name="idx_qmra_ten_stat_due"),
        ]

    def __str__(self):
        return f"{self.number} — {self.title} ({self.get_priority_display()})"

    @property
    def is_overdue(self):
        return self.status in ["open", "in_progress", "pending_verification"] and self.due_date < timezone.now().date()

    @property
    def days_open(self):
        end = self.completion_date or timezone.now().date()
        start = self.created_at.date() if self.created_at else timezone.now().date()
        return (end - start).days

    @property
    def action_type_badge_class(self):
        return self.ACTION_TYPE_CSS.get(self.action_type, "badge-info")

    @property
    def priority_badge_class(self):
        return self.PRIORITY_CSS.get(self.priority, "badge-muted")

    @property
    def status_badge_class(self):
        return self.STATUS_CSS.get(self.status, "badge-muted")
