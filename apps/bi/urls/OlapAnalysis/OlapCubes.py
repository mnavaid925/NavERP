from django.urls import path

from apps.bi.views.OlapAnalysis import OlapCubes as views

urlpatterns = [
    path("olap/cubes/", views.olap_cube_list, name="olap_cube_list"),
    path("olap/cubes/create/", views.olap_cube_create, name="olap_cube_create"),
    path("olap/cubes/<int:pk>/", views.olap_cube_detail, name="olap_cube_detail"),
    path("olap/cubes/<int:pk>/edit/", views.olap_cube_edit, name="olap_cube_edit"),
    path("olap/cubes/<int:pk>/delete/", views.olap_cube_delete, name="olap_cube_delete"),
    path("olap/cubes/<int:pk>/refresh/", views.olap_cube_refresh, name="olap_cube_refresh"),
]
