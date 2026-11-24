from apps.documents.urls.RecordsManagement.DestructionCertificates import (
    urlpatterns as destruction_certificate_urls,
)
from apps.documents.urls.RecordsManagement.DispositionReview import (
    urlpatterns as disposition_review_urls,
)
from apps.documents.urls.RecordsManagement.DocumentLegalHolds import (
    urlpatterns as legal_hold_urls,
)
from apps.documents.urls.RecordsManagement.RecordDeclarations import (
    urlpatterns as record_declaration_urls,
)
from apps.documents.urls.RecordsManagement.RetentionSchedules import (
    urlpatterns as retention_schedule_urls,
)
from apps.documents.urls.RecordsManagement.VitalRecords import (
    urlpatterns as vital_records_urls,
)

urlpatterns = (
    retention_schedule_urls
    + record_declaration_urls
    + legal_hold_urls
    + destruction_certificate_urls
    + disposition_review_urls
    + vital_records_urls
)
