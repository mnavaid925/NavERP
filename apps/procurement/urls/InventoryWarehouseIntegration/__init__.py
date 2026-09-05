"""6.18 Inventory & Warehouse Integration URL patterns — one module per views module.

``app_name`` is set once in ``apps/procurement/urls/__init__.py``; this package only concatenates
its entity/page modules' ``urlpatterns``.

Six first segments belong to this sub-module, every one of them a new whole component checked
against the inventory in ``apps/procurement/urls/__init__.py``: ``replenishment-policies/``,
``replenishment-runs/``, ``material-issues/``, ``stock-position/``, ``receipt-bin-map/`` and
``count-accuracy/``. None is a prefix of any other segment in the app — Django matches path
components, not strings.

**Shadowing surface, stated accurately.** No route in this app uses a converter in its FIRST path
component — every first segment is a literal — so no module can shadow another's namespace.
(The commonly copy-pasted claim that the app "registers no greedy ``<str:…>`` converter anywhere"
is simply false: ``contract-sign/<str:token>/`` exists at
``apps/procurement/urls/ContractsManagement/Contracts.py:16``. It is harmless precisely because
its greedy converter sits in the SECOND component, behind a literal first one — which is the
invariant that actually holds, and the one worth stating.) Verify it with::

    grep -rnE 'path\\(\\s*["'"'"']<' apps/procurement/urls/

which returns nothing.

**Build order.** Only ``Policies`` is concatenated so far. ``Runs``, ``MaterialIssues``,
``StockPosition``, ``ReceiptBinMap`` and ``CountAccuracy`` are the same sub-module's remaining
entity/page modules and each appends its own line here as it lands, rather than this file
importing a module that does not exist yet and taking the whole URLconf down with it.
"""
from .Policies import urlpatterns as _iwi_policies


urlpatterns = [
    *_iwi_policies,   # replenishment-policies/ CRUD
]
