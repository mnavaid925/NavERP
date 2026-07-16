"""HRM 3.26 Request Management — Assetrequest URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Asset Requests (laptop / equipment)
    path("asset-requests/", views.assetrequest_list, name="assetrequest_list"),
    path("asset-requests/add/", views.assetrequest_create, name="assetrequest_create"),
    path("asset-requests/<int:pk>/", views.assetrequest_detail, name="assetrequest_detail"),
    path("asset-requests/<int:pk>/edit/", views.assetrequest_edit, name="assetrequest_edit"),
    path("asset-requests/<int:pk>/delete/", views.assetrequest_delete, name="assetrequest_delete"),
    path("asset-requests/<int:pk>/submit/", views.assetrequest_submit, name="assetrequest_submit"),
    path("asset-requests/<int:pk>/cancel/", views.assetrequest_cancel, name="assetrequest_cancel"),
    path("asset-requests/<int:pk>/approve/", views.assetrequest_approve, name="assetrequest_approve"),
    path("asset-requests/<int:pk>/reject/", views.assetrequest_reject, name="assetrequest_reject"),
    path("asset-requests/<int:pk>/fulfill/", views.assetrequest_fulfill, name="assetrequest_fulfill"),
]
