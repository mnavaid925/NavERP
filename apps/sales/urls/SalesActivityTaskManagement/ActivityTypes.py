"""Sales 8.8 — URLs for the activity-type catalogue.

Five routes. **THE ORDER INSIDE THIS FILE IS BEHAVIOUR, NOT STYLE**: Django resolves
first-match-wins, so the literal ``activity-types/add/`` MUST precede ``activity-types/<int:pk>/`` —
listed below it, ``int("add")`` raises ``ValueError`` and the register is a 500 rather than a page.

No pattern here can be captured by another module's route: every one begins with the literal segment
``activity-types/``, verified free against the whole concatenated ``sales:urlpatterns`` list, not
just against this file.

No ``?return_to=`` anywhere. A caller-supplied redirect target is an open redirect waiting to be
phished; every POST here redirects to a name this module owns.
"""
from django.urls import path

from apps.sales.views.SalesActivityTaskManagement.ActivityTypes import (
    activity_type_create,
    activity_type_delete,
    activity_type_detail,
    activity_type_edit,
    activity_type_list,
)

urlpatterns = [
    path("activity-types/", activity_type_list, name="activity_type_list"),
    # THE LITERAL MUST PRECEDE <int:pk>/ — see the module docstring.
    path("activity-types/add/", activity_type_create, name="activity_type_create"),
    path("activity-types/<int:pk>/edit/", activity_type_edit, name="activity_type_edit"),
    path("activity-types/<int:pk>/delete/", activity_type_delete, name="activity_type_delete"),
    # The bare keyed page is LAST — it is the only pattern here a sibling literal could lose to.
    path("activity-types/<int:pk>/", activity_type_detail, name="activity_type_detail"),
]