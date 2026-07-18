"""SCM 4.5 Order Management System — SalesOrderAllocation routes.

The create route hangs off its parent LINE (`sales-order-lines/<line_pk>/allocations/add/`),
mirroring `rfqs/<rfq_pk>/quotes/add/`: an allocation only makes sense against a specific order line,
so the parent is carried in the URL rather than offered as a form dropdown.
"""
from django.urls import path

from apps.scm import views

urlpatterns = [
    path("allocations/", views.salesorderallocation_list, name="salesorderallocation_list"),
    path("sales-order-lines/<int:line_pk>/allocations/add/", views.salesorderallocation_create,
         name="salesorderallocation_create"),
    path("allocations/<int:pk>/", views.salesorderallocation_detail,
         name="salesorderallocation_detail"),
    path("allocations/<int:pk>/edit/", views.salesorderallocation_edit,
         name="salesorderallocation_edit"),
    path("allocations/<int:pk>/delete/", views.salesorderallocation_delete,
         name="salesorderallocation_delete"),
    path("allocations/<int:pk>/release/", views.salesorderallocation_release,
         name="salesorderallocation_release"),
    path("allocations/<int:pk>/cancel/", views.salesorderallocation_cancel,
         name="salesorderallocation_cancel"),
]
