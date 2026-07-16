"""HRM 3.4 Employee Offboarding — Clearanceitem models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


class ClearanceItem(TenantOwned):
    """One department clearance line on a ``SeparationCase`` (3.4). Asset-return lines link the
    employee's issued ``AssetAllocation``; marking such a line cleared also returns that asset (in the
    same transaction — see ``views.clearanceitem_mark_cleared``). ``status``/``cleared_by``/
    ``cleared_at`` are workflow-owned."""

    CLEARANCE_DEPT_CHOICES = [
        ("it", "IT"),
        ("finance", "Finance"),
        ("hr", "HR"),
        ("admin", "Admin"),
        ("manager", "Manager / KT"),
        ("legal", "Legal"),
        ("security", "Security"),
        ("library", "Library"),
        ("custom", "Custom"),
    ]
    CLEARANCE_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("in_progress", "In Progress"),
        ("cleared", "Cleared"),
        ("not_applicable", "Not Applicable"),
        ("rejected", "Rejected"),
    ]
    # Terminal/resolved states that satisfy the all-mandatory-cleared gate.
    RESOLVED_STATUSES = ("cleared", "not_applicable")

    case = models.ForeignKey("hrm.SeparationCase", on_delete=models.CASCADE, related_name="clearance_items")
    department = models.CharField(max_length=20, choices=CLEARANCE_DEPT_CHOICES, default="hr")
    department_label = models.CharField(max_length=100, blank=True, help_text="Free-text label when department is Custom.")
    description = models.CharField(max_length=255)
    is_mandatory = models.BooleanField(default=True)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="hrm_clearance_items_assigned")
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=CLEARANCE_STATUS_CHOICES, default="pending", editable=False)
    cleared_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="hrm_clearance_items_cleared", editable=False)
    cleared_at = models.DateTimeField(null=True, blank=True, editable=False)
    asset_allocation = models.ForeignKey("hrm.AssetAllocation", on_delete=models.SET_NULL, null=True, blank=True, related_name="clearance_items", help_text="Issued asset this line covers (returned when the line is cleared).")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["case", "department", "description"]
        indexes = [
            models.Index(fields=["tenant", "case"], name="hrm_ci_tenant_case_idx"),
            models.Index(fields=["tenant", "status"], name="hrm_ci_tenant_status_idx"),
            models.Index(fields=["tenant", "case", "status"], name="hrm_ci_tenant_case_st_idx"),
            models.Index(fields=["tenant", "department"], name="hrm_ci_tenant_dept_idx"),
        ]

    @property
    def department_display(self):
        """The custom label when department == 'custom' (and one is set), else the choice label."""
        if self.department == "custom" and self.department_label:
            return self.department_label
        return self.get_department_display()

    def __str__(self):
        return f"{self.get_department_display()} — {self.description} [{self.get_status_display()}]"
