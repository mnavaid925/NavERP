from django.urls import path

from apps.quality.views.CapaManagement import CapaEffectivenessReviews as views

urlpatterns = [
    path("capa/effectiveness/", views.capa_effectiveness_review_list, name="capa_effectiveness_review_list"),
    path("capa/effectiveness/create/", views.capa_effectiveness_review_create, name="capa_effectiveness_review_create"),
    path("capa/effectiveness/export/", views.capa_effectiveness_review_export, name="capa_effectiveness_review_export"),
    path("capa/effectiveness/<int:pk>/", views.capa_effectiveness_review_detail, name="capa_effectiveness_review_detail"),
    path("capa/effectiveness/<int:pk>/edit/", views.capa_effectiveness_review_edit, name="capa_effectiveness_review_edit"),
    path("capa/effectiveness/<int:pk>/delete/", views.capa_effectiveness_review_delete, name="capa_effectiveness_review_delete"),
    path("capa/effectiveness/<int:pk>/sign-off/", views.capa_effectiveness_review_sign_off, name="capa_effectiveness_review_sign_off"),
]
