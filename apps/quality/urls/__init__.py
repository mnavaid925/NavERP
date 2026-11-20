from apps.quality.urls.CapaManagement.CapaActions import (
    urlpatterns as capa_actions_urls,
)
from apps.quality.urls.CapaManagement.CapaEffectivenessReviews import (
    urlpatterns as capa_effectiveness_reviews_urls,
)
from apps.quality.urls.CapaManagement.CapaInvestigations import (
    urlpatterns as capa_investigations_urls,
)
from apps.quality.urls.CapaManagement.CapaTrackingBoard import (
    urlpatterns as capa_tracking_board_urls,
)
from apps.quality.urls.CapaManagement.RootCauseAnalyses import (
    urlpatterns as root_cause_analyses_urls,
)
from apps.quality.urls.DesignControls.DesignInputs import (
    urlpatterns as design_inputs_urls,
)
from apps.quality.urls.DesignControls.DesignProjects import (
    urlpatterns as design_projects_urls,
)
from apps.quality.urls.DesignControls.DesignReviews import (
    urlpatterns as design_reviews_urls,
)
from apps.quality.urls.DesignControls.DesignVerifications import (
    urlpatterns as design_verifications_urls,
)
from apps.quality.urls.DesignControls.TraceabilityMatrix import (
    urlpatterns as traceability_matrix_urls,
)
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
from apps.quality.urls.NonConformance.MrbDispositions import (
    urlpatterns as mrb_dispositions_urls,
)
from apps.quality.urls.NonConformance.NcrAnalytics import (
    urlpatterns as ncr_analytics_urls,
)
from apps.quality.urls.NonConformance.NonConformanceReports import (
    urlpatterns as non_conformance_reports_urls,
)
from apps.quality.urls.NonConformance.ProcessDeviations import (
    urlpatterns as process_deviations_urls,
)
from apps.quality.urls.NonConformance.QuarantineContainments import (
    urlpatterns as quarantine_containments_urls,
)
from apps.quality.urls.RiskManagement.FmeaMatrix import (
    urlpatterns as fmea_matrix_urls,
)
from apps.quality.urls.RiskManagement.RiskAssessments import (
    urlpatterns as risk_assessments_urls,
)
from apps.quality.urls.RiskManagement.RiskControlMeasures import (
    urlpatterns as risk_control_measures_urls,
)
from apps.quality.urls.RiskManagement.RiskManagementPlans import (
    urlpatterns as risk_management_plans_urls,
)
from apps.quality.urls.RiskManagement.RiskReviewRecords import (
    urlpatterns as risk_review_records_urls,
)
from apps.quality.urls.SupplierQuality.SupplierChangeNotifications import (
    urlpatterns as supplier_change_notifications_urls,
)
from apps.quality.urls.SupplierQuality.SupplierCorrectiveActions import (
    urlpatterns as supplier_corrective_actions_urls,
)
from apps.quality.urls.SupplierQuality.SupplierQualificationAudits import (
    urlpatterns as supplier_qualification_audits_urls,
)
from apps.quality.urls.SupplierQuality.SupplierQualityDirectory import (
    urlpatterns as supplier_quality_directory_urls,
)
from apps.quality.urls.IncomingQuality.CertificatesOfAnalysis import (
    urlpatterns as certificates_of_analysis_urls,
)
from apps.quality.urls.IncomingQuality.IncomingInspectionLots import (
    urlpatterns as incoming_inspection_lots_urls,
)
from apps.quality.urls.IncomingQuality.IncomingInspectionPlans import (
    urlpatterns as incoming_inspection_plans_urls,
)
from apps.quality.urls.IncomingQuality.IqcSpcDashboard import (
    urlpatterns as iqc_spc_dashboard_urls,
)
from apps.quality.urls.IncomingQuality.QualityReturnAuthorizations import (
    urlpatterns as quality_return_authorizations_urls,
)
from apps.quality.urls.SupplierQuality.SupplierQualityScorecards import (
    urlpatterns as supplier_quality_scorecards_urls,
)
from apps.quality.urls.InProcessQuality.FirstArticleInspections import (
    urlpatterns as first_article_inspections_urls,
)
from apps.quality.urls.InProcessQuality.InProcessInspections import (
    urlpatterns as in_process_inspections_urls,
)
from apps.quality.urls.InProcessQuality.LayeredProcessAudits import (
    urlpatterns as layered_process_audits_urls,
)
from apps.quality.urls.InProcessQuality.ProcessParameterLogs import (
    urlpatterns as process_parameter_logs_urls,
)
from apps.quality.urls.InProcessQuality.SpcDashboard import (
    urlpatterns as ipqc_spc_dashboard_urls,
)
from apps.quality.urls.CalibrationAnalysis.CalibrationGages import (
    urlpatterns as calibration_gages_urls,
)
from apps.quality.urls.CalibrationAnalysis.CalibrationRecords import (
    urlpatterns as calibration_records_urls,
)
from apps.quality.urls.CalibrationAnalysis.OutOfToleranceInvestigations import (
    urlpatterns as oot_investigations_urls,
)
from apps.quality.urls.CalibrationAnalysis.MeasurementSystemAnalyses import (
    urlpatterns as msa_studies_urls,
)
from apps.quality.urls.CalibrationAnalysis.CalibrationVendors import (
    urlpatterns as calibration_vendors_urls,
)
from apps.quality.urls.FinalQuality.CertificatesOfConformance import (
    urlpatterns as certificates_of_conformance_urls,
)
from apps.quality.urls.FinalQuality.FinalInspectionLots import (
    urlpatterns as final_inspection_lots_urls,
)
from apps.quality.urls.FinalQuality.OqcHoldBoard import (
    urlpatterns as oqc_hold_board_urls,
)
from apps.quality.urls.FinalQuality.PackagingLabelVerifications import (
    urlpatterns as packaging_label_verifications_urls,
)
from apps.quality.urls.FinalQuality.QualityReleaseAuthorizations import (
    urlpatterns as quality_release_authorizations_urls,
)
from apps.quality.urls.AuditManagement import (
    urlpatterns as audit_management_urls,
)
from apps.quality.urls.TrainingCompetency import (
    urlpatterns as training_competency_urls,
)

app_name = "quality"

urlpatterns = (
    controlled_documents_urls
    + document_change_orders_urls
    + electronic_signatures_urls
    + document_acknowledgments_urls
    + design_projects_urls
    + design_inputs_urls
    + design_reviews_urls
    + design_verifications_urls
    + traceability_matrix_urls
    + risk_management_plans_urls
    + risk_assessments_urls
    + risk_control_measures_urls
    + risk_review_records_urls
    + fmea_matrix_urls
    + capa_investigations_urls
    + root_cause_analyses_urls
    + capa_actions_urls
    + capa_effectiveness_reviews_urls
    + capa_tracking_board_urls
    + non_conformance_reports_urls
    + quarantine_containments_urls
    + mrb_dispositions_urls
    + process_deviations_urls
    + ncr_analytics_urls
    + supplier_qualification_audits_urls
    + supplier_quality_scorecards_urls
    + supplier_corrective_actions_urls
    + supplier_change_notifications_urls
    + supplier_quality_directory_urls
    + incoming_inspection_plans_urls
    + incoming_inspection_lots_urls
    + certificates_of_analysis_urls
    + quality_return_authorizations_urls
    + iqc_spc_dashboard_urls
    + in_process_inspections_urls
    + first_article_inspections_urls
    + process_parameter_logs_urls
    + layered_process_audits_urls
    + ipqc_spc_dashboard_urls
    + calibration_gages_urls
    + calibration_records_urls
    + oot_investigations_urls
    + msa_studies_urls
    + calibration_vendors_urls
    + final_inspection_lots_urls
    + certificates_of_conformance_urls
    + packaging_label_verifications_urls
    + quality_release_authorizations_urls
    + oqc_hold_board_urls
    + audit_management_urls
    + training_competency_urls
)

