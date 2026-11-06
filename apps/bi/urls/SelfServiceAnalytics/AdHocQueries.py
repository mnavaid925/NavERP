from django.urls import path

from apps.bi.views.SelfServiceAnalytics import AdHocQueries as views

urlpatterns = [
    path("queries/", views.ad_hoc_query_list, name="ad_hoc_query_list"),
    path("queries/create/", views.ad_hoc_query_create, name="ad_hoc_query_create"),
    path("queries/<int:pk>/", views.ad_hoc_query_detail, name="ad_hoc_query_detail"),
    path("queries/<int:pk>/edit/", views.ad_hoc_query_edit, name="ad_hoc_query_edit"),
    path("queries/<int:pk>/delete/", views.ad_hoc_query_delete, name="ad_hoc_query_delete"),
    path("queries/<int:pk>/composer/", views.ad_hoc_query_composer, name="ad_hoc_query_composer"),
    path("queries/<int:pk>/execute/", views.ad_hoc_query_execute, name="ad_hoc_query_execute"),
    path("queries/<int:pk>/export/", views.ad_hoc_query_export, name="ad_hoc_query_export"),
]
