from django.urls import path

from apps.assets.views.MobileAssetManagement import FieldWorkOrders as views

urlpatterns = [
    path("mobile/work-orders/", views.field_work_order_list, name="field_work_order_list"),
    path("mobile/work-orders/create/", views.field_work_order_create, name="field_work_order_create"),
    path("mobile/work-orders/<int:pk>/", views.field_work_order_detail, name="field_work_order_detail"),
    path("mobile/work-orders/<int:pk>/edit/", views.field_work_order_edit, name="field_work_order_edit"),
    path("mobile/work-orders/<int:pk>/delete/", views.field_work_order_delete, name="field_work_order_delete"),
]
