from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.ecommerce.models.SearchDiscovery.SearchQueryLogs import SearchQueryLog
from apps.ecommerce.views._common import ecommerce_object, ecommerce_scope


@login_required
def searchquerylog_list(request):
    qs = ecommerce_scope(
        SearchQueryLog.objects.select_related("customer", "clicked_product"),
        request,
    )

    search_query = request.GET.get("q", "").strip()
    is_zero_result = request.GET.get("is_zero_result", "").strip()
    sort_order = request.GET.get("sort_order", "").strip()

    if search_query:
        qs = qs.filter(
            Q(number__icontains=search_query)
            | Q(query_text__icontains=search_query)
            | Q(normalized_query__icontains=search_query)
            | Q(redirected_to__icontains=search_query)
            | Q(session_key__icontains=search_query)
        )

    if is_zero_result in ("true", "1", "True"):
        qs = qs.filter(is_zero_result=True)
    elif is_zero_result in ("false", "0", "False"):
        qs = qs.filter(is_zero_result=False)

    if sort_order:
        qs = qs.filter(sort_order=sort_order)

    paginator = Paginator(qs, 25)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "logs": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "q": search_query,
        "selected_zero_result": is_zero_result,
        "selected_sort": sort_order,
    }
    return render(
        request, "ecommerce/searchdiscovery/querylog/list.html", context
    )


@login_required
def searchquerylog_detail(request, pk):
    log = ecommerce_object(
        request,
        SearchQueryLog,
        pk,
        select_related=("customer", "clicked_product"),
    )
    applied_filters_items = []
    if isinstance(log.applied_filters, dict):
        applied_filters_items = list(log.applied_filters.items())

    context = {
        "log": log,
        "applied_filters_items": applied_filters_items,
    }
    return render(
        request, "ecommerce/searchdiscovery/querylog/detail.html", context
    )


@login_required
@tenant_admin_required
@require_POST
def searchquerylog_delete(request, pk):
    log = ecommerce_object(request, SearchQueryLog, pk)
    number = log.number
    query_text = log.query_text
    log.delete()
    write_audit_log(
        request,
        action="delete",
        instance=log,
        notes=f"Deleted search query log {number} ('{query_text}')",
    )
    messages.success(request, f"Search log '{number}' deleted.")
    return redirect("ecommerce:searchquerylog_list")
