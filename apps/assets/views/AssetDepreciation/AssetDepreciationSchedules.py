from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.assets.forms.AssetDepreciation.AssetDepreciationSchedules import AssetDepreciationScheduleForm
from apps.assets.models.AssetDepreciation.AssetDepreciationSchedules import AssetDepreciationSchedule
from apps.assets.views._common import assets_object
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def depreciation_schedule_list(request):
    qs = AssetDepreciationSchedule.objects.filter(tenant=request.tenant).select_related(
        "fixed_asset", "operational_asset", "fiscal_period", "cost_center"
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(fixed_asset__name__icontains=q)
            | Q(fixed_asset__number__icontains=q)
            | Q(operational_asset__name__icontains=q)
            | Q(notes__icontains=q)
        )

    selected_status = request.GET.get("status", "").strip()
    if selected_status:
        qs = qs.filter(status=selected_status)

    selected_method = request.GET.get("method", "").strip()
    if selected_method:
        qs = qs.filter(depreciation_method=selected_method)

    selected_year = request.GET.get("year", "").strip()
    if selected_year and selected_year.isdigit():
        qs = qs.filter(fiscal_year=int(selected_year))

    all_tenant_schedules = AssetDepreciationSchedule.objects.filter(tenant=request.tenant)
    agg = all_tenant_schedules.aggregate(
        total_runs=Count("id"),
        posted_count=Count("id", filter=Q(status="posted")),
        calculated_count=Count("id", filter=Q(status="calculated")),
        total_depreciation=Sum("depreciation_amount"),
    )

    year_choices = (
        all_tenant_schedules.values_list("fiscal_year", flat=True)
        .distinct()
        .order_by("-fiscal_year")
    )

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "depreciation_schedules": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "status_choices": AssetDepreciationSchedule.STATUS_CHOICES,
        "method_choices": AssetDepreciationSchedule.METHOD_CHOICES,
        "year_choices": list(year_choices) or [2026],
        "total_depreciation_period": agg["total_depreciation"] or Decimal("0.00"),
        "posted_count": agg["posted_count"] or 0,
        "calculated_count": agg["calculated_count"] or 0,
        "total_runs": agg["total_runs"] or 0,
        "q": q,
        "selected_status": selected_status,
        "selected_method": selected_method,
        "selected_year": selected_year,
    }
    return render(
        request, "assets/asset_depreciation/depreciation_schedule/list.html", context
    )


@login_required
def depreciation_schedule_detail(request, pk):
    schedule = assets_object(
        request,
        AssetDepreciationSchedule,
        pk=pk,
        select_related=[
            "fixed_asset",
            "operational_asset",
            "fiscal_period",
            "expense_account",
            "accumulated_account",
            "cost_center",
            "journal_entry",
            "posted_by",
        ],
    )
    context = {
        "schedule": schedule,
        "object": schedule,
    }
    return render(
        request, "assets/asset_depreciation/depreciation_schedule/detail.html", context
    )


@login_required
def depreciation_schedule_create(request):
    if request.method == "POST":
        form = AssetDepreciationScheduleForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            schedule = form.save(commit=False)
            schedule.tenant = request.tenant
            schedule.save()
            schedule.calculate_depreciation()
            schedule.save()
            write_audit_log(request.user, schedule, "create", tenant=request.tenant)
            messages.success(
                request, f"Depreciation schedule {schedule.number} created and calculated."
            )
            return redirect("assets:depreciation_schedule_detail", pk=schedule.pk)
    else:
        form = AssetDepreciationScheduleForm(tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": False,
        "schedule": None,
        "object": None,
    }
    return render(
        request, "assets/asset_depreciation/depreciation_schedule/form.html", context
    )


@login_required
def depreciation_schedule_edit(request, pk):
    schedule = assets_object(request, AssetDepreciationSchedule, pk=pk)
    if schedule.status == "posted":
        messages.error(request, "Posted depreciation schedules cannot be edited.")
        return redirect("assets:depreciation_schedule_detail", pk=schedule.pk)

    if request.method == "POST":
        form = AssetDepreciationScheduleForm(
            request.POST, instance=schedule, tenant=request.tenant
        )
        if form.is_valid():
            schedule = form.save(commit=False)
            schedule.save()
            schedule.calculate_depreciation()
            schedule.save()
            write_audit_log(request.user, schedule, "update", tenant=request.tenant)
            messages.success(
                request, f"Depreciation schedule {schedule.number} updated successfully."
            )
            return redirect("assets:depreciation_schedule_detail", pk=schedule.pk)
    else:
        form = AssetDepreciationScheduleForm(instance=schedule, tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": True,
        "schedule": schedule,
        "object": schedule,
    }
    return render(
        request, "assets/asset_depreciation/depreciation_schedule/form.html", context
    )


@login_required
@require_POST
@tenant_admin_required
def depreciation_schedule_delete(request, pk):
    schedule = assets_object(request, AssetDepreciationSchedule, pk=pk)
    if schedule.status == "posted":
        messages.error(request, "Cannot delete a posted depreciation schedule. Void or reverse instead.")
        return redirect("assets:depreciation_schedule_detail", pk=schedule.pk)

    num = schedule.number
    schedule.delete()
    write_audit_log(request.user, schedule, "delete", tenant=request.tenant)
    messages.success(request, f"Depreciation schedule {num} deleted.")
    return redirect("assets:depreciation_schedule_list")


@login_required
@require_POST
def depreciation_schedule_calculate(request, pk):
    schedule = assets_object(request, AssetDepreciationSchedule, pk=pk)
    if schedule.status == "posted":
        messages.error(request, "Cannot recalculate a posted depreciation schedule.")
        return redirect("assets:depreciation_schedule_detail", pk=schedule.pk)

    amount = schedule.calculate_depreciation(force=True)
    schedule.save()
    write_audit_log(request.user, schedule, "calculate", tenant=request.tenant)
    messages.success(request, f"Depreciation calculated: ${amount:,.2f} for {schedule.number}.")
    return redirect("assets:depreciation_schedule_detail", pk=schedule.pk)


@login_required
@require_POST
@tenant_admin_required
def depreciation_schedule_post(request, pk):
    schedule = assets_object(request, AssetDepreciationSchedule, pk=pk)
    try:
        je = schedule.post_to_gl(user=request.user)
        write_audit_log(request.user, schedule, "post", tenant=request.tenant)
        msg = f"Schedule {schedule.number} posted to General Ledger."
        if je:
            msg += f" Journal Entry {je.number} created."
        messages.success(request, msg)
    except ValidationError as exc:
        messages.error(request, str(exc.message if hasattr(exc, "message") else exc))

    return redirect("assets:depreciation_schedule_detail", pk=schedule.pk)
