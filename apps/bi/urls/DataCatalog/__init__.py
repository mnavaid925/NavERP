from apps.bi.urls.DataCatalog.CatalogAssets import urlpatterns as asset_urls
from apps.bi.urls.DataCatalog.CatalogLineageEdges import urlpatterns as lineage_urls
from apps.bi.urls.DataCatalog.DataGovernancePolicies import urlpatterns as policy_urls
from apps.bi.urls.DataCatalog.CatalogTrustEndorsements import urlpatterns as endorsement_urls
from apps.bi.urls.DataCatalog.Overview import urlpatterns as overview_urls

urlpatterns = overview_urls + asset_urls + lineage_urls + policy_urls + endorsement_urls
