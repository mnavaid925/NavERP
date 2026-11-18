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
        "inspection_stage",
        "item_code",
        "item_name",
        "lot_number",
        "production_order_number",
        "sample_size",
        "defect_count",
        "result",
        "status",
        "tenant",
    )
    list_filter = ("inspection_stage", "result", "status", "sampling_type", "tenant")
    search_fields = ("number", "title", "item_code", "item_name", "lot_number", "production_order_number")
    list_select_related = ("tenant", "inspector", "verified_by")


@admin.register(FirstArticleInspection)
class FirstArticleInspectionAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "fai_reason",
        "part_number",
        "part_name",
        "drawing_number",
        "drawing_revision",
        "production_order_number",
        "overall_result",
        "status",
        "tenant",
    )
    list_filter = ("fai_reason", "overall_result", "status", "tenant")
    search_fields = ("number", "part_number", "part_name", "drawing_number", "production_order_number")
    list_select_related = ("tenant", "inspector", "quality_engineer", "customer_representative")


@admin.register(ProcessParameterLog)
class ProcessParameterLogAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "operation_name",
        "parameter_name",
        "machine_code",
        "nominal_value",
        "actual_value",
        "is_out_of_spec",
        "spc_alert",
        "tenant",
    )
    list_filter = ("is_out_of_spec", "spc_alert", "parameter_type", "tenant")
    search_fields = ("number", "operation_name", "parameter_name", "machine_code", "production_order_number")
    list_select_related = ("tenant", "operator", "verified_by")


@admin.register(LayeredProcessAudit)
class LayeredProcessAuditAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "title",
        "audit_level",
        "frequency",
        "area_name",
        "auditor_name",
        "conformance_rate",
        "result",
        "status",
        "tenant",
    )
    list_filter = ("audit_level", "frequency", "result", "status", "tenant")
    search_fields = ("number", "title", "area_name", "auditor_name")
    list_select_related = ("tenant", "auditor", "supervisor_signoff")





