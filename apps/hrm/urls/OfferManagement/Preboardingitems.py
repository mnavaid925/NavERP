"""HRM 3.8 Offer Management — Preboardingitems URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Pre-boarding items (3.8) — inline on the offer hub (add/remove/submit/verify/reject/send-invite)
    path("offers/<int:pk>/preboarding/add/", views.preboardingitem_add, name="preboardingitem_add"),
    path("preboarding-items/<int:pk>/delete/", views.preboardingitem_delete, name="preboardingitem_delete"),
    path("preboarding-items/<int:pk>/submit/", views.preboardingitem_mark_submitted, name="preboardingitem_mark_submitted"),
    path("preboarding-items/<int:pk>/verify/", views.preboardingitem_verify, name="preboardingitem_verify"),
    path("preboarding-items/<int:pk>/reject/", views.preboardingitem_reject, name="preboardingitem_reject"),
    path("preboarding-items/<int:pk>/send-invite/", views.preboardingitem_send_invite, name="preboardingitem_send_invite"),
]
