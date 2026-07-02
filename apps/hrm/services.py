"""HRM domain services — request-free business logic shared by views, the seeder, and tests.

Keeping this out of ``views.py`` lets the management command (and tests) call it without importing
the view layer (a layering violation). Pure model logic only; no request/response coupling.
"""
from datetime import timedelta
from decimal import Decimal

from django.db.models import DecimalField, OuterRef, Subquery, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from .models import (
    ZERO,
    AssetAllocation,
    ClearanceItem,
    LeaveAllocation,
    LeaveRequest,
    OfferApproval,
    OnboardingTask,
    PreboardingItem,
    RequisitionApproval,
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
    # Push the per-allocation "approved days used" aggregate into one correlated subquery so the whole
    # computation is a single SQL pass (mirrors hrm.views._used_days_subquery; inlined here to avoid a
    # services->views import). Using ``alloc.balance`` in the loop would instead fire one aggregate per
    # encashable allocation (N+1).
    _dec = DecimalField(max_digits=7, decimal_places=2)
    used_subq = (LeaveRequest.objects
                 .filter(tenant=OuterRef("tenant"), employee=OuterRef("employee"),
                         leave_type=OuterRef("leave_type"), status="approved",
                         start_date__year=OuterRef("year"))
                 .values("employee").annotate(s=Sum("days")).values("s"))
    allocations = (LeaveAllocation.objects
                   .filter(tenant=employee.tenant, employee=employee, year=year,
                           status="active", leave_type__encashable=True)
                   .annotate(used_db=Coalesce(Subquery(used_subq, output_field=_dec),
                                              Decimal("0"), output_field=_dec)))
    days = ZERO
    for alloc in allocations:
        # Net out days already cashed out via an approved LeaveEncashment (3.10) so the final
        # settlement doesn't pay the same balance twice.
        bal = (alloc.allocated_days or ZERO) - alloc.used_db - (alloc.encashed_days or ZERO)
        if bal > ZERO:
            days += bal
    basic_salary = ZERO
    if employee.designation_id and employee.designation and employee.designation.min_salary:
        basic_salary = employee.designation.min_salary
    amount = ((days * (basic_salary / Decimal("30"))).quantize(Decimal("0.01"))
              if basic_salary else ZERO)
    return days, amount


# --------------------------------------------------------------------------- 3.5 Job Requisition

# Default sequential approval chain raised for a requisition on submission when no steps were
# added manually: (step_order, approver_role). Approver is left null (assigned later / overridden
# by a tenant admin). Mirrors the ``generate_clearance_checklist`` idempotency contract.
_DEFAULT_APPROVAL_CHAIN = [
    (1, "hr"),
    (2, "executive"),
]


def generate_approval_chain(requisition):
    """Create the default sequential approval steps for a ``JobRequisition``. Idempotent — if the
    requisition already has any approval rows, the existing chain is returned untouched (a tenant
    may have added custom steps before submitting). Returns the full list of approval rows.

    Shared by ``views.jobrequisition_submit`` and the seeder so both build the same chain.
    """
    existing = list(requisition.approvals.order_by("step_order"))
    if existing:
        return existing
    to_create = [
        RequisitionApproval(tenant=requisition.tenant, requisition=requisition,
                            step_order=order, approver_role=role, status="pending")
        for order, role in _DEFAULT_APPROVAL_CHAIN
    ]
    RequisitionApproval.objects.bulk_create(to_create)
    return list(requisition.approvals.order_by("step_order"))


def apply_template_to_requisition(requisition, template):
    """Copy a ``JobDescriptionTemplate``'s JD body onto a requisition (copy-on-apply). Overwrites
    the four ``jd_*`` fields and records which template was applied; deliberately does NOT touch
    ``employment_type`` (the requisition owns its own value). Request-free so the seeder/tests can
    call it. Persists with an explicit ``update_fields`` (keeps ``updated_at`` fresh)."""
    requisition.jd_summary = template.jd_summary
    requisition.jd_responsibilities = template.jd_responsibilities
    requisition.jd_requirements = template.jd_requirements
    requisition.jd_nice_to_have = template.jd_nice_to_have
    requisition.template = template
    requisition.save(update_fields=["jd_summary", "jd_responsibilities", "jd_requirements",
                                    "jd_nice_to_have", "template", "updated_at"])


# --------------------------------------------------------------------------- 3.8 Offer Management

# Default sequential offer-approval chain: hiring-manager sign-off then HR (the P0 baseline per
# research — simpler than the requisition's hr→executive chain). A 3rd executive step is appended
# when total compensation exceeds the threshold (the Lever/Ashby conditional-routing finding,
# implemented as a simple constant rather than a configurable rule engine this pass).
_DEFAULT_OFFER_APPROVAL_CHAIN = [
    (1, "hiring_manager"),
    (2, "hr"),
]
# Total-comp (base + bonus + signing) above which an extra executive approval step is auto-added.
OFFER_APPROVAL_EXEC_THRESHOLD = Decimal("150000")


def generate_offer_approval_chain(offer):
    """Create the default sequential approval steps for an ``Offer``. Idempotent — if the offer already
    has any approval rows, the existing chain is returned untouched (a tenant may have added custom
    steps before submitting). A high-value offer (total comp over ``OFFER_APPROVAL_EXEC_THRESHOLD``)
    gets an extra executive step appended. Returns the full list of approval rows.

    Shared by ``views.offer_submit`` and the seeder so both build the same chain.
    """
    existing = list(offer.approvals.order_by("step_order"))
    if existing:
        return existing
    chain = list(_DEFAULT_OFFER_APPROVAL_CHAIN)
    if offer.total_compensation > OFFER_APPROVAL_EXEC_THRESHOLD:
        chain.append((len(chain) + 1, "executive"))
    to_create = [
        OfferApproval(tenant=offer.tenant, offer=offer, step_order=order,
                      approver_role=role, status="pending")
        for order, role in chain
    ]
    OfferApproval.objects.bulk_create(to_create)
    return list(offer.approvals.order_by("step_order"))


# Default pre-boarding document-collection checklist raised on offer acceptance:
#   (document_type, is_required). Mirrors ``_CLEARANCE_LINES``.
_PREBOARDING_CHECKLIST = [
    ("id_proof", True),
    ("address_proof", True),
    ("tax_form", True),
    ("bank_details", True),
    ("nda", True),
    ("background_check_consent", True),
    ("education_certificate", False),
]


def generate_preboarding_checklist(offer):
    """Create the standard pre-boarding document-collection lines for an accepted ``Offer``. Idempotent
    — keyed on ``document_type``, re-running never duplicates an existing line. Returns the count of
    newly-created lines.

    Shared by ``views.offer_accept`` and the seeder so both build the same checklist.
    """
    existing = set(PreboardingItem.objects.filter(tenant=offer.tenant, offer=offer)
                   .values_list("document_type", flat=True))
    to_create = [
        PreboardingItem(tenant=offer.tenant, offer=offer, document_type=doc_type, is_required=required)
        for doc_type, required in _PREBOARDING_CHECKLIST
        if doc_type not in existing
    ]
    if to_create:
        PreboardingItem.objects.bulk_create(to_create)
    return len(to_create)
