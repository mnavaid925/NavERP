from apps.quality.forms.CapaManagement.CapaActions import CapaActionForm
from apps.quality.forms.CapaManagement.CapaEffectivenessReviews import CapaEffectivenessReviewForm
from apps.quality.forms.CapaManagement.CapaInvestigations import CapaInvestigationForm
from apps.quality.forms.CapaManagement.RootCauseAnalyses import RootCauseAnalysisForm
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
from apps.quality.forms.RiskManagement.RiskAssessments import RiskAssessmentForm
from apps.quality.forms.RiskManagement.RiskControlMeasures import RiskControlMeasureForm
from apps.quality.forms.RiskManagement.RiskManagementPlans import RiskManagementPlanForm
from apps.quality.forms.RiskManagement.RiskReviewRecords import RiskReviewRecordForm

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
    "RiskManagementPlanForm",
    "RiskAssessmentForm",
    "RiskControlMeasureForm",
    "RiskReviewRecordForm",
    "CapaInvestigationForm",
    "RootCauseAnalysisForm",
    "CapaActionForm",
    "CapaEffectivenessReviewForm",
]

