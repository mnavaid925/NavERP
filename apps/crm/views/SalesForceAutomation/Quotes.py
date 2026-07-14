"""CRM 1.2 Sales Force Automation — Quotes views (split from apps/crm/views.py)."""
from apps.crm.views._common import *  # noqa: F401,F403
from apps.crm.models import (
    Opportunity,
    Quote,
    QuoteLine,
)
from apps.crm.forms import (
    QuoteForm,
    QuoteLineForm,
)


# ------------------------------------------------------------ Quotes (1.2 quoting)
@login_required
def quote_list(request):
    return crud_list(
        request,
        Quote.objects.filter(tenant=request.tenant).select_related("account", "opportunity", "owner"),
        "crm/sales/quote/list.html",
        search_fields=["number", "name", "account__name"],
        filters=[("status", "status", False), ("opportunity", "opportunity_id", True)],
        extra_context={"status_choices": Quote.STATUS_CHOICES,
                       "opportunities": Opportunity.objects.filter(tenant=request.tenant).only("pk", "name", "number")},
    )


@login_required
def quote_create(request):
    return crud_create(request, form_class=QuoteForm, template="crm/sales/quote/form.html",
                       success_url="crm:quote_list")


@login_required
def quote_detail(request, pk):
    obj = get_object_or_404(
        Quote.objects.select_related("account", "opportunity", "price_book", "owner"),
        pk=pk, tenant=request.tenant)
    return render(request, "crm/sales/quote/detail.html", {
        "obj": obj,
        "lines": obj.lines.select_related("product"),
        "line_form": QuoteLineForm(tenant=request.tenant),
    })


@login_required
def quote_edit(request, pk):
    return crud_edit(request, model=Quote, pk=pk, form_class=QuoteForm,
                     template="crm/sales/quote/form.html", success_url="crm:quote_list")


@login_required
@require_POST
def quote_delete(request, pk):
    return crud_delete(request, model=Quote, pk=pk, success_url="crm:quote_list")


@login_required
def quote_print(request, pk):
    """Print-styled quote (login-gated — quotes carry pricing, so no public token endpoint)."""
    obj = get_object_or_404(
        Quote.objects.select_related("account", "opportunity", "price_book", "owner"),
        pk=pk, tenant=request.tenant)
    return render(request, "crm/sales/quote/print.html", {
        "obj": obj, "lines": obj.lines.select_related("product")})


@login_required
@require_POST
def quoteline_add(request, pk):
    quote = get_object_or_404(Quote.objects.select_related("price_book"), pk=pk, tenant=request.tenant)
    if quote.status not in Quote.OPEN_STATUSES:
        messages.info(request, "Only a draft or sent quote can be edited.")
        return redirect("crm:quote_detail", pk=quote.pk)
    form = QuoteLineForm(request.POST, tenant=request.tenant)
    if not form.is_valid():
        messages.error(request, "Could not add line — check the fields.")
        return redirect("crm:quote_detail", pk=quote.pk)
    line = form.save(commit=False)
    line.tenant = request.tenant
    line.quote = quote
    # Default price/desc/tax from the product, adjusted by the quote's price book.
    if line.product_id:
        if not line.unit_price:
            base = line.product.unit_price
            line.unit_price = quote.price_book.adjusted_price(base) if quote.price_book else base
        if not line.tax_pct:
            line.tax_pct = line.product.tax_pct
        if not line.description:
            line.description = line.product.name
    line.order = quote.lines.count()
    with transaction.atomic():
        line.save()
        quote.recalc_totals()
    messages.success(request, "Line added.")
    return redirect("crm:quote_detail", pk=quote.pk)


@login_required
@require_POST
def quoteline_remove(request, line_pk):
    line = get_object_or_404(QuoteLine.objects.select_related("quote"), pk=line_pk, tenant=request.tenant)
    quote = line.quote
    with transaction.atomic():
        line.delete()
        quote.recalc_totals()
    messages.success(request, "Line removed.")
    return redirect("crm:quote_detail", pk=quote.pk)


# Quote send/accept/decline + opportunity_advance stay @login_required (NOT @tenant_admin_required):
# pipeline progression is day-to-day rep work (cf. Salesforce/HubSpot deal ownership). The
# tenant-admin gate in this codebase is reserved for financial posting / workspace config. All
# transitions are audit-logged.
@login_required
@require_POST
def quote_send(request, pk):
    quote = get_object_or_404(Quote, pk=pk, tenant=request.tenant)
    if quote.status != "draft":
        messages.info(request, "Only a draft quote can be sent.")
        return redirect("crm:quote_detail", pk=quote.pk)
    quote.status = "sent"
    quote.sent_at = timezone.now()
    quote.save(update_fields=["status", "sent_at", "updated_at"])
    write_audit_log(request.user, quote, "update", {"action": "send"})
    messages.success(request, f"{quote.number} marked as sent.")
    return redirect("crm:quote_detail", pk=quote.pk)


@login_required
@require_POST
def quote_accept(request, pk):
    quote = get_object_or_404(Quote, pk=pk, tenant=request.tenant)
    if quote.status != "sent":
        messages.info(request, "Only a sent quote can be accepted.")
        return redirect("crm:quote_detail", pk=quote.pk)
    quote.status = "accepted"
    quote.accepted_at = timezone.now()
    quote.save(update_fields=["status", "accepted_at", "updated_at"])
    write_audit_log(request.user, quote, "update", {"action": "accept"})
    messages.success(request, f"{quote.number} accepted.")
    return redirect("crm:quote_detail", pk=quote.pk)


@login_required
@require_POST
def quote_decline(request, pk):
    quote = get_object_or_404(Quote, pk=pk, tenant=request.tenant)
    if quote.status != "sent":
        messages.info(request, "Only a sent quote can be declined.")
        return redirect("crm:quote_detail", pk=quote.pk)
    quote.status = "declined"
    quote.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, quote, "update", {"action": "decline"})
    messages.success(request, f"{quote.number} declined.")
    return redirect("crm:quote_detail", pk=quote.pk)
