"""Procurement 6.11 Order Fulfillment & Tracking — AdvancedShipmentNotice views.

**Advanced Shipping Notice (ASN)** bullet: record what a supplier says is on its way against a
purchase order, watch it move, and confirm it when it lands. Recording and moving a notice is
open to any workspace member (it is bookkeeping about someone else's truck); DELETING one is
tenant-admin gated and drafts-only, because a submitted notice is part of the receiving trail
that 6.12 reads.

Every status guard is enforced HERE as well as in the template — hiding a button does not stop a
direct POST — and again inside the model's verb methods, which run under a row lock so a
double-submitted confirmation cannot re-stamp a delivery.

READ-ONLY against the spine (L36): nothing in this module writes ``scm.PurchaseOrder`` or
``scm.PurchaseOrderLine``.
"""
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Q
from django.urls import reverse

from apps.core.crud import _changed
from apps.procurement.forms import (
    AdvancedShipmentNoticeForm,
    AsnCancelForm,
    AsnDeliveryConfirmForm,
    AsnLineFormSet,
)
from apps.procurement.models import AdvancedShipmentNotice
from apps.procurement.views._common import *  # noqa: F401,F403
# The confirmation board's tab whitelist — the inline confirm form posts back here with its
# ?due= tab, and this is the one definition of which values are real.
from apps.procurement.views.OrderFulfillment.FulfillmentBoards import _BUCKET_KEYS
from apps.scm.models import Carrier, PurchaseOrder

#: Statuses whose header/lines are frozen — the edit page refuses them server-side.
_CLOSED_STATUSES = ("delivered", "cancelled")


def _tenant_orders(request):
    """Recent purchase orders for the ``?po=`` dropdown. Capped: the filter widget is a
    convenience, not a browsable index of every order this workspace has ever raised."""
    return (PurchaseOrder.objects.filter(tenant=request.tenant)
            .order_by("-order_date", "-id")[:200])


def _tenant_carriers(request):
    return (Carrier.objects.filter(tenant=request.tenant)
            .select_related("party").order_by("party__name"))


@login_required
def asn_list(request):
    """The ASN register. Every filter is applied BEFORE pagination, so the page counts and the
    stat cards tell the same story the rows do."""
    qs = (AdvancedShipmentNotice.objects.filter(tenant=request.tenant)
          .select_related("purchase_order", "purchase_order__vendor", "carrier",
                          "carrier__party", "shipment")
          .annotate(line_total=Count("lines"))
          # Restate Meta.ordering EXPLICITLY. ``annotate(Count(...))`` sets a GROUP BY, and
          # ``QuerySet.ordered`` reports False whenever group_by is set even though the compiler
          # still emits Meta.ordering — which makes Paginator raise UnorderedObjectListWarning on
          # every request. Saying it here is the same SQL, minus the noise.
          .order_by("-created_at", "-id"))

    # ``late`` is date arithmetic against "now", not a column, so it cannot be a crud_list filter
    # tuple. Applied to the queryset first — never to the page, which would make the counts lie.
    if request.GET.get("late", "").strip() == "1":
        qs = qs.filter(status__in=AdvancedShipmentNotice.IN_FLIGHT_STATUSES,
                       expected_delivery_date__lt=timezone.localdate())

    return crud_list(
        request, qs, "procurement/orderfulfillment/asn/list.html",
        search_fields=["number", "supplier_reference", "tracking_number",
                       "purchase_order__number"],
        # (get_param, orm_lookup, is_int) — the int ones go through crud_list's as_db_int guard,
        # so ?carrier=abc / ?po=999999999999999999999 skip the filter instead of 500ing (L11).
        filters=[
            ("status", "status", False),
            ("source", "source", False),
            ("carrier", "carrier_id", True),
            ("po", "purchase_order_id", True),
        ],
        extra_context={
            "status_choices": AdvancedShipmentNotice.STATUS_CHOICES,
            "source_choices": AdvancedShipmentNotice.SOURCE_CHOICES,
            "carriers": _tenant_carriers(request),
            "purchase_orders": _tenant_orders(request),
            "stats": _asn_stats(request),
        },
    )


def _asn_stats(request):
    """The four stat cards, in ONE aggregate query rather than four ``.count()`` round trips.

    Deliberately computed over the WHOLE workspace, not the filtered page: a stat card answers
    "how is the inbound pipeline doing?", which must not change because someone typed a search.
    """
    today = timezone.localdate()
    in_flight = Q(status__in=AdvancedShipmentNotice.IN_FLIGHT_STATUSES)
    return AdvancedShipmentNotice.objects.filter(tenant=request.tenant).aggregate(
        total=Count("id"),
        in_flight=Count("id", filter=in_flight),
        late=Count("id", filter=in_flight & Q(expected_delivery_date__lt=today)),
        delivered=Count("id", filter=Q(status="delivered")),
    )


@login_required
def asn_detail(request, pk):
    obj = get_object_or_404(
        AdvancedShipmentNotice.objects.select_related(
            "purchase_order", "purchase_order__vendor", "carrier", "carrier__party",
            "shipment", "confirmed_by", "created_by"),
        pk=pk, tenant=request.tenant,
    )
    is_admin = bool(request.user.is_superuser
                    or getattr(request.user, "is_tenant_admin", False))
    # The model's memoized fetch — the same rows (and the same memoized PurchaseOrderLine
    # instances) the discrepancy fold already walked, so the template's per-row
    # outstanding/variance reads cost nothing extra.
    lines = obj.line_rows()
    # ...but each of those PurchaseOrderLine instances would still fire its OWN receipt
    # aggregate the first time `outstanding_at_declare` asks. Seed every memo from the spine's
    # one-query map instead: N aggregates become 1, which is exactly the caller pattern
    # PurchaseOrder.received_by_line() documents.
    received = obj.purchase_order.received_by_line()
    for row in lines:
        if row.po_line_id:
            row.po_line._received_qty_cache = received.get(row.po_line_id) or Decimal("0")
    return render(request, "procurement/orderfulfillment/asn/detail.html", {
        "obj": obj,
        "lines": lines,
        "order": obj.purchase_order,
        "confirm_form": AsnDeliveryConfirmForm(),
        "cancel_form": AsnCancelForm(),
        # The Actions sidebar gates on these booleans; every one of them is re-enforced in the
        # view that performs the action, and again in the model verb.
        "can_edit": obj.is_editable,
        "can_submit": obj.status == "draft",
        "can_mark_in_transit": obj.status in ("draft", "submitted"),
        "can_confirm": obj.is_in_flight,
        "can_cancel": obj.status not in _CLOSED_STATUSES,
        # Delete is admin-only AND drafts-only — don't offer a button that would 403.
        "can_delete": is_admin and obj.status == "draft",
    })


@login_required
def asn_create(request):
    """Record a new notice. Lines are declared on the EDIT page: the ``po_line`` dropdown can
    only be narrowed once the purchase order is known, so offering it here would mean offering
    every line in the workspace."""
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before recording shipping notices.")
        return redirect("dashboard:home")

    if request.method == "POST":
        form = AdvancedShipmentNoticeForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.created_by = request.user
            obj.save()
            write_audit_log(request.user, obj, "create",
                            {"purchase_order": obj.purchase_order.number})
            messages.success(
                request,
                f"ASN {obj.number} recorded — declare the shipped lines below.")
            return redirect("procurement:asn_detail", pk=obj.pk)
    else:
        form = AdvancedShipmentNoticeForm(tenant=request.tenant)

    return render(request, "procurement/orderfulfillment/asn/form.html", {
        "form": form,
        "is_edit": False,
        "obj": None,
        "formset": None,
        "order": None,
    })


@login_required
def asn_edit(request, pk):
    """Correct the header and declare/adjust the shipped lines.

    Refused once the notice is delivered or cancelled: at that point it is a closed receiving
    record, and 6.12 books goods against what it says.
    """
    obj = get_object_or_404(
        AdvancedShipmentNotice.objects.select_related("purchase_order", "purchase_order__vendor"),
        pk=pk, tenant=request.tenant,
    )
    if obj.status in _CLOSED_STATUSES:
        messages.error(
            request,
            f"ASN {obj.number} is {obj.get_status_display().lower()} and can no longer be edited.")
        return redirect("procurement:asn_detail", pk=pk)

    if request.method == "POST":
        form = AdvancedShipmentNoticeForm(request.POST, instance=obj, tenant=request.tenant)
        # AsnLineForm is a plain ModelForm (the child carries no tenant) — no form_kwargs.
        formset = AsnLineFormSet(request.POST, instance=obj)
        if form.is_valid() and formset.is_valid():
            # Header + line rows are one logical write; a half-saved declaration would report a
            # discrepancy that never existed.
            with transaction.atomic():
                obj = form.save()
                formset.instance = obj
                formset.save()
            # WHICH header fields moved, not just "the header moved" — a disputed inbound
            # delivery is later argued over carrier / tracking_number / expected_delivery_date.
            # The shared helper keeps the redaction policy in one place rather than duplicating
            # a sensitive-field list here.
            changes = _changed(form)
            changes["lines"] = obj.lines.count()
            write_audit_log(request.user, obj, "update", changes)
            messages.success(request, f"ASN {obj.number} updated.")
            return redirect("procurement:asn_detail", pk=obj.pk)
    else:
        form = AdvancedShipmentNoticeForm(instance=obj, tenant=request.tenant)
        formset = AsnLineFormSet(instance=obj)

    return render(request, "procurement/orderfulfillment/asn/form.html", {
        "form": form,
        "is_edit": True,
        "obj": obj,
        "formset": formset,
        "order": obj.purchase_order,
    })


@login_required
@tenant_admin_required
@require_POST
def asn_delete(request, pk):
    """Drafts only. A submitted notice has been acted on — cancel it instead, which keeps the
    record and its reason. Admin-gated because deletion removes the trail entirely."""
    obj = get_object_or_404(AdvancedShipmentNotice, pk=pk, tenant=request.tenant)
    if obj.status != "draft":
        messages.error(request,
                       f"Only a draft ASN can be deleted — cancel {obj.number} instead.")
        return redirect("procurement:asn_detail", pk=pk)
    return crud_delete(request, model=AdvancedShipmentNotice, pk=pk,
                       success_url="procurement:asn_list")


@login_required
@require_POST
def asn_submit(request, pk):
    with transaction.atomic():
        obj = get_object_or_404(AdvancedShipmentNotice.objects.select_for_update(),
                                pk=pk, tenant=request.tenant)
        if not obj.submit():
            messages.info(request,
                          f"ASN {obj.number} is already {obj.get_status_display().lower()}.")
            return redirect("procurement:asn_detail", pk=pk)
    write_audit_log(request.user, obj, "update", {"action": "submit", "status": obj.status})
    messages.success(request, f"ASN {obj.number} submitted.")
    return redirect("procurement:asn_detail", pk=pk)


@login_required
@require_POST
def asn_mark_in_transit(request, pk):
    with transaction.atomic():
        obj = get_object_or_404(AdvancedShipmentNotice.objects.select_for_update(),
                                pk=pk, tenant=request.tenant)
        if not obj.mark_in_transit():
            messages.info(request,
                          f"ASN {obj.number} is {obj.get_status_display().lower()} — it cannot "
                          f"move to in-transit.")
            return redirect("procurement:asn_detail", pk=pk)
    write_audit_log(request.user, obj, "update", {"action": "mark_in_transit",
                                                  "status": obj.status})
    messages.success(request, f"ASN {obj.number} marked in transit.")
    return redirect("procurement:asn_detail", pk=pk)


@login_required
@require_POST
def asn_confirm_delivery(request, pk):
    """Stamp arrival + proof of delivery.

    Also the target of the delivery-confirmation board's INLINE form, which posts the same field
    names plus ``next=confirmation`` so the user lands back on the board instead of on a detail
    page they never opened.
    """
    # Read the return target before anything can redirect — it is plain POST data, and only the
    # single literal "confirmation" is honoured (never an arbitrary URL, which would be an open
    # redirect).
    back_to_board = request.POST.get("next", "").strip() == "confirmation"
    # ...and which TAB of it. Whitelisted against the board's own bucket keys, so this stays a
    # hardcoded url + a known query value — never a user-supplied URL.
    bucket = request.POST.get("due", "").strip()
    if bucket not in _BUCKET_KEYS:
        bucket = ""
    success_url = ("procurement:delivery_confirmation" if back_to_board
                   else "procurement:asn_detail")

    def _back(**kwargs):
        if not back_to_board:
            return redirect(success_url, **kwargs)
        url = reverse(success_url)
        # Without the tab, a buyer working Overdue or Awaiting is silently dropped back onto
        # "Due today" after every single confirmation.
        return redirect(f"{url}?due={bucket}" if bucket else url)

    with transaction.atomic():
        obj = get_object_or_404(AdvancedShipmentNotice.objects.select_for_update(),
                                pk=pk, tenant=request.tenant)
        form = AsnDeliveryConfirmForm(request.POST)
        if not form.is_valid():
            messages.error(request,
                           "Check the delivery details — the arrival could not be recorded.")
            return _back(pk=pk)
        data = form.cleaned_data
        if not obj.confirm_delivery(
                request.user,
                delivered_at=data.get("delivered_at"),
                arrival_condition=data.get("arrival_condition") or "good",
                pod_reference=data.get("pod_reference") or "",
                received_signature_name=data.get("received_signature_name") or ""):
            # Not in flight: already delivered (a double-submitted confirmation), still a draft,
            # or cancelled. Never re-stamp.
            messages.info(request,
                          f"ASN {obj.number} is {obj.get_status_display().lower()} — there is "
                          f"nothing to confirm.")
            return _back(pk=pk)

    write_audit_log(request.user, obj, "update", {
        "action": "confirm_delivery",
        "condition": obj.arrival_condition,
        "delivered_at": str(obj.delivered_at),
        "discrepancy": obj.discrepancy_verdict,
    })
    messages.success(request, f"Delivery of ASN {obj.number} confirmed.")
    return _back(pk=pk)


@login_required
@require_POST
def asn_cancel(request, pk):
    with transaction.atomic():
        obj = get_object_or_404(AdvancedShipmentNotice.objects.select_for_update(),
                                pk=pk, tenant=request.tenant)
        form = AsnCancelForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Give a reason when cancelling a shipping notice.")
            return redirect("procurement:asn_detail", pk=pk)
        if not obj.cancel(request.user, form.cleaned_data["cancellation_reason"]):
            messages.info(request,
                          f"ASN {obj.number} is {obj.get_status_display().lower()} and cannot "
                          f"be cancelled.")
            return redirect("procurement:asn_detail", pk=pk)
    write_audit_log(request.user, obj, "update",
                    {"action": "cancel", "reason": obj.cancellation_reason[:200]})
    messages.success(request, f"ASN {obj.number} cancelled.")
    return redirect("procurement:asn_detail", pk=pk)
