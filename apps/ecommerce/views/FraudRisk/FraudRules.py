from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.core.utils import write_audit_log
from apps.ecommerce.forms.FraudRisk.FraudRules import FraudRuleForm
from apps.ecommerce.models.FraudRisk.FraudRules import FraudRule
from apps.ecommerce.models.FraudRisk.TransactionRiskAssessments import TransactionRiskAssessment
from apps.ecommerce.models.FraudRisk.ChargebackDisputes import ChargebackDispute
from apps.ecommerce.models.FraudRisk.AccountSecurityAlerts import AccountSecurityAlert
from apps.ecommerce.views._common import ecommerce_object, ecommerce_scope


@login_required
def fraud_risk_hub(request):
    rules_qs = ecommerce_scope(FraudRule.objects.all(), request)
    assessments_qs = ecommerce_scope(TransactionRiskAssessment.objects.all(), request)
    disputes_qs = ecommerce_scope(ChargebackDispute.objects.all(), request)
    alerts_qs = ecommerce_scope(AccountSecurityAlert.objects.all(), request)

    rules_stats = rules_qs.aggregate(
        total_rules=Count("id"),
        active_rules=Count("id", filter=Q(is_active=True)),
    )
    total_rules = rules_stats["total_rules"]
    active_rules = rules_stats["active_rules"]

    assessments_stats = assessments_qs.aggregate(
        total_assessments=Count("id"),
        high_risk_assessments=Count("id", filter=Q(risk_tier__in=["high", "critical"])),
        pending_reviews=Count("id", filter=Q(actual_decision="pending")),
    )
    total_assessments = assessments_stats["total_assessments"]
    high_risk_assessments = assessments_stats["high_risk_assessments"]
    pending_reviews = assessments_stats["pending_reviews"]

    disputes_stats = disputes_qs.aggregate(
        total_disputes=Count("id"),
        open_disputes=Count("id", filter=Q(stage__in=["inquiry", "needs_response", "under_review"])),
        dispute_amount_total=Sum("dispute_amount"),
    )
    total_disputes = disputes_stats["total_disputes"]
    open_disputes = disputes_stats["open_disputes"]
    dispute_amount_total = disputes_stats["dispute_amount_total"] or 0

    alerts_stats = alerts_qs.aggregate(
        total_alerts=Count("id"),
        open_alerts=Count("id", filter=Q(status__in=["new", "investigating"])),
        critical_alerts=Count("id", filter=Q(severity="critical", status__in=["new", "investigating"])),
    )
    total_alerts = alerts_stats["total_alerts"]
    open_alerts = alerts_stats["open_alerts"]
    critical_alerts = alerts_stats["critical_alerts"]

    recent_assessments = assessments_qs.select_related("order", "currency")[:5]
    recent_disputes = disputes_qs.select_related("order", "currency")[:5]
    recent_alerts = alerts_qs.select_related("user", "party")[:5]

    context = {
        "total_rules": total_rules,
        "active_rules": active_rules,
        "total_assessments": total_assessments,
        "high_risk_assessments": high_risk_assessments,
        "pending_reviews": pending_reviews,
        "total_disputes": total_disputes,
        "open_disputes": open_disputes,
        "dispute_amount_total": dispute_amount_total,
        "total_alerts": total_alerts,
        "open_alerts": open_alerts,
        "critical_alerts": critical_alerts,
        "recent_assessments": recent_assessments,
        "recent_disputes": recent_disputes,
        "recent_alerts": recent_alerts,
    }
    return render(request, "ecommerce/fraud_risk/fraud_risk_hub.html", context)


@login_required
def fraud_rule_list(request):
    qs = ecommerce_scope(FraudRule.objects.all(), request)

    search_query = request.GET.get("q", "").strip()
    if search_query:
        qs = qs.filter(
            Q(name__icontains=search_query)
            | Q(rule_code__icontains=search_query)
            | Q(number__icontains=search_query)
            | Q(threshold_value__icontains=search_query)
            | Q(description__icontains=search_query)
        )

    scope_filter = request.GET.get("scope", "").strip()
    if scope_filter:
        qs = qs.filter(rule_scope=scope_filter)

    type_filter = request.GET.get("type", "").strip()
    if type_filter:
        qs = qs.filter(rule_type=type_filter)

    action_filter = request.GET.get("action", "").strip()
    if action_filter:
        qs = qs.filter(action_to_take=action_filter)

    is_active_filter = request.GET.get("is_active", "").strip()
    if is_active_filter == "1":
        qs = qs.filter(is_active=True)
    elif is_active_filter == "0":
        qs = qs.filter(is_active=False)

    stats = qs.aggregate(
        total_count=Count("id"),
        active_count=Count("id", filter=Q(is_active=True)),
    )
    total_count = stats["total_count"]
    active_count = stats["active_count"]

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "rules": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "total_count": total_count,
        "active_count": active_count,
        "search_query": search_query,
        "scope_filter": scope_filter,
        "type_filter": type_filter,
        "action_filter": action_filter,
        "is_active_filter": is_active_filter,
        "scope_choices": FraudRule.RULE_SCOPE_CHOICES,
        "type_choices": FraudRule.RULE_TYPE_CHOICES,
        "action_choices": FraudRule.ACTION_CHOICES,
    }
    return render(request, "ecommerce/fraud_risk/fraud_rule/list.html", context)


@login_required
def fraud_rule_create(request):
    if request.method == "POST":
        form = FraudRuleForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            rule = form.save(commit=False)
            rule.tenant = request.tenant
            rule.save()
            write_audit_log(
                request.user,
                rule,
                "create",
                changes={"name": rule.name, "rule_scope": rule.rule_scope, "action_to_take": rule.action_to_take},
                tenant=request.tenant,
            )
            messages.success(request, f"Fraud detection rule '{rule.name}' created successfully.")
            return redirect("ecommerce:fraud_rule_detail", pk=rule.pk)
    else:
        form = FraudRuleForm(tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": False,
    }
    return render(request, "ecommerce/fraud_risk/fraud_rule/form.html", context)


@login_required
def fraud_rule_detail(request, pk):
    rule = ecommerce_object(request, FraudRule, pk)
    context = {
        "rule": rule,
    }
    return render(request, "ecommerce/fraud_risk/fraud_rule/detail.html", context)


@login_required
def fraud_rule_edit(request, pk):
    rule = ecommerce_object(request, FraudRule, pk)
    if request.method == "POST":
        form = FraudRuleForm(request.POST, instance=rule, tenant=request.tenant)
        if form.is_valid():
            rule = form.save()
            write_audit_log(
                request.user,
                rule,
                "update",
                changes={"name": rule.name, "is_active": rule.is_active, "action_to_take": rule.action_to_take},
                tenant=request.tenant,
            )
            messages.success(request, f"Fraud detection rule '{rule.name}' updated successfully.")
            return redirect("ecommerce:fraud_rule_detail", pk=rule.pk)
    else:
        form = FraudRuleForm(instance=rule, tenant=request.tenant)

    context = {
        "form": form,
        "rule": rule,
        "is_edit": True,
    }
    return render(request, "ecommerce/fraud_risk/fraud_rule/form.html", context)


@login_required
@require_POST
def fraud_rule_delete(request, pk):
    rule = ecommerce_object(request, FraudRule, pk)
    name = rule.name
    write_audit_log(
        request.user,
        rule,
        "delete",
        changes={"name": name},
        tenant=request.tenant,
    )
    rule.delete()
    messages.success(request, f"Fraud detection rule '{name}' deleted successfully.")
    return redirect("ecommerce:fraud_rule_list")
