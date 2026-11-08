from apps.assets.urls.AssetClassification.AssetCategories import urlpatterns as category_urls
from apps.assets.urls.AssetClassification.AssetCriticalityAssessments import (
    urlpatterns as criticality_assessment_urls,
)
from apps.assets.urls.AssetClassification.AssetModels import urlpatterns as model_urls
from apps.assets.urls.AssetClassification.AssetSpecificationTemplates import (
    urlpatterns as spec_template_urls,
)

urlpatterns = category_urls + model_urls + criticality_assessment_urls + spec_template_urls
