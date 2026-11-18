from django.urls import path

from apps.quality.views.NonConformance import ProcessDeviations as views

urlpatterns = [
    path("deviations/", views.process_deviation_list, name="process_deviation_list"),
    path("deviations/create/", views.process_deviation_create, name="process_deviation_create"),
    path("deviations/<int:pk>/", views.process_deviation_detail, name="process_deviation_detail"),
    path("deviations/<int:pk>/edit/", views.process_deviation_edit, name="process_deviation_edit"),
    path("deviations/<int:pk>/delete/", views.process_deviation_delete, name="process_deviation_delete"),
]
