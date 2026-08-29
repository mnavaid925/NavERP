"""Procurement 6.10 Purchase Order Management — PurchaseOrderChanges URL patterns.

Filed from a purchase order's page (``orders/<pk>/change/``), decided on the change's own
detail page. Literal routes precede ``<int:pk>`` — Django is first-match-wins.
"""
from django.urls import path

from apps.procurement import views


urlpatterns = [
    path("po-changes/", views.poc_list, name="poc_list"),
    path("po-changes/<int:pk>/", views.poc_detail, name="poc_detail"),
    path("po-changes/<int:pk>/approve/", views.poc_approve, name="poc_approve"),
    path("po-changes/<int:pk>/reject/", views.poc_reject, name="poc_reject"),
    path("po-changes/new/<int:purchase_order_pk>/", views.poc_create, name="poc_create"),
]
