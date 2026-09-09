"""Projects 7.4 — ProjectBudgetLine routes (prefix ``budgetlines/``)."""
from django.urls import path

from apps.projects import views

urlpatterns = [
    path("budgetlines/", views.pbl_list, name="pbl_list"),
    path("budgetlines/add/", views.pbl_create, name="pbl_create"),
    path("budgetlines/<int:pk>/", views.pbl_detail, name="pbl_detail"),
    path("budgetlines/<int:pk>/edit/", views.pbl_edit, name="pbl_edit"),
    path("budgetlines/<int:pk>/delete/", views.pbl_delete, name="pbl_delete"),
]
