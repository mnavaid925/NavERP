"""HRM 3.13 Salary Structure — Salarystructuretemplate URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Salary Structure Templates (3.13)
    path("salary-structures/", views.salarystructuretemplate_list, name="salarystructuretemplate_list"),
    path("salary-structures/add/", views.salarystructuretemplate_create, name="salarystructuretemplate_create"),
    path("salary-structures/<int:pk>/", views.salarystructuretemplate_detail, name="salarystructuretemplate_detail"),
    path("salary-structures/<int:pk>/edit/", views.salarystructuretemplate_edit, name="salarystructuretemplate_edit"),
    path("salary-structures/<int:pk>/delete/", views.salarystructuretemplate_delete, name="salarystructuretemplate_delete"),
    path("salary-structures/<int:template_pk>/lines/add/", views.salarystructureline_add, name="salarystructureline_add"),
    path("salary-structure-lines/<int:pk>/edit/", views.salarystructureline_edit, name="salarystructureline_edit"),
    path("salary-structure-lines/<int:pk>/delete/", views.salarystructureline_delete, name="salarystructureline_delete"),
]
