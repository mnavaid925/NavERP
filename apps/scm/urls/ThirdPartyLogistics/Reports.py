"""SCM 4.17 Third-Party Logistics (3PL) — the two COMPUTED report pages: ``client-inventory/`` and
``client-space/``.

Two of this sub-module's five NavERP bullets are PAGES rather than tables (the ``sparepart_list`` /
``labor_board`` / ``cold_storage_report`` precedent), so neither adds a model, a form or a write of
any kind:

* ``client-inventory/`` — **Client Inventory Segregation**, derived over 4.3's item master
  (``Item.owner_client``) and the append-only ``StockMove`` ledger. Options are all query string:
  ``?client=&category=&location=``.
* ``client-space/`` — **Warehouse Rental Management**, derived over the client record's space
  commitment and the ``Location`` rows reserved to it. Options: ``?client=&space_model=``.

Neither takes an ``<int:pk>``, because neither is about one record: the client id arrives as a
FILTER (``?client=``) so the page keeps its totals row and its dropdown while narrowing. That also
means neither route can shadow a literal, since there is no converter here to be greedy with.

COLLISION CHECK — both prefixes checked against the WHOLE concatenated urlconf, not merely against
the 4.17 block:

* Nothing anywhere in ``apps/scm`` starts with ``client`` except this sub-module's own
  ``client-rate-cards`` / ``client-rate-card-lines`` / ``client-billing-runs`` /
  ``client-billing-run-lines`` and the two below. Django matches WHOLE path components and never
  splits one at a hyphen, so ``client-inventory``, ``client-space``, ``client-rate-cards`` and
  ``client-billing-runs`` are unrelated first segments; none shadows another and **none may ever be
  "tidied" into a shared ``clients/<something>/`` parent**, which would turn independent segments
  into one greedy component.
* ``client-inventory/`` is a DISTINCT whole component from 4.3's ``items/`` /
  ``stock-moves/`` / ``locations/`` and from 4.5's ``inventory``-flavoured routes; ``client-space/``
  shares no component with anything shipped.

**VIEW-NAME collision check:** ``client_inventory_report`` and ``client_space_report`` were compared
against every ``name=`` value in ``apps/scm/urls/**`` and collide with nothing. (Existing report
names in the app are ``cold_storage_report``, ``valuation_report``, ``ap_aging``-style pages and
4.11's ``logistics_kpis`` — no overlap.)

**Neither page writes anything**, so neither has a POST route: no stock movement, no journal entry
(L29), no client or item column. They are GET pages, and every option they take is a query string.
"""
from django.urls import path

from apps.scm import views

urlpatterns = [
    # Whose stock is whose, what it is worth, and which SKUs nobody has assigned yet.
    path("client-inventory/", views.client_inventory_report, name="client_inventory_report"),
    # Committed space beside the bins actually reserved — with NO invented conversion between them.
    path("client-space/", views.client_space_report, name="client_space_report"),
]
