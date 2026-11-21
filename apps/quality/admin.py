from django.contrib import admin

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



@admin.register(DesignProject)
class DesignProjectAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "title",
        "device_name",
        "device_class",
        "regulatory_pathway",
        "current_phase",
        "status",
        "project_lead",
        "dhf_locked",
        "tenant",
    )
    list_filter = ("device_class", "regulatory_pathway", "current_phase", "status", "dhf_locked", "tenant")
    search_fields = ("number", "title", "device_name", "project_lead__username")
    list_select_related = ("tenant", "project_lead", "quality_lead", "department")


@admin.register(DesignInput)
class DesignInputAdmin(admin.ModelAdmin):
    list_display = (
        "identifier",
        "number",
        "title",
        "project",
        "input_type",
        "priority",
        "status",
        "owner",
        "tenant",
    )
    list_filter = ("input_type", "priority", "status", "tenant")
    search_fields = ("identifier", "number", "title", "project__number", "project__title")
    list_select_related = ("tenant", "project", "owner", "user_need_parent", "controlled_document")


@admin.register(DesignReview)
class DesignReviewAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "title",
        "project",
        "review_stage",
        "review_date",
        "status",
        "lead_reviewer",
        "independent_reviewer",
        "action_items_resolved",
        "tenant",
    )
    list_filter = ("review_stage", "status", "action_items_resolved", "tenant")
    search_fields = ("number", "title", "project__number", "lead_reviewer__username", "independent_reviewer__username")
    list_select_related = ("tenant", "project", "lead_reviewer", "independent_reviewer", "electronic_signature")


@admin.register(DesignVerification)
class DesignVerificationAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "title",
        "project",
        "primary_input",
        "activity_type",
        "test_method",
        "pass_fail_result",
        "status",
        "tenant",
    )
    list_filter = ("activity_type", "test_method", "pass_fail_result", "status", "tenant")
    search_fields = ("number", "title", "primary_input__identifier", "project__number")
    list_select_related = ("tenant", "project", "primary_input", "executed_by", "protocol_document", "report_document")


@admin.register(ControlledDocument)
class ControlledDocumentAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "title",
        "document_type",
        "revision",
        "lifecycle_state",
        "is_latest_revision",
        "department",
        "owner",
        "effective_date",
        "tenant",
    )
    list_filter = ("lifecycle_state", "document_type", "is_latest_revision", "classification", "tenant")
    search_fields = ("number", "title", "revision", "owner__username", "department__name")
    list_select_related = ("tenant", "owner", "department", "supersedes", "superseded_by")


@admin.register(DocumentChangeOrder)
class DocumentChangeOrderAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "title",
        "change_type",
        "priority",
        "document",
        "target_revision",
        "status",
        "ccb_decision",
        "requested_by",
        "tenant",
    )
    list_filter = ("status", "change_type", "priority", "ccb_decision", "tenant")
    search_fields = ("number", "title", "document__number", "document__title", "requested_by__username")
    list_select_related = ("tenant", "document", "requested_by", "ccb_decision_by")


@admin.register(ElectronicSignatureRecord)
class ElectronicSignatureRecordAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "document",
        "document_revision",
        "signer_name",
        "signature_meaning",
        "signature_timestamp",
        "tenant",
    )
    list_filter = ("signature_meaning", "tenant")
    search_fields = ("number", "signer_name", "signer__username", "document__number", "document__title")
    list_select_related = ("tenant", "document", "change_order", "signer")
    readonly_fields = ("signature_timestamp", "signature_hash", "ip_address")


@admin.register(DocumentAcknowledgment)
class DocumentAcknowledgmentAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "document",
        "document_revision",
        "user",
        "due_date",
        "status",
        "acknowledged_at",
        "tenant",
    )
    list_filter = ("status", "tenant")
    search_fields = ("number", "user__username", "document__number", "document__title")
    list_select_related = ("tenant", "document", "user", "employee", "signature_record")


@admin.register(RiskManagementPlan)
class RiskManagementPlanAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "title",
        "plan_version",
        "device_classification",
        "status",
        "design_project",
        "lead_risk_manager",
        "overall_residual_risk_acceptable",
        "next_review_due_date",
        "tenant",
    )
    list_filter = ("device_classification", "status", "overall_residual_risk_acceptable", "tenant")
    search_fields = ("number", "title", "design_project__number", "lead_risk_manager__username")
    list_select_related = ("tenant", "design_project", "lead_risk_manager", "department", "approved_signature")


@admin.register(RiskAssessment)
class RiskAssessmentAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "plan",
        "analysis_type",
        "hazard_category",
        "initial_rpn",
        "initial_risk_level",
        "residual_rpn",
        "residual_risk_level",
        "residual_risk_acceptable",
        "lifecycle_status",
        "tenant",
    )
    list_filter = ("analysis_type", "hazard_category", "initial_risk_level", "residual_risk_level", "lifecycle_status", "tenant")
    search_fields = ("number", "hazard_description", "failure_mode", "potential_harm", "plan__number", "plan__title")
    list_select_related = ("tenant", "plan", "design_input")


@admin.register(RiskControlMeasure)
class RiskControlMeasureAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "risk_assessment",
        "control_hierarchy",
        "title",
        "assigned_to",
        "implementation_verified",
        "effectiveness_verified",
        "status",
        "tenant",
    )
    list_filter = ("control_hierarchy", "status", "implementation_verified", "effectiveness_verified", "tenant")
    search_fields = ("number", "title", "risk_assessment__number", "risk_assessment__hazard_description", "assigned_to__username")
    list_select_related = ("tenant", "risk_assessment", "assigned_to", "design_input", "controlled_document", "design_verification")


@admin.register(RiskReviewRecord)
class RiskReviewRecordAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "plan",
        "review_title",
        "review_type",
        "review_date",
        "lead_reviewer",
        "overall_residual_risk_reconfirmed",
        "status",
        "tenant",
    )
    list_filter = ("review_type", "status", "overall_residual_risk_reconfirmed", "tenant")
    search_fields = ("number", "review_title", "findings_summary", "lead_reviewer__username", "plan__number", "plan__title")
    list_select_related = ("tenant", "plan", "lead_reviewer", "approved_signature")


@admin.register(CapaInvestigation)
class CapaInvestigationAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "title",
        "action_type",
        "source_type",
        "risk_priority",
        "status",
        "lead_investigator",
        "quality_owner",
        "target_closure_date",
        "is_escalated",
        "tenant",
    )
    list_filter = ("action_type", "source_type", "risk_priority", "status", "is_escalated", "containment_implemented", "tenant")
    search_fields = ("number", "title", "source_reference", "affected_item_code", "lead_investigator__username")
    list_select_related = ("tenant", "lead_investigator", "quality_owner", "department", "design_project", "risk_assessment")


@admin.register(RootCauseAnalysis)
class RootCauseAnalysisAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "capa",
        "rca_method",
        "root_cause_category",
        "status",
        "lead_investigator",
        "verified_by",
        "tenant",
    )
    list_filter = ("rca_method", "root_cause_category", "status", "tenant")
    search_fields = ("number", "problem_statement", "root_cause_summary", "capa__number", "lead_investigator__username")
    list_select_related = ("tenant", "capa", "lead_investigator", "verified_by")


@admin.register(CapaAction)
class CapaActionAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "capa",
        "action_type",
        "title",
        "assigned_to",
        "due_date",
        "status",
        "tenant",
    )
    list_filter = ("action_type", "status", "tenant")
    search_fields = ("number", "title", "description", "capa__number", "assigned_to__username")
    list_select_related = ("tenant", "capa", "root_cause", "assigned_to", "department", "verified_by")


@admin.register(CapaEffectivenessReview)
class CapaEffectivenessReviewAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "capa",
        "verification_method",
        "planned_review_date",
        "evaluator",
        "recurrence_observed",
        "outcome",
        "status",
        "tenant",
    )
    list_filter = ("verification_method", "recurrence_observed", "outcome", "status", "tenant")
    search_fields = ("number", "review_criteria", "review_notes", "capa__number", "evaluator__username")
    list_select_related = ("tenant", "capa", "evaluator", "formal_signature")


@admin.register(NonConformanceReport)
class NonConformanceReportAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "title",
        "source_type",
        "category",
        "severity",
        "status",
        "defect_code",
        "affected_item_code",
        "owner",
        "tenant",
    )
    list_filter = ("source_type", "category", "severity", "status", "tenant")
    search_fields = ("number", "title", "defect_code", "affected_item_code", "affected_item_name", "lot_serial_numbers", "owner__username")
    list_select_related = ("tenant", "department", "initiator", "owner", "supplier_party", "capa_investigation")


@admin.register(QuarantineContainment)
class QuarantineContainmentAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "ncr",
        "title",
        "hold_type",
        "quarantine_location",
        "red_tag_number",
        "quantity_on_hold",
        "status",
        "tenant",
    )
    list_filter = ("hold_type", "status", "tenant")
    search_fields = ("number", "title", "red_tag_number", "quarantine_location", "ncr__number")
    list_select_related = ("tenant", "ncr", "hold_applied_by", "released_by")


@admin.register(MrbDisposition)
class MrbDispositionAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "ncr",
        "title",
        "disposition_decision",
        "total_cost_impact",
        "mrb_chair",
        "reinspection_required",
        "reinspection_passed",
        "status",
        "tenant",
    )
    list_filter = ("disposition_decision", "status", "reinspection_required", "reinspection_passed", "tenant")
    search_fields = ("number", "title", "technical_justification", "ncr__number", "mrb_chair__username")
    list_select_related = ("tenant", "ncr", "mrb_chair", "rework_assignee", "quality_approved_by")


@admin.register(ProcessDeviation)
class ProcessDeviationAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "title",
        "deviation_type",
        "category",
        "risk_impact_level",
        "valid_until",
        "max_batches_permitted",
        "batches_produced_count",
        "status",
        "tenant",
    )
    list_filter = ("deviation_type", "category", "risk_impact_level", "status", "tenant")
    search_fields = ("number", "title", "quality_impact_assessment", "affected_lots_summary", "requested_by__username")
    list_select_related = ("tenant", "ncr", "controlled_document", "department", "requested_by", "approved_by")


@admin.register(SupplierQualificationAudit)
class SupplierQualificationAuditAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "supplier",
        "assessment_type",
        "criticality_tier",
        "qualification_status",
        "audit_result",
        "score",
        "dock_to_stock_eligible",
        "next_audit_due_date",
        "tenant",
    )
    list_filter = (
        "assessment_type",
        "criticality_tier",
        "qualification_status",
        "audit_result",
        "dock_to_stock_eligible",
        "requires_coa",
        "tenant",
    )
    search_fields = ("number", "supplier__name", "scope_commodities", "notes")
    list_select_related = ("tenant", "supplier", "lead_auditor", "quality_agreement")


@admin.register(SupplierQualityScorecard)
class SupplierQualityScorecardAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "supplier",
        "cadence",
        "period_start",
        "period_end",
        "overall_score",
        "grade",
        "status",
        "evaluated_by",
        "tenant",
    )
    list_filter = ("cadence", "grade", "status", "is_manual_override", "tenant")
    search_fields = ("number", "supplier__name", "override_justification", "evaluation_notes")
    list_select_related = ("tenant", "supplier", "evaluated_by")


@admin.register(SupplierCorrectiveAction)
class SupplierCorrectiveActionAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "supplier",
        "title",
        "severity",
        "status",
        "root_cause_category",
        "response_due_date",
        "is_effective",
        "closed_at",
        "tenant",
    )
    list_filter = ("severity", "status", "root_cause_category", "is_effective", "tenant")
    search_fields = ("number", "title", "supplier__name", "defect_summary", "affected_item_code")
    list_select_related = ("tenant", "supplier", "purchase_order", "non_conformance", "issued_by", "verified_by")


@admin.register(SupplierChangeNotification)
class SupplierChangeNotificationAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "supplier",
        "title",
        "change_category",
        "risk_level",
        "status",
        "disposition",
        "proposed_effective_date",
        "approved_by",
        "tenant",
    )
    list_filter = (
        "change_category",
        "risk_level",
        "status",
        "disposition",
        "affects_form_fit_function",
        "requires_requalification",
        "tenant",
    )
    search_fields = (
        "number",
        "title",
        "supplier__name",
        "supplier_scn_number",
        "description",
        "affected_item_code",
    )
    list_select_related = (
        "tenant",
        "supplier",
        "design_project",
        "requalification_audit",
        "approved_by",
        "evaluated_by",
    )


@admin.register(IncomingInspectionPlan)
class IncomingInspectionPlanAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "title",
        "item_code",
        "item_name",
        "revision",
        "supplier",
        "sampling_standard",
        "inspection_frequency",
        "status",
        "tenant",
    )
    list_filter = ("sampling_standard", "inspection_frequency", "status", "tenant")
    search_fields = ("number", "title", "item_code", "item_name", "supplier__name")
    list_select_related = ("tenant", "supplier", "sop_document", "assigned_team")


@admin.register(IncomingInspectionLot)
class IncomingInspectionLotAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "lot_number",
        "item_code",
        "item_name",
        "supplier",
        "lot_quantity",
        "sample_size",
        "stage",
        "usage_decision",
        "spc_cpk",
        "spc_out_of_control",
        "tenant",
    )
    list_filter = ("stage", "usage_decision", "spc_out_of_control", "tenant")
    search_fields = ("number", "lot_number", "item_code", "item_name", "supplier__name")
    list_select_related = ("tenant", "supplier", "inspection_plan", "inspector", "decided_by")


@admin.register(CertificateOfAnalysis)
class CertificateOfAnalysisAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "certificate_number",
        "item_code",
        "lot_number",
        "supplier",
        "is_within_spec",
        "variance_count",
        "status",
        "tenant",
    )
    list_filter = ("status", "is_within_spec", "tenant")
    search_fields = ("number", "certificate_number", "item_code", "lot_number", "supplier__name")
    list_select_related = ("tenant", "supplier", "inspection_lot", "inspection_plan", "verified_by")


@admin.register(QualityReturnAuthorization)
class QualityReturnAuthorizationAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "vendor_rma_number",
        "inspection_lot",
        "supplier",
        "return_reason",
        "disposition_type",
        "return_quantity",
        "estimated_credit_value",
        "status",
        "tenant",
    )
    list_filter = ("status", "disposition_type", "return_reason", "tenant")
    search_fields = ("number", "vendor_rma_number", "supplier__name", "carrier", "tracking_number")
    list_select_related = ("tenant", "supplier", "inspection_lot", "assigned_coordinator")


@admin.register(InProcessInspection)
class InProcessInspectionAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "title",
        "inspection_type",
        "item_code",
        "item_name",
        "lot_number",
        "production_order_number",
        "sample_size_inspected",
        "quantity_rejected",
        "disposition",
        "status",
        "tenant",
    )
    list_filter = ("inspection_type", "disposition", "status", "defect_category", "tenant")
    search_fields = ("number", "title", "item_code", "item_name", "lot_number", "production_order_number")
    list_select_related = ("tenant", "inspector", "operator")


@admin.register(FirstArticleInspection)
class FirstArticleInspectionAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "title",
        "setup_reason",
        "item_code",
        "item_name",
        "drawing_number",
        "drawing_revision",
        "production_order_number",
        "release_verdict",
        "status",
        "tenant",
    )
    list_filter = ("fai_type", "setup_reason", "release_verdict", "status", "tenant")
    search_fields = ("number", "title", "item_code", "item_name", "drawing_number", "production_order_number")
    list_select_related = ("tenant", "inspector", "approved_by")


@admin.register(ProcessParameterLog)
class ProcessParameterLogAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "parameter_name",
        "parameter_category",
        "work_center_code",
        "target_nominal_value",
        "recorded_value",
        "excursion_status",
        "containment_action",
        "tenant",
    )
    list_filter = ("parameter_category", "excursion_status", "containment_action", "tenant")
    search_fields = ("number", "parameter_name", "work_center_code", "production_order_number", "item_code")
    list_select_related = ("tenant", "logged_by")


@admin.register(LayeredProcessAudit)
class LayeredProcessAuditAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "title",
        "audit_layer",
        "focus_area",
        "work_center_code",
        "shift",
        "compliance_percentage",
        "status",
        "tenant",
    )
    list_filter = ("audit_layer", "focus_area", "status", "tenant")
    search_fields = ("number", "title", "work_center_code", "shift")
    list_select_related = ("tenant", "auditor")


@admin.register(CalibrationGage)
class CalibrationGageAdmin(admin.ModelAdmin):
    list_display = (
        "gage_id",
        "name",
        "gage_type",
        "criticality",
        "status",
        "max_permissible_error",
        "engineering_unit",
        "is_reference_standard",
        "next_calibration_due",
        "tenant",
    )
    list_filter = ("gage_type", "criticality", "status", "is_reference_standard", "tenant")
    search_fields = ("gage_id", "number", "name", "serial_number", "manufacturer")
    list_select_related = ("tenant", "custodian", "department", "work_center")


@admin.register(CalibrationRecord)
class CalibrationRecordAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "gage",
        "calibration_date",
        "calibration_type",
        "as_found_condition",
        "as_left_condition",
        "overall_result",
        "expanded_uncertainty",
        "status",
        "tenant",
    )
    list_filter = ("calibration_type", "overall_result", "as_found_condition", "status", "tenant")
    search_fields = ("number", "gage__gage_id", "gage__name", "certificate_number", "technician_name")
    list_select_related = ("tenant", "gage", "service_vendor", "calibrated_by_user", "approved_by")
    filter_horizontal = ("standards_used",)


@admin.register(OutOfToleranceInvestigation)
class OutOfToleranceInvestigationAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "title",
        "gage",
        "discovery_date",
        "risk_level",
        "status",
        "product_disposition",
        "suspect_lots_count",
        "product_recall_required",
        "tenant",
    )
    list_filter = ("risk_level", "status", "product_disposition", "product_recall_required", "tenant")
    search_fields = ("number", "title", "gage__gage_id", "products_affected")
    list_select_related = ("tenant", "gage", "calibration_record", "investigator", "quality_approver")


@admin.register(MeasurementSystemAnalysis)
class MeasurementSystemAnalysisAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "study_title",
        "gage",
        "study_type",
        "analysis_method",
        "percent_gage_rr_study_variation",
        "percent_tolerance_pt_ratio",
        "number_of_distinct_categories_ndc",
        "study_result",
        "status",
        "tenant",
    )
    list_filter = ("study_type", "analysis_method", "study_result", "status", "tenant")
    search_fields = ("number", "study_title", "gage__gage_id", "characteristic_name")
    list_select_related = ("tenant", "gage", "study_lead", "approved_by")


@admin.register(FinalInspectionLot)
class FinalInspectionLotAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "title",
        "inspection_stage",
        "status",
        "usage_decision",
        "item_code",
        "lot_number",
        "lot_quantity",
        "sample_size_inspected",
        "units_passed",
        "units_rejected",
        "is_on_hold",
        "tenant",
    )
    list_filter = ("inspection_stage", "status", "usage_decision", "is_on_hold", "tenant")
    search_fields = ("number", "title", "item_code", "item_name", "lot_number", "sales_order_number")
    list_select_related = ("tenant", "customer", "sales_order", "work_order", "inspector", "decision_by")


@admin.register(CertificateOfConformance)
class CertificateOfConformanceAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "title",
        "certificate_type",
        "status",
        "customer",
        "item_code",
        "lot_number",
        "certified_quantity",
        "signed_date",
        "tenant",
    )
    list_filter = ("certificate_type", "status", "tenant")
    search_fields = ("number", "title", "customer__name", "item_code", "lot_number", "customer_po_number")
    list_select_related = ("tenant", "customer", "sales_order", "shipment", "authorized_signatory")


@admin.register(PackagingLabelVerification)
class PackagingLabelVerificationAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "title",
        "status",
        "disposition",
        "barcode_symbology",
        "iso_iec_print_grade",
        "carton_count_inspected",
        "label_content_accurate",
        "carton_integrity_intact",
        "tenant",
    )
    list_filter = ("status", "disposition", "barcode_symbology", "iso_iec_print_grade", "tenant")
    search_fields = ("number", "title", "item_code", "lot_number", "label_part_number", "scanned_barcode_data")
    list_select_related = ("tenant", "artwork_master", "inspection_lot", "shipment", "verifier")


@admin.register(QualityReleaseAuthorization)
class QualityReleaseAuthorizationAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "title",
        "status",
        "release_disposition",
        "customer",
        "shipment_number",
        "quantity_authorized",
        "is_on_hold",
        "release_date",
        "tenant",
    )
    list_filter = ("status", "release_disposition", "is_on_hold", "final_inspection_passed", "tenant")
    search_fields = ("number", "title", "customer__name", "shipment_number", "lot_number", "carrier_name")
    list_select_related = ("tenant", "customer", "shipment", "sales_order", "releasing_officer")


@admin.register(AuditProgram)
class AuditProgramAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "title",
        "program_year",
        "program_type",
        "risk_basis",
        "status",
        "program_manager",
        "start_date",
        "end_date",
        "tenant",
    )
    list_filter = ("program_year", "program_type", "risk_basis", "status", "tenant")
    search_fields = ("number", "title", "scope_description", "program_manager__username")
    list_select_related = ("tenant", "program_manager", "approved_by")


@admin.register(QualityAudit)
class QualityAuditAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "title",
        "audit_type",
        "audit_method",
        "standard_framework",
        "status",
        "outcome",
        "lead_auditor",
        "planned_start_date",
        "tenant",
    )
    list_filter = ("audit_type", "audit_method", "standard_framework", "status", "outcome", "tenant")
    search_fields = ("number", "title", "scope_objectives", "product_scope", "lead_auditor__username")
    list_select_related = ("tenant", "program", "target_org_unit", "external_entity", "lead_auditor")


@admin.register(AuditFinding)
class AuditFindingAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "title",
        "severity",
        "standard_clause",
        "status",
        "assignee",
        "response_due_date",
        "audit",
        "tenant",
    )
    list_filter = ("severity", "status", "tenant")
    search_fields = ("number", "title", "standard_clause", "requirement_statement", "condition_evidence")
    list_select_related = ("tenant", "audit", "audited_org_unit", "assignee", "linked_capa")


@admin.register(RegulatoryInspectionHost)
class RegulatoryInspectionHostAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "inspection_title",
        "agency_or_body",
        "agency_name",
        "lead_inspector_name",
        "status",
        "formal_outcome",
        "form_483_issued",
        "scheduled_start_date",
        "tenant",
    )
    list_filter = ("agency_or_body", "inspection_purpose", "status", "formal_outcome", "form_483_issued", "tenant")
    search_fields = ("number", "inspection_title", "agency_name", "lead_inspector_name", "war_room_location")
    list_select_related = ("tenant", "audit", "front_room_lead", "back_room_lead", "scribe_user")


@admin.register(CompetencyMatrix)
class CompetencyMatrixAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "title",
        "role_title",
        "qualification_tier",
        "department",
        "criticality",
        "revision",
        "status",
        "minimum_passing_score",
        "validity_period_months",
        "tenant",
    )
    list_filter = ("qualification_tier", "criticality", "status", "tenant")
    search_fields = ("number", "title", "role_title", "description")
    list_select_related = ("tenant", "department", "approved_by")


@admin.register(QualityTrainingCourse)
class QualityTrainingCourseAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "title",
        "course_code",
        "category",
        "delivery_method",
        "assessment_method",
        "duration_hours",
        "passing_score",
        "status",
        "retrain_on_revision",
        "tenant",
    )
    list_filter = ("category", "delivery_method", "assessment_method", "status", "retrain_on_revision", "tenant")
    search_fields = ("number", "title", "course_code", "syllabus_summary")
    list_select_related = ("tenant", "competency_matrix", "controlled_document", "external_provider", "instructor")


@admin.register(TrainingEnrollment)
class TrainingEnrollmentAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "course",
        "trainee",
        "assignment_reason",
        "assigned_date",
        "due_date",
        "status",
        "is_passed",
        "score",
        "tenant",
    )
    list_filter = ("assignment_reason", "status", "is_passed", "tenant")
    search_fields = ("number", "course__title", "trainee__username", "trainee__first_name", "trainee__last_name")
    list_select_related = ("tenant", "course", "trainee", "document_change_order", "capa_action", "practical_verified_by")


@admin.register(CompetencyCertification)
class CompetencyCertificationAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "qualification_title",
        "trainee",
        "qualification_level",
        "course",
        "issue_date",
        "valid_until",
        "status",
        "certified_by",
        "tenant",
    )
    list_filter = ("qualification_level", "status", "tenant")
    search_fields = ("number", "qualification_title", "trainee__username", "certificate_hash")
    list_select_related = ("tenant", "trainee", "course", "competency_matrix", "certified_by", "enrollment")


@admin.register(CustomerComplaint)
class CustomerComplaintAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "title",
        "customer",
        "item_code",
        "lot_number",
        "severity",
        "status",
        "validity",
        "reportability",
        "date_received",
        "tenant",
    )
    list_filter = ("status", "severity", "validity", "reportability", "intake_channel", "tenant")
    search_fields = ("number", "title", "item_code", "item_name", "lot_number", "serial_number", "complainant_name", "customer__name")
    list_select_related = ("tenant", "customer", "sales_order", "assigned_to")


@admin.register(ComplaintInvestigation)
class ComplaintInvestigationAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "complaint",
        "lead_investigator",
        "analytical_method",
        "root_cause_category",
        "status",
        "dhr_reviewed",
        "capa_required",
        "tenant",
    )
    list_filter = ("status", "analytical_method", "root_cause_category", "capa_required", "tenant")
    search_fields = ("number", "complaint__number", "dhr_lot_number", "root_cause_narrative", "investigation_conclusion")
    list_select_related = ("tenant", "complaint", "lead_investigator", "qa_approved_by", "capa", "ncr", "risk_assessment")


@admin.register(RegulatoryReport)
class RegulatoryReportAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "complaint",
        "agency",
        "report_type",
        "adverse_event_class",
        "timeline_category",
        "statutory_due_date",
        "submission_status",
        "tenant",
    )
    list_filter = ("agency", "report_type", "adverse_event_class", "timeline_category", "submission_status", "tenant")
    search_fields = ("number", "complaint__number", "agency_report_identifier", "agency_acknowledgement_number", "event_summary")
    list_select_related = ("tenant", "complaint", "prepared_by", "reviewed_by")


@admin.register(FieldAction)
class FieldActionAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "title",
        "action_type",
        "recall_class",
        "coordinator",
        "affected_product_code",
        "status",
        "initiation_date",
        "tenant",
    )
    list_filter = ("action_type", "recall_class", "status", "tenant")
    search_fields = ("number", "title", "affected_product_code", "affected_product_name", "affected_lot_numbers", "regulatory_recall_number")
    list_select_related = ("tenant", "initiating_complaint", "coordinator", "fsn_document")


@admin.register(QualityObjective)
class QualityObjectiveAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "title",
        "category",
        "period_year",
        "cadence",
        "target_value",
        "current_value",
        "metric_unit",
        "status",
        "rag_status",
        "owner",
        "org_unit",
        "tenant",
    )
    list_filter = ("category", "period_year", "cadence", "status", "rag_status", "tenant")
    search_fields = ("number", "title", "description", "action_plan_summary")
    list_select_related = ("tenant", "owner", "org_unit")


@admin.register(ManagementReview)
class ManagementReviewAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "title",
        "cadence",
        "scheduled_date",
        "actual_meeting_date",
        "status",
        "qms_suitability_conclusion",
        "executive_sponsor",
        "lead_facilitator",
        "quorum_met",
        "tenant",
    )
    list_filter = ("cadence", "status", "qms_suitability_conclusion", "quorum_met", "tenant")
    search_fields = ("number", "title", "executive_summary", "minutes_discussion")
    list_select_related = ("tenant", "executive_sponsor", "lead_facilitator", "org_unit", "approved_by")


@admin.register(ManagementReviewInput)
class ManagementReviewInputAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "management_review",
        "agenda_order",
        "title",
        "category",
        "presenter",
        "status",
        "tenant",
    )
    list_filter = ("category", "status", "tenant")
    search_fields = ("number", "title", "summary_findings")
    list_select_related = ("tenant", "management_review", "presenter", "linked_audit", "linked_capa", "linked_complaint", "linked_ncr")


@admin.register(ManagementReviewAction)
class ManagementReviewActionAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "management_review",
        "title",
        "action_type",
        "priority",
        "assignee",
        "due_date",
        "status",
        "verified_by",
        "tenant",
    )
    list_filter = ("action_type", "priority", "status", "tenant")
    search_fields = ("number", "title", "description", "resolution_summary")
    list_select_related = ("tenant", "management_review", "assignee", "verified_by", "spawned_capa", "spawned_change_order")


@admin.register(ValidationProtocol)
class ValidationProtocolAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "title",
        "protocol_stage",
        "target_type",
        "status",
        "revalidation_trigger",
        "equipment_tag",
        "target_completion_date",
        "lead_author",
        "qa_reviewer",
        "tenant",
    )
    list_filter = ("protocol_stage", "target_type", "status", "revalidation_trigger", "tenant")
    search_fields = ("number", "title", "equipment_tag", "process_name", "item_code")
    list_select_related = ("tenant", "lead_author", "qa_reviewer", "final_approver", "department")


@admin.register(ProcessCapabilityStudy)
class ProcessCapabilityStudyAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "title",
        "parameter_name",
        "parameter_category",
        "mean_value",
        "cpk_index",
        "ppk_index",
        "capability_determination",
        "status",
        "investigator",
        "tenant",
    )
    list_filter = ("capability_determination", "parameter_category", "status", "tenant")
    search_fields = ("number", "title", "parameter_name", "equipment_tag", "process_name")
    list_select_related = ("tenant", "investigator", "approved_by", "validation_protocol")


@admin.register(ComputerSystemValidation)
class ComputerSystemValidationAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "system_name",
        "version_release",
        "vendor_name",
        "gamp_category",
        "gxp_impact",
        "status",
        "is_part_11_compliant",
        "next_review_due",
        "system_owner",
        "tenant",
    )
    list_filter = ("gamp_category", "gxp_impact", "status", "is_part_11_compliant", "tenant")
    search_fields = ("number", "system_name", "vendor_name", "version_release")
    list_select_related = ("tenant", "system_owner", "quality_lead", "validation_protocol")


@admin.register(CleaningValidation)
class CleaningValidationAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "title",
        "equipment_train_tag",
        "target_residue",
        "calculated_maco_mg",
        "calculated_swab_limit_ug",
        "cleaning_status",
        "is_visually_clean",
        "next_revalidation_date",
        "analytical_lead",
        "tenant",
    )
    list_filter = ("cleaning_status", "calculation_basis", "analytical_method", "is_visually_clean", "tenant")
    search_fields = ("number", "title", "equipment_train_tag", "target_residue", "cleaning_agent_used")
    list_select_related = ("tenant", "analytical_lead", "qa_approver", "validation_protocol", "cleaning_sop")


@admin.register(HazardousMaterial)
class HazardousMaterialAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "material_name",
        "trade_name",
        "cas_number",
        "physical_state",
        "storage_location_code",
        "maximum_storage_quantity",
        "quantity_uom",
        "status",
        "tenant",
    )
    list_filter = ("physical_state", "status", "is_flammable", "is_corrosive", "is_toxic", "tenant")
    search_fields = ("number", "material_name", "trade_name", "cas_number", "storage_location_code")
    list_select_related = ("tenant", "org_unit", "supplier", "managed_by")


@admin.register(SafetyIncident)
class SafetyIncidentAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "title",
        "incident_type",
        "severity",
        "incident_date",
        "is_osha_recordable",
        "lost_workdays_count",
        "status",
        "tenant",
    )
    list_filter = ("incident_type", "severity", "is_osha_recordable", "status", "tenant")
    search_fields = ("number", "title", "location_details")
    list_select_related = ("tenant", "org_unit", "reported_by", "affected_person", "lead_investigator")


@admin.register(EnvironmentalMonitoringLog)
class EnvironmentalMonitoringLogAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "sampling_point_id",
        "cleanroom_class",
        "monitoring_category",
        "sampling_timestamp",
        "measured_value",
        "unit_of_measure",
        "upper_action_limit",
        "evaluation_status",
        "tenant",
    )
    list_filter = ("cleanroom_class", "monitoring_category", "evaluation_status", "operational_state", "tenant")
    search_fields = ("number", "sampling_point_id", "parameter_name")
    list_select_related = ("tenant", "org_unit", "sampled_by", "verified_by")


@admin.register(WasteDisposalManifest)
class WasteDisposalManifestAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "manifest_type",
        "physical_state",
        "quantity_value",
        "quantity_uom",
        "accumulation_start_date",
        "shipment_date",
        "status",
        "tenant",
    )
    list_filter = ("manifest_type", "physical_state", "status", "tenant")
    search_fields = ("number", "generator_epa_id", "transporter_epa_id", "tsdf_epa_id", "epa_waste_codes")
    list_select_related = ("tenant", "associated_hazardous_material", "generator_org_unit", "transporter", "tsdf_facility")












