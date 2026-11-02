from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.utils import write_audit_log
from apps.ecommerce.forms.FraudRisk.TransactionRiskAssessments import TransactionRiskAssessmentForm
from apps.ecommerce.models.FraudRisk.TransactionRiskAssessments import TransactionRiskAssessment
from apps.ecommerce.views._common import ecommerce_object, ecommerce_scope


@login_required
def transaction_risk_assessment_list(request):
    qs = ecommerce_scope(
        TransactionRiskAssessment.objects.select_related("order", "customer_party", "currency", "user", "analyst_user"),
        request,
    )

    search_query = request.GET.get("q", "").strip()
    if search_query:
        qs = qs.filter(
            Q(number__icontains=search_query)
            | Q(order__number__icontains=search_query)
            | Q(ip_address__icontains=search_query)
            | Q(device_fingerprint__icontains=search_query)
            | Q(customer_party__name__icontains=search_query)
            | Q(risk_factors_summary__icontains=search_query)
        )

    tier_filter = request.GET.get("tier", "").strip()
    if tier_filter:
        qs = qs.filter(risk_tier=tier_filter)

    action_filter = request.GET.get("action", "").strip()
    if action_filter:
        qs = qs.filter(recommended_action=action_filter)

    decision_filter = request.GET.get("decision", "").strip()
    if decision_filter:
        qs = qs.filter(actual_decision=decision_filter)

    total_count = qs.count()

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "assessments": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "total_count": total_count,
        "search_query": search_query,
        "tier_filter": tier_filter,
        "action_filter": action_filter,
        "decision_filter": decision_filter,
        "tier_choices": TransactionRiskAssessment.RISK_TIER_CHOICES,
        "action_choices": TransactionRiskAssessment.RECOMMENDED_ACTION_CHOICES,
        "decision_choices": TransactionRiskAssessment.ACTUAL_DECISION_CHOICES,
    }
    return render(request, "ecommerce/fraud_risk/transaction_risk_assessment/list.html", context)


@login_required
def transaction_risk_assessment_create(request):
    if request.method == "POST":
        form = TransactionRiskAssessmentForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            assessment = form.save(commit=False)
            assessment.tenant = request.tenant
            if assessment.actual_decision in ["approved_manual", "declined_manual"]:
                assessment.analyst_user = request.user
                assessment.reviewed_at = timezone.now()
            assessment.save()
            write_audit_log(
                tenant=request.tenant,
                user=request.user,
                action="create",
                model_name="TransactionRiskAssessment",
                object_id=assessment.pk,
                changes={"risk_score": assessment.risk_score, "actual_decision": assessment.actual_decision},
            )
            messages.success(request, f"Transaction risk assessment {assessment.number} recorded.")
            return redirect("ecommerce:transaction_risk_assessment_detail", pk=assessment.pk)
    else:
        form = TransactionRiskAssessmentForm(tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": False,
    }
    return render(request, "ecommerce/fraud_risk/transaction_risk_assessment/form.html", context)


@login_required
def transaction_risk_assessment_detail(request, pk):
    assessment = ecommerce_object(
        request,
        TransactionRiskAssessment,
        pk,
        select_related=("order", "customer_party", "currency", "user", "analyst_user"),
    )
    context = {
        "assessment": assessment,
    }
    return render(request, "ecommerce/fraud_risk/transaction_risk_assessment/detail.html", context)


@login_required
def transaction_risk_assessment_edit(request, pk):
    assessment = ecommerce_object(request, TransactionRiskAssessment, pk)
    if request.method == "POST":
        form = TransactionRiskAssessmentForm(request.POST, instance=assessment, tenant=request.tenant)
        if form.is_valid():
            assessment = form.save(commit=False)
            if assessment.actual_decision in ["approved_manual", "declined_manual"] and not assessment.reviewed_at:
                assessment.analyst_user = request.user
                assessment.reviewed_at = timezone.now()
            assessment.save()
            write_audit_log(
                tenant=request.tenant,
                user=request.user,
                action="update",
                model_name="TransactionRiskAssessment",
                object_id=assessment.pk,
                changes={"actual_decision": assessment.actual_decision, "risk_score": assessment.risk_score},
            )
            messages.success(request, f"Transaction risk assessment {assessment.number} updated.")
            return redirect("ecommerce:transaction_risk_assessment_detail", pk=assessment.pk)
    else:
        form = TransactionRiskAssessmentForm(instance=assessment, tenant=request.tenant)

    context = {
        "form": form,
        "assessment": assessment,
        "is_edit": True,
    }
    return render(request, "ecommerce/fraud_risk/transaction_risk_assessment/form.html", context)


@login_required
@require_POST
def transaction_risk_assessment_delete(request, pk):
    assessment = ecommerce_object(request, TransactionRiskAssessment, pk)
    number = assessment.number
    assessment.delete()
    write_audit_log(
        tenant=request.tenant,
        user=request.user,
        action="delete",
        model_name="TransactionRiskAssessment",
        object_id=pk,
        changes={"number": number},
    )
    messages.success(request, f"Transaction risk assessment {number} deleted.")
    return redirect("ecommerce:transaction_risk_assessment_list")
