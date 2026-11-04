from django.contrib.auth.decorators import login_required
from django.db.models import Count
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

    total_models = models_qs.count()
    total_certified_models = models_qs.filter(certification_status="certified").count()
    total_glossary_terms = terms_qs.count()
    total_certified_terms = terms_qs.filter(certification_status="certified").count()
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

    model_type_counts = models_qs.values("model_type").annotate(count=Count("id")).order_by("-count")
    domain_term_counts = terms_qs.values("domain_category").annotate(count=Count("id")).order_by("-count")

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
