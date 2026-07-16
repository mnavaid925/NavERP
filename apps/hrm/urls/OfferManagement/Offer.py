"""HRM 3.8 Offer Management — Offer URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Offers (3.8) — CRUD + hub + approval chain + status machine + printable letter
    path("offers/", views.offer_list, name="offer_list"),
    path("offers/add/", views.offer_create, name="offer_create"),
    path("offers/<int:pk>/", views.offer_detail, name="offer_detail"),
    path("offers/<int:pk>/edit/", views.offer_edit, name="offer_edit"),
    path("offers/<int:pk>/delete/", views.offer_delete, name="offer_delete"),
    path("offers/<int:pk>/submit/", views.offer_submit, name="offer_submit"),
    path("offers/<int:pk>/approve-step/", views.offer_approve_step, name="offer_approve_step"),
    path("offers/<int:pk>/reject-step/", views.offer_reject_step, name="offer_reject_step"),
    path("offers/<int:pk>/extend/", views.offer_extend, name="offer_extend"),
    path("offers/<int:pk>/accept/", views.offer_accept, name="offer_accept"),
    path("offers/<int:pk>/decline/", views.offer_decline, name="offer_decline"),
    path("offers/<int:pk>/rescind/", views.offer_rescind, name="offer_rescind"),
    path("offers/<int:pk>/expire/", views.offer_expire, name="offer_expire"),
    path("offers/<int:pk>/send-email/", views.offer_send_email, name="offer_send_email"),
]
