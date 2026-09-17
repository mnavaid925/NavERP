"""Projects 7.12 Portfolio & Program Management — PortfolioDashboard URLs.
"""
from django.urls import path

from apps.projects.views.PortfolioProgramManagement import PortfolioDashboard as views

urlpatterns = [
    path("portfolio-dashboard/", views.pfm_dashboard, name="pfm_dashboard"),
]
