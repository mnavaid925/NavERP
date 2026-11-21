from apps.quality.urls.TraceabilitySerialization.BatchRecords import (
    urlpatterns as batch_records_urls,
)
from apps.quality.urls.TraceabilitySerialization.DeviceIdentifiers import (
    urlpatterns as device_identifiers_urls,
)
from apps.quality.urls.TraceabilitySerialization.ProductRecalls import (
    urlpatterns as product_recalls_urls,
)
from apps.quality.urls.TraceabilitySerialization.SerializedItems import (
    urlpatterns as serialized_items_urls,
)
from apps.quality.urls.TraceabilitySerialization.TraceabilityDashboard import (
    urlpatterns as traceability_dashboard_urls,
)

urlpatterns = (
    traceability_dashboard_urls
    + batch_records_urls
    + device_identifiers_urls
    + serialized_items_urls
    + product_recalls_urls
)
