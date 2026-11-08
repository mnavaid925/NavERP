# Review Findings: Sub-module 11.1 Asset Procurement & Acquisition

Base changeset: `bc6237b0a0cb658deeb38bad07eb93981df3cc42...HEAD`
Reviewers: `code-reviewer`, `explorer`, `frontend-reviewer`, `performance-reviewer`, `qa-smoke-tester`, `security-reviewer`

---

## Critical

- [x] `C1` — `apps/assets/views/AssetProcurement/*.py` (all 22 mutation views): Incompatible `write_audit_log()` call signature. Views call `write_audit_log(request=request, action="...", instance=..., details=...)` but `apps.core.utils.write_audit_log` defines `(user, obj, action, changes=None, tenant=None)`. Calling with `request` raises a runtime `TypeError: unexpected keyword argument 'request'` on every POST mutation (create, edit, delete, approve, reject, inspect, quarantine, execute, reverse, mark_printed, affix, verify). Additionally, `AuditLog.action` has `max_length=10`. Fix: Update all 22 calls to `write_audit_log(request.user, instance, "update", changes={...}, tenant=request.tenant)`.
- [x] `C2` — `apps/assets/forms/AssetProcurement/*.py` and `templates/assets/asset_procurement/*/form.html`: Pervasive mass assignment of workflow `status`. All 4 ModelForms omit `"status"` from `Meta.exclude` and render an editable `<select name="status">` in template forms, allowing users to bypass approval, inspection, capitalization, and scanner verification workflows. Fix: Add `"status"` to `Meta.exclude` in all 4 ModelForms, remove `"status"` from form widgets, and remove status select fields from form templates.
- [x] `C3` — `apps/assets/forms/AssetProcurement/AssetTags.py:12`: Mass assignment and silent clearing of `is_verified` on `AssetTagForm`. `is_verified` is omitted from `Meta.exclude`. In Django ModelForms, missing boolean fields in POST data evaluate to `False`, so editing any verified asset tag silently clears `is_verified` back to `False`. Fix: Add `"is_verified"` and `"scanner_device_id"` to `Meta.exclude` in `AssetTagForm`.
- [x] `C4` — `apps/assets/views/AssetProcurement/*.py` (`asset_capitalization_delete`, `asset_requisition_delete`, `asset_acquisition_receipt_delete`, `asset_tag_delete`): Missing status guards on deletion views. Raw POST deletion permits deleting already-capitalized records (orphaning the linked `accounting.FixedAsset` ledger record), approved requisitions, accepted intake receipts, and active tags. Fix: Reject deletion if `capitalization.status == "capitalized"` (require reversal first); restrict requisition deletion to `("draft", "rejected")`; reject receipt deletion if `("accepted", "capitalized")`; restrict tag deletion to `("pending_print", "printed", "damaged_reissued")`.
- [x] `C5` — `apps/assets/views/AssetProcurement/AssetRequisitions.py:180`: Segregation of Duties (SoD) bypass / self-approval on CapEx Requisitions. Submitter can approve their own capital expenditure requisition (`requisition.submitted_by_id == request.user.pk`). Fix: Enforce a view-level check in `asset_requisition_approve` prohibiting self-approval.

---

## Important

- [x] `I1` — `apps/assets/models/__init__.py:1-7`: Sub-module models (`AssetRequisition`, `AssetAcquisitionReceipt`, `AssetCapitalization`, `AssetTag`) are not re-exported in `apps/assets/models/__init__.py`, violating the NavERP backend package re-export contract and breaking `from apps.assets.models import *`. Fix: Re-export the 4 models and include them in `__all__`.
- [x] `I2` — `templates/assets/asset_procurement/*/*.html`: Missing filter dropdowns and pagination parameter loss in all four list templates.
  - `asset_requisition/list.html`: missing `<select name="category">` for `category_choices`, pagination drops `&category={{ request.GET.category }}`.
  - `asset_acquisition_receipt/list.html`: missing `<select name="location">` for `locations`, pagination drops `&location={{ request.GET.location }}`.
  - `asset_capitalization/list.html`: missing `<select name="method">` for `method_choices`, pagination drops `&method={{ request.GET.method }}`.
  - `asset_tag/list.html`: missing `<select name="format">` for `format_choices`, pagination drops `&format={{ request.GET.format }}`.
  Fix: Add the missing `<select>` controls to the filter cards and preserve parameters in pagination links.
- [x] `I3` — `apps/assets/views/AssetProcurement/*.py`: Unhandled `ValueError` HTTP 500 crashes on non-numeric GET parameters in `asset_acquisition_receipt_list` (`?location=bad`), `asset_capitalization_create` (`?receipt=bad`), and `asset_tag_create` (`?capitalization=bad`). Fix: Guard with `if param and param.isdigit():`.
- [x] `I4` — `apps/assets/views/AssetProcurement/AssetCapitalizations.py:169-205`: Missing concurrency row locking with `select_for_update()` in `asset_capitalization_execute`. Concurrent requests / rapid double clicks can create duplicate `FixedAsset` ledger instances. Fix: Acquire row lock with `select_for_update()` inside `transaction.atomic()`.
- [x] `I5` — `apps/assets/views/AssetProcurement/*.py`: Lifecycle state mutation endpoints lack `with transaction.atomic():` surrounding status changes and audit log writes. Fix: Wrap all mutation workflows in atomic transactions.
- [x] `I6` — `apps/assets/forms/AssetProcurement/AssetRequisitions.py:56` and `AssetAcquisitionReceipts.py:46`: Form dropdown N+1 queries via `PurchaseOrder.__str__` (which accesses `self.vendor`). Fix: Add `.select_related("vendor")` to `purchase_order` form field querysets.
- [ ] `I7` — `apps/assets/views/overview.py:22-33`: Overview KPIs execute 8 separate round-trip count/sum queries. Fix: Consolidate using conditional aggregation (`Count("id", filter=Q(...))`, `Sum(...)`) into 4 queries.
- [ ] `I8` — `apps/assets/models/AssetProcurement/AssetAcquisitionReceipts.py:116`: Missing index for default sort order `(tenant, received_date)`. Fix: Add `models.Index(fields=["tenant", "received_date"], name="idx_arcv_ten_rcvdate")`.
- [ ] `I9` — `apps/assets/views/AssetProcurement/*.py`: Missing status guards on edit views (`asset_capitalization_edit`, `asset_requisition_edit`, `asset_acquisition_receipt_edit`). Editing capitalized assets desynchronizes financial ledger records; editing approved requisitions alters CapEx without re-approval. Fix: Block edit mode if capitalization is `"capitalized"`, requisition is in `("approved", "ordered", "received")`, or receipt is `"capitalized"`.
- [ ] `I10` — `apps/assets/views/AssetProcurement/AssetCapitalizations.py:169, 218`: Missing privilege gates on financial ledger mutations (`asset_capitalization_execute`, `asset_capitalization_reverse`). Low-privilege users can create or reverse fixed asset ledger records. Fix: Decorate with `@tenant_admin_required`.

---

## Minor

- [ ] `M1` — `apps/assets/forms/AssetProcurement/AssetRequisitions.py:15`: Rejection reason mass assignment on `AssetRequisitionForm`. Fix: Add `"rejection_reason"` to `Meta.exclude`.
- [ ] `M2` — `apps/assets/views/AssetProcurement/AssetRequisitions.py:212`: Empty rejection reason allowed in `asset_requisition_reject`. Fix: Validate `if not reason: messages.error(...)`.
- [ ] `M3` — `apps/assets/models/AssetProcurement/AssetTags.py:102`: Missing index on `(tenant, is_verified)`. Fix: Add `models.Index(fields=["tenant", "is_verified"], name="idx_atag_ten_ver")`.
- [ ] `M4` — `apps/assets/views/AssetProcurement/AssetRequisitions.py:62`: Requisition detail view does not eager-load `"purchase_order__vendor"`. Fix: Add to `select_related`.
- [ ] `M5` — `apps/assets/views/AssetProcurement/AssetTags.py:236`: Tag print label view accesses `operational_asset.location.name` without selecting location. Fix: Add `"operational_asset__location"` to `select_related`.
- [ ] `M6` — `apps/assets/admin.py:11-36`: ModelAdmins lack `list_select_related = ("tenant",)`. Fix: Add `list_select_related`.
- [ ] `M7` — `templates/assets/asset_procurement/asset_requisition/detail.html:135`: Potential null vendor traversal `requisition.purchase_order.vendor.name`. Fix: Guard with `{% if requisition.purchase_order.vendor %}`.
- [ ] `M8` — `templates/assets/asset_procurement/*/*detail.html`: Icon-only Delete buttons lack `title="Delete"` and `aria-label="Delete"`. Fix: Add accessibility labels.
- [ ] `M9` — `templates/assets/asset_procurement/*/*list.html`: Filter labels not explicitly linked with input IDs. Fix: Add `for` and matching `id` attributes.
- [ ] `M10` — `apps/assets/management/commands/seed_assets.py:48`: Seeder output lacks stdout notice regarding tenant admin login credentials (`admin_acme` / `password`). Fix: Add reminder notice.
- [ ] `M11` — `apps/assets/forms/AssetProcurement/AssetRequisitions.py:51`: Vendor queryset does not filter `roles__status="active"`. Fix: Add `roles__status="active"`.
- [ ] `M12` — `apps/assets/forms/AssetProcurement/AssetCapitalizations.py:30`: Cost fields lack server-side negative amount validation. Fix: Add validation in `clean()` ensuring cost fields are `>= 0`.

---
