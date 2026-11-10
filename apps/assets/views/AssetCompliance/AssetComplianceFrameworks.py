from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Avg, Count, ProtectedError, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.assets.forms.AssetCompliance.AssetComplianceFrameworks import AssetComplianceFrameworkForm
from apps.assets.models import AssetCategory
from apps.assets.models.AssetCompliance.AssetComplianceFrameworks import AssetComplianceFramework
from apps.assets.views._common import assets_object, assets_scope
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def asset_compliance_framework_list(request):
    qs = assets_scope(
        AssetComplianceFramework.objects.select_related(
            "regulatory_agency",
            "applicable_category",
        ).defer("description"),
        request,
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(name__icontains=q)
            | Q(code__icontains=q)
            | Q(regulatory_agency__name__icontains=q)
            | Q(applicable_category__name__icontains=q)
        )

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        qs = qs.filter(status=status_filter)

    type_filter = request.GET.get("framework_type", "").strip()
    if type_filter:
        qs = qs.filter(framework_type=type_filter)

    category_id = request.GET.get("category", "").strip()
    if category_id and category_id.isdigit():
        qs = qs.filter(applicable_category_id=int(category_id))

    # Aggregate KPI metrics over tenant-scoped records
    base_all = AssetComplianceFramework.objects.filter(tenant=request.tenant)
    total_frameworks = base_all.count()
    active_count = base_all.filter(status="active").count()
    avg_readiness = base_all.aggregate(avg=Avg("readiness_score"))["avg"]
    avg_readiness_score = round(avg_readiness or 100)

    category_list = AssetCategory.objects.filter(tenant=request.tenant).order_by("name")

    paginator = Paginator(qs, 25)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "assets/assetcompliance/asset_compliance_framework/list.html",
        {
            "frameworks": page_obj,
            "page_obj": page_obj,
            "paginator": paginator,
            "is_paginated": page_obj.has_other_pages(),
            "status_choices": AssetComplianceFramework.STATUS_CHOICES,
            "type_choices": AssetComplianceFramework.FRAMEWORK_TYPE_CHOICES,
            "category_list": category_list,
            "total_frameworks": total_frameworks,
            "active_count": active_count,
            "avg_readiness_score": avg_readiness_score,
        },
    )


@login_required
def asset_compliance_framework_detail(request, pk):
    framework = assets_object(
        request,
        AssetComplianceFramework,
        pk,
        select_related=["regulatory_agency", "applicable_category"],
    )
    audits = framework.audits.select_related("asset", "lead_auditor_user").order_by("-audit_date")[:10]
    return render(
        request,
        "assets/assetcompliance/asset_compliance_framework/detail.html",
        {
            "framework": framework,
            "audits": audits,
        },
    )


@login_required
def asset_compliance_framework_create(request):
    if request.method == "POST":
        form = AssetComplianceFrameworkForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            framework = form.save(commit=False)
            framework.tenant = request.tenant
            framework.save()
            write_audit_log(
                request.user,
                framework,
                "create",
                changes={"details": f"Registered compliance framework {framework.number} ({framework.code})"},
                tenant=request.tenant,
            )
            messages.success(request, f"Compliance framework {framework.number} registered successfully.")
            return redirect("assets:asset_compliance_framework_detail", pk=framework.pk)
    else:
        form = AssetComplianceFrameworkForm(tenant=request.tenant)

    return render(
        request,
        "assets/assetcompliance/asset_compliance_framework/form.html",
        {
            "form": form,
            "framework": None,
            "is_edit": False,
        },
    )


@login_required
def asset_compliance_framework_edit(request, pk):
    framework = assets_object(request, AssetComplianceFramework, pk)
    if request.method == "POST":
        form = AssetComplianceFrameworkForm(request.POST, instance=framework, tenant=request.tenant)
        if form.is_valid():
            framework = form.save()
            write_audit_log(
                request.user,
                framework,
                "update",
                changes={"details": f"Updated compliance framework {framework.number} ({framework.code})"},
                tenant=request.tenant,
            )
            messages.success(request, f"Compliance framework {framework.number} updated successfully.")
            return redirect("assets:asset_compliance_framework_detail", pk=framework.pk)
    else:
        form = AssetComplianceFrameworkForm(instance=framework, tenant=request.tenant)

    return render(
        request,
        "assets/assetcompliance/asset_compliance_framework/form.html",
        {
            "form": form,
            "framework": framework,
            "is_edit": True,
        },
    )


@login_required
@require_POST
@tenant_admin_required
def asset_compliance_framework_delete(request, pk):
    framework = assets_object(request, AssetComplianceFramework, pk)
    num = framework.number
    code = framework.code
    try:
        with transaction.atomic():
            write_audit_log(
                request.user,
                framework,
                "delete",
                changes={"details": f"Deleted compliance framework {num} ({code})"},
                tenant=request.tenant,
            )
            framework.delete()
    except ProtectedError:
        messages.error(
            request,
            f"Cannot delete compliance framework {code} because related audit records exist. Reassign or delete related audits first.",
        )
        return redirect("assets:asset_compliance_framework_detail", pk=pk)
    messages.success(request, f"Compliance framework {num} ({code}) was deleted.")
    return redirect("assets:asset_compliance_framework_list")
