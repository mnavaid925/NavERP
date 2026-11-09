from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q, Sum
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounting.models import FixedAsset
from apps.assets.forms.AssetPerformance.AssetOeeRecords import AssetOeeRecordForm
from apps.assets.models.AssetPerformance.AssetOeeRecords import AssetOeeRecord
from apps.assets.views._common import assets_object
from apps.core.utils import write_audit_log


@login_required
def asset_oee_record_list(request):
    qs = AssetOeeRecord.objects.filter(tenant=request.tenant).select_related(
        "fixed_asset", "operational_asset"
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(shift_name__icontains=q)
            | Q(notes__icontains=q)
            | Q(fixed_asset__name__icontains=q)
            | Q(operational_asset__name__icontains=q)
        )

    selected_status = request.GET.get("status", "").strip()
    if selected_status:
        qs = qs.filter(status=selected_status)

    selected_tier = request.GET.get("tier", "").strip()
    if selected_tier:
        qs = qs.filter(benchmark_tier=selected_tier)

    fixed_asset_id = request.GET.get("fixed_asset", "").strip()
    if fixed_asset_id.isdigit():
        qs = qs.filter(fixed_asset_id=int(fixed_asset_id))

    all_tenant_records = AssetOeeRecord.objects.filter(tenant=request.tenant)
    agg = all_tenant_records.aggregate(
        total_records=Count("id"),
        avg_oee=Avg("oee_percentage"),
        world_class_count=Count("id", filter=Q(benchmark_tier="world_class")),
        total_good=Sum("good_units_produced"),
        total_defects=Sum("defect_units_count"),
    )

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    fixed_assets = FixedAsset.objects.filter(tenant=request.tenant).only("id", "name").order_by("name")

    context = {
        "page_obj": page_obj,
        "paginator": paginator,
        "q": q,
        "status": selected_status,
        "tier": selected_tier,
        "fixed_asset_id": fixed_asset_id,
        "status_choices": AssetOeeRecord.STATUS_CHOICES,
        "tier_choices": AssetOeeRecord.BENCHMARK_TIER_CHOICES,
        "fixed_assets": fixed_assets,
        "status_css": AssetOeeRecord.STATUS_CSS,
        "tier_css": AssetOeeRecord.TIER_CSS,
        "agg": agg,
    }
    return render(request, "assets/asset_performance/asset_oee_record/list.html", context)


@login_required
def asset_oee_record_detail(request, pk):
    record = assets_object(
        request,
        AssetOeeRecord,
        pk,
        select_related=["fixed_asset", "operational_asset", "recorded_by"],
    )
    context = {
        "record": record,
        "status_css": AssetOeeRecord.STATUS_CSS,
        "tier_css": AssetOeeRecord.TIER_CSS,
    }
    return render(request, "assets/asset_performance/asset_oee_record/detail.html", context)


@login_required
def asset_oee_record_create(request):
    if request.method == "POST":
        form = AssetOeeRecordForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            record = form.save(commit=False)
            record.tenant = request.tenant
            if not record.recorded_by:
                record.recorded_by = request.user
            record.save()
            write_audit_log(request.user, record, "create", tenant=request.tenant)
            messages.success(request, f"OEE entry {record.number} saved. Calculated OEE: {record.oee_percentage}%.")
            return redirect("assets:asset_oee_record_detail", pk=record.pk)
    else:
        initial = {
            "record_date": timezone.now().date(),
            "shift_name": "Shift 1",
            "planned_production_time_minutes": Decimal("480.00"),
            "ideal_cycle_time_seconds": Decimal("10.00"),
            "recorded_by": request.user.pk,
        }
        fixed_asset_id = request.GET.get("fixed_asset")
        if fixed_asset_id and fixed_asset_id.isdigit():
            initial["fixed_asset"] = int(fixed_asset_id)
        form = AssetOeeRecordForm(initial=initial, tenant=request.tenant)

    context = {
        "form": form,
        "record": None,
        "is_edit": False,
    }
    return render(request, "assets/asset_performance/asset_oee_record/form.html", context)


@login_required
def asset_oee_record_edit(request, pk):
    record = assets_object(request, AssetOeeRecord, pk)
    if request.method == "POST":
        form = AssetOeeRecordForm(request.POST, instance=record, tenant=request.tenant)
        if form.is_valid():
            record = form.save()
            write_audit_log(request.user, record, "update", tenant=request.tenant)
            messages.success(request, f"OEE entry {record.number} updated. Recalculated OEE: {record.oee_percentage}%.")
            return redirect("assets:asset_oee_record_detail", pk=record.pk)
    else:
        form = AssetOeeRecordForm(instance=record, tenant=request.tenant)

    context = {
        "form": form,
        "record": record,
        "is_edit": True,
    }
    return render(request, "assets/asset_performance/asset_oee_record/form.html", context)


@login_required
@require_POST
def asset_oee_record_delete(request, pk):
    record = assets_object(request, AssetOeeRecord, pk, select_related=["fixed_asset", "operational_asset"])
    number = record.number
    write_audit_log(request.user, record, "delete", tenant=request.tenant)
    record.delete()
    messages.success(request, f"OEE entry {number} deleted.")
    return redirect("assets:asset_oee_record_list")


@login_required
@require_POST
def asset_oee_record_finalize(request, pk):
    record = assets_object(request, AssetOeeRecord, pk, select_related=["fixed_asset", "operational_asset"])
    if record.status != "draft":
        messages.error(request, f"OEE entry {record.number} cannot be finalized because it is currently {record.get_status_display().lower()}.")
        return redirect("assets:asset_oee_record_detail", pk=record.pk)
    record.status = "finalized"
    record.save()
    write_audit_log(request.user, record, "finalize", tenant=request.tenant)
    messages.success(request, f"OEE entry {record.number} verified and finalized.")
    return redirect("assets:asset_oee_record_detail", pk=record.pk)
