from decimal import Decimal
import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, F, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.bi.forms.DataCatalog.CatalogAssets import (
    CatalogAssetForm,
    CatalogAssetCertifyForm,
    CatalogAssetDeprecateForm,
)
from apps.bi.models.DataCatalog.CatalogAssets import CatalogAsset
from apps.bi.views._common import bi_object, bi_scope
from apps.core.utils import write_audit_log


@login_required
def catalog_asset_list(request):
    queryset = (
        bi_scope(CatalogAsset.objects.all(), request)
        .select_related("data_steward", "owning_org_unit")
    )

    q = request.GET.get("q", "").strip()[:100]
    if q:
        queryset = queryset.filter(
            Q(name__icontains=q)
            | Q(code__icontains=q)
            | Q(number__icontains=q)
            | Q(description__icontains=q)
        )

    domain_filter = request.GET.get("domain", "").strip()
    if domain_filter:
        queryset = queryset.filter(domain=domain_filter)

    asset_type_filter = request.GET.get("asset_type", "").strip()
    if asset_type_filter:
        queryset = queryset.filter(asset_type=asset_type_filter)

    sensitivity_filter = request.GET.get("sensitivity", "").strip()
    if sensitivity_filter:
        queryset = queryset.filter(data_sensitivity=sensitivity_filter)

    tier_filter = request.GET.get("tier", "").strip()
    if tier_filter:
        queryset = queryset.filter(enterprise_tier=tier_filter)

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        queryset = queryset.filter(certification_status=status_filter)

    all_tenant_records = bi_scope(CatalogAsset.objects.all(), request)
    counts = all_tenant_records.aggregate(
        total=Count("id"),
        certified=Count("id", filter=Q(certification_status="certified")),
        tier1=Count("id", filter=Q(enterprise_tier="tier_1_mission_critical")),
        restricted=Count(
            "id",
            filter=Q(data_sensitivity__in=["restricted_pii", "highly_sensitive_pci_phi"]),
        ),
    )
    total_count = counts["total"] or 0
    certified_count = counts["certified"] or 0
    tier1_count = counts["tier1"] or 0
    restricted_count = counts["restricted"] or 0

    paginator = Paginator(queryset.order_by("-created_at"), 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "assets": page_obj,
        "domain_choices": CatalogAsset.DOMAIN_CHOICES,
        "asset_type_choices": CatalogAsset.ASSET_TYPE_CHOICES,
        "sensitivity_choices": CatalogAsset.SENSITIVITY_CHOICES,
        "tier_choices": CatalogAsset.TIER_CHOICES,
        "certification_status_choices": CatalogAsset.CERTIFICATION_STATUS_CHOICES,
        "total_count": total_count,
        "certified_count": certified_count,
        "tier1_count": tier1_count,
        "restricted_count": restricted_count,
    }
    return render(request, "bi/data_catalog/catalog_asset/list.html", context)


@login_required
def catalog_asset_detail(request, pk):
    asset = bi_object(
        request,
        CatalogAsset,
        pk,
        select_related=(
            "data_steward",
            "owning_org_unit",
            "warehouse_table",
            "semantic_model",
            "golden_record",
            "business_glossary_term",
            "quality_scorecard",
            "deprecation_replacement",
        ),
    )

    CatalogAsset.objects.filter(pk=asset.pk).update(view_count=F("view_count") + 1)
    asset.refresh_from_db(fields=["view_count"])

    upstream_lineage = asset.upstream_edges.select_related("upstream_asset").filter(is_active=True).order_by("impact_criticality")
    downstream_lineage = asset.downstream_edges.select_related("downstream_asset").filter(is_active=True).order_by("impact_criticality")
    endorsements = asset.endorsements.select_related("attested_by").filter(is_active=True).order_by("-attested_at")

    schema_columns = asset.schema_columns_json or []
    search_tags = asset.search_tags_json or []

    certify_form = CatalogAssetCertifyForm(initial={"certification_status": asset.certification_status})
    deprecate_form = CatalogAssetDeprecateForm(tenant=request.tenant, current_asset=asset)

    context = {
        "asset": asset,
        "schema_columns": schema_columns,
        "search_tags": search_tags,
        "upstream_lineage": upstream_lineage,
        "downstream_lineage": downstream_lineage,
        "endorsements": endorsements,
        "replacement_asset": asset.deprecation_replacement,
        "certify_form": certify_form,
        "deprecate_form": deprecate_form,
    }
    return render(request, "bi/data_catalog/catalog_asset/detail.html", context)


@login_required
def catalog_asset_create(request):
    if request.method == "POST":
        form = CatalogAssetForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            asset = form.save(commit=False)
            asset.tenant = request.tenant
            asset.save()
            write_audit_log(
                request.user,
                "create",
                asset,
                f"Registered catalog asset {asset.number} ({asset.name})",
                tenant=request.tenant,
            )
            messages.success(request, f"Catalog asset {asset.number} registered successfully.")
            return redirect("bi:catalog_asset_detail", pk=asset.pk)
    else:
        form = CatalogAssetForm(tenant=request.tenant)

    context = {
        "form": form,
        "asset": None,
        "is_edit": False,
    }
    return render(request, "bi/data_catalog/catalog_asset/form.html", context)


@login_required
def catalog_asset_edit(request, pk):
    asset = bi_object(request, CatalogAsset, pk)
    if request.method == "POST":
        form = CatalogAssetForm(request.POST, instance=asset, tenant=request.tenant)
        if form.is_valid():
            asset = form.save()
            write_audit_log(
                request.user,
                "update",
                asset,
                f"Updated catalog asset {asset.number} ({asset.name})",
                tenant=request.tenant,
            )
            messages.success(request, f"Catalog asset {asset.number} updated successfully.")
            return redirect("bi:catalog_asset_detail", pk=asset.pk)
    else:
        form = CatalogAssetForm(instance=asset, tenant=request.tenant)

    context = {
        "form": form,
        "asset": asset,
        "is_edit": True,
    }
    return render(request, "bi/data_catalog/catalog_asset/form.html", context)


@login_required
@require_POST
def catalog_asset_delete(request, pk):
    asset = bi_object(request, CatalogAsset, pk)
    asset_number = asset.number
    asset.delete()
    write_audit_log(
        request.user,
        "delete",
        asset,
        f"Deleted catalog asset {asset_number}",
        tenant=request.tenant,
    )
    messages.success(request, f"Catalog asset {asset_number} was deleted.")
    return redirect("bi:catalog_asset_list")


@login_required
@require_POST
def catalog_asset_certify(request, pk):
    asset = bi_object(request, CatalogAsset, pk)
    form = CatalogAssetCertifyForm(request.POST)
    if form.is_valid():
        new_status = form.cleaned_data["certification_status"]
        notes = form.cleaned_data.get("certification_notes", "")
        old_status = asset.certification_status
        asset.certification_status = new_status
        asset.save(update_fields=["certification_status", "updated_at"])
        write_audit_log(
            request.user,
            "status_change",
            asset,
            f"Changed certification from {old_status} to {new_status}. Notes: {notes}",
            tenant=request.tenant,
        )
        messages.success(request, f"Asset certification status updated to {asset.get_certification_status_display()}.")
    else:
        messages.error(request, "Invalid certification parameters.")
    return redirect("bi:catalog_asset_detail", pk=asset.pk)


@login_required
@require_POST
def catalog_asset_deprecate(request, pk):
    asset = bi_object(request, CatalogAsset, pk)
    form = CatalogAssetDeprecateForm(request.POST, tenant=request.tenant, current_asset=asset)
    if form.is_valid():
        replacement = form.cleaned_data.get("deprecation_replacement")
        reason = form.cleaned_data["deprecation_reason"]
        asset.certification_status = "deprecated"
        asset.deprecation_replacement = replacement
        asset.save(update_fields=["certification_status", "deprecation_replacement", "updated_at"])
        write_audit_log(
            request.user,
            "deprecate",
            asset,
            f"Marked asset deprecated. Replacement: {replacement.number if replacement else 'None'}. Reason: {reason}",
            tenant=request.tenant,
        )
        messages.warning(request, f"Asset {asset.number} has been marked deprecated.")
    else:
        messages.error(request, "Invalid deprecation submission. Please provide a reason.")
    return redirect("bi:catalog_asset_detail", pk=asset.pk)
