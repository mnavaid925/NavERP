"""Procurement 6.2 Requisition Management — Requisition tracking URL patterns."""
from django.urls import path

from apps.procurement import views


urlpatterns = [
    path("requisitions/", views.req_list, name="req_list"),
    # Literal suffixes precede the bare <int:pk> detail — first-match-wins.
    path("requisitions/<int:requisition_pk>/request-amendment/", views.req_amendment_create,
         name="req_amendment_create"),
    path("requisitions/<int:pk>/", views.req_detail, name="req_detail"),
]
