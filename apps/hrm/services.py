"""HRM domain services — request-free business logic shared by views, the seeder, and tests.

Keeping this out of ``views.py`` lets the management command (and tests) call it without importing
the view layer (a layering violation). Pure model logic only; no request/response coupling.
"""
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from .models import (
    ZERO,
    AssetAllocation,
    ClearanceItem,
    LeaveAllocation,
    OnboardingTask,
)


def generate_tasks_from_template(program):
    """Create concrete ``OnboardingTask`` rows from the program's template task lines, each with
    ``due_date = program.start_date + due_offset_days``. Idempotent — ``get_or_create`` keyed on the
    task title means re-running never duplicates an existing task. Returns the count of newly-created
    tasks.

    NOTE (known limitation): renaming a template task after generation and re-running creates a new
    task rather than renaming the old one (the old title lingers). Acceptable for this pass — regen
    is meant to *add* newly-introduced template tasks, not reconcile renames.
    """
    if not program.template_id:
        return 0
    template_tasks = list(program.template.template_tasks.order_by("phase", "order", "title"))
    if not template_tasks:
        return 0
    # One SELECT for the titles already present, then one bulk INSERT — keeps the idempotency
    # contract (title-keyed) while avoiding the 2N queries a per-row get_or_create would run.
    existing = set(OnboardingTask.objects.filter(tenant=program.tenant, program=program)
                   .values_list("title", flat=True))
    to_create = []
    for tt in template_tasks:
        if tt.title in existing:
            continue
        due = program.start_date + timedelta(days=tt.due_offset_days) if program.start_date else None
        to_create.append(OnboardingTask(
            tenant=program.tenant, program=program, title=tt.title,
            description=tt.description, task_category=tt.task_category,
            assignee_role=tt.assignee_role, due_date=due, phase=tt.phase,
            is_mandatory=tt.is_mandatory, order=tt.order))
    if to_create:
        OnboardingTask.objects.bulk_create(to_create)
    return len(to_create)


# --------------------------------------------------------------------------- 3.4 Offboarding

# Default department clearance lines for a separation case:
#   (department, description, is_mandatory_resolver). ``is_mandatory_resolver`` is either a bool or
#   the string "requires_kt" (resolved from the case). The IT line additionally gets linked to one
#   of the employee's still-issued assets.
_CLEARANCE_LINES = [
    ("it", "Return IT equipment and revoke system access", True),
    ("hr", "Complete HR exit formalities and documentation", True),
    ("finance", "Clear outstanding dues and expense claims", True),
    ("admin", "Return admin assets (ID/access card, SIM, vehicle)", False),
    ("manager", "Complete knowledge transfer to the team", "requires_kt"),
    ("legal", "Sign NDA / non-compete acknowledgment", False),
]


def generate_clearance_checklist(case):
    """Create the standard department clearance lines for a ``SeparationCase``. Idempotent — keyed on
    ``(department, description)``, re-running never duplicates an existing line. The IT line is linked
    to one of the employee's still-issued ``AssetAllocation`` rows (if any) so that marking it cleared
    also returns that asset. Returns the count of newly-created lines.

    Shared by ``views.separationcase_approve`` and the seeder so both build the same checklist.
    """
    existing = set(ClearanceItem.objects.filter(tenant=case.tenant, case=case)
                   .values_list("department", "description"))
    # One currently-issued asset to attach to the IT line (laptop/desktop/phone/access first).
    issued_asset = (AssetAllocation.objects
                    .filter(tenant=case.tenant, employee=case.employee, status="issued")
                    .order_by("asset_category", "-issued_at").first())
    to_create = []
    for dept, desc, mandatory in _CLEARANCE_LINES:
        if (dept, desc) in existing:
            continue
        is_mandatory = case.requires_kt if mandatory == "requires_kt" else bool(mandatory)
        to_create.append(ClearanceItem(
            tenant=case.tenant, case=case, department=dept, description=desc,
            is_mandatory=is_mandatory,
            asset_allocation=issued_asset if dept == "it" else None))
    if to_create:
        ClearanceItem.objects.bulk_create(to_create)
    return len(to_create)


def compute_leave_encashment(employee):
    """Best-effort leave encashment for an offboarding employee. Sums the *balance* of the employee's
    active, encashable leave allocations for the current year and values it at ``basic_salary / 30``
    per day, where ``basic_salary`` is taken from the designation's minimum salary band (until a
    dedicated salary-structure module exists). Returns ``(days, amount)`` as ``Decimal``s.

    NOTE: ``basic_salary`` is an approximation — replace with the real CTC basic component once the
    salary-structure sub-module (3.13) lands.
    """
    year = timezone.localdate().year
    allocations = (LeaveAllocation.objects
                   .filter(tenant=employee.tenant, employee=employee, year=year,
                           status="active", leave_type__encashable=True)
                   .select_related("leave_type"))
    days = ZERO
    for alloc in allocations:
        bal = alloc.balance  # derived (allocated − used); only positive balances are encashed
        if bal and bal > ZERO:
            days += bal
    basic_salary = ZERO
    if employee.designation_id and employee.designation and employee.designation.min_salary:
        basic_salary = employee.designation.min_salary
    amount = ((days * (basic_salary / Decimal("30"))).quantize(Decimal("0.01"))
              if basic_salary else ZERO)
    return days, amount
