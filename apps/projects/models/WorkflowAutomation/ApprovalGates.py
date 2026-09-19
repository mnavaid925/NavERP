"""Projects 7.17 — ProjectApprovalGate model.

Approval Automation: governance gates, auto-approval within tolerances, SLA timeout escalation, and delegation.
"""
from decimal import Decimal
from django.db import models

from apps.projects.models._base import *


class ProjectApprovalGate(TenantNumbered):
    """Multi-tier governance approval gate for project phase gates, deliverables, and overrides."""

    NUMBER_PREFIX = "PAR"

    GATE_TYPE_CHOICES = [
        ("phase_gate", "Phase Transition Gate"),
        ("scope_change", "Scope Change Approval"),
        ("budget_override", "Budget Baseline Override"),
        ("deliverable_acceptance", "Deliverable Acceptance"),
        ("charter_signoff", "Charter Sign-off"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending Review"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("escalated", "Escalated"),
        ("auto_approved", "Auto-Approved"),
        ("cancelled", "Cancelled"),
    ]

    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="approval_gates",
    )
    rule = models.ForeignKey(
        "projects.ProjectWorkflowRule",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="spawned_gates",
    )
    gate_type = models.CharField(max_length=30, choices=GATE_TYPE_CHOICES, default="phase_gate")
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    target_model = models.CharField(max_length=50, help_text="e.g. Project, ScopeChangeRequest, DeliverableInspection")
    target_id = models.PositiveIntegerField()
    target_label = models.CharField(max_length=255, blank=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
    )
    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
    )
    delegate_approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    escalate_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    timeout_hours = models.PositiveIntegerField(default=48)
    threshold_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    auto_approve_threshold = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    decision_notes = models.TextField(blank=True)
    decided_at = models.DateTimeField(null=True, blank=True, editable=False)
    escalated_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["-created_at", "-id"]
        unique_together = [("tenant", "number")]
        indexes = [
            models.Index(fields=["tenant", "project", "status"], name="par_tnt_prj_stat_idx"),
            models.Index(fields=["tenant", "approver", "status"], name="par_tnt_appr_stat_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.title} ({self.get_status_display()})"

    @property
    def status_badge(self):
        badges = {
            "pending": "badge-amber",
            "approved": "badge-green",
            "auto_approved": "badge-green",
            "rejected": "badge-red",
            "escalated": "badge-red",
            "cancelled": "badge-slate",
        }
        return badges.get(self.status, "badge-slate")

    @property
    def is_terminal(self):
        return self.status in ("approved", "auto_approved", "rejected", "cancelled")
