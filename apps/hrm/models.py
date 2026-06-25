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
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
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
# 3.2 Organizational Structure — JobGrade + Designation + Department/CostCenter
# companions to ``core.OrgUnit``. Departments and cost-centers are canonical
# ``core.OrgUnit`` nodes (name/parent/hierarchy live there); HRM never duplicates
# them — it adds a thin tenant-scoped companion table (head/owner/budget/code) that
# core cannot hold, mirroring how ``EmployeeProfile`` extends ``core.Party``. The org
# chart is DERIVED from ``core.Employment.manager`` + ``OrgUnit.parent`` (a view, no model).
# ---------------------------------------------------------------------------
class JobGrade(TenantOwned):
    """Orderable job-grade / level catalog (3.2). ``level_order`` ranks seniority (1 = most
    junior) for hierarchy display and org-chart level-coloring. Replaces the free-text
    ``Designation.grade`` CharField as the primary grade reference (the CharField is kept for
    back-compat). Small per-tenant catalog identified by name — not auto-numbered."""

    name = models.CharField(max_length=50)
    level_order = models.PositiveSmallIntegerField(default=1)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["level_order", "name"]
        unique_together = ("tenant", "name")
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="hrm_jg_tenant_active_idx"),
            models.Index(fields=["tenant", "level_order"], name="hrm_jg_tenant_order_idx"),
        ]

    def __str__(self):
        return f"{self.name} (L{self.level_order})" if self.level_order else self.name


class Designation(TenantOwned):
    """Job title with a job-grade, description and salary band (3.2). Department is reused from
    ``core.OrgUnit``; the grade is reused from ``hrm.JobGrade`` (the free-text ``grade`` stays
    as a fallback). ``budgeted_headcount`` is the lightweight position-slot proxy."""

    name = models.CharField(max_length=255)
    job_grade = models.ForeignKey("hrm.JobGrade", on_delete=models.SET_NULL, null=True, blank=True, related_name="designations")
    grade = models.CharField(max_length=50, blank=True)
    department = models.ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="designations")
    description = models.TextField(blank=True)
    requirements = models.TextField(blank=True)
    min_salary = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    mid_salary = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    max_salary = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    budgeted_headcount = models.PositiveSmallIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        unique_together = ("tenant", "name")
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="hrm_desig_tenant_active_idx"),
            models.Index(fields=["tenant", "department"], name="hrm_desig_tenant_dept_idx"),
            models.Index(fields=["tenant", "job_grade"], name="hrm_desig_tenant_jg_idx"),
        ]

    def clean(self):
        super().clean()
        if self.min_salary is not None and self.max_salary is not None and self.min_salary > self.max_salary:
            raise ValidationError({"max_salary": "Maximum salary must be greater than or equal to the minimum."})
        if self.mid_salary is not None:
            if self.min_salary is not None and self.mid_salary < self.min_salary:
                raise ValidationError({"mid_salary": "Midpoint salary must be at least the minimum."})
            if self.max_salary is not None and self.mid_salary > self.max_salary:
                raise ValidationError({"mid_salary": "Midpoint salary must not exceed the maximum."})

    def __str__(self):
        label = self.job_grade.name if self.job_grade else self.grade
        return f"{self.name} ({label})" if label else self.name


class DepartmentProfile(TenantOwned):
    """HRM companion to ``core.OrgUnit(kind="department")`` (3.2). Adds the HR fields core cannot
    hold — department head, cost-center mapping, mnemonic code — without duplicating the OrgUnit
    node (name/parent/hierarchy stay on OrgUnit). The ``head`` drives future approval chains."""

    org_unit = models.OneToOneField("core.OrgUnit", on_delete=models.CASCADE, related_name="department_profile")
    code = models.CharField(max_length=20, blank=True)
    description = models.TextField(blank=True)
    head = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.SET_NULL, null=True, blank=True, related_name="headed_departments")
    cost_center = models.ForeignKey(
        "core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="department_cost_mappings", limit_choices_to={"kind": "cost_center"})
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["org_unit__name"]
        unique_together = ("tenant", "org_unit")
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="hrm_dp_tenant_active_idx"),
            models.Index(fields=["tenant", "head"], name="hrm_dp_tenant_head_idx"),
            models.Index(fields=["tenant", "cost_center"], name="hrm_dp_tenant_cc_idx"),
        ]

    def clean(self):
        super().clean()
        # NOTE: the PRIMARY cross-tenant defense is the form's FK queryset scoping (org_unit/
        # cost_center are limited to the active tenant in DepartmentProfileForm). These model-level
        # tenant checks are defense-in-depth for direct ``model.save()`` (admin/shell): the view sets
        # ``tenant`` only AFTER ``form.is_valid()``, so ``tenant_id`` is None during form validation
        # and the tenant branch is skipped then (the queryset guard already covers that path).
        if self.org_unit_id:
            if self.org_unit.kind != "department":
                raise ValidationError({"org_unit": "Linked unit must be a Department."})
            if self.tenant_id and self.org_unit.tenant_id != self.tenant_id:
                raise ValidationError({"org_unit": "Department belongs to another tenant."})
        if self.cost_center_id:
            if self.cost_center.kind != "cost_center":
                raise ValidationError({"cost_center": "Linked unit must be a Cost Center."})
            if self.tenant_id and self.cost_center.tenant_id != self.tenant_id:
                raise ValidationError({"cost_center": "Cost Center belongs to another tenant."})

    def __str__(self):
        return f"{self.org_unit.name} ({self.code})" if self.code else self.org_unit.name


class CostCenterProfile(TenantOwned):
    """HRM companion to ``core.OrgUnit(kind="cost_center")`` (3.2). Adds the budget owner, annual
    budget and code core cannot hold. The CC node + its parent roll-up hierarchy live on OrgUnit;
    budget-vs-actuals reporting (against payroll spend) waits on the Accounting module."""

    org_unit = models.OneToOneField("core.OrgUnit", on_delete=models.CASCADE, related_name="cost_center_profile")
    code = models.CharField(max_length=20, blank=True)
    description = models.TextField(blank=True)
    owner = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.SET_NULL, null=True, blank=True, related_name="owned_cost_centers")
    budget_annual = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    budget_year = models.PositiveSmallIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["org_unit__name"]
        unique_together = ("tenant", "org_unit")
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="hrm_cc_tenant_active_idx"),
            models.Index(fields=["tenant", "owner"], name="hrm_cc_tenant_owner_idx"),
        ]

    def clean(self):
        super().clean()
        # Defense-in-depth (see DepartmentProfile.clean): the form queryset is the primary guard;
        # the tenant branch fires only on direct model.save() once tenant is set.
        if self.org_unit_id:
            if self.org_unit.kind != "cost_center":
                raise ValidationError({"org_unit": "Linked unit must be a Cost Center."})
            if self.tenant_id and self.org_unit.tenant_id != self.tenant_id:
                raise ValidationError({"org_unit": "Cost Center belongs to another tenant."})

    def __str__(self):
        return f"{self.org_unit.name} ({self.code})" if self.code else self.org_unit.name


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
    MARITAL_STATUS_CHOICES = [
        ("single", "Single"),
        ("married", "Married"),
        ("divorced", "Divorced"),
        ("widowed", "Widowed"),
        ("other", "Other"),
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
    # WARNING: bank_account / bank_routing are stored in plaintext for demo purposes. In
    # production, encrypt at rest (e.g. via the tenants EncryptionKey pattern) or store only a
    # tokenized/masked value. Never render the raw account number — use masked_bank_account().
    # Both are also redacted from AuditLog.changes (see core.crud._SENSITIVE_AUDIT_FIELDS).
    bank_name = models.CharField(max_length=255, blank=True)
    bank_account = models.CharField(max_length=64, blank=True)
    bank_routing = models.CharField(max_length=20, blank=True)
    probation_end_date = models.DateField(null=True, blank=True)
    confirmed_on = models.DateField(null=True, blank=True)
    notice_period_days = models.PositiveSmallIntegerField(null=True, blank=True,
        help_text="Profile-default notice period; a SeparationCase can override it per departure.")
    emergency_contact_name = models.CharField(max_length=255, blank=True)
    emergency_contact_phone = models.CharField(max_length=30, blank=True)
    emergency_contact_relation = models.CharField(max_length=100, blank=True)
    # Second emergency contact (most HRIS products support ≥2).
    emergency_contact_2_name = models.CharField(max_length=255, blank=True)
    emergency_contact_2_phone = models.CharField(max_length=30, blank=True)
    emergency_contact_2_relation = models.CharField(max_length=100, blank=True)
    # Personnel-file fields (3.1 completion — competitive HRIS parity).
    marital_status = models.CharField(max_length=20, choices=MARITAL_STATUS_CHOICES, blank=True)
    work_email = models.EmailField(blank=True, help_text="Company email, distinct from personal_email.")
    work_location = models.CharField(max_length=255, blank=True, help_text="Office / site / remote assignment.")
    father_name = models.CharField(max_length=255, blank=True)
    spouse_name = models.CharField(max_length=255, blank=True)
    # WARNING: national_id / passport_number are sensitive PII stored in plaintext for the demo —
    # encrypt at rest in production (mirror the bank_account note above). The full ID documents live
    # in EmployeeDocument; these are the quick-reference values on the profile.
    national_id = models.CharField(max_length=100, blank=True)
    national_id_type = models.CharField(max_length=50, blank=True, help_text="e.g. Aadhaar, SSN, NRIC, PAN.")
    passport_number = models.CharField(max_length=50, blank=True)
    passport_expiry = models.DateField(null=True, blank=True)
    current_address = models.TextField(blank=True)
    permanent_address = models.TextField(blank=True)
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

    @staticmethod
    def _mask_last4(value):
        v = value or ""
        return f"••••{v[-4:]}" if len(v) >= 4 else ("••••" if v else "")

    def masked_bank_account(self):
        """Last-4 view of the account number (never render the full value)."""
        return self._mask_last4(self.bank_account)

    def masked_bank_routing(self):
        """Last-4 view of the routing number (never render the full value)."""
        return self._mask_last4(self.bank_routing)

    def masked_national_id(self):
        """Last-4 view of the national ID (sensitive PII — never render the full value)."""
        return self._mask_last4(self.national_id)

    def masked_passport_number(self):
        """Last-4 view of the passport number (sensitive PII — never render the full value)."""
        return self._mask_last4(self.passport_number)

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


# ---------------------------------------------------------------------------
# 3.3 Employee Onboarding — Template → Program → Task + Documents / Assets /
# Orientation. Everything FKs ``EmployeeProfile`` (the anchor), never ``core.Party``.
# A reusable ``OnboardingTemplate`` (with typed ``OnboardingTemplateTask`` lines) is
# applied to one new hire to produce an ``OnboardingProgram`` whose concrete
# ``OnboardingTask`` rows are generated with due dates = start_date + offset. Welcome
# Kit lives as fields on the program (no separate table). ``progress`` is derived.
# ---------------------------------------------------------------------------

# Shared choice sets — referenced by both the template task definition and the concrete
# per-program task, so the taxonomy stays identical between the two (module-level = single source).
TASK_CATEGORY_CHOICES = [
    ("hr_admin", "HR Admin"),
    ("it_setup", "IT Setup"),
    ("manager_action", "Manager Action"),
    ("buddy_action", "Buddy Action"),
    ("new_hire_action", "New Hire Action"),
    ("document_sign", "Document Sign"),
    ("equipment_request", "Equipment Request"),
    ("training", "Training"),
    ("meet_greet", "Meet & Greet"),
    ("custom", "Custom"),
]
ASSIGNEE_ROLE_CHOICES = [
    ("hr", "HR"),
    ("it", "IT"),
    ("manager", "Manager"),
    ("buddy", "Buddy"),
    ("new_hire", "New Hire"),
]
PHASE_CHOICES = [
    ("preboarding", "Preboarding"),
    ("week_1", "Week 1"),
    ("month_1", "Month 1"),
    ("month_2", "Month 2"),
    ("month_3", "Month 3"),
    ("ongoing", "Ongoing"),
]


class OnboardingTemplate(TenantNumbered):
    """A reusable onboarding checklist (3.3) — applied to a new hire to spin up a program.
    Optionally tied to a ``Designation`` so HR can auto-suggest the right template per role."""

    NUMBER_PREFIX = "ONBT"

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    designation = models.ForeignKey("hrm.Designation", on_delete=models.SET_NULL, null=True, blank=True, related_name="onboarding_templates")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        unique_together = [("tenant", "number"), ("tenant", "name")]
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="hrm_onbt_tenant_active_idx"),
            models.Index(fields=["tenant", "designation"], name="hrm_onbt_tenant_desig_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.name}" if self.number else self.name


class OnboardingTemplateTask(TenantOwned):
    """One task definition line inside an ``OnboardingTemplate`` (3.3). ``due_offset_days`` is
    relative to the hire's start date (negative = preboarding, 0 = day one, positive = after)."""

    template = models.ForeignKey("hrm.OnboardingTemplate", on_delete=models.CASCADE, related_name="template_tasks")
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    task_category = models.CharField(max_length=30, choices=TASK_CATEGORY_CHOICES, default="custom")
    assignee_role = models.CharField(max_length=20, choices=ASSIGNEE_ROLE_CHOICES, default="hr")
    due_offset_days = models.IntegerField(default=0, help_text="Days relative to start date (negative = before, 0 = first day, positive = after).")
    phase = models.CharField(max_length=20, choices=PHASE_CHOICES, default="week_1")
    order = models.PositiveIntegerField(default=0)
    is_mandatory = models.BooleanField(default=True)

    class Meta:
        ordering = ["template", "phase", "order", "title"]
        unique_together = ("tenant", "template", "title")
        indexes = [
            models.Index(fields=["tenant", "template"], name="hrm_ontt_tenant_tmpl_idx"),
            models.Index(fields=["tenant", "template", "phase"], name="hrm_ontt_tenant_tmpl_phase_idx"),
        ]

    def __str__(self):
        return f"{self.template} → {self.title}"


class OnboardingProgram(TenantNumbered):
    """A template applied to one new hire (3.3) — the per-employee onboarding instance.
    ``progress`` is derived from its tasks (spine principle: never stored). The Welcome Kit
    (3.3) is the ``welcome_*`` / ``first_day_notes`` fields here — no separate table."""

    NUMBER_PREFIX = "ONB"

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("active", "Active"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.CASCADE, related_name="onboarding_programs")
    template = models.ForeignKey("hrm.OnboardingTemplate", on_delete=models.SET_NULL, null=True, blank=True, related_name="programs")
    start_date = models.DateField(help_text="The new hire's first day — drives every task due date.")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    buddy = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.SET_NULL, null=True, blank=True, related_name="buddy_for")
    welcome_message = models.TextField(blank=True)
    welcome_video_url = models.URLField(blank=True)
    first_day_notes = models.TextField(blank=True)
    completed_at = models.DateTimeField(null=True, blank=True, editable=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-start_date"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "employee"], name="hrm_onb_tenant_emp_idx"),
            models.Index(fields=["tenant", "status"], name="hrm_onb_tenant_status_idx"),
            models.Index(fields=["tenant", "start_date"], name="hrm_onb_tenant_start_idx"),
        ]

    @property
    def progress(self):
        """Percent of tasks resolved (0–100). Derived — never stored. Skipped tasks count as
        resolved so an all-skipped program reads as 100% done, not stuck. List views use the
        ``tasks_total``/``tasks_done`` annotations (no N+1); the detail view computes this from its
        already-fetched task list. Memoised so an accidental second call doesn't re-query."""
        if not hasattr(self, "_progress_cache"):
            total = self.tasks.count()
            if total:
                done = self.tasks.filter(status__in=("completed", "skipped")).count()
                self._progress_cache = int(round(done / total * 100))
            else:
                self._progress_cache = 0
        return self._progress_cache

    def __str__(self):
        return f"{self.number} · {self.employee}" if self.number else str(self.employee)


class OnboardingTask(TenantOwned):
    """A concrete task on one ``OnboardingProgram`` (3.3). Generated from the template's task
    lines (due_date = program.start_date + offset) or added ad-hoc. ``completed_at`` /
    ``completed_by`` are system-set by the complete action, never on the form."""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("skipped", "Skipped"),
    ]

    program = models.ForeignKey("hrm.OnboardingProgram", on_delete=models.CASCADE, related_name="tasks")
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    task_category = models.CharField(max_length=30, choices=TASK_CATEGORY_CHOICES, default="custom")
    assignee_role = models.CharField(max_length=20, choices=ASSIGNEE_ROLE_CHOICES, default="hr")
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_onboarding_tasks")
    due_date = models.DateField(null=True, blank=True)
    phase = models.CharField(max_length=20, choices=PHASE_CHOICES, default="week_1")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    is_mandatory = models.BooleanField(default=True)
    completed_at = models.DateTimeField(null=True, blank=True, editable=False)
    completed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="completed_onboarding_tasks", editable=False)
    order = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["program", "phase", "order", "due_date"]
        indexes = [
            models.Index(fields=["tenant", "program"], name="hrm_ont_tenant_prog_idx"),
            models.Index(fields=["tenant", "program", "status"], name="hrm_ont_tenant_prog_status_idx"),
            models.Index(fields=["tenant", "program", "phase"], name="hrm_ont_tenant_prog_phase_idx"),
        ]

    def is_overdue(self):
        """True when an unresolved task's due date has passed (display-only helper)."""
        return bool(self.due_date and self.status in ("pending", "in_progress")
                    and self.due_date < date.today())

    def __str__(self):
        return f"{self.program} → {self.title}"


class OnboardingDocument(TenantOwned):
    """A document to collect / e-sign for a program (3.3). ``esign_status`` tracks the signing
    lifecycle without a live e-sign integration; ``external_ref`` stubs a future envelope id.
    ``signed_at`` is system-set by the mark-signed action."""

    DOCUMENT_TYPE_CHOICES = [
        ("employment_contract", "Employment Contract"),
        ("nda", "NDA"),
        ("offer_letter", "Offer Letter"),
        ("id_proof", "ID Proof"),
        ("tax_form", "Tax Form"),
        ("bank_details", "Bank Details"),
        ("policy_acknowledgment", "Policy Acknowledgment"),
        ("background_check", "Background Check"),
        ("custom", "Custom"),
    ]
    ESIGN_STATUS_CHOICES = [
        ("not_required", "Not Required"),
        ("pending", "Pending"),
        ("sent", "Sent"),
        ("viewed", "Viewed"),
        ("signed", "Signed"),
        ("declined", "Declined"),
    ]

    program = models.ForeignKey("hrm.OnboardingProgram", on_delete=models.CASCADE, related_name="documents")
    document_type = models.CharField(max_length=30, choices=DOCUMENT_TYPE_CHOICES, default="custom")
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    file = models.FileField(upload_to="hrm/onboarding/docs/%Y/%m/", null=True, blank=True)
    esign_required = models.BooleanField(default=False)
    esign_status = models.CharField(max_length=20, choices=ESIGN_STATUS_CHOICES, default="not_required")
    due_date = models.DateField(null=True, blank=True)
    signed_at = models.DateTimeField(null=True, blank=True, editable=False)
    external_ref = models.CharField(max_length=255, blank=True, help_text="External e-sign envelope/reference id (future integration).")

    class Meta:
        ordering = ["program", "document_type", "title"]
        indexes = [
            models.Index(fields=["tenant", "program"], name="hrm_ond_tenant_prog_idx"),
            models.Index(fields=["tenant", "program", "esign_status"], name="hrm_ond_tenant_prog_esign_idx"),
        ]

    def save(self, *args, **kwargs):
        # ``esign_status`` is workflow-owned (not a form field) — derive its open value from the
        # ``esign_required`` toggle so it can't be hand-advanced via a crafted POST. A required doc
        # enters the signing flow at ``pending``; an unrequired one is ``not_required``. The
        # terminal ``signed`` (set by mark-signed) / ``declined`` states are never overwritten, and
        # the e-sign-provider integration states (``sent``/``viewed``) are left untouched.
        if self.esign_status not in ("signed", "declined", "sent", "viewed"):
            self.esign_status = "pending" if self.esign_required else "not_required"
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.program} → {self.title}"


class AssetAllocation(TenantNumbered):
    """A physical asset issued to a new hire (3.3) — laptop, ID card, access card, etc.
    ``returned_at`` is system-set by the return action. ``program`` is nullable so assets can be
    issued/tracked outside a formal onboarding program (and reused for offboarding returns)."""

    NUMBER_PREFIX = "AST"

    ASSET_CATEGORY_CHOICES = [
        ("laptop", "Laptop"),
        ("desktop", "Desktop"),
        ("phone", "Phone"),
        ("id_card", "ID Card"),
        ("access_card", "Access Card"),
        ("uniform", "Uniform"),
        ("vehicle", "Vehicle"),
        ("sim", "SIM Card"),
        ("other", "Other"),
    ]
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("issued", "Issued"),
        ("returned", "Returned"),
        ("lost", "Lost"),
        ("damaged", "Damaged"),
    ]

    program = models.ForeignKey("hrm.OnboardingProgram", on_delete=models.SET_NULL, null=True, blank=True, related_name="assets")
    employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.CASCADE, related_name="asset_allocations")
    asset_name = models.CharField(max_length=255)
    asset_category = models.CharField(max_length=30, choices=ASSET_CATEGORY_CHOICES, default="other")
    serial_number = models.CharField(max_length=100, blank=True)
    asset_tag = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    issued_at = models.DateTimeField(null=True, blank=True)
    issued_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="hrm_assets_issued")
    returned_at = models.DateTimeField(null=True, blank=True, editable=False)
    return_due_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    # NOTE: a nullable FK to ``assets.Asset`` (Module 11 Asset Management) belongs here once that
    # module exists — add ``asset = models.ForeignKey("assets.Asset", ...)`` in a later migration
    # to link this issuance to the canonical fixed-asset register. Stubbed for now.

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "employee"], name="hrm_ast_tenant_emp_idx"),
            models.Index(fields=["tenant", "status"], name="hrm_ast_tenant_status_idx"),
            models.Index(fields=["tenant", "program"], name="hrm_ast_tenant_prog_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.asset_name} → {self.employee}" if self.number else self.asset_name


class OrientationSession(TenantOwned):
    """A scheduled orientation / training / meet-and-greet for a new hire (3.3). ``program`` is
    nullable for ad-hoc sessions. ``meeting_url`` supports virtual sessions; ``attendance_status``
    tracks completion without full calendar integration."""

    SESSION_TYPE_CHOICES = [
        ("orientation", "Orientation"),
        ("training", "Training"),
        ("meet_greet", "Meet & Greet"),
        ("policy_review", "Policy Review"),
        ("system_demo", "System Demo"),
        ("department_intro", "Department Intro"),
        ("social", "Social / Team Lunch"),
        ("custom", "Custom"),
    ]
    ATTENDANCE_STATUS_CHOICES = [
        ("scheduled", "Scheduled"),
        ("attended", "Attended"),
        ("missed", "Missed"),
        ("rescheduled", "Rescheduled"),
        ("cancelled", "Cancelled"),
    ]

    program = models.ForeignKey("hrm.OnboardingProgram", on_delete=models.SET_NULL, null=True, blank=True, related_name="orientation_sessions")
    employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.CASCADE, related_name="orientation_sessions")
    title = models.CharField(max_length=255)
    session_type = models.CharField(max_length=30, choices=SESSION_TYPE_CHOICES, default="orientation")
    facilitator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="facilitated_orientation_sessions")
    facilitator_name = models.CharField(max_length=255, blank=True, help_text="Free-text fallback for an external trainer with no user account.")
    scheduled_at = models.DateTimeField(null=True, blank=True)
    duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    location = models.CharField(max_length=255, blank=True)
    meeting_url = models.URLField(blank=True)
    attendance_status = models.CharField(max_length=20, choices=ATTENDANCE_STATUS_CHOICES, default="scheduled")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["scheduled_at"]
        indexes = [
            models.Index(fields=["tenant", "employee"], name="hrm_ors_tenant_emp_idx"),
            models.Index(fields=["tenant", "program"], name="hrm_ors_tenant_prog_idx"),
            models.Index(fields=["tenant", "scheduled_at"], name="hrm_ors_tenant_sched_idx"),
            models.Index(fields=["tenant", "attendance_status"], name="hrm_ors_tenant_attst_idx"),
        ]

    def clean(self):
        super().clean()
        # A program session can't be scheduled before the hire even starts. Fetch only the start
        # date (not the whole program row) to keep this validation path light.
        if self.program_id and self.scheduled_at:
            start = (OnboardingProgram.objects.filter(pk=self.program_id)
                     .values_list("start_date", flat=True).first())
            if start and self.scheduled_at.date() < start:
                raise ValidationError({"scheduled_at": "Session cannot be scheduled before the program start date."})

    def __str__(self):
        return f"{self.title} @ {self.scheduled_at:%Y-%m-%d %H:%M}" if self.scheduled_at else self.title


# ---------------------------------------------------------------------------
# 3.4 Employee Offboarding — SeparationCase → ExitInterview / ClearanceItem /
# FinalSettlement. Everything FKs ``EmployeeProfile`` (the anchor) and reuses the
# existing ``AssetAllocation`` for asset-return clearance lines (no duplicate asset
# table). F&F GL posting stays with ``accounting.PayrollRun`` (``gl_posted`` is a stub).
# ---------------------------------------------------------------------------

# 1–5 Likert bound, reused across the exit-interview rating fields. A tuple so an accidental
# append in a test/migration can't leak an extra validator onto all eight fields.
_RATING_VALIDATORS = (MinValueValidator(1), MaxValueValidator(5))


class SeparationCase(TenantNumbered):
    """The master offboarding record (3.4) — one per departure event. Drives the
    resignation → approval → clearance → settlement → completion lifecycle.
    ``expected_last_working_day`` is derived in ``save()`` (notice_start_date + notice_period_days);
    ``all_mandatory_cleared`` gates the F&F release. The relieving/experience letters are generated
    from this record's fields (no separate table) and only stamp the generated-at timestamp."""

    NUMBER_PREFIX = "SEP"

    SEPARATION_TYPE_CHOICES = [
        ("resignation", "Resignation"),
        ("termination", "Termination"),
        ("layoff", "Layoff"),
        ("retirement", "Retirement"),
        ("contract_end", "End of Contract"),
        ("deceased", "Deceased"),
    ]
    EXIT_REASON_CHOICES = [
        ("better_opportunity", "Better Opportunity"),
        ("compensation", "Compensation"),
        ("career_growth", "Career Growth"),
        ("relocation", "Relocation"),
        ("health", "Health"),
        ("personal", "Personal"),
        ("retirement", "Retirement"),
        ("performance", "Performance"),
        ("policy_violation", "Policy Violation"),
        ("other", "Other"),
    ]
    NOTICE_BUYOUT_CHOICES = [
        ("none", "None"),
        ("pay_in_lieu", "Pay in Lieu of Notice"),
        ("recover", "Recover Shortfall"),
    ]
    # Lifecycle: approving a case generates its clearance checklist and moves it straight to
    # ``in_clearance`` (there is no standalone "approved" holding state).
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("pending_approval", "Pending Approval"),
        ("in_clearance", "In Clearance"),
        ("cleared", "Cleared"),
        ("settled", "Settled"),
        ("completed", "Completed"),
        ("rejected", "Rejected"),
        ("withdrawn", "Withdrawn"),
    ]
    # Statuses at which the relieving/experience letters may be generated (clearance done).
    LETTER_READY_STATUSES = ("cleared", "settled", "completed")

    employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.CASCADE, related_name="separation_cases")
    separation_type = models.CharField(max_length=20, choices=SEPARATION_TYPE_CHOICES, default="resignation")
    exit_reason = models.CharField(max_length=30, choices=EXIT_REASON_CHOICES, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True, editable=False)
    resignation_letter = models.FileField(upload_to="hrm/offboarding/letters/%Y/%m/", null=True, blank=True)
    notice_period_days = models.PositiveIntegerField(default=30)
    notice_start_date = models.DateField(null=True, blank=True, help_text="Day 1 of the notice period (usually the resignation date).")
    # Derived in save() — never hand-edited.
    expected_last_working_day = models.DateField(null=True, blank=True, editable=False)
    actual_last_working_day = models.DateField(null=True, blank=True, help_text="HR-confirmed last working day.")
    notice_buyout_type = models.CharField(max_length=20, choices=NOTICE_BUYOUT_CHOICES, default="none")
    requires_kt = models.BooleanField(default=True, help_text="Adds a Knowledge-Transfer clearance line on approval.")
    # Workflow-owned (set only by the audited workflow actions, never on the form).
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft", editable=False)
    approver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="hrm_approved_separations", editable=False)
    approved_at = models.DateTimeField(null=True, blank=True, editable=False)
    rejection_reason = models.TextField(blank=True)
    withdrawal_reason = models.TextField(blank=True)
    relieving_letter_generated_at = models.DateTimeField(null=True, blank=True, editable=False)
    relieving_letter_generated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="hrm_relieving_letters_generated", editable=False)
    experience_letter_generated_at = models.DateTimeField(null=True, blank=True, editable=False)
    experience_letter_generated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="hrm_experience_letters_generated", editable=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="hrm_sep_tenant_status_idx"),
            models.Index(fields=["tenant", "employee"], name="hrm_sep_tenant_emp_idx"),
            models.Index(fields=["tenant", "separation_type"], name="hrm_sep_tenant_type_idx"),
        ]

    @property
    def all_mandatory_cleared(self):
        """True when every *mandatory* clearance line is cleared/NA — the gate for marking the case
        cleared and generating letters. A case with no mandatory lines reads as cleared (nothing
        blocks)."""
        return not (self.clearance_items.filter(is_mandatory=True)
                    .exclude(status__in=("cleared", "not_applicable")).exists())

    def save(self, *args, **kwargs):
        # Expected LWD is always derived from the notice window — never hand-edited. Workflow actions
        # save with an explicit ``update_fields`` list; make sure the recomputed value is persisted
        # (and not silently dropped) by adding the column to that list when it isn't already there.
        if self.notice_start_date and self.notice_period_days:
            self.expected_last_working_day = self.notice_start_date + timedelta(days=self.notice_period_days)
        else:
            self.expected_last_working_day = None
        update_fields = kwargs.get("update_fields")
        if update_fields is not None and "expected_last_working_day" not in update_fields:
            kwargs["update_fields"] = list(update_fields) + ["expected_last_working_day"]
        return super().save(*args, **kwargs)

    def __str__(self):
        name = self.employee.name if self.employee_id else "—"
        return f"{self.number} · {name} ({self.get_status_display()})"


class ExitInterview(TenantNumbered):
    """A structured exit interview tied to a ``SeparationCase`` (3.4). One per case (form-guarded —
    not a DB constraint, so a skipped/no-show one can be superseded). Eight 1–5 Likert ratings + a
    coded ``primary_reason`` feed attrition insight. ``status``/``conducted_at`` are workflow-owned
    (set by the complete/skip actions, never on the form)."""

    NUMBER_PREFIX = "EI"

    MODE_CHOICES = [
        ("in_person", "In Person"),
        ("video", "Video Call"),
        ("phone", "Phone"),
        ("form", "Self-Service Form"),
    ]
    EI_STATUS_CHOICES = [
        ("scheduled", "Scheduled"),
        ("completed", "Completed"),
        ("skipped", "Skipped"),
        ("no_show", "No Show"),
    ]
    # (field, label) pairs — drives the form fieldset and the detail rating display.
    RATING_FIELDS = [
        ("rating_job_satisfaction", "Job Satisfaction"),
        ("rating_management", "Management"),
        ("rating_compensation", "Compensation"),
        ("rating_work_environment", "Work Environment"),
        ("rating_growth_opportunities", "Growth Opportunities"),
        ("rating_work_life_balance", "Work-Life Balance"),
        ("rating_culture", "Culture"),
        ("rating_overall", "Overall"),
    ]

    case = models.ForeignKey("hrm.SeparationCase", on_delete=models.CASCADE, related_name="exit_interviews")
    interviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="hrm_exit_interviews_conducted")
    scheduled_at = models.DateTimeField(null=True, blank=True)
    conducted_at = models.DateTimeField(null=True, blank=True, editable=False)
    mode = models.CharField(max_length=20, choices=MODE_CHOICES, default="in_person")
    status = models.CharField(max_length=20, choices=EI_STATUS_CHOICES, default="scheduled", editable=False)
    rating_job_satisfaction = models.SmallIntegerField(null=True, blank=True, validators=_RATING_VALIDATORS)
    rating_management = models.SmallIntegerField(null=True, blank=True, validators=_RATING_VALIDATORS)
    rating_compensation = models.SmallIntegerField(null=True, blank=True, validators=_RATING_VALIDATORS)
    rating_work_environment = models.SmallIntegerField(null=True, blank=True, validators=_RATING_VALIDATORS)
    rating_growth_opportunities = models.SmallIntegerField(null=True, blank=True, validators=_RATING_VALIDATORS)
    rating_work_life_balance = models.SmallIntegerField(null=True, blank=True, validators=_RATING_VALIDATORS)
    rating_culture = models.SmallIntegerField(null=True, blank=True, validators=_RATING_VALIDATORS)
    rating_overall = models.SmallIntegerField(null=True, blank=True, validators=_RATING_VALIDATORS)
    primary_reason = models.CharField(max_length=30, choices=SeparationCase.EXIT_REASON_CHOICES, blank=True)
    would_recommend = models.BooleanField(null=True, blank=True)
    would_rejoin = models.BooleanField(null=True, blank=True)
    what_went_well = models.TextField(blank=True)
    what_to_improve = models.TextField(blank=True)
    additional_comments = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "case"], name="hrm_ei_tenant_case_idx"),
            models.Index(fields=["tenant", "status"], name="hrm_ei_tenant_status_idx"),
            models.Index(fields=["tenant", "mode"], name="hrm_ei_tenant_mode_idx"),
        ]

    @property
    def average_rating(self):
        """Mean of the answered Likert ratings (1 decimal), or None if none answered."""
        vals = [getattr(self, f) for f, _ in self.RATING_FIELDS if getattr(self, f) is not None]
        return round(sum(vals) / len(vals), 1) if vals else None

    def __str__(self):
        name = self.case.employee.name if self.case_id and self.case.employee_id else "—"
        return f"{self.number} · Exit Interview for {name}"


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


class FinalSettlement(TenantNumbered):
    """The full-and-final settlement for a ``SeparationCase`` (3.4) — one per case (DB-enforced).
    Earnings minus deductions give the derived ``net_payable`` (never stored). ``status`` runs
    draft → computed → hr_approved → finance_approved → paid (+ cancelled). ``gl_posted`` is a stub:
    GL posting stays with ``accounting.PayrollRun`` (a later integration pass)."""

    NUMBER_PREFIX = "FNF"

    FNF_STATUS_CHOICES = [
        ("draft", "Draft"),
        ("computed", "Computed"),
        ("hr_approved", "HR Approved"),
        ("finance_approved", "Finance Approved"),
        ("paid", "Paid"),
        ("cancelled", "Cancelled"),
    ]

    case = models.ForeignKey("hrm.SeparationCase", on_delete=models.CASCADE, related_name="final_settlements")
    settlement_date = models.DateField(null=True, blank=True, help_text="Target payment date.")
    # --- Earnings ---
    prorata_salary = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    leave_encashment_days = models.DecimalField(max_digits=6, decimal_places=2, default=ZERO)
    leave_encashment_amount = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    gratuity_eligible = models.BooleanField(default=False)
    gratuity_amount = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    bonus_amount = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    reimbursement_amount = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    other_income = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    # --- Deductions ---
    notice_recovery_amount = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO, help_text="Recovery for unserved notice (or a negative value for an employer buyout payout).")
    loan_recovery = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    asset_deduction = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    advance_recovery = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    tax_deduction = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    professional_tax = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    other_deduction = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    # --- Workflow-owned ---
    status = models.CharField(max_length=20, choices=FNF_STATUS_CHOICES, default="draft", editable=False)
    hr_approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="hrm_fnf_hr_approved", editable=False)
    hr_approved_at = models.DateTimeField(null=True, blank=True, editable=False)
    finance_approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="hrm_fnf_finance_approved", editable=False)
    finance_approved_at = models.DateTimeField(null=True, blank=True, editable=False)
    paid_at = models.DateField(null=True, blank=True, editable=False)
    notes = models.TextField(blank=True)
    gl_posted = models.BooleanField(default=False, editable=False, help_text="GL-posting stub — always False in v1 (posting deferred to accounting.PayrollRun).")

    class Meta:
        ordering = ["-created_at"]
        unique_together = [("tenant", "number"), ("tenant", "case")]
        indexes = [
            models.Index(fields=["tenant", "status"], name="hrm_fnf_tenant_status_idx"),
            models.Index(fields=["tenant", "case"], name="hrm_fnf_tenant_case_idx"),
        ]

    @property
    def total_earnings(self):
        return (self.prorata_salary + self.leave_encashment_amount + self.gratuity_amount
                + self.bonus_amount + self.reimbursement_amount + self.other_income)

    @property
    def total_deductions(self):
        return (self.notice_recovery_amount + self.loan_recovery + self.asset_deduction
                + self.advance_recovery + self.tax_deduction + self.professional_tax
                + self.other_deduction)

    @property
    def net_payable(self):
        """Derived — never stored. Total earnings minus total deductions."""
        return self.total_earnings - self.total_deductions

    def __str__(self):
        name = self.case.employee.name if self.case_id and self.case.employee_id else "—"
        return f"{self.number} · FnF for {name} [{self.get_status_display()}]"


# ---------------------------------------------------------------------------
# 3.1 Employee Management (completion) — EmployeeDocument (personnel-file vault) +
# EmployeeLifecycleEvent (dated job-history timeline). Both FK ``EmployeeProfile``
# (the anchor) — distinct from ``OnboardingDocument`` (program e-sign) and the generic
# ``core.Document``. Children of the employee, not co-equal sub-module entities.
# ---------------------------------------------------------------------------
class EmployeeDocument(TenantNumbered):
    """A personnel-file document for one employee (3.1 Document Management) — ID proof, passport,
    visa, certificate, contract, NDA, etc. ``verification_status`` is workflow-owned (HR verifies/
    rejects); ``is_expired``/``is_expiring_soon`` are derived from ``expires_on``."""

    NUMBER_PREFIX = "EDOC"

    DOCUMENT_TYPE_CHOICES = [
        ("national_id", "National ID / Aadhaar / NRIC"),
        ("passport", "Passport"),
        ("driving_license", "Driving License"),
        ("address_proof", "Address Proof"),
        ("visa", "Visa"),
        ("work_permit", "Work Permit"),
        ("degree_certificate", "Degree / Diploma Certificate"),
        ("professional_cert", "Professional Certification"),
        ("appointment_letter", "Appointment Letter"),
        ("employment_contract", "Employment Contract"),
        ("nda", "Non-Disclosure Agreement"),
        ("non_compete", "Non-Compete Agreement"),
        ("tax_form", "Tax Form (W-4 / Form 16 / TDS)"),
        ("bank_proof", "Bank Account Proof"),
        ("pf_nomination", "PF / Pension Nomination"),
        ("medical_cert", "Medical / Fitness Certificate"),
        ("background_check", "Background Check Report"),
        ("experience_certificate", "Previous Employment / Experience Letter"),
        ("other", "Other"),
    ]
    VERIFICATION_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("verified", "Verified"),
        ("rejected", "Rejected"),
    ]

    employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.CASCADE, related_name="documents")
    document_type = models.CharField(max_length=30, choices=DOCUMENT_TYPE_CHOICES, default="other")
    title = models.CharField(max_length=255)
    document_number = models.CharField(max_length=100, blank=True, help_text="The alphanumeric ID on the document itself (passport no., PAN, licence no.).")
    issuing_authority = models.CharField(max_length=255, blank=True)
    issuing_country = models.CharField(max_length=100, blank=True)
    issued_on = models.DateField(null=True, blank=True)
    expires_on = models.DateField(null=True, blank=True, help_text="Leave blank for documents that do not expire.")
    is_confidential = models.BooleanField(default=False, help_text="HR-only visibility flag.")
    file = models.FileField(upload_to="hrm/employee_docs/%Y/%m/", null=True, blank=True)
    # Workflow-owned — set only by the mark-verified / reject POST actions, never on the form.
    verification_status = models.CharField(max_length=20, choices=VERIFICATION_STATUS_CHOICES, default="pending", editable=False)
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="hrm_verified_documents", editable=False)
    verified_at = models.DateTimeField(null=True, blank=True, editable=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "employee"], name="hrm_edoc_tenant_emp_idx"),
            models.Index(fields=["tenant", "document_type"], name="hrm_edoc_tenant_type_idx"),
            models.Index(fields=["tenant", "verification_status"], name="hrm_edoc_tenant_vstat_idx"),
            models.Index(fields=["tenant", "expires_on"], name="hrm_edoc_tenant_expiry_idx"),
        ]

    @property
    def is_expired(self):
        """True when the document has an expiry that is already in the past."""
        return self.expires_on is not None and self.expires_on < date.today()

    @property
    def is_expiring_soon(self):
        """True when the document expires within the next 30 days (and is not already expired)."""
        if self.expires_on is None:
            return False
        days = (self.expires_on - date.today()).days
        return 0 <= days <= 30

    def __str__(self):
        return f"{self.number} · {self.title}"


# Module-level so the form, views and templates share one source for the event taxonomy.
LIFECYCLE_EVENT_TYPE_CHOICES = [
    ("hire", "Hire"),
    ("confirmation", "Confirmation (Probation End)"),
    ("transfer", "Transfer"),
    ("promotion", "Promotion"),
    ("demotion", "Demotion"),
    ("salary_revision", "Salary Revision"),
    ("re_designation", "Re-designation"),
    ("location_change", "Location Change"),
    ("reporting_change", "Reporting Manager Change"),
    ("suspension", "Suspension"),
    ("reinstatement", "Reinstatement"),
    ("contract_renewal", "Contract Renewal"),
    ("separation", "Separation"),
    ("other", "Other"),
]


class EmployeeLifecycleEvent(TenantNumbered):
    """An append-only, dated record of a single job-change event (3.1 Employee Lifecycle) — hire,
    confirmation, transfer, promotion, salary revision, separation, etc. Populate only the from→to
    fields relevant to the event type. v1 records the timeline; it does NOT auto-mutate
    ``core.Employment``/``EmployeeProfile`` (a deferred bidirectional-sync enhancement)."""

    NUMBER_PREFIX = "ELC"

    employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.CASCADE, related_name="lifecycle_events")
    event_type = models.CharField(max_length=30, choices=LIFECYCLE_EVENT_TYPE_CHOICES, default="other")
    effective_date = models.DateField()
    reason = models.TextField(blank=True)
    # From / To capture — all nullable/blank; fill only what the event changes.
    from_designation = models.ForeignKey("hrm.Designation", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    to_designation = models.ForeignKey("hrm.Designation", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    from_department = models.ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    to_department = models.ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    from_location = models.CharField(max_length=255, blank=True)
    to_location = models.CharField(max_length=255, blank=True)
    from_job_title = models.CharField(max_length=255, blank=True)
    to_job_title = models.CharField(max_length=255, blank=True)
    from_salary = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    to_salary = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    from_manager = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    to_manager = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    from_employee_type = models.CharField(max_length=20, blank=True)
    to_employee_type = models.CharField(max_length=20, blank=True)
    notes = models.TextField(blank=True)
    initiated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="hrm_initiated_lifecycle_events", editable=False)

    class Meta:
        ordering = ["-effective_date", "-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "employee", "effective_date"], name="hrm_elc_tenant_emp_date_idx"),
            models.Index(fields=["tenant", "event_type"], name="hrm_elc_tenant_type_idx"),
            models.Index(fields=["tenant", "employee", "event_type"], name="hrm_elc_tenant_emp_type_idx"),
            models.Index(fields=["tenant", "effective_date"], name="hrm_elc_tenant_effdate_idx"),
        ]

    def __str__(self):
        name = self.employee.name if self.employee_id else "—"
        return f"{self.number} · {name} — {self.get_event_type_display()} ({self.effective_date})"
