from django.urls import path

from apps.bi.views.SemanticLayer import DrillHierarchies as views

urlpatterns = [
    path("semantic/hierarchies/", views.drill_hierarchy_list, name="drill_hierarchy_list"),
    path("semantic/hierarchies/create/", views.drill_hierarchy_create, name="drill_hierarchy_create"),
    path("semantic/hierarchies/<int:pk>/", views.drill_hierarchy_detail, name="drill_hierarchy_detail"),
    path("semantic/hierarchies/<int:pk>/edit/", views.drill_hierarchy_edit, name="drill_hierarchy_edit"),
    path("semantic/hierarchies/<int:pk>/delete/", views.drill_hierarchy_delete, name="drill_hierarchy_delete"),
]
