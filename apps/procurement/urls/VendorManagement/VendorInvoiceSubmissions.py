"""Procurement 6.4 Vendor Management — VendorInvoiceSubmission URL patterns."""
from django.urls import path

from apps.procurement import views


urlpatterns = [
    # Literal routes MUST precede the <int:pk> ones — Django is first-match-wins.
    path("submissions/", views.vis_list, name="vis_list"),
    path("submissions/<int:pk>/", views.vis_detail, name="vis_detail"),
    path("submissions/<int:pk>/review/", views.vis_start_review, name="vis_start_review"),
    path("submissions/<int:pk>/accept/", views.vis_accept, name="vis_accept"),
    path("submissions/<int:pk>/reject/", views.vis_reject, name="vis_reject"),
    path("submissions/<int:pk>/delete/", views.vis_delete, name="vis_delete"),
]
