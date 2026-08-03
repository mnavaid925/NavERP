"""SCM 4.13 Asset Management — ``Asset`` routes (prefix ``assets/``) and its spare-parts child
(prefix ``asset-spare-parts/``).

COLLISION CHECK — both prefixes were checked against the WHOLE concatenated urlconf, not merely
against this block: **nothing anywhere in ``scm`` starts with ``asset``**. ``assets/``,
``asset-spare-parts/`` and 4.13's own ``asset-depreciation/`` (in ``Reports.py``) are three DISTINCT
whole path components — Django matches whole components and never splits one at a hyphen, so none of
the three can shadow either of the others, and none of them may be "tidied" to look like another.
This module introduces NO greedy ``<str:…>`` converter; 4.10's ``return-tracking/<str:token>/``
remains the app's only one.

``add/`` is literal and MUST precede ``<int:pk>/``: Django is first-match-wins, so a pk route above
it would swallow the create page and then 404 as "asset 'add' not found".

THE CHILD HANGS OFF ITS OWN PK. ``asset-spare-parts/<int:pk>/edit/`` and ``…/delete/`` are NOT
nested under the asset — a child pk already identifies its parent, and nesting would invite a caller
to pair a real line with somebody else's asset id (the ``compliance-checks/`` rationale). The one
exception is the ADD route, which is nested under ``assets/<int:pk>/`` on purpose: there is no child
yet, so the parent has to come from somewhere, and taking it from the URL rather than from a POST
field is what stops a crafted body grafting a line onto another workspace's machine.
``AssetSparePart`` carries no ``tenant`` column, so every view here resolves it through
``asset__tenant``.

``asset-spare-parts/`` has NO list and NO detail route, and that is a decision: a parts list is a
panel on the asset it belongs to, and a workspace-wide list of "every part line on every machine" is
the spare-parts REPORT (``scm:sparepart_list``), which reads 4.3's ledger rather than this join
table. Both edit and delete redirect back to the parent's detail page for the same reason.
"""
from django.urls import path

from apps.scm import views

urlpatterns = [
    path("assets/", views.asset_list, name="asset_list"),
    # Literal — must stay above every <int:pk> route below it.
    path("assets/add/", views.asset_create, name="asset_create"),
    path("assets/<int:pk>/", views.asset_detail, name="asset_detail"),
    path("assets/<int:pk>/edit/", views.asset_edit, name="asset_edit"),
    path("assets/<int:pk>/delete/", views.asset_delete, name="asset_delete"),
    # The ONE parent-nested child route — the parent comes from the URL, never from the POST body.
    path("assets/<int:pk>/spare-parts/add/", views.asset_add_spare_part,
         name="asset_add_spare_part"),
    # …and the two that take the child's OWN pk. See the module docstring for why they are not
    # nested under the asset.
    path("asset-spare-parts/<int:pk>/edit/", views.assetsparepart_edit,
         name="assetsparepart_edit"),
    path("asset-spare-parts/<int:pk>/delete/", views.assetsparepart_delete,
         name="assetsparepart_delete"),
]
