# Review Findings — Procurement 6.9 Catalog Management

Six-lane wave over `2ab53bfe..HEAD` (2026-08-26). Lanes: code-reviewer · explorer ·
frontend-reviewer · performance-reviewer · qa-smoke-tester · security-reviewer.
Duplicates merged; IDs assigned by severity order. Fixer marks `[x] fixed` /
`[~] skipped — reason`. Smoke baseline: temp/smoke_69.py ALL PASS before fixes.

## Critical

### [x] C1 fixed — `approve()` now re-runs the tenant-scoped active-sibling query inside one `transaction.atomic()` before flipping+saving; a second sequential approval returns False (probe verified: two drafts @ qty 200 → first True/active, second False/draft).
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

### [x] I1 fixed — `validate_and_stage` wraps item saves AND batch status/counters/error-log in ONE atomic block, re-fetching the row with `select_for_update()` and re-checking `status == "received"` inside the lock (probe: happy path stages 1/2 rows w/ error_log; re-validate refused).
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

### [x] I2 fixed — `@tenant_admin_required` added to item approve/reject/block, tier approve/retire, upload validate/publish/reject (submit stays member-open; house decorator stack matched). Probe: member POSTs → 403 with state unchanged; admin approve → 302 + approved; smoke ALL PASS.
`views/CatalogManagement/{CatalogItems,Tiers,UploadBatches}.py`: item submit/approve/reject/
block, tier approve/retire, upload validate/publish/reject are gated only by
`@login_required`. Every peer decide/approve verb in this app uses `@tenant_admin_required`
(Amendments.py, VendorSuspensions.py, SourcingEvents.py, ContractsManagement). Maker-checker
is currently bypassable by any member (self-approve staged items + own tiers).
**Fix:** add `@tenant_admin_required` to the decision verbs (keep plain members able to
submit/propose and view). Match house import from apps.core.decorators.
Verify: non-admin member gets refusal; admin flows still pass smoke_69.py.

### [x] I3 fixed — form-level 2 MB size validator (`MAX_UPLOAD_BYTES`), `ALLOWED_EXTENSIONS` narrowed to `(".csv",)` with model clean()/form messages + help text updated, and a 10 000-row cap that early-stops parsing into a clean `(False, "file exceeds the … data-row limit")` refusal (probe verified all three).
`forms/UploadBatches.py` extension-only allowlist; model reads whole file into memory, no
row cap; allowlist promises .xls/.xlsx/.xml but parser is CSV-only.
**Fix:** form-level size validator (e.g. ≤ 2 MB), reject > 10 000 data rows into error_log,
narrow ALLOWED_EXTENSIONS to (".csv",) until a real XLSX/XML parser exists (update help text
+ contract docstring reference).
Verify: oversized file → form field error; >10k-row file (generate synthetically) → clean
refusal recorded in error_log/batch state without staging storm.

### [x] I4 fixed — operands swapped to `{% if request.GET.catalog_item == it.pk|stringformat:"d" %}` (value attr also stringified), matching catalogitem/list.html:48.
`templates/procurement/catalogmanagement/tier/list.html:31` applies
`|stringformat:"d"` to an ALREADY-string GET value → TypeError→"" → never equals pk
(frontend F-01). Siblings do `{% if request.GET.catalog_item == it.pk|stringformat:"d" %}`.
**Fix:** swap operands exactly like catalogitem/list.html:48.
Verify: apply filter → dropdown retains selection.

### [x] I5 fixed — LIST `select_related` now `"supplier", "contract", "uom", "currency"` (contract added for the rendered `obj.contract.number`, unused `"item"` join dropped; detail untouched). List page renders 11 queries with the blocked toner contract column present.
`views/CatalogManagement/CatalogItems.py` select_related omits `"contract"` while the row
loop renders it (seeded blocked toner row hits this) (performance P-1).
**Fix:** add `"contract"` to select_related (optionally drop unused `"item"` join from the
LIST only — perf P-2 — keep detail intact).
Verify: django-connection count or code inspection; page still renders all columns.

## Minor

### [x] M1 fixed — staging prefixes `'` onto formula-leading (`= + - @ \t`) `name`/`category_text` text cells and rejects formula-leading `supplier_part_no` rows with an error-log line (probe verified both paths).
`UploadBatches.validate_and_stage`: prefix `'` for staged `name`/`category_text` cells
beginning with `=` `+` `-` `@` `\t`; reject such `supplier_part_no` values with an error line
(code M1 / security F-05). No export exists yet — defense at the boundary.
### [x] M2 fixed — dead `get_object_or_404` pre-fetch removed from `catalog_upload_delete`; `crud_delete` re-fetches itself.
`views/.../UploadBatches.py:88` fetches obj then crud_delete re-fetches — delete line
(code M2 / explorer M3).
### [x] M3 fixed — `reader.fieldnames` checked against `EXPECTED_HEADERS` right after `DictReader` construction; missing columns → `(False, "missing columns: …")` (probe verified).
`models/.../UploadBatches.py`: check `reader.fieldnames ⊇ EXPECTED_HEADERS` right after
DictReader construction → return `(False, "missing columns: …")` (code M3).
### [x] M4 fixed — destructive delete button now `btn btn-danger`.
`punchoutendpoint/detail.html:18` `class="btn btn-outline danger"` → use `btn btn-danger`
(frontend F-02).
### [x] M5 fixed — all four `discount_pct` guards switched to `is not None` (tier list row, tier detail rule + pricing table + sibling rows) so an explicit 0.00 discount renders.
`tier/list.html:58`, `tier/detail.html:33,53,70` use `{% if obj.discount_pct %}` → explicit
0.00 discount hides the rule; mirror `is not None` guard from catalogitem/detail.html:83
(frontend F-03).
### [x] M6 fixed — stray `enctype="multipart/form-data"` removed from the item form (no FileField).
`catalogitem/form.html:8` has no FileField — remove attribute (frontend F-04).
### [x] M7 fixed — related_names renamed to `procurement_punchout_endpoints` / `procurement_catalog_upload_batches`; migration `0014_alter_cataloguploadbatch_party_and_more` generated via makemigrations and migrated (0012/0013 untouched).
`PunchOutEndpoints.party.related_name="punchout_endpoints"` and
`UploadBatches.party.related_name="catalog_upload_batches"` vs sibling convention
(`procurement_*`) (explorer M2). Rename → regenerate procurement migration (expect 0014;
0012 belongs to the parallel session — do not touch it).
### [x] M8 fixed — item urls restored to `from apps.procurement import views` + `views.<name>` idiom with the literal-before-pk comment; all 9 names reverse-checked.
`urls/CatalogManagement/CatalogItems.py` imports view callables directly; every sibling uses
`from apps.procurement import views` + `views.<name>`; restore inline literal-before-pk
comment (code M5 / explorer M1).
### [x] M9 fixed — `CatalogItem.Meta.unique_together` now a bare tuple; `makemigrations --check` reports no changes.
`CatalogItems.Meta` uses `[("tenant","number")]`; newest siblings use bare tuple (explorer L4).
### [x] M10 fixed — `write_audit_log(None, endpoint, "create")` added after both seeded `PunchOutEndpoint.objects.create(...)` calls.
Add `write_audit_log(None, endpoint, "create")` ×2 in `_seed_catalog` (explorer L2).
### [x] M11 fixed — thin self-describing `_catalog_supplier` alias added above `_seed_catalog`; both call sites (Northwind + Cascade) now use it — no `_eauc_supplier` reference left in the catalog block.
Add thin self-describing alias `_catalog_supplier = _eauc_supplier`-style helper or local
wrapper so the block doesn't couple to an e-auction-named method (explorer L3).
### [x] M12 fixed — `"status"` added to `readonly_fields` on CatalogItemAdmin, CatalogPriceTierAdmin and CatalogUploadBatchAdmin (registry probe verified all three).
Add `"status"` to readonly_fields on CatalogItemAdmin/CatalogPriceTierAdmin/
CatalogUploadBatchAdmin to match the file's own posture (security F-04).
### [x] M13 fixed — `"shared_secret"` added to `apps/core/crud._SENSITIVE_AUDIT_FIELDS` (surgical 3-line edit only; import probe verified).
One-line addition in apps/core/crud.py frozenset so any future refactor onto crud_edit cannot
leak the secret into AuditLog.changes (security F-03). COORDINATION: shared foundation file —
surgical Edit only; parallel session is active in apps/procurement, not core.
### [x] M14 fixed — all four CatalogManagement views and forms now import via `from apps.procurement.models import …` / `from apps.procurement.forms import …`; the intra-package import inside `models/CatalogManagement/UploadBatches.py::validate_and_stage` kept as-is (all 8 modules import cleanly).
`from apps.procurement.models.CatalogManagement.CatalogItems import CatalogItem` works but
siblings import via `from apps.procurement.models import …`; normalize views/forms imports
now that re-exports exist (KEEP the models-package internal import in UploadBatches.py
validate_and_stage — legitimate intra-package wiring) (explorer L1).
### [x] M15 fixed — approver user fetched once before the atomic block; `approved_by`/`submitted_by`/`validated_by` passed as `create()` kwargs; both post-create UPDATEs dropped (AST probe: 0 `.save(update_fields=)` left in `_seed_catalog`).
Fetch approver user once before the atomic block; pass approved_by/submitted_by as create()
kwargs, dropping the two post-create UPDATEs (perf P-4).
### [~] M16 skipped — info-only finding, NO ACTION per review verdict (no code change required).
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
