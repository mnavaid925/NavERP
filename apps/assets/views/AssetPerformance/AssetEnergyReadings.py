from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounting.models import FixedAsset
from apps.assets.forms.AssetPerformance.AssetEnergyReadings import AssetEnergyReadingForm
from apps.assets.models.AssetPerformance.AssetEnergyReadings import AssetEnergyReading
from apps.assets.views._common import assets_object
from apps.core.utils import write_audit_log


@login_required
def asset_energy_reading_list(request):
    qs = AssetEnergyReading.objects.filter(tenant=request.tenant).select_related(
        "fixed_asset", "operational_asset", "utility_provider", "recorded_by"
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(meter_serial_number__icontains=q)
            | Q(notes__icontains=q)
            | Q(fixed_asset__name__icontains=q)
            | Q(operational_asset__name__icontains=q)
        )

    selected_status = request.GET.get("status", "").strip()
    if selected_status:
        qs = qs.filter(status=selected_status)

    selected_utility = request.GET.get("utility_type", "").strip()
    if selected_utility:
        qs = qs.filter(utility_type=selected_utility)

    selected_scope = request.GET.get("scope", "").strip()
    if selected_scope:
        qs = qs.filter(ghg_scope=selected_scope)

    fixed_asset_id = request.GET.get("fixed_asset", "").strip()
    if fixed_asset_id.isdigit():
        qs = qs.filter(fixed_asset_id=int(fixed_asset_id))

    all_tenant_readings = AssetEnergyReading.objects.filter(tenant=request.tenant)
    agg = all_tenant_readings.aggregate(
        total_readings=Count("id"),
        total_carbon=Sum("carbon_emissions_kg_co2e"),
        total_cost=Sum("total_energy_cost"),
        electricity_kwh=Sum("consumption_value", filter=Q(utility_type="electricity")),
    )

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    fixed_assets = FixedAsset.objects.filter(tenant=request.tenant).order_by("name")

    context = {
        "page_obj": page_obj,
        "paginator": paginator,
        "q": q,
        "status": selected_status,
        "utility_type": selected_utility,
        "scope": selected_scope,
        "fixed_asset_id": fixed_asset_id,
        "status_choices": AssetEnergyReading.STATUS_CHOICES,
        "utility_choices": AssetEnergyReading.UTILITY_TYPE_CHOICES,
        "scope_choices": AssetEnergyReading.GHG_SCOPE_CHOICES,
        "fixed_assets": fixed_assets,
        "status_css": AssetEnergyReading.STATUS_CSS,
        "utility_css": AssetEnergyReading.UTILITY_CSS,
        "scope_css": AssetEnergyReading.GHG_SCOPE_CSS,
        "agg": agg,
    }
    return render(request, "assets/asset_performance/asset_energy_reading/list.html", context)


@login_required
def asset_energy_reading_detail(request, pk):
    reading = assets_object(
        request,
        AssetEnergyReading,
        pk,
        select_related=["fixed_asset", "operational_asset", "utility_provider", "recorded_by"],
    )
    context = {
        "reading": reading,
        "status_css": AssetEnergyReading.STATUS_CSS,
        "utility_css": AssetEnergyReading.UTILITY_CSS,
        "scope_css": AssetEnergyReading.GHG_SCOPE_CSS,
    }
    return render(request, "assets/asset_performance/asset_energy_reading/detail.html", context)


@login_required
def asset_energy_reading_create(request):
    if request.method == "POST":
        form = AssetEnergyReadingForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            reading = form.save(commit=False)
            reading.tenant = request.tenant
            if not reading.recorded_by:
                reading.recorded_by = request.user
            reading.save()
            write_audit_log(request.user, reading, "create", tenant=request.tenant)
            messages.success(request, f"Energy meter reading {reading.number} logged successfully.")
            return redirect("assets:asset_energy_reading_detail", pk=reading.pk)
    else:
        initial = {
            "reading_timestamp": timezone.now().strftime("%Y-%m-%dT%H:%M"),
            "utility_type": "electricity",
            "unit_of_measure": "kWh",
            "emission_factor": Decimal("0.4500"),
            "ghg_scope": "scope_2",
            "recorded_by": request.user.pk,
        }
        fixed_asset_id = request.GET.get("fixed_asset")
        if fixed_asset_id and fixed_asset_id.isdigit():
            initial["fixed_asset"] = int(fixed_asset_id)
        form = AssetEnergyReadingForm(initial=initial, tenant=request.tenant)

    context = {
        "form": form,
        "reading": None,
        "is_edit": False,
    }
    return render(request, "assets/asset_performance/asset_energy_reading/form.html", context)


@login_required
def asset_energy_reading_edit(request, pk):
    reading = assets_object(request, AssetEnergyReading, pk)
    if request.method == "POST":
        form = AssetEnergyReadingForm(request.POST, instance=reading, tenant=request.tenant)
        if form.is_valid():
            reading = form.save()
            write_audit_log(request.user, reading, "update", tenant=request.tenant)
            messages.success(request, f"Energy reading {reading.number} updated successfully.")
            return redirect("assets:asset_energy_reading_detail", pk=reading.pk)
    else:
        form = AssetEnergyReadingForm(instance=reading, tenant=request.tenant)

    context = {
        "form": form,
        "reading": reading,
        "is_edit": True,
    }
    return render(request, "assets/asset_performance/asset_energy_reading/form.html", context)


@login_required
@require_POST
def asset_energy_reading_delete(request, pk):
    reading = assets_object(request, AssetEnergyReading, pk)
    number = reading.number
    write_audit_log(request.user, reading, "delete", tenant=request.tenant)
    reading.delete()
    messages.success(request, f"Energy reading {number} deleted.")
    return redirect("assets:asset_energy_reading_list")


@login_required
@require_POST
def asset_energy_reading_validate(request, pk):
    reading = assets_object(request, AssetEnergyReading, pk)
    reading.status = "validated"
    reading.save()
    write_audit_log(request.user, reading, "validate", tenant=request.tenant)
    messages.success(request, f"Energy reading {reading.number} validated.")
    return redirect("assets:asset_energy_reading_detail", pk=reading.pk)
