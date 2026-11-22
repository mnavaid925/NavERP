from django.urls import path

from apps.documents.views.VersionControl import DocumentLocks as views

urlpatterns = [
    path("locks/", views.document_lock_list, name="document_lock_list"),
    path("locks/<int:pk>/", views.document_lock_detail, name="document_lock_detail"),
    path("documents/<int:doc_pk>/checkout/", views.document_checkout, name="document_checkout"),
    path("documents/<int:doc_pk>/checkin/", views.document_checkin, name="document_checkin"),
    path("documents/<int:doc_pk>/discard-checkout/", views.document_discard_checkout, name="document_discard_checkout"),
    path("locks/<int:pk>/force-unlock/", views.document_force_unlock, name="document_force_unlock"),
]
