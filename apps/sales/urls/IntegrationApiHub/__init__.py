from .Connectors import urlpatterns as connector_urls
from .Dashboard import urlpatterns as dashboard_urls
from .FieldMappings import urlpatterns as mapping_urls
from .SyncJobs import urlpatterns as job_urls
from .SyncRuns import urlpatterns as run_urls

urlpatterns = dashboard_urls + connector_urls + mapping_urls + job_urls + run_urls
