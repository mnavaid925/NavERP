from django.urls import path

from apps.quality.views.NonConformance import MrbDispositions as views

urlpatterns = [
    path("mrb-dispositions/", views.mrb_disposition_list, name="mrb_disposition_list"),
    path("mrb-dispositions/create/", views.mrb_disposition_create, name="mrb_disposition_create"),
    path("mrb-dispositions/<int:pk>/", views.mrb_disposition_detail, name="mrb_disposition_detail"),
    path("mrb-dispositions/<int:pk>/edit/", views.mrb_disposition_edit, name="mrb_disposition_edit"),
    path("mrb-dispositions/<int:pk>/delete/", views.mrb_disposition_delete, name="mrb_disposition_delete"),
]
