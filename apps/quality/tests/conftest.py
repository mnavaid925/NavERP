"""Shared fixtures for apps/quality test suite (Module 12: Quality Management System)."""
from datetime import timedelta
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





