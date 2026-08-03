"""SCM 4.13 Asset Management — ``MaintenancePlan`` views: the PM programme and its generate action.

**A plan is a definition, and these views never let it become an event by itself.** Everything on the
form is an INPUT (the trigger, the cadence, the call horizon, where the schedule currently stands,
and what a generated job inherits); everything the pages read back — ``due_status``,
``days_until_due``, ``meter_gap``, ``is_due`` — is a method that recomputes on every read. There is
no stored "is overdue" flag for a view to catch up, which is why nothing in this module writes on a
GET (the 4.12 licence/requirement list pages do; they have a stored, date-derived ``status`` and this
model deliberately does not).

**:func:`maintenanceplan_generate` is the only route here that creates anything.** It is an explicit
user action — a POST from a button — and never a background auto-post: an ERP that quietly raises
work orders overnight produces a queue nobody trusts, and the moment one is wrong there is no human
decision in the audit trail to point at. It is ``@tenant_admin_required`` because it creates a
DOCUMENT (the ``maintenanceplan_generate`` line of the module gate list), ``@require_POST`` so a GET
is a 405 rather than a silent state change, and it does its whole job inside one
``transaction.atomic()`` — the work order, its snapshotted checklist and the plan's rolled-forward
schedule either all land or none of them do. A half-generated cycle (a job with no tasks, or a plan
advanced past a job that was never written) is worse than a failed press.

**The task copy is a SNAPSHOT with no FK back**, and that is the whole reason
``MaintenanceWorkOrderTask`` repeats the five columns instead of pointing at ``MaintenancePlanTask``.
Editing a plan next month must not rewrite what a job three weeks ago actually asked a technician to
check and sign against. So :func:`maintenanceplan_generate` copies columns, and nothing afterwards
can reach back through the job to the plan's steps.

**Nothing here posts a StockMove and nothing here drafts an accounting document** (L29). Parts leave
stock at the work order's issue verb; the plan only names the storeroom they will be drawn from.

**The ``due`` filter is a queryset date filter, not a Python scan.** ``due_status()`` is a method, so
the tempting implementation is "evaluate it over the table and keep the matches" — that reads every
plan in the workspace, and it reads a meter for each meter-driven one, to render fifteen rows. The
filter is therefore expressed against ``next_due_on`` and the row's own ``lead_time_days``, exactly
the ``_due_soon_q`` technique 4.12's requirement queue uses (see :func:`_lead_window_q` for why that
needs an OR over the windows the workspace actually uses rather than one expression).

*The stated limit of that:* the usage axes cannot be expressed in SQL at all — a ``meter`` or
``condition`` plan is due because of the asset's latest READING, which lives in another table at
another grain. So ``?due=overdue`` narrows on the DATE axis, and a plan that is overdue only on its
meter still renders its own red "Overdue" chip in the unfiltered list. That is the honest split: the
chip tells the truth per row, the filter is a date query, and the docstring says so rather than
letting a reader assume the two are the same rule.

Context-var contract (pinned, L7 — the templates are written by a separate agent, so every key each
page consumes is listed here, not just the list variable):

* ``scm/assets/maintenanceplan/list.html`` — ``object_list`` + ``page_obj`` + ``q`` (from
  ``crud_list``) plus ``trigger_choices``, ``basis_choices``, ``priority_choices``, ``due_choices``,
  ``assets``, ``assignees``, ``due`` (the accepted value, ``""`` when absent or junk),
  ``overdue_count``, ``due_soon_count``, ``active_count``. Each row carries the two annotations
  ``has_open_job`` and ``has_tasks``. Filter params are ``q`` / ``trigger_type`` /
  ``schedule_basis`` / ``priority`` / ``asset`` / ``assigned_to`` / ``due`` / ``is_active``; the two
  pk selects compare with ``|stringformat:"d"`` and NEVER ``|slugify``.
* ``scm/assets/maintenanceplan/detail.html`` — ``obj``, ``tasks``, ``task_count``,
  ``safety_task_count``, ``jobs``, ``jobs_truncated``, ``job_count``, ``open_job``,
  ``latest_reading``, ``meter_gap``, ``days_until_due``, ``due_status``, ``due_label``, ``due_css``,
  ``is_due``, ``can_generate``, ``generate_block_reason``.
* ``scm/assets/maintenanceplan/form.html`` — ``form``, ``formset``, ``is_edit``, ``obj`` (``None``
  on create).

``maintenanceplan_delete`` and ``maintenanceplan_generate`` are tenant-admin only. The templates hide
those two buttons with the house idiom ``{% if request.user.is_superuser or
request.user.is_tenant_admin %}`` — there is no context key for it, and offering a member a one-click
403 is worse than not offering the button (the 4.11 finding).

Badge colours come from the model's own ``due_status_css`` / ``trigger_css`` / ``priority_css`` /
``work_type_css`` properties. ``badge-success`` / ``badge-warning`` / ``badge-danger`` DO NOT EXIST
in theme.css (L33).
"""
from datetime import datetime, timedelta

from django.db.models import ProtectedError

from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._common import _changed
from apps.scm.views._helpers import _need_tenant

from apps.scm.forms import MaintenancePlanForm, MaintenancePlanTaskFormSet
from apps.scm.models import (Asset, MaintenancePlan, MaintenancePlanTask, MaintenanceWorkOrder,
                             MaintenanceWorkOrderTask)
#: The shared priority vocabulary, re-exported through ``apps.scm.models`` by the package's
#: ``from .AssetManagement._choices import *`` line. Imported rather than restated so the filter
#: dropdown and the column it filters can never offer different words.
from apps.scm.models import PRIORITY_CHOICES

#: Every FK a plan ROW renders. ``select_related`` here is not decoration: ``due_status()`` reads
#: ``self.asset`` (through ``latest_reading()``), and the row prints the asset, the crew and the
#: storeroom, so without it a page of 15 plans is up to 60 extra queries for four columns. None of
#: the three ``__str__``s walks a second FK (``Asset`` -> "code · name", ``Location`` -> "code ·
#: name", ``Party`` -> ``name``), so nothing deeper is owed.
_PLAN_SELECT = ("asset", "assigned_to", "parts_location")

#: How many jobs the detail page's history panel shows. The cap is a queryset SLICE so the DATABASE
#: applies it — it bounds what is fetched, not what is rendered (L40 §1). One more than the cap is
#: read so the page can say it is showing a window without a second COUNT.
MAX_PANEL_ROWS = 25

#: What the ``due`` filter offers. NOT a model vocabulary — these are three *views* of the queue, so
#: they are declared here and handed to the template rather than hard-coded into the select. The
#: model's own five-word ``DUE_STATUS_LABELS`` is a per-row answer and stays a per-row answer;
#: ``due_today`` falls inside ``due_soon`` here because "raise it now" is one bucket to a planner.
DUE_CHOICES = [
    ("overdue", "Overdue"),
    ("due_soon", "Due soon — inside the call horizon"),
    ("scheduled", "Scheduled — beyond the horizon"),
]

#: How many distinct call horizons the due-soon/scheduled condition expands into (see
#: :func:`_lead_window_q`). ``lead_time_days`` is a per-row column and no portable ORM expression
#: adds an integer column of days to a date on MySQL, so the condition is an OR over the windows the
#: workspace actually uses — realistically one or two, because ``lead_time_days`` has a default. The
#: cap bounds the SQL for a pathological workspace; past it both conditions collapse to the single
#: widest boundary, which keeps them complementary (no plan lands in both buckets or in neither) and
#: errs towards calling work due rather than hiding it (fail open — the 4.11 impact-floor posture).
_MAX_LEAD_WINDOWS = 64

#: Ceiling applied to a lead-time window before it becomes a ``timedelta``. The column is validated
#: at 365 on the way IN, but a fixture, an import or a direct DB write is not, and
#: ``today + timedelta(days=N)`` raises ``OverflowError`` past ~2.7 million days — an uncaught 500 on
#: an ordinary list page, from a value no form ever saw (the 4.10 DoS finding, one table along).
_MAX_LEAD_DAYS = 3650

#: ``MaintenanceWorkOrder.title`` is ``max_length=255`` and ``MaintenancePlan.name`` is 255 on its
#: own, so the generated title has to be composed to fit rather than truncated afterwards — a bare
#: ``[:255]`` would silently cut the ASSET CODE off the end, which is the half of the title that
#: tells a technician which machine to walk to.
_TITLE_MAX = 255


# =================================================================================================
# Shared conditions. Each is written from the same inputs as the model method it mirrors, so the
# chip a row renders and the bucket this page put it in cannot disagree on the same screen (the 4.10
# "two of three shapes" finding).
# =================================================================================================
def _overdue_q(today):
    """Q for a plan whose published due DATE is already past.

    ``is_active`` is ANDed in because :meth:`MaintenancePlan.due_status` answers ``not_scheduled``
    for an inactive plan before it looks at anything else — a plan that cannot generate a job cannot
    be overdue for one, and counting retired schedules would make the overdue chip permanently red
    for work nobody owes.

    A NULL ``next_due_on`` never matches, which is correct: that is ``not_scheduled``, not overdue.
    """
    return Q(is_active=True, next_due_on__lt=today)


def _lead_window_q(tenant, today, *, beyond):
    """Q for "inside the row's own call horizon" (``beyond=False``) or "past it" (``beyond=True``).

    ``due_soon`` is ``0 <= days_until_due <= lead_time_days`` and ``scheduled`` is the strict
    remainder, so the two are one rule read from opposite sides — written once here rather than
    twice, because two copies drift the first time the horizon rule changes.

    ``lead_time_days`` is a COLUMN, and Django cannot add an integer column of days to a date
    portably (``F("lead_time_days") * timedelta`` is not a legal duration expression on MySQL). So
    the condition expands into one ``(lead_time_days=N, next_due_on <= today + N)`` clause per window
    the workspace actually uses, read in ONE small grouped query — the ``_due_soon_q`` technique
    4.12's compliance queue already ships.

    Returns a NEVER-matching Q when the workspace has no future-dated active plan, rather than an
    empty ``Q()``: an empty Q matches EVERYTHING, which would turn an empty chip into the whole
    register.
    """
    if tenant is None:
        return Q(pk__in=())
    base = Q(is_active=True, next_due_on__gte=today)
    windows = sorted(set(
        MaintenancePlan.objects
        .filter(tenant=tenant, is_active=True, next_due_on__gte=today)
        .order_by()  # Meta.ordering is ["-id"]; a DISTINCT over values_list carrying an unrelated
                     # ORDER BY column returns duplicates.
        .values_list("lead_time_days", flat=True)
        .distinct()[:_MAX_LEAD_WINDOWS]
    ))
    if not windows:
        return Q(pk__in=())
    if len(windows) >= _MAX_LEAD_WINDOWS:
        # Degraded, and deliberately at ONE boundary for both sides so the pair stays a partition:
        # a plan between its own horizon and the widest one reads as due_soon (over-calling work as
        # due is the safe direction) and is absent from scheduled.
        edge = today + timedelta(days=min(max(windows), _MAX_LEAD_DAYS))
        return base & (Q(next_due_on__gt=edge) if beyond else Q(next_due_on__lte=edge))
    condition = Q()
    for days in windows:
        edge = today + timedelta(days=min(days, _MAX_LEAD_DAYS))
        condition |= (Q(lead_time_days=days, next_due_on__gt=edge) if beyond
                      else Q(lead_time_days=days, next_due_on__lte=edge))
    return base & condition


def _asset_qs(tenant):
    """Assets the ``asset`` filter offers — only those that actually CARRY a plan.

    The unfiltered alternative is the whole asset register, thousands of ``<option>``s of which all
    but a handful select nothing. This is both the bounded query and the more useful dropdown (the
    ``tradedocument_list`` shipments precedent).
    """
    if tenant is None:
        return Asset.objects.none()
    return (Asset.objects.filter(tenant=tenant, maintenance_plans__isnull=False)
            .distinct().order_by("code"))


def _assignee_qs(tenant):
    """Parties the ``assigned_to`` filter offers — whoever a plan in this workspace names.

    Deliberately WIDER than the FORM's dropdown, which is narrowed to the ``employee`` role: a party
    whose employee role was later removed still owns the plans they were put on, and "what is still
    assigned to them" is exactly the question this filter answers (the 4.12 ``_owner_qs`` reasoning).
    Scoped through ``scm_maintenance_plans__tenant`` as well as the party's own tenant — the house
    belt-and-braces, so the join cannot reach across a workspace even if a row is malformed.
    """
    if tenant is None:
        return Party.objects.none()
    return (Party.objects.filter(tenant=tenant, scm_maintenance_plans__tenant=tenant)
            .distinct().order_by("name"))


def _open_job(plan):
    """The plan's newest job that is still live, or ``None``.

    ``MaintenanceWorkOrder.OPEN_STATUSES`` is declared on the model precisely because three readers
    depend on it and one of them is named as "the plan's generate refusal". Reading it here rather
    than restating the five statuses is what keeps the refusal, the asset's open-job chip and the
    work-order list filter counting the same rows.
    """
    return (plan.work_orders.filter(tenant_id=plan.tenant_id,
                                    status__in=MaintenanceWorkOrder.OPEN_STATUSES)
            .order_by("-id").first())


def _generate_block_reason(plan, open_job):
    """Why :func:`maintenanceplan_generate` would refuse right now, or ``""``.

    ONE statement of the rule, read by both the detail page's ``can_generate`` gate and the verb's
    guard inside the lock, so a button can never be offered for a press the view will refuse (§7.5).

    Two refusals, and both are about the plan rather than the calendar. **Not due yet is NOT a
    refusal**: ``lead_time_days`` exists so a job can legitimately be raised ahead of its date, and a
    planner pulling a service forward because the machine is already open is ordinary work, not an
    error. What is refused is a plan that cannot raise work at all (inactive) and a plan that already
    has one outstanding — the second because a duplicate PM job splits the checklist, the parts and
    the cost of one service across two documents, and nothing afterwards can tell they were the same
    occurrence.
    """
    if not plan.is_active:
        return (f"{plan.number} is inactive — an inactive plan never comes due and cannot raise a "
                "job. Re-activate it first if this service is still owed.")
    if open_job is not None:
        return (f"{plan.number} already has an open job ({open_job.number}, "
                f"{open_job.get_status_display().lower()}) — finish, close or cancel it before "
                "raising another, or the same service ends up split across two documents.")
    return ""


def _due_datetime(due_on):
    """A plan's due DATE as an aware datetime at local midnight, or ``None``.

    ``MaintenanceWorkOrder.scheduled_start`` is a ``DateTimeField`` and ``next_due_on`` is a
    ``DateField``; the conversion is stated here rather than inline because it is what
    ``is_on_time`` ends up measured against. ``get_current_timezone()``, not UTC — the
    ``workorder_schedule`` idiom (``Manufacturing/WorkOrders.py:244``): a due date is a fact about
    the workspace's calendar, and midnight in the wrong zone moves a job across a day boundary.
    """
    if due_on is None:
        return None
    return timezone.make_aware(datetime.combine(due_on, datetime.min.time()),
                               timezone.get_current_timezone())


def _job_title(plan):
    """``"<plan name> — <asset code>"``, composed to fit ``title``'s 255 characters.

    See :data:`_TITLE_MAX`: the plan name alone can fill the column, so the NAME is trimmed and the
    asset code is kept. A technician reading a queue needs to know which machine before they need
    the full wording of the schedule.
    """
    suffix = f" — {plan.asset.code}"
    return f"{plan.name[:_TITLE_MAX - len(suffix)]}{suffix}"


def _job_description(plan):
    """The generated job's prose: where it came from, the planned labour, then the instructions.

    **``estimated_hours`` is deliberately NOT copied into ``labour_hours``.**
    ``MaintenanceWorkOrder`` has no ``estimated_hours`` column, and ``labour_hours`` is the ACTUAL
    figure ``labour_cost`` — and therefore ``total_cost``, the asset's ``maintenance_cost_to_date``
    and the depreciation report's repair-vs-replace ratio — is computed from. Pre-filling it would
    put a real cost on a job nobody has worked yet, which is exactly what ``parts_cost`` refuses to
    do for un-issued lines. The estimate is carried as a stated line instead: it informs the
    technician without becoming a number a report adds up.
    """
    lines = [f"Generated from {plan.number} ({plan.get_trigger_type_display()})."]
    if plan.estimated_hours:
        lines.append(f"Planned labour: {plan.estimated_hours} h.")
    instructions = (plan.instructions or "").strip()
    if instructions:
        lines.extend(["", instructions])
    return "\n".join(lines)


def _audit_value(value):
    """One audit-diff value as something ``AuditLog.changes`` (a ``JSONField``) can hold.

    Dates and ``Decimal``s are not JSON-serializable, and a verb that stamped one would raise while
    writing the audit row — AFTER its own transaction had already committed.
    """
    if value is None or isinstance(value, (bool, int, str)):
        return value
    return str(value)[:200]


# =================================================================================================
# CRUD
# =================================================================================================
@login_required
def maintenanceplan_list(request):
    """The PM programme: search, seven filters, three header chips.

    EVERY filter is applied BEFORE ``crud_list`` paginates. A filter applied afterwards would page
    over the unfiltered set and quietly show the wrong rows on page 2.

    The two pk filters go through ``crud_list``'s ``filters`` spec with ``is_int=True``, which is
    where the L11 guard lives: ``?asset=abc``, ``?asset=²`` and a 21-digit ``?asset=…`` must all SKIP
    the filter rather than raise out of ``.filter()``.

    **The two ``Exists`` annotations are what let the list gate its own row actions** without a
    query per row: ``has_open_job`` decides whether the Generate button is offered (the same
    condition :func:`_generate_block_reason` refuses on) and ``has_tasks`` whether the row can
    advertise a checklist. ``Exists`` and not ``Count`` — the template only asks "are there any?",
    a COUNT forces a GROUP BY over the whole child table, and it also makes ``QuerySet.ordered``
    report False, which the paginator then warns about (the 4.8 finding).

    *One cost is knowingly accepted here.* Rendering the due chip calls ``due_status()``, which for a
    ``meter`` / ``combined`` / ``condition`` plan reads the asset's latest reading — one indexed
    ``LIMIT 1`` on ``scm_mtr_tnt_asset_idx``, memoised on the instance so all five readers
    (``due_status``, its label, its css, ``is_due``, ``meter_gap``) share it. Calendar plans, which
    are the majority, cost nothing at all. The bound is therefore at most one small point lookup per
    meter-driven row ON THE PAGE (15), and removing it would mean hand-rolling pagination purely to
    prime that cache — a bespoke list path traded for fifteen index seeks.
    """
    today = timezone.localdate()

    queryset = (MaintenancePlan.objects.filter(tenant=request.tenant)
                .select_related(*_PLAN_SELECT)
                .annotate(
                    has_open_job=Exists(MaintenanceWorkOrder.objects.filter(
                        plan=OuterRef("pk"), status__in=MaintenanceWorkOrder.OPEN_STATUSES)),
                    has_tasks=Exists(MaintenancePlanTask.objects.filter(plan=OuterRef("pk")))))

    # --- the one filter crud_list's equality spec cannot express -----------------------------------
    overdue_condition = _overdue_q(today)
    # Built unconditionally because the header chip below counts it as well as the filter using it.
    # Its `scheduled` twin is built only inside the branch that needs it — the two are one query
    # each, and nothing on the page counts "scheduled".
    due_soon_condition = _lead_window_q(request.tenant, today, beyond=False)

    due = (request.GET.get("due") or "").strip()
    if due == "overdue":
        queryset = queryset.filter(overdue_condition)
    elif due == "due_soon":
        queryset = queryset.filter(due_soon_condition)
    elif due == "scheduled":
        queryset = queryset.filter(_lead_window_q(request.tenant, today, beyond=True))
    else:
        # Absent, or hand-edited junk: no narrowing, and the select is told so. The ``crud_list``
        # posture on a bad filter — skip it, never 500, and never silently show nothing.
        due = ""

    # ONE aggregate for the whole header strip. Computed over the UNFILTERED workspace on purpose:
    # "4 overdue" is a fact somebody has to act on, and recomputing it per filter would make the
    # number change as you browse.
    chips = MaintenancePlan.objects.filter(tenant=request.tenant).aggregate(
        overdue=Count("id", filter=overdue_condition),
        due_soon=Count("id", filter=due_soon_condition),
        active=Count("id", filter=Q(is_active=True)),
    )

    return crud_list(
        request, queryset, "scm/assets/maintenanceplan/list.html",
        search_fields=["name", "number", "asset__code", "asset__name"],
        filters=[("trigger_type", "trigger_type", False),
                 ("schedule_basis", "schedule_basis", False),
                 ("priority", "priority", False),
                 # is_int=True: crud_list applies the L11 guard — a non-decimal, Unicode-superscript
                 # or over-range value SKIPS the filter instead of raising out of .filter().
                 ("asset", "asset_id", True),
                 ("assigned_to", "assigned_to_id", True),
                 # crud_list maps the strings "True"/"False" onto real booleans; the template
                 # therefore renders those two exact option values (the shipped house convention).
                 ("is_active", "is_active", False)],
        extra_context={
            # Every dropdown the filter bar renders gets its choices/queryset here. A filter with no
            # context to render from is the single most common defect in this codebase.
            "trigger_choices": MaintenancePlan.TRIGGER_CHOICES,
            "basis_choices": MaintenancePlan.SCHEDULE_BASIS_CHOICES,
            "priority_choices": PRIORITY_CHOICES,
            "due_choices": DUE_CHOICES,
            "assets": _asset_qs(request.tenant),
            "assignees": _assignee_qs(request.tenant),
            "due": due,
            "overdue_count": chips["overdue"] or 0,
            "due_soon_count": chips["due_soon"] or 0,
            "active_count": chips["active"] or 0,
        },
    )


@login_required
def maintenanceplan_create(request):
    return _maintenanceplan_form(request, instance=None)


@login_required
def maintenanceplan_edit(request, pk):
    """Editable at any time, deliberately — including once it has raised jobs.

    A plan is a standing instruction, and standing instructions are re-scoped, re-timed and
    re-crewed; a screen that froze the row the moment it generated something would push those
    corrections into the notes field. Nothing an edit does reaches a job that already exists: the
    checklist a work order carries is a SNAPSHOT with no FK back (see the module docstring), and
    ``last_completed_on`` / ``last_generated_on`` are ``editable=False`` and off the form, so an edit
    can change what the plan WILL ask for and never what a past job actually asked.
    """
    obj = get_object_or_404(MaintenancePlan, pk=pk, tenant=request.tenant)
    return _maintenanceplan_form(request, instance=obj)


def _maintenanceplan_form(request, instance):
    """Plan + its job-plan task formset committed in ONE ``transaction.atomic()``.

    ``formset.instance = form.instance`` goes AFTER ``form.is_valid()`` and BEFORE
    ``formset.is_valid()``: on create the formset's own instance is an empty ``MaintenancePlan()``
    with ``tenant_id`` None, and pointing it at the bound instance is what makes every child
    validate against the parent that is actually about to be saved. It is the same ordering
    ``_tradedocument_form`` documents, kept here so the two inline-formset save paths in the app
    read identically rather than one of them looking like an accident.

    ``form_kwargs={"tenant": request.tenant}`` is REQUIRED — ``MaintenancePlanTaskForm`` subclasses
    ``TenantModelForm`` for its widget classes and its constructor takes ``tenant``; omitting it is a
    ``TypeError`` at bind time, not a subtle bug.

    This path bypasses ``crud_edit`` (so the parent and its lines commit together), which means the
    audit row ``crud_edit`` would have written has to be written BY HAND — with ``_changed(form)``,
    never a second copy of the redaction list.
    """
    if instance is None and _need_tenant(request):
        return redirect("scm:maintenanceplan_list")
    is_edit = instance is not None

    if request.method == "POST":
        form = MaintenancePlanForm(request.POST, request.FILES, instance=instance,
                                   tenant=request.tenant)
        formset = MaintenancePlanTaskFormSet(request.POST, instance=instance,
                                             form_kwargs={"tenant": request.tenant})
        form_ok = form.is_valid()
        if form_ok:
            formset.instance = form.instance   # <- load-bearing; see the docstring
        if form_ok and formset.is_valid():
            with transaction.atomic():
                plan = form.save(commit=False)
                # Stamped again even though MaintenancePlanForm.__init__ already put it on the
                # unsaved instance: the form's stamp exists so `MaintenancePlan.clean()` can run its
                # cross-tenant FK guard during validation, and this one is the save path's own
                # guarantee. Neither is redundant with the other.
                plan.tenant = request.tenant
                plan.save()
                formset.instance = plan
                formset.save()
            write_audit_log(request.user, plan, "update" if is_edit else "create", _changed(form))
            messages.success(request, f"{plan.number} saved.")
            return redirect("scm:maintenanceplan_detail", pk=plan.pk)
    else:
        form = MaintenancePlanForm(instance=instance, tenant=request.tenant)
        formset = MaintenancePlanTaskFormSet(instance=instance,
                                             form_kwargs={"tenant": request.tenant})

    return render(request, "scm/assets/maintenanceplan/form.html", {
        "form": form, "formset": formset, "is_edit": is_edit, "obj": instance})


@login_required
def maintenanceplan_detail(request, pk):
    """One plan: where its schedule stands, its checklist, and every job it has raised.

    ``due_status`` / ``days_until_due`` / ``meter_gap`` / ``latest_reading`` are computed ONCE here
    and handed over as plain values rather than left for the template to pull off the model five
    times. They all read ``latest_reading()``, which memoises per instance, so this is one query
    either way — but computing them in the view is what lets the page print an honest em dash for a
    ``None`` instead of a template silently rendering an empty string it cannot distinguish from 0.

    ``meter_gap`` is ``None``, never ``0``, when the plan is not meter-driven or the asset has never
    been read. "No answer" and "due right now" are different facts, and a confident zero states the
    second (the 4.11 lesson).
    """
    obj = get_object_or_404(MaintenancePlan.objects.select_related(*_PLAN_SELECT),
                            pk=pk, tenant=request.tenant)

    # The job plan. Meta.ordering is ["sequence", "id"], which is the order it is worked in.
    tasks = list(obj.tasks.all())

    # The history panel. One more than the cap is fetched so the page can say it is showing a
    # window; the explicit `tenant=` is redundant (the related manager already constrains by plan,
    # which implies the tenant) and is stated anyway so this page holds the module-wide rule
    # mechanically rather than by inference.
    jobs = list(obj.work_orders.filter(tenant=request.tenant)
                .select_related("asset", "assigned_to")[:MAX_PANEL_ROWS + 1])
    jobs_truncated = len(jobs) > MAX_PANEL_ROWS
    del jobs[MAX_PANEL_ROWS:]

    open_job = _open_job(obj)
    block_reason = _generate_block_reason(obj, open_job)
    due_status = obj.due_status()

    return render(request, "scm/assets/maintenanceplan/detail.html", {
        "obj": obj,
        "tasks": tasks,
        "task_count": len(tasks),
        "safety_task_count": sum(1 for task in tasks if task.is_safety_step),
        "jobs": jobs,
        "jobs_truncated": jobs_truncated,
        "job_count": obj.work_orders.filter(tenant=request.tenant).count(),
        "open_job": open_job,
        # None-able on purpose — print an em dash, never a 0 (see the docstring).
        "latest_reading": obj.latest_reading(),
        "meter_gap": obj.meter_gap(),
        "days_until_due": obj.days_until_due(),
        "due_status": due_status,
        "due_label": MaintenancePlan.DUE_STATUS_LABELS.get(due_status, "Not scheduled"),
        "due_css": MaintenancePlan.DUE_STATUS_CSS.get(due_status, "badge-muted"),
        "is_due": obj.is_due(),
        # The action gate, decided here from the SAME helper the verb guards on, so the button and
        # the route behind it cannot disagree about whether a press will work.
        "can_generate": not block_reason,
        "generate_block_reason": block_reason,
    })


@tenant_admin_required
@require_POST
def maintenanceplan_delete(request, pk):
    """Delete the plan — and say what goes with it and what survives.

    Two different cascades hang off this row and a user is owed both facts. ``MaintenancePlanTask``
    is ``CASCADE``, so the job plan's steps go; that is right (a step's meaning is its plan's) and it
    is a larger consequence than "Deleted successfully." admits, because those steps cannot be
    reconstructed. ``MaintenanceWorkOrder.plan`` is ``SET_NULL`` by contrast, so every job the plan
    ever raised SURVIVES with its own snapshotted checklist and its costs, and merely loses the
    provenance link — which is exactly why the snapshot has no FK back.

    Tenant-admin gated for that reason, and because the honest alternative is already on the form:
    an ``is_active=False`` plan never comes due, cannot generate, and keeps its history.

    The ``ProtectedError`` catch is the generic §7.4 guard, not an enumeration: nothing PROTECTs this
    table today, but Module 11 is a declared FK extender of it, and an enumeration would go stale
    silently — as a 500 on a mainline delete. ``atomic()`` so the audit row ``crud_delete`` writes
    before deleting rolls back with a failed delete.
    """
    obj = get_object_or_404(MaintenancePlan.objects.only("pk", "number"),
                            pk=pk, tenant=request.tenant)
    task_rows = obj.tasks.count()
    orphaned_jobs = obj.work_orders.filter(tenant=request.tenant).count()

    try:
        with transaction.atomic():
            response = crud_delete(request, model=MaintenancePlan, pk=pk,
                                   success_url="scm:maintenanceplan_list")
    except ProtectedError as exc:
        blockers = sorted({protected._meta.verbose_name for protected in exc.protected_objects})
        messages.error(
            request,
            f"{obj.number} is still referenced by {', '.join(blockers)} and cannot be deleted — "
            "deactivate it instead, so the schedule stops coming due but its history survives.")
        return redirect("scm:maintenanceplan_detail", pk=pk)

    if task_rows:
        messages.info(request, f"{task_rows} job-plan step(s) were removed with {obj.number} — that "
                               "checklist cannot be reconstructed.")
    if orphaned_jobs:
        messages.info(request, f"{orphaned_jobs} maintenance job(s) kept their own checklist and "
                               f"costs and simply lost the link to {obj.number}.")
    return response


# =================================================================================================
# The generate action — the only route in this module that creates a document.
# =================================================================================================
@tenant_admin_required
@require_POST
def maintenanceplan_generate(request, pk):
    """Raise the plan's next job: snapshot the checklist, then roll the schedule forward.

    **Explicit and human, never a background auto-post** — see the module docstring. Admin-gated
    because it creates a document; ``@require_POST`` so a GET is a 405 rather than a silent state
    change; and the row is re-read under ``SELECT … FOR UPDATE`` INSIDE the transaction so a double
    POST cannot raise two jobs for one occurrence and advance the schedule twice.

    The order inside the lock is load-bearing:

    1. **Refuse first**, from :func:`_generate_block_reason` — the same helper the detail page's
       button is gated on. An inactive plan or one with an outstanding job creates NOTHING; the
       refusal is a message and a redirect, never a 500 and never a half-written cycle.
    2. **Capture ``next_due_on`` BEFORE :meth:`MaintenancePlan.advance` moves it.** That date becomes
       the job's ``scheduled_start``, and ``is_on_time`` measures completion against it. Reading it
       back off the plan afterwards would compare every generated job with a date that has not
       arrived yet and report 100% PM compliance forever — the trap
       ``MaintenanceWorkOrder.is_on_time`` spells out.
    3. **Snapshot the tasks as plain column copies**, in one ``bulk_create``. There is deliberately
       no FK back to ``MaintenancePlanTask``: editing the plan next month must not rewrite what this
       job asked a technician to check.
    4. **Advance, and fold the write into ONE save.** :meth:`advance` returns the list of field names
       it wrote and does not save by default, exactly so this caller can add its own
       ``last_generated_on`` stamp and issue a single ``UPDATE`` instead of two.

    ``status`` is left at its default ``requested``: generating a job is not approving one, and the
    column is ``editable=False`` with its own verb.
    """
    with transaction.atomic():
        # No select_related on the locked read: MaintenancePlan.asset is a non-nullable FK, so
        # joining it here would put the ASSET row under FOR UPDATE too and serialise unrelated edits
        # to that machine. The asset is loaded once, lazily, for the title.
        plan = get_object_or_404(MaintenancePlan.objects.select_for_update(),
                                 pk=pk, tenant=request.tenant)

        block = _generate_block_reason(plan, _open_job(plan))
        if block:
            messages.error(request, block)
            return redirect("scm:maintenanceplan_detail", pk=pk)

        due_on = plan.next_due_on            # (2) — before advance() moves it
        job = MaintenanceWorkOrder(
            tenant=plan.tenant,
            asset=plan.asset,
            plan=plan,
            source="plan",
            title=_job_title(plan),
            description=_job_description(plan),
            # The shared vocabularies from _choices.py are what make these two plain copies rather
            # than a mapping: one list, so the plan cannot carry a value this column will not accept.
            work_type=plan.work_type,
            priority=plan.priority,
            assigned_to=plan.assigned_to,
            parts_location=plan.parts_location,
            reported_at=timezone.now(),
            scheduled_start=_due_datetime(due_on),
        )
        job.save()

        # (3) — plain column copies. bulk_create because a job plan is a handful of rows and one
        # INSERT is one round trip; nothing on MaintenanceWorkOrderTask has a save() override or a
        # signal that a bulk insert would skip.
        snapshot = [
            MaintenanceWorkOrderTask(
                work_order=job,
                sequence=task.sequence,
                description=task.description,
                expected_result=task.expected_result,
                is_mandatory=task.is_mandatory,
                is_safety_step=task.is_safety_step,
            )
            for task in plan.tasks.all()
        ]
        if snapshot:
            MaintenanceWorkOrderTask.objects.bulk_create(snapshot)

        # (4) — stamp the event we actually observed, and NOTHING else.
        #
        # Generating a job does NOT roll the schedule. `advance()` has exactly one caller — the
        # work-order complete verb — because the schedule must have exactly one writer, the same rule
        # `Asset.status` and `downtime_minutes` follow. Rolling here as well used to advance a
        # `fixed` plan by TWO cycles per occurrence: `advance()` anchors a fixed plan on its own
        # published `next_due_on` (MaintenancePlans.py:436), so the second call compounds the first.
        # Measured on a quarterly plan: Jan 1 -> generate Apr 1 -> complete Jun 30. The April
        # inspection silently never came due, and the identical compounding hit `next_due_reading`
        # on a fixed meter plan (1000 -> 1250 -> 1500).
        #
        # Completion is the right owner even setting that bug aside:
        #   * `floating` is DEFINED as "measured from the last completion". Rolling at generate time
        #     measured it from the generate date instead — a plan generated in August and completed
        #     in October would publish a date anchored on August.
        #   * a generated job that is later CANCELLED must not consume a cycle. With the roll here,
        #     cancelling left the schedule already advanced past an occurrence nobody performed.
        # The plan therefore stays visibly due until the work is actually done, which is what the
        # forecast board should say; `generate` already refuses while an open job exists, so it
        # cannot double-generate in the meantime.
        plan.last_generated_on = timezone.localdate()
        plan.save(update_fields=["last_generated_on", "updated_at"])

    # Two audit rows because two records genuinely moved: a job was created, and the plan's published
    # schedule changed. Written after the commit, and every value forced through _audit_value —
    # AuditLog.changes is a JSONField and a date/Decimal would raise while writing the row.
    write_audit_log(request.user, job, "create", {
        "action": "generate",
        "plan": plan.number,
        "source": "plan",
        "tasks_copied": len(snapshot),
        "scheduled_start": _audit_value(job.scheduled_start),
    })
    write_audit_log(request.user, plan, "update", {
        "action": "generate",
        "work_order": job.number,
        # The published schedule is deliberately NOT part of this diff — generating a job does not
        # move it (see (4) above). The roll is audited by the complete verb, which owns it.
        "last_generated_on": _audit_value(plan.last_generated_on),
    })

    messages.success(request, f"{job.number} raised from {plan.number}"
                              + (f" with {len(snapshot)} checklist step(s)." if snapshot
                                 else " — this plan has no job-plan steps, so the job carries no "
                                      "checklist."))
    # Said out loud, because "I generated the job but the plan still shows as due" is otherwise read
    # as a bug rather than as the design. The schedule moves when the work is finished, not when it
    # is raised.
    if plan.trigger_type == "condition":
        # A condition plan has no cycle to roll at all: its next occurrence is decided by the
        # machine, not by a schedule.
        messages.info(request, f"{plan.number} keeps its trigger — a "
                               f"'{plan.get_trigger_type_display()}' plan has no cycle to roll "
                               "forward, so it will come due again when the reading says so.")
    else:
        messages.info(request, f"{plan.number} stays due until {job.number} is completed — the "
                               "schedule rolls forward on completion, so a job that is cancelled "
                               "does not consume a cycle.")
    return redirect("scm:maintenanceworkorder_detail", pk=job.pk)
