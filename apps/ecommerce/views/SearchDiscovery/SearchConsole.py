import time
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db import models
from django.db.models import Avg, Count, F, Min, Q
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from apps.core.utils import write_audit_log
from apps.ecommerce.models.ProductCatalog.CatalogProducts import CatalogProduct
from apps.ecommerce.models.ProductCatalog.ProductVariants import ProductVariant
from apps.ecommerce.models.ProductCatalog.StoreCategories import StoreCategory
from apps.ecommerce.models.SearchDiscovery.SearchFacetConfigs import SearchFacetConfig
from apps.ecommerce.models.SearchDiscovery.SearchMerchandisingRules import SearchMerchandisingRule
from apps.ecommerce.models.SearchDiscovery.SearchQueryLogs import SearchQueryLog
from apps.ecommerce.models.SearchDiscovery.SearchSynonyms import SearchSynonym
from apps.ecommerce.views._common import ecommerce_scope


@login_required
def search_console(request):
    start_time = time.time()
    tenant = request.tenant
    now = timezone.now()

    q = request.GET.get("q", "").strip()
    category_id = request.GET.get("category", "").strip()
    brand_filter = request.GET.get("brand", "").strip()
    price_min = request.GET.get("price_min", "").strip()
    price_max = request.GET.get("price_max", "").strip()
    in_stock_only = request.GET.get("in_stock", "").strip()
    sort_order = request.GET.get("sort", "relevance").strip()

    sort_choices = [
        ("relevance", "Most Relevant"),
        ("price_asc", "Price: Low to High"),
        ("price_desc", "Price: High to Low"),
        ("newest", "Newest Arrivals"),
        ("rating", "Customer Rating"),
    ]

    applied_synonyms = []
    applied_merchandising_rules = []
    promotional_banners = []
    redirect_url = ""
    query_logged = False

    # Check for direct redirect rules if query given
    if q:
        norm_q = q.lower()
        schedule_q = (
            (Q(start_date__isnull=True) | Q(start_date__lte=now))
            & (Q(end_date__isnull=True) | Q(end_date__gte=now))
        )
        redirect_rule = (
            SearchMerchandisingRule.objects.filter(
                tenant=tenant,
                is_active=True,
                action_type="redirect",
            )
            .filter(schedule_q)
            .filter(
                Q(match_type="exact", trigger_query__iexact=norm_q)
                | Q(match_type="contains", trigger_query__icontains=norm_q)
                | Q(match_type="starts_with", trigger_query__istartswith=norm_q)
            )
            .order_by("-priority")
            .first()
        )
        if redirect_rule and redirect_rule.redirect_url:
            redirect_url = redirect_rule.redirect_url
            applied_merchandising_rules.append(redirect_rule)
            # Log the redirected search query
            latency_ms = int((time.time() - start_time) * 1000)
            SearchQueryLog.objects.create(
                tenant=tenant,
                query_text=q,
                normalized_query=norm_q,
                results_count=0,
                is_zero_result=False,
                execution_time_ms=latency_ms,
                redirected_to=redirect_url,
                sort_order=sort_order,
                session_key=request.session.session_key or "",
            )
            query_logged = True
            # In console workbench, we can show the redirect notice or forward if user clicked
            if request.GET.get("auto_redirect") == "1":
                if url_has_allowed_host_and_scheme(
                    url=redirect_url,
                    allowed_hosts={request.get_host()},
                    require_https=request.is_secure(),
                ):
                    return redirect(redirect_url)

    # Base products queryset
    base_qs = (
        CatalogProduct.objects.filter(tenant=tenant, status="active")
        .select_related("primary_category", "item")
        .prefetch_related("variants")
    )

    # 1. Apply Synonym Expansions
    expanded_terms = [q] if q else []
    if q:
        norm_q = q.lower()
        active_synonyms = SearchSynonym.objects.filter(
            tenant=tenant, is_active=True
        ).filter(
            Q(root_term=norm_q) | Q(synonyms__icontains=norm_q)
        )
        matched_ids = []
        for syn in active_synonyms:
            syn_terms = syn.get_synonym_list()
            is_matched = False
            if syn.synonym_type == "two_way":
                if norm_q == syn.root_term or norm_q in syn_terms:
                    is_matched = True
                    expanded_terms.append(syn.root_term)
                    expanded_terms.extend(syn_terms)
            elif syn.synonym_type == "one_way":
                if norm_q == syn.root_term:
                    is_matched = True
                    expanded_terms.extend(syn_terms)
            elif syn.synonym_type == "replacement":
                if norm_q == syn.root_term and syn_terms:
                    is_matched = True
                    expanded_terms = [syn_terms[0]]

            if is_matched:
                applied_synonyms.append(syn)
                matched_ids.append(syn.pk)

        if matched_ids:
            SearchSynonym.objects.filter(id__in=matched_ids).update(
                hit_count=F("hit_count") + 1
            )

    # Deduplicate expanded terms
    expanded_terms = list(dict.fromkeys([t.strip().lower() for t in expanded_terms if t.strip()]))

    # 2. Text Search Matching
    if expanded_terms:
        search_filter = Q()
        for term in expanded_terms:
            search_filter |= (
                Q(name__icontains=term)
                | Q(number__icontains=term)
                | Q(item__sku__icontains=term)
                | Q(variants__sku__icontains=term)
                | Q(description__icontains=term)
                | Q(primary_category__name__icontains=term)
            )
        base_qs = base_qs.filter(search_filter).distinct()

    # 3. Dynamic Facet Filters
    active_filters = {}
    if category_id and category_id.isdigit():
        base_qs = base_qs.filter(
            Q(primary_category_id=int(category_id))
            | Q(categories__id=int(category_id))
        ).distinct()
        active_filters["category"] = category_id

    if brand_filter:
        base_qs = base_qs.filter(brand__iexact=brand_filter)
        active_filters["brand"] = brand_filter

    if price_min:
        try:
            min_val = Decimal(price_min)
            if min_val.is_finite() and min_val >= Decimal("0"):
                base_qs = base_qs.filter(variants__price__gte=min_val).distinct()
                active_filters["price_min"] = price_min
        except (ValueError, ArithmeticError):
            pass

    if price_max:
        try:
            max_val = Decimal(price_max)
            if max_val.is_finite() and max_val >= Decimal("0"):
                base_qs = base_qs.filter(variants__price__lte=max_val).distinct()
                active_filters["price_max"] = price_max
        except (ValueError, ArithmeticError):
            pass

    if in_stock_only in ("1", "true"):
        base_qs = base_qs.filter(is_digital=False)
        active_filters["in_stock"] = "1"

    # Compute Facet Groups for sidebar
    facet_configs = SearchFacetConfig.objects.filter(tenant=tenant, is_active=True).order_by(
        "display_order"
    )
    facet_groups = []
    for fc in facet_configs:
        if fc.source_type == "category":
            continue
        group = {
            "config": fc,
            "items": [],
        }
        if fc.source_type == "brand":
            brands = (
                CatalogProduct.objects.filter(tenant=tenant, status="active")
                .exclude(brand="")
                .values("brand")
                .annotate(prod_count=Count("id"))
                .order_by("-prod_count")[: fc.max_values_shown]
            )
            group["items"] = [
                {"value": b["brand"], "label": b["brand"], "count": b["prod_count"]}
                for b in brands
            ]
        elif fc.source_type == "availability":
            group["items"] = [
                {"value": "1", "label": "In Stock Only", "count": ""},
            ]
        elif fc.source_type == "variant_option" and fc.option_key:
            variant_options = ProductVariant.objects.filter(
                tenant=tenant,
                product__in=base_qs,
            ).values_list("option_values", flat=True)
            counts = {}
            for ov in variant_options:
                if isinstance(ov, dict):
                    val = ov.get(fc.option_key)
                    if val is not None and val != "":
                        str_val = str(val)
                        counts[str_val] = counts.get(str_val, 0) + 1
            sorted_options = sorted(counts.items(), key=lambda x: (-x[1], x[0]))[: fc.max_values_shown]
            group["items"] = [
                {"value": opt_val, "label": opt_val, "count": opt_cnt}
                for opt_val, opt_cnt in sorted_options
            ]
        for itm in group["items"]:
            itm["is_selected"] = (active_filters.get(fc.code) == str(itm["value"]))
        facet_groups.append(group)

    # 4. Merchandising Rules Evaluation (Boost, Bury, Pin, Block, Banner)
    blocked_product_ids = set()
    pin_rules = []
    score_modifiers = {}  # product_id -> int score modifier

    active_rules = (
        SearchMerchandisingRule.objects.filter(tenant=tenant, is_active=True)
        .filter(
            (Q(start_date__isnull=True) | Q(start_date__lte=now))
            & (Q(end_date__isnull=True) | Q(end_date__gte=now))
        )
        .select_related("boosted_product__item", "boosted_product__primary_category")
        .prefetch_related("boosted_product__variants")
        .order_by("-priority")
    )

    for rule in active_rules:
        is_triggered = False
        if rule.rule_type == "global":
            is_triggered = True
        elif rule.rule_type == "query" and q:
            norm_q = q.lower()
            t_query = rule.trigger_query.lower()
            if rule.match_type == "exact" and norm_q == t_query:
                is_triggered = True
            elif rule.match_type == "contains" and t_query in norm_q:
                is_triggered = True
            elif rule.match_type == "starts_with" and norm_q.startswith(t_query):
                is_triggered = True
        elif rule.rule_type == "category" and category_id and category_id.isdigit():
            if rule.target_category_id == int(category_id):
                is_triggered = True

        if is_triggered:
            applied_merchandising_rules.append(rule)
            if rule.action_type == "banner":
                promotional_banners.append(rule)
            elif rule.action_type == "block" and rule.boosted_product_id:
                blocked_product_ids.add(rule.boosted_product_id)
            elif rule.action_type == "pin" and rule.boosted_product_id and rule.pin_position:
                pin_rules.append((rule.pin_position, rule.boosted_product))
            elif rule.action_type in ("boost", "bury") and rule.boosted_product_id:
                score_modifiers[rule.boosted_product_id] = (
                    score_modifiers.get(rule.boosted_product_id, 0) + rule.boost_weight
                )

    # Exclude blocked products
    if blocked_product_ids:
        base_qs = base_qs.exclude(id__in=blocked_product_ids)

    # 5. Sorting
    if sort_order == "price_asc":
        product_list = list(
            base_qs.annotate(min_price=Min("variants__price")).order_by("min_price")[:100]
        )
    elif sort_order == "price_desc":
        product_list = list(
            base_qs.annotate(min_price=Min("variants__price")).order_by("-min_price")[:100]
        )
    elif sort_order == "newest":
        product_list = list(base_qs.order_by("-created_at").distinct()[:100])
    else:
        # Default relevance sorting with merchandising score adjustments
        raw_products = list(base_qs.distinct()[:100])
        # Sort key: modified score descending
        product_list = sorted(
            raw_products,
            key=lambda p: score_modifiers.get(p.id, 0),
            reverse=True,
        )

    # 6. Apply Pinned Products to Fixed Slots (1-indexed)
    pin_rules.sort(key=lambda item: item[0])
    for slot_idx, pinned_prod in pin_rules:
        if pinned_prod and pinned_prod.status == "active":
            # Avoid duplicate if product already in list
            product_list = [p for p in product_list if p.id != pinned_prod.id]
            insert_idx = max(0, slot_idx - 1)
            if insert_idx < len(product_list):
                product_list.insert(insert_idx, pinned_prod)
            else:
                product_list.append(pinned_prod)

    total_results = len(product_list)
    latency_ms = int((time.time() - start_time) * 1000)

    # 7. Fallback Recommendations on Zero Results
    fallback_recommendations = []
    if total_results == 0 and q:
        fallback_recommendations = list(
            CatalogProduct.objects.filter(tenant=tenant, status="active")
            .select_related("item", "primary_category")
            .prefetch_related("variants")
            .order_by("-created_at")[:4]
        )

    # 8. Log Search Query Telemetry
    if q and not query_logged:
        user_party = getattr(request.user, "party", None) if hasattr(request.user, "party") else None
        customer_party = (
            user_party
            if (user_party and getattr(user_party, "tenant_id", None) == tenant.pk)
            else None
        )
        SearchQueryLog.objects.create(
            tenant=tenant,
            query_text=q,
            normalized_query=q.lower(),
            results_count=total_results,
            is_zero_result=(total_results == 0),
            execution_time_ms=latency_ms,
            applied_filters=active_filters,
            sort_order=sort_order,
            session_key=request.session.session_key or "",
            customer=customer_party,
            ip_address=request.META.get("REMOTE_ADDR"),
        )

    all_categories = StoreCategory.objects.filter(tenant=tenant, is_active=True)

    context = {
        "q": q,
        "products": product_list,
        "total_results": total_results,
        "execution_time_ms": latency_ms,
        "facet_groups": facet_groups,
        "active_filters": active_filters,
        "applied_synonyms": applied_synonyms,
        "applied_merchandising_rules": applied_merchandising_rules,
        "promotional_banners": promotional_banners,
        "redirect_url": redirect_url,
        "categories": all_categories,
        "sort_order": sort_order,
        "sort_choices": sort_choices,
        "fallback_recommendations": fallback_recommendations,
    }
    return render(
        request, "ecommerce/searchdiscovery/console/console.html", context
    )


@login_required
def search_autocomplete(request):
    """Instant search-as-you-type endpoint returning top matching products & suggestions."""
    q = request.GET.get("q", "").strip()
    if not q or len(q) < 2:
        return JsonResponse({"products": [], "categories": [], "suggestions": []})

    tenant = request.tenant
    norm_q = q.lower()

    # Search products
    raw_products = list(
        CatalogProduct.objects.filter(
            tenant=tenant,
            status="active",
        )
        .filter(
            Q(name__icontains=norm_q)
            | Q(number__icontains=norm_q)
            | Q(item__sku__icontains=norm_q)
            | Q(variants__sku__icontains=norm_q)
        )
        .select_related("item")
        .prefetch_related("variants")
        .distinct()[:5]
    )
    products = []
    for p in raw_products:
        products.append({
            "id": p.id,
            "number": p.number,
            "name": p.name,
            "sku": p.sku,
            "base_price": p.base_price,
            "brand": p.brand,
        })

    # Search categories
    categories = list(
        StoreCategory.objects.filter(
            tenant=tenant,
            is_active=True,
            name__icontains=norm_q,
        ).values("id", "name", "slug")[:3]
    )

    # Suggestion queries from synonyms & logs
    synonym_terms = []
    synonyms = SearchSynonym.objects.filter(
        tenant=tenant, is_active=True, root_term__istartswith=norm_q
    )[:3]
    for syn in synonyms:
        synonym_terms.append(syn.root_term)

    if request.headers.get("HX-Request"):
        return render(
            request,
            "ecommerce/searchdiscovery/console/autocomplete_results.html",
            {
                "q": q,
                "products": products,
                "categories": categories,
                "suggestions": synonym_terms,
            },
        )

    return JsonResponse(
        {
            "q": q,
            "products": products,
            "categories": categories,
            "suggestions": synonym_terms,
        }
    )


@login_required
def search_analytics(request):
    """Discovery analytics dashboard reporting query volume, zero-result terms, and latency."""
    tenant = request.tenant

    logs_qs = SearchQueryLog.objects.filter(tenant=tenant)
    stats = logs_qs.aggregate(
        total=Count("id"),
        zero_results=Count("id", filter=Q(is_zero_result=True)),
        avg_latency=Avg("execution_time_ms"),
    )
    total_searches = stats["total"] or 0
    zero_result_searches = stats["zero_results"] or 0
    zero_result_rate = (
        round((zero_result_searches / total_searches) * 100, 1)
        if total_searches > 0
        else 0.0
    )

    avg_latency = stats["avg_latency"] or 0
    avg_latency_ms = round(avg_latency, 1)

    top_queries = (
        logs_qs.exclude(normalized_query="")
        .values("normalized_query")
        .annotate(query_count=Count("id"))
        .order_by("-query_count")[:10]
    )

    zero_result_queries = (
        logs_qs.filter(is_zero_result=True)
        .exclude(normalized_query="")
        .values("normalized_query")
        .annotate(query_count=Count("id"))
        .order_by("-query_count")[:10]
    )

    top_clicked_products = list(
        logs_qs.filter(clicked_product__isnull=False)
        .values(
            "clicked_product__id",
            "clicked_product__name",
            "clicked_product__number",
            "clicked_product__item__sku",
        )
        .annotate(click_count=Count("id"))
        .order_by("-click_count")[:10]
    )
    for p in top_clicked_products:
        p["clicked_product__sku"] = (
            p.get("clicked_product__item__sku") or p["clicked_product__number"]
        )

    context = {
        "total_searches": total_searches,
        "zero_result_searches": zero_result_searches,
        "zero_result_rate": zero_result_rate,
        "avg_latency_ms": avg_latency_ms,
        "top_queries": top_queries,
        "zero_result_queries": zero_result_queries,
        "top_clicked_products": top_clicked_products,
    }
    return render(
        request, "ecommerce/searchdiscovery/analytics/analytics.html", context
    )
