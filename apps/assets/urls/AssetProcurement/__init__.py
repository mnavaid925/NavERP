from apps.assets.urls.AssetProcurement.AssetAcquisitionReceipts import (
    urlpatterns as receipt_urlpatterns,
)
from apps.assets.urls.AssetProcurement.AssetCapitalizations import (
    urlpatterns as capitalization_urlpatterns,
)
from apps.assets.urls.AssetProcurement.AssetRequisitions import (
    urlpatterns as requisition_urlpatterns,
)
from apps.assets.urls.AssetProcurement.AssetTags import (
    urlpatterns as tag_urlpatterns,
)

urlpatterns = (
    requisition_urlpatterns
    + receipt_urlpatterns
    + capitalization_urlpatterns
    + tag_urlpatterns
)
