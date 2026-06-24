"""Seed HRM (Module 3) demo data — designations, employees (reusing core ``Party`` persons),
leave types/allocations/requests, public holidays, shifts/assignments, and attendance, per
tenant. Idempotent: a tenant that already has ``EmployeeProfile`` rows is skipped (use
``--flush`` to wipe and re-seed). Reuses the core spine Parties seeded by the core seeder — no
duplicate person records. Run after the core/accounts/tenants seeders.
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.core.models import Employment, OrgUnit, Party, PartyRole, Tenant
from apps.hrm.models import (
    AssetAllocation,
    AttendanceRecord,
    Designation,
    EmployeeProfile,
    LeaveAllocation,
    LeaveRequest,
    LeaveType,
    OnboardingDocument,
    OnboardingProgram,
    OnboardingTask,
    OnboardingTemplate,
    OnboardingTemplateTask,
    OrientationSession,
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

# 3.3 Employee Onboarding — reusable templates. Each task line:
# (title, task_category, assignee_role, due_offset_days, phase, is_mandatory).
ONBOARDING_TEMPLATES = [
    {
        "name": "Engineering New Hire",
        "description": "Standard onboarding checklist for engineering roles.",
        "designation_index": 0,  # tie to the first designation (Software Engineer)
        "tasks": [
            ("Send welcome email", "hr_admin", "hr", -3, "preboarding", True),
            ("Prepare workstation & accounts", "it_setup", "it", -2, "preboarding", True),
            ("Sign employment contract", "document_sign", "new_hire", 0, "week_1", True),
            ("Issue laptop & ID card", "equipment_request", "it", 0, "week_1", True),
            ("Team introduction & office tour", "meet_greet", "manager", 1, "week_1", True),
            ("Set up development environment", "it_setup", "new_hire", 2, "week_1", True),
            ("30-day check-in", "manager_action", "manager", 30, "month_1", False),
        ],
    },
    {
        "name": "General Staff Onboarding",
        "description": "Baseline onboarding for non-technical staff.",
        "designation_index": None,
        "tasks": [
            ("Collect personal documents", "hr_admin", "hr", -2, "preboarding", True),
            ("Office tour & orientation", "meet_greet", "hr", 0, "week_1", True),
            ("Sign company policies", "document_sign", "new_hire", 1, "week_1", True),
            ("Benefits enrollment", "hr_admin", "hr", 3, "week_1", True),
            ("Manager 1:1 meeting", "manager_action", "manager", 14, "month_1", False),
        ],
    },
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
            self._seed_onboarding(tenant, flush=options["flush"])
        self.stdout.write(self.style.WARNING(
            "NOTE: Superuser 'admin' has no tenant — HRM data won't appear when logged in as admin. "
            "Log in as admin_acme / admin_globex (password)."))

    @transaction.atomic
    def _seed_tenant(self, tenant, *, flush):
        if flush:
            # Children first (onboarding rows FK EmployeeProfile/Designation), then the masters.
            for model in (OnboardingTask, OnboardingDocument, OrientationSession, AssetAllocation,
                          OnboardingProgram, OnboardingTemplateTask, OnboardingTemplate,
                          AttendanceRecord, ShiftAssignment, Shift, LeaveRequest, LeaveAllocation,
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
            # Unique suffix so a tenant with zero existing persons never gets duplicate names.
            persons.append(Party.objects.create(
                tenant=tenant, kind="person", name=f"{PERSON_NAMES[i % len(PERSON_NAMES)]} {i + 1}"))
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

    @transaction.atomic
    def _seed_onboarding(self, tenant, *, flush):
        """Seed 3.3 Employee Onboarding demo data. Guarded independently of the main HRM guard so a
        tenant whose employees already exist (skipped by ``_seed_tenant``) still gets onboarding."""
        if OnboardingTemplate.objects.filter(tenant=tenant).exists():
            self.stdout.write(self.style.NOTICE(
                f"Onboarding data already exists for '{tenant.name}'. Use --flush to re-seed."))
            return
        employees = list(EmployeeProfile.objects.filter(tenant=tenant)
                         .select_related("party").order_by("number"))
        if not employees:
            self.stdout.write(self.style.WARNING(
                f"No employees for '{tenant.name}' — skipping onboarding (run the HRM seed first)."))
            return
        designations = list(Designation.objects.filter(tenant=tenant).order_by("name"))
        actor = get_user_model().objects.filter(tenant=tenant).order_by("id").first()
        today = timezone.localdate()

        def _mk_dt(d, hour):
            dt = datetime.datetime.combine(d, datetime.time(hour, 0))
            return timezone.make_aware(dt) if timezone.is_naive(dt) else dt

        # --- Templates + their task lines ---
        templates_by_name = {}
        for spec in ONBOARDING_TEMPLATES:
            desig = None
            if spec["designation_index"] is not None and designations:
                desig = designations[spec["designation_index"] % len(designations)]
            tmpl, _ = OnboardingTemplate.objects.get_or_create(
                tenant=tenant, name=spec["name"],
                defaults={"description": spec["description"], "designation": desig})
            templates_by_name[spec["name"]] = tmpl
            for order, (title, cat, role, offset, phase, mand) in enumerate(spec["tasks"]):
                OnboardingTemplateTask.objects.get_or_create(
                    tenant=tenant, template=tmpl, title=title,
                    defaults={"task_category": cat, "assignee_role": role, "due_offset_days": offset,
                              "phase": phase, "order": order, "is_mandatory": mand})

        # Canonical due-date logic (program.start_date + offset), reused so the seed matches the app.
        from apps.hrm.views import _generate_tasks_from_template

        # --- Program A: active, future start, with a buddy ---
        emp_a = employees[0]
        first_a = emp_a.party.name.split()[0] if emp_a.party_id else "there"
        prog_a = OnboardingProgram.objects.create(
            tenant=tenant, employee=emp_a, template=templates_by_name["Engineering New Hire"],
            start_date=today + datetime.timedelta(days=7), status="active",
            buddy=employees[1] if len(employees) > 1 else None,
            welcome_message=f"Welcome aboard, {first_a}! The whole team is excited to have you.",
            welcome_video_url="https://example.com/welcome",
            first_day_notes="Arrive at 9:30 AM and ask for HR at the front desk. Bring a photo ID.")
        _generate_tasks_from_template(prog_a)

        # --- Program B: completed, past start, a few tasks ticked off ---
        prog_b = None
        if len(employees) > 1:
            emp_b = employees[1]
            first_b = emp_b.party.name.split()[0] if emp_b.party_id else "there"
            prog_b = OnboardingProgram.objects.create(
                tenant=tenant, employee=emp_b, template=templates_by_name["General Staff Onboarding"],
                start_date=today - datetime.timedelta(days=30), status="completed",
                completed_at=timezone.now(),
                welcome_message=f"Welcome, {first_b}!",
                first_day_notes="Orientation in Room 2 at 10 AM.")
            _generate_tasks_from_template(prog_b)
            for t in list(prog_b.tasks.order_by("phase", "order"))[:3]:
                t.status = "completed"
                t.completed_at = timezone.now()
                t.completed_by = actor
                t.save(update_fields=["status", "completed_at", "completed_by", "updated_at"])

        programs = [p for p in (prog_a, prog_b) if p is not None]

        # --- Documents per program ---
        for program in programs:
            OnboardingDocument.objects.get_or_create(
                tenant=tenant, program=program, title="Employment Contract",
                defaults={"document_type": "employment_contract", "esign_required": True,
                          "esign_status": "signed", "signed_at": timezone.now(),
                          "external_ref": "DEMO-ENV-0001"})
            OnboardingDocument.objects.get_or_create(
                tenant=tenant, program=program, title="Government ID Proof",
                defaults={"document_type": "id_proof", "esign_required": False,
                          "esign_status": "pending", "due_date": program.start_date})
            OnboardingDocument.objects.get_or_create(
                tenant=tenant, program=program, title="Employee Handbook Acknowledgment",
                defaults={"document_type": "policy_acknowledgment", "esign_required": False,
                          "esign_status": "not_required"})

        # --- Assets per program's employee ---
        for program in programs:
            for name, cat, status, serial in [
                ('MacBook Pro 14"', "laptop", "issued", "C02-DEMO-001"),
                ("Employee ID Card", "id_card", "issued", ""),
                ("Building Access Card", "access_card", "pending", ""),
            ]:
                obj, created = AssetAllocation.objects.get_or_create(
                    tenant=tenant, employee=program.employee, program=program, asset_name=name,
                    defaults={"asset_category": cat, "status": status, "serial_number": serial})
                if created and status == "issued":
                    obj.issued_at = timezone.now()
                    obj.issued_by = actor
                    obj.save(update_fields=["issued_at", "issued_by", "updated_at"])

        # --- Orientation sessions for the active program ---
        OrientationSession.objects.get_or_create(
            tenant=tenant, program=prog_a, employee=prog_a.employee, title="HR Orientation",
            defaults={"session_type": "orientation", "facilitator": actor,
                      "scheduled_at": _mk_dt(prog_a.start_date, 10), "duration_minutes": 60,
                      "location": "Room A1", "attendance_status": "scheduled"})
        OrientationSession.objects.get_or_create(
            tenant=tenant, program=prog_a, employee=prog_a.employee, title="IT Setup Walk-through",
            defaults={"session_type": "system_demo", "facilitator": actor,
                      "scheduled_at": _mk_dt(prog_a.start_date + datetime.timedelta(days=1), 14),
                      "duration_minutes": 45, "meeting_url": "https://example.com/it-setup",
                      "attendance_status": "scheduled"})

        self.stdout.write(self.style.SUCCESS(
            f"Onboarding seeded for '{tenant.name}': "
            f"{OnboardingTemplate.objects.filter(tenant=tenant).count()} templates, "
            f"{len(programs)} programs, "
            f"{OnboardingTask.objects.filter(tenant=tenant).count()} tasks, "
            f"{OnboardingDocument.objects.filter(tenant=tenant).count()} docs, "
            f"{AssetAllocation.objects.filter(tenant=tenant).count()} assets, "
            f"{OrientationSession.objects.filter(tenant=tenant).count()} sessions."))

    @staticmethod
    def _last_workdays(end, count):
        """Return the most recent ``count`` weekdays up to and including ``end``."""
        days, cur = [], end
        while len(days) < count:
            if cur.weekday() < 5:  # Mon–Fri
                days.append(cur)
            cur -= datetime.timedelta(days=1)
        return days
