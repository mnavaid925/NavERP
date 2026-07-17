"""SCM 4.3 Inventory Management — LotSerial URL patterns."""
from django.urls import path

from apps.scm import views


urlpatterns = [
    path("lot-serials/", views.lotserial_list, name="lotserial_list"),
    path("lot-serials/add/", views.lotserial_create, name="lotserial_create"),
    path("lot-serials/<int:pk>/", views.lotserial_detail, name="lotserial_detail"),
    path("lot-serials/<int:pk>/edit/", views.lotserial_edit, name="lotserial_edit"),
    path("lot-serials/<int:pk>/delete/", views.lotserial_delete, name="lotserial_delete"),
]
