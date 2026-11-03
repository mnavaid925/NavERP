from apps.bi.urls.EtlPipelines.EtlPipelineRuns import urlpatterns as runs_urls
from apps.bi.urls.EtlPipelines.EtlPipelines import urlpatterns as pipelines_urls
from apps.bi.urls.EtlPipelines.EtlPipelineVersions import urlpatterns as versions_urls
from apps.bi.urls.EtlPipelines.TransformationSteps import urlpatterns as steps_urls

urlpatterns = pipelines_urls + steps_urls + versions_urls + runs_urls

__all__ = ["urlpatterns"]
