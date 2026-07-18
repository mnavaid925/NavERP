"""SCM 4.4 Warehouse Management — CycleCountTask URL patterns."""
from django.urls import path

from apps.scm import views


urlpatterns = [
    path("cycle-counts/", views.cyclecounttask_list, name="cyclecounttask_list"),
    path("cycle-counts/add/", views.cyclecounttask_create, name="cyclecounttask_create"),
    path("cycle-counts/<int:pk>/", views.cyclecounttask_detail, name="cyclecounttask_detail"),
    path("cycle-counts/<int:pk>/edit/", views.cyclecounttask_edit, name="cyclecounttask_edit"),
    path("cycle-counts/<int:pk>/delete/", views.cyclecounttask_delete, name="cyclecounttask_delete"),
    path("cycle-counts/<int:pk>/start/", views.cyclecounttask_start, name="cyclecounttask_start"),
    path("cycle-counts/<int:pk>/complete/", views.cyclecounttask_complete, name="cyclecounttask_complete"),
    path("cycle-counts/<int:pk>/reconcile/", views.cyclecounttask_reconcile, name="cyclecounttask_reconcile"),
    path("cycle-counts/<int:pk>/cancel/", views.cyclecounttask_cancel, name="cyclecounttask_cancel"),
]
