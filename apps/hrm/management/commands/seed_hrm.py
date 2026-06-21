"""Seed HRM (Module 3) demo data — designations, employees (reusing core ``Party`` persons),
leave types/allocations/requests, public holidays, shifts/assignments, and attendance, per
tenant. Idempotent: a tenant that already has ``EmployeeProfile`` rows is skipped (use
``--flush`` to wipe and re-seed). Reuses the core spine Parties seeded by the core seeder — no
duplicate person records. Run after the core/accounts/tenants seeders.
"""
import datetime
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.core.models import Employment, OrgUnit, Party, PartyRole, Tenant
from apps.hrm.models import (
    AttendanceRecord,
    Designation,
    EmployeeProfile,
    LeaveAllocation,
    LeaveRequest,
    LeaveType,
    PublicHoliday,
    Shift,
    ShiftAssignment,
)

# Fallback person names if a tenant has too few persons to staff the demo.
PERSON_NAMES = ["Aisha Khan", "Daniel Reed", "Sofia Marquez", "Liam O'Brien", "Hana Suzuki"]

DESIGNATIONS = [
    ("Software Engineer", "L2", Decimal("60000"), Decimal("90000")),
    ("Senior Engineer", "L3", Decimal("90000"), Decimal("130000")),
    ("Engineering Manager", "M1", Decimal("130000"), Decimal("180000")),
]
EMPLOYEE_TYPES = ["full_time", "full_time", "part_time", "contract", "full_time"]
GENDERS = ["female", "male", "female", "male", "female"]

LEAVE_TYPES = [
    # name, code, is_paid, accrual_rule, accrual_days, max_balance, max_carry_forward, encashable
    ("Annual Leave", "AL", True, "annual", Decimal("21"), Decimal("30"), Decimal("5"), True),
    ("Sick Leave", "SL", True, "monthly", Decimal("1.5"), Decimal("18"), Decimal("0"), False),
    ("Casual Leave", "CL", True, "annual", Decimal("12"), Decimal("12"), Decimal("0"), False),
    ("Unpaid Leave", "UPL", False, "none", Decimal("0"), Decimal("0"), Decimal("0"), False),
]
# month, day, name, is_optional
HOLIDAYS = [
    (1, 1, "New Year's Day", False),
    (5, 1, "Labour Day", False),
    (7, 4, "Founders' Day", False),
    (12, 24, "Festival Eve", True),
    (12, 25, "Festival Day", False),
]
SHIFTS = [
    # name, start, end, grace, is_default
    ("Morning Shift", datetime.time(9, 0), datetime.time(18, 0), 15, True),
    ("Night Shift", datetime.time(21, 0), datetime.time(6, 0), 30, False),
]


class Command(BaseCommand):
    help = "Seed HRM demo data (designations, employees, leave, attendance, shifts) — idempotent."

    def add_arguments(self, parser):
        parser.add_argument("--flush", action="store_true",
                            help="Delete existing HRM data for each tenant, then re-seed.")

    def handle(self, *args, **options):
        tenants = list(Tenant.objects.all())
        if not tenants:
            self.stdout.write(self.style.WARNING("No tenants found — run the core seeder first."))
            return
        for tenant in tenants:
            self._seed_tenant(tenant, flush=options["flush"])
        self.stdout.write(self.style.WARNING(
            "NOTE: Superuser 'admin' has no tenant — HRM data won't appear when logged in as admin. "
            "Log in as admin_acme / admin_globex (password123)."))

    @transaction.atomic
    def _seed_tenant(self, tenant, *, flush):
        if flush:
            for model in (AttendanceRecord, ShiftAssignment, Shift, LeaveRequest, LeaveAllocation,
                          LeaveType, PublicHoliday, EmployeeProfile, Designation):
                model.objects.filter(tenant=tenant).delete()

        if EmployeeProfile.objects.filter(tenant=tenant).exists():
            self.stdout.write(self.style.NOTICE(
                f"HRM data already exists for '{tenant.name}'. Use --flush to re-seed."))
            return

        today = timezone.localdate()
        year = today.year
        dept = (OrgUnit.objects.filter(tenant=tenant, kind="department").first()
                or OrgUnit.objects.filter(tenant=tenant).first())

        # --- Designations (reuse core OrgUnit as department) ---
        designations = []
        for name, grade, lo, hi in DESIGNATIONS:
            d, _ = Designation.objects.get_or_create(
                tenant=tenant, name=name,
                defaults={"grade": grade, "department": dept, "min_salary": lo, "max_salary": hi})
            designations.append(d)

        # --- Employees: reuse existing person Parties, top up if too few ---
        persons = list(Party.objects.filter(tenant=tenant, kind="person").order_by("id"))
        i = 0
        while len(persons) < 4:
            persons.append(Party.objects.create(
                tenant=tenant, kind="person", name=PERSON_NAMES[i % len(PERSON_NAMES)]))
            i += 1
        persons = persons[:5]

        employees = []
        for idx, party in enumerate(persons):
            PartyRole.objects.get_or_create(
                tenant=tenant, party=party, role="employee",
                defaults={"status": "active", "start_date": today})
            employment, _ = Employment.objects.get_or_create(
                tenant=tenant, party=party,
                defaults={"org_unit": dept, "job_title": designations[idx % len(designations)].name,
                          "hired_on": today - datetime.timedelta(days=365 + idx * 40),
                          "status": "active"})
            emp, _ = EmployeeProfile.objects.get_or_create(
                tenant=tenant, party=party,
                defaults={
                    "employment": employment,
                    "designation": designations[idx % len(designations)],
                    "employee_type": EMPLOYEE_TYPES[idx % len(EMPLOYEE_TYPES)],
                    "gender": GENDERS[idx % len(GENDERS)],
                    "date_of_birth": datetime.date(1990, 1, 1) + datetime.timedelta(days=idx * 220),
                    "nationality": "—",
                    "personal_email": f"{party.name.split()[0].lower()}.{idx}@example.com",
                    "mobile": f"+1-555-01{idx:02d}",
                    "bank_name": "Demo Bank",
                    "bank_account": f"000123456{idx:03d}",
                    "bank_routing": "DEMO0001",
                    "probation_end_date": today + datetime.timedelta(days=30),
                    "emergency_contact_name": "Emergency Contact",
                    "emergency_contact_phone": "+1-555-9999",
                    "emergency_contact_relation": "Spouse",
                })
            employees.append(emp)

        # --- Leave types + per-employee allocations ---
        leave_types = []
        for name, code, paid, rule, accr, mx, cf, enc in LEAVE_TYPES:
            lt, _ = LeaveType.objects.get_or_create(
                tenant=tenant, code=code,
                defaults={"name": name, "is_paid": paid, "accrual_rule": rule, "accrual_days": accr,
                          "max_balance": mx, "max_carry_forward": cf, "encashable": enc})
            leave_types.append(lt)
        for emp in employees:
            for lt in leave_types:
                LeaveAllocation.objects.get_or_create(
                    tenant=tenant, employee=emp, leave_type=lt, year=year,
                    defaults={"allocated_days": lt.accrual_days or Decimal("0"), "status": "active"})

        # --- Leave requests: one approved (past), one pending (upcoming) ---
        if employees:
            LeaveRequest.objects.create(
                tenant=tenant, employee=employees[0], leave_type=leave_types[0],
                start_date=today - datetime.timedelta(days=20),
                end_date=today - datetime.timedelta(days=18),
                reason="Family event.", status="approved", approved_at=timezone.now())
            LeaveRequest.objects.create(
                tenant=tenant, employee=employees[min(1, len(employees) - 1)], leave_type=leave_types[1],
                start_date=today + datetime.timedelta(days=7),
                end_date=today + datetime.timedelta(days=8),
                reason="Medical appointment.", status="pending")

        # --- Public holidays ---
        for month, day, name, optional in HOLIDAYS:
            PublicHoliday.objects.get_or_create(
                tenant=tenant, date=datetime.date(year, month, day), name=name,
                defaults={"is_optional": optional})

        # --- Shifts + assignments ---
        shifts = []
        for name, start, end, grace, default in SHIFTS:
            s, _ = Shift.objects.get_or_create(
                tenant=tenant, name=name,
                defaults={"start_time": start, "end_time": end, "grace_minutes": grace,
                          "is_default": default})
            shifts.append(s)
        morning = shifts[0]
        for emp in employees:
            ShiftAssignment.objects.get_or_create(
                tenant=tenant, employee=emp, effective_from=datetime.date(year, 1, 1),
                defaults={"shift": morning})

        # --- Attendance: last 5 working days per employee ---
        workdays = self._last_workdays(today, 5)
        att_statuses = ["present", "present", "present", "absent", "on_leave"]
        for emp in employees:
            for n, day in enumerate(workdays):
                status = att_statuses[n % len(att_statuses)]
                ci = co = None
                if status in ("present", "regularized", "half_day"):
                    ci, co = datetime.time(9, 5), datetime.time(18, 0)
                AttendanceRecord.objects.get_or_create(
                    tenant=tenant, employee=emp, date=day,
                    defaults={"check_in": ci, "check_out": co, "shift": morning,
                              "status": status, "source": "manual"})

        self.stdout.write(self.style.SUCCESS(
            f"HRM seeded for '{tenant.name}': {len(employees)} employees, "
            f"{LeaveAllocation.objects.filter(tenant=tenant).count()} allocations, "
            f"{AttendanceRecord.objects.filter(tenant=tenant).count()} attendance rows."))

    @staticmethod
    def _last_workdays(end, count):
        """Return the most recent ``count`` weekdays up to and including ``end``."""
        days, cur = [], end
        while len(days) < count:
            if cur.weekday() < 5:  # Mon–Fri
                days.append(cur)
            cur -= datetime.timedelta(days=1)
        return days
