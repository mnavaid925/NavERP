from django.urls import path
from apps.bi.views.MasterData import MdmHierarchyNodes as views

urlpatterns = [
    path("mdm/hierarchy-nodes/", views.mdm_hierarchy_node_list, name="mdm_hierarchy_node_list"),
    path("mdm/hierarchy-nodes/create/", views.mdm_hierarchy_node_create, name="mdm_hierarchy_node_create"),
    path("mdm/hierarchy-nodes/<int:pk>/", views.mdm_hierarchy_node_detail, name="mdm_hierarchy_node_detail"),
    path("mdm/hierarchy-nodes/<int:pk>/edit/", views.mdm_hierarchy_node_edit, name="mdm_hierarchy_node_edit"),
    path("mdm/hierarchy-nodes/<int:pk>/delete/", views.mdm_hierarchy_node_delete, name="mdm_hierarchy_node_delete"),
]
