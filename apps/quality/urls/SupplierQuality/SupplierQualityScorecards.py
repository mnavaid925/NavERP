from django.urls import path

from apps.quality.views.SupplierQuality import SupplierQualityScorecards as views

urlpatterns = [
    path("scorecards/", views.supplier_quality_scorecard_list, name="supplier_quality_scorecard_list"),
    path("scorecards/create/", views.supplier_quality_scorecard_create, name="supplier_quality_scorecard_create"),
    path("scorecards/export/", views.supplier_quality_scorecard_export, name="supplier_quality_scorecard_export"),
    path("scorecards/<int:pk>/", views.supplier_quality_scorecard_detail, name="supplier_quality_scorecard_detail"),
    path("scorecards/<int:pk>/edit/", views.supplier_quality_scorecard_edit, name="supplier_quality_scorecard_edit"),
    path("scorecards/<int:pk>/delete/", views.supplier_quality_scorecard_delete, name="supplier_quality_scorecard_delete"),
    path("scorecards/<int:pk>/publish/", views.supplier_quality_scorecard_publish, name="supplier_quality_scorecard_publish"),
]
