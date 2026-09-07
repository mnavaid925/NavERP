"""Projects 7.1 — ProjectRequest routes (prefix ``project-requests/``)."""
from django.urls import path

from apps.projects import views

urlpatterns = [
    # Literal routes MUST precede the <int:pk> ones — Django is first-match-wins.
    path("project-requests/", views.prq_list, name="prq_list"),
    path("project-requests/add/", views.prq_create, name="prq_create"),
    path("project-requests/<int:pk>/", views.prq_detail, name="prq_detail"),
    path("project-requests/<int:pk>/edit/", views.prq_edit, name="prq_edit"),
    path("project-requests/<int:pk>/delete/", views.prq_delete, name="prq_delete"),
    path("project-requests/<int:pk>/submit/", views.prq_submit, name="prq_submit"),
    path("project-requests/<int:pk>/approve/", views.prq_approve, name="prq_approve"),
    path("project-requests/<int:pk>/reject/", views.prq_reject, name="prq_reject"),
    path("project-requests/<int:pk>/return/", views.prq_return_for_information,
         name="prq_return_for_information"),
    path("project-requests/<int:pk>/convert/", views.prq_convert, name="prq_convert"),
]
