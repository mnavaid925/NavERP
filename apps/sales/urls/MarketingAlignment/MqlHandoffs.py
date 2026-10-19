"""Sales 8.13 — URLs for `MqlHandoff`."""
from django.urls import path

from apps.sales.views.MarketingAlignment import MqlHandoffs as views

urlpatterns = [
    path("marketing-alignment/mql-handoffs/", views.mql_handoff_list, name="mql_handoff_list"),
    path("marketing-alignment/mql-handoffs/create/", views.mql_handoff_create, name="mql_handoff_create"),
    path("marketing-alignment/mql-handoffs/<int:pk>/", views.mql_handoff_detail, name="mql_handoff_detail"),
    path("marketing-alignment/mql-handoffs/<int:pk>/edit/", views.mql_handoff_edit, name="mql_handoff_edit"),
    path("marketing-alignment/mql-handoffs/<int:pk>/delete/", views.mql_handoff_delete, name="mql_handoff_delete"),
]
