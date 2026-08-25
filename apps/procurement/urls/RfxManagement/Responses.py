"""Procurement 6.6 RFx Management — RfxResponse URL patterns."""
from django.urls import path

from apps.procurement import views


urlpatterns = [
    # Literal routes MUST precede the <int:pk> ones — Django is first-match-wins.
    path("rfx/responses/", views.rfx_response_list, name="rfx_response_list"),
    path("rfx/responses/add/", views.rfx_response_create, name="rfx_response_create"),
    path("rfx/responses/<int:pk>/", views.rfx_response_detail, name="rfx_response_detail"),
    path("rfx/responses/<int:pk>/edit/", views.rfx_response_edit, name="rfx_response_edit"),
    path("rfx/responses/<int:pk>/delete/", views.rfx_response_delete,
         name="rfx_response_delete"),
    path("rfx/responses/<int:pk>/status/", views.rfx_response_set_status,
         name="rfx_response_set_status"),
]
