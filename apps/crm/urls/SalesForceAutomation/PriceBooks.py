"""CRM 1.2 Sales Force Automation — PriceBooks URL patterns (split from apps/crm/urls.py)."""
from django.urls import path

from apps.crm import views


urlpatterns = [
    # Price books (1.2 Quoting)
    path("price-books/", views.pricebook_list, name="pricebook_list"),
    path("price-books/add/", views.pricebook_create, name="pricebook_create"),
    path("price-books/<int:pk>/", views.pricebook_detail, name="pricebook_detail"),
    path("price-books/<int:pk>/edit/", views.pricebook_edit, name="pricebook_edit"),
    path("price-books/<int:pk>/delete/", views.pricebook_delete, name="pricebook_delete"),
]
