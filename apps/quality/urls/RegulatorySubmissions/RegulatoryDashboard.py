from django.urls import path

from apps.quality.views.RegulatorySubmissions import RegulatoryDashboard as views

urlpatterns = [
    path("regulatory-compliance/dashboard/", views.regulatory_dashboard, name="regulatory_dashboard"),
]
