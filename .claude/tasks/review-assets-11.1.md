# Review Findings: Sub-module 11.1 Asset Procurement & Acquisition

Base changeset: `bc6237b0a0cb658deeb38bad07eb93981df3cc42...HEAD`

---

## Pass 1: Code Reviewer (`code-reviewer`)

### Critical
1. `apps/assets/views/AssetProcurement/AssetCapitalizations.py:152` — `asset_capitalization_delete` does not enforce a view-level status guard, allowing direct POST deletion of an already-capitalized asset record and orphaning the linked `FixedAsset` ledger record. Fix: Reject deletion if `capitalization.status == "capitalized"`, requiring explicit reversal first.
2. `apps/assets/views/AssetProcurement/AssetRequisitions.py:139` — `asset_requisition_delete` has no status guard, allowing direct POST deletion of requisitions in `approved`, `ordered`, or `received` status. Fix: Restrict deletion to records where `requisition.status in ("draft", "rejected")`.
3. `apps/assets/views/AssetProcurement/AssetAcquisitionReceipts.py:141` — `asset_acquisition_receipt_delete` lacks a status guard, allowing deletion of accepted or already-capitalized intake receipts. Fix: Reject deletion if `receipt.status in ("accepted", "capitalized")`.

### Important
1. `apps/assets/forms/AssetProcurement/AssetRequisitions.py:15` — `AssetRequisitionForm` does not exclude `status` and renders an editable status dropdown in `templates/assets/asset_procurement/asset_requisition/form.html:155`, allowing users to bypass approval workflows by creating/editing records directly into `approved` or `ordered`. Fix: Add `"status"` to `Meta.exclude` and remove the status dropdown from the template form.
2. `apps/assets/forms/AssetProcurement/AssetAcquisitionReceipts.py:13` — `AssetAcquisitionReceiptForm` does not exclude `status` and renders it in `templates/assets/asset_procurement/asset_acquisition_receipt/form.html:133`, allowing users to bypass the inspection/quarantine workflow. Fix: Add `"status"` to `Meta.exclude` and remove the status field from the template form.
3. `apps/assets/forms/AssetProcurement/AssetCapitalizations.py:16` — `AssetCapitalizationForm` does not exclude `status` and renders it in `templates/assets/asset_procurement/asset_capitalization/form.html:177`, enabling direct creation of "capitalized" records without executing `asset_capitalization_execute` and creating the `FixedAsset`. Fix: Add `"status"` to `Meta.exclude` and remove the status field from the template form.
4. `apps/assets/forms/AssetProcurement/AssetTags.py:12` — `AssetTagForm` does not exclude `status` and renders it in `templates/assets/asset_procurement/asset_tag/form.html:98`, allowing unverified tags to be set directly to `verified` without scanner audit. Fix: Add `"status"` to `Meta.exclude` and remove the status field from the template form.
5. `apps/assets/views/AssetProcurement/AssetAcquisitionReceipts.py:44` — `location_id` parsed from `request.GET.get("location")` is filtered directly via `receiving_location_id=location_id` without `.isdigit()` validation, raising a 500 on non-numeric input. Fix: Guard with `if location_id and location_id.isdigit():`.
6. `apps/assets/views/AssetProcurement/AssetCapitalizations.py:89` — `receipt_pk` from `request.GET.get("receipt")` is passed directly into `.filter(pk=receipt_pk)` without `.isdigit()` validation, raising a 500 on non-numeric parameters. Fix: Guard with `if receipt_pk and receipt_pk.isdigit():`.
7. `apps/assets/views/AssetProcurement/AssetTags.py:80` — `cap_pk` from `request.GET.get("capitalization")` is passed directly into `.filter(pk=cap_pk)` without `.isdigit()` validation, raising a 500 on non-numeric parameters. Fix: Guard with `if cap_pk and cap_pk.isdigit():`.
8. `templates/assets/asset_procurement/asset_acquisition_receipt/list.html:27` — The view queries and passes `locations` to context, but the template filter `<form>` completely omits the location `<select>` dropdown and drops the param in pagination. Fix: Add the location filter select widget and preserve `&location={{ request.GET.location }}` in pagination links.
9. `templates/assets/asset_procurement/asset_capitalization/list.html:27` — The view passes `method_choices` to context, but the template filter `<form>` omits the depreciation method `<select>` dropdown and drops the param in pagination. Fix: Add the method filter dropdown and preserve `&method={{ request.GET.method }}` in pagination links.
10. `templates/assets/asset_procurement/asset_tag/list.html:27` — The view passes `format_choices` to context, but the template filter `<form>` omits the tag format `<select>` dropdown and drops the param in pagination. Fix: Add the format filter dropdown and preserve `&format={{ request.GET.format }}` in pagination links.

### Minor
1. `apps/assets/management/commands/seed_assets.py:48` — Seeder completion output does not print the standard reminder regarding tenant admin credentials and the `tenant=None` empty view behavior for the superuser. Fix: Add standard stdout notice informing users to log in with `admin_acme`.
2. `apps/assets/views/AssetProcurement/AssetRequisitions.py:212` — `asset_requisition_reject` does not validate that `rejection_reason` is non-empty on the server side before persisting status change. Fix: Validate `if not reason: messages.error(...)`.
3. `apps/assets/forms/AssetProcurement/AssetRequisitions.py:15` — `rejection_reason` is included in `AssetRequisitionForm` and rendered in edit mode, allowing editing of rejection history outside the workflow rejection modal. Fix: Add `"rejection_reason"` to `Meta.exclude`.
4. `apps/assets/views/AssetProcurement/AssetRequisitions.py:180` — `asset_requisition_approve` permits the submitter to approve their own CapEx requisition (`requisition.submitted_by == request.user`). Fix: Add validation warning or require admin approval.

---

## Pass 2: Codebase Explorer (`explorer`)

### Critical
1. `apps/assets/forms/AssetProcurement/AssetTags.py:12` — `is_verified` is not included in `Meta.exclude` on `AssetTagForm` and is not rendered in `templates/assets/asset_procurement/asset_tag/form.html`. Because Django ModelForm treats omitted BooleanField inputs in POST data as `False`, editing any verified `AssetTag` (`is_verified=True`) via `asset_tag_edit` silently overwrites and resets `is_verified` back to `False`. Fix: Add `"is_verified"` to `Meta.exclude` in `AssetTagForm`.

### Important
1. `apps/assets/models/__init__.py:1-7` — `apps/assets/models/__init__.py` does not re-export `AssetRequisition`, `AssetAcquisitionReceipt`, `AssetCapitalization`, and `AssetTag` from `apps.assets.models.AssetProcurement`. While Django's app registry caches models, importing from `apps.assets.models` or `from apps.assets.models import *` fails to expose the sub-module models, violating the NavERP backend package re-export contract. Fix: Re-export the 4 models from `apps.assets.models.AssetProcurement` in `apps/assets/models/__init__.py` and add them to `__all__`.
2. `templates/assets/asset_procurement/asset_requisition/list.html:27` — View `asset_requisition_list` passes `"category_choices"` and filters on `request.GET.get("category")`, but the template filter `<form>` omits the category `<select name="category">` dropdown. Additionally, pagination links drop `&category={{ request.GET.category }}`. Fix: Add category dropdown populated from `category_choices` to the filter `<form>` in `list.html` and preserve parameter in pagination links.
3. `templates/assets/asset_procurement/asset_acquisition_receipt/list.html:27` — View passes `"locations"` and filters on `receiving_location_id`, but template filter `<form>` omits the location `<select name="location">` dropdown. Fix: Add location filter dropdown and preserve in pagination links.
4. `templates/assets/asset_procurement/asset_capitalization/list.html:27` — View passes `"method_choices"` and filters on `depreciation_method`, but template filter `<form>` omits the depreciation method `<select name="method">` dropdown. Fix: Add method filter dropdown and preserve in pagination links.
5. `templates/assets/asset_procurement/asset_tag/list.html:27` — View passes `"format_choices"` and filters on `tag_format`, but template filter `<form>` omits the tag format `<select name="format">` dropdown. Fix: Add format filter dropdown and preserve in pagination links.

### Minor
1. `apps/assets/views/AssetProcurement/AssetCapitalizations.py:88-90` — In `asset_capitalization_create`, `receipt_pk = request.GET.get("receipt")` is passed directly into `.filter(pk=receipt_pk)` without `.isdigit()` validation, raising a 500 / ValueError on malformed query strings. Fix: Guard with `if receipt_pk and receipt_pk.isdigit():`.
2. `apps/assets/views/AssetProcurement/AssetTags.py:79-81` — In `asset_tag_create`, `cap_pk = request.GET.get("capitalization")` is passed directly into `.filter(pk=cap_pk)` without `.isdigit()` validation, raising a 500 / ValueError on malformed query strings. Fix: Guard with `if cap_pk and cap_pk.isdigit():`.
3. `apps/assets/views/AssetProcurement/AssetAcquisitionReceipts.py:43-45` — In `asset_acquisition_receipt_list`, `location_id = request.GET.get("location")` is filtered directly via `receiving_location_id=location_id` without checking `.isdigit()`. Fix: Guard with `if location_id and location_id.isdigit():`.
4. `apps/assets/forms/AssetProcurement/AssetRequisitions.py:51` — `self.fields["proposed_vendor"].queryset` filters `roles__role__in=["vendor", "supplier"]` without checking `roles__status="active"`. Inactive or archived supplier profiles could be selected. Fix: Add `roles__status="active"` to the queryset filter.

---

## Pass 3: Frontend Reviewer (`frontend-reviewer`)

### Critical
None.

### Important
1. `templates/assets/asset_procurement/asset_requisition/list.html:27` — `<select name="category">` dropdown filter is missing from the filter form, and pagination links do not preserve `&category={{ request.GET.category }}`. Fix: Add category dropdown populated from `category_choices` to filter form and append parameter to pagination links.
2. `templates/assets/asset_procurement/asset_acquisition_receipt/list.html:27` — `<select name="location">` dropdown filter is missing from the filter form, and pagination links do not preserve `&location={{ request.GET.location }}`. Fix: Add location filter dropdown using `|stringformat:"d"` for PK comparison, and preserve parameter in pagination links.
3. `templates/assets/asset_procurement/asset_capitalization/list.html:27` — `<select name="method">` dropdown filter is missing from the filter form, and pagination links do not preserve `&method={{ request.GET.method }}`. Fix: Add depreciation method dropdown populated from `method_choices`, and preserve parameter in pagination links.
4. `templates/assets/asset_procurement/asset_tag/list.html:27` — `<select name="format">` dropdown is missing from the filter form. Fix: Add technology format dropdown populated from `format_choices`.

### Minor
1. `templates/assets/asset_procurement/asset_requisition/detail.html:48` (and receipt, cap, tag detail views) — Icon-only Delete buttons lack `title="Delete"` and `aria-label="Delete"`. Fix: Add accessibility labels.
2. `templates/assets/asset_procurement/asset_requisition/list.html:29` (and list filter cards) — Filter labels not explicitly linked to inputs with `for` and `id`. Fix: Add `for` and matching `id` attributes.
3. `templates/assets/asset_procurement/asset_requisition/detail.html:135` — `requisition.purchase_order.vendor.name` accessed without checking if `vendor` is non-null. Fix: Guard with `{% if requisition.purchase_order.vendor %}`.

---

## Pass 4: Performance Reviewer (`performance-reviewer`)

### Critical
None.

### Important
1. `apps/assets/forms/AssetProcurement/AssetRequisitions.py:56` and `AssetAcquisitionReceipts.py:46` — Form dropdown N+1 via `PurchaseOrder.__str__` which references `self.vendor`. Fix: Add `.select_related("vendor")` to `purchase_order` form field queryset.
2. `apps/assets/views/overview.py:22-33` — Overview executes 8 separate DB count/sum queries. Fix: Combine queries using conditional aggregation (`Count("id", filter=Q(...))`, `Sum("total_cost_basis", filter=Q(...))`) into 4 queries.
3. `apps/assets/models/AssetProcurement/AssetAcquisitionReceipts.py:116` — Missing index for default sort order `(tenant, received_date)`. Fix: Add `models.Index(fields=["tenant", "received_date"], name="idx_arcv_ten_rcvdate")`.
4. `apps/assets/views/AssetProcurement/AssetCapitalizations.py:169-205` — Missing concurrency row lock in `asset_capitalization_execute`. Double-clicks can create duplicate `FixedAsset` ledger instances. Fix: Use `select_for_update()` inside `transaction.atomic()`.
5. `apps/assets/views/AssetProcurement/*.py` — State mutation workflow endpoints lack `with transaction.atomic():` surrounding status changes and audit log writes. Fix: Wrap in atomic transactions.

### Minor
1. `apps/assets/views/AssetProcurement/AssetRequisitions.py:62` — Requisition detail does not select `"purchase_order__vendor"`. Fix: Add to `select_related`.
2. `apps/assets/views/AssetProcurement/AssetTags.py:236` — Tag print label view accesses `operational_asset.location.name` without `"operational_asset__location"`. Fix: Add to `select_related`.
3. `apps/assets/models/AssetProcurement/AssetTags.py:102` — Missing index on `(tenant, is_verified)`. Fix: Add `models.Index(fields=["tenant", "is_verified"], name="idx_atag_ten_ver")`.
4. `apps/assets/admin.py:11-36` — ModelAdmins lack `list_select_related = ("tenant",)`. Fix: Add `list_select_related`.

---

## Pass 5: QA Smoke Tester (`qa-smoke-tester`)

### Critical
1. `apps/assets/views/AssetProcurement/*.py` (all 22 mutation views) — Incompatible `write_audit_log()` call signature: views call `write_audit_log(request=request, action="...", instance=..., details=...)` but `apps.core.utils.write_audit_log` defines `(user, obj, action, changes=None, tenant=None)`. Passing `request` causes a runtime `TypeError: write_audit_log() got an unexpected keyword argument 'request'`, crashing any form save, update, delete, approval, rejection, inspection, capitalization execution, or tag verification with HTTP 500. Additionally, `AuditLog.action` has `max_length=10` (`"create"`, `"update"`, `"delete"`), so long custom strings cause truncation. Fix: Update all 22 calls to `write_audit_log(request.user, instance, "update", changes={...}, tenant=request.tenant)`.

### Important
1. `apps/assets/views/AssetProcurement/AssetAcquisitionReceipts.py:43-46` — Unhandled `ValueError` when filtering `location` with non-digit query parameters (`?location=bad`), raising an unhandled HTTP 500. Fix: Guard with `if location_id and location_id.isdigit():`.
2. `apps/assets/views/AssetProcurement/AssetCapitalizations.py:88-91` and `AssetTags.py:79-82` — Unhandled `ValueError` on non-numeric initial query parameters in Create views (`?receipt=bad`, `?capitalization=bad`), crashing with HTTP 500. Fix: Check `.isdigit()` before querying.
3. `templates/assets/asset_procurement/*/*.html` — Filter dropdowns omitted from list templates (`category`, `location`, `method`, `format`). Fix: Add missing `<select>` dropdown controls to all 4 list templates.

### Minor
None.

---
