"""SCM 4.12 Contract & Compliance — TradeDocument routes (prefix ``trade-documents/``).

COLLISION CHECK — ``trade-documents/`` was checked against the WHOLE concatenated urlconf, not
merely against this block: no existing ``scm`` first segment starts with ``trade`` at all, so the
segment is free. It is also a distinct whole path component from 4.12's own ``trade-licenses/`` —
Django matches whole path components and never splits one at the hyphen, so neither can shadow the
other, and neither may be "tidied" to look like the other.

``add/`` is literal and MUST precede ``<int:pk>/`` — Django is first-match-wins, so a pk route above
it would swallow the create page and 404 as "document 'add' not found". The five verb routes all sit
under their own ``<int:pk>/`` and are POST-only at the view; a GET to one is a 405, not a silent
state change. This module introduces NO greedy ``<str:…>`` converter: 4.10's
``return-tracking/<str:token>/`` remains the app's only one.

``<int:pk>/print/`` is a GET (it renders a page), which is why it is the one ``<int:pk>/<verb>/``
route here that is not ``@require_POST``.
"""
from django.urls import path

from apps.scm import views

urlpatterns = [
    path("trade-documents/", views.tradedocument_list, name="tradedocument_list"),
    # Literal — must stay above every <int:pk> route below it.
    path("trade-documents/add/", views.tradedocument_create, name="tradedocument_create"),
    path("trade-documents/<int:pk>/", views.tradedocument_detail, name="tradedocument_detail"),
    path("trade-documents/<int:pk>/edit/", views.tradedocument_edit, name="tradedocument_edit"),
    path("trade-documents/<int:pk>/delete/", views.tradedocument_delete,
         name="tradedocument_delete"),
    # The lifecycle: draft/amended -> issued -> submitted -> accepted, with void reachable from any
    # of them. Issuing is what charges the licence balance and voiding is what gives it back.
    path("trade-documents/<int:pk>/issue/", views.tradedocument_issue, name="tradedocument_issue"),
    path("trade-documents/<int:pk>/submit/", views.tradedocument_submit,
         name="tradedocument_submit"),
    path("trade-documents/<int:pk>/accept/", views.tradedocument_accept,
         name="tradedocument_accept"),
    path("trade-documents/<int:pk>/void/", views.tradedocument_void, name="tradedocument_void"),
    path("trade-documents/<int:pk>/print/", views.tradedocument_print, name="tradedocument_print"),
]
