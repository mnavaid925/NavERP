from django.urls import path

from apps.bi.views.SemanticLayer import CalculatedMeasures as views

urlpatterns = [
    path("semantic/measures/", views.calculated_measure_list, name="calculated_measure_list"),
    path("semantic/measures/create/", views.calculated_measure_create, name="calculated_measure_create"),
    path("semantic/measures/<int:pk>/", views.calculated_measure_detail, name="calculated_measure_detail"),
    path("semantic/measures/<int:pk>/edit/", views.calculated_measure_edit, name="calculated_measure_edit"),
    path("semantic/measures/<int:pk>/delete/", views.calculated_measure_delete, name="calculated_measure_delete"),
]
