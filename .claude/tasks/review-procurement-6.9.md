# Review Findings — Procurement 6.9 Catalog Management

Six-lane wave over `2ab53bfe..HEAD` (2026-08-26). Lanes: code-reviewer · explorer ·
frontend-reviewer · performance-reviewer · qa-smoke-tester · security-reviewer.
Duplicates merged; IDs assigned by severity order. Fixer marks `[x] fixed` /
`[~] skipped — reason`. Smoke baseline: temp/smoke_69.py ALL PASS before fixes.

## Critical

### [ ] C1 — Tier single-occupancy invariant bypassable via sequential approvals
`apps/procurement/models/CatalogManagement/Tiers.py` (`approve()`), found independently by
code-reviewer (I1) AND qa-smoke-tester (M1, reproduced twice live).
Two *draft* tiers may share `(tenant, catalog_item, min_quantity)` while nothing is active
(NULL `valid_from` rows don't collide in the unique_together); approving both flips BOTH to
`active` because the overlap guard lives only in `clean()` (form path) and `approve()` saves
via bare `update_fields`. Quoting at that quantity becomes ambiguous — violates the model's
own documented invariant.
**Fix:** inside `approve()`, before mutating, repeat the tenant-scoped sibling query
(`CatalogPriceTier.objects.filter(tenant_id=…, catalog_item_id=…,
min_quantity=self.min_quantity, status="active").exclude(pk=self.pk).exists()` → return
False); keep the flip+save in one transaction. View already renders graceful error on False.
Verify: POST two proposals at qty 200 on one seeded item, approve both → second refused.

## Important

### [ ] I1 — Upload staging not crash-atomic + double-click TOCTOU
`models/CatalogManagement/UploadBatches.py::validate_and_stage` (code-reviewer I2).
Item saves run inside `transaction.atomic()` but the batch status/counters/error-log write
lands outside; a mid-way failure leaves staged items with batch still `received` → retry
double-stages. The `status != "received"` guard is checked before any lock, so two
near-simultaneous POSTs both pass and duplicate the import.
**Fix:** one `transaction.atomic()` around everything after parsing; re-fetch row with
`select_for_update()` and re-check `status == "received"` inside the lock; stage items +
save batch in that same transaction.
Verify: happy-path validate still works; counters consistent after induced failure is hard
headlessly — at minimum assert single-threaded behavior unchanged + code inspection.

### [ ] I2 — Decision verbs lack function-level authorization (OWASP A01)
`views/CatalogManagement/{CatalogItems,Tiers,UploadBatches}.py`: item submit/approve/reject/
block, tier approve/retire, upload validate/publish/reject are gated only by
`@login_required`. Every peer decide/approve verb in this app uses `@tenant_admin_required`
(Amendments.py, VendorSuspensions.py, SourcingEvents.py, ContractsManagement). Maker-checker
is currently bypassable by any member (self-approve staged items + own tiers).
**Fix:** add `@tenant_admin_required` to the decision verbs (keep plain members able to
submit/propose and view). Match house import from apps.core.decorators.
Verify: non-admin member gets refusal; admin flows still pass smoke_69.py.

### [ ] I3 — Upload resource limits absent (OWASP A05)
`forms/UploadBatches.py` extension-only allowlist; model reads whole file into memory, no
row cap; allowlist promises .xls/.xlsx/.xml but parser is CSV-only.
**Fix:** form-level size validator (e.g. ≤ 2 MB), reject > 10 000 data rows into error_log,
narrow ALLOWED_EXTENSIONS to (".csv",) until a real XLSX/XML parser exists (update help text
+ contract docstring reference).
Verify: oversized file → form field error; >10k-row file (generate synthetically) → clean
refusal recorded in error_log/batch state without staging storm.

### [ ] I4 — Tier list FK filter never re-selects (broken dropdown)
`templates/procurement/catalogmanagement/tier/list.html:31` applies
`|stringformat:"d"` to an ALREADY-string GET value → TypeError→"" → never equals pk
(frontend F-01). Siblings do `{% if request.GET.catalog_item == it.pk|stringformat:"d" %}`.
**Fix:** swap operands exactly like catalogitem/list.html:48.
Verify: apply filter → dropdown retains selection.

### [ ] I5 — N+1: catalog item list renders obj.contract.number without join
`views/CatalogManagement/CatalogItems.py` select_related omits `"contract"` while the row
loop renders it (seeded blocked toner row hits this) (performance P-1).
**Fix:** add `"contract"` to select_related (optionally drop unused `"item"` join from the
LIST only — perf P-2 — keep detail intact).
Verify: django-connection count or code inspection; page still renders all columns.

## Minor

### [ ] M1 — CSV formula-injection hardening at staging
`UploadBatches.validate_and_stage`: prefix `'` for staged `name`/`category_text` cells
beginning with `=` `+` `-` `@` `\t`; reject such `supplier_part_no` values with an error line
(code M1 / security F-05). No export exists yet — defense at the boundary.
### [ ] M2 — Dead pre-fetch in `catalog_upload_delete`
`views/.../UploadBatches.py:88` fetches obj then crud_delete re-fetches — delete line
(code M2 / explorer M3).
### [ ] M3 — `EXPECTED_HEADERS` declared but never validated
`models/.../UploadBatches.py`: check `reader.fieldnames ⊇ EXPECTED_HEADERS` right after
DictReader construction → return `(False, "missing columns: …")` (code M3).
### [ ] M4 — Dead class on destructive button
`punchoutendpoint/detail.html:18` `class="btn btn-outline danger"` → use `btn btn-danger`
(frontend F-02).
### [ ] M5 — Discount display truthiness bug at 0%
`tier/list.html:58`, `tier/detail.html:33,53,70` use `{% if obj.discount_pct %}` → explicit
0.00 discount hides the rule; mirror `is not None` guard from catalogitem/detail.html:83
(frontend F-03).
### [ ] M6 — Stray multipart enctype on item form
`catalogitem/form.html:8` has no FileField — remove attribute (frontend F-04).
### [ ] M7 — Party FK related_names missing `procurement_` prefix
`PunchOutEndpoints.party.related_name="punchout_endpoints"` and
`UploadBatches.party.related_name="catalog_upload_batches"` vs sibling convention
(`procurement_*`) (explorer M2). Rename → regenerate procurement migration (expect 0014;
0012 belongs to the parallel session — do not touch it).
### [ ] M8 — URL module import idiom drift
`urls/CatalogManagement/CatalogItems.py` imports view callables directly; every sibling uses
`from apps.procurement import views` + `views.<name>`; restore inline literal-before-pk
comment (code M5 / explorer M1).
### [ ] M9 — `unique_together` list-of-tuple style
`CatalogItems.Meta` uses `[("tenant","number")]`; newest siblings use bare tuple (explorer L4).
### [ ] M10 — Seeded punch-out endpoints skip audit rows
Add `write_audit_log(None, endpoint, "create")` ×2 in `_seed_catalog` (explorer L2).
### [ ] M11 — `_seed_catalog` reaches into `_eauc_supplier`
Add thin self-describing alias `_catalog_supplier = _eauc_supplier`-style helper or local
wrapper so the block doesn't couple to an e-auction-named method (explorer L3).
### [ ] M12 — Admin can hand-flip `status` on the three workflow models
Add `"status"` to readonly_fields on CatalogItemAdmin/CatalogPriceTierAdmin/
CatalogUploadBatchAdmin to match the file's own posture (security F-04).
### [ ] M13 — Belt-and-braces: add `"shared_secret"` to `core.crud._SENSITIVE_AUDIT_FIELDS`
One-line addition in apps/core/crud.py frozenset so any future refactor onto crud_edit cannot
leak the secret into AuditLog.changes (security F-03). COORDINATION: shared foundation file —
surgical Edit only; parallel session is active in apps/procurement, not core.
### [ ] M14 — Entity modules bypass package re-exports for cross-entity imports
`from apps.procurement.models.CatalogManagement.CatalogItems import CatalogItem` works but
siblings import via `from apps.procurement.models import …`; normalize views/forms imports
now that re-exports exist (KEEP the models-package internal import in UploadBatches.py
validate_and_stage — legitimate intra-package wiring) (explorer L1).
### [ ] M15 — Seeder user lookup hoist (optional polish)
Fetch approver user once before the atomic block; pass approved_by/submitted_by as create()
kwargs, dropping the two post-create UPDATEs (perf P-4).
### [ ] M16 — Info-only, NO ACTION
Mixed-lane range contains committed 6.8 follow-ups (their session's files); `/media/` served
unauthenticated only under DEBUG=True (config/urls.py static()) — production-safe default.

## Clean areas (consensus across lanes)
State machines stamp-once + return False on illegal transitions; q2 clamping everywhere;
explicit-fields forms with TenantUniqueMixin first + _reject_foreign on every tenant-scoped FK;
currency correctly global; tenant scoping universal incl. all verbs and choices; POST-only
verbs with audit; secret runtime handling exemplary (pop-on-edit, PasswordInput, placeholder,
admin exclude, redacted audit); CSRF/XSS/mass-assignment/injection surfaces clean; migration
0013 ↔ models parity; re-export completeness 30/30 views, 4/4 forms/models; template path
shape per CLAUDE.md; sidebar 5 bullets live matching 6.8 markup; junk-param hostile GETs
zero-500; superuser sees empty lists by design; deep QA matrix 26/26 except C1.
