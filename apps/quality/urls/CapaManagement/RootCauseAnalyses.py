from django.urls import path

from apps.quality.views.CapaManagement import RootCauseAnalyses as views

urlpatterns = [
    path("capa/rca/", views.root_cause_analysis_list, name="root_cause_analysis_list"),
    path("capa/rca/create/", views.root_cause_analysis_create, name="root_cause_analysis_create"),
    path("capa/rca/export/", views.root_cause_analysis_export, name="root_cause_analysis_export"),
    path("capa/rca/<int:pk>/", views.root_cause_analysis_detail, name="root_cause_analysis_detail"),
    path("capa/rca/<int:pk>/edit/", views.root_cause_analysis_edit, name="root_cause_analysis_edit"),
    path("capa/rca/<int:pk>/delete/", views.root_cause_analysis_delete, name="root_cause_analysis_delete"),
    path("capa/rca/<int:pk>/verify/", views.root_cause_analysis_verify, name="root_cause_analysis_verify"),
]
