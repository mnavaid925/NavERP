from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.assets.forms.AssetInventoryTracking.AssetAudits import AssetAuditForm
from apps.assets.models.AssetInventoryTracking.AssetAudits import AssetAudit
from apps.core.decorators import tenant_admin_required
from apps.core.models import OrgUnit
from apps.core.utils import write_audit_log
from apps.scm.models import Location


@login_required
def asset_audit_list(request):
    qs = AssetAudit.objects.filter(tenant=request.tenant).select_related(
        "target_location", "target_org_unit", "lead_auditor", "supervisor", "reconciled_by"
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(title__icontains=q)
            | Q(asset_category__icontains=q)
            | Q(discrepancy_notes__icontains=q)
        )

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    audit_type = request.GET.get("audit_type", "").strip()
    if audit_type:
        qs = qs.filter(audit_type=audit_type)

    location_id = request.GET.get("location", "").strip()
    if location_id and location_id.isdigit():
        qs = qs.filter(target_location_id=int(location_id))

    org_unit_id = request.GET.get("org_unit", "").strip()
    if org_unit_id and org_unit_id.isdigit():
        qs = qs.filter(target_org_unit_id=int(org_unit_id))

    # Aggregates for KPI cards
    all_tenant_audits = AssetAudit.objects.filter(tenant=request.tenant)
    counts = all_tenant_audits.aggregate(
        total=Count("id"),
        scheduled=Count("id", filter=Q(status="scheduled")),
        in_progress=Count("id", filter=Q(status="in_progress")),
        completed=Count("id", filter=Q(status="completed")),
        reconciled=Count("id", filter=Q(status="reconciled")),
    )

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    locations = Location.objects.filter(tenant=request.tenant, is_active=True).order_by("name")
    org_units = OrgUnit.objects.filter(tenant=request.tenant).order_by("name")

    context = {
        "audits": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "locations": locations,
        "org_units": org_units,
        "type_choices": AssetAudit.AUDIT_TYPE_CHOICES,
        "status_choices": AssetAudit.STATUS_CHOICES,
        "action_choices": AssetAudit.RECONCILIATION_ACTION_CHOICES,
        "q": q,
        "total_count": counts["total"] or 0,
        "scheduled_count": counts["scheduled"] or 0,
        "in_progress_count": counts["in_progress"] or 0,
        "completed_count": counts["completed"] or 0,
        "reconciled_count": counts["reconciled"] or 0,
    }
    return render(request, "assets/asset_inventory_tracking/asset_audit/list.html", context)


@login_required
def asset_audit_detail(request, pk):
    audit = get_object_or_404(
        AssetAudit.objects.select_related(
            "target_location", "target_org_unit", "lead_auditor", "supervisor", "reconciled_by"
        ),
        pk=pk,
        tenant=request.tenant,
    )
    return render(request, "assets/asset_inventory_tracking/asset_audit/detail.html", {"audit": audit})


@login_required
def asset_audit_create(request):
    if request.method == "POST":
        form = AssetAuditForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                obj = form.save(commit=False)
                obj.tenant = request.tenant
                obj.save()
                form.save_m2m()
                write_audit_log(request.user, obj, "create", tenant=request.tenant)
            messages.success(request, f"Asset audit {obj.number} created successfully.")
            return redirect("assets:asset_audit_detail", pk=obj.pk)
    else:
        form = AssetAuditForm(tenant=request.tenant)

    return render(
        request,
        "assets/asset_inventory_tracking/asset_audit/form.html",
        {"form": form, "audit": None, "is_edit": False},
    )


@login_required
def asset_audit_edit(request, pk):
    audit = get_object_or_404(AssetAudit, pk=pk, tenant=request.tenant)
    if audit.status in ("completed", "reconciled", "cancelled"):
        messages.error(request, f"Audit {audit.number} is {audit.get_status_display()} and cannot be edited.")
        return redirect("assets:asset_audit_detail", pk=audit.pk)

    if request.method == "POST":
        form = AssetAuditForm(request.POST, instance=audit, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                obj = form.save()
                write_audit_log(request.user, obj, "update", tenant=request.tenant)
            messages.success(request, f"Asset audit {obj.number} updated successfully.")
            return redirect("assets:asset_audit_detail", pk=obj.pk)
    else:
        form = AssetAuditForm(instance=audit, tenant=request.tenant)

    return render(
        request,
        "assets/asset_inventory_tracking/asset_audit/form.html",
        {"form": form, "audit": audit, "is_edit": True},
    )


@login_required
@require_POST
def asset_audit_delete(request, pk):
    audit = get_object_or_404(AssetAudit, pk=pk, tenant=request.tenant)
    if audit.status not in ("draft", "cancelled"):
        messages.error(request, f"Audit {audit.number} cannot be deleted because it is {audit.get_status_display()}.")
        return redirect("assets:asset_audit_detail", pk=audit.pk)

    num = audit.number
    with transaction.atomic():
        write_audit_log(request.user, audit, "delete", tenant=request.tenant)
        audit.delete()
    messages.success(request, f"Audit {num} has been deleted.")
    return redirect("assets:asset_audit_list")


@login_required
@require_POST
def asset_audit_start(request, pk):
    audit = get_object_or_404(AssetAudit, pk=pk, tenant=request.tenant)
    if audit.status not in ("draft", "scheduled"):
        messages.error(request, f"Cannot start audit in '{audit.get_status_display()}' state.")
        return redirect("assets:asset_audit_detail", pk=audit.pk)

    with transaction.atomic():
        audit.status = "in_progress"
        audit.started_at = timezone.now()
        audit.save(update_fields=["status", "started_at", "updated_at"])
        write_audit_log(request.user, audit, "update", changes={"status": "in_progress"}, tenant=request.tenant)

    messages.success(request, f"Audit {audit.number} started. Count execution in progress.")
    return redirect("assets:asset_audit_detail", pk=audit.pk)


@login_required
@require_POST
def asset_audit_complete(request, pk):
    audit = get_object_or_404(AssetAudit, pk=pk, tenant=request.tenant)
    if audit.status != "in_progress":
        messages.error(request, f"Cannot complete audit in '{audit.get_status_display()}' state.")
        return redirect("assets:asset_audit_detail", pk=audit.pk)

    with transaction.atomic():
        audit.status = "completed"
        audit.completed_at = timezone.now()
        audit.save(update_fields=["status", "completed_at", "updated_at"])
        write_audit_log(request.user, audit, "update", changes={"status": "completed"}, tenant=request.tenant)

    messages.success(request, f"Audit {audit.number} marked completed. Ready for supervisor reconciliation.")
    return redirect("assets:asset_audit_detail", pk=audit.pk)


@login_required
@tenant_admin_required
@require_POST
def asset_audit_reconcile(request, pk):
    audit = get_object_or_404(AssetAudit, pk=pk, tenant=request.tenant)
    if audit.status != "completed":
        messages.error(request, f"Cannot reconcile audit in '{audit.get_status_display()}' state. Must be completed first.")
        return redirect("assets:asset_audit_detail", pk=audit.pk)

    action = request.POST.get("reconciliation_action", "no_action_needed").strip()
    valid_actions = dict(AssetAudit.RECONCILIATION_ACTION_CHOICES)
    if action not in valid_actions:
        action = "no_action_needed"

    notes = request.POST.get("discrepancy_notes", audit.discrepancy_notes).strip()

    with transaction.atomic():
        audit.status = "reconciled"
        audit.reconciliation_action = action
        audit.discrepancy_notes = notes
        audit.reconciled_by = request.user
        audit.reconciled_at = timezone.now()
        audit.save(update_fields=["status", "reconciliation_action", "discrepancy_notes", "reconciled_by", "reconciled_at", "updated_at"])
        write_audit_log(request.user, audit, "update", changes={"status": "reconciled", "action": action}, tenant=request.tenant)

    messages.success(request, f"Audit {audit.number} successfully reconciled ({valid_actions[action]}).")
    return redirect("assets:asset_audit_detail", pk=audit.pk)


@login_required
@require_POST
def asset_audit_cancel(request, pk):
    audit = get_object_or_404(AssetAudit, pk=pk, tenant=request.tenant)
    if audit.status in ("completed", "reconciled", "cancelled"):
        messages.error(request, f"Cannot cancel audit in '{audit.get_status_display()}' state.")
        return redirect("assets:asset_audit_detail", pk=audit.pk)

    with transaction.atomic():
        audit.status = "cancelled"
        audit.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, audit, "update", changes={"status": "cancelled"}, tenant=request.tenant)

    messages.info(request, f"Audit {audit.number} has been cancelled.")
    return redirect("assets:asset_audit_detail", pk=audit.pk)
