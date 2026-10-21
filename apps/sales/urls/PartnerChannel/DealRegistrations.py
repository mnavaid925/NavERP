"""Sales 8.14 — URLs for `DealRegistration`."""
from django.urls import path

from apps.sales.views.PartnerChannel import DealRegistrations as views

urlpatterns = [
    path("partner-channel/deal-registrations/", views.deal_registration_list, name="deal_registration_list"),
    path("partner-channel/deal-registrations/create/", views.deal_registration_create, name="deal_registration_create"),
    path("partner-channel/deal-registrations/<int:pk>/", views.deal_registration_detail, name="deal_registration_detail"),
    path("partner-channel/deal-registrations/<int:pk>/edit/", views.deal_registration_edit, name="deal_registration_edit"),
    path("partner-channel/deal-registrations/<int:pk>/delete/", views.deal_registration_delete, name="deal_registration_delete"),
    path("partner-channel/deal-registrations/<int:pk>/convert/", views.deal_registration_convert, name="deal_registration_convert"),
]
