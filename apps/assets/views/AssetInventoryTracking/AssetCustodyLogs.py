from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.assets.forms.AssetInventoryTracking.AssetCustodyLogs import AssetCustodyLogForm
from apps.assets.models.AssetInventoryTracking.AssetCustodyLogs import AssetCustodyLog
from apps.core.models import Party
from apps.core.utils import write_audit_log
from apps.scm.models import Asset


@login_required
def asset_custody_log_list(request):
    qs = AssetCustodyLog.objects.filter(tenant=request.tenant).select_related(
        "asset", "borrower", "crib_attendant"
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(asset__number__icontains=q)
            | Q(asset__name__icontains=q)
            | Q(borrower_name__icontains=q)
            | Q(borrower__name__icontains=q)
            | Q(work_order_reference__icontains=q)
        )

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    action_type = request.GET.get("action_type", "").strip()
    if action_type:
        qs = qs.filter(action_type=action_type)

    borrower_id = request.GET.get("borrower", "").strip()
    if borrower_id and borrower_id.isdigit():
        qs = qs.filter(borrower_id=int(borrower_id))

    asset_id = request.GET.get("asset", "").strip()
    if asset_id and asset_id.isdigit():
        qs = qs.filter(asset_id=int(asset_id))

    # Auto-flag overdue loans
    today = timezone.now().date()
    overdue_qs = AssetCustodyLog.objects.filter(
        tenant=request.tenant,
        status="active_loan",
        expected_return_date__lt=today,
    )
    if overdue_qs.exists():
        overdue_qs.update(status="overdue")

    all_tenant_logs = AssetCustodyLog.objects.filter(tenant=request.tenant)
    counts = all_tenant_logs.aggregate(
        total=Count("id"),
        active_loans=Count("id", filter=Q(status="active_loan")),
        overdue=Count("id", filter=Q(status="overdue")),
        returned=Count("id", filter=Q(status="returned")),
    )

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    borrowers = Party.objects.filter(tenant=request.tenant).order_by("name")
    assets = Asset.objects.filter(tenant=request.tenant).order_by("number")

    context = {
        "custody_logs": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "borrowers": borrowers,
        "assets": assets,
        "action_choices": AssetCustodyLog.ACTION_TYPE_CHOICES,
        "status_choices": AssetCustodyLog.STATUS_CHOICES,
        "condition_choices": AssetCustodyLog.CHECKOUT_CONDITION_CHOICES,
        "q": q,
        "total_count": counts["total"] or 0,
        "active_loans_count": counts["active_loans"] or 0,
        "overdue_count": counts["overdue"] or 0,
        "returned_count": counts["returned"] or 0,
    }
    return render(request, "assets/asset_inventory_tracking/asset_custody_log/list.html", context)


@login_required
def asset_custody_log_detail(request, pk):
    custody_log = get_object_or_404(
        AssetCustodyLog.objects.select_related("asset", "borrower", "crib_attendant"),
        pk=pk,
        tenant=request.tenant,
    )
    return render(
        request,
        "assets/asset_inventory_tracking/asset_custody_log/detail.html",
        {"custody_log": custody_log},
    )


@login_required
def asset_custody_log_create(request):
    if request.method == "POST":
        form = AssetCustodyLogForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                obj = form.save(commit=False)
                obj.tenant = request.tenant
                if not obj.crib_attendant:
                    obj.crib_attendant = request.user
                obj.save()
                form.save_m2m()
                write_audit_log(request.user, obj, "create", tenant=request.tenant)
            messages.success(request, f"Equipment custody checkout {obj.number} logged successfully.")
            return redirect("assets:asset_custody_log_detail", pk=obj.pk)
    else:
        initial = {}
        asset_id = request.GET.get("asset", "").strip()
        if asset_id and asset_id.isdigit():
            initial["asset"] = int(asset_id)
        form = AssetCustodyLogForm(initial=initial, tenant=request.tenant)

    return render(
        request,
        "assets/asset_inventory_tracking/asset_custody_log/form.html",
        {"form": form, "custody_log": None, "is_edit": False},
    )


@login_required
def asset_custody_log_edit(request, pk):
    custody_log = get_object_or_404(AssetCustodyLog, pk=pk, tenant=request.tenant)
    if custody_log.status == "returned":
        messages.error(request, f"Loan {custody_log.number} has been returned and closed. It cannot be edited.")
        return redirect("assets:asset_custody_log_detail", pk=custody_log.pk)

    if request.method == "POST":
        form = AssetCustodyLogForm(request.POST, instance=custody_log, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                obj = form.save()
                write_audit_log(request.user, obj, "update", tenant=request.tenant)
            messages.success(request, f"Custody loan {obj.number} updated successfully.")
            return redirect("assets:asset_custody_log_detail", pk=obj.pk)
    else:
        form = AssetCustodyLogForm(instance=custody_log, tenant=request.tenant)

    return render(
        request,
        "assets/asset_inventory_tracking/asset_custody_log/form.html",
        {"form": form, "custody_log": custody_log, "is_edit": True},
    )


@login_required
@require_POST
def asset_custody_log_delete(request, pk):
    custody_log = get_object_or_404(AssetCustodyLog, pk=pk, tenant=request.tenant)
    if custody_log.status not in ("returned", "damaged_returned"):
        messages.error(request, f"Cannot delete custody record in '{custody_log.get_status_display()}' status.")
        return redirect("assets:asset_custody_log_detail", pk=custody_log.pk)

    num = custody_log.number
    with transaction.atomic():
        write_audit_log(request.user, custody_log, "delete", tenant=request.tenant)
        custody_log.delete()
    messages.success(request, f"Custody record {num} deleted.")
    return redirect("assets:asset_custody_log_list")


@login_required
@require_POST
def asset_custody_log_checkin(request, pk):
    custody_log = get_object_or_404(AssetCustodyLog, pk=pk, tenant=request.tenant)
    if custody_log.status not in ("active_loan", "overdue"):
        messages.error(request, f"Cannot check in loan in '{custody_log.get_status_display()}' state.")
        return redirect("assets:asset_custody_log_detail", pk=custody_log.pk)

    condition = request.POST.get("return_condition", "good").strip()
    valid_conditions = dict(AssetCustodyLog.RETURN_CONDITION_CHOICES)
    if condition not in valid_conditions:
        condition = "good"

    notes = request.POST.get("condition_notes", custody_log.condition_notes).strip()

    with transaction.atomic():
        new_status = "damaged_returned" if condition in ("damaged", "inoperable") else "returned"
        custody_log.status = new_status
        custody_log.action_type = "checkin"
        custody_log.actual_return_date = timezone.now()
        custody_log.return_condition = condition
        custody_log.condition_notes = notes
        custody_log.save(
            update_fields=[
                "status",
                "action_type",
                "actual_return_date",
                "return_condition",
                "condition_notes",
                "updated_at",
            ]
        )
        write_audit_log(
            request.user,
            custody_log,
            "update",
            changes={"status": new_status, "condition": condition},
            tenant=request.tenant,
        )

    messages.success(request, f"Asset {custody_log.asset.number} checked in successfully ({valid_conditions[condition]}).")
    return redirect("assets:asset_custody_log_detail", pk=custody_log.pk)


@login_required
@require_POST
def asset_custody_log_extend(request, pk):
    custody_log = get_object_or_404(AssetCustodyLog, pk=pk, tenant=request.tenant)
    if custody_log.status not in ("active_loan", "overdue"):
        messages.error(request, f"Cannot extend loan in '{custody_log.get_status_display()}' state.")
        return redirect("assets:asset_custody_log_detail", pk=custody_log.pk)

    days_str = request.POST.get("extension_days", "7").strip()
    days = int(days_str) if days_str.isdigit() else 7

    with transaction.atomic():
        base_date = custody_log.expected_return_date or timezone.now().date()
        custody_log.expected_return_date = base_date + timedelta(days=days)
        custody_log.status = "active_loan"
        custody_log.action_type = "extension"
        custody_log.save(update_fields=["expected_return_date", "status", "action_type", "updated_at"])
        write_audit_log(
            request.user,
            custody_log,
            "update",
            changes={"status": "active_loan", "extended_to": str(custody_log.expected_return_date)},
            tenant=request.tenant,
        )

    messages.success(request, f"Custody loan {custody_log.number} extended to {custody_log.expected_return_date}.")
    return redirect("assets:asset_custody_log_detail", pk=custody_log.pk)


@login_required
@require_POST
def asset_custody_log_mark_lost(request, pk):
    custody_log = get_object_or_404(AssetCustodyLog, pk=pk, tenant=request.tenant)
    if custody_log.status not in ("active_loan", "overdue"):
        messages.error(request, f"Cannot mark lost in '{custody_log.get_status_display()}' state.")
        return redirect("assets:asset_custody_log_detail", pk=custody_log.pk)

    with transaction.atomic():
        custody_log.status = "unreturned_lost"
        custody_log.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, custody_log, "update", changes={"status": "unreturned_lost"}, tenant=request.tenant)

    messages.warning(request, f"Loan {custody_log.number} flagged as unreturned / lost. Please initiate missing asset incident report.")
    return redirect("assets:asset_custody_log_detail", pk=custody_log.pk)
