from apps.quality.models._base import TenantNumbered, TenantOwned
from apps.quality.models.CapaManagement.CapaActions import CapaAction
from apps.quality.models.CapaManagement.CapaEffectivenessReviews import CapaEffectivenessReview
from apps.quality.models.CapaManagement.CapaInvestigations import CapaInvestigation
from apps.quality.models.CapaManagement.RootCauseAnalyses import RootCauseAnalysis
from apps.quality.models.DesignControls.DesignInputs import DesignInput
from apps.quality.models.DesignControls.DesignProjects import DesignProject
from apps.quality.models.DesignControls.DesignReviews import DesignReview
from apps.quality.models.DesignControls.DesignVerifications import DesignVerification
from apps.quality.models.DocumentControl.ControlledDocuments import ControlledDocument
from apps.quality.models.DocumentControl.DocumentAcknowledgments import DocumentAcknowledgment
from apps.quality.models.DocumentControl.DocumentChangeOrders import DocumentChangeOrder
from apps.quality.models.DocumentControl.ElectronicSignatures import ElectronicSignatureRecord
from apps.quality.models.NonConformance.MrbDispositions import MrbDisposition
from apps.quality.models.NonConformance.NonConformanceReports import NonConformanceReport
from apps.quality.models.NonConformance.ProcessDeviations import ProcessDeviation
from apps.quality.models.NonConformance.QuarantineContainments import QuarantineContainment
from apps.quality.models.RiskManagement.RiskAssessments import RiskAssessment
from apps.quality.models.RiskManagement.RiskControlMeasures import RiskControlMeasure
from apps.quality.models.RiskManagement.RiskManagementPlans import RiskManagementPlan
from apps.quality.models.RiskManagement.RiskReviewRecords import RiskReviewRecord
from apps.quality.models.IncomingQuality.CertificatesOfAnalysis import (
    CertificateOfAnalysis,
)
from apps.quality.models.IncomingQuality.IncomingInspectionLots import (
    IncomingInspectionLot,
)
from apps.quality.models.IncomingQuality.IncomingInspectionPlans import (
    IncomingInspectionPlan,
)
from apps.quality.models.IncomingQuality.QualityReturnAuthorizations import (
    QualityReturnAuthorization,
)
from apps.quality.models.SupplierQuality.SupplierChangeNotifications import (
    SupplierChangeNotification,
)
from apps.quality.models.SupplierQuality.SupplierCorrectiveActions import (
    SupplierCorrectiveAction,
)
from apps.quality.models.SupplierQuality.SupplierQualificationAudits import (
    SupplierQualificationAudit,
)
from apps.quality.models.SupplierQuality.SupplierQualityScorecards import (
    SupplierQualityScorecard,
)
from apps.quality.models.InProcessQuality.FirstArticleInspections import (
    FirstArticleInspection,
)
from apps.quality.models.InProcessQuality.InProcessInspections import (
    InProcessInspection,
)
from apps.quality.models.InProcessQuality.LayeredProcessAudits import (
    LayeredProcessAudit,
)
from apps.quality.models.InProcessQuality.ProcessParameterLogs import (
    ProcessParameterLog,
)

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
    "RiskManagementPlan",
    "RiskAssessment",
    "RiskControlMeasure",
    "RiskReviewRecord",
    "CapaInvestigation",
    "RootCauseAnalysis",
    "CapaAction",
    "CapaEffectivenessReview",
    "NonConformanceReport",
    "QuarantineContainment",
    "MrbDisposition",
    "ProcessDeviation",
    "SupplierQualificationAudit",
    "SupplierQualityScorecard",
    "SupplierCorrectiveAction",
    "SupplierChangeNotification",
    "IncomingInspectionPlan",
    "IncomingInspectionLot",
    "CertificateOfAnalysis",
    "QualityReturnAuthorization",
    "InProcessInspection",
    "FirstArticleInspection",
    "ProcessParameterLog",
    "LayeredProcessAudit",
]

