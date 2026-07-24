"""SCM 4.7 Demand Planning — SeasonalityProfile routes (prefix ``seasonality/``).

Literal routes before ``<int:pk>/``.
"""
from django.urls import path

from apps.scm import views

urlpatterns = [
    path("seasonality/", views.seasonalityprofile_list, name="seasonalityprofile_list"),
    path("seasonality/add/", views.seasonalityprofile_create, name="seasonalityprofile_create"),
    path("seasonality/<int:pk>/", views.seasonalityprofile_detail, name="seasonalityprofile_detail"),
    path("seasonality/<int:pk>/edit/", views.seasonalityprofile_edit, name="seasonalityprofile_edit"),
    path("seasonality/<int:pk>/delete/", views.seasonalityprofile_delete,
         name="seasonalityprofile_delete"),
    path("seasonality/<int:pk>/derive/", views.seasonalityprofile_derive,
         name="seasonalityprofile_derive"),
]
