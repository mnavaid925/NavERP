"""Procurement 6.9 Catalog Management — PunchOutEndpoint URL patterns."""
from django.urls import path

from apps.procurement import views


urlpatterns = [
    # Literal routes MUST precede the <int:pk> ones — Django is first-match-wins.
    path("punchout/", views.punchout_endpoint_list, name="punchout_endpoint_list"),
    path("punchout/add/", views.punchout_endpoint_create, name="punchout_endpoint_create"),
    path("punchout/<int:pk>/", views.punchout_endpoint_detail, name="punchout_endpoint_detail"),
    path("punchout/<int:pk>/edit/", views.punchout_endpoint_edit,
         name="punchout_endpoint_edit"),
    path("punchout/<int:pk>/delete/", views.punchout_endpoint_delete,
         name="punchout_endpoint_delete"),
    path("punchout/<int:pk>/test/", views.punchout_endpoint_test,
         name="punchout_endpoint_test"),
]
