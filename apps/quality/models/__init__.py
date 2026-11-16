from apps.quality.models._base import TenantNumbered, TenantOwned
from apps.quality.models.DesignControls.DesignInputs import DesignInput
from apps.quality.models.DesignControls.DesignProjects import DesignProject
from apps.quality.models.DesignControls.DesignReviews import DesignReview
from apps.quality.models.DesignControls.DesignVerifications import DesignVerification
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
    "DesignProject",
    "DesignInput",
    "DesignReview",
    "DesignVerification",
]
