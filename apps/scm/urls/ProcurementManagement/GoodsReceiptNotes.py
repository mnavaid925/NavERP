"""SCM 4.1 Procurement Management — GoodsReceiptNotes URL patterns."""
from django.urls import path

from apps.scm import views


urlpatterns = [
    # Literal routes MUST precede the <int:pk> ones — Django is first-match-wins.
    path("receipts/", views.goodsreceipt_list, name="goodsreceipt_list"),
    path("receipts/add/", views.goodsreceipt_create, name="goodsreceipt_create"),
    path("receipts/<int:pk>/", views.goodsreceipt_detail, name="goodsreceipt_detail"),
    path("receipts/<int:pk>/edit/", views.goodsreceipt_edit, name="goodsreceipt_edit"),
    path("receipts/<int:pk>/delete/", views.goodsreceipt_delete, name="goodsreceipt_delete"),
    path("receipts/<int:pk>/receive/", views.goodsreceipt_receive, name="goodsreceipt_receive"),
    path("receipts/<int:pk>/cancel/", views.goodsreceipt_cancel, name="goodsreceipt_cancel"),
    path("receipts/<int:pk>/rematch/", views.goodsreceipt_rematch, name="goodsreceipt_rematch"),
]
