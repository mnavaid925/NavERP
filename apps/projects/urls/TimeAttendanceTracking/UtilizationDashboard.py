from django.urls import path
from apps.projects import views

urlpatterns = [
    path("utilization/", views.utilization_dashboard, name="utilization_dashboard"),
]
