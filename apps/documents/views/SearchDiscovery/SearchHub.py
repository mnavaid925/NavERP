import csv
import hashlib
import json
import re
import time

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, F, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.core.utils import write_audit_log
from apps.documents.models.SearchDiscovery.DocumentSavedSearches import DocumentSavedSearch
from apps.documents.models.SearchDiscovery.DocumentSearchQueryLogs import DocumentSearchQueryLog
from apps.documents.models.SearchDiscovery.DocumentSearchSynonyms import DocumentSearchSynonym
from apps.documents.models.StorageRepository.DocumentFolders import DocumentFolder
from apps.documents.models.VersionControl.Documents import Document
from apps.documents.views._common import _csv_safe, safe_parse_date


def _parse_nlp_intents(query_text):
    """
    Extracts semantic intent tokens from conversational queries:
    e.g. 'type:contract', 'status:approved', 'classification:confidential', 'author:admin'
    """
    tokens = []
    clean_query = query_text
    nlp_patterns = [
        (r'\btype:([a-zA-Z0-9_\-]+)\b', 'document_type', 'Type'),
        (r'\bstatus:([a-zA-Z0-9_\-]+)\b', 'status', 'Status'),
        (r'\bclassification:([a-zA-Z0-9_\-]+)\b', 'classification', 'Classification'),
        (r'\bauthor:([a-zA-Z0-9_\-]+)\b', 'author_name', 'Author'),
    ]

    for pattern, key, label in nlp_patterns:
        match = re.search(pattern, clean_query, re.IGNORECASE)
        if match:
            val = match.group(1).lower()
            tokens.append({"key": key, "value": val, "label": f"{label}: {val}"})
            clean_query = re.sub(pattern, '', clean_query, flags=re.IGNORECASE).strip()

    return tokens, clean_query


@login_required
def search_hub(request):
    start_time = time.time()
    raw_query = request.GET.get("q", "").strip()

    # NLP Intent token parsing
    intent_chips, search_term = _parse_nlp_intents(raw_query)

    # Base queryset for current tenant
    qs = Document.objects.filter(tenant=request.tenant).select_related(
        "owner", "department"
    )

    synonyms_applied = []
    if search_term:
        query_words = [w.strip().lower() for w in search_term.split() if len(w.strip()) > 1]
        active_synonyms = DocumentSearchSynonym.objects.filter(
            tenant=request.tenant,
            is_active=True,
        )

        expansion_terms = set(query_words)
        matched_syn_ids = []
        for syn in active_synonyms:
            canonical_term = syn.term.lower().strip()
            syn_terms = [t.lower() for t in syn.get_all_terms()]
            matched = False
            for qw in query_words:
                if syn.is_bidirectional:
                    if qw in syn_terms:
                        matched = True
                        break
                else:
                    if qw == canonical_term:
                        matched = True
                        break
            if matched:
                expansion_terms.update(syn_terms)
                symbol = "↔" if syn.is_bidirectional else "→"
                synonyms_applied.append(f"{syn.term} {symbol} {syn.synonyms}")
                matched_syn_ids.append(syn.id)

        if matched_syn_ids:
            DocumentSearchSynonym.objects.filter(id__in=matched_syn_ids).update(hit_count=F("hit_count") + 1)

        # Build Q filter matching title, description, number, and version text
        text_q = Q()
        for term in expansion_terms:
            text_q |= (
                Q(title__icontains=term) |
                Q(description__icontains=term) |
                Q(number__icontains=term) |
                Q(versions__extracted_text__icontains=term)
            )
        qs = qs.filter(text_q).distinct()

    # Filter by NLP intent tokens
    for token in intent_chips:
        k, v = token["key"], token["value"]
        if k == "document_type":
            qs = qs.filter(document_type__iexact=v)
        elif k == "status":
            qs = qs.filter(status__iexact=v)
        elif k == "classification":
            qs = qs.filter(classification__iexact=v)
        elif k == "author_name":
            qs = qs.filter(owner__username__icontains=v)

    # Facet filter parameters
    selected_doc_type = request.GET.get("doc_type", "").strip()
    if selected_doc_type:
        qs = qs.filter(document_type=selected_doc_type)

    selected_classification = request.GET.get("classification", "").strip()
    if selected_classification:
        qs = qs.filter(classification=selected_classification)

    selected_status = request.GET.get("status", "").strip()
    if selected_status:
        qs = qs.filter(status=selected_status)

    selected_folder_id = request.GET.get("folder", "").strip()
    if selected_folder_id and selected_folder_id.isdigit():
        folder_obj = DocumentFolder.objects.filter(tenant=request.tenant, pk=int(selected_folder_id)).first()
        if folder_obj:
            if folder_obj.department_id:
                qs = qs.filter(department_id=folder_obj.department_id)
            else:
                qs = qs.filter(Q(tags__icontains=folder_obj.slug) | Q(description__icontains=folder_obj.name))

    selected_author_id = request.GET.get("author", "").strip()
    if selected_author_id and selected_author_id.isdigit():
        qs = qs.filter(owner_id=int(selected_author_id))

    date_from_str = request.GET.get("date_from", "").strip()
    date_from = safe_parse_date(date_from_str) if date_from_str else None
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)

    date_to_str = request.GET.get("date_to", "").strip()
    date_to = safe_parse_date(date_to_str) if date_to_str else None
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)

    # Sorting
    sort_by = request.GET.get("sort_by", "relevance")
    if sort_by == "updated_at_desc":
        qs = qs.order_by("-updated_at")
    elif sort_by == "created_at_desc":
        qs = qs.order_by("-created_at")
    elif sort_by == "title_asc":
        qs = qs.order_by("title")
    else:
        qs = qs.order_by("-updated_at")

    total_count = qs.count()
    duration_ms = int((time.time() - start_time) * 1000)

    # Log query execution telemetry if a query was submitted
    if raw_query or selected_doc_type or selected_classification or selected_status:
        try:
            filters_payload = {
                "doc_type": selected_doc_type,
                "classification": selected_classification,
                "status": selected_status,
                "folder": selected_folder_id,
                "author": selected_author_id,
                "date_from": date_from_str,
                "date_to": date_to_str,
            }
            DocumentSearchQueryLog.objects.create(
                tenant=request.tenant,
                query_text=raw_query or "(faceted search)",
                user=request.user,
                filters_applied_json=json.dumps(filters_payload),
                results_count=total_count,
                is_zero_result=(total_count == 0),
                execution_time_ms=duration_ms,
                search_source="search_hub",
                session_key=hashlib.sha256(request.session.session_key.encode("utf-8")).hexdigest()[:16] if (request.session and request.session.session_key) else "",
            )
        except Exception:
            pass  # Non-blocking telemetry log

    # Pagination
    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # Facet aggregations across tenant
    base_facets_qs = Document.objects.filter(tenant=request.tenant)
    if search_term:
        base_facets_qs = base_facets_qs.filter(text_q).distinct()

    doc_type_counts = dict(base_facets_qs.values("document_type").annotate(c=Count("id", distinct=True)).values_list("document_type", "c"))
    classification_counts = dict(base_facets_qs.values("classification").annotate(c=Count("id", distinct=True)).values_list("classification", "c"))
    status_counts = dict(base_facets_qs.values("status").annotate(c=Count("id", distinct=True)).values_list("status", "c"))

    facets = {
        "document_types": [
            {"value": val, "label": label, "count": doc_type_counts.get(val, 0), "selected": (selected_doc_type == val)}
            for val, label in Document.DOCUMENT_TYPE_CHOICES
        ],
        "classifications": [
            {"value": val, "label": label, "count": classification_counts.get(val, 0), "selected": (selected_classification == val)}
            for val, label in Document.CLASSIFICATION_CHOICES
        ],
        "statuses": [
            {"value": val, "label": label, "count": status_counts.get(val, 0), "selected": (selected_status == val)}
            for val, label in Document.STATUS_CHOICES
        ],
    }

    folders = DocumentFolder.objects.filter(tenant=request.tenant, is_active=True).order_by("path", "name")

    popular_searches = (
        DocumentSearchQueryLog.objects.filter(tenant=request.tenant, is_zero_result=False)
        .exclude(query_text="(faceted search)")
        .values("query_text")
        .annotate(c=Count("id"))
        .order_by("-c")[:6]
    )

    saved_searches = DocumentSavedSearch.objects.filter(
        tenant=request.tenant,
        is_active=True,
    ).filter(
        Q(owner=request.user) | Q(visibility="public")
    ).order_by("-is_pinned", "-updated_at")[:6]

    zero_result_suggestions = []
    if total_count == 0 and raw_query:
        # Suggest alternative synonyms or popular searches
        zero_result_suggestions.append("Check spelling of your search terms")
        zero_result_suggestions.append("Broaden criteria by removing specific facet filters")
        zero_result_suggestions.append("Try wildcard or partial keyword variations")

    active_filters = {
        "doc_type": selected_doc_type,
        "classification": selected_classification,
        "status": selected_status,
        "folder": selected_folder_id,
        "author": selected_author_id,
        "date_from": date_from_str,
        "date_to": date_to_str,
    }

    return render(
        request,
        "documents/search_discovery/search_hub.html",
        {
            "page_obj": page_obj,
            "results": page_obj.object_list,
            "total_count": total_count,
            "query_text": raw_query,
            "facets": facets,
            "folders": folders,
            "active_filters": active_filters,
            "intent_chips": intent_chips,
            "popular_searches": popular_searches,
            "saved_searches": saved_searches,
            "zero_result_suggestions": zero_result_suggestions,
            "synonyms_applied": synonyms_applied,
            "execution_time_ms": duration_ms,
            "sort_by": sort_by,
        },
    )


@login_required
def search_click_track(request, pk):
    doc = get_object_or_404(Document, pk=pk, tenant=request.tenant)
    rank = request.GET.get("rank")
    rank_int = int(rank) if (rank and rank.isdigit()) else None

    # Update latest query log for session with clicked document
    latest_log = (
        DocumentSearchQueryLog.objects.filter(
            tenant=request.tenant,
            user=request.user,
        )
        .order_by("-created_at")
        .first()
    )
    if latest_log:
        latest_log.clicked_document = doc
        latest_log.click_rank = rank_int
        latest_log.save(update_fields=["clicked_document", "click_rank"])

    return redirect("documents:document_detail", pk=doc.pk)


@login_required
def search_export_csv(request):
    raw_query = request.GET.get("q", "").strip()
    qs = Document.objects.filter(tenant=request.tenant).select_related(
        "owner", "department"
    )

    if raw_query:
        qs = qs.filter(
            Q(title__icontains=raw_query) |
            Q(description__icontains=raw_query) |
            Q(number__icontains=raw_query)
        )

    selected_doc_type = request.GET.get("doc_type", "").strip()
    if selected_doc_type:
        qs = qs.filter(document_type=selected_doc_type)

    selected_classification = request.GET.get("classification", "").strip()
    if selected_classification:
        qs = qs.filter(classification=selected_classification)

    selected_status = request.GET.get("status", "").strip()
    if selected_status:
        qs = qs.filter(status=selected_status)

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="search_results.csv"'
    writer = csv.writer(response)
    writer.writerow(["Number", "Title", "Document Type", "Classification", "Status", "Department", "Owner", "Created At"])

    for doc in qs[:500]:
        writer.writerow([
            _csv_safe(doc.number),
            _csv_safe(doc.title),
            _csv_safe(doc.get_document_type_display()),
            _csv_safe(doc.get_classification_display()),
            _csv_safe(doc.get_status_display()),
            _csv_safe(doc.department.name if doc.department else "General"),
            _csv_safe(doc.owner.username if doc.owner else ""),
            _csv_safe(doc.created_at.strftime("%Y-%m-%d %H:%M")),
        ])

    write_audit_log(request.user, qs.first() if qs.exists() else None, "export", tenant=request.tenant)
    return response
