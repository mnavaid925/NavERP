# Module 12.9 Pre-Build Contract — Final Quality Control (FQC) / Outgoing Quality Control (OQC) (`apps/quality/`)

> Frozen in Phase 3.1 before any Phase 3.3 entity build. Every model field, `max_length`,
> `CHOICES` tuple, badge class (`static/css/theme.css`), index/constraint name (`<= 30` chars),
> form `Meta.fields` + excluded fields, URL route/name (literal before `<int:pk>`), exact view
> context key, filter param, `AuditLog.action` verb (`<= 10` chars), and `LIVE_LINKS["12.9"]`
> entry below is authoritative across backend, templates, smoke tests, reviews, and unit/security tests.

- **Parent App**: `apps.quality` (Extends existing app; incremental migration `0015_...`; NO changes to `config/settings.py` or `config/urls.py`)
- **Package Directories**:
  - `apps/quality/models/FinalQuality/`
  - `apps/quality/forms/FinalQuality/`
  - `apps/quality/views/FinalQuality/`
  - `apps/quality/urls/FinalQuality/`
  - `templates/quality/finalquality/{final_inspection_lot,certificate_of_conformance,packaging_label_verification,quality_release_authorization}/{list,detail,form}.html` + `templates/quality/finalquality/oqc_hold_board.html`
- **AuditLog `action` Max Length (`<= 10` chars, L66)**:
  - Allowed `action` verbs passed to `write_audit_log(request.user, obj, verb, tenant=request.tenant)`:
    `"create"`, `"update"`, `"delete"`, `"release"`, `"hold"`, `"sign"`, `"export"` (all `<= 8` chars).
- **Theme CSS Classes (`static/css/theme.css`, L33)**:
  - Allowed badge classes ONLY: `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`.
  - Allowed `.stat-icon` colors ONLY: `blue`, `green`, `orange`, `purple`, `slate`, `red`.
  - Detail views use `<dl class="detail-grid"><div class="detail-item"><dt>...</dt><dd>...</dd></div></dl>`.
- **Pagination & CSV Standard**:
  - `PAGE_SIZE = 15` (`Paginator(qs, PAGE_SIZE)`).
  - Paginator guards `has_previous` / `has_next` (L9).
  - CSV exports stream via `HttpResponse(content_type="text/csv")` using CSV formula neutralization (`csv_safe` or leading quote stripping) + `X-Content-Type-Options: nosniff`.
- **Tenant Scoping & FK Isolation (L29, L39, L11)**:
  - All foreign keys are tenant-scoped: `accounts.User`, `core.OrgUnit`, `core.Party`, `quality.ControlledDocument`, `quality.NonConformanceReport`, `quality.ProcessDeviation`, `scm.WorkOrder`, `scm.SalesOrder`, `scm.Shipment`.
  - FKs populated in forms using `Model.objects.filter(tenant=self.tenant)` and validated in `clean()` via `reject_foreign(...)`.
  - List view FK query param parsing MUST check `.isdigit()` (L11) before filtering.

---

## 1. Models & Choices Contract (`apps/quality/models/FinalQuality/`)

All 4 models inherit `apps.quality.models._base.TenantNumbered` (`tenant` FK `core.Tenant`, `number` `CharField(32, editable=False)`, `created_at`, `updated_at`, collision-retrying `save()`).

### 1.1 `FinalInspectionLot` (`FinalInspectionLots.py`)
- **`NUMBER_PREFIX`**: `"QFQC"`
- **`Meta.ordering`**: `["-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Final Inspection Lot"` / `"Final Inspection Lots"`
- **Choices & Badge Maps**:
  - `INSPECTION_STAGE_CHOICES` (`max_length=30`):
    - `("finished_goods_dock", "Finished Goods Receiving / Dock")`
    - `("pre_packaging_fqc", "Pre-Packaging Final Inspection")`
    - `("post_packaging_oqc", "Post-Packaging Outgoing Inspection")`
    - `("functional_end_of_line", "Functional End-of-Line Test")`
    - `("pre_shipment_audit", "Pre-Shipment Customer Audit")`
  - `SAMPLING_STANDARD_CHOICES` (`max_length=30`):
    - `("ansi_asq_z1_4_normal", "ANSI/ASQ Z1.4 (ISO 2859-1) Normal II")`
    - `("ansi_asq_z1_4_tightened", "ANSI/ASQ Z1.4 Tightened III")`
    - `("ansi_asq_z1_4_reduced", "ANSI/ASQ Z1.4 Reduced I")`
    - `("c_zero_sampling", "Squeglia C=0 Zero Acceptance Plan")`
    - `("hundred_percent_screening", "100% 1-to-1 Screening Inspection")`
    - `("custom_protocol", "Custom Customer Protocol")`
  - `STATUS_CHOICES` (`max_length=20`):
    - `("draft", "Draft / Scheduled")`
    - `("in_progress", "In Progress")`
    - `("completed", "Completed")`
    - `("cancelled", "Cancelled")`
  - `USAGE_DECISION_CHOICES` (`max_length=30`):
    - `("pending", "Pending Decision")`
    - `("accepted", "Accepted / Conforming")`
    - `("accepted_with_concession", "Accepted with Concession")`
    - `("quarantined_hold", "Quarantined on Hold")`
    - `("rejected_mrb", "Rejected to MRB")`
  - `STAGE_CSS`:
    - `"finished_goods_dock": "badge-slate"`
    - `"pre_packaging_fqc": "badge-info"`
    - `"post_packaging_oqc": "badge-slate"`
    - `"functional_end_of_line": "badge-amber"`
    - `"pre_shipment_audit": "badge-slate"`
  - `STATUS_CSS`:
    - `"draft": "badge-slate"`
    - `"in_progress": "badge-amber"`
    - `"completed": "badge-green"`
    - `"cancelled": "badge-muted"`
  - `USAGE_DECISION_CSS`:
    - `"pending": "badge-slate"`
    - `"accepted": "badge-green"`
    - `"accepted_with_concession": "badge-info"`
    - `"quarantined_hold": "badge-red"`
    - `"rejected_mrb": "badge-red"`
- **Fields**:
  - `title`: `CharField(max_length=255)`
  - `inspection_stage`: `CharField(max_length=30, choices=INSPECTION_STAGE_CHOICES, default="post_packaging_oqc", db_index=True)`
  - `sampling_standard`: `CharField(max_length=30, choices=SAMPLING_STANDARD_CHOICES, default="ansi_asq_z1_4_normal")`
  - `aql_critical`: `DecimalField(max_digits=4, decimal_places=2, default=Decimal("0.00"))`
  - `aql_major`: `DecimalField(max_digits=4, decimal_places=2, default=Decimal("1.00"))`
  - `aql_minor`: `DecimalField(max_digits=4, decimal_places=2, default=Decimal("4.00"))`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default="draft", db_index=True)`
  - `usage_decision`: `CharField(max_length=30, choices=USAGE_DECISION_CHOICES, default="pending", db_index=True)`
  - `decision_rationale`: `TextField(blank=True)`
  - `item_code`: `CharField(max_length=100, blank=True)`
  - `item_name`: `CharField(max_length=255, blank=True)`
  - `lot_number`: `CharField(max_length=100, blank=True)`
  - `batch_number`: `CharField(max_length=100, blank=True)`
  - `serial_number_range`: `CharField(max_length=255, blank=True, help_text="e.g. SN-1000 through SN-1250")`
  - `lot_quantity`: `PositiveIntegerField(default=1)`
  - `sample_size_inspected`: `PositiveIntegerField(default=1)`
  - `critical_defects_count`: `PositiveIntegerField(default=0)`
  - `major_defects_count`: `PositiveIntegerField(default=0)`
  - `minor_defects_count`: `PositiveIntegerField(default=0)`
  - `units_passed`: `PositiveIntegerField(default=0)`
  - `units_rejected`: `PositiveIntegerField(default=0)`
  - `visual_inspection_passed`: `BooleanField(default=True)`
  - `dimensional_inspection_passed`: `BooleanField(default=True)`
  - `functional_test_passed`: `BooleanField(default=True)`
  - `packaging_inspection_passed`: `BooleanField(default=True)`
  - `is_on_hold`: `BooleanField(default=False, db_index=True)`
  - `hold_reason`: `TextField(blank=True)`
  - `customer`: `ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="final_inspection_lots")`
  - `sales_order_number`: `CharField(max_length=64, blank=True)`
  - `sales_order`: `ForeignKey("scm.SalesOrder", on_delete=models.SET_NULL, null=True, blank=True, related_name="final_inspection_lots")`
  - `work_order_number`: `CharField(max_length=64, blank=True)`
  - `work_order`: `ForeignKey("scm.WorkOrder", on_delete=models.SET_NULL, null=True, blank=True, related_name="final_inspection_lots")`
  - `inspection_plan`: `ForeignKey("quality.ControlledDocument", on_delete=models.SET_NULL, null=True, blank=True, related_name="final_inspection_lots")`
  - `non_conformance`: `ForeignKey("quality.NonConformanceReport", on_delete=models.SET_NULL, null=True, blank=True, related_name="final_inspection_lots")`
  - `process_deviation`: `ForeignKey("quality.ProcessDeviation", on_delete=models.SET_NULL, null=True, blank=True, related_name="final_inspection_lots")`
  - `inspector`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="fqc_inspections_performed")`
  - `decision_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="fqc_usage_decisions_made")`
  - `inspection_date`: `DateField(null=True, blank=True)`
  - `decision_date`: `DateField(null=True, blank=True)`
  - `inspection_notes`: `TextField(blank=True)`
- **Indexes**:
  - `models.Index(fields=["tenant", "status"], name="quality_fqc_tnt_stat_idx")`
  - `models.Index(fields=["tenant", "usage_decision"], name="quality_fqc_tnt_dec_idx")`
  - `models.Index(fields=["tenant", "lot_number"], name="quality_fqc_tnt_lot_idx")`

---

### 1.2 `CertificateOfConformance` (`CertificatesOfConformance.py`)
- **`NUMBER_PREFIX`**: `"QCOC"`
- **`Meta.ordering`**: `["-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Certificate of Conformance"` / `"Certificates of Conformance"`
- **Choices & Badge Maps**:
  - `CERTIFICATE_TYPE_CHOICES` (`max_length=30`):
    - `("standard_commercial", "Standard Commercial (ISO 9001)")`
    - `("aerospace_as9100_as9102", "Aerospace (AS9100 / AS9102)")`
    - `("medical_device_iso13485", "Medical Device (ISO 13485 / FDA)")`
    - `("automotive_iatf_16949", "Automotive (IATF 16949)")`
    - `("custom_customer_format", "Customer Specific Format")`
  - `STATUS_CHOICES` (`max_length=20`):
    - `("draft", "Draft")`
    - `("under_review", "Under Review")`
    - `("approved_signed", "Approved & Digitally Signed")`
    - `("revoked", "Revoked / Superseded")`
  - `TYPE_CSS`:
    - `"standard_commercial": "badge-slate"`
    - `"aerospace_as9100_as9102": "badge-info"`
    - `"medical_device_iso13485": "badge-green"`
    - `"automotive_iatf_16949": "badge-amber"`
    - `"custom_customer_format": "badge-slate"`
  - `STATUS_CSS`:
    - `"draft": "badge-slate"`
    - `"under_review": "badge-amber"`
    - `"approved_signed": "badge-green"`
    - `"revoked": "badge-red"`
- **Fields**:
  - `title`: `CharField(max_length=255)`
  - `certificate_type`: `CharField(max_length=30, choices=CERTIFICATE_TYPE_CHOICES, default="standard_commercial", db_index=True)`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default="draft", db_index=True)`
  - `customer`: `ForeignKey("core.Party", on_delete=models.CASCADE, related_name="certificates_of_conformance")`
  - `customer_po_number`: `CharField(max_length=64, blank=True)`
  - `sales_order_number`: `CharField(max_length=64, blank=True)`
  - `sales_order`: `ForeignKey("scm.SalesOrder", on_delete=models.SET_NULL, null=True, blank=True, related_name="quality_certificates_of_conformance")`
  - `shipment_number`: `CharField(max_length=64, blank=True)`
  - `shipment`: `ForeignKey("scm.Shipment", on_delete=models.SET_NULL, null=True, blank=True, related_name="quality_certificates_of_conformance")`
  - `item_code`: `CharField(max_length=100, blank=True)`
  - `item_name`: `CharField(max_length=255, blank=True)`
  - `revision`: `CharField(max_length=32, blank=True, default="Rev A")`
  - `lot_number`: `CharField(max_length=100, blank=True)`
  - `batch_number`: `CharField(max_length=100, blank=True)`
  - `serial_numbers_text`: `TextField(blank=True, help_text="Comma-separated or newline-separated serial numbers covered by this certificate")`
  - `certified_quantity`: `PositiveIntegerField(default=1)`
  - `inspection_lot`: `ForeignKey("quality.FinalInspectionLot", on_delete=models.SET_NULL, null=True, blank=True, related_name="certificates_of_conformance")`
  - `applicable_specifications`: `TextField(blank=True, help_text="Industry, military, or engineering specifications complied with (e.g. ASTM A240, Mil-Spec, ISO 9001)")`
  - `test_results_summary`: `TextField(blank=True, help_text="Summary of dimensional, tensile, hardness, electrical, or functional test outcomes")`
  - `conformance_statement`: `TextField(blank=True, help_text="Legal declaration certifying goods conform in all respects to drawing, contract, and specs")`
  - `authorized_signatory`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="cocs_authorized")`
  - `signatory_title`: `CharField(max_length=100, blank=True, default="Director of Quality Assurance")`
  - `signed_date`: `DateField(null=True, blank=True)`
  - `digital_signature_hash`: `CharField(max_length=128, blank=True, help_text="Cryptographic SHA-256 hash stamp of sign-off")`
  - `qr_verification_code`: `CharField(max_length=64, blank=True, unique=True, help_text="Unique tamper-evident token for public or customer verification")`
  - `notes`: `TextField(blank=True)`
- **Indexes**:
  - `models.Index(fields=["tenant", "status"], name="quality_coc_tnt_stat_idx")`
  - `models.Index(fields=["tenant", "certificate_type"], name="quality_coc_tnt_type_idx")`
  - `models.Index(fields=["tenant", "customer"], name="quality_coc_tnt_cust_idx")`

---

### 1.3 `PackagingLabelVerification` (`PackagingLabelVerifications.py`)
- **`NUMBER_PREFIX`**: `"QPKG"`
- **`Meta.ordering`**: `["-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Packaging & Label Verification"` / `"Packaging & Label Verifications"`
- **Choices & Badge Maps**:
  - `BARCODE_SYMBOLOGY_CHOICES` (`max_length=30`):
    - `("code_128_1d", "Code 128 (1D Linear)")`
    - `("datamatrix_gs1_2d", "GS1 DataMatrix (2D)")`
    - `("qr_code_2d", "QR Code (2D)")`
    - `("gs1_128_sscc", "GS1-128 / SSCC Carton Code")`
    - `("upc_ean_retail", "UPC-A / EAN-13 Retail Code")`
    - `("other", "Other Symbology")`
  - `ISO_IEC_GRADE_CHOICES` (`max_length=20`):
    - `("grade_a_4_0", "Grade A (3.5 - 4.0) Excellent")`
    - `("grade_b_3_0", "Grade B (2.5 - 3.4) Good")`
    - `("grade_c_2_0", "Grade C (1.5 - 2.4) Acceptable")`
    - `("grade_d_1_0", "Grade D (0.5 - 1.4) Marginal")`
    - `("grade_f_fail", "Grade F (0.0 - 0.4) Unacceptable / Fail")`
  - `STATUS_CHOICES` (`max_length=20`):
    - `("draft", "Draft / Staged")`
    - `("verified", "Verified / Completed")`
    - `("failed", "Failed Verification")`
    - `("cancelled", "Cancelled")`
  - `DISPOSITION_CHOICES` (`max_length=25`):
    - `("pending", "Pending Verification")`
    - `("pass_released", "Pass / Released to Pack")`
    - `("relabel_required", "Relabeling Required")`
    - `("repack_required", "Repackaging Required")`
    - `("reject_quarantine", "Reject / Quarantine")`
  - `BARCODE_CSS`:
    - `"code_128_1d": "badge-slate"`
    - `"datamatrix_gs1_2d": "badge-info"`
    - `"qr_code_2d": "badge-info"`
    - `"gs1_128_sscc": "badge-amber"`
    - `"upc_ean_retail": "badge-slate"`
    - `"other": "badge-muted"`
  - `ISO_IEC_GRADE_CSS`:
    - `"grade_a_4_0": "badge-green"`
    - `"grade_b_3_0": "badge-green"`
    - `"grade_c_2_0": "badge-amber"`
    - `"grade_d_1_0": "badge-amber"`
    - `"grade_f_fail": "badge-red"`
  - `STATUS_CSS`:
    - `"draft": "badge-slate"`
    - `"verified": "badge-green"`
    - `"failed": "badge-red"`
    - `"cancelled": "badge-muted"`
  - `DISPOSITION_CSS`:
    - `"pending": "badge-slate"`
    - `"pass_released": "badge-green"`
    - `"relabel_required": "badge-amber"`
    - `"repack_required": "badge-amber"`
    - `"reject_quarantine": "badge-red"`
- **Fields**:
  - `title`: `CharField(max_length=255)`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default="draft", db_index=True)`
  - `disposition`: `CharField(max_length=25, choices=DISPOSITION_CHOICES, default="pending", db_index=True)`
  - `item_code`: `CharField(max_length=100, blank=True)`
  - `item_name`: `CharField(max_length=255, blank=True)`
  - `lot_number`: `CharField(max_length=100, blank=True)`
  - `carton_count_inspected`: `PositiveIntegerField(default=1)`
  - `label_part_number`: `CharField(max_length=100, blank=True)`
  - `label_artwork_revision`: `CharField(max_length=32, blank=True, default="Rev 1")`
  - `artwork_master`: `ForeignKey("quality.ControlledDocument", on_delete=models.SET_NULL, null=True, blank=True, related_name="packaging_verifications", help_text="Released artwork master specification")`
  - `barcode_symbology`: `CharField(max_length=30, choices=BARCODE_SYMBOLOGY_CHOICES, default="datamatrix_gs1_2d")`
  - `scanned_barcode_data`: `CharField(max_length=255, blank=True, help_text="Decoded text string from barcode scanner")`
  - `iso_iec_print_grade`: `CharField(max_length=20, choices=ISO_IEC_GRADE_CHOICES, default="grade_a_4_0")`
  - `label_content_accurate`: `BooleanField(default=True, help_text="Part number, description, quantity, batch/lot, and manufacturing date match perfectly")`
  - `regulatory_symbols_present`: `BooleanField(default=True, help_text="CE, UL, RoHS, WEEE, FDA, country-of-origin symbols present and legible")`
  - `serialization_verified`: `BooleanField(default=True, help_text="Serial numbers adhere to scheme and contain zero duplicates")`
  - `carton_integrity_intact`: `BooleanField(default=True, help_text="Outer shipping cartons free of tears, moisture, crushing, or structural damage")`
  - `tamper_evident_seal_intact`: `BooleanField(default=True, help_text="Tamper-evident tape, security seals, or shrink wrap intact")`
  - `cushioning_dunnage_adequate`: `BooleanField(default=True, help_text="Internal cushioning and ESD/moisture barrier protection verified")`
  - `pallet_stacking_compliant`: `BooleanField(default=True, help_text="Pallet pattern, strapping, corner boards, and stretch wrap verified")`
  - `inspection_lot`: `ForeignKey("quality.FinalInspectionLot", on_delete=models.SET_NULL, null=True, blank=True, related_name="packaging_verifications")`
  - `shipment`: `ForeignKey("scm.Shipment", on_delete=models.SET_NULL, null=True, blank=True, related_name="packaging_verifications")`
  - `verifier`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="packaging_verifications_performed")`
  - `verified_date`: `DateField(null=True, blank=True)`
  - `discrepancy_details`: `TextField(blank=True)`
  - `notes`: `TextField(blank=True)`
- **Indexes**:
  - `models.Index(fields=["tenant", "status"], name="quality_pkg_tnt_stat_idx")`
  - `models.Index(fields=["tenant", "disposition"], name="quality_pkg_tnt_disp_idx")`
  - `models.Index(fields=["tenant", "iso_iec_print_grade"], name="quality_pkg_tnt_grd_idx")`

---

### 1.4 `QualityReleaseAuthorization` (`QualityReleaseAuthorizations.py`)
- **`NUMBER_PREFIX`**: `"QREL"`
- **`Meta.ordering`**: `["-created_at"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Quality Release Authorization"` / `"Quality Release Authorizations"`
- **Choices & Badge Maps**:
  - `RELEASE_DISPOSITION_CHOICES` (`max_length=30`):
    - `("pending_review", "Pending Quality Review")`
    - `("released_full", "Fully Released for Shipment")`
    - `("conditional_release", "Conditional Release (Concession)")`
    - `("quarantined_hold", "Quarantined on Quality Hold")`
    - `("rejected_shipping_blocked", "Rejected / Shipping Blocked")`
  - `STATUS_CHOICES` (`max_length=20`):
    - `("draft", "Draft")`
    - `("active_hold", "Active Hold")`
    - `("authorized", "Authorized & Signed")`
    - `("cancelled", "Cancelled")`
  - `DISPOSITION_CSS`:
    - `"pending_review": "badge-slate"`
    - `"released_full": "badge-green"`
    - `"conditional_release": "badge-info"`
    - `"quarantined_hold": "badge-red"`
    - `"rejected_shipping_blocked": "badge-red"`
  - `STATUS_CSS`:
    - `"draft": "badge-slate"`
    - `"active_hold": "badge-red"`
    - `"authorized": "badge-green"`
    - `"cancelled": "badge-muted"`
- **Fields**:
  - `title`: `CharField(max_length=255)`
  - `status`: `CharField(max_length=20, choices=STATUS_CHOICES, default="draft", db_index=True)`
  - `release_disposition`: `CharField(max_length=30, choices=RELEASE_DISPOSITION_CHOICES, default="pending_review", db_index=True)`
  - `customer`: `ForeignKey("core.Party", on_delete=models.CASCADE, related_name="quality_releases")`
  - `destination_country`: `CharField(max_length=100, blank=True, help_text="Destination country for export compliance check")`
  - `destination_facility`: `CharField(max_length=255, blank=True)`
  - `shipment_number`: `CharField(max_length=64, blank=True)`
  - `shipment`: `ForeignKey("scm.Shipment", on_delete=models.SET_NULL, null=True, blank=True, related_name="quality_releases")`
  - `sales_order_number`: `CharField(max_length=64, blank=True)`
  - `sales_order`: `ForeignKey("scm.SalesOrder", on_delete=models.SET_NULL, null=True, blank=True, related_name="quality_releases")`
  - `lot_number`: `CharField(max_length=100, blank=True)`
  - `quantity_authorized`: `PositiveIntegerField(default=1)`
  - `inspection_lot`: `ForeignKey("quality.FinalInspectionLot", on_delete=models.SET_NULL, null=True, blank=True, related_name="quality_releases")`
  - `certificate_of_conformance`: `ForeignKey("quality.CertificateOfConformance", on_delete=models.SET_NULL, null=True, blank=True, related_name="quality_releases")`
  - `packaging_verification`: `ForeignKey("quality.PackagingLabelVerification", on_delete=models.SET_NULL, null=True, blank=True, related_name="quality_releases")`
  - `is_on_hold`: `BooleanField(default=False, db_index=True)`
  - `hold_reason`: `TextField(blank=True)`
  - `final_inspection_passed`: `BooleanField(default=True, help_text="Final inspection lot passed or accepted with concession")`
  - `no_open_ncrs_or_capas`: `BooleanField(default=True, help_text="Verified zero open NCRs, deviations, or blocking CAPAs on this batch")`
  - `packaging_label_approved`: `BooleanField(default=True, help_text="Packaging and barcode verification passed")`
  - `coc_issued_and_signed`: `BooleanField(default=True, help_text="Certificate of Conformance issued and signed")`
  - `export_compliance_verified`: `BooleanField(default=True, help_text="Export control, ECCN/ITAR, and restricted party screening cleared")`
  - `certificate_of_origin_attached`: `BooleanField(default=False, help_text="Certificate of origin attached if required by destination customs")`
  - `shipping_container_security_seal`: `CharField(max_length=100, blank=True, help_text="Bolt seal, cable seal, or container tamper tag number")`
  - `carrier_name`: `CharField(max_length=100, blank=True)`
  - `tracking_reference`: `CharField(max_length=100, blank=True)`
  - `releasing_officer`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="shipments_released")`
  - `release_date`: `DateField(null=True, blank=True)`
  - `concession_rationale`: `TextField(blank=True, help_text="Required if conditional release granted")`
  - `notes`: `TextField(blank=True)`
- **Indexes**:
  - `models.Index(fields=["tenant", "status"], name="quality_rel_tnt_stat_idx")`
  - `models.Index(fields=["tenant", "release_disposition"], name="quality_rel_tnt_disp_idx")`
  - `models.Index(fields=["tenant", "is_on_hold"], name="quality_rel_tnt_hold_idx")`

---

## 2. Forms Contract (`apps/quality/forms/FinalQuality/`)

All forms inherit `TenantUniqueMixin`, `TenantModelForm` (`apps.core.forms`). Exclude `tenant`, `number`, `created_at`, `updated_at`, `digital_signature_hash`, `qr_verification_code`.

### 2.1 `FinalInspectionLotForm` (`FinalInspectionLots.py`)
- `Meta.model = FinalInspectionLot`
- `Meta.fields = [`
  `"title", "inspection_stage", "sampling_standard",`
  `"aql_critical", "aql_major", "aql_minor",`
  `"status", "usage_decision", "decision_rationale",`
  `"item_code", "item_name", "lot_number", "batch_number", "serial_number_range",`
  `"lot_quantity", "sample_size_inspected",`
  `"critical_defects_count", "major_defects_count", "minor_defects_count",`
  `"units_passed", "units_rejected",`
  `"visual_inspection_passed", "dimensional_inspection_passed", "functional_test_passed", "packaging_inspection_passed",`
  `"is_on_hold", "hold_reason",`
  `"customer", "sales_order_number", "sales_order", "work_order_number", "work_order",`
  `"inspection_plan", "non_conformance", "process_deviation",`
  `"inspector", "decision_by", "inspection_date", "decision_date", "inspection_notes"`
  `]`
- Widgets:
  - `inspection_date`: `forms.DateInput(attrs={"type": "date", "class": "form-input"})`
  - `decision_date`: `forms.DateInput(attrs={"type": "date", "class": "form-input"})`
  - `decision_rationale`: `forms.Textarea(attrs={"rows": 2, "class": "form-textarea"})`
  - `hold_reason`: `forms.Textarea(attrs={"rows": 2, "class": "form-textarea"})`
  - `inspection_notes`: `forms.Textarea(attrs={"rows": 2, "class": "form-textarea"})`

### 2.2 `CertificateOfConformanceForm` (`CertificatesOfConformance.py`)
- `Meta.model = CertificateOfConformance`
- `Meta.fields = [`
  `"title", "certificate_type", "status", "customer",`
  `"customer_po_number", "sales_order_number", "sales_order",`
  `"shipment_number", "shipment",`
  `"item_code", "item_name", "revision", "lot_number", "batch_number",`
  `"serial_numbers_text", "certified_quantity", "inspection_lot",`
  `"applicable_specifications", "test_results_summary", "conformance_statement",`
  `"authorized_signatory", "signatory_title", "signed_date", "notes"`
  `]`
- Widgets:
  - `signed_date`: `forms.DateInput(attrs={"type": "date", "class": "form-input"})`
  - `applicable_specifications`: `forms.Textarea(attrs={"rows": 2, "class": "form-textarea"})`
  - `test_results_summary`: `forms.Textarea(attrs={"rows": 3, "class": "form-textarea"})`
  - `conformance_statement`: `forms.Textarea(attrs={"rows": 3, "class": "form-textarea"})`
  - `serial_numbers_text`: `forms.Textarea(attrs={"rows": 2, "class": "form-textarea"})`
  - `notes`: `forms.Textarea(attrs={"rows": 2, "class": "form-textarea"})`

### 2.3 `PackagingLabelVerificationForm` (`PackagingLabelVerifications.py`)
- `Meta.model = PackagingLabelVerification`
- `Meta.fields = [`
  `"title", "status", "disposition",`
  `"item_code", "item_name", "lot_number", "carton_count_inspected",`
  `"label_part_number", "label_artwork_revision", "artwork_master",`
  `"barcode_symbology", "scanned_barcode_data", "iso_iec_print_grade",`
  `"label_content_accurate", "regulatory_symbols_present", "serialization_verified",`
  `"carton_integrity_intact", "tamper_evident_seal_intact", "cushioning_dunnage_adequate", "pallet_stacking_compliant",`
  `"inspection_lot", "shipment", "verifier", "verified_date",`
  `"discrepancy_details", "notes"`
  `]`
- Widgets:
  - `verified_date`: `forms.DateInput(attrs={"type": "date", "class": "form-input"})`
  - `discrepancy_details`: `forms.Textarea(attrs={"rows": 2, "class": "form-textarea"})`
  - `notes`: `forms.Textarea(attrs={"rows": 2, "class": "form-textarea"})`

### 2.4 `QualityReleaseAuthorizationForm` (`QualityReleaseAuthorizations.py`)
- `Meta.model = QualityReleaseAuthorization`
- `Meta.fields = [`
  `"title", "status", "release_disposition", "customer",`
  `"destination_country", "destination_facility",`
  `"shipment_number", "shipment", "sales_order_number", "sales_order",`
  `"lot_number", "quantity_authorized",`
  `"inspection_lot", "certificate_of_conformance", "packaging_verification",`
  `"is_on_hold", "hold_reason",`
  `"final_inspection_passed", "no_open_ncrs_or_capas", "packaging_label_approved",`
  `"coc_issued_and_signed", "export_compliance_verified", "certificate_of_origin_attached",`
  `"shipping_container_security_seal", "carrier_name", "tracking_reference",`
  `"releasing_officer", "release_date", "concession_rationale", "notes"`
  `]`
- Widgets:
  - `release_date`: `forms.DateInput(attrs={"type": "date", "class": "form-input"})`
  - `hold_reason`: `forms.Textarea(attrs={"rows": 2, "class": "form-textarea"})`
  - `concession_rationale`: `forms.Textarea(attrs={"rows": 2, "class": "form-textarea"})`
  - `notes`: `forms.Textarea(attrs={"rows": 2, "class": "form-textarea"})`

---

## 3. Views & URLs Contract (`apps/quality/views/FinalQuality/` and `urls/FinalQuality/`)

### 3.1 Pinned Context Keys (L7)

| View | Context Keys Pinned |
|---|---|
| `final_inspection_lot_list` | `inspection_lots`, `page_obj`, `paginator`, `q`, `stage`, `status`, `decision`, `on_hold`, `stage_choices`, `status_choices`, `decision_choices`, `total_count`, `accepted_count`, `hold_count`, `rejected_count` |
| `final_inspection_lot_detail` | `lot`, `STAGE_CSS`, `STATUS_CSS`, `DECISION_CSS` |
| `final_inspection_lot_create` / `_edit` | `form`, `lot` (edit mode only), `is_edit` |
| `certificate_of_conformance_list` | `certificates`, `page_obj`, `paginator`, `q`, `type`, `status`, `customer_id`, `type_choices`, `status_choices`, `customers`, `total_count`, `signed_count`, `review_count` |
| `certificate_of_conformance_detail` | `certificate`, `TYPE_CSS`, `STATUS_CSS` |
| `certificate_of_conformance_create` / `_edit` | `form`, `certificate` (edit mode only), `is_edit` |
| `packaging_label_verification_list` | `verifications`, `page_obj`, `paginator`, `q`, `status`, `disposition`, `grade`, `status_choices`, `disposition_choices`, `grade_choices`, `total_count`, `verified_count`, `failed_count` |
| `packaging_label_verification_detail` | `verification`, `BARCODE_CSS`, `GRADE_CSS`, `STATUS_CSS`, `DISPOSITION_CSS` |
| `packaging_label_verification_create` / `_edit` | `form`, `verification` (edit mode only), `is_edit` |
| `quality_release_authorization_list` | `releases`, `page_obj`, `paginator`, `q`, `status`, `disposition`, `on_hold`, `customer_id`, `status_choices`, `disposition_choices`, `customers`, `total_count`, `authorized_count`, `hold_count` |
| `quality_release_authorization_detail` | `release`, `STATUS_CSS`, `DISPOSITION_CSS` |
| `quality_release_authorization_create` / `_edit` | `form`, `release` (edit mode only), `is_edit` |
| `oqc_hold_board` | `active_holds_lots`, `active_holds_releases`, `pending_inspection_lots`, `pending_cocs`, `ready_releases`, `hold_lot_count`, `hold_release_count`, `pending_lot_count`, `pending_coc_count`, `ready_release_count` |

### 3.2 URL Patterns (`apps/quality/urls/FinalQuality/` and `urls/__init__.py`)

All routes mounted under `quality:`:

1. `FinalInspectionLots.py`:
   - `path("final-inspections/", views.final_inspection_lot_list, name="final_inspection_lot_list")`
   - `path("final-inspections/create/", views.final_inspection_lot_create, name="final_inspection_lot_create")`
   - `path("final-inspections/export/", views.final_inspection_lot_export, name="final_inspection_lot_export")`
   - `path("final-inspections/<int:pk>/", views.final_inspection_lot_detail, name="final_inspection_lot_detail")`
   - `path("final-inspections/<int:pk>/edit/", views.final_inspection_lot_edit, name="final_inspection_lot_edit")`
   - `path("final-inspections/<int:pk>/delete/", views.final_inspection_lot_delete, name="final_inspection_lot_delete")`
   - `path("final-inspections/<int:pk>/toggle-hold/", views.final_inspection_lot_toggle_hold, name="final_inspection_lot_toggle_hold")`

2. `CertificatesOfConformance.py`:
   - `path("certificates-of-conformance/", views.certificate_of_conformance_list, name="certificate_of_conformance_list")`
   - `path("certificates-of-conformance/create/", views.certificate_of_conformance_create, name="certificate_of_conformance_create")`
   - `path("certificates-of-conformance/export/", views.certificate_of_conformance_export, name="certificate_of_conformance_export")`
   - `path("certificates-of-conformance/<int:pk>/", views.certificate_of_conformance_detail, name="certificate_of_conformance_detail")`
   - `path("certificates-of-conformance/<int:pk>/edit/", views.certificate_of_conformance_edit, name="certificate_of_conformance_edit")`
   - `path("certificates-of-conformance/<int:pk>/delete/", views.certificate_of_conformance_delete, name="certificate_of_conformance_delete")`
   - `path("certificates-of-conformance/<int:pk>/sign/", views.certificate_of_conformance_sign, name="certificate_of_conformance_sign")`

3. `PackagingLabelVerifications.py`:
   - `path("packaging-verifications/", views.packaging_label_verification_list, name="packaging_label_verification_list")`
   - `path("packaging-verifications/create/", views.packaging_label_verification_create, name="packaging_label_verification_create")`
   - `path("packaging-verifications/export/", views.packaging_label_verification_export, name="packaging_label_verification_export")`
   - `path("packaging-verifications/<int:pk>/", views.packaging_label_verification_detail, name="packaging_label_verification_detail")`
   - `path("packaging-verifications/<int:pk>/edit/", views.packaging_label_verification_edit, name="packaging_label_verification_edit")`
   - `path("packaging-verifications/<int:pk>/delete/", views.packaging_label_verification_delete, name="packaging_label_verification_delete")`

4. `QualityReleaseAuthorizations.py`:
   - `path("quality-releases/", views.quality_release_authorization_list, name="quality_release_authorization_list")`
   - `path("quality-releases/create/", views.quality_release_authorization_create, name="quality_release_authorization_create")`
   - `path("quality-releases/export/", views.quality_release_authorization_export, name="quality_release_authorization_export")`
   - `path("quality-releases/<int:pk>/", views.quality_release_authorization_detail, name="quality_release_authorization_detail")`
   - `path("quality-releases/<int:pk>/edit/", views.quality_release_authorization_edit, name="quality_release_authorization_edit")`
   - `path("quality-releases/<int:pk>/delete/", views.quality_release_authorization_delete, name="quality_release_authorization_delete")`
   - `path("quality-releases/<int:pk>/toggle-hold/", views.quality_release_authorization_toggle_hold, name="quality_release_authorization_toggle_hold")`

5. `OqcHoldBoard.py`:
   - `path("hold-and-release-board/", views.oqc_hold_board, name="oqc_hold_board")`

---

## 4. Navigation Wire-up Contract (`apps/core/navigation.py`)

Exact mapping for `LIVE_LINKS["12.9"]`:
```python
    "12.9": {
        "Final Inspection Protocols": "quality:final_inspection_lot_list",
        "Lot Sampling & Acceptance Testing": "quality:oqc_hold_board",
        "Certificate of Conformance (CoC)": "quality:certificate_of_conformance_list",
        "Packaging & Labeling Verification": "quality:packaging_label_verification_list",
        "Shipment Release & Traceability": "quality:quality_release_authorization_list",
    },
```
Matches `NavERP.md` lines 1922–1928 bullet text character-for-character.
