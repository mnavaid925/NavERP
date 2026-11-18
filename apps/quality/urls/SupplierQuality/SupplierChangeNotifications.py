from django.urls import path

from apps.quality.views.SupplierQuality import SupplierChangeNotifications as views

urlpatterns = [
    path("scns/", views.supplier_change_notification_list, name="supplier_change_notification_list"),
    path("scns/create/", views.supplier_change_notification_create, name="supplier_change_notification_create"),
    path("scns/export/", views.supplier_change_notification_export, name="supplier_change_notification_export"),
    path("scns/<int:pk>/", views.supplier_change_notification_detail, name="supplier_change_notification_detail"),
    path("scns/<int:pk>/edit/", views.supplier_change_notification_edit, name="supplier_change_notification_edit"),
    path("scns/<int:pk>/delete/", views.supplier_change_notification_delete, name="supplier_change_notification_delete"),
    path("scns/<int:pk>/disposition/", views.supplier_change_notification_disposition, name="supplier_change_notification_disposition"),
]
