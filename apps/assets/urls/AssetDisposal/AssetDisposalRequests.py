from django.urls import path

from apps.assets.views.AssetDisposal import AssetDisposalRequests as views

urlpatterns = [
    path("disposal/requests/", views.asset_disposal_request_list, name="asset_disposal_request_list"),
    path("disposal/requests/create/", views.asset_disposal_request_create, name="asset_disposal_request_create"),
    path("disposal/requests/<int:pk>/", views.asset_disposal_request_detail, name="asset_disposal_request_detail"),
    path("disposal/requests/<int:pk>/edit/", views.asset_disposal_request_edit, name="asset_disposal_request_edit"),
    path("disposal/requests/<int:pk>/delete/", views.asset_disposal_request_delete, name="asset_disposal_request_delete"),
    path("disposal/requests/<int:pk>/submit/", views.asset_disposal_request_submit, name="asset_disposal_request_submit"),
    path("disposal/requests/<int:pk>/appraise/", views.asset_disposal_request_appraise, name="asset_disposal_request_appraise"),
    path("disposal/requests/<int:pk>/approve/", views.asset_disposal_request_approve, name="asset_disposal_request_approve"),
    path("disposal/requests/<int:pk>/reject/", views.asset_disposal_request_reject, name="asset_disposal_request_reject"),
    path("disposal/requests/<int:pk>/complete/", views.asset_disposal_request_complete, name="asset_disposal_request_complete"),
]
