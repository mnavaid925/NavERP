from django.urls import path

from apps.ecommerce.views.InventoryStock import ChannelInventorySyncs as views

urlpatterns = [
    path("inventory/sync/", views.channelinventorysync_list, name="channelinventorysync_list"),
    path("inventory/sync/create/", views.channelinventorysync_create, name="channelinventorysync_create"),
    path("inventory/sync/<int:pk>/", views.channelinventorysync_detail, name="channelinventorysync_detail"),
    path("inventory/sync/<int:pk>/edit/", views.channelinventorysync_edit, name="channelinventorysync_edit"),
    path("inventory/sync/<int:pk>/trigger/", views.channelinventorysync_trigger, name="channelinventorysync_trigger"),
    path("inventory/sync/<int:pk>/delete/", views.channelinventorysync_delete, name="channelinventorysync_delete"),
]
