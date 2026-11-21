# Module 12.18 Pre-Build Contract — Traceability & Serialization (`apps/quality/`)

> Frozen in Phase 3.1 before any Phase 3.3 entity build. Every model field, `max_length`,
> `CHOICES` tuple, badge class (`static/css/theme.css`), index/constraint name (`<= 30` chars),
> form `Meta.fields` + excluded fields, URL route/name (literal before `<int:pk>`), exact view
> context key, filter param, `AuditLog.action` verb (`<= 10` chars), and `LIVE_LINKS["12.18"]`
> entry below is authoritative across backend, templates, smoke tests, reviews, and unit/security tests.

- **Parent App**: `apps.quality` (Extends existing app; incremental migration `0031_...`; NO changes to `config/settings.py` or `config/urls.py`)
- **Package Directories**:
  - `apps/quality/models/TraceabilitySerialization/`
  - `apps/quality/forms/TraceabilitySerialization/`
  - `apps/quality/views/TraceabilitySerialization/`
  - `apps/quality/urls/TraceabilitySerialization/`
  - `templates/quality/traceabilityserialization/{batch_record,device_identifier,serialized_item,product_recall}/{list,detail,form}.html` + `templates/quality/traceabilityserialization/traceability_dashboard.html`
- **AuditLog `action` Max Length (`<= 10` chars, L66)**:
  - Allowed `action` verbs passed to `write_audit_log(request.user, obj, verb, tenant=request.tenant)`:
    `"create"`, `"update"`, `"delete"`, `"release"`, `"quarantine"`, `"commission"`, `"aggregate"`, `"recall"` (all `<= 10` chars).
- **Theme CSS Classes (`static/css/theme.css`, L33)**:
  - Allowed badge classes ONLY: `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, `badge-slate`.
  - Allowed `.stat-icon` colors ONLY: `blue`, `green`, `orange`, `purple`, `slate`, `red`.
  - Detail views use `<dl class="detail-grid"><div class="detail-item"><dt>...</dt><dd>...</dd></div></dl>`.
- **Pagination & CSV Standard**:
  - `PAGE_SIZE = 15` (`Paginator(qs, PAGE_SIZE)`).
  - Paginator guards `has_previous` / `has_next` (L9).
  - CSV exports stream via `HttpResponse(content_type="text/csv")` using CSV formula neutralization (`csv_safe` or leading quote stripping) + `X-Content-Type-Options: nosniff`.
- **Tenant Scoping & FK Isolation (L29, L39, L11)**:
  - All foreign keys are tenant-scoped: `accounts.User`, `core.OrgUnit`, `core.Party`, `scm.WorkOrder`, `scm.Shipment`, `quality.ControlledDocument`, `quality.ElectronicSignatureRecord`, `quality.NonConformanceReport`, `quality.ProcessDeviation`, `quality.CapaInvestigation`, `quality.FinalInspectionLot`, `quality.CustomerComplaint`.
  - FKs populated in forms using `Model.objects.filter(tenant=self.tenant)` and validated in `clean()` via `reject_foreign(...)`.
  - List view FK query param parsing MUST check `.isdigit()` (L11) before filtering.

---

## 1. Models & Choices Contract (`apps/quality/models/TraceabilitySerialization/`)

All 4 models inherit `apps.quality.models._base.TenantNumbered` (`tenant` FK `core.Tenant`, `number` `CharField(32, editable=False)`, `created_at`, `updated_at`, collision-retrying `save()`).

### 1.1 `BatchRecord` (`BatchRecords.py`)
- **`NUMBER_PREFIX`**: `"QBMR"`
- **`Meta.ordering`**: `["-created_at", "batch_number"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Batch Manufacturing Record"` / `"Batch Manufacturing Records"`
- **Choices & Badge Maps**:
  - `STATUS_CHOICES` (`max_length=25`):
    - `("draft", "Draft / Staged")`
    - `("in_production", "In Production")`
    - `("production_complete", "Production Complete")`
    - `("qa_review", "Under QA Review")`
    - `("released", "Batch Released")`
    - `("rejected", "Batch Rejected")`
    - `("quarantined", "Quarantined Hold")`
  - `RELEASE_STATUS_CHOICES` (`max_length=25`):
    - `("pending", "Pending Disposition")`
    - `("approved_full", "Full Release Approved")`
    - `("approved_concession", "Release with Concession")`
    - `("rejected", "Disposition Rejected")`
    - `("on_hold", "Quality Hold Active")`
  - `STATUS_CSS`:
    - `"draft": "badge-slate"`
    - `"in_production": "badge-info"`
    - `"production_complete": "badge-info"`
    - `"qa_review": "badge-amber"`
    - `"released": "badge-green"`
    - `"rejected": "badge-red"`
    - `"quarantined": "badge-amber"`
  - `RELEASE_STATUS_CSS`:
    - `"pending": "badge-slate"`
    - `"approved_full": "badge-green"`
    - `"approved_concession": "badge-amber"`
    - `"rejected": "badge-red"`
    - `"on_hold": "badge-red"`
- **Fields (exact names & types)**:
  - `title`: `CharField(max_length=255)`
  - `batch_number`: `CharField(max_length=100, db_index=True)`
  - `product_code`: `CharField(max_length=100, db_index=True)`
  - `product_name`: `CharField(max_length=255)`
  - `status`: `CharField(max_length=25, choices=STATUS_CHOICES, default="draft", db_index=True)`
  - `release_status`: `CharField(max_length=25, choices=RELEASE_STATUS_CHOICES, default="pending", db_index=True)`
  - `production_order_number`: `CharField(max_length=64, blank=True)`
  - `work_order`: `ForeignKey("scm.WorkOrder", on_delete=models.SET_NULL, null=True, blank=True, related_name="quality_batch_records")`
  - `master_document`: `ForeignKey("quality.ControlledDocument", on_delete=models.SET_NULL, null=True, blank=True, related_name="quality_batch_records")`
  - `planned_quantity`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))`
  - `actual_quantity`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))`
  - `unit_of_measure`: `CharField(max_length=25, default="EA")`
  - `yield_percentage`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))`
  - `manufacturing_date`: `DateField(null=True, blank=True)`
  - `expiration_date`: `DateField(null=True, blank=True)`
  - `retest_date`: `DateField(null=True, blank=True)`
  - `supervisor`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="supervised_batch_records")`
  - `qa_reviewer`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="reviewed_batch_records")`
  - `qa_decision_at`: `DateTimeField(null=True, blank=True)`
  - `electronic_signature`: `ForeignKey("quality.ElectronicSignatureRecord", on_delete=models.SET_NULL, null=True, blank=True, related_name="batch_record_signatures")`
  - `linked_ncr`: `ForeignKey("quality.NonConformanceReport", on_delete=models.SET_NULL, null=True, blank=True, related_name="batch_records")`
  - `linked_deviation`: `ForeignKey("quality.ProcessDeviation", on_delete=models.SET_NULL, null=True, blank=True, related_name="batch_records")`
  - `linked_fqc`: `ForeignKey("quality.FinalInspectionLot", on_delete=models.SET_NULL, null=True, blank=True, related_name="batch_records")`
  - `component_genealogy`: `JSONField(default=list, blank=True)`
  - `checklist_passed`: `BooleanField(default=False)`
  - `is_quarantined`: `BooleanField(default=False)`
  - `notes`: `TextField(blank=True)`
- **Properties**:
  - `@property can_release`: `checklist_passed and not is_quarantined and (linked_ncr is None or linked_ncr.status == "closed")`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qbmr_ten_num_uniq")` (25)
  - `Index(fields=["tenant", "batch_number"], name="idx_qbmr_ten_batch")` (18)
  - `Index(fields=["tenant", "status"], name="idx_qbmr_ten_status")` (19)
  - `Index(fields=["tenant", "release_status"], name="idx_qbmr_ten_release")` (20)

---

### 1.2 `DeviceIdentifier` (`DeviceIdentifiers.py`)
- **`NUMBER_PREFIX`**: `"QUDI"`
- **`Meta.ordering`**: `["device_name", "primary_di"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Device Identifier (UDI)"` / `"Device Identifiers (UDI)"`
- **Choices & Badge Maps**:
  - `ISSUING_AGENCY_CHOICES` (`max_length=20`):
    - `("gs1", "GS1")`
    - `("hibcc", "HIBCC")`
    - `("iccbba", "ICCBBA")`
    - `("other", "Other Recognized Agency")`
  - `DEVICE_CLASS_CHOICES` (`max_length=20`):
    - `("class_i", "Class I (Low Risk)")`
    - `("class_iia", "Class IIa / Class II (Moderate)")`
    - `("class_iib", "Class IIb (Moderate-High)")`
    - `("class_iii", "Class III (High Risk)")`
    - `("unclassified", "Unclassified / General")`
  - `REGULATORY_STATUS_CHOICES` (`max_length=25`):
    - `("draft", "Draft / In Preparation")`
    - `("ready_to_submit", "Ready for Submission")`
    - `("submitted", "Submitted to Agency")`
    - `("published", "Published / Active")`
    - `("rejected", "Submission Rejected")`
  - `DISTRIBUTION_STATUS_CHOICES` (`max_length=35`):
    - `("in_commercial_distribution", "In Commercial Distribution")`
    - `("off_market", "Off Market / Discontinued")`
    - `("not_yet_distributed", "Not Yet in Commercial Distribution")`
  - `BARCODE_FORMAT_CHOICES` (`max_length=25`):
    - `("gs1_datamatrix", "GS1 DataMatrix (2D)")`
    - `("gs1_128", "GS1-128 (1D Linear)")`
    - `("hibc_2d", "HIBC 2D Barcode")`
    - `("qr_code", "QR Code")`
  - `MRI_STATUS_CHOICES` (`max_length=20`):
    - `("mr_safe", "MR Safe")`
    - `("mr_conditional", "MR Conditional")`
    - `("mr_unsafe", "MR Unsafe")`
    - `("not_evaluated", "Not Evaluated")`
  - `REGULATORY_STATUS_CSS`:
    - `"draft": "badge-slate"`
    - `"ready_to_submit": "badge-info"`
    - `"submitted": "badge-amber"`
    - `"published": "badge-green"`
    - `"rejected": "badge-red"`
  - `DEVICE_CLASS_CSS`:
    - `"class_i": "badge-slate"`
    - `"class_iia": "badge-info"`
    - `"class_iib": "badge-amber"`
    - `"class_iii": "badge-red"`
    - `"unclassified": "badge-muted"`
- **Fields (exact names & types)**:
  - `device_name`: `CharField(max_length=255)`
  - `model_number`: `CharField(max_length=100, blank=True)`
  - `primary_di`: `CharField(max_length=64, db_index=True)`
  - `issuing_agency`: `CharField(max_length=20, choices=ISSUING_AGENCY_CHOICES, default="gs1", db_index=True)`
  - `device_class`: `CharField(max_length=20, choices=DEVICE_CLASS_CHOICES, default="class_iia", db_index=True)`
  - `basic_udi_di`: `CharField(max_length=64, blank=True, db_index=True)`
  - `gudid_status`: `CharField(max_length=25, choices=REGULATORY_STATUS_CHOICES, default="draft", db_index=True)`
  - `eudamed_status`: `CharField(max_length=25, choices=REGULATORY_STATUS_CHOICES, default="draft", db_index=True)`
  - `brand_name`: `CharField(max_length=255, blank=True)`
  - `commercial_distribution_status`: `CharField(max_length=35, choices=DISTRIBUTION_STATUS_CHOICES, default="in_commercial_distribution", db_index=True)`
  - `catalog_number`: `CharField(max_length=100, blank=True)`
  - `barcode_format`: `CharField(max_length=25, choices=BARCODE_FORMAT_CHOICES, default="gs1_datamatrix", db_index=True)`
  - `is_sterile`: `BooleanField(default=False)`
  - `contains_latex`: `BooleanField(default=False)`
  - `is_single_use`: `BooleanField(default=True)`
  - `mri_safety_status`: `CharField(max_length=20, choices=MRI_STATUS_CHOICES, default="mr_safe", db_index=True)`
  - `storage_handling_instructions`: `TextField(blank=True)`
  - `fda_listing_number`: `CharField(max_length=64, blank=True)`
  - `submission_date`: `DateField(null=True, blank=True)`
  - `approval_document`: `ForeignKey("quality.ControlledDocument", on_delete=models.SET_NULL, null=True, blank=True, related_name="device_identifiers")`
  - `regulatory_contact`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="managed_device_identifiers")`
  - `notes`: `TextField(blank=True)`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qudi_ten_num_uniq")` (25)
  - `Index(fields=["tenant", "primary_di"], name="idx_qudi_ten_pdi")` (16)
  - `Index(fields=["tenant", "gudid_status"], name="idx_qudi_ten_gudid")` (18)
  - `Index(fields=["tenant", "eudamed_status"], name="idx_qudi_ten_euda")` (17)

---

### 1.3 `SerializedItem` (`SerializedItems.py`)
- **`NUMBER_PREFIX`**: `"QSER"`
- **`Meta.ordering`**: `["-created_at", "serial_number"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Serialized Item"` / `"Serialized Items"`
- **Choices & Badge Maps**:
  - `PACKAGING_LEVEL_CHOICES` (`max_length=25`):
    - `("unit", "Item / Primary Unit")`
    - `("bundle", "Bundle / Intermediate")`
    - `("carton", "Carton / Shipper Case")`
    - `("case", "Master Case")`
    - `("pallet", "Pallet / Logistical Unit (SSCC)")`
  - `COMMISSIONING_STATUS_CHOICES` (`max_length=25`):
    - `("allocated", "Serial Allocated")`
    - `("commissioned", "Commissioned / Active")`
    - `("aggregated", "Aggregated in Pack")`
    - `("shipped", "Shipped Outbound")`
    - `("decommissioned", "Decommissioned")`
    - `("destroyed", "Destroyed / Sampled")`
    - `("recalled", "Recalled / Quarantined")`
  - `EPCIS_STATE_CHOICES` (`max_length=25`):
    - `("active", "Active In Inventory")`
    - `("in_transit", "In Transit")`
    - `("delivered", "Delivered / Dispensed")`
    - `("quarantined", "Quarantine Hold")`
    - `("suspect", "Suspect Counterfeit / Diverted")`
  - `COMMISSIONING_STATUS_CSS`:
    - `"allocated": "badge-slate"`
    - `"commissioned": "badge-info"`
    - `"aggregated": "badge-purple"`
    - `"shipped": "badge-green"`
    - `"decommissioned": "badge-slate"`
    - `"destroyed": "badge-muted"`
    - `"recalled": "badge-red"`
  - `EPCIS_STATE_CSS`:
    - `"active": "badge-green"`
    - `"in_transit": "badge-info"`
    - `"delivered": "badge-slate"`
    - `"quarantined": "badge-amber"`
    - `"suspect": "badge-red"`
- **Fields (exact names & types)**:
  - `serial_number`: `CharField(max_length=100, db_index=True)`
  - `gtin_or_di`: `CharField(max_length=64, db_index=True)`
  - `item_code`: `CharField(max_length=100, db_index=True)`
  - `item_name`: `CharField(max_length=255)`
  - `lot_number`: `CharField(max_length=100, db_index=True)`
  - `batch_record`: `ForeignKey("quality.BatchRecord", on_delete=models.SET_NULL, null=True, blank=True, related_name="serialized_items")`
  - `device_identifier`: `ForeignKey("quality.DeviceIdentifier", on_delete=models.SET_NULL, null=True, blank=True, related_name="serialized_items")`
  - `packaging_level`: `CharField(max_length=25, choices=PACKAGING_LEVEL_CHOICES, default="unit", db_index=True)`
  - `parent_container`: `ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="child_units")`
  - `sscc_code`: `CharField(max_length=64, blank=True, db_index=True)`
  - `commissioning_status`: `CharField(max_length=25, choices=COMMISSIONING_STATUS_CHOICES, default="allocated", db_index=True)`
  - `epcis_state`: `CharField(max_length=25, choices=EPCIS_STATE_CHOICES, default="active", db_index=True)`
  - `verification_code`: `CharField(max_length=64, blank=True)`
  - `is_cold_chain`: `BooleanField(default=False)`
  - `temperature_limit_min`: `DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)`
  - `temperature_limit_max`: `DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)`
  - `custodian`: `ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="custody_serialized_items")`
  - `location_unit`: `ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True, related_name="serialized_items")`
  - `shipment`: `ForeignKey("scm.Shipment", on_delete=models.SET_NULL, null=True, blank=True, related_name="serialized_items")`
  - `manufacturing_date`: `DateField(null=True, blank=True)`
  - `expiration_date`: `DateField(null=True, blank=True)`
  - `commissioned_at`: `DateTimeField(null=True, blank=True)`
  - `notes`: `TextField(blank=True)`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qser_ten_num_uniq")` (25)
  - `Index(fields=["tenant", "serial_number"], name="idx_qser_ten_serial")` (19)
  - `Index(fields=["tenant", "commissioning_status"], name="idx_qser_ten_comm")` (17)
  - `Index(fields=["tenant", "packaging_level"], name="idx_qser_ten_pkg")` (16)

---

### 1.4 `ProductRecall` (`ProductRecalls.py`)
- **`NUMBER_PREFIX`**: `"QRCL"`
- **`Meta.ordering`**: `["-created_at", "title"]`
- **`Meta.verbose_name` / `verbose_name_plural`**: `"Product Recall"` / `"Product Recalls"`
- **Choices & Badge Maps**:
  - `RECALL_CLASS_CHOICES` (`max_length=25`):
    - `("class_i", "Class I — Serious Threat / Death Risk")`
    - `("class_ii", "Class II — Temporary / Reversible Risk")`
    - `("class_iii", "Class III — Violation without Adverse Effect")`
    - `("market_withdrawal", "Market Withdrawal (Minor)")`
    - `("safety_alert", "Safety Alert / Field Notice")`
  - `RECALL_STATUS_CHOICES` (`max_length=25`):
    - `("initiated", "Recall Initiated")`
    - `("containment_hold", "Containment Hold Active")`
    - `("notification_sent", "Consignee Notifications Sent")`
    - `("recovery_in_progress", "Product Recovery In Progress")`
    - `("effectiveness_check", "Effectiveness Check Review")`
    - `("completed", "Recall Execution Completed")`
    - `("terminated", "Formally Terminated / Closed")`
  - `RECALL_CLASS_CSS`:
    - `"class_i": "badge-red"`
    - `"class_ii": "badge-amber"`
    - `"class_iii": "badge-info"`
    - `"market_withdrawal": "badge-slate"`
    - `"safety_alert": "badge-purple"`
  - `RECALL_STATUS_CSS`:
    - `"initiated": "badge-amber"`
    - `"containment_hold": "badge-red"`
    - `"notification_sent": "badge-info"`
    - `"recovery_in_progress": "badge-amber"`
    - `"effectiveness_check": "badge-info"`
    - `"completed": "badge-green"`
    - `"terminated": "badge-slate"`
- **Fields (exact names & types)**:
  - `title`: `CharField(max_length=255)`
  - `recall_class`: `CharField(max_length=25, choices=RECALL_CLASS_CHOICES, default="class_ii", db_index=True)`
  - `status`: `CharField(max_length=25, choices=RECALL_STATUS_CHOICES, default="initiated", db_index=True)`
  - `is_mock_recall`: `BooleanField(default=False)`
  - `mock_drill_hours`: `DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)`
  - `item_code`: `CharField(max_length=100, db_index=True)`
  - `item_name`: `CharField(max_length=255)`
  - `affected_lot_numbers`: `TextField()`
  - `affected_serial_range`: `CharField(max_length=255, blank=True)`
  - `hazard_summary`: `TextField()`
  - `root_cause`: `TextField(blank=True)`
  - `customer_complaint`: `ForeignKey("quality.CustomerComplaint", on_delete=models.SET_NULL, null=True, blank=True, related_name="product_recalls")`
  - `capa_investigation`: `ForeignKey("quality.CapaInvestigation", on_delete=models.SET_NULL, null=True, blank=True, related_name="product_recalls")`
  - `total_distributed_qty`: `PositiveIntegerField(default=0)`
  - `total_quarantined_qty`: `PositiveIntegerField(default=0)`
  - `total_recovered_qty`: `PositiveIntegerField(default=0)`
  - `total_destroyed_qty`: `PositiveIntegerField(default=0)`
  - `recovery_rate_pct`: `DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))`
  - `regulatory_agency_notified`: `CharField(max_length=100, blank=True)`
  - `regulatory_notification_date`: `DateField(null=True, blank=True)`
  - `coordinator`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="coordinated_recalls")`
  - `closure_approved_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="closed_recalls")`
  - `closed_at`: `DateTimeField(null=True, blank=True)`
  - `notes`: `TextField(blank=True)`
- **Constraints & Indexes (`<= 30` chars)**:
  - `UniqueConstraint(fields=["tenant", "number"], name="quality_qrcl_ten_num_uniq")` (25)
  - `Index(fields=["tenant", "recall_class"], name="idx_qrcl_ten_class")` (18)
  - `Index(fields=["tenant", "status"], name="idx_qrcl_ten_status")` (19)
  - `Index(fields=["tenant", "is_mock_recall"], name="idx_qrcl_ten_mock")` (17)

---

## 2. Forms Contract (`apps/quality/forms/TraceabilitySerialization/`)

All ModelForms inherit `django.forms.ModelForm`. Form `__init__` sets `self.tenant` and populates all tenant FK querysets (`Model.objects.filter(tenant=self.tenant)`). Clean methods reject foreign tenant objects via `reject_foreign(...)`.

### 2.1 `BatchRecordForm` (`BatchRecords.py`)
- **`Meta.model`**: `BatchRecord`
- **`Meta.fields`**: All model fields except exclusions.
- **`Meta.exclude`**: `["tenant", "number", "yield_percentage", "qa_decision_at", "created_at", "updated_at"]`

### 2.2 `DeviceIdentifierForm` (`DeviceIdentifiers.py`)
- **`Meta.model`**: `DeviceIdentifier`
- **`Meta.fields`**: All model fields except exclusions.
- **`Meta.exclude`**: `["tenant", "number", "created_at", "updated_at"]`

### 2.3 `SerializedItemForm` (`SerializedItems.py`)
- **`Meta.model`**: `SerializedItem`
- **`Meta.fields`**: All model fields except exclusions.
- **`Meta.exclude`**: `["tenant", "number", "commissioned_at", "created_at", "updated_at"]`

### 2.4 `ProductRecallForm` (`ProductRecalls.py`)
- **`Meta.model`**: `ProductRecall`
- **`Meta.fields`**: All model fields except exclusions.
- **`Meta.exclude`**: `["tenant", "number", "recovery_rate_pct", "closed_at", "created_at", "updated_at"]`

---

## 3. URLs Contract (`apps/quality/urls/TraceabilitySerialization/` & `apps/quality/urls/__init__.py`)

All URL patterns live in `apps/quality/urls/TraceabilitySerialization/<Entity>.py`. Literal patterns are strictly registered before `<int:pk>` patterns.

| Pattern | View Name | Route Name | Notes |
|---------|-----------|------------|-------|
| `traceability/` | `traceability_dashboard` | `traceability_dashboard` | Command center & genealogy lookup |
| `traceability/export/` | `traceability_export_csv` | `traceability_export_csv` | CSV telemetry export |
| `traceability/batch-records/` | `batch_record_list` | `batch_record_list` | List + Search + Filter |
| `traceability/batch-records/create/` | `batch_record_create` | `batch_record_create` | Create |
| `traceability/batch-records/<int:pk>/` | `batch_record_detail` | `batch_record_detail` | Detail |
| `traceability/batch-records/<int:pk>/edit/` | `batch_record_edit` | `batch_record_edit` | Edit |
| `traceability/batch-records/<int:pk>/delete/` | `batch_record_delete` | `batch_record_delete` | POST delete |
| `traceability/batch-records/<int:pk>/release/` | `batch_record_release` | `batch_record_release` | POST QA batch release |
| `traceability/udi/` | `device_identifier_list` | `device_identifier_list` | List + Search + Filter |
| `traceability/udi/create/` | `device_identifier_create` | `device_identifier_create` | Create |
| `traceability/udi/<int:pk>/` | `device_identifier_detail` | `device_identifier_detail` | Detail |
| `traceability/udi/<int:pk>/edit/` | `device_identifier_edit` | `device_identifier_edit` | Edit |
| `traceability/udi/<int:pk>/delete/` | `device_identifier_delete` | `device_identifier_delete` | POST delete |
| `traceability/serialized-items/` | `serialized_item_list` | `serialized_item_list` | List + Search + Filter |
| `traceability/serialized-items/create/` | `serialized_item_create` | `serialized_item_create` | Create |
| `traceability/serialized-items/<int:pk>/` | `serialized_item_detail` | `serialized_item_detail` | Detail |
| `traceability/serialized-items/<int:pk>/edit/` | `serialized_item_edit` | `serialized_item_edit` | Edit |
| `traceability/serialized-items/<int:pk>/delete/` | `serialized_item_delete` | `serialized_item_delete` | POST delete |
| `traceability/recalls/` | `product_recall_list` | `product_recall_list` | List + Search + Filter |
| `traceability/recalls/create/` | `product_recall_create` | `product_recall_create` | Create |
| `traceability/recalls/<int:pk>/` | `product_recall_detail` | `product_recall_detail` | Detail |
| `traceability/recalls/<int:pk>/edit/` | `product_recall_edit` | `product_recall_edit` | Edit |
| `traceability/recalls/<int:pk>/delete/` | `product_recall_delete` | `product_recall_delete` | POST delete |

---

## 4. Views & Context Contract (`apps/quality/views/TraceabilitySerialization/`)

Every view context key is pinned below. Missing context keys or typos cause blank renders or `NoReverseMatch`.

### 4.1 `batch_record_list`
- **Context**:
  - `page_obj`: paginated `BatchRecord` queryset
  - `batch_records`: `page_obj.object_list`
  - `status_choices`: `BatchRecord.STATUS_CHOICES`
  - `release_status_choices`: `BatchRecord.RELEASE_STATUS_CHOICES`
  - `selected_status`: `request.GET.get('status', '')`
  - `selected_release_status`: `request.GET.get('release_status', '')`
  - `query`: `request.GET.get('q', '')`

### 4.2 `batch_record_detail`
- **Context**:
  - `batch_record`: `BatchRecord` instance
  - `serialized_items`: `batch_record.serialized_items.all()[:20]`
  - `can_release`: `batch_record.can_release`

### 4.3 `batch_record_form` (shared create/edit)
- **Context**:
  - `form`: `BatchRecordForm`
  - `batch_record`: instance or `None`
  - `is_edit`: boolean

### 4.4 `device_identifier_list`
- **Context**:
  - `page_obj`: paginated `DeviceIdentifier` queryset
  - `device_identifiers`: `page_obj.object_list`
  - `issuing_agency_choices`: `DeviceIdentifier.ISSUING_AGENCY_CHOICES`
  - `device_class_choices`: `DeviceIdentifier.DEVICE_CLASS_CHOICES`
  - `gudid_status_choices`: `DeviceIdentifier.REGULATORY_STATUS_CHOICES`
  - `eudamed_status_choices`: `DeviceIdentifier.REGULATORY_STATUS_CHOICES`
  - `selected_device_class`: `request.GET.get('device_class', '')`
  - `selected_gudid_status`: `request.GET.get('gudid_status', '')`
  - `query`: `request.GET.get('q', '')`

### 4.5 `device_identifier_detail`
- **Context**:
  - `device_identifier`: `DeviceIdentifier` instance
  - `serialized_items`: `device_identifier.serialized_items.all()[:20]`

### 4.6 `device_identifier_form` (shared create/edit)
- **Context**:
  - `form`: `DeviceIdentifierForm`
  - `device_identifier`: instance or `None`
  - `is_edit`: boolean

### 4.7 `serialized_item_list`
- **Context**:
  - `page_obj`: paginated `SerializedItem` queryset
  - `serialized_items`: `page_obj.object_list`
  - `packaging_level_choices`: `SerializedItem.PACKAGING_LEVEL_CHOICES`
  - `commissioning_status_choices`: `SerializedItem.COMMISSIONING_STATUS_CHOICES`
  - `epcis_state_choices`: `SerializedItem.EPCIS_STATE_CHOICES`
  - `selected_level`: `request.GET.get('packaging_level', '')`
  - `selected_status`: `request.GET.get('commissioning_status', '')`
  - `selected_state`: `request.GET.get('epcis_state', '')`
  - `query`: `request.GET.get('q', '')`

### 4.8 `serialized_item_detail`
- **Context**:
  - `serialized_item`: `SerializedItem` instance
  - `child_units`: `serialized_item.child_units.all()`

### 4.9 `serialized_item_form` (shared create/edit)
- **Context**:
  - `form`: `SerializedItemForm`
  - `serialized_item`: instance or `None`
  - `is_edit`: boolean

### 4.10 `product_recall_list`
- **Context**:
  - `page_obj`: paginated `ProductRecall` queryset
  - `product_recalls`: `page_obj.object_list`
  - `recall_class_choices`: `ProductRecall.RECALL_CLASS_CHOICES`
  - `status_choices`: `ProductRecall.RECALL_STATUS_CHOICES`
  - `selected_class`: `request.GET.get('recall_class', '')`
  - `selected_status`: `request.GET.get('status', '')`
  - `selected_mock`: `request.GET.get('is_mock_recall', '')`
  - `query`: `request.GET.get('q', '')`

### 4.11 `product_recall_detail`
- **Context**:
  - `product_recall`: `ProductRecall` instance

### 4.12 `product_recall_form` (shared create/edit)
- **Context**:
  - `form`: `ProductRecallForm`
  - `product_recall`: instance or `None`
  - `is_edit`: boolean

### 4.13 `traceability_dashboard`
- **Context**:
  - `total_batches`: count
  - `released_batches`: count
  - `quarantined_batches`: count
  - `total_serialized`: count
  - `commissioned_units`: count
  - `active_recalls`: count
  - `recent_batch_records`: queryset (5 latest)
  - `recent_serialized_items`: queryset (5 latest)
  - `recent_recalls`: queryset (5 latest)
  - `udi_devices`: queryset (5 latest)

---

## 5. Navigation & Sidebar Contract (`apps/core/navigation.py`)

Exact `LIVE_LINKS["12.18"]` mapping to be added in `apps/core/navigation.py`:

```python
    "12.18": {
        "Batch & Lot Record Management": "quality:batch_record_list",
        "Unique Device Identification (UDI)": "quality:device_identifier_list",
        "Serialization & Aggregation": "quality:serialized_item_list",
        "Track & Trace / Supply Chain Integrity": "quality:traceability_dashboard",
        "Recall & Withdrawal Execution": "quality:product_recall_list",
    },
```
