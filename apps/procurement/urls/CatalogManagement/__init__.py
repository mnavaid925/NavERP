"""Procurement 6.9 Catalog Management URL patterns — one module per entity."""
from .CatalogItems import urlpatterns as _cat_items
from .PunchOutEndpoints import urlpatterns as _cat_punchout
from .Tiers import urlpatterns as _cat_tiers
from .UploadBatches import urlpatterns as _cat_uploads

urlpatterns = [
    *_cat_items,      # 6.9 catalog item register + approval lifecycle
    *_cat_tiers,      # 6.9 volume/contract price tiers (propose→approve)
    *_cat_punchout,   # 6.9 punch-out endpoint configuration (+ test stamp)
    *_cat_uploads,    # 6.9 supplier catalog upload batches (validate/stage/publish)
]
