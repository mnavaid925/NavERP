from django.urls import path

from apps.sales import views


urlpatterns = [
    path("routing-rules/", views.lead_routing_rule_list, name="lead_routing_rule_list"),
    path("routing-rules/add/", views.lead_routing_rule_create, name="lead_routing_rule_create"),
    path("routing-rules/<int:pk>/", views.lead_routing_rule_detail, name="lead_routing_rule_detail"),
    path("routing-rules/<int:pk>/edit/", views.lead_routing_rule_edit, name="lead_routing_rule_edit"),
    path("routing-rules/<int:pk>/delete/", views.lead_routing_rule_delete, name="lead_routing_rule_delete"),
    path("routing-rules/<int:pk>/toggle/", views.lead_routing_rule_toggle, name="lead_routing_rule_toggle"),
    path("routing-rules/<int:pk>/preview/", views.lead_routing_rule_preview, name="lead_routing_rule_preview"),
    path("routing-rules/<int:pk>/run/", views.lead_routing_rule_run, name="lead_routing_rule_run"),
]
