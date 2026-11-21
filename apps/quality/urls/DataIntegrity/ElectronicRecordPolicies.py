from django.urls import path

from apps.quality.views.DataIntegrity import ElectronicRecordPolicies as views

urlpatterns = [
    path("policies/", views.electronic_record_policy_list, name="electronic_record_policy_list"),
    path("policies/create/", views.electronic_record_policy_create, name="electronic_record_policy_create"),
    path("policies/<int:pk>/", views.electronic_record_policy_detail, name="electronic_record_policy_detail"),
    path("policies/<int:pk>/edit/", views.electronic_record_policy_edit, name="electronic_record_policy_edit"),
    path("policies/<int:pk>/delete/", views.electronic_record_policy_delete, name="electronic_record_policy_delete"),
]
