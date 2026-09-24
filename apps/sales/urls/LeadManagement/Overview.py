from django.urls import path

from apps.sales import views


urlpatterns = [
    path("", views.lead_overview, name="sales_root"),
    path("overview/", views.lead_overview, name="lead_overview"),
    path("leads/<int:pk>/handoff/", views.lead_handoff, name="lead_handoff"),
]
