from django.urls import path

from apps.bi.views.AlertsSubscriptions import BiNotificationItems as views

urlpatterns = [
    path("notifications/", views.bi_notification_item_list, name="bi_notification_item_list"),
    path("notifications/create/", views.bi_notification_item_create, name="bi_notification_item_create"),
    path("notifications/<int:pk>/", views.bi_notification_item_detail, name="bi_notification_item_detail"),
    path("notifications/<int:pk>/edit/", views.bi_notification_item_edit, name="bi_notification_item_edit"),
    path("notifications/<int:pk>/delete/", views.bi_notification_item_delete, name="bi_notification_item_delete"),
    path("notification-center/", views.notification_center, name="notification_center"),
    path("notifications/<int:pk>/mark-read/", views.notification_mark_read, name="notification_mark_read"),
    path("notifications/<int:pk>/acknowledge/", views.notification_acknowledge, name="notification_acknowledge"),
    path("notifications/<int:pk>/snooze/", views.notification_snooze, name="notification_snooze"),
    path("notifications/<int:pk>/escalate/", views.notification_escalate, name="notification_escalate"),
]
