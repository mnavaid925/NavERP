"""Computed End-of-Life & Refresh Cycles Workbench views (11.18)."""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Q
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


def _build_refresh_context(request):
    """Gather EOL, hardware refresh forecast, NIST sanitization backlog, and renewal horizon."""
    today = timezone.now().date()
    raw_horizon = parse_pos_int(request.GET.get("horizon"))
    horizon_days = raw_horizon if raw_horizon in _VALID_HORIZONS else 90
    selected_priority = request.GET.get("priority", "").strip()
    if selected_priority not in _VALID_PRIORITIES:
        selected_priority = ""

    cutoff = today + timedelta(days=horizon_days)

    hw_qs = (
        assets_scope(ItHardwareAsset.objects.all(), request)
        .exclude(status__in=ItHardwareAsset.LOCKED_STATUSES)
        .select_related("org_unit", "currency", "owner")
        .order_by("refresh_due_date", "vendor_eol_date", "hostname")
    )
    hw_qs = apply_fk_filter(hw_qs, request, "org_unit")

    sw_qs = (
        assets_scope(SoftwareLicense.objects.all(), request)
        .exclude(status__in=SoftwareLicense.LOCKED_STATUSES)
        .select_related("org_unit", "currency", "license_owner")
        .order_by("renewal_date", "vendor_eol_date", "software_name")
    )
    sw_qs = apply_fk_filter(sw_qs, request, "org_unit")

    cloud_qs = (
        assets_scope(CloudAssetSubscription.objects.all(), request)
        .exclude(status__in=CloudAssetSubscription.LOCKED_STATUSES)
        .select_related("org_unit", "currency", "business_owner")
        .order_by("renewal_date", "vendor_eol_date", "name")
    )
    cloud_qs = apply_fk_filter(cloud_qs, request, "org_unit")

    overdue_hw_count = 0
    due_90d_hw_count = 0
    total_refresh_capex = Decimal("0.00")
    hardware_rows = []
    sanitization_backlog = []
    org_unit_totals = {}

    for hw in hw_qs:
        prio = hw.refresh_priority
        if prio == "overdue_critical":
            overdue_hw_count += 1
        elif prio == "due_within_90d":
            due_90d_hw_count += 1

        if hw.sanitization_required and hw.sanitization_status == "pending_wipe":
            sanitization_backlog.append(hw)

        target_date = hw.refresh_due_date or hw.vendor_eol_date
        within_horizon = bool(target_date and target_date <= cutoff)
        matches_horizon = (
            prio in ("overdue_critical", "due_within_90d")
            or within_horizon
            or hw.status == "pending_refresh"
        )
        if selected_priority:
            include_row = prio == selected_priority
        else:
            include_row = matches_horizon

        if include_row:
            capex = hw.estimated_refresh_cost or Decimal("0.00")
            total_refresh_capex += capex
            hardware_rows.append(hw)
            ou_name = hw.org_unit.name if hw.org_unit else "Unassigned Org Unit"
            bucket = org_unit_totals.setdefault(
                ou_name,
                {"org_unit_name": ou_name, "hw_count": 0, "overdue_count": 0, "capex": Decimal("0.00")},
            )
            bucket["hw_count"] += 1
            if prio == "overdue_critical":
                bucket["overdue_count"] += 1
            bucket["capex"] += capex

    software_rows = list(
        sw_qs.filter(
            Q(renewal_date__isnull=False, renewal_date__lte=cutoff)
            | Q(vendor_eol_date__isnull=False, vendor_eol_date__lte=cutoff)
        )
    )
    cloud_rows = list(
        cloud_qs.filter(
            Q(renewal_date__isnull=False, renewal_date__lte=cutoff)
            | Q(vendor_eol_date__isnull=False, vendor_eol_date__lte=cutoff)
        )
    )

    org_unit_summary = sorted(
        org_unit_totals.values(),
        key=lambda row: (-row["capex"], row["org_unit_name"]),
    )

    return {
        "hardware_rows": hardware_rows,
        "software_rows": software_rows,
        "cloud_rows": cloud_rows,
        "sanitization_backlog": sanitization_backlog,
        "org_unit_summary": org_unit_summary,
        "org_units": OrgUnit.objects.filter(tenant=request.tenant).order_by("name"),
        "horizon_days": horizon_days,
        "selected_priority": selected_priority,
        "total_refresh_capex": total_refresh_capex,
        "overdue_hw_count": overdue_hw_count,
        "due_90d_hw_count": due_90d_hw_count,
        "pending_wipe_count": len(sanitization_backlog),
        "expiring_sw_cloud_count": len(software_rows) + len(cloud_rows),
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
    ctx = _build_refresh_context(request)
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
    rows = []
    for hw in ctx["hardware_rows"]:
        rows.append(
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
        )
    for sw in ctx["software_rows"]:
        rows.append(
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
        )
    for cl in ctx["cloud_rows"]:
        rows.append(
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
        )
    return csv_export_response(
        filename="it_refresh_board.csv",
        headers=headers,
        rows=rows,
    )
