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
