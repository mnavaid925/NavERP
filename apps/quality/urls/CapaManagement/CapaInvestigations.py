from django.urls import path

from apps.quality.views.CapaManagement import CapaInvestigations as views

urlpatterns = [
    path("capa/", views.capa_investigation_list, name="capa_investigation_list"),
    path("capa/create/", views.capa_investigation_create, name="capa_investigation_create"),
    path("capa/export/", views.capa_investigation_export, name="capa_investigation_export"),
    path("capa/<int:pk>/", views.capa_investigation_detail, name="capa_investigation_detail"),
    path("capa/<int:pk>/edit/", views.capa_investigation_edit, name="capa_investigation_edit"),
    path("capa/<int:pk>/delete/", views.capa_investigation_delete, name="capa_investigation_delete"),
    path("capa/<int:pk>/advance/", views.capa_investigation_advance_status, name="capa_investigation_advance_status"),
    path("capa/<int:pk>/close/", views.capa_investigation_close, name="capa_investigation_close"),
]
