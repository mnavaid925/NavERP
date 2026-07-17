"""SCM 4.1 Procurement Management — PurchaseRequisitions URL patterns."""
from django.urls import path

from apps.scm import views


urlpatterns = [
    # Literal routes MUST precede the <int:pk> ones — Django is first-match-wins.
    path("requisitions/", views.requisition_list, name="requisition_list"),
    path("requisitions/add/", views.requisition_create, name="requisition_create"),
    path("requisitions/<int:pk>/", views.requisition_detail, name="requisition_detail"),
    path("requisitions/<int:pk>/edit/", views.requisition_edit, name="requisition_edit"),
    path("requisitions/<int:pk>/delete/", views.requisition_delete, name="requisition_delete"),
    path("requisitions/<int:pk>/submit/", views.requisition_submit, name="requisition_submit"),
    path("requisitions/<int:pk>/approve/", views.requisition_approve, name="requisition_approve"),
    path("requisitions/<int:pk>/reject/", views.requisition_reject, name="requisition_reject"),
]
