"""HRM 3.8 Offer Management — Offerlettertemplate URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Offer Letter Templates (3.8) — CRUD (printable-letter body library)
    path("offer-letter-templates/", views.offerlettertemplate_list, name="offerlettertemplate_list"),
    path("offer-letter-templates/add/", views.offerlettertemplate_create, name="offerlettertemplate_create"),
    path("offer-letter-templates/<int:pk>/", views.offerlettertemplate_detail, name="offerlettertemplate_detail"),
    path("offer-letter-templates/<int:pk>/edit/", views.offerlettertemplate_edit, name="offerlettertemplate_edit"),
    path("offer-letter-templates/<int:pk>/delete/", views.offerlettertemplate_delete, name="offerlettertemplate_delete"),
]
