"""SCM 4.3 Inventory Management — ReorderRule URL patterns."""
from django.urls import path

from apps.scm import views


urlpatterns = [
    path("reorder-rules/", views.reorderrule_list, name="reorderrule_list"),
    path("reorder-rules/add/", views.reorderrule_create, name="reorderrule_create"),
    path("reorder-rules/<int:pk>/edit/", views.reorderrule_edit, name="reorderrule_edit"),
    path("reorder-rules/<int:pk>/delete/", views.reorderrule_delete, name="reorderrule_delete"),
]
