"""CRM 1.6 Analytics & Reporting — Widgets URL patterns (split from apps/crm/urls.py)."""
from django.urls import path

from apps.crm import views


urlpatterns = [
    path("dashboards/<int:dash_pk>/widgets/add/", views.widget_create, name="widget_create"),
    path("widgets/<int:pk>/edit/", views.widget_edit, name="widget_edit"),
    path("widgets/<int:pk>/delete/", views.widget_delete, name="widget_delete"),
    path("widgets/<int:pk>/move/<str:direction>/", views.widget_move, name="widget_move"),
]
