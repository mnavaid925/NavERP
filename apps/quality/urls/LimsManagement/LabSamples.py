from django.urls import path

from apps.quality.views.LimsManagement import LabSamples as views

urlpatterns = [
    path("lims/samples/", views.lab_sample_list, name="lab_sample_list"),
    path("lims/samples/create/", views.lab_sample_create, name="lab_sample_create"),
    path("lims/samples/<int:pk>/", views.lab_sample_detail, name="lab_sample_detail"),
    path("lims/samples/<int:pk>/edit/", views.lab_sample_edit, name="lab_sample_edit"),
    path("lims/samples/<int:pk>/delete/", views.lab_sample_delete, name="lab_sample_delete"),
    path("lims/samples/<int:pk>/receive/", views.lab_sample_receive, name="lab_sample_receive"),
]
