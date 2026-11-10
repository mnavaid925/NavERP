from django.urls import path

from apps.assets.views.AssetLeaseRental import AssetLeaseBuyAnalyses as views

urlpatterns = [
    path("lease-buy-analyses/", views.asset_lease_buy_analysis_list, name="asset_lease_buy_analysis_list"),
    path("lease-buy-analyses/create/", views.asset_lease_buy_analysis_create, name="asset_lease_buy_analysis_create"),
    path("lease-buy-analyses/<int:pk>/", views.asset_lease_buy_analysis_detail, name="asset_lease_buy_analysis_detail"),
    path("lease-buy-analyses/<int:pk>/edit/", views.asset_lease_buy_analysis_edit, name="asset_lease_buy_analysis_edit"),
    path("lease-buy-analyses/<int:pk>/delete/", views.asset_lease_buy_analysis_delete, name="asset_lease_buy_analysis_delete"),
    path("lease-buy-analyses/<int:pk>/evaluate/", views.asset_lease_buy_analysis_evaluate, name="asset_lease_buy_analysis_evaluate"),
]
