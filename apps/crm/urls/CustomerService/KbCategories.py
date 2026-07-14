"""CRM 1.4 Customer Service & Support — KbCategories URL patterns (split from apps/crm/urls.py)."""
from django.urls import path

from apps.crm import views


urlpatterns = [
    # KB categories (1.4)
    path("kb-categories/", views.kbcategory_list, name="kbcategory_list"),
    path("kb-categories/add/", views.kbcategory_create, name="kbcategory_create"),
    path("kb-categories/<int:pk>/", views.kbcategory_detail, name="kbcategory_detail"),
    path("kb-categories/<int:pk>/edit/", views.kbcategory_edit, name="kbcategory_edit"),
    path("kb-categories/<int:pk>/delete/", views.kbcategory_delete, name="kbcategory_delete"),
]
