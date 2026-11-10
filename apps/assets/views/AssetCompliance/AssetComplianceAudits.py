from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.assets.forms.AssetCompliance.AssetComplianceAudits import AssetComplianceAuditForm
from apps.assets.models.AssetCompliance.AssetComplianceAudits import AssetComplianceAudit
from apps.assets.models.AssetCompliance.AssetComplianceFrameworks import AssetComplianceFramework
from apps.assets.views._common import assets_object, assets_scope
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def asset_compliance_audit_list(request):
    qs = assets_scope(
        AssetComplianceAudit.objects.select_related(
            "framework",
            "asset",
            "lead_auditor_user",
            "auditor_party",
        ).defer("scope_description", "summary_findings"),
        request,
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(title__icontains=q)
            | Q(framework__name__icontains=q)
            | Q(framework__code__icontains=q)
            | Q(asset__name__icontains=q)
            | Q(asset__code__icontains=q)
        )

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        qs = qs.filter(status=status_filter)

    type_filter = request.GET.get("audit_type", "").strip()
    if type_filter:
        qs = qs.filter(audit_type=type_filter)

    rating_filter = request.GET.get("compliance_rating", "").strip()
    if rating_filter:
        qs = qs.filter(compliance_rating=rating_filter)

    framework_id = request.GET.get("framework", "").strip()
    if framework_id and framework_id.isdigit():
        qs = qs.filter(framework_id=int(framework_id))

    # Aggregate KPI counts
    base_all = AssetComplianceAudit.objects.filter(tenant=request.tenant)
    total_audits = base_all.count()
    in_progress_count = base_all.filter(status="in_progress").count()
    completed_count = base_all.filter(status="completed").count()
    breaches_count = base_all.filter(
        compliance_rating__in=["major_non_conformance", "critical_breach"]
    ).count()

    framework_list = AssetComplianceFramework.objects.filter(tenant=request.tenant).order_by("code")

    paginator = Paginator(qs, 25)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "assets/assetcompliance/asset_compliance_audit/list.html",
        {
            "audits": page_obj,
            "page_obj": page_obj,
            "paginator": paginator,
            "is_paginated": page_obj.has_other_pages(),
            "status_choices": AssetComplianceAudit.STATUS_CHOICES,
            "type_choices": AssetComplianceAudit.AUDIT_TYPE_CHOICES,
            "rating_choices": AssetComplianceAudit.COMPLIANCE_RATING_CHOICES,
            "framework_list": framework_list,
            "total_audits": total_audits,
            "in_progress_count": in_progress_count,
            "completed_count": completed_count,
            "breaches_count": breaches_count,
        },
    )


@login_required
def asset_compliance_audit_detail(request, pk):
    audit = assets_object(
        request,
        AssetComplianceAudit,
        pk,
        select_related=["framework", "asset", "lead_auditor_user", "auditor_party"],
    )
    incidents = audit.incidents.select_related("asset", "assigned_investigator").order_by("-incident_date")[:10]
    return render(
        request,
        "assets/assetcompliance/asset_compliance_audit/detail.html",
        {
            "audit": audit,
            "incidents": incidents,
        },
    )


@login_required
def asset_compliance_audit_create(request):
    if request.method == "POST":
        form = AssetComplianceAuditForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            audit = form.save(commit=False)
            audit.tenant = request.tenant
            audit.save()
            write_audit_log(
                request.tenant,
                request.user,
                "create",
                "AssetComplianceAudit",
                audit.pk,
                f"Scheduled compliance audit {audit.number} ({audit.title})",
            )
            messages.success(request, f"Compliance audit {audit.number} created successfully.")
            return redirect("assets:asset_compliance_audit_detail", pk=audit.pk)
    else:
        initial = {}
        framework_arg = request.GET.get("framework", "").strip()
        if framework_arg and framework_arg.isdigit():
            initial["framework"] = int(framework_arg)
        form = AssetComplianceAuditForm(initial=initial, tenant=request.tenant)

    return render(
        request,
        "assets/assetcompliance/asset_compliance_audit/form.html",
        {
            "form": form,
            "audit": None,
            "is_edit": False,
        },
    )


@login_required
def asset_compliance_audit_edit(request, pk):
    audit = assets_object(request, AssetComplianceAudit, pk)
    if request.method == "POST":
        form = AssetComplianceAuditForm(request.POST, instance=audit, tenant=request.tenant)
        if form.is_valid():
            audit = form.save()
            write_audit_log(
                request.tenant,
                request.user,
                "update",
                "AssetComplianceAudit",
                audit.pk,
                f"Updated compliance audit {audit.number} ({audit.title})",
            )
            messages.success(request, f"Compliance audit {audit.number} updated successfully.")
            return redirect("assets:asset_compliance_audit_detail", pk=audit.pk)
    else:
        form = AssetComplianceAuditForm(instance=audit, tenant=request.tenant)

    return render(
        request,
        "assets/assetcompliance/asset_compliance_audit/form.html",
        {
            "form": form,
            "audit": audit,
            "is_edit": True,
        },
    )


@login_required
@require_POST
def asset_compliance_audit_delete(request, pk):
    audit = assets_object(request, AssetComplianceAudit, pk)
    num = audit.number
    audit.delete()
    write_audit_log(
        request.tenant,
        request.user,
        "delete",
        "AssetComplianceAudit",
        pk,
        f"Deleted compliance audit {num}",
    )
    messages.success(request, f"Compliance audit {num} was deleted.")
    return redirect("assets:asset_compliance_audit_list")


@login_required
@require_POST
def asset_compliance_audit_start(request, pk):
    audit = assets_object(request, AssetComplianceAudit, pk)
    if audit.status == "scheduled":
        audit.status = "in_progress"
        audit.save(update_fields=["status", "updated_at"])
        write_audit_log(
            request.tenant,
            request.user,
            "update",
            "AssetComplianceAudit",
            audit.pk,
            f"Started fieldwork for audit {audit.number}",
        )
        messages.success(request, f"Audit {audit.number} fieldwork has been started.")
    else:
        messages.warning(request, f"Audit {audit.number} cannot be started from status '{audit.get_status_display()}'.")
    return redirect("assets:asset_compliance_audit_detail", pk=audit.pk)


@login_required
@require_POST
def asset_compliance_audit_complete(request, pk):
    audit = assets_object(request, AssetComplianceAudit, pk)
    if audit.status in ["in_progress", "under_review", "scheduled"]:
        audit.status = "completed"
        audit.completed_at = timezone.now()
        audit.save(update_fields=["status", "completed_at", "updated_at"])
        write_audit_log(
            request.tenant,
            request.user,
            "update",
            "AssetComplianceAudit",
            audit.pk,
            f"Completed and signed off compliance audit {audit.number}",
        )
        messages.success(request, f"Compliance audit {audit.number} is now marked as Completed.")
    else:
        messages.warning(request, f"Audit {audit.number} is already closed or cancelled.")
    return redirect("assets:asset_compliance_audit_detail", pk=audit.pk)
