# Research — Sub-module 12.16: Environmental, Health & Safety (EHS) (Module 12 — Quality Management System, `quality`)

## Repo state checked first

- **`LIVE_LINKS` built in Module 12 so far (`apps/core/navigation.py`):**
  - `"12.1"` (Document Control & Management): `ControlledDocument`, `ElectronicSignatureRecord`, `DocumentAcknowledgment`, `DocumentChangeOrder`, Archive Vault
  - `"12.2"` (Design Controls & Development): `DesignProject`, `DesignInput`, `DesignReview`, `DesignVerification`, Traceability Matrix
  - `"12.3"` (Risk Management / ISO 14971): `RiskAssessment`, `RiskControlMeasure`, `RiskManagementPlan`, `RiskReviewRecord`, FMEA Matrix
  - `"12.4"` (Corrective & Preventive Action / CAPA): `CapaInvestigation`, `RootCauseAnalysis`, `CapaAction`, `CapaEffectivenessReview`, Tracking Board
  - `"12.5"` (Non-Conformance & Deviation Management): `NonConformanceReport`, `QuarantineContainment`, `MrbDisposition`, `ProcessDeviation`, Analytics Dashboard
  - `"12.6"` (Supplier & Vendor Quality Management): `SupplierQualificationAudit`, `SupplierQualityScorecard`, `SupplierCorrectiveAction`, `SupplierChangeNotification`, AVL Directory
  - `"12.7"` (Incoming Quality Control / IQC): `IncomingInspectionPlan`, `IncomingInspectionLot`, `CertificateOfAnalysis`, `QualityReturnAuthorization`, SPC Dashboard
  - `"12.8"` (In-Process Quality Control / IPQC): `ProcessParameterLog`, `FirstArticleInspection`, `InProcessInspection`, `LayeredProcessAudit`, SPC Dashboard
  - `"12.9"` (Final Quality Control / OQC): `FinalInspectionLot`, `CertificateOfConformance`, `PackagingLabelVerification`, `QualityReleaseAuthorization`, OQC Hold Board
  - `"12.10"` (Calibration & Measurement System Analysis): `CalibrationGage`, `CalibrationRecord`, `OutOfToleranceInvestigation`, `MeasurementSystemAnalysis`, Vendor Directory
  - `"12.11"` (Audit Management): `AuditProgram`, `QualityAudit`, `AuditFinding`, `RegulatoryInspectionHost`, Action Tracker
  - `"12.12"` (Training & Competency Management): `CompetencyMatrix`, `QualityTrainingCourse`, `TrainingEnrollment`, `CompetencyCertification`, Compliance Dashboard
  - `"12.13"` (Customer Complaints & Post-Market Surveillance): `CustomerComplaint`, `ComplaintInvestigation`, `RegulatoryReport`, `FieldAction`, Trending Dashboard
  - `"12.14"` (Management Review & Quality Planning): `QualityObjective`, `ManagementReview`, `ManagementReviewInput`, `ManagementReviewAction`, Planning Dashboard
- **Sibling models available to FK in `apps/quality/models/` (56 verified models):**
  - `ControlledDocument` (`QDOC-`): for binding Safety Data Sheets (SDSs), chemical hygiene plans, cleanroom SOPs, EHS policies, waste management procedures.
  - `ElectronicSignatureRecord` (`QSIG-`): 21 CFR Part 11 electronic signatures for EHS incident closures, cleanroom environmental batch releases, and hazardous waste manifest certifications.
  - `NonConformanceReport` (`QNCR-`): non-conformance records generated from cleanroom excursions, chemical leaks, or PPE compliance failures.
  - `ProcessDeviation` (`QDEV-`): environmental parameter deviations (temperature, humidity, air pressure spikes, particle count alerts).
  - `CapaInvestigation` (`QCAP-`): root cause analysis and corrective/preventive actions triggered by workplace injuries, repeated near-misses, or regulatory inspections.
  - `CalibrationGage` (`QGAG-`): airborne particle counters, microbial air samplers, hygrometers, thermometers, and differential pressure sensors utilized in environmental monitoring.
  - `QualityAudit` (`QAUD-`) & `AuditFinding` (`QFND-`): EHS inspections, safety walkthroughs, EPA/OSHA compliance audits, and ISO 14001 / ISO 45001 internal audits.
- **Spine entities verified to exist (`apps/core/models/`, `accounts`):**
  - `core.Tenant`: multi-tenant workspace isolation.
  - `core.OrgUnit`: facility, site, plant, laboratory, warehouse, or cleanroom department.
  - `core.Party` & `core.PartyRole`: chemical suppliers, licensed hazardous waste transporters, TSDF (Treatment, Storage, and Disposal Facility) operators, occupational medical clinics, regulatory enforcement agencies (OSHA, EPA).
  - `accounts.User` (`settings.AUTH_USER_MODEL`): reporting employee, safety officer, industrial hygienist, sampling technician, EHS manager, waste certifier.
- **Cross-module masters / unbuilt masters status (lessons L28, L29):**
  - Unbuilt masters: `Item`, `UOM`, `StockMove`, `LotSerial` (Module 5). Replaced with explicit tenant-scoped text/code fields: `chemical_code`, `chemical_name`, `lot_number`, `container_serial_number`, `storage_location_code`, `unit_of_measure`.
  - Financial ledger: Owned by `apps/accounting`. Disposal fees, remediation costs, and fines reference `accounting.GLAccount` or standard currency fields without recreating ledgers.
- **Prefix availability audit (repo-wide verified, 0 collisions across 13 apps & `contract-*.md`):**
  - `QHAZ`: **FREE** (Quality Hazardous Material / Chemical Inventory)
  - `QSIR`: **FREE** (Quality Safety Incident Report)
  - `QENV`: **FREE** (Quality Environmental Monitoring Log)
  - `QWST`: **FREE** (Quality Waste Disposal Manifest)

---

## Leaders surveyed (with source links)

1. **VelocityEHS** (formerly MSDSonline / Accelerate Platform) — *Market benchmark in chemical management, SDS indexing, secondary labeling, incident/near-miss reporting, and air/water/waste environmental compliance.*
   - Sources: [ehs.com - Chemical Management](https://www.ehs.com/solutions/chemical-management/), [ehs.com - Incident Management](https://www.ehs.com/solutions/health-safety/incident-management/), [ehs.com - Environmental Compliance](https://www.ehs.com/solutions/environmental-compliance/)
2. **Intelex Technologies** (Fortive) — *Enterprise leader in EHSQ software with integrated Safety Inspection Management, Near-Miss & Incident Investigation, Waste Tracking, and cleanroom/facility environmental compliance.*
   - Sources: [intelex.com - EHS Applications](https://www.intelex.com/applications/), [intelex.com - Inspection Management](https://www.intelex.com/applications/inspection-management/), [intelex.com - Incident Management](https://www.intelex.com/applications/incident-management/)
3. **Cority** (CorityOne / Cortex AI) — *Premier enterprise EHS platform renowned for Occupational Health (medical surveillance, audiometric/respiratory tests), Industrial Hygiene exposure monitoring, Waste & Emissions, and Chemical Inventory.*
   - Sources: [cority.com - Occupational Health](https://www.cority.com/solutions/occupational-health/), [cority.com - Safety Management](https://www.cority.com/solutions/safety/), [cority.com - Environmental & Waste](https://www.cority.com/solutions/environmental/)
4. **Enablon** (Wolters Kluwer) — *Tier-1 global EHS and operational risk management suite with hazardous chemical screening, BowTie/5-Whys incident investigations, and cradle-to-grave hazardous waste tracking (RCRA & EU WFD).*
   - Sources: [wolterskluwer.com - Enablon EHS](https://www.wolterskluwer.com/en/solutions/enablon), [wolterskluwer.com - Chemical Safety](https://www.wolterskluwer.com/en/solutions/enablon/chemical-management)
5. **Benchmark Gensuite** — *Frontline-oriented EHS and sustainability software with mobile safety walkthroughs, digital SDS OCR extraction, hazardous waste profiling, and AI ergonomic assessments.*
   - Sources: [benchmarkgensuite.com - Chemical Management](https://benchmarkgensuite.com/chemical-management-software/), [benchmarkgensuite.com - Safety & Ergonomics](https://benchmarkgensuite.com/safety-software/)
6. **ETQ Reliance EHS** (Hexagon) — *Life sciences and manufacturing QMS/EHS platform combining Incident Management, OSHA 300 / RIDDOR recordkeeping, Hazardous Waste Cradle-to-Grave tracking, and mobile EHS inspection checklists.*
   - Sources: [etq.com - Environmental Health and Safety Software](https://www.etq.com/solutions/ehs-software/)
7. **Sphera** (SpheraCloud) — *Industrial leader in chemical lifecycle management, pre-purchase approval, hazardous waste manifest tracking, First Report incident intake, and operational risk mitigation.*
   - Sources: [sphera.com - Chemical Management](https://sphera.com/chemical-management-software/), [sphera.com - Health and Safety Management](https://sphera.com/health-and-safety-management-software/)
8. **Quentic** (AMCS Group) — *Modular European/Global EHS platform for GHS/CLP Hazardous Chemicals, Mobile Safety Walkthroughs, Waste & Resource Streams, and Occupational Health check-up surveillance.*
   - Sources: [quentic.com - Hazardous Chemicals](https://www.quentic.com/software/hazardous-chemicals/), [quentic.com - Risks & Audits](https://www.quentic.com/software/risks-audits/), [quentic.com - Occupational Health](https://www.quentic.com/software/health-safety/)
9. **Novatek International** (NovEM Environmental Monitoring) & **TSI / Lighthouse Worldwide Solutions** — *Global standards for Cleanroom Environmental Monitoring Systems (EMS) under ISO 14644-1/2, EU GMP Annex 1, viable microbial tracking (settle plates, contact plates, air samplers), non-viable particle counting, and excursion investigations.*
   - Sources: [ntint.com - Environmental Monitoring](https://ntint.com/products/environmental-monitoring-software/), [tsi.com - Facility Monitoring Systems](https://www.tsi.com/solutions/facility-monitoring-systems/)

---

## Regulatory Alignment & Industry Standards Framework

A robust, enterprise-grade EHS sub-module must comply simultaneously with national statutory safety laws and international quality/environmental standards:

1. **OSHA (Occupational Safety and Health Administration - USA):**
   - **29 CFR 1910.1200 (Hazard Communication Standard / HazCom GHS):** Standardized 16-section Safety Data Sheets (SDSs), GHS pictograms, signal words, hazard/precautionary statements, secondary container labeling, chemical inventory indexing.
   - **29 CFR 1904 (Injury & Illness Recordkeeping):** OSHA Form 300 (Log of Work-Related Injuries and Illnesses), OSHA 300A (Summary), OSHA 301 (Injury and Illness Incident Report); DART rate (Days Away, Restricted, or Transferred); 8-hour fatality / 24-hour amputation/inpatient hospitalization reporting triggers.
   - **29 CFR 1910.132-138 (Personal Protective Equipment):** Hazard assessments, mandatory equipment selection (eye/face, head, foot, hand, respiratory), PPE compliance verification at incident time.
   - **29 CFR 1910.1000 (Air Contaminants / Permissible Exposure Limits):** OSHA PEL, NIOSH REL, ACGIH TLV (Threshold Limit Values), 8-hour Time-Weighted Average (TWA), Short-Term Exposure Limit (STEL), and Ceiling limits.
2. **ISO Standards (International Organization for Standardization):**
   - **ISO 14001:2015 (Environmental Management Systems):** Environmental aspects and impacts, compliance obligations, operational controls, incident and spill response, cradle-to-grave waste tracking.
   - **ISO 45001:2018 (Occupational Health & Safety Management Systems):** Hierarchy of controls (elimination, substitution, engineering, administrative, PPE), worker hazard reporting, near-miss logging, participatory investigations, corrective actions.
   - **ISO 14644-1:2015 & ISO 14644-2:2015 (Cleanrooms and Controlled Environments):** Particulate cleanliness classification (ISO Classes 1 through 9), monitoring particle sizes ($\ge 0.5\,\mu\text{m}$ and $\ge 5.0\,\mu\text{m}$), operational states (at-rest vs. in-operation), differential pressure, relative humidity, temperature alert/action thresholds.
3. **Life Sciences & Cleanroom Good Manufacturing Practice (GMP):**
   - **EU GMP Annex 1:2022 (Manufacture of Sterile Medicinal Products):** Cleanroom classification Grades A, B, C, D; total airborne particulate limits; viable microbiological monitoring (air sampling CFU/$\text{m}^3$, 90 mm settle plates, 55 mm contact plates, 5-finger glove prints); continuous particle monitoring; contamination excursion protocols.
   - **FDA 21 CFR Part 820 / QMSR (ISO 13485:2016 Clause 6.4):** Contamination control, environmental control of manufacturing spaces, health and cleanliness of personnel.
   - **FDA 21 CFR Part 11 / EU Annex 11:** Audit trails, dual electronic signatures, attribution, tamper-proof EHS and environmental log integrity.
4. **EPA & Hazardous Waste Regulatory Framework:**
   - **EPA RCRA (Resource Conservation and Recovery Act - 40 CFR Parts 260-273):** Hazardous waste determinations, EPA waste codes (D001 Ignitable, D002 Corrosive, D003 Reactive, D004-D043 Toxicity Characteristic, F-listed spent solvents, K-listed industrial, P-listed & U-listed discarded commercial chemicals).
   - **Uniform Hazardous Waste Manifest (EPA Form 8700-22):** Cradle-to-grave chain of custody tracking from generator facility through licensed transporter to designated TSDF (Treatment, Storage, and Disposal Facility).
   - **Accumulation Time Limits:** Large Quantity Generator (LQG: 90 days), Small Quantity Generator (SQG: 180 days), Very Small Quantity Generator (VSQG). Certificate of Disposal / Destruction verification.
   - **EU Waste Framework Directive (2008/98/EC) & Basel Convention:** Transboundary waste tracking, hazardous consignment notes.

---

## Feature catalog (this sub-module only)

### 1. Hazardous Material Management
- **SDS Library & Version Control** — Centralized cataloging of 16-section GHS Safety Data Sheets with issue date, revision date, 3-year expiry alerts, and electronic document attachment · seen in: VelocityEHS, Intelex, Cority, Sphera, Benchmark Gensuite · priority: `table-stakes` · spine: new table `HazardousMaterial`, reuses `quality.ControlledDocument` · buildable now.
- **GHS Hazard Classification & Pictograms** — Formal GHS hazard classes (explosive, flammable, oxidizer, gas under pressure, corrosive, toxic, irritant/sensitizer, carcinogen/health hazard, aquatic toxicity), signal word (Danger, Warning, None), hazard statements (H-codes), and precautionary statements (P-codes) · seen in: VelocityEHS, Quentic, Sphera, Enablon · priority: `table-stakes` · spine: `HazardousMaterial` choices & JSON/text fields · buildable now.
- **NFPA 704 Standard Fire Diamond Rating** — 0-4 numeric rating for Health, Flammability, and Instability/Reactivity, plus Special Hazard codes (OX, W, SA) for emergency first responders · seen in: VelocityEHS, Sphera, Benchmark Gensuite · priority: `common` · spine: `HazardousMaterial` fields · buildable now.
- **Chemical Inventory & Facility Storage Location** — Tracking of chemical trade name, chemical formula, CAS number, UN number, container size/type, physical state (liquid, solid, gas, aerosol), maximum quantity permitted, and storage location / OrgUnit · seen in: VelocityEHS, Intelex, Cority, Quentic · priority: `table-stakes` · spine: `HazardousMaterial`, FK `core.OrgUnit`, FK `core.Party` (supplier) · buildable now.
- **Occupational Exposure Limits (OEL / PEL / TLV)** — Monitoring of regulatory exposure limits (OSHA PEL, ACGIH TLV, NIOSH REL) including 8-hr Time-Weighted Average (TWA), Short-Term Exposure Limit (STEL), and Ceiling concentration limits with UOM (ppm, $\text{mg}/\text{m}^3$) · seen in: Cority, VelocityEHS, Enablon · priority: `common` · spine: `HazardousMaterial` fields · buildable now.
- **PPE Requirements & Compatibility Matrix** — Explicit personal protective equipment rules for handling (respirator cartridge type, glove material, eye protection, chemical apron), incompatible chemical classes (avoid storage with acids, oxidizers, water), and emergency spill response instructions · seen in: VelocityEHS, Quentic, Sphera · priority: `table-stakes` · spine: `HazardousMaterial` fields · buildable now.
- **Secondary Container GHS Label Generation** — Automatic generation of GHS workplace secondary container labels containing product identifier, pictograms, and hazard warnings · seen in: VelocityEHS, Benchmark Gensuite, Sphera · priority: `differentiator` · spine: template render / printable action · buildable now.

### 2. Workplace Safety Inspections & Incident Management
- **Workplace Safety Incident & Near-Miss Intake** — Standardized digital first report of injury/illness, near miss, unsafe condition, chemical spill, equipment damage, or cleanroom contamination event with date, time, location, affected employee, and witness statements · seen in: VelocityEHS, Intelex, Cority, ETQ Reliance, Sphera, Enablon · priority: `table-stakes` · spine: new table `SafetyIncident`, FK `core.OrgUnit`, FK `accounts.User` · buildable now.
- **OSHA 300 / 300A / 301 Recordability Determination** — Automated classification of recordable criteria under OSHA 29 CFR 1904: medical treatment beyond first aid, loss of consciousness, days away from work, job restriction/transfer, fatality, or occupational illness · seen in: Cority, VelocityEHS, Intelex, ETQ Reliance · priority: `table-stakes` · spine: `SafetyIncident` boolean and classification choices · buildable now.
- **Lost & Restricted Workday Tracking (DART Metrics)** — Logging of exact lost workdays, restricted duty days, date of return to full duty, and calculation inputs for Days Away, Restricted, or Transferred (DART) and OSHA Incident Rates · seen in: Cority, ETQ Reliance, VelocityEHS · priority: `table-stakes` · spine: `SafetyIncident` integer & date fields · buildable now.
- **Injury & Body Part Taxonomy** — Comprehensive classification of injured body parts (head, eyes, hands/fingers, back, lungs, multiple) and nature of injury/illness (burn, laceration, repetitive strain, chemical inhalation, fracture, dermatitis) · seen in: Cority, Intelex, Benchmark Gensuite · priority: `common` · spine: `SafetyIncident` choices · buildable now.
- **PPE Compliance Verification at Event** — Explicit verification of whether required PPE was donned, whether equipment failed or was inadequate, and immediate safety officer findings · seen in: Intelex, Benchmark Gensuite, Quentic · priority: `common` · spine: `SafetyIncident` choices & notes · buildable now.
- **Immediate Containment & Safety Action Logging** — Documenting immediate first aid, evacuation, equipment lock-out, spill kit deployment, or cleanroom isolation deployed immediately following an event · seen in: VelocityEHS, Sphera, Intelex · priority: `table-stakes` · spine: `SafetyIncident` text fields · buildable now.
- **Root Cause & CAPA Integration** — Structured root cause categorization (human error, equipment failure, procedure absent, training gap, ergonomics, environmental) and one-click escalation to formal CAPA (`QCAP-`) or Non-Conformance (`QNCR-`) · seen in: ETQ Reliance, Intelex, Cority, Enablon · priority: `table-stakes` · spine: `SafetyIncident`, FK `quality.CapaInvestigation`, FK `quality.NonConformanceReport` · buildable now.
- **Safety Rounds & Inspection Checklists** — Scheduled walkthrough inspections verifying emergency eyewash stations, fire extinguishers, chemical storage cabinets, and cleanroom airlocks · seen in: Intelex, Benchmark Gensuite, Quentic · priority: `common` · spine: leverages existing `quality.QualityAudit` (`QAUD-`) and `quality.AuditFinding` (`QFND-`) from sub-module 12.11 · verified built.

### 3. Environmental Monitoring
- **Cleanroom Classification & Operational State** — Tracking of controlled cleanroom zones by ISO 14644-1 cleanliness classification (ISO Class 3 through 9) and EU GMP Grades A, B, C, D under both "At Rest" and "In Operation" operational states · seen in: Novatek NovEM, TSI FMS, Lighthouse LMS, ETQ Reliance · priority: `table-stakes` · spine: new table `EnvironmentalMonitoringLog`, FK `core.OrgUnit` · buildable now.
- **Airborne Particle Count Monitoring ($\ge 0.5\,\mu\text{m}$ & $\ge 5.0\,\mu\text{m}$)** — Digital logging of non-viable optical particle counter readings per cubic meter ($\text{particles}/\text{m}^3$) or cubic foot ($\text{particles}/\text{ft}^3$), verifying compliance with maximum concentration limits · seen in: Novatek NovEM, TSI FMS, Lighthouse LMS · priority: `table-stakes` · spine: `EnvironmentalMonitoringLog` decimal & choice fields · buildable now.
- **Viable Microbial Monitoring (Air, Settle, Surface, Gloves)** — Quantitative tracking of microbial colony-forming units (CFU) across active air samplers ($\text{CFU}/\text{m}^3$), passive 90 mm settle plates ($\text{CFU}/4\text{hr}$), 55 mm contact surface plates ($\text{CFU}/\text{plate}$), and 5-finger glove prints · seen in: Novatek NovEM, ETQ Reliance, Intelex · priority: `table-stakes` · spine: `EnvironmentalMonitoringLog` fields · buildable now.
- **Physical Environmental Parameters (Pressure, Temp, RH)** — Recording room differential pressure (Pascals / in $\text{H}_2\text{O}$ across airlocks), ambient temperature ($^\circ\text{C}$), and relative humidity (%RH) with target values and tolerance bands · seen in: TSI FMS, Lighthouse LMS, Novatek NovEM, Cority · priority: `table-stakes` · spine: `EnvironmentalMonitoringLog` fields · buildable now.
- **Dual-Tier Alert & Action Limit Thresholds** — Configuration of alert levels (early warning requiring review) and action levels (regulatory limit requiring mandatory deviation/CAPA), with automatic excursion status calculation (`normal`, `alert_exceeded`, `action_exceeded`) · seen in: Novatek NovEM, TSI FMS, ETQ Reliance · priority: `table-stakes` · spine: `EnvironmentalMonitoringLog` threshold fields & computed evaluation · buildable now.
- **Monitoring Instrument & Gage Traceability** — Direct foreign key link to calibrated measuring instruments (particle counters, anemometers, microbial samplers) to confirm calibration validity at time of sampling · seen in: Novatek NovEM, ETQ Reliance, Intelex · priority: `common` · spine: `EnvironmentalMonitoringLog`, FK `quality.CalibrationGage` · buildable now.
- **Excursion Deviation & Investigation Escalation** — Direct cross-linking of action level breaches to `quality.ProcessDeviation` (`QDEV-`) or `quality.NonConformanceReport` (`QNCR-`) with containment and root cause tracking · seen in: Novatek NovEM, ETQ Reliance · priority: `table-stakes` · spine: `EnvironmentalMonitoringLog`, FK `quality.ProcessDeviation`, FK `quality.NonConformanceReport` · buildable now.

### 4. Waste Management & Disposal
- **Hazardous & Regulated Waste Stream Profiling** — Categorization of waste streams: EPA hazardous chemical waste, universal waste (batteries, lamps, mercury devices), biohazard/infectious medical waste, radioactive waste, non-hazardous industrial waste, and WEEE (electronic waste) · seen in: Cority, Intelex, Sphera, Enablon, Benchmark Gensuite · priority: `table-stakes` · spine: new table `WasteDisposalManifest`, choices · buildable now.
- **EPA Hazardous Waste Code Assignment** — Tracking of regulatory waste codes: Ignitable (D001), Corrosive (D002), Reactive (D003), Toxicity Characteristic (D004–D043), F-listed spent solvents (F001–F005), and P/U acute chemical wastes · seen in: Sphera, VelocityEHS, Enablon, Cority · priority: `table-stakes` · spine: `WasteDisposalManifest` code fields · buildable now.
- **Cradle-to-Grave Uniform Waste Manifest Tracking** — Complete digital tracking corresponding to EPA Form 8700-22 Uniform Hazardous Waste Manifest: Generator EPA ID, Manifest Tracking Number, container count/type (55-gal drums, IBC totes, cylinders, roll-offs), total quantity/weight with UOM, packaging group, and DOT proper shipping name · seen in: Sphera, Intelex, Cority, ETQ Reliance, Enablon · priority: `table-stakes` · spine: `WasteDisposalManifest` fields · buildable now.
- **Supply Chain Transporter & TSDF Facility Linkage** — Foreign key tracking to verified licensed waste transporter entities (`core.Party`) and designated Treatment, Storage, and Disposal Facilities (TSDF `core.Party`) with facility EPA IDs and state permit numbers · seen in: Sphera, Cority, Intelex, Enablon · priority: `table-stakes` · spine: `WasteDisposalManifest`, FK `core.Party` (transporter), FK `core.Party` (TSDF) · buildable now.
- **Discrepancy Reporting & Certificate of Destruction** — Capturing TSDF receipt discrepancies (weight variance $>10\%$, bulk variance $>1\%$, waste type mismatch), management method code (incineration, solvent recovery, wastewater treatment, secure chemical landfill), and digital Certificate of Disposal / Destruction number and date · seen in: Sphera, Cority, Intelex, Benchmark Gensuite · priority: `common` · spine: `WasteDisposalManifest` discrepancy & certificate fields · buildable now.
- **Generator Accumulation Time Limit Monitoring** — Real-time tracking of container accumulation start date against generator compliance timeframes (90 days for LQG, 180 days for SQG) to prevent statutory deadline overruns · seen in: Sphera, VelocityEHS, Cority · priority: `differentiator` · spine: `WasteDisposalManifest` date fields & computed status · buildable now.
- **Linked Hazardous Material Reference** — Optional foreign key link from waste manifest item back to the originating `HazardousMaterial` chemical record to maintain chemical lifecycle integrity · seen in: Sphera, VelocityEHS, Quentic · priority: `common` · spine: `WasteDisposalManifest`, FK `HazardousMaterial` · buildable now.

### 5. Occupational Health & Ergonomics
- **Workplace Injury & Illness Trending (OSHA Form 300A Metrics)** — Aggregation of recordable incidents, injury severity rates, lost workday rates, and DART metrics by department, facility, and time period · seen in: Cority, Intelex, VelocityEHS, ETQ Reliance · priority: `table-stakes` · spine: aggregated from `SafetyIncident` · buildable now via views/analytics.
- **Ergonomic Hazard & Workstation Assessment** — Structured physical risk evaluations (manual material handling, repetitive motion, awkward postures, vibration, lifting index) evaluating workstation design against NIOSH, RULA (Rapid Upper Limb Assessment), or REBA (Rapid Entire Body Assessment) scoring · seen in: Benchmark Gensuite, Cority, VelocityEHS · priority: `common` · spine: mapped to `SafetyIncident` root causes & deferred to stand-alone assessment model · deferred.
- **Medical Surveillance & Health Monitoring Protocols** — Tracking baseline, periodic, and exit medical examinations for workers exposed to hazardous agents (audiometric hearing tests for noise $>85\,\text{dBA}$, spirometry respiratory protection clearance, blood lead/solvent biological monitoring, cleanroom gowning health clearances) · seen in: Cority, Quentic, Intelex · priority: `common` · spine: linked to `HazardousMaterial` exposure triggers & deferred to stand-alone surveillance pass · deferred.
- **Return-to-Work & Modified Duty Management** — Clinical case management tracking physician clearance, restricted duty restrictions, physical therapy milestones, and return-to-full-duty dates · seen in: Cority, Intelex, ETQ Reliance · priority: `common` · spine: captured within `SafetyIncident` restricted work days · buildable now.

### Beyond the bullets
- **Electronic Signature & 21 CFR Part 11 Sign-off** — Dual e-signature authorization (author and EHS officer) for incident closure, cleanroom environmental release, and hazardous waste manifest certification · seen in: ETQ Reliance, Novatek, Intelex · priority: `table-stakes` · spine: reuses `quality.ElectronicSignatureRecord` (`QSIG-`) · buildable now.
- **EHS Dashboard & Executive Leading/Lagging Indicators** — Unified command center displaying active open incidents, near-miss ratios, cleanroom excursions, expiring SDS sheets, and pending waste manifests awaiting TSDF confirmation · seen in: Cority, VelocityEHS, Intelex, Sphera, Benchmark Gensuite · priority: `table-stakes` · spine: dedicated dashboard view & HTMX widgets · buildable now.

---

## Recommended build scope (this pass — 4 models)

To establish an authoritative, fully functional EHS capability that integrates seamlessly with the rest of NavERP without bloated multi-table overhead, we recommend exactly **4 core models** subclassing `TenantNumbered` in package `apps/quality/models/EhsManagement/`:

```
apps/quality/
  models/EhsManagement/
    HazardousMaterials.py            # HazardousMaterial (QHAZ-)
    SafetyIncidents.py               # SafetyIncident (QSIR-)
    EnvironmentalMonitoringLogs.py   # EnvironmentalMonitoringLog (QENV-)
    WasteDisposalManifests.py        # WasteDisposalManifest (QWST-)
```

### 1. `HazardousMaterial` [Prefix: `QHAZ-`]
- **Domain Focus:** Hazardous Material Management, GHS SDS chemical catalog, NFPA hazard ratings, storage locations, exposure limits, and PPE requirements.
- **Key Fields & Choices:**
  - Identification: `material_number` (auto `QHAZ-YYYYMM-XXXX`), `chemical_name` (CharField), `trade_name` (CharField, blank), `cas_number` (CharField, blank), `un_number` (CharField, blank), `chemical_formula` (CharField, blank).
  - SDS Document Control: `sds_revision` (CharField), `sds_issue_date` (DateField), `sds_expiry_date` (DateField), `sds_document` (FK `quality.ControlledDocument`, null/blank), `is_sds_current` (BooleanField).
  - Classification: `physical_state` (Choices: `liquid`, `solid`, `gas`, `aerosol`, `sludge`), `ghg_signal_word` (Choices: `danger`, `warning`, `none`), `ghs_pictograms` (CharField/JSON: exploding_bomb, flame, flame_over_circle, gas_cylinder, corrosion, skull_crossbones, health_hazard, exclamation_mark, environment).
  - NFPA 704 Diamond: `nfpa_health` (Integer 0-4), `nfpa_flammability` (Integer 0-4), `nfpa_instability` (Integer 0-4), `nfpa_special_hazard` (Choices: `none`, `ox`, `w_slash`, `sa`, `cor`, `bio`).
  - Exposure & Controls: `osha_pel` (CharField, blank), `acgih_tlv` (CharField, blank), `exposure_uom` (CharField, blank, e.g. ppm, mg/m3), `ppe_requirements` (TextField), `incompatible_materials` (TextField), `spill_cleanup_procedure` (TextField).
  - Storage & Organization: `org_unit` (FK `core.OrgUnit`), `storage_location_code` (CharField, e.g. "Cabinet-Flam-02"), `maximum_storage_quantity` (DecimalField), `quantity_uom` (CharField), `supplier` (FK `core.Party`, null/blank, role=supplier), `status` (Choices: `active`, `restricted`, `under_review`, `discontinued`).
  - Auditing: `managed_by` (FK `accounts.User`), `created_at`, `updated_at`.
- **Verified FKs:** `core.Tenant`, `core.OrgUnit`, `quality.ControlledDocument`, `core.Party`, `accounts.User`.

### 2. `SafetyIncident` [Prefix: `QSIR-`]
- **Domain Focus:** Workplace Safety Inspections, Near-Miss Reporting, Injury & Illness Tracking, OSHA 300 Recordability, Lost Workdays, and CAPA Escalation.
- **Key Fields & Choices:**
  - Identification: `incident_number` (auto `QSIR-YYYYMM-XXXX`), `title` (CharField), `incident_date` (DateTimeField), `report_date` (DateField).
  - Classification: `incident_type` (Choices: `injury_illness`, `near_miss`, `hazardous_condition`, `chemical_spill`, `fire_explosion`, `property_damage`, `cleanroom_breach`), `severity` (Choices: `minor`, `moderate`, `severe`, `critical`, `fatal`), `status` (Choices: `reported`, `investigating`, `under_review`, `capa_pending`, `closed`, `cancelled`).
  - Location & Parties: `org_unit` (FK `core.OrgUnit`), `location_details` (CharField, e.g. "Cleanroom B Airlock 3"), `reported_by` (FK `accounts.User`), `affected_person` (FK `accounts.User`, null/blank), `affected_party_name` (CharField, blank, for contractors/visitors), `affected_party_type` (Choices: `employee`, `contractor`, `visitor`, `temporary_worker`).
  - Injury & Health Details: `nature_of_injury` (Choices: `none`, `strain_sprain`, `laceration_cut`, `burn_heat_chemical`, `fracture`, `contusion_bruise`, `eye_injury`, `inhalation_respiratory`, `skin_irritation`, `hearing_impact`, `other`), `body_part_affected` (Choices: `none`, `head_face`, `eyes`, `hands_fingers`, `arms_shoulders`, `back_spine`, `legs_knees`, `feet_toes`, `respiratory_system`, `multiple`), `medical_treatment_level` (Choices: `none`, `first_aid_only`, `clinic_visit`, `emergency_room`, `hospitalization`).
  - OSHA 300 Metrics: `is_osha_recordable` (BooleanField), `osha_classification` (Choices: `non_recordable`, `first_aid`, `days_away_from_work`, `job_transfer_restriction`, `other_recordable_case`), `lost_workdays_count` (PositiveIntegerField, default 0), `restricted_workdays_count` (PositiveIntegerField, default 0), `date_returned_to_work` (DateField, null/blank).
  - Safety & PPE Controls: `ppe_compliance_status` (Choices: `compliant`, `non_compliant`, `inadequate_ppe`, `not_applicable`), `ppe_notes` (TextField, blank), `immediate_actions_taken` (TextField).
  - Investigation & RCA: `lead_investigator` (FK `accounts.User`, null/blank), `root_cause_category` (Choices: `human_factors`, `equipment_failure`, `procedure_gap`, `training_deficiency`, `ergonomic_strain`, `environmental_hazard`, `inadequate_ppe`, `under_investigation`), `investigation_findings` (TextField, blank).
  - Sibling Integration: `capa_investigation` (FK `quality.CapaInvestigation`, null/blank), `non_conformance_report` (FK `quality.NonConformanceReport`, null/blank).
- **Verified FKs:** `core.Tenant`, `core.OrgUnit`, `accounts.User` (reporter, affected person, investigator), `quality.CapaInvestigation`, `quality.NonConformanceReport`.

### 3. `EnvironmentalMonitoringLog` [Prefix: `QENV-`]
- **Domain Focus:** Cleanroom classification, continuous particulate counts, microbial monitoring (air/settle/surface), physical climate parameters (pressure/temp/humidity), dual alert/action thresholds, and excursion containment.
- **Key Fields & Choices:**
  - Identification: `log_number` (auto `QENV-YYYYMM-XXXX`), `sampling_timestamp` (DateTimeField), `sampling_point_id` (CharField, e.g. "CR-ISO7-ZONE-B4").
  - Cleanroom Classification: `org_unit` (FK `core.OrgUnit`), `cleanroom_class` (Choices: `iso_class_3`, `iso_class_4`, `iso_class_5`, `iso_class_6`, `iso_class_7`, `iso_class_8`, `iso_class_9`, `unclassified_controlled`), `operational_state` (Choices: `at_rest`, `in_operation`).
  - Monitoring Category: `monitoring_category` (Choices: `airborne_particles_0_5um`, `airborne_particles_5_0um`, `viable_air_microbial`, `viable_settle_plate`, `viable_surface_contact`, `viable_glove_print`, `differential_pressure`, `temperature`, `relative_humidity`).
  - Measured Metrics: `parameter_name` (CharField), `measured_value` (DecimalField), `unit_of_measure` (Choices: `particles_m3`, `particles_ft3`, `cfu_m3`, `cfu_plate`, `pascals`, `celsius`, `percent_rh`).
  - Threshold Standards: `target_nominal_value` (DecimalField, null/blank), `lower_alert_limit` (DecimalField, null/blank), `upper_alert_limit` (DecimalField, null/blank), `lower_action_limit` (DecimalField, null/blank), `upper_action_limit` (DecimalField, null/blank).
  - Evaluation & Excursion: `evaluation_status` (Choices: `normal`, `alert_exceeded`, `action_exceeded`, `invalid_sample`), `excursion_details` (TextField, blank), `immediate_containment_action` (TextField, blank).
  - Personnel & Equipment: `sampled_by` (FK `accounts.User`), `verified_by` (FK `accounts.User`, null/blank), `measurement_instrument` (FK `quality.CalibrationGage`, null/blank).
  - Sibling Integration: `process_deviation` (FK `quality.ProcessDeviation`, null/blank), `non_conformance_report` (FK `quality.NonConformanceReport`, null/blank), `capa_investigation` (FK `quality.CapaInvestigation`, null/blank).
- **Verified FKs:** `core.Tenant`, `core.OrgUnit`, `accounts.User` (sampler, verifier), `quality.CalibrationGage`, `quality.ProcessDeviation`, `quality.NonConformanceReport`, `quality.CapaInvestigation`.

### 4. `WasteDisposalManifest` [Prefix: `QWST-`]
- **Domain Focus:** Hazardous Waste Management, EPA RCRA Uniform Manifest tracking, cradle-to-grave TSDF disposal lifecycle, waste profiling, discrepancy handling, and destruction certificates.
- **Key Fields & Choices:**
  - Identification: `manifest_number` (auto `QWST-YYYYMM-XXXX`), `regulatory_manifest_id` (CharField, e.g. EPA Form 8700-22 tracking #), `manifest_type` (Choices: `hazardous_chemical`, `universal_waste`, `biohazard_infectious`, `radioactive`, `non_hazardous_industrial`, `electronic_weee`).
  - Generator Facility: `generator_org_unit` (FK `core.OrgUnit`), `generator_epa_id` (CharField), `accumulation_start_date` (DateField).
  - Waste Profile: `waste_description` (CharField, e.g. "Waste Flammable Liquid, N.O.S. (Acetone, Toluene)"), `epa_waste_codes` (CharField, e.g. "D001, F003"), `associated_hazardous_material` (FK `HazardousMaterial`, null/blank), `physical_state` (Choices: `liquid`, `solid`, `sludge`, `gas_cylinder`).
  - Hazard Characteristics: `is_ignitable` (BooleanField), `is_corrosive` (BooleanField), `is_reactive` (BooleanField), `is_toxic` (BooleanField).
  - Quantity & Packaging: `container_type` (Choices: `drum_55gal`, `tote_ibc`, `cylinder`, `box_fiberboard`, `tank_bulk`, `roll_off`), `container_count` (PositiveIntegerField), `quantity_value` (DecimalField), `quantity_uom` (Choices: `pounds`, `kilograms`, `gallons`, `liters`, `tons`).
  - Chain of Custody: `transporter` (FK `core.Party`, role=vendor/transporter), `transporter_epa_id` (CharField, blank), `tsdf_facility` (FK `core.Party`, role=vendor/disposal), `tsdf_epa_id` (CharField, blank), `shipment_date` (DateField), `tsdf_receipt_date` (DateField, null/blank).
  - Disposition Verification: `status` (Choices: `draft`, `scheduled`, `in_transit`, `received_by_tsdf`, `certified_disposed`, `discrepancy_flagged`), `management_method_code` (CharField, blank, e.g. "H040 Incineration", "H020 Solvent Recovery"), `certificate_of_disposal_number` (CharField, blank), `certificate_received_date` (DateField, null/blank), `discrepancy_details` (TextField, blank).
  - Authorization: `certifying_officer` (FK `accounts.User`), `created_at`, `updated_at`.
- **Verified FKs:** `core.Tenant`, `core.OrgUnit`, `HazardousMaterial`, `core.Party` (transporter, TSDF facility), `accounts.User`.

---

## Belongs to sibling sub-modules (parked, not scoped here)

- **General Internal & External Quality Audits** → Sibling sub-module **12.11 Audit Management** (`QualityAudit`, `AuditFinding`). General facility safety audit programs and ISO 14001 / ISO 45001 certification audit logs belong there.
- **Formal Root Cause Analysis Methodologies (5-Whys, Fishbone, RCA Action Plans)** → Sibling sub-module **12.4 Corrective & Preventive Action (CAPA)** (`RootCauseAnalysis`, `CapaAction`). `SafetyIncident` links to `CapaInvestigation` rather than duplicating the RCA engine.
- **Material Quarantine & Material Review Board (MRB) Segregation** → Sibling sub-module **12.5 Non-Conformance & Deviation Management** (`QuarantineContainment`, `MrbDisposition`).
- **Measuring Instrument Calibration & MSA Gage R&R** → Sibling sub-module **12.10 Calibration & Measurement System Analysis** (`CalibrationGage`, `CalibrationRecord`). `EnvironmentalMonitoringLog` links to `CalibrationGage`.
- **EHS Training Courses & Safety Certifications** → Sibling sub-module **12.12 Training & Competency Management** (`QualityTrainingCourse`, `CompetencyCertification`). Worker forklift licenses, OSHA 10/30-hour cards, and HazCom certifications belong there.
- **Manufacturing Batch Environmental Clearance** → Sibling sub-module **12.18 Traceability & Serialization** and **12.15 Process Validation**.

---

## Deferred (later passes / integrations)

1. **Standalone AI Ergonomic Video / Posture Motion Scoring Engine** — Computer vision or automated sensor ingestion analyzing RULA/REBA ergonomic angles from video feeds (seen in Benchmark Gensuite and VelocityEHS AI). Deferred to later enterprise AI expansion; currently supported via ergonomic root cause classification in `SafetyIncident`.
2. **Automated EPA e-Manifest XML / REST API EDI Gateway** — Direct electronic transmission to the US EPA RCRAInfo e-Manifest national database system via EPA CDX/REST APIs. Deferred to integration phase; supported natively via complete data capture in `WasteDisposalManifest`.
3. **Live SCADA / IoT Particle Counter & Sensor Telemetry Feed** — Continuous real-time MQTT/OPC-UA streaming from fixed cleanroom particle counters directly into `EnvironmentalMonitoringLog` without human validation. Deferred to IoT integration pass; manual entry and CSV batch upload supported immediately.
4. **Standalone Occupational Medical Surveillance Clinical Registry** — Dedicated audiogram decibel curve tracking, spirometry lung volume curves, and HIPAA/GDPR clinical medical records. Supported in this pass via `SafetyIncident` medical metrics, with dedicated clinical protocols scheduled for an occupational health specialized pass.
