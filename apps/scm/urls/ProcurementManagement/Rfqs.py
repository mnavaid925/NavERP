"""SCM 4.1 Procurement Management — RFQ + quote URL patterns."""
from django.urls import path

from apps.scm import views


urlpatterns = [
    # Literal routes MUST precede the <int:pk> ones — Django is first-match-wins.
    path("rfqs/", views.rfq_list, name="rfq_list"),
    path("rfqs/add/", views.rfq_create, name="rfq_create"),
    path("rfqs/<int:pk>/", views.rfq_detail, name="rfq_detail"),
    path("rfqs/<int:pk>/edit/", views.rfq_edit, name="rfq_edit"),
    path("rfqs/<int:pk>/delete/", views.rfq_delete, name="rfq_delete"),
    path("rfqs/<int:pk>/send/", views.rfq_send, name="rfq_send"),
    path("rfqs/<int:pk>/close/", views.rfq_close, name="rfq_close"),
    path("rfqs/<int:pk>/compare/", views.rfq_compare, name="rfq_compare"),
    # Quotes are children of an RFQ — creating one names its parent.
    path("rfqs/<int:rfq_pk>/quotes/add/", views.quote_create, name="quote_create"),
    path("quotes/<int:pk>/edit/", views.quote_edit, name="quote_edit"),
    path("quotes/<int:pk>/delete/", views.quote_delete, name="quote_delete"),
    path("quotes/<int:pk>/award/", views.quote_award, name="quote_award"),
]
