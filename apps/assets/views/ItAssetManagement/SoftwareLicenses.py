"""Function-based CRUD and SAM compliance views for Software Licenses (11.18)."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.assets.forms.ItAssetManagement.SoftwareLicenses import SoftwareLicenseForm
from apps.assets.models.ItAssetManagement._validators import add_months
from apps.assets.models.ItAssetManagement.CmdbRelationships import CmdbRelationship
from apps.assets.models.ItAssetManagement.SoftwareLicenses import SoftwareLicense
from apps.assets.views._common import assets_object, assets_scope
from apps.assets.views.ItAssetManagement._helpers import (
    CMDB_REL_SELECT_RELATED,
    PAGE_SIZE,
    apply_choice_filter,
    apply_fk_filter,
    csv_export_response,
    is_tenant_admin_user,
)
from apps.core.decorators import tenant_admin_required
from apps.core.models.OrgUnit import OrgUnit
from apps.core.utils import write_audit_log

_SW_LIST_SELECT_RELATED = (
    "org_unit",
    "currency",
    "publisher_party",
    "license_owner",
)

_SW_DETAIL_SELECT_RELATED = _SW_LIST_SELECT_RELATED + (
    "reseller_party",
    "gl_expense_account",
    "purchase_order__vendor",
    "service_contract",
)


def _filter_software_queryset(request, base_qs, select_related=_SW_LIST_SELECT_RELATED):
    """Apply search and dropdown GET filters to a SoftwareLicense queryset."""
    qs = base_qs.select_related(*select_related) if select_related else base_qs
    search_query = request.GET.get("q", "").strip()
    if search_query:
        qs = qs.filter(
            Q(number__icontains=search_query)
            | Q(software_name__icontains=search_query)
            | Q(publisher_name__icontains=search_query)
            | Q(product_sku__icontains=search_query)
            | Q(agreement_number__icontains=search_query)
        )
    qs = apply_choice_filter(
        qs,
        request,
        "status",
        allowed_values={val for val, _ in SoftwareLicense.STATUS_CHOICES},
    )
    qs = apply_choice_filter(
        qs,
        request,
        "software_category",
        allowed_values={val for val, _ in SoftwareLicense.SOFTWARE_CATEGORY_CHOICES},
    )
    qs = apply_choice_filter(
        qs,
        request,
        "license_type",
        allowed_values={val for val, _ in SoftwareLicense.LICENSE_TYPE_CHOICES},
    )
    qs = apply_choice_filter(
        qs,
        request,
        "license_metric",
        allowed_values={val for val, _ in SoftwareLicense.LICENSE_METRIC_CHOICES},
    )
    qs = apply_fk_filter(qs, request, "org_unit")
    return qs


@login_required
def software_license_list(request):
    """List software licenses with ELP compliance KPIs, search, filters, and pagination."""
    base_qs = assets_scope(SoftwareLicense.objects.all(), request)
    kpis = base_qs.aggregate(
        total_count=Count("id"),
        compliant_count=Count("id", filter=Q(status="active_compliant")),
        true_up_count=Count("id", filter=Q(status="true_up_required")),
        reclaimable_seats_total=Sum("reclaimable_inactive_count"),
    )
    filtered_qs = _filter_software_queryset(request, base_qs)
    paginator = Paginator(filtered_qs, PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "licenses": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "total_count": kpis["total_count"] or 0,
        "compliant_count": kpis["compliant_count"] or 0,
        "true_up_count": kpis["true_up_count"] or 0,
        "reclaimable_seats_total": kpis["reclaimable_seats_total"] or 0,
        "status_choices": SoftwareLicense.STATUS_CHOICES,
        "category_choices": SoftwareLicense.SOFTWARE_CATEGORY_CHOICES,
        "license_type_choices": SoftwareLicense.LICENSE_TYPE_CHOICES,
        "metric_choices": SoftwareLicense.LICENSE_METRIC_CHOICES,
        "org_units": OrgUnit.objects.filter(tenant=request.tenant).order_by("name"),
        "search_query": request.GET.get("q", "").strip(),
    }
    return render(request, "assets/itassetmanagement/software_license/list.html", context)


@login_required
def software_license_export_csv(request):
    """Export filtered software licenses as a formula-safe CSV."""
    base_qs = assets_scope(SoftwareLicense.objects.all(), request)
    qs = _filter_software_queryset(request, base_qs, select_related=())
    headers = [
        "Number",
        "Software Name",
        "Publisher",
        "Category",
        "License Type",
        "Metric",
        "Entitled",
        "Allocated",
        "Active Used",
        "Compliance Delta",
        "Reclaimable Inactive",
        "Annual Spend",
        "Renewal Date",
        "Vendor EOL",
        "Status",
    ]
    rows = (
        [
            lic.number,
            lic.software_name,
            lic.publisher_name,
            lic.get_software_category_display(),
            lic.get_license_type_display(),
            lic.get_license_metric_display(),
            lic.entitled_quantity,
            lic.allocated_quantity,
            lic.active_used_quantity,
            lic.compliance_delta,
            lic.reclaimable_inactive_count,
            lic.total_annual_spend,
            lic.renewal_date.isoformat() if lic.renewal_date else "",
            lic.vendor_eol_date.isoformat() if lic.vendor_eol_date else "",
            lic.get_status_display(),
        ]
        for lic in qs[:10000].iterator(chunk_size=1000)
    )
    return csv_export_response(filename="software_licenses.csv", headers=headers, rows=rows)


@login_required
def software_license_create(request):
    """Create a new tenant-scoped software license record."""
    if request.method == "POST":
        if request.tenant is None:
            messages.warning(request, "Workspace context is required to create a software license.")
            return redirect("assets:software_license_list")
        form = SoftwareLicenseForm(request.POST, tenant=request.tenant)
        form.instance.tenant = request.tenant
        if form.is_valid():
            with transaction.atomic():
                license_obj = form.save(commit=False)
                license_obj.tenant = request.tenant
                if license_obj.license_owner_id is None:
                    license_obj.license_owner = request.user
                license_obj.status = license_obj.compute_compliance_status()
                license_obj.last_reconciled_at = timezone.now()
                license_obj.save()
                write_audit_log(request.user, license_obj, "create", tenant=request.tenant)
            messages.success(request, f"Software License {license_obj.number} created.")
            return redirect("assets:software_license_detail", pk=license_obj.pk)
    else:
        form = SoftwareLicenseForm(tenant=request.tenant)

    return render(
        request,
        "assets/itassetmanagement/software_license/form.html",
        {
            "form": form,
            "license_obj": None,
            "is_edit": False,
            "title": "New Software License",
        },
    )


@login_required
def software_license_detail(request, pk):
    """Display a software license detail page with ELP delta, harvesting, and CMDB edges."""
    license_obj = assets_object(
        request,
        SoftwareLicense,
        pk,
        select_related=_SW_DETAIL_SELECT_RELATED,
    )
    outbound_edges = (
        CmdbRelationship.objects.filter(tenant=request.tenant, source_software=license_obj)
        .select_related(*CMDB_REL_SELECT_RELATED)
        .order_by("-updated_at")
    )
    inbound_edges = (
        CmdbRelationship.objects.filter(tenant=request.tenant, target_software=license_obj)
        .select_related(*CMDB_REL_SELECT_RELATED)
        .order_by("-updated_at")
    )
    return render(
        request,
        "assets/itassetmanagement/software_license/detail.html",
        {
            "license_obj": license_obj,
            "outbound_edges": outbound_edges,
            "inbound_edges": inbound_edges,
        },
    )


@login_required
def software_license_edit(request, pk):
    """Edit an unlocked software license record."""
    license_obj = assets_object(request, SoftwareLicense, pk)
    if license_obj.is_locked:
        messages.warning(
            request,
            f"Software License {license_obj.number} is retired and cannot be edited.",
        )
        return redirect("assets:software_license_detail", pk=license_obj.pk)
    if license_obj.status == "audit_hold" and not is_tenant_admin_user(request.user):
        raise PermissionDenied("Tenant administrator access required while license is on Audit Hold.")

    if request.method == "POST":
        form = SoftwareLicenseForm(request.POST, instance=license_obj, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                license_obj = form.save(commit=False)
                license_obj.status = license_obj.compute_compliance_status()
                license_obj.last_reconciled_at = timezone.now()
                license_obj.save()
                write_audit_log(request.user, license_obj, "update", tenant=request.tenant)
            messages.success(request, f"Software License {license_obj.number} updated.")
            return redirect("assets:software_license_detail", pk=license_obj.pk)
    else:
        form = SoftwareLicenseForm(instance=license_obj, tenant=request.tenant)

    return render(
        request,
        "assets/itassetmanagement/software_license/form.html",
        {
            "form": form,
            "license_obj": license_obj,
            "is_edit": True,
            "title": f"Edit {license_obj.number} — {license_obj.software_name}",
        },
    )


@tenant_admin_required
@require_POST
def software_license_delete(request, pk):
    """Delete an unlocked software license record (tenant admin only)."""
    license_obj = assets_object(request, SoftwareLicense, pk)
    if license_obj.is_locked:
        messages.warning(
            request,
            f"Software License {license_obj.number} is retired and cannot be deleted.",
        )
        return redirect("assets:software_license_detail", pk=license_obj.pk)
    number = license_obj.number
    with transaction.atomic():
        write_audit_log(request.user, license_obj, "delete", tenant=request.tenant)
        license_obj.delete()
    messages.success(request, f"Software License {number} deleted.")
    return redirect("assets:software_license_list")


@login_required
@require_POST
def software_license_sync_compliance(request, pk):
    """Recompute Effective License Position (ELP) status and reconciliation timestamp."""
    license_obj = assets_object(request, SoftwareLicense, pk)
    if license_obj.is_locked:
        messages.warning(request, f"Software License {license_obj.number} is retired.")
        return redirect("assets:software_license_detail", pk=license_obj.pk)
    if license_obj.status == "audit_hold" and not is_tenant_admin_user(request.user):
        raise PermissionDenied("Tenant administrator access required while license is on Audit Hold.")
    prev_status = license_obj.status
    with transaction.atomic():
        if license_obj.status == "audit_hold" and is_tenant_admin_user(request.user):
            license_obj.status = "draft"
        license_obj.status = license_obj.compute_compliance_status()
        license_obj.last_reconciled_at = timezone.now()
        license_obj.save(update_fields=["status", "last_reconciled_at", "updated_at"])
        write_audit_log(
            request.user,
            license_obj,
            "sync_elp",
            changes={"status": [prev_status, license_obj.status]},
            tenant=request.tenant,
        )
    messages.success(
        request,
        f"ELP reconciled for {license_obj.number}: {license_obj.get_status_display()}.",
    )
    return redirect("assets:software_license_detail", pk=license_obj.pk)


@login_required
@require_POST
def software_license_reclaim_inactive(request, pk):
    """Harvest reclaimable inactive seats from allocated quantity."""
    license_obj = assets_object(request, SoftwareLicense, pk)
    if license_obj.is_locked:
        messages.warning(request, f"Software License {license_obj.number} is retired.")
        return redirect("assets:software_license_detail", pk=license_obj.pk)
    if license_obj.status == "audit_hold" and not is_tenant_admin_user(request.user):
        raise PermissionDenied("Tenant administrator access required while license is on Audit Hold.")
    harvested = int(license_obj.reclaimable_inactive_count or 0)
    if harvested <= 0:
        messages.info(request, f"No inactive seats flagged for reclamation on {license_obj.number}.")
        return redirect("assets:software_license_detail", pk=license_obj.pk)
    prev_allocated = int(license_obj.allocated_quantity or 0)
    prev_reclaimable = int(license_obj.reclaimable_inactive_count or 0)
    prev_status = license_obj.status
    with transaction.atomic():
        license_obj.allocated_quantity = max(0, prev_allocated - harvested)
        license_obj.reclaimable_inactive_count = 0
        license_obj.status = license_obj.compute_compliance_status()
        license_obj.last_reconciled_at = timezone.now()
        license_obj.save(
            update_fields=[
                "allocated_quantity",
                "reclaimable_inactive_count",
                "status",
                "last_reconciled_at",
                "updated_at",
            ]
        )
        write_audit_log(
            request.user,
            license_obj,
            "reclaim",
            changes={
                "allocated_quantity": [prev_allocated, license_obj.allocated_quantity],
                "reclaimable_inactive_count": [prev_reclaimable, 0],
                "status": [prev_status, license_obj.status],
            },
            tenant=request.tenant,
        )
    messages.success(request, f"Reclaimed {harvested} inactive seat(s) on {license_obj.number}.")
    return redirect("assets:software_license_detail", pk=license_obj.pk)


@tenant_admin_required
@require_POST
def software_license_record_true_up(request, pk):
    """Expand entitled_quantity to resolve an under-licensed shortfall."""
    license_obj = assets_object(request, SoftwareLicense, pk)
    if license_obj.is_locked:
        messages.warning(request, f"Software License {license_obj.number} is retired.")
        return redirect("assets:software_license_detail", pk=license_obj.pk)
    shortfall = max(0, int(license_obj.allocated_quantity or 0) - int(license_obj.entitled_quantity or 0))
    if shortfall <= 0:
        messages.info(request, f"Software License {license_obj.number} has no entitlement shortfall.")
        return redirect("assets:software_license_detail", pk=license_obj.pk)
    prev_entitled = int(license_obj.entitled_quantity or 0)
    prev_status = license_obj.status
    with transaction.atomic():
        license_obj.entitled_quantity = int(license_obj.allocated_quantity)
        license_obj.status = license_obj.compute_compliance_status()
        license_obj.last_reconciled_at = timezone.now()
        license_obj.save(
            update_fields=[
                "entitled_quantity",
                "status",
                "last_reconciled_at",
                "updated_at",
            ]
        )
        write_audit_log(
            request.user,
            license_obj,
            "true_up",
            changes={
                "entitled_quantity": [prev_entitled, license_obj.entitled_quantity],
                "status": [prev_status, license_obj.status],
            },
            tenant=request.tenant,
        )
    messages.success(
        request,
        f"Recorded true-up of +{shortfall} entitlement(s) on {license_obj.number}.",
    )
    return redirect("assets:software_license_detail", pk=license_obj.pk)


@login_required
@require_POST
def software_license_renew_term(request, pk):
    """Advance software license renewal date by 12 months."""
    license_obj = assets_object(request, SoftwareLicense, pk)
    if license_obj.is_locked:
        messages.warning(request, f"Software License {license_obj.number} is retired.")
        return redirect("assets:software_license_detail", pk=license_obj.pk)
    if license_obj.status == "audit_hold" and not is_tenant_admin_user(request.user):
        raise PermissionDenied("Tenant administrator access required while license is on Audit Hold.")
    today = timezone.now().date()
    base_date = max(license_obj.renewal_date, today) if license_obj.renewal_date else today
    prev_renewal = license_obj.renewal_date.isoformat() if license_obj.renewal_date else None
    prev_status = license_obj.status
    with transaction.atomic():
        license_obj.renewal_date = add_months(base_date, 12)
        if license_obj.status == "expired":
            license_obj.status = "draft"
        license_obj.status = license_obj.compute_compliance_status(today=today)
        license_obj.last_reconciled_at = timezone.now()
        license_obj.save(
            update_fields=[
                "renewal_date",
                "status",
                "last_reconciled_at",
                "updated_at",
            ]
        )
        write_audit_log(
            request.user,
            license_obj,
            "renew",
            changes={
                "renewal_date": [prev_renewal, license_obj.renewal_date.isoformat()],
                "status": [prev_status, license_obj.status],
            },
            tenant=request.tenant,
        )
    messages.success(
        request,
        f"Renewed {license_obj.number} through {license_obj.renewal_date.isoformat()}.",
    )
    return redirect("assets:software_license_detail", pk=license_obj.pk)


@tenant_admin_required
@require_POST
def software_license_place_audit_hold(request, pk):
    """Place software license under vendor Audit Hold."""
    license_obj = assets_object(request, SoftwareLicense, pk)
    if license_obj.is_locked:
        messages.warning(request, f"Software License {license_obj.number} is retired.")
        return redirect("assets:software_license_detail", pk=license_obj.pk)
    prev_status = license_obj.status
    with transaction.atomic():
        license_obj.status = "audit_hold"
        license_obj.save(update_fields=["status", "updated_at"])
        write_audit_log(
            request.user,
            license_obj,
            "hold",
            changes={"status": [prev_status, "audit_hold"]},
            tenant=request.tenant,
        )
    messages.warning(request, f"Software License {license_obj.number} placed on Audit Hold.")
    return redirect("assets:software_license_detail", pk=license_obj.pk)


@tenant_admin_required
@require_POST
def software_license_retire(request, pk):
    """Retire a software license record."""
    license_obj = assets_object(request, SoftwareLicense, pk)
    if license_obj.is_locked:
        messages.warning(request, f"Software License {license_obj.number} is already retired.")
        return redirect("assets:software_license_detail", pk=license_obj.pk)
    prev_status = license_obj.status
    with transaction.atomic():
        license_obj.status = "retired"
        license_obj.retired_at = timezone.now()
        license_obj.save(update_fields=["status", "retired_at", "updated_at"])
        write_audit_log(
            request.user,
            license_obj,
            "retire",
            changes={"status": [prev_status, "retired"]},
            tenant=request.tenant,
        )
    messages.success(request, f"Software License {license_obj.number} retired.")
    return redirect("assets:software_license_detail", pk=license_obj.pk)
