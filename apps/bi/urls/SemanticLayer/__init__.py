from apps.bi.urls.SemanticLayer.BusinessGlossaryTermUrls import (
    urlpatterns as business_glossary_term_urlpatterns,
)
from apps.bi.urls.SemanticLayer.CalculatedMeasureUrls import (
    urlpatterns as calculated_measure_urlpatterns,
)
from apps.bi.urls.SemanticLayer.DrillHierarchyUrls import (
    urlpatterns as drill_hierarchy_urlpatterns,
)
from apps.bi.urls.SemanticLayer.SemanticModelUrls import (
    urlpatterns as semantic_model_urlpatterns,
)
from apps.bi.urls.SemanticLayer.SemanticOverviewUrls import (
    urlpatterns as semantic_overview_urlpatterns,
)

urlpatterns = (
    semantic_overview_urlpatterns
    + semantic_model_urlpatterns
    + business_glossary_term_urlpatterns
    + calculated_measure_urlpatterns
    + drill_hierarchy_urlpatterns
)

__all__ = ["urlpatterns"]
