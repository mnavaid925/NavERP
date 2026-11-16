from django.urls import path

from apps.quality.views.DesignControls import DesignProjects as views

urlpatterns = [
    path("design-controls/projects/", views.design_project_list, name="design_project_list"),
    path("design-controls/projects/export/", views.design_project_export, name="design_project_export"),
    path("design-controls/projects/create/", views.design_project_create, name="design_project_create"),
    path("design-controls/projects/<int:pk>/", views.design_project_detail, name="design_project_detail"),
    path("design-controls/projects/<int:pk>/edit/", views.design_project_edit, name="design_project_edit"),
    path("design-controls/projects/<int:pk>/delete/", views.design_project_delete, name="design_project_delete"),
    path("design-controls/projects/<int:pk>/advance-phase/", views.design_project_advance_phase, name="design_project_advance_phase"),
    path("design-controls/projects/<int:pk>/lock-dhf/", views.design_project_lock_dhf, name="design_project_lock_dhf"),
]
