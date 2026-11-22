from django.urls import path

from apps.documents.views.StorageRepository import RepositoryDashboard as views

urlpatterns = [
    path("storage/dashboard/", views.repository_dashboard, name="repository_dashboard"),
]
