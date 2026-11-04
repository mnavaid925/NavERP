from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import render

from apps.bi.models.SemanticLayer.BusinessGlossaryTerms import BusinessGlossaryTerm
from apps.bi.models.SemanticLayer.CalculatedMeasures import CalculatedMeasure
from apps.bi.models.SemanticLayer.DrillHierarchies import DrillHierarchy
from apps.bi.models.SemanticLayer.SemanticModels import SemanticModel
from apps.bi.views._common import bi_scope


@login_required
def semantic_overview(request):
    models_qs = bi_scope(SemanticModel.objects.all(), request)
    terms_qs = bi_scope(BusinessGlossaryTerm.objects.all(), request)
    measures_qs = bi_scope(CalculatedMeasure.objects.all(), request)
    hierarchies_qs = bi_scope(DrillHierarchy.objects.all(), request)

    model_stats = models_qs.aggregate(
        total_models=Count("id"),
        total_certified_models=Count("id", filter=Q(certification_status="certified")),
    )
    total_models = model_stats["total_models"]
    total_certified_models = model_stats["total_certified_models"]

    term_stats = terms_qs.aggregate(
        total_glossary_terms=Count("id"),
        total_certified_terms=Count("id", filter=Q(certification_status="certified")),
    )
    total_glossary_terms = term_stats["total_glossary_terms"]
    total_certified_terms = term_stats["total_certified_terms"]

    total_measures = measures_qs.count()
    total_hierarchies = hierarchies_qs.count()

    recent_models = (
        models_qs.select_related("warehouse_table", "data_mart", "owner")
        .order_by("-updated_at")[:5]
    )
    recent_terms = (
        terms_qs.select_related("steward", "org_unit")
        .order_by("-updated_at")[:5]
    )

    model_type_dict = dict(SemanticModel.MODEL_TYPE_CHOICES)
    model_type_counts = [
        {
            "model_type": model_type_dict.get(item["model_type"], item["model_type"].replace("_", " ").title()),
            "count": item["count"],
        }
        for item in models_qs.values("model_type").annotate(count=Count("id")).order_by("-count")
    ]
    domain_dict = dict(BusinessGlossaryTerm.DOMAIN_CATEGORY_CHOICES)
    domain_term_counts = [
        {
            "domain_category": domain_dict.get(item["domain_category"], item["domain_category"].replace("_", " ").title()),
            "count": item["count"],
        }
        for item in terms_qs.values("domain_category").annotate(count=Count("id")).order_by("-count")
    ]

    context = {
        "total_models": total_models,
        "total_certified_models": total_certified_models,
        "total_glossary_terms": total_glossary_terms,
        "total_certified_terms": total_certified_terms,
        "total_measures": total_measures,
        "total_hierarchies": total_hierarchies,
        "recent_models": recent_models,
        "recent_terms": recent_terms,
        "model_type_counts": model_type_counts,
        "domain_term_counts": domain_term_counts,
    }
    return render(request, "bi/semantic_layer/semantic_overview.html", context)
