"""Computed End-of-Life & Refresh Cycles Workbench views (11.18)."""

from datetime import timedelta
from decimal import Decimal
from itertools import chain

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce
from django.shortcuts import render
from django.utils import timezone

from apps.assets.models.ItAssetManagement.CloudAssetSubscriptions import (
    CloudAssetSubscription,
)
from apps.assets.models.ItAssetManagement.ItHardwareAssets import ItHardwareAsset
from apps.assets.models.ItAssetManagement.SoftwareLicenses import SoftwareLicense
from apps.assets.views._common import assets_scope
from apps.assets.views.ItAssetManagement._helpers import (
    apply_fk_filter,
    csv_export_response,
    parse_pos_int,
)
from apps.core.models.OrgUnit import OrgUnit

_VALID_HORIZONS = {30, 90, 180, 365}
_VALID_PRIORITIES = {"overdue_critical", "due_within_90d", "planned_fy", "healthy"}
_BOARD_ROW_CAP = 200


def _refresh_priority_predicates(today, cutoff):
    """Build SQL Q predicates matching ``ItHardwareAsset.refresh_priority``."""
    d90 = today + timedelta(days=90)
    d365 = today + timedelta(days=365)
    overdue_q = Q(vendor_eol_date__lt=today) | Q(refresh_due_date__lt=today)
    due_90d_q = ~overdue_q & (
        Q(refresh_due_date__gte=today, refresh_due_date__lte=d90)
        | Q(refresh_due_date__isnull=True, vendor_eol_date__gte=today, vendor_eol_date__lte=d90)
    )
    planned_fy_q = ~overdue_q & ~due_90d_q & (
        Q(refresh_due_date__gt=d90, refresh_due_date__lte=d365)
        | Q(refresh_due_date__isnull=True, vendor_eol_date__gt=d90, vendor_eol_date__lte=d365)
    )
    healthy_q = ~overdue_q & ~due_90d_q & ~planned_fy_q
    within_horizon_q = Q(refresh_due_date__lte=cutoff) | Q(
        refresh_due_date__isnull=True, vendor_eol_date__lte=cutoff
    )
    matches_horizon_q = overdue_q | due_90d_q | within_horizon_q | Q(status="pending_refresh")
    return overdue_q, due_90d_q, planned_fy_q, healthy_q, matches_horizon_q


def _build_refresh_querysets(request):
    """Return scoped, filtered hardware, software, and cloud querysets for refresh views."""
    today = timezone.now().date()
    raw_horizon = parse_pos_int(request.GET.get("horizon"))
    horizon_days = raw_horizon if raw_horizon in _VALID_HORIZONS else 90
    selected_priority = request.GET.get("priority", "").strip()
    if selected_priority not in _VALID_PRIORITIES:
        selected_priority = ""

    cutoff = today + timedelta(days=horizon_days)
    overdue_q, due_90d_q, planned_fy_q, healthy_q, matches_horizon_q = _refresh_priority_predicates(
        today, cutoff
    )

    hw_base_qs = apply_fk_filter(
        assets_scope(ItHardwareAsset.objects.all(), request)
        .exclude(status__in=ItHardwareAsset.LOCKED_STATUSES)
        .order_by("refresh_due_date", "vendor_eol_date", "hostname"),
        request,
        "org_unit",
    )

    priority_q = {
        "overdue_critical": overdue_q,
        "due_within_90d": due_90d_q,
        "planned_fy": planned_fy_q,
        "healthy": healthy_q,
    }.get(selected_priority)
    filtered_hw_qs = hw_base_qs.filter(priority_q if priority_q is not None else matches_horizon_q)

    cutoff_q = Q(renewal_date__isnull=False, renewal_date__lte=cutoff) | Q(
        vendor_eol_date__isnull=False, vendor_eol_date__lte=cutoff
    )
    sw_filtered_qs = apply_fk_filter(
        assets_scope(SoftwareLicense.objects.all(), request)
        .exclude(status__in=SoftwareLicense.LOCKED_STATUSES)
        .filter(cutoff_q)
        .order_by("renewal_date", "vendor_eol_date", "software_name"),
        request,
        "org_unit",
    )
    cloud_filtered_qs = apply_fk_filter(
        assets_scope(CloudAssetSubscription.objects.all(), request)
        .exclude(status__in=CloudAssetSubscription.LOCKED_STATUSES)
        .filter(cutoff_q)
        .order_by("renewal_date", "vendor_eol_date", "name"),
        request,
        "org_unit",
    )

    return {
        "horizon_days": horizon_days,
        "selected_priority": selected_priority,
        "overdue_q": overdue_q,
        "due_90d_q": due_90d_q,
        "hw_base_qs": hw_base_qs,
        "filtered_hw_qs": filtered_hw_qs,
        "sw_filtered_qs": sw_filtered_qs,
        "cloud_filtered_qs": cloud_filtered_qs,
    }


def _build_refresh_context(request):
    """Gather EOL, hardware refresh forecast, NIST sanitization backlog, and renewal horizon."""
    qsets = _build_refresh_querysets(request)
    hw_base_qs = qsets["hw_base_qs"]
    filtered_hw_qs = qsets["filtered_hw_qs"]
    sw_filtered_qs = qsets["sw_filtered_qs"]
    cloud_filtered_qs = qsets["cloud_filtered_qs"]
    overdue_q = qsets["overdue_q"]
    due_90d_q = qsets["due_90d_q"]

    pending_wipe_q = Q(sanitization_required=True, sanitization_status="pending_wipe")
    hw_kpis = hw_base_qs.aggregate(
        overdue_hw_count=Count("id", filter=overdue_q),
        due_90d_hw_count=Count("id", filter=due_90d_q),
        pending_wipe_count=Count("id", filter=pending_wipe_q),
    )
    total_refresh_capex = filtered_hw_qs.aggregate(
        total=Coalesce(Sum("estimated_refresh_cost"), Decimal("0.00"))
    )["total"]

    raw_ou_rows = (
        filtered_hw_qs.values("org_unit__name")
        .annotate(
            hw_count=Count("id"),
            overdue_count=Count("id", filter=overdue_q),
            capex=Coalesce(Sum("estimated_refresh_cost"), Decimal("0.00")),
        )
        .order_by("-capex", "org_unit__name")[:_BOARD_ROW_CAP]
    )
    org_unit_summary = [
        {
            "org_unit_name": row["org_unit__name"] or "Unassigned Org Unit",
            "hw_count": row["hw_count"],
            "overdue_count": row["overdue_count"],
            "capex": row["capex"],
        }
        for row in raw_ou_rows
    ]

    hardware_rows = list(filtered_hw_qs.select_related("org_unit", "currency")[:_BOARD_ROW_CAP])
    sanitization_backlog = list(hw_base_qs.filter(pending_wipe_q)[:_BOARD_ROW_CAP])
    expiring_sw_cloud_count = sw_filtered_qs.count() + cloud_filtered_qs.count()
    software_rows = list(sw_filtered_qs[:_BOARD_ROW_CAP])
    cloud_rows = list(cloud_filtered_qs[:_BOARD_ROW_CAP])

    return {
        "hardware_rows": hardware_rows,
        "software_rows": software_rows,
        "cloud_rows": cloud_rows,
        "sanitization_backlog": sanitization_backlog,
        "org_unit_summary": org_unit_summary,
        "org_units": OrgUnit.objects.filter(tenant=request.tenant).order_by("name"),
        "horizon_days": qsets["horizon_days"],
        "selected_priority": qsets["selected_priority"],
        "total_refresh_capex": total_refresh_capex,
        "overdue_hw_count": hw_kpis["overdue_hw_count"] or 0,
        "due_90d_hw_count": hw_kpis["due_90d_hw_count"] or 0,
        "pending_wipe_count": hw_kpis["pending_wipe_count"] or 0,
        "expiring_sw_cloud_count": expiring_sw_cloud_count,
    }


@login_required
def it_refresh_board(request):
    """Display computed IT Hardware refresh horizon, sanitization queue, & renewal cliffs."""
    context = _build_refresh_context(request)
    return render(
        request,
        "assets/itassetmanagement/it_refresh_board.html",
        context,
    )


@login_required
def it_refresh_board_export_csv(request):
    """Export computed IT refresh & renewal items as a formula-safe CSV."""
    qsets = _build_refresh_querysets(request)
    headers = [
        "Asset Domain",
        "Number",
        "Name / Hostname",
        "Org Unit",
        "Target Date",
        "Vendor EOL Date",
        "Priority / Status",
        "Estimated CapEx / Annual Spend",
    ]
    hw_iter = (
        [
            "IT Hardware",
            hw.number,
            hw.hostname,
            hw.org_unit.name if hw.org_unit else "",
            hw.refresh_due_date.isoformat() if hw.refresh_due_date else "",
            hw.vendor_eol_date.isoformat() if hw.vendor_eol_date else "",
            hw.refresh_priority_display,
            hw.estimated_refresh_cost,
        ]
        for hw in qsets["filtered_hw_qs"].select_related("org_unit")[:10000].iterator(chunk_size=1000)
    )
    sw_iter = (
        [
            "Software License",
            sw.number,
            sw.software_name,
            sw.org_unit.name if sw.org_unit else "",
            sw.renewal_date.isoformat() if sw.renewal_date else "",
            sw.vendor_eol_date.isoformat() if sw.vendor_eol_date else "",
            sw.get_status_display(),
            sw.total_annual_spend,
        ]
        for sw in qsets["sw_filtered_qs"].select_related("org_unit")[:10000].iterator(chunk_size=1000)
    )
    cl_iter = (
        [
            "Cloud / SaaS",
            cl.number,
            cl.name,
            cl.org_unit.name if cl.org_unit else "",
            cl.renewal_date.isoformat() if cl.renewal_date else "",
            cl.vendor_eol_date.isoformat() if cl.vendor_eol_date else "",
            cl.get_status_display(),
            cl.annual_contract_value or cl.monthly_recurring_cost,
        ]
        for cl in qsets["cloud_filtered_qs"].select_related("org_unit")[:10000].iterator(chunk_size=1000)
    )
    return csv_export_response(
        filename="it_refresh_board.csv",
        headers=headers,
        rows=chain(hw_iter, sw_iter, cl_iter),
    )
