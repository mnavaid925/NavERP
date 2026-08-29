"""Procurement 6.11 Order Fulfillment & Tracking — DeliverySchedule views.

**Split Delivery Management** bullet: the instalment register (list / detail / CRUD) plus the
one-question **split console** that turns a single ordered line into N evenly-spaced instalments.

Deleting is open to any workspace member rather than admin-gated: an instalment hangs no
approval, no signature and no money off itself — it is a plan row, and the evidence of what
actually arrived lives on the ASN and (6.12) the receipt. Every other privileged path in 6.11
(the ASN's POD stamp, the backorder's deletion) stays gated.

Coverage figures are DERIVED (L29). The list page annotates the sibling-coverage aggregate as
``sched_total_annot`` with ONE correlated subquery so the ``coverage_pct`` column does not fire a
query per row; the model property prefers that annotation when it is present.
"""
from decimal import ROUND_HALF_UP, Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, DecimalField, OuterRef, Q, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from django.urls import reverse

from apps.core.crud import as_db_int
from apps.procurement.forms import DeliveryScheduleForm, DeliveryScheduleSplitForm
from apps.procurement.models import DeliverySchedule, split_po_line
from apps.procurement.views._common import *  # noqa: F401,F403
from apps.scm.models import PurchaseOrder, PurchaseOrderLine

ZERO = Decimal("0")

#: Quantity columns are DecimalField(14, 4); the aggregate of several of them needs headroom, so
#: the subquery declares its own wider output field rather than borrowing the column's.
_QTY_OUT = DecimalField(max_digits=18, decimal_places=4)

#: The list of orders offered in the ?po= filter widget. Capped — a workspace with thousands of
#: orders must not render a thousand-option <select>.
_PO_PICKER_LIMIT = 200


def _scheduled_total_subquery(tenant, outer_ref):
    """Correlated 'live scheduled quantity for this PO line' aggregate.

    ``outer_ref`` is ``"po_line"`` when annotating DeliverySchedule rows and ``"pk"`` when
    annotating PurchaseOrderLine rows — the same subquery serves both boards.
    """
    inner = (DeliverySchedule.objects
             .filter(tenant=tenant, po_line=OuterRef(outer_ref))
             .exclude(status="cancelled")
             .values("po_line")
             .annotate(total=Sum("scheduled_quantity"))
             .values("total"))
    return Coalesce(Subquery(inner, output_field=_QTY_OUT), Value(ZERO, output_field=_QTY_OUT))


def _purchase_order_picker(tenant):
    return (PurchaseOrder.objects.filter(tenant=tenant)
            .order_by("-order_date", "-id")[:_PO_PICKER_LIMIT])


def _coverage(scheduled_total, ordered):
    """(coverage_pct, is_under_covered) for a line — the detail page's own arithmetic, kept
    identical to ``DeliverySchedule.coverage_pct`` so the two can never disagree."""
    if not ordered or ordered <= ZERO:
        return 0, True
    pct = (scheduled_total / ordered * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    pct = max(0, min(100, int(pct)))
    return pct, pct < 100


@login_required
def deliveryschedule_list(request):
    today = timezone.localdate()
    qs = (DeliverySchedule.objects.filter(tenant=request.tenant)
          .select_related("po_line", "po_line__purchase_order", "ship_to",
                          # asn.__str__ walks purchase_order.number — the chained hop has to be
                          # selected too or {{ obj.asn }} costs two queries per row.
                          "asn", "asn__purchase_order")
          .annotate(sched_total_annot=_scheduled_total_subquery(request.tenant, "po_line")))

    # ?late=1 is NOT a crud_list filter (it is a compound condition, not one lookup): applied to
    # the queryset BEFORE crud_list so pagination and the page counts stay honest.
    if request.GET.get("late") == "1":
        qs = qs.filter(status__in=DeliverySchedule.OPEN_STATUSES, need_by_date__lt=today)

    stats = DeliverySchedule.objects.filter(tenant=request.tenant).aggregate(
        total=Count("id"),
        open=Count("id", filter=Q(status__in=DeliverySchedule.OPEN_STATUSES)),
        late=Count("id", filter=Q(status__in=DeliverySchedule.OPEN_STATUSES,
                                  need_by_date__lt=today)),
        received=Count("id", filter=Q(status="received")),
    )

    return crud_list(
        request, qs, "procurement/orderfulfillment/deliveryschedule/list.html",
        search_fields=["number", "po_line__item_description", "po_line__sku_hint",
                       "po_line__purchase_order__number"],
        # (get_param, orm_lookup, is_int) — the int ones go through as_db_int, so a hand-edited
        # ?po=abc / ?po=9999999999999999999999 skips the filter instead of 500ing (L11).
        filters=[("status", "status", False),
                 ("mode", "delivery_mode", False),
                 ("po", "po_line__purchase_order_id", True)],
        extra_context={
            "status_choices": DeliverySchedule.STATUS_CHOICES,
            "mode_choices": DeliverySchedule.MODE_CHOICES,
            "purchase_orders": _purchase_order_picker(request.tenant),
            "stats": stats,
        },
    )


@login_required
def deliveryschedule_detail(request, pk):
    obj = get_object_or_404(
        DeliverySchedule.objects.select_related(
            "po_line", "po_line__purchase_order", "po_line__purchase_order__vendor",
            "ship_to", "asn", "asn__purchase_order", "created_by"),
        pk=pk, tenant=request.tenant,
    )
    po_line = obj.po_line
    # INCLUDES obj itself so the running instalment table on the page is complete.
    siblings = (DeliverySchedule.objects
                .filter(tenant=request.tenant, po_line=po_line)
                .select_related("asn", "asn__purchase_order", "ship_to")
                .order_by("sequence", "id"))
    scheduled_total = (siblings.exclude(status="cancelled")
                       .aggregate(s=Sum("scheduled_quantity"))["s"] or ZERO)
    ordered = po_line.quantity or ZERO
    coverage_pct, is_under_covered = _coverage(scheduled_total, ordered)

    return render(request, "procurement/orderfulfillment/deliveryschedule/detail.html", {
        "obj": obj,
        "po_line": po_line,
        "order": po_line.purchase_order,
        "siblings": siblings,
        "scheduled_total": scheduled_total,
        "remaining_quantity": ordered - scheduled_total,
        "coverage_pct": coverage_pct,
        "is_under_covered": is_under_covered,
    })


@login_required
def deliveryschedule_create(request):
    """Thin wrapper around ``crud_create`` — the generic helper neither stamps this module's
    authorship (``created_by``) nor carries the ``?po_line=`` deep-link prefill, so the same
    save/audit/redirect shape is spelled out here (the 6.1 ``alert_create`` precedent)."""
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before scheduling deliveries.")
        return redirect("dashboard:home")

    if request.method == "POST":
        form = DeliveryScheduleForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.created_by = request.user
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Delivery schedule {obj.number} created.")
            return redirect("procurement:deliveryschedule_detail", pk=obj.pk)
    else:
        # A prefill is a convenience, NEVER an authorization path: the pk is only honoured when
        # the line really belongs to this workspace, and is dropped silently otherwise.
        initial = {}
        line_pk = as_db_int(request.GET.get("po_line"))
        if line_pk is not None:
            line = (PurchaseOrderLine.objects
                    .filter(pk=line_pk, purchase_order__tenant=request.tenant).first())
            if line is not None:
                initial["po_line"] = line.pk
        form = DeliveryScheduleForm(tenant=request.tenant, initial=initial)

    return render(request, "procurement/orderfulfillment/deliveryschedule/form.html",
                  {"form": form, "is_edit": False, "obj": None})


@login_required
def deliveryschedule_edit(request, pk):
    return crud_edit(
        request, model=DeliverySchedule, pk=pk, form_class=DeliveryScheduleForm,
        template="procurement/orderfulfillment/deliveryschedule/form.html",
        success_url=reverse("procurement:deliveryschedule_detail", args=[pk]),
    )


@login_required
@require_POST
def deliveryschedule_delete(request, pk):
    """POST-only. Any workspace member may drop a plan row — see the module docstring."""
    return crud_delete(request, model=DeliverySchedule, pk=pk,
                       success_url="procurement:deliveryschedule_list")


@login_required
def deliveryschedule_split(request):
    """**Split Delivery Management**: divide one PO line's uncommitted quantity into N
    evenly-spaced instalments.

    The whole split runs inside ``transaction.atomic()`` holding ``select_for_update()`` over the
    line's EXISTING schedule rows, so two buyers hitting Split at once cannot each read the same
    "already scheduled" total and together over-commit the line. ``split_po_line()`` re-checks
    coverage under that lock and raises ``ValidationError``, which lands as a non-field form
    error rather than a 500.
    """
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before splitting deliveries.")
        return redirect("dashboard:home")

    created = []
    if request.method == "POST":
        form = DeliveryScheduleSplitForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            po_line = form.cleaned_data["po_line"]
            instalments = form.cleaned_data["instalments"]
            try:
                with transaction.atomic():
                    # Materialize the lock BEFORE reading any total: an unevaluated queryset
                    # locks nothing.
                    list(DeliverySchedule.objects
                         .filter(tenant=request.tenant, po_line=po_line)
                         .select_for_update()
                         .values_list("pk", flat=True))
                    created = split_po_line(
                        request.tenant, po_line, instalments,
                        form.cleaned_data["first_date"], form.cleaned_data["interval_days"],
                        user=request.user,
                    )
            except ValidationError as exc:
                form.add_error(None, exc.messages)
            else:
                for row in created:
                    write_audit_log(request.user, row, "create",
                                    {"action": "split", "instalments": len(created),
                                     "po_line": str(po_line)[:120]})
                messages.success(
                    request,
                    f"{len(created)} delivery instalments created for "
                    f"{po_line.purchase_order.number}.",
                )
                url = reverse("procurement:deliveryschedule_list")
                return redirect(f"{url}?po={po_line.purchase_order_id}")
    else:
        form = DeliveryScheduleSplitForm(tenant=request.tenant)

    po_lines = (PurchaseOrderLine.objects
                .filter(purchase_order__tenant=request.tenant)
                .select_related("purchase_order")
                .annotate(scheduled_total=_scheduled_total_subquery(request.tenant, "pk"))
                .order_by("-purchase_order_id", "id")[:_PO_PICKER_LIMIT])

    return render(request, "procurement/orderfulfillment/deliveryschedule/split.html", {
        "form": form,
        "is_edit": False,
        "obj": None,
        "po_lines": po_lines,
    })
