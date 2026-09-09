"""Projects 7.3 Resource Management — ResourceProfile [RSP-]: one bookable person.

One row per person the workspace can book against project work — an internal HR employee
**or** an external party, never a second person master (L28: the employee is
``hrm.EmployeeProfile``'s 1:1 over ``core.Party``; the contractor is a bare ``core.Party``).
Exactly one of the two is set; ``clean()`` enforces it and keeps one pool row per employee.

Skills, competencies and certifications are deliberately NOT re-declared here — HRM 3.40's
``hrm.EmployeeSkill`` owns the matrix, and this module's pages link to that register as a lens.
No money columns (rates/cost are 7.4's), no availability engine beyond the contractor
engagement window (leave deduction is HRM 3.10's), and the bookings themselves live on
``ResourceAllocation`` — this is the denominator side of every capacity computation:
``weekly_capacity_hours``.
"""
from apps.projects.models._base import *  # noqa: F401,F403
from apps.projects.models._base import models


class ResourceProfile(TenantNumbered):
    """A bookable person in the tenant's resource pool (7.3 bullet 1)."""

    NUMBER_PREFIX = "RSP"

    RESOURCE_TYPE_CHOICES = [
        ("internal", "Internal"),
        ("contractor", "Contractor"),
        ("freelancer", "Freelancer"),
        ("consultant", "Consultant"),
    ]
    STATUS_CHOICES = [
        ("active", "Active"),
        ("inactive", "Inactive"),
    ]

    employee = models.ForeignKey(
        "hrm.EmployeeProfile", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="resource_profiles",
        help_text="Internal staff. Exactly one of employee/party.")
    party = models.ForeignKey(
        "core.Party", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="resource_profiles",
        help_text="External contractor/freelancer identity. Exactly one of employee/party.")
    resource_type = models.CharField(max_length=12, choices=RESOURCE_TYPE_CHOICES, default="internal")
    default_role = models.CharField(
        max_length=80, help_text="The role bookings copy when they don't name one.")
    org_unit = models.ForeignKey(
        "core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="resource_profiles", help_text="Home team — the pool filter.")
    skill_summary = models.CharField(
        max_length=255, blank=True,
        help_text="Quick filter text. The matrix itself is HRM 3.40's EmployeeSkill register.")
    weekly_capacity_hours = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal("40.00"),
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Bookable hours per week — the denominator of every capacity computation.")
    utilization_target_pct = models.PositiveSmallIntegerField(
        default=80, validators=[MinValueValidator(1), MaxValueValidator(100)])
    available_from = models.DateField(
        null=True, blank=True, help_text="Engagement window start (contractors).")
    available_to = models.DateField(
        null=True, blank=True, help_text="Engagement window end (contractors).")
    status = models.CharField(max_length=8, choices=STATUS_CHOICES, default="active")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["employee__party__name", "party__name", "id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "resource_type"], name="rsp_tnt_rtype_idx"),
            models.Index(fields=["tenant", "status"], name="rsp_tnt_status_idx"),
            models.Index(fields=["tenant", "employee"], name="rsp_tnt_employee_idx"),
            models.Index(fields=["tenant", "party"], name="rsp_tnt_party_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.name}"

    @property
    def name(self):
        """Display name: the employee's party, the external party, else the number."""
        if self.employee_id and self.employee.party_id:
            return self.employee.party.name
        if self.party_id:
            return self.party.name
        return self.number

    def clean(self):
        # One-of employee/party — a row with neither has no identity; a row with both
        # double-counts one person's capacity.
        if bool(self.employee_id) == bool(self.party_id):
            raise ValidationError(
                "Choose an employee or an external party — exactly one of the two.")
        # One pool row per employee per tenant. Deliberately a clean() guard, not a
        # conditional unique constraint — MariaDB can't enforce one (7.2 BSL precedent).
        if (self.employee_id and self.tenant_id
                and ResourceProfile.objects.filter(
                    tenant_id=self.tenant_id, employee_id=self.employee_id)
                .exclude(pk=self.pk).exists()):
            raise ValidationError(
                {"employee": "This employee is already in this tenant's resource pool."})
