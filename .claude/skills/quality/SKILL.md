---
name: quality
description: Work on the Quality Management System (QMS) module (Module 12 — document control & management, controlled SOPs & work instructions, engineering/document change orders (DCO), 21 CFR Part 11 compliant electronic signatures with HMAC non-repudiation, training/compliance acknowledgments; 12.2 Design Controls & Development; 12.3 Risk Management (ISO 14971 / FMEA); 12.4 Corrective & Preventive Action (CAPA); 12.5 Non-Conformance & Deviation Management (NCR, Quarantine & Containment, MRB Dispositions, Process Deviations); 12.6 Supplier & Vendor Quality Management; 12.7 Incoming Quality Control (IQC); 12.8 In-Process Quality Control (IPQC); 12.9 Final Quality Control & Outgoing Quality Control (FQC / OQC); 12.10 Calibration & Measurement System Analysis (MSA); 12.11 Audit Management — Audit Programs [QPRG-], Quality Audits [QAUD-], Graded Audit Findings & Observations [QFND-], Regulatory & Certification Inspection Hosts [QHST-], Audit Action Tracker, and Inspection War Room Command Center; and 12.13 Customer Complaint Handling — Customer Complaints [QCMP-], Complaint Investigations [QCIN-], Regulatory Vigilance Reports [QRPT-], Field Actions & Recalls [QFMA-], and Complaint Intelligence & Trending Command Center). Use when the user asks to add/change/debug anything under apps/quality or templates/quality, extend the quality seeder, touch quality sidebar wiring (LIVE_LINKS 12.1 through 12.13), or invokes /quality.
---

# Quality Management System (QMS) Module (Module 12)

Enterprise Quality Management System (QMS) compliant with ISO 9001, ISO 13485:2016, ISO 14971:2019, IEC 60812, GxP, FDA 21 CFR Part 11, and FDA 21 CFR § 820.30 regulatory standards. Provides end-to-end controlled document lifecycle management, Engineering/Document Change Orders (DCO) with Change Control Board (CCB) governance, dual-credential electronic signatures with HMAC-SHA256 non-repudiation digests, employee compliance training acknowledgments, document archive vault workbench, medical device design planning, user needs & engineering specifications, stage-gate design reviews with independent reviewer governance, verification & validation protocols, dynamic Requirements Traceability Matrix (RTM), audit-ready Design History File (DHF) compilation, and ISO 14971 medical device risk management with hazard analysis, FMEA risk assessments, risk mitigation controls, interactive risk matrix heatmaps, risk traceability matrices, and risk management reports.

- **App path:** `apps/quality/`
- **Templates:** `templates/quality/`
- **URL prefix:** `/quality/` (`app_name="quality"`)
- Mounted in `config/urls.py`; registered in `config/settings.py` `INSTALLED_APPS` as `apps.quality`.

---

## Sub-modules Overview

- **12.1 Document Control & Management**:
  - **Controlled Documents** [`QDOC-`]: SOPs, Work Instructions, Policies, Specifications, Protocols, Manuals, and Forms with version control (`1.0` -> `2.0`), review interval tracking, lifecycle state machine (`draft` -> `in_review` -> `approved` -> `effective` -> `superseded` / `obsolete` / `archived`), and predecessor/successor lineage tracking.
  - **Document Change Orders (DCO)** [`QDCR-`]: Formal engineering change control tickets with priority triage (`low`, `medium`, `high`, `critical`, `emergency`), review assessments, regulatory impact determinations, and Change Control Board (CCB) approval workflows.
  - **21 CFR Part 11 Electronic Signatures** [`QSIG-`]: Dual-credential re-authentication (`password` check), signature meaning binding (`authored`, `reviewed`, `quality_approval`, `management_approval`, `ccb_approval`, `acknowledgment`), remote IP address capture, and RFC 2104 HMAC-SHA256 cryptographic verification digests.
  - **Document Acknowledgments** [`QACK-`]: SOP/policy distribution and compliance sign-off tracking for employees with due dates, overdue escalations, and binding electronic signatures.
  - **Document Archive Vault**: Specialized compliance workbench for exploring, filtering, and exporting superseded, obsolete, and archived historical documentation.

- **12.2 Design Controls & Development**:
  - **Design Projects & DHF Planning** [`QDPL-`]: Medical device and critical software development project management complying with FDA 21 CFR § 820.30 and ISO 13485:2016 Clause 7.3. Manages device classification (`class_i`, `class_ii`, `class_iii`), regulatory pathways (`510k`, `pma`, `de_novo`, `ce_mark`, `exempt`), sequential phase-gate lifecycle (`planning` -> `input` -> `output_verification` -> `validation` -> `commercial_closure` -> `closed`), project and quality leads, target completion dates, and post-transfer immutable regulatory freeze (`dhf_locked=True`).
  - **Design Inputs & Engineering Specs** [`QINP-`]: Product specifications, user needs, functional, software, hardware, safety, usability, risk control, and packaging requirements. Features parent-child requirement traceability (linking derived design inputs to parent user needs), acceptance criteria, priority triage (`low`, `medium`, `high`, `critical`), and auto-verification status tracking.
  - **Stage-Gate Design Reviews** [`QREV-`]: Formal phase milestone evaluations satisfying 21 CFR § 820.30(e). Governs review stages (`planning_gate`, `inputs_gate`, `outputs_gate`, `verification_gate`, `validation_gate`, `transfer_gate`, `post_market_gate`), lead reviewer assignment, mandatory independent reviewer sign-off (with operational independence from project lead), action item tracking, formal gate approval, and electronic signature linking.
  - **Design Verification & Validation Protocols** [`QVER-`]: V&V test execution records satisfying 21 CFR § 820.30(f)/(g). Features activity types (`design_verification`, `design_validation`), test methods (`lab_testing`, `inspection`, `analysis`, `clinical_eval`, `usability_study`, `simulation`), sample sizes, acceptance criteria, results summaries, pass/fail results (`pending`, `pass`, `fail`, `inconclusive`), executor tracking, and bi-directional status synchronization with primary design inputs.
  - **Requirements Traceability Matrix (RTM)**: Living compliance workbench rendering the multi-tier traceability chain (`User Need` -> `Design Input` -> `Verification Protocol` -> `Test Result` -> `Status`), calculating requirement coverage percentages, flagging uncovered inputs as coverage gaps, and offering streaming CSV export (`RTM_<number>.csv`).
  - **Design History File (DHF) Dossier**: Audit-ready regulatory dossier index compiling the complete design history (DHF plan, requirements specification, design review minutes, V&V execution protocols, and linked controlled documents), evaluating DHF completeness criteria, and providing CSV index export (`DHF_Index_<number>.csv`).

- **12.3 Risk Management (ISO 14971 / FMEA)**:
  - **Risk Management Plans (RMP)** [`QRMP-`]: ISO 14971 Clause 4 compliant risk management planning for medical devices and critical products. Manages device classification (`class_i`, `class_ii_a`, `class_ii_b`, `class_iii`), risk evaluation matrix dimensions (`3x3`, `4x4`, `5x5`), scope description, risk acceptability criteria/policy, periodic review intervals, linked `DesignProject`, lead risk manager, and lifecycle statuses (`draft` -> `active` -> `periodic_review` -> `archived`).
  - **Hazard Identification & FMEA Risk Assessments** [`QRSK-`]: ISO 14971 Clause 5/6 hazard analysis and IEC 60812 Failure Modes & Effects Analysis (DFMEA, PFMEA, UFMEA, AFMEA). Tracks sequence of events, hazardous situations, potential harm, initial Risk Priority Number ($RPN = S \times P \times D$), and auto-calculated initial risk levels (`unacceptable`, `alarp`, `broadly_acceptable`). Re-evaluates residual risk scores ($RPN_{res} = S_{res} \times P_{res} \times D_{res}$) upon applying risk controls, enforcing regulatory safety gates.
  - **Risk Control Measures & Mitigations** [`QRCM-`]: ISO 14971 Clause 7 risk reduction controls strictly structured according to the mandatory 3-tier hierarchy: (1) Inherent Safety by Design, (2) Protective Measures in medical device or manufacturing process, and (3) Information for Safety / Training / IFU warnings. Traces directly into the engineering design spine (`DesignInput` requirements, `DesignVerification` test protocols, and `ControlledDocument` procedures) with dual verification tracking (`implementation_verified`, `effectiveness_verified`).
  - **Risk Management Reviews & Reports (RMR)** [`QRMR-`]: ISO 14971 Clause 9 formal risk evaluation reports across project milestones (`initial_rmr`, `periodic_review`, `design_change_review`, `post_market_surveillance`, `complaint_trend_trigger`, `ncr_capa_trigger`). Enforces formal approval workflows, post-approval tampering guards, and 21 CFR Part 11 electronic signature integration.
  - **FMEA Risk Matrix Heatmap Workbench**: Interactive visual matrix mapping Severity vs. Probability distributions for pre-mitigation and residual risks, highlighting risk zone transitions, Pareto RPN distributions, and filtered plan-specific CSV export.
  - **Risk Traceability Matrix (Hazard -> Control -> Verification)**: Comprehensive traceability workbench linking every identified hazard to its control measure, verification protocol, test result, and residual risk acceptance evaluation with coverage metrics and CSV export.

- **12.4 Corrective & Preventive Action (CAPA)**:
  - **CAPA Investigations** [`QCAP-`]: Regulatory problem-solving workflows conforming to ISO 13485:2016 §8.5.2/§8.5.3 and 21 CFR § 820.100. Captures multi-source issue intake (`customer_complaint`, `internal_audit`, `ncr`, `management_review`, `supplier_issue`, `trend_analysis`, `regulatory_finding`), risk priority triage (`low`, `medium`, `high`, `critical`), immediate containment measures, 7-stage lifecycle state machine (`draft` -> `under_investigation` -> `rca_in_progress` -> `action_pending` -> `effectiveness_review` -> `closed` / `voided`), escalation protocols, and Part 11 electronic signature closure sign-offs.
  - **Root Cause Analysis (RCA)** [`QRCA-`]: Systematic root cause analysis combining the 5 Whys iterative causal ladder and the Ishikawa 6M fishbone analysis framework (`manpower`, `machine`, `material`, `method`, `measurement`, `environment`). Features escape point detection failure analysis, independent quality engineering verification, and prevention of premature closure.
  - **CAPA Action Plans** [`QACT-`]: Targeted action items categorized across containment, corrective, and preventive action types. Enforces strict parent CAPA integrity, links directly to QMS engineering assets (`ControlledDocument`, `DocumentChangeOrder`, `DesignProject`), tracks completion dates and implementation evidence, and mandates independent verification by a qualified user other than the assignee.
  - **Effectiveness Reviews & Verification** [`QEFF-`]: Delayed statistical evaluation window (30/60/90 days post-implementation) verifying that underlying causes were permanently eliminated without introducing unintended consequences. Features evaluation methods (`statistical_sampling`, `trend_analysis`, `process_audit`, `customer_feedback`, `repeat_incident_check`), defect recurrence tracking, and a hard safety invariant preventing an "Effective" determination if defect recurrence is documented.
  - **CAPA Tracking & Escalation Board**: High-level visual Kanban workbench tracking open investigations across 5 operational workflow lanes (`Draft`, `Under Investigation`, `RCA in Progress`, `Action Implementation`, `Effectiveness Review`) and 4 aging tiers (`0-30`, `31-60`, `61-90`, `>90 days`), surfacing overdue alerts, escalation badges, and filtered CSV exports.

- **12.5 Non-Conformance & Deviation Management**:
  - **Non-Conformance Reports (NCR)** [`QNCR-`]: Cross-functional defect logging conforming to 21 CFR § 820.90 and ISO 13485:2016 Clause 8.3 across intake sources (`incoming_inspection`, `in_process`, `final_qa`, `warehouse_storage`, `customer_return`, `internal_audit`, `supplier_notification`), severity triage, immediate physical containment, financial loss estimation, and disposition linking.
  - **Quarantine & Containment Holds** [`QHLD-`]: Red-tag physical and logical quarantine holds preventing unintended release, tracking segregated storage locations, initial vs. released quantity accounting, tampering seals, and authorized quality release workflows.
  - **Material Review Board (MRB) Dispositions** [`QMRB-`]: Formal tripartite MRB disposition authority (`rework`, `repair`, `scrap`, `return_to_vendor`, `use_as_is`, `regrade`) with cost accounting (scrap, rework labor, vendor chargeback) and multi-signature engineering/quality approval.
  - **Process Deviations & Concessions** [`QDEV-`]: Planned and unplanned departure authorization with risk classification (`minor`, `moderate`, `critical`), batch/unit quantity caps, temporal validity windows, and regulatory customer notification flags.
  - **NCR Analytics & Quality Cost Workbench**: Enterprise analytics command center with interactive trend charting, Pareto root-cause analysis, defect distribution, scrap/rework cost telemetry, and filtered CSV exports.

- **12.6 Supplier & Vendor Quality Management**:
  - **Approved Vendor List (AVL) Governance Directory**: Centralized governance command center across all active suppliers, tracking qualification status, risk tiers, audit scores, dock-to-stock certifications, receiving inspection protocols, and open SCAR/SCN alerts.
  - **Supplier Qualification Audits** [`QSQA-`]: Comprehensive on-site and desktop audit assessments satisfying ISO 13485:2016 Clause 7.4. Criticality tiers (`critical`, `major`, `minor`, `indirect`), audit scoring (0-100), qualification status state machine (`under_evaluation` -> `approved` / `conditional` / `suspended` / `disqualified`), dock-to-stock eligibility authorizations, CoA requirements, and quality agreement linking (`ControlledDocument`).
  - **Supplier Quality Scorecards** [`QSSC-`]: Multi-dimensional performance scorecards with automated 5-dimension weighted composite score calculation: Lot Acceptance Rate (30%), Defect PPM (25%), SCAR Responsiveness (20%), Audit Compliance (15%), and Documentation/CoA (10%), generating letter grades `A` (>=90), `B` (80-89.9), `C` (70-79.9), `D` (<70), with audited manual override capability.
  - **Supplier Corrective Action Requests (SCAR)** [`QSCA-`]: Customer-to-vendor CAPA lifecycle requiring 24-48h emergency containment, 8D problem solving, vendor 5 Whys root cause analysis, corrective/preventive plans, and independent effectiveness verification.
  - **Supplier Change Notifications (SCN/PCN)** [`QSCN-`]: Vendor-initiated material and process modifications, Form-Fit-Function (FFF) evaluation, risk triage, re-qualification triggers, and formal CCB/quality disposition sign-off.

- **12.7 Incoming Quality Control (IQC)**:
  - **Incoming Inspection Plans** [`QIIP-`]: Configurable inspection protocols governed by ANSI/ASQ Z1.4, ISO 2859-1 (attributes), and ISO 3951-1 (variables). Configures inspection levels (`level_1`, `level_2`, `level_3`, `s1`, `s2`, `s3`, `s4`), dynamic severity switching rules (`normal`, `tightened`, `reduced`), skip-lot frequencies, AQL defect thresholds (critical, major, minor), CoA/CoC verification gates, and quality SOP document linkages (`ControlledDocument`).
  - **Goods Receipt & Inspection Lots** [`QIIL-`]: Receiving inspection execution records with automated ANSI Z1.4 code letter calculation, sample size determination, dimensional measurement capture with automated finite-number validation, defect triage (critical, major, minor), usage decision state machine (`pending` -> `accepted` / `accepted_with_deviation` / `rework` / `scrap` / `quarantine` / `return_to_vendor`), skip-lot consecutive acceptance counters, automated non-conformance logging (`QNCR-`), and automated quarantine containment hold (`QHLD-`) creation upon lot rejection.
  - **Certificate of Analysis (CoA) Management** [`QCOA-`]: Vendor analytical test result verification conforming to receiving specifications. Parameter test result matching (min/max specification limits), verification state machine (`pending_review` -> `accepted` / `rejected` / `conditional`), and regulatory archive file attachments with MIME and extension validation.
  - **Quality Return Authorizations (RMA)** [`QRMA-`]: Formal vendor return merchandise authorizations and debit memos. Captures return reasons (`defective_material`, `out_of_spec`, `coa_failed`, `wrong_material`, `damaged_in_transit`, `over_shipment`), return quantities, disposition tracking (`replacement_requested`, `credit_memo_requested`, `rework_at_vendor`, `scrap_on_site`), carrier tracking numbers, and replacement receipt tracking.
  - **Inspection Data Capture & SPC Analytics Dashboard**: Interactive statistical process control dashboard displaying total lots inspected, lot acceptance rate (%), average process capability index ($C_{pk}$), out-of-control alert monitoring, defect Pareto distribution, and top supplier quality ranking leaderboard.

- **12.8 In-Process Quality Control (IPQC)**:
  - **In-Process Inspections** [`QIPQ-`]: Production floor inspections across execution stages (`first_piece`, `in_process_patrol`, `setup_verification`, `last_off`, `shift_handover`, `sampling`), inspection types (`attribute_go_no_go`, `variable_dimensional`, `visual_cosmetic`, `functional_test`), sample size, defect counts (critical, major, minor), defect categories (`dimensional`, `surface_defect`, `assembly_error`, `contamination`, `labeling_packaging`, `functional_failure`), pass/fail results (`pass`, `fail`, `conditional_pass`), disposition (`accept_to_run`, `rework_in_station`, `scrap_lot`, `quarantine_hold`, `escalate_to_ncr`), automated NCR spawning (`quality:non_conformance_report_detail`), and operator/inspector verification.
  - **First Article Inspection (FAI)** [`QFAI-`]: AS9102 Rev C and ISO 9001 compliant First Article Inspection protocols across setup reasons (`new_part_introduction`, `drawing_revision`, `machine_tooling_change`, `process_parameter_shift`, `material_lot_change`, `relocation_facility`, `extended_downtime`), AS9102 Form 1/2/3 characteristic verification (`characteristics_json`), drawing revision tracking, customer approval gating, and production authorization release state machine (`draft` -> `submitted` -> `in_review` -> `approved` / `rejected` -> `released_to_production`).
  - **Process Parameter Logs** [`QPAR-`]: Machine & environmental telemetry logs across parameter types (`temperature`, `pressure`, `speed_feed`, `humidity`, `dwell_time`, `torque_force`, `voltage_current`, `cycle_time`, `concentration_ph`), target nominal, USL/LSL tolerances, measured values, excursion flags (`in_control`, `warning_trend`, `out_of_control_excursion`), automated SPC excursion detection via standard deviations and control limits, immediate containment actions, and production order/work center tracking.
  - **Layered Process Audits (LPA)** [`QLPA-`]: CQI-8 compliant multi-tier hierarchical audit checklists across audit levels (`layer_1_shift_supervisor`, `layer_2_area_manager`, `layer_3_plant_executive`, `layer_4_specialist_safety_quality`), manufacturing work center and shift evaluations, question compliance scoring, automated compliance score calculation ($0-100\%$), findings count, and audit closure sign-off.

- **12.9 Final Quality Control (FQC) & Outgoing Quality Control (OQC)**:
  - **Final Inspection Lots** [`QFQC-`]: Finished goods release protocols across inspection stages (`post_packaging_oqc`, `pre_packaging_fqc`, `finished_goods_dock`, `functional_end_of_line`, `pre_shipment_audit`), sampling standards (`ansi_asq_z1_4_normal`, `ansi_asq_z1_4_tightened`, `c_zero_sampling`, `hundred_percent_inspection`), AQL defect triage (critical, major, minor), defect counts, units passed/rejected, multi-stage compliance checks (visual, dimensional, functional, packaging), usage decisions (`accepted`, `accepted_with_concession`, `quarantined_hold`, `rejected_mrb`), pass rate percentage telemetry, and quarantine hold management.
  - **Certificates of Conformance (CoC)** [`QCOC-`]: Formal customer attestation certificates across regulatory profiles (`standard_commercial`, `aerospace_as9100_as9102`, `medical_device_iso13485`, `automotive_iatf_16949`, `custom_customer_format`), customer and sales order linkages, applicable engineering specifications, test result summaries, legal conformance declarations, tamper-evident unique QR verification codes (`COC-`), cryptographic SHA-256 digital signature binding, post-signature immutability locks, and regulatory deletion guards.
  - **Packaging & Labeling Verifications** [`QPKG-`]: Shipping carton and pallet verification conforming to ISO/IEC 15415/15416 and GS1 standards. Barcode symbologies (`datamatrix_gs1_2d`, `code_128_1d`, `qr_code_2d`, `gs1_128_sscc`, `upc_ean_retail`), ISO/IEC print grading (`grade_a_4_0`, `grade_b_3_0`, `grade_c_2_0`, `grade_d_1_0`, `grade_f_fail`), decoded scanned payload verification, regulatory markings verification (CE, UL, RoHS, FDA, country-of-origin), carton integrity, tamper seals, and disposition tracking (`pass_released`, `relabel_required`, `repack_required`, `reject_quarantine`).
  - **Quality Release Authorizations** [`QREL-`]: Multi-gate finished goods outbound shipping release authorizations. Enforces 4-way compliance validation (final inspection passed, zero open NCRs/CAPAs, packaging approved, CoC issued and signed), cross-record counterparty customer integrity validation, container security seals, carrier tracking references, hold-authorization conflict protection, and audit logging.
  - **OQC Hold & Release Board**: Real-time operational Kanban command center tracking active quarantine holds across inspection lots and shipping releases, pending inspection queues, pending CoC sign-offs, and cleared shipments with unsliced KPI metric summary cards.

- **12.10 Calibration & Measurement System Analysis (MSA)**:
  - **Calibration Gages & Instrument Registry** [`QGAG-`]: Master gage registry satisfying ISO 9001:2015 §7.1.5, ISO/IEC 17025, and FDA 21 CFR § 820.72. Tracks instrument tags (`gage_id`), gage types (`gage_block_master`, `digital_micrometer`, `vernier_digital_caliper`, `optical_comparator_vision`, `torque_wrench`, `multimeter_dmm`, `pressure_transducer_calibrator`, `cct_temperature_well`, `height_gage`, `thread_plug_ring_gage`, `custom_fixture_indicator`), criticality (`safety_critical`, `quality_critical`, `standard_commercial`), reference standard flags, NIST traceability numbers, ISO 17025 accreditation, metrological resolutions, accuracy ratings, max permissible error (MPE), calibration intervals, due date forecasting, and self-parenting prevention.
  - **Calibration Execution & Metrology Records** [`QCAL-`]: Metrological event records across internal metrology labs and ISO 17025 accredited calibration vendors (`service_vendor` -> `core.Party`). Tracks certificate numbers, environmental telemetry (temperature °C, relative humidity %), expanded uncertainty ($U, k=2$), test uncertainty ratios ($TUR$), decision rules (`binary_shared_risk_simple`, `binary_guardbanded_ilac_g8`, `non_binary_fuzzy_acceptance`), guardbanded tolerance reduction, M2M reference standards used, and post-completion instrument state synchronization.
  - **Out-of-Tolerance (OOT) Investigations** [`QOOT-`]: Reverse-tracing quality investigations initiated upon calibration failures (`fail_out_of_tolerance`). Automates suspect manufacturing window bounding between the last in-spec passing calibration and the failure event, production lot containment, MPE exceedance calculation, consumer vs. producer risk ratings, product recall triggers, and direct cross-module escalations to NCR (`QNCR-`) and CAPA (`QCAP-`).
  - **Measurement System Analysis (MSA / Gage R&R)** [`QMSA-`]: AIAG MSA 4th Edition compliant measurement system analysis studies. Supports study types (`grr_crossed_anova`, `grr_nested_anova`, `linearity_and_bias`, `stability_study`, `attribute_agreement_kappa`, `type_1_gage_study`), ANOVA variance decomposition (Repeatability EV, Reproducibility AV, Total GRR, Part Variation PV, Total Variation TV), acceptance criteria evaluation (%GRR of study variation, %GRR of tolerance P/T ratio, and Number of Distinct Categories $ndc \ge 5$), linearity slopes, bias estimates, and regression goodness-of-fit $R^2$.
  - **Calibration Vendor Governance Directory**: Directory of external calibration laboratories and metrology service providers linked to `core.Party`, tracking ISO/IEC 17025 accreditation statuses, active calibrations performed, and direct deep-links into performed calibration history.

- **12.11 Audit Management**:
  - **Audit Program Planning** [`QPRG-`]: Annual and risk-based audit schedules conforming to ISO 19011:2018 and ISO 13485:2016 Clause 8.2.4. Tracks program year, audit frequency (`annual`, `semi_annual`, `quarterly`, `monthly`, `risk_based_continuous`), lifecycle status (`draft`, `approved`, `active`, `completed`, `cancelled`), lead audit manager (`accounts.User`), approving authority (`accounts.User`), formal approval date, allocated budget, scope description, objectives statement, and dynamic progress metrics (`progress_percentage` reusing annotated counts to prevent N+1 queries).
  - **Quality Audits & Protocols** [`QAUD-`]: Internal, supplier, and regulatory agency audit execution records across audit types (`internal_qms`, `internal_process`, `supplier_external`, `regulatory_agency`, `customer_second_party`, `certification_body`), standards frameworks (`iso_9001`, `iso_13485`, `fda_21_cfr_820`, `iso_14971`, `mdsap`, `eu_mdr`, `as9100`, `iatf_16949`, `gxp`), lead auditor and audit team members, department/supplier audited, execution methodology (`on_site`, `remote_virtual`, `hybrid`), audit status lifecycle (`scheduled`, `prep_in_progress`, `active_fieldwork`, `reporting`, `capa_pending`, `closed`, `cancelled`), quantitative scoring (0.00-100.00), executive summaries, and dynamic synchronization of child finding counters (`sync_findings_counts()`).
  - **Audit Findings & Observations** [`QFND-`]: Graded non-conformance logging conforming to ISO 19011 severity grading (`critical_finding`, `major_nonconformance`, `minor_nonconformance`, `opportunity_for_improvement`, `positive_observation`). Captures requirement statements, objective evidence, regulatory clause references, responsible department, assigned auditee (`accounts.User`), SLA response due dates, remediation responses, independent verification sign-off (enforcing auditor independence by barring assignees from self-verifying and closing), and direct cross-spawning of CAPA investigations (`QCAP-`).
  - **Regulatory & Certification Inspection Hosting** [`QHST-`]: Specialized inspection host command center for FDA (QSIT / 483 / EIR), ISO 13485 Notified Body, MDSAP, and customer audits. Tracks inspection types, inspecting agencies/bodies, lead inspector credentials, facility locations, hosting rooms / virtual bridges, company host liaisons, designated scribes, inspection status lifecycle (`announced_prep`, `on_site_active`, `daily_wrap_up`, `exit_interview`, `post_audit_response`, `closed`), Form 483 issuance flags, agency report references, structured Front/Back Room request queues, and timestamped live inspection notes.
  - **Audit Action Tracker**: Cross-audit compliance workbench monitoring open findings, CAPA escalations, remediation response milestones, and overdue SLAs across 4 aging tiers (`0-30`, `31-60`, `61-90`, `>90 days`) with status badges and CSV export.
  - **Inspection War Room Command Center**: Real-time operational hosting interface featuring Front Room / Back Room live request dispatching (`war_room_requests`), document staging tracking, SME runner assignments, and scribe audit logs.

- **12.13 Customer Complaint Handling**:
  - **Customer Complaint Intake & Triage** [`QCMP-`]: FDA 21 CFR § 820.198, ISO 13485:2016 Clause 8.2.2, and ISO 10002 compliant customer allegation logging across intake channels (`phone`, `email`, `web_portal`, `sales_rep`, `service_tech`, `distributor`, `regulatory_agency`, `other`). Tracks customer link (`core.Party`), sales orders (`scm.SalesOrder`), return material authorizations (`scm.ReturnAuthorization`), product/lot/serial data, patient involvement, adverse event screening, severity triage (`critical_safety`, `major_malfunction`, `minor_cosmetic`, `service_inconvenience`, `unspecified`), validity determination (`pending_triage`, `valid_complaint`, `invalid_allegation`, `commercial_inquiry`), regulatory reportability classification (`undetermined`, `reportable_event`, `non_reportable`, `exempt`), sample return tracking, non-reportable justification mandate, formal closure letter dispatch, and multi-tenant isolation.
  - **Complaint Technical Investigations & Root Cause Analysis** [`QCIN-`]: Technical problem-solving investigations verifying whether non-conformances occurred. Tracks DHR (Device History Record) batch manufacturing reviews, physical sample examinations, laboratory analytical methods (`visual_microscopy`, `dimensional_metrology`, `mechanical_stress`, `electrical_functional`, `chemical_spectroscopy`, `software_code_audit`, `historical_data_review`, `other`), clinical Health Hazard Evaluations (HHE), ISO 14971 residual risk escalation check (`risk_exceeds_threshold`), Ishikawa/5-Whys root cause categories (`component_defect`, `assembly_workmanship`, `process_deviation`, `design_flaw`, `software_bug`, `packaging_barrier`, `transit_damage`, `user_error_misuse`, `unconfirmed_no_defect`, `other`), direct cross-module CAPA (`QCAP-`) and NCR (`QNCR-`) escalations, and formal QA approval workflows.
  - **Regulatory Vigilance Reporting & MDR** [`QRPT-`]: Mandatory adverse event vigilance reporting satisfying FDA 21 CFR Part 803 (Medical Device Reporting / MedWatch 3500A), EU MDR Article 87 (Manufacturer Incident Report / MIR), Health Canada, PMDA, and TGA regulations. Governs regulatory agency targets, adverse event classification (`death`, `serious_injury`, `malfunction_death_injury_potential`, `malfunction_recurrent`, `use_error_harm`), statutory urgency timeline clocks (`5_day_remedial`, `10_day_death_deterioration`, `15_day_serious_incident`, `30_day_standard_mdr`), dynamic countdown badges (`urgency_badge_css` with critical <=3 day warning), XML gateway transmission tracking, agency case file numbers, acknowledgement receipt capture, and statutory due date enforcement.
  - **Field Actions, Recalls & Safety Alerts** [`QFMA-`]: 21 CFR Part 7 and Part 806 compliant market correction and removal governance across action types (`recall_removal`, `fsca_safety_notice`, `field_correction_rework`, `safety_advisory_alert`, `market_withdrawal`), FDA recall classes (`class_i_critical`, `class_ii_moderate`, `class_iii_minor`, `fsca_safety_alert`, `not_classified`), Field Safety Notice (FSN) document linkages (`ControlledDocument`), affected lot scope, consignee notification dispatch tracking, response rate monitoring, unit quarantine/recovery reconciliation progress tracking, regulatory recall numbers, and formal termination justification.
  - **Complaint Intelligence & Trending Command Center**: Post-market surveillance executive dashboard (`complaint_trending_dashboard`) tracking YTD complaints, active investigations, statutory regulatory clocks, active field recalls, average cycle time (days to close), Pareto defect category distributions, severity distribution charts, and recall reconciliation recovery progress.

---

## App Layout & Architecture

Backend layers follow the mandatory NavERP package structure (`models/`, `forms/`, `views/`, `urls/`):

```
apps/quality/
  models/
    _base.py                                  <- TenantOwned, TenantNumbered abstract base models
    DocumentControl/                          <- Sub-module 12.1 models
      ControlledDocuments.py                  <- ControlledDocument [QDOC-]
      DocumentChangeOrders.py                 <- DocumentChangeOrder [QDCR-]
      ElectronicSignatures.py                 <- ElectronicSignatureRecord [QSIG-]
      DocumentAcknowledgments.py              <- DocumentAcknowledgment [QACK-]
    DesignControls/                           <- Sub-module 12.2 models
      DesignProjects.py                       <- DesignProject [QDPL-]
      DesignInputs.py                         <- DesignInput [QINP-]
      DesignReviews.py                        <- DesignReview [QREV-]
      DesignVerifications.py                  <- DesignVerification [QVER-]
    RiskManagement/                           <- Sub-module 12.3 models
      RiskManagementPlans.py                  <- RiskManagementPlan [QRMP-]
      RiskAssessments.py                      <- RiskAssessment [QRSK-]
      RiskControlMeasures.py                  <- RiskControlMeasure [QRCM-]
      RiskReviewRecords.py                    <- RiskReviewRecord [QRMR-]
    CapaManagement/                           <- Sub-module 12.4 models
      CapaInvestigations.py                   <- CapaInvestigation [QCAP-]
      RootCauseAnalyses.py                    <- RootCauseAnalysis [QRCA-]
      CapaActions.py                          <- CapaAction [QACT-]
      CapaEffectivenessReviews.py             <- CapaEffectivenessReview [QEFF-]
    NonConformance/                           <- Sub-module 12.5 models
      NonConformanceReports.py                <- NonConformanceReport [QNCR-]
      QuarantineContainments.py               <- QuarantineContainment [QHLD-]
      MrbDispositions.py                      <- MrbDisposition [QMRB-]
      ProcessDeviations.py                    <- ProcessDeviation [QDEV-]
    SupplierQuality/                          <- Sub-module 12.6 models
      SupplierQualificationAudits.py          <- SupplierQualificationAudit [QSQA-]
      SupplierQualityScorecards.py            <- SupplierQualityScorecard [QSSC-]
      SupplierCorrectiveActions.py            <- SupplierCorrectiveAction [QSCA-]
      SupplierChangeNotifications.py          <- SupplierChangeNotification [QSCN-]
    IncomingQuality/                          <- Sub-module 12.7 models
      IncomingInspectionPlans.py              <- IncomingInspectionPlan [QIIP-]
      IncomingInspectionLots.py               <- IncomingInspectionLot [QIIL-]
      CertificatesOfAnalysis.py               <- CertificateOfAnalysis [QCOA-]
      QualityReturnAuthorizations.py          <- QualityReturnAuthorization [QRMA-]
    InProcessQuality/                         <- Sub-module 12.8 models
      InProcessInspections.py                 <- InProcessInspection [QIPQ-]
      FirstArticleInspections.py              <- FirstArticleInspection [QFAI-]
      ProcessParameterLogs.py                 <- ProcessParameterLog [QPAR-]
      LayeredProcessAudits.py                 <- LayeredProcessAudit [QLPA-]
    FinalQuality/                             <- Sub-module 12.9 models
      FinalInspectionLots.py                  <- FinalInspectionLot [QFQC-]
      CertificatesOfConformance.py            <- CertificateOfConformance [QCOC-]
      PackagingLabelVerifications.py          <- PackagingLabelVerification [QPKG-]
      QualityReleaseAuthorizations.py         <- QualityReleaseAuthorization [QREL-]
    CalibrationAnalysis/                      <- Sub-module 12.10 models
      CalibrationGages.py                     <- CalibrationGage [QGAG-]
      CalibrationRecords.py                   <- CalibrationRecord [QCAL-]
      OutOfToleranceInvestigations.py         <- OutOfToleranceInvestigation [QOOT-]
      MeasurementSystemAnalyses.py            <- MeasurementSystemAnalysis [QMSA-]
    AuditManagement/                          <- Sub-module 12.11 models
      AuditPrograms.py                        <- AuditProgram [QPRG-]
      QualityAudits.py                        <- QualityAudit [QAUD-]
      AuditFindings.py                        <- AuditFinding [QFND-]
      RegulatoryInspections.py                <- RegulatoryInspectionHost [QHST-]
    CustomerComplaints/                       <- Sub-module 12.13 models
      CustomerComplaints.py                   <- CustomerComplaint [QCMP-]
      ComplaintInvestigations.py              <- ComplaintInvestigation [QCIN-]
      RegulatoryReports.py                    <- RegulatoryReport [QRPT-]
      FieldActions.py                         <- FieldAction [QFMA-]
    __init__.py                               <- Re-exports all models
  forms/
    _common.py                                <- Base QualityModelForm with tenant injection & clean helpers
    DocumentControl/                          <- Sub-module 12.1 forms
      ControlledDocuments.py                  <- ControlledDocumentForm, ControlledDocumentRevisionForm
      DocumentChangeOrders.py                 <- DocumentChangeOrderForm, DocumentChangeOrderReviewForm, CCBDecisionForm
      ElectronicSignatures.py                 <- ElectronicSignatureForm (21 CFR Part 11 dual-credential check)
      DocumentAcknowledgments.py              <- DocumentAcknowledgmentForm
    DesignControls/                           <- Sub-module 12.2 forms
      DesignProjects.py                       <- DesignProjectForm
      DesignInputs.py                         <- DesignInputForm (with DHF lock check & passing V&V guard)
      DesignReviews.py                        <- DesignReviewForm (with 21 CFR § 820.30(e) independent reviewer check)
      DesignVerifications.py                  <- DesignVerificationForm (with sample size & criteria validation)
    RiskManagement/                           <- Sub-module 12.3 forms
      RiskManagementPlans.py                  <- RiskManagementPlanForm
      RiskAssessments.py                      <- RiskAssessmentForm (with ISO 14971 safety gate & ALARP checks)
      RiskControlMeasures.py                  <- RiskControlMeasureForm (with objective verification evidence guards)
      RiskReviewRecords.py                    <- RiskReviewRecordForm (with restricted draft/under_review choices)
    CapaManagement/                           <- Sub-module 12.4 forms
      CapaInvestigations.py                   <- CapaInvestigationForm (with target date and status guards)
      RootCauseAnalyses.py                    <- RootCauseAnalysisForm (with parent CAPA immutability check)
      CapaActions.py                          <- CapaActionForm (with cross-CAPA root cause verification)
      CapaEffectivenessReviews.py             <- CapaEffectivenessReviewForm (with recurrence safety invariant)
    NonConformance/                           <- Sub-module 12.5 forms
      NonConformanceReports.py                <- NonConformanceReportForm
      QuarantineContainments.py               <- QuarantineContainmentForm
      MrbDispositions.py                      <- MrbDispositionForm
      ProcessDeviations.py                    <- ProcessDeviationForm
    SupplierQuality/                          <- Sub-module 12.6 forms
      SupplierQualificationAudits.py          <- SupplierQualificationAuditForm
      SupplierQualityScorecards.py            <- SupplierQualityScorecardForm
      SupplierCorrectiveActions.py            <- SupplierCorrectiveActionForm
      SupplierChangeNotifications.py          <- SupplierChangeNotificationForm
    IncomingQuality/                          <- Sub-module 12.7 forms
      IncomingInspectionPlans.py              <- IncomingInspectionPlanForm
      IncomingInspectionLots.py               <- IncomingInspectionLotForm
      CertificatesOfAnalysis.py               <- CertificateOfAnalysisForm
      QualityReturnAuthorizations.py          <- QualityReturnAuthorizationForm
    InProcessQuality/                         <- Sub-module 12.8 forms
      InProcessInspections.py                 <- InProcessInspectionForm
      FirstArticleInspections.py              <- FirstArticleInspectionForm
      ProcessParameterLogs.py                 <- ProcessParameterLogForm
      LayeredProcessAudits.py                 <- LayeredProcessAuditForm
    FinalQuality/                             <- Sub-module 12.9 forms
      FinalInspectionLots.py                  <- FinalInspectionLotForm
      CertificatesOfConformance.py            <- CertificateOfConformanceForm
      PackagingLabelVerifications.py          <- PackagingLabelVerificationForm
      QualityReleaseAuthorizations.py         <- QualityReleaseAuthorizationForm
    CalibrationAnalysis/                      <- Sub-module 12.10 forms
      CalibrationGages.py                     <- CalibrationGageForm
      CalibrationRecords.py                   <- CalibrationRecordForm
      OutOfToleranceInvestigations.py         <- OutOfToleranceInvestigationForm
      MeasurementSystemAnalyses.py            <- MeasurementSystemAnalysisForm
    AuditManagement/                          <- Sub-module 12.11 forms
      AuditPrograms.py                        <- AuditProgramForm, AuditProgramApprovalForm
      QualityAudits.py                        <- QualityAuditForm, QualityAuditScoreForm
      AuditFindings.py                        <- AuditFindingForm, AuditFindingResponseForm, AuditFindingVerifyForm
      RegulatoryInspections.py                <- RegulatoryInspectionHostForm, RegulatoryInspectionLogEntryForm
    CustomerComplaints/                       <- Sub-module 12.13 forms
      CustomerComplaints.py                   <- CustomerComplaintForm, ComplaintTriageForm
      ComplaintInvestigations.py              <- ComplaintInvestigationForm
      RegulatoryReports.py                    <- RegulatoryReportForm
      FieldActions.py                         <- FieldActionForm
    __init__.py                               <- Re-exports all forms
  views/
    _common.py                                <- Base view helpers (quality_object, quality_scope, tenant_admin_required, write_audit_log)
    DocumentControl/                          <- Sub-module 12.1 views
      ControlledDocuments.py                  <- List, Detail, Create, Edit, Delete, Submit, Approve, Make Effective, Obsolete, Revise, Export, Vault
      DocumentChangeOrders.py                 <- List, Detail, Create, Edit, Delete, Submit, CCB Decision, Export
      ElectronicSignatures.py                 <- List, Detail, Verify, Sign Controlled Document, Export
      DocumentAcknowledgments.py              <- List, Detail, Create, Delete, Sign Acknowledgment, Export
    DesignControls/                           <- Sub-module 12.2 views
      DesignProjects.py                       <- List, Detail, Create, Edit, Delete, Advance Phase, Lock DHF, Export
      DesignInputs.py                         <- List, Detail, Create, Edit, Delete, Export
      DesignReviews.py                        <- List, Detail, Create, Edit, Delete, Approve Gate, Export
      DesignVerifications.py                  <- List, Detail, Create, Edit, Delete, Export
      TraceabilityMatrix.py                   <- Traceability Matrix, Matrix Export, DHF Dossier, DHF Export
    RiskManagement/                           <- Sub-module 12.3 views
      RiskManagementPlans.py                  <- List, Detail, Create, Edit, Delete, Activate, Archive, Export
      RiskAssessments.py                      <- List, Detail, Create, Edit, Delete, Export
      RiskControlMeasures.py                  <- List, Detail, Create, Edit, Delete, Verify Impl, Verify Eff, Export
      RiskReviewRecords.py                    <- List, Detail, Create, Edit, Delete, Approve, Export
      FmeaMatrix.py                           <- FMEA Matrix, Matrix Export, Risk Traceability Matrix, Traceability Export
    CapaManagement/                           <- Sub-module 12.4 views
      CapaInvestigations.py                   <- List, Detail, Create, Edit, Delete, Advance Status, Close, Export
      RootCauseAnalyses.py                    <- List, Detail, Create, Edit, Delete, Verify, Export
      CapaActions.py                          <- List, Detail, Create, Edit, Delete, Mark Completed, Verify, Export
      CapaEffectivenessReviews.py             <- List, Detail, Create, Edit, Delete, Sign Off, Export
      CapaTrackingBoard.py                    <- Kanban Tracking Board, Tracking Board Export
    NonConformance/                           <- Sub-module 12.5 views
      NonConformanceReports.py                <- List, Detail, Create, Edit, Delete, Advance Status, Export
      QuarantineContainments.py               <- List, Detail, Create, Edit, Delete, Release, Export
      MrbDispositions.py                      <- List, Detail, Create, Edit, Delete, Approve, Export
      ProcessDeviations.py                    <- List, Detail, Create, Edit, Delete, Authorize, Close, Export
      NcrAnalytics.py                         <- Analytics Dashboard, Cost Analysis, Export
    SupplierQuality/                          <- Sub-module 12.6 views
      SupplierQualificationAudits.py          <- List, Detail, Create, Edit, Delete, Approve, Export
      SupplierQualityScorecards.py            <- List, Detail, Create, Edit, Delete, Publish, Recalculate, Export
      SupplierCorrectiveActions.py            <- List, Detail, Create, Edit, Delete, Verify, Close, Export
      SupplierChangeNotifications.py          <- List, Detail, Create, Edit, Delete, Disposition, Export
      AvlDirectory.py                         <- Directory View, Export
    IncomingQuality/                          <- Sub-module 12.7 views
      IncomingInspectionPlans.py              <- List, Detail, Create, Edit, Delete, Export
      IncomingInspectionLots.py               <- List, Detail, Create, Edit, Delete, Record Decision, Export
      CertificatesOfAnalysis.py               <- List, Detail, Create, Edit, Delete, Verify, Export
      QualityReturnAuthorizations.py          <- List, Detail, Create, Edit, Delete, Dispatch, Export
      IqcSpcDashboard.py                      <- SPC Dashboard, Export
    InProcessQuality/                         <- Sub-module 12.8 views
      InProcessInspections.py                 <- List, Detail, Create, Edit, Delete, Export
      FirstArticleInspections.py              <- List, Detail, Create, Edit, Delete, Release, Export
      ProcessParameterLogs.py                 <- List, Detail, Create, Edit, Delete, Export
      LayeredProcessAudits.py                 <- List, Detail, Create, Edit, Delete, Export
      SpcAnalytics.py                         <- SPC Analytics Dashboard, Export
    FinalQuality/                             <- Sub-module 12.9 views
      FinalInspectionLots.py                  <- List, Detail, Create, Edit, Delete, Toggle Hold, Export
      CertificatesOfConformance.py            <- List, Detail, Create, Edit, Delete, Sign, Export
      PackagingLabelVerifications.py          <- List, Detail, Create, Edit, Delete, Export
      QualityReleaseAuthorizations.py         <- List, Detail, Create, Edit, Delete, Toggle Hold, Export
      OqcHoldBoard.py                         <- OQC Hold & Release Board
    CalibrationAnalysis/                      <- Sub-module 12.10 views
      CalibrationGages.py                     <- List, Detail, Create, Edit, Delete, Export
      CalibrationRecords.py                   <- List, Detail, Create, Edit, Delete, Export
      OutOfToleranceInvestigations.py         <- List, Detail, Create, Edit, Delete, Export
      MeasurementSystemAnalyses.py            <- List, Detail, Create, Edit, Delete, Export
      CalibrationVendors.py                   <- Calibration Vendor Directory
    AuditManagement/                          <- Sub-module 12.11 views
      AuditPrograms.py                        <- List, Detail, Create, Edit, Delete, Approve, Export
      QualityAudits.py                        <- List, Detail, Create, Edit, Delete, Advance Status, Export
      AuditFindings.py                        <- List, Detail, Create, Edit, Delete, Submit Response, Verify/Close, Create CAPA, Export
      RegulatoryInspections.py                <- List, Detail, Create, Edit, Delete, Advance Status, Add Log, Export
      AuditActionTracker.py                   <- Audit Action Tracker, Tracker Export
      AuditWarRoom.py                         <- Inspection War Room Command Center, War Room Export
    CustomerComplaints/                       <- Sub-module 12.13 views
      CustomerComplaints.py                   <- List, Detail, Create, Edit, Delete, Triage, Close, Export
      ComplaintInvestigations.py              <- List, Detail, Create, Edit, Delete, Complete, Export
      RegulatoryReports.py                    <- List, Detail, Create, Edit, Delete, Submit, Acknowledge, Export
      FieldActions.py                         <- List, Detail, Create, Edit, Delete, Close, Export
      ComplaintTrendingDashboard.py           <- Quality Executive Complaint Intelligence & Post-Market Surveillance Dashboard
    __init__.py                               <- Re-exports all views
  urls/
    DocumentControl/                          <- Sub-module 12.1 URLs
      ControlledDocuments.py
      DocumentChangeOrders.py
      ElectronicSignatures.py
      DocumentAcknowledgments.py
    DesignControls/                           <- Sub-module 12.2 URLs
      DesignProjects.py
      DesignInputs.py
      DesignReviews.py
      DesignVerifications.py
      TraceabilityMatrix.py
    RiskManagement/                           <- Sub-module 12.3 URLs
      RiskManagementPlans.py
      RiskAssessments.py
      RiskControlMeasures.py
      RiskReviewRecords.py
      FmeaMatrix.py
    CapaManagement/                           <- Sub-module 12.4 URLs
      CapaInvestigations.py
      RootCauseAnalyses.py
      CapaActions.py
      CapaEffectivenessReviews.py
      CapaTrackingBoard.py
    NonConformance/                           <- Sub-module 12.5 URLs
      NonConformanceReports.py
      QuarantineContainments.py
      MrbDispositions.py
      ProcessDeviations.py
      NcrAnalytics.py
    SupplierQuality/                          <- Sub-module 12.6 URLs
      SupplierQualificationAudits.py
      SupplierQualityScorecards.py
      SupplierCorrectiveActions.py
      SupplierChangeNotifications.py
      AvlDirectory.py
    IncomingQuality/                          <- Sub-module 12.7 URLs
      IncomingInspectionPlans.py
      IncomingInspectionLots.py
      CertificatesOfAnalysis.py
      QualityReturnAuthorizations.py
      IqcSpcDashboard.py
    InProcessQuality/                         <- Sub-module 12.8 URLs
      InProcessInspections.py
      FirstArticleInspections.py
      ProcessParameterLogs.py
      LayeredProcessAudits.py
      SpcAnalytics.py
    FinalQuality/                             <- Sub-module 12.9 URLs
      FinalInspectionLots.py
      CertificatesOfConformance.py
      PackagingLabelVerifications.py
      QualityReleaseAuthorizations.py
      OqcHoldBoard.py
    CalibrationAnalysis/                      <- Sub-module 12.10 URLs
      CalibrationGages.py
      CalibrationRecords.py
      OutOfToleranceInvestigations.py
      MeasurementSystemAnalyses.py
      CalibrationVendors.py
    AuditManagement/                          <- Sub-module 12.11 URLs
      AuditPrograms.py
      QualityAudits.py
      AuditFindings.py
      RegulatoryInspections.py
      AuditActionTracker.py
      AuditWarRoom.py
    CustomerComplaints/                       <- Sub-module 12.13 URLs
      CustomerComplaints.py
      ComplaintInvestigations.py
      RegulatoryReports.py
      FieldActions.py
      ComplaintTrendingDashboard.py
    __init__.py                               <- Re-exports all URL patterns
  admin.py                                    <- Django admin registrations for all models
  management/commands/
    seed_quality.py                           <- Idempotent QMS seeder (12.1 through 12.13)
  tests/                                      <- Pytest test suite (100% green, 2,001+ passing tests)
    conftest.py                               <- Shared 12.1 through 12.13 fixtures
    test_customercomplaints_models.py         <- Sub-module 12.13 model tests (6 tests)
    test_customercomplaints_forms.py          <- Sub-module 12.13 form tests (9 tests)
    test_customercomplaints_views.py          <- Sub-module 12.13 view tests (10 tests)
    test_customercomplaints_security.py       <- Sub-module 12.13 security tests (9 tests)
    test_auditmanagement_models.py           <- Sub-module 12.11 model tests (10 tests)
    test_auditmanagement_forms.py            <- Sub-module 12.11 form tests (13 tests)
    test_auditmanagement_views.py            <- Sub-module 12.11 view tests (16 tests)
    test_auditmanagement_security.py         <- Sub-module 12.11 security tests (12 tests)
    test_calibrationanalysis_models.py        <- Sub-module 12.10 model tests (44 tests)
    test_calibrationanalysis_forms.py         <- Sub-module 12.10 form tests (45 tests)
    test_calibrationanalysis_views.py         <- Sub-module 12.10 view tests (73 tests)
    test_calibrationanalysis_security.py      <- Sub-module 12.10 security tests (24 tests)
    test_finalquality_forms.py
    test_finalquality_views.py
    test_finalquality_security.py
    test_documentcontrol_models.py
    test_documentcontrol_forms.py
    test_documentcontrol_views.py
    test_documentcontrol_security.py
    test_designcontrols_models.py
    test_designcontrols_forms.py
    test_designcontrols_views.py
    test_designcontrols_security.py
    test_riskmanagement_models.py
    test_riskmanagement_forms.py
    test_riskmanagement_views.py
    test_riskmanagement_security.py
    test_capamanagement_models.py
    test_capamanagement_forms.py
    test_capamanagement_views.py
    test_capamanagement_security.py
    test_nonconformance_models.py
    test_nonconformance_forms.py
    test_nonconformance_views.py
    test_nonconformance_security.py
    test_supplierquality_models.py
    test_supplierquality_forms.py
    test_supplierquality_views.py
    test_supplierquality_security.py
    test_incomingquality_models.py
    test_incomingquality_forms.py
    test_incomingquality_views.py
    test_incomingquality_security.py
    test_inprocessquality_models.py
    test_inprocessquality_forms.py
    test_inprocessquality_views.py
    test_inprocessquality_security.py
```

---

## Models & Entities

### Sub-module 12.1 Entities

#### 1. `ControlledDocument` (Prefix: `QDOC-`)
- **Table:** `quality_controlled_document`
- **Key Fields:** `number`, `title`, `document_type` (`sop`, `work_instruction`, `policy`, `specification`, `protocol`, `manual`, `form`, `other`), `department` (`core.OrgUnit`), `owner` (`accounts.User`), `revision` (e.g. `"1.0"`), `is_latest_revision`, `lifecycle_state` (`draft`, `in_review`, `approved`, `effective`, `superseded`, `obsolete`, `archived`), `effective_date`, `next_review_date`, `review_interval_months`, `supersedes`, `superseded_by`, `classification` (`public`, `internal`, `confidential`, `restricted`), `file`, `is_template`.
- **Properties & Methods:** `is_locked`, `is_effective`, `is_under_review`, `is_overdue_review`, `watermark_text`, `make_effective()`, `supersede()`, `mark_obsolete()`.

#### 2. `DocumentChangeOrder` (Prefix: `QDCR-`)
- **Table:** `quality_change_order`
- **Key Fields:** `number`, `title`, `document` (`ControlledDocument`), `change_type` (`new_document`, `revision`, `obsoletion`, `emergency`, `administrative`), `priority` (`low`, `medium`, `high`, `critical`, `emergency`), `status` (`draft`, `submitted`, `in_assessment`, `ccb_review`, `approved`, `rejected`, `implemented`, `cancelled`), `requested_by` (`accounts.User`), `reason_for_change`, `change_description`, `regulatory_impact`, `ccb_decision` (`approved`, `rejected`, `more_info_required`, `waived`), `ccb_decision_date`, `ccb_decision_by` (`accounts.User`), `closure_notes`.

#### 3. `ElectronicSignatureRecord` (Prefix: `QSIG-`)
- **Table:** `quality_e_signature`
- **Key Fields:** `number`, `document` (`ControlledDocument`), `change_order` (`DocumentChangeOrder`), `signer` (`accounts.User`), `signer_name`, `signer_title`, `signature_meaning` (`authored`, `reviewed`, `quality_approval`, `management_approval`, `ccb_approval`, `acknowledgment`), `signed_at`, `verification_hash` (HMAC-SHA256), `ip_address`, `document_revision`, `comments`.

#### 4. `DocumentAcknowledgment` (Prefix: `QACK-`)
- **Table:** `quality_doc_acknowledgment`
- **Key Fields:** `number`, `document` (`ControlledDocument`), `document_revision`, `user` (`accounts.User`), `employee` (`hrm.EmployeeProfile`), `status` (`pending`, `acknowledged`, `waived`), `due_date`, `acknowledged_at`, `signature_record` (`ElectronicSignatureRecord`), `notes`.

---

### Sub-module 12.2 Entities

#### 5. `DesignProject` (Prefix: `QDPL-`)
- **Table:** `quality_design_project`
- **Key Fields:** `number`, `title`, `device_name`, `device_class` (`class_i`, `class_ii`, `class_iii`), `regulatory_pathway` (`510k`, `pma`, `de_novo`, `ce_mark`, `exempt`), `intended_use`, `current_phase` (`planning`, `input`, `output_verification`, `validation`, `commercial_closure`, `closed`), `status` (`draft`, `active`, `on_hold`, `completed`, `cancelled`), `project_lead` (`accounts.User`), `quality_lead` (`accounts.User`), `department` (`core.OrgUnit`), `target_completion_date`, `actual_completion_date`, `dhf_location`, `dhf_locked`, `description`.
- **Properties & Methods:** `is_locked`, `is_active`, `phase_progress_pct`, `status_css`, `phase_css`, `device_class_css`.
- **Compound Index:** `idx_qdpl_ten_created` on `(tenant, -created_at)`.

#### 6. `DesignInput` (Prefix: `QINP-`)
- **Table:** `quality_design_input`
- **Key Fields:** `number`, `project` (`DesignProject`), `identifier` (e.g. `"UN-001"`, `"SRS-102"`), `title`, `input_type` (`user_need`, `functional`, `performance`, `interface`, `safety`, `regulatory`, `software`, `hardware`, `usability`, `risk_control`, `packaging`), `priority` (`low`, `medium`, `high`, `critical`), `status` (`draft`, `approved`, `verified`, `deprecated`), `owner` (`accounts.User`), `user_need_parent` (`self`, self-referential FK), `controlled_document` (`ControlledDocument`), `acceptance_criteria`, `description`, `rationales`.
- **Properties & Methods:** `is_verified` (optimized with prefetch cache inspection), `status_css`, `priority_css`, `input_type_css`.

#### 7. `DesignReview` (Prefix: `QREV-`)
- **Table:** `quality_design_review`
- **Key Fields:** `number`, `project` (`DesignProject`), `title`, `review_stage` (`planning_gate`, `inputs_gate`, `outputs_gate`, `verification_gate`, `validation_gate`, `transfer_gate`, `post_market_gate`), `review_date`, `status` (`scheduled`, `in_progress`, `approved`, `conditional`, `rejected`), `lead_reviewer` (`accounts.User`), `independent_reviewer` (`accounts.User`, 21 CFR § 820.30(e)), `electronic_signature` (`ElectronicSignatureRecord`), `conclusions`, `action_items`, `action_items_resolved`, `recommendations`.
- **Properties & Methods:** `is_cleared`, `stage_css`, `status_css`.

#### 8. `DesignVerification` (Prefix: `QVER-`)
- **Table:** `quality_design_verification`
- **Key Fields:** `number`, `project` (`DesignProject`), `primary_input` (`DesignInput`), `title`, `activity_type` (`design_verification`, `design_validation`), `status` (`draft`, `in_progress`, `passed`, `failed`, `cancelled`), `test_method` (`lab_testing`, `inspection`, `analysis`, `clinical_eval`, `usability_study`, `simulation`), `sample_size`, `acceptance_criteria`, `results_summary`, `pass_fail_result` (`pending`, `pass`, `fail`, `inconclusive`), `executed_by` (`accounts.User`), `execution_date`, `protocol_document` (`ControlledDocument`), `report_document` (`ControlledDocument`), `notes`.
- **Properties & Methods:** `is_passed`, `status_css`, `result_css`, `activity_type_css`.

### Sub-module 12.3 Entities

#### 9. `RiskManagementPlan` (Prefix: `QRMP-`)
- **Table:** `quality_risk_management_plan`
- **Key Fields:** `number`, `title`, `device_name`, `device_classification` (`class_i`, `class_ii_a`, `class_ii_b`, `class_iii`), `design_project` (`DesignProject`), `lead_risk_manager` (`accounts.User`), `department` (`core.OrgUnit`), `status` (`draft`, `active`, `periodic_review`, `archived`), `plan_version`, `matrix_dimension` (`3x3`, `4x4`, `5x5`), `periodic_review_frequency_months`, `next_review_due_date`, `scope_description`, `risk_acceptability_policy`, `overall_benefit_risk_summary`, `overall_residual_risk_acceptable`, `approved_signature` (`ElectronicSignatureRecord`), `approval_date`.
- **Properties & Methods:** `status_css`, `device_class_css`, `assessments_count`, `unmitigated_risks_count`, `is_review_overdue`.
- **Indexes:** `idx_qrmp_ten_status` on `(tenant, status)`, `idx_qrmp_ten_created` on `(tenant, -created_at)`.

#### 10. `RiskAssessment` (Prefix: `QRSK-`)
- **Table:** `quality_risk_assessment`
- **Key Fields:** `number`, `plan` (`RiskManagementPlan`), `hazard_category` (`biological`, `chemical`, `electrical`, `mechanical`, `thermal`, `radiation`, `software`, `usability`, `operational`, `information_security`), `hazard_description`, `sequence_of_events`, `hazardous_situation`, `potential_harm`, `affected_user` (`patient`, `operator`, `service_personnel`, `third_party`), `analysis_type` (`dfmea`, `pfmea`, `ufmea`, `afmea`), `failure_mode`, `cause_of_failure`, `effect_of_failure`, `initial_severity` (1-5), `initial_probability` (1-5), `initial_detectability` (1-5), `initial_rpn`, `initial_risk_level` (`broadly_acceptable`, `alarp`, `unacceptable`), `residual_severity`, `residual_probability`, `residual_detectability`, `residual_rpn`, `residual_risk_level`, `residual_risk_acceptable`, `benefit_risk_justification`, `bra_required`, `lifecycle_status` (`identified`, `analyzed`, `mitigated`, `verified`, `accepted`, `closed`), `design_input` (`DesignInput`), `created_by` (`accounts.User`).
- **Properties & Methods:** `calculate_level(severity, probability)`, `initial_risk_level_badge`, `residual_risk_level_badge`, `lifecycle_status_badge`, `analysis_type_badge`.
- **Safety Gate Invariant:** `save()` auto-enforces `residual_risk_acceptable = False` if `residual_risk_level == "unacceptable"`, and sets `bra_required = True` when in ALARP zone.
- **Indexes:** `idx_qrsk_ten_plan_type`, `idx_qrsk_ten_init_level`, `idx_qrsk_ten_res_level`, `idx_qrsk_ten_status`, `idx_qrsk_ten_hazard_cat`, `idx_qrsk_ten_created`.

#### 11. `RiskControlMeasure` (Prefix: `QRCM-`)
- **Table:** `quality_risk_control_measure`
- **Key Fields:** `number`, `risk_assessment` (`RiskAssessment`), `title`, `description`, `control_hierarchy` (`inherent_safety`, `protective_measure`, `information_for_safety`), `assigned_to` (`accounts.User`), `target_completion_date`, `implementation_verified`, `implementation_date`, `effectiveness_verified`, `effectiveness_date`, `status` (`proposed`, `in_progress`, `implemented`, `verified`, `rejected`), `verification_notes`, `design_input` (`DesignInput`), `design_verification` (`DesignVerification`), `controlled_document` (`ControlledDocument`), `introduces_new_hazard`, `new_hazard_details`, `created_by` (`accounts.User`).
- **Properties & Methods:** `is_fully_verified` (both impl and eff verified), `control_hierarchy_badge`, `status_badge`.
- **Indexes:** `idx_qrcm_ten_asmt`, `idx_qrcm_ten_hier`, `idx_qrcm_ten_status`, `idx_qrcm_ten_created`.

#### 12. `RiskReviewRecord` (Prefix: `QRMR-`)
- **Table:** `quality_risk_review_record`
- **Key Fields:** `number`, `plan` (`RiskManagementPlan`), `review_title`, `review_type` (`initial_rmr`, `periodic_review`, `design_change_review`, `post_market_surveillance`, `complaint_trend_trigger`, `ncr_capa_trigger`), `review_date`, `period_start_date`, `period_end_date`, `lead_reviewer` (`accounts.User`), `status` (`draft`, `under_review`, `approved`, `rejected`), `findings_summary`, `post_market_data_reviewed`, `risk_benefit_conclusion`, `overall_residual_risk_acceptable`, `approved_signature` (`ElectronicSignatureRecord`), `approval_date`.
- **Properties & Methods:** `status_badge`, `review_type_badge`.
- **Indexes:** `idx_qrmr_ten_plan_type`, `idx_qrmr_ten_status`, `idx_qrmr_ten_created`.

---

### Sub-module 12.4 Entities

#### 13. `CapaInvestigation` (Prefix: `QCAP-`)
- **Table:** `quality_capa_investigation`
- **Key Fields:** `number`, `title`, `action_type` (`corrective`, `preventive`), `source_type` (`customer_complaint`, `internal_audit`, `ncr`, `management_review`, `supplier_issue`, `trend_analysis`, `regulatory_finding`), `risk_priority` (`low`, `medium`, `high`, `critical`), `status` (`draft`, `under_investigation`, `rca_in_progress`, `action_pending`, `effectiveness_review`, `closed`, `voided`), `department` (`core.OrgUnit`), `lead_investigator` (`accounts.User`), `quality_owner` (`accounts.User`), `issue_summary`, `containment_actions`, `containment_verified`, `containment_verified_by` (`accounts.User`), `containment_verified_at`, `target_closure_date`, `closed_at`, `closure_approved_by` (`accounts.User`), `closure_summary`, `formal_closure_signature` (`ElectronicSignatureRecord`), `design_project` (`DesignProject`), `risk_assessment` (`RiskAssessment`), `is_escalated`, `escalation_reason`.
- **Properties & Methods:** `action_type_badge`, `source_type_badge`, `risk_priority_badge`, `status_badge`, `days_open`, `is_overdue`, `actions_count` (with `__dict__` cache check), `pending_actions_count` (with `__dict__` cache check), `rca_count`.
- **Indexes:** `idx_qcap_ten_status`, `idx_qcap_ten_act_type`, `idx_qcap_ten_dept`, `idx_qcap_ten_src_type`, `idx_qcap_ten_risk_pri`, `idx_qcap_ten_tgt_date`, `idx_qcap_ten_created`.

#### 14. `RootCauseAnalysis` (Prefix: `QRCA-`)
- **Table:** `quality_root_cause_analysis`
- **Key Fields:** `number`, `capa` (`CapaInvestigation`), `rca_method` (`five_whys`, `fishbone_ishikawa`, `fault_tree`, `fmea_deduction`, `is_is_not`, `barrier_analysis`), `problem_statement`, `why_1`, `why_2`, `why_3`, `why_4`, `why_5`, `root_cause_summary`, `root_cause_category` (`manpower`, `machine`, `material`, `method`, `measurement`, `environment`), `escape_point`, `lead_investigator` (`accounts.User`), `status` (`in_progress`, `verified`, `rejected`), `verified_by` (`accounts.User`), `verified_date`, `verification_notes`.
- **Properties & Methods:** `rca_method_badge`, `root_cause_category_badge`, `status_badge`, `why_levels_count`, `is_verified`.
- **Indexes:** `idx_qrca_ten_capa_stat`, `idx_qrca_ten_method`, `idx_qrca_ten_cat`, `idx_qrca_ten_created`.

#### 15. `CapaAction` (Prefix: `QACT-`)
- **Table:** `quality_capa_action`
- **Key Fields:** `number`, `capa` (`CapaInvestigation`), `root_cause` (`RootCauseAnalysis`), `action_type` (`immediate_containment`, `corrective`, `preventive`), `title`, `description`, `assigned_to` (`accounts.User`), `department` (`core.OrgUnit`), `due_date`, `completion_date`, `status` (`pending`, `in_progress`, `implemented`, `verified`, `cancelled`), `implementation_notes`, `verified_by` (`accounts.User`), `verified_on`, `verification_evidence`, `controlled_document` (`ControlledDocument`), `change_order` (`DocumentChangeOrder`), `design_project` (`DesignProject`).
- **Properties & Methods:** `action_type_badge`, `status_badge`, `is_overdue`, `is_verified`.
- **Indexes:** `idx_qact_ten_capa_stat`, `idx_qact_ten_type`, `idx_qact_ten_dept`, `idx_qact_ten_due`, `idx_qact_ten_created`.

#### 16. `CapaEffectivenessReview` (Prefix: `QEFF-`)
- **Table:** `quality_capa_effectiveness_review`
- **Key Fields:** `number`, `capa` (`CapaInvestigation`), `review_criteria`, `verification_method` (`statistical_sampling`, `trend_analysis`, `process_audit`, `customer_feedback`, `repeat_incident_check`), `planned_review_date`, `actual_review_date`, `evaluator` (`accounts.User`), `status` (`scheduled`, `in_progress`, `completed`, `cancelled`), `outcome` (`pending`, `effective`, `partially_effective`, `ineffective`), `results_summary`, `recurrence_observed`, `recurrence_details`, `follow_up_capa_required`, `formal_signature` (`ElectronicSignatureRecord`).
- **Properties & Methods:** `verification_method_badge`, `status_badge`, `outcome_badge`, `is_effective`, `is_review_overdue`.
- **Indexes:** `idx_qeff_ten_capa_stat`, `idx_qeff_ten_method`, `idx_qeff_ten_outcome`, `idx_qeff_ten_planned`, `idx_qeff_ten_created`.

### Sub-module 12.6 Entities

#### 17. `SupplierQualificationAudit` (Prefix: `QSQA-`)
- **Table:** `quality_supplier_qualification_audit`
- **Key Fields:** `number`, `supplier` (`core.Party`), `assessment_type` (`initial_qualification`, `periodic_reaudit`, `for_cause`, `certification_review`, `quality_agreement_review`), `criticality_tier` (`critical`, `major`, `minor`, `indirect`), `audit_method` (`on_site`, `desktop_survey`, `third_party_iso`, `virtual`), `qualification_status` (`under_evaluation`, `approved`, `conditional`, `suspended`, `disqualified`), `audit_result` (`pending`, `passed`, `passed_with_capa`, `failed`, `exempt`), `score` (0-100), `audit_date`, `next_audit_due_date`, `lead_auditor` (`accounts.User`), `quality_agreement` (`ControlledDocument`), `dock_to_stock_eligible`, `requires_coa`, `skip_lot_allowed`, `critical_findings_count`, `major_findings_count`, `minor_findings_count`, `scope_of_authorization`, `findings_summary`.
- **Properties & Methods:** `status_css`, `tier_css`, `result_css`, `is_expired`, `is_audit_overdue`, `total_findings`.
- **Indexes:** `idx_qsqa_ten_status`, `idx_qsqa_ten_tier`, `idx_qsqa_ten_supplier`, `idx_qsqa_ten_next_due`, `idx_qsqa_ten_created`.

#### 18. `SupplierQualityScorecard` (Prefix: `QSSC-`)
- **Table:** `quality_supplier_scorecard`
- **Key Fields:** `number`, `supplier` (`core.Party`), `cadence` (`monthly`, `quarterly`, `semi_annual`, `annual`), `period_start`, `period_end`, `status` (`draft`, `published`, `archived`), `overall_score` (0-100), `grade` (`A`, `B`, `C`, `D`), `lot_acceptance_rate_score` (30% weight), `defect_ppm_score` (25% weight), `scar_responsiveness_score` (20% weight), `audit_compliance_score` (15% weight), `documentation_coa_score` (10% weight), `total_lots_received`, `lots_accepted`, `lots_rejected`, `total_units_received`, `defective_units_count`, `is_manual_override`, `override_justification`, `evaluated_by` (`accounts.User`), `executive_summary`.
- **Properties & Methods:** `status_css`, `grade_css`, `cadence_css`, `is_expired`, `is_action_required`, `calculate_composite_score()`, `determine_grade()`.
- **Indexes:** `idx_qssc_ten_supplier`, `idx_qssc_ten_status`, `idx_qssc_ten_grade`, `idx_qssc_ten_period`, `idx_qssc_ten_created`, `idx_qssc_ten_pend_created`.

#### 19. `SupplierCorrectiveAction` (Prefix: `QSCA-`)
- **Table:** `quality_supplier_corrective_action`
- **Key Fields:** `number`, `supplier` (`core.Party`), `title`, `problem_description`, `severity` (`critical`, `major`, `minor`), `status` (`issued`, `containment_acknowledged`, `rca_submitted`, `ca_plan_approved`, `implementation_verified`, `effectiveness_verified`, `closed`, `cancelled`), `issued_date`, `response_due_date`, `containment_required`, `containment_due_date`, `containment_actions`, `root_cause_category`, `vendor_root_cause_analysis`, `corrective_action_plan`, `preventive_action_plan`, `is_effective`, `effectiveness_review_notes`, `closed_at`, `purchase_order` (`scm.PurchaseOrder`), `non_conformance` (`scm.NonConformance`), `qualification_audit` (`SupplierQualificationAudit`), `internal_capa` (`CapaInvestigation`), `issued_by` (`accounts.User`), `verified_by` (`accounts.User`).
- **Properties & Methods:** `severity_css`, `status_css`, `category_css`, `is_overdue`, `days_open`.
- **Indexes:** `idx_qsca_ten_status`, `idx_qsca_ten_sev`, `idx_qsca_ten_supp`, `idx_qsca_ten_resp_due`, `idx_qsca_ten_created`.

#### 20. `SupplierChangeNotification` (Prefix: `QSCN-`)
- **Table:** `quality_supplier_change_notification`
- **Key Fields:** `number`, `supplier` (`core.Party`), `title`, `supplier_scn_number`, `change_category` (`material`, `process`, `facility_location`, `tooling`, `sub_tier_supplier`, `packaging_labeling`, `specification`, `test_method`, `software_firmware`, `other`), `risk_level` (`level_1_minor`, `level_2_moderate`, `level_3_major`), `status` (`submitted`, `initial_triage`, `technical_evaluation`, `sample_validation`, `qualification_pending`, `approved`, `rejected`, `withdrawn`), `disposition` (`pending`, `approved`, `approved_with_conditions`, `rejected`), `disposition_date`, `approved_by` (`accounts.User`), `proposed_effective_date`, `affects_form_fit_function`, `requires_requalification`, `requires_regulatory_filing`, `description`, `justification`, `impact_assessment_notes`, `design_project` (`DesignProject`), `requalification_audit` (`SupplierQualificationAudit`), `evaluated_by` (`accounts.User`).
- **Properties & Methods:** `category_css`, `risk_css`, `status_css`, `disposition_css`, `has_critical_impact`, `is_high_risk`.
- **Indexes:** `idx_qscn_ten_status`, `idx_qscn_ten_risk`, `idx_qscn_ten_cat`, `idx_qscn_ten_disp`, `idx_qscn_ten_supp`, `idx_qscn_ten_created`.

### Sub-module 12.7 Entities

#### 21. `IncomingInspectionPlan` (Prefix: `QIIP-`)
- **Table:** `quality_incoming_inspection_plan`
- **Key Fields:** `number`, `title`, `item_code`, `item_name`, `revision`, `supplier` (`core.Party`), `sampling_standard` (`ansi_asq_z14`, `iso_2859_1`, `iso_3951_1`, `c_zero`), `inspection_level` (`level_1`, `level_2`, `level_3`, `s1`, `s2`, `s3`, `s4`), `inspection_severity` (`normal`, `tightened`, `reduced`), `inspection_frequency` (`every_lot`, `skip_lot`, `first_article`, `dock_to_stock`), `skip_lot_interval`, `aql_critical` (Decimal), `aql_major` (Decimal), `aql_minor` (Decimal), `requires_coa`, `requires_coc`, `status` (`draft`, `active`, `under_review`, `deprecated`), `sop_document` (`ControlledDocument`), `assigned_team` (`core.OrgUnit`), `notes`, `characteristics_json`.
- **Properties & Methods:** `status_css`, `severity_css`, `frequency_css`, `sampling_standard_badge`, `is_active`, `characteristics_count`.
- **Compound Indexes:** `idx_qiip_ten_item_supp`, `idx_qiip_ten_status`, `idx_qiip_ten_created`.

#### 22. `IncomingInspectionLot` (Prefix: `QIIL-`)
- **Table:** `quality_incoming_inspection_lot`
- **Key Fields:** `number`, `inspection_plan` (`IncomingInspectionPlan`), `item_code`, `item_name`, `supplier` (`core.Party`), `purchase_order` (`scm.PurchaseOrder`), `lot_number`, `lot_quantity` (Decimal), `sample_size` (int), `sample_code_letter`, `inspected_quantity` (Decimal), `accepted_quantity` (Decimal), `rejected_quantity` (Decimal), `quarantine_quantity` (Decimal), `critical_defects` (int), `major_defects` (int), `minor_defects` (int), `stage` (`pending_receipt`, `in_inspection`, `in_testing`, `under_review`, `completed`, `quarantined`, `cancelled`), `usage_decision` (`pending`, `accepted`, `accepted_with_deviation`, `rework`, `scrap`, `quarantine`, `return_to_vendor`, `skip_lot_passed`), `decision_date`, `decision_notes`, `decided_by` (`accounts.User`), `inspector` (`accounts.User`), `linked_ncr` (`NonConformanceReport`), `linked_deviation` (`ProcessDeviation`), `linked_containment` (`QuarantineContainment`), `linked_scar` (`SupplierCorrectiveAction`), `consecutive_accepted_lots` (int), `spc_mean` (Decimal), `spc_std_dev` (Decimal), `spc_cp` (Decimal), `spc_cpk` (Decimal), `spc_out_of_control` (bool), `measurements_json`, `notes`.
- **Properties & Methods:** `stage_css`, `decision_css`, `is_decided`, `is_accepted`, `is_rejected`, `total_defects`, `defect_rate_pct`, `calculate_sample_size()`.
- **Compound Indexes:** `idx_qiil_ten_stage`, `idx_qiil_ten_decision`, `idx_qiil_ten_supp_lot`, `idx_qiil_ten_plan`, `idx_qiil_ten_created`.

#### 23. `CertificateOfAnalysis` (Prefix: `QCOA-`)
- **Table:** `quality_certificate_of_analysis`
- **Key Fields:** `number`, `inspection_lot` (`IncomingInspectionLot`), `supplier` (`core.Party`), `item_code`, `lot_number`, `vendor_coa_number`, `manufacture_date`, `expiration_date`, `verification_status` (`pending_review`, `accepted`, `rejected`, `conditional`), `verified_by` (`accounts.User`), `verified_at`, `verification_notes`, `coa_file`, `test_results_json`.
- **Properties & Methods:** `status_css`, `is_verified`, `is_expired`, `test_results_count`.
- **Compound Indexes:** `idx_qcoa_ten_status`, `idx_qcoa_ten_supp_lot`, `idx_qcoa_ten_created`.

#### 24. `QualityReturnAuthorization` (Prefix: `QRMA-`)
- **Table:** `quality_return_authorization`
- **Key Fields:** `number`, `inspection_lot` (`IncomingInspectionLot`), `supplier` (`core.Party`), `item_code`, `lot_number`, `return_quantity` (Decimal), `reason` (`defective_material`, `out_of_spec`, `coa_failed`, `wrong_material`, `damaged_in_transit`, `over_shipment`), `description`, `disposition` (`replacement_requested`, `credit_memo_requested`, `rework_at_vendor`, `scrap_on_site`), `status` (`draft`, `authorized`, `shipped`, `delivered_to_vendor`, `completed`, `cancelled`), `authorized_by` (`accounts.User`), `authorized_at`, `debit_memo_number`, `credit_memo_number`, `tracking_number`, `carrier_name`, `shipped_at`, `replacement_received_at`, `notes`.
- **Properties & Methods:** `status_css`, `reason_css`, `disposition_css`, `is_shipped`, `is_completed`.
- **Compound Indexes:** `idx_qrma_ten_status`, `idx_qrma_ten_supp_lot`, `idx_qrma_ten_created`.

### Sub-module 12.8 Entities

#### 25. `InProcessInspection` (Prefix: `QIPQ-`)
- **Table:** `quality_in_process_inspection`
- **Key Fields:** `number`, `inspection_stage` (`first_piece`, `in_process_patrol`, `setup_verification`, `last_off`, `shift_handover`, `sampling`), `inspection_type` (`attribute_go_no_go`, `variable_dimensional`, `visual_cosmetic`, `functional_test`), `item_code`, `item_name`, `lot_number`, `serial_number`, `work_order` (`scm.WorkOrder`), `production_order_number`, `work_center` (`scm.WorkCenter`), `work_center_code`, `sample_size` (int), `sample_frequency_minutes` (int), `critical_defects` (int), `major_defects` (int), `minor_defects` (int), `defect_category` (`dimensional`, `surface_defect`, `assembly_error`, `contamination`, `labeling_packaging`, `functional_failure`), `result` (`pass`, `fail`, `conditional_pass`), `disposition` (`accept_to_run`, `rework_in_station`, `scrap_lot`, `quarantine_hold`, `escalate_to_ncr`), `inspector` (`accounts.User`), `operator_name`, `notes`, `inspection_plan_document` (`ControlledDocument`), `linked_ncr` (`NonConformanceReport`), `inspected_at`.
- **Properties & Methods:** `stage_css`, `type_css`, `result_css`, `defect_category_css`, `disposition_css`, `is_pass`, `total_defects`.
- **Compound Indexes:** `idx_qipq_ten_stage`, `idx_qipq_ten_res`, `idx_qipq_ten_created`, `idx_qipq_ten_item_lot`, `idx_qipq_ten_wo`.

#### 26. `FirstArticleInspection` (Prefix: `QFAI-`)
- **Table:** `quality_first_article_inspection`
- **Key Fields:** `number`, `item_code`, `item_name`, `drawing_number`, `drawing_revision`, `setup_reason` (`new_part_introduction`, `drawing_revision`, `machine_tooling_change`, `process_parameter_shift`, `material_lot_change`, `relocation_facility`, `extended_downtime`), `work_order` (`scm.WorkOrder`), `production_order_number`, `work_center` (`scm.WorkCenter`), `work_center_code`, `status` (`draft`, `submitted`, `in_review`, `approved`, `rejected`, `released_to_production`), `is_full_fai` (bool), `baseline_fai_number`, `total_characteristics_count` (int), `characteristics_conforming_count` (int), `characteristics_nonconforming_count` (int), `inspection_date`, `inspector` (`accounts.User`), `approved_by` (`accounts.User`), `approval_date`, `customer_approval_required` (bool), `customer_approval_reference`, `linked_ncr` (`NonConformanceReport`), `linked_sop` (`ControlledDocument`), `notes`, `characteristics_json`.
- **Properties & Methods:** `status_css`, `setup_reason_css`, `is_approved`, `is_released`, `conformance_pct`.
- **Compound Indexes:** `idx_qfai_ten_stat`, `idx_qfai_ten_reason`, `idx_qfai_ten_item_dwg`, `idx_qfai_ten_wo`, `idx_qfai_ten_created`.

#### 27. `ProcessParameterLog` (Prefix: `QPAR-`)
- **Table:** `quality_process_parameter_log`
- **Key Fields:** `number`, `parameter_name`, `parameter_type` (`temperature`, `pressure`, `speed_feed`, `humidity`, `dwell_time`, `torque_force`, `voltage_current`, `cycle_time`, `concentration_ph`), `unit_of_measure`, `work_center` (`scm.WorkCenter`), `work_center_code`, `work_order` (`scm.WorkOrder`), `production_order_number`, `target_nominal_value` (Decimal), `upper_spec_limit` (Decimal), `lower_spec_limit` (Decimal), `upper_control_limit` (Decimal), `lower_control_limit` (Decimal), `measured_value` (Decimal), `excursion_flag` (`in_control`, `warning_trend`, `out_of_control_excursion`), `logged_at`, `logged_by` (`accounts.User`), `spc_sigma_deviation` (Decimal), `containment_action_taken`, `linked_deviation` (`ProcessDeviation`), `notes`.
- **Properties & Methods:** `type_css`, `excursion_css`, `is_excursion`, `is_within_spec`.
- **Compound Indexes:** `idx_qpar_ten_param_type`, `idx_qpar_ten_excursion`, `idx_qpar_ten_wc_time`, `idx_qpar_ten_wo`, `idx_qpar_ten_created`.

#### 28. `LayeredProcessAudit` (Prefix: `QLPA-`)
- **Table:** `quality_layered_process_audit`
- **Key Fields:** `number`, `audit_layer` (`layer_1_shift_supervisor`, `layer_2_area_manager`, `layer_3_plant_executive`, `layer_4_specialist_safety_quality`), `title`, `work_center` (`scm.WorkCenter`), `work_center_code`, `shift` (`shift_1_morning`, `shift_2_afternoon`, `shift_3_night`), `audit_date`, `auditor` (`accounts.User`), `status` (`scheduled`, `in_progress`, `completed`, `findings_pending_ca`, `closed`), `questions_evaluated_count` (int), `questions_passed_count` (int), `questions_failed_count` (int), `compliance_score_pct` (Decimal), `critical_findings_count` (int), `findings_summary`, `corrective_action_required` (bool), `linked_capa` (`CapaInvestigation`), `checklist_items_json`, `notes`.
- **Properties & Methods:** `layer_css`, `status_css`, `is_compliant`, `total_findings`.
- **Compound Indexes:** `idx_qlpa_ten_layer`, `idx_qlpa_ten_status`, `idx_qlpa_ten_wc_date`, `idx_qlpa_ten_created`.

### Sub-module 12.11 Entities

#### 29. `AuditProgram` (Prefix: `QPRG-`)
- **Table:** `quality_audit_program`
- **Key Fields:** `number`, `program_year` (int), `title`, `frequency` (`annual`, `semi_annual`, `quarterly`, `monthly`, `risk_based_continuous`), `status` (`draft`, `approved`, `active`, `completed`, `cancelled`), `lead_audit_manager` (`accounts.User`), `approving_authority` (`accounts.User`), `approval_date`, `allocated_budget` (Decimal), `scope_description`, `objectives_statement`, `notes`.
- **Properties & Methods:** `progress_percentage` (reusing pre-annotated totals to eliminate N+1 queries), `status_badge`, `frequency_badge`, `total_audits_count`, `completed_audits_count`.
- **Compound Indexes:** `idx_qprg_ten_year` on `(tenant, -program_year)`, `idx_qprg_ten_status` on `(tenant, status)`, `idx_qprg_ten_created` on `(tenant, -created_at)`.

#### 30. `QualityAudit` (Prefix: `QAUD-`)
- **Table:** `quality_audit`
- **Key Fields:** `number`, `program` (`AuditProgram`), `title`, `audit_type` (`internal_qms`, `internal_process`, `supplier_external`, `regulatory_agency`, `customer_second_party`, `certification_body`), `standards_framework` (`iso_9001`, `iso_13485`, `fda_21_cfr_820`, `iso_14971`, `mdsap`, `eu_mdr`, `as9100`, `iatf_16949`, `gxp`), `lead_auditor` (`accounts.User`), `audit_team_members` (`ManyToManyField(accounts.User)`), `department` (`core.OrgUnit`), `supplier` (`core.Party`), `scheduled_start_date`, `scheduled_end_date`, `actual_start_date`, `actual_end_date`, `execution_method` (`on_site`, `remote_virtual`, `hybrid`), `status` (`scheduled`, `prep_in_progress`, `active_fieldwork`, `reporting`, `capa_pending`, `closed`, `cancelled`), `audit_score` (Decimal), `executive_summary`, `total_findings_count` (int), `open_findings_count` (int), `critical_findings_count` (int), `notes`.
- **Properties & Methods:** `audit_type_badge`, `framework_badge`, `status_badge`, `method_badge`, `sync_findings_counts()`.
- **Compound Indexes:** `idx_qaud_ten_stat` on `(tenant, status)`, `idx_qaud_ten_type` on `(tenant, audit_type)`, `idx_qaud_ten_dates` on `(tenant, scheduled_start_date)`, `idx_qaud_ten_created` on `(tenant, -created_at)`, `idx_qaud_ten_framework` on `(tenant, standards_framework)`.

#### 31. `AuditFinding` (Prefix: `QFND-`)
- **Table:** `quality_audit_finding`
- **Key Fields:** `number`, `audit` (`QualityAudit`), `finding_grade` (`critical_finding`, `major_nonconformance`, `minor_nonconformance`, `opportunity_for_improvement`, `positive_observation`), `title`, `requirement_statement`, `objective_evidence`, `clause_reference`, `department` (`core.OrgUnit`), `assignee` (`accounts.User`), `response_due_date`, `remediation_response`, `response_submitted_at`, `status` (`draft`, `issued`, `remediation_submitted`, `verified_closed`, `escalated_to_capa`), `verified_by` (`accounts.User`), `verified_at`, `verification_notes`, `linked_capa` (`CapaInvestigation`), `notes`.
- **Properties & Methods:** `grade_badge`, `status_badge`, `is_overdue` (evaluated only for `draft`, `issued`, `escalated` past due date), `save()` / `delete()` (automatically synchronizes parent audit finding counters).
- **Compound Indexes:** `idx_qfnd_ten_grade` on `(tenant, finding_grade)`, `idx_qfnd_ten_stat` on `(tenant, status)`, `idx_qfnd_ten_due` on `(tenant, response_due_date)`, `idx_qfnd_ten_created` on `(tenant, -created_at)`.

#### 32. `RegulatoryInspectionHost` (Prefix: `QHST-`)
- **Table:** `quality_regulatory_inspection_host`
- **Key Fields:** `number`, `inspection_title`, `inspection_type` (`fda_qsit`, `notified_body_iso13485`, `customer_qualification`, `health_canada_mdsap`, `mhra_ema`, `unannounced_inspection`), `inspecting_agency`, `lead_inspector_name`, `inspector_credentials`, `start_date`, `end_date`, `facility_location`, `primary_room_bridge`, `company_host_liaison` (`accounts.User`), `designated_scribe` (`accounts.User`), `inspection_status` (`announced_prep`, `on_site_active`, `daily_wrap_up`, `exit_interview`, `post_audit_response`, `closed`), `form_483_issued` (bool), `findings_count` (int), `agency_report_reference`, `war_room_requests` (JSONField), `live_inspection_notes`, `notes`.
- **Properties & Methods:** `inspection_type_badge`, `status_badge`, `requests_count`, `is_active_hosting`.
- **Compound Indexes:** `idx_qhst_ten_stat` on `(tenant, inspection_status)`, `idx_qhst_ten_type` on `(tenant, inspection_type)`, `idx_qhst_ten_dates` on `(tenant, start_date)`, `idx_qhst_ten_created` on `(tenant, -created_at)`.


---

## Routes & URLs

All routes use the `quality:` namespace:

### Sub-module 12.1 Routes
| URL Pattern | View Name | Purpose |
|---|---|---|
| `/quality/documents/` | `controlled_document_list` | Controlled documents list with filters and KPI stats |
| `/quality/documents/create/` | `controlled_document_create` | Create new controlled document |
| `/quality/documents/<pk>/` | `controlled_document_detail` | Document detail view with revision history & action buttons |
| `/quality/documents/<pk>/edit/` | `controlled_document_edit` | Edit metadata/file of draft or unapproved document |
| `/quality/documents/<pk>/delete/` | `controlled_document_delete` | POST-only delete for draft documents |
| `/quality/documents/<pk>/submit/` | `controlled_document_submit` | Submit draft document for review |
| `/quality/documents/<pk>/approve/` | `controlled_document_approve` | Admin approval for reviewed document |
| `/quality/documents/<pk>/make-effective/` | `controlled_document_make_effective` | Admin action: mark approved document effective |
| `/quality/documents/<pk>/obsolete/` | `controlled_document_obsolete` | Admin action: retire effective document |
| `/quality/documents/<pk>/new-revision/` | `controlled_document_new_revision` | Branch new revision from effective document |
| `/quality/documents/<pk>/sign/` | `controlled_document_sign` | 21 CFR Part 11 electronic signature execution |
| `/quality/documents/export/` | `controlled_document_export` | CSV export of controlled documents |
| `/quality/documents/vault/` | `document_archive_vault` | Compliance vault workbench for historical documents |
| `/quality/change-orders/` | `document_change_order_list` | DCO tickets list with filters and KPI stats |
| `/quality/change-orders/create/` | `document_change_order_create` | Create new document change order |
| `/quality/change-orders/<pk>/` | `document_change_order_detail` | DCO detail with signature manifest & actions |
| `/quality/change-orders/<pk>/edit/` | `document_change_order_edit` | Edit draft DCO |
| `/quality/change-orders/<pk>/delete/` | `document_change_order_delete` | POST-only delete for draft DCO |
| `/quality/change-orders/<pk>/submit/` | `document_change_order_submit` | Submit draft DCO for CCB review |
| `/quality/change-orders/<pk>/ccb-decision/` | `document_change_order_ccb_decision` | Record CCB determination |
| `/quality/change-orders/export/` | `document_change_order_export` | CSV export of change orders |
| `/quality/signatures/` | `electronic_signature_list` | Audit log of all 21 CFR Part 11 electronic signatures |
| `/quality/signatures/<pk>/` | `electronic_signature_detail` | Signature manifest verification detail |
| `/quality/signatures/<pk>/verify/` | `electronic_signature_verify` | Dynamic HMAC integrity check |
| `/quality/signatures/export/` | `electronic_signature_export` | CSV export of electronic signatures |
| `/quality/acknowledgments/` | `document_acknowledgment_list` | Employee compliance acknowledgments list |
| `/quality/acknowledgments/create/` | `document_acknowledgment_create` | Assign new acknowledgment requirement |
| `/quality/acknowledgments/<pk>/` | `document_acknowledgment_detail` | Acknowledgment detail view |
| `/quality/acknowledgments/<pk>/sign/` | `document_acknowledgment_sign` | Dual-credential sign-off for assigned employee |
| `/quality/acknowledgments/<pk>/delete/` | `document_acknowledgment_delete` | Admin delete of pending acknowledgment |
| `/quality/acknowledgments/export/` | `document_acknowledgment_export` | CSV export of acknowledgments |

### Sub-module 12.2 Routes
| URL Pattern | View Name | Purpose |
|---|---|---|
| `/quality/design-controls/projects/` | `design_project_list` | Design projects list with filters, stats, and search |
| `/quality/design-controls/projects/create/` | `design_project_create` | Initialize new design project and DHF plan |
| `/quality/design-controls/projects/<pk>/` | `design_project_detail` | Project detail, phase timeline, linked inputs, reviews & tests |
| `/quality/design-controls/projects/<pk>/edit/` | `design_project_edit` | Edit project metadata (guarded by DHF lock) |
| `/quality/design-controls/projects/<pk>/delete/` | `design_project_delete` | POST-only delete (guarded by DHF lock) |
| `/quality/design-controls/projects/<pk>/advance-phase/` | `design_project_advance_phase` | POST-only phase progression through stage gates |
| `/quality/design-controls/projects/<pk>/lock-dhf/` | `design_project_lock_dhf` | Formal 21 CFR § 820.30(j) immutable DHF freeze |
| `/quality/design-controls/projects/export/` | `design_project_export` | CSV export of design projects |
| `/quality/design-controls/inputs/` | `design_input_list` | Design inputs & user needs list |
| `/quality/design-controls/inputs/create/` | `design_input_create` | Add design input / specification |
| `/quality/design-controls/inputs/<pk>/` | `design_input_detail` | Design input detail with child specs and linked V&V protocols |
| `/quality/design-controls/inputs/<pk>/edit/` | `design_input_edit` | Edit specification (guarded by DHF lock) |
| `/quality/design-controls/inputs/<pk>/delete/` | `design_input_delete` | POST-only delete (guarded by DHF lock) |
| `/quality/design-controls/inputs/export/` | `design_input_export` | CSV export of design inputs |
| `/quality/design-controls/reviews/` | `design_review_list` | Stage-gate design reviews list |
| `/quality/design-controls/reviews/create/` | `design_review_create` | Schedule stage-gate design review |
| `/quality/design-controls/reviews/<pk>/` | `design_review_detail` | Design review detail with actions & approval gate |
| `/quality/design-controls/reviews/<pk>/edit/` | `design_review_edit` | Edit review notes & action items (guarded by DHF lock) |
| `/quality/design-controls/reviews/<pk>/delete/` | `design_review_delete` | POST-only delete (guarded by DHF lock) |
| `/quality/design-controls/reviews/<pk>/approve-gate/` | `design_review_approve_gate` | Formally clear and approve stage gate milestone |
| `/quality/design-controls/reviews/export/` | `design_review_export` | CSV export of design reviews |
| `/quality/design-controls/verifications/` | `design_verification_list` | V&V test protocols list |
| `/quality/design-controls/verifications/create/` | `design_verification_create` | Author V&V test protocol (auto-verifies primary input) |
| `/quality/design-controls/verifications/<pk>/` | `design_verification_detail` | Verification protocol execution detail & results |
| `/quality/design-controls/verifications/<pk>/edit/` | `design_verification_edit` | Update test results (auto-syncs primary input status) |
| `/quality/design-controls/verifications/<pk>/delete/` | `design_verification_delete` | POST-only delete (recalculates input status) |
| `/quality/design-controls/verifications/export/` | `design_verification_export` | CSV export of verification protocols |
| `/quality/design-controls/matrix/` | `traceability_matrix` | Requirements Traceability Matrix (RTM) workbench |
| `/quality/design-controls/matrix/export/` | `traceability_matrix_export` | Stream RTM CSV (`RTM_<number>.csv`) |
| `/quality/design-controls/projects/<pk>/dhf/` | `design_project_dhf` | Audit-ready Design History File (DHF) dossier |
| `/quality/design-controls/projects/<pk>/dhf/export/` | `design_project_dhf_export` | Stream DHF Index CSV (`DHF_Index_<number>.csv`) |

### Sub-module 12.3 Routes
| URL Pattern | View Name | Purpose |
|---|---|---|
| `/quality/risk-management/plans/` | `risk_management_plan_list` | Risk management plans list with filters, KPI cards, and search |
| `/quality/risk-management/plans/create/` | `risk_management_plan_create` | Create new ISO 14971 risk management plan |
| `/quality/risk-management/plans/<pk>/` | `risk_management_plan_detail` | Plan detail, batched stats, linked hazards, reviews, and e-signatures |
| `/quality/risk-management/plans/<pk>/edit/` | `risk_management_plan_edit` | Edit plan metadata (guarded against active/signed plans) |
| `/quality/risk-management/plans/<pk>/delete/` | `risk_management_plan_delete` | POST-only delete (requires tenant admin, preserves audit object_id) |
| `/quality/risk-management/plans/<pk>/activate/` | `risk_management_plan_activate` | POST-only milestone transition to active (requires tenant admin) |
| `/quality/risk-management/plans/<pk>/archive/` | `risk_management_plan_archive` | POST-only milestone transition to archived (requires tenant admin) |
| `/quality/risk-management/plans/export/` | `risk_management_plan_export` | CSV export with csv_safe sanitization |
| `/quality/risk-management/assessments/` | `risk_assessment_list` | FMEA hazard assessments list with category, level, and plan filters |
| `/quality/risk-management/assessments/create/` | `risk_assessment_create` | Add hazard analysis / FMEA failure mode with pre-mitigation scores |
| `/quality/risk-management/assessments/<pk>/` | `risk_assessment_detail` | Assessment detail with linked controls, residual evaluation, and BRA |
| `/quality/risk-management/assessments/<pk>/edit/` | `risk_assessment_edit` | Edit hazard assessment and recompute residual metrics |
| `/quality/risk-management/assessments/<pk>/delete/` | `risk_assessment_delete` | POST-only delete (requires tenant admin) |
| `/quality/risk-management/assessments/export/` | `risk_assessment_export` | CSV export of risk assessments |
| `/quality/risk-management/controls/` | `risk_control_measure_list` | Risk control measures list with hierarchy and status filters |
| `/quality/risk-management/controls/create/` | `risk_control_measure_create` | Add mitigation measure linked to design input/verification |
| `/quality/risk-management/controls/<pk>/` | `risk_control_measure_detail` | Control measure detail with verification protocol status |
| `/quality/risk-management/controls/<pk>/edit/` | `risk_control_measure_edit` | Edit control measure (with objective evidence validation) |
| `/quality/risk-management/controls/<pk>/delete/` | `risk_control_measure_delete` | POST-only delete (requires tenant admin) |
| `/quality/risk-management/controls/<pk>/verify-implementation/` | `risk_control_measure_verify_impl` | POST-only action marking implementation verified with audit log |
| `/quality/risk-management/controls/<pk>/verify-effectiveness/` | `risk_control_measure_verify_eff` | POST-only action marking effectiveness verified with audit log |
| `/quality/risk-management/controls/export/` | `risk_control_measure_export` | CSV export of control measures |
| `/quality/risk-management/reviews/` | `risk_review_record_list` | Risk management reviews list |
| `/quality/risk-management/reviews/create/` | `risk_review_record_create` | Schedule risk management review |
| `/quality/risk-management/reviews/<pk>/` | `risk_review_record_detail` | Review detail with findings, conclusions, and approval status |
| `/quality/risk-management/reviews/<pk>/edit/` | `risk_review_record_edit` | Edit review notes (guarded against approved reviews) |
| `/quality/risk-management/reviews/<pk>/delete/` | `risk_review_record_delete` | POST-only delete (requires tenant admin) |
| `/quality/risk-management/reviews/<pk>/approve/` | `risk_review_record_approve` | POST-only formal review approval (requires tenant admin) |
| `/quality/risk-management/reviews/export/` | `risk_review_record_export` | CSV export of review records |
| `/quality/risk-management/fmea-matrix/` | `fmea_matrix` | Interactive 5x5 / NxN FMEA risk matrix heatmap workbench |
| `/quality/risk-management/fmea-matrix/export/` | `fmea_matrix_export` | CSV export of matrix distribution for selected plan |
| `/quality/risk-management/traceability-matrix/` | `risk_traceability_matrix` | Comprehensive Hazard -> Control -> Verification Traceability Matrix |
| `/quality/risk-management/traceability-matrix/export/` | `risk_traceability_matrix_export` | CSV export of Risk Traceability Matrix |

### Sub-module 12.4 Routes
| URL Pattern | View Name | Purpose |
|---|---|---|
| `/quality/capa/investigations/` | `capa_investigation_list` | CAPA investigations list with filters, KPI counters, and search |
| `/quality/capa/investigations/create/` | `capa_investigation_create` | Log new CAPA investigation with initial containment |
| `/quality/capa/investigations/<pk>/` | `capa_investigation_detail` | Detailed CAPA dossier with linked RCAs, actions, reviews, and audit trail |
| `/quality/capa/investigations/<pk>/edit/` | `capa_investigation_edit` | Edit investigation metadata (guarded against closed/voided CAPAs) |
| `/quality/capa/investigations/<pk>/delete/` | `capa_investigation_delete` | POST-only delete (requires tenant admin, blocks closed CAPAs) |
| `/quality/capa/investigations/<pk>/advance-status/` | `capa_investigation_advance_status` | POST-only lifecycle phase progression (blocks direct closure, gates voiding to admin) |
| `/quality/capa/investigations/<pk>/close/` | `capa_investigation_close` | POST-only formal closure (requires tenant admin, checks pending actions, records signature) |
| `/quality/capa/investigations/export/` | `capa_investigation_export` | CSV export with formula injection defense |
| `/quality/capa/root-causes/` | `root_cause_analysis_list` | RCA records list with method and category filters |
| `/quality/capa/root-causes/create/` | `root_cause_analysis_create` | Add 5 Whys or Ishikawa fishbone analysis to CAPA |
| `/quality/capa/root-causes/<pk>/` | `root_cause_analysis_detail` | RCA visual ladder, fishbone diagram, and verification status |
| `/quality/capa/root-causes/<pk>/edit/` | `root_cause_analysis_edit` | Edit RCA (guarded against verified records) |
| `/quality/capa/root-causes/<pk>/delete/` | `root_cause_analysis_delete` | POST-only delete (requires tenant admin, blocks verified RCAs) |
| `/quality/capa/root-causes/<pk>/verify/` | `root_cause_analysis_verify` | POST-only quality engineering verification |
| `/quality/capa/root-causes/export/` | `root_cause_analysis_export` | CSV export of root cause analyses |
| `/quality/capa/actions/` | `capa_action_list` | Action items list with action type and overdue status |
| `/quality/capa/actions/create/` | `capa_action_create` | Add action item linked to root cause and QMS engineering spine |
| `/quality/capa/actions/<pk>/` | `capa_action_detail` | Action detail with verification evidence and linked assets |
| `/quality/capa/actions/<pk>/edit/` | `capa_action_edit` | Edit action plan (guarded against verified actions) |
| `/quality/capa/actions/<pk>/delete/` | `capa_action_delete` | POST-only delete (requires tenant admin, blocks verified actions) |
| `/quality/capa/actions/<pk>/mark-completed/` | `capa_action_mark_completed` | POST-only implementation sign-off with implementation notes |
| `/quality/capa/actions/<pk>/verify/` | `capa_action_verify` | POST-only independent verification (requires implemented status, enforces separation of duties) |
| `/quality/capa/actions/export/` | `capa_action_export` | CSV export of CAPA actions |
| `/quality/capa/effectiveness-reviews/` | `capa_effectiveness_review_list` | Effectiveness reviews list with outcome and overdue filters |
| `/quality/capa/effectiveness-reviews/create/` | `capa_effectiveness_review_create` | Schedule post-implementation effectiveness evaluation |
| `/quality/capa/effectiveness-reviews/<pk>/` | `capa_effectiveness_review_detail` | Review detail with recurrence tracking and statistical results |
| `/quality/capa/effectiveness-reviews/<pk>/edit/` | `capa_effectiveness_review_edit` | Edit review protocol (guarded against completed reviews) |
| `/quality/capa/effectiveness-reviews/<pk>/delete/` | `capa_effectiveness_review_delete` | POST-only delete (requires tenant admin, blocks completed reviews) |
| `/quality/capa/effectiveness-reviews/<pk>/sign-off/` | `capa_effectiveness_review_sign_off` | POST-only outcome sign-off (evaluator/admin check, blocks 'effective' if recurrence observed) |
| `/quality/capa/effectiveness-reviews/export/` | `capa_effectiveness_review_export` | CSV export of effectiveness reviews |
| `/quality/capa/tracking-board/` | `capa_tracking_board` | Interactive 5-column Kanban board with 4-tier aging matrix |
| `/quality/capa/tracking-board/export/` | `capa_tracking_board_export` | CSV export of aging workbench data |

### Sub-module 12.7 Routes
| URL Pattern | View Name | Purpose |
|---|---|---|
| `/quality/incoming-quality/plans/` | `incoming_inspection_plan_list` | Inspection plans list with item, supplier, standard, and status filters |
| `/quality/incoming-quality/plans/create/` | `incoming_inspection_plan_create` | Create new incoming inspection plan with AQL parameters |
| `/quality/incoming-quality/plans/<pk>/` | `incoming_inspection_plan_detail` | Inspection plan detail with sampling configuration & audit trail |
| `/quality/incoming-quality/plans/<pk>/edit/` | `incoming_inspection_plan_edit` | Edit inspection plan parameters |
| `/quality/incoming-quality/plans/<pk>/delete/` | `incoming_inspection_plan_delete` | POST-only delete (requires tenant admin) |
| `/quality/incoming-quality/plans/export/` | `incoming_inspection_plan_export` | CSV export of incoming inspection plans |
| `/quality/incoming-quality/lots/` | `incoming_inspection_lot_list` | Inspection lots list with stage and usage decision filters |
| `/quality/incoming-quality/lots/create/` | `incoming_inspection_lot_create` | Create new inspection lot with automatic ANSI Z1.4 code letter calculation |
| `/quality/incoming-quality/lots/<pk>/` | `incoming_inspection_lot_detail` | Detailed inspection lot dossier with defect summary and measurements |
| `/quality/incoming-quality/lots/<pk>/edit/` | `incoming_inspection_lot_edit` | Update lot measurements and defect counts |
| `/quality/incoming-quality/lots/<pk>/delete/` | `incoming_inspection_lot_delete` | POST-only delete (requires tenant admin) |
| `/quality/incoming-quality/lots/<pk>/decision/` | `incoming_inspection_lot_decision` | Record usage decision (spawns QNCR and QHLD on rejection) |
| `/quality/incoming-quality/lots/export/` | `incoming_inspection_lot_export` | CSV export of incoming inspection lots |
| `/quality/incoming-quality/coas/` | `certificate_of_analysis_list` | Certificates of analysis list with status filters |
| `/quality/incoming-quality/coas/create/` | `certificate_of_analysis_create` | Log and upload vendor CoA with specification limits |
| `/quality/incoming-quality/coas/<pk>/` | `certificate_of_analysis_detail` | CoA verification dossier and test results |
| `/quality/incoming-quality/coas/<pk>/edit/` | `certificate_of_analysis_edit` | Edit CoA metadata and test specifications |
| `/quality/incoming-quality/coas/<pk>/delete/` | `certificate_of_analysis_delete` | POST-only delete (requires tenant admin) |
| `/quality/incoming-quality/coas/<pk>/verify/` | `certificate_of_analysis_verify` | Record CoA verification determination |
| `/quality/incoming-quality/coas/export/` | `certificate_of_analysis_export` | CSV export of certificates of analysis |
| `/quality/incoming-quality/rmas/` | `quality_return_authorization_list` | Quality return authorizations list with status and reason filters |
| `/quality/incoming-quality/rmas/create/` | `quality_return_authorization_create` | Issue RMA debit memo for rejected inspection lot |
| `/quality/incoming-quality/rmas/<pk>/` | `quality_return_authorization_detail` | RMA tracking dossier with replacement / credit memo details |
| `/quality/incoming-quality/rmas/<pk>/edit/` | `quality_return_authorization_edit` | Edit RMA details |
| `/quality/incoming-quality/rmas/<pk>/delete/` | `quality_return_authorization_delete` | POST-only delete (requires tenant admin) |
| `/quality/incoming-quality/rmas/<pk>/dispatch/` | `quality_return_authorization_dispatch` | Record carrier dispatch and shipment tracking number |
| `/quality/incoming-quality/rmas/export/` | `quality_return_authorization_export` | CSV export of quality return authorizations |
| `/quality/incoming-quality/spc-dashboard/` | `iqc_spc_dashboard` | Interactive SPC Analytics dashboard with Pareto charts and capability indices |
| `/quality/incoming-quality/spc-dashboard/export/` | `iqc_spc_dashboard_export` | CSV export of SPC alerts and defect distribution |

### Sub-module 12.8 Routes
| URL Pattern | View Name | Purpose |
|---|---|---|
| `/quality/in-process-quality/inspections/` | `in_process_inspection_list` | In-process inspections list with stage, type, result, disposition, and date filters |
| `/quality/in-process-quality/inspections/create/` | `in_process_inspection_create` | Log production inspection with defect classification and disposition |
| `/quality/in-process-quality/inspections/<pk>/` | `in_process_inspection_detail` | Detailed inspection dossier with linked NCR route and action buttons |
| `/quality/in-process-quality/inspections/<pk>/edit/` | `in_process_inspection_edit` | Edit inspection results and defect counts |
| `/quality/in-process-quality/inspections/<pk>/delete/` | `in_process_inspection_delete` | POST-only delete (requires tenant admin) |
| `/quality/in-process-quality/inspections/export/` | `in_process_inspection_export` | CSV export of in-process inspections with audit logging |
| `/quality/in-process-quality/fai/` | `first_article_inspection_list` | First article inspections list with status and setup reason filters |
| `/quality/in-process-quality/fai/create/` | `first_article_inspection_create` | Create new FAI protocol conforming to AS9102 / ISO 9001 |
| `/quality/in-process-quality/fai/<pk>/` | `first_article_inspection_detail` | FAI dossier with characteristic verification breakdown and approval status |
| `/quality/in-process-quality/fai/<pk>/edit/` | `first_article_inspection_edit` | Edit FAI characteristic counts and drawing revision metadata |
| `/quality/in-process-quality/fai/<pk>/delete/` | `first_article_inspection_delete` | POST-only delete (requires tenant admin) |
| `/quality/in-process-quality/fai/<pk>/release/` | `first_article_inspection_release` | Production authorization release gate (requires tenant admin, checks approval) |
| `/quality/in-process-quality/fai/export/` | `first_article_inspection_export` | CSV export of first article inspections with audit logging |
| `/quality/in-process-quality/parameters/` | `process_parameter_log_list` | Machine and environmental parameter telemetry logs with excursion filters |
| `/quality/in-process-quality/parameters/create/` | `process_parameter_log_create` | Log telemetry reading with automated SPC excursion detection |
| `/quality/in-process-quality/parameters/<pk>/` | `process_parameter_log_detail` | Parameter log dossier with control limits and containment action |
| `/quality/in-process-quality/parameters/<pk>/edit/` | `process_parameter_log_edit` | Edit parameter measurement and excursion notes |
| `/quality/in-process-quality/parameters/<pk>/delete/` | `process_parameter_log_delete` | POST-only delete (requires tenant admin) |
| `/quality/in-process-quality/parameters/export/` | `process_parameter_log_export` | CSV export of parameter telemetry logs with audit logging |
| `/quality/in-process-quality/audits/` | `layered_process_audit_list` | CQI-8 layered process audits list with layer, shift, and status filters |
| `/quality/in-process-quality/audits/create/` | `layered_process_audit_create` | Schedule or execute layered process audit across management layers |
| `/quality/in-process-quality/audits/<pk>/` | `layered_process_audit_detail` | Audit dossier with question compliance score and corrective action alerts |
| `/quality/in-process-quality/audits/<pk>/edit/` | `layered_process_audit_edit` | Edit audit questions, findings count, and compliance score |
| `/quality/in-process-quality/audits/<pk>/delete/` | `layered_process_audit_delete` | POST-only delete (requires tenant admin) |
| `/quality/in-process-quality/audits/export/` | `layered_process_audit_export` | CSV export of layered process audits with audit logging |
| `/quality/in-process-quality/spc-dashboard/` | `spc_dashboard` | Interactive In-Process Quality SPC dashboard and Work Instruction compliance |
| `/quality/in-process-quality/spc-dashboard/export/` | `spc_dashboard_export` | CSV export of in-process quality control summary metrics |

### Sub-module 12.11 Routes
| URL Pattern | View Name | Purpose |
|---|---|---|
| `/quality/audits/programs/` | `audit_program_list` | Audit programs list with year, frequency, status filters and progress tracking |
| `/quality/audits/programs/create/` | `audit_program_create` | Create annual/multi-year audit program |
| `/quality/audits/programs/<pk>/` | `audit_program_detail` | Audit program detail with linked audits, progress percentage, and KPI metrics |
| `/quality/audits/programs/<pk>/edit/` | `audit_program_edit` | Edit audit program metadata and budget allocation |
| `/quality/audits/programs/<pk>/delete/` | `audit_program_delete` | POST-only delete (requires tenant admin) |
| `/quality/audits/programs/<pk>/approve/` | `audit_program_approve` | Formal program approval (requires tenant admin) |
| `/quality/audits/programs/export/` | `audit_program_export` | CSV export of audit programs with formula sanitization |
| `/quality/audits/audits/` | `quality_audit_list` | Quality audits list with type, framework, status, method, and date filters |
| `/quality/audits/audits/create/` | `quality_audit_create` | Schedule quality audit with audit team members |
| `/quality/audits/audits/<pk>/` | `quality_audit_detail` | Detailed audit dossier with finding cards, score, and action shortcuts |
| `/quality/audits/audits/<pk>/edit/` | `quality_audit_edit` | Edit quality audit protocol, team members, and scoring |
| `/quality/audits/audits/<pk>/delete/` | `quality_audit_delete` | POST-only delete (requires tenant admin) |
| `/quality/audits/audits/<pk>/advance-status/` | `quality_audit_advance_status` | POST-only lifecycle status progression |
| `/quality/audits/audits/export/` | `quality_audit_export` | CSV export of quality audits with audit logging |
| `/quality/audits/findings/` | `audit_finding_list` | Graded audit findings list with grade, status, and overdue SLA filters |
| `/quality/audits/findings/create/` | `audit_finding_create` | Log audit finding/observation with requirement and evidence |
| `/quality/audits/findings/<pk>/` | `audit_finding_detail` | Audit finding dossier with remediation tracking and CAPA escalation |
| `/quality/audits/findings/<pk>/edit/` | `audit_finding_edit` | Edit audit finding requirement, clause, and assignee |
| `/quality/audits/findings/<pk>/delete/` | `audit_finding_delete` | POST-only delete (requires tenant admin, resyncs audit counters) |
| `/quality/audits/findings/<pk>/submit-response/` | `audit_finding_submit_response` | Submit remediation response and evidence |
| `/quality/audits/findings/<pk>/verify-close/` | `audit_finding_verify_close` | Verify and close finding (enforces auditor independence) |
| `/quality/audits/findings/<pk>/create-capa/` | `audit_finding_create_capa` | Directly spawn linked CAPA investigation (`QCAP-`) |
| `/quality/audits/findings/export/` | `audit_finding_export` | CSV export of audit findings with audit logging |
| `/quality/audits/inspections/` | `regulatory_inspection_host_list` | Regulatory inspection hosts list with agency, type, and status filters |
| `/quality/audits/inspections/create/` | `regulatory_inspection_host_create` | Schedule inspection hosting protocol (FDA, Notified Body, MDSAP) |
| `/quality/audits/inspections/<pk>/` | `regulatory_inspection_host_detail` | Inspection hosting dossier with liaison, scribe, and live request log |
| `/quality/audits/inspections/<pk>/edit/` | `regulatory_inspection_host_edit` | Edit inspection hosting metadata and findings count |
| `/quality/audits/inspections/<pk>/delete/` | `regulatory_inspection_host_delete` | POST-only delete (requires tenant admin) |
| `/quality/audits/inspections/<pk>/advance-status/` | `regulatory_inspection_host_advance_status` | POST-only inspection hosting phase transition |
| `/quality/audits/inspections/<pk>/add-log/` | `regulatory_inspection_host_add_log` | Add timestamped live observation/scribe entry |
| `/quality/audits/inspections/export/` | `regulatory_inspection_host_export` | CSV export of regulatory inspection hosting records |
| `/quality/audits/action-tracker/` | `audit_action_tracker` | Audit Action Tracker workbench with aging tiers and overdue SLA alerts |
| `/quality/audits/action-tracker/export/` | `audit_action_tracker_export` | CSV export of open audit remediation actions |
| `/quality/audits/inspections/<pk>/war-room/` | `audit_war_room` | Live Inspection War Room command center with request dispatching |
| `/quality/audits/inspections/<pk>/war-room/export/` | `audit_war_room_export` | CSV export of War Room request manifest |

### Sub-module 12.13 Routes
| URL Pattern | View Name | Purpose |
|---|---|---|
| `/quality/complaints/` | `customer_complaint_list` | Complaints register with severity, status, validity, channel filters and KPI summaries |
| `/quality/complaints/create/` | `customer_complaint_create` | Log customer allegation with intake channel, severity, and product data |
| `/quality/complaints/<pk>/` | `customer_complaint_detail` | Detailed complaint dossier with linked investigations, reports, and field actions |
| `/quality/complaints/<pk>/edit/` | `customer_complaint_edit` | Edit complaint record (locked when closed/cancelled) |
| `/quality/complaints/<pk>/delete/` | `customer_complaint_delete` | POST-only delete (requires tenant admin, blocked if filed reports exist) |
| `/quality/complaints/<pk>/triage/` | `customer_complaint_triage` | Triage determination (validity, severity, reportability, investigation requirement) |
| `/quality/complaints/<pk>/close/` | `customer_complaint_close` | Formal resolution sign-off and closure letter dispatch recording |
| `/quality/complaints/export/csv/` | `customer_complaint_export_csv` | CSV export of customer complaints with active filter preservation |
| `/quality/investigations/` | `complaint_investigation_list` | Technical investigations register with analytical method and root cause filters |
| `/quality/investigations/create/` | `complaint_investigation_create` | Initiate failure analysis and DHR review investigation |
| `/quality/investigations/<pk>/` | `complaint_investigation_detail` | Detailed investigation report with lab findings, HHE, and CAPA/NCR links |
| `/quality/investigations/<pk>/edit/` | `complaint_investigation_edit` | Edit investigation findings (locked when approved) |
| `/quality/investigations/<pk>/delete/` | `complaint_investigation_delete` | POST-only delete (requires tenant admin, blocked if approved) |
| `/quality/investigations/<pk>/complete/` | `complaint_investigation_complete` | Formal completion and quality sign-off action |
| `/quality/investigations/export/csv/` | `complaint_investigation_export_csv` | CSV export of complaint investigations |
| `/quality/regulatory-reports/` | `regulatory_report_list` | Vigilance reporting tracker with agency, report type, timeline, and status filters |
| `/quality/regulatory-reports/create/` | `regulatory_report_create` | Draft MedWatch 3500A / EU MIR adverse event report |
| `/quality/regulatory-reports/<pk>/` | `regulatory_report_detail` | Regulatory report dossier with statutory countdown clock and acknowledgement info |
| `/quality/regulatory-reports/<pk>/edit/` | `regulatory_report_edit` | Edit regulatory report (locked when submitted/acknowledged) |
| `/quality/regulatory-reports/<pk>/delete/` | `regulatory_report_delete` | POST-only delete (requires tenant admin, blocked if submitted) |
| `/quality/regulatory-reports/<pk>/submit/` | `regulatory_report_submit` | Record gateway transmission date and agency case identifier |
| `/quality/regulatory-reports/<pk>/acknowledge/` | `regulatory_report_acknowledge` | Record agency acceptance and receipt acknowledgement number |
| `/quality/regulatory-reports/export/csv/` | `regulatory_report_export_csv` | CSV export of regulatory vigilance reports |
| `/quality/field-actions/` | `field_action_list` | Field actions & recalls register with action type, class, and status filters |
| `/quality/field-actions/create/` | `field_action_create` | Declare voluntary recall or Field Safety Corrective Action (FSCA) |
| `/quality/field-actions/<pk>/` | `field_action_detail` | Product recall command center with consignee response and recovery progress |
| `/quality/field-actions/<pk>/edit/` | `field_action_edit` | Edit field action strategy and affected lot scope |
| `/quality/field-actions/<pk>/delete/` | `field_action_delete` | POST-only delete (requires tenant admin) |
| `/quality/field-actions/<pk>/close/` | `field_action_close` | Terminate recall and record agency concurrence justification |
| `/quality/field-actions/export/csv/` | `field_action_export_csv` | CSV export of field actions |
| `/quality/trending/` | `complaint_trending_dashboard` | Executive complaint intelligence command center with cycle time and Pareto charts |

---

## Seeder (`seed_quality`)

Run command:
```powershell
venv\Scripts\python.exe manage.py seed_quality
```

Creates realistic GxP compliance data for `acme` and `globex` tenants:
- **12.1 Data**: 5 Controlled Documents, 3 Change Orders, 4 Electronic Signatures, 4 Acknowledgments per tenant.
- **12.2 Data**:
  - 2 Design Projects per tenant (`InfuseFlow Pro 3000` active, `AccuInject 5mL Safety Syringe` locked)
  - 4 Design Inputs per active project (`UN-001`, `UN-002`, `DI-001`, `DI-002`)
  - 2 Stage-Gate Design Reviews (Planning Gate approved, Input/Verification Gate scheduled)
  - 2 Design Verification & Validation Protocols (Occlusion pressure, Battery transit)
- **12.3 Data**:
  - 2 Risk Management Plans per tenant:
    - Smart Infusion Pump System (`InfuseFlow Pro 3000`, Class II, 5x5 matrix, active)
    - Sterile Syringe Device (`AccuInject 5mL Safety Syringe`, Class II, 5x5 matrix, active)
  - 4 Hazard Identification & FMEA Risk Assessments:
    - Electrical hazard: Chassis voltage leakage during line power surge ($S=4, P=3 \rightarrow \text{ALARP}$)
    - Software/Operational: Free-flow bolus delivery due to motor encoder desync ($S=5, P=3 \rightarrow \text{Unacceptable}$)
    - Mechanical: Syringe plunger clamp disengagement during infusion ($S=3, P=3 \rightarrow \text{ALARP}$)
    - Usability: Confusion between primary infusion and secondary piggyback ($S=3, P=2 \rightarrow \text{ALARP}$)
  - 4 Risk Control Measures across the 3-tier ISO 14971 hierarchy:
    - Inherent Safety: Dual-channel independent optical encoder with hardware watchdog (verified)
    - Inherent Safety: Galvanic 4kV dielectric isolation transformer (verified)
    - Protective Measure: Redundant mechanical anti-free-flow clamp (verified)
    - Information for Safety: Clear dual-color graphical UI on touchscreen and IFU warning label (verified)
  - Residual Risk Evaluations:
    - Post-mitigation motor desync reduced from $RPN=15$ (Unacceptable) to $RPN=2$ (Broadly Acceptable)
    - Electrical surge reduced to $RPN=2$ (Broadly Acceptable)
  - 2 Risk Management Reviews:
    - Interim Design Risk Assessment Review (Approved with e-signature)
    - Pre-Verification Risk Assessment Review (Under Review)

- **12.4 Data**:
  - 4 CAPA investigations per tenant:
    - `Infusion Pump Pressure Sensor Drift`: Customer complaint, Critical priority, under investigation with quarantined lots
    - `Sterile Barrier Pouch Seal Temperature Excursion`: Internal audit finding, High priority, RCA in progress
    - `Automated Syringe Assembly Alignment Fault`: NCR root cause, Medium priority, corrective actions pending
    - `Annual Trend: Luer Lock Thread Stripping`: Historical trend analysis, Medium priority, closed with e-signature sign-off
  - 4 Root Cause Analyses (5 Whys causal stepping ladders and Ishikawa 6M fishbone models with escape point barrier gaps)
  - 5 CAPA Actions across immediate containment, corrective, and preventive types linked to DCOs and engineering specs
  - 3 Effectiveness Reviews with statistical sampling, trend evaluations, and Part 11 e-signature records

- **12.7 Data**:
  - 2 Incoming Inspection Plans per tenant:
    - `Receiving Plan - Titanium Rods` (ANSI/ASQ Z1.4, Level II Normal, AQL 0.00/1.00/4.00, requires CoA, linked to SOP-QMS-001)
    - `Receiving Plan - Sterile Syringe Barrels` (ISO 2859-1, Level II Reduced, skip-lot frequency interval 5)
  - 3 Incoming Inspection Lots per tenant:
    - Lot `LOT-2026-IQC-001` (Titanium Rods, 500 units, sample size 32, accepted, SPC Cpk=1.36)
    - Lot `LOT-2026-IQC-002` (Titanium Rods, 300 units, rejected due to critical diameter defect, spawned NonConformanceReport and QuarantineContainment hold)
    - Lot `LOT-2026-IQC-003` (Syringe Barrels, 1,000 units, skip-lot passed without inspection)
  - 2 Certificates of Analysis per tenant:
    - CoA for `LOT-2026-IQC-001` (Titanium alloy composition, accepted and verified)
    - CoA for `LOT-2026-IQC-003` (Polypropylene resin assay, pending review)
  - 1 Quality Return Authorization per tenant:
    - RMA for rejected Lot `LOT-2026-IQC-002` (300 units, replacement requested, carrier dispatch tracking recorded)

- **12.8 Data**:
  - 2 In-Process Inspections per tenant:
    - `QIPQ-2026-00001` (First piece inspection on Titanium Rod machining, Pass, Accept to run)
    - `QIPQ-2026-00002` (In-process patrol on Syringe Barrel molding, Fail with surface defect, Escalate to NCR)
  - 2 First Article Inspections per tenant:
    - `QFAI-2026-00001` (New Part Introduction FAI, AS9102 Form 1/2/3 complete, 100% conforming, Released to production)
    - `QFAI-2026-00002` (Machine Tooling Change FAI, partial re-inspection, In review)
  - 3 Process Parameter Logs per tenant:
    - `QPAR-2026-00001` (Barrel Injection Temperature: 245°C nominal, In control)
    - `QPAR-2026-00002` (Injection Pack Pressure: 142 bar, Out-of-control excursion with containment action)
    - `QPAR-2026-00003` (CNC Spindle Speed: 4,500 RPM nominal, In control)
  - 2 Layered Process Audits per tenant:
    - `QLPA-2026-00001` (Layer 1 Shift Supervisor audit on Work Center CNC-01, Shift 1, 100% compliance score)
    - `QLPA-2026-00002` (Layer 2 Area Manager audit on Cleanroom Molding, Shift 2, 85% compliance score with minor finding)

- **12.10 Data**:
  - 6 Calibration Gages per tenant:
    - `GAG-STD-001` (Ceramic Master Gauge Block Set Grade 0, Reference Standard, active)
    - `GAG-DIG-002` (Digital Outside Micrometer 0-25mm, active)
    - `GAG-CAL-003` (Vernier Digital Caliper 150mm, active)
    - `GAG-TORQ-004` (Electronic Torque Wrench 10-100 Nm, quarantined OOT)
    - `GAG-DMM-005` (6.5 Digit Precision Multimeter, pending calibration)
    - `GAG-OPT-006` (Optical Vision Measuring System, active)
  - 4 Calibration Records per tenant:
    - `EXT-CAL-2026-001` (Accredited external calibration on GAG-STD-001, Pass, guardbanded ILAC-G8)
    - `INT-CAL-2026-002` (Internal routine calibration on GAG-DIG-002, Pass)
    - `EXT-CAL-2026-003` (Accredited calibration on GAG-CAL-003, Pass with limitations)
    - `INT-CAL-2026-OOT-01` (Failed calibration on GAG-TORQ-004, Fail Out of Tolerance, triggered OOT-2026-001)
  - 1 Out-of-Tolerance Investigation per tenant:
    - `OOT-2026-001` (Electronic Torque Wrench OOT, High Risk, 150 suspect units contained on hold, linked to CAPA)
  - 3 Measurement System Analysis Studies per tenant:
    - `MSA-2026-001` (Gage R&R ANOVA on Micrometer, %GRR 14.07%, NDC 9, Acceptable)
    - `MSA-2026-002` (Gage R&R ANOVA on Digital Caliper, %GRR 22.40%, NDC 6, Marginal/Conditional)
    - `MSA-2026-003` (Linearity and Bias Study on Master Gauge Blocks, R² 0.985, Acceptable)

- **12.11 Data**:
  - 2 Audit Programs per tenant:
    - `QPRG-2026-00001` (Annual Integrated QMS Audit Program 2026, Approved, $65,000 budget)
    - `QPRG-2026-00002` (Risk-Based Supplier Quality Audit Program 2026, Draft, $45,000 budget)
  - 3 Quality Audits per tenant:
    - `QAUD-2026-00001` (Internal QMS & Design Controls Audit, ISO 13485:2016, Closed, Audit Score: 94.50%)
    - `QAUD-2026-00002` (Critical Component Supplier On-Site Audit, ISO 9001:2015, Active Fieldwork)
    - `QAUD-2026-00003` (Annual Regulatory Preparedness Audit, FDA 21 CFR § 820, Scheduled)
  - 3 Audit Findings per tenant:
    - `QFND-2026-00001` (DCO Sign-off Missing Witness Signature, Minor Non-conformance, Verified Closed)
    - `QFND-2026-00002` (Calibration Traceability Certificate Expired, Major Non-conformance, Escalated to CAPA)
    - `QFND-2026-00003` (Supplier Quality Manual Review Interval Review, Opportunity for Improvement, Draft)
  - 2 Regulatory Inspection Hosts per tenant:
    - `QHST-2026-00001` (FDA QSIT Comprehensive Surveillance Inspection, On-Site Active with War Room requests)
    - `QHST-2026-00002` (BSI Notified Body ISO 13485:2016 Recertification Audit, Announced Prep)

Seeder is 100% idempotent: subsequent runs check `.exists()` and skip existing records.

---

## Conventions & Gotchas

1. **Multi-Tenancy Isolation:**
   - Always filter querysets by `tenant=request.tenant`.
   - Use `quality_object(request, Model, pk, select_related=[...])` in views for consistent tenant checks and HTTP 404 responses.
   - Forms inherit from `QualityModelForm` which injects `tenant` and filters foreign key querysets. Cross-tenant foreign keys submitted in POST data are rejected with validation errors via `reject_foreign`.
2. **21 CFR § 820.30(j) Regulatory DHF Freeze:**
   - Projects with `dhf_locked=True` represent frozen design history files.
   - Any attempt to modify, delete, advance phase, add/edit/delete inputs, reviews, or verification protocols under a locked project is strictly rejected at the view and form validation layers.
3. **21 CFR § 820.30(e) Independent Reviewer Governance:**
   - Every formal design review requires an independent reviewer who does not have direct operational responsibility for the design under evaluation.
   - Form validation strictly prohibits `independent_reviewer == lead_reviewer` and `independent_reviewer == project.project_lead`.
4. **Auto-Synchronization of Verification Status:**
   - When a `DesignVerification` protocol achieves `pass_fail_result == "pass"` and `status == "passed"`, the `primary_input.status` automatically updates to `"verified"` and an `AuditLog` entry (`action="verify"`) is emitted.
   - Modifying a test from pass to fail or deleting a passing protocol automatically re-evaluates `primary_input.status` and reverts it to `"approved"` if no other passing tests exist.
5. **ISO 14971 Regulatory Safety Gates:**
   - `RiskAssessment.calculate_level(severity, probability)` enforces:
     - Unacceptable (Red): $S \times P \ge 15$
     - ALARP (Amber): $6 \le S \times P < 15$
     - Broadly Acceptable (Green): $S \times P < 6$
   - Safety Gate Invariant: Under ISO 14971 Clause 7.4/8, residual risks calculating to `unacceptable` CANNOT be marked `residual_risk_acceptable=True`. `save()` automatically sets `residual_risk_acceptable=False` when residual risk level is unacceptable.
   - Clinical Benefit-Risk Analysis (BRA): In the ALARP zone, marking `residual_risk_acceptable=True` requires documented `benefit_risk_justification`.
6. **21 CFR Part 11 Electronic Signature Integrity & Tampering Guards:**
   - Plans with `approved_signature` or `status in ("active", "archived")` and review records with `status == "approved"` cannot be modified directly via edit views. A new revision or milestone review must be created.
   - Deletion views record `write_audit_log` BEFORE calling `.delete()` to preserve the entity's `object_id` in audit records.
7. **Query Optimization in FMEA & Traceability Matrices:**
   - Plan detail view aggregates KPI counts into single `.aggregate(Count("id", filter=Q(...)))` calls.
   - Matrix views avoid standalone COUNT queries on already iterated querysets by using `len(assessments)`.
   - In exports, prefetch caches are preserved using `list(a.control_measures.all())` rather than `.exists()`.
8. **CAPA Lifecycle Governance (ISO 13485:2016 §8.5.2 / 21 CFR § 820.100):**
   - Direct transitions to `closed` are blocked on standard advance status endpoints. Closure must occur via `capa_investigation_close` with `@tenant_admin_required`, verification that `pending_actions_count == 0`, and timestamping `closed_at`.
   - Closed investigations cannot be modified, reopened, or deleted.
   - Child records (RCAs, Actions, Reviews) under a closed CAPA cannot be deleted or re-verified.
   - Parent CAPA immutability: Child forms (`RootCauseAnalysisForm`, `CapaActionForm`, `CapaEffectivenessReviewForm`) disallow reassigning parent `capa` on existing records.
   - Cross-record integrity: `CapaActionForm` validates that `root_cause.capa_id == capa.id`.
9. **CAPA Effectiveness Recurrence Safety Gate:**
   - Under 21 CFR § 820.100(a)(4), an effectiveness review CANNOT be marked `outcome="effective"` if `recurrence_observed=True`. Both `CapaEffectivenessReviewForm.clean()` and `capa_effectiveness_review_sign_off` enforce this rule unconditionally.
10. **Separation of Duties in Action Verification:**
    - `capa_action_verify` requires the action to be in `implemented` status and prevents the assignee (`assigned_to`) from self-verifying without tenant-admin privilege.
11. **Property Annotation Cache Pattern:**
    - Because `@property` methods override annotations in class descriptors, `CapaInvestigation.actions_count` and `pending_actions_count` inspect `self.__dict__` first. When pre-annotated on the queryset, zero additional queries are generated in list tables.
12. **Theme CSS Badges:**
    - Strictly use colour-named classes from `static/css/theme.css`: `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-slate`, `badge-muted`. Never use semantic names like `badge-success`, `badge-danger`, `badge-purple`, or `badge-blue`.
13. **Incoming Quality Control (IQC) Invariants (ISO 2859-1 / ANSI Z1.4):**
    - `IncomingInspectionLot.calculate_sample_size(lot_qty, level)` deterministically derives sample code letters and inspection sample sizes.
    - All measurement data ingestion must explicitly validate `math.isfinite(val)` to prevent `nan` or `inf` float poison from breaking Decimal model fields and SPC calculation routines.
    - Automated QMS Spine Spawning: Marking usage decision as rejected (`rework`, `scrap`, `quarantine`, `return_to_vendor`) automatically generates a `NonConformanceReport` (`QNCR-`) and a `QuarantineContainment` (`QHLD-`) hold.
    - Skip-Lot Logic: Consecutive accepted lots are tracked per supplier/item; reaching skip intervals allows lots to be usage-decided as `skip_lot_passed` without physical sampling.
    - Scalar FK Representation: `QualityReturnAuthorization.__str__` uses scalar `self.inspection_lot_id` rather than chained FK properties to eliminate N+1 queries during audit logging.
14. **In-Process Quality Control (IPQC) Invariants (AS9102 Rev C / CQI-8 / ISO 9001):**
    - Production Authorization Release Gate: Authorizing an FAI for production release (`first_article_inspection_release`) requires tenant-admin privileges, checks that status is `approved`, verifies that all characteristics are conforming (`characteristics_nonconforming_count == 0`), and transitions status atomically to `released_to_production`.
    - Automated SPC Excursion Detection: `ProcessParameterLog.save()` evaluates parameter measurements against USL/LSL and control limits, calculating sigma deviations and automatically flagging `out_of_control_excursion` or `warning_trend`, demanding documented containment actions.
    - Automated QMS NCR Escalation: In-process inspections with failed disposition (`escalate_to_ncr`) or critical defects link directly to `quality:non_conformance_report_detail` across list and detail interfaces.
    - CQI-8 Audit Score Clamping: `LayeredProcessAudit.save()` automatically computes compliance score percentage and clamps values between $0.00\%$ and $100.00\%$ to prevent division by zero or out-of-range scoring anomalies.
    - Server-Side User Attribution: Critical audit fields (`logged_by` on `ProcessParameterLog` and `approved_by` on `FirstArticleInspection`) are strictly excluded from edit forms and assigned server-side from `request.user` to prevent client-side credential spoofing.
15. **Final Quality Control & Outgoing Quality Control (FQC / OQC) Invariants:**
    - CoC Cryptographic Signing: `certificate_of_conformance_sign` requires tenant-admin permissions, locks approved/revoked records against re-signing, and binds critical document specs into the SHA-256 digest (`number:tenant_id:user_id:customer_id:item_code:lot_number:certified_quantity:specs:test_results:timestamp`).
    - Post-Signing Immutability: Editing or hard-deleting approved/signed Certificates of Conformance or authorized Quality Release Authorizations is strictly blocked to preserve non-repudiation and regulatory compliance audit trails.
    - Multi-Gate Outgoing Release: Quality releases enforce a 4-point verification gate (final inspection lot passed, zero open NCRs/CAPAs, packaging approved, CoC issued and signed) plus cross-record counterparty customer verification before shipment clearance.
    - Quarantine Hold Governance: Activating a hold on an inspection lot or release requires tenant-admin authority and a non-empty `hold_reason`. Releasing while on hold is prohibited.
    - OQC Hold Board Performance: KPI counts are computed on unsliced querysets before slicing `[:10]` previews, avoiding SQL subquery overhead and count truncation.
16. **Calibration & MSA Invariants (ISO 9001 §7.1.5 / ISO 17025 / AIAG MSA 4th Ed):**
    - Metrological Circular Dependency Prevention: An instrument cannot select itself as its own master reference standard (`reference_standard_parent`), and a gage cannot be included in its own calibration `standards_used`.
    - Calibration Completion Synchronization: Gages only transition status and recalibration due dates (`next_calibration_due = calibration_date + interval`) upon formal completion (`status == "completed"`). A failed calibration (`fail_out_of_tolerance`) immediately locks the gage in `quarantined_oot`.
    - OOT Reverse-Tracing Window: When creating an Out-of-Tolerance investigation, the initial suspect manufacturing window defaults between the last valid in-spec passing calibration date and the failure event date.
    - AIAG ANOVA Variance Decomposition: MSA Gage R&R calculates repeatability $EV$, reproducibility $AV$, total Gage R&R $GRR = \sqrt{EV^2 + AV^2}$, part variation $PV$, and total variation $TV = \sqrt{GRR^2 + PV^2}$. Acceptance evaluates $\%GRR = (GRR / TV) \times 100\%$ and $ndc = 1.41 \times (PV / GRR) \ge 5$.
    - CSV Formula Sanitization: All calibration and MSA CSV exports apply `_csv_safe` formula sanitization (leading quote neutralization for `=`, `+`, `-`, `@`, `\t`, `\r`) with `X-Content-Type-Options: nosniff`.
17. **Audit Management Invariants (ISO 19011:2018 / ISO 13485:2016 §8.2.4 / 21 CFR § 820.22):**
    - Auditor Independence Principle: Under ISO 19011:2018 §4(e), auditors must not audit their own work. In `AuditFindingVerifyForm` and `audit_finding_verify_close`, verification of remediation actions prohibits the finding's assignee (`assignee == request.user`) from self-verifying and closing their own audit finding unless overridden by tenant admin.
    - Dynamic Finding Counter Synchronization: `QualityAudit.sync_findings_counts()` recalculates `total_findings_count`, `open_findings_count`, and `critical_findings_count` across finding save and delete signals, ensuring audit-level KPI metrics never drift.
    - Deletion Cascade Recalculation: `AuditFinding.delete()` explicitly triggers `self.audit.sync_findings_counts()` so parent summary counters remain accurate upon deletion.
    - Overdue SLA Calculation Safety: `AuditFinding.is_overdue` strictly checks `status in ("draft", "issued", "escalated")` and `response_due_date < timezone.now().date()`, ensuring that findings with submitted remediation responses in verification or closed states are not falsely marked overdue.
    - Seamless QMS Spine CAPA Integration: `audit_finding_create_capa` auto-populates `CapaInvestigation` with `issue_summary`, `action_type="corrective"`, `source_type="internal_audit"`, `source_reference`, `risk_priority`, `quality_owner`, `lead_investigator`, and links back to the finding.
    - Inspection War Room Live Dispatching: `RegulatoryInspectionHost` supports structured JSON request dispatching (`war_room_requests`) capturing request number, topic, requested item, SME runner, status (`requested`, `retrieving`, `legal_review`, `ready_for_inspector`, `presented`), and delivery timestamps.

---

## Sidebar Wiring (`LIVE_LINKS`)

Wired in `apps/core/navigation.py`:

```python
LIVE_LINKS = {
    # ...
    "12.1": [
        "quality:controlled_document_list",
        "quality:document_archive_vault",
        "quality:document_change_order_list",
        "quality:electronic_signature_list",
        "quality:document_acknowledgment_list",
    ],
    "12.2": [
        "quality:design_project_list",
        "quality:design_input_list",
        "quality:design_review_list",
        "quality:design_verification_list",
        "quality:traceability_matrix",
    ],
    "12.3": [
        "quality:risk_management_plan_list",
        "quality:risk_assessment_list",
        "quality:risk_control_measure_list",
        "quality:fmea_matrix",
        "quality:risk_traceability_matrix",
    ],
    "12.4": [
        "quality:capa_investigation_list",
        "quality:root_cause_analysis_list",
        "quality:capa_action_list",
        "quality:capa_tracking_board",
        "quality:capa_effectiveness_review_list",
    ],
    "12.5": [
        "quality:non_conformance_report_list",
        "quality:quarantine_containment_list",
        "quality:mrb_disposition_list",
        "quality:process_deviation_list",
        "quality:ncr_analytics_dashboard",
    ],
    "12.6": [
        "quality:avl_directory",
        "quality:supplier_qualification_audit_list",
        "quality:supplier_quality_scorecard_list",
        "quality:supplier_corrective_action_list",
        "quality:supplier_change_notification_list",
    ],
    "12.7": [
        "quality:incoming_inspection_plan_list",
        "quality:incoming_inspection_lot_list",
        "quality:certificate_of_analysis_list",
        "quality:iqc_spc_dashboard",
        "quality:quality_return_authorization_list",
    ],
    "12.8": [
        "quality:process_parameter_log_list",
        "quality:first_article_inspection_list",
        "quality:in_process_inspection_list",
        "quality:spc_dashboard",
        "quality:layered_process_audit_list",
    ],
    "12.9": {
        "Final Inspection Protocols": "quality:final_inspection_lot_list",
        "Lot Sampling & Acceptance Testing": "quality:oqc_hold_board",
        "Certificate of Conformance (CoC)": "quality:certificate_of_conformance_list",
        "Packaging & Labeling Verification": "quality:packaging_label_verification_list",
        "Shipment Release & Traceability": "quality:quality_release_authorization_list",
    },
    "12.10": {
        "Calibration Schedule & Planning": "quality:calibration_gage_list",
        "Calibration Execution & Records": "quality:calibration_record_list",
        "Out-of-Tolerance (OOT) Handling": "quality:out_of_tolerance_investigation_list",
        "Measurement System Analysis (MSA / Gage R&R)": "quality:measurement_system_analysis_list",
        "Calibration Vendor Management": "quality:calibration_vendor_directory",
    },
    "12.11": {
        "Audit Program Planning": "quality:audit_program_list",
        "Audit Execution & Checklists": "quality:quality_audit_list",
        "Audit Findings & Reporting": "quality:audit_finding_list",
        "Corrective Action Tracking": "quality:audit_action_tracker",
        "Regulatory & Certification Audits": "quality:regulatory_inspection_host_list",
    },
    "12.13": {
        "Complaint Intake & Triage": "quality:customer_complaint_list",
        "Investigation & Root Cause Analysis": "quality:complaint_investigation_list",
        "Regulatory Reporting & Vigilance": "quality:regulatory_report_list",
        "Field Action & Recall Management": "quality:field_action_list",
        "Complaint Trending & Closure": "quality:complaint_trending_dashboard",
    },
}
```
