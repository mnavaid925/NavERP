"""Procurement 6.13 Invoice & Voucher Management — SupplierInvoiceLine views + Payment Schedule.

Six routes: the line register (list/detail/create/edit/delete) and the **Payment Schedule**
board.

Discipline worth recording, because a reviewer will otherwise go looking for it:

* **The line has no tenant column.** Every queryset is filtered ``invoice__tenant=request.tenant``
  and every object is fetched ``get_object_or_404(..., invoice__tenant=request.tenant)`` — a bare
  ``pk`` lookup on a child is a cross-tenant read.
* **Lines belong to an editable invoice only.** Add and edit refuse a header that has moved past
  ``EDITABLE_STATUSES`` (or into a terminal status) the same way lane A's header edit does: a
  line added to an approved invoice would not be in the bill that was already posted.
* **Deleting a line re-derives the header money.** The line's own ``save()`` does it on write;
  the delete path has no ``save()`` to ride, so it calls ``recalc_totals()`` itself.
* **Payment Schedule is a PROJECTION, not a register.** It reads approved + scheduled invoices
  with a due date and buckets them by week; it writes nothing.
"""
from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, F, OuterRef, Q, Subquery, Sum
from django.urls import reverse

from apps.accounting.models import Currency, PaymentTerm
from apps.core.crud import _changed, as_db_int
from apps.core.models import Party
# NOT-YET-WIRED entities of this SAME sub-module: import the entity MODULE directly, never
# ``from apps.procurement.models import X`` — the sub-package is not wired until the Integrator
# lands it and a package-level re-export is a star-import cycle at URLconf import.
from apps.procurement.forms.InvoiceVoucherManagement.SupplierInvoiceLines import SupplierInvoiceLineForm
from apps.procurement.models.InvoiceVoucherManagement.SupplierInvoiceLines import SupplierInvoiceLine
from apps.procurement.models.InvoiceVoucherManagement.SupplierInvoices import SupplierInvoice
from apps.procurement.views._common import *  # noqa: F401,F403
from apps.scm.models import GoodsReceiptLine, Item

ZERO = Decimal("0")

TEMPLATE_LIST = "procurement/invoicevouchermanagement/supplierinvoiceline/list.html"
TEMPLATE_DETAIL = "procurement/invoicevouchermanagement/supplierinvoiceline/detail.html"
TEMPLATE_FORM = "procurement/invoicevouchermanagement/supplierinvoiceline/form.html"
TEMPLATE_SCHEDULE = "procurement/invoicevouchermanagement/payment_schedule.html"

#: How many invoices the register's filter dropdown offers. A dropdown that renders the whole
#: workspace is a page that never finishes loading.
INVOICE_CHOICE_LIMIT = 200

#: Payment Schedule horizon: the default number of weekly buckets, and the clamp applied to the
#: ``?weeks=`` GET value (an unclamped 10000 would build ten thousand buckets).
HORIZON_WEEKS_DEFAULT = 8
HORIZON_WEEKS_MIN = 1
HORIZON_WEEKS_MAX = 26

#: Every hop the line register and the detail page walk. The CHAINED hops are not optional: the
#: register renders ``po_line.purchase_order``, ``receipt_line.goods_receipt``,
#: ``invoice.currency`` and ``tax_code`` per row, so leaving them out is 4N single-row queries.
_ROW_RELATIONS = ("invoice", "invoice__currency", "po_line", "po_line__purchase_order",
                  "receipt_line", "receipt_line__goods_receipt", "item", "gl_account", "tax_code")
_DETAIL_RELATIONS = _ROW_RELATIONS + ("invoice__vendor", "invoice__payment_term")


# -- shared helpers --------------------------------------------------------------------------

def _need_tenant(request, what):
    """The superuser has no workspace by design; say so instead of rendering an empty page."""
    if request.tenant is None:
        messages.error(request, f"Select a tenant workspace to {what}.")
        return redirect("dashboard:home")
    return None


def _line_stats(tenant):
    """The four register stat cards, counted over the WHOLE workspace.

    A stat card answers "how much of this invoice is matched?", which must not change because
    somebody typed a search.
    """
    # ONE aggregate, the way the other three lanes in this sub-module build their cards — three
    # separate COUNTs over the same table is three scans for four numbers.
    agg = SupplierInvoiceLine.objects.filter(invoice__tenant=tenant).aggregate(
        lines=Count("id"),
        matched=Count("id", filter=Q(matched_qty=F("quantity"))),
        # Non-PO: a line with nothing to three-way match against, i.e. the free-text spend that
        # has to be coded by hand.
        non_po=Count("id", filter=Q(po_line__isnull=True)),
    )
    return {
        "lines": agg["lines"],
        "matched": agg["matched"],
        "unmatched": agg["lines"] - agg["matched"],
        "non_po": agg["non_po"],
    }


def _cumulative_subqueries(tenant_id):
    """The two over-invoicing figures the register renders, as correlated subqueries.

    The model properties behind them are ``Sum()`` aggregates, so reading them inside the row loop
    is 2N queries. As subqueries they cost nothing per row. ``.order_by()`` is MANDATORY on both:
    both models declare ``Meta.ordering = ["id"]``, which would otherwise join the ordering column
    to the GROUP BY and return one row per line instead of one row per ordered line. The invoiced
    side carries the tenant scope the model property applies — it is the over-invoicing control and
    must never sum across a workspace boundary.
    """
    invoiced = (SupplierInvoiceLine.objects
                .filter(po_line=OuterRef("po_line"), invoice__tenant_id=tenant_id)
                .exclude(invoice__status__in=SupplierInvoice.TERMINAL_STATUSES)
                .exclude(invoice__invoice_type="credit_memo")
                .order_by().values("po_line").annotate(s=Sum("quantity")).values("s")[:1])
    received = (GoodsReceiptLine.objects
                .filter(po_line=OuterRef("po_line"))
                .exclude(goods_receipt__status="cancelled")
                .order_by().values("po_line").annotate(s=Sum("quantity_received"))
                .values("s")[:1])
    return invoiced, received


def _editable(invoice):
    """Mirrors lane A's header-edit guard: a line may only be added to a draft, parked or
    captured invoice — past that, the header's bill is already posted."""
    return invoice.status in SupplierInvoice.EDITABLE_STATUSES


# -- the line register --------------------------------------------------------------------------

@login_required
def supplierinvoiceline_list(request):
    guard = _need_tenant(request, "review supplier invoice lines")
    if guard is not None:
        return guard
    invoiced_sq, received_sq = _cumulative_subqueries(request.tenant.pk)
    rows = (SupplierInvoiceLine.objects.filter(invoice__tenant=request.tenant)
            .select_related(*_ROW_RELATIONS)
            .annotate(cum_invoiced_qty=Subquery(invoiced_sq),
                      cum_received_qty=Subquery(received_sq)))

    # ``gl_missing`` is applied HERE, not through crud_list. An ``__isnull`` lookup is only
    # validated when the SQL is compiled — inside ``paginate()``, outside crud_list's
    # ValueError/ValidationError guard — so ?gl_missing=1 / on / true / abc all 500ed. Anything
    # that is not a recognised truth value now falls through unfiltered (L11).
    gl_missing = request.GET.get("gl_missing", "").strip()
    if gl_missing in ("True", "true", "1", "on", "yes"):
        rows = rows.filter(gl_account__isnull=True)
    elif gl_missing in ("False", "false", "0", "off", "no"):
        rows = rows.filter(gl_account__isnull=False)

    return crud_list(
        request,
        rows,
        TEMPLATE_LIST,
        search_fields=["description", "sku_hint", "invoice__number", "invoice__invoice_number"],
        # (get_param, orm_lookup, is_int) — the int ones go through crud_list's as_db_int guard,
        # so ?invoice=abc skips the filter instead of 500ing (L11). ``gl_missing`` is applied
        # above, not here: it is named after what it SELECTS rather than the column it inspects
        # (True means the account is MISSING), and an ``__isnull`` lookup cannot go through
        # crud_list at all — see the comment on it.
        filters=[("invoice", "invoice_id", True), ("po_line", "po_line_id", True),
                 ("item", "item_id", True)],
        extra_context={
            "invoices": (SupplierInvoice.objects.filter(tenant=request.tenant)
                         .order_by("-invoice_date", "-id")[:INVOICE_CHOICE_LIMIT]),
            "items": Item.objects.filter(tenant=request.tenant).order_by("name"),
            "stats": _line_stats(request.tenant),
        },
    )


@login_required
def supplierinvoiceline_detail(request, pk):
    obj = get_object_or_404(
        SupplierInvoiceLine.objects.select_related(*_DETAIL_RELATIONS),
        pk=pk, invoice__tenant=request.tenant)
    invoice = obj.invoice
    invoiced = obj.cumulative_invoiced_qty
    received = obj.cumulative_received_qty
    ordered = obj.po_line.quantity if obj.po_line_id else ZERO
    return render(request, TEMPLATE_DETAIL, {
        "obj": obj,
        "invoice": invoice,
        # The line's own variances (the reverse of InvoiceMatchVariance.invoice_line), newest
        # first — the evidence behind whatever the match engine decided about this row.
        "variances": list(obj.variances.select_related("dispute").order_by("-detected_at", "-id")),
        "cumulative": {
            "invoiced": invoiced,
            "received": received,
            "ordered": ordered,
            "remaining": ordered - invoiced,
        },
        "can_edit": _editable(invoice),
    })


def _line_form(request, invoice_pk=None, instance=None):
    """One line, hand-rolled.

    Hand-rolled rather than ``crud_create`` / ``crud_edit`` for two reasons: the header comes
    from the URL (a parent pk in a POST body is how a caller grafts a line onto another
    workspace's invoice), and the header is stamped on the instance BEFORE ``save()`` so the
    line's own ``save()`` can hand the recalculated money back to the right invoice. Hand-rolled
    means this path owes its own :func:`write_audit_log`.
    """
    is_edit = instance is not None
    invoice = (instance.invoice if is_edit
               else get_object_or_404(SupplierInvoice, pk=invoice_pk, tenant=request.tenant))

    if request.method == "POST":
        form = SupplierInvoiceLineForm(request.POST, instance=instance, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.invoice = invoice
            obj.save()
            write_audit_log(request.user, obj, "update" if is_edit else "create",
                            _changed(form))
            messages.success(request, f"Line saved on {invoice.number}.")
            return redirect("procurement:supplierinvoice_detail", pk=invoice.pk)
    else:
        form = SupplierInvoiceLineForm(instance=instance, tenant=request.tenant)

    return render(request, TEMPLATE_FORM, {
        "form": form,
        "obj": instance,
        "invoice": invoice,
        "is_edit": is_edit,
        "title": f"Edit line on {invoice.number}" if is_edit else f"Add a line to {invoice.number}",
        "submit_label": "Save changes" if is_edit else "Add line",
        "cancel_url": reverse("procurement:supplierinvoice_detail", args=[invoice.pk]),
    })


@login_required
def supplierinvoiceline_create(request):
    """Create requires ``?invoice=<pk>``: a line with no header is an orphan row.

    The pk goes through ``as_db_int`` and then a tenant-scoped existence check, so
    ``?invoice=abc`` and ``?invoice=<another workspace's pk>`` are the same refusal.
    """
    guard = _need_tenant(request, "add supplier invoice lines")
    if guard is not None:
        return guard

    invoice_pk = as_db_int(request.GET.get("invoice", ""))
    invoice = (SupplierInvoice.objects.filter(pk=invoice_pk, tenant=request.tenant).first()
               if invoice_pk is not None else None)
    if invoice is None:
        messages.error(request, "Open a supplier invoice to add lines to it.")
        return redirect("procurement:supplierinvoice_list")
    if not _editable(invoice):
        messages.error(
            request,
            f"{invoice.number} is {invoice.get_status_display().lower()} — only a draft, parked "
            f"or captured invoice can take new lines.")
        return redirect("procurement:supplierinvoice_detail", pk=invoice.pk)
    return _line_form(request, invoice_pk=invoice.pk, instance=None)


@login_required
def supplierinvoiceline_edit(request, pk):
    obj = get_object_or_404(SupplierInvoiceLine.objects.select_related("invoice"),
                            pk=pk, invoice__tenant=request.tenant)
    if not _editable(obj.invoice):
        messages.error(
            request,
            f"{obj.invoice.number} is {obj.invoice.get_status_display().lower()} — its lines can "
            f"no longer be edited.")
        return redirect("procurement:supplierinvoiceline_detail", pk=pk)
    return _line_form(request, instance=obj)


@login_required
@require_POST
def supplierinvoiceline_delete(request, pk):
    """Remove one line and re-derive the header money.

    Hand-rolled rather than ``crud_delete``, which filters ``tenant=`` on the model — a column
    this child has not got (the ``AssetSparePart`` precedent in scm, same hazard, same fix). The
    audit row is written HERE, before the delete, while the row still exists to be described.
    """
    obj = get_object_or_404(SupplierInvoiceLine.objects.select_related("invoice"),
                            pk=pk, invoice__tenant=request.tenant)
    invoice = obj.invoice
    # Same guard the create and edit paths apply: past EDITABLE_STATUSES the header's Bill and
    # JournalEntry are already posted, so removing a line here would silently rewrite a total
    # the GL has already booked.
    if not _editable(invoice):
        messages.error(
            request,
            f"{invoice.number} is {invoice.get_status_display().lower()} — its lines can "
            f"no longer be removed.")
        return redirect("procurement:supplierinvoiceline_detail", pk=pk)
    invoice_pk = invoice.pk
    write_audit_log(request.user, obj, "delete")
    obj.delete()
    # A line's save() is what normally keeps the header money in step; a delete has no save() to
    # ride, so the header is re-derived here or it would keep billing for a line that is gone.
    invoice.recalc_totals()
    messages.success(request, f"Line removed from {invoice.number}.")
    return redirect("procurement:supplierinvoice_detail", pk=invoice_pk)


# -- Payment Schedule ---------------------------------------------------------------------------

def _horizon_weeks(request):
    """``?weeks=`` clamped to 1–26 — an unclamped value is a bucket list, not a horizon."""
    value = as_db_int(request.GET.get("weeks", ""))
    if value is None:
        return HORIZON_WEEKS_DEFAULT
    return max(HORIZON_WEEKS_MIN, min(HORIZON_WEEKS_MAX, value))


def _bucket(key, label, start, end, rows):
    """One bucket. ``total`` is the sum of the invoices' totals, already 2dp on every row."""
    return {
        "key": key,
        "label": label,
        "start": start,
        "end": end,
        "rows": rows,
        "count": len(rows),
        "total": sum((row.total or ZERO for row in rows), ZERO).quantize(Decimal("0.01")),
    }


def _discount_capturable(invoice, today):
    """What is still takeable on this invoice today — zero once the window has closed.

    ``discount_expiry_date`` already includes the workspace's grace days, so this is the only
    date to compare against.
    """
    expiry = invoice.discount_expiry_date or invoice.discount_date
    if not expiry or expiry < today:
        return ZERO
    return invoice.discount_amount()


@login_required
def paymentschedule_list(request):
    """**Payment Schedule** — what is owed, by when, and what a discount is still worth.

    A bucketed projection, not a register: approved and scheduled invoices with a due date,
    split into one Overdue bucket plus ``horizon_weeks`` weekly buckets. Every filter
    (``q``, ``vendor``, ``terms``) is applied BEFORE bucketing, so a bucket's ``count`` and
    ``total`` always describe the rows it actually holds.

    NOT paginated, deliberately. A pager over a flattened row list left every bucket rendering in
    full while the widget underneath counted a slice, so page 2 was byte-identical to page 1. The
    horizon IS the bound here — the queryset is filtered to ``overdue + 7 x horizon_weeks`` days
    and ``?weeks=`` is clamped to 26 — so there is nothing left for a pager to do.
    """
    guard = _need_tenant(request, "review the payment schedule")
    if guard is not None:
        return guard

    tenant = request.tenant
    today = timezone.localdate()
    q = request.GET.get("q", "").strip()
    horizon_weeks = _horizon_weeks(request)

    qs = (SupplierInvoice.objects
          .filter(tenant=tenant, status__in=("approved", "scheduled"))
          .exclude(due_date=None)
          .select_related("vendor", "currency", "payment_term")
          .order_by("due_date", "id"))

    vendor_pk = as_db_int(request.GET.get("vendor", ""))
    if vendor_pk is not None:
        qs = qs.filter(vendor_id=vendor_pk)
    terms_pk = as_db_int(request.GET.get("terms", ""))
    if terms_pk is not None:
        qs = qs.filter(payment_term_id=terms_pk)
    if q:
        qs = qs.filter(Q(number__icontains=q) | Q(invoice_number__icontains=q)
                       | Q(vendor__name__icontains=q))

    # Bound the scan to the horizon the page actually reports on. Every overdue row
    # (due_date < today) and every bucketed row (due_date <= horizon_end) is kept; only rows the
    # buckets would have discarded are dropped, so ``stats.invoices`` and ``discounted_total``
    # now describe exactly what is rendered instead of the whole future payables book.
    horizon_end = today + timedelta(days=7 * horizon_weeks - 1)
    qs = qs.filter(due_date__lte=horizon_end)

    rows = list(qs)

    overdue = [row for row in rows if row.due_date < today]
    buckets = [_bucket("overdue", "Overdue", None, None, overdue)]
    for index in range(horizon_weeks):
        start = today + timedelta(days=7 * index)
        end = start + timedelta(days=6)
        label = f"{start.strftime('%d %b')} – {end.strftime('%d %b')}"
        buckets.append(_bucket(f"w{index}", label, start, end,
                               [row for row in rows if start <= row.due_date <= end]))

    total_payable = sum((bucket["total"] for bucket in buckets), ZERO).quantize(Decimal("0.01"))
    discounted_total = sum((_discount_capturable(row, today) for row in rows), ZERO)

    return render(request, TEMPLATE_SCHEDULE, {
        "buckets": buckets,
        "total_payable": total_payable,
        "terms": PaymentTerm.objects.filter(tenant=tenant, is_active=True).order_by("name"),
        # accounting.Currency is GLOBAL — the workspace's own first currency, falling back to any.
        "currency": (Currency.objects.filter(pk__in=qs.values("currency_id")).first()
                     or Currency.objects.first()),
        "vendors": Party.objects.filter(tenant=tenant).order_by("name"),
        "stats": {
            "invoices": len(rows),
            "total_payable": total_payable,
            "overdue_total": buckets[0]["total"],
            "discounted_total": discounted_total.quantize(Decimal("0.01")),
        },
        "horizon_weeks": horizon_weeks,
        "today": today,
        "q": q,
    })
