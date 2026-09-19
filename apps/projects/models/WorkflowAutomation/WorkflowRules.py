"""Projects 7.17 — ProjectWorkflowRule and WorkflowExecutionLog models.

Visual Workflow Designer and Trigger-Condition-Action (TCA) automation rule engine.
"""
from django.db import models

from apps.projects.models._base import *


class ProjectWorkflowRule(TenantNumbered):
    """Primary Trigger-Condition-Action (TCA) automation rule engine for project events."""

    NUMBER_PREFIX = "PWF"

    TRIGGER_ENTITY_CHOICES = [
        ("project", "Project"),
        ("task", "Task"),
        ("milestone", "Milestone"),
        ("risk", "Risk"),
        ("issue", "Issue"),
        ("budget", "Budget Line"),
        ("scope_change", "Scope Change Request"),
        ("inspection", "Deliverable Inspection"),
    ]

    TRIGGER_EVENT_CHOICES = [
        ("created", "Record Created"),
        ("updated", "Record Updated"),
        ("status_changed", "Status Changed"),
        ("due_date_approaching", "Due Date Approaching"),
        ("threshold_breached", "Threshold Breached"),
        ("blocked", "Task Blocked"),
    ]

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="workflow_rules",
        help_text="Null implies tenant-wide rule",
    )
    is_active = models.BooleanField(default=True)
    trigger_entity = models.CharField(max_length=30, choices=TRIGGER_ENTITY_CHOICES, default="task")
    trigger_event = models.CharField(max_length=30, choices=TRIGGER_EVENT_CHOICES, default="status_changed")
    trigger_field = models.CharField(max_length=100, blank=True)
    trigger_value = models.CharField(max_length=255, blank=True)
    conditions = models.JSONField(default=list, blank=True)
    actions = models.JSONField(default=list, blank=True)
    execution_count = models.PositiveIntegerField(default=0, editable=False)
    last_fired_at = models.DateTimeField(null=True, blank=True, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_project_workflows",
    )

    class Meta:
        ordering = ["-created_at", "-id"]
        unique_together = [("tenant", "number")]
        indexes = [
            models.Index(fields=["tenant", "trigger_entity", "is_active"], name="pwf_tnt_trg_act_idx"),
            models.Index(fields=["tenant", "project", "is_active"], name="pwf_tnt_prj_act_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.name}"

    @property
    def is_active_badge(self):
        return "badge-green" if self.is_active else "badge-slate"


class WorkflowExecutionLog(TenantOwned):
    """Execution audit trail for a ProjectWorkflowRule execution."""

    STATUS_CHOICES = [
        ("success", "Success"),
        ("failed", "Failed"),
        ("condition_failed", "Conditions Not Met"),
        ("simulated", "Simulated Run"),
    ]

    rule = models.ForeignKey(
        ProjectWorkflowRule,
        on_delete=models.CASCADE,
        related_name="execution_logs",
    )
    record_label = models.CharField(max_length=255, blank=True)
    target_model = models.CharField(max_length=50, blank=True)
    target_id = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="success")
    fired_at = models.DateTimeField(auto_now_add=True)
    error_msg = models.TextField(blank=True)
    duration_ms = models.PositiveIntegerField(default=0)
    evaluated_conditions = models.JSONField(default=dict, blank=True)
    executed_actions = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["-fired_at", "-id"]
        indexes = [
            models.Index(fields=["tenant", "rule", "status"], name="pwf_log_tnt_rule_stat_idx"),
            models.Index(fields=["tenant", "-fired_at"], name="pwf_log_tnt_fired_idx"),
        ]

    def __str__(self):
        rule_label = self.rule.number if "rule" in self._state.fields_cache else f"Rule #{self.rule_id}"
        return f"Log for {rule_label} ({self.status}) at {self.fired_at}"

    @property
    def status_badge(self):
        badges = {
            "success": "badge-green",
            "failed": "badge-red",
            "condition_failed": "badge-amber",
            "simulated": "badge-info",
        }
        return badges.get(self.status, "badge-slate")
