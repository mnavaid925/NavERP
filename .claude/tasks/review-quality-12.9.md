# Review Findings: Quality Sub-module 12.9 (Final Quality Control / Outgoing Quality Control)

**Changeset**: `e58ed9e5cac450ee54d13b851d396e1d0eed24f7...HEAD`
**Date**: 2026-11-19
**Reviewers**: `code-reviewer`, `explorer`, `frontend-reviewer`, `performance-reviewer`, `qa-smoke-tester`, `security-reviewer`

---

## Critical

- [ ] **C1**: `apps/quality/models/FinalQuality/CertificatesOfConformance.py:150` & `apps/quality/views/FinalQuality/CertificatesOfConformance.py:194`
  - Unhandled `RelatedObjectDoesNotExist` crash in `CertificateOfConformance.__str__` during CSV export. `__str__` dereferences `self.customer.name` without guarding against unpersisted or null customer, causing `write_audit_log(..., CertificateOfConformance(), ...)` to trigger an immediate HTTP 500 error on export.
  - *Fix*: In `CertificatesOfConformance.py:150`, guard customer access (`self.customer.name if getattr(self, "customer_id", None) and hasattr(self, "customer") and self.customer else "No Customer"`), and in `certificate_of_conformance_export`, pass `None` to `write_audit_log` with `changes={"model": "CertificateOfConformance"}`.

- [ ] **C2**: `apps/quality/views/FinalQuality/CertificatesOfConformance.py:175-189`
  - State guard and authorization bypass on digital signature endpoint (`certificate_of_conformance_sign`). The view lacks a check on `certificate.status` and is gated only by `@login_required`. Any authenticated tenant member can issue a POST to re-sign and overwrite the cryptographic hash, date, and signatory on already approved (`approved_signed`) or revoked certificates.
  - *Fix*: Add status guard `if certificate.status in ("approved_signed", "revoked"): messages.error(request, f"Certificate {certificate.number} is locked and cannot be re-signed."); return redirect("quality:certificate_of_conformance_detail", pk=certificate.pk)` and require tenant admin or quality signatory authority.

- [ ] **C3**: `apps/quality/views/FinalQuality/CertificatesOfConformance.py:177-184`
  - Inadequate cryptographic signature binding in `certificate_of_conformance_sign`. The SHA-256 digest is calculated solely from metadata (`number`, `tenant_id`, `user_id`, `now`), omitting the actual attested document contents (`customer_id`, `item_code`, `lot_number`, `certified_quantity`, `applicable_specifications`, `test_results_summary`, `conformance_statement`), failing to detect subsequent specification or test tampering.
  - *Fix*: Bind the critical document specification and test fields into the SHA-256 digest before hashing.

---

## Important

- [ ] **I1**: `apps/quality/views/FinalQuality/OqcHoldBoard.py:26-35, 51-55`
  - Slicing `[:10]` is applied to `pending_inspection_lots`, `pending_cocs`, and `ready_releases` before calling `.count()`, producing SQL subqueries and capping KPI summary cards (`pending_lot_count`, `pending_coc_count`, `ready_release_count`) at a maximum of 10.
  - *Fix*: In `oqc_hold_board`, compute `.count()` on the unsliced querysets before taking the `[:10]` preview slice for the template lists.

- [ ] **I2**: `apps/quality/management/commands/seed_quality.py:3189`
  - `seed_quality.py` seeds `lot_2` with `sampling_standard="c0_zero_acceptance"`, but `FinalInspectionLot.SAMPLING_STANDARD_CHOICES` specifies `"c_zero_sampling"`, causing raw string rendering and broken dropdown binding.
  - *Fix*: Change `sampling_standard="c0_zero_acceptance"` to `sampling_standard="c_zero_sampling"` in `apps/quality/management/commands/seed_quality.py:3189`.

- [ ] **I3**: Delete action permission guard mismatch in 8 template locations
  - Files:
    - `templates/quality/finalquality/final_inspection_lot/list.html:199` & `detail.html:63`
    - `templates/quality/finalquality/certificate_of_conformance/list.html:177` & `detail.html:56`
    - `templates/quality/finalquality/packaging_label_verification/list.html:173` & `detail.html:44`
    - `templates/quality/finalquality/quality_release_authorization/list.html:193` & `detail.html:67`
  - Delete forms check `{% if user.is_staff or user.is_superuser %}` instead of `{% if request.user.is_superuser or request.user.is_tenant_admin %}`, hiding delete buttons from valid tenant admins who lack the Django `is_staff` flag.
  - *Fix*: Update guard to `{% if request.user.is_superuser or request.user.is_tenant_admin %}` across all 8 locations.

- [ ] **I4**: `templates/quality/finalquality/final_inspection_lot/form.html:125-133`
  - Core field omission: `minor_defects_count` is declared in `FinalInspectionLotForm.Meta.fields` and displayed on detail pages, but was omitted from Section 2 in `form.html` (only `critical_defects_count` and `major_defects_count` are present).
  - *Fix*: Add `minor_defects_count` input group after `major_defects_count`.

- [ ] **I5**: N+1 queries in CSV export views
  - Files:
    - `apps/quality/views/FinalQuality/QualityReleaseAuthorizations.py:198` (missing `select_related("customer", "releasing_officer")`)
    - `apps/quality/views/FinalQuality/CertificatesOfConformance.py:195` (missing `select_related("customer", "authorized_signatory")`)
    - `apps/quality/views/FinalQuality/PackagingLabelVerifications.py:168` (missing `select_related("verifier")`)
  - Un-prefetched foreign keys accessed per-row over export querysets causing 1+2N queries.
  - *Fix*: Add `.select_related(...)` to the export querysets.

- [ ] **I6**: Chained N+1 queries via `__str__` on form `<select>` dropdowns (Lesson L18)
  - Files:
    - `apps/quality/forms/FinalQuality/QualityReleaseAuthorizations.py:108-111` (`certificate_of_conformance` field)
    - `apps/quality/forms/FinalQuality/{FinalInspectionLots,QualityReleaseAuthorizations,CertificatesOfConformance}.py` (`sales_order` field)
  - `CertificateOfConformance.__str__` and `SalesOrder.__str__` traverse `self.customer.name`. Choice rendering triggers 1+N queries on form load.
  - *Fix*: Add `.select_related("customer")` to these field querysets in form `__init__`.

- [ ] **I7**: `apps/quality/views/FinalQuality/CertificatesOfConformance.py:140-159`
  - Post-signing mutation vulnerability: `certificate_of_conformance_edit` permits editing approved and signed certificates (`approved_signed`) or revoked certificates, allowing certified specifications and test results to be altered while retaining the signature stamp.
  - *Fix*: Add guard at top of `certificate_of_conformance_edit` blocking edits when `certificate.status in ("approved_signed", "revoked")`.

- [ ] **I8**: `apps/quality/forms/FinalQuality/CertificatesOfConformance.py:15-40`
  - Mass assignment & signatory forgery via form fields: `CertificateOfConformanceForm.Meta.fields` includes workflow-controlled `"status"`, `"authorized_signatory"`, and `"signed_date"`, allowing direct form submission to fake approval states without the cryptographic signing flow.
  - *Fix*: Exclude `"status"`, `"authorized_signatory"`, and `"signed_date"` from form `Meta.fields`.

- [ ] **I9**: Cross-record counterparty integrity check in forms
  - Files: `apps/quality/forms/FinalQuality/QualityReleaseAuthorizations.py:122-139` & `CertificatesOfConformance.py:98-108`
  - Neither form validates that linked `sales_order`, `inspection_lot`, or `certificate_of_conformance` belong to the same customer as the parent record.
  - *Fix*: Add cross-record counterparty validation in `clean()` verifying `linked.customer_id == customer.pk` when both are present.

- [ ] **I10**: `apps/quality/views/FinalQuality/QualityReleaseAuthorizations.py:180-200` & `FinalInspectionLots.py:174-193`
  - Missing authorization gate and mandatory reason on quality hold toggles: views are gated only by `@login_required`, and activating a quarantine hold does not require a non-empty `hold_reason`.
  - *Fix*: Require `@tenant_admin_required` or quality authority, and validate `hold_reason` when placing on hold.

---

## Minor

- [ ] **M1**: `apps/quality/models/FinalQuality/FinalInspectionLots.py:176, 183`
  - Model `related_name` contract divergence: uses `fqc_inspections_conducted` and `fqc_usage_decisions` instead of contract-specified `fqc_inspections_performed` and `fqc_usage_decisions_made`.
  - *Fix*: Align related_name or document aliases.

- [ ] **M2**: `apps/quality/views/FinalQuality/OqcHoldBoard.py:38-43`
  - Discrepancy between `ready_releases` queryset in `oqc_hold_board` and `is_cleared_to_ship` property.
  - *Fix*: Filter on prerequisite boolean flags (`final_inspection_passed=True, no_open_ncrs_or_capas=True, packaging_label_approved=True, coc_issued_and_signed=True`).

- [ ] **M3**: `templates/quality/finalquality/{final_inspection_lot,certificate_of_conformance,quality_release_authorization}/form.html`
  - Manual text fallback fields (`sales_order_number`, `work_order_number`, `shipment_number`) omitted from form templates alongside relational dropdowns.
  - *Fix*: Render optional manual text inputs.

- [ ] **M4**: `templates/quality/finalquality/oqc_hold_board.html:116, 137`
  - Fallback handling for blank shipment and lot references on hold board cards.
  - *Fix*: Add empty fallbacks (`|default:"—"`).

- [ ] **M5**: `apps/quality/views/FinalQuality/OqcHoldBoard.py:26-29`
  - Dead query: `pending_inspection_lots` passed into context but never rendered by template.
  - *Fix*: Compute `pending_lot_count` directly and omit unneeded queryset from context.

- [ ] **M6**: `apps/quality/views/FinalQuality/OqcHoldBoard.py:15-24`
  - Duplicate SQL queries on hold board active lists: `.count()` followed immediately by template iteration.
  - *Fix*: Pre-evaluate active hold lists or consolidate counts.

- [ ] **M7**: `apps/quality/models/FinalQuality/QualityReleaseAuthorizations.py:163-167` & `FinalInspectionLots.py:193-198`
  - Missing compound indexes on `(tenant, customer)` for `QualityReleaseAuthorization` and `(tenant, inspection_stage)` for `FinalInspectionLot`.
  - *Fix*: Add compound indexes in `Meta.indexes`.

- [ ] **M8**: `apps/quality/views/FinalQuality/{FinalInspectionLots,PackagingLabelVerifications,CertificatesOfConformance,QualityReleaseAuthorizations}.py`
  - Over-fetching unused `select_related` joins in list views.
  - *Fix*: Trim unused joins.

- [ ] **M9**: `apps/quality/views/FinalQuality/CertificatesOfConformance.py` & `QualityReleaseAuthorizations.py`
  - Deletion guards for signed certificates and authorized releases to preserve regulatory audit trails.
  - *Fix*: Reject hard-deleting approved/signed certificates or authorized releases without prior revocation.

- [ ] **M10**: `apps/quality/forms/FinalQuality/QualityReleaseAuthorizations.py:122-139`
  - Form validation permits `status="authorized"` and `release_disposition="released_full"` while `is_on_hold=True`.
  - *Fix*: Add validation in `clean()` rejecting authorization while on hold.
