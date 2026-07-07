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
from apps.hrm.models import (  # 3.15 Statutory Compliance
    EmployeeStatutoryIdentifier,
    StatutoryConfig,
    StatutoryReturn,
    StatutoryStateRule,
)
from apps.hrm.models import (  # 3.16 Tax & Investment
    InvestmentDeclaration,
    InvestmentDeclarationLine,
    InvestmentProof,
    TaxComputation,
    TaxRegimeConfig,
    TaxSlabBand,
)
from apps.hrm.models import (  # 3.17 Payout & Reports
    BankReconciliation,
    PayoutBatch,
    PayoutPayment,
    PayslipDistribution,
)
from apps.hrm.models import (  # 3.18 Goal Setting
    GoalCheckIn,
    GoalPeriod,
    KeyResult,
    Objective,
)
from apps.hrm.models import (  # 3.19 Performance Review
    PerformanceReview,
    ReviewCycle,
    ReviewRating,
    ReviewTemplate,
)
from apps.hrm.models import (  # 3.20 Continuous Feedback
    Feedback,
    KudosBadge,
    MeetingActionItem,
    OneOnOneMeeting,
)
from apps.hrm.models import (  # 3.21 Performance Improvement
    CoachingNote,
    PIPCheckIn,
    PerformanceImprovementPlan,
    WarningLetter,
)
from apps.hrm.models import (  # 3.22 Training Management
    TrainingCourse,
    TrainingSession,
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
            self._seed_statutory(tenant, flush=options["flush"])
            self._seed_tax(tenant, flush=options["flush"])
            self._seed_payout(tenant, flush=options["flush"])
            self._seed_goals(tenant, flush=options["flush"])
            self._seed_reviews(tenant, flush=options["flush"])
            self._seed_feedback(tenant, flush=options["flush"])
            self._seed_improvement(tenant, flush=options["flush"])
            self._seed_training(tenant, flush=options["flush"])
        self.stdout.write(self.style.WARNING(
            "NOTE: Superuser 'admin' has no tenant — HRM data won't appear when logged in as admin. "
            "Log in as admin_acme / admin_globex (password)."))

    @transaction.atomic
    def _seed_tenant(self, tenant, *, flush):
        if flush:
            # Children first (onboarding/offboarding rows FK EmployeeProfile/Designation), then masters.
            # 3.12: elections FK holiday/policy/employee; policies FK/M2M holiday/designation — wipe first.
            # 3.14: Payslip.employee is PROTECT, so payslips must be wiped before EmployeeProfile below.
            # 3.15: statutory returns/identifiers FK PayrollCycle/EmployeeProfile — wipe them first.
            # 3.16: tax computations/declarations FK EmployeeProfile (PROTECT) + StatutoryReturn — wipe
            # BEFORE the statutory + employee rows below.
            for model in (TaxComputation, InvestmentProof, InvestmentDeclarationLine,
                          InvestmentDeclaration, TaxSlabBand, TaxRegimeConfig,
                          StatutoryReturn, EmployeeStatutoryIdentifier, StatutoryStateRule,
                          StatutoryConfig,
                          # 3.17: reconciliations/payments FK batch/cycle/payslip (PROTECT) — wipe first.
                          BankReconciliation, PayoutPayment, PayoutBatch, PayslipDistribution,
                          PayslipLine, Payslip, PayrollCycle,
                          # 3.19: PerformanceReview.subject/reviewer FK EmployeeProfile (PROTECT) + cycle
                          # (PROTECT) — wipe reviews (ratings→reviews→cycles→templates) BEFORE the employee
                          # rows below. Also before GoalPeriod (ReviewCycle.goal_period SET_NULL is harmless
                          # either way, but keep review teardown grouped ahead of the goal teardown).
                          ReviewRating, PerformanceReview, ReviewCycle, ReviewTemplate,
                          # 3.20: Feedback/1:1s PROTECT EmployeeProfile (giver/receiver/manager/
                          # employee/owner) — wipe the feedback + 1:1 rows (action-items→meetings,
                          # feedback→badges) BEFORE the employee rows below.
                          # 3.22: TrainingSession.course is PROTECT (wipe sessions before courses);
                          # instructor_employee/external_vendor are SET_NULL (not a PROTECT barrier) — listed
                          # here only so a full --flush leaves no orphaned training rows.
                          TrainingSession, TrainingCourse,
                          # 3.21: PIPs/warnings/coaching PROTECT EmployeeProfile — wipe them child-first
                          # (coaching/warnings/check-ins then plans) BEFORE the employee rows below.
                          CoachingNote, WarningLetter, PIPCheckIn, PerformanceImprovementPlan,
                          MeetingActionItem, OneOnOneMeeting, Feedback, KudosBadge,
                          # 3.18: Objective.owner FK EmployeeProfile (PROTECT) + goal_period (PROTECT) —
                          # wipe goals (check-ins→KRs→objectives→periods) BEFORE the employee rows below.
                          GoalCheckIn, KeyResult, Objective, GoalPeriod,
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

    def _seed_statutory(self, tenant, *, flush):
        """3.15 Statutory Compliance — a StatutoryConfig singleton, three Maharashtra
        StatutoryStateRule rows (2 PT slabs + 1 half-yearly LWF), an EmployeeStatutoryIdentifier
        per seeded employee, and one generated PF StatutoryReturn over the 3.14 payroll cycle.
        Runs AFTER _seed_payroll (it aggregates the cycle's PayslipLine rows)."""
        if flush:
            # Children first: returns → identifiers → state rules → config.
            StatutoryReturn.objects.filter(tenant=tenant).delete()
            EmployeeStatutoryIdentifier.objects.filter(tenant=tenant).delete()
            StatutoryStateRule.objects.filter(tenant=tenant).delete()
            StatutoryConfig.objects.filter(tenant=tenant).delete()
        if StatutoryConfig.objects.filter(tenant=tenant).exists():
            self.stdout.write(self.style.NOTICE(
                f"Statutory compliance data already exists for '{tenant.name}'. Use --flush to re-seed."))
            return

        config = StatutoryConfig.objects.create(
            tenant=tenant,
            pf_establishment_code="MH/BAN/1234567/000",
            esi_employer_code="11-22-334455-000-1111",
            pt_default_state="Maharashtra",
            tan_number="MUMB12345C",
            tds_circle_address="ITO (TDS), Room 101, Mumbai",
            pan_of_deductor="AABCN1234A",
            is_lwf_applicable=True)

        eff = datetime.date(2024, 4, 1)
        # Two Maharashtra PT slabs (0–7500 → nil; 7501–10000 → ₹175/mo) + a half-yearly LWF row.
        StatutoryStateRule.objects.create(
            tenant=tenant, state="Maharashtra", scheme="pt",
            income_from=Decimal("0.00"), income_to=Decimal("7500.00"),
            pt_monthly_amount=Decimal("0.00"), is_active=True, effective_from=eff)
        StatutoryStateRule.objects.create(
            tenant=tenant, state="Maharashtra", scheme="pt",
            income_from=Decimal("7501.00"), income_to=Decimal("10000.00"),
            pt_monthly_amount=Decimal("175.00"), is_active=True, effective_from=eff)
        StatutoryStateRule.objects.create(
            tenant=tenant, state="Maharashtra", scheme="lwf",
            lwf_employee_contribution=Decimal("6.00"), lwf_employer_contribution=Decimal("18.00"),
            lwf_periodicity="half_yearly", lwf_due_month_1="July", lwf_due_month_2="January",
            registration_number="LWF/MH/998877", is_active=True, effective_from=eff)

        # A statutory identifier per seeded employee (deterministic demo IDs; idempotent).
        for emp in EmployeeProfile.objects.filter(tenant=tenant).select_related("party"):
            EmployeeStatutoryIdentifier.objects.get_or_create(
                tenant=tenant, employee=emp,
                defaults={"uan_number": f"UAN{emp.pk:010d}",
                          "pf_number": f"MH/BAN/1234567/000/{emp.pk:04d}",
                          "esi_number": f"3411{emp.pk:06d}",
                          "pt_state": "Maharashtra"})

        # Generate one PF return over the existing 3.14 payroll cycle (rolls up PF PayslipLines).
        cycle = PayrollCycle.objects.filter(tenant=tenant).order_by("pay_date").first()
        ret_number = "—"
        if cycle is not None:
            # PF for wage-month M is due by the 15th of the following month.
            due = (cycle.period_end.replace(day=1) + datetime.timedelta(days=32)).replace(day=15)
            ret = StatutoryReturn.objects.create(
                tenant=tenant, scheme="pf", period_type="monthly",
                period_start=cycle.period_start, period_end=cycle.period_end, cycle=cycle,
                due_date=due, notes="Demo monthly PF challan/return.")
            ret.recompute()
            ret_number = ret.number

        self.stdout.write(self.style.SUCCESS(
            f"Statutory compliance seeded for '{tenant.name}': 1 config, "
            f"{StatutoryStateRule.objects.filter(tenant=tenant).count()} state rules, "
            f"{EmployeeStatutoryIdentifier.objects.filter(tenant=tenant).count()} identifier(s), "
            f"{StatutoryReturn.objects.filter(tenant=tenant).count()} return ({ret_number})."))

    def _seed_tax(self, tenant, *, flush):
        """3.16 Tax & Investment — 2 FY-2025-26 TaxRegimeConfigs (new + old) with their slab bands, an
        InvestmentDeclaration (old regime, to demonstrate deductions) + 80C/HRA lines + a verified proof,
        and a generated + Form-16-linked TaxComputation. Runs AFTER _seed_statutory (Form-16 linkage
        needs the StatutoryReturn/StatutoryConfig rows; the TDS-YTD aggregation needs PayslipLine rows)."""
        if flush:
            # Children first: computations → proofs → lines → declarations → slab bands → configs.
            TaxComputation.objects.filter(tenant=tenant).delete()
            InvestmentProof.objects.filter(tenant=tenant).delete()
            InvestmentDeclarationLine.objects.filter(tenant=tenant).delete()
            InvestmentDeclaration.objects.filter(tenant=tenant).delete()
            TaxSlabBand.objects.filter(tenant=tenant).delete()
            TaxRegimeConfig.objects.filter(tenant=tenant).delete()
        if TaxRegimeConfig.objects.filter(tenant=tenant).exists():
            self.stdout.write(self.style.NOTICE(
                f"Tax & Investment data already exists for '{tenant.name}'. Use --flush to re-seed."))
            return

        fy = "2025-26"
        new_cfg = TaxRegimeConfig.objects.create(
            tenant=tenant, financial_year=fy, regime="new",
            standard_deduction=Decimal("75000.00"), cess_rate=Decimal("4.00"),
            rebate_income_threshold=Decimal("1200000.00"), rebate_max_tax=Decimal("60000.00"),
            is_default_regime=True,
            tax_law_reference="FY 2025-26 Finance Act rates; Income Tax Act 2025 section renumbering pending.")
        new_bands = [(0, 400000, 0), (400000, 800000, 5), (800000, 1200000, 10),
                     (1200000, 1600000, 15), (1600000, 2000000, 20), (2000000, 2400000, 25),
                     (2400000, None, 30)]
        for i, (lo, hi, rate) in enumerate(new_bands, start=1):
            TaxSlabBand.objects.create(
                tenant=tenant, config=new_cfg, income_from=Decimal(lo),
                income_to=(Decimal(hi) if hi is not None else None), rate_percent=Decimal(rate), sequence=i)

        old_cfg = TaxRegimeConfig.objects.create(
            tenant=tenant, financial_year=fy, regime="old",
            standard_deduction=Decimal("50000.00"), cess_rate=Decimal("4.00"),
            rebate_income_threshold=Decimal("500000.00"), rebate_max_tax=Decimal("12500.00"),
            is_default_regime=False)
        old_bands = [(0, 250000, 0), (250000, 500000, 5), (500000, 1000000, 20), (1000000, None, 30)]
        for i, (lo, hi, rate) in enumerate(old_bands, start=1):
            TaxSlabBand.objects.create(
                tenant=tenant, config=old_cfg, income_from=Decimal(lo),
                income_to=(Decimal(hi) if hi is not None else None), rate_percent=Decimal(rate), sequence=i)

        # An employee with an active salary structure (from _seed_salary/_seed_payroll).
        struct = (EmployeeSalaryStructure.objects.filter(tenant=tenant, status="active")
                  .select_related("employee__party").order_by("id").first())
        comp_number = "—"
        if struct is not None:
            emp = struct.employee
            today = timezone.localdate()
            # A mid-year-joiner demo (previous_employer_income) so the computation produces a real,
            # hand-verifiable tax figure rather than 0 on the low demo CTC.
            decl = InvestmentDeclaration.objects.create(
                tenant=tenant, employee=emp, financial_year=fy, regime_elected="old",
                status="submitted",
                declaration_window_open=datetime.date(2025, 4, 1),
                declaration_window_close=datetime.date(2025, 6, 30),
                proof_window_open=datetime.date(2025, 12, 1),
                proof_window_close=datetime.date(2026, 2, 28),
                previous_employer_income=Decimal("800000.00"), previous_employer_tds=Decimal("0.00"),
                notes="Demo declaration (mid-year joiner).")
            line_80c = InvestmentDeclarationLine.objects.create(
                tenant=tenant, declaration=decl, section_code="80c", declared_amount=Decimal("150000.00"))
            InvestmentDeclarationLine.objects.create(
                tenant=tenant, declaration=decl, section_code="hra", declared_amount=Decimal("0.00"),
                monthly_rent_amount=Decimal("15000.00"), is_metro_city=True)
            # A verified 80C proof (file left blank — demo placeholder; the workflow is what's shown).
            admin_user = get_user_model().objects.filter(tenant=tenant).order_by("id").first()
            InvestmentProof.objects.create(
                tenant=tenant, declaration_line=line_80c, file="", title="LIC Premium Receipt",
                amount=Decimal("150000.00"), verification_status="verified",
                verified_by=admin_user, verified_at=timezone.now())
            line_80c.verified_amount = Decimal("150000.00")
            line_80c.save(update_fields=["verified_amount"])

            comp = TaxComputation.objects.create(
                tenant=tenant, employee=emp, declaration=decl, financial_year=fy,
                computation_type="final", remaining_pay_periods=6)
            comp.recompute()
            comp.link_form16()
            comp_number = f"{comp.number} -> {comp.tax_payable} payable"

        self.stdout.write(self.style.SUCCESS(
            f"Tax & Investment seeded for '{tenant.name}': "
            f"{TaxRegimeConfig.objects.filter(tenant=tenant).count()} regime configs "
            f"({TaxSlabBand.objects.filter(tenant=tenant).count()} slab bands), "
            f"{InvestmentDeclaration.objects.filter(tenant=tenant).count()} declaration, "
            f"{InvestmentProof.objects.filter(tenant=tenant).count()} proof, "
            f"{TaxComputation.objects.filter(tenant=tenant).count()} computation ({comp_number})."))

    def _seed_payout(self, tenant, *, flush):
        """3.17 Payout & Reports — locks the seeded PayrollCycle (a payout batch needs a locked cycle),
        generates a PayoutBatch + one PayoutPayment per payslip (one on-hold, one paid, one failed for
        demo variety), a PayslipDistribution per payslip (some sent), and a BankReconciliation. Runs
        AFTER _seed_tax; leaves accounting.PayrollRun untouched (a real lock also creates that run — the
        seeder just flips the status, the payout only needs is_locked)."""
        if flush:
            # Children first: reconciliations → payments → batch → distributions.
            BankReconciliation.objects.filter(tenant=tenant).delete()
            PayoutPayment.objects.filter(tenant=tenant).delete()
            PayoutBatch.objects.filter(tenant=tenant).delete()
            PayslipDistribution.objects.filter(tenant=tenant).delete()
        if PayoutBatch.objects.filter(tenant=tenant).exists():
            self.stdout.write(self.style.NOTICE(
                f"Payout data already exists for '{tenant.name}'. Use --flush to re-seed."))
            return

        cycle = (PayrollCycle.objects.filter(tenant=tenant).order_by("pay_date")
                 .prefetch_related("payslips__employee__party").first())
        if cycle is None or not cycle.payslips.exists():
            self.stdout.write(self.style.NOTICE(
                f"No payroll cycle with payslips for '{tenant.name}' — skipping payout seed."))
            return

        admin_user = get_user_model().objects.filter(tenant=tenant).order_by("id").first()
        # Lock the cycle so it can be paid out (a real lock via payrollcycle_lock also creates the
        # accounting.PayrollRun; the demo only needs is_locked=True).
        if not cycle.is_locked:
            cycle.status = "locked"
            cycle.save(update_fields=["status"])

        batch = PayoutBatch.objects.create(
            tenant=tenant, cycle=cycle, status="draft", bank_file_format="neft",
            source_bank_name="Company Payroll A/C", source_account_last4="••••4321",
            generated_by=admin_user, generated_at=timezone.now(), notes="Demo salary disbursement.")
        # Generate one payment per payslip (on-hold → zero-action row).
        payments = []
        for ps in cycle.payslips.select_related("employee__party"):
            emp = ps.employee
            payments.append(PayoutPayment.objects.create(
                tenant=tenant, batch=batch, payslip=ps, employee=emp, net_amount=ps.net_pay,
                bank_name_snapshot=emp.bank_name,
                bank_account_last4_snapshot=emp.masked_bank_account(),
                bank_routing_snapshot=emp.masked_bank_routing(),
                status="on_hold" if ps.on_hold else "pending"))
        # Approve + disburse.
        batch.status = "approved"
        batch.approved_by = admin_user
        batch.approved_at = timezone.now()
        batch.save(update_fields=["status", "approved_by", "approved_at"])
        now = timezone.now()
        PayoutPayment.objects.filter(batch=batch, status="pending").update(
            status="processing", initiated_at=now)
        batch.status = "disbursed"
        batch.disbursed_at = now
        batch.save(update_fields=["status", "disbursed_at"])
        # Mark the processing ones: first paid (with a UTR), the rest failed — for demo variety.
        processing = list(PayoutPayment.objects.filter(batch=batch, status="processing")
                          .order_by("employee__party__name"))
        for i, pay in enumerate(processing):
            if i == 0:
                pay.status = "paid"
                pay.paid_on = timezone.now()
                pay.transaction_reference = f"UTR{batch.pk:04d}{pay.pk:04d}"
                pay.save(update_fields=["status", "paid_on", "transaction_reference"])
            else:
                pay.status = "failed"
                pay.failure_reason = "Incorrect bank details (demo)."
                pay.save(update_fields=["status", "failure_reason"])
        # Derive the batch status: a failed present → partially_disbursed.
        if PayoutPayment.objects.filter(batch=batch, status__in=["failed", "returned"]).exists():
            batch.status = "partially_disbursed"
            batch.save(update_fields=["status"])

        # A PayslipDistribution per payslip; mark the paid employee's as sent.
        for ps in cycle.payslips.select_related("employee"):
            dist = PayslipDistribution.for_payslip(ps)
            if PayoutPayment.objects.filter(batch=batch, payslip=ps, status="paid").exists():
                emp = ps.employee
                dist.sent_to_email = emp.work_email or emp.personal_email or ""
                dist.status = "sent"
                dist.sent_at = timezone.now()
                dist.sent_by = admin_user
                dist.save(update_fields=["sent_to_email", "status", "sent_at", "sent_by"])

        # A reconciliation over the batch (matches the paid+UTR rows; flags the failed one).
        recon = BankReconciliation.objects.create(
            tenant=tenant, batch=batch, statement_date=timezone.localdate(),
            statement_reference="STMT-DEMO-001", notes="Demo bank statement reconciliation.")
        recon.reconciled_by = admin_user
        recon.recompute()
        recon.save(update_fields=["reconciled_by"])

        self.stdout.write(self.style.SUCCESS(
            f"Payout seeded for '{tenant.name}': 1 batch ({batch.number}, {batch.get_status_display()}), "
            f"{PayoutPayment.objects.filter(batch=batch).count()} payments "
            f"({batch.paid_count} paid / {batch.failed_count} failed / {batch.on_hold_count} on-hold), "
            f"{PayslipDistribution.objects.filter(tenant=tenant).count()} distributions, "
            f"1 reconciliation ({recon.number}, {recon.get_status_display()})."))

    def _seed_goals(self, tenant, *, flush):
        """3.18 Goal Setting — an active + a closed GoalPeriod, a 3-level Objective cascade
        (company → department → individual) reusing existing EmployeeProfile owners + a
        core.OrgUnit department, KeyResults with mixed metric_types/weights tuned to a spread of
        health states (on_track / at_risk / off_track), and staggered GoalCheckIns. Reuses seeded
        employees/departments — creates no new person/org rows. Runs after _seed_payout."""
        if flush:
            # Children first: check-ins → key results → objectives → periods.
            GoalCheckIn.objects.filter(tenant=tenant).delete()
            KeyResult.objects.filter(tenant=tenant).delete()
            Objective.objects.filter(tenant=tenant).delete()
            GoalPeriod.objects.filter(tenant=tenant).delete()
        if GoalPeriod.objects.filter(tenant=tenant).exists():
            self.stdout.write(self.style.NOTICE(
                f"Goal-setting data already exists for '{tenant.name}'. Use --flush to re-seed."))
            return

        emps = list(EmployeeProfile.objects.filter(tenant=tenant)
                    .select_related("party", "employment").order_by("party__name"))
        if len(emps) < 2:
            self.stdout.write(self.style.NOTICE(
                f"Not enough employees for '{tenant.name}' — skipping goal-setting seed."))
            return

        def emp(i):
            return emps[i % len(emps)]

        dept = OrgUnit.objects.filter(tenant=tenant, kind="department").order_by("name").first()
        today = timezone.localdate()
        td = datetime.timedelta
        # Active period ~50% elapsed (so the derived health spread is meaningful), plus a prior closed one.
        active = GoalPeriod.objects.create(
            tenant=tenant, name="Current Half-Year Cycle", period_type="half_yearly",
            start_date=today - td(days=90), end_date=today + td(days=90), status="active",
            description="The in-flight OKR cycle for the organization.")
        GoalPeriod.objects.create(
            tenant=tenant, name="Previous Quarter Cycle", period_type="quarterly",
            start_date=today - td(days=270), end_date=today - td(days=91), status="closed",
            description="A wrapped-up prior cycle, kept for history.")

        # --- Objective cascade: 1 company → 2 department → 2 individual ---
        comp = Objective.objects.create(
            tenant=tenant, title="Grow ARR to $2M and delight customers", owner=emp(0),
            goal_period=active, scope="company", target_type="committed", status="active", weight=100,
            description="The north-star company objective this cycle.")
        dept1 = Objective.objects.create(
            tenant=tenant, title="Ship the v2 platform", owner=emp(1), goal_period=active,
            parent_objective=comp, department=dept, scope="department", target_type="committed",
            status="active", weight=60)
        dept2 = Objective.objects.create(
            tenant=tenant, title="Scale go-to-market", owner=emp(2), goal_period=active,
            parent_objective=comp, department=dept, scope="department", target_type="aspirational",
            status="active", weight=40)
        ind1 = Objective.objects.create(
            tenant=tenant, title="Close 10 enterprise deals", owner=emp(2), goal_period=active,
            parent_objective=dept2, scope="individual", target_type="committed", status="active", weight=100)
        ind2 = Objective.objects.create(
            tenant=tenant, title="Reduce onboarding time", owner=emp(3), goal_period=active,
            parent_objective=dept1, scope="individual", target_type="committed", status="active", weight=100)

        D = Decimal
        # (objective, [(title, metric_type, start, target, current, unit, weight, status), ...])
        # current values are tuned so each objective lands in a distinct health band vs. ~50% elapsed.
        KRS = {
            comp: [  # ~60% → on_track
                ("ARR reaches $2M", "currency", D("1200000"), D("2000000"), D("1680000"), "$", D("50"), "in_progress"),
                ("Lift NPS to 60", "numeric", D("45"), D("60"), D("54"), "pts", D("30"), "in_progress"),
                ("Flagship feature launch progress", "percentage", D("0"), D("100"), D("60"), "%", D("20"), "in_progress"),
            ],
            dept1: [  # ~28% → at_risk
                ("Migrate 100 customers to v2", "numeric", D("0"), D("100"), D("40"), "customers", D("70"), "in_progress"),
                ("Pass the v2 security audit", "boolean", None, None, D("0"), "", D("30"), "not_started"),
            ],
            dept2: [  # ~60% → on_track
                ("Build $5M qualified pipeline", "currency", D("1000000"), D("5000000"), D("3400000"), "$", D("50"), "in_progress"),
                ("Raise win rate to 30%", "percentage", D("18"), D("30"), D("25.2"), "%", D("50"), "in_progress"),
            ],
            ind1: [  # ~15% → off_track
                ("Sign 10 enterprise logos", "numeric", D("0"), D("10"), D("1.5"), "deals", D("100"), "in_progress"),
            ],
            ind2: [  # ~78% → on_track (milestone done + fast time-to-value)
                ("Publish the onboarding runbook", "milestone", None, None, None, "", D("40"), "completed"),
                ("Cut time-to-value under 14 days", "numeric", D("30"), D("14"), D("20"), "days", D("60"), "in_progress"),
            ],
        }

        kr_total = ci_total = 0
        for objective, rows in KRS.items():
            for title, mtype, start, target, current, unit, weight, status in rows:
                kr = KeyResult.objects.create(
                    tenant=tenant, objective=objective, title=title, metric_type=mtype,
                    start_value=start, target_value=target, current_value=current, unit=unit,
                    weight=weight, status=status,
                    is_milestone_event=(mtype == "milestone"))
                kr_total += 1
                # Two staggered check-ins; the LATEST reports `current` so save() leaves
                # current_value consistent with the intended health band above.
                confidence = "on_track" if objective in (comp, dept2, ind2) else (
                    "at_risk" if objective is dept1 else "off_track")
                if current is not None:
                    GoalCheckIn.objects.create(
                        tenant=tenant, key_result=kr, created_by=objective.owner,
                        checkin_date=today - td(days=45), value_at_checkin=(current / 2).quantize(D("0.01")),
                        confidence="at_risk", comment="Mid-cycle progress — ramping up.")
                    GoalCheckIn.objects.create(
                        tenant=tenant, key_result=kr, created_by=objective.owner,
                        checkin_date=today - td(days=7), value_at_checkin=current, confidence=confidence,
                        comment="Latest weekly update.")
                    ci_total += 2
                else:
                    GoalCheckIn.objects.create(
                        tenant=tenant, key_result=kr, created_by=objective.owner,
                        checkin_date=today - td(days=7), value_at_checkin=None, confidence=confidence,
                        is_milestone_event=(mtype == "milestone"),
                        comment="Milestone completed." if status == "completed" else "Qualitative check-in.")
                    ci_total += 1

        self.stdout.write(self.style.SUCCESS(
            f"Goal setting seeded for '{tenant.name}': "
            f"{GoalPeriod.objects.filter(tenant=tenant).count()} periods, "
            f"{Objective.objects.filter(tenant=tenant).count()} objectives (3-level cascade), "
            f"{kr_total} key results, {ci_total} check-ins."))

    def _seed_reviews(self, tenant, *, flush):
        """3.19 Performance Review — 1 ReviewCycle (mid-phase, linked to the 3.18 active GoalPeriod),
        3 ReviewTemplates (self/manager/peer), and PerformanceReviews across self/manager/peer for a
        few employees with varied statuses + ReviewRating lines (spread ratings so the derived
        overall_rating and the calibrated-override case both show). Reuses seeded EmployeeProfiles +
        the 3.18 GoalPeriod — creates no new person/period rows. Runs after _seed_goals."""
        if flush:
            ReviewRating.objects.filter(tenant=tenant).delete()
            PerformanceReview.objects.filter(tenant=tenant).delete()
            ReviewCycle.objects.filter(tenant=tenant).delete()
            ReviewTemplate.objects.filter(tenant=tenant).delete()
        if ReviewCycle.objects.filter(tenant=tenant).exists():
            self.stdout.write(self.style.NOTICE(
                f"Performance-review data already exists for '{tenant.name}'. Use --flush to re-seed."))
            return

        emps = list(EmployeeProfile.objects.filter(tenant=tenant)
                    .select_related("party", "employment").order_by("party__name"))
        if len(emps) < 2:
            self.stdout.write(self.style.NOTICE(
                f"Not enough employees for '{tenant.name}' — skipping performance-review seed."))
            return

        def emp(i):
            return emps[i % len(emps)]

        def manager_profile_of(subject):
            mp = subject.manager  # a core.Party or None (derived off employment)
            return getattr(mp, "employee_profile", None) if mp is not None else None

        today = timezone.localdate()
        td = datetime.timedelta
        active_gp = GoalPeriod.objects.filter(tenant=tenant, status="active").first()

        cycle = ReviewCycle.objects.create(
            tenant=tenant, name="H1 Performance Review", cycle_type="half_yearly",
            status="manager_review", goal_period=active_gp,
            self_review_start=today - td(days=40), self_review_end=today - td(days=20),
            manager_review_start=today - td(days=19), manager_review_end=today + td(days=5),
            calibration_date=today + td(days=12), results_release_date=today + td(days=20),
            description="Mid-year performance review cycle.")

        # --- 3 templates: self + manager (goal-aware), peer (anonymous) ---
        t_self = ReviewTemplate.objects.create(
            tenant=tenant, name="Self-Assessment", review_type="self", rating_scale_max=5,
            include_goals=True, is_anonymous=False, description="Employee self-evaluation.")
        t_mgr = ReviewTemplate.objects.create(
            tenant=tenant, name="Manager Review", review_type="manager", rating_scale_max=5,
            include_goals=True, is_anonymous=False, description="Manager evaluation of the employee.")
        t_peer = ReviewTemplate.objects.create(
            tenant=tenant, name="Peer Feedback", review_type="peer", rating_scale_max=5,
            include_goals=False, is_anonymous=True, description="Anonymous peer feedback.")

        D = Decimal
        # (title, category, rating, weight) triples reused per review; ratings spread, weights sum ~100.
        RATING_SETS = {
            "high": [("Delivers quality work", "competency", D("4.5"), D("40")),
                     ("Collaboration", "competency", D("4.0"), D("30")),
                     ("Goal achievement", "goal", D("4.0"), D("30"))],
            "mid": [("Delivers quality work", "competency", D("3.5"), D("40")),
                    ("Collaboration", "competency", D("3.0"), D("30")),
                    ("Goal achievement", "goal", D("3.5"), D("30"))],
        }

        def add_ratings(review, key):
            for label, cat, val, wt in RATING_SETS[key]:
                ReviewRating.objects.create(
                    tenant=tenant, review=review, criterion_label=label, criterion_category=cat,
                    rating_value=val, weight=wt, comment="")

        reviews_made = 0
        # 1) Self review (subject == reviewer), submitted.
        subj0 = emp(1)
        r_self = PerformanceReview.objects.create(
            tenant=tenant, cycle=cycle, template=t_self, subject=subj0, reviewer=subj0,
            review_type="self", status="submitted", submitted_at=timezone.now(),
            strengths="Shipped the v2 migration ahead of schedule.",
            improvements="Want to grow cross-team influence.")
        add_ratings(r_self, "high")
        reviews_made += 1

        # 2) Manager review of subj0 — shared, manager_rating snapshotted.
        mgr0 = manager_profile_of(subj0) or emp(0)
        if mgr0.pk == subj0.pk:
            mgr0 = emp(0) if emp(0).pk != subj0.pk else emp(2)
        r_mgr = PerformanceReview.objects.create(
            tenant=tenant, cycle=cycle, template=t_mgr, subject=subj0, reviewer=mgr0,
            review_type="manager", status="shared", submitted_at=timezone.now(),
            shared_at=timezone.now(), strengths="Strong technical delivery.",
            improvements="Delegate more.")
        add_ratings(r_mgr, "high")
        r_mgr.manager_rating = r_mgr.overall_rating  # snapshot the as-submitted rating
        r_mgr.save(update_fields=["manager_rating"])
        reviews_made += 1

        # 3) Manager review of another employee — acknowledged + calibrated (override differs from overall).
        subj1 = emp(2) if emp(2).pk != subj0.pk else emp(3)
        mgr1 = manager_profile_of(subj1) or emp(0)
        if mgr1.pk == subj1.pk:
            mgr1 = emp(0) if emp(0).pk != subj1.pk else emp(1)
        r_mgr2 = PerformanceReview.objects.create(
            tenant=tenant, cycle=cycle, template=t_mgr, subject=subj1, reviewer=mgr1,
            review_type="manager", status="acknowledged", submitted_at=timezone.now(),
            shared_at=timezone.now(), acknowledged_at=timezone.now(), acknowledged_by=subj1,
            strengths="Reliable and consistent.", improvements="Stretch goals for next cycle.")
        add_ratings(r_mgr2, "mid")
        r_mgr2.manager_rating = r_mgr2.overall_rating
        r_mgr2.calibrated_rating = (r_mgr2.overall_rating or D("3")) - D("0.5")  # calibrated down
        r_mgr2.potential_rating = D("4")
        r_mgr2.calibration_notes = "Adjusted for cross-team consistency."
        r_mgr2.save(update_fields=["manager_rating", "calibrated_rating", "potential_rating", "calibration_notes"])
        reviews_made += 1

        # 4) Anonymous peer review of subj0.
        peer0 = emp(3) if emp(3).pk not in (subj0.pk, mgr0.pk) else emp(4)
        if peer0.pk == subj0.pk:
            peer0 = emp(0)
        r_peer = PerformanceReview.objects.create(
            tenant=tenant, cycle=cycle, template=t_peer, subject=subj0, reviewer=peer0,
            review_type="peer", status="submitted", is_anonymous=True, submitted_at=timezone.now(),
            strengths="Great to pair with.", improvements="Sometimes takes on too much.")
        add_ratings(r_peer, "mid")
        reviews_made += 1

        self.stdout.write(self.style.SUCCESS(
            f"Performance review seeded for '{tenant.name}': 1 cycle ({cycle.name}, {cycle.get_status_display()}), "
            f"{ReviewTemplate.objects.filter(tenant=tenant).count()} templates, "
            f"{reviews_made} reviews (self/manager/peer, incl. 1 calibrated), "
            f"{ReviewRating.objects.filter(tenant=tenant).count()} rating lines."))

    def _seed_feedback(self, tenant, *, flush):
        """3.20 Continuous Feedback — a small KudosBadge catalog, real-time Feedback rows spanning
        types/visibility/status (incl. an anonymous one, a goal-linked one, a review-linked one, and
        a request→response pair demonstrating the pull workflow), and 2 OneOnOneMeetings (one
        completed with shared + private notes and 2 action items, one upcoming). Reuses seeded
        EmployeeProfiles + a 3.18 Objective + a 3.19 PerformanceReview — creates no new person rows.
        Runs after _seed_reviews."""
        if flush:
            MeetingActionItem.objects.filter(tenant=tenant).delete()
            OneOnOneMeeting.objects.filter(tenant=tenant).delete()
            Feedback.objects.filter(tenant=tenant).delete()
            KudosBadge.objects.filter(tenant=tenant).delete()
        if (Feedback.objects.filter(tenant=tenant).exists()
                or KudosBadge.objects.filter(tenant=tenant).exists()):
            self.stdout.write(self.style.NOTICE(
                f"Continuous-feedback data already exists for '{tenant.name}'. Use --flush to re-seed."))
            return

        emps = list(EmployeeProfile.objects.filter(tenant=tenant)
                    .select_related("party", "employment").order_by("party__name"))
        if len(emps) < 3:
            # Anonymous + request/response demos need ≥3 distinct people to be meaningful.
            self.stdout.write(self.style.NOTICE(
                f"Not enough employees for '{tenant.name}' — skipping continuous-feedback seed."))
            return

        def emp(i):
            return emps[i % len(emps)]

        def manager_profile_of(subject):
            mp = subject.manager  # a core.Party or None (derived off employment)
            return getattr(mp, "employee_profile", None) if mp is not None else None

        now = timezone.now()
        td = datetime.timedelta
        today = timezone.localdate()

        # --- KudosBadge catalog (recognition tags; icon = a Lucide icon name) ---
        BADGES = [
            ("Team Player", "Goes out of the way to help teammates.", "handshake", "#2563eb", "Collaboration"),
            ("Above & Beyond", "Delivered well beyond expectations.", "rocket", "#16a34a", "Excellence"),
            ("Customer Hero", "Delighted a customer.", "star", "#f59e0b", "Customer First"),
            ("Innovator", "Brought a creative new idea to life.", "lightbulb", "#7c3aed", "Innovation"),
        ]
        badges = {}
        for name, desc, icon, color, value in BADGES:
            badges[name] = KudosBadge.objects.create(
                tenant=tenant, name=name, description=desc, icon=icon, color=color, linked_value=value)

        obj0 = Objective.objects.filter(tenant=tenant).order_by("title").first()
        review0 = PerformanceReview.objects.filter(tenant=tenant).order_by("number").first()

        a, b, c, d = emp(0), emp(1), emp(2), emp(3)
        fb_made = 0
        # 1) Public kudos with a badge.
        Feedback.objects.create(
            tenant=tenant, giver=a, receiver=b, feedback_type="kudos", visibility="public",
            status="given", badge=badges["Team Player"],
            message="Thanks for jumping in on the release — you saved the day!")
        fb_made += 1
        # 2) Private constructive feedback.
        Feedback.objects.create(
            tenant=tenant, giver=b, receiver=c, feedback_type="constructive", visibility="private",
            status="given",
            message="Consider looping in QA earlier next sprint so we catch edge cases sooner.")
        fb_made += 1
        # 3) Team-visibility appreciation, acknowledged, goal-linked, badged.
        Feedback.objects.create(
            tenant=tenant, giver=c, receiver=a, feedback_type="appreciation", visibility="team",
            status="acknowledged", acknowledged_at=now, badge=badges["Above & Beyond"],
            related_objective=obj0,
            message="Your mentoring this quarter really lifted the whole team.")
        fb_made += 1
        # 4) Anonymous public feedback (giver masked on read for non-admins).
        Feedback.objects.create(
            tenant=tenant, giver=d, receiver=b, feedback_type="appreciation", visibility="public",
            status="given", is_anonymous=True,
            message="Really appreciate how calm and clear you are under pressure.")
        fb_made += 1
        # 5) Review-linked feedback (only when the review subject isn't the giver — no self-feedback).
        if review0 is not None and review0.subject_id != a.pk:
            Feedback.objects.create(
                tenant=tenant, giver=a, receiver=review0.subject, feedback_type="appreciation",
                visibility="private", status="given", related_review=review0,
                message="Following up on your review — great progress on the growth goals.")
            fb_made += 1
        # 6) Request → response pair (the pull workflow: a asks c; c responds, linked via requested_from).
        ask = Feedback.objects.create(
            tenant=tenant, giver=a, receiver=c, feedback_type="request", visibility="private",
            status="requested",
            message="Could you share feedback on how the Q2 launch went from your side?")
        fb_made += 1
        Feedback.objects.create(
            tenant=tenant, giver=c, receiver=a, feedback_type="appreciation", visibility="private",
            status="given", requested_from=ask,
            message="Happy to! The launch was smooth — your cross-team coordination was the highlight.")
        fb_made += 1

        # --- 1:1 meetings (manager↔employee, distinct people) ---
        mgr = manager_profile_of(b) or a
        if mgr.pk == b.pk:
            mgr = a if a.pk != b.pk else c
        m1 = OneOnOneMeeting.objects.create(
            tenant=tenant, manager=mgr, employee=b, scheduled_at=now - td(days=7),
            status="completed", completed_at=now - td(days=7),
            agenda="Q2 retro; growth goals; current blockers.",
            shared_notes="Discussed the launch retro and agreed on two focus areas for Q3.",
            manager_private_notes="Flight risk is low; ready for a stretch project next quarter.",
            related_objective=obj0)
        MeetingActionItem.objects.create(
            tenant=tenant, meeting=m1, description="Draft the Q3 stretch-project proposal.",
            owner=b, due_date=today + td(days=7), status="open")
        MeetingActionItem.objects.create(
            tenant=tenant, meeting=m1, description="Share the launch retro notes with the team.",
            owner=mgr, due_date=today - td(days=2), status="done", completed_at=now - td(days=3))
        OneOnOneMeeting.objects.create(
            tenant=tenant, manager=mgr, employee=b, scheduled_at=now + td(days=7),
            status="scheduled", agenda="Career-path check-in; feedback follow-ups.")

        self.stdout.write(self.style.SUCCESS(
            f"Continuous feedback seeded for '{tenant.name}': "
            f"{KudosBadge.objects.filter(tenant=tenant).count()} badges, "
            f"{fb_made} feedback items (kudos/appreciation/constructive/request, incl. 1 anonymous + a "
            f"request/response pair), "
            f"{OneOnOneMeeting.objects.filter(tenant=tenant).count()} 1:1 meetings, "
            f"{MeetingActionItem.objects.filter(tenant=tenant).count()} action items."))

    def _seed_improvement(self, tenant, *, flush):
        """3.21 Performance Improvement — the corrective-action layer (runs LAST, after _seed_feedback).
        2 PIPs (one active with check-ins, one closed-successful that cites the subject's review),
        progressive warning letters, and manager-only coaching notes. Reuses existing EmployeeProfiles +
        a 3.19 PerformanceReview — creates no new person rows. (ASCII-only stdout — see the 3.20 cp1252
        console bug.)"""
        if flush:
            CoachingNote.objects.filter(tenant=tenant).delete()
            WarningLetter.objects.filter(tenant=tenant).delete()
            PIPCheckIn.objects.filter(tenant=tenant).delete()
            PerformanceImprovementPlan.objects.filter(tenant=tenant).delete()
        if (PerformanceImprovementPlan.objects.filter(tenant=tenant).exists()
                or WarningLetter.objects.filter(tenant=tenant).exists()):
            self.stdout.write(self.style.NOTICE(
                f"Performance-improvement data already exists for '{tenant.name}'. Use --flush to re-seed."))
            return

        emps = list(EmployeeProfile.objects.filter(tenant=tenant)
                    .select_related("party").order_by("party__name"))
        if len(emps) < 3:
            self.stdout.write(self.style.NOTICE(
                f"Not enough employees for '{tenant.name}' — skipping performance-improvement seed."))
            return

        now = timezone.now()
        today = timezone.localdate()
        td = datetime.timedelta
        subj_a, mgr, subj_c = emps[0], emps[1], emps[2]   # distinct (len >= 3); mgr != either subject

        def review_for(profile):
            return PerformanceReview.objects.filter(tenant=tenant, subject=profile).order_by("number").first()

        # --- PIP 1: active, HR-approved, acknowledged, with 2 check-ins ---
        pip1 = PerformanceImprovementPlan.objects.create(
            tenant=tenant, subject=subj_a, manager=mgr, triggering_review=review_for(subj_a),
            status="active", start_date=today - td(days=20), end_date=today + td(days=40),
            hr_approved_at=now - td(days=20), hr_approved_by=mgr,
            acknowledged_at=now - td(days=19), acknowledged_by=subj_a,
            performance_issue="Consistently missing sprint commitments over the last two cycles.",
            expected_standards="Deliver committed sprint scope; flag blockers within 24 hours.",
            improvement_goals="Meet 90% of committed story points for two consecutive sprints.",
            support_provided="Weekly 1:1 coaching, a senior mentor, and a focused-work time block.",
            measurement_criteria="Sprint burndown plus peer-review feedback at each check-in.")
        PIPCheckIn.objects.create(
            tenant=tenant, pip=pip1, checkin_date=today - td(days=6), completed_at=now - td(days=6),
            progress_rating="at_risk", progress_notes="Improving, but still behind on the migration task.")
        PIPCheckIn.objects.create(
            tenant=tenant, pip=pip1, checkin_date=today + td(days=8), progress_rating="on_track",
            progress_notes="Scheduled mid-plan review.")

        # --- PIP 2: closed successful, cites the subject's review ---
        PerformanceImprovementPlan.objects.create(
            tenant=tenant, subject=subj_c, manager=mgr, triggering_review=review_for(subj_c),
            status="closed", outcome="successful", outcome_date=today - td(days=2),
            outcome_notes="Met all improvement goals; plan closed successfully.",
            start_date=today - td(days=95), end_date=today - td(days=5),
            hr_approved_at=now - td(days=95), hr_approved_by=mgr,
            acknowledged_at=now - td(days=94), acknowledged_by=subj_c,
            performance_issue="Quality gaps in customer-facing deliverables.",
            expected_standards="Zero critical defects in released work.",
            improvement_goals="Pass QA on first submission for 8 consecutive deliverables.",
            support_provided="Pairing with QA, a review checklist, and targeted training.",
            measurement_criteria="Defect-escape rate per release.")

        # --- Warning letters (progressive discipline) ---
        WarningLetter.objects.create(
            tenant=tenant, issued_to=subj_a, issued_by=mgr, level="verbal", category="attendance",
            incident_date=today - td(days=30), status="acknowledged",
            acknowledged_at=now - td(days=28), acknowledged_by=subj_a,
            description="Repeated late arrivals (3 occasions in one week) without prior notice.",
            policy_reference="Attendance Policy 4.2",
            employee_response="Acknowledged; commuting issue now resolved.",
            expiry_date=today + td(days=150))
        WarningLetter.objects.create(
            tenant=tenant, issued_to=subj_a, issued_by=mgr, level="written", category="performance",
            incident_date=today - td(days=10), status="issued", related_pip=pip1,
            description="Continued failure to meet sprint commitments despite the active improvement plan.",
            policy_reference="Performance Policy 6.1", expiry_date=today + td(days=180))
        WarningLetter.objects.create(
            tenant=tenant, issued_to=subj_c, issued_by=mgr, level="verbal", category="conduct",
            incident_date=today - td(days=60), status="acknowledged",
            acknowledged_at=now - td(days=58), acknowledged_by=subj_c,
            description="Unprofessional tone in a shared team channel.",
            policy_reference="Code of Conduct 2.3", expiry_date=today - td(days=1))  # past expiry (is_expired demo)

        # --- Coaching notes (coach/admin only — NEVER the coached employee) ---
        CoachingNote.objects.create(
            tenant=tenant, coach=mgr, employee=subj_a, related_pip=pip1, note_date=today - td(days=6),
            category="skill_development",
            content="Private note: struggles to break large tasks down; pairing them with a mentor for estimation.")
        CoachingNote.objects.create(
            tenant=tenant, coach=mgr, employee=subj_c, note_date=today - td(days=40), category="behavior",
            content="Private note: strong turnaround this quarter; consider for a stretch assignment next cycle.")

        self.stdout.write(self.style.SUCCESS(
            f"Performance improvement seeded for '{tenant.name}': "
            f"{PerformanceImprovementPlan.objects.filter(tenant=tenant).count()} PIPs (1 active + check-ins, 1 closed), "
            f"{PIPCheckIn.objects.filter(tenant=tenant).count()} check-ins, "
            f"{WarningLetter.objects.filter(tenant=tenant).count()} warning letters, "
            f"{CoachingNote.objects.filter(tenant=tenant).count()} coaching notes."))

    def _seed_training(self, tenant, *, flush):
        """3.22 Training Management - the ILT catalog + scheduled occurrences (runs after
        _seed_improvement). 3 courses (an internal classroom onboarding bootcamp, a safety
        certification, and an external leadership program that requires the bootcamp) + 4 sessions
        spanning classroom / virtual / external delivery and multiple statuses (incl. one extra
        classroom on a distinct instructor+venue+day to show the overlap guard doesn't false-positive
        on legitimate scheduling). Reuses existing EmployeeProfile instructors, an existing vendor-role
        Party, and an existing accounting.Currency - creates NO new person/vendor/currency rows.
        (ASCII-only stdout - Windows cp1252 console bug, see 3.20/3.21.)"""
        if flush:
            TrainingSession.objects.filter(tenant=tenant).delete()
            TrainingCourse.objects.filter(tenant=tenant).delete()
        if TrainingCourse.objects.filter(tenant=tenant).exists():
            self.stdout.write(self.style.NOTICE(
                f"Training data already exists for '{tenant.name}'. Use --flush to re-seed."))
            return

        emps = list(EmployeeProfile.objects.filter(tenant=tenant)
                    .select_related("party").order_by("party__name"))
        if len(emps) < 2:
            self.stdout.write(self.style.NOTICE(
                f"Not enough employees for '{tenant.name}' - skipping training seed."))
            return
        instructor_a, instructor_b = emps[0], emps[1]
        vendor = Party.objects.filter(tenant=tenant, roles__role="vendor").first()
        from apps.accounting.models import Currency   # lazy - global master, no tenant FK
        currency = Currency.objects.filter(code="USD").first() or Currency.objects.first()

        # --- Courses (catalog) ---
        bootcamp = TrainingCourse.objects.create(
            tenant=tenant, title="Technical Onboarding Bootcamp", category="onboarding",
            delivery_mode="classroom", provider_type="internal", duration_hours=Decimal("16.00"),
            default_capacity=25,
            description="A two-day hands-on introduction to the engineering stack, tools, and workflows.")
        safety = TrainingCourse.objects.create(
            tenant=tenant, title="Workplace Safety Certification", category="safety",
            delivery_mode="classroom", provider_type="internal", duration_hours=Decimal("8.00"),
            is_certification=True, certification_name="Certified Safety Associate",
            certification_validity_months=24, default_capacity=30,
            description="Mandatory workplace health-and-safety training with a certification exam.")
        leadership = TrainingCourse.objects.create(
            tenant=tenant, title="Leadership Excellence Program", category="leadership",
            delivery_mode="external", provider_type="external", duration_hours=Decimal("24.00"),
            prerequisite_course=bootcamp, default_capacity=15,
            description="An external facilitator-led program for emerging managers (bootcamp required first).")

        now = timezone.now()

        def at(days, hour):
            return (now + datetime.timedelta(days=days)).replace(hour=hour, minute=0, second=0, microsecond=0)

        # --- Sessions (classroom / virtual / external, mixed statuses) ---
        TrainingSession.objects.create(
            tenant=tenant, course=bootcamp, delivery_mode="classroom", status="scheduled",
            start_datetime=at(7, 9), end_datetime=at(7, 17), capacity=25,
            venue_name="HQ Training Room A", venue_address="Head Office, 2nd Floor",
            instructor_employee=instructor_a, notes="Day 1 of the onboarding bootcamp.")
        TrainingSession.objects.create(
            tenant=tenant, course=safety, delivery_mode="virtual", status="confirmed",
            start_datetime=at(10, 10), end_datetime=at(10, 12), capacity=30,
            meeting_platform="zoom", meeting_link="https://example.zoom.us/j/1234567890",
            meeting_id="123 456 7890", instructor_employee=instructor_b,
            notes="Live virtual safety briefing.")
        TrainingSession.objects.create(
            tenant=tenant, course=leadership, delivery_mode="external", status="completed",
            start_datetime=at(-20, 9), end_datetime=at(-20, 16), capacity=15,
            external_vendor=vendor, external_instructor_name="" if vendor else "Guest Facilitator",
            estimated_cost=Decimal("5000.00"), actual_cost=Decimal("5200.00"), currency=currency,
            invoice_reference="INV-TRN-0001",
            notes="Off-site leadership workshop delivered by an external provider.")
        TrainingSession.objects.create(
            tenant=tenant, course=bootcamp, delivery_mode="classroom", status="scheduled",
            start_datetime=at(14, 9), end_datetime=at(14, 17), capacity=25,
            venue_name="HQ Training Room B", venue_address="Head Office, 3rd Floor",
            instructor_employee=instructor_b,
            notes="Repeat cohort - distinct room/instructor/day (no scheduling conflict).")

        self.stdout.write(self.style.SUCCESS(
            f"Training seeded for '{tenant.name}': "
            f"{TrainingCourse.objects.filter(tenant=tenant).count()} courses, "
            f"{TrainingSession.objects.filter(tenant=tenant).count()} sessions (classroom/virtual/external)."))
