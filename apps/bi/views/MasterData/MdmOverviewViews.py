from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import render

from apps.bi.models.MasterData.MdmGoldenRecords import MdmGoldenRecord
from apps.bi.models.MasterData.MdmHierarchyNodes import MdmHierarchyNode
from apps.bi.models.MasterData.MdmReferenceCodes import MdmReferenceCode
from apps.bi.models.MasterData.MdmSurvivorshipRules import MdmSurvivorshipRule
from apps.bi.views._common import bi_scope


@login_required
def mdm_overview(request):
    all_golden = bi_scope(MdmGoldenRecord.objects.all(), request)
    all_rules = bi_scope(MdmSurvivorshipRule.objects.all(), request)
    all_nodes = bi_scope(MdmHierarchyNode.objects.all(), request)
    all_codes = bi_scope(MdmReferenceCode.objects.all(), request)

    total_golden_records = all_golden.count()
    total_rules = all_rules.count()
    total_hierarchy_nodes = all_nodes.count()
    total_reference_codes = all_codes.count()

    gold_tier_count = all_golden.filter(trust_tier="gold").count()
    pending_review_count = all_golden.filter(status="pending_review").count()

    domain_counts_raw = (
        all_golden.values("domain")
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    domain_map = dict(MdmGoldenRecord.DOMAIN_CHOICES)
    domain_distribution = [
        {"domain": d["domain"], "label": domain_map.get(d["domain"], d["domain"]), "count": d["count"]}
        for d in domain_counts_raw
    ]

    recent_golden_records = (
        all_golden.select_related("party", "assigned_steward")
        .order_by("-created_at")[:6]
    )

    survivorship_rules = all_rules.order_by("priority_order")[:5]

    root_hierarchies = (
        all_nodes.filter(parent__isnull=True)
        .select_related("golden_record", "party", "org_unit")
        .order_by("hierarchy_type", "sort_order")[:6]
    )

    code_set_counts = (
        all_codes.values("code_set")
        .annotate(count=Count("id"))
        .order_by("-count")[:8]
    )

    context = {
        "total_golden_records": total_golden_records,
        "total_rules": total_rules,
        "total_hierarchy_nodes": total_hierarchy_nodes,
        "total_reference_codes": total_reference_codes,
        "gold_tier_count": gold_tier_count,
        "pending_review_count": pending_review_count,
        "domain_distribution": domain_distribution,
        "recent_golden_records": recent_golden_records,
        "survivorship_rules": survivorship_rules,
        "root_hierarchies": root_hierarchies,
        "code_set_counts": code_set_counts,
    }
    return render(request, "bi/master_data/mdm_overview.html", context)
