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

**Build order — COMPLETE.** All six modules are concatenated: the three entity modules
(``Policies``, ``Runs``, ``MaterialIssues``) and the three derived read-only page modules
(``StockPosition``, ``ReceiptBinMap``, ``CountAccuracy``). Each appended its own line here as it
landed, rather than this file importing a module that did not exist yet and taking the whole
URLconf down with it. **The sub-package now contributes exactly 27 patterns** — the count the
contract's §3 table freezes, and the number ``apps/procurement/urls/__init__.py`` expects to gain
when the Integrator includes this package. If that total moves, a route was added, dropped or
renamed away from the frozen contract.

The three derived pages carry ONE pattern each and no ``<int:pk>`` route at all: they own no model,
so there is nothing to address by pk. They are declared last purely because they landed last —
their first segments (``stock-position/``, ``receipt-bin-map/``, ``count-accuracy/``) are unique
whole components, so position in this list cannot change which pattern wins.
"""
from .CountAccuracy import urlpatterns as _iwi_countaccuracy
from .MaterialIssues import urlpatterns as _iwi_materialissues
from .Policies import urlpatterns as _iwi_policies
from .ReceiptBinMap import urlpatterns as _iwi_receiptbinmap
from .Runs import urlpatterns as _iwi_runs
from .StockPosition import urlpatterns as _iwi_stockposition


urlpatterns = [
    *_iwi_policies,         # replenishment-policies/ CRUD                            (5)
    *_iwi_runs,             # replenishment-runs/ CRUD + generate/release/cancel + decide (9)
    *_iwi_materialissues,   # material-issues/ CRUD + submit/post/cancel + line add/delete (10)
    *_iwi_stockposition,    # stock-position/ — derived, read-only                    (1)
    *_iwi_receiptbinmap,    # receipt-bin-map/ — derived, read-only                   (1)
    *_iwi_countaccuracy,    # count-accuracy/ — derived, read-only                    (1)
]                           #                                                    total 27
