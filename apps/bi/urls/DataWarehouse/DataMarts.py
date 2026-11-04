from django.urls import path

from apps.bi.views.DataWarehouse import DataMarts as views

urlpatterns = [
    path("data-marts/", views.data_mart_list, name="data_mart_list"),
    path("data-marts/create/", views.data_mart_create, name="data_mart_create"),
    path("data-marts/<int:pk>/", views.data_mart_detail, name="data_mart_detail"),
    path("data-marts/<int:pk>/edit/", views.data_mart_edit, name="data_mart_edit"),
    path("data-marts/<int:pk>/delete/", views.data_mart_delete, name="data_mart_delete"),
]
