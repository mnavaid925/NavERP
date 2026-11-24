from django.urls import path

from apps.documents import views

urlpatterns = [
    path("bpm/analytics/", views.process_analytics_dashboard, name="process_analytics_dashboard"),
]
