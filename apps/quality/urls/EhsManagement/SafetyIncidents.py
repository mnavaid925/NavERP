from django.urls import path

from apps.quality.views.EhsManagement import SafetyIncidents as views

urlpatterns = [
    path("safety-incidents/", views.safety_incident_list, name="safety_incident_list"),
    path("safety-incidents/create/", views.safety_incident_create, name="safety_incident_create"),
    path("safety-incidents/export/", views.safety_incident_export, name="safety_incident_export"),
    path("safety-incidents/<int:pk>/", views.safety_incident_detail, name="safety_incident_detail"),
    path("safety-incidents/<int:pk>/edit/", views.safety_incident_update, name="safety_incident_update"),
    path("safety-incidents/<int:pk>/delete/", views.safety_incident_delete, name="safety_incident_delete"),
    path("safety-incidents/<int:pk>/investigate/", views.safety_incident_investigate, name="safety_incident_investigate"),
]
