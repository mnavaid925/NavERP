# Contract — Sub-module 11.1: Asset Procurement & Acquisition (Module 11: Asset Management System, `assets`)

- **Sub-module:** 11.1 Asset Procurement & Acquisition • **Module:** 11 Asset Management System • **App:** `apps/assets`
- **Date:** 2026-11-08 • **Status:** FROZEN PRE-BUILD CONTRACT • **Phase:** 3.1 Spec
- **App Status:** Brand-new app `apps/assets/`. Initial migration: `0001_initial.py`.
- **Package Layout:** `AssetProcurement/` across `models/`, `forms/`, `views/`, `urls/`, and templates `templates/assets/asset_procurement/`.

---

## 1. Models & CHOICES Contract

All 4 models inherit from `apps.assets.models._base.TenantNumbered` (`tenant`, `number`, `created_at`, `updated_at`).

### 1.1 `AssetRequisition` (`apps/assets/models/AssetProcurement/AssetRequisitions.py`)
- **Table:** `assets_requisition`
- **Number Prefix:** `AREQ` (format: `AREQ-00001`)
- **CHOICES:**
  - `PRIORITY_CHOICES = [('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('urgent', 'Urgent')]`
  - `STATUS_CHOICES = [('draft', 'Draft'), ('pending_approval', 'Pending Approval'), ('approved', 'Approved'), ('rejected', 'Rejected'), ('ordered', 'PO Issued / Ordered'), ('received', 'Received'), ('cancelled', 'Cancelled')]`
  - `CATEGORY_CHOICES = [('machinery', 'Plant & Heavy Machinery'), ('vehicle', 'Fleet & Commercial Vehicle'), ('it_hardware', 'IT & Computer Equipment'), ('tooling', 'Tooling & Test Equipment'), ('facility', 'Building & Facility Equipment'), ('office_furniture', 'Furniture & Fixtures'), ('other', 'Other Capital Asset')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='asset_requisitions')`
  - `number`: `CharField(max_length=32, editable=False)`
  - `title`: `CharField(max_length=200)`
  - `description`: `TextField(blank=True)`
  - `business_justification`: `TextField(help_text='CapEx justification, expected ROI, or replacement driver')`
  - `asset_category`: `CharField(max_length=40, choices=CATEGORY_CHOICES, default='machinery')`
  - `priority`: `CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')`
  - `estimated_cost`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal('0.00'))`
  - `currency`: `ForeignKey('accounting.Currency', on_delete=SET_NULL, null=True, blank=True, related_name='asset_requisitions')`
  - `budget_code`: `CharField(max_length=64, blank=True, help_text='Capital budget line item or project code')`
  - `proposed_vendor`: `ForeignKey('core.Party', on_delete=SET_NULL, null=True, blank=True, related_name='proposed_asset_requisitions')`
  - `proposed_manufacturer`: `CharField(max_length=120, blank=True)`
  - `proposed_model`: `CharField(max_length=100, blank=True)`
  - `required_delivery_date`: `DateField(null=True, blank=True)`
  - `target_org_unit`: `ForeignKey('core.OrgUnit', on_delete=SET_NULL, null=True, blank=True, related_name='targeted_asset_requisitions')`
  - `target_location`: `ForeignKey('scm.Location', on_delete=SET_NULL, null=True, blank=True, related_name='targeted_asset_requisitions')`
  - `status`: `CharField(max_length=30, choices=STATUS_CHOICES, default='draft')`
  - `submitted_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='submitted_asset_requisitions')`
  - `submitted_at`: `DateTimeField(null=True, blank=True)`
  - `approved_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='approved_asset_requisitions')`
  - `approved_at`: `DateTimeField(null=True, blank=True)`
  - `rejection_reason`: `TextField(blank=True)`
  - `purchase_order`: `ForeignKey('scm.PurchaseOrder', on_delete=SET_NULL, null=True, blank=True, related_name='asset_requisitions')`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='assets_areq_ten_num_uniq')`
  - `Index(fields=['tenant', 'status'], name='idx_areq_ten_stat')`
  - `Index(fields=['tenant', 'priority'], name='idx_areq_ten_prio')`
  - `Index(fields=['tenant', 'asset_category'], name='idx_areq_ten_cat')`
  - `Index(fields=['tenant', 'created_at'], name='idx_areq_ten_created')`

---

### 1.2 `AssetAcquisitionReceipt` (`apps/assets/models/AssetProcurement/AssetAcquisitionReceipts.py`)
- **Table:** `assets_acquisition_receipt`
- **Number Prefix:** `ARCV` (format: `ARCV-00001`)
- **CHOICES:**
  - `CONDITION_CHOICES = [('excellent', 'Excellent (New / Undamaged)'), ('good', 'Good (Minor cosmetic blemishes)'), ('fair', 'Fair (Operational with wear)'), ('damaged', 'Damaged in Transit'), ('defective', 'Defective / Rejected')]`
  - `STATUS_CHOICES = [('pending_inspection', 'Pending Inspection'), ('accepted', 'Inspected & Accepted'), ('quarantined', 'Quarantined / On Hold'), ('rejected', 'Rejected & RMA Issued'), ('capitalized', 'Fully Capitalized')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='asset_acquisition_receipts')`
  - `number`: `CharField(max_length=32, editable=False)`
  - `title`: `CharField(max_length=200)`
  - `requisition`: `ForeignKey('assets.AssetRequisition', on_delete=SET_NULL, null=True, blank=True, related_name='acquisition_receipts')`
  - `purchase_order`: `ForeignKey('scm.PurchaseOrder', on_delete=SET_NULL, null=True, blank=True, related_name='asset_receipts')`
  - `vendor`: `ForeignKey('core.Party', on_delete=SET_NULL, null=True, blank=True, related_name='supplied_asset_receipts')`
  - `manufacturer`: `CharField(max_length=120, blank=True)`
  - `model_number`: `CharField(max_length=100, blank=True)`
  - `serial_number`: `CharField(max_length=100, blank=True, help_text='Manufacturer serial, chassis, or VIN')`
  - `quantity_received`: `PositiveIntegerField(default=1)`
  - `received_date`: `DateField(default=timezone.now)`
  - `carrier_name`: `CharField(max_length=100, blank=True)`
  - `tracking_number`: `CharField(max_length=100, blank=True)`
  - `bill_of_lading`: `CharField(max_length=100, blank=True)`
  - `receiving_location`: `ForeignKey('scm.Location', on_delete=SET_NULL, null=True, blank=True, related_name='asset_receipts')`
  - `condition_on_arrival`: `CharField(max_length=20, choices=CONDITION_CHOICES, default='good')`
  - `inspection_notes`: `TextField(blank=True)`
  - `inspected_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='inspected_asset_receipts')`
  - `inspected_at`: `DateTimeField(null=True, blank=True)`
  - `status`: `CharField(max_length=30, choices=STATUS_CHOICES, default='pending_inspection')`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='assets_arcv_ten_num_uniq')`
  - `Index(fields=['tenant', 'status'], name='idx_arcv_ten_stat')`
  - `Index(fields=['tenant', 'condition_on_arrival'], name='idx_arcv_ten_cond')`
  - `Index(fields=['tenant', 'serial_number'], name='idx_arcv_ten_ser')`
  - `Index(fields=['tenant', 'created_at'], name='idx_arcv_ten_created')`

---

### 1.3 `AssetCapitalization` (`apps/assets/models/AssetProcurement/AssetCapitalizations.py`)
- **Table:** `assets_capitalization`
- **Number Prefix:** `ACAP` (format: `ACAP-00001`)
- **CHOICES:**
  - `DEPRECIATION_METHOD_CHOICES = [('straight_line', 'Straight Line'), ('declining_balance', 'Declining Balance (200%)'), ('units_of_production', 'Units of Production')]`
  - `STATUS_CHOICES = [('draft', 'Draft Evaluation'), ('approved', 'Approved for Capitalization'), ('capitalized', 'Capitalized into Fixed Assets'), ('reversed', 'Reversed')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='asset_capitalizations')`
  - `number`: `CharField(max_length=32, editable=False)`
  - `title`: `CharField(max_length=200)`
  - `asset_name`: `CharField(max_length=255, help_text='Designation for the capitalized asset register')`
  - `acquisition_receipt`: `ForeignKey('assets.AssetAcquisitionReceipt', on_delete=SET_NULL, null=True, blank=True, related_name='capitalization_events')`
  - `requisition`: `ForeignKey('assets.AssetRequisition', on_delete=SET_NULL, null=True, blank=True, related_name='capitalization_events')`
  - `purchase_cost`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal('0.00'))`
  - `freight_cost`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal('0.00'))`
  - `installation_cost`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal('0.00'))`
  - `customs_duties_cost`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal('0.00'))`
  - `other_initial_costs`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal('0.00'))`
  - `total_cost_basis`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal('0.00'))`
  - `is_cip_conversion`: `BooleanField(default=False, help_text='Whether this capitalizes a Construction-in-Progress asset')`
  - `cip_gl_account`: `ForeignKey('accounting.GLAccount', on_delete=SET_NULL, null=True, blank=True, related_name='asset_cip_clearances')`
  - `asset_gl_account`: `ForeignKey('accounting.GLAccount', on_delete=SET_NULL, null=True, blank=True, related_name='asset_capitalizations')`
  - `depreciation_method`: `CharField(max_length=30, choices=DEPRECIATION_METHOD_CHOICES, default='straight_line')`
  - `useful_life_months`: `PositiveIntegerField(default=60)`
  - `salvage_value`: `DecimalField(max_digits=16, decimal_places=2, default=Decimal('0.00'))`
  - `in_service_date`: `DateField(default=timezone.now)`
  - `fixed_asset`: `ForeignKey('accounting.FixedAsset', on_delete=SET_NULL, null=True, blank=True, related_name='capitalization_records')`
  - `operational_asset`: `ForeignKey('scm.Asset', on_delete=SET_NULL, null=True, blank=True, related_name='capitalization_records')`
  - `status`: `CharField(max_length=30, choices=STATUS_CHOICES, default='draft')`
  - `capitalized_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='capitalized_assets')`
  - `capitalized_at`: `DateTimeField(null=True, blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='assets_acap_ten_num_uniq')`
  - `Index(fields=['tenant', 'status'], name='idx_acap_ten_stat')`
  - `Index(fields=['tenant', 'depreciation_method'], name='idx_acap_ten_meth')`
  - `Index(fields=['tenant', 'in_service_date'], name='idx_acap_ten_insvc')`
  - `Index(fields=['tenant', 'created_at'], name='idx_acap_ten_created')`

---

### 1.4 `AssetTag` (`apps/assets/models/AssetProcurement/AssetTags.py`)
- **Table:** `assets_tag`
- **Number Prefix:** `ATAG` (format: `ATAG-00001`)
- **CHOICES:**
  - `TAG_FORMAT_CHOICES = [('qr_code', 'QR Code (2D Data Matrix)'), ('barcode_128', 'Code 128 Linear Barcode'), ('rfid_uhf', 'UHF Gen2 RFID EPC Tag'), ('nfc', 'NFC HF Tag (13.56 MHz)'), ('metal_plate', 'Anodized Aluminum Asset Nameplate')]`
  - `STATUS_CHOICES = [('pending_print', 'Pending Print'), ('printed', 'Printed / Awaiting Affixation'), ('affixed', 'Affixed to Physical Asset'), ('verified', 'Scanner Verified'), ('damaged_reissued', 'Damaged / Reissued'), ('retired', 'Decommissioned / Retired')]`
- **Fields:**
  - `tenant`: `ForeignKey('core.Tenant', on_delete=CASCADE, related_name='asset_tags')`
  - `number`: `CharField(max_length=32, editable=False)`
  - `tag_code`: `CharField(max_length=64, help_text='Machine-readable barcode/QR/RFID value, unique in workspace')`
  - `tag_format`: `CharField(max_length=30, choices=TAG_FORMAT_CHOICES, default='qr_code')`
  - `operational_asset`: `ForeignKey('scm.Asset', on_delete=SET_NULL, null=True, blank=True, related_name='asset_tags')`
  - `capitalization`: `ForeignKey('assets.AssetCapitalization', on_delete=SET_NULL, null=True, blank=True, related_name='asset_tags')`
  - `physical_placement`: `CharField(max_length=255, blank=True, help_text='e.g., Front chassis next to power supply')`
  - `affixed_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='affixed_asset_tags')`
  - `affixed_at`: `DateTimeField(null=True, blank=True)`
  - `is_verified`: `BooleanField(default=False)`
  - `verified_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True, related_name='verified_asset_tags')`
  - `verified_at`: `DateTimeField(null=True, blank=True)`
  - `scanner_device_id`: `CharField(max_length=64, blank=True, help_text='Handheld terminal or scanner ID')`
  - `status`: `CharField(max_length=30, choices=STATUS_CHOICES, default='pending_print')`
  - `notes`: `TextField(blank=True)`
  - `created_at`: `DateTimeField(auto_now_add=True)`
  - `updated_at`: `DateTimeField(auto_now=True)`
- **Constraints & Indexes:**
  - `UniqueConstraint(fields=['tenant', 'number'], name='assets_atag_ten_num_uniq')`
  - `UniqueConstraint(fields=['tenant', 'tag_code'], name='assets_atag_ten_code_uniq')`
  - `Index(fields=['tenant', 'status'], name='idx_atag_ten_stat')`
  - `Index(fields=['tenant', 'tag_format'], name='idx_atag_ten_fmt')`
  - `Index(fields=['tenant', 'created_at'], name='idx_atag_ten_created')`

---

## 2. Forms Contract

All forms inherit from `forms.ModelForm` and exclude `tenant`, `number`, and auto-timestamps. They apply Tailwind design system CSS (`form-input`, `form-select`, `form-textarea`) via widget attrs.

### 2.1 `AssetRequisitionForm` (`apps/assets/forms/AssetProcurement/AssetRequisitions.py`)
- **Excludes:** `tenant`, `number`, `created_at`, `updated_at`, `submitted_by`, `submitted_at`, `approved_by`, `approved_at`
- **Tenant scoping in `__init__`:**
  - `currency.queryset = Currency.objects.filter(tenant=tenant, is_active=True)`
  - `proposed_vendor.queryset = Party.objects.filter(tenant=tenant, roles__role_type__in=['vendor', 'supplier']).distinct()`
  - `target_org_unit.queryset = OrgUnit.objects.filter(tenant=tenant, is_active=True)`
  - `target_location.queryset = Location.objects.filter(tenant=tenant, is_active=True)`
  - `purchase_order.queryset = PurchaseOrder.objects.filter(tenant=tenant)`

### 2.2 `AssetAcquisitionReceiptForm` (`apps/assets/forms/AssetProcurement/AssetAcquisitionReceipts.py`)
- **Excludes:** `tenant`, `number`, `created_at`, `updated_at`, `inspected_by`, `inspected_at`
- **Tenant scoping in `__init__`:**
  - `requisition.queryset = AssetRequisition.objects.filter(tenant=tenant)`
  - `purchase_order.queryset = PurchaseOrder.objects.filter(tenant=tenant)`
  - `vendor.queryset = Party.objects.filter(tenant=tenant, roles__role_type__in=['vendor', 'supplier']).distinct()`
  - `receiving_location.queryset = Location.objects.filter(tenant=tenant, is_active=True)`

### 2.3 `AssetCapitalizationForm` (`apps/assets/forms/AssetProcurement/AssetCapitalizations.py`)
- **Excludes:** `tenant`, `number`, `created_at`, `updated_at`, `total_cost_basis`, `capitalized_by`, `capitalized_at`
- **Tenant scoping in `__init__`:**
  - `acquisition_receipt.queryset = AssetAcquisitionReceipt.objects.filter(tenant=tenant)`
  - `requisition.queryset = AssetRequisition.objects.filter(tenant=tenant)`
  - `cip_gl_account.queryset = GLAccount.objects.filter(tenant=tenant, is_active=True)`
  - `asset_gl_account.queryset = GLAccount.objects.filter(tenant=tenant, is_active=True)`
  - `fixed_asset.queryset = FixedAsset.objects.filter(tenant=tenant)`
  - `operational_asset.queryset = Asset.objects.filter(tenant=tenant)`

### 2.4 `AssetTagForm` (`apps/assets/forms/AssetProcurement/AssetTags.py`)
- **Excludes:** `tenant`, `number`, `created_at`, `updated_at`, `affixed_by`, `affixed_at`, `verified_by`, `verified_at`
- **Tenant scoping in `__init__`:**
  - `operational_asset.queryset = Asset.objects.filter(tenant=tenant)`
  - `capitalization.queryset = AssetCapitalization.objects.filter(tenant=tenant)`

---

## 3. URLs & Views Contract

App Name: `assets` (`apps_name = "assets"`).

| URL Pattern | View Function | Name | Context Keys |
|---|---|---|---|
| `/` | `overview` | `overview` | `kpis`, `recent_requisitions`, `recent_receipts`, `recent_capitalizations`, `recent_tags` |
| `requisitions/` | `asset_requisition_list` | `asset_requisition_list` | `requisitions`, `page_obj`, `status_choices`, `priority_choices`, `category_choices` |
| `requisitions/create/` | `asset_requisition_create` | `asset_requisition_create` | `form` |
| `requisitions/<int:pk>/` | `asset_requisition_detail` | `asset_requisition_detail` | `requisition` |
| `requisitions/<int:pk>/edit/` | `asset_requisition_edit` | `asset_requisition_edit` | `form`, `requisition` |
| `requisitions/<int:pk>/delete/` | `asset_requisition_delete` | `asset_requisition_delete` | `requisition` |
| `requisitions/<int:pk>/submit/` | `asset_requisition_submit` | `asset_requisition_submit` | POST-only action |
| `requisitions/<int:pk>/approve/` | `asset_requisition_approve` | `asset_requisition_approve` | POST-only action |
| `requisitions/<int:pk>/reject/` | `asset_requisition_reject` | `asset_requisition_reject` | POST-only action |
| `receipts/` | `asset_acquisition_receipt_list` | `asset_acquisition_receipt_list` | `receipts`, `page_obj`, `status_choices`, `condition_choices`, `locations` |
| `receipts/create/` | `asset_acquisition_receipt_create` | `asset_acquisition_receipt_create` | `form` |
| `receipts/<int:pk>/` | `asset_acquisition_receipt_detail` | `asset_acquisition_receipt_detail` | `receipt` |
| `receipts/<int:pk>/edit/` | `asset_acquisition_receipt_edit` | `asset_acquisition_receipt_edit` | `form`, `receipt` |
| `receipts/<int:pk>/delete/` | `asset_acquisition_receipt_delete` | `asset_acquisition_receipt_delete` | `receipt` |
| `receipts/<int:pk>/inspect/` | `asset_acquisition_receipt_inspect` | `asset_acquisition_receipt_inspect` | POST-only action |
| `receipts/<int:pk>/quarantine/` | `asset_acquisition_receipt_quarantine` | `asset_acquisition_receipt_quarantine` | POST-only action |
| `capitalizations/` | `asset_capitalization_list` | `asset_capitalization_list` | `capitalizations`, `page_obj`, `status_choices`, `method_choices` |
| `capitalizations/create/` | `asset_capitalization_create` | `asset_capitalization_create` | `form` |
| `capitalizations/<int:pk>/` | `asset_capitalization_detail` | `asset_capitalization_detail` | `capitalization` |
| `capitalizations/<int:pk>/edit/` | `asset_capitalization_edit` | `asset_capitalization_edit` | `form`, `capitalization` |
| `capitalizations/<int:pk>/delete/` | `asset_capitalization_delete` | `asset_capitalization_delete` | `capitalization` |
| `capitalizations/<int:pk>/execute/` | `asset_capitalization_execute` | `asset_capitalization_execute` | POST-only action |
| `capitalizations/<int:pk>/reverse/` | `asset_capitalization_reverse` | `asset_capitalization_reverse` | POST-only action |
| `tags/` | `asset_tag_list` | `asset_tag_list` | `tags`, `page_obj`, `status_choices`, `format_choices` |
| `tags/create/` | `asset_tag_create` | `asset_tag_create` | `form` |
| `tags/<int:pk>/` | `asset_tag_detail` | `asset_tag_detail` | `tag` |
| `tags/<int:pk>/edit/` | `asset_tag_edit` | `asset_tag_edit` | `form`, `tag` |
| `tags/<int:pk>/delete/` | `asset_tag_delete` | `asset_tag_delete` | `tag` |
| `tags/<int:pk>/mark-printed/` | `asset_tag_mark_printed` | `asset_tag_mark_printed` | POST-only action |
| `tags/<int:pk>/affix/` | `asset_tag_affix` | `asset_tag_affix` | POST-only action |
| `tags/<int:pk>/verify/` | `asset_tag_verify` | `asset_tag_verify` | POST-only action |
| `tags/<int:pk>/print/` | `asset_tag_print_label` | `asset_tag_print_label` | `tag` (printable label sheet) |

---

## 4. Context Keys Master Pin Table

| View Function | Context Variable | Type | Source / Values |
|---|---|---|---|
| `asset_requisition_list` | `requisitions` | QuerySet / Page | `AssetRequisition.objects.filter(tenant=request.tenant)` |
| `asset_requisition_list` | `page_obj` | Page | Paginator page |
| `asset_requisition_list` | `status_choices` | list | `AssetRequisition.STATUS_CHOICES` |
| `asset_requisition_list` | `priority_choices` | list | `AssetRequisition.PRIORITY_CHOICES` |
| `asset_requisition_list` | `category_choices` | list | `AssetRequisition.CATEGORY_CHOICES` |
| `asset_requisition_detail` | `requisition` | `AssetRequisition` | Object instance |
| `asset_requisition_create` | `form` | `AssetRequisitionForm` | Unbound form |
| `asset_requisition_edit` | `form` | `AssetRequisitionForm` | Bound form |
| `asset_requisition_edit` | `requisition` | `AssetRequisition` | Object instance |
| `asset_acquisition_receipt_list` | `receipts` | QuerySet / Page | `AssetAcquisitionReceipt.objects.filter(tenant=request.tenant)` |
| `asset_acquisition_receipt_list` | `page_obj` | Page | Paginator page |
| `asset_acquisition_receipt_list` | `status_choices` | list | `AssetAcquisitionReceipt.STATUS_CHOICES` |
| `asset_acquisition_receipt_list` | `condition_choices` | list | `AssetAcquisitionReceipt.CONDITION_CHOICES` |
| `asset_acquisition_receipt_list` | `locations` | QuerySet | `Location.objects.filter(tenant=request.tenant, is_active=True)` |
| `asset_acquisition_receipt_detail` | `receipt` | `AssetAcquisitionReceipt` | Object instance |
| `asset_acquisition_receipt_create` | `form` | `AssetAcquisitionReceiptForm` | Unbound form |
| `asset_acquisition_receipt_edit` | `form` | `AssetAcquisitionReceiptForm` | Bound form |
| `asset_acquisition_receipt_edit` | `receipt` | `AssetAcquisitionReceipt` | Object instance |
| `asset_capitalization_list` | `capitalizations` | QuerySet / Page | `AssetCapitalization.objects.filter(tenant=request.tenant)` |
| `asset_capitalization_list` | `page_obj` | Page | Paginator page |
| `asset_capitalization_list` | `status_choices` | list | `AssetCapitalization.STATUS_CHOICES` |
| `asset_capitalization_list` | `method_choices` | list | `AssetCapitalization.DEPRECIATION_METHOD_CHOICES` |
| `asset_capitalization_detail` | `capitalization` | `AssetCapitalization` | Object instance |
| `asset_capitalization_create` | `form` | `AssetCapitalizationForm` | Unbound form |
| `asset_capitalization_edit` | `form` | `AssetCapitalizationForm` | Bound form |
| `asset_capitalization_edit` | `capitalization` | `AssetCapitalization` | Object instance |
| `asset_tag_list` | `tags` | QuerySet / Page | `AssetTag.objects.filter(tenant=request.tenant)` |
| `asset_tag_list` | `page_obj` | Page | Paginator page |
| `asset_tag_list` | `status_choices` | list | `AssetTag.STATUS_CHOICES` |
| `asset_tag_list` | `format_choices` | list | `AssetTag.TAG_FORMAT_CHOICES` |
| `asset_tag_detail` | `tag` | `AssetTag` | Object instance |
| `asset_tag_create` | `form` | `AssetTagForm` | Unbound form |
| `asset_tag_edit` | `form` | `AssetTagForm` | Bound form |
| `asset_tag_edit` | `tag` | `AssetTag` | Object instance |
| `asset_tag_print_label` | `tag` | `AssetTag` | Object instance |
| `overview` | `kpis` | dict | Aggregated metrics |
| `overview` | `recent_requisitions` | list | Latest 5 requisitions |
| `overview` | `recent_receipts` | list | Latest 5 receipts |
| `overview` | `recent_capitalizations` | list | Latest 5 capitalizations |
| `overview` | `recent_tags` | list | Latest 5 tags |

---

## 5. Navigation & Sidebar Wiring

In `apps/core/navigation.py`:

```python
    "11.1": {
        "Purchase Requisition & Approval": "assets:asset_requisition_list",
        "Vendor Selection & RFQ": "assets:asset_requisition_list",
        "Purchase Order & Receipt": "assets:asset_acquisition_receipt_list",
        "Asset Capitalization & Depreciation Setup": "assets:asset_capitalization_list",
        "Asset Tagging & Registration": "assets:asset_tag_list",
        # Plural and convenience aliases
        "Asset Requisitions": "assets:asset_requisition_list",
        "Acquisition Receipts": "assets:asset_acquisition_receipt_list",
        "Capitalizations": "assets:asset_capitalization_list",
        "Asset Tags": "assets:asset_tag_list",
        "Asset Procurement Hub": "assets:overview",
    },
```
