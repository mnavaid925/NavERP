"""HRM 3.16 Tax & Investment — Investmentdeclaration URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Investment declarations (+ inline section lines) + submit/lock workflow
    path("investment-declarations/", views.investmentdeclaration_list, name="investmentdeclaration_list"),
    path("investment-declarations/add/", views.investmentdeclaration_create, name="investmentdeclaration_create"),
    path("investment-declarations/<int:pk>/", views.investmentdeclaration_detail, name="investmentdeclaration_detail"),
    path("investment-declarations/<int:pk>/edit/", views.investmentdeclaration_edit, name="investmentdeclaration_edit"),
    path("investment-declarations/<int:pk>/delete/", views.investmentdeclaration_delete, name="investmentdeclaration_delete"),
    path("investment-declarations/<int:pk>/submit/", views.investmentdeclaration_submit, name="investmentdeclaration_submit"),
    path("investment-declarations/<int:pk>/lock/", views.investmentdeclaration_lock, name="investmentdeclaration_lock"),
    path("investment-declarations/<int:declaration_pk>/lines/add/", views.investmentdeclarationline_create, name="investmentdeclarationline_create"),
    path("investment-declarations/<int:declaration_pk>/lines/<int:pk>/edit/", views.investmentdeclarationline_edit, name="investmentdeclarationline_edit"),
    path("investment-declarations/<int:declaration_pk>/lines/<int:pk>/delete/", views.investmentdeclarationline_delete, name="investmentdeclarationline_delete"),
]
