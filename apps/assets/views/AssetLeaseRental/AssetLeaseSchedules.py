from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.assets.forms.AssetLeaseRental.AssetLeaseSchedules import AssetLeaseScheduleForm
from apps.assets.models.AssetLeaseRental.AssetLeaseContracts import AssetLeaseContract
from apps.assets.models.AssetLeaseRental.AssetLeaseSchedules import AssetLeaseSchedule
from apps.assets.views._common import assets_object, assets_scope
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def asset_lease_schedule_list(request):
    qs = assets_scope(
        AssetLeaseSchedule.objects.select_related("lease_contract", "lease_contract__lessor"),
        request,
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(payment_reference__icontains=q)
            | Q(lease_contract__number__icontains=q)
            | Q(lease_contract__title__icontains=q)
        )

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        qs = qs.filter(status=status_filter)

    lease_filter = request.GET.get("lease", "").strip()
    if lease_filter and lease_filter.isdigit():
        qs = qs.filter(lease_contract_id=int(lease_filter))

    base_tenant_qs = assets_scope(AssetLeaseSchedule.objects.all(), request)
    kpi_agg = base_tenant_qs.aggregate(
        total_schedules=Count("id"),
        scheduled_count=Count("id", filter=Q(status="scheduled")),
        paid_count=Count("id", filter=Q(status="paid")),
        total_paid_amount=Sum("payment_amount", filter=Q(status="paid")),
    )
    total_schedules = kpi_agg["total_schedules"] or 0
    scheduled_count = kpi_agg["scheduled_count"] or 0
    paid_count = kpi_agg["paid_count"] or 0
    total_paid_amount = kpi_agg["total_paid_amount"] or Decimal("0.00")

    paginator = Paginator(qs, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    lease_list = AssetLeaseContract.objects.filter(tenant=request.tenant).only("id", "number", "title").order_by("-id")

    context = {
        "schedules": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "status_choices": AssetLeaseSchedule.STATUS_CHOICES,
        "lease_list": lease_list,
        "total_schedules": total_schedules,
        "scheduled_count": scheduled_count,
        "paid_count": paid_count,
        "total_paid_amount": total_paid_amount,
        "q": q,
        "status": status_filter,
        "lease": lease_filter,
    }
    return render(request, "assets/assetleaserental/asset_lease_schedule/list.html", context)


@login_required
def asset_lease_schedule_detail(request, pk):
    schedule = assets_object(
        request,
        AssetLeaseSchedule,
        pk,
        select_related=["lease_contract", "lease_contract__lessor"],
    )
    return render(
        request,
        "assets/assetleaserental/asset_lease_schedule/detail.html",
        {"schedule": schedule},
    )


@login_required
def asset_lease_schedule_create(request):
    initial = {}
    lease_param = request.GET.get("lease")
    if lease_param and lease_param.isdigit():
        initial["lease_contract"] = int(lease_param)

    if request.method == "POST":
        form = AssetLeaseScheduleForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                instance = form.save(commit=False)
                instance.tenant = request.tenant
                instance.save()

                write_audit_log(
                    request.user,
                    instance,
                    "create",
                    changes=f"Created lease schedule {instance.number} for {instance.lease_contract.number}",
                    tenant=request.tenant,
                )

                messages.success(request, f"Lease schedule line {instance.number} created.")
                return redirect("assets:asset_lease_schedule_detail", pk=instance.pk)
    else:
        form = AssetLeaseScheduleForm(initial=initial, tenant=request.tenant)

    return render(
        request,
        "assets/assetleaserental/asset_lease_schedule/form.html",
        {"form": form, "title": "New Lease Schedule Line", "is_edit": False},
    )


@login_required
def asset_lease_schedule_edit(request, pk):
    schedule = assets_object(request, AssetLeaseSchedule, pk)

    if request.method == "POST":
        form = AssetLeaseScheduleForm(request.POST, instance=schedule, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                instance = form.save(commit=False)
                instance.save()

                write_audit_log(
                    request.user,
                    instance,
                    "update",
                    changes=f"Updated lease schedule {instance.number}",
                    tenant=request.tenant,
                )

                messages.success(request, f"Lease schedule line {instance.number} updated.")
                return redirect("assets:asset_lease_schedule_detail", pk=instance.pk)
    else:
        form = AssetLeaseScheduleForm(instance=schedule, tenant=request.tenant)

    return render(
        request,
        "assets/assetleaserental/asset_lease_schedule/form.html",
        {"form": form, "title": f"Edit Schedule — {schedule.number}", "is_edit": True, "schedule": schedule},
    )


@require_POST
@tenant_admin_required
def asset_lease_schedule_delete(request, pk):
    schedule = assets_object(request, AssetLeaseSchedule, pk)
    num = schedule.number
    contract_pk = schedule.lease_contract_id
    if schedule.status == "paid":
        messages.warning(request, f"Cannot delete schedule line {num} because it has already been paid and settled.")
        return redirect("assets:asset_lease_contract_detail", pk=contract_pk)

    write_audit_log(
        request.user,
        schedule,
        "delete",
        changes=f"Deleted lease schedule line {num}",
        tenant=request.tenant,
    )
    schedule.delete()
    messages.success(request, f"Schedule line {num} deleted.")
    return redirect("assets:asset_lease_contract_detail", pk=contract_pk)


@require_POST
@login_required
def asset_lease_schedule_mark_paid(request, pk):
    schedule = assets_object(request, AssetLeaseSchedule, pk, select_related=["lease_contract"])
    if schedule.status == "paid":
        messages.warning(request, f"Schedule period {schedule.period_number} is already marked as Paid.")
        return redirect("assets:asset_lease_schedule_detail", pk=schedule.pk)

    payment_ref = request.POST.get("payment_reference", "").strip()

    with transaction.atomic():
        schedule.status = "paid"
        schedule.paid_date = timezone.now().date()
        if payment_ref:
            schedule.payment_reference = payment_ref
        schedule.save()

        # Update contract current balances
        contract = schedule.lease_contract
        contract.current_lease_liability = schedule.ending_liability
        contract.current_rou_asset_carrying_value = schedule.ending_rou_asset_value
        contract.save()

        write_audit_log(
            request.user,
            schedule,
            "paid",
            changes=f"Marked schedule {schedule.number} (Period {schedule.period_number}) as paid (${schedule.payment_amount})",
            tenant=request.tenant,
        )

        messages.success(
            request,
            f"Schedule period {schedule.period_number} marked as Paid. Updated remaining liability to ${contract.current_lease_liability:,.2f}.",
        )
    return redirect("assets:asset_lease_schedule_detail", pk=schedule.pk)


@require_POST
@login_required
def asset_lease_schedule_accrue(request, pk):
    schedule = assets_object(request, AssetLeaseSchedule, pk)
    schedule.status = "accrued"
    schedule.save()

    write_audit_log(
        request.user,
        schedule,
        "accrue",
        changes=f"Accrued interest expense and ROU depreciation for schedule {schedule.number}",
        tenant=request.tenant,
    )
    messages.info(request, f"Schedule period {schedule.period_number} marked as Accrued.")
    return redirect("assets:asset_lease_schedule_detail", pk=schedule.pk)
