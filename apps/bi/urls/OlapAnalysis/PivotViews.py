from django.urls import path

from apps.bi.views.OlapAnalysis import PivotViews as views

urlpatterns = [
    path("olap/pivots/", views.pivot_view_list, name="pivot_view_list"),
    path("olap/pivots/create/", views.pivot_view_create, name="pivot_view_create"),
    path("olap/pivots/<int:pk>/", views.pivot_view_detail, name="pivot_view_detail"),
    path("olap/pivots/<int:pk>/edit/", views.pivot_view_edit, name="pivot_view_edit"),
    path("olap/pivots/<int:pk>/delete/", views.pivot_view_delete, name="pivot_view_delete"),
    path("olap/pivots/<int:pk>/matrix/", views.pivot_view_matrix, name="pivot_view_matrix"),
]
