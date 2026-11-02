from django.urls import path
from apps.ecommerce.views.B2bWholesale import B2bQuickOrderTemplates as views

urlpatterns = [
    path("b2b/templates/", views.b2bquickordertemplate_list, name="b2bquickordertemplate_list"),
    path("b2b/templates/new/", views.b2bquickordertemplate_create, name="b2bquickordertemplate_create"),
    path("b2b/templates/<int:pk>/", views.b2bquickordertemplate_detail, name="b2bquickordertemplate_detail"),
    path("b2b/templates/<int:pk>/edit/", views.b2bquickordertemplate_edit, name="b2bquickordertemplate_edit"),
    path("b2b/templates/<int:pk>/delete/", views.b2bquickordertemplate_delete, name="b2bquickordertemplate_delete"),
    path("b2b/quick-order/", views.b2b_quick_order_matrix, name="b2b_quick_order_matrix"),
]
