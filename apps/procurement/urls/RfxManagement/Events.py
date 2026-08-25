"""Procurement 6.6 RFx Management — RfxEvent URL patterns."""
from django.urls import path

from apps.procurement import views


urlpatterns = [
    # Literal routes MUST precede the <int:pk> ones — Django is first-match-wins.
    path("rfx/", views.rfx_list, name="rfx_list"),
    path("rfx/add/", views.rfx_create, name="rfx_create"),
    path("rfx/library/", views.rfx_library, name="rfx_library"),
    path("rfx/scoring/", views.rfx_scoring, name="rfx_scoring"),
    path("rfx/library/<int:pk>/use/", views.rfx_clone, name="rfx_clone"),
    path("rfx/<int:pk>/", views.rfx_detail, name="rfx_detail"),
    path("rfx/<int:pk>/edit/", views.rfx_edit, name="rfx_edit"),
    path("rfx/<int:pk>/delete/", views.rfx_delete, name="rfx_delete"),
    path("rfx/<int:pk>/issue/", views.rfx_issue, name="rfx_issue"),
    path("rfx/<int:pk>/close/", views.rfx_close, name="rfx_close"),
    path("rfx/<int:pk>/cancel/", views.rfx_cancel, name="rfx_cancel"),
    path("rfx/<int:pk>/compare/", views.rfx_compare, name="rfx_compare"),
    path("rfx/<int:pk>/questions/<int:q_pk>/move/", views.rfx_question_move,
         name="rfx_question_move"),
]
