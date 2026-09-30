"""Sales 8.7 — URLs for quota plans.

Nine routes, and the four action verbs sit under their own ``<int:pk>/`` prefix rather than
hanging off a bare plan pk, so an action is never indistinguishable from a detail route.

**THE ORDER INSIDE THIS FILE IS BEHAVIOUR, NOT STYLE**: Django resolves first-match-wins, so
the literal ``quota-plans/add/`` MUST precede ``quota-plans/<int:pk>/`` — listed below it,
``int("add")`` raises ``ValueError`` and the register is a 500 rather than a page. The same
class of bug is why 8.5's greedy ``quotes/portal/<str:token>/`` is the cautionary tale
everywhere in this sub-module.

The four verbs — ``submit/``, ``approve/``, ``reject/`` and ``lock/`` — are **POST-only** in
the view. They drive the plan's approval lifecycle and ``lock/`` freezes the plan's computed
amount, so a GET that performed any of them would let a prefetch, a crawler or a link preview
advance or freeze a quota by touching a URL.

**A plan records *how* a quota was derived, never the quota itself.** The amount is edited
on CRM 1.2's ``crm.SalesQuota``, in CRM's form, by CRM's permission set; 8.7 reads that table
and never writes it (contract §0.3). The plan inherits its window from ``sales.ForecastPeriod``
(8.4) and does not re-spell year / quarter / month.

No ``?return_to=`` anywhere. A caller-supplied redirect target is an open redirect waiting to
be phished; every POST here redirects to a name this module owns.

No pattern here can be captured by another module's route: every one begins with the literal
segment ``quota-plans/``, which was verified free against the whole concatenated
``sales:urlpatterns`` list — the 8.5 greedy ``quotes/portal/<str:token>/`` is scoped inside
``quotes/`` and cannot reach it.
"""
from django.urls import path

from apps.sales.views.TerritoryQuotaManagement.QuotaPlans import (
    quota_plan_approve,
    quota_plan_create,
    quota_plan_delete,
    quota_plan_detail,
    quota_plan_edit,
    quota_plan_list,
    quota_plan_lock,
    quota_plan_reject,
    quota_plan_submit,
)


urlpatterns = [
    path(
        "quota-plans/",
        quota_plan_list,
        name="quota_plan_list",
    ),
    # THE LITERAL MUST PRECEDE <int:pk>/ — see the module docstring.
    path(
        "quota-plans/add/",
        quota_plan_create,
        name="quota_plan_create",
    ),
    # ---- the four POST-only lifecycle verbs ----
    path(
        "quota-plans/<int:pk>/submit/",
        quota_plan_submit,
        name="quota_plan_submit",
    ),
    path(
        "quota-plans/<int:pk>/approve/",
        quota_plan_approve,
        name="quota_plan_approve",
    ),
    path(
        "quota-plans/<int:pk>/reject/",
        quota_plan_reject,
        name="quota_plan_reject",
    ),
    path(
        "quota-plans/<int:pk>/lock/",
        quota_plan_lock,
        name="quota_plan_lock",
    ),
    path(
        "quota-plans/<int:pk>/edit/",
        quota_plan_edit,
        name="quota_plan_edit",
    ),
    path(
        "quota-plans/<int:pk>/delete/",
        quota_plan_delete,
        name="quota_plan_delete",
    ),
    # The bare keyed page is LAST — it is the only pattern here a sibling literal could lose to.
    path(
        "quota-plans/<int:pk>/",
        quota_plan_detail,
        name="quota_plan_detail",
    ),
]
