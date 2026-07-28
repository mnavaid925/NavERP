"""SCM 4.10 Returns Management — WarrantyClaim routes (prefix ``warranty-claims/``).

Three verb routes under ``<int:pk>/``. None posts stock and none drafts an accounting document —
``accounting.Bill`` has no ``kind`` field, so there is no vendor-credit document to raise. The
claim records the amounts and stops.
"""
from django.urls import path

from apps.scm import views

urlpatterns = [
    path("warranty-claims/", views.warrantyclaim_list, name="warrantyclaim_list"),
    path("warranty-claims/add/", views.warrantyclaim_create, name="warrantyclaim_create"),
    path("warranty-claims/<int:pk>/", views.warrantyclaim_detail, name="warrantyclaim_detail"),
    path("warranty-claims/<int:pk>/edit/", views.warrantyclaim_edit, name="warrantyclaim_edit"),
    path("warranty-claims/<int:pk>/delete/", views.warrantyclaim_delete,
         name="warrantyclaim_delete"),
    path("warranty-claims/<int:pk>/submit/", views.warrantyclaim_submit,
         name="warrantyclaim_submit"),
    path("warranty-claims/<int:pk>/record-response/", views.warrantyclaim_record_response,
         name="warrantyclaim_record_response"),
    path("warranty-claims/<int:pk>/record-credit/", views.warrantyclaim_record_credit,
         name="warrantyclaim_record_credit"),
]
