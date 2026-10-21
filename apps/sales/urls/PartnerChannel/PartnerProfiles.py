"""Sales 8.14 — URLs for `PartnerProfile`."""
from django.urls import path

from apps.sales.views.PartnerChannel import PartnerProfiles as views

urlpatterns = [
    path("partner-channel/partners/", views.partner_profile_list, name="partner_profile_list"),
    path("partner-channel/partners/new/", views.partner_profile_create, name="partner_profile_create"),
    path("partner-channel/partners/create/", views.partner_profile_create),
    path("partner-channel/partners/<int:pk>/", views.partner_profile_detail, name="partner_profile_detail"),
    path("partner-channel/partners/<int:pk>/edit/", views.partner_profile_edit, name="partner_profile_edit"),
    path("partner-channel/partners/<int:pk>/delete/", views.partner_profile_delete, name="partner_profile_delete"),
    path("partner-channel/console/", views.partner_performance_console, name="partner_performance_console"),
]
