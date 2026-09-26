"""Views for QuoteApprovalRule management."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.sales.forms.QuoteProposalCPQ.QuoteApprovalRules import QuoteApprovalRuleForm
from apps.sales.models.QuoteProposalCPQ.QuoteApprovalRules import QuoteApprovalRule


@login_required
def quote_approval_rule_list(request):
    """List and filter CPQ pricing approval rules."""
    tenant = request.tenant
    qs = QuoteApprovalRule.objects.filter(tenant=tenant)

    # Search
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q) |
            Q(number__icontains=q) |
            Q(description__icontains=q)
        )

    # Filters
    rule_type = request.GET.get("rule_type", "").strip()
    if rule_type:
        qs = qs.filter(rule_type=rule_type)

    approver_role = request.GET.get("approver_role", "").strip()
    if approver_role:
        qs = qs.filter(approver_role=approver_role)

    is_active = request.GET.get("is_active", "").strip()
    if is_active in ["true", "1"]:
        qs = qs.filter(is_active=True)
    elif is_active in ["false", "0"]:
        qs = qs.filter(is_active=False)

    stats = {
        "total": QuoteApprovalRule.objects.filter(tenant=tenant).count(),
        "active": QuoteApprovalRule.objects.filter(tenant=tenant, is_active=True).count(),
        "max_discount": QuoteApprovalRule.objects.filter(tenant=tenant, rule_type="max_discount").count(),
        "min_margin": QuoteApprovalRule.objects.filter(tenant=tenant, rule_type="min_margin").count(),
    }

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "rules": page_obj,
        "rule_type_choices": QuoteApprovalRule.RULE_TYPE_CHOICES,
        "approver_role_choices": QuoteApprovalRule.APPROVER_ROLE_CHOICES,
        "stats": stats,
    }
    return render(request, "sales/quote_proposal_cpq/quoteapprovalrule/list.html", context)


@login_required
@tenant_admin_required
def quote_approval_rule_create(request):
    """Create a new QuoteApprovalRule."""
    if request.method == "POST":
        form = QuoteApprovalRuleForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            rule = form.save(commit=False)
            rule.tenant = request.tenant
            rule.save()
            write_audit_log(request.user, "create", "QuoteApprovalRule", rule.id, f"Created rule {rule.number} ({rule.name})")
            messages.success(request, f"Approval rule {rule.name} created successfully.")
            return redirect("sales:quote_approval_rule_detail", pk=rule.pk)
    else:
        form = QuoteApprovalRuleForm(tenant=request.tenant)

    return render(request, "sales/quote_proposal_cpq/quoteapprovalrule/form.html", {
        "form": form,
        "is_create": True,
    })


@login_required
def quote_approval_rule_detail(request, pk):
    """View details of a QuoteApprovalRule."""
    rule = get_object_or_404(QuoteApprovalRule, pk=pk, tenant=request.tenant)
    recent_quotes = rule.quotes.filter(tenant=request.tenant).order_by("-created_at")[:10]
    return render(request, "sales/quote_proposal_cpq/quoteapprovalrule/detail.html", {
        "rule": rule,
        "recent_quotes": recent_quotes,
    })


@login_required
@tenant_admin_required
def quote_approval_rule_edit(request, pk):
    """Edit an existing QuoteApprovalRule."""
    rule = get_object_or_404(QuoteApprovalRule, pk=pk, tenant=request.tenant)
    if request.method == "POST":
        form = QuoteApprovalRuleForm(request.POST, instance=rule, tenant=request.tenant)
        if form.is_valid():
            rule = form.save()
            write_audit_log(request.user, "update", "QuoteApprovalRule", rule.id, f"Updated rule {rule.number}")
            messages.success(request, f"Approval rule {rule.name} updated successfully.")
            return redirect("sales:quote_approval_rule_detail", pk=rule.pk)
    else:
        form = QuoteApprovalRuleForm(instance=rule, tenant=request.tenant)

    return render(request, "sales/quote_proposal_cpq/quoteapprovalrule/form.html", {
        "form": form,
        "rule": rule,
        "is_create": False,
    })


@require_POST
@login_required
@tenant_admin_required
def quote_approval_rule_delete(request, pk):
    """Delete a QuoteApprovalRule."""
    rule = get_object_or_404(QuoteApprovalRule, pk=pk, tenant=request.tenant)
    name = rule.name
    rule_id = rule.id
    rule.delete()
    write_audit_log(request.user, "delete", "QuoteApprovalRule", rule_id, f"Deleted rule {name}")
    messages.success(request, f"Approval rule {name} deleted successfully.")
    return redirect("sales:quote_approval_rule_list")
