from django.urls import path

from apps.bi.views.SelfServiceAnalytics import AdHocCalculatedFields as views

urlpatterns = [
    path("calculated-fields/", views.ad_hoc_calculated_field_list, name="ad_hoc_calculated_field_list"),
    path("calculated-fields/create/", views.ad_hoc_calculated_field_create, name="ad_hoc_calculated_field_create"),
    path("calculated-fields/<int:pk>/", views.ad_hoc_calculated_field_detail, name="ad_hoc_calculated_field_detail"),
    path("calculated-fields/<int:pk>/edit/", views.ad_hoc_calculated_field_edit, name="ad_hoc_calculated_field_edit"),
    path("calculated-fields/<int:pk>/delete/", views.ad_hoc_calculated_field_delete, name="ad_hoc_calculated_field_delete"),
    path("calculated-fields/validate/", views.ad_hoc_calculated_field_validate, name="ad_hoc_calculated_field_validate"),
]
