from apps.documents.views.RecordsManagement.DestructionCertificates import (
    destruction_certificate_authorize,
    destruction_certificate_create,
    destruction_certificate_detail,
    destruction_certificate_execute,
    destruction_certificate_list,
)
from apps.documents.views.RecordsManagement.DispositionReview import disposition_review_board
from apps.documents.views.RecordsManagement.DocumentLegalHolds import (
    legal_hold_acknowledge,
    legal_hold_create,
    legal_hold_detail,
    legal_hold_list,
    legal_hold_release,
)
from apps.documents.views.RecordsManagement.RecordDeclarations import (
    record_declaration_create,
    record_declaration_delete,
    record_declaration_detail,
    record_declaration_edit,
    record_declaration_list,
    record_declaration_trigger_cutoff,
)
from apps.documents.views.RecordsManagement.RetentionSchedules import (
    retention_schedule_create,
    retention_schedule_delete,
    retention_schedule_detail,
    retention_schedule_edit,
    retention_schedule_list,
)
from apps.documents.views.RecordsManagement.VitalRecords import vital_records_list

__all__ = [
    "retention_schedule_list",
    "retention_schedule_detail",
    "retention_schedule_create",
    "retention_schedule_edit",
    "retention_schedule_delete",
    "record_declaration_list",
    "record_declaration_detail",
    "record_declaration_create",
    "record_declaration_edit",
    "record_declaration_delete",
    "record_declaration_trigger_cutoff",
    "legal_hold_list",
    "legal_hold_detail",
    "legal_hold_create",
    "legal_hold_release",
    "legal_hold_acknowledge",
    "destruction_certificate_list",
    "destruction_certificate_detail",
    "destruction_certificate_create",
    "destruction_certificate_authorize",
    "destruction_certificate_execute",
    "disposition_review_board",
    "vital_records_list",
]
