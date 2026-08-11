"""SCM 4.15 Cold Chain Management — ``ColdChainMonitor`` routes (prefix ``cold-chain-monitors/``).

Full CRUD plus three derived actions: the temperature profile, the per-monitor detection pass and the
whole-workspace sweep.

COLLISION CHECK — ``cold-chain-monitors/`` was checked against the WHOLE concatenated urlconf, not
merely against this block: **nothing anywhere in ``scm`` starts with ``cold``.** Django matches WHOLE
path components and never splits one at a hyphen, so ``cold-chain-monitors``, ``cold-storage-report``
and ``cold-chain-compliance`` (4.15's report module) are three UNRELATED segments; none can shadow
another, and none may ever be "tidied" to look like another. Near neighbours that are NOT collisions,
checked rather than assumed: 4.12's ``compliance-requirements/`` and ``compliance-checks/``, 4.3's
``categories/`` and ``locations/``, 4.6's ``carriers/``.

This module introduces NO greedy ``<str:…>`` converter — 4.10's ``return-tracking/<str:token>/``
remains the app's only one.

ORDER IS BEHAVIOUR. ``add/`` and ``detect/`` are LITERAL and must stay above the ``<int:pk>/`` block:
Django is first-match-wins, and although the ``int`` converter would refuse to match ``add`` today,
the convention is what keeps a later ``<str:…>`` route from swallowing the create page and 404-ing as
"monitor 'add' not found".

``cold-chain-monitors/<int:pk>/readings/add/`` and ``…/readings/import/`` are NOT declared here — they
create a ``TemperatureReading``, so they live in this package's ``TemperatureReadings`` module beside
the thing they create (the 4.14 ``laborsession_add_activity`` precedent). They carry more path
segments than ``<int:pk>/``, so nothing in this file can shadow them wherever they are concatenated.

Every verb route is POST-only AT THE VIEW, so a GET to one is a 405 rather than a silent state
change, and both detection routes are additionally ``@tenant_admin_required``.
"""
from django.urls import path

from apps.scm import views

urlpatterns = [
    path("cold-chain-monitors/", views.coldchainmonitor_list, name="coldchainmonitor_list"),
    # LITERAL — both must stay above the <int:pk> block below.
    path("cold-chain-monitors/add/", views.coldchainmonitor_create, name="coldchainmonitor_create"),
    # The whole-workspace detection sweep. POST-only, tenant-admin only, and it redirects to the
    # excursion queue because the queue is what the pass changes.
    path("cold-chain-monitors/detect/", views.coldchain_detect, name="coldchain_detect"),

    path("cold-chain-monitors/<int:pk>/", views.coldchainmonitor_detail,
         name="coldchainmonitor_detail"),
    path("cold-chain-monitors/<int:pk>/edit/", views.coldchainmonitor_edit,
         name="coldchainmonitor_edit"),
    path("cold-chain-monitors/<int:pk>/delete/", views.coldchainmonitor_delete,
         name="coldchainmonitor_delete"),
    # The temperature profile — bullet 4's headline artefact. A GET page whose window is a QUERY
    # STRING (?date_from=&date_to=), so it adds no route of its own beyond this one.
    path("cold-chain-monitors/<int:pk>/profile/", views.coldchainmonitor_profile,
         name="coldchainmonitor_profile"),
    # The per-monitor detection pass — the button on the detail page.
    path("cold-chain-monitors/<int:pk>/detect/", views.coldchainmonitor_detect,
         name="coldchainmonitor_detect"),
]
