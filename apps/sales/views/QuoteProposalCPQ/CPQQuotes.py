"""Views for CPQQuote management and lifecycle operations."""
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.utils import write_audit_log
from apps.crm.models import Opportunity
from apps.sales.cpq_services import cpq_recalc_quote_totals, cpq_evaluate_approval
from apps.sales.forms.QuoteProposalCPQ.CPQQuotes import CPQQuoteForm
from apps.sales.models.QuoteProposalCPQ.CPQQuotes import CPQQuote


@login_required
def cpq_quote_list(request):
    """List and filter enterprise CPQ quotes."""
    tenant = request.tenant
    qs = CPQQuote.objects.filter(tenant=tenant).select_related(
        "opportunity", "account", "contact", "currency", "owner"
    )

    # Search
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q) |
            Q(number__icontains=q) |
            Q(account__name__icontains=q) |
            Q(opportunity__name__icontains=q)
        )

    # Filters
    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    approval_status = request.GET.get("approval_status", "").strip()
    if approval_status:
        qs = qs.filter(approval_status=approval_status)

    opp_id = request.GET.get("opportunity", "").strip()
    if opp_id:
        qs = qs.filter(opportunity_id=opp_id)

    is_primary = request.GET.get("is_primary", "").strip()
    if is_primary in ["true", "1"]:
        qs = qs.filter(is_primary=True)
    elif is_primary in ["false", "0"]:
        qs = qs.filter(is_primary=False)

    stats = {
        "total": CPQQuote.objects.filter(tenant=tenant).count(),
        "draft": CPQQuote.objects.filter(tenant=tenant, status="draft").count(),
        "in_review": CPQQuote.objects.filter(tenant=tenant, status="in_review").count(),
        "approved": CPQQuote.objects.filter(tenant=tenant, status="approved").count(),
        "presented": CPQQuote.objects.filter(tenant=tenant, status="presented").count(),
        "accepted": CPQQuote.objects.filter(tenant=tenant, status="accepted").count(),
        "converted": CPQQuote.objects.filter(tenant=tenant, status="converted").count(),
    }

    opportunities = Opportunity.objects.filter(
        tenant=tenant,
        cpq_quotes__isnull=False
    ).distinct().order_by("name")

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "quotes": page_obj,
        "status_choices": CPQQuote.STATUS_CHOICES,
        "approval_status_choices": CPQQuote.APPROVAL_STATUS_CHOICES,
        "opportunities": opportunities,
        "stats": stats,
    }
    return render(request, "sales/quote_proposal_cpq/cpqquote/list.html", context)


@login_required
def cpq_quote_create(request):
    """Create a new CPQQuote header."""
    tenant = request.tenant
    if request.method == "POST":
        form = CPQQuoteForm(request.POST, tenant=tenant)
        if form.is_valid():
            quote = form.save(commit=False)
            quote.tenant = tenant
            if not quote.owner_id:
                quote.owner = request.user
            quote.save()

            # If marked primary, ensure other quotes in same group are not primary
            if quote.is_primary:
                CPQQuote.objects.filter(
                    tenant=tenant,
                    quote_group_id=quote.quote_group_id,
                    is_primary=True
                ).exclude(pk=quote.pk).update(is_primary=False)

            cpq_recalc_quote_totals(quote, save=True)
            write_audit_log(request.user, "create", "CPQQuote", quote.id, f"Created quote {quote.number} ({quote.name})")
            messages.success(request, f"Quote {quote.number} created successfully. You can now configure line items and bundles.")
            return redirect("sales:cpq_quote_detail", pk=quote.pk)
    else:
        initial = {}
        if request.GET.get("opportunity"):
            initial["opportunity"] = request.GET.get("opportunity")
        form = CPQQuoteForm(tenant=tenant, initial=initial)

    return render(request, "sales/quote_proposal_cpq/cpqquote/form.html", {
        "form": form,
        "is_create": True,
    })


@login_required
def cpq_quote_detail(request, pk):
    """Workspace for quote configuration, line hierarchy, approval tracking, and customer presentation."""
    tenant = request.tenant
    quote = get_object_or_404(
        CPQQuote.objects.select_related(
            "opportunity", "account", "contact", "currency", "price_book",
            "approval_rule", "approved_by", "proposal_template", "converted_order", "owner"
        ),
        pk=pk,
        tenant=tenant
    )

    # Ensure fresh totals
    cpq_recalc_quote_totals(quote, save=True)

    # Group lines by parent / hierarchy
    all_lines = list(quote.lines.select_related("product", "item", "uom", "tax_code").order_by("sequence", "id"))
    
    # Related quotes in same revision group
    revisions = CPQQuote.objects.filter(
        tenant=tenant,
        quote_group_id=quote.quote_group_id
    ).order_by("-revision_number")

    is_admin = request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)
    can_edit = quote.is_editable or is_admin
    can_approve = is_admin and quote.approval_status == "pending"
    can_convert = quote.can_convert

    return render(request, "sales/quote_proposal_cpq/cpqquote/detail.html", {
        "quote": quote,
        "lines": all_lines,
        "revisions": revisions,
        "can_edit": can_edit,
        "can_approve": can_approve,
        "can_convert": can_convert,
    })


@login_required
def cpq_quote_edit(request, pk):
    """Edit CPQQuote header attributes."""
    tenant = request.tenant
    quote = get_object_or_404(CPQQuote, pk=pk, tenant=tenant)
    is_admin = request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)

    if not quote.is_editable and not is_admin:
        messages.warning(request, f"Quote {quote.number} is locked in status '{quote.get_status_display()}'. Create a new revision to make changes.")
        return redirect("sales:cpq_quote_detail", pk=quote.pk)

    if request.method == "POST":
        form = CPQQuoteForm(request.POST, instance=quote, tenant=tenant)
        if form.is_valid():
            quote = form.save()
            if quote.is_primary:
                CPQQuote.objects.filter(
                    tenant=tenant,
                    quote_group_id=quote.quote_group_id,
                    is_primary=True
                ).exclude(pk=quote.pk).update(is_primary=False)

            cpq_recalc_quote_totals(quote, save=True)
            write_audit_log(request.user, "update", "CPQQuote", quote.id, f"Updated quote {quote.number}")
            messages.success(request, f"Quote {quote.number} updated successfully.")
            return redirect("sales:cpq_quote_detail", pk=quote.pk)
    else:
        form = CPQQuoteForm(instance=quote, tenant=tenant)

    return render(request, "sales/quote_proposal_cpq/cpqquote/form.html", {
        "form": form,
        "quote": quote,
        "is_create": False,
    })


@require_POST
@login_required
def cpq_quote_delete(request, pk):
    """Delete a draft or rejected CPQQuote."""
    tenant = request.tenant
    quote = get_object_or_404(CPQQuote, pk=pk, tenant=tenant)
    
    if quote.status == "converted":
        messages.error(request, "Cannot delete a quote that has been converted to a sales order.")
        return redirect("sales:cpq_quote_detail", pk=quote.pk)

    number = quote.number
    quote_id = quote.id
    quote.delete()
    write_audit_log(request.user, "delete", "CPQQuote", quote_id, f"Deleted quote {number}")
    messages.success(request, f"Quote {number} deleted successfully.")
    return redirect("sales:cpq_quote_list")
