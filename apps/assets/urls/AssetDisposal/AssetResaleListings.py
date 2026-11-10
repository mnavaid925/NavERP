from django.urls import path

from apps.assets.views.AssetDisposal import AssetResaleListings as views

urlpatterns = [
    path("disposal/resale-listings/", views.asset_resale_listing_list, name="asset_resale_listing_list"),
    path("disposal/resale-listings/create/", views.asset_resale_listing_create, name="asset_resale_listing_create"),
    path("disposal/resale-listings/<int:pk>/", views.asset_resale_listing_detail, name="asset_resale_listing_detail"),
    path("disposal/resale-listings/<int:pk>/edit/", views.asset_resale_listing_edit, name="asset_resale_listing_edit"),
    path("disposal/resale-listings/<int:pk>/delete/", views.asset_resale_listing_delete, name="asset_resale_listing_delete"),
    path("disposal/resale-listings/<int:pk>/record-bid/", views.asset_resale_listing_record_bid, name="asset_resale_listing_record_bid"),
    path("disposal/resale-listings/<int:pk>/accept-sale/", views.asset_resale_listing_accept_sale, name="asset_resale_listing_accept_sale"),
    path("disposal/resale-listings/<int:pk>/mark-paid/", views.asset_resale_listing_mark_paid, name="asset_resale_listing_mark_paid"),
    path("disposal/resale-listings/<int:pk>/mark-delivered/", views.asset_resale_listing_mark_delivered, name="asset_resale_listing_mark_delivered"),
]
