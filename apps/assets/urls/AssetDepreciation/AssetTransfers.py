from django.urls import path

from apps.assets.views.AssetDepreciation.AssetTransfers import (
    transfer_complete,
    transfer_create,
    transfer_delete,
    transfer_detail,
    transfer_dispatch,
    transfer_edit,
    transfer_list,
)

urlpatterns = [
    path("transfers/", transfer_list, name="transfer_list"),
    path("transfers/create/", transfer_create, name="transfer_create"),
    path("transfers/<int:pk>/", transfer_detail, name="transfer_detail"),
    path("transfers/<int:pk>/edit/", transfer_edit, name="transfer_edit"),
    path("transfers/<int:pk>/delete/", transfer_delete, name="transfer_delete"),
    path("transfers/<int:pk>/dispatch/", transfer_dispatch, name="transfer_dispatch"),
    path("transfers/<int:pk>/complete/", transfer_complete, name="transfer_complete"),
]
