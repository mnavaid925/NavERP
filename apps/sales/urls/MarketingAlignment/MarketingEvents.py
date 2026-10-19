"""Sales 8.13 — URLs for `MarketingEvent` and `EventRegistration`."""
from django.urls import path

from apps.sales.views.MarketingAlignment import MarketingEvents as views

urlpatterns = [
    path("marketing-alignment/events/", views.marketing_event_list, name="marketing_event_list"),
    path("marketing-alignment/events/create/", views.marketing_event_create, name="marketing_event_create"),
    path("marketing-alignment/events/<int:pk>/", views.marketing_event_detail, name="marketing_event_detail"),
    path("marketing-alignment/events/<int:pk>/edit/", views.marketing_event_edit, name="marketing_event_edit"),
    path("marketing-alignment/events/<int:pk>/delete/", views.marketing_event_delete, name="marketing_event_delete"),
    path("marketing-alignment/events/<int:pk>/registrations/", views.marketing_event_registrations, name="marketing_event_registrations"),
    path("marketing-alignment/events/<int:pk>/registrations/create/", views.marketing_event_registration_create, name="marketing_event_registration_create"),
]
