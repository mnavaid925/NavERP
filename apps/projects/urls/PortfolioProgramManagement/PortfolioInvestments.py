"""Projects 7.12 Portfolio & Program Management — PortfolioInvestment URLs.
"""
from django.urls import path

from apps.projects.views.PortfolioProgramManagement import PortfolioInvestments as views

urlpatterns = [
    path("investments/", views.pin_list, name="pin_list"),
    path("investments/add/", views.pin_create, name="pin_create"),
    path("investments/<int:pk>/", views.pin_detail, name="pin_detail"),
    path("investments/<int:pk>/edit/", views.pin_edit, name="pin_edit"),
    path("investments/<int:pk>/delete/", views.pin_delete, name="pin_delete"),
    path("investments/<int:pk>/fund/", views.pin_fund, name="pin_fund"),
    path("investments/<int:pk>/reject/", views.pin_reject, name="pin_reject"),
    path("investments/<int:pk>/defer/", views.pin_defer, name="pin_defer"),
]
