from django.urls import path

from apps.quality.views.TraceabilitySerialization import ProductRecalls as views

urlpatterns = [
    path("traceability/recalls/", views.product_recall_list, name="product_recall_list"),
    path("traceability/recalls/create/", views.product_recall_create, name="product_recall_create"),
    path("traceability/recalls/<int:pk>/", views.product_recall_detail, name="product_recall_detail"),
    path("traceability/recalls/<int:pk>/edit/", views.product_recall_edit, name="product_recall_edit"),
    path("traceability/recalls/<int:pk>/delete/", views.product_recall_delete, name="product_recall_delete"),
]
