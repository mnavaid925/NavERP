from django.urls import path

from apps.bi.views.Dashboards import BiDashboardBookmarks as views

urlpatterns = [
    path("dashboards/bookmarks/", views.bi_dashboard_bookmark_list, name="bi_dashboard_bookmark_list"),
    path("dashboards/bookmarks/create/", views.bi_dashboard_bookmark_create, name="bi_dashboard_bookmark_create"),
    path("dashboards/bookmarks/<int:pk>/", views.bi_dashboard_bookmark_detail, name="bi_dashboard_bookmark_detail"),
    path("dashboards/bookmarks/<int:pk>/edit/", views.bi_dashboard_bookmark_edit, name="bi_dashboard_bookmark_edit"),
    path("dashboards/bookmarks/<int:pk>/delete/", views.bi_dashboard_bookmark_delete, name="bi_dashboard_bookmark_delete"),
    path("dashboards/bookmarks/<int:pk>/apply/", views.bi_dashboard_bookmark_apply, name="bi_dashboard_bookmark_apply"),
]
