"""HRM 3.26 Request Management — Idcardrequest URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # ID Card Requests (new / replacement / correction)
    path("id-card-requests/", views.idcardrequest_list, name="idcardrequest_list"),
    path("id-card-requests/add/", views.idcardrequest_create, name="idcardrequest_create"),
    path("id-card-requests/<int:pk>/", views.idcardrequest_detail, name="idcardrequest_detail"),
    path("id-card-requests/<int:pk>/edit/", views.idcardrequest_edit, name="idcardrequest_edit"),
    path("id-card-requests/<int:pk>/delete/", views.idcardrequest_delete, name="idcardrequest_delete"),
    path("id-card-requests/<int:pk>/submit/", views.idcardrequest_submit, name="idcardrequest_submit"),
    path("id-card-requests/<int:pk>/cancel/", views.idcardrequest_cancel, name="idcardrequest_cancel"),
    path("id-card-requests/<int:pk>/approve/", views.idcardrequest_approve, name="idcardrequest_approve"),
    path("id-card-requests/<int:pk>/reject/", views.idcardrequest_reject, name="idcardrequest_reject"),
    path("id-card-requests/<int:pk>/issue/", views.idcardrequest_issue, name="idcardrequest_issue"),
]
