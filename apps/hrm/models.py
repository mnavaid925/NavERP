"""Human Resource Management (Module 3) domain models.

HRM reuses the unified core spine (NavERP-ERD.md): an **employee** is a ``core.Party`` with a
``core.Employment`` (job/department/manager) — this app never creates a standalone employee
table. ``EmployeeProfile`` is a thin 1:1 extension of ``Party`` carrying the HRM-specific
fields (employee type, bank, emergency contact, photo, …) and is the **anchor** every other
HRM model FKs into (leave, attendance, shifts) — never ``core.Party`` directly.

Departments / org hierarchy reuse ``core.OrgUnit`` (kind="department"); ``Designation`` adds
only the HRM-owned job-grade/salary-band table and FKs an OrgUnit by string.

Derived-not-stored (spine principle): a ``LeaveAllocation`` balance is **always** computed from
approved ``LeaveRequest`` rows; ``LeaveRequest.days`` and ``AttendanceRecord.hours_worked`` are
recomputed in ``save()`` from their dates/times, never hand-edited on the form.

Payroll/GL posting is **owned by ``accounting.PayrollRun`` (PRUN-…)** — HRM does NOT duplicate
it. The HRM payroll/payslip layer (FKing into ``accounting.PayrollRun``) is a later pass.
"""
from datetime import date, datetime
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, models, transaction
from django.db.models import Sum

from apps.core.utils import next_number

ZERO = Decimal("0")


# ---------------------------------------------------------------------------
# Shared abstract bases (mirror the proven apps/crm + apps/accounting pattern;
# local copy — peer domain apps don't import each other).
# ---------------------------------------------------------------------------
class TenantOwned(models.Model):
    """Tenant FK + created/updated timestamps. ``related_name="+"`` — views always filter
    ``Model.objects.filter(tenant=request.tenant)`` so no reverse accessor is needed and the
    abstract base never clashes across its many subclasses."""

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="+", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class TenantNumbered(TenantOwned):
    """Adds a human-readable per-tenant ``number`` (e.g. ``EMP-00001``) assigned once in
    ``save()`` with a retry-on-collision guard (mirrors ``tenants.SubscriptionInvoice``)."""

    NUMBER_PREFIX = ""

    number = models.CharField(max_length=20, editable=False)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self.number and self.tenant_id and self.NUMBER_PREFIX:
            for _ in range(5):
                self.number = next_number(type(self), self.tenant, self.NUMBER_PREFIX)
                try:
                    with transaction.atomic():
                        return super().save(*args, **kwargs)
                except IntegrityError:
                    self.number = ""
        return super().save(*args, **kwargs)


# ---------------------------------------------------------------------------
# 3.2 Organizational Structure — Designation (reuses core.OrgUnit for department)
# ---------------------------------------------------------------------------
class Designation(TenantOwned):
    """Job title / grade with a salary band (3.2). Department is reused from ``core.OrgUnit``."""

    name = models.CharField(max_length=255)
    grade = models.CharField(max_length=50, blank=True)
    department = models.ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="designations")
    min_salary = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    max_salary = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        unique_together = ("tenant", "name")
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="hrm_desig_tenant_active_idx"),
            models.Index(fields=["tenant", "department"], name="hrm_desig_tenant_dept_idx"),
        ]

    def clean(self):
        super().clean()
        if self.min_salary is not None and self.max_salary is not None and self.min_salary > self.max_salary:
            raise ValidationError({"max_salary": "Maximum salary must be greater than or equal to the minimum."})

    def __str__(self):
        return f"{self.name} ({self.grade})" if self.grade else self.name


# ---------------------------------------------------------------------------
# 3.1 Employee Management — EmployeeProfile (anchor; 1:1 over core.Party/Employment)
# ---------------------------------------------------------------------------
class EmployeeProfile(TenantNumbered):
    """The HRM employee record (3.1) — a 1:1 extension of ``core.Party`` + ``core.Employment``.
    All other HRM models FK to this, never to ``core.Party`` directly."""

    NUMBER_PREFIX = "EMP"

    EMPLOYEE_TYPE_CHOICES = [
        ("full_time", "Full Time"),
        ("part_time", "Part Time"),
        ("contract", "Contract"),
        ("intern", "Intern"),
        ("consultant", "Consultant"),
    ]
    GENDER_CHOICES = [
        ("male", "Male"),
        ("female", "Female"),
        ("other", "Other"),
        ("prefer_not_to_say", "Prefer Not to Say"),
    ]
    BLOOD_GROUP_CHOICES = [
        ("A+", "A+"), ("A-", "A-"), ("B+", "B+"), ("B-", "B-"),
        ("AB+", "AB+"), ("AB-", "AB-"), ("O+", "O+"), ("O-", "O-"),
    ]

    party = models.OneToOneField("core.Party", on_delete=models.CASCADE, related_name="employee_profile")
    employment = models.OneToOneField("core.Employment", on_delete=models.SET_NULL, null=True, blank=True, related_name="employee_profile")
    designation = models.ForeignKey("hrm.Designation", on_delete=models.SET_NULL, null=True, blank=True, related_name="employees")
    employee_type = models.CharField(max_length=20, choices=EMPLOYEE_TYPE_CHOICES, default="full_time")
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    blood_group = models.CharField(max_length=5, choices=BLOOD_GROUP_CHOICES, blank=True)
    nationality = models.CharField(max_length=100, blank=True)
    personal_email = models.EmailField(blank=True)
    mobile = models.CharField(max_length=30, blank=True)
    # WARNING: bank_account is stored in plaintext for demo purposes. In production, encrypt at
    # rest (e.g. via the tenants EncryptionKey pattern) or store only a tokenized/masked value.
    bank_name = models.CharField(max_length=255, blank=True)
    bank_account = models.CharField(max_length=64, blank=True)
    bank_routing = models.CharField(max_length=20, blank=True)
    probation_end_date = models.DateField(null=True, blank=True)
    confirmed_on = models.DateField(null=True, blank=True)
    emergency_contact_name = models.CharField(max_length=255, blank=True)
    emergency_contact_phone = models.CharField(max_length=30, blank=True)
    emergency_contact_relation = models.CharField(max_length=100, blank=True)
    photo = models.ImageField(upload_to="hrm/photos/%Y/%m/", null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["party__name"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "employee_type"], name="hrm_emp_tenant_type_idx"),
            models.Index(fields=["tenant", "designation"], name="hrm_emp_tenant_desig_idx"),
        ]

    @property
    def department(self):
        """Convenience accessor — the department lives on the linked core.Employment."""
        return self.employment.org_unit if self.employment_id else None

    @property
    def manager(self):
        return self.employment.manager if self.employment_id else None

    @property
    def name(self):
        return self.party.name if self.party_id else ""

    def masked_bank_account(self):
        """Last-4 view of the account number (never render the full value)."""
        acct = self.bank_account or ""
        return f"••••{acct[-4:]}" if len(acct) >= 4 else ("••••" if acct else "")

    def __str__(self):
        return f"{self.number} · {self.party.name}" if self.party_id else self.number


# ---------------------------------------------------------------------------
# 3.10 Leave Management — LeaveType / LeaveAllocation / LeaveRequest
# ---------------------------------------------------------------------------
class LeaveType(TenantOwned):
    """Configurable leave catalog (3.10) — accrual / carry-forward / encashment policy."""

    ACCRUAL_CHOICES = [
        ("none", "No Accrual"),
        ("monthly", "Monthly Accrual"),
        ("annual", "Annual Grant"),
    ]

    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20)
    is_paid = models.BooleanField(default=True)
    accrual_rule = models.CharField(max_length=20, choices=ACCRUAL_CHOICES, default="annual")
    accrual_days = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    max_balance = models.DecimalField(max_digits=5, decimal_places=2, default=0, help_text="0 = unlimited")
    max_carry_forward = models.DecimalField(max_digits=5, decimal_places=2, default=0, help_text="Days carriable to next year (0 = none)")
    encashable = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        unique_together = ("tenant", "code")
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="hrm_lvtype_tenant_active_idx"),
        ]

    def clean(self):
        super().clean()
        if self.accrual_rule != "none" and (self.accrual_days or ZERO) <= ZERO:
            raise ValidationError({"accrual_days": "Accrual days must be greater than zero for an accruing leave type."})

    def __str__(self):
        return f"{self.name} ({self.code})"


class LeaveAllocation(TenantNumbered):
    """Per-employee, per-year leave entitlement (3.10). The used/balance figures are **derived**
    from approved ``LeaveRequest`` rows — never stored editable."""

    NUMBER_PREFIX = "LA"

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("active", "Active"),
        ("expired", "Expired"),
    ]

    employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.CASCADE, related_name="leave_allocations")
    leave_type = models.ForeignKey("hrm.LeaveType", on_delete=models.CASCADE, related_name="allocations")
    year = models.PositiveSmallIntegerField()
    allocated_days = models.DecimalField(max_digits=5, decimal_places=2)
    note = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")

    class Meta:
        ordering = ["-year", "employee__party__name"]
        unique_together = [("tenant", "number"), ("tenant", "employee", "leave_type", "year")]
        indexes = [
            models.Index(fields=["tenant", "employee", "year"], name="hrm_la_tenant_emp_year_idx"),
            models.Index(fields=["tenant", "leave_type", "year"], name="hrm_la_tenant_type_year_idx"),
            models.Index(fields=["tenant", "status"], name="hrm_la_tenant_status_idx"),
        ]

    @property
    def used_days(self):
        # Calendar-year semantic: a request is charged to the year of its start_date. A request
        # straddling a year boundary is counted whole against the start year (acceptable for the
        # demo; exact split + year-end carry-forward is a deferred enhancement — see todo.md).
        # Cached on the instance so `balance` doesn't re-run the aggregate. List views should use
        # the `used_days_db`/`balance_db` annotations (see hrm.views._used_days_subquery) instead.
        if not hasattr(self, "_used_days_cache"):
            agg = LeaveRequest.objects.filter(
                tenant_id=self.tenant_id, employee_id=self.employee_id,
                leave_type_id=self.leave_type_id, status="approved",
                start_date__year=self.year,
            ).aggregate(s=Sum("days"))
            self._used_days_cache = agg["s"] or ZERO
        return self._used_days_cache

    @property
    def balance(self):
        return (self.allocated_days or ZERO) - self.used_days

    def __str__(self):
        return f"{self.number} · {self.employee} · {self.leave_type} · {self.year}"


class LeaveRequest(TenantNumbered):
    """Apply / approve / reject leave (3.10). ``days`` is recomputed in ``save()`` from the date
    range, excluding non-optional public holidays in that range."""

    NUMBER_PREFIX = "LR"

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("cancelled", "Cancelled"),
    ]
    OPEN_STATUSES = ("draft", "pending")

    employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.CASCADE, related_name="leave_requests")
    leave_type = models.ForeignKey("hrm.LeaveType", on_delete=models.CASCADE, related_name="leave_requests")
    start_date = models.DateField()
    end_date = models.DateField()
    days = models.DecimalField(max_digits=5, decimal_places=2, default=0, editable=False)
    reason = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    approver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="hrm_approvals")
    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_reason = models.TextField(blank=True)
    cancelled_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-start_date"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "employee", "status"], name="hrm_lr_tenant_emp_status_idx"),
            models.Index(fields=["tenant", "status"], name="hrm_lr_tenant_status_idx"),
            models.Index(fields=["tenant", "leave_type", "start_date"], name="hrm_lr_tenant_type_start_idx"),
        ]

    def clean(self):
        super().clean()
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "End date cannot be before the start date."})

    def _recompute_days(self):
        if self.start_date and self.end_date and self.end_date >= self.start_date:
            total = (self.end_date - self.start_date).days + 1
            holidays = 0
            if self.tenant_id:
                holidays = PublicHoliday.objects.filter(
                    tenant_id=self.tenant_id, is_optional=False,
                    date__gte=self.start_date, date__lte=self.end_date,
                ).count()
            self.days = Decimal(max(0, total - holidays))
        else:
            self.days = ZERO

    def save(self, *args, **kwargs):
        self._recompute_days()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.number} · {self.employee} · {self.leave_type} · {self.start_date}"


# ---------------------------------------------------------------------------
# 3.12 Holiday Management — PublicHoliday
# ---------------------------------------------------------------------------
class PublicHoliday(TenantOwned):
    """Tenant-scoped holiday calendar (3.12). Non-optional holidays are excluded from
    ``LeaveRequest.days``; optional (floating) holidays are not."""

    date = models.DateField()
    name = models.CharField(max_length=255)
    is_optional = models.BooleanField(default=False)

    class Meta:
        ordering = ["date"]
        unique_together = ("tenant", "date", "name")
        indexes = [
            models.Index(fields=["tenant", "date"], name="hrm_holiday_tenant_date_idx"),
        ]

    def __str__(self):
        return f"{self.date} — {self.name}"


# ---------------------------------------------------------------------------
# 3.9 Attendance Management — Shift / ShiftAssignment / AttendanceRecord
# ---------------------------------------------------------------------------
class Shift(TenantOwned):
    """A working-shift definition (3.9) — start/end + late-arrival grace tolerance."""

    name = models.CharField(max_length=100)
    start_time = models.TimeField()
    end_time = models.TimeField()
    grace_minutes = models.PositiveSmallIntegerField(default=15)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        unique_together = ("tenant", "name")
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="hrm_shift_tenant_active_idx"),
        ]

    def __str__(self):
        return f"{self.name} ({self.start_time:%H:%M}–{self.end_time:%H:%M})"


class ShiftAssignment(TenantOwned):
    """Assigns a ``Shift`` to an employee for an effective date range (3.9)."""

    employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.CASCADE, related_name="shift_assignments")
    shift = models.ForeignKey("hrm.Shift", on_delete=models.CASCADE, related_name="assignments")
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-effective_from"]
        unique_together = ("tenant", "employee", "effective_from")
        indexes = [
            models.Index(fields=["tenant", "employee", "effective_from"], name="hrm_sa_tenant_emp_from_idx"),
            models.Index(fields=["tenant", "shift"], name="hrm_sa_tenant_shift_idx"),
        ]

    def clean(self):
        super().clean()
        if self.effective_to and self.effective_from and self.effective_to < self.effective_from:
            raise ValidationError({"effective_to": "End date cannot be before the start date."})

    def __str__(self):
        return f"{self.employee} → {self.shift} from {self.effective_from}"


class AttendanceRecord(TenantNumbered):
    """A daily attendance entry per employee (3.9). ``hours_worked`` is recomputed in ``save()``
    from check-in/out (handling an overnight shift), never hand-edited on the form."""

    NUMBER_PREFIX = "ATT"

    STATUS_CHOICES = [
        ("present", "Present"),
        ("absent", "Absent"),
        ("half_day", "Half Day"),
        ("on_leave", "On Leave"),
        ("holiday", "Holiday"),
        ("regularized", "Regularized"),
    ]
    SOURCE_CHOICES = [
        ("web", "Web"),
        ("mobile", "Mobile App"),
        ("biometric", "Biometric"),
        ("manual", "Manual Entry"),
    ]

    employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.CASCADE, related_name="attendance_records")
    date = models.DateField()
    check_in = models.TimeField(null=True, blank=True)
    check_out = models.TimeField(null=True, blank=True)
    hours_worked = models.DecimalField(max_digits=5, decimal_places=2, default=0, editable=False)
    shift = models.ForeignKey("hrm.Shift", on_delete=models.SET_NULL, null=True, blank=True, related_name="attendance_records")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="present")
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default="web")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-date"]
        unique_together = [("tenant", "number"), ("tenant", "employee", "date")]
        indexes = [
            models.Index(fields=["tenant", "employee", "date"], name="hrm_att_tenant_emp_date_idx"),
            models.Index(fields=["tenant", "date", "status"], name="hrm_att_tenant_date_stat_idx"),
            models.Index(fields=["tenant", "status"], name="hrm_att_tenant_status_idx"),
        ]

    def _recompute_hours(self):
        if self.check_in and self.check_out:
            ci = datetime.combine(date.min, self.check_in)
            co = datetime.combine(date.min, self.check_out)
            seconds = (co - ci).total_seconds()
            if seconds < 0:  # overnight shift — check-out is the next calendar day
                seconds += 24 * 3600
            self.hours_worked = (Decimal(seconds) / Decimal(3600)).quantize(Decimal("0.01"))
        else:
            self.hours_worked = ZERO

    def is_late(self):
        """True when check-in is past the shift start + grace window (display-only helper).
        Compared in minutes-of-day to stay platform-safe (no epoch conversion)."""
        if not (self.check_in and self.shift_id and self.shift and self.shift.start_time):
            return False
        start_min = self.shift.start_time.hour * 60 + self.shift.start_time.minute
        check_in_min = self.check_in.hour * 60 + self.check_in.minute
        return check_in_min > start_min + self.shift.grace_minutes

    def save(self, *args, **kwargs):
        self._recompute_hours()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.number} · {self.employee} · {self.date} · {self.get_status_display()}"
