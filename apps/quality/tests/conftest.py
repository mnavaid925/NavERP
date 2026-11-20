"""Shared fixtures for apps/quality test suite (Module 12: Quality Management System)."""
from datetime import timedelta
from decimal import Decimal
import pytest
from django.utils import timezone

from apps.core.models import OrgUnit, Party, PartyRole
from apps.hrm.models import EmployeeProfile
from apps.quality.models import (
    ControlledDocument,
    DocumentChangeOrder,
    ElectronicSignatureRecord,
    DocumentAcknowledgment,
    DesignProject,
    DesignInput,
    DesignReview,
    DesignVerification,
    RiskManagementPlan,
    RiskAssessment,
    RiskControlMeasure,
    RiskReviewRecord,
    CapaInvestigation,
    RootCauseAnalysis,
    CapaAction,
    CapaEffectivenessReview,
    NonConformanceReport,
    QuarantineContainment,
    MrbDisposition,
    ProcessDeviation,
    SupplierQualificationAudit,
    SupplierQualityScorecard,
    SupplierCorrectiveAction,
    SupplierChangeNotification,
    IncomingInspectionPlan,
    IncomingInspectionLot,
    CertificateOfAnalysis,
    QualityReturnAuthorization,
    InProcessInspection,
    FirstArticleInspection,
    ProcessParameterLog,
    LayeredProcessAudit,
    FinalInspectionLot,
    CertificateOfConformance,
    PackagingLabelVerification,
    QualityReleaseAuthorization,
    CalibrationGage,
    CalibrationRecord,
    OutOfToleranceInvestigation,
    MeasurementSystemAnalysis,
    AuditProgram,
    QualityAudit,
    AuditFinding,
    RegulatoryInspectionHost,
)


@pytest.fixture
def quality_department(db, tenant_a):
    return OrgUnit.objects.create(
        tenant=tenant_a,
        name="Quality Assurance",
        kind="department",
    )


@pytest.fixture
def quality_department_b(db, tenant_b):
    return OrgUnit.objects.create(
        tenant=tenant_b,
        name="Quality Assurance Globex",
        kind="department",
    )


@pytest.fixture
def quality_employee(db, tenant_a, admin_user, quality_department):
    party = Party.objects.create(
        tenant=tenant_a,
        name="Admin QA Manager",
        party_type="individual",
    )
    PartyRole.objects.create(
        tenant=tenant_a,
        party=party,
        role_type="employee",
    )
    return EmployeeProfile.objects.create(
        tenant=tenant_a,
        party=party,
        user=admin_user,
        department=quality_department,
        number="EMP-QA-001",
        job_title="QA Director",
    )


@pytest.fixture
def quality_employee_b(db, tenant_b, admin_b, quality_department_b):
    party = Party.objects.create(
        tenant=tenant_b,
        name="Globex QA Officer",
        party_type="individual",
    )
    PartyRole.objects.create(
        tenant=tenant_b,
        party=party,
        role_type="employee",
    )
    return EmployeeProfile.objects.create(
        tenant=tenant_b,
        party=party,
        user=admin_b,
        department=quality_department_b,
        number="EMP-QA-999",
        job_title="Globex QA Lead",
    )


@pytest.fixture
def quality_doc_draft(db, tenant_a, admin_user, quality_department):
    return ControlledDocument.objects.create(
        tenant=tenant_a,
        title="Draft Standard Operating Procedure",
        document_type="sop",
        department=quality_department,
        owner=admin_user,
        revision="1.0",
        lifecycle_state="draft",
        classification="internal",
        description="Initial draft SOP for document control testing.",
    )


@pytest.fixture
def quality_doc_effective(db, tenant_a, admin_user, quality_department):
    now = timezone.now().date()
    return ControlledDocument.objects.create(
        tenant=tenant_a,
        title="Effective Good Manufacturing Practice Procedure",
        document_type="sop",
        department=quality_department,
        owner=admin_user,
        revision="2.0",
        lifecycle_state="effective",
        classification="confidential",
        description="Effective GxP compliance document.",
        effective_date=now,
        next_review_date=now + timedelta(days=365),
    )


@pytest.fixture
def doc_a(quality_doc_effective):
    return quality_doc_effective


@pytest.fixture
def quality_doc_b(db, tenant_b, admin_b, quality_department_b):
    return ControlledDocument.objects.create(
        tenant=tenant_b,
        title="Globex Confidential Batch Record",
        document_type="work_instruction",
        department=quality_department_b,
        owner=admin_b,
        revision="1.0",
        lifecycle_state="effective",
        classification="restricted",
        description="Globex tenant isolated document.",
    )


@pytest.fixture
def doc_b(quality_doc_b):
    return quality_doc_b


@pytest.fixture
def quality_dco(db, tenant_a, admin_user, quality_doc_draft):
    return DocumentChangeOrder.objects.create(
        tenant=tenant_a,
        document=quality_doc_draft,
        title="DCO: Revise SOP for 2026 Audit Requirements",
        change_type="revision",
        priority="high",
        status="submitted",
        requested_by=admin_user,
        reason_for_change="Regulatory compliance alignment.",
        change_description="Updated section 4 and revised review intervals.",
    )


@pytest.fixture
def quality_dco_b(db, tenant_b, admin_b, quality_doc_b):
    return DocumentChangeOrder.objects.create(
        tenant=tenant_b,
        document=quality_doc_b,
        title="Globex DCO: Emergency Production Alteration",
        change_type="emergency",
        priority="critical",
        status="submitted",
        requested_by=admin_b,
        reason_for_change="Globex internal change order.",
        change_description="Globex confidential update.",
    )


@pytest.fixture
def quality_sig(db, tenant_a, admin_user, quality_doc_effective):
    sig = ElectronicSignatureRecord(
        tenant=tenant_a,
        document=quality_doc_effective,
        signer=admin_user,
        signer_name="Admin Acme",
        signer_title="QA Director",
        signature_meaning="quality_approval",
        document_revision=quality_doc_effective.revision,
        ip_address="127.0.0.1",
        comments="Approved for release per SOP-001.",
    )
    sig.verification_hash = sig.generate_hash()
    sig.save()
    return sig


@pytest.fixture
def quality_ack(db, tenant_a, admin_user, quality_employee, quality_doc_effective):
    return DocumentAcknowledgment.objects.create(
        tenant=tenant_a,
        document=quality_doc_effective,
        user=admin_user,
        employee=quality_employee,
        status="pending",
        due_date=timezone.now().date() + timedelta(days=14),
    )


@pytest.fixture
def quality_ack_b(db, tenant_b, admin_b, quality_employee_b, quality_doc_b):
    return DocumentAcknowledgment.objects.create(
        tenant=tenant_b,
        document=quality_doc_b,
        user=admin_b,
        employee=quality_employee_b,
        status="pending",
        due_date=timezone.now().date() + timedelta(days=7),
    )


# --- Sub-module 12.2: Design Controls & Development Fixtures ---

@pytest.fixture
def design_project_a(db, tenant_a, admin_user, quality_department):
    return DesignProject.objects.create(
        tenant=tenant_a,
        title="NextGen Smart Infusion Pump",
        device_name="InfuseFlow Pro 3000",
        device_class="class_ii",
        regulatory_pathway="510k",
        intended_use="Controlled volumetric administration of IV fluids.",
        current_phase="planning",
        status="active",
        project_lead=admin_user,
        quality_lead=admin_user,
        department=quality_department,
        dhf_locked=False,
    )


@pytest.fixture
def design_project_locked(db, tenant_a, admin_user, quality_department):
    return DesignProject.objects.create(
        tenant=tenant_a,
        title="Disposable Safety Syringe",
        device_name="AccuInject 5mL",
        device_class="class_ii",
        regulatory_pathway="510k",
        intended_use="Subcutaneous injection.",
        current_phase="commercial_closure",
        status="completed",
        project_lead=admin_user,
        quality_lead=admin_user,
        department=quality_department,
        dhf_locked=True,
    )


@pytest.fixture
def design_project_b(db, tenant_b, admin_b, quality_department_b):
    return DesignProject.objects.create(
        tenant=tenant_b,
        title="Globex Surgical Laser System",
        device_name="Globex Beam 500",
        device_class="class_iii",
        regulatory_pathway="pma",
        intended_use="Laser surgical tissue ablation.",
        current_phase="planning",
        status="active",
        project_lead=admin_b,
        quality_lead=admin_b,
        department=quality_department_b,
        dhf_locked=False,
    )


@pytest.fixture
def design_input_need(db, tenant_a, admin_user, design_project_a):
    return DesignInput.objects.create(
        tenant=tenant_a,
        project=design_project_a,
        identifier="UN-001",
        title="Battery Backup Requirement",
        input_type="user_need",
        priority="high",
        status="approved",
        owner=admin_user,
        acceptance_criteria="Continuous infusion for minimum 8 hours during patient transit.",
    )


@pytest.fixture
def design_input_spec(db, tenant_a, admin_user, design_project_a, design_input_need):
    return DesignInput.objects.create(
        tenant=tenant_a,
        project=design_project_a,
        identifier="DI-001",
        title="Lithium-Ion Battery Capacity",
        input_type="functional",
        priority="high",
        status="approved",
        owner=admin_user,
        user_need_parent=design_input_need,
        acceptance_criteria="Battery rating must exceed 4500mAh with charge protection circuit.",
    )


@pytest.fixture
def design_input_b(db, tenant_b, admin_b, design_project_b):
    return DesignInput.objects.create(
        tenant=tenant_b,
        project=design_project_b,
        identifier="UN-GLX-001",
        title="Globex Optical Sensor Spec",
        input_type="user_need",
        priority="critical",
        status="approved",
        owner=admin_b,
        acceptance_criteria="Laser beam alignment deviation must be under 0.05mm.",
    )


@pytest.fixture
def design_review_a(db, tenant_a, admin_user, design_project_a):
    return DesignReview.objects.create(
        tenant=tenant_a,
        project=design_project_a,
        title="Phase 1 Design Planning Gate Review",
        review_stage="planning_gate",
        review_date=timezone.now().date(),
        status="scheduled",
        lead_reviewer=admin_user,
    )


@pytest.fixture
def design_review_b(db, tenant_b, admin_b, design_project_b):
    return DesignReview.objects.create(
        tenant=tenant_b,
        project=design_project_b,
        title="Globex Phase 1 Review",
        review_stage="planning_gate",
        review_date=timezone.now().date(),
        status="scheduled",
        lead_reviewer=admin_b,
    )


@pytest.fixture
def design_verification_a(db, tenant_a, admin_user, design_project_a, design_input_spec):
    return DesignVerification.objects.create(
        tenant=tenant_a,
        project=design_project_a,
        primary_input=design_input_spec,
        title="Battery Run-Time Verification Protocol",
        activity_type="design_verification",
        status="draft",
        test_method="lab_testing",
        sample_size=5,
        pass_fail_result="pending",
        acceptance_criteria="All 5 units run for >= 8 hours under full occlusion pressure.",
        results_summary="Protocol prepared for bench testing.",
    )


@pytest.fixture
def design_verification_b(db, tenant_b, admin_b, design_project_b, design_input_b):
    return DesignVerification.objects.create(
        tenant=tenant_b,
        project=design_project_b,
        primary_input=design_input_b,
        title="Globex Beam Calibration Test",
        activity_type="design_verification",
        status="draft",
        test_method="lab_testing",
        sample_size=3,
        pass_fail_result="pending",
        acceptance_criteria="Optical sensor detects spot alignment within tolerance.",
        results_summary="Globex protocol initialized.",
    )


@pytest.fixture
def risk_management_plan_a(db, tenant_a, admin_user, design_project_a):
    return RiskManagementPlan.objects.create(
        tenant=tenant_a,
        title="InfuseFlow Pro 3000 Risk Management Plan",
        device_classification="class_ii_a",
        design_project=design_project_a,
        lead_risk_manager=admin_user,
        status="active",
        matrix_dimension="5x5",
        scope_description="ISO 14971 compliance plan across design, verification, and commercial release.",
        risk_acceptability_policy="Broadly acceptable when RPN < 4; ALARP when 4 <= RPN < 15 with clinical benefit justification.",
    )


@pytest.fixture
def risk_management_plan_b(db, tenant_b, admin_b, design_project_b):
    return RiskManagementPlan.objects.create(
        tenant=tenant_b,
        title="Globex Laser Scalpel Risk Management Plan",
        device_classification="class_iii",
        design_project=design_project_b,
        lead_risk_manager=admin_b,
        status="active",
        matrix_dimension="5x5",
        scope_description="Globex laser device risk management lifecycle.",
        risk_acceptability_policy="Globex acceptable risk criteria per ISO 14971.",
    )


@pytest.fixture
def risk_assessment_a(db, tenant_a, admin_user, risk_management_plan_a):
    return RiskAssessment.objects.create(
        tenant=tenant_a,
        plan=risk_management_plan_a,
        hazard_category="energy_electrical",
        hazard_description="Chassis isolation breakdown during power surge",
        foreseeable_sequence_of_events="Line voltage spike causes capacitor breakdown bridging current to metal chassis.",
        hazardous_situation="Operator or patient touches energized enclosure.",
        potential_harm="Ventricular fibrillation or thermal shock injury.",
        analysis_type="dfmea",
        initial_severity=4,
        initial_probability=3,
        lifecycle_status="open",
    )


@pytest.fixture
def risk_assessment_b(db, tenant_b, admin_b, risk_management_plan_b):
    return RiskAssessment.objects.create(
        tenant=tenant_b,
        plan=risk_management_plan_b,
        hazard_category="energy_thermal",
        hazard_description="Optical waveguide overheating during extended laser emission",
        foreseeable_sequence_of_events="Cooling circuit blockage causes optic assembly thermal accumulation.",
        hazardous_situation="Excess heat transmitted to surgeon handle.",
        potential_harm="Second-degree burn on operator hand.",
        analysis_type="dfmea",
        initial_severity=3,
        initial_probability=3,
        lifecycle_status="open",
    )


@pytest.fixture
def risk_control_measure_a(db, tenant_a, admin_user, risk_assessment_a, design_input_spec, design_verification_a):
    return RiskControlMeasure.objects.create(
        tenant=tenant_a,
        risk_assessment=risk_assessment_a,
        control_hierarchy="inherent_safety",
        title="Galvanic 4kV Dielectric Isolation Transformer",
        description="Integrate double-reinforced galvanic barrier meeting IEC 60601-1 3rd edition.",
        assigned_to=admin_user,
        design_input=design_input_spec,
        design_verification=design_verification_a,
        implementation_verified=False,
        effectiveness_verified=False,
        status="planned",
    )


@pytest.fixture
def risk_control_measure_b(db, tenant_b, admin_b, risk_assessment_b, design_input_b, design_verification_b):
    return RiskControlMeasure.objects.create(
        tenant=tenant_b,
        risk_assessment=risk_assessment_b,
        control_hierarchy="inherent_safety",
        title="Thermal Cutoff Sensor on Laser Diode Housing",
        description="Hardware bimetallic thermostat cuts laser power if waveguide exceeds 55C.",
        assigned_to=admin_b,
        design_input=design_input_b,
        design_verification=design_verification_b,
        implementation_verified=False,
        effectiveness_verified=False,
        status="planned",
    )


@pytest.fixture
def risk_review_record_a(db, tenant_a, admin_user, risk_management_plan_a):
    return RiskReviewRecord.objects.create(
        tenant=tenant_a,
        plan=risk_management_plan_a,
        review_type="initial_rmr",
        review_title="Interim Design Verification Risk Review",
        findings_summary="Review of active risks, verification protocol outcomes, and residual risk acceptance.",
        review_date=timezone.now().date(),
        lead_reviewer=admin_user,
        status="draft",
    )


@pytest.fixture
def risk_review_record_b(db, tenant_b, admin_b, risk_management_plan_b):
    return RiskReviewRecord.objects.create(
        tenant=tenant_b,
        plan=risk_management_plan_b,
        review_type="initial_rmr",
        review_title="Globex Waveguide Safety Review",
        findings_summary="Evaluation of laser thermal containment mitigations.",
        review_date=timezone.now().date(),
        lead_reviewer=admin_b,
        status="draft",
    )


# ---------------------------------------------------------------------------
# Sub-module 12.4: CAPA (Corrective & Preventive Action) Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def capa_investigation_a(db, tenant_a, admin_user, quality_department):
    return CapaInvestigation.objects.create(
        tenant=tenant_a,
        title="Optical Fiber Connector Cracking Under Mechanical Stress",
        action_type="corrective",
        source_type="complaint",
        risk_priority="high",
        status="under_investigation",
        department=quality_department,
        lead_investigator=admin_user,
        quality_owner=admin_user,
        issue_summary="Connector ferrules fracture when subjected to 15N bending load during clinical use.",
        containment_actions="Quarantine lot OF-2026-088; notify distribution centers.",
        target_closure_date=timezone.now().date() + timedelta(days=30),
    )


@pytest.fixture
def capa_investigation_b(db, tenant_b, admin_b, quality_department_b):
    return CapaInvestigation.objects.create(
        tenant=tenant_b,
        title="Globex Power Converter Thermal Excursion",
        action_type="corrective",
        source_type="internal_audit",
        risk_priority="critical",
        status="under_investigation",
        department=quality_department_b,
        lead_investigator=admin_b,
        quality_owner=admin_b,
        issue_summary="Heatsink paste drying causes overheating in laser power supply unit.",
        containment_actions="Halt production line 3; verify incoming thermal compound.",
        target_closure_date=timezone.now().date() + timedelta(days=20),
    )


@pytest.fixture
def root_cause_analysis_a(db, tenant_a, admin_user, capa_investigation_a):
    return RootCauseAnalysis.objects.create(
        tenant=tenant_a,
        capa=capa_investigation_a,
        rca_method="five_whys",
        problem_statement="Connector ferrules crack under 15N load instead of rated 30N specification.",
        why_1="Ferrule molded wall thickness was below 0.8mm nominal.",
        why_2="Injection molding tooling core pin experienced wear after 50,000 cycles.",
        why_3="Preventive maintenance schedule did not include core pin dimensional CMM inspection.",
        why_4="Tool maintenance SOP lacked critical dimension inspection checklist for optical cores.",
        why_5="No periodic design verification for tooling wear-out limits was established.",
        root_cause_summary="Lack of tool wear CMM measurement verification in preventive maintenance procedure.",
        root_cause_category="machine",
        lead_investigator=admin_user,
        status="in_progress",
    )


@pytest.fixture
def root_cause_analysis_b(db, tenant_b, admin_b, capa_investigation_b):
    return RootCauseAnalysis.objects.create(
        tenant=tenant_b,
        capa=capa_investigation_b,
        rca_method="five_whys",
        problem_statement="Thermal paste dries out under operating temperature.",
        why_1="Thermal resistance increased above 0.5 C/W.",
        why_2="Paste viscosity decreased due to solvent evaporation.",
        why_3="Supplier changed formulation without notification.",
        why_4="Incoming inspection did not test volatile organic content.",
        why_5="Supplier quality agreement did not list thermal compound as critical material.",
        root_cause_summary="Supplier material formulation change without prior supplier quality agreement gate.",
        root_cause_category="material",
        lead_investigator=admin_b,
        status="in_progress",
    )


@pytest.fixture
def capa_action_a(db, tenant_a, admin_user, quality_department, capa_investigation_a, root_cause_analysis_a):
    return CapaAction.objects.create(
        tenant=tenant_a,
        capa=capa_investigation_a,
        root_cause=root_cause_analysis_a,
        action_type="corrective",
        title="Update Tooling PM SOP to require CMM Core Pin Metrology",
        description="Revise SOP-MNT-042 to mandate CMM measurement of core pins every 10,000 cycles.",
        assigned_to=admin_user,
        department=quality_department,
        due_date=timezone.now().date() + timedelta(days=14),
        status="pending",
    )


@pytest.fixture
def capa_action_b(db, tenant_b, admin_b, quality_department_b, capa_investigation_b, root_cause_analysis_b):
    return CapaAction.objects.create(
        tenant=tenant_b,
        capa=capa_investigation_b,
        root_cause=root_cause_analysis_b,
        action_type="corrective",
        title="Institute Incoming VOC Testing for Thermal Paste",
        description="Establish gas chromatography inspection for incoming compound barrels.",
        assigned_to=admin_b,
        department=quality_department_b,
        due_date=timezone.now().date() + timedelta(days=10),
        status="pending",
    )


@pytest.fixture
def capa_effectiveness_review_a(db, tenant_a, admin_user, capa_investigation_a):
    return CapaEffectivenessReview.objects.create(
        tenant=tenant_a,
        capa=capa_investigation_a,
        review_criteria="Zero ferrule cracking across 5 consecutive lots (Cpk >= 1.33).",
        verification_method="statistical_sampling",
        planned_review_date=timezone.now().date() + timedelta(days=30),
        evaluator=admin_user,
        status="scheduled",
    )


@pytest.fixture
def capa_effectiveness_review_b(db, tenant_b, admin_b, capa_investigation_b):
    return CapaEffectivenessReview.objects.create(
        tenant=tenant_b,
        capa=capa_investigation_b,
        review_criteria="Thermal resistance remains below 0.3 C/W over 1,000 burn-in hours.",
        verification_method="trend_analysis",
        planned_review_date=timezone.now().date() + timedelta(days=60),
        evaluator=admin_b,
        status="scheduled",
    )


# -----------------------------------------------------------------------------
# Sub-module 12.5 Fixtures (Non-Conformance & Deviation Management)
# -----------------------------------------------------------------------------

@pytest.fixture
def supplier_party_a(db, tenant_a):
    party = Party.objects.create(
        tenant=tenant_a,
        name="Precision Medical Tech Co",
        kind="organization",
    )
    PartyRole.objects.create(
        tenant=tenant_a,
        party=party,
        role="vendor",
    )
    return party


@pytest.fixture
def supplier_party_b(db, tenant_b):
    party = Party.objects.create(
        tenant=tenant_b,
        name="Apex Industrial Parts Globex",
        kind="organization",
    )
    PartyRole.objects.create(
        tenant=tenant_b,
        party=party,
        role="vendor",
    )
    return party


@pytest.fixture
def ncr_a(db, tenant_a, admin_user, quality_department, supplier_party_a):
    return NonConformanceReport.objects.create(
        tenant=tenant_a,
        title="Excess Micro-Burrs on Surgical Cannula Tips",
        description="Micro-burrs exceeding 0.05mm tolerance discovered on cannula tips during optical comparator inspection.",
        source_type="incoming_inspection",
        category="material",
        severity="major",
        status="containment_active",
        department=quality_department,
        initiator=admin_user,
        owner=admin_user,
        affected_item_code="CAN-TIP-004",
        lot_serial_numbers="LOT-2026-X819",
        quantity_inspected=1000,
        quantity_nonconforming=75,
        immediate_containment_required=True,
        supplier_party=supplier_party_a,
    )


@pytest.fixture
def ncr_b(db, tenant_b, admin_b, quality_department_b, supplier_party_b):
    return NonConformanceReport.objects.create(
        tenant=tenant_b,
        title="Globex Defective O-Ring Seal Batch",
        description="Cracked seal surfaces under pressure.",
        source_type="incoming_inspection",
        category="material",
        severity="critical",
        status="containment_active",
        department=quality_department_b,
        initiator=admin_b,
        owner=admin_b,
        affected_item_code="GLX-SEAL-99",
        lot_serial_numbers="GLX-LOT-001",
        quantity_inspected=500,
        quantity_nonconforming=120,
        immediate_containment_required=True,
        supplier_party=supplier_party_b,
    )


@pytest.fixture
def quarantine_a(db, tenant_a, admin_user, ncr_a):
    return QuarantineContainment.objects.create(
        tenant=tenant_a,
        ncr=ncr_a,
        title="Quarantine Hold - Cannula Batch X819",
        hold_type="physical_quarantine",
        quarantine_location="Warehouse Bay 4B, Red Cage #2",
        quantity_on_hold=75,
        status="active",
        hold_applied_by=admin_user,
        release_criteria="MRB rework and 100% reinspection pass required.",
    )


@pytest.fixture
def quarantine_b(db, tenant_b, admin_b, ncr_b):
    return QuarantineContainment.objects.create(
        tenant=tenant_b,
        ncr=ncr_b,
        title="Quarantine Hold - Globex Seal Vault",
        hold_type="physical_quarantine",
        quarantine_location="Globex Vault G1",
        quantity_on_hold=120,
        status="active",
        hold_applied_by=admin_b,
        release_criteria="Globex isolation applied.",
    )


@pytest.fixture
def mrb_a(db, tenant_a, admin_user, ncr_a):
    return MrbDisposition.objects.create(
        tenant=tenant_a,
        ncr=ncr_a,
        title="MRB Disposition - Cannula Micro-Burr Rework",
        disposition_decision="rework",
        technical_justification="Secondary ultrasonic electropolishing run can deburr to specification without violating outer diameter tolerances.",
        mrb_chair=admin_user,
        rework_assignee=admin_user,
        rework_instructions="Run cannulas through ultrasonic bath for 4 minutes at 60C, followed by DI water rinse.",
        reinspection_required=True,
        reinspection_criteria="Microscope inspection at 40x magnification: 0 burrs visible.",
        scrap_cost=0,
        rework_labor_cost=450,
        vendor_chargeback_cost=450,
        status="under_review",
    )


@pytest.fixture
def mrb_b(db, tenant_b, admin_b, ncr_b):
    return MrbDisposition.objects.create(
        tenant=tenant_b,
        ncr=ncr_b,
        title="MRB Disposition - Globex Seal Scrap",
        disposition_decision="scrap",
        technical_justification="Cracked compound is unsafe for use; complete batch condemned.",
        mrb_chair=admin_b,
        scrap_cost=3200,
        rework_labor_cost=0,
        vendor_chargeback_cost=3200,
        status="under_review",
    )


@pytest.fixture
def process_deviation_a(db, tenant_a, admin_user, ncr_a):
    return ProcessDeviation.objects.create(
        tenant=tenant_a,
        ncr=ncr_a,
        title="Temporary Parameter Adjustment for Deburring Ultrasonic Bath",
        deviation_type="unplanned",
        category="process_parameter",
        status="draft",
        risk_impact_level="minor",
        quality_impact_assessment="Tested on 5 dummy cannulas. No core tube deformation observed. Cleanroom particulate counts normal.",
        requested_by=admin_user,
        customer_notification_required=False,
    )


@pytest.fixture
def process_deviation_b(db, tenant_b, admin_b, ncr_b):
    return ProcessDeviation.objects.create(
        tenant=tenant_b,
        ncr=ncr_b,
        title="Globex Deviation Compound Blend Test",
        deviation_type="unplanned",
        category="process_parameter",
        status="draft",
        risk_impact_level="moderate",
        quality_impact_assessment="Risk evaluated.",
        requested_by=admin_b,
        customer_notification_required=True,
    )


# -----------------------------------------------------------------------------
# Sub-module 12.6 Fixtures (Supplier & Vendor Quality Management)
# -----------------------------------------------------------------------------

@pytest.fixture
def audit_a(db, tenant_a, supplier_party_a, admin_user, doc_a):
    return SupplierQualificationAudit.objects.create(
        tenant=tenant_a,
        supplier=supplier_party_a,
        assessment_type="initial_qualification",
        criticality_tier="critical",
        audit_method="on_site",
        qualification_status="approved",
        audit_result="passed",
        score=94.50,
        dock_to_stock_eligible=True,
        requires_coa=True,
        lead_auditor=admin_user,
        quality_agreement=doc_a,
        scope_commodities="Surgical cannulas, medical catheter components",
        notes="Compliant facility. ISO 13485 cleanroom certified.",
    )


@pytest.fixture
def audit_b(db, tenant_b, supplier_party_b, admin_b):
    return SupplierQualificationAudit.objects.create(
        tenant=tenant_b,
        supplier=supplier_party_b,
        assessment_type="periodic_reaudit",
        criticality_tier="major",
        audit_method="desktop_survey",
        qualification_status="under_evaluation",
        audit_result="pending",
        score=78.00,
        dock_to_stock_eligible=False,
        lead_auditor=admin_b,
        scope_commodities="Industrial seals",
    )


@pytest.fixture
def scorecard_a(db, tenant_a, supplier_party_a, admin_user):
    return SupplierQualityScorecard.objects.create(
        tenant=tenant_a,
        supplier=supplier_party_a,
        cadence="quarterly",
        period_start=timezone.now().date() - timedelta(days=90),
        period_end=timezone.now().date(),
        status="published",
        lot_acceptance_rate_score=Decimal("96.00"),
        defect_ppm_score=Decimal("92.00"),
        scar_responsiveness_score=Decimal("90.00"),
        audit_compliance_score=Decimal("95.00"),
        documentation_coa_score=Decimal("98.00"),
        total_lots_received=120,
        lots_rejected=2,
        total_scars_issued=1,
        evaluated_by=admin_user,
        evaluation_notes="Solid Q3 quality performance.",
    )


@pytest.fixture
def scorecard_b(db, tenant_b, supplier_party_b, admin_b):
    return SupplierQualityScorecard.objects.create(
        tenant=tenant_b,
        supplier=supplier_party_b,
        cadence="monthly",
        period_start=timezone.now().date() - timedelta(days=30),
        period_end=timezone.now().date(),
        status="draft",
        lot_acceptance_rate_score=Decimal("75.00"),
        defect_ppm_score=Decimal("68.00"),
        scar_responsiveness_score=Decimal("80.00"),
        audit_compliance_score=Decimal("70.00"),
        documentation_coa_score=Decimal("85.00"),
        evaluated_by=admin_b,
    )


@pytest.fixture
def scar_a(db, tenant_a, supplier_party_a, admin_user, audit_a):
    return SupplierCorrectiveAction.objects.create(
        tenant=tenant_a,
        supplier=supplier_party_a,
        title="Excess Micro-Burrs on Delivery Lot CAN-TIP-004",
        defect_summary="Tip burrs exceeding 0.05mm limit discovered during optical comparator check.",
        severity="major",
        status="containment_acknowledged",
        containment_action="Immediate quarantine of remaining 925 units in warehouse.",
        issued_date=timezone.now().date(),
        response_due_date=timezone.now().date() + timedelta(days=14),
        issued_by=admin_user,
        qualification_audit=audit_a,
        affected_item_code="CAN-TIP-004",
    )


@pytest.fixture
def scar_b(db, tenant_b, supplier_party_b, admin_b, audit_b):
    return SupplierCorrectiveAction.objects.create(
        tenant=tenant_b,
        supplier=supplier_party_b,
        title="Globex Seal Defect SCAR",
        defect_summary="Cracked seals delivered.",
        severity="critical",
        status="issued",
        issued_date=timezone.now().date(),
        issued_by=admin_b,
        qualification_audit=audit_b,
    )


@pytest.fixture
def scn_a(db, tenant_a, supplier_party_a, admin_user, audit_a):
    return SupplierChangeNotification.objects.create(
        tenant=tenant_a,
        supplier=supplier_party_a,
        title="Ultrasonic Bath Frequency Upgrade from 40kHz to 68kHz",
        change_category="manufacturing_process",
        risk_level="level_2_moderate",
        status="technical_evaluation",
        description="Supplier is changing ultrasonic cleaning frequency to improve surface finish.",
        affected_item_code="CAN-TIP-004",
        affects_form_fit_function=False,
        requires_requalification=False,
        requalification_audit=audit_a,
        evaluated_by=admin_user,
    )


@pytest.fixture
def scn_b(db, tenant_b, supplier_party_b, admin_b, audit_b):
    return SupplierChangeNotification.objects.create(
        tenant=tenant_b,
        supplier=supplier_party_b,
        title="Globex Vendor Tooling Relocation",
        change_category="tooling_equipment",
        risk_level="level_3_major",
        status="submitted",
        description="Vendor moving molding tool to new plant.",
        affects_form_fit_function=True,
        requires_requalification=True,
        requalification_audit=audit_b,
        evaluated_by=admin_b,
    )


# ---------------------------------------------------------------------------
# 12.7 Incoming Quality Control Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def incoming_plan_a(db, tenant_a, supplier_party_a, doc_a, quality_department):
    return IncomingInspectionPlan.objects.create(
        tenant=tenant_a,
        title="Receiving Plan - Titanium Rods",
        item_code="TI-ROD-01",
        item_name="Medical Grade Titanium Rod 10mm",
        revision="A",
        sampling_standard="ansi_asq_z14",
        inspection_level="level_2",
        inspection_severity="normal",
        inspection_frequency="every_lot",
        skip_lot_interval=5,
        aql_critical=Decimal("0.00"),
        aql_major=Decimal("1.00"),
        aql_minor=Decimal("4.00"),
        requires_coa=True,
        requires_coc=False,
        status="active",
        characteristics_matrix=[
            {"name": "Diameter", "type": "variable", "target": 10.0, "lsl": 9.95, "usl": 10.05, "unit": "mm"},
            {"name": "Surface Finish", "type": "attribute", "target": "Ra < 0.4", "unit": "um"},
        ],
        supplier=supplier_party_a,
        sop_document=doc_a,
        assigned_team=quality_department,
    )


@pytest.fixture
def incoming_plan_b(db, tenant_b, supplier_party_b, doc_b, quality_department_b):
    return IncomingInspectionPlan.objects.create(
        tenant=tenant_b,
        title="Globex Plan - Ceramic Seals",
        item_code="CER-SEAL-09",
        item_name="High-Alumina Ceramic Gasket Seal",
        revision="B",
        sampling_standard="iso_2859_1",
        inspection_level="level_1",
        inspection_severity="normal",
        inspection_frequency="every_lot",
        status="active",
        supplier=supplier_party_b,
        sop_document=doc_b,
        assigned_team=quality_department_b,
    )


@pytest.fixture
def incoming_lot_a(db, tenant_a, supplier_party_a, incoming_plan_a, admin_user):
    return IncomingInspectionLot.objects.create(
        tenant=tenant_a,
        inspection_plan=incoming_plan_a,
        supplier=supplier_party_a,
        item_code="TI-ROD-01",
        item_name="Medical Grade Titanium Rod 10mm",
        lot_number="LOT-2026-IQC-001",
        lot_quantity=Decimal("500.000"),
        sample_size=32,
        inspected_quantity=32,
        accepted_quantity=Decimal("500.000"),
        stage="completed",
        usage_decision="accepted",
        spc_mean=Decimal("10.0010"),
        spc_std_dev=Decimal("0.0120"),
        spc_cp=Decimal("1.390"),
        spc_cpk=Decimal("1.360"),
        spc_out_of_control=False,
        inspector=admin_user,
        decided_by=admin_user,
        measurements_data=[
            {"sample_no": 1, "characteristic": "Diameter", "value": 10.001, "is_pass": True},
            {"sample_no": 2, "characteristic": "Diameter", "value": 9.998, "is_pass": True},
        ],
    )


@pytest.fixture
def incoming_lot_b(db, tenant_b, supplier_party_b, incoming_plan_b, admin_b):
    return IncomingInspectionLot.objects.create(
        tenant=tenant_b,
        inspection_plan=incoming_plan_b,
        supplier=supplier_party_b,
        item_code="CER-SEAL-09",
        item_name="High-Alumina Ceramic Gasket Seal",
        lot_number="LOT-GLX-9901",
        lot_quantity=Decimal("200.000"),
        sample_size=13,
        stage="in_inspection",
        usage_decision="pending",
        inspector=admin_b,
    )


@pytest.fixture
def coa_a(db, tenant_a, supplier_party_a, incoming_lot_a, incoming_plan_a, admin_user, doc_a):
    return CertificateOfAnalysis.objects.create(
        tenant=tenant_a,
        certificate_number="COA-VND-2026-001",
        item_code="TI-ROD-01",
        item_name="Medical Grade Titanium Rod 10mm",
        lot_number="LOT-2026-IQC-001",
        manufacturer_name="Advanced Titanium Alloys LLC",
        supplier=supplier_party_a,
        inspection_lot=incoming_lot_a,
        inspection_plan=incoming_plan_a,
        supporting_document=doc_a,
        parameters_payload=[
            {"parameter": "Tensile Strength", "lsl": 860, "usl": 950, "actual_value": 895, "unit": "MPa", "is_pass": True},
            {"parameter": "Yield Strength", "lsl": 790, "usl": 880, "actual_value": 830, "unit": "MPa", "is_pass": True},
        ],
        variance_count=0,
        is_within_spec=True,
        status="verified_compliant",
        verified_by=admin_user,
    )


@pytest.fixture
def coa_b(db, tenant_b, supplier_party_b, incoming_lot_b, incoming_plan_b, admin_b, doc_b):
    return CertificateOfAnalysis.objects.create(
        tenant=tenant_b,
        certificate_number="COA-GLX-9988",
        item_code="CER-SEAL-09",
        item_name="High-Alumina Ceramic Gasket Seal",
        lot_number="LOT-GLX-9901",
        supplier=supplier_party_b,
        inspection_lot=incoming_lot_b,
        inspection_plan=incoming_plan_b,
        supporting_document=doc_b,
        variance_count=1,
        is_within_spec=False,
        status="received",
    )


@pytest.fixture
def rma_a(db, tenant_a, supplier_party_a, incoming_lot_a, admin_user):
    return QualityReturnAuthorization.objects.create(
        tenant=tenant_a,
        inspection_lot=incoming_lot_a,
        supplier=supplier_party_a,
        vendor_rma_number="RMA-RET-2026-01",
        return_reason="dimensional_oos",
        disposition_type="return_for_credit",
        return_quantity=Decimal("50.000"),
        unit_of_measure="EA",
        estimated_credit_value=Decimal("1250.00"),
        status="rma_requested",
        assigned_coordinator=admin_user,
    )


@pytest.fixture
def rma_b(db, tenant_b, supplier_party_b, incoming_lot_b, admin_b):
    return QualityReturnAuthorization.objects.create(
        tenant=tenant_b,
        inspection_lot=incoming_lot_b,
        supplier=supplier_party_b,
        vendor_rma_number="RMA-GLX-0099",
        return_reason="functional_failure",
        disposition_type="return_for_replacement",
        return_quantity=Decimal("20.000"),
        unit_of_measure="EA",
        estimated_credit_value=Decimal("400.00"),
        status="draft",
        assigned_coordinator=admin_b,
    )


@pytest.fixture
def in_process_inspection_a(db, tenant_a, admin_user):
    return InProcessInspection.objects.create(
        tenant=tenant_a,
        title="CNC Mill Line 2 In-Line Inspection",
        inspection_type="dimensional_tolerance",
        stage_gate="Op 020 - Turning",
        status="completed",
        disposition="released",
        production_order_number="PO-2026-8801",
        work_center_code="WC-CNC-02",
        item_code="ST-SHAFT-22",
        item_name="Precision Turbine Stainless Drive Shaft",
        lot_number="LOT-2026-IP-001",
        batch_quantity=500,
        sample_size_inspected=5,
        quantity_passed=5,
        quantity_rejected=0,
        inspector=admin_user,
    )


@pytest.fixture
def in_process_inspection_b(db, tenant_b, admin_b):
    return InProcessInspection.objects.create(
        tenant=tenant_b,
        title="Globex Assembly Check",
        inspection_type="visual_surface",
        stage_gate="Final Inspection",
        status="in_inspection",
        disposition="pending",
        production_order_number="GLX-PO-001",
        work_center_code="WC-GLX-01",
        item_code="GLX-ITEM-01",
        item_name="Globex Component",
        lot_number="LOT-GLX-001",
        batch_quantity=100,
        sample_size_inspected=10,
        quantity_passed=10,
        quantity_rejected=0,
        inspector=admin_b,
    )


@pytest.fixture
def fai_a(db, tenant_a, admin_user):
    return FirstArticleInspection.objects.create(
        tenant=tenant_a,
        title="AS9102 Full FAI - Bracket",
        fai_type="full_fai",
        setup_reason="new_product_intro",
        status="in_inspection",
        release_verdict="pending",
        production_order_number="PO-2026-FAI-01",
        work_center_code="WC-CNC-01",
        item_code="AERO-BRKT-901",
        item_name="Titanium Support Bracket Strut",
        drawing_number="DWG-AERO-901",
        drawing_revision="Rev C",
        total_characteristics_inspected=18,
        characteristics_conforming=18,
        characteristics_out_of_spec=0,
        inspector=admin_user,
    )


@pytest.fixture
def fai_b(db, tenant_b, admin_b):
    return FirstArticleInspection.objects.create(
        tenant=tenant_b,
        title="Globex FAI",
        fai_type="full_fai",
        setup_reason="new_product_intro",
        status="draft",
        release_verdict="pending",
        production_order_number="GLX-PO-FAI",
        work_center_code="WC-GLX-02",
        item_code="GLX-ITEM-99",
        item_name="Globex Bracket",
        drawing_number="DWG-GLX-01",
        drawing_revision="Rev A",
        total_characteristics_inspected=5,
        characteristics_conforming=5,
        characteristics_out_of_spec=0,
        inspector=admin_b,
    )


@pytest.fixture
def parameter_log_a(db, tenant_a, admin_user):
    return ProcessParameterLog.objects.create(
        tenant=tenant_a,
        parameter_name="Reflow Temperature",
        parameter_category="temperature",
        unit_of_measure="°C",
        work_center_code="WC-SMT-01",
        production_order_number="PO-2026-8802",
        item_code="PCB-A440",
        lot_number="LOT-2026-IP-002",
        target_nominal_value=Decimal("245.0000"),
        upper_spec_limit=Decimal("255.0000"),
        lower_spec_limit=Decimal("235.0000"),
        upper_control_limit=Decimal("250.0000"),
        lower_control_limit=Decimal("240.0000"),
        recorded_value=Decimal("246.2000"),
        excursion_status="normal",
        logged_by=admin_user,
    )


@pytest.fixture
def parameter_log_b(db, tenant_b, admin_b):
    return ProcessParameterLog.objects.create(
        tenant=tenant_b,
        parameter_name="Globex Pressure",
        parameter_category="pressure",
        unit_of_measure="bar",
        work_center_code="WC-GLX-01",
        production_order_number="GLX-PO-002",
        item_code="GLX-ITEM-01",
        lot_number="LOT-GLX-002",
        target_nominal_value=Decimal("50.0000"),
        upper_spec_limit=Decimal("60.0000"),
        lower_spec_limit=Decimal("40.0000"),
        recorded_value=Decimal("51.0000"),
        excursion_status="normal",
        logged_by=admin_b,
    )


@pytest.fixture
def layered_audit_a(db, tenant_a, admin_user):
    return LayeredProcessAudit.objects.create(
        tenant=tenant_a,
        title="Daily Supervisor LPA",
        audit_layer="tier_2_supervisor",
        focus_area="standard_work_wi",
        status="completed",
        work_center_code="WC-CNC-02",
        shift="Shift 1 (Morning)",
        scheduled_date=timezone.now().date(),
        conducted_at=timezone.now(),
        total_questions_audited=10,
        questions_conforming=10,
        questions_non_conforming=0,
        compliance_percentage=Decimal("100.00"),
        auditor=admin_user,
    )


@pytest.fixture
def layered_audit_b(db, tenant_b, admin_b):
    return LayeredProcessAudit.objects.create(
        tenant=tenant_b,
        title="Globex Weekly LPA",
        audit_layer="tier_3_quality_manager",
        focus_area="environmental_5s",
        status="scheduled",
        work_center_code="WC-GLX-01",
        shift="Shift 1",
        scheduled_date=timezone.now().date(),
        total_questions_audited=10,
        questions_conforming=10,
        questions_non_conforming=0,
        compliance_percentage=Decimal("100.00"),
        auditor=admin_b,
    )


# ==============================================================================
# Sub-module 12.9: Final Quality Control / Outgoing Quality Control (FQC / OQC)
# ==============================================================================

@pytest.fixture
def customer_party_a(db, tenant_a):
    return Party.objects.create(
        tenant=tenant_a,
        name="Acme Aerospace Client Ltd",
    )


@pytest.fixture
def customer_party_b(db, tenant_b):
    return Party.objects.create(
        tenant=tenant_b,
        name="Globex Medical Client LLC",
    )


@pytest.fixture
def final_lot_a(db, tenant_a, admin_user, customer_party_a):
    return FinalInspectionLot.objects.create(
        tenant=tenant_a,
        title="Final Inspection - Precision Actuators",
        inspection_stage="post_packaging_oqc",
        sampling_standard="ansi_asq_z1_4_normal",
        aql_critical=Decimal("0.00"),
        aql_major=Decimal("0.65"),
        aql_minor=Decimal("4.00"),
        status="completed",
        usage_decision="accepted",
        decision_rationale="AQL Level II conforming, 0 defects",
        item_code="ACT-990",
        item_name="Precision Flight Actuator",
        lot_number="LOT-2026-FQC-01",
        batch_number="BATCH-990-A",
        serial_number_range="ACT-001 through ACT-100",
        lot_quantity=100,
        sample_size_inspected=20,
        critical_defects_count=0,
        major_defects_count=0,
        minor_defects_count=0,
        units_passed=20,
        units_rejected=0,
        visual_inspection_passed=True,
        dimensional_inspection_passed=True,
        functional_test_passed=True,
        packaging_inspection_passed=True,
        is_on_hold=False,
        customer=customer_party_a,
        inspector=admin_user,
        decision_by=admin_user,
        inspection_date=timezone.now().date(),
        decision_date=timezone.now().date(),
    )


@pytest.fixture
def final_lot_b(db, tenant_b, admin_b, customer_party_b):
    return FinalInspectionLot.objects.create(
        tenant=tenant_b,
        title="Globex OQC Inspection",
        inspection_stage="finished_goods_dock",
        sampling_standard="ansi_asq_z1_4_normal",
        aql_critical=Decimal("0.00"),
        aql_major=Decimal("1.00"),
        aql_minor=Decimal("4.00"),
        status="in_progress",
        usage_decision="quarantined_hold",
        decision_rationale="Quarantined on hold",
        item_code="GLX-VALVE-01",
        item_name="Globex Safety Valve",
        lot_number="LOT-GLX-FQC-01",
        lot_quantity=500,
        sample_size_inspected=50,
        critical_defects_count=0,
        major_defects_count=2,
        minor_defects_count=1,
        units_passed=47,
        units_rejected=3,
        visual_inspection_passed=False,
        dimensional_inspection_passed=True,
        functional_test_passed=True,
        packaging_inspection_passed=False,
        is_on_hold=True,
        hold_reason="Packaging torn during transit",
        customer=customer_party_b,
        inspector=admin_b,
        inspection_date=timezone.now().date(),
    )


@pytest.fixture
def coc_a(db, tenant_a, admin_user, customer_party_a, final_lot_a):
    return CertificateOfConformance.objects.create(
        tenant=tenant_a,
        title="CoC - Precision Actuators",
        certificate_type="aerospace_as9100_as9102",
        status="approved_signed",
        customer=customer_party_a,
        customer_po_number="PO-99120",
        sales_order_number="SO-4401",
        item_code="ACT-990",
        item_name="Precision Flight Actuator",
        revision="Rev D",
        lot_number="LOT-2026-FQC-01",
        certified_quantity=100,
        inspection_lot=final_lot_a,
        applicable_specifications="AS9100D, MIL-STD-130N",
        test_results_summary="Tensile 850 MPa, zero pressure leaks.",
        conformance_statement="Certified conforming in all respects to engineering drawing.",
        authorized_signatory=admin_user,
        signatory_title="QA Director",
        signed_date=timezone.now().date(),
        digital_signature_hash="sha256-mock-hash-valid",
    )


@pytest.fixture
def coc_b(db, tenant_b, admin_b, customer_party_b, final_lot_b):
    return CertificateOfConformance.objects.create(
        tenant=tenant_b,
        title="Globex CoC Draft",
        certificate_type="standard_commercial",
        status="draft",
        customer=customer_party_b,
        item_code="GLX-VALVE-01",
        item_name="Globex Safety Valve",
        certified_quantity=500,
        inspection_lot=final_lot_b,
    )


@pytest.fixture
def packaging_verification_a(db, tenant_a, admin_user, final_lot_a):
    return PackagingLabelVerification.objects.create(
        tenant=tenant_a,
        title="Packaging Audit - Actuators",
        status="verified",
        disposition="pass_released",
        item_code="ACT-990",
        item_name="Precision Flight Actuator",
        lot_number="LOT-2026-FQC-01",
        carton_count_inspected=10,
        label_part_number="LBL-ACT-99",
        label_artwork_revision="Rev 2",
        barcode_symbology="datamatrix_gs1_2d",
        scanned_barcode_data="(01)0085009901(10)LOT-2026-FQC-01",
        iso_iec_print_grade="grade_a_4_0",
        label_content_accurate=True,
        regulatory_symbols_present=True,
        serialization_verified=True,
        carton_integrity_intact=True,
        tamper_evident_seal_intact=True,
        cushioning_dunnage_adequate=True,
        pallet_stacking_compliant=True,
        inspection_lot=final_lot_a,
        verifier=admin_user,
        verified_date=timezone.now().date(),
    )


@pytest.fixture
def packaging_verification_b(db, tenant_b, admin_b, final_lot_b):
    return PackagingLabelVerification.objects.create(
        tenant=tenant_b,
        title="Globex Packaging Audit",
        status="failed",
        disposition="relabel_required",
        item_code="GLX-VALVE-01",
        item_name="Globex Safety Valve",
        lot_number="LOT-GLX-FQC-01",
        carton_count_inspected=5,
        barcode_symbology="code_128_1d",
        iso_iec_print_grade="grade_d_1_0",
        label_content_accurate=False,
        carton_integrity_intact=False,
        tamper_evident_seal_intact=False,
        inspection_lot=final_lot_b,
        verifier=admin_b,
        verified_date=timezone.now().date(),
    )


@pytest.fixture
def quality_release_a(db, tenant_a, admin_user, customer_party_a, final_lot_a, coc_a, packaging_verification_a):
    return QualityReleaseAuthorization.objects.create(
        tenant=tenant_a,
        title="Final Outgoing Release - Actuators",
        status="authorized",
        release_disposition="released_full",
        customer=customer_party_a,
        destination_country="United States",
        destination_facility="Aero Hub Bay 1",
        sales_order_number="SO-4401",
        lot_number="LOT-2026-FQC-01",
        quantity_authorized=100,
        inspection_lot=final_lot_a,
        certificate_of_conformance=coc_a,
        packaging_verification=packaging_verification_a,
        is_on_hold=False,
        final_inspection_passed=True,
        no_open_ncrs_or_capas=True,
        packaging_label_approved=True,
        coc_issued_and_signed=True,
        export_compliance_verified=True,
        shipping_container_security_seal="SEAL-44910",
        carrier_name="FedEx Cargo",
        releasing_officer=admin_user,
        release_date=timezone.now().date(),
    )


@pytest.fixture
def quality_release_b(db, tenant_b, admin_b, customer_party_b, final_lot_b):
    return QualityReleaseAuthorization.objects.create(
        tenant=tenant_b,
        title="Globex Release Quarantine",
        status="active_hold",
        release_disposition="quarantined_hold",
        customer=customer_party_b,
        lot_number="LOT-GLX-FQC-01",
        quantity_authorized=500,
        inspection_lot=final_lot_b,
        is_on_hold=True,
        hold_reason="Quarantined on hold",
        releasing_officer=admin_b,
    )


# ---------------------------------------------------------------------------
# Sub-module 12.10 Fixtures: Calibration & Measurement System Analysis
# ---------------------------------------------------------------------------


@pytest.fixture
def cal_vendor_a(db, tenant_a):
    vendor = Party.objects.create(
        tenant=tenant_a,
        name="Precision Standards Metrology Lab LLC",
        kind="organization",
    )
    PartyRole.objects.create(
        tenant=tenant_a,
        party=vendor,
        role="vendor",
    )
    return vendor


@pytest.fixture
def cal_vendor_b(db, tenant_b):
    vendor = Party.objects.create(
        tenant=tenant_b,
        name="Globex Calibration Services Ltd",
        kind="organization",
    )
    PartyRole.objects.create(
        tenant=tenant_b,
        party=vendor,
        role="vendor",
    )
    return vendor


@pytest.fixture
def cal_standard_a(db, tenant_a, quality_department):
    return CalibrationGage.objects.create(
        tenant=tenant_a,
        gage_id="GAG-REF-001",
        name="Ceramic Master Gauge Block Set Grade 0",
        gage_type="gauge_block_pin",
        status="active_in_service",
        criticality="critical",
        manufacturer="Mitutoyo",
        model_number="516-902",
        serial_number="MB-99201",
        is_reference_standard=True,
        nist_traceability_number="NIST-MET-2026-8810",
        measurement_range="0.5mm to 100mm",
        resolution="0.0001 mm",
        accuracy_spec="Grade 0 ISO 3650",
        max_permissible_error=Decimal("0.00012"),
        engineering_unit="mm",
        calibration_interval_days=365,
        last_calibration_date=timezone.now().date() - timedelta(days=60),
        next_calibration_due=timezone.now().date() + timedelta(days=305),
        department=quality_department,
    )


@pytest.fixture
def cal_standard_b(db, tenant_b, quality_department_b):
    return CalibrationGage.objects.create(
        tenant=tenant_b,
        gage_id="GAG-REF-GLX-01",
        name="Globex Reference Length Standard",
        gage_type="gauge_block_pin",
        status="active_in_service",
        criticality="critical",
        manufacturer="Starrett",
        model_number="ST-500",
        serial_number="GLX-REF-880",
        is_reference_standard=True,
        nist_traceability_number="NIST-GLX-2026-001",
        measurement_range="0 to 500mm",
        engineering_unit="mm",
        calibration_interval_days=365,
        last_calibration_date=timezone.now().date() - timedelta(days=30),
        next_calibration_due=timezone.now().date() + timedelta(days=335),
        department=quality_department_b,
    )


@pytest.fixture
def cal_gage_a(db, tenant_a, quality_department, cal_standard_a):
    return CalibrationGage.objects.create(
        tenant=tenant_a,
        gage_id="GAG-DIG-002",
        name="Digital Outside Micrometer 0-25mm",
        gage_type="caliper_micrometer",
        status="active_in_service",
        criticality="critical",
        manufacturer="Mitutoyo",
        model_number="293-240-30",
        serial_number="MIC-40912",
        is_reference_standard=False,
        reference_standard_parent=cal_standard_a,
        nist_traceability_number="NIST-CAL-2026-0044",
        measurement_range="0 - 25 mm",
        resolution="0.001 mm",
        accuracy_spec="+/- 0.001 mm",
        max_permissible_error=Decimal("0.00200"),
        engineering_unit="mm",
        calibration_interval_days=180,
        last_calibration_date=timezone.now().date() - timedelta(days=30),
        next_calibration_due=timezone.now().date() + timedelta(days=150),
        department=quality_department,
    )


@pytest.fixture
def cal_gage_b(db, tenant_b, quality_department_b, cal_standard_b):
    return CalibrationGage.objects.create(
        tenant=tenant_b,
        gage_id="GAG-DIG-GLX-02",
        name="Globex Digital Caliper 150mm",
        gage_type="caliper_micrometer",
        status="active_in_service",
        criticality="major",
        manufacturer="Mitutoyo",
        model_number="500-196-30",
        serial_number="GLX-CAL-1002",
        is_reference_standard=False,
        reference_standard_parent=cal_standard_b,
        measurement_range="0 - 150 mm",
        engineering_unit="mm",
        calibration_interval_days=180,
        last_calibration_date=timezone.now().date() - timedelta(days=20),
        next_calibration_due=timezone.now().date() + timedelta(days=160),
        department=quality_department_b,
    )


@pytest.fixture
def cal_record_a(db, tenant_a, cal_gage_a, cal_standard_a, cal_vendor_a, admin_user):
    record = CalibrationRecord.objects.create(
        tenant=tenant_a,
        gage=cal_gage_a,
        calibration_date=timezone.now().date() - timedelta(days=30),
        status="completed",
        calibration_type="external_accredited",
        service_vendor=cal_vendor_a,
        certificate_number="CERT-CAL-2026-0819",
        overall_result="pass",
        ambient_temperature_c=Decimal("20.10"),
        ambient_relative_humidity=Decimal("45.00"),
        expanded_uncertainty=Decimal("0.00045"),
        test_uncertainty_ratio=Decimal("4.44"),
        guardband_applied=True,
        calibrated_by_user=admin_user,
        technician_name="Sarah Connor, Metrologist",
        approved_by=admin_user,
        approved_at=timezone.now(),
    )
    record.standards_used.add(cal_standard_a)
    return record


@pytest.fixture
def cal_record_oot_a(db, tenant_a, cal_gage_a, cal_standard_a, admin_user):
    record = CalibrationRecord.objects.create(
        tenant=tenant_a,
        gage=cal_gage_a,
        calibration_date=timezone.now().date() - timedelta(days=10),
        status="completed",
        calibration_type="internal_metrology",
        certificate_number="CERT-INT-2026-OOT-01",
        overall_result="fail_out_of_tolerance",
        ambient_temperature_c=Decimal("20.00"),
        ambient_relative_humidity=Decimal("46.00"),
        expanded_uncertainty=Decimal("0.00050"),
        test_uncertainty_ratio=Decimal("2.10"),
        guardband_applied=True,
        calibrated_by_user=admin_user,
        technician_name="John Doe, Cal Tech",
        approved_by=admin_user,
        approved_at=timezone.now(),
    )
    record.standards_used.add(cal_standard_a)
    return record


@pytest.fixture
def cal_record_b(db, tenant_b, cal_gage_b, cal_standard_b, cal_vendor_b, admin_b):
    record = CalibrationRecord.objects.create(
        tenant=tenant_b,
        gage=cal_gage_b,
        calibration_date=timezone.now().date() - timedelta(days=20),
        status="completed",
        calibration_type="external_accredited",
        service_vendor=cal_vendor_b,
        certificate_number="GLX-CERT-2026-001",
        overall_result="pass",
        calibrated_by_user=admin_b,
        technician_name="Globex Metrology Tech",
    )
    record.standards_used.add(cal_standard_b)
    return record


@pytest.fixture
def cal_oot_a(db, tenant_a, cal_gage_a, cal_record_oot_a, admin_user):
    return OutOfToleranceInvestigation.objects.create(
        tenant=tenant_a,
        calibration_record=cal_record_oot_a,
        gage=cal_gage_a,
        title="Torque & Measurement OOT Investigation 2026-01",
        status="investigating",
        risk_level="critical",
        suspect_window_start=timezone.now().date() - timedelta(days=90),
        suspect_window_end=timezone.now().date() - timedelta(days=10),
        suspect_lots_count=150,
        consumer_risk_rating=4,
        producer_risk_rating=3,
        product_recall_required=False,
        containment_actions_taken="Hold placed on production lot LOT-ACTUATOR-904",
        investigator=admin_user,
    )


@pytest.fixture
def cal_oot_b(db, tenant_b, cal_gage_b, cal_record_b, admin_b):
    return OutOfToleranceInvestigation.objects.create(
        tenant=tenant_b,
        calibration_record=cal_record_b,
        gage=cal_gage_b,
        title="Globex OOT Investigation",
        status="open",
        risk_level="minor",
        suspect_window_start=timezone.now().date() - timedelta(days=30),
        suspect_window_end=timezone.now().date() - timedelta(days=20),
        suspect_lots_count=10,
        investigator=admin_b,
    )


@pytest.fixture
def cal_msa_a(db, tenant_a, cal_gage_a, admin_user):
    return MeasurementSystemAnalysis.objects.create(
        tenant=tenant_a,
        gage=cal_gage_a,
        study_title="Machining Cell 1 Spool Diameter Gage R&R Study",
        study_type="gage_rr_crossed",
        status="approved",
        analysis_method="anova",
        characteristic_name="Outer Spool Diameter",
        specification_tolerance=Decimal("0.0500"),
        number_of_operators=3,
        number_of_parts=10,
        number_of_trials=3,
        repeatability_ev=Decimal("0.00185"),
        reproducibility_av=Decimal("0.00112"),
        gage_rr_grr=Decimal("0.00216"),
        part_variation_pv=Decimal("0.01520"),
        total_variation_tv=Decimal("0.01535"),
        percent_gage_rr_study_variation=Decimal("14.07"),
        percent_tolerance_pt_ratio=Decimal("25.92"),
        number_of_distinct_categories_ndc=Decimal("9.00"),
        bias_value=Decimal("0.00020"),
        linearity_slope=Decimal("0.00100"),
        linearity_r_squared=Decimal("0.9850"),
        study_lead=admin_user,
        study_date=timezone.now().date() - timedelta(days=15),
        approved_by=admin_user,
        approved_at=timezone.now(),
    )


@pytest.fixture
def cal_msa_b(db, tenant_b, cal_gage_b, admin_b):
    return MeasurementSystemAnalysis.objects.create(
        tenant=tenant_b,
        gage=cal_gage_b,
        study_title="Globex Valve Gage R&R Study",
        study_type="linearity_and_bias",
        status="draft",
        analysis_method="anova",
        characteristic_name="Globex Valve Diameter",
        study_lead=admin_b,
        study_date=timezone.now().date(),
    )


# ---------------------------------------------------------------------------
# Sub-module 12.11 Fixtures: Audit Management
# ---------------------------------------------------------------------------


@pytest.fixture
def audit_program_a(db, tenant_a, admin_user):
    today = timezone.now().date()
    return AuditProgram.objects.create(
        tenant=tenant_a,
        title="Acme Enterprise Quality Audit Program",
        program_year=today.year,
        program_type="integrated_enterprise",
        risk_basis="high_risk_semi_annual",
        scope_description="Global quality oversight covering ISO 13485:2016 design controls and cGMP.",
        start_date=today.replace(month=1, day=1),
        end_date=today.replace(month=12, day=31),
        allocated_budget_hours=480,
        status="active",
        program_manager=admin_user,
        notes="Board-approved audit program.",
    )


@pytest.fixture
def audit_program_b(db, tenant_b, admin_b):
    today = timezone.now().date()
    return AuditProgram.objects.create(
        tenant=tenant_b,
        title="Globex Supplier Audit Program",
        program_year=today.year,
        program_type="supplier_external",
        risk_basis="medium_risk_biennial",
        scope_description="Supplier and external vendor quality audit program.",
        start_date=today.replace(month=1, day=1),
        end_date=today.replace(month=12, day=31),
        allocated_budget_hours=240,
        status="active",
        program_manager=admin_b,
        notes="Globex vendor audit program.",
    )


@pytest.fixture
def quality_audit_a(db, tenant_a, audit_program_a, admin_user, quality_department):
    today = timezone.now().date()
    return QualityAudit.objects.create(
        tenant=tenant_a,
        program=audit_program_a,
        title="ISO 13485:2016 Design Controls Audit",
        audit_type="internal_system",
        audit_method="on_site",
        standard_framework="iso_13485_2016",
        target_org_unit=quality_department,
        lead_auditor=admin_user,
        planned_start_date=today - timedelta(days=10),
        planned_end_date=today + timedelta(days=5),
        scope_objectives="Design history file and risk management controls verification.",
        product_scope="CardioSense Pro Series IV",
        status="in_progress",
        outcome="pending",
    )


@pytest.fixture
def quality_audit_b(db, tenant_b, audit_program_b, admin_b, quality_department_b):
    today = timezone.now().date()
    return QualityAudit.objects.create(
        tenant=tenant_b,
        program=audit_program_b,
        title="Globex ISO 9001 Supplier Audit",
        audit_type="supplier_qualification",
        audit_method="on_site",
        standard_framework="iso_9001_2015",
        target_org_unit=quality_department_b,
        lead_auditor=admin_b,
        planned_start_date=today - timedelta(days=5),
        planned_end_date=today + timedelta(days=10),
        scope_objectives="Supplier receiving and quality assurance system audit.",
        product_scope="Globex Valves",
        status="scheduled",
        outcome="pending",
    )


@pytest.fixture
def audit_finding_a(db, tenant_a, quality_audit_a, admin_user, quality_department):
    today = timezone.now().date()
    return AuditFinding.objects.create(
        tenant=tenant_a,
        audit=quality_audit_a,
        finding_number_in_audit=1,
        title="Discrepancy in DHF Table 4 risk file revision index",
        severity="minor",
        standard_clause="ISO 13485:2016 §7.3.3",
        requirement_statement="Design risk management files shall maintain contemporaneous revision history.",
        condition_evidence="DHF-774 Rev C referenced Risk File RA-102 Rev B instead of active Rev C.",
        audited_org_unit=quality_department,
        assignee=admin_user,
        response_due_date=today + timedelta(days=20),
        status="issued",
    )


@pytest.fixture
def audit_finding_b(db, tenant_b, quality_audit_b, admin_b, quality_department_b):
    today = timezone.now().date()
    return AuditFinding.objects.create(
        tenant=tenant_b,
        audit=quality_audit_b,
        finding_number_in_audit=1,
        title="Missing lot traceability in supplier Certificate of Analysis",
        severity="major",
        standard_clause="ISO 9001:2015 §8.4",
        requirement_statement="External suppliers must provide full traceability.",
        condition_evidence="Raw material heat lot not referenced on receiving tag.",
        audited_org_unit=quality_department_b,
        assignee=admin_b,
        response_due_date=today + timedelta(days=15),
        status="issued",
    )


@pytest.fixture
def inspection_host_a(db, tenant_a, quality_audit_a, admin_user):
    today = timezone.now().date()
    return RegulatoryInspectionHost.objects.create(
        tenant=tenant_a,
        audit=quality_audit_a,
        inspection_title="US FDA cGMP / QSIT Surveillance Inspection",
        agency_or_body="fda_cdrh",
        agency_name="US Food & Drug Administration",
        lead_inspector_name="Consumer Safety Officer Arthur Vance",
        scheduled_start_date=today - timedelta(days=2),
        scheduled_end_date=today + timedelta(days=3),
        actual_start_date=today - timedelta(days=2),
        front_room_lead=admin_user,
        back_room_lead=admin_user,
        war_room_location="Executive Conference Room Alpha",
        status="active_inspection",
        requests_logged_count=12,
        requests_fulfilled_count=10,
    )


@pytest.fixture
def inspection_host_b(db, tenant_b, quality_audit_b, admin_b):
    today = timezone.now().date()
    return RegulatoryInspectionHost.objects.create(
        tenant=tenant_b,
        audit=quality_audit_b,
        inspection_title="TÜV SÜD ISO 13485:2016 Recertification Audit",
        agency_or_body="iso_notified_body",
        agency_name="TÜV SÜD Product Service GmbH",
        lead_inspector_name="Lead Auditor Klaus Becker",
        scheduled_start_date=today + timedelta(days=30),
        scheduled_end_date=today + timedelta(days=34),
        front_room_lead=admin_b,
        back_room_lead=admin_b,
        war_room_location="Boardroom B",
        status="preparation",
    )









