"""SCM 4.18 Finance & Accounting Integration — ``LandedCostVoucher`` routes.

Full CRUD plus the four-rung verb ladder (``allocate → accrue → draft-bill``, and ``cancel``), plus
three routes for the cost charges.

COLLISION CHECK — checked against the WHOLE concatenated urlconf rather than against this block
alone: **nothing anywhere in ``apps/scm`` starts with ``landed``, ``duty`` or ``finance``.**
``landed-cost-vouchers`` and ``landed-cost-charges`` are two DISTINCT whole path components; Django
matches whole components and never splits one at a hyphen, so neither can shadow the other — and
NEITHER MAY EVER BE "TIDIED" into a shared ``landed-cost/<something>/`` parent, which would make them
the same first component and put their ordering at the mercy of concatenation order across entity
modules. The 4.18 report routes (``landed-cost-variance/``) are a third distinct component under the
same rule.

Near neighbours that are NOT collisions, checked rather than assumed: 4.6's ``loads/`` and
``freight-invoices/``, 4.1's ``goods-receipts/``, 4.12's ``trade-documents/`` / ``trade-licenses/``,
4.17's ``client-billing-runs/``.

4.18 introduces NO greedy ``<str:…>`` converter — 4.10's ``return-tracking/<str:token>/`` and 4.16's
``portal-documents/<str:token>/`` remain the app's only two.

ORDER IS BEHAVIOUR. ``add/`` is LITERAL and stays above the ``<int:pk>/`` block: Django is
first-match-wins, and although the ``int`` converter would refuse to match ``add`` today, the
convention is what keeps a later ``<str:…>`` route from swallowing the create page and 404-ing as
"landed cost voucher 'add' not found".

**The charge routes are split on purpose, and the split is a security decision, not a style one.**
``landed-cost-vouchers/<int:pk>/charges/add/`` nests under the PARENT because the voucher has to come
from the ROUTE — a parent pk in a POST body is how a caller grafts a charge onto another workspace's
voucher (the 4.17 ``client-billing-runs/<int:pk>/lines/add/`` precedent). ``edit`` and ``delete``
take the CHARGE's own pk instead, because the child pk already identifies the row and nesting it
would invite a caller to pair a real child with somebody else's parent id. Both are scoped through
``voucher__tenant=request.tenant`` at the view regardless.

Every verb route is POST-only AT THE VIEW, so a GET to one is a 405 rather than a silent state
change; all four verbs are additionally ``@tenant_admin_required`` (L27).
"""
from django.urls import path

from apps.scm import views

urlpatterns = [
    path("landed-cost-vouchers/", views.landedcostvoucher_list, name="landedcostvoucher_list"),
    # LITERAL — must stay above the <int:pk> block below.
    path("landed-cost-vouchers/add/", views.landedcostvoucher_create,
         name="landedcostvoucher_create"),

    path("landed-cost-vouchers/<int:pk>/", views.landedcostvoucher_detail,
         name="landedcostvoucher_detail"),
    path("landed-cost-vouchers/<int:pk>/edit/", views.landedcostvoucher_edit,
         name="landedcostvoucher_edit"),
    path("landed-cost-vouchers/<int:pk>/delete/", views.landedcostvoucher_delete,
         name="landedcostvoucher_delete"),

    # --- the verb ladder: draft → allocated → accrued → reconciled (cancel while unbilled) ---
    path("landed-cost-vouchers/<int:pk>/allocate/", views.landedcostvoucher_allocate,
         name="landedcostvoucher_allocate"),
    path("landed-cost-vouchers/<int:pk>/accrue/", views.landedcostvoucher_accrue,
         name="landedcostvoucher_accrue"),
    path("landed-cost-vouchers/<int:pk>/draft-bill/", views.landedcostvoucher_draft_bill,
         name="landedcostvoucher_draft_bill"),
    path("landed-cost-vouchers/<int:pk>/cancel/", views.landedcostvoucher_cancel,
         name="landedcostvoucher_cancel"),

    # --- cost charges ---
    # NESTED: pk is the VOUCHER. The parent comes from the route, never from the POST body.
    path("landed-cost-vouchers/<int:pk>/charges/add/", views.landedcostcharge_create,
         name="landedcostcharge_create"),
    # OWN pk: pk is the CHARGE. A separate first segment, so nothing above can shadow these.
    path("landed-cost-charges/<int:pk>/edit/", views.landedcostcharge_edit,
         name="landedcostcharge_edit"),
    path("landed-cost-charges/<int:pk>/delete/", views.landedcostcharge_delete,
         name="landedcostcharge_delete"),
]
