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
import math
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import IntegrityError, models, transaction
from django.db.models import Q, Sum
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
