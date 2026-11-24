from django.urls import path

from apps.documents import views

urlpatterns = [
    path("bpm/routing-rules/", views.routing_rule_list, name="routing_rule_list"),
    path("bpm/routing-rules/create/", views.routing_rule_create, name="routing_rule_create"),
    path("bpm/routing-rules/simulator/", views.routing_rule_simulator, name="routing_rule_simulator"),
    path("bpm/routing-rules/<int:pk>/", views.routing_rule_detail, name="routing_rule_detail"),
    path("bpm/routing-rules/<int:pk>/edit/", views.routing_rule_edit, name="routing_rule_edit"),
    path("bpm/routing-rules/<int:pk>/delete/", views.routing_rule_delete, name="routing_rule_delete"),
    path("bpm/routing-rules/<int:pk>/toggle/", views.routing_rule_toggle, name="routing_rule_toggle"),
]
