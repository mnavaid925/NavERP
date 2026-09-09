"""Projects 7.4 — ProjectExpense routes (prefix ``expenses/``)."""
from django.urls import path

from apps.projects import views

urlpatterns = [
    path("expenses/", views.pex_list, name="pex_list"),
    path("expenses/add/", views.pex_create, name="pex_create"),
    path("expenses/<int:pk>/", views.pex_detail, name="pex_detail"),
    path("expenses/<int:pk>/edit/", views.pex_edit, name="pex_edit"),
    path("expenses/<int:pk>/delete/", views.pex_delete, name="pex_delete"),
    path("expenses/<int:pk>/post/", views.pex_post, name="pex_post"),
    path("expenses/<int:pk>/void/", views.pex_void, name="pex_void"),
]
