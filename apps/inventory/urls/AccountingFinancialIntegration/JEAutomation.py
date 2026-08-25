"""Inventory 5.18 Accounting & Financial Integration — routes.

Prefixes are distinct whole components (``finance/…``, ``tax-rules``,
``gl-post-rules``); every verb is a literal segment ending in its own token before
the ``<int:pk>`` patterns, so nothing shadows detail/edit/delete.
"""
from django.urls import path

from apps.inventory import views

urlpatterns = [
    # -- AP integration ----------------------------------------------------------------------
    path("finance/ap-sync/", views.ap_sync, name="ap_sync"),
    path("finance/ap-sync/<int:pk>/run/", views.ap_sync_run, name="ap_sync_run"),
    # -- AR integration ----------------------------------------------------------------------
    path("finance/ar-sync/", views.ar_sync, name="ar_sync"),
    path("finance/ar-sync/<int:pk>/run/", views.ar_sync_run, name="ar_sync_run"),
    # -- JE automation ------------------------------------------------------------------------
    path("finance/je-automation/", views.je_automation, name="je_automation"),
    path("finance/je-automation/adjustments/<int:pk>/post/", views.je_post_adjustment,
         name="je_post_adjustment"),
    path("finance/je-automation/cogs/post/", views.je_post_cogs, name="je_post_cogs"),
]
