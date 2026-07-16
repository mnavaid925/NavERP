"""HRM 3.32 Analytics Dashboard — Widget URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("analytics/dashboards/<int:dash_pk>/widgets/add/", views.hr_widget_create, name="hr_widget_create"),
    path("analytics/widgets/<int:pk>/edit/", views.hr_widget_edit, name="hr_widget_edit"),
    path("analytics/widgets/<int:pk>/delete/", views.hr_widget_delete, name="hr_widget_delete"),
    path("analytics/widgets/<int:pk>/move/<str:direction>/", views.hr_widget_move, name="hr_widget_move"),
]
