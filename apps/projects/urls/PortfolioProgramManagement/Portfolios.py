"""Projects 7.12 Portfolio & Program Management — Portfolio URLs.
"""
from django.urls import path

from apps.projects.views.PortfolioProgramManagement import Portfolios as views

urlpatterns = [
    path("portfolios/", views.prt_list, name="prt_list"),
    path("portfolios/add/", views.prt_create, name="prt_create"),
    path("portfolios/<int:pk>/", views.prt_detail, name="prt_detail"),
    path("portfolios/<int:pk>/edit/", views.prt_edit, name="prt_edit"),
    path("portfolios/<int:pk>/delete/", views.prt_delete, name="prt_delete"),
]
