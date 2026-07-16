"""HRM 3.16 Tax & Investment — Taxregimeconfig URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # ===================== 3.16 Tax & Investment =====================
    # Tax regime config (+ inline slab bands) + regime comparison
    path("tax-regimes/", views.taxregimeconfig_list, name="taxregimeconfig_list"),
    path("tax-regimes/add/", views.taxregimeconfig_create, name="taxregimeconfig_create"),
    path("tax-regimes/<int:pk>/", views.taxregimeconfig_detail, name="taxregimeconfig_detail"),
    path("tax-regimes/<int:pk>/edit/", views.taxregimeconfig_edit, name="taxregimeconfig_edit"),
    path("tax-regimes/<int:pk>/delete/", views.taxregimeconfig_delete, name="taxregimeconfig_delete"),
    path("tax-regimes/<int:config_pk>/slab-bands/add/", views.taxslabband_create, name="taxslabband_create"),
    path("tax-regimes/<int:config_pk>/slab-bands/<int:pk>/edit/", views.taxslabband_edit, name="taxslabband_edit"),
    path("tax-regimes/<int:config_pk>/slab-bands/<int:pk>/delete/", views.taxslabband_delete, name="taxslabband_delete"),
]
