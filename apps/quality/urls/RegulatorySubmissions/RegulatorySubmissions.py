from django.urls import path

from apps.quality.views.RegulatorySubmissions import RegulatorySubmissions as views

urlpatterns = [
    path("submissions/", views.regulatory_submission_list, name="regulatory_submission_list"),
    path("submissions/create/", views.regulatory_submission_create, name="regulatory_submission_create"),
    path("submissions/export/", views.regulatory_submission_export, name="regulatory_submission_export"),
    path("submissions/<int:pk>/", views.regulatory_submission_detail, name="regulatory_submission_detail"),
    path("submissions/<int:pk>/edit/", views.regulatory_submission_edit, name="regulatory_submission_edit"),
    path("submissions/<int:pk>/delete/", views.regulatory_submission_delete, name="regulatory_submission_delete"),
]
