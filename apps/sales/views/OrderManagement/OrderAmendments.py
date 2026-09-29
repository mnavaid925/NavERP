"""Sales 8.6 — the change order: 5 CRUD views + 4 line actions + 4 amendment actions.

This is the flow SCM 4.5 declined to build ("there is deliberately NO amendment flow here —
amend/cancel with impact analysis is Module 8.6's job"). It exists to make three promises
visible on a screen before anyone presses a button:

* **what the change is** — the lines it proposes to move, each with its before and after;
* **what it costs** — the delta on the order total and the net revenue impact, FROZEN at
  propose time so an approver approves a number and not a moving target;
* **what it disturbs** — the reservations the warehouse has already made and the shipments
  already raised, neither of which move with the amendment.

Ownership (L36/L37) is the constraint everything else follows from. ``scm.SalesOrder`` belongs
to SCM 4.5, and this file:

* reads the order through an FK and never declares, constructs or duplicates it;
* writes order line quantities and prices **only** through ``OrderAmendment.apply()``, which
  itself calls 4.5's own ``recalc_totals()`` and ``recompute_allocation_status()``;
* delegates the cancellation to 4.5's own logic, which already refuses while
  ``has_active_allocations()``, so there is no second cancellation path in the app;
* never writes ``SalesOrder.status`` directly. ``close`` is refused in ``apply()`` and said so.

Four rules govern every view here, and they are the same four as the hold workbench's:

* **Tenant scope, always.** ``filter(tenant=request.tenant)``, never ``.objects.all()``. The
  tenantless superuser therefore sees empty lists BY DESIGN, and every action verb 404s on
  another workspace's amendment.
* **Junk in, ignored out (L11).** ``?change_type=nonsense`` narrows nothing rather than raising,
  and ``?sales_order=`` goes through ``as_db_int`` so a 40-digit value is skipped instead of
  overflowing the driver.
* **No GET may mutate.** Every action verb is ``@require_POST`` + CSRF.
* **Audit on every mutation.** ``write_audit_log`` is POSITIONAL —
  ``(user, obj, action, changes, tenant)`` — and the instance is the SECOND argument.

Two structural rules are specific to this entity and are enforced by the URLconf rather than by
convention:

* **No route takes a child pk alone.** Both line actions are nested under the parent
  (``<int:pk>/lines/<int:line_pk>/``), so a line can only ever be reached through the amendment
  that owns it. That is simultaneously the CRUD-completeness answer and the tenant guard.
* **``?return_to=`` is never accepted.** A caller-supplied redirect target is an open redirect
  waiting to be phished; every POST here redirects to a name this file owns.
"""
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.crud import as_db_int, paginate
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.sales.forms.OrderManagement.OrderAmendments import (
    OrderAmendmentDecisionForm,
    OrderAmendmentForm,
    OrderAmendmentLineForm,
)
from apps.sales.models.OrderManagement.OrderAmendments import OrderAmendment, OrderAmendmentLine
from apps.sales.views._common import *  # noqa: F401,F403  (login_required, get_object_or_404, ...)


LIST_TEMPLATE = "sales/ordermanagement/orderamendment/list.html"
DETAIL_TEMPLATE = "sales/ordermanagement/orderamendment/detail.html"
FORM_TEMPLATE = "sales/ordermanagement/orderamendment/form.html"
LINE_FORM_TEMPLATE = "sales/ordermanagement/orderamendment/line_form.html"
IMPACT_TEMPLATE = "sales/ordermanagement/orderamendment/impact.html"

#: Rows per page. Matches the shared pagination partial's expectation of ``page_obj``.
PAGE_SIZE = 15

#: Statuses the open-queue board shows. Read from the model, never a second literal.
OPEN_STATUSES = OrderAmendment.OPEN_STATUSES



def _amendment_queryset(request):
    """The tenant-scoped amendment register. One place, so no view can forget the filter."""
    return OrderAmendment.objects.filter(tenant=request.tenant).select_related(
        "sales_order", "sales_order__customer", "requested_by", "decided_by", "applied_by",
    )


def _amendment_lines_page(request, amendment):
    """The amendment's proposed lines as a Page of 15, with the order lines pre-fetched.

    A Page rather than a list because the shared pagination partial reads ``page_obj``, and
    ``lines`` is an ALIAS of the very same Page — never a second paginator run over the same
    queryset.
    """
    queryset = amendment.lines.select_related("sales_order_line", "sales_order_line__item")
    return paginate(request, queryset, PAGE_SIZE)


def _tenant_sales_orders(request, amendable_only=False):
    """The order dropdown for the filters and the form. Read-only over SCM 4.5's table."""
    from apps.scm.models import SalesOrder

    queryset = SalesOrder.objects.filter(tenant=request.tenant)
    if amendable_only:
        queryset = queryset.filter(status__in=OrderAmendment.AMENDABLE_STATUSES)
    return queryset.select_related("customer").order_by("-order_date", "-id")


def _order_lines_for(amendment):
    """The parent order's own lines, for the line form's dropdown and the impact page."""
    from apps.scm.models import SalesOrderLine

    if amendment is None or not amendment.sales_order_id:
        return SalesOrderLine.objects.none()
    return SalesOrderLine.objects.filter(
        sales_order_id=amendment.sales_order_id
    ).select_related("item").order_by("id")


def _snapshot_impact(amendment):
    """Freeze ``amendment.recompute_impact()`` into the column. THE ONLY WRITER.

    Called after a change to the amendment or to any of its lines — never on read, and never
    from a form. That is what makes the blob evidence rather than a live query: the impact page
    can show it beside today's figures and the two can be seen to disagree.
    """
    amendment.impact_snapshot = amendment.recompute_impact()
    amendment.save(update_fields=["impact_snapshot", "updated_at"])
    return amendment.impact_snapshot


def _detail_context(request, amendment, decision_form=None, line_form=None):
    """The FULL detail context, in one place, because several views must all be able to render it.

    ``order_amendment_decide`` re-renders this on an invalid form, which is the difference
    between "your decision was not recorded" and a bare form with no amendment number on it.
    Building it in one helper is what guarantees the error path and the normal path cannot drift
    apart — and therefore that a context key a template reads can never go missing on one of
    them (L8: a missing key is a silently blank region at HTTP 200).
    """
    order = amendment.sales_order
    page_obj = _amendment_lines_page(request, amendment)
    return {
        "amendment": amendment,
        "lines": page_obj,
        "page_obj": page_obj,
        "order": order,
        # The PARSED dict, never the raw column: a malformed blob degrades to an empty panel
        # via parsed_impact rather than rendering a JSON string into the page (or 500ing the
        # one page whose whole job is to explain a commercial decision).
        "impact": amendment.parsed_impact,
        "decision_form": decision_form or OrderAmendmentDecisionForm(),
        "line_form": line_form or OrderAmendmentLineForm(
            tenant=request.tenant, amendment=amendment
        ),
        # The three action flags. Each mirrors EXACTLY the guard its verb enforces, so a button
        # that is offered cannot refuse on click and a button that is withheld is explained
        # (4.11).
        "can_decide": amendment.status in ("draft", "pending"),
        "can_apply": (
            amendment.status == "approved"
            and order is not None
            and order.status in OrderAmendment.AMENDABLE_STATUSES
        ),
        "can_withdraw": amendment.status in ("draft", "pending"),
    }


def _list_context(request, queryset, page_obj, filters, stats):
    """The list board's context. Shared by the register and the open queue so they cannot drift."""
    context = {
        "amendments": page_obj,
        "page_obj": page_obj,
        "change_type_choices": OrderAmendment.CHANGE_TYPE_CHOICES,
        "status_choices": OrderAmendment.STATUS_CHOICES,
        "sales_orders": _tenant_sales_orders(request),
        "stats": stats,
    }
    context.update(filters)
    return context


def _filtered_amendments(request, base_queryset):
    """Apply the four list filters to a queryset, returning ``(queryset, echo, stats)``.

    Every value is validated before it is used. A choice filter ignores anything outside its
    own ``CHOICES`` and a FK filter goes through ``as_db_int`` — so ``?change_type=nonsense``
    and ``?sales_order=abc`` both narrow nothing rather than raising on a URL anybody can type
    into the address bar (L11). Zero is skipped too: it is not a pk, and filtering on it
    returns an empty page that reads as "this workspace has no amendments", which is a lie.
    """
    queryset = base_queryset

    q = request.GET.get("q", "").strip()
    if q:
        queryset = queryset.filter(
            Q(number__icontains=q)
            | Q(reason__icontains=q)
            | Q(sales_order__number__icontains=q)
        )

    change_type = request.GET.get("change_type", "").strip()
    if change_type in dict(OrderAmendment.CHANGE_TYPE_CHOICES):
        queryset = queryset.filter(change_type=change_type)
    else:
        change_type = ""

    status = request.GET.get("status", "").strip()
    if status in dict(OrderAmendment.STATUS_CHOICES):
        queryset = queryset.filter(status=status)
    else:
        status = ""

    sales_order_filter = request.GET.get("sales_order", "").strip()
    sales_order_pk = as_db_int(sales_order_filter)
    if sales_order_pk:
        queryset = queryset.filter(sales_order_id=sales_order_pk)
    else:
        sales_order_filter = ""

    filters = {
        "q": q,
        "change_type": change_type,
        "status": status,
        "sales_order": sales_order_filter,
    }
    return queryset, filters


@login_required
@tenant_admin_required
def order_amendment_list(request):
    """The amendment register — every change order in this workspace."""
    base_queryset = _amendment_queryset(request)
    queryset, filters = _filtered_amendments(request, base_queryset)

    # Filters are read BEFORE pagination, so the page count reflects what is on screen.
    page_obj = paginate(request, queryset, PAGE_SIZE)

    # Stats describe the WHOLE tenant register, not the filtered page — a stats strip that
    # changes when you search is a stats strip nobody trusts. Counts, one grouped query.
    stats = base_queryset.aggregate(
        total=Count("id"),
        open=Count("id", filter=Q(status__in=OPEN_STATUSES)),
        approved=Count("id", filter=Q(status="approved")),
        applied=Count("id", filter=Q(status="applied")),
    )
    return render(request, LIST_TEMPLATE, _list_context(request, queryset, page_obj, filters, stats))


@login_required
@tenant_admin_required
def order_amendment_create(request):
    """Propose a change order.

    The impact snapshot is written by the SERVER at this moment and never again, so an approver
    is looking at the consequence as it stood when the change was proposed. That is also why
    it cannot be typed: a clerk who could write "no impact" into the evidence field would have
    nothing left to check.
    """
    if request.method == "POST":
        form = OrderAmendmentForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            amendment = form.save(commit=False)
            amendment.tenant = request.tenant
            amendment.status = "draft"
            amendment.requested_by = request.user
            amendment.requested_at = timezone.now()
            amendment.save()
            # Frozen AFTER the row exists, because the snapshot names the amendment.
            snapshot = _snapshot_impact(amendment)
            write_audit_log(
                request.user,
                amendment,
                "create",
                {
                    "action": "create_order_amendment",
                    "number": amendment.number,
                    "sales_order": amendment.sales_order.number,
                    "change_type": amendment.change_type,
                    "delta_total": snapshot.get("delta_total"),
                    "allocations_affected": snapshot.get("allocations_affected"),
                },
                tenant=request.tenant,
            )
            messages.success(
                request,
                f"Amendment {amendment.number} proposed against order "
                f"{amendment.sales_order.number}. Add its lines, then send it for approval.",
            )
            return redirect("sales:order_amendment_detail", pk=amendment.pk)
    else:
        form = OrderAmendmentForm(tenant=request.tenant)
    return render(request, FORM_TEMPLATE, {
        "form": form,
        # `obj` is pinned on BOTH create and edit — None on create — so the shared form
        # template never has to branch on which one it got.
        "obj": None,
        "is_edit": False,
        "change_type_choices": OrderAmendment.CHANGE_TYPE_CHOICES,
        # Already filtered to AMENDABLE_STATUSES; a draft or shipped order is not offered.
        "sales_orders": _tenant_sales_orders(request, amendable_only=True),
    })


@login_required
@tenant_admin_required
def order_amendment_detail(request, pk):
    """One change order: its lines, its frozen impact, and the verbs its status allows."""
    amendment = get_object_or_404(_amendment_queryset(request), pk=pk)
    return render(request, DETAIL_TEMPLATE, _detail_context(request, amendment))


@login_required
@tenant_admin_required
def order_amendment_edit(request, pk):
    """Edit the four authorable fields. The lifecycle is NOT editable here.

    ``status``, ``impact_snapshot`` and every action stamp are workflow-owned. An edit form
    that could flip a withdrawn amendment back to approved would make the audit trail a
    suggestion, and one that could re-freeze the impact snapshot at will would let the number
    an approver signed off be quietly replaced after the fact.
    """
    amendment = get_object_or_404(_amendment_queryset(request), pk=pk)
    if not amendment.is_open:
        messages.info(
            request,
            f"Amendment {amendment.number} is {amendment.get_status_display().lower()} and is a "
            "closed document. It can be read, not edited.",
        )
        return redirect("sales:order_amendment_detail", pk=amendment.pk)

    if request.method == "POST":
        form = OrderAmendmentForm(request.POST, instance=amendment, tenant=request.tenant)
        if form.is_valid():
            amendment = form.save()
            # A changed reason or change_type means the proposal is no longer the one that was
            # snapshotted, so the evidence is re-frozen. This is one of only three writers of
            # the column, and it is still the server writing it.
            snapshot = _snapshot_impact(amendment)
            write_audit_log(
                request.user,
                amendment,
                "update",
                {
                    "action": "update_order_amendment",
                    "number": amendment.number,
                    "changed": sorted(form.changed_data),
                    "delta_total": snapshot.get("delta_total"),
                },
                tenant=request.tenant,
            )
            messages.success(request, f"Amendment {amendment.number} updated.")
            return redirect("sales:order_amendment_detail", pk=amendment.pk)
    else:
        form = OrderAmendmentForm(instance=amendment, tenant=request.tenant)
    return render(request, FORM_TEMPLATE, {
        "form": form,
        "obj": amendment,
        "is_edit": True,
        "change_type_choices": OrderAmendment.CHANGE_TYPE_CHOICES,
        "sales_orders": _tenant_sales_orders(request, amendable_only=True),
    })


@require_POST
@login_required
@tenant_admin_required
def order_amendment_delete(request, pk):
    """Delete a change order outright — refused once it has been approved.

    An applied amendment is the record of a change that actually moved a customer's order.
    Deleting it would leave the order carrying figures nobody can account for, which is the
    un-audited edit this whole entity exists to prevent. A draft or pending one carries no
    consequence and may go.
    """
    amendment = get_object_or_404(_amendment_queryset(request), pk=pk)
    if not amendment.is_open or amendment.status == "approved":
        messages.error(
            request,
            f"Amendment {amendment.number} has already been approved. An approved, applied, "
            "rejected or withdrawn change order is a permanent record and cannot be deleted.",
        )
        return redirect("sales:order_amendment_detail", pk=amendment.pk)
    number = amendment.number
    order_number = amendment.sales_order.number if amendment.sales_order_id else ""
    # The number is captured BEFORE the row goes, because after ``delete()`` there is no pk
    # left to stamp the audit row with.
    write_audit_log(
        request.user,
        amendment,
        "delete",
        {
            "action": "delete_order_amendment",
            "number": number,
            "sales_order": order_number,
            "change_type": amendment.change_type,
        },
        tenant=request.tenant,
    )
    amendment.delete()
    messages.success(request, f"Amendment {number} deleted.")
    return redirect("sales:order_amendment_list")


def _line_form_context(form, amendment, line):
    """The line form's context. ``line`` is pinned on BOTH add and edit — None on add."""
    return {
        "form": form,
        "amendment": amendment,
        "line": line,
        "is_edit": line is not None,
        "order": amendment.sales_order,
        # The parent order's own lines, so the template can render the current figures beside
        # the dropdown and the author can see what they are changing.
        "order_lines": _order_lines_for(amendment),
    }


def _lines_frozen(request, amendment):
    """``True`` (and a message already queued) when the amendment's lines can no longer move.

    One helper for all three line verbs so the refusal text is identical wherever it comes from
    — a line button that silently does nothing on a withdrawn amendment is a bug report.
    """
    if amendment.is_open:
        return False
    messages.info(
        request,
        f"Amendment {amendment.number} is {amendment.get_status_display().lower()} — its lines "
        "are frozen.",
    )
    return True


@require_POST
@login_required
@tenant_admin_required
def order_amendment_line_add(request, pk):
    """Add ONE proposed line change to an open amendment, then re-freeze the impact.

    POST-only, and the amendment comes from the URL rather than the body: a form that accepted
    the parent would let a crafted POST append a line to somebody else's change order.

    The snapshot is re-frozen on every line change because the amendment the approver will read
    has just changed. Freezing only at create time would show an approver an impact analysis for
    a proposal that no longer exists — stale in the one direction that makes a change look
    cheaper than it is.
    """
    amendment = get_object_or_404(_amendment_queryset(request), pk=pk)
    if _lines_frozen(request, amendment):
        return redirect("sales:order_amendment_detail", pk=amendment.pk)

    form = OrderAmendmentLineForm(request.POST, tenant=request.tenant, amendment=amendment)
    if form.is_valid():
        line = form.save(commit=False)
        # The parent is set HERE, from the URL, and never from cleaned_data — the field is not
        # on the form, which is exactly why the model's clean() is keyed on NON_FIELD_ERRORS.
        line.amendment = amendment
        line.save()
        snapshot = _snapshot_impact(amendment)
        write_audit_log(
            request.user,
            amendment,
            "create",
            {
                "action": "add_amendment_line",
                "number": amendment.number,
                "operation": line.operation,
                "sales_order_line": line.sales_order_line_id,
                "new_quantity": str(line.new_quantity or ""),
                "new_unit_price": str(line.new_unit_price or ""),
                "delta_total": snapshot.get("delta_total"),
            },
            tenant=request.tenant,
        )
        messages.success(request, f"Line added to amendment {amendment.number}.")
        return redirect("sales:order_amendment_detail", pk=amendment.pk)
    # An invalid form renders the line page with the FULL context, not a bare form, so the
    # author can see the amendment they are editing and the order lines they choose from.
    return render(request, LINE_FORM_TEMPLATE, _line_form_context(form, amendment, None))


@require_POST
@login_required
@tenant_admin_required
def order_amendment_line_edit(request, pk, line_pk):
    """Edit one proposed line change. Nested under the parent — a child pk alone is no route.

    The line is fetched THROUGH the amendment (``filter(amendment=amendment), pk=line_pk``), so
    a line id from another tenant's change order is a 404 rather than an edit.
    """
    amendment = get_object_or_404(_amendment_queryset(request), pk=pk)
    line = get_object_or_404(
        OrderAmendmentLine.objects.filter(amendment=amendment), pk=line_pk
    )
    if _lines_frozen(request, amendment):
        return redirect("sales:order_amendment_detail", pk=amendment.pk)

    form = OrderAmendmentLineForm(
        request.POST, instance=line, tenant=request.tenant, amendment=amendment
    )
    if form.is_valid():
        line = form.save(commit=False)
        line.amendment = amendment
        line.save()
        snapshot = _snapshot_impact(amendment)
        write_audit_log(
            request.user,
            amendment,
            "update",
            {
                "action": "edit_amendment_line",
                "number": amendment.number,
                "line": line.pk,
                "operation": line.operation,
                "sales_order_line": line.sales_order_line_id,
                "new_quantity": str(line.new_quantity or ""),
                "new_unit_price": str(line.new_unit_price or ""),
                "delta_total": snapshot.get("delta_total"),
            },
            tenant=request.tenant,
        )
        messages.success(request, f"Line {line.pk} updated on amendment {amendment.number}.")
        return redirect("sales:order_amendment_detail", pk=amendment.pk)
    return render(request, LINE_FORM_TEMPLATE, _line_form_context(form, amendment, line))


@require_POST
@login_required
@tenant_admin_required
def order_amendment_line_delete(request, pk, line_pk):
    """Remove one proposed line change, then re-freeze the impact.

    Only the PROPOSAL is deleted. No order line is touched: nothing has been applied, so the
    order is still exactly as it was before the amendment was proposed.
    """
    amendment = get_object_or_404(_amendment_queryset(request), pk=pk)
    line = get_object_or_404(
        OrderAmendmentLine.objects.filter(amendment=amendment), pk=line_pk
    )
    if _lines_frozen(request, amendment):
        return redirect("sales:order_amendment_detail", pk=amendment.pk)

    description = (
        f"{line.get_operation_display()} line {line.sales_order_line_id}"
        if line.sales_order_line_id
        else f"Add line ({line.new_quantity or '?'})"
    )
    line_pk = line.pk
    line.delete()
    snapshot = _snapshot_impact(amendment)
    write_audit_log(
        request.user,
        amendment,
        "update",
        {
            "action": "delete_amendment_line",
            "number": amendment.number,
            "line": line_pk,
            "removed": description,
            "delta_total": snapshot.get("delta_total"),
        },
        tenant=request.tenant,
    )
    messages.success(request, f"Line removed from amendment {amendment.number}.")
    return redirect("sales:order_amendment_detail", pk=amendment.pk)


@require_POST
@login_required
@tenant_admin_required
def order_amendment_decide(request, pk):
    """Approve or reject a change order. ONE form, two outcomes, one set of stamps.

    The **view** writes ``decided_by`` / ``decided_at`` and the status; the form only carries
    the author's choice and their note. An invalid form re-renders the FULL detail context
    rather than a bare form — an approver who mistypes the radio buttons should come back to
    the amendment they were reading, with the impact still on screen.
    """
    amendment = get_object_or_404(_amendment_queryset(request), pk=pk)

    if request.method == "POST":
        form = OrderAmendmentDecisionForm(request.POST)
        if form.is_valid():
            if amendment.status not in ("draft", "pending"):
                messages.error(
                    request,
                    f"Amendment {amendment.number} is already "
                    f"{amendment.get_status_display().lower()} — it cannot be decided again.",
                )
                return redirect("sales:order_amendment_detail", pk=amendment.pk)
            decision = form.cleaned_data["decision"]
            note = (form.cleaned_data.get("note") or "").strip()
            amendment.status = decision
            amendment.decided_by = request.user
            amendment.decided_at = timezone.now()
            if note:
                amendment.notes = f"{amendment.notes}\n{decision.title()}: {note}".strip()
            amendment.save(update_fields=[
                "status", "decided_by", "decided_at", "notes", "updated_at",
            ])
            write_audit_log(
                request.user,
                amendment,
                "update",
                {
                    "action": "decide_order_amendment",
                    "number": amendment.number,
                    "decision": decision,
                    "note": note[:500],
                },
                tenant=request.tenant,
            )
            messages.success(
                request,
                f"Amendment {amendment.number} {decision}."
                + (" It can now be applied to the order." if decision == "approved" else ""),
            )
            return redirect("sales:order_amendment_detail", pk=amendment.pk)
    else:
        form = OrderAmendmentDecisionForm()
    return render(request, DETAIL_TEMPLATE, _detail_context(request, amendment, decision_form=form))


@require_POST
@login_required
@tenant_admin_required
def order_amendment_apply(request, pk):
    """Apply an APPROVED change order. The one verb that moves the customer's order.

    The order is re-read with ``select_for_update()`` **inside** the transaction, so two clerks
    pressing Apply at the same moment cannot both write against the same starting figures — the
    second one blocks, then re-reads and applies to whatever the first left. All the actual
    refusals live in ``OrderAmendment.apply()`` rather than here, because a guard that exists
    only in a view is a guard that can be bypassed by calling the method.
    """
    amendment = get_object_or_404(_amendment_queryset(request), pk=pk)

    if amendment.status != "approved":
        messages.error(
            request,
            f"Amendment {amendment.number} is {amendment.get_status_display().lower()} — only an "
            "approved change order can be applied.",
        )
        return redirect("sales:order_amendment_detail", pk=amendment.pk)

    note = (request.POST.get("note") or "").strip()
    try:
        with transaction.atomic():
            from apps.scm.models import SalesOrder

            # The row is re-fetched under a row lock INSIDE the transaction. select_for_update
            # outside one is a no-op on SQLite and a lie on MySQL.
            locked_order = SalesOrder.objects.select_for_update().get(
                pk=amendment.sales_order_id, tenant=request.tenant
            )
            result = amendment.apply(request.user, locked_order, note)
    except OrderAmendment.DoesNotExist:
        messages.error(request, "The order this amendment points at no longer exists.")
        return redirect("sales:order_amendment_list")
    except ValidationError as exc:
        # Every message apply() raises is non-field, so this join never loses one.
        messages.error(request, " ".join(exc.messages))
        return redirect("sales:order_amendment_detail", pk=amendment.pk)

    write_audit_log(
        request.user,
        amendment,
        "update",
        {
            "action": "apply_order_amendment",
            "number": amendment.number,
            "sales_order": result["order"],
            "change_type": amendment.change_type,
            "lines": result["lines"],
            "cancelled": result["cancelled"],
        },
        tenant=request.tenant,
    )
    if result["cancelled"]:
        messages.success(
            request,
            f"Amendment {amendment.number} applied — order {result['order']} is now cancelled.",
        )
    else:
        messages.success(
            request,
            f"Amendment {amendment.number} applied to order {result['order']}. Totals were "
            "recalculated by SCM's own logic.",
        )
    return redirect("sales:order_amendment_detail", pk=amendment.pk)


@require_POST
@login_required
@tenant_admin_required
def order_amendment_withdraw(request, pk):
    """Withdraw a draft or pending change order — the proposer changing their mind.

    An APPROVED amendment cannot be withdrawn: it has been approved against a specific impact
    analysis, and the honest way to undo that is to apply it or propose a new one. A blanket
    "withdraw" that worked on an approved document would make the approval meaningless.
    """
    amendment = get_object_or_404(_amendment_queryset(request), pk=pk)
    if amendment.status not in ("draft", "pending"):
        messages.error(
            request,
            f"Amendment {amendment.number} is {amendment.get_status_display().lower()} and can no "
            "longer be withdrawn. An approved change order must be applied, not withdrawn.",
        )
        return redirect("sales:order_amendment_detail", pk=amendment.pk)

    amendment.status = "withdrawn"
    amendment.save(update_fields=["status", "updated_at"])
    write_audit_log(
        request.user,
        amendment,
        "update",
        {"action": "withdraw_order_amendment", "number": amendment.number},
        tenant=request.tenant,
    )
    messages.success(request, f"Amendment {amendment.number} withdrawn.")
    return redirect("sales:order_amendment_detail", pk=amendment.pk)


@login_required
@tenant_admin_required
def order_amendment_open_queue(request):
    """The work queue: the amendments that still need a decision or an application.

    The same list template with the same context, pre-filtered to
    ``status__in=("draft", "pending", "approved")`` read from ``OPEN_STATUSES``. Sharing the
    context builder is what guarantees this board and the register cannot drift apart in their
    filters or their context keys — a second hand-built context here would be the classic way
    one of the two pages renders blank at HTTP 200 (L8).

    A GET, because it reads and mutates nothing. The Apply and Withdraw buttons on the rows it
    renders are POST forms with CSRF, so no GET reaches a mutator.
    """
    base_queryset = _amendment_queryset(request)
    queryset = base_queryset.filter(status__in=OPEN_STATUSES)
    # The queue is a VIEW of the open set, so a user arriving with the register's filters keeps
    # them — a search that silently did nothing because the URL changed would read as a bug.
    queryset, filters = _filtered_amendments(request, queryset)
    page_obj = paginate(request, queryset, PAGE_SIZE)
    stats = base_queryset.aggregate(
        total=Count("id"),
        open=Count("id", filter=Q(status__in=OPEN_STATUSES)),
        approved=Count("id", filter=Q(status="approved")),
        applied=Count("id", filter=Q(status="applied")),
    )
    return render(request, LIST_TEMPLATE, _list_context(request, queryset, page_obj, filters, stats))


@login_required
@tenant_admin_required
def order_amendment_impact(request, pk):
    """The pre-approval impact read-out: the FROZEN snapshot BESIDE today's live figures.

    The two columns on this page are the whole point of the entity, and they are two different
    things on purpose:

    * the **frozen snapshot** is what the amendment looked like when it was proposed — what
      each line was, what it proposes, the total delta, the reservations and shipments counted
      at that moment. It is what an approver signs off, and it does not move afterwards.
    * the **live figures** are the order as it is RIGHT NOW, plus the reservations and shipments
      that exist now, plus whether a revenue schedule has since been opened against it.

    When they agree, the approval was taken against the current state. When they disagree — and
    they will disagree the moment somebody edits the order directly in SCM, or an allocation is
    made, or a shipment is raised — that difference is the finding. The template SAYS which is
    which in prose rather than relying on a column heading; a page showing two totals with no
    indication which is the evidence and which is the rumour is how an approval goes wrong.

    Read-only. Nothing on this page mutates, and nothing here re-freezes the snapshot — the
    whole point is that it is what it was.
    """
    amendment = get_object_or_404(_amendment_queryset(request), pk=pk)
    order = amendment.sales_order
    page_obj = _amendment_lines_page(request, amendment)

    allocations = []
    shipments = []
    schedule = None
    if order is not None:
        from apps.scm.models import SalesOrderAllocation, Shipment

        allocations = list(
            SalesOrderAllocation.objects.filter(
                sales_order_line__sales_order_id=order.pk
            ).select_related("sales_order_line", "location").order_by("id")
        )
        shipments = list(
            Shipment.objects.filter(sales_order_id=order.pk).order_by("-id")
        )
        # Entity 4 of this sub-module owns RevenueSchedule. Imported defensively so this page
        # renders before that model exists rather than 500ing on the one screen whose job is
        # to tell the approver what else is attached to this order.
        try:
            from apps.sales.models.OrderManagement.RevenueSchedules import RevenueSchedule

            schedule = RevenueSchedule.objects.filter(
                tenant=request.tenant, sales_order_id=order.pk
            ).first()
        except ImportError:
            schedule = None

    return render(request, IMPACT_TEMPLATE, {
        "amendment": amendment,
        # The FROZEN blob, parsed. Never recomputed here.
        "impact": amendment.parsed_impact,
        "lines": page_obj,
        "page_obj": page_obj,
        "order": order,
        "allocations": allocations,
        "shipments": shipments,
        "schedule": schedule,
    })
