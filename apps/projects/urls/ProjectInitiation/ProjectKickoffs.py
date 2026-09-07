"""Projects 7.1 — ProjectKickoff routes (prefix ``kickoffs/``)."""
from django.urls import path

from apps.projects import views

urlpatterns = [
    path("kickoffs/", views.pko_list, name="pko_list"),
    path("kickoffs/add/", views.pko_create, name="pko_create"),
    path("kickoffs/<int:pk>/", views.pko_detail, name="pko_detail"),
    path("kickoffs/<int:pk>/edit/", views.pko_edit, name="pko_edit"),
    path("kickoffs/<int:pk>/delete/", views.pko_delete, name="pko_delete"),
    path("kickoffs/<int:pk>/schedule/", views.pko_schedule, name="pko_schedule"),
    path("kickoffs/<int:pk>/mark-held/", views.pko_mark_held, name="pko_mark_held"),
    path("kickoffs/<int:pk>/complete/", views.pko_complete, name="pko_complete"),
    path("kickoffs/<int:pk>/baseline/", views.pko_mark_baseline_set,
         name="pko_mark_baseline_set"),
]
