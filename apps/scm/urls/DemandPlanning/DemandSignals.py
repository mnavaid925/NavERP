"""SCM 4.7 Demand Planning — DemandSignal routes (prefix ``demand-signals/``).

``demand-signals/add/`` and ``demand-signals/detect/`` are literal and MUST precede
``demand-signals/<int:pk>/`` — Django is first-match-wins, so a pk route above them would swallow
both (and `detect` would 404 as "signal 'detect' not found").
"""
from django.urls import path

from apps.scm import views

urlpatterns = [
    path("demand-signals/", views.demandsignal_list, name="demandsignal_list"),
    path("demand-signals/add/", views.demandsignal_create, name="demandsignal_create"),
    path("demand-signals/detect/", views.demandsignal_detect, name="demandsignal_detect"),
    path("demand-signals/<int:pk>/", views.demandsignal_detail, name="demandsignal_detail"),
    path("demand-signals/<int:pk>/edit/", views.demandsignal_edit, name="demandsignal_edit"),
    path("demand-signals/<int:pk>/delete/", views.demandsignal_delete, name="demandsignal_delete"),
    path("demand-signals/<int:pk>/review/", views.demandsignal_review, name="demandsignal_review"),
    path("demand-signals/<int:pk>/apply/", views.demandsignal_apply, name="demandsignal_apply"),
    path("demand-signals/<int:pk>/dismiss/", views.demandsignal_dismiss, name="demandsignal_dismiss"),
]
