from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.bi.forms.DataCatalog.DataGovernancePolicies import DataGovernancePolicyForm
from apps.bi.models.DataCatalog.DataGovernancePolicies import DataGovernancePolicy
from apps.bi.views._common import bi_object, bi_scope
from apps.core.utils import write_audit_log


@login_required
def data_governance_policy_list(request):
    queryset = (
        bi_scope(DataGovernancePolicy.objects.all(), request)
        .select_related("policy_owner")
    )

    q = request.GET.get("q", "").strip()[:100]
    if q:
        queryset = queryset.filter(
            Q(name__icontains=q)
            | Q(code__icontains=q)
            | Q(number__icontains=q)
            | Q(compliance_notes__icontains=q)
            | Q(description__icontains=q)
        )

    policy_type_filter = request.GET.get("policy_type", "").strip()
    if policy_type_filter:
        queryset = queryset.filter(policy_type=policy_type_filter)

    framework_filter = request.GET.get("framework", "").strip()
    if framework_filter:
        queryset = queryset.filter(regulatory_framework=framework_filter)

    enforcement_filter = request.GET.get("enforcement", "").strip()
    if enforcement_filter:
        queryset = queryset.filter(enforcement_level=enforcement_filter)

    all_tenant_policies = bi_scope(DataGovernancePolicy.objects.all(), request)
    counts = all_tenant_policies.aggregate(
        total=Count("id"),
        strict=Count("id", filter=Q(enforcement_level="strict_blocking")),
        active=Count("id", filter=Q(is_active=True)),
    )
    total_count = counts["total"] or 0
    strict_count = counts["strict"] or 0
    active_count = counts["active"] or 0

    paginator = Paginator(queryset.order_by("-created_at"), 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "policies": page_obj,
        "policy_type_choices": DataGovernancePolicy.POLICY_TYPE_CHOICES,
        "framework_choices": DataGovernancePolicy.REGULATORY_FRAMEWORK_CHOICES,
        "enforcement_choices": DataGovernancePolicy.ENFORCEMENT_LEVEL_CHOICES,
        "total_count": total_count,
        "strict_count": strict_count,
        "active_count": active_count,
    }
    return render(request, "bi/data_catalog/data_governance_policy/list.html", context)


@login_required
def data_governance_policy_detail(request, pk):
    policy = bi_object(
        request,
        DataGovernancePolicy,
        pk,
        select_related=("policy_owner",),
    )
    context = {
        "policy": policy,
    }
    return render(request, "bi/data_catalog/data_governance_policy/detail.html", context)


@login_required
def data_governance_policy_create(request):
    if request.method == "POST":
        form = DataGovernancePolicyForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            policy = form.save(commit=False)
            policy.tenant = request.tenant
            policy.save()
            write_audit_log(
                request.user,
                "create",
                policy,
                f"Created governance policy {policy.number} ({policy.name})",
                tenant=request.tenant,
            )
            messages.success(request, f"Governance policy {policy.number} registered successfully.")
            return redirect("bi:data_governance_policy_detail", pk=policy.pk)
    else:
        form = DataGovernancePolicyForm(tenant=request.tenant)

    context = {
        "form": form,
        "policy": None,
        "is_edit": False,
    }
    return render(request, "bi/data_catalog/data_governance_policy/form.html", context)


@login_required
def data_governance_policy_edit(request, pk):
    policy = bi_object(request, DataGovernancePolicy, pk)
    if request.method == "POST":
        form = DataGovernancePolicyForm(request.POST, instance=policy, tenant=request.tenant)
        if form.is_valid():
            policy = form.save()
            write_audit_log(
                request.user,
                "update",
                policy,
                f"Updated governance policy {policy.number} ({policy.name})",
                tenant=request.tenant,
            )
            messages.success(request, f"Governance policy {policy.number} updated successfully.")
            return redirect("bi:data_governance_policy_detail", pk=policy.pk)
    else:
        form = DataGovernancePolicyForm(instance=policy, tenant=request.tenant)

    context = {
        "form": form,
        "policy": policy,
        "is_edit": True,
    }
    return render(request, "bi/data_catalog/data_governance_policy/form.html", context)


@login_required
@require_POST
def data_governance_policy_delete(request, pk):
    policy = bi_object(request, DataGovernancePolicy, pk)
    policy_number = policy.number
    policy.delete()
    write_audit_log(
        request.user,
        "delete",
        policy,
        f"Deleted governance policy {policy_number}",
        tenant=request.tenant,
    )
    messages.success(request, f"Governance policy {policy_number} was deleted.")
    return redirect("bi:data_governance_policy_list")
