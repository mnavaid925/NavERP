from apps.quality.forms.DesignControls.DesignInputs import DesignInputForm
from apps.quality.forms.DesignControls.DesignProjects import DesignProjectForm
from apps.quality.forms.DesignControls.DesignReviews import DesignReviewForm
from apps.quality.forms.DesignControls.DesignVerifications import DesignVerificationForm
from apps.quality.forms.DocumentControl.ControlledDocuments import (
    ControlledDocumentForm,
    ControlledDocumentRevisionForm,
)
from apps.quality.forms.DocumentControl.DocumentAcknowledgments import DocumentAcknowledgmentForm
from apps.quality.forms.DocumentControl.DocumentChangeOrders import DocumentChangeOrderForm
from apps.quality.forms.DocumentControl.ElectronicSignatures import ElectronicSignatureForm

__all__ = [
    "ControlledDocumentForm",
    "ControlledDocumentRevisionForm",
    "DocumentChangeOrderForm",
    "ElectronicSignatureForm",
    "DocumentAcknowledgmentForm",
    "DesignProjectForm",
    "DesignInputForm",
    "DesignReviewForm",
    "DesignVerificationForm",
]
