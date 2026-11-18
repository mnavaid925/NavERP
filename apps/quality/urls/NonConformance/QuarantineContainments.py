from django.urls import path

from apps.quality.views.NonConformance import QuarantineContainments as views

urlpatterns = [
    path("quarantines/", views.quarantine_containment_list, name="quarantine_containment_list"),
    path("quarantines/create/", views.quarantine_containment_create, name="quarantine_containment_create"),
    path("quarantines/<int:pk>/", views.quarantine_containment_detail, name="quarantine_containment_detail"),
    path("quarantines/<int:pk>/edit/", views.quarantine_containment_edit, name="quarantine_containment_edit"),
    path("quarantines/<int:pk>/delete/", views.quarantine_containment_delete, name="quarantine_containment_delete"),
]
