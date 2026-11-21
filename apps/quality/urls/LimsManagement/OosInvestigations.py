from django.urls import path

from apps.quality.views.LimsManagement import OosInvestigations as views

urlpatterns = [
    path("lims/oos/", views.oos_investigation_list, name="oos_investigation_list"),
    path("lims/oos/create/", views.oos_investigation_create, name="oos_investigation_create"),
    path("lims/oos/<int:pk>/", views.oos_investigation_detail, name="oos_investigation_detail"),
    path("lims/oos/<int:pk>/edit/", views.oos_investigation_edit, name="oos_investigation_edit"),
    path("lims/oos/<int:pk>/delete/", views.oos_investigation_delete, name="oos_investigation_delete"),
    path("lims/oos/<int:pk>/close/", views.oos_investigation_close, name="oos_investigation_close"),
]
