from django.urls import path

from apps.assets.views.AssetDisposal import AssetTradeIns as views

urlpatterns = [
    path("disposal/trade-ins/", views.asset_trade_in_list, name="asset_trade_in_list"),
    path("disposal/trade-ins/create/", views.asset_trade_in_create, name="asset_trade_in_create"),
    path("disposal/trade-ins/<int:pk>/", views.asset_trade_in_detail, name="asset_trade_in_detail"),
    path("disposal/trade-ins/<int:pk>/edit/", views.asset_trade_in_edit, name="asset_trade_in_edit"),
    path("disposal/trade-ins/<int:pk>/delete/", views.asset_trade_in_delete, name="asset_trade_in_delete"),
    path("disposal/trade-ins/<int:pk>/surrender/", views.asset_trade_in_surrender, name="asset_trade_in_surrender"),
    path("disposal/trade-ins/<int:pk>/settle/", views.asset_trade_in_settle, name="asset_trade_in_settle"),
]
