"""Procurement 6.17 Risk & Compliance Management — ScreeningHit URL patterns.

One first segment, ``screening-hits/``, collision-checked as a whole component against the
concatenated inventory in ``apps/procurement/urls/__init__.py``. Django matches path components,
not strings, so ``screening-hits/`` and ``screenings/`` are two distinct segments and neither can
shadow the other; the app registers no greedy ``<str:…>`` converter either.

There is no ``screening-hits/add/`` route on purpose: a hit only exists under a screening, so it
is created at ``screenings/<int:pk>/hits/add/`` (registered in ``Screenings.py``, next to the
segment it belongs to). Every route below therefore takes the HIT's pk, and every one of them
resolves it with ``screening__tenant=request.tenant`` — ``ScreeningHit`` is tenant-less, so the
parent FK is the only tenant boundary there is.

``delete/`` and ``dispose/`` are POST-only through their view decorators.
"""
from django.urls import path

from apps.procurement import views


urlpatterns = [
    path("screening-hits/", views.screeninghit_list, name="screeninghit_list"),
    path("screening-hits/<int:pk>/", views.screeninghit_detail, name="screeninghit_detail"),
    path("screening-hits/<int:pk>/edit/", views.screeninghit_edit, name="screeninghit_edit"),
    path("screening-hits/<int:pk>/delete/", views.screeninghit_delete,
         name="screeninghit_delete"),
    path("screening-hits/<int:pk>/dispose/", views.screeninghit_dispose,
         name="screeninghit_dispose"),
]
