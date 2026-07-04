"""Seed HRM (Module 3) demo data — designations, employees (reusing core ``Party`` persons),
leave types/allocations/requests, public holidays, shifts/assignments, and attendance, per
tenant. Idempotent: a tenant that already has ``EmployeeProfile`` rows is skipped (use
``--flush`` to wipe and re-seed). Reuses the core spine Parties seeded by the core seeder — no
duplicate person records. Run after the core/accounts/tenants seeders.
"""
import datetime
import secrets
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.core.models import Employment, OrgUnit, Party, PartyRole, Tenant
from apps.hrm.models import (
    AssetAllocation,
    AttendanceRecord,
    AttendanceRegularization,
    ClearanceItem,
    CostCenterProfile,
    DepartmentProfile,
    Designation,
    EmployeeDocument,
    EmployeeLifecycleEvent,
    EmployeeProfile,
    ExitInterview,
    FinalSettlement,
    GeoFence,
    JobDescriptionTemplate,
    JobGrade,
    JobRequisition,
    LeaveAllocation,
    LeaveEncashment,
    LeaveRequest,
    LeaveType,
    OnboardingDocument,
    OnboardingProgram,
    OnboardingTask,
    OnboardingTemplate,
    OnboardingTemplateTask,
    OrientationSession,
    OvertimeRequest,
    PublicHoliday,
    HolidayPolicy,
    FloatingHolidayElection,
    RequisitionApproval,
    Timesheet,
    TimesheetEntry,
    SeparationCase,
    Shift,
    ShiftAssignment,
)
from apps.hrm.models import (  # 3.6 Candidate Management
    CandidateCommunication,
    CandidateEmailTemplate,
    CandidateProfile,
    CandidateSkill,
    CandidateTag,
    JobApplication,
)
from apps.hrm.models import (  # 3.7 Interview Process
    FeedbackCriterion,
    Interview,
    InterviewFeedback,
    InterviewPanelist,
)
from apps.hrm.models import (  # 3.8 Offer Management
    BackgroundVerification,
    Offer,
    OfferApproval,
    OfferLetterTemplate,
    PreboardingItem,
)
from apps.hrm.models import (  # 3.13 Salary Structure
    EmployeeSalaryStructure,
    PayComponent,
    SalaryStructureLine,
    SalaryStructureTemplate,
)
from apps.hrm.models import (  # 3.14 Payroll Processing
    Payslip,
    PayslipLine,
    PayrollCycle,
)

# Fallback person names if a tenant has too few persons to staff the demo.
PERSON_NAMES = ["Aisha Khan", "Daniel Reed", "Sofia Marquez", "Liam O'Brien", "Hana Suzuki"]

DESIGNATIONS = [
    ("Software Engineer", "L2", Decimal("60000"), Decimal("90000")),
    ("Senior Engineer", "L3", Decimal("90000"), Decimal("130000")),
    ("Engineering Manager", "M1", Decimal("130000"), Decimal("180000")),
]

# 3.2 Organizational Structure — orderable grade catalog. (name, level_order, description)
JOB_GRADES = [
    ("G1 — Junior", 1, "Entry-level individual contributor."),
    ("G2 — Mid", 2, "Developing individual contributor."),
    ("G3 — Senior", 3, "Senior individual contributor."),
    ("M1 — Manager", 4, "First-level people manager."),
    ("M2 — Director", 5, "Department or function director."),
]
# Designation name -> (job-grade index, mid_salary, budgeted_headcount).
DESIGNATION_GRADE_MAP = {
    "Software Engineer": (1, Decimal("75000"), 3),
    "Senior Engineer": (2, Decimal("110000"), 2),
    "Engineering Manager": (3, Decimal("155000"), 1),
}
# Cost-center OrgUnit nodes HRM seeds (none exist in core). (name, code, annual budget)
COST_CENTERS = [
    ("Engineering Cost Center", "ENGC", Decimal("1200000")),
    ("Operations Cost Center", "OPSC", Decimal("750000")),
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
# month, day, name, is_optional, category
HOLIDAYS = [
    (1, 1, "New Year's Day", False, "national"),
    (5, 1, "Labour Day", False, "national"),
    (7, 4, "Founders' Day", False, "company"),
    (10, 2, "Cultural Observance Day", True, "observance"),
    (12, 24, "Festival Eve", True, "observance"),
    (12, 25, "Festival Day", False, "national"),
]
SHIFTS = [
    # name, start, end, grace, is_default
    ("Morning Shift", datetime.time(9, 0), datetime.time(18, 0), 15, True),
    ("Night Shift", datetime.time(21, 0), datetime.time(6, 0), 30, False),
]
# 3.9 Geofencing — GPS zones for field/site attendance. (name, address, lat, lng, radius_m)
GEOFENCES = [
    ("Head Office", "1 Corporate Plaza", Decimal("40.712776"), Decimal("-74.005974"), 150),
    ("Client Site — North", "88 Industrial Ave", Decimal("40.730610"), Decimal("-73.935242"), 200),
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
            self._seed_org_structure(tenant, flush=options["flush"])
            self._seed_onboarding(tenant, flush=options["flush"])
            self._seed_offboarding(tenant, flush=options["flush"])
            self._seed_employee_records(tenant, flush=options["flush"])
            self._seed_job_requisition(tenant, flush=options["flush"])
            self._seed_candidates(tenant, flush=options["flush"])
            self._seed_interviews(tenant, flush=options["flush"])
            self._seed_offers(tenant, flush=options["flush"])
            self._seed_timetracking(tenant, flush=options["flush"])
            self._seed_salary(tenant, flush=options["flush"])
            self._seed_payroll(tenant, flush=options["flush"])
        self.stdout.write(self.style.WARNING(
            "NOTE: Superuser 'admin' has no tenant — HRM data won't appear when logged in as admin. "
            "Log in as admin_acme / admin_globex (password)."))

    @transaction.atomic
    def _seed_tenant(self, tenant, *, flush):
        if flush:
            # Children first (onboarding/offboarding rows FK EmployeeProfile/Designation), then masters.
            # 3.12: elections FK holiday/policy/employee; policies FK/M2M holiday/designation — wipe first.
            # 3.14: Payslip.employee is PROTECT, so payslips must be wiped before EmployeeProfile below.
            for model in (PayslipLine, Payslip, PayrollCycle,
                          FloatingHolidayElection, HolidayPolicy,
                          FinalSettlement, ExitInterview, ClearanceItem, SeparationCase,
                          OnboardingTask, OnboardingDocument, OrientationSession, AssetAllocation,
                          OnboardingProgram, OnboardingTemplateTask, OnboardingTemplate,
                          CostCenterProfile, DepartmentProfile,
                          AttendanceRegularization, AttendanceRecord, GeoFence,
                          ShiftAssignment, Shift, LeaveEncashment, LeaveRequest, LeaveAllocation,
                          LeaveType, PublicHoliday, EmployeeProfile, Designation, JobGrade):
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

        # --- Leave encashment (3.10): requests to encash unused, encashable (Annual) leave ---
        encashable_type = next((lt for lt in leave_types if lt.encashable), None)
        if employees and encashable_type:
            for idx, emp in enumerate(employees[:2]):
                if LeaveEncashment.objects.filter(
                        tenant=tenant, employee=emp, leave_type=encashable_type, year=year).exists():
                    continue
                rate = Decimal("120.00")
                if emp.designation_id and emp.designation and emp.designation.min_salary:
                    rate = (emp.designation.min_salary / Decimal("30")).quantize(Decimal("0.01"))
                LeaveEncashment.objects.create(
                    tenant=tenant, employee=emp, leave_type=encashable_type, year=year,
                    days=Decimal("3"), rate_per_day=rate,
                    status="pending" if idx == 0 else "draft")

        # --- Public holidays (3.12) ---
        optional_holidays = []
        for month, day, name, optional, category in HOLIDAYS:
            h, _ = PublicHoliday.objects.get_or_create(
                tenant=tenant, date=datetime.date(year, month, day), name=name,
                defaults={"is_optional": optional, "category": category})
            if h.is_optional:
                optional_holidays.append(h)

        # --- Holiday policies (3.12): a company-wide default + a full-time-staff scoped policy ---
        default_policy, _ = HolidayPolicy.objects.get_or_create(
            tenant=tenant, name="Company Default",
            defaults={"is_default": True, "floating_holiday_quota": 2, "is_active": True,
                      "description": "Applies to all employees when no more specific policy matches."})
        # Scoped by employee_type only (not org_unit) so it governs every full-time employee in the
        # demo — the seeded staff span several departments, so a single-org_unit scope would match
        # only some of them and obscure the policy-resolution demo.
        scoped_policy, _ = HolidayPolicy.objects.get_or_create(
            tenant=tenant, name="Full-Time Staff Policy",
            defaults={"employee_type": "full_time", "floating_holiday_quota": 1, "is_active": True,
                      "description": "Full-time employees — one floating holiday per year."})
        if optional_holidays:
            default_policy.holidays.set(optional_holidays)
            scoped_policy.holidays.set(optional_holidays[:1])

        # --- Floating holiday elections (3.12): employees elect an optional holiday (quota-capped) ---
        actor = get_user_model().objects.filter(tenant=tenant).order_by("id").first()
        if employees and optional_holidays:
            chosen = optional_holidays[0]
            for idx, emp in enumerate(employees[:2]):
                election, created = FloatingHolidayElection.objects.get_or_create(
                    tenant=tenant, employee=emp, holiday=chosen,
                    defaults={"status": "approved" if idx == 0 else "pending",
                              "note": "Elected via the demo seeder."})
                if created and idx == 0 and actor is not None:
                    election.approved_by = actor
                    election.approved_at = timezone.now()
                    election.save(update_fields=["approved_by", "approved_at", "updated_at"])

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

        # --- Geofences (3.9): GPS zones for field attendance ---
        geofences = []
        for name, address, lat, lng, radius in GEOFENCES:
            g, _ = GeoFence.objects.get_or_create(
                tenant=tenant, name=name,
                defaults={"address": address, "latitude": lat, "longitude": lng, "radius_m": radius})
            geofences.append(g)
        hq = geofences[0]

        # --- Attendance: last 5 working days per employee (present punches tagged to the HQ geofence) ---
        workdays = self._last_workdays(today, 5)
        att_statuses = ["present", "present", "present", "absent", "on_leave"]
        for emp in employees:
            for n, day in enumerate(workdays):
                status = att_statuses[n % len(att_statuses)]
                ci = co = None
                lat = lng = geofence = None
                if status in ("present", "regularized", "half_day"):
                    ci, co = datetime.time(9, 5), datetime.time(18, 0)
                    geofence = hq
                    # First present day sits outside the fence (demo), the rest at its centre (verified).
                    if n == 0:
                        lat, lng = Decimal("40.732776"), Decimal("-74.005974")  # ~2 km north → outside
                    else:
                        lat, lng = hq.latitude, hq.longitude
                AttendanceRecord.objects.get_or_create(
                    tenant=tenant, employee=emp, date=day,
                    defaults={"check_in": ci, "check_out": co, "shift": morning,
                              "status": status, "source": "manual",
                              "latitude": lat, "longitude": lng, "geofence": geofence})

        # --- Attendance regularization (3.9): a request to fix a missed/absent punch ---
        for idx, emp in enumerate(employees[:2]):
            absent_rec = (AttendanceRecord.objects
                          .filter(tenant=tenant, employee=emp, status="absent")
                          .order_by("date").first())
            if absent_rec and not AttendanceRegularization.objects.filter(
                    tenant=tenant, employee=emp, date=absent_rec.date).exists():
                AttendanceRegularization.objects.create(
                    tenant=tenant, employee=emp, attendance_record=absent_rec, date=absent_rec.date,
                    reason_type="missed_punch",
                    requested_check_in=datetime.time(9, 0), requested_check_out=datetime.time(18, 0),
                    reason="Was present but the biometric device failed to log the punch.",
                    status="pending" if idx == 0 else "draft")

        self.stdout.write(self.style.SUCCESS(
            f"HRM seeded for '{tenant.name}': {len(employees)} employees, "
            f"{LeaveAllocation.objects.filter(tenant=tenant).count()} allocations, "
            f"{AttendanceRecord.objects.filter(tenant=tenant).count()} attendance rows, "
            f"{GeoFence.objects.filter(tenant=tenant).count()} geofences, "
            f"{AttendanceRegularization.objects.filter(tenant=tenant).count()} regularizations, "
            f"{LeaveEncashment.objects.filter(tenant=tenant).count()} encashments."))

    @transaction.atomic
    def _seed_org_structure(self, tenant, *, flush):
        """Seed 3.2 Organizational Structure demo data — job grades, department profiles, and cost
        centers (with their OrgUnit nodes, since core seeds none). Guarded independently of the main
        HRM guard so a tenant whose employees already exist still gets the org-structure rows."""
        if JobGrade.objects.filter(tenant=tenant).exists():
            self.stdout.write(self.style.NOTICE(
                f"Org-structure data already exists for '{tenant.name}'. Use --flush to re-seed."))
            return
        today = timezone.localdate()
        employees = list(EmployeeProfile.objects.filter(tenant=tenant)
                         .select_related("party").order_by("number"))

        # --- Job grades (orderable catalog) ---
        grades = []
        for name, order, desc in JOB_GRADES:
            g, _ = JobGrade.objects.get_or_create(
                tenant=tenant, name=name,
                defaults={"level_order": order, "description": desc})
            grades.append(g)

        # --- Link designations -> grades + fill mid-salary / budgeted headcount (only if unset) ---
        for desig in Designation.objects.filter(tenant=tenant):
            mapping = DESIGNATION_GRADE_MAP.get(desig.name)
            if not mapping:
                continue
            grade_idx, mid, headcount = mapping
            changed = []
            if desig.job_grade_id is None and grade_idx < len(grades):
                desig.job_grade = grades[grade_idx]
                changed.append("job_grade")
            if desig.mid_salary is None:
                desig.mid_salary = mid
                changed.append("mid_salary")
            if desig.budgeted_headcount is None:
                desig.budgeted_headcount = headcount
                changed.append("budgeted_headcount")
            if changed:
                desig.save(update_fields=changed + ["updated_at"])

        # --- Cost-center OrgUnit nodes (none exist in core) + their HRM profiles ---
        company = OrgUnit.objects.filter(tenant=tenant, kind="company").first()
        cost_centers = []
        for idx, (name, code, budget) in enumerate(COST_CENTERS):
            unit, _ = OrgUnit.objects.get_or_create(
                tenant=tenant, kind="cost_center", name=name, defaults={"parent": company})
            CostCenterProfile.objects.get_or_create(
                tenant=tenant, org_unit=unit,
                defaults={"code": code, "budget_annual": budget, "budget_year": today.year,
                          "owner": employees[idx % len(employees)] if employees else None,
                          "description": f"{name} — personnel budget pool."})
            cost_centers.append(unit)

        # --- Department profiles over the existing department OrgUnits ---
        dept_units = list(OrgUnit.objects.filter(tenant=tenant, kind="department").order_by("name"))
        for idx, unit in enumerate(dept_units):
            DepartmentProfile.objects.get_or_create(
                tenant=tenant, org_unit=unit,
                defaults={"code": unit.name[:3].upper(),
                          "head": employees[idx % len(employees)] if employees else None,
                          "cost_center": cost_centers[idx % len(cost_centers)] if cost_centers else None,
                          "description": f"{unit.name} department."})

        self.stdout.write(self.style.SUCCESS(
            f"Org-structure seeded for '{tenant.name}': "
            f"{JobGrade.objects.filter(tenant=tenant).count()} grades, "
            f"{DepartmentProfile.objects.filter(tenant=tenant).count()} department profiles, "
            f"{CostCenterProfile.objects.filter(tenant=tenant).count()} cost centers."))

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
        from apps.hrm.services import generate_tasks_from_template

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
        generate_tasks_from_template(prog_a)

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
            generate_tasks_from_template(prog_b)
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
                defaults={"document_type": "id_proof", "esign_required": True,
                          "due_date": program.start_date})  # esign_status derived → "pending"
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

    @transaction.atomic
    def _seed_offboarding(self, tenant, *, flush):
        """Seed 3.4 Employee Offboarding demo data. Guarded independently of the main HRM guard so a
        tenant whose employees already exist still gets offboarding. On --flush the rows are wiped by
        ``_seed_tenant`` (they're in its delete list), so this only needs the existence guard."""
        from apps.hrm.services import generate_clearance_checklist

        if SeparationCase.objects.filter(tenant=tenant).exists():
            self.stdout.write(self.style.NOTICE(
                f"Offboarding data already exists for '{tenant.name}'. Use --flush to re-seed."))
            return
        employees = list(EmployeeProfile.objects.filter(tenant=tenant)
                         .select_related("party", "designation", "employment").order_by("number"))
        if not employees:
            self.stdout.write(self.style.WARNING(
                f"No employees for '{tenant.name}' — skipping offboarding (run the HRM seed first)."))
            return
        actor = get_user_model().objects.filter(tenant=tenant).order_by("id").first()
        today = timezone.localdate()
        now = timezone.now()

        # --- Case 1: completed voluntary resignation, fully cleared + settled ---
        emp1 = employees[0]
        case1 = SeparationCase.objects.create(
            tenant=tenant, employee=emp1, separation_type="resignation",
            exit_reason="better_opportunity", notice_period_days=30,
            notice_start_date=today - datetime.timedelta(days=60),
            actual_last_working_day=today - datetime.timedelta(days=30),
            notice_buyout_type="none", requires_kt=True, status="completed",
            submitted_at=now, approver=actor, approved_at=now,
            notes="Voluntary resignation — joined a new organization.")
        generate_clearance_checklist(case1)
        for ci in case1.clearance_items.all():
            ci.status = "cleared"
            ci.cleared_by = actor
            ci.cleared_at = now
            ci.save(update_fields=["status", "cleared_by", "cleared_at", "updated_at"])
        ExitInterview.objects.create(
            tenant=tenant, case=case1, interviewer=actor, scheduled_at=now, conducted_at=now,
            mode="in_person", status="completed",
            rating_job_satisfaction=4, rating_management=4, rating_compensation=3,
            rating_work_environment=4, rating_growth_opportunities=3, rating_work_life_balance=4,
            rating_culture=5, rating_overall=4, primary_reason="better_opportunity",
            would_recommend=True, would_rejoin=False,
            what_went_well="Supportive team and good mentorship.",
            what_to_improve="Clearer growth paths and faster promotions.",
            additional_comments="Grateful for the experience.")
        FinalSettlement.objects.create(
            tenant=tenant, case=case1, settlement_date=today - datetime.timedelta(days=28),
            prorata_salary=Decimal("15000"), leave_encashment_days=Decimal("5"),
            leave_encashment_amount=Decimal("5000"), tax_deduction=Decimal("2000"),
            status="paid", hr_approved_by=actor, hr_approved_at=now,
            finance_approved_by=actor, finance_approved_at=now,
            paid_at=today - datetime.timedelta(days=28),
            notes="Settled and paid via bank transfer.")

        # --- Case 2: resignation in progress, clearance underway (HR line cleared) ---
        if len(employees) > 1:
            emp2 = employees[1]
            case2 = SeparationCase.objects.create(
                tenant=tenant, employee=emp2, separation_type="resignation",
                exit_reason="career_growth", notice_period_days=30,
                notice_start_date=today - datetime.timedelta(days=15),
                notice_buyout_type="none", requires_kt=False, status="in_clearance",
                submitted_at=now, approver=actor, approved_at=now,
                notes="Pursuing a senior role elsewhere.")
            generate_clearance_checklist(case2)
            hr_line = case2.clearance_items.filter(department="hr").first()
            if hr_line:
                hr_line.status = "cleared"
                hr_line.cleared_by = actor
                hr_line.cleared_at = now
                hr_line.save(update_fields=["status", "cleared_by", "cleared_at", "updated_at"])

        self.stdout.write(self.style.SUCCESS(
            f"Offboarding seeded for '{tenant.name}': "
            f"{SeparationCase.objects.filter(tenant=tenant).count()} cases, "
            f"{ClearanceItem.objects.filter(tenant=tenant).count()} clearance items, "
            f"{ExitInterview.objects.filter(tenant=tenant).count()} exit interview(s), "
            f"{FinalSettlement.objects.filter(tenant=tenant).count()} settlement(s)."))

    @transaction.atomic
    def _seed_employee_records(self, tenant, *, flush):
        """Seed 3.1 Employee Management completion demo data — personnel-file documents + lifecycle
        events for the first few seeded employees. Guarded independently (its own EmployeeDocument
        existence check), so a tenant whose employees already exist still gets these records."""
        if flush:
            EmployeeLifecycleEvent.objects.filter(tenant=tenant).delete()
            EmployeeDocument.objects.filter(tenant=tenant).delete()
        if EmployeeDocument.objects.filter(tenant=tenant).exists():
            self.stdout.write(self.style.NOTICE(
                f"Employee records already exist for '{tenant.name}'. Use --flush to re-seed."))
            return
        employees = list(EmployeeProfile.objects.filter(tenant=tenant)
                         .select_related("party", "employment").order_by("created_at")[:3])
        if not employees:
            self.stdout.write(self.style.WARNING(
                f"No employees for '{tenant.name}' — skipping employee records."))
            return
        today = timezone.localdate()
        now = timezone.now()
        actor = get_user_model().objects.filter(tenant=tenant).order_by("id").first()

        for emp in employees:
            # National ID — verified.
            nid = EmployeeDocument.objects.create(
                tenant=tenant, employee=emp, document_type="national_id", title="National ID",
                document_number=f"NID-{emp.pk:06d}", issuing_country="—", is_confidential=True)
            nid.verification_status = "verified"
            nid.verified_by = actor
            nid.verified_at = now
            nid.save(update_fields=["verification_status", "verified_by", "verified_at", "updated_at"])
            # Passport — pending, expiring soon (today + 180 days).
            EmployeeDocument.objects.create(
                tenant=tenant, employee=emp, document_type="passport", title="Passport",
                document_number=f"P{emp.pk:07d}", issuing_authority="Passport Office",
                issued_on=today - datetime.timedelta(days=3650),
                expires_on=today + datetime.timedelta(days=180))
            # Appointment letter — verified.
            al = EmployeeDocument.objects.create(
                tenant=tenant, employee=emp, document_type="appointment_letter",
                title="Appointment Letter")
            al.verification_status = "verified"
            al.verified_by = actor
            al.verified_at = now
            al.save(update_fields=["verification_status", "verified_by", "verified_at", "updated_at"])

            # Lifecycle: a hire event (on the employment's hired_on), + a confirmation if confirmed.
            hired = emp.employment.hired_on if emp.employment_id and emp.employment.hired_on \
                else today - datetime.timedelta(days=365)
            EmployeeLifecycleEvent.objects.create(
                tenant=tenant, employee=emp, event_type="hire", effective_date=hired,
                reason="Initial hire", to_designation=emp.designation,
                to_job_title=emp.designation.name if emp.designation_id else "")
            if emp.confirmed_on:
                EmployeeLifecycleEvent.objects.create(
                    tenant=tenant, employee=emp, event_type="confirmation",
                    effective_date=emp.confirmed_on, reason="Probation successfully completed")

        self.stdout.write(self.style.SUCCESS(
            f"Employee records seeded for '{tenant.name}': "
            f"{EmployeeDocument.objects.filter(tenant=tenant).count()} documents, "
            f"{EmployeeLifecycleEvent.objects.filter(tenant=tenant).count()} lifecycle event(s)."))

    @staticmethod
    def _last_workdays(end, count):
        """Return the most recent ``count`` weekdays up to and including ``end``."""
        days, cur = [], end
        while len(days) < count:
            if cur.weekday() < 5:  # Mon–Fri
                days.append(cur)
            cur -= datetime.timedelta(days=1)
        return days

    @transaction.atomic
    def _seed_job_requisition(self, tenant, *, flush):
        """Seed 3.5 Job Requisition demo data — 2 JD templates + 3 requisitions across the lifecycle
        (one posted, one draft, one approved-with-chain). Reuses the already-seeded designations /
        employees / department OrgUnit. Guarded independently (its own JobRequisition existence
        check) so a tenant whose employees already exist still gets recruiting data."""
        if flush:
            RequisitionApproval.objects.filter(tenant=tenant).delete()
            JobRequisition.objects.filter(tenant=tenant).delete()
            JobDescriptionTemplate.objects.filter(tenant=tenant).delete()
        if JobRequisition.objects.filter(tenant=tenant).exists():
            self.stdout.write(self.style.NOTICE(
                f"Job requisitions already exist for '{tenant.name}'. Use --flush to re-seed."))
            return
        designations = list(Designation.objects.filter(tenant=tenant).order_by("created_at"))
        employees = list(EmployeeProfile.objects.filter(tenant=tenant)
                         .select_related("party").order_by("created_at"))
        if not designations or not employees:
            self.stdout.write(self.style.WARNING(
                f"No designations/employees for '{tenant.name}' — skipping job requisitions."))
            return
        dept = OrgUnit.objects.filter(tenant=tenant, kind="department").first()
        cost_center = OrgUnit.objects.filter(tenant=tenant, kind="cost_center").first()
        today = timezone.localdate()

        def desig(i):
            return designations[i] if len(designations) > i else designations[0]

        def emp(i):
            return employees[i] if len(employees) > i else employees[0]

        # --- 2 reusable JD templates (idempotent via tenant+name get_or_create) ---
        tmpl1, _ = JobDescriptionTemplate.objects.get_or_create(
            tenant=tenant, name="Software Engineer — Backend",
            defaults={
                "designation": desig(0), "employment_type": "full_time",
                "jd_summary": "Build and maintain scalable backend services.",
                "jd_responsibilities": "- Design REST APIs\n- Write unit tests\n- Review code",
                "jd_requirements": "- 3+ years Python/Django\n- Strong SQL fundamentals",
                "jd_nice_to_have": "- Experience with Docker / Kubernetes",
            })
        tmpl2, _ = JobDescriptionTemplate.objects.get_or_create(
            tenant=tenant, name="Engineering Manager",
            defaults={
                "designation": desig(2), "employment_type": "full_time",
                "jd_summary": "Lead a team of 5–8 engineers and own delivery.",
                "jd_responsibilities": "- Define the roadmap\n- Run 1:1s\n- Hire and grow talent",
                "jd_requirements": "- 5+ years engineering\n- 2+ years people management",
                "jd_nice_to_have": "- MBA or advanced degree",
            })

        # --- 3 requisitions across the lifecycle (TenantNumbered → save(), never bulk_create) ---
        req_specs = [
            {"title": "Senior Python Developer", "designation": desig(1), "headcount": 2,
             "req_type": "standard", "reason_for_hire": "new_headcount", "posting_type": "external",
             "priority": "high", "salary_min": Decimal("90000"), "salary_max": Decimal("130000"),
             "estimated_annual_cost": Decimal("150000"), "template": tmpl1,
             "jd_summary": tmpl1.jd_summary, "jd_responsibilities": tmpl1.jd_responsibilities,
             "jd_requirements": tmpl1.jd_requirements, "jd_nice_to_have": tmpl1.jd_nice_to_have,
             "target_start_date": today + datetime.timedelta(days=45), "status": "posted",
             "submitted_at": timezone.now(), "approved_at": timezone.now(),
             "posted_at": timezone.now()},
            {"title": "Junior Software Engineer", "designation": desig(0), "headcount": 1,
             "req_type": "backfill", "reason_for_hire": "backfill", "posting_type": "both",
             "priority": "medium", "salary_min": Decimal("60000"), "salary_max": Decimal("85000"),
             "target_start_date": today + datetime.timedelta(days=60), "status": "draft"},
            {"title": "Engineering Manager", "designation": desig(2), "headcount": 1,
             "req_type": "standard", "reason_for_hire": "new_headcount", "posting_type": "external",
             "priority": "urgent", "salary_min": Decimal("130000"), "salary_max": Decimal("180000"),
             "estimated_annual_cost": Decimal("205000"), "template": tmpl2,
             "jd_summary": tmpl2.jd_summary, "jd_responsibilities": tmpl2.jd_responsibilities,
             "jd_requirements": tmpl2.jd_requirements, "jd_nice_to_have": tmpl2.jd_nice_to_have,
             "target_start_date": today + datetime.timedelta(days=30), "status": "approved",
             "submitted_at": timezone.now(), "approved_at": timezone.now()},
        ]
        reqs = []
        for spec in req_specs:
            jr = JobRequisition(
                tenant=tenant, department=dept, cost_center=cost_center, location="Head Office",
                employment_type="full_time", salary_currency="USD",
                hiring_manager=emp(0), recruiter=emp(1), **spec)
            jr.save()
            reqs.append(jr)

        # --- A fully-approved 2-step chain on the approved requisition (demonstrates the audit trail) ---
        actor = get_user_model().objects.filter(tenant=tenant).order_by("id").first()
        approved_req = reqs[2]
        RequisitionApproval.objects.bulk_create([
            RequisitionApproval(tenant=tenant, requisition=approved_req, step_order=1,
                                approver=actor, approver_role="hr", status="approved",
                                decided_by=actor, decided_at=timezone.now()),
            RequisitionApproval(tenant=tenant, requisition=approved_req, step_order=2,
                                approver=actor, approver_role="executive", status="approved",
                                decided_by=actor, decided_at=timezone.now()),
        ])

        self.stdout.write(self.style.SUCCESS(
            f"Job requisitions seeded for '{tenant.name}': "
            f"{JobDescriptionTemplate.objects.filter(tenant=tenant).count()} templates, "
            f"{JobRequisition.objects.filter(tenant=tenant).count()} requisitions, "
            f"{RequisitionApproval.objects.filter(tenant=tenant).count()} approval step(s)."))

    @transaction.atomic
    def _seed_candidates(self, tenant, *, flush):
        """Seed 3.6 Candidate Management demo data — talent-pool tags, 2 recruiting email templates,
        6 candidates (each a fresh ``core.Party`` + ``PartyRole(role="candidate")``) with structured
        skills, 8 applications spread across the pipeline against the already-seeded requisitions, and
        a couple of logged communications. Also mints ``public_token`` on posted requisitions so the
        public careers portal resolves. Guarded on CandidateProfile existence (own check)."""
        if flush:
            CandidateCommunication.objects.filter(tenant=tenant).delete()
            JobApplication.objects.filter(tenant=tenant).delete()
            CandidateSkill.objects.filter(tenant=tenant).delete()
            cand_party_ids = list(
                CandidateProfile.objects.filter(tenant=tenant).values_list("party_id", flat=True))
            CandidateProfile.objects.filter(tenant=tenant).delete()
            Party.objects.filter(tenant=tenant, id__in=cand_party_ids).delete()
            CandidateEmailTemplate.objects.filter(tenant=tenant).delete()
            CandidateTag.objects.filter(tenant=tenant).delete()
        if CandidateProfile.objects.filter(tenant=tenant).exists():
            self.stdout.write(self.style.NOTICE(
                f"Candidate data already exists for '{tenant.name}'. Use --flush to re-seed."))
            return

        # Mint career-portal tokens on posted requisitions (the seeder sets status directly, bypassing
        # the post action that would normally mint them).
        for req in JobRequisition.objects.filter(
                tenant=tenant, status="posted", public_token__isnull=True):
            req.public_token = secrets.token_urlsafe(32)
            req.save(update_fields=["public_token"])

        # --- 3 talent-pool tags ---
        tags = {}
        for name, color in [("Python Engineers Pool", "#3B82F6"), ("Strong Culture Fit", "#10B981"),
                            ("Re-engage Later", "#F59E0B")]:
            tags[name], _ = CandidateTag.objects.get_or_create(
                tenant=tenant, name=name, defaults={"color": color})

        # --- 2 recruiting email templates ---
        tmpl_received, _ = CandidateEmailTemplate.objects.get_or_create(
            tenant=tenant, name="Application Received — Standard",
            defaults={
                "template_type": "application_received", "is_active": True, "is_auto_send": True,
                "subject": "Thank you for applying, {{candidate_name}}",
                "body_html": ("Dear {{candidate_name}},\n\nThank you for applying for the {{job_title}} "
                              "position at {{company_name}}. We have received your application "
                              "({{application_number}}) and will review it shortly.\n\nBest regards,\n"
                              "{{recruiter_name}}")})
        CandidateEmailTemplate.objects.get_or_create(
            tenant=tenant, name="Application Rejected — Standard",
            defaults={
                "template_type": "rejection", "is_active": True, "is_auto_send": False,
                "subject": "Update on your application for {{job_title}}",
                "body_html": ("Dear {{candidate_name}},\n\nThank you for your interest in the "
                              "{{job_title}} position at {{company_name}}. After careful consideration, "
                              "we will not be moving forward with your application at this time.\n\nWe "
                              "wish you the best in your search.\n\nBest regards,\n{{recruiter_name}}")})

        # --- 6 candidates (fresh Party + candidate role) with structured skills ---
        cand_specs = [
            {"first_name": "Alice", "last_name": "Johnson", "email": "alice.johnson@example.com",
             "phone": "+1-555-0101", "current_job_title": "Senior Software Engineer",
             "current_employer": "TechCorp", "city": "Austin", "country": "US",
             "years_of_experience": Decimal("7.0"), "highest_qualification": "masters",
             "source": "linkedin", "skill_set": "Python, Django, React",
             "skills": [("Python", "expert"), ("Django", "advanced")]},
            {"first_name": "Bob", "last_name": "Martinez", "email": "bob.martinez@example.com",
             "phone": "+1-555-0102", "current_job_title": "Product Manager",
             "current_employer": "ProductCo", "city": "Denver", "country": "US",
             "years_of_experience": Decimal("5.0"), "highest_qualification": "bachelors",
             "source": "referral", "skill_set": "Product Management, Agile",
             "skills": [("Product Management", "advanced"), ("Agile", "expert")]},
            {"first_name": "Carol", "last_name": "Singh", "email": "carol.singh@example.com",
             "phone": "+1-555-0103", "current_job_title": "UX Designer",
             "current_employer": "DesignStudio", "city": "Seattle", "country": "US",
             "years_of_experience": Decimal("4.0"), "highest_qualification": "bachelors",
             "source": "careers_page", "skill_set": "Figma, User Research",
             "skills": [("Figma", "expert"), ("User Research", "advanced")]},
            {"first_name": "David", "last_name": "Lee", "email": "david.lee@example.com",
             "phone": "+1-555-0104", "current_job_title": "DevOps Engineer",
             "current_employer": "CloudCo", "city": "Portland", "country": "US",
             "years_of_experience": Decimal("6.0"), "highest_qualification": "bachelors",
             "source": "indeed", "skill_set": "Docker, Kubernetes",
             "skills": [("Docker", "expert"), ("Kubernetes", "advanced")]},
            {"first_name": "Eva", "last_name": "Brown", "email": "eva.brown@example.com",
             "phone": "+1-555-0105", "current_job_title": "Data Analyst",
             "current_employer": "DataCorp", "city": "Chicago", "country": "US",
             "years_of_experience": Decimal("3.0"), "highest_qualification": "masters",
             "source": "glassdoor", "status": "hired", "skill_set": "SQL, Python",
             "skills": [("SQL", "advanced"), ("Python", "intermediate")]},
            {"first_name": "Frank", "last_name": "Wilson", "email": "frank.wilson@example.com",
             "phone": "+1-555-0106", "current_job_title": "Sales Executive",
             "current_employer": "SalesCo", "city": "Miami", "country": "US",
             "years_of_experience": Decimal("8.0"), "highest_qualification": "bachelors",
             "source": "agency", "skill_set": "CRM, B2B Sales",
             "skills": [("CRM", "advanced"), ("B2B Sales", "expert")]},
        ]
        candidates = []
        for spec in cand_specs:
            skills = spec.pop("skills")
            party = Party.objects.create(
                tenant=tenant, kind="person", name=f"{spec['first_name']} {spec['last_name']}")
            PartyRole.objects.get_or_create(tenant=tenant, party=party, role="candidate")
            cand = CandidateProfile.objects.create(
                tenant=tenant, party=party, gdpr_consent=True,
                gdpr_consent_date=timezone.now(), **spec)
            for skill_name, proficiency in skills:
                CandidateSkill.objects.create(
                    tenant=tenant, candidate=cand, skill_name=skill_name,
                    proficiency=proficiency, source="manual")
            candidates.append(cand)

        candidates[0].tags.add(tags["Python Engineers Pool"], tags["Strong Culture Fit"])
        candidates[1].tags.add(tags["Strong Culture Fit"])

        # --- 8 applications across the pipeline (distinct candidate↔requisition pairs) ---
        reqs = list(JobRequisition.objects.filter(tenant=tenant).order_by("created_at"))
        applications = []
        if reqs:
            def req(i):
                return reqs[i] if len(reqs) > i else reqs[0]

            # (candidate_idx, req_idx, stage, source, rating, rejection_reason)
            app_specs = [
                (0, 0, "interview", "linkedin", 4, ""),
                (1, 0, "screening", "referral", 3, ""),
                (2, 0, "applied", "careers_page", None, ""),
                (3, 0, "phone_screen", "indeed", 4, ""),
                (4, 0, "hired", "glassdoor", 5, ""),
                (5, 2, "screening", "agency", 3, ""),
                (0, 2, "applied", "linkedin", None, ""),
                (1, 1, "rejected", "referral", 2, "position_filled"),
            ]
            for c_idx, r_idx, stage, source, rating, reject in app_specs:
                defaults = {"stage": stage, "source": source, "rating": rating}
                if stage not in ("applied",):
                    defaults["stage_changed_at"] = timezone.now()
                if stage == "hired":
                    defaults["hired_on"] = timezone.localdate()
                if reject:
                    defaults["rejection_reason"] = reject
                app, _ = JobApplication.objects.get_or_create(
                    tenant=tenant, candidate=candidates[c_idx], requisition=req(r_idx),
                    defaults=defaults)
                applications.append(app)

        # --- A couple of logged communications on the first application ---
        actor = get_user_model().objects.filter(tenant=tenant).order_by("id").first()
        if applications:
            first = applications[0]
            CandidateCommunication.objects.create(
                tenant=tenant, candidate=first.candidate, application=first, template=tmpl_received,
                channel="email", direction="outbound", delivery_status="sent", sent_by=None,
                subject=f"Thank you for applying, {first.candidate.name}",
                body=(f"Dear {first.candidate.name},\n\nThank you for applying for the "
                      f"{first.requisition.title} position at {tenant.name}. We have received your "
                      f"application ({first.number}) and will review it shortly.\n\nBest regards,\n"
                      "The hiring team"))
            CandidateCommunication.objects.create(
                tenant=tenant, candidate=first.candidate, application=first, channel="email",
                direction="outbound", delivery_status="sent", sent_by=actor,
                subject="You've been shortlisted",
                body=(f"Hi {first.candidate.name},\n\nGreat news — you've been shortlisted for the "
                      f"{first.requisition.title} role. We'll reach out shortly to schedule a call.\n\n"
                      "Best,\nRecruiting"))

        self.stdout.write(self.style.SUCCESS(
            f"Candidates seeded for '{tenant.name}': "
            f"{CandidateProfile.objects.filter(tenant=tenant).count()} candidates, "
            f"{JobApplication.objects.filter(tenant=tenant).count()} applications, "
            f"{CandidateTag.objects.filter(tenant=tenant).count()} tags, "
            f"{CandidateEmailTemplate.objects.filter(tenant=tenant).count()} email templates."))

    def _seed_interviews(self, tenant, *, flush):
        """Seed 3.7 Interview Process demo data — interview-invite/reminder email templates, 2 interviews
        (a completed video round + an upcoming in-person round) scheduled on existing 3.6 applications,
        1–2 panelists each, and a submitted scorecard with 3 rating criteria on the completed round.
        Reuses existing JobApplication rows + tenant Users — no duplicate masters. Guarded on Interview
        existence; skipped (with a notice) if the tenant has no applications yet."""
        from datetime import timedelta

        if flush:
            Interview.objects.filter(tenant=tenant).delete()  # cascades panelists/feedback/criteria
        if Interview.objects.filter(tenant=tenant).exists():
            self.stdout.write(self.style.NOTICE(
                f"Interview data already exists for '{tenant.name}'. Use --flush to re-seed."))
            return

        # Prefer applications already in/past the interview stage; fall back to any application.
        apps_qs = list(JobApplication.objects.filter(
            tenant=tenant, stage__in=["phone_screen", "assessment", "interview", "offer", "hired"]
        ).select_related("candidate", "requisition").order_by("applied_at")[:2])
        if not apps_qs:
            apps_qs = list(JobApplication.objects.filter(tenant=tenant)
                           .select_related("candidate", "requisition").order_by("applied_at")[:2])
        if not apps_qs:
            self.stdout.write(self.style.NOTICE(
                f"No applications for '{tenant.name}' — skipping interview seed (seed candidates first)."))
            return

        # Recruiting email templates the invite/reminder send-actions resolve (idempotent).
        CandidateEmailTemplate.objects.get_or_create(
            tenant=tenant, name="Interview Invitation — Standard",
            defaults={
                "template_type": "interview_invite", "is_active": True, "is_auto_send": False,
                "subject": "Interview invitation for {{job_title}}",
                "body_html": ("Dear {{candidate_name}},\n\nWe'd like to invite you to interview for the "
                              "{{job_title}} role at {{company_name}}. The details are below.\n\nBest "
                              "regards,\n{{recruiter_name}}")})
        CandidateEmailTemplate.objects.get_or_create(
            tenant=tenant, name="Interview Reminder — Standard",
            defaults={
                "template_type": "interview_reminder", "is_active": True, "is_auto_send": False,
                "subject": "Reminder: your interview for {{job_title}}",
                "body_html": ("Hi {{candidate_name}},\n\nA friendly reminder about your upcoming interview "
                              "for the {{job_title}} role. The details are below.\n\nSee you then,\n"
                              "{{recruiter_name}}")})

        users = list(get_user_model().objects.filter(tenant=tenant, is_active=True).order_by("id")[:3])
        actor = users[0] if users else None
        now = timezone.now()

        intv_specs = [
            {"title": "Technical Round", "round_number": 1, "mode": "video", "status": "completed",
             "video_provider": "zoom", "meeting_url": "https://zoom.us/j/1234567890",
             "location": "", "delta_days": -2, "duration": 60, "make_feedback": True,
             "reco": "yes", "summary": "Strong technical depth; clear communicator.",
             "criteria": [("Technical Skills", 4), ("Problem Solving", 5), ("Communication", 4)]},
            {"title": "HR / Culture-fit Round", "round_number": 2, "mode": "in_person",
             "status": "scheduled", "video_provider": "", "meeting_url": "",
             "location": "Meeting Room 2, HQ", "delta_days": 4, "duration": 45, "make_feedback": False,
             "reco": "", "summary": "", "criteria": []},
        ]
        for i, spec in enumerate(intv_specs):
            application = apps_qs[i % len(apps_qs)]
            interview = Interview.objects.create(
                tenant=tenant, application=application, title=spec["title"],
                round_number=spec["round_number"], mode=spec["mode"], status=spec["status"],
                scheduled_at=now + timedelta(days=spec["delta_days"]), duration_minutes=spec["duration"],
                location=spec["location"], video_provider=spec["video_provider"],
                meeting_url=spec["meeting_url"], scheduled_by=actor,
                interviewer_instructions="Focus on role-relevant competencies; use structured questions.")
            panel = []
            for j, role in [(0, "lead"), (1, "interviewer")]:
                if len(users) > j:
                    panelist, _ = InterviewPanelist.objects.get_or_create(
                        interview=interview, interviewer=users[j],
                        defaults={"tenant": tenant, "role": role, "rsvp_status": "accepted",
                                  "notified_at": now})
                    panel.append(panelist)
            if spec["make_feedback"]:
                feedback = InterviewFeedback.objects.create(
                    tenant=tenant, interview=interview, panelist=panel[0] if panel else None,
                    submitted_by=actor, overall_recommendation=spec["reco"], summary=spec["summary"],
                    is_submitted=True, submitted_at=now)
                for crit_name, rating in spec["criteria"]:
                    FeedbackCriterion.objects.create(
                        tenant=tenant, feedback=feedback, criterion_name=crit_name, rating=rating)

        self.stdout.write(self.style.SUCCESS(
            f"Interviews seeded for '{tenant.name}': "
            f"{Interview.objects.filter(tenant=tenant).count()} interviews, "
            f"{InterviewPanelist.objects.filter(tenant=tenant).count()} panelists, "
            f"{InterviewFeedback.objects.filter(tenant=tenant).count()} scorecards, "
            f"{FeedbackCriterion.objects.filter(tenant=tenant).count()} criteria."))

    def _seed_offers(self, tenant, *, flush):
        """Seed 3.8 Offer Management demo data — 1 reusable offer-letter template, 2 offers over existing
        3.6 applications (one accepted end-to-end with a fully-approved 2-step chain, a completed clear
        background check, and a pre-boarding checklist; one pending-approval with a partly-decided chain),
        using the same ``generate_offer_approval_chain``/``generate_preboarding_checklist`` services the
        views use so seeded + live shapes match. Reuses existing applications + tenant Users — no duplicate
        masters. Guarded on Offer existence; skipped (with a notice) if the tenant has no applications."""
        from datetime import timedelta

        from apps.hrm.services import generate_offer_approval_chain, generate_preboarding_checklist

        if flush:
            Offer.objects.filter(tenant=tenant).delete()  # cascades approvals/background-checks/preboarding
        if Offer.objects.filter(tenant=tenant).exists():
            self.stdout.write(self.style.NOTICE(
                f"Offer data already exists for '{tenant.name}'. Use --flush to re-seed."))
            return

        # Prefer applications already at/past the offer stage; fall back to any application.
        apps_qs = list(JobApplication.objects.filter(
            tenant=tenant, stage__in=["offer", "hired"]
        ).select_related("candidate", "requisition").order_by("applied_at")[:2])
        if len(apps_qs) < 2:
            apps_qs = list(JobApplication.objects.filter(tenant=tenant)
                           .select_related("candidate", "requisition").order_by("applied_at")[:2])
        if not apps_qs:
            self.stdout.write(self.style.NOTICE(
                f"No applications for '{tenant.name}' — skipping offer seed (seed candidates first)."))
            return

        letter_tmpl, _ = OfferLetterTemplate.objects.get_or_create(
            tenant=tenant, name="Standard Offer Letter",
            defaults={"is_active": True,
                      "body_html": (
                          "Dear {{candidate_name}},\n\nWe are pleased to offer you the position of "
                          "{{job_title}} at {{company_name}}. Your annual base salary will be "
                          "{{currency}} {{base_salary}}, with a proposed start date of {{start_date}}.\n\n"
                          "We are excited about the prospect of you joining us and look forward to your "
                          "response.\n\nSincerely,\n{{hiring_manager_name}}")})

        users = list(get_user_model().objects.filter(tenant=tenant, is_active=True).order_by("id")[:3])
        actor = users[0] if users else None
        now = timezone.now()
        today = timezone.localdate()

        # ---- Offer 1: accepted end-to-end (2-step chain both approved + clear BGV + pre-boarding) ----
        app1 = apps_qs[0]
        offer1 = Offer.objects.create(
            tenant=tenant, application=app1, offer_letter_template=letter_tmpl,
            base_salary=Decimal("120000.00"), currency="USD",
            bonus_amount=Decimal("12000.00"), bonus_terms="10% annual performance bonus.",
            signing_bonus=Decimal("5000.00"), equity_terms="1,000 RSUs vesting over 4 years.",
            relocation_assistance=Decimal("3000.00"),
            benefits_summary="Health, dental, vision, 401(k) match, 20 days PTO.",
            start_date=today + timedelta(days=30), expires_on=today + timedelta(days=7),
            status="accepted", accepted_at=now, extended_by=actor, extended_at=now - timedelta(days=3),
            signature_status="signed", created_by=actor,
            notes="Extended after a strong final round.")
        generate_offer_approval_chain(offer1)  # total comp <= threshold → 2 steps (hiring_manager, hr)
        for step in offer1.approvals.all():
            step.status = "approved"
            step.approver = actor
            step.decided_by = actor
            step.decided_at = now - timedelta(days=4)
            step.save()
        # Advance the recruiting pipeline to hired (mirrors offer_accept).
        app1.stage = "hired"
        app1.hired_on = today
        app1.stage_changed_at = now
        app1.save(update_fields=["stage", "hired_on", "stage_changed_at", "updated_at"])
        BackgroundVerification.objects.create(
            tenant=tenant, offer=offer1, vendor="checkr", check_type="employment",
            status="completed", result="clear", consent_given=True, consent_date=now - timedelta(days=6),
            initiated_at=now - timedelta(days=6), completed_at=now - timedelta(days=1), initiated_by=actor,
            notes="Employment history verified — no discrepancies.")
        generate_preboarding_checklist(offer1)
        pb_items = list(offer1.preboarding_items.order_by("document_type"))
        for idx, item in enumerate(pb_items):
            if idx < 2:  # first two verified
                item.status = "verified"
                item.submitted_at = now - timedelta(days=2)
                item.verified_by = actor
                item.verified_at = now - timedelta(days=1)
                item.save()
            elif idx == 2:  # one submitted awaiting review
                item.status = "submitted"
                item.submitted_at = now - timedelta(days=1)
                item.save()

        # ---- Offer 2: pending approval (2-step chain, first approved / second pending) ----
        app2 = apps_qs[1] if len(apps_qs) > 1 else None
        if app2 is not None and app2.pk != app1.pk:
            offer2 = Offer.objects.create(
                tenant=tenant, application=app2, offer_letter_template=letter_tmpl,
                base_salary=Decimal("95000.00"), currency="USD",
                benefits_summary="Health, dental, 15 days PTO.",
                start_date=today + timedelta(days=45), expires_on=today + timedelta(days=10),
                status="pending_approval", created_by=actor, notes="Awaiting HR sign-off.")
            generate_offer_approval_chain(offer2)  # 2 steps
            steps2 = list(offer2.approvals.order_by("step_order"))
            if steps2:  # approve the first step (hiring manager), leave HR pending
                first = steps2[0]
                first.status = "approved"
                first.approver = actor
                first.decided_by = actor
                first.decided_at = now
                first.save()

        self.stdout.write(self.style.SUCCESS(
            f"Offers seeded for '{tenant.name}': "
            f"{Offer.objects.filter(tenant=tenant).count()} offers, "
            f"{OfferApproval.objects.filter(tenant=tenant).count()} approval steps, "
            f"{BackgroundVerification.objects.filter(tenant=tenant).count()} background checks, "
            f"{PreboardingItem.objects.filter(tenant=tenant).count()} pre-boarding items, "
            f"{OfferLetterTemplate.objects.filter(tenant=tenant).count()} letter templates."))

    @transaction.atomic
    def _seed_timetracking(self, tenant, *, flush):
        """Seed 3.11 Time Tracking demo data — 2 timesheets per (up to 3) seeded employee (one approved
        last week, one pending this week), each with 4 ``TimesheetEntry`` lines against a seeded
        ``accounting.Project`` where one exists (else free-text tasks + no project), plus 1 pending
        ``OvertimeRequest``. Guarded on Timesheet existence; reuses existing EmployeeProfile +
        accounting.Project — no duplicate masters. Totals set via ``refresh_totals()`` (never hand-typed)."""
        from apps.accounting.models_advanced import Project

        if flush:
            OvertimeRequest.objects.filter(tenant=tenant).delete()
            Timesheet.objects.filter(tenant=tenant).delete()  # cascades TimesheetEntry
        if Timesheet.objects.filter(tenant=tenant).exists():
            self.stdout.write(self.style.NOTICE(
                f"Time-tracking data already exists for '{tenant.name}'. Use --flush to re-seed."))
            return

        employees = list(EmployeeProfile.objects.filter(tenant=tenant).select_related("party")[:3])
        if not employees:
            self.stdout.write(self.style.NOTICE(
                f"No employees for '{tenant.name}' — skipping time-tracking seed (seed employees first)."))
            return
        project = Project.objects.filter(tenant=tenant).first()  # optional — may be None
        today = datetime.date.today()
        this_monday = today - datetime.timedelta(days=today.weekday())
        last_monday = this_monday - datetime.timedelta(days=7)
        tasks = ["Feature development", "Code review", "Client meeting", "Bug fixing", "Documentation"]

        ts_count = entry_count = 0
        for idx, emp in enumerate(employees):
            for start, target in [(last_monday, "approved"), (this_monday, "pending")]:
                ts = Timesheet.objects.create(
                    tenant=tenant, employee=emp, period_start=start,
                    period_end=start + datetime.timedelta(days=6), status="draft")
                ts_count += 1
                for d in range(4):  # Mon–Thu
                    billable = (d % 2 == 0)
                    TimesheetEntry.objects.create(
                        tenant=tenant, timesheet=ts, date=start + datetime.timedelta(days=d),
                        project=project if billable else None,
                        task_description=tasks[(idx + d) % len(tasks)],
                        hours=Decimal("8.00") if d < 3 else Decimal("6.00"),
                        is_billable=billable,
                        billable_rate=Decimal("75.00") if billable else Decimal("0"))
                    entry_count += 1
                ts.refresh_totals()
                if target == "approved":
                    ts.status, ts.approved_at = "approved", timezone.now()
                    ts.save(update_fields=["status", "approved_at", "updated_at"])
                else:
                    ts.status = "pending"
                    ts.save(update_fields=["status", "updated_at"])

        first_approved = Timesheet.objects.filter(tenant=tenant, status="approved").order_by("period_start").first()
        OvertimeRequest.objects.create(
            tenant=tenant, employee=employees[0], timesheet=first_approved,
            date=last_monday + datetime.timedelta(days=2), hours_claimed=Decimal("3.00"),
            multiplier=Decimal("1.50"), payout_method="pay",
            reason="Production incident response after hours.", status="pending")

        self.stdout.write(self.style.SUCCESS(
            f"Time-tracking seeded for '{tenant.name}': {ts_count} timesheets, {entry_count} entries, "
            f"{OvertimeRequest.objects.filter(tenant=tenant).count()} overtime requests."))

    def _seed_salary(self, tenant, *, flush):
        """3.13 Salary Structure — a pay-component catalog (earnings/statutory/reimbursement/variable),
        a grade-wise CTC structure template with a fixed-amount breakdown, and one active employee
        assignment. Reuses seeded JobGrade + EmployeeProfile; does NOT run payroll (that's 3.14)."""
        if flush:
            # Children first: assignments + lines before their templates + components (line→component
            # is PROTECT, so a component can't be deleted while a line references it).
            EmployeeSalaryStructure.objects.filter(tenant=tenant).delete()
            SalaryStructureLine.objects.filter(tenant=tenant).delete()
            SalaryStructureTemplate.objects.filter(tenant=tenant).delete()
            PayComponent.objects.filter(tenant=tenant).delete()
        if PayComponent.objects.filter(tenant=tenant).exists():
            self.stdout.write(self.style.NOTICE(
                f"Salary structure data already exists for '{tenant.name}'. Use --flush to re-seed."))
            return

        # --- Pay components: (name, code, type, calc, default_amount, default_pct, freq, taxable, side, cap, requires_bill, order) ---
        COMPONENTS = [
            ("Basic", "BASIC", "earning", "pct_of_ctc", None, Decimal("40"), "monthly", True, "employee", None, False, 1),
            ("House Rent Allowance", "HRA", "earning", "pct_of_basic", None, Decimal("50"), "monthly", True, "employee", None, False, 2),
            ("Special Allowance", "SPL", "earning", "fixed_amount", Decimal("20000"), None, "monthly", True, "employee", None, False, 3),
            ("Provident Fund (Employee)", "PF-EE", "statutory_deduction", "pct_of_basic", None, Decimal("12"), "monthly", False, "employee", None, False, 10),
            ("Provident Fund (Employer)", "PF-ER", "statutory_deduction", "pct_of_basic", None, Decimal("12"), "monthly", False, "employer", None, False, 11),
            ("Professional Tax", "PT", "statutory_deduction", "fixed_amount", Decimal("200"), None, "monthly", False, "employee", None, False, 12),
            ("LTA Reimbursement", "LTA", "reimbursement", "fixed_amount", Decimal("1500"), None, "annual", False, "employee", Decimal("18000"), True, 20),
            ("Performance Bonus", "BONUS", "variable", "fixed_amount", Decimal("5000"), None, "one_time", True, "employee", None, False, 30),
        ]
        comps = {}
        for name, code, ctype, calc, amt, pct, freq, taxable, side, cap, bill, order in COMPONENTS:
            c, _ = PayComponent.objects.get_or_create(
                tenant=tenant, name=name,
                defaults={"code": code, "component_type": ctype, "calculation_type": calc,
                          "default_amount": amt, "default_percentage": pct, "frequency": freq,
                          "is_taxable": taxable, "contribution_side": side, "annual_cap_amount": cap,
                          "requires_bill": bill, "display_order": order,
                          "variable_subtype": "bonus" if ctype == "variable" else ""})
            comps[code] = c

        # --- A grade-wise CTC template + fixed-amount breakdown (earnings + employer PF + LTA) ---
        grade = JobGrade.objects.filter(tenant=tenant).order_by("level_order").first()
        template, _ = SalaryStructureTemplate.objects.get_or_create(
            tenant=tenant, name="Standard Staff — CTC",
            defaults={"job_grade": grade, "annual_ctc_amount": Decimal("120000"),
                      "currency": "USD", "description": "Default grade-wise CTC structure."})
        # (component code, fixed amount, sequence) — fixed so the derived CTC total is sensible.
        LINES = [
            ("BASIC", Decimal("60000"), 1),
            ("HRA", Decimal("30000"), 2),
            ("SPL", Decimal("20000"), 3),
            ("PF-ER", Decimal("7200"), 4),
            ("LTA", Decimal("1500"), 5),
        ]
        for code, amt, seq in LINES:
            if code in comps:
                SalaryStructureLine.objects.get_or_create(
                    tenant=tenant, template=template, pay_component=comps[code],
                    defaults={"calculation_type": "fixed_amount", "amount": amt, "sequence": seq})

        # --- One active assignment for the first employee ---
        emp = (EmployeeProfile.objects.filter(tenant=tenant)
               .select_related("party").order_by("party__name").first())
        if emp and not EmployeeSalaryStructure.objects.filter(
                tenant=tenant, employee=emp, status="active").exists():
            EmployeeSalaryStructure.objects.create(
                tenant=tenant, employee=emp, template=template,
                annual_ctc_amount=template.annual_ctc_amount or Decimal("120000"),
                effective_from=timezone.localdate(), status="active",
                notes="Initial assignment (demo seeder).")

        self.stdout.write(self.style.SUCCESS(
            f"Salary structure seeded for '{tenant.name}': "
            f"{PayComponent.objects.filter(tenant=tenant).count()} components, "
            f"{SalaryStructureTemplate.objects.filter(tenant=tenant).count()} template(s), "
            f"{SalaryStructureLine.objects.filter(tenant=tenant).count()} lines, "
            f"{EmployeeSalaryStructure.objects.filter(tenant=tenant).count()} assignment(s)."))

    def _seed_payroll(self, tenant, *, flush):
        """3.14 Payroll Processing — a regular monthly cycle with payslips computed (via `recompute()`)
        from the 3.13 salary structures, one payslip on hold. Ensures a few employees have an active
        `EmployeeSalaryStructure` first (reusing the 3.13 template). Runs after `_seed_salary`."""
        if flush:
            # Children first: lines → payslips → cycle.
            PayslipLine.objects.filter(tenant=tenant).delete()
            Payslip.objects.filter(tenant=tenant).delete()
            PayrollCycle.objects.filter(tenant=tenant).delete()
        if PayrollCycle.objects.filter(tenant=tenant).exists():
            self.stdout.write(self.style.NOTICE(
                f"Payroll data already exists for '{tenant.name}'. Use --flush to re-seed."))
            return

        template = SalaryStructureTemplate.objects.filter(tenant=tenant).order_by("id").first()
        if template is None:
            self.stdout.write(self.style.NOTICE(
                f"No salary structure template for '{tenant.name}' — skipping payroll seed."))
            return

        # Give the first few employees an active salary structure (idempotent, one-active guard).
        for emp in (EmployeeProfile.objects.filter(tenant=tenant).select_related("party")
                    .order_by("party__name")[:3]):
            if not EmployeeSalaryStructure.objects.filter(
                    tenant=tenant, employee=emp, status="active").exists():
                EmployeeSalaryStructure.objects.create(
                    tenant=tenant, employee=emp, template=template,
                    annual_ctc_amount=template.annual_ctc_amount or Decimal("120000"),
                    effective_from=timezone.localdate().replace(day=1), status="active",
                    notes="Payroll demo assignment.")

        # A regular cycle for the current month.
        today = timezone.localdate()
        period_start = today.replace(day=1)
        period_end = (period_start + datetime.timedelta(days=32)).replace(day=1) - datetime.timedelta(days=1)
        cycle = PayrollCycle.objects.create(
            tenant=tenant, period_start=period_start, period_end=period_end, pay_date=period_end,
            cycle_type="regular", status="draft", notes="Demo monthly payroll cycle.")
        days_in = (period_end - period_start).days + 1
        for structure in (EmployeeSalaryStructure.objects.filter(tenant=tenant, status="active")
                          .select_related("employee")):
            ps = Payslip.objects.create(
                tenant=tenant, cycle=cycle, employee=structure.employee, salary_structure=structure,
                days_in_period=days_in, days_worked=days_in)
            ps.recompute()
        # Put one payslip on hold for demo variety.
        if cycle.payslips.count() > 1:
            held = cycle.payslips.order_by("-id").first()
            held.on_hold = True
            held.hold_reason = "Pending exit clearance (demo)."
            held.save(update_fields=["on_hold", "hold_reason"])

        self.stdout.write(self.style.SUCCESS(
            f"Payroll seeded for '{tenant.name}': {PayrollCycle.objects.filter(tenant=tenant).count()} cycle, "
            f"{cycle.payslips.count()} payslips, "
            f"{PayslipLine.objects.filter(tenant=tenant).count()} lines."))
