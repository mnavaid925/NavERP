from django.urls import path

from apps.quality.views.CustomerComplaints import ComplaintTrendingDashboard as views

urlpatterns = [
    path("trending/", views.complaint_trending_dashboard, name="complaint_trending_dashboard"),
]
