from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import render

from apps.quality.models.SupplierQuality.SupplierQualificationAudits import (
    SupplierQualificationAudit,
)

PAGE_SIZE = 20


@login_required
def avl_directory(request):
    base_qs = SupplierQualificationAudit.objects.filter(tenant=request.tenant).select_related(
        "supplier", "lead_auditor", "quality_agreement"
    )

    # Aggregate key AVL Governance metrics in a single query
    metrics = base_qs.aggregate(
        active=Count("id", filter=Q(qualification_status="approved")),
        critical=Count("id", filter=Q(criticality_tier="critical")),
        dock_to_stock=Count("id", filter=Q(dock_to_stock_eligible=True)),
        pending_audits=Count("id", filter=Q(audit_result="pending")),
    )
    active_count = metrics["active"]
    critical_count = metrics["critical"]
    dock_to_stock_count = metrics["dock_to_stock"]
    pending_audits_count = metrics["pending_audits"]

    # Filterable table
    qs = base_qs
    search_query = request.GET.get("q", "").strip()
    if search_query:
        qs = qs.filter(
            Q(supplier__name__icontains=search_query)
            | Q(scope_commodities__icontains=search_query)
            | Q(number__icontains=search_query)
        )

    current_status = request.GET.get("status", "").strip()
    if current_status:
        qs = qs.filter(qualification_status=current_status)

    current_tier = request.GET.get("tier", "").strip()
    if current_tier:
        qs = qs.filter(criticality_tier=current_tier)

    paginator = Paginator(qs, PAGE_SIZE)
    page_number = request.GET.get("page")
    qualifications = paginator.get_page(page_number)

    context = {
        "qualifications": qualifications,
        "active_count": active_count,
        "critical_count": critical_count,
        "dock_to_stock_count": dock_to_stock_count,
        "pending_audits_count": pending_audits_count,
        "status_choices": SupplierQualificationAudit.QUALIFICATION_STATUS_CHOICES,
        "tier_choices": SupplierQualificationAudit.CRITICALITY_TIER_CHOICES,
        "search_query": search_query,
        "current_status": current_status,
        "current_tier": current_tier,
    }
    return render(
        request,
        "quality/supplierquality/avl_directory.html",
        context,
    )
