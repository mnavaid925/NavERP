from django.urls import path

from apps.ecommerce.views.AnalyticsBi import AnalyticsCockpit as views

urlpatterns = [
    path("analytics/cockpit/", views.analytics_cockpit, name="analytics_cockpit"),
]
