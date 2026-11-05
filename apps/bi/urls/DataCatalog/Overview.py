from django.urls import path

from apps.bi.views.DataCatalog.Overview import catalog_overview

urlpatterns = [
    path("catalog/overview/", catalog_overview, name="catalog_overview"),
]
