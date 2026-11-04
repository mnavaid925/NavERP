from django.urls import path

from apps.bi.views.DataQuality import DataQualityRules as views

urlpatterns = [
    path("data-quality/rules/", views.data_quality_rule_list, name="data_quality_rule_list"),
    path("data-quality/rules/create/", views.data_quality_rule_create, name="data_quality_rule_create"),
    path("data-quality/rules/<int:pk>/", views.data_quality_rule_detail, name="data_quality_rule_detail"),
    path("data-quality/rules/<int:pk>/edit/", views.data_quality_rule_edit, name="data_quality_rule_edit"),
    path("data-quality/rules/<int:pk>/delete/", views.data_quality_rule_delete, name="data_quality_rule_delete"),
    path("data-quality/rules/<int:pk>/run/", views.data_quality_rule_run, name="data_quality_rule_run"),
]
