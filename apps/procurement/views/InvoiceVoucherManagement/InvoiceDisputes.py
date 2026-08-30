"""Procurement 6.13 Invoice & Voucher Management — InvoiceDispute views + Dispute Aging.

Ten routes: the register, one detail page, raise/edit/delete, the four status verbs
(escalate / await supplier / await internal / close), the **resolve** verb — the only one that
can mint a credit memo — and the standalone **Dispute Aging** board.

Discipline worth recording, because a reviewer will otherwise go looking for it:

* **Every queryset is ``filter(tenant=request.tenant)``** — never ``.all()``. This model HAS its
  own tenant column, so every object is fetched ``get_object_or_404(..., tenant=request.tenant)``
  rather than through the invoice.
* **Ordinary CRUD is ``@login_required``; every privileged write adds ``@tenant_admin_required``
  and ``@require_POST``** (in that order) — resolving and deleting decide money, escalating
  commits the department to a deadline.
* **Every verb runs the row under ``select_for_update()``** inside ``transaction.atomic()``, so
  two clerks clicking on the same dispute cannot both audit a state change.
* **The templates are told what they may offer** through ``can_edit`` / ``can_resolve`` /
  ``is_admin`` and the ``actions`` list, each of which mirrors the decorator on the route it
  points at — a hidden button and a refused POST always agree.

The aging board deliberately READS only this lane's table and writes nothing.
"""
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Q
from django.urls import reverse

from apps.core.crud import as_db_int, paginate
from apps.core.models import Party
from apps.procurement.forms.InvoiceVoucherManagement.InvoiceDisputes import InvoiceDisputeForm
# NOT-YET-WIRED entities of this SAME sub-module: import the entity MODULE directly, never
# ``from apps.procurement.models import X`` — the sub-package is not wired until the Integrator
# lands it and a package-level re-export is a star-import cycle at URLconf import.
from apps.procurement.models.InvoiceVoucherManagement.InvoiceDisputes import (
    REASON_CODE_CHOICES, RESOLUTION_CHOICES, STATUS_CHOICES, InvoiceDispute)
from apps.procurement.models.InvoiceVoucherManagement.SupplierInvoiceLines import SupplierInvoiceLine
from apps.procurement.models.InvoiceVoucherManagement.SupplierInvoices import SupplierInvoice
from apps.procurement.views._common import *  # noqa: F401,F403

ZERO = Decimal("0")

TEMPLATE_LIST = "procurement/invoicevouchermanagement/invoicedispute/list.html"
TEMPLATE_DETAIL = "procurement/invoicevouchermanagement/invoicedispute/detail.html"
TEMPLATE_FORM = "procurement/invoicevouchermanagement/invoicedispute/form.html"
TEMPLATE_AGING = "procurement/invoicevouchermanagement/dispute_aging.html"

#: How far ahead the aging board's "due in 7 days" card looks.
DUE_WINDOW_DAYS = 7

#: How far back "resolved recently" reaches on the aging board.
RESOLVED_WINDOW_DAYS = 30

#: Rows per card on the aging board.
AGING_PAGE_SIZE = 15

#: The aging buckets, in the vocabulary ``InvoiceDispute.age_bucket`` returns. Overdue is listed
#: first because the board exists to surface what is late.
AGING_BUCKETS = [
    ("overdue", "Overdue"),
    ("0-7", "0–7 days"),
    ("8-14", "8–14 days"),
    ("15-30", "15–30 days"),
    ("31-60", "31–60 days"),
    ("60+", "Over 60 days"),
    ("none", "No due date"),
]

#: Every hop a register row (or its own ``__str__``) walks.
_ROW_RELATIONS = ("invoice", "invoice_line", "supplier", "assigned_to")

#: Every hop the detail page walks — the whole dispute plus the document it was raised on.
_DETAIL_RELATIONS = _ROW_RELATIONS + (
    "invoice__vendor", "invoice__currency", "raised_by", "credit_memo_invoice")


# -- shared helpers --------------------------------------------------------------------------

def _is_admin(request):
    """Mirrors ``@tenant_admin_required`` exactly, so a hidden button and a refused POST agree."""
    return bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False))


def _need_tenant(request, what):
    """The superuser has no workspace by design; say so instead of rendering an empty page."""
    if request.tenant is None:
        messages.error(request, f"Select a tenant workspace to {what}.")
        return redirect("dashboard:home")
    return None


def _as_decimal(value):
    """``value`` as a usable ``Decimal`` — ``ZERO`` for anything unusable (L35/L11)."""
    try:
        number = Decimal(value if value is not None else ZERO)
    except (InvalidOperation, ValueError, TypeError, ArithmeticError):
        return ZERO
    return number if number.is_finite() else ZERO


def _refuse(obj, verb):
    return f"{obj.number} is {obj.get_status_display().lower()} and cannot be {verb}."


def _stats(tenant, today):
    """The four register stat cards in ONE aggregate over the whole workspace.

    Counted over the WHOLE workspace, not the filtered page: a stat card answers "how much
    argument is outstanding?", which must not change because somebody typed a search.
    """
    return InvoiceDispute.objects.filter(tenant=tenant).aggregate(
        open=Count("id", filter=Q(status__in=InvoiceDispute.OPEN_STATUSES)),
        overdue=Count("id", filter=Q(status__in=InvoiceDispute.OPEN_STATUSES,
                                     due_date__lt=today)),
        escalated=Count("id", filter=Q(status="escalated")),
        resolved=Count("id", filter=Q(status="resolved")),
    )


def _assignees(tenant):
    """Whoever actually owns a dispute in this workspace — not every user in it.

    A dropdown of the whole directory is a page that never finishes loading on a big tenant, and
    an empty option list is more honest than one full of people who own nothing.
    """
    return (get_user_model().objects
            .filter(tenant=tenant, procurement_invoice_disputes_assigned__isnull=False)
            .distinct().order_by("email"))


def _transition(request, pk, action, invoke, success, refuse):
    """One status verb: lock the row, call it, report and audit.

    ``invoke`` re-checks its own guard and returns a bool — the row lock is what makes that
    guard meaningful, and the method is what makes a direct POST safe.
    """
    guard = _need_tenant(request, "change invoice disputes")
    if guard is not None:
        return guard
    with transaction.atomic():
        obj = get_object_or_404(InvoiceDispute.objects.select_for_update(),
                                pk=pk, tenant=request.tenant)
        if not invoke(obj):
            messages.error(request, refuse(obj))
            return redirect("procurement:invoicedispute_detail", pk=pk)
    write_audit_log(request.user, obj, "update", {"action": action})
    messages.success(request, success(obj))
    return redirect("procurement:invoicedispute_detail", pk=pk)


# -- the register ------------------------------------------------------------------------------

@login_required
def invoicedispute_list(request):
    """The disputes register — every dispute in the workspace, newest first."""
    guard = _need_tenant(request, "review invoice disputes")
    if guard is not None:
        return guard
    rows = InvoiceDispute.objects.filter(tenant=request.tenant)
    # Applied BEFORE crud_list, because ``?overdue=1`` is a predicate on the row set and not one
    # of the register's dropdown filters. Anything non-empty counts as checked, so a checkbox
    # posted as ``on`` works as well as the documented ``?overdue=1``.
    if (request.GET.get("overdue") or "").strip() not in ("", "0"):
        rows = rows.filter(due_date__lt=timezone.localdate(),
                           status__in=InvoiceDispute.OPEN_STATUSES)
    return crud_list(
        request,
        rows.select_related(*_ROW_RELATIONS),
        TEMPLATE_LIST,
        search_fields=["number", "description", "invoice__number", "invoice__invoice_number",
                       "supplier__name"],
        # (get_param, orm_lookup, is_int) — the int ones go through crud_list's as_db_int guard,
        # so ?supplier=abc / ?supplier=999999999999999999999 skip the filter instead of 500ing
        # (L11).
        filters=[("status", "status", False), ("reason_code", "reason_code", False),
                 ("supplier", "supplier_id", True), ("assigned_to", "assigned_to_id", True)],
        extra_context={
            "status_choices": STATUS_CHOICES,
            "reason_choices": REASON_CODE_CHOICES,
            "suppliers": Party.objects.filter(tenant=request.tenant).order_by("name"),
            "assignees": _assignees(request.tenant),
            "stats": _stats(request.tenant, timezone.localdate()),
        },
    )


@login_required
def invoicedispute_detail(request, pk):
    """One dispute: what is contested, what the engine said, and what can still be done."""
    obj = get_object_or_404(InvoiceDispute.objects.select_related(*_DETAIL_RELATIONS),
                            pk=pk, tenant=request.tenant)
    is_admin = _is_admin(request)
    can_resolve = is_admin and obj.is_open

    # Each entry mirrors the decorator on the route it points at, so the page never offers a
    # button that would 403. The resolve panel is its own form and is gated by ``can_resolve``.
    actions = []
    if is_admin and obj.status in ("open", "awaiting_supplier", "awaiting_internal"):
        actions.append({"url": reverse("procurement:invoicedispute_escalate", args=[obj.pk]),
                        "label": "Escalate", "verb": "post", "css": "btn-danger"})
    if obj.status in ("open", "awaiting_internal", "escalated"):
        actions.append({"url": reverse("procurement:invoicedispute_await_supplier", args=[obj.pk]),
                        "label": "Await supplier", "verb": "post", "css": "btn-outline"})
    if obj.status in ("open", "awaiting_supplier", "escalated"):
        actions.append({"url": reverse("procurement:invoicedispute_await_internal", args=[obj.pk]),
                        "label": "Await internal review", "verb": "post", "css": "btn-outline"})
    if is_admin and obj.status == "resolved":
        actions.append({"url": reverse("procurement:invoicedispute_close", args=[obj.pk]),
                        "label": "Close", "verb": "post", "css": "btn-outline"})

    return render(request, TEMPLATE_DETAIL, {
        "obj": obj,
        "invoice": obj.invoice,
        "invoice_line": obj.invoice_line,
        # The evidence this dispute was raised on — matched to the dispute by lane C's own FK,
        # which is the only honest answer to "what is the argument actually about?".
        "variances": list(obj.variances.select_related("invoice", "invoice_line")
                          .order_by("-detected_at", "-id")),
        "resolution_choices": RESOLUTION_CHOICES,
        "days_open": obj.days_open,
        "is_overdue": obj.is_overdue,
        "actions": actions,
        # Editing is refused by the view unless the dispute is open; resolving needs an admin.
        "can_edit": obj.is_open,
        "can_resolve": can_resolve,
        "is_admin": is_admin,
    })


# -- raise / amend -------------------------------------------------------------------------------

def _dispute_form(request, invoice_pk=None, instance=None):
    """Raise or amend one dispute.

    Hand-rolled rather than ``crud_create`` / ``crud_edit`` because it stamps the tenant AND
    ``raised_by``, and because the invoice it is raised against arrives as a GET parameter that
    has to be validated before it is offered as an initial value.
    """
    is_edit = instance is not None
    invoice = None
    if is_edit:
        invoice = instance.invoice
    elif invoice_pk is not None:
        # Resolved by pk+tenant, so a hand-typed ``?invoice=`` from another workspace is simply
        # ignored rather than leaked into the form's initial data.
        invoice = (SupplierInvoice.objects.filter(pk=invoice_pk, tenant=request.tenant)
                   .select_related("vendor").first())

    if request.method == "POST":
        form = InvoiceDisputeForm(request.POST, instance=instance, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            if not is_edit:
                # Authorship is stamped once, at creation — amending a dispute must not silently
                # transfer who raised it.
                obj.raised_by = request.user if request.user.is_authenticated else None
            obj.save()
            write_audit_log(request.user, obj, "update" if is_edit else "create")
            messages.success(request, f"Dispute {obj.number} saved.")
            return redirect("procurement:invoicedispute_detail", pk=obj.pk)
    else:
        initial = {"invoice": invoice.pk} if (not is_edit and invoice is not None) else {}
        form = InvoiceDisputeForm(instance=instance, tenant=request.tenant, initial=initial)

    if is_edit:
        cancel_url = reverse("procurement:invoicedispute_detail", args=[instance.pk])
    elif invoice is not None:
        # Raised from an invoice: "cancel" means "back to the invoice I came from".
        cancel_url = reverse("procurement:supplierinvoice_detail", args=[invoice.pk])
    else:
        cancel_url = reverse("procurement:invoicedispute_list")

    return render(request, TEMPLATE_FORM, {
        "form": form,
        "obj": instance,
        "invoice": invoice,
        "is_edit": is_edit,
        "title": "Edit dispute" if is_edit else "Raise a dispute",
        "submit_label": "Save changes" if is_edit else "Raise dispute",
        "cancel_url": cancel_url,
    })


@login_required
def invoicedispute_create(request):
    """Raise a dispute, optionally pre-pointed at one invoice (``?invoice=<pk>``)."""
    guard = _need_tenant(request, "raise invoice disputes")
    if guard is not None:
        return guard
    # as_db_int: junk and over-range pks skip the filter instead of 500ing (L11).
    return _dispute_form(request, invoice_pk=as_db_int(request.GET.get("invoice")))


@login_required
def invoicedispute_edit(request, pk):
    obj = get_object_or_404(InvoiceDispute, pk=pk, tenant=request.tenant)
    if not obj.is_open:
        # A settled dispute is a closed book: amending its amount or reason after the fact would
        # rewrite the trail of a decision that has already been reported.
        messages.error(
            request,
            f"{obj.number} is {obj.get_status_display().lower()} — only an open dispute can be "
            f"edited.")
        return redirect("procurement:invoicedispute_detail", pk=pk)
    return _dispute_form(request, instance=obj)


@login_required
@tenant_admin_required
@require_POST
def invoicedispute_delete(request, pk):
    """Admin-gated: deleting a dispute erases the trail of money that was withheld."""
    return crud_delete(request, model=InvoiceDispute, pk=pk,
                       success_url="procurement:invoicedispute_list")


# -- resolve --------------------------------------------------------------------------------------

def _spawn_credit_memo(obj):
    """Mint the credit memo that settles this dispute, for the NEGATIVE disputed amount.

    A credit memo is a ``SupplierInvoice`` with ``invoice_type="credit_memo"`` — lane A owns the
    only invoice table, and a second one would be a parallel ledger of claims. The amount is
    carried on ONE line, and it is negative by design: lane B refuses a positive line on a
    credit memo, and a memo that increases what we owe is not a credit.

    The invoice number is derived from the disputed document's own number, which is what the
    supplier's statement has to be reconciled against.
    """
    source = obj.invoice
    line = obj.invoice_line
    amount = -_as_decimal(obj.disputed_amount).copy_abs()

    memo = SupplierInvoice.objects.create(
        tenant=obj.tenant,
        vendor=obj.supplier or source.vendor,
        purchase_order=source.purchase_order,
        goods_receipt=source.goods_receipt,
        payment_term=source.payment_term,
        currency=source.currency,
        tax_code=source.tax_code,
        invoice_type="credit_memo",
        invoice_number=f"CM-{source.invoice_number}"[:64],
        invoice_date=timezone.localdate(),
        notes=f"Credit memo raised by dispute {obj.number}.",
    )
    SupplierInvoiceLine.objects.create(
        invoice=memo,
        po_line=line.po_line if line is not None else None,
        receipt_line=line.receipt_line if line is not None else None,
        gl_account=line.gl_account if line is not None else None,
        tax_code=line.tax_code if line is not None else source.tax_code,
        description=f"Credit for {obj.number} — {obj.get_reason_code_display()}"[:255],
        quantity=Decimal("1"),
        unit_price=amount,
    )
    # The header money follows the lines — one line, so the memo's total is the credit itself.
    memo.recalc_totals(save=True)
    return memo


@login_required
@tenant_admin_required
@require_POST
def invoicedispute_resolve(request, pk):
    """Settle a dispute — the only route that can mint a credit memo.

    ``resolution`` is required and must be one of ``RESOLUTION_CHOICES``; ``resolution_note`` is
    optional. A ``credit_memo`` settlement only creates the memo when the operator ASKS for one
    (``spawn_credit_memo``), because the supplier may have already sent it — minting a second
    one would double the credit.
    """
    guard = _need_tenant(request, "resolve invoice disputes")
    if guard is not None:
        return guard

    resolution = (request.POST.get("resolution") or "").strip()
    if resolution not in dict(RESOLUTION_CHOICES):
        messages.error(request, "Choose how this dispute was resolved.")
        return redirect("procurement:invoicedispute_detail", pk=pk)
    note = (request.POST.get("resolution_note") or "").strip()

    credit_memo = None
    with transaction.atomic():
        obj = get_object_or_404(InvoiceDispute.objects.select_for_update(),
                                pk=pk, tenant=request.tenant)
        if not obj.resolve(request.user, resolution, note):
            messages.error(request, _refuse(obj, "resolved"))
            return redirect("procurement:invoicedispute_detail", pk=pk)
        if resolution == "credit_memo" and request.POST.get("spawn_credit_memo"):
            credit_memo = _spawn_credit_memo(obj)
            obj.link_credit_memo(credit_memo)

    changes = {"action": "resolve", "resolution": resolution}
    if note:
        changes["note"] = note
    if credit_memo is not None:
        changes["credit_memo"] = credit_memo.number
    write_audit_log(request.user, obj, "update", changes)
    messages.success(
        request,
        (f"{obj.number} resolved — credit memo {credit_memo.number} raised."
         if credit_memo is not None
         else f"{obj.number} resolved as {dict(RESOLUTION_CHOICES)[resolution].lower()}."))
    return redirect("procurement:invoicedispute_detail", pk=pk)


# -- status verbs -----------------------------------------------------------------------------------

@login_required
@tenant_admin_required
@require_POST
def invoicedispute_escalate(request, pk):
    return _transition(
        request, pk, "escalate",
        lambda obj: obj.escalate(request.user),
        lambda obj: f"{obj.number} escalated.",
        lambda obj: _refuse(obj, "escalated"),
    )


@login_required
@require_POST
def invoicedispute_await_supplier(request, pk):
    return _transition(
        request, pk, "await_supplier",
        lambda obj: obj.await_supplier(request.user),
        lambda obj: f"{obj.number} is waiting on the supplier.",
        lambda obj: _refuse(obj, "moved to awaiting supplier"),
    )


@login_required
@require_POST
def invoicedispute_await_internal(request, pk):
    return _transition(
        request, pk, "await_internal",
        lambda obj: obj.await_internal(request.user),
        lambda obj: f"{obj.number} is waiting on an internal review.",
        lambda obj: _refuse(obj, "moved to awaiting internal review"),
    )


@login_required
@tenant_admin_required
@require_POST
def invoicedispute_close(request, pk):
    return _transition(
        request, pk, "close",
        lambda obj: obj.close(request.user),
        lambda obj: f"{obj.number} closed.",
        lambda obj: _refuse(obj, "closed — only a resolved dispute can be closed"),
    )


# -- Dispute Aging ---------------------------------------------------------------------------------

@login_required
def invoicedispute_aging(request):
    """**Dispute Aging** — the same open disputes, grouped by how long they have been running.

    The register answers "what is disputed?"; this board answers "what has been waiting longest,
    and how much is tied up in it". It writes nothing.

    A card's ``count`` and ``amount`` describe the WHOLE bucket, while ``rows`` is this page's
    slice of it — a header that changed because somebody paged forward would be a lie about the
    money. ``page_obj`` paginates the flattened row list, which is what a card's table is a view
    of.
    """
    guard = _need_tenant(request, "review dispute aging")
    if guard is not None:
        return guard

    tenant = request.tenant
    today = timezone.localdate()

    open_rows = list(InvoiceDispute.objects
                     .filter(tenant=tenant, status__in=InvoiceDispute.OPEN_STATUSES)
                     .select_related(*_ROW_RELATIONS)
                     # Due date first: the thing that is due soonest is the thing to work.
                     .order_by("due_date", "-raised_at"))

    bucket = (request.GET.get("bucket") or "").strip()
    grouped = {key: [] for key, _label in AGING_BUCKETS}
    for dispute in open_rows:
        grouped.setdefault(dispute.age_bucket, []).append(dispute)
    if bucket in grouped:
        open_rows = grouped[bucket]

    page_obj = paginate(request, open_rows, AGING_PAGE_SIZE)
    page_rows = list(page_obj.object_list)

    buckets = [{
        "key": key,
        "label": label,
        "rows": [dispute for dispute in page_rows if dispute.age_bucket == key],
        "count": len(grouped.get(key, [])),
        "amount": sum((_as_decimal(dispute.disputed_amount)
                       for dispute in grouped.get(key, [])), ZERO),
    } for key, label in AGING_BUCKETS]

    return render(request, TEMPLATE_AGING, {
        "buckets": buckets,
        "page_obj": page_obj,
        "today": today,
        "stats": InvoiceDispute.objects.filter(tenant=tenant).aggregate(
            open=Count("id", filter=Q(status__in=InvoiceDispute.OPEN_STATUSES)),
            overdue=Count("id", filter=Q(status__in=InvoiceDispute.OPEN_STATUSES,
                                         due_date__lt=today)),
            due_7d=Count("id", filter=Q(status__in=InvoiceDispute.OPEN_STATUSES,
                                        due_date__gte=today,
                                        due_date__lte=today + timedelta(days=DUE_WINDOW_DAYS))),
            resolved_30d=Count("id", filter=Q(status__in=("resolved", "closed"),
                                              resolved_at__gte=timezone.now()
                                              - timedelta(days=RESOLVED_WINDOW_DAYS))),
        ),
        "bucket_choices": AGING_BUCKETS,
        "bucket": bucket,
    })
