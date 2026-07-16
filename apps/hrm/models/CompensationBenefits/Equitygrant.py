"""HRM 3.37 Compensation & Benefits — Equitygrant models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


class EquityGrant(TenantNumbered):
    """An equity/ESOP grant to an employee (``ESOP-#####``) — ISO/NSO/RSU/ESPP/phantom, with a cliff + graded
    vesting schedule. Vesting (vested/unvested/exercisable) is COMPUTED from the schedule + today, NEVER a
    stored balance (mirrors LeaveAllocation/TravelBooking derivation). Only exercised_shares is stored, updated
    by the bespoke record-exercise action. 409A/ASC-718 valuation + GL posting are deferred."""

    NUMBER_PREFIX = "ESOP"

    GRANT_TYPE_CHOICES = [
        ("iso", "ISO (Incentive Stock Option)"),
        ("nso", "NSO (Non-qualified Stock Option)"),
        ("rsu", "RSU (Restricted Stock Unit)"),
        ("espp", "ESPP (Employee Stock Purchase Plan)"),
        ("phantom", "Phantom Stock"),
    ]
    VESTING_FREQUENCY_CHOICES = [
        ("monthly", "Monthly"),
        ("quarterly", "Quarterly"),
        ("annual", "Annual"),
    ]
    STATUS_CHOICES = [
        ("active", "Active"),
        ("fully_vested", "Fully Vested"),
        ("exercised", "Exercised"),
        ("cancelled", "Cancelled"),
        ("expired", "Expired"),
    ]

    employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.CASCADE, related_name="equity_grants")
    grant_type = models.CharField(max_length=10, choices=GRANT_TYPE_CHOICES, default="rsu")
    grant_date = models.DateField()
    shares_granted = models.PositiveIntegerField(default=0)
    exercise_price = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True,
        help_text="Strike price per share (options); blank for RSUs.")
    fair_market_value_at_grant = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    currency = models.ForeignKey("accounting.Currency", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="hrm_equity_grants")
    vesting_start_date = models.DateField()
    cliff_months = models.PositiveSmallIntegerField(default=12)
    vesting_duration_months = models.PositiveSmallIntegerField(default=48)
    vesting_frequency = models.CharField(max_length=10, choices=VESTING_FREQUENCY_CHOICES, default="monthly")
    exercised_shares = models.PositiveIntegerField(default=0)
    last_exercised_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="active")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-grant_date", "id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "employee", "status"], name="hrm_esop_emp_status_idx"),
            models.Index(fields=["tenant", "status"], name="hrm_esop_tnt_status_idx"),
            models.Index(fields=["tenant", "-grant_date"], name="hrm_esop_tnt_grant_idx"),
        ]

    def __str__(self):
        return f"{self.number} - {self.get_grant_type_display()}" if self.number else self.get_grant_type_display()

    # ---- Vesting (computed, NEVER stored) ----
    @property
    def _months_vested(self):
        """Whole months from vesting_start_date to today (0 if the start is in the future)."""
        if not self.vesting_start_date:
            return 0
        today = timezone.localdate()
        if today <= self.vesting_start_date:
            return 0
        m = (today.year - self.vesting_start_date.year) * 12 + (today.month - self.vesting_start_date.month)
        if today.day < self.vesting_start_date.day:
            m -= 1
        return max(0, m)

    @property
    def vested_shares(self):
        """0 before the cliff, then graded (by vesting_frequency) up to shares_granted at the end of the
        vesting window. The cliff gate + linear-by-event math yields the standard '25% at a 1-yr cliff'."""
        if not self.shares_granted or not self.vesting_duration_months:
            return 0
        elapsed = self._months_vested
        if elapsed < (self.cliff_months or 0):
            return 0
        if elapsed >= self.vesting_duration_months:
            return self.shares_granted
        freq = {"monthly": 1, "quarterly": 3, "annual": 12}.get(self.vesting_frequency, 1)
        total_events = max(1, self.vesting_duration_months // freq)
        done_events = min(elapsed // freq, total_events)
        return int(self.shares_granted * done_events // total_events)

    @property
    def vested_percent(self):
        if not self.shares_granted:
            return Decimal("0")
        return (Decimal(self.vested_shares) / self.shares_granted * 100).quantize(Decimal("0.01"))

    @property
    def unvested_shares(self):
        return self.shares_granted - self.vested_shares

    @property
    def exercisable_shares(self):
        """Vested shares not yet exercised/released."""
        return max(0, self.vested_shares - self.exercised_shares)
