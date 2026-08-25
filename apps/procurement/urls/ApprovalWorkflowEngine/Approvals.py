"""Procurement 6.3 Approval Workflow Engine — queue/history/mine/decision routes.

Literal routes (`history/`, `mine/`) precede the `<int:pk>` ones — Django is
first-match-wins and `<int:...>` cannot match them anyway, but the ordering stays
explicit like every other module in this app.
"""
from django.urls import path

from apps.procurement import views

urlpatterns = [
    path("approvals/", views.approval_queue, name="approval_queue"),
    path("approvals/history/", views.approval_history, name="approval_history"),
    path("approvals/mine/", views.approval_mine, name="approval_mine"),
    path("approvals/<int:pk>/approve/", views.approval_approve, name="approval_approve"),
    path("approvals/<int:pk>/reject/", views.approval_reject, name="approval_reject"),
]
