"""Procurement 6.2 Requisition Management — RequisitionAmendments URL patterns."""
from django.urls import path

from apps.procurement import views


urlpatterns = [
    # Literal routes MUST precede the <int:pk> ones — Django is first-match-wins.
    path("amendments/", views.amendment_list, name="amendment_list"),
    path("amendments/<int:pk>/", views.amendment_detail, name="amendment_detail"),
    path("amendments/<int:pk>/approve/", views.amendment_approve, name="amendment_approve"),
    path("amendments/<int:pk>/reject/", views.amendment_reject, name="amendment_reject"),
]
