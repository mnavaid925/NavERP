"""HRM 3.12 Holiday Management — Holidaypolicy models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403
from apps.hrm.models.EmployeeManagement.EmployeeProfiles import EmployeeProfile
from apps.hrm.models.EmployeeManagement.EmployeeProfiles import EmployeeProfile


class HolidayPolicy(TenantOwned):
    """A location/eligibility-scoped holiday policy (3.12 — "Holiday Policies" bullet).

    A policy narrows *which* optional holidays an employee may draw from (``holidays``; empty =
    the whole tenant's optional-holiday pool) and *how many* they may elect per year
    (``floating_holiday_quota``), scoped to a location / department / employee-type / designation.
    ``for_employee()`` resolves the single governing policy for an employee — the most specific
    active match, falling back to the ``is_default`` company-wide policy — so eligibility logic
    lives in one place (mirrors the "most-specific match wins" idea from the sidebar resolver)."""

    name = models.CharField(max_length=150)
    location = models.CharField(
        max_length=255, blank=True,
        help_text="Matched (case-insensitive contains) against an employee's work location. Blank = any.")
    org_unit = models.ForeignKey(
        "core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="holiday_policies", help_text="Department/branch scope. Blank = any.")
    employee_type = models.CharField(
        max_length=20, blank=True, choices=EmployeeProfile.EMPLOYEE_TYPE_CHOICES,
        help_text="Employment-type eligibility. Blank = any.")
    designation = models.ForeignKey(
        "hrm.Designation", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="holiday_policies", help_text="Designation/grade eligibility. Blank = any.")
    is_default = models.BooleanField(
        default=False, help_text="The fallback policy applied when no more specific policy matches.")
    floating_holiday_quota = models.PositiveSmallIntegerField(
        default=0, help_text="Maximum optional (floating) holidays an eligible employee may elect per year.")
    holidays = models.ManyToManyField(
        "hrm.PublicHoliday", blank=True, related_name="policies",
        help_text="Optional — restrict the electable optional-holiday pool. Empty = all optional holidays.")
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["-is_default", "name"]
        unique_together = ("tenant", "name")
        indexes = [
            models.Index(fields=["tenant", "is_default"], name="hrm_hpol_tenant_default_idx"),
        ]

    def __str__(self):
        return self.name

    @classmethod
    def for_employee(cls, employee):
        """Return the governing ``HolidayPolicy`` for ``employee`` (an ``EmployeeProfile``), or
        ``None``. Every *set* scope field on a policy must match the employee (a blank field is a
        wildcard that matches anyone); among matching policies the one with the most matched scope
        fields wins, and a tie breaks toward the ``is_default`` policy."""
        if employee is None or not getattr(employee, "tenant_id", None):
            return None
        emp_location = (getattr(employee, "work_location", "") or "").strip().lower()
        emp_org_unit_id = employee.employment.org_unit_id if employee.employment_id else None
        emp_type = employee.employee_type or ""
        emp_desig_id = employee.designation_id

        best, best_rank = None, (-1, -1)
        for p in cls.objects.filter(tenant_id=employee.tenant_id, is_active=True):
            score, ok = 0, True
            if p.location:
                if emp_location and p.location.strip().lower() in emp_location:
                    score += 1
                else:
                    ok = False
            if ok and p.org_unit_id is not None:
                if p.org_unit_id == emp_org_unit_id:
                    score += 1
                else:
                    ok = False
            if ok and p.employee_type:
                if p.employee_type == emp_type:
                    score += 1
                else:
                    ok = False
            if ok and p.designation_id is not None:
                if p.designation_id == emp_desig_id:
                    score += 1
                else:
                    ok = False
            if not ok:
                continue
            # Most specific wins; a default policy breaks ties (so an explicit default outranks a
            # non-default all-wildcard policy of the same score).
            rank = (score, 1 if p.is_default else 0)
            if rank > best_rank:
                best, best_rank = p, rank
        return best
