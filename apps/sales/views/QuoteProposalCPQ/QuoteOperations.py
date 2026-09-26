"""Dedicated CPQ operational views: approvals, proposals, public portal, version compare, order conversion, and guided selling."""
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Max
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.crm.models import Opportunity, Product
from apps.sales.cpq_services import (
    cpq_recalc_quote_totals,
    cpq_evaluate_approval,
    cpq_create_revision,
    cpq_compare_quote_versions,
    cpq_render_proposal_html,
    cpq_convert_to_sales_order,
)
from apps.sales.forms.QuoteProposalCPQ.CPQQuotes import (
    CPQQuoteApprovalActionForm,
    CPQPortalSignForm,
)
from apps.sales.models.QuoteProposalCPQ.CPQQuotes import CPQQuote
from apps.sales.models.QuoteProposalCPQ.CPQQuoteLines import CPQQuoteLine
from apps.sales.models.QuoteProposalCPQ.ProductBundles import ProductBundleOption


# -------------------------------------------------------------------------
# 1. Approval Governance Workflow
# -------------------------------------------------------------------------

@require_POST
@login_required
def quote_submit_approval(request, pk):
    """Evaluate pricing rules and submit quote into approval workflow."""
    tenant = request.tenant
    quote = get_object_or_404(CPQQuote, pk=pk, tenant=tenant)

    if not quote.lines.exists():
        messages.error(request, "Cannot submit an empty quote for approval. Add at least one line item.")
        return redirect("sales:cpq_quote_detail", pk=quote.pk)

    requires_approval, rule, reason = cpq_evaluate_approval(quote)

    if requires_approval:
        if rule and rule.auto_reject:
            quote.status = "rejected"
            quote.approval_status = "rejected"
            quote.approval_rule = rule
            quote.approval_note = f"Auto-rejected by policy {rule.name}: {reason}"
            messages.error(request, f"Quote auto-rejected: {reason}")
        else:
            quote.status = "in_review"
            quote.approval_status = "pending"
            quote.approval_rule = rule
            quote.approval_note = reason
            messages.warning(request, f"Quote requires managerial approval: {reason}")
    else:
        quote.status = "approved"
        quote.approval_status = "approved"
        quote.approved_at = timezone.now()
        quote.approved_by = request.user
        quote.approval_note = "Within standard pricing thresholds."
        messages.success(request, "Quote pricing is within standard thresholds and has been automatically approved.")

    quote.save(update_fields=["status", "approval_status", "approval_rule", "approved_at", "approved_by", "approval_note", "updated_at"])
    write_audit_log(request.user, quote, "submit_approval", {"action": "submit_approval", "status": quote.approval_status}, tenant=tenant)
    return redirect("sales:cpq_quote_detail", pk=quote.pk)


@login_required
def quote_approval_queue(request):
    """Manager dashboard of all quotes pending approval review."""
    tenant = request.tenant
    pending_quotes = CPQQuote.objects.filter(
        tenant=tenant,
        approval_status="pending"
    ).select_related("opportunity", "account", "owner", "approval_rule", "currency").order_by("-created_at")

    stats = {
        "pending": pending_quotes.count(),
        "approved_this_month": CPQQuote.objects.filter(
            tenant=tenant,
            approval_status="approved",
            approved_at__year=timezone.now().year,
            approved_at__month=timezone.now().month
        ).count(),
        "rejected_this_month": CPQQuote.objects.filter(
            tenant=tenant,
            approval_status="rejected",
            updated_at__year=timezone.now().year,
            updated_at__month=timezone.now().month
        ).count(),
    }

    return render(request, "sales/quote_proposal_cpq/operations/approval_queue.html", {
        "pending_quotes": pending_quotes,
        "stats": stats,
    })


@login_required
@tenant_admin_required
def quote_approval_action(request, pk):
    """Review and approve or reject a pending CPQ quote with audit notes."""
    tenant = request.tenant
    quote = get_object_or_404(CPQQuote, pk=pk, tenant=tenant)

    if request.method == "POST":
        form = CPQQuoteApprovalActionForm(request.POST)
        if form.is_valid():
            action = form.cleaned_data["action"]
            note = form.cleaned_data["note"]

            if action == "approved":
                quote.approval_status = "approved"
                quote.status = "approved"
                quote.approved_by = request.user
                quote.approved_at = timezone.now()
                quote.approval_note = note or "Approved by management."
                messages.success(request, f"Quote {quote.number} approved successfully.")
            else:
                quote.approval_status = "rejected"
                quote.status = "rejected"
                quote.approved_by = request.user
                quote.approved_at = timezone.now()
                quote.approval_note = note
                messages.warning(request, f"Quote {quote.number} rejected.")

            quote.save(update_fields=["approval_status", "status", "approved_by", "approved_at", "approval_note", "updated_at"])
            write_audit_log(request.user, quote, "approval_decision", {"action": action, "note": note}, tenant=tenant)
            return redirect("sales:cpq_quote_detail", pk=quote.pk)
    else:
        form = CPQQuoteApprovalActionForm(initial={"action": "approved"})

    return render(request, "sales/quote_proposal_cpq/operations/approval_action.html", {
        "quote": quote,
        "form": form,
    })


# -------------------------------------------------------------------------
# 2. Versioning & Side-by-Side Comparison
# -------------------------------------------------------------------------

@require_POST
@login_required
def quote_create_revision(request, pk):
    """Create a new version (revision) of a quote."""
    tenant = request.tenant
    quote = get_object_or_404(CPQQuote, pk=pk, tenant=tenant)

    new_quote = cpq_create_revision(quote, user=request.user)
    write_audit_log(request.user, new_quote, "create_revision", {"action": "create_revision", "from_quote": quote.number, "new_quote": new_quote.number}, tenant=tenant)
    messages.success(request, f"Created Revision {new_quote.revision_number} ({new_quote.number}). Prior revision marked superseded.")
    return redirect("sales:cpq_quote_detail", pk=new_quote.pk)


@login_required
def quote_compare_versions(request, pk_a, pk_b):
    """Compare two revisions in a quote family side-by-side."""
    tenant = request.tenant
    quote_a = get_object_or_404(CPQQuote.objects.select_related("currency", "account"), pk=pk_a, tenant=tenant)
    quote_b = get_object_or_404(CPQQuote.objects.select_related("currency", "account"), pk=pk_b, tenant=tenant)

    diff_data = cpq_compare_quote_versions(quote_a, quote_b)

    return render(request, "sales/quote_proposal_cpq/operations/compare.html", {
        "quote_a": quote_a,
        "quote_b": quote_b,
        "diff_data": diff_data,
    })


@login_required
def quote_version_list(request):
    """Register of quote revision families with version counts and primary indicators."""
    tenant = request.tenant
    
    # Group by quote_group_id
    families = (
        CPQQuote.objects.filter(tenant=tenant)
        .values("quote_group_id")
        .annotate(
            version_count=Count("id"),
            latest_revision=Max("revision_number"),
        )
        .order_by("-latest_revision")
    )

    family_records = []
    for f in families:
        group_id = f["quote_group_id"]
        latest_quote = (
            CPQQuote.objects.filter(tenant=tenant, quote_group_id=group_id)
            .select_related("account", "opportunity", "currency", "owner")
            .order_by("-revision_number")
            .first()
        )
        if latest_quote:
            family_records.append({
                "group_id": group_id,
                "version_count": f["version_count"],
                "latest_quote": latest_quote,
            })

    return render(request, "sales/quote_proposal_cpq/operations/version_list.html", {
        "families": family_records,
    })


# -------------------------------------------------------------------------
# 3. Proposal Generation & Customer Portal
# -------------------------------------------------------------------------

@login_required
def quote_proposal_board(request):
    """Board displaying ready-to-present quotes and proposal document tracking."""
    tenant = request.tenant
    quotes = CPQQuote.objects.filter(
        tenant=tenant,
        status__in=["approved", "presented", "accepted"]
    ).select_related("opportunity", "account", "owner", "currency").order_by("-updated_at")

    stats = {
        "presented": CPQQuote.objects.filter(tenant=tenant, status="presented").count(),
        "accepted": CPQQuote.objects.filter(tenant=tenant, status="accepted").count(),
        "signed": CPQQuote.objects.filter(tenant=tenant, signed_at__isnull=False).count(),
    }

    return render(request, "sales/quote_proposal_cpq/operations/proposal_board.html", {
        "quotes": quotes,
        "stats": stats,
    })


@login_required
def quote_generate_proposal(request, pk):
    """Render customer-facing proposal HTML snapshot and display preview."""
    tenant = request.tenant
    quote = get_object_or_404(
        CPQQuote.objects.select_related("opportunity", "account", "contact", "currency", "owner"),
        pk=pk,
        tenant=tenant
    )

    proposal_html = cpq_render_proposal_html(quote)
    if quote.status == "approved":
        quote.status = "presented"
        quote.save(update_fields=["status", "updated_at"])

    return render(request, "sales/quote_proposal_cpq/operations/proposal_preview.html", {
        "quote": quote,
        "proposal_html": proposal_html,
    })


def quote_portal_view(request, token):
    """Public customer-facing quote acceptance portal (accessed via secure token)."""
    quote = get_object_or_404(
        CPQQuote.objects.select_related("tenant", "currency", "account", "contact", "owner"),
        signing_token=token
    )
    
    # Recalculate to ensure accurate figures
    cpq_recalc_quote_totals(quote, save=True)

    lines = list(quote.lines.select_related("product").order_by("sequence", "id"))
    form = CPQPortalSignForm(initial={
        "signer_name": quote.contact.name if quote.contact else "",
        "signer_email": getattr(quote.contact, "email", ""),
    })

    return render(request, "sales/quote_proposal_cpq/operations/portal.html", {
        "quote": quote,
        "lines": lines,
        "form": form,
    })


@require_POST
def quote_portal_sign(request, token):
    """Public endpoint to record e-signature and accept quote."""
    quote = get_object_or_404(CPQQuote, signing_token=token)

    if quote.status in ["accepted", "converted"]:
        messages.info(request, "This proposal has already been digitally accepted.")
        return redirect("sales:quote_portal_view", token=token)

    form = CPQPortalSignForm(request.POST)
    if form.is_valid():
        quote.signer_name = form.cleaned_data["signer_name"]
        quote.signer_title = form.cleaned_data["signer_title"]
        quote.signer_email = form.cleaned_data["signer_email"]
        quote.signature_data = form.cleaned_data["signature_data"]
        quote.signed_at = timezone.now()
        quote.status = "accepted"
        quote.save(update_fields=["signer_name", "signer_title", "signer_email", "signature_data", "signed_at", "status", "updated_at"])

        # Re-render HTML with signature block
        cpq_render_proposal_html(quote)

        # Audit
        write_audit_log(None, quote, "portal_sign", {"action": "portal_sign", "signer_name": quote.signer_name}, tenant=quote.tenant)
        messages.success(request, "Thank you! The proposal has been digitally signed and accepted.")
        return redirect("sales:quote_portal_view", token=token)

    lines = list(quote.lines.select_related("product").order_by("sequence", "id"))
    return render(request, "sales/quote_proposal_cpq/operations/portal.html", {
        "quote": quote,
        "lines": lines,
        "form": form,
    })


@require_POST
def quote_portal_toggle_line(request, token, line_id):
    """Customer toggle for optional add-on components on the portal."""
    quote = get_object_or_404(CPQQuote, signing_token=token)
    line = get_object_or_404(CPQQuoteLine, id=line_id, quote=quote)

    if quote.status in ["accepted", "converted"]:
        messages.error(request, "Cannot modify options on a signed proposal.")
        return redirect("sales:quote_portal_view", token=token)

    if line.is_optional:
        line.is_selected = not line.is_selected
        line.save(update_fields=["is_selected", "updated_at"])
        cpq_recalc_quote_totals(quote, save=True)

    return redirect("sales:quote_portal_view", token=token)


# -------------------------------------------------------------------------
# 4. Quote-to-Order Conversion
# -------------------------------------------------------------------------

@login_required
def quote_conversion_board(request):
    """Conversion dashboard tracking quotes ready for ERP order creation and already-converted orders."""
    tenant = request.tenant
    
    ready_quotes = CPQQuote.objects.filter(
        tenant=tenant,
        status__in=["approved", "presented", "accepted"],
        converted_order__isnull=True
    ).select_related("opportunity", "account", "currency", "owner").order_by("-updated_at")

    converted_quotes = CPQQuote.objects.filter(
        tenant=tenant,
        status="converted"
    ).select_related("converted_order", "account", "currency", "owner").order_by("-updated_at")[:20]

    stats = {
        "ready_count": ready_quotes.count(),
        "converted_count": CPQQuote.objects.filter(tenant=tenant, status="converted").count(),
    }

    return render(request, "sales/quote_proposal_cpq/operations/conversion_board.html", {
        "ready_quotes": ready_quotes,
        "converted_quotes": converted_quotes,
        "stats": stats,
    })


@require_POST
@login_required
def quote_convert_to_order(request, pk):
    """Convert an accepted or approved quote into an SCM SalesOrder."""
    tenant = request.tenant
    quote = get_object_or_404(CPQQuote, pk=pk, tenant=tenant)

    try:
        order = cpq_convert_to_sales_order(quote, user=request.user)
        write_audit_log(request.user, quote, "convert_order", {"action": "convert_order", "sales_order": order.number}, tenant=tenant)
        messages.success(request, f"Quote {quote.number} successfully converted to Sales Order {order.number}!")
        return redirect("sales:cpq_quote_detail", pk=quote.pk)
    except Exception as exc:
        messages.error(request, f"Order conversion failed: {str(exc)}")
        return redirect("sales:cpq_quote_detail", pk=quote.pk)


# -------------------------------------------------------------------------
# 5. Guided Selling Wizard
# -------------------------------------------------------------------------

@login_required
def cpq_guided_selling(request):
    """Interactive guided selling questionnaire recommending product bundles and option packages."""
    tenant = request.tenant
    bundle_products = Product.objects.filter(tenant=tenant, bundle_options__isnull=False, is_active=True).distinct()
    opportunities = Opportunity.objects.filter(tenant=tenant).order_by("name")

    selected_bundle_id = request.GET.get("bundle") or request.POST.get("bundle")
    selected_bundle = None
    options = []

    if selected_bundle_id:
        selected_bundle = get_object_or_404(Product, pk=selected_bundle_id, tenant=tenant)
        options = list(ProductBundleOption.objects.filter(
            tenant=tenant,
            bundle_product=selected_bundle,
            is_active=True
        ).select_related("component_product", "component_item", "depends_on_product").order_by("option_group", "sort_order"))

    if request.method == "POST" and "apply_guided_bundle" in request.POST:
        quote_id = request.POST.get("quote_id")
        opp_id = request.POST.get("opportunity_id")

        if quote_id:
            quote = get_object_or_404(CPQQuote, pk=quote_id, tenant=tenant)
        else:
            # Create a new quote
            opp = Opportunity.objects.filter(pk=opp_id, tenant=tenant).first() if opp_id else None
            quote = CPQQuote.objects.create(
                tenant=tenant,
                name=f"{selected_bundle.name} Solution Package",
                opportunity=opp,
                account=opp.account if opp else None,
                currency=opp.currency if opp and opp.currency else None,
                status="draft",
                owner=request.user,
            )

        # 1. Add parent bundle header line
        bundle_parent_line = CPQQuoteLine.objects.create(
            tenant=tenant,
            quote=quote,
            parent_line=None,
            line_type="bundle_parent",
            product=selected_bundle,
            description=f"Package: {selected_bundle.name}",
            quantity=Decimal("1.00"),
            list_price=selected_bundle.list_price or Decimal("0.00"),
            unit_price=selected_bundle.list_price or Decimal("0.00"),
            sequence=10,
        )

        # 2. Add selected components
        seq = 20
        for opt in options:
            input_name = f"opt_{opt.id}"
            qty_name = f"qty_{opt.id}"
            
            # If required or checked
            if opt.is_required or input_name in request.POST:
                qty_val = request.POST.get(qty_name, str(opt.default_quantity))
                try:
                    qty = Decimal(qty_val)
                except Exception:
                    qty = opt.default_quantity

                unit_price = opt.unit_price_override or opt.component_product.list_price or Decimal("0.00")
                disc = opt.discount_pct_override or Decimal("0.00")

                CPQQuoteLine.objects.create(
                    tenant=tenant,
                    quote=quote,
                    parent_line=bundle_parent_line,
                    line_type="bundle_component",
                    product=opt.component_product,
                    item=opt.component_item,
                    description=f"{opt.option_group}: {opt.component_product.name}",
                    quantity=qty,
                    list_price=opt.component_product.list_price or Decimal("0.00"),
                    discount_pct=disc,
                    unit_price=unit_price,
                    sequence=seq,
                )
                seq += 10

        cpq_recalc_quote_totals(quote, save=True)
        messages.success(request, f"Bundle '{selected_bundle.name}' added to quote {quote.number}!")
        return redirect("sales:cpq_quote_detail", pk=quote.pk)

    return render(request, "sales/quote_proposal_cpq/operations/guided_selling.html", {
        "bundle_products": bundle_products,
        "selected_bundle": selected_bundle,
        "options": options,
        "opportunities": opportunities,
        "preselect_quote_id": request.GET.get("quote"),
    })
