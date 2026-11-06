from django.urls import path

from apps.bi.views.OlapAnalysis import WritebackCells as views

urlpatterns = [
    path("olap/writeback-cells/", views.writeback_cell_list, name="writeback_cell_list"),
    path("olap/writeback-cells/create/", views.writeback_cell_create, name="writeback_cell_create"),
    path("olap/writeback-cells/<int:pk>/", views.writeback_cell_detail, name="writeback_cell_detail"),
    path("olap/writeback-cells/<int:pk>/edit/", views.writeback_cell_edit, name="writeback_cell_edit"),
    path("olap/writeback-cells/<int:pk>/delete/", views.writeback_cell_delete, name="writeback_cell_delete"),
]
