from django.urls import path

from apps.ecommerce.views.AnalyticsBi import AttributionTouchpoints as views

urlpatterns = [
    path("analytics/attribution/", views.attributiontouchpoint_list, name="attributiontouchpoint_list"),
    path("analytics/attribution/create/", views.attributiontouchpoint_create, name="attributiontouchpoint_create"),
    path("analytics/attribution/<int:pk>/", views.attributiontouchpoint_detail, name="attributiontouchpoint_detail"),
    path("analytics/attribution/<int:pk>/edit/", views.attributiontouchpoint_edit, name="attributiontouchpoint_edit"),
    path("analytics/attribution/<int:pk>/delete/", views.attributiontouchpoint_delete, name="attributiontouchpoint_delete"),
]
