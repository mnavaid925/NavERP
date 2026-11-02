from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.utils import write_audit_log
from apps.ecommerce.forms.FraudRisk.ChargebackDisputes import ChargebackDisputeForm
from apps.ecommerce.models.FraudRisk.ChargebackDisputes import ChargebackDispute
from apps.ecommerce.views._common import ecommerce_object, ecommerce_scope


@login_required
def chargeback_dispute_list(request):
    qs = ecommerce_scope(
        ChargebackDispute.objects.select_related("order", "customer_party", "currency"),
        request,
    )

    search_query = request.GET.get("q", "").strip()
    if search_query:
        qs = qs.filter(
            Q(number__icontains=search_query)
            | Q(gateway_dispute_id__icontains=search_query)
            | Q(order__number__icontains=search_query)
            | Q(reason_code__icontains=search_query)
            | Q(customer_party__legal_name__icontains=search_query)
            | Q(evidence_summary__icontains=search_query)
        )

    stage_filter = request.GET.get("stage", "").strip()
    if stage_filter:
        qs = qs.filter(stage=stage_filter)

    reason_filter = request.GET.get("reason", "").strip()
    if reason_filter:
        qs = qs.filter(reason_category=reason_filter)

    total_count = qs.count()

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "disputes": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "total_count": total_count,
        "search_query": search_query,
        "stage_filter": stage_filter,
        "reason_filter": reason_filter,
        "stage_choices": ChargebackDispute.STAGE_CHOICES,
        "reason_choices": ChargebackDispute.REASON_CATEGORY_CHOICES,
    }
    return render(request, "ecommerce/fraud_risk/chargeback_dispute/list.html", context)


@login_required
def chargeback_dispute_create(request):
    if request.method == "POST":
        form = ChargebackDisputeForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            dispute = form.save(commit=False)
            dispute.tenant = request.tenant
            if dispute.stage == "representment_submitted" and not dispute.representment_submitted_at:
                dispute.representment_submitted_at = timezone.now()
            elif dispute.stage in ["won", "lost", "accepted"] and not dispute.resolved_at:
                dispute.resolved_at = timezone.now()
            dispute.save()
            write_audit_log(
                tenant=request.tenant,
                user=request.user,
                action="create",
                model_name="ChargebackDispute",
                object_id=dispute.pk,
                changes={"dispute_amount": str(dispute.dispute_amount), "stage": dispute.stage, "order": dispute.order.number},
            )
            messages.success(request, f"Chargeback dispute case {dispute.number} registered.")
            return redirect("ecommerce:chargeback_dispute_detail", pk=dispute.pk)
    else:
        form = ChargebackDisputeForm(tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": False,
    }
    return render(request, "ecommerce/fraud_risk/chargeback_dispute/form.html", context)


@login_required
def chargeback_dispute_detail(request, pk):
    dispute = ecommerce_object(
        request,
        ChargebackDispute,
        pk,
        select_related=("order", "customer_party", "currency"),
    )
    context = {
        "dispute": dispute,
    }
    return render(request, "ecommerce/fraud_risk/chargeback_dispute/detail.html", context)


@login_required
def chargeback_dispute_edit(request, pk):
    dispute = ecommerce_object(request, ChargebackDispute, pk)
    if request.method == "POST":
        form = ChargebackDisputeForm(request.POST, instance=dispute, tenant=request.tenant)
        if form.is_valid():
            dispute = form.save(commit=False)
            if dispute.stage == "representment_submitted" and not dispute.representment_submitted_at:
                dispute.representment_submitted_at = timezone.now()
            elif dispute.stage in ["won", "lost", "accepted"] and not dispute.resolved_at:
                dispute.resolved_at = timezone.now()
            dispute.save()
            write_audit_log(
                tenant=request.tenant,
                user=request.user,
                action="update",
                model_name="ChargebackDispute",
                object_id=dispute.pk,
                changes={"stage": dispute.stage, "reason_category": dispute.reason_category},
            )
            messages.success(request, f"Chargeback dispute case {dispute.number} updated.")
            return redirect("ecommerce:chargeback_dispute_detail", pk=dispute.pk)
    else:
        form = ChargebackDisputeForm(instance=dispute, tenant=request.tenant)

    context = {
        "form": form,
        "dispute": dispute,
        "is_edit": True,
    }
    return render(request, "ecommerce/fraud_risk/chargeback_dispute/form.html", context)


@login_required
@require_POST
def chargeback_dispute_delete(request, pk):
    dispute = ecommerce_object(request, ChargebackDispute, pk)
    number = dispute.number
    dispute.delete()
    write_audit_log(
        tenant=request.tenant,
        user=request.user,
        action="delete",
        model_name="ChargebackDispute",
        object_id=pk,
        changes={"number": number},
    )
    messages.success(request, f"Chargeback dispute case {number} deleted.")
    return redirect("ecommerce:chargeback_dispute_list")
