"""Projects 7.17 — RecurringTaskSchedule model.

Recurring Task Automation: cadence-driven schedule generator for repetitive tasks and sprint rituals.
"""
from datetime import timedelta
from decimal import Decimal
from django.db import models
from django.utils import timezone

from apps.projects.models._base import *


class RecurringTaskSchedule(TenantNumbered):
    """Cadence-driven schedule generator creating ProjectTask instances on schedule."""

    NUMBER_PREFIX = "RTS"

    FREQUENCY_CHOICES = [
        ("daily", "Daily"),
        ("weekly", "Weekly"),
        ("biweekly", "Bi-Weekly"),
        ("monthly", "Monthly"),
        ("quarterly", "Quarterly"),
        ("sprint_cadence", "Sprint Cadence"),
    ]

    PRIORITY_CHOICES = [
        ("urgent", "Urgent"),
        ("high", "High"),
        ("medium", "Medium"),
        ("low", "Low"),
    ]

    ASSIGNEE_STRATEGY_CHOICES = [
        ("fixed_user", "Fixed User"),
        ("project_manager", "Project Manager"),
        ("unassigned", "Unassigned"),
    ]

    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="recurring_schedules",
    )
    title_template = models.CharField(
        max_length=255,
        help_text="Supports {{date}}, {{week}}, {{project}}, {{sprint}}",
    )
    description_template = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default="weekly")
    interval_count = models.PositiveSmallIntegerField(default=1)
    days_of_week = models.CharField(max_length=50, blank=True, help_text="e.g. MON,WED,FRI")
    day_of_month = models.PositiveSmallIntegerField(null=True, blank=True)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default="medium")
    effort_hours = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("0.00"))
    assignee_strategy = models.CharField(max_length=20, choices=ASSIGNEE_STRATEGY_CHOICES, default="fixed_user")
    default_assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    next_run_date = models.DateField()
    last_run_date = models.DateField(null=True, blank=True, editable=False)
    tasks_created_count = models.PositiveIntegerField(default=0, editable=False)

    class Meta:
        ordering = ["next_run_date", "-id"]
        unique_together = [("tenant", "number")]
        indexes = [
            models.Index(fields=["tenant", "project", "is_active"], name="rts_tnt_prj_act_idx"),
            models.Index(fields=["tenant", "next_run_date", "is_active"], name="rts_tnt_nxt_act_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.title_template} ({self.get_frequency_display()})"

    @property
    def is_active_badge(self):
        return "badge-green" if self.is_active else "badge-slate"

    @property
    def frequency_badge(self):
        badges = {
            "daily": "badge-blue",
            "weekly": "badge-purple",
            "biweekly": "badge-indigo",
            "monthly": "badge-amber",
            "quarterly": "badge-emerald",
            "sprint_cadence": "badge-cyan",
        }
        return badges.get(self.frequency, "badge-slate")

    def clean(self):
        super().clean()
        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "End date cannot be prior to start date."})

    def advance_next_run_date(self):
        """Advance next_run_date according to frequency and interval."""
        delta_days = 7
        interval = max(self.interval_count, 1)
        if self.frequency == "daily":
            delta_days = 1 * interval
        elif self.frequency == "weekly":
            delta_days = 7 * interval
        elif self.frequency == "biweekly":
            delta_days = 14 * interval
        elif self.frequency == "monthly":
            delta_days = 30 * interval
        elif self.frequency == "quarterly":
            delta_days = 90 * interval
        elif self.frequency == "sprint_cadence":
            delta_days = 14 * interval

        self.next_run_date = self.next_run_date + timedelta(days=delta_days)
        if self.end_date and self.next_run_date > self.end_date:
            self.is_active = False

    def generate_task(self, actor=None):
        """Mint a new ProjectTask from this schedule prototype."""
        from apps.projects.models.ProjectPlanningScheduling.ProjectTasks import ProjectTask

        today = timezone.localdate()
        title = self.title_template
        title = title.replace("{{date}}", today.isoformat())
        title = title.replace("{{week}}", f"W{today.isocalendar()[1]}")
        title = title.replace("{{project}}", self.project.name)

        desc = self.description_template or ""
        desc = desc.replace("{{date}}", today.isoformat())
        desc = desc.replace("{{project}}", self.project.name)
        desc += f"\n\n[Auto-generated by Recurring Schedule {self.number}]"

        # Determine assignee
        assigned_to = None
        if self.assignee_strategy == "fixed_user":
            assigned_to = self.default_assignee
        elif self.assignee_strategy == "project_manager":
            assigned_to = self.project.project_manager

        priority_map = {
            "urgent": "critical",
            "high": "high",
            "medium": "medium",
            "low": "low",
        }
        task_priority = priority_map.get(self.priority, "medium")

        task = ProjectTask.objects.create(
            tenant=self.tenant,
            project=self.project,
            name=title[:255],
            description=desc,
            priority=task_priority,
            effort_hours=self.effort_hours,
            assignee=assigned_to,
            planned_start=self.next_run_date,
            planned_end=self.next_run_date + timedelta(days=5),
            status="planned",
        )

        self.last_run_date = today
        self.tasks_created_count += 1
        self.advance_next_run_date()
        self.save()

        return task
