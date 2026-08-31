"""Procurement 6.14 Spend Analytics & Reporting — classification workbench route.

One route, ``spend/classification/`` — a literal child of the ``spend/`` first segment this
sub-module's computed pages share (``spend/``, ``spend/categories/``, ``spend/export/``,
``spend/export/download/`` in ``SpendDashboards.py``; ``spend/maverick/`` and
``spend/maverick/scan/`` in ``MaverickDashboard.py``). Django matches whole path components, so
``classification`` cannot be swallowed by any of them and none of them can be swallowed by it.

The page is READ-ONLY: there is no POST route here. Writing a rule is
``procurement:spendrule_create``, which every row on the page deep-links with its own prefill.
"""
from django.urls import path

from apps.procurement import views


urlpatterns = [
    path("spend/classification/", views.classification_workbench,
         name="classification_workbench"),
]
