"""SCM 4.8 Manufacturing — WorkOrder routes (prefix ``work-orders/``).

Literal routes before ``<int:pk>/``. The seven verb routes all sit UNDER ``<int:pk>/``, so they
cannot be swallowed by it. ``work-orders/`` is a distinct first segment from 4.1's ``orders/``
(purchase orders) and 4.5's ``sales-orders/``.
"""
from django.urls import path

from apps.scm import views

urlpatterns = [
    path("work-orders/", views.workorder_list, name="workorder_list"),
    path("work-orders/add/", views.workorder_create, name="workorder_create"),
    path("work-orders/<int:pk>/", views.workorder_detail, name="workorder_detail"),
    path("work-orders/<int:pk>/edit/", views.workorder_edit, name="workorder_edit"),
    path("work-orders/<int:pk>/delete/", views.workorder_delete, name="workorder_delete"),
    # Lifecycle — no stock effect.
    path("work-orders/<int:pk>/plan/", views.workorder_plan, name="workorder_plan"),
    path("work-orders/<int:pk>/release/", views.workorder_release, name="workorder_release"),
    path("work-orders/<int:pk>/close/", views.workorder_close, name="workorder_close"),
    path("work-orders/<int:pk>/cancel/", views.workorder_cancel, name="workorder_cancel"),
    path("work-orders/<int:pk>/schedule/", views.workorder_schedule, name="workorder_schedule"),
    # Postings — these move stock.
    path("work-orders/<int:pk>/issue/", views.workorder_issue_components,
         name="workorder_issue_components"),
    path("work-orders/<int:pk>/report/", views.workorder_report_production,
         name="workorder_report_production"),
]
