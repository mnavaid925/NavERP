"""SCM 4.1 Procurement Management — RFQ views (incl. side-by-side quote comparison and award)."""
from apps.scm.views._common import *  # noqa: F401,F403
# `import *` skips underscore-prefixed names, so private helpers need an explicit import.
from apps.scm.views._common import _changed
from apps.scm.views._helpers import _need_tenant
from apps.scm.models import (
    RFQ,
    RFQQuote,
    PurchaseOrder,
    PurchaseOrderLine,
)
from apps.scm.forms import (
    RFQForm,
    RFQLineFormSet,
    RFQVendorFormSet,
    RFQQuoteForm,
    RFQQuoteLineFormSet,
)


@login_required
def rfq_list(request):
    qs = (RFQ.objects
          .filter(tenant=request.tenant)
          .select_related("requisition", "currency")
          .annotate(quote_count=Count("quotes", distinct=True))
          # The Count annotation introduces a GROUP BY that drops Meta.ordering, which makes
          # pagination non-deterministic (rows can repeat or vanish across pages). Re-assert it.
          .order_by("-created_at", "-id"))
    return crud_list(
        request, qs, "scm/procurement/rfq/list.html",
        search_fields=["number", "title"],
        filters=[("status", "status", False)],
        extra_context={"status_choices": RFQ.STATUS_CHOICES},
    )


@login_required
def rfq_create(request):
    return _rfq_form(request, instance=None)


@login_required
def rfq_edit(request, pk):
    obj = get_object_or_404(RFQ, pk=pk, tenant=request.tenant)
    if not obj.is_editable:
        messages.error(request, "A closed, awarded or cancelled RFQ cannot be edited.")
        return redirect("scm:rfq_detail", pk=pk)
    return _rfq_form(request, instance=obj)


def _rfq_form(request, instance):
    if instance is None and _need_tenant(request):
        return redirect("scm:rfq_list")
    is_edit = instance is not None
    if request.method == "POST":
        form = RFQForm(request.POST, request.FILES, instance=instance, tenant=request.tenant)
        lines = RFQLineFormSet(request.POST, instance=instance, prefix="lines",
                               form_kwargs={"tenant": request.tenant})
        vendors = RFQVendorFormSet(request.POST, instance=instance, prefix="vendors",
                                   form_kwargs={"tenant": request.tenant})
        if form.is_valid() and lines.is_valid() and vendors.is_valid():
            with transaction.atomic():
                rfq = form.save(commit=False)
                rfq.tenant = request.tenant
                rfq.save()
                lines.instance = rfq
                lines.save()
                vendors.instance = rfq
                invites = vendors.save(commit=False)
                for invite in invites:
                    invite.tenant = request.tenant
                    invite.save()
                for gone in vendors.deleted_objects:
                    gone.delete()
            write_audit_log(request.user, rfq, "update" if is_edit else "create", _changed(form))
            messages.success(request, f"RFQ {rfq.number} saved.")
            return redirect("scm:rfq_detail", pk=rfq.pk)
    else:
        form = RFQForm(instance=instance, tenant=request.tenant)
        lines = RFQLineFormSet(instance=instance, prefix="lines", form_kwargs={"tenant": request.tenant})
        vendors = RFQVendorFormSet(instance=instance, prefix="vendors", form_kwargs={"tenant": request.tenant})
    return render(request, "scm/procurement/rfq/form.html",
                  {"form": form, "formset": lines, "vendor_formset": vendors,
                   "is_edit": is_edit, "obj": instance})


@login_required
def rfq_detail(request, pk):
    obj = get_object_or_404(
        RFQ.objects.select_related("requisition", "currency"), pk=pk, tenant=request.tenant)
    quotes = list(obj.quotes.select_related("party", "payment_terms"))
    # Which suppliers have answered, resolved in ONE pass over the quotes we already hold. The
    # RFQVendor.has_responded property costs an .exists() per row, which is an N+1 across the
    # invite list on a page every buyer opens right after sending an RFQ.
    responded_party_ids = {q.party_id for q in quotes}
    invited = list(obj.invited_vendors.select_related("party"))
    for invite in invited:
        invite.responded = invite.party_id in responded_party_ids
    return render(request, "scm/procurement/rfq/detail.html", {
        "obj": obj,
        "lines": obj.lines.all(),
        "invited_vendors": invited,
        "quotes": quotes,
        # Resolved from the list already in memory rather than a fresh filter() query.
        "awarded": next((q for q in quotes if q.status == "awarded"), None),
    })


@login_required
@require_POST
def rfq_delete(request, pk):
    obj = get_object_or_404(RFQ, pk=pk, tenant=request.tenant)
    if obj.status != "draft":
        messages.error(request, "Only a draft RFQ can be deleted.")
        return redirect("scm:rfq_detail", pk=pk)
    return crud_delete(request, model=RFQ, pk=pk, success_url="scm:rfq_list")


@login_required
@require_POST
def rfq_send(request, pk):
    """Draft -> sent. Stamps the invite list so 'who was asked, when' is auditable."""
    obj = get_object_or_404(RFQ, pk=pk, tenant=request.tenant)
    if obj.status != "draft":
        messages.info(request, "This RFQ has already been sent.")
        return redirect("scm:rfq_detail", pk=pk)
    if not obj.lines.exists():
        messages.error(request, "Add at least one line before sending.")
        return redirect("scm:rfq_detail", pk=pk)
    if not obj.invited_vendors.exists():
        messages.error(request, "Invite at least one supplier before sending.")
        return redirect("scm:rfq_detail", pk=pk)
    now = timezone.now()
    with transaction.atomic():
        obj.status = "sent"
        if not obj.issue_date:
            obj.issue_date = timezone.localdate()
        obj.save(update_fields=["status", "issue_date", "updated_at"])
        obj.invited_vendors.filter(invited_at__isnull=True).update(invited_at=now)
    write_audit_log(request.user, obj, "update", {"action": "send"})
    messages.success(request, f"RFQ {obj.number} marked as sent to {obj.invited_vendors.count()} supplier(s).")
    return redirect("scm:rfq_detail", pk=pk)


@login_required
@require_POST
def rfq_close(request, pk):
    obj = get_object_or_404(RFQ, pk=pk, tenant=request.tenant)
    if obj.status != "sent":
        messages.info(request, "Only a sent RFQ can be closed.")
        return redirect("scm:rfq_detail", pk=pk)
    obj.status = "closed"
    obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "close"})
    messages.success(request, f"RFQ {obj.number} closed to further quotes.")
    return redirect("scm:rfq_detail", pk=pk)


@login_required
def rfq_compare(request, pk):
    """Side-by-side quote comparison — the point of running an RFQ.

    Builds a matrix of RFQ line (row) x quote (column) so a buyer can see who is cheapest per line,
    not just in total. The per-line best price is computed here rather than in the template so the
    template stays a dumb renderer.
    """
    obj = get_object_or_404(RFQ.objects.select_related("currency"), pk=pk, tenant=request.tenant)
    quotes = list(obj.quotes.select_related("party").prefetch_related("lines"))
    lines = list(obj.lines.all())

    # {rfq_line_id: {quote_id: quote_line}} — one pass over the prefetched lines, no N+1.
    priced = {line.id: {} for line in lines}
    for quote in quotes:
        for quote_line in quote.lines.all():
            if quote_line.rfq_line_id in priced:
                priced[quote_line.rfq_line_id][quote.id] = quote_line

    matrix = []
    for line in lines:
        cells = []
        best = None
        for quote in quotes:
            quote_line = priced[line.id].get(quote.id)
            if quote_line and (best is None or quote_line.unit_price < best):
                best = quote_line.unit_price
        for quote in quotes:
            quote_line = priced[line.id].get(quote.id)
            cells.append({
                "quote": quote,
                "line": quote_line,
                "is_best": bool(quote_line and best is not None and quote_line.unit_price == best),
            })
        matrix.append({"line": line, "cells": cells, "best_price": best})

    totals = [q.total for q in quotes if q.total is not None]
    best_total = min(totals) if totals else None
    return render(request, "scm/procurement/rfq/compare.html", {
        "obj": obj,
        "quotes": quotes,
        "matrix": matrix,
        "best_total": best_total,
        # From the list already in memory — awarded_quote() would re-query for a row we hold.
        "awarded": next((q for q in quotes if q.status == "awarded"), None),
    })


# ------------------------------------------------------------------ quotes (children of an RFQ)
# Quotes only exist between issuing an RFQ and awarding it: there is nothing to quote against a
# draft, and re-pricing an awarded/cancelled RFQ would rewrite the basis of a decision already made.
QUOTABLE_RFQ_STATUSES = ("sent", "closed")


@login_required
def quote_create(request, rfq_pk):
    rfq = get_object_or_404(RFQ, pk=rfq_pk, tenant=request.tenant)
    if rfq.status not in QUOTABLE_RFQ_STATUSES:
        messages.error(request, "Quotes can only be recorded against a sent or closed RFQ.")
        return redirect("scm:rfq_detail", pk=rfq.pk)
    return _quote_form(request, rfq=rfq, instance=None)


@login_required
def quote_edit(request, pk):
    obj = get_object_or_404(RFQQuote.objects.select_related("rfq"), pk=pk, tenant=request.tenant)
    if obj.status == "awarded":
        messages.error(request, "An awarded quote cannot be edited.")
        return redirect("scm:rfq_detail", pk=obj.rfq_id)
    if obj.rfq.status not in QUOTABLE_RFQ_STATUSES:
        messages.error(request, "This RFQ is no longer open to quote changes.")
        return redirect("scm:rfq_detail", pk=obj.rfq_id)
    return _quote_form(request, rfq=obj.rfq, instance=obj)


def _quote_form(request, rfq, instance):
    if instance is None and _need_tenant(request):
        return redirect("scm:rfq_list")
    is_edit = instance is not None
    if request.method == "POST":
        form = RFQQuoteForm(request.POST, instance=instance, tenant=request.tenant)
        formset = RFQQuoteLineFormSet(request.POST, instance=instance, rfq=rfq,
                                      form_kwargs={"tenant": request.tenant})
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                quote = form.save(commit=False)
                quote.tenant = request.tenant
                quote.rfq = rfq
                quote.save()
                formset.instance = quote
                formset.save()
                quote.recalc_totals()
            write_audit_log(request.user, quote, "update" if is_edit else "create", _changed(form))
            messages.success(request, f"Quote {quote.number} saved.")
            return redirect("scm:rfq_detail", pk=rfq.pk)
    else:
        form = RFQQuoteForm(instance=instance, tenant=request.tenant)
        formset = RFQQuoteLineFormSet(instance=instance, rfq=rfq, form_kwargs={"tenant": request.tenant})
    return render(request, "scm/procurement/quote/form.html",
                  {"form": form, "formset": formset, "is_edit": is_edit, "obj": instance, "rfq": rfq})


@login_required
@require_POST
def quote_delete(request, pk):
    # Hand-rolled rather than crud_delete: the redirect needs the parent RFQ's pk, which
    # crud_delete's plain `success_url` string cannot carry.
    obj = get_object_or_404(RFQQuote, pk=pk, tenant=request.tenant)
    if obj.status == "awarded":
        messages.error(request, "An awarded quote cannot be deleted.")
        return redirect("scm:rfq_detail", pk=obj.rfq_id)
    rfq_pk = obj.rfq_id
    write_audit_log(request.user, obj, "delete")
    obj.delete()
    messages.success(request, "Quote deleted.")
    return redirect("scm:rfq_detail", pk=rfq_pk)


@tenant_admin_required
@require_POST
def quote_award(request, pk):
    """Award a quote and draft the resulting purchase order.

    Tenant-admin gated: awarding commits the tenant to a supplier. The PO is created as a DRAFT —
    it still goes through PO approval — so this is a hand-off, not a way to bypass sign-off.
    """
    quote = get_object_or_404(
        RFQQuote.objects.select_related("rfq", "party", "payment_terms"), pk=pk, tenant=request.tenant)
    rfq = quote.rfq
    if rfq.status == "awarded":
        messages.info(request, "This RFQ has already been awarded.")
        return redirect("scm:rfq_detail", pk=rfq.pk)
    if rfq.status not in ("sent", "closed"):
        messages.error(request, "Only a sent or closed RFQ can be awarded.")
        return redirect("scm:rfq_detail", pk=rfq.pk)

    with transaction.atomic():
        quote.status = "awarded"
        quote.save(update_fields=["status", "updated_at"])
        rfq.quotes.exclude(pk=quote.pk).filter(status__in=("received", "shortlisted")).update(status="rejected")
        rfq.status = "awarded"
        rfq.save(update_fields=["status", "updated_at"])

        po = PurchaseOrder(
            tenant=request.tenant,
            vendor=quote.party,
            requisition=rfq.requisition,
            quote=quote,
            currency=rfq.currency,
            payment_terms=quote.payment_terms,
            order_date=timezone.localdate(),
            status="draft",
            notes=f"Created from {rfq.number} / quote {quote.number}.",
        )
        po.save()
        for quote_line in quote.lines.select_related("rfq_line"):
            PurchaseOrderLine.objects.create(
                purchase_order=po,
                item_description=quote_line.rfq_line.item_description,
                sku_hint=quote_line.rfq_line.sku_hint,
                uom_hint=quote_line.rfq_line.uom_hint,
                quantity=quote_line.quantity,
                unit_price=quote_line.unit_price,
            )
        po.recalc_totals()
        if rfq.requisition_id and rfq.requisition.status == "approved":
            rfq.requisition.status = "converted"
            rfq.requisition.save(update_fields=["status", "updated_at"])

    write_audit_log(request.user, quote, "update", {"action": "award", "purchase_order": po.number})
    write_audit_log(request.user, po, "create", {"source": f"{rfq.number}/{quote.number}"})
    messages.success(request, f"Quote {quote.number} awarded — draft order {po.number} created.")
    return redirect("scm:purchaseorder_detail", pk=po.pk)
