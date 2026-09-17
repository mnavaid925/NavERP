"""Projects 7.11 Time & Attendance Tracking — ProjectOvertimeRecord [POT-].

Dedicated overtime claims and approvals for project work, linking resource,
project, task, overtime multiplier, and billing multiplier to client.
"""
from apps.projects.models._base import *  # noqa: F401,F403
from apps.projects.models._base import models


class ProjectOvertimeRecord(TenantNumbered):
    """One overtime claim against a project with approval lifecycle and billing split rates."""

    NUMBER_PREFIX = "POT"

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("submitted", "Submitted"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    OVERTIME_TYPE_CHOICES = [
        ("daily", "Daily Overtime (>8h)"),
        ("weekly", "Weekly Overtime (>40h)"),
        ("weekend", "Weekend Work"),
        ("holiday", "Holiday Work"),
    ]

    resource = models.ForeignKey(
        "projects.ResourceProfile",
        on_delete=models.CASCADE,
        related_name="overtime_records",
        help_text="Resource claiming the overtime.")
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="overtime_records",
        help_text="Project to which overtime hours are charged.")
    project_task = models.ForeignKey(
        "projects.ProjectTask",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="overtime_records",
        help_text="Optional work package/task.")
    time_entry = models.ForeignKey(
        "projects.ResourceTimeEntry",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="overtime_records",
        help_text="Optional link to a primary daily time log.")
    date = models.DateField(help_text="Date overtime was worked.")
    overtime_hours = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01")), MaxValueValidator(Decimal("24.00"))],
        help_text="Overtime hours worked.")
    overtime_type = models.CharField(
        max_length=16,
        choices=OVERTIME_TYPE_CHOICES,
        default="daily")
    pay_multiplier = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=Decimal("1.50"),
        validators=[MinValueValidator(Decimal("1.00")), MaxValueValidator(Decimal("5.00"))],
        help_text="Pay rate multiplier.")
    billable_multiplier = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=Decimal("1.00"),
        validators=[MinValueValidator(Decimal("0.00")), MaxValueValidator(Decimal("5.00"))],
        help_text="Billing multiplier charged to the client.")
    is_billable = models.BooleanField(
        default=True,
        help_text="Whether overtime is billable to the client.")
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default="draft",
        help_text="Verb-driven: draft -> submitted -> approved / rejected.")
    submitted_at = models.DateTimeField(null=True, blank=True, editable=False)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name="approved_overtime_records")
    approved_at = models.DateTimeField(null=True, blank=True, editable=False)
    decision_note = models.TextField(blank=True, help_text="Reason when rejected.")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-date", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "resource", "date"], name="pot_tnt_res_date_idx"),
            models.Index(fields=["tenant", "project", "date"], name="pot_tnt_prj_date_idx"),
            models.Index(fields=["tenant", "status"], name="pot_tnt_status_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.overtime_hours}h OT on {self.date}"

    @property
    def pay_equivalent_hours(self):
        """Multiplier-weighted compensation hours."""
        return q2(self.overtime_hours * self.pay_multiplier)

    @property
    def billable_equivalent_hours(self):
        """Multiplier-weighted client billable hours."""
        if not self.is_billable:
            return ZERO
        return q2(self.overtime_hours * self.billable_multiplier)
