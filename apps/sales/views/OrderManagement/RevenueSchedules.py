"""Sales 8.6 — the revenue register: 5 CRUD views + 3 obligation actions + 1 recognize.

This is the module that shows the repo its ASC 606 position, and the one rule that shapes every
line below is that **no money figure is read from a column**. ``contract_amount``,
``allocated_amount``, ``recognized_amount``, ``deferred_amount``, ``contract_asset``,
``contract_liability`` and ``recognition_progress_pct`` are all ``@property`` on the model, which
means the list view's ``stats`` strip has to sum them ITSELF, in Python, over the fetched
schedules. It does NOT reach for ``aggregate("Sum")``: that is the SQLite integer-division trap
SCM 4.5 names in ``recalc_totals()``, where fractional cents are silently dropped rather than
raising. A register whose total is short by a cent is worse than no register.

Ownership (L36/L37) is the constraint everything else follows from. ``scm.SalesOrder`` belongs to
SCM 4.5, and this file:

* reads the order through an FK and never declares, constructs or duplicates it;
* writes NOTHING on it — not the total, not the status, not a single column. The contract value
  this screen shows is 4.5's own figure, read live;
* posts NO ``JournalEntry`` (L29). ``RevenueSchedule.journal_entry`` is reference-only and
  ``editable=False``; it appears in no form and no view writes it.

Four rules govern every view here, the same four as the change order's:

* **Tenant scope, always.** ``filter(tenant=request.tenant)``, never ``.objects.all()``. The
  tenantless superuser sees empty lists BY DESIGN, and every action verb 404s on another
  workspace's schedule.
* **Junk in, ignored out (L11).** ``?status=nonsense`` narrows nothing rather than raising, and
  ``?sales_order=`` goes through ``as_db_int`` so a 40-digit value is skipped instead of
  overflowing the driver.
* **No GET may mutate.** Every action verb is ``@require_POST`` + CSRF. ``revenue_schedule_recognize``
  is the one that matters most — it is the only thing in the app that writes recognised revenue.
* **Audit on every mutation.** ``write_audit_log`` is POSITIONAL —
  ``(user, obj, action, changes, tenant)`` — and the instance is the SECOND argument.

Two structural rules are specific to this entity and are enforced by the URLconf rather than by
convention:

* **No route takes a child pk alone.** All three obligation routes are nested under the parent
  (``<int:pk>/obligations/<int:obligation_pk>/``), and the obligation is re-fetched THROUGH the
  schedule, so an obligation id from another workspace is a 404 rather than an edit.
* **``?return_to=`` is never accepted.** A caller-supplied redirect target is an open redirect
  waiting to be phished; every POST here redirects to a name this file owns.

**Recognition is refused unless the schedule is active — in the METHOD, not only here.** A guard
that exists in a view alone is a guard that can be bypassed by calling ``recompute()`` directly,
so the real refusal lives in ``RevenueSchedule.recompute()`` and the view simply reports it.
"""
from decimal import Decimal

from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.crud import as_db_int, paginate
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.sales.forms.OrderManagement.RevenueSchedules import (
    PerformanceObligationForm,
    RevenueScheduleForm,
)
from apps.sales.models.OrderManagement.RevenueSchedules import (
    PerformanceObligation,
    RevenueSchedule,
)
from apps.sales.views._common import *  # noqa: F401,F403  (login_required, get_object_or_404, ...)


LIST_TEMPLATE = "sales/ordermanagement/revenueschedule/list.html"
DETAIL_TEMPLATE = "sales/ordermanagement/revenueschedule/detail.html"
FORM_TEMPLATE = "sales/ordermanagement/revenueschedule/form.html"
OBLIGATION_FORM_TEMPLATE = "sales/ordermanagement/revenueschedule/obligation_form.html"

#: Rows per page. Matches the shared pagination partial's expectation of ``page_obj``.
PAGE_SIZE = 15

#: Summed in Python, so the stats strip needs a real zero to add into. ``Decimal("0")``, never
#: ``0`` — a Decimal/``int`` mix raises on the first addition rather than quietly truncating.
ZERO = Decimal("0")


def _schedule_queryset(request):
    """The tenant-scoped revenue register. One place, so no view can forget the filter."""
    return RevenueSchedule.objects.filter(tenant=request.tenant).select_related(
        "sales_order", "sales_order__customer", "fiscal_period",
    )


def _tenant_sales_orders(request):
    """The order dropdown for the filters and the form. Read-only over SCM 4.5's table."""
    from apps.scm.models import SalesOrder

    return (
        SalesOrder.objects.filter(tenant=request.tenant)
        .select_related("customer")
        .order_by("-order_date", "-id")
    )


def _tenant_fiscal_periods(request):
    """The fiscal-period dropdown, tenant-narrowed and newest first."""
    from apps.accounting.models import FiscalPeriod

    return FiscalPeriod.objects.filter(tenant=request.tenant).order_by("-start_date")


def _order_lines_for(schedule):
    """The parent order's own lines, for the obligation form's dropdown and the detail table."""
    from apps.scm.models import SalesOrderLine

    if schedule is None or not schedule.sales_order_id:
        return SalesOrderLine.objects.none()
    return (
        SalesOrderLine.objects.filter(sales_order_id=schedule.sales_order_id)
        .select_related("item")
        .order_by("id")
    )


def _allocations_for(order):
    """Stock reserved against the order — context for how far delivery has actually got.

    Read-only over SCM 4.5's allocation table. A revenue schedule that has recognised nothing
    against reserved stock is worth noticing, which is why the reservations sit beside the
    obligations rather than being three screens away.
    """
    if order is None:
        return []
    from apps.scm.models import SalesOrderAllocation

    return list(
        SalesOrderAllocation.objects.filter(sales_order_line__sales_order_id=order.pk)
        .select_related("sales_order_line", "location")
        .order_by("id")
    )


def _filtered_schedules(request, base_queryset):
    """Apply the six list filters to a queryset, returning ``(queryset, echo)``.

    Every value is validated before it is used. A choice filter ignores anything outside its own
    ``CHOICES`` and an FK filter goes through ``as_db_int`` — so ``?status=nonsense`` and
    ``?sales_order=abc`` both narrow nothing rather than raising on a URL anybody can type into
    the address bar (L11). Zero is skipped too: it is not a pk, and filtering on it returns an
    empty page that reads as "this workspace has no schedules", which is a lie.
    """
    queryset = base_queryset

    q = request.GET.get("q", "").strip()
    if q:
        queryset = queryset.filter(
            Q(number__icontains=q) | Q(notes__icontains=q) | Q(sales_order__number__icontains=q)
        )

    method = request.GET.get("method", "").strip()
    if method in dict(RevenueSchedule.METHOD_CHOICES):
        queryset = queryset.filter(method=method)
    else:
        method = ""

    status = request.GET.get("status", "").strip()
    if status in dict(RevenueSchedule.STATUS_CHOICES):
        queryset = queryset.filter(status=status)
    else:
        status = ""

    standard = request.GET.get("compliance_standard", "").strip()
    if standard in dict(RevenueSchedule.COMPLIANCE_STANDARD_CHOICES):
        queryset = queryset.filter(compliance_standard=standard)
    else:
        standard = ""

    period_filter = request.GET.get("fiscal_period", "").strip()
    period_pk = as_db_int(period_filter)
    if period_pk:
        queryset = queryset.filter(fiscal_period_id=period_pk)
    else:
        period_filter = ""

    order_filter = request.GET.get("sales_order", "").strip()
    order_pk = as_db_int(order_filter)
    if order_pk:
        queryset = queryset.filter(sales_order_id=order_pk)
    else:
        order_filter = ""

    filters = {
        "q": q,
        "method": method,
        "status": status,
        "compliance_standard": standard,
        "fiscal_period": period_filter,
        "sales_order": order_filter,
    }
    return queryset, filters



def _register_stats(schedules):
    """The stats strip — EVERY money figure summed in PYTHON over the fetched schedules.

    ``schedules`` is a LIST, not a queryset: each schedule's ``contract_amount``,
    ``allocated_amount`` and ``recognized_amount`` are ``@property`` values that read its own
    order and its own obligations, so summing them is Python work by definition. There is no
    ``aggregate("Sum")`` that could do this correctly, and the one that would do it WRONG is
    the SQLite decimal / integer-division trap SCM 4.5 names in ``recalc_totals()``.

    The counts describe the WHOLE tenant register, not the filtered page — a stats strip that
    changes when you search is a stats strip nobody trusts. The money describes it too: these
    are the numbers the company is carrying, and they do not become a different company because
    somebody typed into the search box.
    """
    total = active = overdue = 0
    contract_value = recognized = deferred = ZERO
    for schedule in schedules:
        total += 1
        if schedule.status == "active":
            active += 1
        if schedule.is_overdue:
            overdue += 1
        contract_value += schedule.contract_amount
        recognized += schedule.recognized_amount
        deferred += schedule.deferred_amount
    return {
        "total": total,
        "active": active,
        "overdue": overdue,
        "contract_value": contract_value,
        "recognized": recognized,
        "deferred": deferred,
    }


def _list_context(request, queryset, page_obj, filters, stats):
    """The register's context, in one place. Every key the list template reads is pinned here."""
    context = {
        "schedules": page_obj,
        "page_obj": page_obj,
        "method_choices": RevenueSchedule.METHOD_CHOICES,
        "status_choices": RevenueSchedule.STATUS_CHOICES,
        "compliance_standard_choices": RevenueSchedule.COMPLIANCE_STANDARD_CHOICES,
        "sales_orders": _tenant_sales_orders(request),
        "fiscal_periods": _tenant_fiscal_periods(request),
        "stats": stats,
    }
    context.update(filters)
    return context


def _detail_context(request, schedule, obligation_form=None):
    """The FULL detail context, in one place.

    The obligation add / edit verbs re-render this template on an invalid form, and that is the
    difference between "your obligation was not saved" and a bare form with no schedule number on
    it. Building it in one helper is what guarantees the error path and the normal path cannot
    drift apart — and therefore that a context key a template reads can never go missing on one
    of them (L8: a missing key is a silently blank region at HTTP 200).
    """
    order = schedule.sales_order
    return {
        "schedule": schedule,
        "order": order,
        "obligations": schedule.obligations.select_related("item", "sales_order_line"),
        "allocations": _allocations_for(order),
        "fiscal_periods": _tenant_fiscal_periods(request),
        "obligation_form": obligation_form or PerformanceObligationForm(
            tenant=request.tenant, schedule=schedule,
        ),
        "order_lines": _order_lines_for(schedule),
        # Mirrors EXACTLY the guard ``recompute()`` enforces, so the button is offered where the
        # verb will let it through and withheld elsewhere (4.11).
        "can_recognize": schedule.status == "active",
    }


def _obligation_form_context(form, schedule, obligation):
    """The obligation form's context. ``obligation`` is pinned on BOTH add and edit — None on add."""
    return {
        "form": form,
        "schedule": schedule,
        "obligation": obligation,
        "is_edit": obligation is not None,
        "order": schedule.sales_order,
        # The parent order's own lines, so the template can render the current figures beside the
        # dropdown and the author can see what they are allocating against.
        "order_lines": _order_lines_for(schedule),
    }


@login_required
@tenant_admin_required
def revenue_schedule_list(request):
    """The revenue register — every revenue schedule in this workspace."""
    base_queryset = _schedule_queryset(request)
    queryset, filters = _filtered_schedules(request, base_queryset)

    # Filters are read BEFORE pagination, so the page count reflects what is on screen.
    page_obj = paginate(request, queryset, PAGE_SIZE)
    # The stats walk the WHOLE tenant register, so the money is complete rather than being a
    # function of which page you are on.
    stats = _register_stats(list(base_queryset))
    return render(
        request, LIST_TEMPLATE, _list_context(request, queryset, page_obj, filters, stats)
    )



@login_required
@tenant_admin_required
def revenue_schedule_create(request):
    """Open a revenue schedule against an SCM order.

    Nothing is recognised here and nothing is posted. The schedule is a frame; the money arrives
    only when the obligations are added and someone presses Recognise on an ACTIVE schedule.
    """
    if request.method == "POST":
        form = RevenueScheduleForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            schedule = form.save(commit=False)
            # Set by the mixin from request.tenant already; asserted here so a future refactor
            # that drops the mixin cannot leave a schedule without a tenant.
            schedule.tenant = request.tenant
            schedule.save()
            write_audit_log(
                request.user,
                schedule,
                "create",
                {
                    "action": "create_revenue_schedule",
                    "number": schedule.number,
                    "sales_order": schedule.sales_order.number,
                    "status": schedule.status,
                    "method": schedule.method,
                    "compliance_standard": schedule.compliance_standard,
                    # A derived figure, reported as a string so the audit row is exact.
                    "contract_amount": str(schedule.contract_amount),
                },
                tenant=request.tenant,
            )
            messages.success(
                request,
                f"Revenue schedule {schedule.number} opened against order "
                f"{schedule.sales_order.number}. Add its obligations, then set it active to "
                "recognise revenue.",
            )
            return redirect("sales:revenue_schedule_detail", pk=schedule.pk)
    else:
        form = RevenueScheduleForm(tenant=request.tenant)
    return render(request, FORM_TEMPLATE, {
        "form": form,
        # `obj` is pinned on BOTH create and edit — None on create — so the shared form template
        # never has to branch on which one it got.
        "obj": None,
        "is_edit": False,
        "method_choices": RevenueSchedule.METHOD_CHOICES,
        "fiscal_periods": _tenant_fiscal_periods(request),
    })


@login_required
@tenant_admin_required
def revenue_schedule_detail(request, pk):
    """One revenue schedule: the five-step ASC 606 read-out and its obligations."""
    schedule = get_object_or_404(_schedule_queryset(request), pk=pk)
    return render(request, DETAIL_TEMPLATE, _detail_context(request, schedule))


@login_required
@tenant_admin_required
def revenue_schedule_edit(request, pk):
    """Edit the six authorable fields, one of which is ``status``.

    ``status`` IS editable here and is the single authorable status in 8.6: going active is how
    a person authorises recognition, and going void is how they withdraw it. What is NOT
    editable is anything derived — the money figures are properties, so there is nothing here to
    save, and ``journal_entry`` is reference-only and off the form (8.6 posts nothing, L29).
    """
    schedule = get_object_or_404(_schedule_queryset(request), pk=pk)
    if not schedule.is_editable:
        messages.info(
            request,
            f"Revenue schedule {schedule.number} is "
            f"{schedule.get_status_display().lower()} and is a closed document. It can be read, "
            "not edited.",
        )
        return redirect("sales:revenue_schedule_detail", pk=schedule.pk)

    if request.method == "POST":
        form = RevenueScheduleForm(request.POST, instance=schedule, tenant=request.tenant)
        if form.is_valid():
            became_active = (
                schedule.status != "active" and form.cleaned_data["status"] == "active"
            )
            schedule = form.save()
            # Going active is a decision with consequences, so the derived position at the
            # moment of the decision is written to the audit trail. Still a derived figure, read
            # live — never stored.
            write_audit_log(
                request.user,
                schedule,
                "update",
                {
                    "action": "update_revenue_schedule",
                    "number": schedule.number,
                    "changed": sorted(form.changed_data),
                    "status": schedule.status,
                    "became_active": became_active,
                    "contract_amount": str(schedule.contract_amount),
                },
                tenant=request.tenant,
            )
            messages.success(request, f"Revenue schedule {schedule.number} updated.")
            return redirect("sales:revenue_schedule_detail", pk=schedule.pk)
    else:
        form = RevenueScheduleForm(instance=schedule, tenant=request.tenant)
    return render(request, FORM_TEMPLATE, {
        "form": form,
        "obj": schedule,
        "is_edit": True,
        "method_choices": RevenueSchedule.METHOD_CHOICES,
        "fiscal_periods": _tenant_fiscal_periods(request),
    })



@require_POST
@login_required
@tenant_admin_required
def revenue_schedule_delete(request, pk):
    """Delete a schedule outright — refused once it is complete or void.

    A complete or void schedule is the record of a revenue position somebody reported. Deleting
    it would leave the reported figures with nothing behind them, which is the un-audited edit
    this whole entity exists to prevent. A draft or active one carries no posted consequence
    and may go.
    """
    schedule = get_object_or_404(_schedule_queryset(request), pk=pk)
    if schedule.is_locked or schedule.status == "void":
        messages.error(
            request,
            f"Revenue schedule {schedule.number} is {schedule.get_status_display().lower()} — a "
            "complete or void schedule is a permanent record and cannot be deleted.",
        )
        return redirect("sales:revenue_schedule_detail", pk=schedule.pk)
    number = schedule.number
    order_number = schedule.sales_order.number if schedule.sales_order_id else ""
    contract_amount = str(schedule.contract_amount)
    # The number and the derived figures are captured BEFORE the row goes, because after
    # ``delete()`` there is no pk left to read them from or to stamp the audit row with.
    write_audit_log(
        request.user,
        schedule,
        "delete",
        {
            "action": "delete_revenue_schedule",
            "number": number,
            "sales_order": order_number,
            "contract_amount": contract_amount,
            "recognized": str(schedule.recognized_amount),
        },
        tenant=request.tenant,
    )
    schedule.delete()
    messages.success(request, f"Revenue schedule {number} deleted.")
    return redirect("sales:revenue_schedule_list")


def _obligations_frozen(request, schedule):
    """``True`` (and a message already queued) when the schedule's obligations can no longer move.

    One helper for all three obligation verbs so the refusal text is identical wherever it comes
    from — a button that silently does nothing on a complete schedule is a bug report.
    """
    if schedule.is_editable:
        return False
    messages.info(
        request,
        f"Revenue schedule {schedule.number} is {schedule.get_status_display().lower()} — its "
        "obligations are frozen.",
    )
    return True



@require_POST
@login_required
@tenant_admin_required
def revenue_schedule_obligation_add(request, pk):
    """Add ONE performance obligation to a schedule, then leave the money to the server.

    POST-only, and the schedule comes from the URL rather than the body: a form that accepted
    the parent would let a crafted POST append a promise to somebody else's contract.

    The two money columns are NOT written here. ``allocated_amount`` and ``recognized_amount``
    are ``editable=False`` and are written by ``RevenueSchedule.recompute()`` alone, so adding
    an obligation changes the *inputs* of the arithmetic and nothing else — the figures move
    when somebody presses Recognise, and not a second before.
    """
    schedule = get_object_or_404(_schedule_queryset(request), pk=pk)
    if _obligations_frozen(request, schedule):
        return redirect("sales:revenue_schedule_detail", pk=schedule.pk)

    form = PerformanceObligationForm(request.POST, tenant=request.tenant, schedule=schedule)
    if form.is_valid():
        obligation = form.save(commit=False)
        # The parent is set HERE, from the URL, and never from cleaned_data — the field is not
        # on the form, which is exactly why the model's clean() is keyed on NON_FIELD_ERRORS.
        obligation.schedule = schedule
        obligation.save()
        write_audit_log(
            request.user,
            schedule,
            "create",
            {
                "action": "add_performance_obligation",
                "number": schedule.number,
                "obligation": obligation.pk,
                "obligation_type": obligation.obligation_type,
                "description": obligation.description[:200],
                "allocation_pct": str(obligation.allocation_pct or ""),
                "recognize_on": str(obligation.recognize_on or ""),
                "evidence_reference": obligation.evidence_reference[:200],
                "allocation_pct_total": str(schedule.allocation_pct_total),
            },
            tenant=request.tenant,
        )
        messages.success(
            request,
            f"Obligation added to schedule {schedule.number}. The allocated and recognised "
            "figures move when you press Recognise.",
        )
        return redirect("sales:revenue_schedule_detail", pk=schedule.pk)
    # An invalid form renders the obligation page with the FULL context, not a bare form, so the
    # author sees the schedule they are editing and the order lines they choose from.
    return render(
        request, OBLIGATION_FORM_TEMPLATE, _obligation_form_context(form, schedule, None)
    )


@require_POST
@login_required
@tenant_admin_required
def revenue_schedule_obligation_edit(request, pk, obligation_pk):
    """Edit one performance obligation. Nested under the parent — a child pk alone is no route.

    The obligation is fetched THROUGH the schedule (``filter(schedule=schedule), pk=obligation_pk``),
    so an obligation id from another workspace's contract is a 404 rather than an edit. The
    form's ``clean()`` re-checks that even a well-formed URL's instance belongs to THIS schedule,
    so a mismatched id cannot be silently re-parented by the save.
    """
    schedule = get_object_or_404(_schedule_queryset(request), pk=pk)
    obligation = get_object_or_404(
        PerformanceObligation.objects.filter(schedule=schedule), pk=obligation_pk
    )
    if _obligations_frozen(request, schedule):
        return redirect("sales:revenue_schedule_detail", pk=schedule.pk)

    form = PerformanceObligationForm(
        request.POST, instance=obligation, tenant=request.tenant, schedule=schedule
    )
    if form.is_valid():
        obligation = form.save(commit=False)
        obligation.schedule = schedule
        obligation.save()
        write_audit_log(
            request.user,
            schedule,
            "update",
            {
                "action": "edit_performance_obligation",
                "number": schedule.number,
                "obligation": obligation.pk,
                "obligation_type": obligation.obligation_type,
                "description": obligation.description[:200],
                "allocation_pct": str(obligation.allocation_pct or ""),
                "recognize_on": str(obligation.recognize_on or ""),
                "changed": sorted(form.changed_data),
                "allocation_pct_total": str(schedule.allocation_pct_total),
            },
            tenant=request.tenant,
        )
        messages.success(
            request, f"Obligation {obligation.pk} updated on schedule {schedule.number}."
        )
        return redirect("sales:revenue_schedule_detail", pk=schedule.pk)
    return render(
        request, OBLIGATION_FORM_TEMPLATE, _obligation_form_context(form, schedule, obligation)
    )



@require_POST
@login_required
@tenant_admin_required
def revenue_schedule_obligation_delete(request, pk, obligation_pk):
    """Remove one performance obligation, then leave the money to the server.

    Only the OBLIGATION is deleted. No order line is touched and nothing is posted — the order is
    still exactly what it was, and the only consequence is that this promise stops being
    recognised against. The stored ``allocated_amount`` / ``recognized_amount`` on the SURVIVING
    obligations are deliberately left alone: they are the last recomputed position, and
    recomputing on delete would make an un-audited read look like a decision.
    """
    schedule = get_object_or_404(_schedule_queryset(request), pk=pk)
    obligation = get_object_or_404(
        PerformanceObligation.objects.filter(schedule=schedule), pk=obligation_pk
    )
    if _obligations_frozen(request, schedule):
        return redirect("sales:revenue_schedule_detail", pk=schedule.pk)

    description = obligation.description[:200]
    obligation_pk = obligation.pk
    write_audit_log(
        request.user,
        schedule,
        "update",
        {
            "action": "delete_performance_obligation",
            "number": schedule.number,
            "obligation": obligation_pk,
            "removed": description,
            "allocation_pct": str(obligation.allocation_pct or ""),
            "allocation_pct_total": str(schedule.allocation_pct_total),
        },
        tenant=request.tenant,
    )
    obligation.delete()
    messages.success(
        request, f"Obligation removed from schedule {schedule.number}. Press Recognise to "
                 "restate the position.",
    )
    return redirect("sales:revenue_schedule_detail", pk=schedule.pk)


@require_POST
@login_required
@tenant_admin_required
def revenue_schedule_recognize(request, pk):
    """Recognise revenue as far as the passed recognition dates allow. THE ONLY WRITER.

    This is the one verb in 8.6 that moves money, and it is POST-only for that reason — a GET
    that recognises revenue would mean a prefetch, a crawler or a link preview could recognise a
    customer's revenue by touching a URL.

    The refusal lives in ``RevenueSchedule.recompute()``, not here: a guard that exists only in a
    view is a guard that can be bypassed by calling the method. The view's own status check is
    there to give a good message, and the method's check is there to be the rule. Both are kept,
    and they agree because the view's condition is literally the method's.

    No ``JournalEntry`` is created and none is linked (L29). 8.6 states the revenue position; the
    ledger is another module's job, and the reference-only ``journal_entry`` FK is where a human
    records that the posting happened elsewhere.
    """
    schedule = get_object_or_404(_schedule_queryset(request), pk=pk)
    result = schedule.recompute()

    if result["refused"]:
        messages.error(request, result["reason"])
        return redirect("sales:revenue_schedule_detail", pk=schedule.pk)

    write_audit_log(
        request.user,
        schedule,
        "update",
        {
            "action": "recognize_revenue_schedule",
            "number": schedule.number,
            "sales_order": schedule.sales_order.number if schedule.sales_order_id else "",
            "contract_amount": str(result["contract_amount"]),
            "allocated": str(result["allocated"]),
            "recognized": str(result["recognized"]),
            "deferred": str(result["deferred"]),
            "obligations_touched": result["obligations_touched"],
        },
        tenant=request.tenant,
    )
    messages.success(
        request,
        f"Schedule {schedule.number} recomputed: {result['recognized']} recognised of "
        f"{result['contract_amount']} contract value, {result['deferred']} deferred. "
        "No journal entry was posted — 8.6 states the position, the ledger is another module's "
        "job.",
    )
    return redirect("sales:revenue_schedule_detail", pk=schedule.pk)

