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
from apps.quality.models.CalibrationAnalysis.CalibrationGages import (
    CalibrationGage,
)
from apps.quality.models.CalibrationAnalysis.CalibrationRecords import (
    CalibrationRecord,
)
from apps.quality.models.CalibrationAnalysis.OutOfToleranceInvestigations import (
    OutOfToleranceInvestigation,
)
from apps.quality.models.CalibrationAnalysis.MeasurementSystemAnalyses import (
    MeasurementSystemAnalysis,
)
from apps.quality.models.FinalQuality.CertificatesOfConformance import (
    CertificateOfConformance,
)
from apps.quality.models.FinalQuality.FinalInspectionLots import (
    FinalInspectionLot,
)
from apps.quality.models.FinalQuality.PackagingLabelVerifications import (
    PackagingLabelVerification,
)
from apps.quality.models.FinalQuality.QualityReleaseAuthorizations import (
    QualityReleaseAuthorization,
)
from apps.quality.models.AuditManagement.AuditPrograms import (
    AuditProgram,
)
from apps.quality.models.AuditManagement.QualityAudits import (
    QualityAudit,
)
from apps.quality.models.AuditManagement.AuditFindings import (
    AuditFinding,
)
from apps.quality.models.AuditManagement.RegulatoryInspectionHosts import (
    RegulatoryInspectionHost,
)
from apps.quality.models.TrainingCompetency.CompetencyMatrices import (
    CompetencyMatrix,
)
from apps.quality.models.TrainingCompetency.QualityTrainingCourses import (
    QualityTrainingCourse,
)
from apps.quality.models.TrainingCompetency.TrainingEnrollments import (
    TrainingEnrollment,
)
from apps.quality.models.TrainingCompetency.CompetencyCertifications import (
    CompetencyCertification,
)
from apps.quality.models.CustomerComplaints.CustomerComplaints import (
    CustomerComplaint,
)
from apps.quality.models.CustomerComplaints.ComplaintInvestigations import (
    ComplaintInvestigation,
)
from apps.quality.models.CustomerComplaints.RegulatoryReports import (
    RegulatoryReport,
)
from apps.quality.models.CustomerComplaints.FieldActions import (
    FieldAction,
)
from apps.quality.models.ManagementReview.QualityObjectives import (
    QualityObjective,
)
from apps.quality.models.ManagementReview.ManagementReviews import (
    ManagementReview,
)
from apps.quality.models.ManagementReview.ManagementReviewInputs import (
    ManagementReviewInput,
)
from apps.quality.models.ManagementReview.ManagementReviewActions import (
    ManagementReviewAction,
)
from apps.quality.models.ProcessValidation.ValidationProtocols import (
    ValidationProtocol,
)
from apps.quality.models.ProcessValidation.ProcessCapabilityStudies import (
    ProcessCapabilityStudy,
)
from apps.quality.models.ProcessValidation.ComputerSystemValidations import (
    ComputerSystemValidation,
)
from apps.quality.models.ProcessValidation.CleaningValidations import (
    CleaningValidation,
)
from apps.quality.models.EhsManagement.HazardousMaterials import (
    HazardousMaterial,
)
from apps.quality.models.EhsManagement.SafetyIncidents import (
    SafetyIncident,
)
from apps.quality.models.EhsManagement.EnvironmentalMonitoringLogs import (
    EnvironmentalMonitoringLog,
)
from apps.quality.models.EhsManagement.WasteDisposalManifests import (
    WasteDisposalManifest,
)
from apps.quality.models.RegulatorySubmissions.RegulatorySubmissions import (
    RegulatorySubmission,
)
from apps.quality.models.RegulatorySubmissions.ProductRegistrations import (
    ProductRegistration,
)
from apps.quality.models.RegulatorySubmissions.RegulatoryCommitments import (
    RegulatoryCommitment,
)
from apps.quality.models.RegulatorySubmissions.PostMarketSurveillanceReports import (
    PostMarketSurveillanceReport,
)
from apps.quality.models.TraceabilitySerialization.BatchRecords import (
    BatchRecord,
)
from apps.quality.models.TraceabilitySerialization.DeviceIdentifiers import (
    DeviceIdentifier,
)
from apps.quality.models.TraceabilitySerialization.SerializedItems import (
    SerializedItem,
)
from apps.quality.models.TraceabilitySerialization.ProductRecalls import (
    ProductRecall,
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
    "CalibrationGage",
    "CalibrationRecord",
    "OutOfToleranceInvestigation",
    "MeasurementSystemAnalysis",
    "FinalInspectionLot",
    "CertificateOfConformance",
    "PackagingLabelVerification",
    "QualityReleaseAuthorization",
    "AuditProgram",
    "QualityAudit",
    "AuditFinding",
    "RegulatoryInspectionHost",
    "CompetencyMatrix",
    "QualityTrainingCourse",
    "TrainingEnrollment",
    "CompetencyCertification",
    "CustomerComplaint",
    "ComplaintInvestigation",
    "RegulatoryReport",
    "FieldAction",
    "QualityObjective",
    "ManagementReview",
    "ManagementReviewInput",
    "ManagementReviewAction",
    "ValidationProtocol",
    "ProcessCapabilityStudy",
    "ComputerSystemValidation",
    "CleaningValidation",
    "HazardousMaterial",
    "SafetyIncident",
    "EnvironmentalMonitoringLog",
    "WasteDisposalManifest",
    "RegulatorySubmission",
    "ProductRegistration",
    "RegulatoryCommitment",
    "PostMarketSurveillanceReport",
    "BatchRecord",
    "DeviceIdentifier",
    "SerializedItem",
    "ProductRecall",
]

