from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.shortcuts import render

from apps.ecommerce.models.B2bWholesale.B2bCompanyAccounts import B2bCompanyAccount
from apps.ecommerce.models.B2bWholesale.B2bCompanyUsers import B2bCompanyUser
from apps.ecommerce.models.B2bWholesale.B2bQuickOrderTemplates import B2bQuickOrderTemplate
from apps.ecommerce.models.B2bWholesale.B2bQuoteRequests import B2bQuoteRequest
from apps.ecommerce.views._common import ecommerce_scope


@login_required
def b2b_wholesale_hub(request):
    """Central operational command cockpit for B2B & Wholesale Commerce."""
    co_stats = ecommerce_scope(B2bCompanyAccount.objects.all(), request).aggregate(
        total_co=Count("id"),
        active_co=Count("id", filter=Q(status="active")),
        pending_co=Count("id", filter=Q(status="pending_review")),
        total_credit=Sum("credit_limit"),
        avail_credit=Sum("available_credit"),
    )

    rfq_stats = ecommerce_scope(B2bQuoteRequest.objects.all(), request).aggregate(
        open_rfqs=Count("id", filter=Q(status__in=["submitted", "under_review", "buyer_review"])),
        quoted_val=Sum("quoted_total", filter=Q(status__in=["quoted", "accepted", "converted_to_order"])),
    )

    templates_count = ecommerce_scope(
        B2bQuickOrderTemplate.objects.filter(is_active=True),
        request,
    ).count()

    buyers_count = ecommerce_scope(
        B2bCompanyUser.objects.filter(status="active"),
        request,
    ).count()

    recent_companies = ecommerce_scope(
        B2bCompanyAccount.objects.select_related("company_party", "primary_contact").order_by("-created_at"),
        request,
    )[:5]

    recent_quotes = ecommerce_scope(
        B2bQuoteRequest.objects.select_related("company", "requested_by", "currency").order_by("-created_at"),
        request,
    )[:5]

    context = {
        "total_companies_count": co_stats["total_co"] or 0,
        "active_companies_count": co_stats["active_co"] or 0,
        "pending_reviews_count": co_stats["pending_co"] or 0,
        "total_credit_granted": co_stats["total_credit"] or Decimal("0.00"),
        "available_credit_sum": co_stats["avail_credit"] or Decimal("0.00"),
        "open_rfqs_count": rfq_stats["open_rfqs"] or 0,
        "quoted_pipeline_value": rfq_stats["quoted_val"] or Decimal("0.00"),
        "active_templates_count": templates_count,
        "active_buyers_count": buyers_count,
        "recent_companies": recent_companies,
        "recent_quotes": recent_quotes,
    }
    return render(request, "ecommerce/b2b_wholesale/b2b_wholesale_hub.html", context)
