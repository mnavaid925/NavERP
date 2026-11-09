from django.urls import path

from apps.assets.views.AssetPerformance import AssetOeeRecords as views

urlpatterns = [
    path("oee/", views.asset_oee_record_list, name="asset_oee_record_list"),
    path("oee/create/", views.asset_oee_record_create, name="asset_oee_record_create"),
    path("oee/<int:pk>/", views.asset_oee_record_detail, name="asset_oee_record_detail"),
    path("oee/<int:pk>/edit/", views.asset_oee_record_edit, name="asset_oee_record_edit"),
    path("oee/<int:pk>/delete/", views.asset_oee_record_delete, name="asset_oee_record_delete"),
    path("oee/<int:pk>/finalize/", views.asset_oee_record_finalize, name="asset_oee_record_finalize"),
]
