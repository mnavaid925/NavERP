from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.ecommerce.forms.CustomerSupport.OrderIssueClaims import OrderIssueClaimForm
from apps.ecommerce.models.CustomerSupport.OrderIssueClaims import OrderIssueClaim
from apps.ecommerce.views._common import ecommerce_object


@login_required
def orderissueclaim_list(request):
    qs = OrderIssueClaim.objects.filter(tenant=request.tenant).select_related(
        "order", "customer", "ticket", "reviewed_by"
    )

    query = request.GET.get("q", "").strip()
    if query:
        qs = qs.filter(
            Q(number__icontains=query)
            | Q(order__number__icontains=query)
            | Q(carrier_tracking_number__icontains=query)
            | Q(customer_notes__icontains=query)
        )

    selected_claim_type = request.GET.get("claim_type", "").strip()
    if selected_claim_type:
        qs = qs.filter(claim_type=selected_claim_type)

    selected_status = request.GET.get("status", "").strip()
    if selected_status:
        qs = qs.filter(status=selected_status)

    selected_resolution = request.GET.get("resolution", "").strip()
    if selected_resolution:
        qs = qs.filter(resolution_action=selected_resolution)

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "claims": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "claim_type_choices": OrderIssueClaim.CLAIM_TYPE_CHOICES,
        "status_choices": OrderIssueClaim.STATUS_CHOICES,
        "resolution_choices": OrderIssueClaim.RESOLUTION_CHOICES,
        "selected_claim_type": selected_claim_type,
        "selected_status": selected_status,
        "selected_resolution": selected_resolution,
        "query": query,
    }
    return render(request, "ecommerce/customer_support/claim/list.html", context)


@login_required
def orderissueclaim_detail(request, pk):
    claim = ecommerce_object(
        request,
        OrderIssueClaim,
        pk,
        select_related=("order", "customer", "ticket", "reviewed_by"),
    )
    return render(request, "ecommerce/customer_support/claim/detail.html", {"claim": claim})


@login_required
def orderissueclaim_create(request):
    if request.method == "POST":
        form = OrderIssueClaimForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            claim = form.save(commit=False)
            claim.tenant = request.tenant
            claim.save()
            write_audit_log(
                request.user,
                claim,
                "create",
                {"number": claim.number, "order": claim.order.number, "claim_type": claim.claim_type},
                tenant=request.tenant,
            )
            messages.success(request, f"Claim {claim.number} submitted successfully.")
            return redirect("ecommerce:orderissueclaim_detail", pk=claim.pk)
    else:
        form = OrderIssueClaimForm(tenant=request.tenant)

    return render(
        request,
        "ecommerce/customer_support/claim/form.html",
        {"form": form, "claim": None},
    )


@login_required
def orderissueclaim_edit(request, pk):
    claim = ecommerce_object(request, OrderIssueClaim, pk)
    if request.method == "POST":
        form = OrderIssueClaimForm(request.POST, instance=claim, tenant=request.tenant)
        if form.is_valid():
            claim = form.save()
            write_audit_log(
                request.user,
                claim,
                "update",
                {"status": claim.status, "resolution_action": claim.resolution_action},
                tenant=request.tenant,
            )
            messages.success(request, f"Claim {claim.number} updated successfully.")
            return redirect("ecommerce:orderissueclaim_detail", pk=claim.pk)
    else:
        form = OrderIssueClaimForm(instance=claim, tenant=request.tenant)

    return render(
        request,
        "ecommerce/customer_support/claim/form.html",
        {"form": form, "claim": claim},
    )


@login_required
@tenant_admin_required
@require_POST
def orderissueclaim_delete(request, pk):
    claim = ecommerce_object(request, OrderIssueClaim, pk)
    number = claim.number
    claim.delete()
    write_audit_log(
        request.user,
        claim,
        "delete",
        {"number": number},
        tenant=request.tenant,
    )
    messages.success(request, f"Claim {number} deleted.")
    return redirect("ecommerce:orderissueclaim_list")
