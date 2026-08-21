"""Inventory URLconf package — one sub-package per NavERP sub-module, one module per entity.

Each entity module exposes its own ``urlpatterns``; this __init__ sets ``app_name = "inventory"``
once and concatenates them.

Django is first-match-wins: within each module the literal routes (`add/`) precede the
``<int:pk>/`` ones. The app introduces NO greedy ``<str:…>`` converter, so there is no cross-module
shadowing surface to reason about; the four first segments (``, `attributes/`, `prices/`,
`files/`) are distinct whole components and none can swallow another.
"""
from .Catalog.ItemAttributes import urlpatterns as _cat_itemattributes
from .Catalog.ItemPrices import urlpatterns as _cat_itemprices
from .Catalog.ProductFiles import urlpatterns as _cat_productfiles
from .Catalog.Overview import urlpatterns as _cat_overview


app_name = "inventory"

urlpatterns = [
    *_cat_overview,        # Catalog/Overview — "" (module landing)
    *_cat_itemattributes,  # Catalog/ItemAttributes
    *_cat_itemprices,      # Catalog/ItemPrices
    *_cat_productfiles,    # Catalog/ProductFiles
]
