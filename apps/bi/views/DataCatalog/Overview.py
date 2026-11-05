from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import render

from apps.bi.models.DataCatalog.CatalogAssets import CatalogAsset
from apps.bi.models.DataCatalog.CatalogLineageEdges import CatalogLineageEdge
from apps.bi.models.DataCatalog.DataGovernancePolicies import DataGovernancePolicy
from apps.bi.models.DataCatalog.CatalogTrustEndorsements import CatalogTrustEndorsement
from apps.bi.views._common import bi_scope


@login_required
def catalog_overview(request):
    assets_qs = bi_scope(CatalogAsset.objects.all(), request).filter(is_active=True)
    edges_qs = bi_scope(CatalogLineageEdge.objects.all(), request).filter(is_active=True)
    policies_qs = bi_scope(DataGovernancePolicy.objects.all(), request).filter(is_active=True)
    endorsements_qs = bi_scope(CatalogTrustEndorsement.objects.all(), request).filter(is_active=True)

    asset_counts = assets_qs.aggregate(
        total=Count("id"),
        certified=Count("id", filter=Q(certification_status="certified")),
        tier1=Count("id", filter=Q(enterprise_tier="tier_1_mission_critical")),
    )
    total_assets = asset_counts["total"] or 0
    certified_assets_count = asset_counts["certified"] or 0
    tier1_assets_count = asset_counts["tier1"] or 0

    edge_counts = edges_qs.aggregate(
        total=Count("id"),
        col_count=Count("id", filter=Q(lineage_type="column_level")),
    )
    total_lineage_edges = edge_counts["total"] or 0
    column_lineage_count = edge_counts["col_count"] or 0

    policy_counts = policies_qs.aggregate(
        total=Count("id"),
        strict=Count("id", filter=Q(enforcement_level="strict_blocking")),
    )
    total_policies = policy_counts["total"] or 0
    strict_policies_count = policy_counts["strict"] or 0

    total_endorsements = endorsements_qs.count()

    recent_assets = (
        assets_qs.select_related("data_steward", "owning_org_unit")
        .order_by("-created_at")[:6]
    )
    recent_edges = (
        edges_qs.select_related("upstream_asset", "downstream_asset")
        .order_by("-created_at")[:5]
    )
    recent_policies = (
        policies_qs.select_related("policy_owner")
        .order_by("-created_at")[:5]
    )
    recent_endorsements = (
        endorsements_qs.select_related("asset", "attested_by")
        .order_by("-attested_at")[:5]
    )

    domain_counts_raw = (
        assets_qs.values("domain")
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    domain_map = dict(CatalogAsset.DOMAIN_CHOICES)
    domain_distribution = [
        {
            "domain": d["domain"],
            "label": domain_map.get(d["domain"], d["domain"]),
            "count": d["count"],
            "pct": round((d["count"] / total_assets) * 100, 1) if total_assets > 0 else 0,
        }
        for d in domain_counts_raw
    ]

    sensitivity_counts_raw = (
        assets_qs.values("data_sensitivity")
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    sensitivity_map = dict(CatalogAsset.SENSITIVITY_CHOICES)
    sensitivity_distribution = [
        {
            "sensitivity": s["data_sensitivity"],
            "label": sensitivity_map.get(s["data_sensitivity"], s["data_sensitivity"]),
            "count": s["count"],
            "pct": round((s["count"] / total_assets) * 100, 1) if total_assets > 0 else 0,
        }
        for s in sensitivity_counts_raw
    ]

    context = {
        "total_assets": total_assets,
        "certified_assets_count": certified_assets_count,
        "tier1_assets_count": tier1_assets_count,
        "total_lineage_edges": total_lineage_edges,
        "column_lineage_count": column_lineage_count,
        "total_policies": total_policies,
        "strict_policies_count": strict_policies_count,
        "total_endorsements": total_endorsements,
        "recent_assets": recent_assets,
        "recent_edges": recent_edges,
        "recent_policies": recent_policies,
        "recent_endorsements": recent_endorsements,
        "domain_distribution": domain_distribution,
        "sensitivity_distribution": sensitivity_distribution,
    }
    return render(request, "bi/data_catalog/catalog_overview.html", context)
