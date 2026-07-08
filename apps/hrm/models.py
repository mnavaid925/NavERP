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
import calendar
import math
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import IntegrityError, models, transaction
from django.db.models import Count, Q, Sum
from django.utils import timezone

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
    # Days rolled in from the prior year by the carry-forward run (a subset of allocated_days). Kept
    # separate so a re-run replaces its own prior contribution instead of double-adding (idempotent).
    carried_forward = models.DecimalField(max_digits=5, decimal_places=2, default=0, editable=False)
    # Days consumed by APPROVED LeaveEncashment payouts. Tracked separately from allocated_days so the
    # accrual engine (which recomputes allocated_days = accrued + carried_forward) can't silently
    # restore cashed-out days on a re-run — balance nets this out instead.
    encashed_days = models.DecimalField(max_digits=5, decimal_places=2, default=0, editable=False)
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
        return (self.allocated_days or ZERO) - self.used_days - (self.encashed_days or ZERO)

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


class LeaveEncashment(TenantNumbered):
    """Convert unused, encashable leave into a cash payout (3.10 Leave Policy). Workflow
    ``draft → pending → approved → paid`` (+ ``rejected``/``cancelled``), mirroring ``LeaveRequest``.
    ``amount`` is recomputed in ``save()`` from ``days × rate_per_day`` (never hand-edited). On
    **approval** the matching ``LeaveAllocation.allocated_days`` is reduced by ``days`` — encashment
    consumes the balance (see ``views.leaveencashment_approve``)."""

    NUMBER_PREFIX = "ENC"

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("paid", "Paid"),
        ("rejected", "Rejected"),
        ("cancelled", "Cancelled"),
    ]
    OPEN_STATUSES = ("draft", "pending")

    employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.CASCADE, related_name="leave_encashments")
    leave_type = models.ForeignKey("hrm.LeaveType", on_delete=models.CASCADE, related_name="encashments")
    year = models.PositiveSmallIntegerField()
    days = models.DecimalField(max_digits=6, decimal_places=2)
    rate_per_day = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount = models.DecimalField(max_digits=14, decimal_places=2, default=0, editable=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    approver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="hrm_encashment_approvals")
    approved_at = models.DateTimeField(null=True, blank=True)
    paid_on = models.DateField(null=True, blank=True)
    payment_reference = models.CharField(max_length=100, blank=True)
    decision_note = models.TextField(blank=True)

    class Meta:
        ordering = ["-year", "-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "employee", "status"], name="hrm_enc_tenant_emp_status_idx"),
            models.Index(fields=["tenant", "status"], name="hrm_enc_tenant_status_idx"),
            models.Index(fields=["tenant", "leave_type", "year"], name="hrm_enc_tenant_type_year_idx"),
        ]

    def clean(self):
        super().clean()
        if (self.days or ZERO) <= ZERO:
            raise ValidationError({"days": "Days to encash must be greater than zero."})
        if self.leave_type_id and self.leave_type and not self.leave_type.encashable:
            raise ValidationError({"leave_type": "This leave type is not marked encashable."})
        # Cannot encash more than the current balance. ``employee`` is already tenant-scoped by the
        # form, so filtering by employee/leave_type/year (no tenant) is safe and avoids a tenant-None
        # gap (the view sets tenant only after form validation).
        if self.employee_id and self.leave_type_id and self.year:
            alloc = (LeaveAllocation.objects
                     .filter(employee_id=self.employee_id, leave_type_id=self.leave_type_id, year=self.year)
                     .first())
            available = alloc.balance if alloc else ZERO
            if self.days and self.days > available:
                raise ValidationError({"days": f"Only {available} day(s) available to encash for {self.year}."})

    def save(self, *args, **kwargs):
        self.amount = ((self.days or ZERO) * (self.rate_per_day or ZERO)).quantize(Decimal("0.01"))
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.number} · {self.employee} · {self.leave_type} · {self.year}"


# ---------------------------------------------------------------------------
# 3.11 Time Tracking — Timesheet (+ TimesheetEntry lines) + OvertimeRequest
# ---------------------------------------------------------------------------
class Timesheet(TenantNumbered):
    """A weekly timesheet header per employee (3.11). ``total_hours``/``billable_hours`` are
    **derived** — recomputed by ``refresh_totals()`` from the child ``TimesheetEntry`` rows, never
    hand-typed (mirrors ``LeaveRequest.days``). Workflow ``draft → pending → approved/rejected``
    (+ ``cancelled``), mirroring ``LeaveRequest``; entries lock once the sheet is approved."""

    NUMBER_PREFIX = "TS"

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("cancelled", "Cancelled"),
    ]
    OPEN_STATUSES = ("draft", "pending")

    employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.CASCADE, related_name="timesheets")
    period_start = models.DateField()
    period_end = models.DateField()
    total_hours = models.DecimalField(max_digits=6, decimal_places=2, default=0, editable=False)
    billable_hours = models.DecimalField(max_digits=6, decimal_places=2, default=0, editable=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    approver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="hrm_timesheet_approvals")
    approved_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.TextField(blank=True)
    rejected_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-period_start"]
        unique_together = [("tenant", "number"), ("tenant", "employee", "period_start")]
        indexes = [
            models.Index(fields=["tenant", "employee", "status"], name="hrm_ts_tenant_emp_status_idx"),
            models.Index(fields=["tenant", "status"], name="hrm_ts_tenant_status_idx"),
            models.Index(fields=["tenant", "period_start"], name="hrm_ts_tenant_period_idx"),
        ]

    def clean(self):
        super().clean()
        if self.period_start and self.period_end and self.period_end < self.period_start:
            raise ValidationError({"period_end": "Period end cannot be before period start."})
        # On edit, the (possibly narrowed) period must still cover every existing entry's date —
        # otherwise a header edit could strand entries outside the period the entry clean() enforces.
        if self.pk and self.period_start and self.period_end:
            if self.entries.exclude(date__gte=self.period_start, date__lte=self.period_end).exists():
                raise ValidationError({"period_start": "This period no longer covers existing time "
                                       "entries — adjust or remove those entries first."})

    def refresh_totals(self, save=True):
        """Recompute total/billable hours from the child entries in a single aggregate pass.
        Called after any entry add/edit/delete and on approval. No-op if the row isn't saved yet
        (a brand-new header has no pk and therefore no entries)."""
        if not self.pk:
            return
        agg = self.entries.aggregate(
            total=Sum("hours"),
            billable=Sum("hours", filter=Q(is_billable=True)))
        self.total_hours = agg["total"] or ZERO
        self.billable_hours = agg["billable"] or ZERO
        if save:
            super().save(update_fields=["total_hours", "billable_hours", "updated_at"])

    def __str__(self):
        return f"{self.number} · {self.employee} · {self.period_start}…{self.period_end}"


class TimesheetEntry(TenantOwned):
    """A single time-log line on a ``Timesheet`` (3.11) — a day's hours against an optional
    ``accounting.Project`` (2.9 job-costing spine) + a free-text task. Billable value
    (``hours × billable_rate``) and utilization are **derived report aggregates**, never stored.
    ``task_description`` is free text until Project Management (Module 7) ships a Task/WBS model."""

    timesheet = models.ForeignKey("hrm.Timesheet", on_delete=models.CASCADE, related_name="entries")
    date = models.DateField()
    # Optional so admin / non-project time is loggable; SET_NULL keeps the line if the project is purged.
    project = models.ForeignKey("accounting.Project", on_delete=models.SET_NULL, null=True, blank=True, related_name="hrm_timesheet_entries")
    task_description = models.CharField(max_length=255, blank=True)
    hours = models.DecimalField(max_digits=5, decimal_places=2)
    is_billable = models.BooleanField(default=True)
    billable_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["date"]
        indexes = [
            models.Index(fields=["tenant", "timesheet"], name="hrm_tse_tenant_ts_idx"),
            models.Index(fields=["tenant", "project"], name="hrm_tse_tenant_proj_idx"),
            models.Index(fields=["tenant", "date"], name="hrm_tse_tenant_date_idx"),
        ]

    def clean(self):
        super().clean()
        if (self.hours or ZERO) <= ZERO:
            raise ValidationError({"hours": "Hours must be greater than zero."})
        if self.timesheet_id and self.timesheet and self.date:
            ts = self.timesheet
            if ts.period_start and ts.period_end and not (ts.period_start <= self.date <= ts.period_end):
                raise ValidationError({"date": "Date must fall within the timesheet's period."})

    @property
    def billable_value(self):
        """Derived line value — only counts when the line is flagged billable."""
        return (self.hours or ZERO) * (self.billable_rate or ZERO) if self.is_billable else ZERO

    def __str__(self):
        return f"{self.timesheet.number if self.timesheet_id else '—'} · {self.date} · {self.hours}h"


class OvertimeRequest(TenantNumbered):
    """An overtime claim (3.11) — daily OT hours at a configurable multiplier, paid out or converted
    to comp-leave. Approval workflow ``draft → pending → approved/rejected`` (+ ``cancelled``),
    mirroring ``LeaveEncashment``. No stored currency ``amount`` — there is no stable employee
    pay-rate source yet (3.13 Salary Structure); ``overtime_pay_equivalent_hours`` is derived."""

    NUMBER_PREFIX = "OT"

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("cancelled", "Cancelled"),
    ]
    OPEN_STATUSES = ("draft", "pending")

    PAYOUT_CHOICES = [
        ("pay", "Pay"),
        ("comp_leave", "Compensatory Leave"),
    ]

    employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.CASCADE, related_name="overtime_requests")
    timesheet = models.ForeignKey("hrm.Timesheet", on_delete=models.SET_NULL, null=True, blank=True, related_name="overtime_requests")
    date = models.DateField()
    hours_claimed = models.DecimalField(max_digits=5, decimal_places=2)
    multiplier = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal("1.50"),
                                     validators=[MinValueValidator(Decimal("1"))])
    payout_method = models.CharField(max_length=20, choices=PAYOUT_CHOICES, default="pay")
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    approver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="hrm_overtime_approvals")
    approved_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.TextField(blank=True)

    class Meta:
        ordering = ["-date"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "employee", "status"], name="hrm_ot_tenant_emp_status_idx"),
            models.Index(fields=["tenant", "status"], name="hrm_ot_tenant_status_idx"),
            models.Index(fields=["tenant", "date"], name="hrm_ot_tenant_date_idx"),
        ]

    def clean(self):
        super().clean()
        if (self.hours_claimed or ZERO) <= ZERO:
            raise ValidationError({"hours_claimed": "Overtime hours must be greater than zero."})
        # A linked timesheet must belong to the same employee (both are tenant-scoped independently).
        if self.timesheet_id and self.employee_id and self.timesheet.employee_id != self.employee_id:
            raise ValidationError({"timesheet": "The linked timesheet belongs to a different employee."})

    @property
    def overtime_pay_equivalent_hours(self):
        """Derived: the multiplier-weighted OT hours (e.g. 4h at 1.5× = 6.0 pay-equivalent hours).
        The currency payout is deferred until a stable pay-rate source (3.13) exists."""
        return (self.hours_claimed or ZERO) * (self.multiplier or ZERO)

    def __str__(self):
        return f"{self.number} · {self.employee} · {self.date} · {self.hours_claimed}h"


# ---------------------------------------------------------------------------
# 3.12 Holiday Management — PublicHoliday + HolidayPolicy + FloatingHolidayElection
# ---------------------------------------------------------------------------
class PublicHoliday(TenantOwned):
    """Tenant-scoped holiday calendar (3.12 — "Holiday Calendar" bullet). Non-optional holidays
    are excluded from ``LeaveRequest.days``; optional (floating) holidays are not — an employee
    instead elects them via ``FloatingHolidayElection``. ``category`` classifies the entry
    (national / regional / company / observance) for filtering."""

    CATEGORY_CHOICES = [
        ("national", "National"),
        ("regional", "Regional"),
        ("company", "Company"),
        ("observance", "Observance"),
    ]

    date = models.DateField()
    name = models.CharField(max_length=255)
    is_optional = models.BooleanField(default=False)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="national")

    class Meta:
        ordering = ["date"]
        unique_together = ("tenant", "date", "name")
        indexes = [
            models.Index(fields=["tenant", "date"], name="hrm_holiday_tenant_date_idx"),
        ]

    def __str__(self):
        return f"{self.date} — {self.name}"


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


class FloatingHolidayElection(TenantOwned):
    """An employee's election of one optional (floating) holiday (3.12 — "Floating Holidays"
    bullet). Only ``is_optional=True`` holidays are electable; the governing ``HolidayPolicy``'s
    ``floating_holiday_quota`` caps how many an employee may take per year (the "restriction
    rules"). Approvals mirror the ``LeaveRequest`` workflow: pending → approved/rejected via the
    privileged view actions (``status``/``approved_by``/``approved_at`` are never form fields)."""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    employee = models.ForeignKey(
        "hrm.EmployeeProfile", on_delete=models.CASCADE, related_name="floating_holiday_elections")
    holiday = models.ForeignKey(
        "hrm.PublicHoliday", on_delete=models.CASCADE, related_name="floating_elections")
    policy = models.ForeignKey(
        "hrm.HolidayPolicy", on_delete=models.SET_NULL, null=True, blank=True, related_name="elections",
        help_text="The governing policy (auto-resolved from the employee if left blank).")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    requested_on = models.DateField(default=timezone.localdate)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="hrm_floating_holiday_approvals", editable=False)
    approved_at = models.DateTimeField(null=True, blank=True, editable=False)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["-requested_on"]
        unique_together = ("tenant", "employee", "holiday")
        indexes = [
            models.Index(fields=["tenant", "employee", "status"], name="hrm_fhe_tenant_emp_status_idx"),
            models.Index(fields=["tenant", "status"], name="hrm_fhe_tenant_status_idx"),
        ]

    def clean(self):
        super().clean()
        if self.holiday_id and not self.holiday.is_optional:
            raise ValidationError({"holiday": "Only optional (floating) holidays can be elected."})
        if self.employee_id and self.holiday_id:
            # ``tenant`` isn't set on the instance during ModelForm validation on create
            # (the view assigns it after ``is_valid()``), so derive it from the employee — an
            # election always shares its employee's tenant. Without this the quota count below
            # would filter on ``tenant_id=None`` and silently pass.
            tenant_id = self.tenant_id or self.employee.tenant_id
            # Resolve + STORE the governing policy here so save() doesn't re-scan for it — the normal
            # ModelForm flow runs clean() before save(), so save()'s auto-resolve becomes a no-op.
            # (A direct .save() that bypasses clean(), e.g. the seeder, still auto-resolves in save().)
            if self.policy_id is None:
                self.policy = HolidayPolicy.for_employee(self.employee)
            policy = self.policy
            if policy is not None and policy.floating_holiday_quota:
                year = self.holiday.date.year
                taken = (FloatingHolidayElection.objects
                         .filter(tenant_id=tenant_id, employee_id=self.employee_id,
                                 status__in=("pending", "approved"), holiday__date__year=year)
                         .exclude(pk=self.pk).count())
                if taken + 1 > policy.floating_holiday_quota:
                    raise ValidationError({"holiday":
                        f"Quota exceeded — {policy.name} allows {policy.floating_holiday_quota} "
                        f"floating holiday(s) in {year}."})

    def save(self, *args, **kwargs):
        # Auto-resolve the governing policy from the employee when not explicitly chosen.
        if self.policy_id is None and self.employee_id:
            self.policy = HolidayPolicy.for_employee(self.employee)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.employee} · {self.holiday} · {self.get_status_display()}"


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
    # Geofencing (3.9): GPS coordinates captured at the punch + the zone it is checked against.
    # ``is_within_geofence`` (verified/outside/unknown) is DERIVED via ``geo_status()`` — not stored.
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True,
                                   validators=[MinValueValidator(Decimal("-90")), MaxValueValidator(Decimal("90"))])
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True,
                                    validators=[MinValueValidator(Decimal("-180")), MaxValueValidator(Decimal("180"))])
    geofence = models.ForeignKey("hrm.GeoFence", on_delete=models.SET_NULL, null=True, blank=True, related_name="attendance_records")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-date"]
        unique_together = [("tenant", "number"), ("tenant", "employee", "date")]
        indexes = [
            models.Index(fields=["tenant", "employee", "date"], name="hrm_att_tenant_emp_date_idx"),
            models.Index(fields=["tenant", "date", "status"], name="hrm_att_tenant_date_stat_idx"),
            models.Index(fields=["tenant", "status"], name="hrm_att_tenant_status_idx"),
            # Geofence-scoped lookups: geofence_detail's recent-punches list + geofence_delete's guard.
            models.Index(fields=["tenant", "geofence"], name="hrm_att_tenant_geofence_idx"),
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

    def has_geo(self):
        """True when a GPS coordinate pair was captured for this punch."""
        return self.latitude is not None and self.longitude is not None

    def geo_status(self):
        """DERIVED geofence verification for display/reporting (never stored):
        ``"verified"`` inside the linked zone, ``"outside"`` beyond its radius, ``""`` when
        there is no coordinate pair or no zone to check against. Evaluated against the zone's
        live radius regardless of ``is_active`` — a punch reflects where it happened."""
        if not (self.has_geo() and self.geofence_id and self.geofence):
            return ""
        return "verified" if self.geofence.contains(self.latitude, self.longitude) else "outside"

    def clean(self):
        super().clean()
        # GPS coordinates are a pair (both or neither); a geofence needs coordinates to check against.
        if (self.latitude is None) != (self.longitude is None):
            raise ValidationError({"longitude": "Provide both latitude and longitude, or neither."})
        if self.geofence_id and self.latitude is None:
            raise ValidationError({"geofence": "Set the punch coordinates to check against this geofence."})

    def save(self, *args, **kwargs):
        self._recompute_hours()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.number} · {self.employee} · {self.date} · {self.get_status_display()}"


# ---------------------------------------------------------------------------
# 3.9 Attendance Management — Geofencing (GeoFence) + Attendance Regularization
# ---------------------------------------------------------------------------
class GeoFence(TenantOwned):
    """A GPS geofence zone for field/site attendance (3.9). A punch's coordinates are checked
    against the zone centre + ``radius_m`` via the haversine ``distance_to`` — real proximity
    maths, not a stub. Small per-tenant catalog identified by name (not auto-numbered)."""

    EARTH_RADIUS_M = 6_371_000  # mean Earth radius, metres

    name = models.CharField(max_length=100)
    address = models.CharField(max_length=255, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6,
                                   validators=[MinValueValidator(Decimal("-90")), MaxValueValidator(Decimal("90"))])
    longitude = models.DecimalField(max_digits=9, decimal_places=6,
                                    validators=[MinValueValidator(Decimal("-180")), MaxValueValidator(Decimal("180"))])
    radius_m = models.PositiveIntegerField(default=100, validators=[MinValueValidator(1)],
                                           help_text="Allowed radius from the centre point, in metres.")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        unique_together = ("tenant", "name")
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="hrm_geo_tenant_active_idx"),
        ]

    def distance_to(self, lat, lng):
        """Great-circle distance in metres from this zone's centre to (lat, lng) via the
        haversine formula. Accepts Decimal or float; returns a float (metres)."""
        lat1, lng1 = math.radians(float(self.latitude)), math.radians(float(self.longitude))
        lat2, lng2 = math.radians(float(lat)), math.radians(float(lng))
        dlat, dlng = lat2 - lat1, lng2 - lng1
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
        return self.EARTH_RADIUS_M * 2 * math.asin(math.sqrt(a))

    def contains(self, lat, lng):
        """True when (lat, lng) is within ``radius_m`` of the zone centre."""
        if lat is None or lng is None:
            return False
        return self.distance_to(lat, lng) <= self.radius_m

    def __str__(self):
        return f"{self.name} (r={self.radius_m}m)"


class AttendanceRegularization(TenantNumbered):
    """Employee-raised request to correct an attendance punch (3.9) — missed/forgotten/erroneous
    check-in-out. Approval workflow ``draft → pending → approved/rejected`` (+ ``cancelled``),
    mirroring ``LeaveRequest``. On approval the requested times are written back onto the linked
    ``AttendanceRecord`` and its status set to ``regularized`` (see ``views.attendanceregularization_approve``)."""

    NUMBER_PREFIX = "REG"

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("cancelled", "Cancelled"),
    ]
    OPEN_STATUSES = ("draft", "pending")

    REASON_TYPE_CHOICES = [
        ("missed_punch", "Missed Punch"),
        ("forgot_checkin", "Forgot Check-In"),
        ("forgot_checkout", "Forgot Check-Out"),
        ("wrong_time", "Wrong Time Recorded"),
        ("on_duty", "On Official Duty"),
        ("work_from_home", "Work From Home"),
        ("system_error", "System / Device Error"),
        ("other", "Other"),
    ]

    employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.CASCADE, related_name="attendance_regularizations")
    # The record being corrected. SET_NULL (not CASCADE) keeps the regularization audit trail even if
    # the attendance row is later purged; optional so an employee can raise one before any row exists.
    attendance_record = models.ForeignKey("hrm.AttendanceRecord", on_delete=models.SET_NULL,
                                          null=True, blank=True, related_name="regularizations")
    date = models.DateField()
    reason_type = models.CharField(max_length=20, choices=REASON_TYPE_CHOICES, default="missed_punch")
    requested_check_in = models.TimeField(null=True, blank=True)
    requested_check_out = models.TimeField(null=True, blank=True)
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    approver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="hrm_regularization_approvals")
    approved_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.TextField(blank=True)

    class Meta:
        ordering = ["-date"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "employee", "status"], name="hrm_reg_tenant_emp_status_idx"),
            models.Index(fields=["tenant", "status"], name="hrm_reg_tenant_status_idx"),
            models.Index(fields=["tenant", "date"], name="hrm_reg_tenant_date_idx"),
        ]

    def clean(self):
        super().clean()
        # A linked record must belong to the same employee — otherwise approval would rewrite
        # another person's punch.
        if self.attendance_record_id and self.employee_id and self.attendance_record.employee_id != self.employee_id:
            raise ValidationError({"attendance_record": "The linked attendance record belongs to a different employee."})
        if not (self.requested_check_in or self.requested_check_out):
            raise ValidationError({"requested_check_in": "Provide at least one of requested check-in / check-out."})

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


# ---------------------------------------------------------------------------
# 3.5 Job Requisition — the "authorization to hire" record + its reusable JD
# template library + the sequential approval chain. A requisition reuses the
# spine: the role/salary-band come from ``hrm.Designation`` (+ ``JobGrade``),
# hiring_manager/recruiter are ``hrm.EmployeeProfile`` rows, and department /
# cost_center are ``core.OrgUnit`` nodes. The future Candidate (3.6) / Interview
# (3.7) / Offer (3.8) sub-modules will FK *into* ``JobRequisition`` — it does NOT
# reference them (they don't exist yet), so 3.5 is fully self-contained.
# ---------------------------------------------------------------------------

# Shared choice constants (module-level — reused by JobDescriptionTemplate, JobRequisition,
# RequisitionApproval, the forms' filter dropdowns, and the seeder).
EMPLOYMENT_TYPE_CHOICES = [
    ("full_time", "Full-Time"),
    ("part_time", "Part-Time"),
    ("contract", "Contract"),
    ("intern", "Intern"),
    ("consultant", "Consultant"),
]

REQ_TYPE_CHOICES = [
    ("standard", "Standard"),
    ("backfill", "Backfill"),
    ("replacement", "Replacement"),
    ("evergreen", "Evergreen / Pipeline"),
]

REASON_FOR_HIRE_CHOICES = [
    ("new_headcount", "New Headcount"),
    ("backfill", "Backfill Vacancy"),
    ("replacement", "Replacement"),
    ("project", "Project / Fixed Term"),
    ("contractor_to_perm", "Contractor to Permanent"),
]

POSTING_TYPE_CHOICES = [
    ("internal", "Internal Only"),
    ("external", "External Only"),
    ("both", "Internal & External"),
]

PRIORITY_CHOICES = [
    ("low", "Low"),
    ("medium", "Medium"),
    ("high", "High"),
    ("urgent", "Urgent"),
]

JR_STATUS_CHOICES = [
    ("draft", "Draft"),
    ("pending_approval", "Pending Approval"),
    ("approved", "Approved"),
    ("posted", "Posted"),
    ("on_hold", "On Hold"),
    ("filled", "Filled"),
    ("cancelled", "Cancelled"),
    ("rejected", "Rejected"),
]

APPROVAL_STEP_STATUS_CHOICES = [
    ("pending", "Pending"),
    ("approved", "Approved"),
    ("rejected", "Rejected"),
    ("returned", "Returned for Revision"),
    ("skipped", "Skipped"),
]

APPROVER_ROLE_CHOICES = [
    ("hiring_manager", "Hiring Manager"),
    ("hr", "HR"),
    ("finance", "Finance"),
    ("executive", "Executive"),
    ("custom", "Custom"),
]


class JobDescriptionTemplate(TenantNumbered):
    """Reusable job-description library (3.5). Optionally tied to a ``Designation`` so a
    requisition raised for that role can auto-suggest the template (mirrors
    ``OnboardingTemplate.designation``). Applying a template copies its ``jd_*`` text onto the
    requisition (copy-on-apply, not a live link), so editing the template never silently mutates
    open requisitions."""

    NUMBER_PREFIX = "JDTMPL"

    name = models.CharField(max_length=255)
    designation = models.ForeignKey("hrm.Designation", on_delete=models.SET_NULL, null=True,
                                    blank=True, related_name="jd_templates")
    employment_type = models.CharField(max_length=20, blank=True, choices=EMPLOYMENT_TYPE_CHOICES)
    jd_summary = models.TextField(blank=True)
    jd_responsibilities = models.TextField(blank=True)
    jd_requirements = models.TextField(blank=True)
    jd_nice_to_have = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        unique_together = ("tenant", "name")
        indexes = [
            models.Index(fields=["tenant", "designation"], name="hrm_jdtmpl_tenant_desig_idx"),
            models.Index(fields=["tenant", "is_active"], name="hrm_jdtmpl_tenant_active_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.name}"


class JobRequisition(TenantNumbered):
    """The hub "authorization to hire" record (3.5). One per opening event; drives the
    draft → pending_approval → approved → posted → filled lifecycle (+ on_hold / rejected /
    cancelled). The JD body fields are an opening-specific *copy* (distinct from the evergreen
    ``Designation.description``). Workflow-owned fields (status + the ``*_at`` stamps) are
    ``editable=False`` and set only by the audited POST actions — never on the form."""

    NUMBER_PREFIX = "JR"

    # Identity
    title = models.CharField(max_length=255)
    designation = models.ForeignKey("hrm.Designation", on_delete=models.SET_NULL, null=True,
                                    blank=True, related_name="requisitions")
    job_grade = models.ForeignKey("hrm.JobGrade", on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name="requisitions")
    template = models.ForeignKey("hrm.JobDescriptionTemplate", on_delete=models.SET_NULL, null=True,
                                 blank=True, related_name="requisitions")

    # Organization
    department = models.ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="hrm_requisitions",
                                   limit_choices_to={"kind": "department"})
    cost_center = models.ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="hrm_requisitions_cc",
                                    limit_choices_to={"kind": "cost_center"})
    location = models.CharField(max_length=255, blank=True)

    # Headcount & type
    headcount = models.PositiveSmallIntegerField(default=1)
    req_type = models.CharField(max_length=20, choices=REQ_TYPE_CHOICES, default="standard")
    employment_type = models.CharField(max_length=20, choices=EMPLOYMENT_TYPE_CHOICES,
                                       default="full_time")
    reason_for_hire = models.CharField(max_length=30, choices=REASON_FOR_HIRE_CHOICES,
                                       default="new_headcount")
    is_replacement_for = models.CharField(max_length=255, blank=True,
                                          help_text="Name of the departing employee (free text; "
                                                    "FK upgrade deferred to 3.6).")
    posting_type = models.CharField(max_length=10, choices=POSTING_TYPE_CHOICES, default="external")

    # Hiring team — per HRM convention, FK to EmployeeProfile (never core.Party directly).
    hiring_manager = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.SET_NULL, null=True,
                                       blank=True, related_name="managed_requisitions")
    recruiter = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.SET_NULL, null=True,
                                  blank=True, related_name="assigned_requisitions")

    # Timeline
    target_start_date = models.DateField(null=True, blank=True)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default="medium")

    # Budget
    salary_min = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    salary_max = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    salary_currency = models.CharField(max_length=3, default="USD")
    estimated_annual_cost = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True,
                                                help_text="Loaded annual cost (salary + benefits).")
    hiring_cost_budget = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True,
                                             help_text="One-time recruitment spend (agency/job-board).")

    # Job description (opening-specific copy)
    jd_summary = models.TextField(blank=True)
    jd_responsibilities = models.TextField(blank=True)
    jd_requirements = models.TextField(blank=True)
    jd_nice_to_have = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    # Workflow-owned — set only by the POST actions, never the form.
    status = models.CharField(max_length=20, choices=JR_STATUS_CHOICES, default="draft",
                              editable=False)
    submitted_at = models.DateTimeField(null=True, blank=True, editable=False)
    approved_at = models.DateTimeField(null=True, blank=True, editable=False)
    posted_at = models.DateTimeField(null=True, blank=True, editable=False)
    filled_at = models.DateTimeField(null=True, blank=True, editable=False)

    # 3.6 Candidate Management — public career-portal bearer credential. Set (once) when the req is
    # posted; an unguessable token resolves the public application page (mirrors crm.Case/LandingPage:
    # unique + null when unposted so the empty values don't collide on the unique constraint).
    public_token = models.CharField(
        max_length=64, unique=True, null=True, blank=True, editable=False,
        help_text="URL-safe token minted when the req is posted; powers the public careers portal.")

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="hrm_jr_tenant_status_idx"),
            models.Index(fields=["tenant", "designation"], name="hrm_jr_tenant_desig_idx"),
            models.Index(fields=["tenant", "department"], name="hrm_jr_tenant_dept_idx"),
            models.Index(fields=["tenant", "hiring_manager"], name="hrm_jr_tenant_hm_idx"),
            models.Index(fields=["tenant", "priority", "status"], name="hrm_jr_tenant_prio_stat_idx"),
        ]

    def clean(self):
        super().clean()
        if (self.salary_min is not None and self.salary_max is not None
                and self.salary_min > self.salary_max):
            raise ValidationError({"salary_max": "Salary minimum cannot exceed maximum."})
        if self.headcount is not None and self.headcount < 1:
            raise ValidationError({"headcount": "Headcount must be at least 1."})

    @property
    def is_overdue(self):
        """True when the target start date has passed and the req isn't yet filled/closed —
        drives the red 'Overdue' indicator."""
        return (self.target_start_date is not None
                and self.target_start_date < date.today()
                and self.status not in ("filled", "cancelled", "rejected"))

    @property
    def approval_progress(self):
        """``(approved_count, total_count)`` over the approval chain — feeds the detail-hub
        progress text. Computed from the prefetched ``approvals`` when available.

        PERF: fires a SELECT unless ``approvals`` is prefetched. Over a *collection* of
        requisitions, compute from an already-fetched list instead (see ``jobrequisition_detail``)."""
        steps = self.approvals.all()
        total = len(steps)
        approved = sum(1 for s in steps if s.status == "approved")
        return approved, total

    @property
    def current_approval_step(self):
        """The lowest-ordered still-pending approval step (the one awaiting a decision), or
        ``None`` when the chain is fully decided.

        PERF: fires a SELECT per call. Don't call in a list loop — the detail view derives the
        current step from its already-fetched ``approvals`` list instead."""
        return (self.approvals.filter(status="pending").order_by("step_order").first())

    def __str__(self):
        return f"{self.number} · {self.title}"


class RequisitionApproval(TenantOwned):
    """One sequential approval step on a ``JobRequisition`` (3.5). The collection is both the
    approval chain (the current step = the lowest ``step_order`` still ``pending``) and the
    immutable audit trail — rows are never edited via a form: the approve/reject/return POST
    actions stamp ``status``/``decided_at``/``decided_by``. Mirrors the ``ClearanceItem`` child
    pattern from 3.4 Offboarding."""

    requisition = models.ForeignKey("hrm.JobRequisition", on_delete=models.CASCADE,
                                    related_name="approvals")
    step_order = models.PositiveSmallIntegerField(default=1)
    approver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                 blank=True, related_name="hrm_requisition_approvals")
    approver_role = models.CharField(max_length=20, choices=APPROVER_ROLE_CHOICES, default="hr")
    # Workflow-owned — set only by the approve/reject/return actions.
    status = models.CharField(max_length=20, choices=APPROVAL_STEP_STATUS_CHOICES,
                              default="pending", editable=False)
    decided_at = models.DateTimeField(null=True, blank=True, editable=False)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                   blank=True, related_name="hrm_approval_decisions", editable=False)
    comments = models.TextField(blank=True)

    class Meta:
        ordering = ["step_order"]
        unique_together = ("requisition", "step_order")
        indexes = [
            models.Index(fields=["requisition", "status"], name="hrm_ra_req_status_idx"),
            models.Index(fields=["approver", "status"], name="hrm_ra_approver_status_idx"),
        ]

    def clean(self):
        super().clean()
        if self.step_order is not None and self.step_order < 1:
            raise ValidationError({"step_order": "Step order must be at least 1."})

    def __str__(self):
        return (f"Step {self.step_order} — {self.get_approver_role_display()} "
                f"— {self.get_status_display()}")


# ---------------------------------------------------------------------------
# 3.6 Candidate Management — the ATS / talent-acquisition slice.
#
# A candidate is a real person → ``core.Party`` + ``PartyRole(role="candidate")``;
# ``CandidateProfile`` is the thin tenant-scoped extension carrying the ATS fields
# (mirrors how ``EmployeeProfile`` extends ``Party``). ``JobApplication`` links a
# candidate to an already-built ``JobRequisition`` (3.5) and runs the recruiting
# pipeline state machine. Communications are an append-only typed email log.
# ---------------------------------------------------------------------------

# Hex-color validator for tag badges (no shared core validator exists yet).
HEX_COLOR_VALIDATOR = RegexValidator(r"^#[0-9A-Fa-f]{6}$", "Enter a valid hex color, e.g. #3B82F6.")

CANDIDATE_STATUS_CHOICES = [
    ("active", "Active"),
    ("inactive", "Inactive"),
    ("hired", "Hired"),
    ("blacklisted", "Blacklisted"),
    ("do_not_contact", "Do Not Contact"),
]

QUALIFICATION_CHOICES = [
    ("high_school", "High School / Secondary"),
    ("diploma", "Diploma / Certificate"),
    ("bachelors", "Bachelor's Degree"),
    ("masters", "Master's Degree"),
    ("phd", "PhD / Doctorate"),
    ("other", "Other"),
]

CANDIDATE_GENDER_CHOICES = [
    ("male", "Male"),
    ("female", "Female"),
    ("non_binary", "Non-Binary"),
    ("prefer_not_to_say", "Prefer Not to Say"),
]

CANDIDATE_SOURCE_CHOICES = [
    ("careers_page", "Company Careers Page"),
    ("referral", "Employee Referral"),
    ("linkedin", "LinkedIn"),
    ("indeed", "Indeed"),
    ("glassdoor", "Glassdoor"),
    ("job_board", "Other Job Board"),
    ("agency", "Recruitment Agency"),
    ("direct_approach", "Direct / Sourced"),
    ("walk_in", "Walk-in"),
    ("other", "Other"),
]

SKILL_PROFICIENCY_CHOICES = [
    ("beginner", "Beginner"),
    ("intermediate", "Intermediate"),
    ("advanced", "Advanced"),
    ("expert", "Expert"),
]

SKILL_SOURCE_CHOICES = [
    ("parsed", "Resume Parsed"),
    ("manual", "Manually Added"),
    ("self_reported", "Self-Reported"),
]

APPLICATION_STAGE_CHOICES = [
    ("applied", "Applied"),
    ("screening", "Screening"),
    ("phone_screen", "Phone Screen"),
    ("assessment", "Assessment / Test"),
    ("interview", "Interview"),
    ("offer", "Offer"),
    ("hired", "Hired"),
    ("rejected", "Rejected"),
    ("withdrawn", "Withdrawn"),
    ("on_hold", "On Hold"),
]

# Terminal stages an application can't be "advanced" out of without an explicit restore.
APPLICATION_TERMINAL_STAGES = ("hired", "rejected", "withdrawn")

REJECTION_REASON_CHOICES = [
    ("overqualified", "Overqualified"),
    ("underqualified", "Underqualified"),
    ("position_filled", "Position Filled"),
    ("no_response", "No Response / Unresponsive"),
    ("failed_screening", "Failed Screening"),
    ("other", "Other"),
]

EMAIL_TEMPLATE_TYPE_CHOICES = [
    ("application_received", "Application Received"),
    ("shortlisted", "Application Shortlisted"),
    ("phone_screen_invite", "Phone Screen Invitation"),
    ("interview_invite", "Interview Invitation"),
    ("interview_reminder", "Interview Reminder"),
    ("stage_advance", "Advance to Next Stage"),
    ("assessment_invite", "Assessment / Test Invitation"),
    ("rejection", "Application Rejected"),
    ("on_hold", "Application On Hold"),
    ("offer", "Offer Communication"),
    ("general", "General / Ad-hoc"),
]

COMMUNICATION_CHANNEL_CHOICES = [
    ("email", "Email"),
    ("sms", "SMS"),
    ("whatsapp", "WhatsApp"),
]

COMMUNICATION_DIRECTION_CHOICES = [
    ("outbound", "Outbound"),
    ("inbound", "Inbound"),
]

DELIVERY_STATUS_CHOICES = [
    ("sent", "Sent"),
    ("delivered", "Delivered"),
    ("failed", "Failed"),
    ("pending", "Pending"),
]


class CandidateTag(TenantOwned):
    """Reusable talent-pool / segmentation label (3.6). A simple tenant catalog (name + color)
    M2M'd onto ``CandidateProfile`` — mirrors the Greenhouse/Ashby/Workable profile-tag pattern.
    No detail page (too few fields); list/create/edit/delete only."""

    name = models.CharField(max_length=100)
    color = models.CharField(max_length=7, default="#6B7280", validators=[HEX_COLOR_VALIDATOR],
                             help_text="Hex color for the tag badge, e.g. #3B82F6.")
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        unique_together = ("tenant", "name")
        indexes = [
            models.Index(fields=["tenant", "name"], name="hrm_ctag_tenant_name_idx"),
        ]

    def __str__(self):
        return self.name


class CandidateProfile(TenantNumbered):
    """The ATS candidate record (3.6) — a 1:1 extension of ``core.Party`` (with a
    ``PartyRole(role="candidate")`` marker), exactly mirroring ``EmployeeProfile``. Carries the
    talent-acquisition fields (contact, resume, skills, sourcing, GDPR consent). ``status`` is the
    candidate-level lifecycle state (distinct from a per-application ``stage``) and is workflow-owned."""

    NUMBER_PREFIX = "CAND"

    party = models.OneToOneField("core.Party", on_delete=models.CASCADE, related_name="candidate_profile")
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    email = models.EmailField(help_text="Unique per tenant — the duplicate-detection anchor.")
    phone = models.CharField(max_length=30, blank=True)
    linkedin_url = models.URLField(blank=True)
    current_job_title = models.CharField(max_length=255, blank=True)
    current_employer = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=2, blank=True, help_text="ISO 3166-1 alpha-2 country code.")
    years_of_experience = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    highest_qualification = models.CharField(max_length=20, choices=QUALIFICATION_CHOICES, blank=True)
    skill_set = models.TextField(blank=True,
        help_text="Comma-delimited free-text skills. Structured skills live in CandidateSkill.")
    resume_file = models.FileField(upload_to="hrm/candidates/resumes/%Y/%m/", null=True, blank=True)
    resume_text = models.TextField(blank=True,
        help_text="Raw text extracted from the resume — powers keyword search (NLP parsing deferred).")
    photo = models.ImageField(upload_to="hrm/candidates/photos/%Y/%m/", null=True, blank=True)
    gender = models.CharField(max_length=20, choices=CANDIDATE_GENDER_CHOICES, blank=True)
    status = models.CharField(max_length=20, choices=CANDIDATE_STATUS_CHOICES, default="active",
                              editable=False)
    source = models.CharField(max_length=20, choices=CANDIDATE_SOURCE_CHOICES, blank=True)
    do_not_contact = models.BooleanField(default=False,
        help_text="Suppresses all automated candidate emails.")
    gdpr_consent = models.BooleanField(default=False)
    gdpr_consent_date = models.DateTimeField(null=True, blank=True, editable=False)
    gdpr_consent_expires = models.DateField(null=True, blank=True,
        help_text="Data-retention window; after this date the record is eligible for anonymization.")
    notes = models.TextField(blank=True)
    sourced_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                   blank=True, related_name="sourced_candidates")
    expected_salary = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    notice_period_days = models.PositiveSmallIntegerField(null=True, blank=True)
    tags = models.ManyToManyField("hrm.CandidateTag", blank=True, related_name="candidates")

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        constraints = [
            models.UniqueConstraint(fields=["tenant", "email"], name="hrm_cand_tenant_email_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="hrm_cand_tenant_status_idx"),
            models.Index(fields=["tenant", "source"], name="hrm_cand_tenant_source_idx"),
            models.Index(fields=["tenant", "do_not_contact"], name="hrm_cand_tenant_dnc_idx"),
            # Supports the default ``-created_at`` ordering of the candidate list under the tenant filter.
            models.Index(fields=["tenant", "created_at"], name="hrm_cand_tenant_created_idx"),
        ]

    @property
    def name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def __str__(self):
        return f"{self.number} · {self.name}" if self.number else self.name


class CandidateSkill(TenantOwned):
    """A structured skill on a candidate (3.6). Child of ``CandidateProfile`` — rows are added/removed
    via POST actions on the candidate detail hub (no standalone form), mirroring the
    ``RequisitionApproval`` / ``ClearanceItem`` inline-child pattern. Powers filter-by-skill search."""

    candidate = models.ForeignKey("hrm.CandidateProfile", on_delete=models.CASCADE, related_name="skills")
    skill_name = models.CharField(max_length=100)
    proficiency = models.CharField(max_length=20, choices=SKILL_PROFICIENCY_CHOICES, blank=True)
    source = models.CharField(max_length=20, choices=SKILL_SOURCE_CHOICES, default="manual")

    class Meta:
        ordering = ["skill_name"]
        unique_together = ("candidate", "skill_name")
        indexes = [
            models.Index(fields=["tenant", "skill_name"], name="hrm_cskill_tenant_name_idx"),
        ]

    def __str__(self):
        label = self.get_proficiency_display() if self.proficiency else "—"
        return f"{self.skill_name} ({label})"


class JobApplication(TenantNumbered):
    """A candidate's application to a requisition (3.6) — the recruiting pipeline record. ``stage`` is
    the workflow-owned state machine (set only by the stage-move POST actions, never the form);
    rating/notes are recruiter annotations. Unique per (candidate, requisition) so one person can't
    double-apply to the same opening."""

    NUMBER_PREFIX = "APP"

    candidate = models.ForeignKey("hrm.CandidateProfile", on_delete=models.CASCADE, related_name="applications")
    requisition = models.ForeignKey("hrm.JobRequisition", on_delete=models.CASCADE, related_name="applications")
    stage = models.CharField(max_length=20, choices=APPLICATION_STAGE_CHOICES, default="applied",
                             editable=False)
    source = models.CharField(max_length=20, choices=CANDIDATE_SOURCE_CHOICES, default="careers_page")
    referred_by = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.SET_NULL, null=True,
                                    blank=True, related_name="referrals")
    cover_letter_text = models.TextField(blank=True)
    cover_letter_file = models.FileField(upload_to="hrm/candidates/covers/%Y/%m/", null=True, blank=True)
    screening_answers = models.JSONField(default=dict, blank=True,
        help_text="Per-requisition screening questions and answers, stored as a {question: answer} map.")
    rating = models.PositiveSmallIntegerField(null=True, blank=True, help_text="Recruiter rating, 1–5.")
    rejection_reason = models.CharField(max_length=30, choices=REJECTION_REASON_CHOICES, blank=True)
    rejection_notes = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    applied_at = models.DateTimeField(auto_now_add=True)
    stage_changed_at = models.DateTimeField(null=True, blank=True, editable=False)
    hired_on = models.DateField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["-applied_at"]
        unique_together = ("tenant", "number")
        constraints = [
            models.UniqueConstraint(fields=["candidate", "requisition"], name="hrm_app_cand_req_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "stage"], name="hrm_app_tenant_stage_idx"),
            models.Index(fields=["tenant", "source"], name="hrm_app_tenant_source_idx"),
            models.Index(fields=["tenant", "requisition"], name="hrm_app_tenant_req_idx"),
            models.Index(fields=["tenant", "candidate"], name="hrm_app_tenant_cand_idx"),
            # Supports the default ``-applied_at`` ordering of the application list under the tenant filter.
            models.Index(fields=["tenant", "applied_at"], name="hrm_app_tenant_applied_idx"),
        ]

    def clean(self):
        super().clean()
        if self.rating is not None and not (1 <= self.rating <= 5):
            raise ValidationError({"rating": "Rating must be between 1 and 5."})

    def __str__(self):
        return f"{self.number} · {self.candidate.name} → {self.requisition.title}"


class CandidateEmailTemplate(TenantNumbered):
    """Reusable recruiting email template (3.6). HRM-owned (peer apps don't cross-import crm's). An
    ``is_auto_send`` template whose ``template_type`` matches a stage transition is fired automatically
    by the application stage-move actions."""

    NUMBER_PREFIX = "CETMPL"

    name = models.CharField(max_length=255)
    template_type = models.CharField(max_length=30, choices=EMAIL_TEMPLATE_TYPE_CHOICES, default="general")
    subject = models.CharField(max_length=500)
    body_html = models.TextField(
        help_text="Merge fields: {{candidate_name}}, {{job_title}}, {{company_name}}, "
                  "{{recruiter_name}}, {{application_number}}.")
    is_active = models.BooleanField(default=True)
    is_auto_send = models.BooleanField(default=False,
        help_text="Auto-send when a JobApplication stage transition matches this template type.")

    class Meta:
        ordering = ["template_type", "name"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "template_type", "is_active"], name="hrm_cetmpl_type_active_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.name}" if self.number else self.name


class CandidateCommunication(TenantNumbered):
    """Append-only typed communication log (3.6). Created only by the send-email POST action /
    ``_send_candidate_email`` helper (no create form; admin blocks add/change). ``sent_by=None`` marks a
    system auto-send. Distinct from the broader ``core.Activity`` ledger — this is the ATS email trail."""

    NUMBER_PREFIX = "CC"

    candidate = models.ForeignKey("hrm.CandidateProfile", on_delete=models.CASCADE, related_name="communications")
    application = models.ForeignKey("hrm.JobApplication", on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="communications")
    template = models.ForeignKey("hrm.CandidateEmailTemplate", on_delete=models.SET_NULL, null=True,
                                 blank=True, related_name="communications")
    channel = models.CharField(max_length=10, choices=COMMUNICATION_CHANNEL_CHOICES, default="email")
    direction = models.CharField(max_length=10, choices=COMMUNICATION_DIRECTION_CHOICES, default="outbound")
    subject = models.CharField(max_length=500, blank=True)
    body = models.TextField()
    sent_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name="candidate_communications")
    sent_at = models.DateTimeField(auto_now_add=True)
    delivery_status = models.CharField(max_length=10, choices=DELIVERY_STATUS_CHOICES, default="sent")

    class Meta:
        ordering = ["-sent_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "candidate"], name="hrm_cc_tenant_cand_idx"),
            models.Index(fields=["tenant", "application"], name="hrm_cc_tenant_app_idx"),
            models.Index(fields=["tenant", "delivery_status"], name="hrm_cc_tenant_dstatus_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.get_channel_display()} → {self.candidate.name}"


# ---------------------------------------------------------------------------
# 3.7 Interview Process — scheduling, panel assignment, and structured feedback/
# scorecards. Interviews hang off the 3.6 ``JobApplication`` spine (candidate +
# requisition are reached through it). Invites/reminders REUSE the 3.6
# ``CandidateEmailTemplate`` + ``CandidateCommunication`` log via the
# ``_send_candidate_email`` view helper — no new email model. Live calendar /
# Zoom-Teams-Meet auto-link / SMS dispatch + AI scoring are DEFERRED (the meeting
# link is a plain field; reminders are a manual, audited action).
# ---------------------------------------------------------------------------
INTERVIEW_MODE_CHOICES = [
    ("in_person", "In Person"),
    ("phone", "Phone"),
    ("video", "Video Call"),
    ("one_way_video", "One-way Video"),
]

INTERVIEW_STATUS_CHOICES = [
    ("scheduled", "Scheduled"),
    ("confirmed", "Confirmed"),
    ("in_progress", "In Progress"),
    ("completed", "Completed"),
    ("cancelled", "Cancelled"),
    ("no_show", "No Show"),
    ("rescheduled", "Rescheduled"),
]

# Closed statuses an interview can't be transitioned out of without an explicit reschedule
# (mirrors APPLICATION_TERMINAL_STAGES). A no-show/cancelled round is re-run by rescheduling.
INTERVIEW_TERMINAL_STATUSES = ("completed", "cancelled", "no_show")

VIDEO_PROVIDER_CHOICES = [
    ("zoom", "Zoom"),
    ("teams", "Microsoft Teams"),
    ("google_meet", "Google Meet"),
    ("other", "Other"),
]

PANELIST_ROLE_CHOICES = [
    ("lead", "Lead Interviewer"),
    ("interviewer", "Interviewer"),
    ("shadow", "Shadow / Trainee"),
    ("observer", "Observer"),
]

RSVP_STATUS_CHOICES = [
    ("pending", "Pending"),
    ("accepted", "Accepted"),
    ("declined", "Declined"),
]

# 5-level hire signal (Greenhouse/Zoho convention: Strong No … Strong Yes).
RECOMMENDATION_CHOICES = [
    ("strong_no", "Strong No"),
    ("no", "No"),
    ("maybe", "Maybe"),
    ("yes", "Yes"),
    ("strong_yes", "Strong Yes"),
]


class Interview(TenantNumbered):
    """A scheduled interview round on a ``JobApplication`` (3.7). ``status`` is the workflow-owned state
    machine — set only by the status-action POSTs (confirm/start/complete/cancel/no_show/reschedule),
    never the form (``editable=False``), mirroring ``JobApplication.stage``. Candidate + requisition are
    reached through ``application``. ``meeting_url``/``video_provider`` hold the video link (live
    Zoom/Teams/Meet generation deferred); ``reminder_sent_at``/``feedback_reminder_sent_at`` are stamped
    by the manual send-reminder actions (automated Celery dispatch deferred)."""

    NUMBER_PREFIX = "INTV"

    application = models.ForeignKey("hrm.JobApplication", on_delete=models.CASCADE, related_name="interviews")
    title = models.CharField(max_length=255, help_text='e.g. "Technical Round 2" or "HR Screen".')
    round_number = models.PositiveSmallIntegerField(default=1)
    mode = models.CharField(max_length=20, choices=INTERVIEW_MODE_CHOICES, default="video")
    status = models.CharField(max_length=20, choices=INTERVIEW_STATUS_CHOICES, default="scheduled",
                              editable=False)
    scheduled_at = models.DateTimeField()
    duration_minutes = models.PositiveSmallIntegerField(default=60)
    location = models.CharField(max_length=255, blank=True,
                                help_text="Physical room / address for in-person rounds.")
    video_provider = models.CharField(max_length=20, choices=VIDEO_PROVIDER_CHOICES, blank=True)
    meeting_url = models.URLField(blank=True,
        help_text="Video meeting link (paste from Zoom/Teams/Meet — auto-generation is deferred).")
    interviewer_instructions = models.TextField(blank=True,
        help_text="Briefing shown to the panel (focus areas, must-asks).")
    notes = models.TextField(blank=True)
    scheduled_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                     blank=True, related_name="scheduled_interviews")
    reminder_sent_at = models.DateTimeField(null=True, blank=True, editable=False)
    feedback_reminder_sent_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["-scheduled_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="hrm_intv_tenant_status_idx"),
            models.Index(fields=["tenant", "mode"], name="hrm_intv_tenant_mode_idx"),
            models.Index(fields=["tenant", "application"], name="hrm_intv_tenant_app_idx"),
            # Supports the default ``-scheduled_at`` ordering of the interview list under the tenant filter.
            models.Index(fields=["tenant", "scheduled_at"], name="hrm_intv_tenant_sched_idx"),
        ]

    @property
    def candidate(self):
        """The interviewee, via the application. Views that list interviews must
        ``select_related("application__candidate")`` to keep this O(1)."""
        return self.application.candidate

    @property
    def requisition(self):
        """The open position, via the application (select_related in list views)."""
        return self.application.requisition

    @property
    def is_closed(self):
        return self.status in INTERVIEW_TERMINAL_STATUSES

    def __str__(self):
        return f"{self.number} · {self.title}" if self.number else self.title


class InterviewPanelist(TenantOwned):
    """An interviewer assigned to an ``Interview`` (3.7). Managed inline on the interview detail hub
    (add/remove/rsvp POST actions) like ``CandidateSkill`` / ``RequisitionApproval`` — no standalone
    pages. ``role`` labels the panel seat; ``rsvp_status`` tracks the interviewer's acceptance;
    ``notified_at`` is stamped when an invite is sent. Unique per (interview, interviewer)."""

    interview = models.ForeignKey("hrm.Interview", on_delete=models.CASCADE, related_name="panelists")
    interviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                    related_name="interview_panels")
    role = models.CharField(max_length=20, choices=PANELIST_ROLE_CHOICES, default="interviewer")
    rsvp_status = models.CharField(max_length=20, choices=RSVP_STATUS_CHOICES, default="pending")
    briefing_notes = models.TextField(blank=True)
    notified_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["role", "pk"]
        unique_together = ("interview", "interviewer")
        indexes = [
            models.Index(fields=["tenant", "interview"], name="hrm_ipan_tenant_intv_idx"),
        ]

    def __str__(self):
        who = self.interviewer.get_full_name() or self.interviewer.username
        return f"{who} ({self.get_role_display()})"


class InterviewFeedback(TenantNumbered):
    """A structured interview scorecard (3.7) — one per panelist per interview. ``overall_recommendation``
    is the 5-level hire signal; ``is_submitted`` flips via the submit action (enabling anti-anchoring
    blinding — strict queryset-level blinding is deferred). Per-competency ratings live in child
    ``FeedbackCriterion`` rows; averages are annotated/aggregated in the views (no query-in-property)."""

    NUMBER_PREFIX = "IFB"

    interview = models.ForeignKey("hrm.Interview", on_delete=models.CASCADE, related_name="feedback_entries")
    panelist = models.ForeignKey("hrm.InterviewPanelist", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="+")
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name="interview_feedback")
    overall_recommendation = models.CharField(max_length=20, choices=RECOMMENDATION_CHOICES, default="maybe")
    summary = models.TextField(blank=True, help_text="Overall impression / key takeaways.")
    is_submitted = models.BooleanField(default=False)
    submitted_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["-created_at"]
        # ("interview", "panelist") enforces one scorecard per panelist per interview (the docstring
        # contract). On MariaDB/SQLite a UNIQUE index treats NULLs as distinct, so multiple
        # panelist=NULL (unassigned) cards on one interview are still allowed — exactly what we want,
        # and portable (a conditional UniqueConstraint would silently no-op on MariaDB: no partial idx).
        unique_together = [("tenant", "number"), ("interview", "panelist")]
        indexes = [
            models.Index(fields=["tenant", "interview"], name="hrm_ifb_tenant_intv_idx"),
            models.Index(fields=["tenant", "overall_recommendation"], name="hrm_ifb_tenant_reco_idx"),
            models.Index(fields=["tenant", "is_submitted"], name="hrm_ifb_tenant_sub_idx"),
        ]

    def __str__(self):
        reco = self.get_overall_recommendation_display()
        return f"{self.number} · {reco}" if self.number else reco


class FeedbackCriterion(TenantOwned):
    """A per-competency rating line on an ``InterviewFeedback`` scorecard (3.7). Managed inline on the
    feedback detail (add/remove POSTs) — no standalone pages. ``rating`` is 1–5 (guarded in
    ``clean()`` and at the form/view layer)."""

    feedback = models.ForeignKey("hrm.InterviewFeedback", on_delete=models.CASCADE, related_name="criteria")
    criterion_name = models.CharField(max_length=150)
    rating = models.PositiveSmallIntegerField(help_text="1 (poor) – 5 (excellent).")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["pk"]
        indexes = [
            models.Index(fields=["tenant", "feedback"], name="hrm_fcrit_tenant_fb_idx"),
        ]

    def clean(self):
        super().clean()
        if self.rating is not None and not (1 <= self.rating <= 5):
            raise ValidationError({"rating": "Rating must be between 1 and 5."})

    def __str__(self):
        return f"{self.criterion_name}: {self.rating}/5"


# ---------------------------------------------------------------------------
# 3.8 Offer Management — offer-letter generation, multi-step approval, offer
# tracking, background verification, and pre-boarding document collection.
#
# Offers hang off the 3.6 ``JobApplication`` spine (candidate + requisition are
# reached through it — no duplicate FKs). The offer-approval chain REUSES the
# 3.5 ``RequisitionApproval`` shape verbatim (``APPROVER_ROLE_CHOICES`` /
# ``APPROVAL_STEP_STATUS_CHOICES`` — not redefined), and the offer/pre-boarding
# emails REUSE the 3.6 ``CandidateEmailTemplate`` + ``CandidateCommunication``
# log via ``_send_candidate_email`` (the ``"offer"`` template-type already
# exists). Offer acceptance drives ``JobApplication.stage`` → ``"hired"`` +
# ``hired_on`` (existing fields, no schema change). Live e-signature and live
# background-check vendor APIs are DEFERRED — ``signed_document`` /
# ``signature_status`` / ``BackgroundVerification.status``/``result`` are plain
# fields a manual action (or a future webhook) writes to; the printable offer
# letter is a server-rendered page, the invite/reminder a manual audited action.
# ---------------------------------------------------------------------------
OFFER_STATUS_CHOICES = [
    ("draft", "Draft"),
    ("pending_approval", "Pending Approval"),
    ("approved", "Approved"),
    ("extended", "Extended to Candidate"),
    ("accepted", "Accepted"),
    ("declined", "Declined"),
    ("rescinded", "Rescinded"),
    ("expired", "Expired"),
]

# Closed statuses an offer can't be transitioned out of (mirrors
# INTERVIEW_TERMINAL_STATUSES / APPLICATION_TERMINAL_STAGES). Also drives the
# ``is_overdue`` guard so a settled offer never shows as overdue.
OFFER_TERMINAL_STATUSES = ("accepted", "declined", "rescinded", "expired")

# Candidate-side decline reasons (mirrors JobApplication.REJECTION_REASON_CHOICES shape).
OFFER_DECLINE_REASON_CHOICES = [
    ("salary", "Salary / Compensation"),
    ("competing_offer", "Accepted a Competing Offer"),
    ("counteroffer", "Counteroffer from Current Employer"),
    ("role_fit", "Role / Responsibilities Fit"),
    ("culture_fit", "Culture / Team Fit"),
    ("timing", "Timing / Start Date"),
    ("other", "Other"),
]

# E-signature status — field only this pass; live DocuSign/Adobe/Zoho Sign wiring deferred.
SIGNATURE_STATUS_CHOICES = [
    ("not_sent", "Not Sent"),
    ("sent", "Sent for Signature"),
    ("viewed", "Viewed by Candidate"),
    ("signed", "Signed"),
    ("declined", "Declined to Sign"),
]

# Background-verification vendor marketplace (Checkr/HireRight/Sterling convention) — field only.
BGV_VENDOR_CHOICES = [
    ("checkr", "Checkr"),
    ("hireright", "HireRight"),
    ("sterling", "Sterling"),
    ("other", "Other / In-house"),
]

# Typed verification categories (Checkr/HireRight standardized check types).
BGV_CHECK_TYPE_CHOICES = [
    ("criminal", "Criminal Record"),
    ("employment", "Employment History"),
    ("education", "Education Verification"),
    ("professional_license", "Professional License / Certification"),
    ("identity", "Identity Verification"),
    ("credit", "Credit Check"),
]

# Standardized check lifecycle (Checkr/Sterling: Started → In Progress → Action
# Needed → Ready for Review → Completed). ``result`` (below) is the separate
# overall verdict, orthogonal to the workflow status.
BGV_STATUS_CHOICES = [
    ("not_started", "Not Started"),
    ("consent_pending", "Consent Pending"),
    ("initiated", "Initiated"),
    ("in_progress", "In Progress"),
    ("action_needed", "Action Needed"),
    ("ready_for_review", "Ready for Review"),
    ("completed", "Completed"),
]

BGV_RESULT_CHOICES = [
    ("clear", "Clear"),
    ("consider", "Consider"),
    ("not_applicable", "Not Applicable"),
]

# Intermediate statuses a manual "update status" action can move an initiated check to (the deferred
# vendor webhook would write these too). Shared by the view guard and the detail-page dropdown so the two
# never drift.
BGV_MANUAL_TRANSITION_STATUSES = ("in_progress", "action_needed", "ready_for_review")

# Pre-boarding document-collection catalog (HiBob/iCIMS convention). Deliberately
# distinct from the post-start 3.3 OnboardingDocument.
PREBOARDING_DOC_TYPE_CHOICES = [
    ("id_proof", "ID Proof"),
    ("address_proof", "Address Proof"),
    ("tax_form", "Tax Form"),
    ("bank_details", "Bank / Direct-Deposit Details"),
    ("nda", "NDA / Confidentiality Agreement"),
    ("education_certificate", "Education Certificate"),
    ("background_check_consent", "Background-Check Consent"),
    ("other", "Other"),
]

# Per-item collection status (mirrors OnboardingTask/ClearanceItem status-child convention).
PREBOARDING_STATUS_CHOICES = [
    ("pending", "Pending"),
    ("submitted", "Submitted"),
    ("verified", "Verified"),
    ("rejected", "Rejected"),
]


class OfferLetterTemplate(TenantNumbered):
    """Reusable printable offer-letter template (3.8). Mirrors ``CandidateEmailTemplate``'s shape but for
    the longer-form letter body: the ``offer_letter_print`` view merges ``body_html``'s tokens against the
    offer/candidate/tenant. Keeping the body here (rather than a TextField on every ``Offer``) makes the
    boilerplate reusable + merge-tokenized across offers."""

    NUMBER_PREFIX = "OLTMPL"

    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    body_html = models.TextField(
        help_text="Merge fields: {{candidate_name}}, {{job_title}}, {{base_salary}}, {{currency}}, "
                  "{{start_date}}, {{company_name}}, {{hiring_manager_name}}.")

    class Meta:
        ordering = ["name"]
        unique_together = ("tenant", "name")
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="hrm_oltmpl_tenant_active_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.name}" if self.number else self.name


class Offer(TenantNumbered):
    """The offer-management hub (3.8) — one row per offer extended for a ``JobApplication`` (FK, not a hard
    1:1, so a re-issued offer supersedes rather than multiplies — mirrors how ``Interview`` FKs the
    application). ``status`` is the workflow-owned state machine
    (draft→pending_approval→approved→extended→accepted/declined/rescinded/expired), ``editable=False`` and
    set only by the audited POST actions — never the form. The approval chain (``approvals``) gates
    extension: an offer can't be extended to the candidate until every step is approved. Acceptance drives
    ``application.stage`` → ``"hired"`` + ``hired_on`` (existing fields)."""

    NUMBER_PREFIX = "OFR"

    application = models.ForeignKey("hrm.JobApplication", on_delete=models.CASCADE, related_name="offers")
    offer_letter_template = models.ForeignKey("hrm.OfferLetterTemplate", on_delete=models.SET_NULL,
                                              null=True, blank=True, related_name="offers")

    # Compensation breakdown (Workday comp bands / SAP SuccessFactors Offer Detail conventions).
    base_salary = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3, default="USD",
                                help_text="Defaults from the requisition's salary_currency at creation.")
    bonus_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    bonus_terms = models.TextField(blank=True)
    signing_bonus = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    equity_terms = models.TextField(blank=True,
        help_text="Grant description / vesting schedule — equity plans aren't a structured table yet.")
    relocation_assistance = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    benefits_summary = models.TextField(blank=True)

    start_date = models.DateField(help_text="Proposed joining date.")
    expires_on = models.DateField(null=True, blank=True, help_text="Offer response deadline.")

    status = models.CharField(max_length=20, choices=OFFER_STATUS_CHOICES, default="draft", editable=False)

    # Candidate decline tracking (recruiter-editable annotations, mirrors JobApplication.rejection_*).
    decline_reason = models.CharField(max_length=30, choices=OFFER_DECLINE_REASON_CHOICES, blank=True)
    decline_notes = models.TextField(blank=True)

    # E-signature — fields now, live vendor wiring deferred.
    signed_document = models.FileField(upload_to="hrm/offers/signed/%Y/%m/", null=True, blank=True)
    signature_status = models.CharField(max_length=20, choices=SIGNATURE_STATUS_CHOICES, default="not_sent")

    # Workflow stamps — set only by the POST actions.
    extended_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="extended_offers", editable=False)
    extended_at = models.DateTimeField(null=True, blank=True, editable=False)
    accepted_at = models.DateTimeField(null=True, blank=True, editable=False)
    declined_at = models.DateTimeField(null=True, blank=True, editable=False)
    rescinded_at = models.DateTimeField(null=True, blank=True, editable=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="created_offers", editable=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="hrm_ofr_tenant_status_idx"),
            models.Index(fields=["tenant", "application"], name="hrm_ofr_tenant_app_idx"),
            models.Index(fields=["tenant", "created_at"], name="hrm_ofr_tenant_created_idx"),
        ]

    def clean(self):
        super().clean()
        for field in ("base_salary", "bonus_amount", "signing_bonus", "relocation_assistance"):
            value = getattr(self, field)
            if value is not None and value < ZERO:
                raise ValidationError({field: "Amount cannot be negative."})

    @property
    def candidate(self):
        """The offeree, via the application. Views listing offers must
        ``select_related("application__candidate")`` to keep this O(1)."""
        return self.application.candidate

    @property
    def requisition(self):
        """The open position, via the application (select_related in list views)."""
        return self.application.requisition

    @property
    def is_closed(self):
        return self.status in OFFER_TERMINAL_STATUSES

    @property
    def is_overdue(self):
        """True when the response deadline has passed and the offer isn't settled — drives the red
        'Overdue' indicator (mirrors ``JobRequisition.is_overdue``)."""
        return (self.expires_on is not None
                and self.expires_on < date.today()
                and self.status not in OFFER_TERMINAL_STATUSES)

    @property
    def total_compensation(self):
        """Base + bonus + signing bonus (relocation is a one-off, excluded) — used by the conditional
        approval-chain threshold and shown on the offer summary."""
        return (self.base_salary or ZERO) + (self.bonus_amount or ZERO) + (self.signing_bonus or ZERO)

    @property
    def approval_progress(self):
        """``(approved_count, total_count)`` over the approval chain — feeds the detail-hub progress text.

        PERF: fires a SELECT unless ``approvals`` is prefetched (the detail view prefetches it)."""
        steps = self.approvals.all()
        total = len(steps)
        approved = sum(1 for s in steps if s.status == "approved")
        return approved, total

    @property
    def current_approval_step(self):
        """The lowest-ordered still-pending approval step, or ``None`` when the chain is fully decided.

        PERF: fires a SELECT per call — don't call in a list loop."""
        return self.approvals.filter(status="pending").order_by("step_order").first()

    def __str__(self):
        return f"{self.number} · {self.application.candidate.name}" if self.number else str(self.pk)


class OfferApproval(TenantOwned):
    """One sequential approval step on an ``Offer`` (3.8). Mirrors ``RequisitionApproval`` field-for-field
    — the collection is both the approval chain (current step = lowest ``step_order`` still ``pending``)
    and the immutable audit trail (rows are never edited via a form: the approve/reject POST actions stamp
    ``status``/``decided_at``/``decided_by``). Reuses ``APPROVER_ROLE_CHOICES`` /
    ``APPROVAL_STEP_STATUS_CHOICES`` verbatim."""

    offer = models.ForeignKey("hrm.Offer", on_delete=models.CASCADE, related_name="approvals")
    step_order = models.PositiveSmallIntegerField(default=1)
    approver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="hrm_offer_approvals")
    approver_role = models.CharField(max_length=20, choices=APPROVER_ROLE_CHOICES, default="hr")
    status = models.CharField(max_length=20, choices=APPROVAL_STEP_STATUS_CHOICES,
                              default="pending", editable=False)
    decided_at = models.DateTimeField(null=True, blank=True, editable=False)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="hrm_offer_approval_decisions", editable=False)
    comments = models.TextField(blank=True)

    class Meta:
        ordering = ["step_order"]
        unique_together = ("offer", "step_order")
        indexes = [
            models.Index(fields=["offer", "status"], name="hrm_oa_offer_status_idx"),
            models.Index(fields=["approver", "status"], name="hrm_oa_approver_status_idx"),
        ]

    def clean(self):
        super().clean()
        if self.step_order is not None and self.step_order < 1:
            raise ValidationError({"step_order": "Step order must be at least 1."})

    def __str__(self):
        return (f"Step {self.step_order} — {self.get_approver_role_display()} "
                f"— {self.get_status_display()}")


class BackgroundVerification(TenantNumbered):
    """A background/reference check ordered on an ``Offer`` (3.8). ``status`` (the Checkr/Sterling
    standardized lifecycle) and ``result`` (Clear/Consider) are orthogonal workflow-owned fields a manual
    action (or a future vendor webhook) writes to — live vendor API ordering/webhooks are DEFERRED.
    Candidate identity data is read through ``offer.application.candidate`` — never re-stored here (no PII
    duplication). The formal adverse-action/dispute compliance sub-flow is out of scope this pass."""

    NUMBER_PREFIX = "BGV"

    offer = models.ForeignKey("hrm.Offer", on_delete=models.CASCADE, related_name="background_checks")
    vendor = models.CharField(max_length=30, choices=BGV_VENDOR_CHOICES, blank=True)
    check_type = models.CharField(max_length=30, choices=BGV_CHECK_TYPE_CHOICES, default="employment")
    status = models.CharField(max_length=20, choices=BGV_STATUS_CHOICES, default="not_started",
                              editable=False)
    result = models.CharField(max_length=20, choices=BGV_RESULT_CHOICES, blank=True)
    consent_given = models.BooleanField(default=False)
    consent_date = models.DateTimeField(null=True, blank=True, editable=False)
    report_file = models.FileField(upload_to="hrm/offers/bgv_reports/%Y/%m/", null=True, blank=True)
    initiated_at = models.DateTimeField(null=True, blank=True, editable=False)
    completed_at = models.DateTimeField(null=True, blank=True, editable=False)
    initiated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                     blank=True, related_name="initiated_bgv_checks", editable=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="hrm_bgv_tenant_status_idx"),
            models.Index(fields=["tenant", "offer"], name="hrm_bgv_tenant_ofr_idx"),
            models.Index(fields=["tenant", "check_type"], name="hrm_bgv_tenant_type_idx"),
            # Backs the default -created_at ordering under the tenant filter (mirrors Offer's index).
            models.Index(fields=["tenant", "created_at"], name="hrm_bgv_tenant_created_idx"),
        ]

    @property
    def is_completed(self):
        return self.status == "completed"

    def __str__(self):
        return f"{self.number} · {self.get_check_type_display()}" if self.number else self.get_check_type_display()


class PreboardingItem(TenantOwned):
    """A pre-start document-collection line tied to an accepted ``Offer`` (3.8). Deliberately distinct from
    the post-start 3.3 ``OnboardingDocument`` (that owns collection from day one onward; this is pre-join,
    offer-tied, and largely candidate-self-service). Managed inline on the offer detail hub (add/remove/
    submit/verify/reject + send-invite POST actions) — no standalone pages. ``status`` is workflow-owned;
    ``reminder_sent_at`` is stamped by the manual send-invite action (Celery auto-dispatch deferred)."""

    offer = models.ForeignKey("hrm.Offer", on_delete=models.CASCADE, related_name="preboarding_items")
    document_type = models.CharField(max_length=30, choices=PREBOARDING_DOC_TYPE_CHOICES, default="other")
    is_required = models.BooleanField(default=True)
    status = models.CharField(max_length=20, choices=PREBOARDING_STATUS_CHOICES, default="pending",
                              editable=False)
    uploaded_file = models.FileField(upload_to="hrm/offers/preboarding/%Y/%m/", null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True, editable=False)
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                    blank=True, related_name="verified_preboarding_items", editable=False)
    verified_at = models.DateTimeField(null=True, blank=True, editable=False)
    reminder_sent_at = models.DateTimeField(null=True, blank=True, editable=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["document_type", "pk"]
        indexes = [
            models.Index(fields=["tenant", "offer"], name="hrm_pbi_tenant_ofr_idx"),
            models.Index(fields=["tenant", "status"], name="hrm_pbi_tenant_status_idx"),
        ]

    def __str__(self):
        return f"{self.get_document_type_display()} ({self.get_status_display()})"


# ---------------------------------------------------------------------------
# 3.13 Salary Structure — PayComponent / SalaryStructureTemplate /
# SalaryStructureLine / EmployeeSalaryStructure
#
# The compensation DEFINITION layer (pay components + grade-wise CTC templates +
# per-employee assignments). It does NOT run payroll or post to the GL — that is owned by
# ``accounting.PayrollRun`` (3.14 / Accounting, per lesson L29); 3.13 only DEFINES the
# structures a payroll run later consumes.
# ---------------------------------------------------------------------------
class PayComponent(TenantOwned):
    """A reusable pay / deduction / statutory / reimbursement / variable component (3.13). This one
    catalog table covers four of the five NavERP.md 3.13 bullets (Pay Components, Tax Components,
    Reimbursements, Variable Pay) via ``component_type``; a ``SalaryStructureLine`` references a
    component and may override its default amount/percentage per template."""

    COMPONENT_TYPE_CHOICES = [
        ("earning", "Earning"),
        ("statutory_deduction", "Statutory Deduction"),
        ("voluntary_deduction", "Voluntary Deduction"),
        ("reimbursement", "Reimbursement"),
        ("variable", "Variable"),
    ]
    CALCULATION_TYPE_CHOICES = [
        ("fixed_amount", "Fixed Amount"),
        ("pct_of_basic", "% of Basic"),
        ("pct_of_ctc", "% of CTC"),
        ("pct_of_gross", "% of Gross"),
    ]
    FREQUENCY_CHOICES = [
        ("monthly", "Monthly"),
        ("annual", "Annual"),
        ("one_time", "One-Time"),
    ]
    CONTRIBUTION_SIDE_CHOICES = [
        ("employee", "Employee"),
        ("employer", "Employer"),
        ("both", "Both"),
    ]

    name = models.CharField(max_length=150)
    code = models.CharField(max_length=20, blank=True, help_text="Optional short code, e.g. HRA, PF-EE.")
    component_type = models.CharField(max_length=20, choices=COMPONENT_TYPE_CHOICES, default="earning")
    variable_subtype = models.CharField(max_length=30, blank=True,
        help_text="Only for variable components — e.g. bonus, incentive, commission.")
    calculation_type = models.CharField(max_length=20, choices=CALCULATION_TYPE_CHOICES, default="fixed_amount")
    default_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="Org-wide default when the calculation is a fixed amount (a structure line can override).")
    default_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="Org-wide default when the calculation is a percentage (a structure line can override).")
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default="monthly")
    is_taxable = models.BooleanField(default=True)
    include_in_ctc = models.BooleanField(default=True)
    contribution_side = models.CharField(max_length=10, choices=CONTRIBUTION_SIDE_CHOICES, default="employee",
        help_text="Which side pays this — mainly for statutory components (PF/ESI).")
    annual_cap_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="Annual cap, e.g. for a reimbursement like LTA/medical.")
    requires_bill = models.BooleanField(default=False,
        help_text="Reimbursement requires a submitted bill/receipt before payout.")
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveSmallIntegerField(default=0)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["display_order", "name"]
        unique_together = ("tenant", "name")
        indexes = [
            models.Index(fields=["tenant", "component_type"], name="hrm_paycomp_tenant_type_idx"),
        ]

    def clean(self):
        super().clean()
        # Soft consistency: a default may be left blank (a line overrides it), but if one IS provided
        # it must match the calculation type.
        if self.calculation_type == "fixed_amount" and self.default_percentage is not None:
            raise ValidationError({"default_percentage": "Fixed-amount components should not set a default percentage."})
        if self.calculation_type.startswith("pct_") and self.default_amount is not None:
            raise ValidationError({"default_amount": "Percentage-based components should not set a default amount."})

    def __str__(self):
        return self.name


class SalaryStructureTemplate(TenantNumbered):
    """A grade-wise CTC structure template (3.13) — ``SST-#####``. Its total CTC is DERIVED from the
    resolved breakdown lines (``computed_ctc_total``), never stored editable."""

    NUMBER_PREFIX = "SST"

    name = models.CharField(max_length=150)
    job_grade = models.ForeignKey("hrm.JobGrade", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="salary_structure_templates")
    annual_ctc_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True,
        help_text="Target annual CTC — the base for %-of-CTC lines.")
    currency = models.CharField(max_length=10, default="USD")
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "job_grade"], name="hrm_sst_tenant_grade_idx"),
        ]

    @property
    def computed_ctc_total(self):
        """Derived total CTC — the sum of every line's resolved amount. Never a stored field."""
        return sum((line.resolved_amount() for line in self.lines.select_related("pay_component").all()),
                   Decimal("0"))

    def __str__(self):
        return f"{self.number} · {self.name}"


class SalaryStructureLine(TenantOwned):
    """One component row in a ``SalaryStructureTemplate``'s CTC breakdown (3.13). May override the
    component's default amount / percentage / calc-type for this template.

    NOTE (v1 simplification): all percentage calc types (``pct_of_basic``/``pct_of_ctc``/
    ``pct_of_gross``) resolve against the template's ``annual_ctc_amount`` because no separate stored
    basic/gross subtotal exists yet — a true multi-base resolver is deferred to a later pass."""

    template = models.ForeignKey("hrm.SalaryStructureTemplate", on_delete=models.CASCADE, related_name="lines")
    pay_component = models.ForeignKey("hrm.PayComponent", on_delete=models.PROTECT)
    calculation_type = models.CharField(max_length=20, choices=PayComponent.CALCULATION_TYPE_CHOICES, blank=True,
        help_text="Overrides the component's calculation type on this template; blank = use the component's.")
    amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    sequence = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sequence", "id"]
        unique_together = ("tenant", "template", "pay_component")
        indexes = [
            models.Index(fields=["tenant", "template"], name="hrm_ssl_tenant_template_idx"),
        ]

    def resolved_amount(self, ctc=None):
        """The annual amount this line contributes to the CTC total. ``ctc`` overrides the base for
        percentage lines (e.g. an employee's actual assigned CTC at payroll time so two employees on
        the same template but different CTCs get different pay); defaults to the template's
        ``annual_ctc_amount``. (v1: all pct types resolve off this single base.)"""
        effective_calc = self.calculation_type or self.pay_component.calculation_type
        if effective_calc == "fixed_amount":
            amount = self.amount if self.amount is not None else self.pay_component.default_amount
            return amount if amount is not None else Decimal("0")
        pct = self.percentage if self.percentage is not None else self.pay_component.default_percentage
        pct = pct if pct is not None else Decimal("0")
        base = ctc if ctc is not None else (self.template.annual_ctc_amount or Decimal("0"))
        return (base * pct / Decimal("100")).quantize(Decimal("0.01"))

    def __str__(self):
        return f"{self.template} · {self.pay_component}"


class EmployeeSalaryStructure(TenantNumbered):
    """An effective-dated assignment of a salary structure / CTC to an employee (3.13) — ``ESS-#####``.
    At most one ``active`` assignment per employee (enforced in ``clean()``)."""

    NUMBER_PREFIX = "ESS"

    STATUS_CHOICES = [
        ("active", "Active"),
        ("superseded", "Superseded"),
    ]

    employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.CASCADE, related_name="salary_structures")
    template = models.ForeignKey("hrm.SalaryStructureTemplate", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="employee_assignments")
    annual_ctc_amount = models.DecimalField(max_digits=14, decimal_places=2,
        help_text="The employee's actual assigned annual CTC (may differ from the template default).")
    effective_from = models.DateField(default=timezone.localdate)
    effective_to = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-effective_from"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "employee", "effective_from"], name="hrm_ess_tenant_emp_efrom_idx"),
            models.Index(fields=["tenant", "status"], name="hrm_ess_tenant_status_idx"),
        ]

    def clean(self):
        super().clean()
        if self.effective_to and self.effective_from and self.effective_to < self.effective_from:
            raise ValidationError({"effective_to": "Effective-to date cannot be before the effective-from date."})
        # At most one active assignment per employee. Derive the tenant from the employee — the
        # instance's own tenant is unset during ModelForm validation on create (mirrors
        # FloatingHolidayElection.clean() from 3.12).
        if self.status == "active" and self.employee_id:
            clash = (EmployeeSalaryStructure.objects
                     .filter(tenant_id=self.employee.tenant_id, employee_id=self.employee_id, status="active")
                     .exclude(pk=self.pk))
            if clash.exists():
                raise ValidationError({"status": "This employee already has an active salary structure — "
                                       "mark the existing one superseded first."})

    def __str__(self):
        return f"{self.number} · {self.employee}"


# ---------------------------------------------------------------------------
# 3.14 Payroll Processing — PayrollCycle / Payslip / PayslipLine
#
# The OPERATIONAL payroll run: computes per-employee payslips from each employee's active
# ``EmployeeSalaryStructure`` (3.13), routes through an approval workflow, and on lock creates/links
# an ``accounting.PayrollRun`` carrying the rolled-up totals so accounting posts the GL journal
# (lesson L29 — HRM never builds a JournalEntry). Named distinctly from ``accounting.PayrollRun``
# (the financial aggregate) which it hands off to.
# ---------------------------------------------------------------------------
class PayrollCycle(TenantNumbered):
    """A pay-period operational payroll run header (3.14) — ``PRC-#####``. Derived ``total_*`` come from
    its ``Payslip``s; ``accounting_payroll_run`` is set on lock (the accounting GL post is separate)."""

    NUMBER_PREFIX = "PRC"

    CYCLE_TYPE_CHOICES = [
        ("regular", "Regular"),
        ("off_cycle", "Off-Cycle"),
        ("bonus", "Bonus"),
    ]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("pending_approval", "Pending Approval"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("locked", "Locked"),
    ]

    period_start = models.DateField()
    period_end = models.DateField()
    pay_date = models.DateField()
    cycle_type = models.CharField(max_length=20, choices=CYCLE_TYPE_CHOICES, default="regular")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="hrm_payroll_cycle_submissions", editable=False)
    submitted_at = models.DateTimeField(null=True, blank=True, editable=False)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="hrm_payroll_cycle_approvals", editable=False)
    approved_at = models.DateTimeField(null=True, blank=True, editable=False)
    rejection_reason = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    accounting_payroll_run = models.ForeignKey(
        "accounting.PayrollRun", on_delete=models.SET_NULL, null=True, blank=True, editable=False,
        related_name="hrm_cycles")

    class Meta:
        ordering = ["-pay_date"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="hrm_prc_tenant_status_idx"),
        ]

    def clean(self):
        super().clean()
        if self.period_end and self.period_start and self.period_end < self.period_start:
            raise ValidationError({"period_end": "Period-end cannot be before period-start."})

    @property
    def is_locked(self):
        return self.status == "locked"

    def _totals(self):
        """One aggregate query for the three payslip totals, cached per instance so a detail render that
        shows total_gross/deductions/net issues one query, not three."""
        if not hasattr(self, "_totals_cache"):
            self._totals_cache = self.payslips.aggregate(
                g=Sum("gross_pay"), d=Sum("total_deductions"), n=Sum("net_pay"))
        return self._totals_cache

    @property
    def headcount(self):
        return self.payslips.count()

    @property
    def total_gross(self):
        return self._totals()["g"] or ZERO

    @property
    def total_deductions(self):
        return self._totals()["d"] or ZERO

    @property
    def total_net(self):
        return self._totals()["n"] or ZERO

    def __str__(self):
        return f"{self.number} · {self.get_cycle_type_display()} · {self.period_start}–{self.period_end}"


class Payslip(TenantNumbered):
    """One employee's payslip within a ``PayrollCycle`` (3.14) — ``PSL-#####``. ``gross_pay`` /
    ``total_deductions`` / ``net_pay`` are DERIVED by ``recompute()`` from the employee's
    ``EmployeeSalaryStructure`` (3.13), never hand-typed. Amounts are stored as POSITIVE magnitudes;
    ``PayslipLine.component_type`` distinguishes earning vs deduction (no signed amounts, matching the
    SalaryStructureLine convention). "Locked" is derived from the cycle — no second state machine."""

    NUMBER_PREFIX = "PSL"

    EARNING_TYPES = frozenset({"earning", "reimbursement", "variable"})
    DEDUCTION_TYPES = frozenset({"statutory_deduction", "voluntary_deduction"})

    cycle = models.ForeignKey("hrm.PayrollCycle", on_delete=models.CASCADE, related_name="payslips")
    employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.PROTECT, related_name="payslips")
    salary_structure = models.ForeignKey(
        "hrm.EmployeeSalaryStructure", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="payslips", help_text="The structure this payslip was computed from.")
    days_in_period = models.PositiveSmallIntegerField(default=30)
    days_worked = models.PositiveSmallIntegerField(default=30)
    lop_days = models.DecimalField(max_digits=5, decimal_places=2, default=0,
        help_text="Unpaid (loss-of-pay) days in the period.")
    lop_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0, editable=False)
    gross_pay = models.DecimalField(max_digits=14, decimal_places=2, default=0, editable=False)
    total_deductions = models.DecimalField(max_digits=14, decimal_places=2, default=0, editable=False)
    net_pay = models.DecimalField(max_digits=14, decimal_places=2, default=0, editable=False)
    arrears_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    bonus_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    on_hold = models.BooleanField(default=False)
    hold_reason = models.TextField(blank=True)
    released_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["cycle", "employee__party__name"]
        unique_together = ("tenant", "cycle", "employee")
        indexes = [
            models.Index(fields=["tenant", "cycle"], name="hrm_psl_tenant_cycle_idx"),
            models.Index(fields=["tenant", "employee"], name="hrm_psl_tenant_emp_idx"),
        ]

    @property
    def is_locked(self):
        return self.cycle.is_locked

    def clean(self):
        super().clean()
        if self.days_in_period and self.days_worked is not None and self.days_worked > self.days_in_period:
            raise ValidationError({"days_worked": "Days worked cannot exceed the days in the period."})
        if self.days_in_period and self.lop_days is not None and self.lop_days > self.days_in_period:
            raise ValidationError({"lop_days": "LOP days cannot exceed the days in the period."})
        for field in ("arrears_amount", "bonus_amount", "lop_days"):
            value = getattr(self, field)
            if value is not None and value < 0:
                raise ValidationError({field: "This value cannot be negative."})

    def recompute(self):
        """Derive gross/deductions/net + LOP and rebuild the ``PayslipLine`` snapshot rows from the
        resolved salary structure. A locked cycle's payslips are immutable."""
        if self.cycle.is_locked:
            raise ValidationError("Cannot recompute a payslip in a locked cycle.")
        # Resolve the structure's lines → monthly amounts (annual / 12), split earning vs deduction.
        resolved = []
        if self.salary_structure_id and self.salary_structure and self.salary_structure.template_id:
            ctc = self.salary_structure.annual_ctc_amount  # employee's assigned CTC scales the pct lines
            for line in (self.salary_structure.template.lines
                         .select_related("pay_component").order_by("sequence", "id")):
                monthly = (line.resolved_amount(ctc) / Decimal("12")).quantize(Decimal("0.01"))
                resolved.append((line.pay_component, monthly))
        ratio = (Decimal(self.days_worked) / Decimal(self.days_in_period)
                 if self.days_in_period else Decimal("1"))
        period_gross = ZERO
        earning_lines, employee_ded_lines, employer_lines = [], [], []
        for pc, monthly in resolved:
            if pc.component_type in self.EARNING_TYPES:
                amt = (monthly * ratio).quantize(Decimal("0.01"))
                period_gross += amt
                earning_lines.append((pc, amt))
            elif pc.component_type in self.DEDUCTION_TYPES:
                # Employer-side statutory contributions (e.g. employer PF/ESI) are a company cost — they
                # are snapshotted for the GL roll-up but do NOT reduce the employee's net pay. Only
                # employee/both/unspecified-side deductions reduce net.
                if pc.contribution_side == "employer":
                    employer_lines.append((pc, monthly))
                else:
                    employee_ded_lines.append((pc, monthly))
        self.lop_amount = (((period_gross / Decimal(self.days_in_period)) * self.lop_days).quantize(Decimal("0.01"))
                           if self.days_in_period else ZERO)
        self.gross_pay = (period_gross - self.lop_amount + self.arrears_amount
                          + self.bonus_amount).quantize(Decimal("0.01"))
        self.total_deductions = sum((m for _, m in employee_ded_lines), ZERO).quantize(Decimal("0.01"))
        self.net_pay = (self.gross_pay - self.total_deductions).quantize(Decimal("0.01"))
        # Rebuild the snapshot lines (earnings, then arrears/bonus, then LOP, then employee deductions,
        # then employer contributions).
        self.lines.all().delete()
        out = []
        for pc, amt in earning_lines:
            out.append(PayslipLine(tenant_id=self.tenant_id, payslip=self, component_name=pc.name,
                component_type=pc.component_type, amount=amt,
                contribution_side=pc.contribution_side, sequence=pc.display_order or 1))
        if self.arrears_amount:
            out.append(PayslipLine(tenant_id=self.tenant_id, payslip=self, component_name="Arrears",
                component_type="arrears", amount=self.arrears_amount, sequence=90))
        if self.bonus_amount:
            out.append(PayslipLine(tenant_id=self.tenant_id, payslip=self, component_name="Bonus",
                component_type="bonus", amount=self.bonus_amount, sequence=91))
        if self.lop_amount:
            out.append(PayslipLine(tenant_id=self.tenant_id, payslip=self, component_name="Loss of Pay",
                component_type="lop", amount=self.lop_amount, sequence=95))
        for pc, m in employee_ded_lines:
            out.append(PayslipLine(tenant_id=self.tenant_id, payslip=self, component_name=pc.name,
                component_type=pc.component_type, amount=m,
                contribution_side=pc.contribution_side, sequence=100 + (pc.display_order or 0)))
        for pc, m in employer_lines:
            out.append(PayslipLine(tenant_id=self.tenant_id, payslip=self, component_name=pc.name,
                component_type=pc.component_type, amount=m,
                contribution_side=pc.contribution_side, sequence=200 + (pc.display_order or 0)))
        PayslipLine.objects.bulk_create(out)
        self.save(update_fields=["lop_amount", "gross_pay", "total_deductions", "net_pay", "updated_at"])

    def __str__(self):
        return f"{self.number} · {self.employee} · {self.cycle.number}"


class PayslipLine(TenantOwned):
    """A snapshotted component line on a ``Payslip`` (3.14). name/type/amount/contribution_side are COPIED
    at generation time so a later ``PayComponent``/structure edit never rewrites historical payslips.
    ``amount`` is a positive magnitude; ``component_type`` says earning vs deduction (+ synthetic
    ``arrears``/``bonus``/``lop`` line types)."""

    COMPONENT_TYPE_CHOICES = PayComponent.COMPONENT_TYPE_CHOICES + [
        ("arrears", "Arrears"),
        ("bonus", "Bonus"),
        ("lop", "Loss of Pay"),
    ]

    payslip = models.ForeignKey("hrm.Payslip", on_delete=models.CASCADE, related_name="lines")
    component_name = models.CharField(max_length=150)
    component_type = models.CharField(max_length=20, choices=COMPONENT_TYPE_CHOICES)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    contribution_side = models.CharField(
        max_length=10, choices=PayComponent.CONTRIBUTION_SIDE_CHOICES, blank=True, default="",
        help_text="Snapshotted from the source component so the lock roll-up needn't re-join PayComponent.")
    sequence = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sequence", "id"]
        indexes = [
            models.Index(fields=["tenant", "payslip"], name="hrm_psll_tenant_payslip_idx"),
        ]

    def __str__(self):
        return f"{self.payslip} · {self.component_name}"


# ---------------------------------------------------------------------------
# 3.15 Statutory Compliance — the Indian statutory-payroll COMPLIANCE layer on
# top of 3.13 (PayComponent/SalaryStructure) + 3.14 (PayrollCycle/Payslip/
# PayslipLine). This is NOT a second payroll engine: the per-employee statutory
# amounts are already computed and snapshotted on ``PayslipLine`` by
# ``Payslip.recompute()``. 3.15 adds only (a) tenant-wide employer
# registration/config (``StatutoryConfig``), (b) state-wise PT+LWF slab/rate
# rules (``StatutoryStateRule``), (c) per-employee government identifiers
# UAN/PF/ESI (``EmployeeStatutoryIdentifier``), and (d) a per-scheme/per-period
# return/challan register (``StatutoryReturn``) whose contribution totals are
# AGGREGATED from existing ``PayslipLine`` rows — never hand-typed. Money still
# posts only through ``accounting.PayrollRun``/``JournalEntry`` (L29); this
# sub-module builds no GL path and adds no new employee master.
# ---------------------------------------------------------------------------

# India's states + union territories — the choice list shared by
# ``StatutoryConfig.pt_default_state``, ``StatutoryStateRule.state``, and
# ``EmployeeStatutoryIdentifier.pt_state`` (PT/LWF are state-scoped schemes).
INDIAN_STATE_CHOICES = [
    ("Andhra Pradesh", "Andhra Pradesh"), ("Arunachal Pradesh", "Arunachal Pradesh"),
    ("Assam", "Assam"), ("Bihar", "Bihar"), ("Chhattisgarh", "Chhattisgarh"),
    ("Goa", "Goa"), ("Gujarat", "Gujarat"), ("Haryana", "Haryana"),
    ("Himachal Pradesh", "Himachal Pradesh"), ("Jharkhand", "Jharkhand"),
    ("Karnataka", "Karnataka"), ("Kerala", "Kerala"), ("Madhya Pradesh", "Madhya Pradesh"),
    ("Maharashtra", "Maharashtra"), ("Manipur", "Manipur"), ("Meghalaya", "Meghalaya"),
    ("Mizoram", "Mizoram"), ("Nagaland", "Nagaland"), ("Odisha", "Odisha"),
    ("Punjab", "Punjab"), ("Rajasthan", "Rajasthan"), ("Sikkim", "Sikkim"),
    ("Tamil Nadu", "Tamil Nadu"), ("Telangana", "Telangana"), ("Tripura", "Tripura"),
    ("Uttar Pradesh", "Uttar Pradesh"), ("Uttarakhand", "Uttarakhand"),
    ("West Bengal", "West Bengal"),
    # Union territories
    ("Andaman and Nicobar Islands", "Andaman and Nicobar Islands"),
    ("Chandigarh", "Chandigarh"),
    ("Dadra and Nagar Haveli and Daman and Diu", "Dadra and Nagar Haveli and Daman and Diu"),
    ("Delhi", "Delhi"), ("Jammu and Kashmir", "Jammu and Kashmir"), ("Ladakh", "Ladakh"),
    ("Lakshadweep", "Lakshadweep"), ("Puducherry", "Puducherry"),
]


class StatutoryConfig(TenantOwned):
    """Tenant-wide statutory registration + default-rate master (3.15) — a settings
    singleton (one row per tenant), mirroring Zoho Payroll's single Statutory Components
    screen. Overrides ``TenantOwned``'s FK with a ``OneToOneField`` so there is exactly
    one config per tenant. Rates/ceilings are stored for documentation + the register
    aggregation; the actual per-payslip statutory computation stays in
    ``PayComponent``/``Payslip.recompute()`` (this model never re-derives contributions)."""

    tenant = models.OneToOneField(
        "core.Tenant", on_delete=models.CASCADE, related_name="hrm_statutory_config")

    # PF (Provident Fund) — Zoho: PF establishment code + ₹15,000 Basic+DA ceiling, 12%/12%.
    pf_establishment_code = models.CharField(max_length=50, blank=True)
    pf_wage_ceiling = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("15000.00"),
        help_text="Monthly Basic+DA ceiling for PF (documentation; enforcement stays in payroll).")
    pf_employee_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("12.00"))
    pf_employer_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("12.00"))
    # ESI (Employee State Insurance) — Zoho: ESI number + ₹21,000 gross ceiling, 0.75%/3.25%.
    esi_employer_code = models.CharField(max_length=50, blank=True)
    esi_wage_ceiling = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("21000.00"),
        help_text="Monthly gross ceiling below which an employee is ESI-eligible.")
    esi_employee_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.75"))
    esi_employer_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("3.25"))
    # PT (Professional Tax) — state-scoped; the fallback state when an employee's own can't resolve.
    pt_default_state = models.CharField(max_length=50, choices=INDIAN_STATE_CHOICES, blank=True)
    # TDS (Tax Deducted at Source) — employer TAN + Form 16 config (greytHR/ClearTax).
    tan_number = models.CharField(max_length=20, blank=True,
        help_text="Employer Tax Deduction Account Number — mandatory on Form 24Q/16 (distinct from PAN).")
    tds_circle_address = models.TextField(blank=True, help_text="TDS circle/ward address printed on Form 16.")
    pan_of_deductor = models.CharField(max_length=10, blank=True,
        help_text="The employer's own PAN (distinct from an employee's PAN in EmployeeProfile.national_id).")
    # LWF (Labour Welfare Fund) — org-wide master switch; per-state detail on StatutoryStateRule.
    is_lwf_applicable = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Statutory Configuration"
        verbose_name_plural = "Statutory Configuration"

    @classmethod
    def for_tenant(cls, tenant):
        """Get-or-create the single config row for ``tenant`` (consistent call-site helper)."""
        obj, _ = cls.objects.get_or_create(tenant=tenant)
        return obj

    def __str__(self):
        return f"Statutory Config · {self.tenant.name if self.tenant_id else ''}"


class StatutoryStateRule(TenantOwned):
    """State-wise PT + LWF slab/rate table (3.15) — one shared table for both state-scoped
    schemes (mirrors greytHR's editable PT slab grid + the LWF state-applicability/periodicity/
    amount pattern). Rate changes are a NEW row (supersede via ``is_active=False``), never an
    in-place edit, so prior-period returns stay historically correct (the greytHR "Odisha PT
    discontinued from April 2026" pattern).

    NULL note: for LWF, ``income_from`` stays ``None`` — and DB unique constraints treat NULLs as
    distinct, so ``clean()`` additionally enforces one active LWF row per ``(tenant, state)``."""

    SCHEME_CHOICES = [
        ("pt", "Professional Tax"),
        ("lwf", "Labour Welfare Fund"),
    ]
    LWF_PERIODICITY_CHOICES = [
        ("monthly", "Monthly"),
        ("half_yearly", "Half-Yearly"),
        ("annual", "Annual"),
    ]

    state = models.CharField(max_length=50, choices=INDIAN_STATE_CHOICES)
    scheme = models.CharField(max_length=10, choices=SCHEME_CHOICES, default="pt")
    # PT-only (blank/null when scheme="lwf") — the income bracket → monthly tax amount.
    income_from = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    income_to = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    pt_monthly_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    pt_deduction_month = models.CharField(max_length=20, blank=True,
        help_text="Optional — some states deduct PT only in specific months (e.g. an annual lump sum).")
    # LWF-only (blank/null when scheme="pt").
    lwf_employee_contribution = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    lwf_employer_contribution = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    lwf_periodicity = models.CharField(max_length=20, choices=LWF_PERIODICITY_CHOICES, blank=True)
    lwf_due_month_1 = models.CharField(max_length=20, blank=True, help_text="e.g. July.")
    lwf_due_month_2 = models.CharField(max_length=20, blank=True, help_text="e.g. January (half-yearly states).")
    registration_number = models.CharField(max_length=50, blank=True,
        help_text="State-specific PT/LWF employer registration number, where applicable.")
    is_active = models.BooleanField(default=True)
    effective_from = models.DateField(default=timezone.localdate)

    class Meta:
        ordering = ["state", "scheme", "income_from"]
        unique_together = ("tenant", "state", "scheme", "income_from")
        indexes = [
            models.Index(fields=["tenant", "scheme"], name="hrm_ssr_tenant_scheme_idx"),
            models.Index(fields=["tenant", "state"], name="hrm_ssr_tenant_state_idx"),
        ]

    def clean(self):
        super().clean()
        if self.scheme == "pt":
            missing = [f for f in ("income_from", "income_to", "pt_monthly_amount")
                       if getattr(self, f) is None]
            if missing:
                raise ValidationError({m: "Required for a Professional Tax slab." for m in missing})
            if (self.income_from is not None and self.income_to is not None
                    and self.income_to < self.income_from):
                raise ValidationError({"income_to": "Income-to cannot be below income-from."})
        elif self.scheme == "lwf":
            if self.lwf_employee_contribution is None or self.lwf_employer_contribution is None:
                raise ValidationError({
                    "lwf_employee_contribution": "Employee + employer LWF contributions are required.",
                })
            if not self.lwf_periodicity:
                raise ValidationError({"lwf_periodicity": "LWF periodicity is required."})
            # App-level guard on top of the (NULL-distinct) DB constraint: at most one active LWF
            # row per (tenant, state) — a rate change supersedes the old row (is_active=False).
            if self.is_active and self.tenant_id:
                clash = StatutoryStateRule.objects.filter(
                    tenant_id=self.tenant_id, state=self.state, scheme="lwf", is_active=True)
                if self.pk:
                    clash = clash.exclude(pk=self.pk)
                if clash.exists():
                    raise ValidationError(
                        "An active LWF rule already exists for this state — deactivate it first.")

    def __str__(self):
        label = f"{self.get_state_display()} · {self.get_scheme_display()}"
        if self.scheme == "pt" and self.income_from is not None:
            label += f" ({self.income_from}–{self.income_to})"
        return label


class EmployeeStatutoryIdentifier(TenantOwned):
    """Per-employee government-issued statutory identifiers (3.15) — a 1:1 companion to
    ``EmployeeProfile`` for the UAN/PF/ESI numbers that don't fit the generic
    ``EmployeeProfile.national_id`` (PAN) field. Created lazily (get-or-create) — not every
    employee needs every identifier filled at once.

    WARNING: ``uan_number``/``pf_number``/``esi_number`` are sensitive government IDs — they are
    added to ``apps.core.crud._SENSITIVE_AUDIT_FIELDS`` so they are redacted from AuditLog.changes
    (mirroring national_id/passport_number). Encrypt at rest in production."""

    employee = models.OneToOneField(
        "hrm.EmployeeProfile", on_delete=models.CASCADE, related_name="statutory_identifiers")
    uan_number = models.CharField(max_length=20, blank=True,
        help_text="PF Universal Account Number (lifelong, distinct from the establishment PF number).")
    pf_number = models.CharField(max_length=30, blank=True,
        help_text="Establishment-specific PF account/member ID.")
    esi_number = models.CharField(max_length=20, blank=True,
        help_text="ESI Insurance Number (blank if the employee is above the ESI ceiling / exempt).")
    pt_state = models.CharField(max_length=50, choices=INDIAN_STATE_CHOICES, blank=True,
        help_text="Resolves which PT/LWF StatutoryStateRule applies; falls back to the config default.")
    is_pf_applicable = models.BooleanField(default=True)
    is_esi_applicable = models.BooleanField(default=True)

    class Meta:
        ordering = ["employee__party__name"]
        indexes = [
            models.Index(fields=["tenant", "employee"], name="hrm_empstat_tenant_emp_idx"),
        ]

    @staticmethod
    def _mask_last4(value):
        """Last-4 masked view of a sensitive ID (mirrors EmployeeProfile._mask_last4)."""
        v = value or ""
        return f"••••{v[-4:]}" if len(v) >= 4 else ("••••" if v else "")

    def masked_uan_number(self):
        """Last-4 view of the UAN (lifelong government ID — never render the full value in the UI)."""
        return self._mask_last4(self.uan_number)

    def masked_pf_number(self):
        return self._mask_last4(self.pf_number)

    def masked_esi_number(self):
        return self._mask_last4(self.esi_number)

    def __str__(self):
        return f"Statutory IDs · {self.employee}"


class StatutoryReturn(TenantNumbered):
    """A per-scheme, per-period statutory return / challan / register record (3.15) —
    ``SCR-#####``. One shared table covers all five schemes (PF/ESI/PT/TDS/LWF). The
    contribution totals are DERIVED by ``recompute()`` — an aggregate over the already-computed
    ``PayslipLine`` rows for the period, mirroring 3.14's ``payrollcycle_lock`` roll-up — never
    hand-typed. ``registration_number_used`` is snapshotted at generation time so a later config/
    rule edit never rewrites a historical return (the ``PayslipLine`` snapshot convention).

    v1 scheme matching: ``PayslipLine`` has no per-line scheme tag yet (PF/ESI/PT/LWF are all
    ``component_type='statutory_deduction'``), so ``recompute()`` matches lines by a
    ``component_name`` substring per ``SCHEME_KEYWORDS``. A proper per-line scheme tag is a
    deferred fast-follow (would require a 3.14 model change)."""

    NUMBER_PREFIX = "SCR"

    SCHEME_CHOICES = [
        ("pf", "Provident Fund"),
        ("esi", "ESI"),
        ("pt", "Professional Tax"),
        ("tds_24q", "TDS — Form 24Q"),
        ("tds_form16", "TDS — Form 16"),
        ("lwf", "Labour Welfare Fund"),
    ]
    PERIOD_TYPE_CHOICES = [
        ("monthly", "Monthly"),
        ("quarterly", "Quarterly"),
        ("half_yearly", "Half-Yearly"),
        ("annual", "Annual"),
    ]
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("filed", "Filed"),
        ("paid", "Paid"),
        ("late", "Late"),
    ]
    # v1 name-substring heuristic mapping a scheme to the PayComponent.name fragments that
    # identify its PayslipLine rows. NOTE: "pf" is NOT a substring of "Provident Fund" — the
    # working keyword for PF is "provident". tds/esi/lwf have no seeded component (aggregate 0).
    SCHEME_KEYWORDS = {
        "pf": ["provident", "epf"],
        "esi": ["esi", "state insurance"],
        "pt": ["professional tax", "profession tax"],
        "tds_24q": ["tds", "income tax", "tax deducted"],
        "tds_form16": ["tds", "income tax", "tax deducted"],
        "lwf": ["lwf", "labour welfare", "labor welfare"],
    }

    scheme = models.CharField(max_length=15, choices=SCHEME_CHOICES)
    period_type = models.CharField(max_length=15, choices=PERIOD_TYPE_CHOICES, default="monthly")
    period_start = models.DateField()
    period_end = models.DateField()
    cycle = models.ForeignKey(
        "hrm.PayrollCycle", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="statutory_returns",
        help_text="Set for the single-cycle monthly case; null for multi-cycle rollups (e.g. quarterly 24Q).")
    employee = models.ForeignKey(
        "hrm.EmployeeProfile", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="statutory_returns", help_text="Set only for per-employee Form 16; null for org-level returns.")
    employee_contribution_total = models.DecimalField(max_digits=14, decimal_places=2, default=0, editable=False)
    employer_contribution_total = models.DecimalField(max_digits=14, decimal_places=2, default=0, editable=False)
    headcount = models.PositiveIntegerField(default=0, editable=False)
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="pending")
    filed_on = models.DateField(null=True, blank=True, editable=False)
    paid_on = models.DateField(null=True, blank=True, editable=False)
    payment_reference = models.CharField(max_length=100, blank=True)
    registration_number_used = models.CharField(max_length=50, blank=True, editable=False,
        help_text="Snapshot of the config/rule registration number at generation time.")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-period_start", "scheme"]
        unique_together = ("tenant", "scheme", "period_start", "employee")
        indexes = [
            models.Index(fields=["tenant", "status"], name="hrm_scr_tenant_status_idx"),
            models.Index(fields=["tenant", "due_date"], name="hrm_scr_tenant_duedate_idx"),
            models.Index(fields=["tenant", "scheme"], name="hrm_scr_tenant_scheme_idx"),
        ]

    def clean(self):
        super().clean()
        if self.period_end and self.period_start and self.period_end < self.period_start:
            raise ValidationError({"period_end": "Period-end cannot be before period-start."})

    @property
    def is_locked(self):
        """Filed/paid/late returns are immutable — only a pending return can be re-aggregated/edited."""
        return self.status != "pending"

    @property
    def is_overdue(self):
        """Still pending past its due date — drives a "late" visual flag before status is flipped."""
        return self.status == "pending" and self.due_date is not None and self.due_date < timezone.localdate()

    def _scheme_lines(self):
        """The ``PayslipLine`` queryset backing this return: statutory-deduction lines for the
        period (by cycle when set, else by cycle.pay_date range), narrowed by the v1 scheme
        keyword match and — for Form 16 — the single employee."""
        lines = PayslipLine.objects.filter(
            tenant_id=self.tenant_id, component_type="statutory_deduction")
        if self.cycle_id:
            lines = lines.filter(payslip__cycle_id=self.cycle_id)
        else:
            lines = lines.filter(
                payslip__cycle__pay_date__gte=self.period_start,
                payslip__cycle__pay_date__lte=self.period_end)
        keywords = self.SCHEME_KEYWORDS.get(self.scheme, [])
        if keywords:
            cond = Q()
            for kw in keywords:
                cond |= Q(component_name__icontains=kw)
            lines = lines.filter(cond)
        if self.employee_id:
            lines = lines.filter(payslip__employee_id=self.employee_id)
        return lines

    def _resolve_registration_number(self):
        """Best-effort registration number for the scheme, snapshotted at generation time."""
        config = StatutoryConfig.objects.filter(tenant_id=self.tenant_id).first()
        if self.scheme == "pf":
            return config.pf_establishment_code if config else ""
        if self.scheme == "esi":
            return config.esi_employer_code if config else ""
        if self.scheme in ("tds_24q", "tds_form16"):
            return config.tan_number if config else ""
        if self.scheme in ("pt", "lwf"):
            state = config.pt_default_state if config else ""
            base = StatutoryStateRule.objects.filter(
                tenant_id=self.tenant_id, scheme=self.scheme, is_active=True,
                registration_number__gt="")
            # Prefer the org's default-state rule; fall back to any state with a registration number.
            rule = (base.filter(state=state).first() if state else None) or base.order_by("state").first()
            return rule.registration_number if rule else ""
        return ""

    def recompute(self):
        """Derive the contribution totals + headcount from the backing ``PayslipLine`` rows and
        snapshot the registration number. Mirrors 3.14's ``payrollcycle_lock`` bucketing exactly:
        ``employer`` = ``contribution_side="employer"``; ``employee`` = everything else
        (employee/both/blank) — so a "both" line is never double-counted. Immutable once filed."""
        if self.is_locked:
            raise ValidationError("Only a pending return can be re-aggregated.")
        lines = self._scheme_lines()
        self.employer_contribution_total = (
            lines.filter(contribution_side="employer").aggregate(s=Sum("amount"))["s"] or ZERO)
        self.employee_contribution_total = (
            lines.exclude(contribution_side="employer").aggregate(s=Sum("amount"))["s"] or ZERO)
        self.headcount = lines.values("payslip__employee_id").distinct().count()
        self.registration_number_used = self._resolve_registration_number()
        self.save(update_fields=[
            "employee_contribution_total", "employer_contribution_total", "headcount",
            "registration_number_used", "updated_at"])

    def __str__(self):
        return f"{self.number} · {self.get_scheme_display()} · {self.period_start}–{self.period_end}"


# ---------------------------------------------------------------------------
# 3.16 Tax & Investment — the India income-tax declaration + computation layer
# on top of 3.13 (EmployeeSalaryStructure = gross basis), 3.14 (PayslipLine =
# TDS already deducted), and 3.15 (StatutoryConfig TAN/PAN + StatutoryReturn
# tds_form16 = the Form-16 register). It DECLARES, VERIFIES, COMPUTES and REPORTS
# tax numbers — it posts NOTHING to the GL (accounting.PayrollRun/JournalEntry
# untouched, L29). Section codes are keyed to the FAMILIAR names (80C/80D/HRA/…);
# the Income Tax Act 2025 (eff. 1 Apr 2026) renumbering was unsettled at build
# time, so a free-text TaxRegimeConfig.tax_law_reference carries the caveat and
# the UI label can change without a schema change.
# ---------------------------------------------------------------------------

# Sections that still reduce taxable income under the NEW regime (a static map, not a DB flag):
# only the additional-NPS 80CCD(1B) + the standard deduction survive; 80C/80D/HRA/24b/LTA/80E and
# other Chapter VI-A deductions do NOT apply under the new regime.
NEW_REGIME_ALLOWED_SECTIONS = frozenset({"80ccd_1b_nps"})

# Statutory per-section deduction caps (FY 2025-26). Applied (capped + surfaced via capped_sections),
# never silently truncated on the declaration line itself, so the employee's raw claim is preserved.
SECTION_CAPS = {
    "80c": Decimal("150000.00"),
    "80ccd_1b_nps": Decimal("50000.00"),
    "24b_home_loan_interest": Decimal("200000.00"),
}


def _progressive_tax(taxable, bands):
    """Sum bracket-by-bracket tax over ``bands`` = ordered iterable of
    ``(income_from, income_to_or_None, rate_percent)`` Decimals (a top band has ``income_to=None``)."""
    tax = ZERO
    for lo, hi, rate in bands:
        if taxable <= lo:
            break
        upper = taxable if hi is None else min(taxable, hi)
        tax += (upper - lo) * rate / Decimal("100")
    return tax.quantize(Decimal("0.01"))


class TaxRegimeConfig(TenantOwned):
    """Per-(tenant, financial_year, regime) rate master (3.16) — standard deduction, cess, Section 87A
    rebate, and (via child ``TaxSlabBand`` rows) the slab table the computation engine walks. A small
    settings table, not auto-numbered."""

    REGIME_CHOICES = [
        ("old", "Old Regime"),
        ("new", "New Regime"),
    ]

    financial_year = models.CharField(max_length=10, help_text='Indian FY, e.g. "2025-26".')
    regime = models.CharField(max_length=10, choices=REGIME_CHOICES, default="new")
    standard_deduction = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("75000.00"),
        help_text="Flat salary deduction (new-regime default ₹75,000; old-regime ₹50,000).")
    cess_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("4.00"),
        help_text="Health & Education Cess applied on the computed tax (both regimes).")
    rebate_income_threshold = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="Section 87A: taxable-income ceiling at/below which the rebate applies.")
    rebate_max_tax = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="Section 87A: the maximum tax the rebate can zero out.")
    is_default_regime = models.BooleanField(default=False,
        help_text="The statutory default regime (new, since FY 2023-24) — drives a declaration's default election.")
    tax_law_reference = models.CharField(max_length=255, blank=True,
        help_text="Free-text note (e.g. Finance Act / Income Tax Act 2025 renumbering caveat).")

    class Meta:
        ordering = ["-financial_year", "regime"]
        unique_together = ("tenant", "financial_year", "regime")
        indexes = [
            models.Index(fields=["tenant", "financial_year"], name="hrm_trc_tenant_fy_idx"),
        ]

    def __str__(self):
        return f"{self.financial_year} · {self.get_regime_display()}"


class TaxSlabBand(TenantOwned):
    """One income bracket of a ``TaxRegimeConfig``'s slab table (3.16) — walked bracket-by-bracket by
    ``TaxComputation``. Managed inline on the config detail (like ``SalaryStructureLine``)."""

    config = models.ForeignKey("hrm.TaxRegimeConfig", on_delete=models.CASCADE, related_name="slab_bands")
    income_from = models.DecimalField(max_digits=12, decimal_places=2)
    income_to = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="Leave blank for the top (unbounded) band.")
    rate_percent = models.DecimalField(max_digits=5, decimal_places=2)
    sequence = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["config", "sequence", "income_from"]
        indexes = [
            models.Index(fields=["tenant", "config"], name="hrm_tsb_tenant_config_idx"),
        ]

    def clean(self):
        super().clean()
        if self.income_to is not None and self.income_from is not None and self.income_to < self.income_from:
            raise ValidationError({"income_to": "Income-to cannot be below income-from."})

    def __str__(self):
        return f"{self.config} · {self.income_from}–{self.income_to or '∞'} @ {self.rate_percent}%"


class InvestmentDeclaration(TenantNumbered):
    """A per-employee-per-FY income-tax declaration header (3.16) — ``ITD-#####``. Regime election +
    declaration/proof windows + the previous-employer figures; its ``lines`` carry the section-wise
    declared amounts. ``draft→submitted→locked`` gates editability (``is_editable``)."""

    NUMBER_PREFIX = "ITD"

    REGIME_CHOICES = TaxRegimeConfig.REGIME_CHOICES
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("submitted", "Submitted"),
        ("locked", "Locked"),
    ]

    employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.PROTECT, related_name="tax_declarations")
    financial_year = models.CharField(max_length=10, help_text='Indian FY, e.g. "2025-26".')
    regime_elected = models.CharField(max_length=10, choices=REGIME_CHOICES, default="new")
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="draft")
    declaration_window_open = models.DateField(null=True, blank=True)
    declaration_window_close = models.DateField(null=True, blank=True)
    proof_window_open = models.DateField(null=True, blank=True)
    proof_window_close = models.DateField(null=True, blank=True)
    previous_employer_income = models.DecimalField(max_digits=14, decimal_places=2, default=0,
        help_text="Salary earned with a previous employer this FY (mid-year joiner projection input).")
    previous_employer_tds = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    submitted_at = models.DateTimeField(null=True, blank=True, editable=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-financial_year", "employee__party__name"]
        unique_together = ("tenant", "employee", "financial_year")
        indexes = [
            models.Index(fields=["tenant", "financial_year"], name="hrm_itd_tenant_fy_idx"),
            models.Index(fields=["tenant", "status"], name="hrm_itd_tenant_status_idx"),
        ]

    @property
    def is_editable(self):
        """A draft declaration's regime + lines are editable; submitted/locked are read-only."""
        return self.status == "draft"

    def __str__(self):
        return f"{self.number} · {self.employee} · {self.financial_year}"


class InvestmentDeclarationLine(TenantOwned):
    """One section row of an ``InvestmentDeclaration`` (3.16). ``declared_amount`` is the employee's
    claim; ``verified_amount`` is set from approved ``InvestmentProof``s (or hand-set by HR) and is what
    the FINAL computation uses. Statutory per-section caps are applied in ``TaxComputation`` (surfaced,
    not truncated), never here."""

    SECTION_CODE_CHOICES = [
        ("80c", "Section 80C"),
        ("80d", "Section 80D — Self & Family"),
        ("80d_parents", "Section 80D — Parents"),
        ("hra", "HRA Exemption"),
        ("24b_home_loan_interest", "Section 24(b) — Home Loan Interest"),
        ("80ccd_1b_nps", "Section 80CCD(1B) — NPS"),
        ("lta", "Leave Travel Allowance"),
        ("80e_education_loan", "Section 80E — Education Loan Interest"),
        ("other_chapter_via", "Other Chapter VI-A"),
    ]

    declaration = models.ForeignKey("hrm.InvestmentDeclaration", on_delete=models.CASCADE, related_name="lines")
    section_code = models.CharField(max_length=25, choices=SECTION_CODE_CHOICES)
    declared_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    verified_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, editable=False,
        help_text="Final amount used once proofs are checked — set by proof verification, never form-typed.")
    # HRA-only sub-fields (blank unless section_code="hra").
    monthly_rent_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    is_metro_city = models.BooleanField(default=False,
        help_text="HRA: metro cities exempt up to 50% of basic, non-metro 40%.")
    landlord_pan = models.CharField(max_length=10, blank=True,
        help_text="HRA: landlord PAN (mandatory when annual rent exceeds ₹1,00,000).")
    # 24(b)-only sub-field.
    lender_name = models.CharField(max_length=255, blank=True, help_text="Home-loan lender (Section 24b).")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["declaration", "section_code"]
        unique_together = ("tenant", "declaration", "section_code")
        indexes = [
            models.Index(fields=["tenant", "declaration"], name="hrm_idl_tenant_decl_idx"),
        ]

    @property
    def effective_amount(self):
        """The amount the computation uses — verified when set, else the declared claim."""
        return self.verified_amount if self.verified_amount is not None else self.declared_amount

    def recompute_verified(self):
        """Roll ``verified_amount`` up from this line's ``verified`` proofs' amounts — the sum of their
        ``amount``s (``None`` when no verified proof carries an amount, so the computation falls back to
        the declared amount via ``effective_amount``)."""
        total = self.proofs.filter(verification_status="verified").aggregate(s=Sum("amount"))["s"]
        self.verified_amount = total
        self.save(update_fields=["verified_amount", "updated_at"])

    def __str__(self):
        return f"{self.declaration} · {self.get_section_code_display()}"


class InvestmentProof(TenantOwned):
    """An uploaded proof document for an ``InvestmentDeclarationLine`` (3.16) + its verification
    workflow. Mirrors ``EmployeeDocument``'s verified_by/verified_at/editable=False convention, one
    state richer (adds ``on_hold``). A line can have several proofs."""

    VERIFICATION_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("verified", "Verified"),
        ("rejected", "Rejected"),
        ("on_hold", "On Hold"),
    ]

    declaration_line = models.ForeignKey(
        "hrm.InvestmentDeclarationLine", on_delete=models.CASCADE, related_name="proofs")
    # WARNING: extension allowlist + size cap enforced in InvestmentProofForm.clean_file (shared
    # _validate_upload). Keep MEDIA_ROOT outside the web root and serve with Content-Disposition:
    # attachment + X-Content-Type-Options: nosniff in production (mirrors EmployeeDocument).
    file = models.FileField(upload_to="hrm/investment_proofs/%Y/%m/")
    title = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="The amount this proof substantiates (a line's verified_amount sums its verified proofs).")
    verification_status = models.CharField(max_length=15, choices=VERIFICATION_STATUS_CHOICES,
        default="pending", editable=False)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="hrm_verified_investment_proofs", editable=False)
    verified_at = models.DateTimeField(null=True, blank=True, editable=False)
    rejection_reason = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "declaration_line"], name="hrm_ivp_tenant_line_idx"),
            models.Index(fields=["tenant", "verification_status"], name="hrm_ivp_tenant_vstat_idx"),
        ]

    def __str__(self):
        return f"{self.declaration_line} · {self.title}"


class TaxComputation(TenantNumbered):
    """The per-employee-per-FY annual tax projection engine (3.16) — ``TXC-#####``. ``recompute()``
    derives ``tax_payable``/``tax_paid_ytd``/``monthly_tds_amount`` (mirroring ``Payslip.recompute()``/
    ``StatutoryReturn.recompute()``); the regime-comparison and taxable-income build-up are DERIVED
    @property methods (never stored). Links to the existing ``StatutoryReturn(scheme="tds_form16")`` row
    via ``link_form16()`` — no new Form-16 table. Recomputed in place, one row per employee per FY."""

    NUMBER_PREFIX = "TXC"

    COMPUTATION_TYPE_CHOICES = [
        ("provisional", "Provisional"),
        ("final", "Final"),
    ]

    employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.PROTECT, related_name="tax_computations")
    declaration = models.ForeignKey("hrm.InvestmentDeclaration", on_delete=models.PROTECT, related_name="tax_computations")
    financial_year = models.CharField(max_length=10, help_text="Denormalized from the declaration for filtering.")
    computation_type = models.CharField(max_length=15, choices=COMPUTATION_TYPE_CHOICES, default="provisional")
    manual_override_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="Overrides the derived monthly TDS when set (edge cases the formula can't cover).")
    override_reason = models.TextField(blank=True)
    remaining_pay_periods = models.PositiveSmallIntegerField(default=12,
        help_text="Pay periods left in the FY the projected tax is spread across.")
    tax_payable = models.DecimalField(max_digits=12, decimal_places=2, default=0, editable=False)
    tax_paid_ytd = models.DecimalField(max_digits=12, decimal_places=2, default=0, editable=False)
    monthly_tds_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, editable=False)
    statutory_return = models.ForeignKey(
        "hrm.StatutoryReturn", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="tax_computations", editable=False,
        help_text="The tds_form16 StatutoryReturn row this Part-B detail belongs to (set by link_form16).")
    computed_at = models.DateTimeField(null=True, blank=True, editable=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-financial_year", "employee__party__name"]
        unique_together = ("tenant", "employee", "financial_year")
        indexes = [
            models.Index(fields=["tenant", "financial_year"], name="hrm_txc_tenant_fy_idx"),
            models.Index(fields=["tenant", "employee"], name="hrm_txc_tenant_emp_idx"),
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Per-instance memo for the engine's DB primitives — the derived @property methods access them
        # many times per render (a detail page reads ~9 properties), so without this the same
        # structure/regime-config/declaration-lines/slab-bands lookups fire dozens of times. Only the
        # QUERY boundaries are cached (not the pure-Python tax properties), so recompute() stays correct.
        self._engine_cache = {}

    def save(self, *args, **kwargs):
        # financial_year is a denormalized copy of the declaration's — derive it here so it is always
        # populated regardless of the entry path (the form excludes it). A blank FY would make
        # _regime_config() find no TaxRegimeConfig and silently compute zero tax.
        if not self.financial_year and self.declaration_id:
            self.financial_year = self.declaration.financial_year
        return super().save(*args, **kwargs)

    # ----- resolved inputs (query the employee's active salary structure / regime config), memoized -----
    def _active_structure(self):
        if "structure" not in self._engine_cache:
            self._engine_cache["structure"] = (
                self.employee.salary_structures.filter(status="active")
                .select_related("template").order_by("-effective_from").first())
        return self._engine_cache["structure"]

    def _structure_lines(self):
        """The active structure's template lines (fetched once with the pay component preloaded)."""
        if "structure_lines" not in self._engine_cache:
            struct = self._active_structure()
            self._engine_cache["structure_lines"] = (
                list(struct.template.lines.select_related("pay_component"))
                if struct and struct.template_id else [])
        return self._engine_cache["structure_lines"]

    def _declaration_lines(self):
        """The declaration's section lines (fetched once — read by hra/chapter-via/capped-sections)."""
        if "declaration_lines" not in self._engine_cache:
            self._engine_cache["declaration_lines"] = list(self.declaration.lines.all())
        return self._engine_cache["declaration_lines"]

    def _component_annual(self, code, name_substr):
        """Resolve a pay component's annual amount from the employee's active structure (basic/HRA)."""
        struct = self._active_structure()
        if not struct or not struct.template_id:
            return ZERO
        for line in self._structure_lines():
            pc = line.pay_component
            if (pc.code or "").upper() == code or name_substr in pc.name.lower():
                return line.resolved_amount(struct.annual_ctc_amount)
        return ZERO

    def _regime_config(self, regime):
        key = ("regime_config", regime)
        if key not in self._engine_cache:
            self._engine_cache[key] = TaxRegimeConfig.objects.filter(
                tenant_id=self.tenant_id, financial_year=self.financial_year, regime=regime
            ).prefetch_related("slab_bands").first()
        return self._engine_cache[key]

    def _fy_date_range(self):
        """Parse ``"YYYY-YY"`` → (Apr 1 start, Mar 31 next-year end) of the Indian FY."""
        try:
            start_year = int(str(self.financial_year).split("-")[0])
        except (ValueError, IndexError, AttributeError):
            return date(1900, 1, 1), date(2999, 12, 31)
        return date(start_year, 4, 1), date(start_year + 1, 3, 31)

    @property
    def gross_annual_income(self):
        struct = self._active_structure()
        base = struct.annual_ctc_amount if struct else ZERO
        return (base + self.declaration.previous_employer_income).quantize(Decimal("0.01"))

    # ----- per-regime deduction helpers (regime-parameterized so both regimes can be compared) -----
    def _hra_exemption(self, regime):
        """Standard 3-way HRA exemption minimum (annual). Zero under the new regime or with no HRA line."""
        if regime == "new":
            return ZERO
        hra_line = next((ln for ln in self._declaration_lines() if ln.section_code == "hra"), None)
        if hra_line is None or not hra_line.monthly_rent_amount:
            return ZERO
        basic = self._component_annual("BASIC", "basic")
        annual_rent = hra_line.monthly_rent_amount * Decimal("12")
        pct = Decimal("50") if hra_line.is_metro_city else Decimal("40")
        candidates = [
            max(annual_rent - basic * Decimal("10") / Decimal("100"), ZERO),  # rent − 10% of basic
            basic * pct / Decimal("100"),                                      # 50%/40% of basic
        ]
        actual_hra = self._component_annual("HRA", "house rent")              # actual HRA received
        if actual_hra > 0:
            candidates.append(actual_hra)
        return max(min(candidates), ZERO).quantize(Decimal("0.01"))

    def _chapter_via(self, regime):
        """Sum the effective (verified-else-declared) Chapter VI-A deductions valid for ``regime``,
        capped per ``SECTION_CAPS``, excluding HRA (handled separately)."""
        total = ZERO
        for line in self._declaration_lines():
            if line.section_code == "hra":
                continue
            if regime == "new" and line.section_code not in NEW_REGIME_ALLOWED_SECTIONS:
                continue
            amt = line.effective_amount
            cap = SECTION_CAPS.get(line.section_code)
            if cap is not None:
                amt = min(amt, cap)
            total += amt
        return total.quantize(Decimal("0.01"))

    @property
    def capped_sections(self):
        """(label, claimed, cap) tuples for sections whose claim exceeded its statutory cap — surfaced
        as a warning, never silently dropped."""
        out = []
        for line in self._declaration_lines():
            cap = SECTION_CAPS.get(line.section_code)
            if cap is not None and line.effective_amount > cap:
                out.append((line.get_section_code_display(), line.effective_amount, cap))
        return out

    def _taxable_income(self, regime):
        config = self._regime_config(regime)
        std = config.standard_deduction if config else ZERO
        taxable = (self.gross_annual_income - std - self._hra_exemption(regime) - self._chapter_via(regime))
        return max(taxable, ZERO).quantize(Decimal("0.01"))

    def _regime_tax(self, regime):
        config = self._regime_config(regime)
        if config is None:
            return ZERO
        taxable = self._taxable_income(regime)
        # Sort the prefetched slab bands in Python (config is loaded via _regime_config's
        # prefetch_related("slab_bands"), so .order_by() would defeat the prefetch with a fresh query).
        bands = [(b.income_from, b.income_to, b.rate_percent)
                 for b in sorted(config.slab_bands.all(), key=lambda b: (b.sequence, b.income_from))]
        tax = _progressive_tax(taxable, bands)
        # Section 87A rebate — zero out (capped) when taxable income is at/below the threshold.
        if config.rebate_income_threshold is not None and taxable <= config.rebate_income_threshold:
            rebate = min(tax, config.rebate_max_tax if config.rebate_max_tax is not None else tax)
            tax = max(tax - rebate, ZERO)
        # Health & Education cess on the post-rebate tax.
        tax = (tax * (Decimal("1") + config.cess_rate / Decimal("100"))).quantize(Decimal("0.01"))
        return tax

    @property
    def hra_exemption(self):
        return self._hra_exemption(self.declaration.regime_elected)

    @property
    def total_chapter_via_deductions(self):
        return self._chapter_via(self.declaration.regime_elected)

    @property
    def taxable_income_old(self):
        return self._taxable_income("old")

    @property
    def taxable_income_new(self):
        return self._taxable_income("new")

    @property
    def tax_old_regime(self):
        return self._regime_tax("old")

    @property
    def tax_new_regime(self):
        return self._regime_tax("new")

    @property
    def cheaper_regime(self):
        """Which regime costs less (for the comparison nudge); ties resolve to 'new'."""
        return "old" if self.tax_old_regime < self.tax_new_regime else "new"

    def _tds_paid_ytd(self):
        """Sum this employee's TDS ``PayslipLine``s across the FY's cycles — reuses 3.15's TDS keyword
        list and the employee-bucket rule (everything not employer-side), scoped to this employee."""
        start, end = self._fy_date_range()
        lines = PayslipLine.objects.filter(
            tenant_id=self.tenant_id, component_type="statutory_deduction",
            payslip__employee_id=self.employee_id,
            payslip__cycle__pay_date__gte=start, payslip__cycle__pay_date__lte=end,
        ).exclude(contribution_side="employer")
        cond = Q()
        for kw in StatutoryReturn.SCHEME_KEYWORDS["tds_24q"]:
            cond |= Q(component_name__icontains=kw)
        return lines.filter(cond).aggregate(s=Sum("amount"))["s"] or ZERO

    def recompute(self):
        """Derive tax_payable (under the elected regime) + tax_paid_ytd + monthly_tds_amount. A ``final``
        computation requires the declaration's proof window to have closed (the provisional/final gate)."""
        if (self.computation_type == "final" and self.declaration.proof_window_close
                and self.declaration.proof_window_close > timezone.localdate()):
            raise ValidationError("A final computation requires the proof window to have closed.")
        self.tax_paid_ytd = self._tds_paid_ytd()
        self.tax_payable = (self.tax_old_regime if self.declaration.regime_elected == "old"
                            else self.tax_new_regime)
        if self.manual_override_amount is not None:
            self.monthly_tds_amount = self.manual_override_amount
        elif self.remaining_pay_periods:
            self.monthly_tds_amount = max(
                (self.tax_payable - self.tax_paid_ytd) / Decimal(self.remaining_pay_periods), ZERO
            ).quantize(Decimal("0.01"))
        else:
            self.monthly_tds_amount = ZERO
        self.computed_at = timezone.now()
        self.save(update_fields=["tax_payable", "tax_paid_ytd", "monthly_tds_amount",
                                 "computed_at", "updated_at"])

    def link_form16(self, user=None):
        """Get-or-create the ``StatutoryReturn(scheme="tds_form16")`` row for this employee/FY (Part A
        source) and link it. Recomputes that row's Part-A aggregates only while it is still pending."""
        start, end = self._fy_date_range()
        ret, _ = StatutoryReturn.objects.update_or_create(
            tenant_id=self.tenant_id, scheme="tds_form16", period_start=start, employee=self.employee,
            defaults={"period_type": "annual", "period_end": end,
                      "notes": f"Form 16 for {self.employee} · FY {self.financial_year}."})
        if ret.status == "pending":
            ret.recompute()
        self.statutory_return = ret
        self.save(update_fields=["statutory_return", "updated_at"])
        return ret

    def __str__(self):
        return f"{self.number} · {self.employee} · {self.financial_year}"


# ---------------------------------------------------------------------------
# 3.17 Payout & Reports — the salary DISBURSEMENT + distribution + reconciliation
# layer on top of 3.14 (PayrollCycle/Payslip). A PayoutBatch is generated from a
# LOCKED PayrollCycle's payslips; PayoutPayment tracks per-employee money-movement
# status (paid/failed/returned) against a snapshot of net_pay + the employee's
# MASKED bank details; PayslipDistribution tracks send/view/download of the payslip;
# BankReconciliation matches a batch's payments to the bank statement by UTR. This is
# bookkeeping ABOUT payments, not a ledger entry — money still posts only through
# accounting.PayrollRun/JournalEntry (L29); 3.17 posts NOTHING new to the GL. The
# actual bank-file writer + payslip-PDF rendering + live bank API are deferred.
# ---------------------------------------------------------------------------
class PayoutBatch(TenantNumbered):
    """A salary-disbursement run header (3.17) — ``POB-#####`` — generated from one **locked**
    ``PayrollCycle``'s payslips. Derived ``total_amount``/``paid_*``/``failed_count`` come from its
    ``PayoutPayment``s (over the non-superseded, i.e. non-retried, rows). One batch per cycle."""

    NUMBER_PREFIX = "POB"

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("approved", "Approved"),
        ("disbursed", "Disbursed"),
        ("partially_disbursed", "Partially Disbursed"),
        ("reconciled", "Reconciled"),
    ]
    BANK_FILE_FORMAT_CHOICES = [
        ("neft", "NEFT"),
        ("nach", "NACH"),
        ("ach", "ACH"),
        ("manual", "Manual"),
        ("other", "Other"),
    ]

    cycle = models.ForeignKey("hrm.PayrollCycle", on_delete=models.PROTECT, related_name="payout_batches")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    bank_file_format = models.CharField(max_length=15, choices=BANK_FILE_FORMAT_CHOICES, default="neft")
    source_bank_name = models.CharField(max_length=255, blank=True,
        help_text="The disbursing (company) bank surfaced before initiating payment.")
    source_account_last4 = models.CharField(max_length=8, blank=True,
        validators=[RegexValidator(r"^(••••)?\d{0,4}$",
            "Enter only a masked last-4 (e.g. ••••4321), never the full account number.")],
        help_text="Masked disbursing account — never the full number.")
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="hrm_payout_batch_generations", editable=False)
    generated_at = models.DateTimeField(null=True, blank=True, editable=False)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="hrm_payout_batch_approvals", editable=False)
    approved_at = models.DateTimeField(null=True, blank=True, editable=False)
    disbursed_at = models.DateTimeField(null=True, blank=True, editable=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-cycle__pay_date"]
        unique_together = ("tenant", "cycle")
        indexes = [
            models.Index(fields=["tenant", "status"], name="hrm_pob_tenant_status_idx"),
        ]

    def clean(self):
        super().clean()
        if self.cycle_id and not self.cycle.is_locked:
            raise ValidationError({"cycle": "A payout batch can only be created from a locked payroll cycle."})

    @property
    def is_editable(self):
        return self.status == "draft"

    def _current_payments(self):
        """The non-superseded payment rows (a retried failed row is excluded — its retry is the current
        one) — the correct set for totals so a retried employee is never double-counted."""
        return self.payments.filter(retries__isnull=True)

    def _totals(self):
        """One aggregate pass over the current payments, cached per instance (mirrors PayrollCycle._totals)."""
        if not hasattr(self, "_totals_cache"):
            cur = self._current_payments()
            self._totals_cache = cur.aggregate(
                head=Count("id"), total=Sum("net_amount"),
                paid_c=Count("id", filter=Q(status="paid")),
                paid_a=Sum("net_amount", filter=Q(status="paid")),
                failed_c=Count("id", filter=Q(status__in=["failed", "returned"])),
                hold_c=Count("id", filter=Q(status="on_hold")))
        return self._totals_cache

    @property
    def headcount(self):
        return self._totals()["head"] or 0

    @property
    def total_amount(self):
        return self._totals()["total"] or ZERO

    @property
    def paid_count(self):
        return self._totals()["paid_c"] or 0

    @property
    def paid_amount(self):
        return self._totals()["paid_a"] or ZERO

    @property
    def failed_count(self):
        return self._totals()["failed_c"] or 0

    @property
    def on_hold_count(self):
        return self._totals()["hold_c"] or 0

    def __str__(self):
        return f"{self.number} · {self.cycle.number} · {self.get_status_display()}"


class PayoutPayment(TenantOwned):
    """One employee's disbursement row within a ``PayoutBatch`` (3.17). ``net_amount`` + the bank fields
    are SNAPSHOTTED at generation — the bank fields are the employee's **already-masked** values
    (``masked_bank_account()``/``masked_bank_routing()``), never the raw account number, so they need no
    ``_SENSITIVE_AUDIT_FIELDS`` redaction. A failed payment is re-tried as a NEW row (``retry_of`` → the
    original), preserving the failure history — so there is deliberately **no** ``unique_together`` on
    ``(batch, payslip)`` (that would block a retry); the generate action guarantees one *original* per
    payslip (draft-only delete+recreate), and there is no user-facing create form."""

    PAYMENT_METHOD_CHOICES = [
        ("bank_transfer", "Bank Transfer"),
        ("neft", "NEFT"),
        ("nach", "NACH"),
        ("ach", "ACH"),
        ("cheque", "Cheque"),
        ("cash", "Cash"),
        ("other", "Other"),
    ]
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("paid", "Paid"),
        ("failed", "Failed"),
        ("returned", "Returned"),
        ("on_hold", "On Hold"),
    ]

    batch = models.ForeignKey("hrm.PayoutBatch", on_delete=models.CASCADE, related_name="payments")
    payslip = models.ForeignKey("hrm.Payslip", on_delete=models.PROTECT, related_name="payout_payments")
    employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.PROTECT, related_name="payout_payments")
    net_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0, editable=False,
        help_text="Snapshot of Payslip.net_pay at generation time.")
    bank_name_snapshot = models.CharField(max_length=255, blank=True, editable=False)
    bank_account_last4_snapshot = models.CharField(max_length=8, blank=True, editable=False,
        help_text="Masked last-4 of the destination account — never the full number.")
    bank_routing_snapshot = models.CharField(max_length=20, blank=True, editable=False)
    payment_method = models.CharField(max_length=15, choices=PAYMENT_METHOD_CHOICES, default="bank_transfer")
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="pending")
    transaction_reference = models.CharField(max_length=64, blank=True,
        help_text="Bank-assigned UTR / trace number — the reconciliation match key.")
    initiated_at = models.DateTimeField(null=True, blank=True, editable=False)
    paid_on = models.DateTimeField(null=True, blank=True, editable=False)
    failure_reason = models.TextField(blank=True)
    retry_of = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="retries")

    class Meta:
        ordering = ["batch", "employee__party__name"]
        indexes = [
            models.Index(fields=["tenant", "batch"], name="hrm_pop_tenant_batch_idx"),
            models.Index(fields=["tenant", "status"], name="hrm_pop_tenant_status_idx"),
        ]

    def __str__(self):
        return f"{self.employee} · {self.net_amount} · {self.get_status_display()}"


class PayslipDistribution(TenantOwned):
    """Delivery tracking for a ``Payslip`` (3.17) — 1:1. Tracks the send→viewed→downloaded signal chain
    (the actual PDF render + SMTP dispatch are deferred). Created lazily via ``for_payslip()``."""

    DELIVERY_CHANNEL_CHOICES = [
        ("email", "Email"),
        ("portal", "Portal"),
        ("print", "Print"),
    ]
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("sent", "Sent"),
        ("viewed", "Viewed"),
        ("downloaded", "Downloaded"),
        ("failed", "Failed"),
    ]

    payslip = models.OneToOneField("hrm.Payslip", on_delete=models.CASCADE, related_name="distribution")
    delivery_channel = models.CharField(max_length=10, choices=DELIVERY_CHANNEL_CHOICES, default="portal")
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="pending")
    sent_to_email = models.EmailField(blank=True, editable=False,
        help_text="Snapshot of the employee's email at send time.")
    sent_at = models.DateTimeField(null=True, blank=True, editable=False)
    viewed_at = models.DateTimeField(null=True, blank=True, editable=False)
    downloaded_at = models.DateTimeField(null=True, blank=True, editable=False)
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="hrm_payslip_distribution_sends", editable=False)

    class Meta:
        ordering = ["-payslip__cycle__pay_date"]
        indexes = [
            models.Index(fields=["tenant", "status"], name="hrm_psd_tenant_status_idx"),
        ]

    @classmethod
    def for_payslip(cls, payslip):
        """Get-or-create the one distribution row for ``payslip`` (defaults portal/pending)."""
        obj, _ = cls.objects.get_or_create(
            tenant_id=payslip.tenant_id, payslip=payslip,
            defaults={"delivery_channel": "portal", "status": "pending"})
        return obj

    def __str__(self):
        return f"{self.payslip} · {self.get_status_display()}"


class BankReconciliation(TenantNumbered):
    """Reconciles a ``PayoutBatch``'s payments against an imported bank statement (3.17) — ``BRC-#####``.
    ``recompute()`` matches by ``PayoutPayment.transaction_reference``/``status`` (no separate
    ``BankStatementLine`` table); matched/unmatched aggregates are derived."""

    NUMBER_PREFIX = "BRC"

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("in_progress", "In Progress"),
        ("reconciled", "Reconciled"),
        ("discrepancy", "Discrepancy"),
    ]

    batch = models.ForeignKey("hrm.PayoutBatch", on_delete=models.PROTECT, related_name="reconciliations")
    statement_date = models.DateField()
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="pending")
    matched_count = models.PositiveIntegerField(default=0, editable=False)
    matched_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0, editable=False)
    unmatched_count = models.PositiveIntegerField(default=0, editable=False)
    unmatched_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0, editable=False)
    statement_reference = models.CharField(max_length=100, blank=True)
    reconciled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="hrm_bank_reconciliations", editable=False)
    reconciled_at = models.DateTimeField(null=True, blank=True, editable=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-statement_date"]
        indexes = [
            models.Index(fields=["tenant", "batch"], name="hrm_brc_tenant_batch_idx"),
            models.Index(fields=["tenant", "status"], name="hrm_brc_tenant_status_idx"),
        ]

    def recompute(self):
        """Match the batch's current payments against the (implicit) bank statement by UTR + status:
        a payment with a transaction_reference AND status=paid is matched; everything else (failed/
        returned, or a processing/pending row with no UTR) is unmatched. Sets aggregates + status."""
        cur = self.batch._current_payments()
        matched = cur.filter(status="paid").exclude(transaction_reference="")
        unmatched = cur.exclude(pk__in=matched.values("pk"))
        m = matched.aggregate(c=Count("id"), a=Sum("net_amount"))
        u = unmatched.aggregate(c=Count("id"), a=Sum("net_amount"))
        self.matched_count = m["c"] or 0
        self.matched_amount = m["a"] or ZERO
        self.unmatched_count = u["c"] or 0
        self.unmatched_amount = u["a"] or ZERO
        self.status = "reconciled" if self.unmatched_count == 0 else "discrepancy"
        self.reconciled_at = timezone.now()
        self.save(update_fields=["matched_count", "matched_amount", "unmatched_count",
                                 "unmatched_amount", "status", "reconciled_at", "updated_at"])

    def __str__(self):
        return f"{self.number} · {self.batch.number} · {self.get_status_display()}"


# ===========================================================================
# 3.18 Goal Setting — Performance Management (OKR mechanics)
# ---------------------------------------------------------------------------
# The first Performance-Management sub-module (3.18 → 3.19 Performance Review →
# 3.20 Continuous Feedback → 3.21 Performance Improvement). Pure HRM-domain
# extension hanging off ``EmployeeProfile`` (the goal owner) and ``core.OrgUnit``
# (department scope, reused exactly as ``Designation.department`` does) — NO new
# core-spine entity. Progress % and health are DERIVED (never stored editable
# columns), mirroring how ``LeaveAllocation``/``AttendanceRecord.hours_worked``
# already work. Cascading alignment is the single self-FK ``Objective.parent_objective``
# (vertical only); weighting is KR-level (``KeyResult.weight``); the KR-type
# distinction is a ``metric_type`` CharField choice rather than a 5th model.
# ===========================================================================
def _clamp_pct(value):
    """Clamp a Decimal progress percentage into ``[0, 100]``."""
    if value < ZERO:
        return ZERO
    hundred = Decimal("100")
    return hundred if value > hundred else value


def _pace_health(progress_pct, start_date, end_date, *, completed=False):
    """Derive an on_track/at_risk/off_track health signal by comparing realized
    progress against the fraction of the period's time already elapsed. Shared by
    ``Objective.health_status`` and ``KeyResult.health_status`` (3.18.5 status/health
    coloring — Weekdone/WorkBoard/Betterworks). ``completed`` short-circuits to the
    terminal state. Guards a zero-length period (no divide-by-zero)."""
    if completed:
        return "completed"
    if not start_date or not end_date:
        return "on_track"
    total_days = (end_date - start_date).days
    if total_days <= 0:
        expected = Decimal("100")
    else:
        elapsed = min(max((timezone.localdate() - start_date).days, 0), total_days)
        expected = Decimal(elapsed) / Decimal(total_days) * Decimal("100")
    gap = expected - Decimal(progress_pct)  # positive ⇒ behind the expected pace
    if gap <= 10:
        return "on_track"
    if gap <= 25:
        return "at_risk"
    return "off_track"


# Human labels for the derived health_status codes (no choices= field to give a get_*_display).
_HEALTH_LABELS = {"on_track": "On Track", "at_risk": "At Risk",
                  "off_track": "Off Track", "completed": "Completed"}


class GoalPeriod(TenantOwned):
    """A named quarterly/half-yearly/annual OKR cycle every ``Objective`` is scoped to
    (3.18.4 Goal Timeline). Small per-tenant catalog identified by ``name`` — not
    auto-numbered, same pattern as ``hrm.JobGrade``. "Current" is simply
    ``status="active"`` (no second is_current source of truth)."""

    PERIOD_TYPE_CHOICES = [
        ("quarterly", "Quarterly"),
        ("half_yearly", "Half-Yearly"),
        ("annual", "Annual"),
        ("custom", "Custom"),
    ]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("active", "Active"),
        ("closed", "Closed"),
        ("archived", "Archived"),
    ]

    name = models.CharField(max_length=100, help_text='e.g. "Q3 2026".')
    period_type = models.CharField(max_length=15, choices=PERIOD_TYPE_CHOICES, default="quarterly")
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="draft")
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["-start_date"]
        unique_together = ("tenant", "name")
        indexes = [
            models.Index(fields=["tenant", "status"], name="hrm_gp_tenant_status_idx"),
        ]

    def clean(self):
        if self.start_date and self.end_date and self.end_date <= self.start_date:
            raise ValidationError({"end_date": "End date must be after the start date."})

    @property
    def objective_count(self):
        # A view's list uses an annotated ``num_objectives`` (O(1)); this property is for
        # the detail page where the objectives are already loaded/prefetched.
        return self.objectives.count()

    @property
    def avg_progress_pct(self):
        """Simple mean of the period's objectives' (already-derived) progress. ``progress_pct``
        is not a DB column, so this is computed in Python — the detail view prefetches
        ``objectives__key_results`` to keep it a bounded number of queries."""
        objs = list(self.objectives.all())
        if not objs:
            return ZERO
        total = sum((o.progress_pct for o in objs), ZERO)
        return _clamp_pct(total / Decimal(len(objs)))

    def __str__(self):
        return f"{self.name} ({self.get_period_type_display()})"


class Objective(TenantNumbered):
    """The "O" in OKR (3.18.1/3.18.2/3.18.3/3.18.4). Owned by an ``EmployeeProfile``,
    scoped to a ``GoalPeriod``, optionally aligned up a cascade via ``parent_objective``
    and tagged to a ``core.OrgUnit`` department. ``progress_pct``/``health_status`` are
    derived from its KeyResults, never stored."""

    NUMBER_PREFIX = "OBJ"

    SCOPE_CHOICES = [
        ("company", "Company"),
        ("department", "Department"),
        ("team", "Team"),
        ("individual", "Individual"),
    ]
    TARGET_TYPE_CHOICES = [
        ("aspirational", "Aspirational"),
        ("committed", "Committed"),
    ]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("active", "Active"),
        ("at_risk", "At Risk"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    owner = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.PROTECT, related_name="objectives",
                              help_text="The goal owner (an EmployeeProfile — never a raw Party/User).")
    goal_period = models.ForeignKey("hrm.GoalPeriod", on_delete=models.PROTECT, related_name="objectives")
    parent_objective = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True,
                                         related_name="child_objectives",
                                         help_text="Aligns (rolls up into) a parent objective — the cascade link.")
    department = models.ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="objectives",
                                   help_text="Department/team scope (a core.OrgUnit); blank for individual goals.")
    scope = models.CharField(max_length=15, choices=SCOPE_CHOICES, default="individual")
    target_type = models.CharField(max_length=15, choices=TARGET_TYPE_CHOICES, default="committed",
                                   help_text="Aspirational (50–70% is a win) vs. committed (100% expected).")
    weight = models.DecimalField(max_digits=5, decimal_places=2, default=100,
                                 validators=[MinValueValidator(0), MaxValueValidator(100)],
                                 help_text="Relative weight among SIBLING objectives under the same parent "
                                           "(for a parent's weighted-children view). NOT used to compute this "
                                           "objective's own progress_pct — that is strictly a KR-weighted rollup.")
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="draft")
    start_date = models.DateField(null=True, blank=True,
                                  help_text="Defaults to the period's start; stored so an objective can start later.")
    due_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-goal_period__start_date", "title"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="hrm_obj_tenant_status_idx"),
            models.Index(fields=["tenant", "goal_period"], name="hrm_obj_tenant_period_idx"),
            models.Index(fields=["tenant", "owner"], name="hrm_obj_tenant_owner_idx"),
            models.Index(fields=["tenant", "parent_objective"], name="hrm_obj_tenant_parent_idx"),
            models.Index(fields=["tenant", "department"], name="hrm_obj_tenant_department_idx"),
        ]

    def clean(self):
        # No self-parenting, and no cycle in the alignment chain (cheap bounded walk).
        if self.parent_objective_id and self.pk and self.parent_objective_id == self.pk:
            raise ValidationError({"parent_objective": "An objective cannot align to itself."})
        node, depth = self.parent_objective, 0
        while node is not None and depth < 20:
            if self.pk and node.pk == self.pk:
                raise ValidationError({"parent_objective": "This alignment would create a cycle."})
            node, depth = node.parent_objective, depth + 1

    def _krs(self):
        """Materialize child KeyResults once per instance (prefetched by list/detail views)
        so ``progress_pct``/``health_status``/``key_result_count`` don't re-query."""
        if not hasattr(self, "_krs_cache"):
            self._krs_cache = list(self.key_results.all())
        return self._krs_cache

    @property
    def progress_pct(self):
        """Weighted average of child ``KeyResult.progress_pct`` by ``KeyResult.weight``
        (3.18.3 weighted rollup). Falls back to a simple mean if all weights are 0;
        ``0`` when there are no key results."""
        krs = self._krs()
        if not krs:
            return ZERO
        total_weight = sum((kr.weight for kr in krs), ZERO)
        if total_weight > 0:
            acc = sum((kr.progress_pct * kr.weight for kr in krs), ZERO)
            return _clamp_pct(acc / total_weight)
        acc = sum((kr.progress_pct for kr in krs), ZERO)
        return _clamp_pct(acc / Decimal(len(krs)))

    @property
    def health_status(self):
        start = self.start_date or (self.goal_period.start_date if self.goal_period_id else None)
        end = self.due_date or (self.goal_period.end_date if self.goal_period_id else None)
        return _pace_health(self.progress_pct, start, end, completed=(self.status == "completed"))

    @property
    def health_status_display(self):
        return _HEALTH_LABELS.get(self.health_status, self.health_status)

    @property
    def key_result_count(self):
        return len(self._krs())

    def __str__(self):
        return f"{self.number} · {self.title}"


class KeyResult(TenantNumbered):
    """The measurable "KR" under an ``Objective`` (3.18.1/3.18.3/3.18.5). ``metric_type``
    folds the Viva Goals/Perdoo/Profit.co KR-type distinction into one CharField.
    ``progress_pct``/``health_status`` are derived, never stored."""

    NUMBER_PREFIX = "KR"

    METRIC_TYPE_CHOICES = [
        ("numeric", "Numeric"),
        ("percentage", "Percentage"),
        ("currency", "Currency"),
        ("boolean", "Boolean"),
        ("milestone", "Milestone"),
    ]
    STATUS_CHOICES = [
        ("not_started", "Not Started"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]
    _METRIC_TYPES = ("numeric", "percentage", "currency")

    objective = models.ForeignKey("hrm.Objective", on_delete=models.CASCADE, related_name="key_results")
    title = models.CharField(max_length=255)
    metric_type = models.CharField(max_length=15, choices=METRIC_TYPE_CHOICES, default="numeric")
    start_value = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True,
                                      help_text="Baseline value (nullable for boolean/milestone KRs).")
    target_value = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    current_value = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True,
                                        help_text="Advanced by GoalCheckIn.save(); also directly editable on the KR form.")
    is_milestone_event = models.BooleanField(default=False,
                                             help_text="For milestone-type KRs: progress is driven by discrete "
                                                       "check-in milestone events rather than a continuous value.")
    unit = models.CharField(max_length=30, blank=True, help_text='Free text, e.g. "%", "$", "signups".')
    weight = models.DecimalField(max_digits=5, decimal_places=2, default=0,
                                 validators=[MinValueValidator(0), MaxValueValidator(100)],
                                 help_text="Weight among sibling KeyResults under the same Objective "
                                           "(equal-split by default, overridable).")
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="not_started")

    class Meta:
        ordering = ["objective", "-weight", "title"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "objective"], name="hrm_kr_tenant_objective_idx"),
            models.Index(fields=["tenant", "status"], name="hrm_kr_tenant_status_idx"),
        ]

    def clean(self):
        if self.metric_type in self._METRIC_TYPES and self.target_value is None:
            raise ValidationError({"target_value": "A numeric/percentage/currency key result needs a target value."})
        if self.weight is not None and self.weight < 0:
            raise ValidationError({"weight": "Weight cannot be negative."})

    @property
    def progress_pct(self):
        """Derived completion %. Numeric-family KRs interpolate start→current→target;
        boolean is 0/100; milestone falls back to completion status (step-weighted
        milestone sub-tracking is deferred)."""
        mt = self.metric_type
        if mt in self._METRIC_TYPES:
            if self.target_value is None:
                return ZERO
            start = self.start_value if self.start_value is not None else ZERO
            current = self.current_value if self.current_value is not None else start
            denom = self.target_value - start
            if denom == 0:
                return Decimal("100") if current >= self.target_value else ZERO
            return _clamp_pct((current - start) / denom * Decimal("100"))
        if mt == "boolean":
            if self.status == "completed":
                return Decimal("100")
            return Decimal("100") if (self.current_value or ZERO) else ZERO
        # milestone: completion-driven fallback (no milestone_target_count field this pass).
        return Decimal("100") if self.status == "completed" else ZERO

    @property
    def health_status(self):
        # Uses the parent objective's period window; views set kr.objective / select_related
        # objective__goal_period so this stays query-free at render time.
        period = self.objective.goal_period if self.objective_id else None
        start = period.start_date if period else None
        end = period.end_date if period else None
        return _pace_health(self.progress_pct, start, end, completed=(self.status == "completed"))

    @property
    def health_status_display(self):
        return _HEALTH_LABELS.get(self.health_status, self.health_status)

    def __str__(self):
        return f"{self.number} · {self.title} ({self.get_metric_type_display()})"


class GoalCheckIn(TenantNumbered):
    """A timestamped progress-update log entry against a ``KeyResult`` (3.18.5 Goal
    Tracking). An append-only history row (no edit view) — Betterworks/Viva Goals/
    Quantive/Perdoo/Weekdone/Profit.co all treat check-ins as history, not a mutable
    field. On create it advances the parent ``KeyResult.current_value``."""

    NUMBER_PREFIX = "GCI"

    CONFIDENCE_CHOICES = [
        ("on_track", "On Track"),
        ("at_risk", "At Risk"),
        ("off_track", "Off Track"),
    ]

    key_result = models.ForeignKey("hrm.KeyResult", on_delete=models.CASCADE, related_name="checkins")
    checkin_date = models.DateField(default=timezone.localdate)
    value_at_checkin = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True,
                                           help_text="The KR value reported at this check-in (advances current_value).")
    confidence = models.CharField(max_length=15, choices=CONFIDENCE_CHOICES, default="on_track",
                                  help_text="Self-reported at check-in time (distinct from the derived KR health_status).")
    is_milestone_event = models.BooleanField(default=False,
                                             help_text="Marks a discrete milestone-completion event (milestone-type KRs).")
    comment = models.TextField(blank=True, help_text="Blockers / wins note.")
    created_by = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="goal_checkins", editable=False,
                                   help_text="Resolved from request.user in the view (allows manager overrides).")

    class Meta:
        ordering = ["-checkin_date", "-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "key_result"], name="hrm_gci_tenant_kr_idx"),
            models.Index(fields=["tenant", "checkin_date"], name="hrm_gci_tenant_date_idx"),
        ]

    def save(self, *args, **kwargs):
        is_create = self.pk is None
        super().save(*args, **kwargs)
        # The check-in is the single write path that advances the KR's current value.
        if is_create and self.value_at_checkin is not None and self.key_result_id:
            kr = self.key_result
            if kr.current_value != self.value_at_checkin:
                kr.current_value = self.value_at_checkin
                kr.save(update_fields=["current_value", "updated_at"])

    def __str__(self):
        return f"{self.number} · {self.key_result.title} · {self.get_confidence_display()}"


# ===========================================================================
# 3.19 Performance Review — Performance Management (formal appraisal cycles)
# ---------------------------------------------------------------------------
# The second Performance-Management sub-module (3.18 Goal Setting → 3.19 → 3.20
# Continuous Feedback → 3.21 Performance Improvement). Formal review-cycle
# mechanics: self/manager/peer/upward review instances, per-competency weighted
# ratings, and calibration fields. REFERENCES the built 3.18 GoalPeriod/Objective
# for the goal-review section (never duplicates OKR fields). subject/reviewer are
# EmployeeProfile; the manager-review reviewer flows through the DERIVED
# EmployeeProfile.manager reporting line — no new manager FK. overall_rating is a
# DERIVED weighted mean (never stored); manager_rating/calibrated_rating are stored
# (Workday's documented pre/post-calibration two-field distinction). No new
# core-spine entity, posts no GL.
# ===========================================================================

# Shared across ReviewTemplate + PerformanceReview (a review instance denormalizes
# review_type from its template for query convenience).
REVIEW_TYPE_CHOICES = [
    ("self", "Self"),
    ("manager", "Manager"),
    ("peer", "Peer"),
    ("upward", "Upward"),
    ("skip_level", "Skip-Level"),
]


class ReviewCycle(TenantOwned):
    """A named annual/half-yearly/quarterly appraisal cycle + a phase machine (3.19.1).
    Small per-tenant catalog identified by ``name`` (not auto-numbered, same pattern as
    ``GoalPeriod``/``JobGrade``). Optionally aligned to a 3.18 ``GoalPeriod`` so a review's
    goal section reuses the OKR cycle window."""

    CYCLE_TYPE_CHOICES = [
        ("annual", "Annual"),
        ("half_yearly", "Half-Yearly"),
        ("quarterly", "Quarterly"),
        ("custom", "Custom"),
    ]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("self_assessment", "Self-Assessment"),
        ("manager_review", "Manager Review"),
        ("calibration", "Calibration"),
        ("released", "Results Released"),
        ("closed", "Closed"),
    ]
    # Phase order for reviewcycle_advance_phase (no magic-string math duplicated in the view).
    PHASE_ORDER = ("draft", "self_assessment", "manager_review", "calibration", "released", "closed")

    name = models.CharField(max_length=100, help_text='e.g. "H1 2026 Performance Review".')
    cycle_type = models.CharField(max_length=15, choices=CYCLE_TYPE_CHOICES, default="annual")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft",
                              help_text="Phase machine — gates which review actions are open. Advanced via the workflow action.")
    self_review_start = models.DateField(null=True, blank=True)
    self_review_end = models.DateField(null=True, blank=True)
    manager_review_start = models.DateField(null=True, blank=True)
    manager_review_end = models.DateField(null=True, blank=True)
    calibration_date = models.DateField(null=True, blank=True)
    results_release_date = models.DateField(null=True, blank=True)
    goal_period = models.ForeignKey("hrm.GoalPeriod", on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="review_cycles",
                                    help_text="Aligns the review to a 3.18 OKR cycle (the goal-review section reads its Objectives).")
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["-self_review_start", "name"]
        unique_together = ("tenant", "name")
        indexes = [
            models.Index(fields=["tenant", "status"], name="hrm_rc_tenant_status_idx"),
        ]

    def clean(self):
        if self.self_review_start and self.self_review_end and self.self_review_end <= self.self_review_start:
            raise ValidationError({"self_review_end": "Self-review end must be after its start."})
        if self.manager_review_start and self.manager_review_end and self.manager_review_end <= self.manager_review_start:
            raise ValidationError({"manager_review_end": "Manager-review end must be after its start."})
        if (self.manager_review_start and self.self_review_end
                and self.manager_review_start < self.self_review_end):
            raise ValidationError(
                {"manager_review_start": "Manager review shouldn't start before self-assessment closes."})

    @property
    def review_count(self):
        return self.reviews.count()

    def __str__(self):
        return f"{self.name} ({self.get_cycle_type_display()})"


class ReviewTemplate(TenantNumbered):
    """The review-form definition per participant type (3.19.3/3.19.4). A cycle can attach several
    templates (one per ``review_type``) so the peer form can differ from the manager form."""

    NUMBER_PREFIX = "RVT"

    REVIEW_TYPE_CHOICES = REVIEW_TYPE_CHOICES

    name = models.CharField(max_length=150)
    review_type = models.CharField(max_length=15, choices=REVIEW_TYPE_CHOICES, default="self")
    rating_scale_max = models.PositiveSmallIntegerField(
        default=5, validators=[MinValueValidator(2), MaxValueValidator(10)],
        help_text="Top of the rating scale (5-point is the de-facto standard).")
    include_goals = models.BooleanField(
        default=False, help_text="Pull the subject's 3.18 Objectives into a goal-review section.")
    is_anonymous = models.BooleanField(
        default=False, help_text="Default anonymity (peer/360 commonly True); overridable per review.")
    description = models.TextField(blank=True, help_text="Instructions shown to the reviewer.")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["review_type", "name"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "review_type"], name="hrm_rvt_tenant_type_idx"),
            models.Index(fields=["tenant", "is_active"], name="hrm_rvt_tenant_active_idx"),
        ]

    @property
    def usage_count(self):
        return self.reviews.count()

    def __str__(self):
        return f"{self.number} · {self.name} ({self.get_review_type_display()})"


class PerformanceReview(TenantNumbered):
    """The per-instance review row — one per (cycle, subject, reviewer) (3.19.2/3.19.3/3.19.4/3.19.5).
    Self/manager/peer/upward all become rows of this one table. ``overall_rating`` is a derived
    weighted mean of the review's ratings; ``manager_rating``/``calibrated_rating`` are stored
    (pre/post-calibration audit trail)."""

    NUMBER_PREFIX = "RVW"

    REVIEW_TYPE_CHOICES = REVIEW_TYPE_CHOICES
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("submitted", "Submitted"),
        ("shared", "Shared"),
        ("acknowledged", "Acknowledged"),
    ]

    cycle = models.ForeignKey("hrm.ReviewCycle", on_delete=models.PROTECT, related_name="reviews")
    template = models.ForeignKey("hrm.ReviewTemplate", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="reviews")
    subject = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.PROTECT, related_name="reviews_received",
                                help_text="The employee being reviewed.")
    reviewer = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.PROTECT, related_name="reviews_authored",
                                 help_text="Who fills this instance (== subject for a self review).")
    review_type = models.CharField(max_length=15, choices=REVIEW_TYPE_CHOICES, default="self",
                                   help_text="Denormalized from the template at creation for query convenience.")
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="draft")
    # overall_rating is DERIVED (see the property) — never a stored column.
    manager_rating = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True,
                                         help_text="As-submitted pre-calibration snapshot (manager reviews).")
    calibrated_rating = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True,
                                            help_text="Post-calibration override; downstream comp/promotion reads this.")
    potential_rating = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True,
                                           help_text="9-box potential axis (visualization deferred).")
    strengths = models.TextField(blank=True)
    improvements = models.TextField(blank=True)
    private_notes = models.TextField(blank=True,
                                     help_text="Manager-only — NEVER rendered on the subject-facing view.")
    calibration_notes = models.TextField(blank=True, help_text="Calibration adjustment rationale.")
    is_anonymous = models.BooleanField(default=False,
                                       help_text="Masks the reviewer on the subject-facing view (peer/upward).")
    submitted_at = models.DateTimeField(null=True, blank=True, editable=False)
    shared_at = models.DateTimeField(null=True, blank=True, editable=False)
    acknowledged_at = models.DateTimeField(null=True, blank=True, editable=False)
    acknowledged_by = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.SET_NULL, null=True, blank=True,
                                        related_name="reviews_acknowledged", editable=False)

    class Meta:
        ordering = ["-cycle__self_review_start", "subject__party__name"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "cycle"], name="hrm_rvw_tenant_cycle_idx"),
            models.Index(fields=["tenant", "subject"], name="hrm_rvw_tenant_subject_idx"),
            models.Index(fields=["tenant", "reviewer"], name="hrm_rvw_tenant_reviewer_idx"),
            models.Index(fields=["tenant", "review_type"], name="hrm_rvw_tenant_type_idx"),
            models.Index(fields=["tenant", "status"], name="hrm_rvw_tenant_status_idx"),
        ]

    def clean(self):
        if self.review_type == "self" and self.subject_id and self.reviewer_id != self.subject_id:
            raise ValidationError({"reviewer": "A self review must have the subject as the reviewer."})
        if self.review_type != "self" and self.subject_id and self.reviewer_id == self.subject_id:
            raise ValidationError({"reviewer": "A non-self review can't have the subject reviewing themselves."})
        if self.manager_rating is not None and self.review_type != "manager":
            raise ValidationError({"manager_rating": "Manager rating only applies to a manager review."})

    def _ratings(self):
        """Materialize the review's rating lines once per instance (prefetched by detail views)
        so overall_rating/rating_count don't re-query (mirrors Objective._krs())."""
        if not hasattr(self, "_ratings_cache"):
            self._ratings_cache = list(self.ratings.all())
        return self._ratings_cache

    @property
    def overall_rating(self):
        """Weighted mean of the review's ``ReviewRating`` values by weight (simple mean if all
        weights are 0). Returns ``None`` — not 0 — when there are no ratings yet, since a rating
        of 0 is a valid low score and an unrated review should read "Not yet rated"."""
        rows = self._ratings()
        if not rows:
            return None
        total_weight = sum((r.weight for r in rows), ZERO)
        if total_weight > 0:
            acc = sum((r.rating_value * r.weight for r in rows), ZERO)
            return (acc / total_weight).quantize(Decimal("0.01"))
        acc = sum((r.rating_value for r in rows), ZERO)
        return (acc / Decimal(len(rows))).quantize(Decimal("0.01"))

    @property
    def rating_count(self):
        return len(self._ratings())

    @property
    def effective_rating(self):
        """The single value downstream consumers (comp/promotion) read — calibrated overrides the
        derived overall, per Workday's documented pattern."""
        return self.calibrated_rating if self.calibrated_rating is not None else self.overall_rating

    @property
    def goal_period(self):
        """Convenience passthrough to the cycle's aligned OKR period (for the goal-review section)."""
        return self.cycle.goal_period if self.cycle_id else None

    @property
    def reviewer_anonymized(self):
        """True when the reviewer name should be hidden in summary/list views (anonymous peer/upward
        feedback). The detail view additionally un-hides it for the reviewer/admin via ``show_reviewer``."""
        return self.is_anonymous and self.review_type in ("peer", "upward")

    def __str__(self):
        return f"{self.number} · {self.subject.party.name} ({self.get_review_type_display()})"


class ReviewRating(TenantNumbered):
    """A per-competency/question rating line under a review (3.19.3/3.19.4). ``weight`` mirrors
    ``Objective.weight``/``KeyResult.weight`` so the review's ``overall_rating`` derives as a
    weighted mean rather than a hand-typed duplicate."""

    NUMBER_PREFIX = "RVR"

    CATEGORY_CHOICES = [
        ("competency", "Competency"),
        ("goal", "Goal"),
        ("value", "Company Value"),
        ("custom", "Custom"),
    ]

    review = models.ForeignKey("hrm.PerformanceReview", on_delete=models.CASCADE, related_name="ratings")
    criterion_label = models.CharField(max_length=255, help_text="The competency/question text.")
    criterion_category = models.CharField(max_length=15, choices=CATEGORY_CHOICES, default="competency")
    rating_value = models.DecimalField(max_digits=4, decimal_places=2,
                                       help_text="Per-criterion score (within the template's rating scale).")
    weight = models.DecimalField(max_digits=5, decimal_places=2, default=0,
                                 validators=[MinValueValidator(0), MaxValueValidator(100)],
                                 help_text="Weight among sibling ratings under the same review (equal-split by default).")
    comment = models.TextField(blank=True)

    class Meta:
        ordering = ["review", "-weight", "criterion_label"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "review"], name="hrm_rvr_tenant_review_idx"),
        ]

    def clean(self):
        if self.rating_value is not None and self.rating_value < 0:
            raise ValidationError({"rating_value": "Rating cannot be negative."})
        if (self.rating_value is not None and self.review_id and self.review.template_id
                and self.rating_value > self.review.template.rating_scale_max):
            raise ValidationError(
                {"rating_value": f"Rating cannot exceed the template's scale max ({self.review.template.rating_scale_max})."})
        if self.weight is not None and self.weight < 0:
            raise ValidationError({"weight": "Weight cannot be negative."})

    def __str__(self):
        return f"{self.number} · {self.criterion_label} ({self.rating_value})"


# ---------------------------------------------------------------------------
# 3.20 Continuous Feedback — the ongoing/informal performance layer: real-time
# kudos/appreciation/constructive feedback (incl. a request-feedback pull
# workflow + anonymous masking), 1:1 meetings with shared/private notes +
# action items, and a computed given/received/requested feedback dashboard
# (a view, NOT a 5th model — mirrors Objective.progress_pct). Third
# Performance-Management sub-module after 3.18 Goal Setting and 3.19 Performance
# Review; PIP/warning-letters/coaching are 3.21. Reuses the unified spine +
# already-built HRM models (NavERP-ERD.md): every person is an
# ``EmployeeProfile`` (giver/receiver, 1:1 manager/employee, action-item owner);
# feedback and 1:1s optionally link to a 3.18 ``Objective`` or a 3.19
# ``PerformanceReview`` for work context. Adds ONLY the Feedback/1:1 tables + a
# small KudosBadge catalog — no new core-spine entity, posts no GL. Confidentiality
# clones 3.19 field-for-field: ``OneOnOneMeeting.manager_private_notes`` clones
# ``PerformanceReview.private_notes`` (manager-only, never rendered employee-side)
# and ``Feedback.is_anonymous`` clones the reviewer-masking pattern (giver hidden
# from non-admins on read).
# ---------------------------------------------------------------------------
class KudosBadge(TenantOwned):
    """A small per-tenant recognition-badge catalog — the values/company-value tags a kudos can
    carry ("Team Player", "Above & Beyond", …). Same shape as ``JobGrade``/``GoalPeriod``/
    ``ReviewCycle``: identified by ``name``, not auto-numbered."""

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True, help_text="Emoji or icon name for the UI chip.")
    color = models.CharField(max_length=20, blank=True, help_text="Hex or Tailwind class for the chip.")
    linked_value = models.CharField(max_length=100, blank=True,
                                    help_text="Free-text company value this badge celebrates (e.g. 'Customer First').")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        unique_together = ("tenant", "name")
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="hrm_kb_tenant_active_idx"),
        ]

    @property
    def usage_count(self):
        return self.feedback_items.count()

    def __str__(self):
        return self.name


class Feedback(TenantNumbered):
    """A real-time feedback row (3.20) — any employee to any employee, any time. One table serves
    kudos/appreciation/constructive feedback AND the "request feedback" pull workflow (via
    ``status`` + the ``requested_from`` self-FK, so no second table). ``is_anonymous`` masks the
    giver on read for non-admins — a direct clone of the 3.19 ``PerformanceReview.reviewer`` +
    ``is_anonymous`` precedent (the FK is kept; only the RENDER is masked)."""

    NUMBER_PREFIX = "FBK"

    FEEDBACK_TYPE_CHOICES = [
        ("kudos", "Kudos"),
        ("appreciation", "Appreciation"),
        ("constructive", "Constructive"),
        ("request", "Feedback Request"),
    ]
    VISIBILITY_CHOICES = [
        ("private", "Private"),
        ("team", "Team"),
        ("public", "Public"),
    ]
    STATUS_CHOICES = [
        ("requested", "Requested"),
        ("given", "Given"),
        ("acknowledged", "Acknowledged"),
        ("responded", "Responded"),
    ]

    giver = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.PROTECT, null=True, blank=True,
                              related_name="feedback_given",
                              help_text="Who gave the feedback (masked on read when is_anonymous).")
    receiver = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.PROTECT,
                                 related_name="feedback_received")
    feedback_type = models.CharField(max_length=15, choices=FEEDBACK_TYPE_CHOICES, default="kudos")
    visibility = models.CharField(max_length=10, choices=VISIBILITY_CHOICES, default="private",
                                  help_text="private = giver/receiver/admin; team = receiver's org unit; public = the feed.")
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="given",
                              help_text="A plain kudos is born 'given'; a pull request is born 'requested' and "
                                        "becomes 'responded' once answered.")
    message = models.TextField(blank=True)
    is_anonymous = models.BooleanField(default=False,
                                       help_text="Masks the giver on the receiver-facing view (admins still see it).")
    badge = models.ForeignKey("hrm.KudosBadge", on_delete=models.SET_NULL, null=True, blank=True,
                              related_name="feedback_items")
    related_objective = models.ForeignKey("hrm.Objective", on_delete=models.SET_NULL, null=True, blank=True,
                                          related_name="feedback_items",
                                          help_text="Optional 3.18 goal this feedback is about.")
    related_review = models.ForeignKey("hrm.PerformanceReview", on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name="feedback_items",
                                       help_text="Optional 3.19 review this feedback is about.")
    requested_from = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name="requested_responses",
                                       help_text="On a response row, points back at the 'requested' ask it answers.")
    acknowledged_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "receiver"], name="hrm_fbk_tenant_recv_idx"),
            models.Index(fields=["tenant", "giver"], name="hrm_fbk_tenant_giver_idx"),
            models.Index(fields=["tenant", "feedback_type"], name="hrm_fbk_tenant_type_idx"),
            models.Index(fields=["tenant", "visibility"], name="hrm_fbk_tenant_vis_idx"),
            models.Index(fields=["tenant", "status"], name="hrm_fbk_tenant_status_idx"),
        ]

    def clean(self):
        if self.giver_id and self.receiver_id and self.giver_id == self.receiver_id:
            raise ValidationError({"receiver": "You cannot give feedback to yourself."})

    @property
    def giver_anonymized(self):
        """True when the giver's name should be hidden from non-admin viewers. Kept as a property so
        any future per-type masking rule has one place to change (mirrors
        ``PerformanceReview.reviewer_anonymized``)."""
        return self.is_anonymous

    def __str__(self):
        who = self.receiver.party.name if self.receiver_id else "?"
        return f"{self.number} · {self.get_feedback_type_display()} → {who}"


class OneOnOneMeeting(TenantNumbered):
    """A manager↔employee 1:1 meeting shell (3.20) — scheduling + a shared agenda/notes + a
    manager-only private-notes field. ``manager_private_notes`` is a direct clone of
    ``PerformanceReview.private_notes``: never rendered on the employee-facing detail. Meeting
    history is just the ordered queryset (no extra table — mirrors how ``GoalCheckIn`` rows ARE a
    KeyResult's history)."""

    NUMBER_PREFIX = "O2O"

    STATUS_CHOICES = [
        ("scheduled", "Scheduled"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    manager = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.PROTECT,
                                related_name="oneonones_as_manager")
    employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.PROTECT,
                                 related_name="oneonones_as_employee")
    scheduled_at = models.DateTimeField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="scheduled")
    agenda = models.TextField(blank=True, help_text="Shared talking points — editable by either party pre-meeting.")
    shared_notes = models.TextField(blank=True, help_text="Visible to both the manager and the employee.")
    manager_private_notes = models.TextField(
        blank=True, help_text="Manager-only — NEVER rendered on the employee-facing view.")
    related_objective = models.ForeignKey("hrm.Objective", on_delete=models.SET_NULL, null=True, blank=True,
                                          related_name="oneonones",
                                          help_text="Optional 3.18 goal this 1:1 is anchored to.")
    completed_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["-scheduled_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "manager"], name="hrm_o2o_tenant_mgr_idx"),
            models.Index(fields=["tenant", "employee"], name="hrm_o2o_tenant_emp_idx"),
            models.Index(fields=["tenant", "status"], name="hrm_o2o_tenant_status_idx"),
            models.Index(fields=["tenant", "scheduled_at"], name="hrm_o2o_tenant_sched_idx"),
        ]

    def clean(self):
        if self.manager_id and self.employee_id and self.manager_id == self.employee_id:
            raise ValidationError({"employee": "A 1:1 needs two distinct people."})

    @property
    def open_action_item_count(self):
        return self.action_items.filter(status="open").count()

    def __str__(self):
        m = self.manager.party.name if self.manager_id else "?"
        e = self.employee.party.name if self.employee_id else "?"
        stamp = f" ({self.scheduled_at:%Y-%m-%d})" if self.scheduled_at else ""
        return f"{self.number} · {m} & {e}{stamp}"


class MeetingActionItem(TenantNumbered):
    """An action item captured in a 1:1 (3.20) — mirrors the ``KeyResult``→``Objective`` /
    ``ReviewRating``→``PerformanceReview`` child-row pattern."""

    NUMBER_PREFIX = "MAI"

    STATUS_CHOICES = [
        ("open", "Open"),
        ("done", "Done"),
    ]

    meeting = models.ForeignKey("hrm.OneOnOneMeeting", on_delete=models.CASCADE, related_name="action_items")
    description = models.TextField()
    owner = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.PROTECT, related_name="meeting_action_items")
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="open")
    completed_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["meeting", "due_date", "description"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "meeting"], name="hrm_mai_tenant_meeting_idx"),
            models.Index(fields=["tenant", "owner"], name="hrm_mai_tenant_owner_idx"),
            models.Index(fields=["tenant", "status"], name="hrm_mai_tenant_status_idx"),
        ]

    @property
    def is_overdue(self):
        """Open + past its due date (derived, mirrors the pattern used across HRM child rows)."""
        return bool(self.status == "open" and self.due_date and self.due_date < timezone.now().date())

    def __str__(self):
        return f"{self.number} · {self.description[:40]}"


# ---------------------------------------------------------------------------
# 3.21 Performance Improvement — the corrective-action / disciplinary layer and
# the FOURTH & FINAL Performance-Management sub-module (3.18 Goal Setting →
# 3.19 Performance Review → 3.20 Continuous Feedback → 3.21). Structured
# Performance Improvement Plans (with an HR-approval workflow), progressive
# disciplinary warning letters, and manager-only coaching logs — the most
# sensitive HRM records, so CONFIDENTIALITY is the design crux. Reuses the
# spine + already-built HRM models (NavERP-ERD.md): every person is an
# ``EmployeeProfile``; a PIP optionally cites the 3.19 ``PerformanceReview``
# that triggered it. Adds ONLY these 4 tables — no new core-spine entity,
# posts no GL. Confidentiality CLONES 3.19/3.20 field-for-field:
# ``_can_view_pip``/``_visible_pips_q`` mirror ``_can_view_review`` (subject/
# manager/admin, no team/public tier); ``CoachingNote`` clones the
# ``OneOnOneMeeting.manager_private_notes`` read-gate at the WHOLE-model level
# (coach/admin only — the coached employee is NEVER a viewer: the strictest
# gate in the cluster).
# ---------------------------------------------------------------------------
class PerformanceImprovementPlan(TenantNumbered):
    """A corrective-action plan (3.21) — subject + owning manager, an HR-approval workflow, structured
    issue/standards/goals/support/measurement sections, a 30/60/90-day window (extendable), and a
    close-with-outcome step. CONFIDENTIAL — visible only to the subject, the manager, or a tenant admin
    (clones the 3.19 ``PerformanceReview`` confidentiality). Optionally cites the ``PerformanceReview``
    that triggered it."""

    NUMBER_PREFIX = "PIP"

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("pending_hr_approval", "Pending HR Approval"),
        ("active", "Active"),
        ("closed", "Closed"),
    ]
    OUTCOME_CHOICES = [
        ("successful", "Successful"),
        ("extended", "Extended"),
        ("failed", "Failed"),
        ("terminated", "Terminated"),
    ]

    subject = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.PROTECT, related_name="pips_as_subject",
                                help_text="The employee on the plan.")
    manager = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.PROTECT, related_name="pips_as_manager",
                                help_text="Who owns/drives the plan (stored explicitly — may differ from the reporting line if escalated).")
    triggering_review = models.ForeignKey("hrm.PerformanceReview", on_delete=models.SET_NULL, null=True, blank=True,
                                          related_name="triggered_pips",
                                          help_text="Optional 3.19 review that prompted this plan.")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft",
                              help_text="Workflow — HR approves a draft before it goes active; changed only via the workflow actions.")
    outcome = models.CharField(max_length=15, choices=OUTCOME_CHOICES, blank=True,
                               help_text="Set only when the plan is closed (via the close action), never on the form.")
    outcome_date = models.DateField(null=True, blank=True)
    outcome_notes = models.TextField(blank=True)
    performance_issue = models.TextField(help_text="The specific performance gap (corrective, not vague criticism).")
    expected_standards = models.TextField()
    improvement_goals = models.TextField(help_text="The SMART expectations the employee must meet.")
    support_provided = models.TextField(blank=True, help_text="Training/coaching/resources the org commits to.")
    measurement_criteria = models.TextField(help_text="How success is judged.")
    start_date = models.DateField()
    end_date = models.DateField()
    extended_end_date = models.DateField(null=True, blank=True, help_text="Set by the extend action.")
    acknowledged_at = models.DateTimeField(null=True, blank=True, editable=False)
    acknowledged_by = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.SET_NULL, null=True, blank=True,
                                        related_name="pips_acknowledged", editable=False)
    hr_approved_at = models.DateTimeField(null=True, blank=True, editable=False)
    hr_approved_by = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name="pips_hr_approved", editable=False)

    class Meta:
        ordering = ["-start_date", "number"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="hrm_pip_tenant_status_idx"),
            models.Index(fields=["tenant", "subject"], name="hrm_pip_tenant_subject_idx"),
            models.Index(fields=["tenant", "manager"], name="hrm_pip_tenant_manager_idx"),
        ]

    def clean(self):
        if self.subject_id and self.manager_id and self.subject_id == self.manager_id:
            raise ValidationError({"manager": "The manager can't be the plan's subject."})
        if self.status == "closed" and not self.outcome:
            raise ValidationError({"outcome": "A closed plan must record an outcome."})
        if self.outcome and self.status != "closed":
            raise ValidationError({"outcome": "An outcome can only be set on a closed plan."})
        if self.start_date and self.end_date and self.end_date <= self.start_date:
            raise ValidationError({"end_date": "End date must be after the start date."})
        if self.extended_end_date and self.end_date and self.extended_end_date <= self.end_date:
            raise ValidationError({"extended_end_date": "The extended end date must be after the original end date."})

    @property
    def effective_end_date(self):
        """The date the plan actually runs to — the extension if set, else the original end."""
        return self.extended_end_date or self.end_date

    @property
    def checkin_count(self):
        return self.checkins.count()

    def __str__(self):
        return f"{self.number} · {self.subject.party.name}" if self.subject_id else self.number


class PIPCheckIn(TenantNumbered):
    """A scheduled review-checkpoint on a PIP (3.21) — mirrors the ``ReviewRating``→``PerformanceReview``
    / ``MeetingActionItem``→``OneOnOneMeeting`` child pattern. Inherits the parent PIP's confidentiality
    (no independent gate — the view checks ``_can_view_pip(request, checkin.pip)``)."""

    NUMBER_PREFIX = "PCI"

    RATING_CHOICES = [
        ("on_track", "On Track"),
        ("at_risk", "At Risk"),
        ("off_track", "Off Track"),
    ]

    pip = models.ForeignKey("hrm.PerformanceImprovementPlan", on_delete=models.CASCADE, related_name="checkins")
    checkin_date = models.DateField()
    completed_at = models.DateTimeField(null=True, blank=True, editable=False)
    progress_notes = models.TextField(blank=True)
    progress_rating = models.CharField(max_length=10, choices=RATING_CHOICES, default="on_track")

    class Meta:
        ordering = ["pip", "checkin_date"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "pip"], name="hrm_pci_tenant_pip_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.pip.number} ({self.checkin_date})" if self.pip_id else self.number


class WarningLetter(TenantNumbered):
    """A progressive-discipline warning letter (3.21) — verbal→written→final→suspension across
    attendance/conduct/performance/policy categories, with an issue→acknowledge workflow + an optional
    employee response. CONFIDENTIAL — visible only to the recipient, the issuer, or a tenant admin.
    Optionally linked to a PIP."""

    NUMBER_PREFIX = "WRN"

    LEVEL_CHOICES = [
        ("verbal", "Verbal Warning"),
        ("written", "Written Warning"),
        ("final", "Final Written Warning"),
        ("suspension", "Suspension"),
    ]
    CATEGORY_CHOICES = [
        ("attendance", "Attendance"),
        ("conduct", "Conduct"),
        ("performance", "Performance"),
        ("policy_violation", "Policy Violation"),
    ]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("issued", "Issued"),
        ("acknowledged", "Acknowledged"),
        ("expired", "Expired"),
    ]

    issued_to = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.PROTECT, related_name="warnings_received")
    issued_by = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.PROTECT, related_name="warnings_issued")
    level = models.CharField(max_length=15, choices=LEVEL_CHOICES, default="verbal")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="conduct")
    incident_date = models.DateField()
    description = models.TextField(help_text="Specific behaviours/actions (not vague criticism).")
    policy_reference = models.CharField(max_length=255, blank=True,
                                        help_text="Which policy/handbook section was violated.")
    related_pip = models.ForeignKey("hrm.PerformanceImprovementPlan", on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="warning_letters")
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="draft")
    acknowledged_at = models.DateTimeField(null=True, blank=True, editable=False)
    acknowledged_by = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.SET_NULL, null=True, blank=True,
                                        related_name="warnings_acknowledged", editable=False)
    employee_response = models.TextField(blank=True, help_text="The recipient's optional written response/rebuttal.")
    expiry_date = models.DateField(null=True, blank=True, help_text="When this warning goes stale (per company policy).")

    class Meta:
        ordering = ["-incident_date", "number"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "issued_to"], name="hrm_wrn_tenant_to_idx"),
            models.Index(fields=["tenant", "level"], name="hrm_wrn_tenant_level_idx"),
            models.Index(fields=["tenant", "status"], name="hrm_wrn_tenant_status_idx"),
        ]

    def clean(self):
        if self.issued_to_id and self.issued_by_id and self.issued_to_id == self.issued_by_id:
            raise ValidationError({"issued_by": "The issuer can't be the recipient."})
        if self.expiry_date and self.incident_date and self.expiry_date <= self.incident_date:
            raise ValidationError({"expiry_date": "The expiry date must be after the incident date."})

    @property
    def is_expired(self):
        """Derived (never a stored flag) — mirrors ``MeetingActionItem.is_overdue``."""
        return bool(self.expiry_date and self.expiry_date < timezone.now().date())

    @property
    def prior_warnings(self):
        """Earlier warnings to the same employee (escalation context) — a DERIVED query, not a stored
        self-FK (per the research deferral)."""
        if not (self.issued_to_id and self.incident_date):
            return WarningLetter.objects.none()
        return (WarningLetter.objects.filter(
            tenant_id=self.tenant_id, issued_to_id=self.issued_to_id, incident_date__lt=self.incident_date)
            .exclude(pk=self.pk).order_by("-incident_date"))

    def __str__(self):
        who = self.issued_to.party.name if self.issued_to_id else "?"
        return f"{self.number} · {who} ({self.get_level_display()})"


class CoachingNote(TenantNumbered):
    """A manager's private coaching log (3.21) — the "manager journal". THE STRICTEST CONFIDENTIALITY IN
    THE CLUSTER: visible ONLY to the ``coach`` (author) + a tenant admin — NEVER to the coached
    ``employee`` at any stage (a whole-model clone of ``OneOnOneMeeting.manager_private_notes``'s
    read-gate). ``content`` is deliberately NOT added to ``core.crud._SENSITIVE_AUDIT_FIELDS`` — it's
    prose (not a bank/token-style secret), audit changes are already admin-only, and the coach/admin-only
    gate protects the read surface."""

    NUMBER_PREFIX = "CN"

    CATEGORY_CHOICES = [
        ("skill_development", "Skill Development"),
        ("behavior", "Behavior"),
        ("career_growth", "Career Growth"),
        ("other", "Other"),
    ]

    employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.PROTECT, related_name="coaching_notes_about",
                                 help_text="The coached employee (who must NEVER see this note).")
    coach = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.PROTECT, related_name="coaching_notes_authored",
                              help_text="The author (manager/HRBP). Resolved server-side, not form-typed.")
    related_pip = models.ForeignKey("hrm.PerformanceImprovementPlan", on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="coaching_notes")
    note_date = models.DateField(default=timezone.localdate, help_text="When the coaching moment happened.")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="other")
    content = models.TextField()

    class Meta:
        ordering = ["-note_date", "-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "employee"], name="hrm_cn_tenant_emp_idx"),
            models.Index(fields=["tenant", "coach"], name="hrm_cn_tenant_coach_idx"),
        ]

    def clean(self):
        if self.employee_id and self.coach_id and self.employee_id == self.coach_id:
            raise ValidationError({"employee": "You can't coach yourself."})

    def __str__(self):
        c = self.coach.party.name if self.coach_id else "?"
        e = self.employee.party.name if self.employee_id else "?"
        return f"{self.number} · {c} -> {e}"


# ---------------------------------------------------------------------------
# 3.22 Training Management — Instructor-Led Training (ILT) scheduling + catalog.
# A NEW HRM domain (not a Performance-Management continuation): a course catalog
# (``TrainingCourse``) and its scheduled occurrences (``TrainingSession``), unified
# across classroom / virtual / external delivery via ``delivery_mode``. Training data
# is ORDINARY tenant-scoped CRUD — no subject/manager confidentiality gate (unlike the
# 3.18–3.21 performance cluster); every authenticated tenant user may see it, same
# openness as 3.2 Designation/JobGrade.
#
# Reuses (never duplicates): ``hrm.EmployeeProfile`` (internal instructor), ``core.Party``
# (external vendor — a ``PartyRole.role="vendor"`` party, NOT a new HRM vendor table;
# ``accounting.VendorProfile`` already extends Party on the AP side), and
# ``accounting.Currency`` (the GLOBAL currency master — string FK, lazy-imported in the
# form so accounting stays a runtime, not module-load, dependency).
#
# Deferred to sibling sub-modules (do NOT build here): 3.23 Learning Management (LMS)
# owns course content / learning paths / assessments / gamification / progress tracking;
# 3.24 Training Administration owns nomination, per-employee attendance capture, post-
# training feedback, certificate generation, and aggregate training-budget/ROI rollups
# (which will consume the estimated/actual cost captured on ``TrainingSession`` here).
# ---------------------------------------------------------------------------
class TrainingCourse(TenantNumbered):
    """A catalog course (3.22 Training Catalog) — the reusable definition an employee is scheduled
    into via a ``TrainingSession``. HRM-owned master (analogous to ``Designation``/``PayComponent``),
    not a core-spine entity. A course can grant a certification and can require a prerequisite course
    (self-FK) — the actual per-occurrence schedule/venue/instructor lives on ``TrainingSession``."""

    NUMBER_PREFIX = "TRC"

    CATEGORY_CHOICES = [
        ("technical", "Technical"),
        ("compliance", "Compliance"),
        ("leadership", "Leadership"),
        ("soft_skills", "Soft Skills"),
        ("safety", "Safety"),
        ("onboarding", "Onboarding"),
        ("product", "Product"),
        ("other", "Other"),
    ]
    # The course's TYPICAL delivery mode (a default hint); the real per-occurrence mode is on the
    # session and may differ. Wider than the session's set — a course can be marketed as "blended".
    DELIVERY_MODE_CHOICES = [
        ("classroom", "Classroom"),
        ("virtual", "Virtual"),
        ("external", "External"),
        ("blended", "Blended"),
    ]
    PROVIDER_TYPE_CHOICES = [
        ("internal", "Internal"),
        ("external", "External"),
    ]

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="technical")
    delivery_mode = models.CharField(max_length=15, choices=DELIVERY_MODE_CHOICES, default="classroom",
                                     help_text="The course's typical mode; each session sets its own actual mode.")
    provider_type = models.CharField(max_length=10, choices=PROVIDER_TYPE_CHOICES, default="internal",
                                     help_text="Run in-house (internal) or sourced from an external provider.")
    duration_hours = models.DecimalField(max_digits=6, decimal_places=2, default=ZERO,
                                         validators=[MinValueValidator(ZERO)])
    is_certification = models.BooleanField(default=False,
                                           help_text="This course grants (or represents) a certification.")
    certification_name = models.CharField(max_length=255, blank=True)
    certification_validity_months = models.PositiveIntegerField(null=True, blank=True,
                                                                help_text="How long the certification stays valid.")
    prerequisite_course = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True,
                                            related_name="unlocks",
                                            help_text="A course that must be completed first.")
    default_capacity = models.PositiveIntegerField(null=True, blank=True,
                                                   help_text="Default seat limit new sessions inherit.")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["title"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "category"], name="hrm_trc_tenant_category_idx"),
            models.Index(fields=["tenant", "is_active"], name="hrm_trc_tenant_active_idx"),
            models.Index(fields=["tenant", "delivery_mode"], name="hrm_trc_tenant_mode_idx"),
        ]

    def clean(self):
        if self.is_certification and not self.certification_name.strip():
            raise ValidationError({"certification_name": "Name the certification a certification course grants."})
        if self.prerequisite_course_id and self.pk and self.prerequisite_course_id == self.pk:
            raise ValidationError({"prerequisite_course": "A course can't be its own prerequisite."})

    def __str__(self):
        return f"{self.number} · {self.title}" if self.number else self.title


class TrainingSession(TenantNumbered):
    """A scheduled occurrence of a ``TrainingCourse`` (3.22 Training Calendar / Classroom / Virtual /
    External) — one date/time window with its own venue OR meeting link OR external vendor, an
    instructor, a capacity, and (for external sessions) cost tracking. ``delivery_mode`` unifies the
    three delivery bullets; ``clean()`` enforces the mode-specific required fields plus an
    instructor/venue double-booking overlap guard (an Absorb LMS differentiator)."""

    NUMBER_PREFIX = "TRS"

    DELIVERY_MODE_CHOICES = [
        ("classroom", "Classroom"),
        ("virtual", "Virtual"),
        ("external", "External"),
    ]
    STATUS_CHOICES = [
        ("scheduled", "Scheduled"),
        ("confirmed", "Confirmed"),
        ("ongoing", "Ongoing"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
        ("postponed", "Postponed"),
    ]
    MEETING_PLATFORM_CHOICES = [
        ("zoom", "Zoom"),
        ("teams", "Microsoft Teams"),
        ("webex", "Webex"),
        ("google_meet", "Google Meet"),
        ("gotomeeting", "GoToMeeting"),
        ("other", "Other"),
    ]
    # Statuses that free an instructor/venue slot — a cancelled/postponed session never conflicts.
    _INACTIVE_STATUSES = ("cancelled", "postponed")
    JOIN_WINDOW = timedelta(minutes=15)   # a "Join" button goes live this long before start.

    course = models.ForeignKey("hrm.TrainingCourse", on_delete=models.PROTECT, related_name="sessions",
                               help_text="The catalog course this session delivers.")
    delivery_mode = models.CharField(max_length=10, choices=DELIVERY_MODE_CHOICES, default="classroom")
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="scheduled")
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()
    timezone = models.CharField(max_length=50, default="UTC",
                                help_text="IANA/display timezone the times are quoted in.")
    capacity = models.PositiveIntegerField(default=20)
    waitlist_enabled = models.BooleanField(default=False,
                                           help_text="Allow a waitlist once full (the queue itself is 3.24 Nomination).")
    # Classroom
    venue_name = models.CharField(max_length=255, blank=True)
    venue_address = models.TextField(blank=True)
    # Virtual
    meeting_platform = models.CharField(max_length=15, choices=MEETING_PLATFORM_CHOICES, blank=True)
    meeting_link = models.URLField(blank=True)
    meeting_id = models.CharField(max_length=100, blank=True)
    # Instructor (internal employee OR a named external trainer)
    instructor_employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.SET_NULL, null=True, blank=True,
                                            related_name="training_sessions_instructed")
    external_instructor_name = models.CharField(max_length=255, blank=True)
    # External vendor — a core.Party (vendor role); no new vendor table.
    external_vendor = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True,
                                        related_name="training_sessions_as_vendor")
    # Cost tracking (external sessions) — currency is the GLOBAL accounting master (no tenant FK).
    estimated_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    actual_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.ForeignKey("accounting.Currency", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="training_sessions")
    invoice_reference = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-start_datetime", "number"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="hrm_trs_tenant_status_idx"),
            models.Index(fields=["tenant", "course"], name="hrm_trs_tenant_course_idx"),
            models.Index(fields=["tenant", "delivery_mode"], name="hrm_trs_tenant_mode_idx"),
            models.Index(fields=["tenant", "start_datetime"], name="hrm_trs_tenant_start_idx"),
            models.Index(fields=["tenant", "instructor_employee"], name="hrm_trs_tenant_instr_idx"),
        ]

    def clean(self):
        if self.start_datetime and self.end_datetime and self.end_datetime <= self.start_datetime:
            raise ValidationError({"end_datetime": "The end time must be after the start time."})
        if self.delivery_mode == "classroom" and not self.venue_name.strip():
            raise ValidationError({"venue_name": "A classroom session needs a venue."})
        if self.delivery_mode == "virtual" and not self.meeting_link.strip():
            raise ValidationError({"meeting_link": "A virtual session needs a meeting link."})
        if self.delivery_mode == "external" and not (self.external_vendor_id or self.external_instructor_name.strip()):
            raise ValidationError(
                {"external_vendor": "An external session needs a vendor or a named external instructor."})
        # Double-booking guard — only when we have a real time window and an active status.
        if self.start_datetime and self.end_datetime and self.status not in self._INACTIVE_STATUSES:
            overlapping = TrainingSession.objects.filter(
                tenant_id=self.tenant_id,
                start_datetime__lt=self.end_datetime,
                end_datetime__gt=self.start_datetime,
            ).exclude(pk=self.pk).exclude(status__in=self._INACTIVE_STATUSES)
            if self.instructor_employee_id and overlapping.filter(
                    instructor_employee_id=self.instructor_employee_id).exists():
                raise ValidationError(
                    {"instructor_employee": "This instructor is already booked for an overlapping session."})
            if self.delivery_mode == "classroom" and self.venue_name.strip() and overlapping.filter(
                    delivery_mode="classroom", venue_name__iexact=self.venue_name.strip()).exists():
                raise ValidationError({"venue_name": "This venue is already booked for an overlapping session."})

    @property
    def can_join(self):
        """Derived (never stored) — the virtual "Join" button is live from 15 min before start until
        the end time, and only when there's a link. Mirrors TalentLMS's calendar Join affordance."""
        if not self.meeting_link or not (self.start_datetime and self.end_datetime):
            return False
        now = timezone.now()
        return (self.start_datetime - self.JOIN_WINDOW) <= now <= self.end_datetime

    @property
    def is_upcoming(self):
        """Derived — a live, not-yet-started session (the calendar's default lens)."""
        return self.status not in ("completed", "cancelled") and bool(
            self.start_datetime and self.start_datetime > timezone.now())

    def __str__(self):
        if self.course_id:
            return f"{self.number} · {self.course.title} ({self.start_datetime:%Y-%m-%d %H:%M})"
        return self.number


# ---------------------------------------------------------------------------
# 3.23 Learning Management (LMS) — the self-paced digital-learning layer that
# BUILDS ON the 3.22 ``TrainingCourse`` catalog (it never re-creates a course
# table). Four models: ``LearningContentItem`` (ordered lessons + a light
# assessment variant, a CASCADE child of a course), ``LearningPath`` (LNP-, a
# role-based journey) + ``LearningPathItem`` (its ordered course refs), and
# ``LearningProgress`` (per-employee×course completion/score/points). Ordinary
# tenant-scoped CRUD — no confidentiality gate (like 3.22).
#
# Reuses: ``hrm.TrainingCourse`` (is_certification/certification_validity_months/
# prerequisite_course already modeled in 3.22), ``hrm.EmployeeProfile`` (learner),
# ``hrm.Designation`` + ``core.OrgUnit`` (kind="department") for path targeting.
# No new core-spine entity; nothing posts to the GL. Gamification leaderboards +
# level tiers are DERIVED queries over ``LearningProgress.points_earned`` — no
# stored leaderboard/badge tables.
#
# Deferred to later passes / 3.24 (do NOT build here): a real question-bank
# assessment engine (Question/Choice/Answer tables + multiple question types),
# the SCORM JS runtime / xAPI LRS (this pass stores the package file only), an LMS
# achievement-badge catalog (distinct from 3.20 ``KudosBadge``), adaptive/
# conditional paths + auto-enrollment, and 3.24 Training Administration
# (nomination, ILT attendance, feedback, certificate issuance, training budget).
# ---------------------------------------------------------------------------
class LearningContentItem(TenantOwned):
    """An ordered lesson/content piece within a ``TrainingCourse`` (3.23 Course Content) — a
    video/document/SCORM/external-link/text item, or a lightweight ``assessment`` (pass-threshold +
    attempts + time-limit, NO stored question bank this pass). A CASCADE child of the course (its
    lessons die with the course), mirroring the ``ClearanceItem``→``SeparationCase`` child pattern."""

    CONTENT_TYPE_CHOICES = [
        ("video", "Video"),
        ("document", "Document"),
        ("scorm", "SCORM Package"),
        ("external_link", "External Link"),
        ("text", "Text / Article"),
        ("assessment", "Assessment"),
    ]

    course = models.ForeignKey("hrm.TrainingCourse", on_delete=models.CASCADE, related_name="content_items")
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    content_type = models.CharField(max_length=15, choices=CONTENT_TYPE_CHOICES, default="video")
    sequence = models.PositiveIntegerField(default=0, help_text="Ordered lesson position within the course.")
    is_required = models.BooleanField(default=True, help_text="Required for course completion (vs. supplemental).")
    estimated_duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    # Content payload — only the one matching content_type is expected filled (enforced in clean()).
    video_url = models.URLField(blank=True)
    document_file = models.FileField(upload_to="hrm/lms/documents/%Y/%m/", blank=True)
    # WARNING: the SCORM package is stored as an OPAQUE file only this pass — it is never extracted.
    # A future SCORM-extraction handler MUST validate archive member paths (zip-slip / path-traversal
    # guard: reject "../" and absolute paths) before writing extracted files to disk — do not trust
    # package internals. See the deferred note in the 3.23 section header.
    scorm_package = models.FileField(upload_to="hrm/lms/scorm/%Y/%m/", blank=True)
    external_url = models.URLField(blank=True)
    body_text = models.TextField(blank=True)
    # Assessment-only (content_type="assessment"); score/pass outcomes live on LearningProgress.
    pass_threshold_percent = models.PositiveIntegerField(
        default=70, validators=[MinValueValidator(0), MaxValueValidator(100)])
    max_attempts = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    time_limit_minutes = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["course", "sequence"]
        indexes = [
            models.Index(fields=["tenant", "course"], name="hrm_lci_tenant_course_idx"),
            models.Index(fields=["tenant", "content_type"], name="hrm_lci_tenant_ctype_idx"),
        ]

    def clean(self):
        # Enforce the ONE content field matching content_type is present (never force-blanks the
        # others — an assessment may still carry body_text instructions).
        required = {
            "video": ("video_url", "a video URL"),
            "document": ("document_file", "a document file"),
            "scorm": ("scorm_package", "a SCORM package file"),
            "external_link": ("external_url", "an external URL"),
            "text": ("body_text", "the article text"),
        }.get(self.content_type)
        if required:
            field, label = required
            value = getattr(self, field, None)
            if not (str(value).strip() if value else ""):
                raise ValidationError({field: f"A {self.get_content_type_display()} lesson needs {label}."})

    def __str__(self):
        if self.course_id:
            return f"{self.course.title} · {self.sequence}. {self.title}"
        return self.title


class LearningPath(TenantNumbered):
    """A role-based learning journey (3.23 Learning Paths) — an ordered curriculum of
    ``TrainingCourse``s (via ``LearningPathItem``) optionally targeted at a ``Designation`` and/or a
    ``core.OrgUnit`` department. Reuses the 3.2 org masters — no new role/department table."""

    NUMBER_PREFIX = "LNP"

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    target_designation = models.ForeignKey("hrm.Designation", on_delete=models.SET_NULL, null=True, blank=True,
                                           related_name="learning_paths",
                                           help_text="Role this path is aimed at (optional).")
    target_department = models.ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True,
                                          related_name="learning_paths", limit_choices_to={"kind": "department"},
                                          help_text="Department this path is aimed at (optional).")
    is_mandatory = models.BooleanField(default=False, help_text="Compliance path (vs. optional development).")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["title"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="hrm_lnp_tenant_active_idx"),
            models.Index(fields=["tenant", "is_mandatory"], name="hrm_lnp_tenant_mand_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.title}" if self.number else self.title


class LearningPathItem(TenantOwned):
    """One ordered ``TrainingCourse`` step in a ``LearningPath`` (3.23 Learning Paths). A CASCADE
    child of the path; the course is PROTECT (a course referenced by a path can't be deleted out from
    under it). Prerequisite gating reuses ``TrainingCourse.prerequisite_course`` (no new rule field)."""

    path = models.ForeignKey("hrm.LearningPath", on_delete=models.CASCADE, related_name="items")
    course = models.ForeignKey("hrm.TrainingCourse", on_delete=models.PROTECT, related_name="path_items")
    sequence = models.PositiveIntegerField(default=0, help_text="Ordered completion position in the path.")
    is_mandatory = models.BooleanField(default=True)

    class Meta:
        ordering = ["path", "sequence"]
        unique_together = ("tenant", "path", "course")
        indexes = [
            models.Index(fields=["tenant", "path"], name="hrm_lpi_tenant_path_idx"),
            models.Index(fields=["tenant", "course"], name="hrm_lpi_tenant_course_idx"),
        ]

    def clean(self):
        # Light-touch prerequisite gating: if this course's prerequisite is ALSO in this path, it must
        # sit at an earlier sequence. If the prerequisite isn't in the path, it's assumed satisfied
        # elsewhere (no hard error) — reuses TrainingCourse.prerequisite_course, no new rule table.
        if self.course_id and self.path_id:
            prereq_id = getattr(self.course, "prerequisite_course_id", None)
            if prereq_id:
                earlier = (LearningPathItem.objects
                           .filter(tenant_id=self.tenant_id, path_id=self.path_id, course_id=prereq_id)
                           .exclude(pk=self.pk).first())
                if earlier is not None and earlier.sequence >= self.sequence:
                    raise ValidationError(
                        {"sequence": "This course's prerequisite must appear earlier in the path."})

    def __str__(self):
        if self.path_id and self.course_id:
            return f"{self.path.title} · {self.sequence}. {self.course.title}"
        return super().__str__()


class LearningProgress(TenantOwned):
    """Per-employee×course learning progress (3.23 Progress Tracking) — status/percent/time-spent, the
    assessment outcome (score/passed/attempts), and gamification ``points_earned``. Unique per
    (tenant, employee, course). Leaderboards + level tiers are DERIVED queries over ``points_earned``
    (no stored table). Reuses ``EmployeeProfile`` (learner) + ``TrainingCourse`` — no new tables."""

    STATUS_CHOICES = [
        ("not_started", "Not Started"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("expired", "Expired"),
    ]

    employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.CASCADE, related_name="learning_progress")
    course = models.ForeignKey("hrm.TrainingCourse", on_delete=models.PROTECT, related_name="learner_progress")
    learning_path = models.ForeignKey("hrm.LearningPath", on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name="progress_records", help_text="Enrolled via this path (optional).")
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="not_started")
    percent_complete = models.PositiveIntegerField(
        default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    time_spent_minutes = models.PositiveIntegerField(default=0)
    score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    passed = models.BooleanField(null=True, blank=True)
    attempt_count = models.PositiveIntegerField(default=0)
    points_earned = models.PositiveIntegerField(default=0, help_text="Gamification points (leaderboard is derived).")
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-updated_at"]
        unique_together = ("tenant", "employee", "course")
        indexes = [
            models.Index(fields=["tenant", "employee"], name="hrm_lprog_tenant_emp_idx"),
            models.Index(fields=["tenant", "course"], name="hrm_lprog_tenant_course_idx"),
            models.Index(fields=["tenant", "status"], name="hrm_lprog_tenant_status_idx"),
        ]

    def clean(self):
        if self.started_at and self.completed_at and self.completed_at < self.started_at:
            raise ValidationError({"completed_at": "Completion can't be before the start."})

    @property
    def certification_expires_on(self):
        """Derived (never stored) — the expiry date for a completed certification course, or None.
        Advances completed_at by the course's certification_validity_months with stdlib month-math
        (calendar.monthrange clamps the day) — no dateutil dependency."""
        if not (self.completed_at and self.course_id):
            return None
        course = self.course
        months = course.certification_validity_months
        if not (course.is_certification and months):
            return None
        d = self.completed_at.date()
        total = d.month - 1 + months
        y, m = d.year + total // 12, total % 12 + 1
        return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))

    @property
    def is_certification_expired(self):
        exp = self.certification_expires_on
        return bool(exp and exp < timezone.now().date())

    def __str__(self):
        who = self.employee if self.employee_id else "?"
        what = self.course.title if self.course_id else "?"
        return f"{who} · {what} ({self.get_status_display()})"
