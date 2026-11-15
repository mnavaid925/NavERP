from apps.quality.urls.DocumentControl.ControlledDocuments import (
    urlpatterns as controlled_documents_urls,
)
from apps.quality.urls.DocumentControl.DocumentAcknowledgments import (
    urlpatterns as document_acknowledgments_urls,
)
from apps.quality.urls.DocumentControl.DocumentChangeOrders import (
    urlpatterns as document_change_orders_urls,
)
from apps.quality.urls.DocumentControl.ElectronicSignatures import (
    urlpatterns as electronic_signatures_urls,
)

app_name = "quality"

urlpatterns = (
    controlled_documents_urls
    + document_change_orders_urls
    + electronic_signatures_urls
    + document_acknowledgments_urls
)
