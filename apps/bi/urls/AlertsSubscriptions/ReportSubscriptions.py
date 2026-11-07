from django.urls import path

from apps.bi.views.AlertsSubscriptions import ReportSubscriptions as views

urlpatterns = [
    path("subscriptions/", views.report_subscription_list, name="report_subscription_list"),
    path("subscriptions/create/", views.report_subscription_create, name="report_subscription_create"),
    path("subscriptions/<int:pk>/", views.report_subscription_detail, name="report_subscription_detail"),
    path("subscriptions/<int:pk>/edit/", views.report_subscription_edit, name="report_subscription_edit"),
    path("subscriptions/<int:pk>/delete/", views.report_subscription_delete, name="report_subscription_delete"),
    path("subscriptions/<int:pk>/run-now/", views.report_subscription_run_now, name="report_subscription_run_now"),
]
