from apps.quality.models._base import TenantNumbered, TenantOwned
from apps.quality.models.DocumentControl.ControlledDocuments import ControlledDocument
from apps.quality.models.DocumentControl.DocumentAcknowledgments import DocumentAcknowledgment
from apps.quality.models.DocumentControl.DocumentChangeOrders import DocumentChangeOrder
from apps.quality.models.DocumentControl.ElectronicSignatures import ElectronicSignatureRecord

__all__ = [
    "TenantOwned",
    "TenantNumbered",
    "ControlledDocument",
    "DocumentChangeOrder",
    "ElectronicSignatureRecord",
    "DocumentAcknowledgment",
]
