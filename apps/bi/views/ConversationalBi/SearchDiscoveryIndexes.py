from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, F, Q
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.bi.forms.ConversationalBi.SearchDiscoveryIndexes import SearchDiscoveryIndexForm
from apps.bi.models.ConversationalBi.SearchDiscoveryIndexes import SearchDiscoveryIndex
from apps.bi.views._common import bi_object, bi_scope
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def search_discovery_index_list(request):
    qs = bi_scope(SearchDiscoveryIndex.objects.all(), request).select_related(
        "semantic_model", "dashboard", "report", "kpi", "warehouse_table", "glossary_term"
    )

    counts = qs.aggregate(
        total=Count("id"),
        verified=Count("id", filter=Q(is_verified=True)),
        featured=Count("id", filter=Q(is_featured=True)),
    )
    total_count = counts["total"] or 0
    verified_count = counts["verified"] or 0
    featured_count = counts["featured"] or 0

    # Search
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(asset_name__icontains=q)
            | Q(number__icontains=q)
            | Q(description__icontains=q)
            | Q(category__icontains=q)
            | Q(search_keywords__icontains=q)
            | Q(synonyms__icontains=q)
        )

    # Filters
    asset_type = request.GET.get("type", "").strip()
    if asset_type:
        qs = qs.filter(asset_type=asset_type)

    verified = request.GET.get("verified", "").strip()
    if verified == "1":
        qs = qs.filter(is_verified=True)
    elif verified == "0":
        qs = qs.filter(is_verified=False)

    featured = request.GET.get("featured", "").strip()
    if featured == "1":
        qs = qs.filter(is_featured=True)

    paginator = Paginator(qs, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "indexes": page_obj,
        "search_discovery_indexes": page_obj,
        "total_count": total_count,
        "verified_count": verified_count,
        "featured_count": featured_count,
        "type_choices": SearchDiscoveryIndex.ASSET_TYPE_CHOICES,
    }
    return render(
        request,
        "bi/conversational_bi/search_discovery_index/list.html",
        context,
    )


@login_required
def search_discovery_index_detail(request, pk):
    index = bi_object(request, SearchDiscoveryIndex, pk)
    synonyms_list = index.synonyms if isinstance(index.synonyms, list) else []

    context = {
        "index": index,
        "synonyms_list": synonyms_list,
    }
    return render(
        request,
        "bi/conversational_bi/search_discovery_index/detail.html",
        context,
    )


@login_required
def search_discovery_index_create(request):
    if request.method == "POST":
        form = SearchDiscoveryIndexForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                instance = form.save(commit=False)
                instance.tenant = request.tenant
                instance.save()
                form.save_m2m()

                write_audit_log(
                    user=request.user,
                    obj=instance,
                    action="create",
                    changes={"details": f"Registered search discovery index '{instance.asset_name}'"},
                    tenant=request.tenant,
                )
                messages.success(request, f"Search discovery index '{instance.number}' created successfully.")
                return redirect("bi:search_discovery_index_detail", pk=instance.pk)
    else:
        form = SearchDiscoveryIndexForm(tenant=request.tenant)

    return render(
        request,
        "bi/conversational_bi/search_discovery_index/form.html",
        {
            "form": form,
            "index": None,
            "is_edit": False,
        },
    )


@login_required
def search_discovery_index_edit(request, pk):
    index = bi_object(request, SearchDiscoveryIndex, pk)

    if request.method == "POST":
        form = SearchDiscoveryIndexForm(request.POST, instance=index, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                instance = form.save()

                write_audit_log(
                    user=request.user,
                    obj=instance,
                    action="update",
                    changes={"details": f"Updated search discovery index '{instance.number}'"},
                    tenant=request.tenant,
                )
                messages.success(request, f"Search discovery index '{instance.number}' updated.")
                return redirect("bi:search_discovery_index_detail", pk=instance.pk)
    else:
        form = SearchDiscoveryIndexForm(instance=index, tenant=request.tenant)

    return render(
        request,
        "bi/conversational_bi/search_discovery_index/form.html",
        {
            "form": form,
            "index": index,
            "is_edit": True,
        },
    )


@tenant_admin_required
@require_POST
def search_discovery_index_delete(request, pk):
    index = bi_object(request, SearchDiscoveryIndex, pk)
    num = index.number

    with transaction.atomic():
        write_audit_log(
            user=request.user,
            obj=index,
            action="delete",
            changes={"details": f"Deleted search discovery index {num}"},
            tenant=request.tenant,
        )
        index.delete()

    messages.success(request, f"Search discovery index '{num}' deleted.")
    return redirect("bi:search_discovery_index_list")


@login_required
@require_POST
def search_discovery_index_reweight(request, pk):
    index = bi_object(request, SearchDiscoveryIndex, pk)
    weight_val = request.POST.get("weight", "").strip()

    with transaction.atomic():
        if weight_val:
            try:
                new_weight = Decimal(weight_val)
                if not new_weight.is_finite():
                    raise InvalidOperation("Non-finite Decimal rejected")
                index.relevance_weight = max(Decimal("0.10"), min(Decimal("99.99"), new_weight))
            except (InvalidOperation, ValueError):
                index.relevance_weight = min(Decimal("99.99"), index.relevance_weight + Decimal("0.50"))
        else:
            index.relevance_weight = min(Decimal("99.99"), index.relevance_weight + Decimal("0.50"))

        index.save(update_fields=["relevance_weight", "updated_at"])

        write_audit_log(
            user=request.user,
            obj=index,
            action="reweight",
            changes={"details": f"Adjusted search boost relevance weight to {index.relevance_weight}"},
            tenant=request.tenant,
        )

    messages.success(request, f"Relevance weight for '{index.asset_name}' set to {index.relevance_weight}.")

    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER")
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect("bi:search_discovery_index_detail", pk=index.pk)


@login_required
def search_discovery_hub(request):
    search_query = request.GET.get("q", "").strip()
    base_qs = bi_scope(SearchDiscoveryIndex.objects.all(), request).select_related(
        "semantic_model", "dashboard", "report", "kpi", "warehouse_table", "glossary_term"
    )

    results = []
    result_count = 0
    if search_query:
        matched = base_qs.filter(
            Q(asset_name__icontains=search_query)
            | Q(number__icontains=search_query)
            | Q(description__icontains=search_query)
            | Q(category__icontains=search_query)
            | Q(search_keywords__icontains=search_query)
            | Q(synonyms__icontains=search_query)
        ).order_by("-is_featured", "-relevance_weight", "-view_count")

        result_count = matched.count()

        # Telemetry: Increment search_hit_count on top results
        top_ids = list(matched[:10].values_list("id", flat=True))
        if top_ids:
            with transaction.atomic():
                SearchDiscoveryIndex.objects.filter(id__in=top_ids).update(
                    search_hit_count=F("search_hit_count") + 1
                )
        results = matched[:24]

    categories = list(
        base_qs.exclude(category="").values_list("category", flat=True).distinct().order_by("category")
    )
    featured_assets = base_qs.filter(is_featured=True).order_by("-relevance_weight")[:8]

    context = {
        "search_query": search_query,
        "results": results,
        "result_count": result_count,
        "categories": categories,
        "featured_assets": featured_assets,
    }
    return render(
        request,
        "bi/conversational_bi/search_discovery_index/hub.html",
        context,
    )
