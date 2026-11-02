from django.urls import path
from apps.ecommerce.views.B2bWholesale import B2bQuoteRequests as views

urlpatterns = [
    path("b2b/quotes/", views.b2bquoterequest_list, name="b2bquoterequest_list"),
    path("b2b/quotes/new/", views.b2bquoterequest_create, name="b2bquoterequest_create"),
    path("b2b/quotes/<int:pk>/", views.b2bquoterequest_detail, name="b2bquoterequest_detail"),
    path("b2b/quotes/<int:pk>/edit/", views.b2bquoterequest_edit, name="b2bquoterequest_edit"),
    path("b2b/quotes/<int:pk>/delete/", views.b2bquoterequest_delete, name="b2bquoterequest_delete"),
    path("b2b/quotes/<int:pk>/submit/", views.b2bquoterequest_submit, name="b2bquoterequest_submit"),
    path("b2b/quotes/<int:pk>/quote/", views.b2bquoterequest_quote, name="b2bquoterequest_quote"),
    path("b2b/quotes/<int:pk>/accept/", views.b2bquoterequest_accept, name="b2bquoterequest_accept"),
    path("b2b/quotes/<int:pk>/reject/", views.b2bquoterequest_reject, name="b2bquoterequest_reject"),
    path("b2b/quotes/<int:pk>/convert-order/", views.b2bquoterequest_convert_order, name="b2bquoterequest_convert_order"),
]
