"""URL patterns for Software Licenses (11.18)."""

from django.urls import path

from apps.assets.views.ItAssetManagement import SoftwareLicenses as views

urlpatterns = [
    path("software-licenses/", views.software_license_list, name="software_license_list"),
    path("software-licenses/create/", views.software_license_create, name="software_license_create"),
    path("software-licenses/export-csv/", views.software_license_export_csv, name="software_license_export_csv"),
    path("software-licenses/<int:pk>/", views.software_license_detail, name="software_license_detail"),
    path("software-licenses/<int:pk>/edit/", views.software_license_edit, name="software_license_edit"),
    path("software-licenses/<int:pk>/delete/", views.software_license_delete, name="software_license_delete"),
    path("software-licenses/<int:pk>/sync-compliance/", views.software_license_sync_compliance, name="software_license_sync_compliance"),
    path("software-licenses/<int:pk>/reclaim/", views.software_license_reclaim_inactive, name="software_license_reclaim_inactive"),
    path("software-licenses/<int:pk>/true-up/", views.software_license_record_true_up, name="software_license_record_true_up"),
    path("software-licenses/<int:pk>/renew/", views.software_license_renew_term, name="software_license_renew_term"),
    path("software-licenses/<int:pk>/audit-hold/", views.software_license_place_audit_hold, name="software_license_place_audit_hold"),
    path("software-licenses/<int:pk>/retire/", views.software_license_retire, name="software_license_retire"),
]
