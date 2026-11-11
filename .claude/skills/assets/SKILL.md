---
name: assets
description: Work on the Asset Management System (AMS / EAM) module (Module 11 — asset procurement & acquisition, physical inventory audits & cycle counts, location & spatial movement tracking, tool crib & equipment custody lending, asset loss/theft incident reporting and loss write-offs, hierarchical taxonomy classification, OEM equipment model specs, multi-criteria risk/criticality assessments, technical specification templates, multi-method depreciation calculation schedules, asset revaluations & impairment testing, physical/cost-center asset transfers, capitalization threshold policies, breakdown work requests & repair tickets, preventive maintenance recurrence schedules & meter triggers, vendor AMC/SLA service contracts, maintenance work history logs with GL posting, operational downtime logging with hourly loss calculation, Overall Equipment Effectiveness OEE tracking with TPM Six Big Losses, smart sub-meter energy & carbon readings with GHG Scope 1/2/3 footprints, multi-dimensional performance scorecards with MTBF/MTTR benchmarking, asset condition assessments with NDT inspections, continuous IoT telemetry readings with threshold anomaly detection, FMEA failure mode analysis with RPN risk matrix, metrology calibration records with tolerance verification, manufacturer/extended warranty management, warranty claim tracking with OEM defect resolution, industrial property & machinery casualty insurance policies, insurance claims with adjuster tracking, proof of loss, and indemnity settlements, asset disposal & retirement requests, appraisals, competitive resale listings, trade-in allowances, certified scrap/salvage with hazardous waste abatement and Certificate of Destruction COD tracking, and lease & rental contract management, ASC 842 / IFRS 16 Right-of-Use asset and lease liability amortization, contract modifications, early terminations, and discounted cash flow Lease vs. Buy decision modeling). Use when the user asks to add/change/debug anything under apps/assets or templates/assets, extend the assets seeder, touch assets sidebar wiring (LIVE_LINKS 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7, 11.8, 11.9, 11.10, 11.11), or invokes /assets.
---

# Asset Management System (AMS / EAM) Module (Module 11)

Comprehensive enterprise physical asset lifecycle and Enterprise Asset Management (EAM), spanning capital acquisition, physical intake inspection, balance sheet capitalization, barcode/RFID tracking, physical cycle count verification, room/bin/facility spatial movements, tool crib custody check-in/out lending, loss/theft incident reporting with write-off authorization, and end-of-life disposal/retirement through competitive resales, vendor trade-ins, and certified scrap/salvage recycling. Reuses the core spine (`accounting.FixedAsset`, `accounting.GLAccount`, `accounting.Currency`, `accounting.AssetDisposal`, `scm.PurchaseOrder`, `scm.Location`, `scm.Asset`, `core.Party`, `core.OrgUnit`).

- **App path:** `apps/assets/`
- **Templates:** `templates/assets/`
- **URL prefix:** `/assets/` (`app_name="assets"`)
- Mounted in `config/urls.py`; registered in `config/settings.py` `INSTALLED_APPS` as `apps.assets`.

---

## Sub-modules Overview

- **11.1 Asset Procurement & Acquisition**: Capital expenditure requisitions, dock intake inspection receipts, asset capitalization & CIP clearing, physical asset tagging & thermal barcode printing.
- **11.2 Asset Inventory & Tracking**: Scheduled cycle counts, wall-to-wall physical audits, discrepancy reconciliation, facility/room/bin spatial relocations, tool crib equipment check-in/out lending with electronic signatures, and lost/stolen incident reporting with loss write-offs.
- **11.3 Asset Classification & Categorization**: Hierarchies, UNSPSC taxonomy, manufacturer model specs, criticality scoring.
- **11.4 Asset Depreciation & Accounting**: Depreciation runs, revaluations, impairment testing, salvage adjustments (interconnected with Module 2 ledger).
- **11.5 Asset Maintenance & Repair**: Breakdown tickets, triage, work orders, preventive maintenance calendars, runtime meter triggers, vendor AMC/SLA agreements, and work history logs with wrench time, ISO failure codes, and GL cost accounting.
- **11.6 Asset Performance & Utilization**: Operational downtime logging with hourly financial loss, Overall Equipment Effectiveness (OEE) tracking with TPM Six Big Losses, smart sub-meter energy readings with GHG Scope 1/2/3 carbon footprint metrics, and multi-dimensional performance scorecards with MTBF/MTTR benchmarking.
- **11.7 Asset Reliability & Condition Monitoring**: Multi-technique non-destructive testing (NDT) condition assessments, continuous IoT & SCADA telemetry streaming with threshold anomaly alerts, FMEA failure mode cataloging with RPN risk matrix & RCM strategies, and metrology calibration records with automated drift/error calculation and corrective maintenance work order generation.
- **11.8 Warranty & Insurance Management**: Manufacturer OEM and extended warranty policies with meter/calendar limits and deductible tracking, warranty claim submissions with OEM defect resolution and net financial recovery, industrial property & machinery breakdown insurance policies with premium/limit tracking, and casualty insurance claims with adjuster assignments, proof-of-loss filings, salvage recovery, and direct indemnity settlements.
- **11.9 Asset Disposal & Retirement**: Asset decommissioning requests, technical & residual value appraisals, multi-channel disposal execution (competitive auctions / private resales with bid tracking, equipment vendor trade-ins with dealer allowance netting, and certified scrap/salvage de-manufacturing with EPA hazardous waste abatement compliance and Certificate of Destruction COD tracking).
- **11.10 Lease & Rental Management**: Master Lease Agreement (MLA) administration, ASC 842 / IFRS 16 statutory operating vs finance lease classification, actuarial amortization payment schedules with ROU asset depreciation and liability reduction, contract modifications/remeasurements, early buyouts and terminations, and discounted cash flow Lease vs. Buy total cost of ownership (TCO) and Net Advantage to Leasing (NAL) modeling.
- **11.11 Compliance & Regulatory Management**: Asset compliance frameworks, regulatory audits, operating permits & environmental licenses, and safety/compliance incident tracking.

---

## App Layout & Architecture

Backend layers follow the mandatory NavERP package structure (`models/`, `forms/`, `views/`, `urls/`):

```
apps/assets/
  models/
    _base.py                                  <- TenantOwned, TenantNumbered abstract base models
    AssetProcurement/                         <- Sub-module 11.1 models
      AssetRequisitions.py                    <- AssetRequisition [AREQ-]
      AssetAcquisitionReceipts.py             <- AssetAcquisitionReceipt [ARCV-]
      AssetCapitalizations.py                 <- AssetCapitalization [ACAP-]
      AssetTags.py                            <- AssetTag [ATAG-]
    AssetInventoryTracking/                   <- Sub-module 11.2 models
      AssetAudits.py                          <- AssetAudit [AAUD-]
      AssetMovementLogs.py                    <- AssetMovementLog [AMOV-]
      AssetCustodyLogs.py                     <- AssetCustodyLog [ACHK-]
      AssetIncidentReports.py                 <- AssetIncidentReport [AINC-]
    AssetClassification/                      <- Sub-module 11.3 models
      AssetCategories.py                      <- AssetCategory [ACAT-]
      AssetModels.py                          <- AssetModel [AMOD-]
      AssetCriticalityAssessments.py          <- AssetCriticalityAssessment [ACRT-]
      AssetSpecificationTemplates.py          <- AssetSpecificationTemplate [ASPC-]
    AssetDepreciation/                        <- Sub-module 11.4 models
      AssetDepreciationSchedules.py           <- AssetDepreciationSchedule [ADEP-]
      AssetRevaluations.py                    <- AssetRevaluation [AREV-]
      AssetTransfers.py                       <- AssetTransfer [AXFR-]
      CapitalizationPolicies.py               <- CapitalizationPolicy [ACTH-]
    AssetMaintenance/                         <- Sub-module 11.5 models
      AssetMaintenanceRequests.py             <- AssetMaintenanceRequest [AMRQ-]
      AssetMaintenanceSchedules.py            <- AssetMaintenanceSchedule [AMSC-]
      AssetServiceContracts.py                <- AssetServiceContract [ASVC-]
      AssetMaintenanceLogs.py                 <- AssetMaintenanceLog [AMLG-]
    AssetPerformance/                         <- Sub-module 11.6 models
      AssetDowntimeLogs.py                    <- AssetDowntimeLog [ADWN-]
      AssetOeeRecords.py                      <- AssetOeeRecord [AOEE-]
      AssetEnergyReadings.py                  <- AssetEnergyReading [AENG-]
      AssetPerformanceScorecards.py           <- AssetPerformanceScorecard [APSC-]
    AssetReliability/                         <- Sub-module 11.7 models
      AssetConditionAssessments.py            <- AssetConditionAssessment [ACAS-]
      AssetTelemetryReadings.py               <- AssetTelemetryReading [ATEL-]
      AssetFailureModes.py                    <- AssetFailureMode [AFMA-]
      AssetCalibrationRecords.py              <- AssetCalibrationRecord [ACAL-]
    AssetWarrantyInsurance/                   <- Sub-module 11.8 models
      AssetWarranties.py                      <- AssetWarranty [AWAR-]
      AssetWarrantyClaims.py                  <- AssetWarrantyClaim [AWCL-]
      AssetInsurancePolicies.py               <- AssetInsurancePolicy [AINS-]
      AssetInsuranceClaims.py                 <- AssetInsuranceClaim [AICL-]
    AssetDisposal/                            <- Sub-module 11.9 models
      AssetDisposalRequests.py                <- AssetDisposalRequest [ADSP-]
      AssetResaleListings.py                  <- AssetResaleListing [ARSL-]
      AssetTradeIns.py                        <- AssetTradeIn [ATIN-]
      AssetScrapSalvages.py                   <- AssetScrapSalvage [ASCR-]
    AssetCompliance/                          <- Sub-module 11.11 models
      AssetComplianceFrameworks.py            <- AssetComplianceFramework [ACF-]
      AssetComplianceAudits.py                <- AssetComplianceAudit [ACA-]
      AssetPermitLicenses.py                  <- AssetPermitLicense [APL-]
      AssetComplianceIncidents.py             <- AssetComplianceIncident [ACI-]
    __init__.py                               <- Re-exports all models
  forms/
    _common.py                                <- Base forms, TenantUniqueMixin, reject_foreign
    AssetProcurement/                         <- Sub-module 11.1 forms
      AssetRequisitions.py                    <- AssetRequisitionForm
      AssetAcquisitionReceipts.py             <- AssetAcquisitionReceiptForm
      AssetCapitalizations.py                 <- AssetCapitalizationForm
      AssetTags.py                            <- AssetTagForm
    AssetInventoryTracking/                   <- Sub-module 11.2 forms
      AssetAudits.py                          <- AssetAuditForm
      AssetMovementLogs.py                    <- AssetMovementLogForm
      AssetCustodyLogs.py                     <- AssetCustodyLogForm
      AssetIncidentReports.py                 <- AssetIncidentReportForm
    AssetClassification/                      <- Sub-module 11.3 forms
      AssetCategories.py                      <- AssetCategoryForm
      AssetModels.py                          <- AssetModelForm
      AssetCriticalityAssessments.py          <- AssetCriticalityAssessmentForm
      AssetSpecificationTemplates.py          <- AssetSpecificationTemplateForm
    AssetDepreciation/                        <- Sub-module 11.4 forms
      AssetDepreciationSchedules.py           <- AssetDepreciationScheduleForm
      AssetRevaluations.py                    <- AssetRevaluationForm
      AssetTransfers.py                       <- AssetTransferForm
      CapitalizationPolicies.py               <- CapitalizationPolicyForm
    AssetMaintenance/                         <- Sub-module 11.5 forms
      AssetMaintenanceRequests.py             <- AssetMaintenanceRequestForm, TriageForm, DispatchForm, ResolveForm, RejectForm
      AssetMaintenanceSchedules.py            <- AssetMaintenanceScheduleForm, RecordCompletionForm
      AssetServiceContracts.py                <- AssetServiceContractForm, RenewForm
      AssetMaintenanceLogs.py                 <- AssetMaintenanceLogForm
    AssetPerformance/                         <- Sub-module 11.6 forms
      AssetDowntimeLogs.py                    <- AssetDowntimeLogForm, AssetDowntimeLogResolveForm
      AssetOeeRecords.py                      <- AssetOeeRecordForm
      AssetEnergyReadings.py                  <- AssetEnergyReadingForm
      AssetPerformanceScorecards.py           <- AssetPerformanceScorecardForm
    AssetReliability/                         <- Sub-module 11.7 forms
      AssetConditionAssessments.py            <- AssetConditionAssessmentForm
      AssetTelemetryReadings.py               <- AssetTelemetryReadingForm
      AssetFailureModes.py                    <- AssetFailureModeForm
      AssetCalibrationRecords.py              <- AssetCalibrationRecordForm
    AssetWarrantyInsurance/                   <- Sub-module 11.8 forms
      AssetWarranties.py                      <- AssetWarrantyForm
      AssetWarrantyClaims.py                  <- AssetWarrantyClaimForm
      AssetInsurancePolicies.py               <- AssetInsurancePolicyForm
      AssetInsuranceClaims.py                 <- AssetInsuranceClaimForm
    AssetDisposal/                            <- Sub-module 11.9 forms
      AssetDisposalRequests.py                <- AssetDisposalRequestForm
      AssetResaleListings.py                  <- AssetResaleListingForm
      AssetTradeIns.py                        <- AssetTradeInForm
      AssetScrapSalvages.py                   <- AssetScrapSalvageForm
    AssetCompliance/                          <- Sub-module 11.11 forms
      AssetComplianceFrameworks.py            <- AssetComplianceFrameworkForm
      AssetComplianceAudits.py                <- AssetComplianceAuditForm
      AssetPermitLicenses.py                  <- AssetPermitLicenseForm
      AssetComplianceIncidents.py             <- AssetComplianceIncidentForm
    __init__.py                               <- Re-exports all forms
  views/
    _common.py                                <- Shared helpers (assets_scope, assets_object, assets_paginate)
    overview.py                               <- Asset Management Hub overview dashboard
    AssetProcurement/                         <- Sub-module 11.1 views
      AssetRequisitions.py                    <- Requisition CRUD + submit, approve, reject
      AssetAcquisitionReceipts.py             <- Receipt CRUD + inspect, quarantine
      AssetCapitalizations.py                 <- Capitalization CRUD + execute, reverse
      AssetTags.py                            <- Tag CRUD + mark_printed, affix, verify, print_label
    AssetInventoryTracking/                   <- Sub-module 11.2 views
      AssetAudits.py                          <- Audit CRUD + start, complete, reconcile, cancel
      AssetMovementLogs.py                    <- Movement CRUD + dispatch, receive, cancel
      AssetCustodyLogs.py                     <- Custody CRUD + checkin, extend, mark_lost
      AssetIncidentReports.py                 <- Incident CRUD + investigate, resolve_recovered, authorize_write_off, close
    AssetClassification/                      <- Sub-module 11.3 views
      AssetCategories.py                      <- Category CRUD
      AssetModels.py                          <- Model CRUD
      AssetCriticalityAssessments.py          <- Criticality CRUD + approve & sync to scm.Asset
      AssetSpecificationTemplates.py          <- Spec Template CRUD
    AssetDepreciation/                        <- Sub-module 11.4 views
      AssetDepreciationSchedules.py           <- Depreciation Schedule CRUD + calculate, post to GL
      AssetRevaluations.py                    <- Revaluation & Impairment CRUD + approve & apply
      AssetTransfers.py                       <- Asset Transfer CRUD + dispatch, complete & update assets
      CapitalizationPolicies.py               <- Capitalization Policy CRUD + interactive evaluator
    AssetMaintenance/                         <- Sub-module 11.5 views
      AssetMaintenanceRequests.py             <- Request CRUD + triage, dispatch, resolve, close, reject
      AssetMaintenanceSchedules.py            <- Schedule CRUD + pause, activate, generate_request, record_completion
      AssetServiceContracts.py                <- Contract CRUD + record_visit, renew, terminate
      AssetMaintenanceLogs.py                 <- Log CRUD + submit_review, approve, post_gl
    AssetPerformance/                         <- Sub-module 11.6 views
      AssetDowntimeLogs.py                    <- Downtime CRUD + resolve
      AssetOeeRecords.py                      <- OEE CRUD + finalize
      AssetEnergyReadings.py                  <- Energy CRUD + validate
      AssetPerformanceScorecards.py           <- Scorecard CRUD + publish
    AssetReliability/                         <- Sub-module 11.7 views
      AssetConditionAssessments.py            <- Assessment CRUD + complete, review, trigger_request
      AssetTelemetryReadings.py               <- Telemetry CRUD + flag_anomaly, trigger_request
      AssetFailureModes.py                    <- FMEA CRUD + activate, archive
      AssetCalibrationRecords.py              <- Calibration CRUD + quarantine
    AssetWarrantyInsurance/                   <- Sub-module 11.8 views
      AssetWarranties.py                      <- Warranty CRUD + activate, renew, void
      AssetWarrantyClaims.py                  <- Warranty Claim CRUD + submit, review, settle, reject
      AssetInsurancePolicies.py               <- Insurance Policy CRUD + activate, renew, cancel
      AssetInsuranceClaims.py                 <- Insurance Claim CRUD + assign_adjuster, file_proof, settle, deny
    AssetDisposal/                            <- Sub-module 11.9 views
      AssetDisposalRequests.py                <- Request CRUD + submit, appraise, approve, reject, complete
      AssetResaleListings.py                  <- Listing CRUD + record_bid, accept_sale, mark_paid, mark_delivered
      AssetTradeIns.py                        <- Trade-In CRUD + surrender, settle
      AssetScrapSalvages.py                   <- Scrap/Salvage CRUD + certify_abatement, record_cod, settle
    AssetCompliance/                          <- Sub-module 11.11 views
      AssetComplianceFrameworks.py            <- Framework CRUD + delete (ProtectedError handled, tenant admin)
      AssetComplianceAudits.py                <- Audit CRUD + start, complete, delete (status guarded, tenant admin)
      AssetPermitLicenses.py                  <- Permit CRUD + renew (status guarded), delete (tenant admin)
      AssetComplianceIncidents.py             <- Incident CRUD + resolve, close, delete (status guarded, tenant admin)
    __init__.py                               <- Re-exports all views
  urls/
    AssetProcurement/                         <- Sub-module 11.1 URL route definitions
      AssetRequisitions.py
      AssetAcquisitionReceipts.py
      AssetCapitalizations.py
      AssetTags.py
    AssetInventoryTracking/                   <- Sub-module 11.2 URL route definitions
      AssetAudits.py
      AssetMovementLogs.py
      AssetCustodyLogs.py
      AssetIncidentReports.py
    AssetClassification/                      <- Sub-module 11.3 URL route definitions
      AssetCategories.py
      AssetModels.py
      AssetCriticalityAssessments.py
      AssetSpecificationTemplates.py
    AssetDepreciation/                        <- Sub-module 11.4 URL route definitions
      AssetDepreciationSchedules.py
      AssetRevaluations.py
      AssetTransfers.py
      CapitalizationPolicies.py
    AssetMaintenance/                         <- Sub-module 11.5 URL route definitions
      AssetMaintenanceRequests.py
      AssetMaintenanceSchedules.py
      AssetServiceContracts.py
      AssetMaintenanceLogs.py
    AssetPerformance/                         <- Sub-module 11.6 URL route definitions
      AssetDowntimeLogs.py
      AssetOeeRecords.py
      AssetEnergyReadings.py
      AssetPerformanceScorecards.py
    AssetReliability/                         <- Sub-module 11.7 URL route definitions
      AssetConditionAssessments.py
      AssetTelemetryReadings.py
      AssetFailureModes.py
      AssetCalibrationRecords.py
    AssetWarrantyInsurance/                   <- Sub-module 11.8 URL route definitions
      AssetWarranties.py
      AssetWarrantyClaims.py
      AssetInsurancePolicies.py
      AssetInsuranceClaims.py
    AssetDisposal/                            <- Sub-module 11.9 URL route definitions
      AssetDisposalRequests.py
      AssetResaleListings.py
      AssetTradeIns.py
      AssetScrapSalvages.py
    AssetCompliance/                          <- Sub-module 11.11 URL route definitions
      AssetComplianceFrameworks.py
      AssetComplianceAudits.py
      AssetPermitLicenses.py
      AssetComplianceIncidents.py
    __init__.py                               <- Root URL router concatenating all packages
  management/commands/
    seed_assets.py                            <- Idempotent demonstration data seeder (11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7, 11.8 & 11.9)
  tests/
    conftest.py                               <- Shared fixtures (tenants, GL accounts, POs, locations, assets, maintenance, performance, reliability, warranties, policies, disposal)
    test_assetprocurement_models.py           <- 11.1 Model invariants, methods, auto-numbering, constraints
    test_assetprocurement_forms.py            <- 11.1 Form validation, clean rules, mass-assignment exclusion
    test_assetprocurement_views.py            <- 11.1 View responses, filtering, guards, actions, execution
    test_assetprocurement_security.py         <- 11.1 IDOR (404), RBAC (403), method restriction (405)
    test_assetinventorytracking_models.py     <- 11.2 Model invariants, sequences, status badges, constraints
    test_assetinventorytracking_forms.py      <- 11.2 Form validation, system field exclusion, reject_foreign
    test_assetinventorytracking_views.py      <- 11.2 View context contracts, filters, lifecycle actions
    test_assetinventorytracking_security.py   <- 11.2 IDOR (404), RBAC admin gates (403), method safety (405)
    test_assetclassification_models.py        <- 11.3 Model invariants, hierarchy cycles, composite scoring
    test_assetclassification_forms.py         <- 11.3 Form validation, mass-assignment exclusions, reject_foreign
    test_assetclassification_views.py         <- 11.3 View context contracts, filters, status guards, sync
    test_assetclassification_security.py      <- 11.3 IDOR (404), RBAC gates (403), method safety (405)
    test_assetdepreciation_models.py          <- 11.4 Multi-method formulas, GL journal generation, step-up/impairment
    test_assetdepreciation_forms.py           <- 11.4 Form validations, system exclusions, reject_foreign
    test_assetdepreciation_views.py           <- 11.4 View contracts, filters, status guards, actions, evaluator
    test_assetdepreciation_security.py        <- 11.4 IDOR (404), RBAC admin gates (403), mass-assignment, audits
    test_asset_maintenance_models.py          <- 11.5 Model invariants, auto-numbering, lifecycle flows, cost calculation
    test_asset_maintenance_forms.py           <- 11.5 Form validations, tenant kwargs, foreign key isolation
    test_asset_maintenance_views.py           <- 11.5 View contracts, filters, action endpoints, pagination
    test_asset_maintenance_security.py        <- 11.5 IDOR (404), RBAC gates (403), cross-tenant FK injection, status guards
    test_assetperformance_models.py           <- 11.6 Model invariants, OEE formulas, energy intensity, scorecards
    test_assetperformance_forms.py            <- 11.6 Form validation, time/power factor bounds, reject_foreign
    test_assetperformance_views.py            <- 11.6 View contracts, page_obj, state actions, delete protection
    test_assetperformance_security.py         <- 11.6 IDOR (404), list isolation, unauthenticated redirect (302)
    test_asset_reliability_models.py          <- 11.7 Model invariants, deviation math, RPN risk matrix, metrology errors
    test_asset_reliability_forms.py           <- 11.7 Form validation, user/vendor scoping, reject_foreign
    test_asset_reliability_views.py           <- 11.7 View context contracts, filters, aggregates, maintenance triggers
    test_asset_reliability_security.py        <- 11.7 IDOR (404), RBAC admin gates (403), audit logging, FK injection
    test_assetwarrantyinsurance_models.py     <- 11.8 Model invariants, date helpers, net recovery, CSS badge mappings
    test_assetwarrantyinsurance_forms.py      <- 11.8 Form validation, date order checks, reject_foreign, mass assignment
    test_assetwarrantyinsurance_views.py      <- 11.8 View contracts, filters, settlement math, status guards, actions
    test_assetwarrantyinsurance_security.py   <- 11.8 IDOR (404), RBAC gates, numeric hardening (L35), state tampering
    test_assetdisposal_models.py              <- 11.9 Model invariants, gain/loss math, sequences, badges
    test_assetdisposal_forms.py               <- 11.9 Form validations, clean rules, tenant foreign key isolation
    test_assetdisposal_views.py               <- 11.9 View contracts, filters, status guards, settlements
    test_assetdisposal_security.py            <- 11.9 IDOR (404), RBAC gates, mass assignment, idempotency
    test_compliance_models.py                 <- 11.11 Model invariants, auto-numbering, properties, constraints
    test_compliance_forms.py                  <- 11.11 Form validation, mass-assignment exclusion, reject_foreign
    test_compliance_views.py                  <- 11.11 View context contracts, filters, status guards, actions
    test_compliance_security.py               <- 11.11 IDOR (404), RBAC gates (403), method safety (405), audits
```

---

## Models & Data Dictionary (11.1, 11.2, 11.3)

### 11.1 Asset Procurement
1. **`AssetRequisition`** (`AREQ-`): CapEx purchase requests with budget codes, segregation of duties approval, and PO conversion.
2. **`AssetAcquisitionReceipt`** (`ARCV-`): Dock receiving and condition inspection logging.
3. **`AssetCapitalization`** (`ACAP-`): CapEx capitalization event allocating purchase/freight/install costs into accounting FixedAsset.
4. **`AssetTag`** (`ATAG-`): Barcode/RFID physical asset tags with verification scanners.

### 11.2 Asset Inventory & Tracking
1. **`AssetAudit`** (`AAUD-`):
   - **Fields:** `number`, `title`, `audit_type` (`wall_to_wall`, `cycle_count`, `spot_check`, `annual`), `target_location` (FK `scm.Location`), `target_org_unit` (FK `core.OrgUnit`), `asset_category`, `lead_auditor` / `supervisor` (FK `User`), `scheduled_date`, `is_blind_count` (Bool), `expected_asset_count`, `scanned_asset_count`, `matched_asset_count`, `missing_asset_count`, `discrepancy_count`, `discrepancy_notes`, `reconciliation_action` (`pending_review`, `no_action_needed`, `location_updated`, `incident_initiated`, `custodian_reassigned`), `status` (`scheduled`, `in_progress`, `completed`, `reconciled`, `cancelled`).
   - **Invariants:** Discrepancy reconciliation requires `@tenant_admin_required`. Deletion restricted to uncommitted audits.
2. **`AssetMovementLog`** (`AMOV-`):
   - **Fields:** `number`, `title`, `asset` (FK `scm.Asset`), `movement_type` (`inter_facility_transfer`, `room_relocation`, `department_transfer`, `offsite_maintenance`), `from_location` / `to_location` (FK `scm.Location`), `from_org_unit` / `to_org_unit` (FK `core.OrgUnit`), `from_room_bin` / `to_room_bin`, `from_custodian` / `to_custodian` (FK `core.Party`), `gps_latitude`, `gps_longitude`, `gps_address`, `carrier_name`, `tracking_number`, `status` (`draft`, `requested`, `dispatched`, `received`, `cancelled`), `dispatch_date` / `dispatched_by`, `received_date` / `received_by`, `condition_on_receipt`.
   - **Invariants:** Receiving updates operational `scm.Asset.location` atomically. Editing restricted to `draft` and `requested` status.
3. **`AssetCustodyLog`** (`ACHK-`):
   - **Fields:** `number`, `asset` (FK `scm.Asset`), `action_type` (`checkout`, `checkin`, `permanent_assignment`, `reassignment`), `borrower` (FK `core.Party`), `borrower_name`, `crib_attendant` (FK `User`), `purpose`, `work_order_reference`, `project_reference`, `checkout_date`, `expected_return_date`, `actual_return_date`, `checkout_condition`, `return_condition`, `condition_notes`, `borrower_signature_acknowledged` (Bool), `status` (`active_loan`, `returned`, `overdue`, `damaged_returned`, `unreturned_lost`).
   - **Invariants:** View-level delete guard blocks deletion of active loans. Overdue loans auto-detected on list view with `.exists()` check.
4. **`AssetIncidentReport`** (`AINC-`):
   - **Fields:** `number`, `title`, `asset` (FK `scm.Asset`), `incident_type` (`lost`, `stolen`, `damaged_beyond_repair`, `missing_in_audit`, `vandalism`, `natural_disaster`), `severity` (`low`, `medium`, `high`, `critical`), `status` (`reported`, `under_investigation`, `confirmed_lost`, `recovered`, `write_off_pending`, `written_off`, `closed`), `resolution_action` (`pending`, `recovered`, `replacement_sourced`, `written_off`, `unresolved_closed`), `incident_date`, `last_known_location` (FK `scm.Location`), `custodian_at_loss` (FK `core.Party`), `investigator` (FK `User`), `police_report_filed`, `police_report_number`, `police_precinct`, `police_filing_date`, `insurance_claim_filed`, `insurance_carrier`, `insurance_claim_number`, `estimated_loss_value`, `insurance_claimed_amount`, `insurance_settled_amount`, `incident_description`, `investigation_findings`, `write_off_authorized_by`, `write_off_date`, `write_off_notes`.
   - **Invariants:** Write-off authorization requires `@tenant_admin_required`, sets operational `scm.Asset.status = 'disposed'`, and is guarded in UI via `request.user.is_tenant_admin`.

### 11.3 Asset Classification & Categorization
1. **`AssetCategory`** (`ACAT-`):
   - **Fields:** `code`, `name`, `parent` (FK `self`), `category_type` (`machinery`, `facility`, `vehicle`, `it_hardware`, `tooling`, `office`), `default_depreciation_method` (`straight_line`, `reducing_balance`, `units_of_production`), `default_useful_life_months`, `unspsc_code`, `iso_55000_class`, `is_active`, `description`.
   - **Invariants:** Cycle detection in `clean()` (prevents self-parenting and recursive loops), tenant isolation enforcement in hierarchy traversal, uppercase `code`.
2. **`AssetModel`** (`AMOD-`):
   - **Fields:** `model_number`, `name`, `category` (FK `AssetCategory`), `manufacturer` (FK `core.Party`), `manufacturer_name_fallback`, `estimated_replacement_cost` (non-negative `MinValueValidator`), `expected_life_years`, `warranty_duration_months`, `metering_type` (`none`, `hours`, `odometer_km`, `cycles`), `model_status` (`active`, `phase_out`, `obsolete`).
   - **Properties:** `display_manufacturer` with Party name and fallback text resolution.
3. **`AssetCriticalityAssessment`** (`ACRT-`):
   - **Fields:** `number`, `asset` (FK `scm.Asset`), `assessor` (FK `core.Party`), `assessment_date`, `production_impact`, `safety_impact`, `environmental_impact`, `regulatory_impact`, `maintenance_cost_impact` (scores 1-5), `single_point_of_failure` (Bool), `composite_score`, `abc_rating` (`A`, `B`, `C`), `assessment_status` (`draft`, `approved`, `superseded`), `approved_by` (FK `User`), `approved_at`, `notes`.
   - **Invariants:** Composite scoring with +5 SPOF bonus and auto-tier derivation. Approval requires `@tenant_admin_required`, supersedes prior approved assessments for the asset, and syncs operational `scm.Asset.criticality` (`critical`, `high`, `medium`, `low`) inside an atomic transaction. Status guards prevent edit/delete of `approved`/`superseded` records.
4. **`AssetSpecificationTemplate`** (`ASPC-`):
   - **Fields:** `number`, `category` (FK `AssetCategory`), `model` (FK `AssetModel`), `attribute_name`, `attribute_key` (snake_case slug), `data_type` (`text`, `numeric`, `boolean`, `date`, `select`), `unit_of_measure`, `min_numeric_value`, `max_numeric_value`, `validation_regex`, `select_choices`, `is_required`, `is_searchable`, `is_filterable`.
   - **Invariants:** Must attach to either Category or Model. Validates regex syntax with `re.compile()` in `clean()`. Numeric bound validation (`min <= max`).

### 11.4 Asset Depreciation & Financial Management
1. **`AssetDepreciationSchedule`** (`ADEP-`):
   - **Fields:** `number`, `fixed_asset` (FK `accounting.FixedAsset`), `operational_asset` (FK `scm.Asset`), `fiscal_period` (FK `accounting.FiscalPeriod`), `fiscal_year`, `period_number`, `period_frequency` (`monthly`, `quarterly`, `semi_annual`, `annual`), `schedule_date`, `depreciation_method` (`straight_line`, `declining_balance_200`, `declining_balance_150`, `sum_of_years`, `units_of_production`), `starting_book_value`, `depreciation_amount`, `accumulated_depreciation_after`, `ending_book_value`, `total_units_expected`, `units_produced_period`, `expense_account` (FK `accounting.GLAccount`), `accumulated_account` (FK `accounting.GLAccount`), `cost_center` (FK `core.OrgUnit`), `status` (`draft`, `calculated`, `posted`, `cancelled`), `journal_entry` (FK `accounting.JournalEntry`), `posted_at`, `posted_by` (FK `User`), `notes`.
   - **Invariants:** Automatic multi-method depreciation calculation with manual override preservation unless `force=True`. GL posting (`post_to_gl`) creates a balanced `JournalEntry` (Dr Expense / Cr Accumulated Depreciation), advances `fixed_asset.accumulated_depreciation` and `last_depreciation_date`, and validates required GL accounts. Status guards prevent modifying/deleting posted runs.
2. **`AssetRevaluation`** (`AREV-`):
   - **Fields:** `number`, `title`, `fixed_asset` (FK `accounting.FixedAsset`), `operational_asset` (FK `scm.Asset`), `event_type` (`impairment`, `revaluation_up`, `reversal_impairment`, `salvage_revision`), `valuation_method` (`independent_appraisal`, `market_approach`, `discounted_cash_flow`, `replacement_cost_depreciated`), `valuation_date`, `appraiser` (FK `core.Party`), `appraiser_name_fallback`, `historical_cost`, `accumulated_depreciation_before`, `carrying_value_before`, `new_fair_market_value`, `revaluation_adjustment`, `new_salvage_value`, `remaining_useful_life_months`, `impairment_loss_account` (FK `accounting.GLAccount`), `revaluation_surplus_account` (FK `accounting.GLAccount`), `status` (`draft`, `submitted`, `approved`, `rejected`), `journal_entry` (FK `accounting.JournalEntry`), `approved_by` (FK `User`), `approved_at`, `justification`, `notes`.
   - **Invariants:** Net adjustment computed as `new_fair_market_value - carrying_value_before`. Execution (`execute_revaluation`) creates balanced `JournalEntry` (Dr Impairment Loss / Cr Acc Deprec for impairments; Dr FixedAsset Cost / Cr Revaluation Surplus for step-ups), updates asset prospective salvage and useful life, and enforces GL account presence.
3. **`AssetTransfer`** (`AXFR-`):
   - **Fields:** `number`, `title`, `fixed_asset` (FK `accounting.FixedAsset`), `operational_asset` (FK `scm.Asset`), `transfer_type` (`cost_center`, `inter_department`, `inter_facility`, `custodian_reassignment`, `inter_company`), `transfer_date`, `source_department` / `destination_department` (FK `core.OrgUnit`), `source_location` / `destination_location` (FK `scm.Location`), `source_custodian` / `destination_custodian` (FK `core.Party`), `source_expense_account` / `destination_expense_account` (FK `accounting.GLAccount`), `transferred_by` / `received_by` (FK `User`), `transportation_cost`, `carrier_reference`, `carrying_value_at_transfer`, `status` (`draft`, `in_transit`, `completed`, `cancelled`), `completed_at`, `transfer_notes`.
   - **Invariants:** Dispatch transitions status to `in_transit`. Completion (`complete_transfer`) updates `fixed_asset` location, custodian, and expense account, plus operational `scm.Asset` (`location`, `custodian`, `org_unit`) atomically.
4. **`CapitalizationPolicy`** (`ACTH-`):
   - **Fields:** `number`, `name`, `policy_scope` (`global_default`, `category_override`, `tax_book_safe_harbor`), `category` (FK `AssetCategory`), `minimum_cost_threshold`, `minimum_useful_life_months`, `default_classification` (`capitalize`, `expense_immediately`, `manual_review`), `de_minimis_safe_harbor` (Bool), `applicable_gaap_standard`, `default_cip_account` (FK `accounting.GLAccount`), `default_expense_account` (FK `accounting.GLAccount`), `policy_notes`, `effective_from`, `effective_to`, `is_active`.
   - **Invariants:** Capitalization decision engine `evaluate_asset(cost, useful_life_months)` evaluates CapEx vs OpEx vs manual review with safe-harbor compliance checks and robust numeric guarding against invalid, infinite, or negative inputs.

### 11.5 Asset Maintenance & Repair
1. **`AssetMaintenanceRequest`** (`AMRQ-`):
   - **Fields:** `number`, `title`, `fixed_asset` (FK `accounting.FixedAsset`), `operational_asset` (FK `scm.Asset`), `requester` (FK `User`), `department` (FK `core.OrgUnit`), `request_type` (`breakdown_repair`, `preventive_service`, `safety_hazard`, `calibration_request`, `inspection_finding`), `urgency` (`low`, `medium`, `high`, `critical`), `is_breakdown` (Bool), `downtime_started_at`, `symptom_description`, `triage_notes`, `assigned_technician` (FK `User`), `assigned_vendor` (FK `core.Party`), `service_contract` (FK `AssetServiceContract`), `dispatched_work_order` (FK `scm.MaintenanceWorkOrder`), `status` (`submitted`, `triaged`, `assigned`, `in_progress`, `resolved`, `closed`, `rejected`), `resolution_summary`, `resolved_at`, `resolved_by` (FK `User`).
   - **Invariants:** Operator emergency tickets, supervisor triage, dispatch to internal technician or external vendor with optional SLA contract linkage, lifecycle state machine (`submitted` -> `triaged` -> `assigned` -> `in_progress` -> `resolved` -> `closed` or `rejected`).
2. **`AssetMaintenanceSchedule`** (`AMSC-`):
   - **Fields:** `number`, `name`, `fixed_asset` (FK `accounting.FixedAsset`), `operational_asset` (FK `scm.Asset`), `asset_category` (FK `AssetCategory`), `schedule_type` (`time_based`, `meter_based`, `condition_based`, `seasonal_shutdown`), `frequency_interval`, `frequency_unit` (`days`, `weeks`, `months`, `years`, `runtime_hours`, `cycles_count`), `meter_trigger_threshold`, `lead_time_days`, `last_service_date`, `last_service_meter`, `next_due_date`, `next_due_meter`, `assigned_technician` (FK `User`), `preferred_vendor` (FK `core.Party`), `service_contract` (FK `AssetServiceContract`), `service_checklist`, `is_mandatory` (Bool), `is_active` (Bool), `status` (`active`, `overdue`, `paused`, `completed`, `retired`), `notes`.
   - **Invariants:** Automatic recurrence advancement on completion (`record_completion`), meter delta tracking, SOP markdown/text checklist parsing, on-demand maintenance request spawning (`generate_request`).
3. **`AssetServiceContract`** (`ASVC-`):
   - **Fields:** `number`, `contract_reference`, `title`, `vendor` (FK `core.Party`), `contract_type` (`comprehensive_amc`, `labor_only_amc`, `oem_warranty`, `extended_warranty`, `preventive_inspection_only`, `on_call_sla`), `sla_tier` (`platinum_24_7`, `gold_same_day`, `silver_next_day`, `bronze`), `start_date`, `end_date`, `contract_value`, `currency` (FK `accounting.Currency`), `billing_frequency` (`annual`, `semi_annual`, `quarterly`, `monthly`), `response_time_sla_hours`, `resolution_time_sla_hours`, `included_routine_visits`, `routine_visits_completed`, `included_emergency_visits`, `emergency_visits_completed`, `parts_discount_percent`, `labor_discount_percent`, `contact_person`, `contact_phone`, `contact_email`, `status` (`draft`, `active`, `expiring_soon`, `expired`, `renewed`, `terminated`), `renewal_notes`, `termination_reason`, `notes`.
   - **Invariants:** Quota tracking for routine/emergency visits, SLA compliance monitoring, early termination gated by `@tenant_admin_required`, contract renewal with auto-rollover.
4. **`AssetMaintenanceLog`** (`AMLG-`):
   - **Fields:** `number`, `fixed_asset` (FK `accounting.FixedAsset`), `operational_asset` (FK `scm.Asset`), `maintenance_request` (FK `AssetMaintenanceRequest`), `maintenance_schedule` (FK `AssetMaintenanceSchedule`), `service_contract` (FK `AssetServiceContract`), `work_order` (FK `scm.MaintenanceWorkOrder`), `service_date`, `completion_date`, `maintenance_type` (`corrective_repair`, `preventive_service`, `emergency_breakdown`, `calibration`, `inspection`, `overhaul`), `failure_code` (`mechanical_wear`, `electrical_short`, `hydraulic_leak`, `software_fault`, `operator_error`, `corrosion`, `thermal_overload`, `lubrication_failure`, `normal_wear`, `other`), `downtime_hours`, `meter_reading`, `lead_technician` (FK `User`), `service_vendor` (FK `core.Party`), `labor_hours`, `labor_cost`, `parts_consumed_summary`, `parts_cost`, `vendor_invoice_cost`, `total_cost`, `expense_account` (FK `accounting.GLAccount`), `root_cause_analysis`, `action_taken`, `status` (`draft`, `in_review`, `approved`, `posted`), `approved_by` (FK `User`), `approved_at`.
   - **Invariants:** Cost roll-up (`labor_cost + parts_cost + vendor_invoice_cost = total_cost`), ISO 14224 failure categorization, supervisory approval workflow, GL posting with synchronized updates across linked schedule, request, and contract.

### 11.6 Asset Performance & Utilization
1. **`AssetDowntimeLog`** (`ADWN-`):
   - **Fields:** `number`, `fixed_asset` (FK `accounting.FixedAsset`), `operational_asset` (FK `scm.Asset`), `maintenance_request` (FK `assets.AssetMaintenanceRequest`), `work_order` (FK `scm.MaintenanceWorkOrder`), `downtime_category` (`unplanned_breakdown`, `planned_maintenance`, `setup_changeover`, `tooling_adjustment`, `process_interruption`, `utility_outage`, `operator_unavailable`, `cleaning_sanitation`), `impact_level` (`full_shutdown`, `partial_derate`, `cell_idle`, `minor_stop`), `root_cause_code`, `failure_description`, `started_at`, `ended_at`, `duration_minutes`, `hourly_cost_rate`, `total_downtime_cost`, `is_mtbf_failure`, `logged_by` (FK `User`), `department` (FK `core.OrgUnit`), `status` (`active`, `resolved`, `under_investigation`, `cancelled`), `resolution_notes`.
   - **Invariants:** Auto-calculates duration and financial loss (`hours * hourly_cost_rate`). Resolve workflow records restart timestamp and notes.
2. **`AssetOeeRecord`** (`AOEE-`):
   - **Fields:** `number`, `fixed_asset` (FK `accounting.FixedAsset`), `operational_asset` (FK `scm.Asset`), `record_date`, `shift_name`, `planned_production_time_minutes`, `operating_time_minutes`, `ideal_cycle_time_seconds`, `total_units_produced`, `good_units_produced`, `defect_units_count`, `rework_units_count`, TPM Six Big Losses (`breakdown_loss_minutes`, `setup_loss_minutes`, `small_stops_loss_minutes`, `reduced_speed_loss_minutes`, `defect_loss_minutes`, `startup_loss_minutes`), `availability_percentage`, `performance_percentage`, `quality_percentage`, `oee_percentage`, `benchmark_tier` (`world_class`, `typical`, `needs_improvement`), `status` (`draft`, `finalized`, `cancelled`), `notes`, `recorded_by` (FK `User`).
   - **Invariants:** Mathematical OEE calculation ($A \times P \times Q$), benchmark classification, status transition guard (`draft` -> `finalized`).
3. **`AssetEnergyReading`** (`AENG-`):
   - **Fields:** `number`, `fixed_asset` (FK `accounting.FixedAsset`), `operational_asset` (FK `scm.Asset`), `reading_timestamp`, `utility_type` (`electricity`, `natural_gas`, `water`, `compressed_air`, `steam`, `diesel`), `meter_serial_number`, `consumption_value`, `unit_of_measure`, `peak_demand_kw`, `power_factor`, `operating_hours`, `units_produced`, `energy_intensity_per_hour`, `energy_intensity_per_unit`, `emission_factor`, `carbon_emissions_kg_co2e`, `ghg_scope` (`scope_1`, `scope_2`, `scope_3`), `cost_per_unit`, `total_energy_cost`, `utility_provider` (FK `core.Party`), `status` (`pending`, `validated`, `flagged_anomaly`, `cancelled`), `notes`, `recorded_by` (FK `User`).
   - **Invariants:** Specific energy consumption (SEC) intensity metrics, GHG Protocol Scope 1/2/3 emissions rollups, validation workflow.
4. **`AssetPerformanceScorecard`** (`APSC-`):
   - **Fields:** `number`, `fixed_asset` (FK `accounting.FixedAsset`), `operational_asset` (FK `scm.Asset`), `period_type` (`daily`, `weekly`, `monthly`, `quarterly`, `annual`), `period_start`, `period_end`, `total_calendar_hours`, `planned_operating_hours`, `actual_operating_hours`, `unplanned_downtime_hours`, `planned_downtime_hours`, `idle_capacity_hours`, `failure_event_count`, `capacity_utilization_rate`, `availability_rate`, `mtbf_hours`, `mttr_hours`, `average_oee_percentage`, `total_energy_consumption_kwh`, `total_carbon_emissions_kg`, `total_downtime_cost`, `performance_index_score`, `benchmark_grade` (`grade_a`, `grade_b`, `grade_c`, `grade_d`), `status` (`draft`, `published`, `archived`), `department` (FK `core.OrgUnit`), `evaluated_by` (FK `User`), `executive_summary`.
   - **Invariants:** Roll-up synthesis (35% Utilization + 35% Availability + 30% OEE), MTBF/MTTR calculation, publish lifecycle.

### 11.8 Asset Warranty & Insurance Management
1. **`AssetWarranty`** (`AWAR-`):
   - **Fields:** `number`, `title`, `warranty_certificate_number`, `fixed_asset` (FK `accounting.FixedAsset`), `operational_asset` (FK `scm.Asset`), `asset_category` (FK `AssetCategory`), `warrantor_party` (FK `core.Party`), `currency` (FK `accounting.Currency`), `warranty_type` (`oem_standard`, `oem_extended`, `third_party_extended`, `dealer_certified`, `refurbished_component`), `coverage_scope` (`comprehensive`, `parts_and_labor`, `parts_only`, `powertrain_major_components`), `start_date`, `end_date`, `meter_type` (`hours`, `kilometers`, `miles`, `production_cycles`, `none_calendar_only`), `meter_limit`, `parts_coverage_percent`, `labor_coverage_percent`, `travel_dispatch_covered`, `deductible_amount`, `contract_purchase_price`, `terms_and_conditions`, `contract_document` (FK `core.Document`), `service_contract` (FK `AssetServiceContract`), `status` (`draft`, `active`, `expiring_soon`, `expired`, `voided`, `claimed`), `registered_by` (FK `User`).
   - **Invariants:** Date validity checks (`end_date >= start_date`), active window derivation (`is_currently_valid`), status guards rejecting renewal of voided warranties, automatic reactivation vs expiration on claim closure.
2. **`AssetWarrantyClaim`** (`AWCL-`):
   - **Fields:** `number`, `title`, `warranty` (FK `AssetWarranty`), `fixed_asset` (FK `accounting.FixedAsset`), `operational_asset` (FK `scm.Asset`), `incident_date`, `operating_meter_at_failure`, `defect_description`, `warrantor_claim_reference`, `maintenance_request` (FK `AssetMaintenanceRequest`), `supporting_document` (FK `core.Document`), `currency` (FK `accounting.Currency`), `claimed_amount`, `approved_amount`, `rejected_amount`, `deductible_applied`, `net_recovery_amount`, `resolution_type` (`pending_evaluation`, `parts_replacement_oem`, `labor_reimbursement`, `full_unit_replacement`, `cash_reimbursement`, `rejected_uncovered`), `part_return_required`, `part_return_tracking_number`, `part_return_status` (`not_required`, `pending_shipment`, `in_transit_to_oem`, `delivered_accepted`), `claim_status` (`draft`, `submitted`, `under_review`, `approved_pending_settlement`, `settled_closed`, `rejected`), `filed_by` (FK `User`), `approved_by` (FK `User`), `settlement_date`, `settlement_notes`.
   - **Invariants:** Hand-parsed numeric inputs protected by `is_finite()` and magnitude limits (L35), net recovery calculation (`approved_amount - deductible_applied`), status transition guards preventing re-settling finalized claims.
3. **`AssetInsurancePolicy`** (`AINS-`):
   - **Fields:** `number`, `policy_number`, `title`, `policy_type` (`machinery_breakdown`, `property_all_risk`, `boiler_pressure_vessel`, `electronic_equipment`, `business_interruption`, `transit_cargo`, `comprehensive_all_risk`), `underwriter_party` (FK `core.Party`), `broker_party` (FK `core.Party`), `fixed_asset` (FK `accounting.FixedAsset`), `operational_asset` (FK `scm.Asset`), `asset_category` (FK `AssetCategory`), `effective_date`, `expiration_date`, `annual_premium`, `premium_frequency` (`annual`, `semi_annual`, `quarterly`, `monthly`), `total_insured_value`, `policy_limit`, `deductible_retention`, `coinsurance_percentage`, `valuation_basis` (`replacement_cost_value`, `actual_cash_value`, `agreed_value`, `functional_replacement_cost`), `currency` (FK `accounting.Currency`), `coverage_terms`, `policy_document` (FK `core.Document`), `status` (`draft`, `active`, `expiring_soon`, `expired`, `cancelled`), `risk_manager` (FK `User`), `notes`.
   - **Invariants:** In-force evaluation (`is_currently_in_force`), renewal guards rejecting cancelled/voided policies, color-named badge mappings.
4. **`AssetInsuranceClaim`** (`AICL-`):
   - **Fields:** `number`, `title`, `policy` (FK `AssetInsurancePolicy`), `fixed_asset` (FK `accounting.FixedAsset`), `operational_asset` (FK `scm.Asset`), `incident_report` (FK `AssetIncidentReport`), `incident_date`, `incident_location`, `peril_type` (`fire_explosion`, `mechanical_breakdown`, `electrical_arcing_surge`, `water_liquid_damage`, `natural_catastrophe`, `operator_error_impact`, `theft_burglary`, `business_interruption_loss`), `incident_description`, `carrier_claim_number`, `adjuster_party` (FK `core.Party`), `adjuster_name_fallback`, `adjuster_phone`, `adjuster_email`, `date_reported_to_carrier`, `proof_of_loss_filed`, `proof_of_loss_date`, `proof_of_loss_document` (FK `core.Document`), `claimed_loss_amount`, `deductible_applied`, `settlement_payout_amount`, `salvage_recovery_amount`, `net_carrier_indemnity`, `currency` (FK `accounting.Currency`), `settlement_method` (`direct_indemnity_check`, `vendor_direct_repair`, `replacement_asset_procurement`, `none_denied`), `settlement_date`, `settlement_notes`, `claim_status` (`incident_reported`, `adjuster_assigned`, `proof_of_loss_filed`, `under_carrier_review`, `approved_pending_payout`, `settled_paid`, `denied_disputed`, `closed`), `claims_officer` (FK `User`).
   - **Invariants:** Double numeric validation on settlement/salvage payouts (L35), net recovery calculation (`settlement_payout_amount + salvage_recovery_amount`), adjuster assignment workflow, proof-of-loss tracking, view-level status guards.

### 11.10 Lease & Rental Management
1. **`AssetLeaseContract`** (`ALC-`):
   - **Fields:** `number`, `title`, `master_lease_agreement_ref`, `lessor` (FK `core.Party`), `asset` (FK `scm.Asset`), `category` (FK `AssetCategory`), `fixed_asset` (FK `accounting.FixedAsset`), `inception_date`, `commencement_date`, `expiration_date`, `first_payment_date`, `early_termination_notice_date`, `lease_term_months`, `economic_life_months`, `payment_amount`, `payment_frequency`, `payment_timing`, `discount_rate_pct`, `fair_market_value`, `initial_direct_costs`, `lease_incentives`, `residual_value_guarantee`, `purchase_option_price`, `transfer_of_ownership`, `has_purchase_option`, `is_specialized_asset`, `classification` (`operating`, `finance`), `classification_overridden`, `classification_notes`, `initial_lease_liability`, `initial_rou_asset_value`, `current_lease_liability`, `current_rou_asset_carrying_value`, `status` (`draft`, `pending_approval`, `active`, `modified`, `expired`, `terminated`, `buyout`), `approved_by` (FK `User`), `notes`.
   - **Invariants:** 5-criteria statutory lease classification test (transfer of ownership, purchase option, lease term >= 75% life, PV of payments >= 90% FMV, specialized asset), actuarial present value calculation of minimum lease payments, Right-of-Use (ROU) initial asset capitalizing initial direct costs and deducting lessor incentives.
2. **`AssetLeaseSchedule`** (`ALSP-`):
   - **Fields:** `number`, `lease_contract` (FK `AssetLeaseContract`), `period_number`, `due_date`, `payment_amount`, `beginning_liability`, `interest_expense`, `principal_reduction`, `ending_liability`, `rou_depreciation`, `ending_rou_asset_value`, `status` (`scheduled`, `accrued`, `paid`, `cancelled`), `payment_reference`, `paid_date`, `notes`.
   - **Invariants:** Sequential amortization schedule generated with atomic numbering, straight-line ROU depreciation, compound periodic interest rate accretion, automatic contract balance sync upon payment.
3. **`AssetLeaseModification`** (`ALMD-`):
   - **Fields:** `number`, `lease_contract` (FK `AssetLeaseContract`), `modification_type` (`term_extension`, `payment_change`, `partial_termination`, `full_termination`, `impairment`, `discount_rate_change`), `request_date`, `effective_date`, `prior_lease_liability`, `revised_lease_liability`, `liability_adjustment`, `prior_rou_asset_value`, `revised_rou_asset_value`, `rou_asset_adjustment`, `gain_loss_on_modification`, `impairment_loss_recognized`, `revised_term_months`, `revised_payment_amount`, `revised_discount_rate_pct`, `requested_by` (FK `User`), `approved_by` (FK `User`), `status` (`draft`, `submitted`, `approved`, `rejected`, `executed`), `justification`, `notes`.
   - **Invariants:** Remeasurement workflow adjusting parent lease liability and ROU asset balances, gain/loss recognition on scope terminations, audit trail logging.
4. **`AssetLeaseBuyAnalysis`** (`ALBA-`):
   - **Fields:** `number`, `title`, `description`, `target_asset_name`, `category` (FK `AssetCategory`), `expected_useful_life_years`, `purchase_price`, `down_payment_pct`, `loan_interest_rate_pct`, `loan_term_years`, `estimated_salvage_value`, `annual_maintenance_cost_buy`, `annual_insurance_tax_buy`, `lease_term_months`, `monthly_lease_payment`, `upfront_lease_fees`, `end_of_lease_purchase_option`, `lessor_covers_maintenance`, `annual_maintenance_cost_lease`, `discount_rate_wacc_pct`, `corporate_tax_rate_pct`, `npv_purchase_option`, `npv_lease_option`, `tco_purchase_option`, `tco_lease_option`, `net_advantage_to_leasing`, `recommendation` (`buy`, `lease`, `neutral`), `status` (`draft`, `evaluated`, `approved`, `rejected`), `evaluated_by` (FK `User`), `approved_by` (FK `User`), `evaluation_notes`.
   - **Invariants:** Discounted after-tax Net Present Value (NPV) modeling using corporate WACC hurdle rate, debt loan amortization schedules, depreciation tax shield benefits, nominal TCO comparisons, Net Advantage to Leasing (NAL) recommendation.

---

## Key URLs & Routes (11.2, 11.3, 11.4 & 11.5)

### 11.5 Asset Maintenance & Repair
Namespace: `assets:`
- **Maintenance Requests:**
  - `assets:asset_maintenance_request_list`: `/assets/maintenance-requests/`
  - `assets:asset_maintenance_request_create`: `/assets/maintenance-requests/create/`
  - `assets:asset_maintenance_request_detail`: `/assets/maintenance-requests/<pk>/`
  - `assets:asset_maintenance_request_edit`: `/assets/maintenance-requests/<pk>/edit/`
  - `assets:asset_maintenance_request_delete`: `/assets/maintenance-requests/<pk>/delete/` [POST, Admin]
  - `assets:asset_maintenance_request_triage`: `/assets/maintenance-requests/<pk>/triage/` [POST]
  - `assets:asset_maintenance_request_dispatch`: `/assets/maintenance-requests/<pk>/dispatch/` [POST]
  - `assets:asset_maintenance_request_resolve`: `/assets/maintenance-requests/<pk>/resolve/` [POST]
  - `assets:asset_maintenance_request_close`: `/assets/maintenance-requests/<pk>/close/` [POST]
  - `assets:asset_maintenance_request_reject`: `/assets/maintenance-requests/<pk>/reject/` [POST]
- **Maintenance Schedules:**
  - `assets:asset_maintenance_schedule_list`: `/assets/schedules/`
  - `assets:asset_maintenance_schedule_create`: `/assets/schedules/create/`
  - `assets:asset_maintenance_schedule_detail`: `/assets/schedules/<pk>/`
  - `assets:asset_maintenance_schedule_edit`: `/assets/schedules/<pk>/edit/`
  - `assets:asset_maintenance_schedule_delete`: `/assets/schedules/<pk>/delete/` [POST, Admin]
  - `assets:asset_maintenance_schedule_activate`: `/assets/schedules/<pk>/activate/` [POST]
  - `assets:asset_maintenance_schedule_pause`: `/assets/schedules/<pk>/pause/` [POST]
  - `assets:asset_maintenance_schedule_generate_request`: `/assets/schedules/<pk>/generate-request/` [POST]
  - `assets:asset_maintenance_schedule_record_completion`: `/assets/schedules/<pk>/record-completion/` [POST]
- **Service Contracts:**
  - `assets:asset_service_contract_list`: `/assets/service-contracts/`
  - `assets:asset_service_contract_create`: `/assets/service-contracts/create/`
  - `assets:asset_service_contract_detail`: `/assets/service-contracts/<pk>/`
  - `assets:asset_service_contract_edit`: `/assets/service-contracts/<pk>/edit/`
  - `assets:asset_service_contract_delete`: `/assets/service-contracts/<pk>/delete/` [POST, Admin]
  - `assets:asset_service_contract_activate`: `/assets/service-contracts/<pk>/activate/` [POST]
  - `assets:asset_service_contract_record_visit`: `/assets/service-contracts/<pk>/record-visit/` [POST]
  - `assets:asset_service_contract_renew`: `/assets/service-contracts/<pk>/renew/` [POST]
  - `assets:asset_service_contract_terminate`: `/assets/service-contracts/<pk>/terminate/` [POST, Admin]
- **Maintenance Logs:**
  - `assets:asset_maintenance_log_list`: `/assets/logs/`
  - `assets:asset_maintenance_log_create`: `/assets/logs/create/`
  - `assets:asset_maintenance_log_detail`: `/assets/logs/<pk>/`
  - `assets:asset_maintenance_log_edit`: `/assets/logs/<pk>/edit/`
  - `assets:asset_maintenance_log_delete`: `/assets/logs/<pk>/delete/` [POST, Admin]
  - `assets:asset_maintenance_log_submit_review`: `/assets/logs/<pk>/submit-review/` [POST]
  - `assets:asset_maintenance_log_approve`: `/assets/logs/<pk>/approve/` [POST, Admin]
  - `assets:asset_maintenance_log_post_gl`: `/assets/logs/<pk>/post-gl/` [POST, Admin]

### 11.6 Asset Performance & Utilization
Namespace: `assets:`
- **Downtime Logs:**
  - `assets:asset_downtime_log_list`: `/assets/downtime/`
  - `assets:asset_downtime_log_create`: `/assets/downtime/create/`
  - `assets:asset_downtime_log_detail`: `/assets/downtime/<pk>/`
  - `assets:asset_downtime_log_edit`: `/assets/downtime/<pk>/edit/`
  - `assets:asset_downtime_log_delete`: `/assets/downtime/<pk>/delete/` [POST]
  - `assets:asset_downtime_log_resolve`: `/assets/downtime/<pk>/resolve/` [GET, POST]
- **OEE Records:**
  - `assets:asset_oee_record_list`: `/assets/oee/`
  - `assets:asset_oee_record_create`: `/assets/oee/create/`
  - `assets:asset_oee_record_detail`: `/assets/oee/<pk>/`
  - `assets:asset_oee_record_edit`: `/assets/oee/<pk>/edit/`
  - `assets:asset_oee_record_delete`: `/assets/oee/<pk>/delete/` [POST]
  - `assets:asset_oee_record_finalize`: `/assets/oee/<pk>/finalize/` [POST]
- **Energy Readings:**
  - `assets:asset_energy_reading_list`: `/assets/energy/`
  - `assets:asset_energy_reading_create`: `/assets/energy/create/`
  - `assets:asset_energy_reading_detail`: `/assets/energy/<pk>/`
  - `assets:asset_energy_reading_edit`: `/assets/energy/<pk>/edit/`
  - `assets:asset_energy_reading_delete`: `/assets/energy/<pk>/delete/` [POST]
  - `assets:asset_energy_reading_validate`: `/assets/energy/<pk>/validate/` [POST]
- **Performance Scorecards:**
  - `assets:asset_performance_scorecard_list`: `/assets/scorecards/`
  - `assets:asset_performance_scorecard_create`: `/assets/scorecards/create/`
  - `assets:asset_performance_scorecard_detail`: `/assets/scorecards/<pk>/`
  - `assets:asset_performance_scorecard_edit`: `/assets/scorecards/<pk>/edit/`
  - `assets:asset_performance_scorecard_delete`: `/assets/scorecards/<pk>/delete/` [POST]
  - `assets:asset_performance_scorecard_publish`: `/assets/scorecards/<pk>/publish/` [POST]

### 11.4 Asset Depreciation & Financial Management
Namespace: `assets:`
- **Depreciation Schedules:**
  - `assets:depreciation_schedule_list`: `/assets/depreciation/`
  - `assets:depreciation_schedule_create`: `/assets/depreciation/create/`
  - `assets:depreciation_schedule_detail`: `/assets/depreciation/<pk>/`
  - `assets:depreciation_schedule_edit`: `/assets/depreciation/<pk>/edit/` [Draft only]
  - `assets:depreciation_schedule_delete`: `/assets/depreciation/<pk>/delete/` [POST, Admin, Draft only]
  - `assets:depreciation_schedule_calculate`: `/assets/depreciation/<pk>/calculate/` [POST, Draft only]
  - `assets:depreciation_schedule_post`: `/assets/depreciation/<pk>/post/` [POST, Admin, Draft only]
- **Revaluations:**
  - `assets:revaluation_list`: `/assets/revaluations/`
  - `assets:revaluation_create`: `/assets/revaluations/create/`
  - `assets:revaluation_detail`: `/assets/revaluations/<pk>/`
  - `assets:revaluation_edit`: `/assets/revaluations/<pk>/edit/` [Draft only]
  - `assets:revaluation_delete`: `/assets/revaluations/<pk>/delete/` [POST, Admin, Draft only]
  - `assets:revaluation_approve`: `/assets/revaluations/<pk>/approve/` [POST, Admin, Draft only]
- **Transfers:**
  - `assets:transfer_list`: `/assets/transfers/`
  - `assets:transfer_create`: `/assets/transfers/create/`
  - `assets:transfer_detail`: `/assets/transfers/<pk>/`
  - `assets:transfer_edit`: `/assets/transfers/<pk>/edit/` [Draft only]
  - `assets:transfer_delete`: `/assets/transfers/<pk>/delete/` [POST, Admin, Draft only]
  - `assets:transfer_dispatch`: `/assets/transfers/<pk>/dispatch/` [POST, Draft only]
  - `assets:transfer_complete`: `/assets/transfers/<pk>/complete/` [POST, Admin, in_transit only]
- **Capitalization Policies:**
  - `assets:capitalization_policy_list`: `/assets/capitalization-policies/`
  - `assets:capitalization_policy_create`: `/assets/capitalization-policies/create/`
  - `assets:capitalization_policy_detail`: `/assets/capitalization-policies/<pk>/` (includes interactive CapEx evaluator)
  - `assets:capitalization_policy_edit`: `/assets/capitalization-policies/<pk>/edit/`
  - `assets:capitalization_policy_delete`: `/assets/capitalization-policies/<pk>/delete/` [POST, Admin]

### 11.3 Asset Classification & Categorization
Namespace: `assets:`
- **Categories:**
  - `assets:asset_category_list`: `/assets/classification/categories/`
  - `assets:asset_category_create`: `/assets/classification/categories/create/`
  - `assets:asset_category_detail`: `/assets/classification/categories/<pk>/`
  - `assets:asset_category_edit`: `/assets/classification/categories/<pk>/edit/`
  - `assets:asset_category_delete`: `/assets/classification/categories/<pk>/delete/` [POST, Admin]
- **Models:**
  - `assets:asset_model_list`: `/assets/classification/models/`
  - `assets:asset_model_create`: `/assets/classification/models/create/`
  - `assets:asset_model_detail`: `/assets/classification/models/<pk>/`
  - `assets:asset_model_edit`: `/assets/classification/models/<pk>/edit/`
  - `assets:asset_model_delete`: `/assets/classification/models/<pk>/delete/` [POST, Admin]
- **Criticality Assessments:**
  - `assets:asset_criticality_assessment_list`: `/assets/classification/criticality-assessments/`
  - `assets:asset_criticality_assessment_create`: `/assets/classification/criticality-assessments/create/`
  - `assets:asset_criticality_assessment_detail`: `/assets/classification/criticality-assessments/<pk>/`
  - `assets:asset_criticality_assessment_edit`: `/assets/classification/criticality-assessments/<pk>/edit/` [Draft only]
  - `assets:asset_criticality_assessment_delete`: `/assets/classification/criticality-assessments/<pk>/delete/` [POST, Admin, Draft only]
  - `assets:asset_criticality_assessment_approve`: `/assets/classification/criticality-assessments/<pk>/approve/` [POST, Admin]
- **Specification Templates:**
  - `assets:asset_specification_template_list`: `/assets/classification/spec-templates/`
  - `assets:asset_specification_template_create`: `/assets/classification/spec-templates/create/`
  - `assets:asset_specification_template_detail`: `/assets/classification/spec-templates/<pk>/`
  - `assets:asset_specification_template_edit`: `/assets/classification/spec-templates/<pk>/edit/`
  - `assets:asset_specification_template_delete`: `/assets/classification/spec-templates/<pk>/delete/` [POST, Admin]

---

## Key URLs & Routes (11.2)

Namespace: `assets:`
- **Audits:**
  - `assets:asset_audit_list`: `/assets/inventory-tracking/audits/`
  - `assets:asset_audit_create`: `/assets/inventory-tracking/audits/create/`
  - `assets:asset_audit_detail`: `/assets/inventory-tracking/audits/<pk>/`
  - `assets:asset_audit_edit`: `/assets/inventory-tracking/audits/<pk>/edit/`
  - `assets:asset_audit_delete`: `/assets/inventory-tracking/audits/<pk>/delete/` [POST]
  - `assets:asset_audit_start`: `/assets/inventory-tracking/audits/<pk>/start/` [POST]
  - `assets:asset_audit_complete`: `/assets/inventory-tracking/audits/<pk>/complete/` [POST]
  - `assets:asset_audit_reconcile`: `/assets/inventory-tracking/audits/<pk>/reconcile/` [POST, Admin]
  - `assets:asset_audit_cancel`: `/assets/inventory-tracking/audits/<pk>/cancel/` [POST]
- **Movements:**
  - `assets:asset_movement_log_list`: `/assets/inventory-tracking/movements/`
  - `assets:asset_movement_log_create`: `/assets/inventory-tracking/movements/create/`
  - `assets:asset_movement_log_detail`: `/assets/inventory-tracking/movements/<pk>/`
  - `assets:asset_movement_log_edit`: `/assets/inventory-tracking/movements/<pk>/edit/`
  - `assets:asset_movement_log_delete`: `/assets/inventory-tracking/movements/<pk>/delete/` [POST]
  - `assets:asset_movement_log_dispatch`: `/assets/inventory-tracking/movements/<pk>/dispatch/` [POST]
  - `assets:asset_movement_log_receive`: `/assets/inventory-tracking/movements/<pk>/receive/` [POST]
  - `assets:asset_movement_log_cancel`: `/assets/inventory-tracking/movements/<pk>/cancel/` [POST]
- **Custody Lending:**
  - `assets:asset_custody_log_list`: `/assets/inventory-tracking/custody/`
  - `assets:asset_custody_log_create`: `/assets/inventory-tracking/custody/create/`
  - `assets:asset_custody_log_detail`: `/assets/inventory-tracking/custody/<pk>/`
  - `assets:asset_custody_log_edit`: `/assets/inventory-tracking/custody/<pk>/edit/`
  - `assets:asset_custody_log_delete`: `/assets/inventory-tracking/custody/<pk>/delete/` [POST]
  - `assets:asset_custody_log_checkin`: `/assets/inventory-tracking/custody/<pk>/checkin/` [POST]
  - `assets:asset_custody_log_extend`: `/assets/inventory-tracking/custody/<pk>/extend/` [POST]
  - `assets:asset_custody_log_mark_lost`: `/assets/inventory-tracking/custody/<pk>/mark-lost/` [POST]
- **Incident Reports:**
  - `assets:asset_incident_report_list`: `/assets/inventory-tracking/incidents/`
  - `assets:asset_incident_report_create`: `/assets/inventory-tracking/incidents/create/`
  - `assets:asset_incident_report_detail`: `/assets/inventory-tracking/incidents/<pk>/`
  - `assets:asset_incident_report_edit`: `/assets/inventory-tracking/incidents/<pk>/edit/`
  - `assets:asset_incident_report_delete`: `/assets/inventory-tracking/incidents/<pk>/delete/` [POST]
  - `assets:asset_incident_report_investigate`: `/assets/inventory-tracking/incidents/<pk>/investigate/` [POST]
  - `assets:asset_incident_report_resolve_recovered`: `/assets/inventory-tracking/incidents/<pk>/resolve-recovered/` [POST]
  - `assets:asset_incident_report_authorize_write_off`: `/assets/inventory-tracking/incidents/<pk>/authorize-write-off/` [POST, Admin]
  - `assets:asset_incident_report_close`: `/assets/inventory-tracking/incidents/<pk>/close/` [POST]

---

## Key URLs & Routes (11.7)

Namespace: `assets:`
- **Condition Assessments:**
  - `assets:asset_condition_assessment_list`: `/assets/reliability/assessments/`
  - `assets:asset_condition_assessment_create`: `/assets/reliability/assessments/create/`
  - `assets:asset_condition_assessment_detail`: `/assets/reliability/assessments/<pk>/`
  - `assets:asset_condition_assessment_edit`: `/assets/reliability/assessments/<pk>/edit/`
  - `assets:asset_condition_assessment_delete`: `/assets/reliability/assessments/<pk>/delete/` [POST, Admin]
  - `assets:asset_condition_assessment_complete`: `/assets/reliability/assessments/<pk>/complete/` [POST]
  - `assets:asset_condition_assessment_review`: `/assets/reliability/assessments/<pk>/review/` [POST, Admin]
  - `assets:asset_condition_assessment_trigger_request`: `/assets/reliability/assessments/<pk>/trigger-request/` [POST]
- **Telemetry Readings:**
  - `assets:asset_telemetry_reading_list`: `/assets/reliability/telemetry/`
  - `assets:asset_telemetry_reading_create`: `/assets/reliability/telemetry/create/`
  - `assets:asset_telemetry_reading_detail`: `/assets/reliability/telemetry/<pk>/`
  - `assets:asset_telemetry_reading_edit`: `/assets/reliability/telemetry/<pk>/edit/`
  - `assets:asset_telemetry_reading_delete`: `/assets/reliability/telemetry/<pk>/delete/` [POST, Admin]
  - `assets:asset_telemetry_reading_flag_anomaly`: `/assets/reliability/telemetry/<pk>/flag-anomaly/` [POST]
  - `assets:asset_telemetry_reading_trigger_request`: `/assets/reliability/telemetry/<pk>/trigger-request/` [POST]
- **Failure Modes & Effects Analysis (FMEA):**
  - `assets:asset_failure_mode_list`: `/assets/reliability/failure-modes/`
  - `assets:asset_failure_mode_create`: `/assets/reliability/failure-modes/create/`
  - `assets:asset_failure_mode_detail`: `/assets/reliability/failure-modes/<pk>/`
  - `assets:asset_failure_mode_edit`: `/assets/reliability/failure-modes/<pk>/edit/`
  - `assets:asset_failure_mode_delete`: `/assets/reliability/failure-modes/<pk>/delete/` [POST, Admin]
  - `assets:asset_failure_mode_activate`: `/assets/reliability/failure-modes/<pk>/activate/` [POST]
  - `assets:asset_failure_mode_archive`: `/assets/reliability/failure-modes/<pk>/archive/` [POST, Admin]
- **Calibration Records:**
  - `assets:asset_calibration_record_list`: `/assets/reliability/calibrations/`
  - `assets:asset_calibration_record_create`: `/assets/reliability/calibrations/create/`
  - `assets:asset_calibration_record_detail`: `/assets/reliability/calibrations/<pk>/`
  - `assets:asset_calibration_record_edit`: `/assets/reliability/calibrations/<pk>/edit/`
  - `assets:asset_calibration_record_delete`: `/assets/reliability/calibrations/<pk>/delete/` [POST, Admin]
  - `assets:asset_calibration_record_quarantine`: `/assets/reliability/calibrations/<pk>/quarantine/` [POST, Admin]

### 11.8 Asset Warranty & Insurance Management
Namespace: `assets:`
- **Asset Warranties:**
  - `assets:asset_warranty_list`: `/assets/warranty-insurance/warranties/`
  - `assets:asset_warranty_create`: `/assets/warranty-insurance/warranties/create/`
  - `assets:asset_warranty_detail`: `/assets/warranty-insurance/warranties/<pk>/`
  - `assets:asset_warranty_edit`: `/assets/warranty-insurance/warranties/<pk>/edit/`
  - `assets:asset_warranty_delete`: `/assets/warranty-insurance/warranties/<pk>/delete/` [POST, Admin]
  - `assets:asset_warranty_activate`: `/assets/warranty-insurance/warranties/<pk>/activate/` [POST]
  - `assets:asset_warranty_renew`: `/assets/warranty-insurance/warranties/<pk>/renew/` [POST]
  - `assets:asset_warranty_void`: `/assets/warranty-insurance/warranties/<pk>/void/` [POST, Admin]
- **Warranty Claims:**
  - `assets:asset_warranty_claim_list`: `/assets/warranty-insurance/warranty-claims/`
  - `assets:asset_warranty_claim_create`: `/assets/warranty-insurance/warranty-claims/create/`
  - `assets:asset_warranty_claim_detail`: `/assets/warranty-insurance/warranty-claims/<pk>/`
  - `assets:asset_warranty_claim_edit`: `/assets/warranty-insurance/warranty-claims/<pk>/edit/`
  - `assets:asset_warranty_claim_delete`: `/assets/warranty-insurance/warranty-claims/<pk>/delete/` [POST, Admin]
  - `assets:asset_warranty_claim_submit`: `/assets/warranty-insurance/warranty-claims/<pk>/submit/` [POST]
  - `assets:asset_warranty_claim_review`: `/assets/warranty-insurance/warranty-claims/<pk>/review/` [POST]
  - `assets:asset_warranty_claim_settle`: `/assets/warranty-insurance/warranty-claims/<pk>/settle/` [POST]
  - `assets:asset_warranty_claim_reject`: `/assets/warranty-insurance/warranty-claims/<pk>/reject/` [POST]
- **Insurance Policies:**
  - `assets:asset_insurance_policy_list`: `/assets/warranty-insurance/policies/`
  - `assets:asset_insurance_policy_create`: `/assets/warranty-insurance/policies/create/`
  - `assets:asset_insurance_policy_detail`: `/assets/warranty-insurance/policies/<pk>/`
  - `assets:asset_insurance_policy_edit`: `/assets/warranty-insurance/policies/<pk>/edit/`
  - `assets:asset_insurance_policy_delete`: `/assets/warranty-insurance/policies/<pk>/delete/` [POST, Admin]
  - `assets:asset_insurance_policy_activate`: `/assets/warranty-insurance/policies/<pk>/activate/` [POST]
  - `assets:asset_insurance_policy_renew`: `/assets/warranty-insurance/policies/<pk>/renew/` [POST]
  - `assets:asset_insurance_policy_cancel`: `/assets/warranty-insurance/policies/<pk>/cancel/` [POST, Admin]
- **Insurance Claims:**
  - `assets:asset_insurance_claim_list`: `/assets/warranty-insurance/insurance-claims/`
  - `assets:asset_insurance_claim_create`: `/assets/warranty-insurance/insurance-claims/create/`
  - `assets:asset_insurance_claim_detail`: `/assets/warranty-insurance/insurance-claims/<pk>/`
  - `assets:asset_insurance_claim_edit`: `/assets/warranty-insurance/insurance-claims/<pk>/edit/`
  - `assets:asset_insurance_claim_delete`: `/assets/warranty-insurance/insurance-claims/<pk>/delete/` [POST, Admin]
  - `assets:asset_insurance_claim_assign_adjuster`: `/assets/warranty-insurance/insurance-claims/<pk>/assign-adjuster/` [POST]
  - `assets:asset_insurance_claim_file_proof`: `/assets/warranty-insurance/insurance-claims/<pk>/file-proof/` [POST]
  - `assets:asset_insurance_claim_settle`: `/assets/warranty-insurance/insurance-claims/<pk>/settle/` [POST]
  - `assets:asset_insurance_claim_deny`: `/assets/warranty-insurance/insurance-claims/<pk>/deny/` [POST]

### 11.9 Asset Disposal & Retirement
Namespace: `assets:`
- **Disposal Requests:**
  - `assets:asset_disposal_request_list`: `/assets/disposal/requests/`
  - `assets:asset_disposal_request_create`: `/assets/disposal/requests/create/`
  - `assets:asset_disposal_request_detail`: `/assets/disposal/requests/<pk>/`
  - `assets:asset_disposal_request_edit`: `/assets/disposal/requests/<pk>/edit/`
  - `assets:asset_disposal_request_delete`: `/assets/disposal/requests/<pk>/delete/` [POST, Admin]
  - `assets:asset_disposal_request_submit`: `/assets/disposal/requests/<pk>/submit/` [POST]
  - `assets:asset_disposal_request_appraise`: `/assets/disposal/requests/<pk>/appraise/` [POST]
  - `assets:asset_disposal_request_approve`: `/assets/disposal/requests/<pk>/approve/` [POST, Admin]
  - `assets:asset_disposal_request_reject`: `/assets/disposal/requests/<pk>/reject/` [POST, Admin]
  - `assets:asset_disposal_request_complete`: `/assets/disposal/requests/<pk>/complete/` [POST, Admin]
- **Resale Listings:**
  - `assets:asset_resale_listing_list`: `/assets/disposal/resale-listings/`
  - `assets:asset_resale_listing_create`: `/assets/disposal/resale-listings/create/`
  - `assets:asset_resale_listing_detail`: `/assets/disposal/resale-listings/<pk>/`
  - `assets:asset_resale_listing_edit`: `/assets/disposal/resale-listings/<pk>/edit/`
  - `assets:asset_resale_listing_delete`: `/assets/disposal/resale-listings/<pk>/delete/` [POST, Admin]
  - `assets:asset_resale_listing_record_bid`: `/assets/disposal/resale-listings/<pk>/record-bid/` [POST]
  - `assets:asset_resale_listing_accept_sale`: `/assets/disposal/resale-listings/<pk>/accept-sale/` [POST]
  - `assets:asset_resale_listing_mark_paid`: `/assets/disposal/resale-listings/<pk>/mark-paid/` [POST]
  - `assets:asset_resale_listing_mark_delivered`: `/assets/disposal/resale-listings/<pk>/mark-delivered/` [POST]
- **Asset Trade-Ins:**
  - `assets:asset_trade_in_list`: `/assets/disposal/trade-ins/`
  - `assets:asset_trade_in_create`: `/assets/disposal/trade-ins/create/`
  - `assets:asset_trade_in_detail`: `/assets/disposal/trade-ins/<pk>/`
  - `assets:asset_trade_in_edit`: `/assets/disposal/trade-ins/<pk>/edit/`
  - `assets:asset_trade_in_delete`: `/assets/disposal/trade-ins/<pk>/delete/` [POST, Admin]
  - `assets:asset_trade_in_surrender`: `/assets/disposal/trade-ins/<pk>/surrender/` [POST]
  - `assets:asset_trade_in_settle`: `/assets/disposal/trade-ins/<pk>/settle/` [POST, Admin]
- **Scrap & Salvage:**
  - `assets:asset_scrap_salvage_list`: `/assets/disposal/scrap-salvage/`
  - `assets:asset_scrap_salvage_create`: `/assets/disposal/scrap-salvage/create/`
  - `assets:asset_scrap_salvage_detail`: `/assets/disposal/scrap-salvage/<pk>/`
  - `assets:asset_scrap_salvage_edit`: `/assets/disposal/scrap-salvage/<pk>/edit/`
  - `assets:asset_scrap_salvage_delete`: `/assets/disposal/scrap-salvage/<pk>/delete/` [POST, Admin]
  - `assets:asset_scrap_salvage_certify_abatement`: `/assets/disposal/scrap-salvage/<pk>/certify-abatement/` [POST]
  - `assets:asset_scrap_salvage_record_cod`: `/assets/disposal/scrap-salvage/<pk>/record-cod/` [POST]
  - `assets:asset_scrap_salvage_settle`: `/assets/disposal/scrap-salvage/<pk>/settle/` [POST, Admin]

### 11.10 Lease & Rental Management
- **Lease Contracts:**
  - `assets:asset_lease_contract_list`: `/assets/leases/`
  - `assets:asset_lease_contract_create`: `/assets/leases/create/`
  - `assets:asset_lease_contract_detail`: `/assets/leases/<pk>/`
  - `assets:asset_lease_contract_edit`: `/assets/leases/<pk>/edit/`
  - `assets:asset_lease_contract_delete`: `/assets/leases/<pk>/delete/` [POST, Admin]
  - `assets:asset_lease_contract_calculate`: `/assets/leases/<pk>/calculate/` [POST]
  - `assets:asset_lease_contract_activate`: `/assets/leases/<pk>/activate/` [POST, Admin]
  - `assets:asset_lease_contract_terminate`: `/assets/leases/<pk>/terminate/` [POST]
- **Lease Payment & Amortization Schedules:**
  - `assets:asset_lease_schedule_list`: `/assets/lease-schedules/`
  - `assets:asset_lease_schedule_create`: `/assets/lease-schedules/create/`
  - `assets:asset_lease_schedule_detail`: `/assets/lease-schedules/<pk>/`
  - `assets:asset_lease_schedule_edit`: `/assets/lease-schedules/<pk>/edit/`
  - `assets:asset_lease_schedule_delete`: `/assets/lease-schedules/<pk>/delete/` [POST, Admin]
  - `assets:asset_lease_schedule_mark_paid`: `/assets/lease-schedules/<pk>/mark-paid/` [POST]
  - `assets:asset_lease_schedule_accrue`: `/assets/lease-schedules/<pk>/accrue/` [POST]
- **Lease Modifications & Remeasurements:**
  - `assets:asset_lease_modification_list`: `/assets/modifications/`
  - `assets:asset_lease_modification_create`: `/assets/modifications/create/`
  - `assets:asset_lease_modification_detail`: `/assets/modifications/<pk>/`
  - `assets:asset_lease_modification_edit`: `/assets/modifications/<pk>/edit/`
  - `assets:asset_lease_modification_delete`: `/assets/modifications/<pk>/delete/` [POST, Admin]
  - `assets:asset_lease_modification_approve`: `/assets/modifications/<pk>/approve/` [POST, Admin]
- **Lease vs. Buy Capital Analyses:**
  - `assets:asset_lease_buy_analysis_list`: `/assets/lease-buy-analyses/`
  - `assets:asset_lease_buy_analysis_create`: `/assets/lease-buy-analyses/create/`
  - `assets:asset_lease_buy_analysis_detail`: `/assets/lease-buy-analyses/<pk>/`
  - `assets:asset_lease_buy_analysis_edit`: `/assets/lease-buy-analyses/<pk>/edit/`
  - `assets:asset_lease_buy_analysis_delete`: `/assets/lease-buy-analyses/<pk>/delete/` [POST, Admin]
  - `assets:asset_lease_buy_analysis_evaluate`: `/assets/lease-buy-analyses/<pk>/evaluate/` [POST]

### 11.11 Compliance & Regulatory Management
- **Compliance Frameworks:**
  - `assets:asset_compliance_framework_list`: `/assets/compliance/frameworks/`
  - `assets:asset_compliance_framework_create`: `/assets/compliance/frameworks/create/`
  - `assets:asset_compliance_framework_detail`: `/assets/compliance/frameworks/<pk>/`
  - `assets:asset_compliance_framework_edit`: `/assets/compliance/frameworks/<pk>/edit/`
  - `assets:asset_compliance_framework_delete`: `/assets/compliance/frameworks/<pk>/delete/` [POST, Admin]
- **Compliance Audits:**
  - `assets:asset_compliance_audit_list`: `/assets/compliance/audits/`
  - `assets:asset_compliance_audit_create`: `/assets/compliance/audits/create/`
  - `assets:asset_compliance_audit_detail`: `/assets/compliance/audits/<pk>/`
  - `assets:asset_compliance_audit_edit`: `/assets/compliance/audits/<pk>/edit/`
  - `assets:asset_compliance_audit_start`: `/assets/compliance/audits/<pk>/start/` [POST]
  - `assets:asset_compliance_audit_complete`: `/assets/compliance/audits/<pk>/complete/` [POST]
  - `assets:asset_compliance_audit_delete`: `/assets/compliance/audits/<pk>/delete/` [POST, Admin]
- **Operating Permits & Licenses:**
  - `assets:asset_permit_license_list`: `/assets/compliance/permits/`
  - `assets:asset_permit_license_create`: `/assets/compliance/permits/create/`
  - `assets:asset_permit_license_detail`: `/assets/compliance/permits/<pk>/`
  - `assets:asset_permit_license_edit`: `/assets/compliance/permits/<pk>/edit/`
  - `assets:asset_permit_license_renew`: `/assets/compliance/permits/<pk>/renew/` [POST]
  - `assets:asset_permit_license_delete`: `/assets/compliance/permits/<pk>/delete/` [POST, Admin]
- **Compliance Incidents & Citations:**
  - `assets:asset_compliance_incident_list`: `/assets/compliance/incidents/`
  - `assets:asset_compliance_incident_create`: `/assets/compliance/incidents/create/`
  - `assets:asset_compliance_incident_detail`: `/assets/compliance/incidents/<pk>/`
  - `assets:asset_compliance_incident_edit`: `/assets/compliance/incidents/<pk>/edit/`
  - `assets:asset_compliance_incident_resolve`: `/assets/compliance/incidents/<pk>/resolve/` [POST]
  - `assets:asset_compliance_incident_close`: `/assets/compliance/incidents/<pk>/close/` [POST]
  - `assets:asset_compliance_incident_delete`: `/assets/compliance/incidents/<pk>/delete/` [POST, Admin]

---

## Conventions & Gotchas

1. **Multi-Tenancy**:
   - All models inherit from `TenantNumbered` (`TenantOwned`).
   - Every view must filter `tenant=request.tenant`.
   - Every ModelForm uses `reject_foreign(self, cleaned_data, [...])` including user ForeignKeys.
2. **Audit Logging Signature**:
   - `write_audit_log(request.user, instance, action, changes={...}, tenant=request.tenant)`.
3. **Operational Spine**:
   - Assets are tracked on `scm.Asset`. Movement receipts update `asset.location`. Loss write-offs update `asset.status = 'disposed'`. Do not create redundant asset tables.
4. **Theme CSS Classes**:
   - Badges: `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-slate`, `badge-muted`.
   - Component classes: `.table-wrap`, `.text-brand`, `.empty-state`, `.pagination`.
5. **RBAC & Privilege Separation**:
   - Audit variance reconciliation and write-off authorizations require `@tenant_admin_required`. Guard UI buttons with `{% if request.user.is_superuser or request.user.is_tenant_admin %}`.
6. **Filter-Preserving Pagination**:
   - All filter parameters (`?q=`, `?status=`, `?type=`, `?location=`, `?asset=`) are strictly preserved in pagination links.

---

## Common Development Tasks

### Running Seeder
```powershell
venv\Scripts\python.exe manage.py seed_assets
```
Idempotent across all tenants. Demo login: `admin_acme` / `password`.

### Running Tests
```powershell
venv\Scripts\python.exe -m pytest apps/assets/tests/
```
Unfiltered run on SQLite in-memory test database (1,686 passing tests across 11.1 through 11.11).

---

## Sidebar Wiring (`apps/core/navigation.py`)
- `11.1`: Asset Procurement & Capitalization (`assets:asset_requisition_list`)
- `11.2`: Inventory Audits & Tracking (`assets:asset_audit_list`)
- `11.3`: Classification & Taxonomy (`assets:asset_category_list`)
- `11.4`: Depreciation & Financials (`assets:depreciation_schedule_list`)
- `11.5`: Maintenance & Repair (`assets:asset_maintenance_request_list`)
- `11.6`: Performance & Utilization (`assets:asset_downtime_log_list`)
- `11.7`: Reliability & Condition Monitoring (`assets:asset_condition_assessment_list`)
- `11.8`: Warranty & Insurance Management (`assets:asset_warranty_list`)
- `11.9`: Asset Disposal & Retirement (`assets:asset_disposal_request_list`)
- `11.10`: Lease & Rental Management (`assets:asset_lease_contract_list`)
- `11.11`: Compliance & Regulatory Management (`assets:asset_compliance_framework_list`)

