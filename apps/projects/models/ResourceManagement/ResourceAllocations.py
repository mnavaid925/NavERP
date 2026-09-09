"""Projects 7.3 Resource Management — ResourceAllocation [RAL-]: one booking.

A role (+ optionally a named resource) asked for or committed to a project / pipeline request /
work package for a magnitude over a date window. A NULL ``resource`` is a **placeholder** — a
state of the booking (the role still needs someone), never a fake person row; ``ral_assign``
names it and ``ral_substitute`` swaps the person while releasing the current row. ``booking_status``
only moves through the verbs (requested → soft → firm → completed, or cancelled/released) —
never through a form.

⚠️ **Two ``ResourceAllocation`` models exist and that is deliberate** — same ruling as 7.1's
three ``PRJ-`` models: ``crm.ResourceAllocation`` [RA-] is the 1.8 pre-spine stand-in (people
keyed on ``User``, CRM projects) and is neither renamed nor migrated from here; THIS is the
Module 7 master, keyed on ``ResourceProfile`` and FK'd into ``projects.Project``. Numbers are
unique per ``(tenant, number)`` within a model, so the different prefixes (RA vs RAL) never
collide — but page copy always says which register the user is on.

No money columns (rates/cost are 7.4/7.15's), no execution actuals (``ResourceTimeEntry`` is
this sub-module's), no leave-aware capacity (uniform weekly hours).
"""
from apps.projects.models._base import *  # noqa: F401,F403
from apps.projects.models._base import models


class ResourceAllocation(TenantNumbered):
    """One booking: a role and magnitude over a window, named or placeholder (7.3 bullets 2-4)."""

    NUMBER_PREFIX = "RAL"

    ALLOCATION_UNIT_CHOICES = [
        ("hours_per_week", "Hours per Week"),
        ("pct_capacity", "% of Capacity"),
        ("total_hours", "Total Hours"),
    ]
    BOOKING_STATUS_CHOICES = [
        ("requested", "Requested"),
        ("soft", "Soft Booked"),
        ("firm", "Firm Booked"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
        ("released", "Released"),
    ]

    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, null=True, blank=True,
        related_name="allocations")
    project_request = models.ForeignKey(
        "projects.ProjectRequest", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="allocations",
        help_text="Pipeline demand with no project yet (approved, unconverted request).")
    project_task = models.ForeignKey(
        "projects.ProjectTask", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="allocations",
        help_text="Optional task-grain booking (planning grain only).")
    resource = models.ForeignKey(
        "projects.ResourceProfile", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="allocations",
        help_text="Leave blank for a placeholder role that still needs someone.")
    role_name = models.CharField(max_length=80)
    skill_requirements = models.CharField(max_length=255, blank=True)
    allocation_unit = models.CharField(
        max_length=14, choices=ALLOCATION_UNIT_CHOICES, default="hours_per_week")
    hours_per_week = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(Decimal("0"))])
    pct_capacity = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(100)])
    total_hours = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(Decimal("0"))])
    start_date = models.DateField()
    end_date = models.DateField(
        null=True, blank=True, help_text="Leave blank for an ongoing booking.")
    booking_status = models.CharField(
        max_length=12, choices=BOOKING_STATUS_CHOICES, default="requested",
        help_text="Verb-driven — moves through assign/commit/complete/cancel, never a form.")
    substitute_of = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="substituted_by",
        help_text="The released booking this successor replaced.")
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="requested_allocations")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-start_date", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "resource"], name="ral_tnt_resource_idx"),
            models.Index(fields=["tenant", "project"], name="ral_tnt_project_idx"),
            models.Index(fields=["tenant", "project_request"], name="ral_tnt_request_idx"),
            models.Index(fields=["tenant", "booking_status"], name="ral_tnt_status_idx"),
            models.Index(fields=["tenant", "start_date"], name="ral_tnt_start_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.role_name}"

    @property
    def is_live(self):
        """True while a soft/firm booking's window covers today."""
        today = timezone.localdate()
        return (self.booking_status in ("soft", "firm")
                and self.start_date <= today
                and (self.end_date is None or self.end_date >= today))

    def planned_hours(self, win_start, win_end):
        """Booked hours inside [win_start, win_end], prorated by overlapping days.

        The proven ``crm.ResourceAllocation.overlap_hours()`` shape, extended to the three
        allocation units. Cancelled AND released bookings count zero (a released row's successor
        already carries the demand — counting both would double it). A ``% of Capacity`` booking
        of a placeholder is unknowable (no person, no denominator) and counts zero — the demand
        lens flags placeholders by presence, not hours.
        """
        if self.booking_status in ("cancelled", "released"):
            return ZERO
        a_end = self.end_date or win_end  # null = ongoing
        ov_start = max(self.start_date, win_start)
        ov_end = min(a_end, win_end)
        if ov_end < ov_start:
            return ZERO
        days = (ov_end - ov_start).days + 1
        if self.allocation_unit == "hours_per_week":
            return q2(self.hours_per_week * days / 7)
        if self.allocation_unit == "pct_capacity":
            if self.resource_id is None:
                return ZERO
            return q2(Decimal(self.pct_capacity or 0) / 100
                      * self.resource.weekly_capacity_hours * days / 7)
        # total_hours: spread over the booking's OWN window, then take the overlapping share.
        window_days = (a_end - self.start_date).days + 1
        if window_days <= 0:
            return ZERO
        return q2(self.total_hours * days / window_days)

    def clean(self):
        # A booking must hang off project work or pipeline demand — both null is unreportable.
        if self.project_id is None and self.project_request_id is None:
            raise ValidationError(
                "Attach the allocation to a project or a project request.")
        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "End date cannot precede start date."})
        # Exactly one magnitude, and it must match the allocation unit — the unit says which
        # number drives every capacity computation, so a second one would be ambiguous.
        magnitude_fields = {
            "hours_per_week": "hours_per_week",
            "pct_capacity": "pct_capacity",
            "total_hours": "total_hours",
        }
        own = magnitude_fields[self.allocation_unit]
        if getattr(self, own) is None:
            raise ValidationError(
                {own: f"Required when the allocation unit is {self.get_allocation_unit_display()}."})
        for other_field in magnitude_fields.values():
            if other_field != own and getattr(self, other_field) is not None:
                raise ValidationError(
                    {other_field: "Leave blank — the allocation unit is "
                                  f"{self.get_allocation_unit_display()}."})
