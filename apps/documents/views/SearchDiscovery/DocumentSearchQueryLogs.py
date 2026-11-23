from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.documents.models.SearchDiscovery.DocumentSearchQueryLogs import DocumentSearchQueryLog
from apps.documents.views._common import documents_object, documents_scope


@login_required
@tenant_admin_required
def document_search_query_log_list(request):
    qs = documents_scope(DocumentSearchQueryLog.objects.all(), request).select_related(
        "user", "clicked_document"
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(query_text__icontains=q) | Q(number__icontains=q))

    source = request.GET.get("search_source", "").strip()
    if source:
        qs = qs.filter(search_source=source)

    zero_result = request.GET.get("zero_result", "").strip()
    if zero_result == "1":
        qs = qs.filter(is_zero_result=True)
    elif zero_result == "0":
        qs = qs.filter(is_zero_result=False)

    user_id = request.GET.get("user", "").strip()
    if user_id and user_id.isdigit():
        qs = qs.filter(user_id=int(user_id))

    counts = qs.aggregate(
        total=Count("id"),
        zero_result=Count("id", filter=Q(is_zero_result=True)),
    )
    total_count = counts["total"] or 0
    zero_result_count = counts["zero_result"] or 0

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "documents/search_discovery/document_search_query_log/list.html",
        {
            "page_obj": page_obj,
            "query_logs": page_obj.object_list,
            "total_count": total_count,
            "zero_result_count": zero_result_count,
            "source_choices": DocumentSearchQueryLog.SOURCE_CHOICES,
        },
    )


@login_required
@tenant_admin_required
def document_search_query_log_detail(request, pk):
    query_log = documents_object(
        request,
        DocumentSearchQueryLog,
        pk,
        select_related=("user", "clicked_document"),
    )
    parsed_filters = query_log.get_filters_dict()

    return render(
        request,
        "documents/search_discovery/document_search_query_log/detail.html",
        {
            "query_log": query_log,
            "parsed_filters": parsed_filters,
        },
    )


@login_required
@tenant_admin_required
@require_POST
def document_search_query_log_delete(request, pk):
    query_log = documents_object(request, DocumentSearchQueryLog, pk)
    num = query_log.number
    write_audit_log(request.user, query_log, "delete", tenant=request.tenant)
    query_log.delete()
    messages.success(request, f"Search log record '{num}' deleted.")
    return redirect("documents:document_search_query_log_list")


@login_required
@tenant_admin_required
def document_search_analytics(request):
    base_qs = documents_scope(DocumentSearchQueryLog.objects.all(), request)

    stats = base_qs.aggregate(
        total=Count("id"),
        zero_results=Count("id", filter=Q(is_zero_result=True)),
        avg_latency=Avg("execution_time_ms"),
    )
    total_searches = stats["total"] or 0
    zero_result_searches = stats["zero_results"] or 0

    if total_searches > 0:
        zero_result_rate = round((zero_result_searches / total_searches) * 100, 1)
    else:
        zero_result_rate = 0.0

    avg_latency = stats["avg_latency"]
    avg_latency_ms = round(avg_latency, 1) if avg_latency else 0.0

    # Top popular successful queries
    top_queries = (
        base_qs.filter(is_zero_result=False)
        .values("query_text")
        .annotate(count=Count("id"))
        .order_by("-count")[:10]
    )

    # Top zero-result queries (content gap identification)
    zero_result_queries = (
        base_qs.filter(is_zero_result=True)
        .values("query_text")
        .annotate(count=Count("id"))
        .order_by("-count")[:10]
    )

    # Distribution by search source
    source_counts = (
        base_qs.values("search_source")
        .annotate(count=Count("id"))
        .order_by("-count")
    )

    return render(
        request,
        "documents/search_discovery/document_search_query_log/analytics.html",
        {
            "total_searches": total_searches,
            "zero_result_searches": zero_result_searches,
            "zero_result_rate": zero_result_rate,
            "avg_latency_ms": avg_latency_ms,
            "top_queries": top_queries,
            "zero_result_queries": zero_result_queries,
            "source_breakdown": source_counts,
        },
    )
