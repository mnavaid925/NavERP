from decimal import Decimal
import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.bi.forms.MasterData.MdmSurvivorshipRuleForms import MdmSurvivorshipRuleForm
from apps.bi.models.MasterData.MdmSurvivorshipRules import MdmSurvivorshipRule
from apps.bi.views._common import bi_object, bi_scope
from apps.core.utils import write_audit_log


@login_required
def mdm_survivorship_rule_list(request):
    queryset = bi_scope(MdmSurvivorshipRule.objects.all(), request).select_related("steward")

    q = request.GET.get("q", "").strip()[:100]
    if q:
        queryset = queryset.filter(
            Q(name__icontains=q)
            | Q(code__icontains=q)
            | Q(number__icontains=q)
            | Q(target_field__icontains=q)
            | Q(description__icontains=q)
        )

    domain_filter = request.GET.get("domain", "").strip()
    if domain_filter:
        queryset = queryset.filter(domain=domain_filter)

    strategy_filter = request.GET.get("survivorship_strategy", "").strip()
    if strategy_filter:
        queryset = queryset.filter(survivorship_strategy=strategy_filter)

    match_filter = request.GET.get("match_algorithm", "").strip()
    if match_filter:
        queryset = queryset.filter(match_algorithm=match_filter)

    all_tenant_rules = bi_scope(MdmSurvivorshipRule.objects.all(), request)
    counts = all_tenant_rules.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(is_active=True)),
    )
    total_count = counts["total"]
    active_count = counts["active"]

    paginator = Paginator(queryset.order_by("priority_order", "name"), 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "rules": page_obj,
        "domain_choices": MdmSurvivorshipRule.DOMAIN_CHOICES,
        "strategy_choices": MdmSurvivorshipRule.SURVIVORSHIP_STRATEGY_CHOICES,
        "match_choices": MdmSurvivorshipRule.MATCH_ALGORITHM_CHOICES,
        "total_count": total_count,
        "active_count": active_count,
    }
    return render(request, "bi/master_data/survivorship_rule/list.html", context)


@login_required
def mdm_survivorship_rule_detail(request, pk):
    rule = bi_object(request, MdmSurvivorshipRule, pk, select_related=("steward",))
    source_priority_list = rule.source_priority_list_json
    if isinstance(source_priority_list, str):
        try:
            source_priority_list = json.loads(source_priority_list)
        except Exception:
            source_priority_list = []

    context = {
        "rule": rule,
        "source_priority_list": source_priority_list,
    }
    return render(request, "bi/master_data/survivorship_rule/detail.html", context)


@login_required
def mdm_survivorship_rule_create(request):
    if request.method == "POST":
        form = MdmSurvivorshipRuleForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            rule = form.save(commit=False)
            rule.tenant = request.tenant
            rule.save()
            write_audit_log(
                request.user,
                rule,
                "create",
                changes=f"Created survivorship rule {rule.number} ({rule.name})",
                tenant=request.tenant,
            )
            messages.success(request, f"Survivorship rule '{rule.name}' created successfully.")
            return redirect("bi:mdm_survivorship_rule_detail", pk=rule.pk)
    else:
        form = MdmSurvivorshipRuleForm(tenant=request.tenant)

    context = {
        "form": form,
        "rule": None,
        "is_edit": False,
    }
    return render(request, "bi/master_data/survivorship_rule/form.html", context)


@login_required
def mdm_survivorship_rule_edit(request, pk):
    rule = bi_object(request, MdmSurvivorshipRule, pk)

    if request.method == "POST":
        form = MdmSurvivorshipRuleForm(request.POST, instance=rule, tenant=request.tenant)
        if form.is_valid():
            saved_rule = form.save()
            write_audit_log(
                request.user,
                saved_rule,
                "update",
                changes=f"Updated survivorship rule {saved_rule.number}",
                tenant=request.tenant,
            )
            messages.success(request, f"Survivorship rule '{saved_rule.name}' updated successfully.")
            return redirect("bi:mdm_survivorship_rule_detail", pk=saved_rule.pk)
    else:
        form = MdmSurvivorshipRuleForm(instance=rule, tenant=request.tenant)

    context = {
        "form": form,
        "rule": rule,
        "is_edit": True,
    }
    return render(request, "bi/master_data/survivorship_rule/form.html", context)


@login_required
@require_POST
def mdm_survivorship_rule_delete(request, pk):
    rule = bi_object(request, MdmSurvivorshipRule, pk)
    rule_number = rule.number
    rule_name = rule.name

    write_audit_log(
        request.user,
        rule,
        "delete",
        changes=f"Deleted survivorship rule {rule_number} ({rule_name})",
        tenant=request.tenant,
    )
    rule.delete()
    messages.success(request, f"Survivorship rule {rule_number} deleted successfully.")
    return redirect("bi:mdm_survivorship_rule_list")
