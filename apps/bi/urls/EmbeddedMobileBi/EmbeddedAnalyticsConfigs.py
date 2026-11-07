from django.urls import path

from apps.bi.views.EmbeddedMobileBi import EmbeddedAnalyticsConfigs as views

urlpatterns = [
    path("embedded-configs/", views.embedded_analytics_config_list, name="embedded_analytics_config_list"),
    path("embedded-configs/create/", views.embedded_analytics_config_create, name="embedded_analytics_config_create"),
    path("embedded-configs/<int:pk>/", views.embedded_analytics_config_detail, name="embedded_analytics_config_detail"),
    path("embedded-configs/<int:pk>/edit/", views.embedded_analytics_config_edit, name="embedded_analytics_config_edit"),
    path("embedded-configs/<int:pk>/delete/", views.embedded_analytics_config_delete, name="embedded_analytics_config_delete"),
    path("embedded-configs/<int:pk>/preview/", views.embedded_analytics_config_preview, name="embedded_analytics_config_preview"),
]
