"""Views for CPQQuoteLine CRUD and bundle component configuration."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.utils import write_audit_log
from apps.sales.cpq_services import cpq_recalc_quote_totals
from apps.sales.forms.QuoteProposalCPQ.CPQQuoteLines import CPQQuoteLineForm
from apps.sales.models.QuoteProposalCPQ.CPQQuotes import CPQQuote
from apps.sales.models.QuoteProposalCPQ.CPQQuoteLines import CPQQuoteLine


@login_required
def cpq_quote_line_list(request, quote_pk):
    """List lines for a specific quote."""
    tenant = request.tenant
    quote = get_object_or_404(CPQQuote, pk=quote_pk, tenant=tenant)
    lines = quote.lines.select_related("product", "item", "uom", "parent_line").order_by("sequence", "id")

    stats = {
        "total_lines": lines.count(),
        "bundles": lines.filter(line_type="bundle_parent").count(),
        "optional": lines.filter(is_optional=True).count(),
    }

    return render(request, "sales/quote_proposal_cpq/cpqquoteline/list.html", {
        "quote": quote,
        "lines": lines,
        "stats": stats,
    })


@login_required
def cpq_quote_line_create(request, quote_pk):
    """Add a new line item to a CPQ quote."""
    tenant = request.tenant
    quote = get_object_or_404(CPQQuote, pk=quote_pk, tenant=tenant)

    if not quote.is_editable and not (request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)):
        messages.warning(request, "This quote is locked. Create a revision to modify line items.")
        return redirect("sales:cpq_quote_detail", pk=quote.pk)

    if request.method == "POST":
        form = CPQQuoteLineForm(request.POST, tenant=tenant, quote=quote)
        if form.is_valid():
            line = form.save(commit=False)
            line.tenant = tenant
            line.quote = quote
            line.save()

            cpq_recalc_quote_totals(quote, save=True)
            write_audit_log(request.user, "create", "CPQQuoteLine", line.id, f"Added line {line.description} to quote {quote.number}")
            messages.success(request, f"Added {line.description} to quote.")
            return redirect("sales:cpq_quote_detail", pk=quote.pk)
    else:
        # Prepopulate sequence to 10 * next count
        next_seq = (quote.lines.count() + 1) * 10
        form = CPQQuoteLineForm(tenant=tenant, quote=quote, initial={"sequence": next_seq})

    return render(request, "sales/quote_proposal_cpq/cpqquoteline/form.html", {
        "form": form,
        "quote": quote,
        "is_create": True,
    })


@login_required
def cpq_quote_line_detail(request, quote_pk, pk):
    """View line item detail."""
    tenant = request.tenant
    quote = get_object_or_404(CPQQuote, pk=quote_pk, tenant=tenant)
    line = get_object_or_404(CPQQuoteLine.objects.select_related("product", "item", "uom", "parent_line"), pk=pk, quote=quote, tenant=tenant)
    children = line.bundle_children.all()

    return render(request, "sales/quote_proposal_cpq/cpqquoteline/detail.html", {
        "quote": quote,
        "line": line,
        "children": children,
    })


@login_required
def cpq_quote_line_edit(request, quote_pk, pk):
    """Edit a line item on a CPQ quote."""
    tenant = request.tenant
    quote = get_object_or_404(CPQQuote, pk=quote_pk, tenant=tenant)
    line = get_object_or_404(CPQQuoteLine, pk=pk, quote=quote, tenant=tenant)

    if not quote.is_editable and not (request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)):
        messages.warning(request, "This quote is locked. Create a revision to modify line items.")
        return redirect("sales:cpq_quote_detail", pk=quote.pk)

    if request.method == "POST":
        form = CPQQuoteLineForm(request.POST, instance=line, tenant=tenant, quote=quote)
        if form.is_valid():
            line = form.save()
            cpq_recalc_quote_totals(quote, save=True)
            write_audit_log(request.user, "update", "CPQQuoteLine", line.id, f"Updated line {line.description} on quote {quote.number}")
            messages.success(request, f"Updated {line.description}.")
            return redirect("sales:cpq_quote_detail", pk=quote.pk)
    else:
        form = CPQQuoteLineForm(instance=line, tenant=tenant, quote=quote)

    return render(request, "sales/quote_proposal_cpq/cpqquoteline/form.html", {
        "form": form,
        "quote": quote,
        "line": line,
        "is_create": False,
    })


@require_POST
@login_required
def cpq_quote_line_delete(request, quote_pk, pk):
    """Delete a line item and recalculate quote totals."""
    tenant = request.tenant
    quote = get_object_or_404(CPQQuote, pk=quote_pk, tenant=tenant)
    line = get_object_or_404(CPQQuoteLine, pk=pk, quote=quote, tenant=tenant)

    if not quote.is_editable and not (request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)):
        messages.warning(request, "This quote is locked and line items cannot be deleted.")
        return redirect("sales:cpq_quote_detail", pk=quote.pk)

    desc = line.description
    line_id = line.id
    line.delete()
    cpq_recalc_quote_totals(quote, save=True)
    write_audit_log(request.user, "delete", "CPQQuoteLine", line_id, f"Deleted line {desc} from quote {quote.number}")
    messages.success(request, f"Removed line item {desc}.")
    return redirect("sales:cpq_quote_detail", pk=quote.pk)
