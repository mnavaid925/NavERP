from django.urls import path

from apps.assets.views.AssetDisposal import AssetScrapSalvages as views

urlpatterns = [
    path("disposal/scrap-salvages/", views.asset_scrap_salvage_list, name="asset_scrap_salvage_list"),
    path("disposal/scrap-salvages/create/", views.asset_scrap_salvage_create, name="asset_scrap_salvage_create"),
    path("disposal/scrap-salvages/<int:pk>/", views.asset_scrap_salvage_detail, name="asset_scrap_salvage_detail"),
    path("disposal/scrap-salvages/<int:pk>/edit/", views.asset_scrap_salvage_edit, name="asset_scrap_salvage_edit"),
    path("disposal/scrap-salvages/<int:pk>/delete/", views.asset_scrap_salvage_delete, name="asset_scrap_salvage_delete"),
    path("disposal/scrap-salvages/<int:pk>/certify-abatement/", views.asset_scrap_salvage_certify_abatement, name="asset_scrap_salvage_certify_abatement"),
    path("disposal/scrap-salvages/<int:pk>/record-cod/", views.asset_scrap_salvage_record_cod, name="asset_scrap_salvage_record_cod"),
    path("disposal/scrap-salvages/<int:pk>/settle/", views.asset_scrap_salvage_settle, name="asset_scrap_salvage_settle"),
]
