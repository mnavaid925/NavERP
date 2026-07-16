"""HRM 3.16 Tax & Investment — Investmentproof URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Investment proofs — upload (per line) + verify/reject/on-hold workflow
    path("investment-proofs/", views.investmentproof_list, name="investmentproof_list"),
    path("investment-proofs/<int:pk>/", views.investmentproof_detail, name="investmentproof_detail"),
    path("investment-declaration-lines/<int:line_pk>/proofs/upload/", views.investmentproof_upload, name="investmentproof_upload"),
    path("investment-proofs/<int:pk>/verify/", views.investmentproof_verify, name="investmentproof_verify"),
    path("investment-proofs/<int:pk>/reject/", views.investmentproof_reject, name="investmentproof_reject"),
    path("investment-proofs/<int:pk>/on-hold/", views.investmentproof_on_hold, name="investmentproof_on_hold"),
]
