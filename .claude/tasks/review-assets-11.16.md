# Module 11.16 Review Findings — Asset Document & Knowledge Management

- **Base SHA**: `66c68399b9650309faea01195c456adbc9622c98`
- **Review Range**: `66c68399b9650309faea01195c456adbc9622c98...HEAD`
- **Status**: All 6 passes complete — deduplicated, sorted, ID-assigned (4 Critical, 15 Important, 13 Minor)

---

## Pass 1 — `code-reviewer`

### Verdict
Commit after fixing Critical+Important findings (0 Critical, 5 Important, 5 Minor) in Module 11.16 (`66c68399b9650309faea01195c456adbc9622c98...HEAD`, scoped to 11.16 commits and excluding pre-existing 11.14 work).

### Important
1. `apps/assets/views/AssetDocumentKnowledge/_helpers.py:19-25` — `parse_pos_int` checks `.isascii()` and `.isdigit()` without a digit-length cap or 32-bit integer ceiling, so `?operational_asset=99999999999999999999999` (or >4300 digits) raises `OverflowError`/`ValueError` (HTTP 500) across every 11.16 list and CSV export view. Fix: Cap length to 10 digits and `val <= 2_147_483_647` (matching sibling `apps/assets/views/AssetAnalytics/_helpers.py:14-19`) or reuse `as_db_int` from `apps/core/crud.py:59`.
2. `apps/assets/models/AssetDocumentKnowledge/AssetOperatorCertifications.py:384` — `is_operator_certified` falls back to `getattr(operational_asset, "asset_category", None)`, which is always `None` because `scm.Asset` only defines `category = models.CharField(max_length=120, blank=True)` (`apps/scm/models/AssetManagement/Assets.py:143`), silently ignoring category-scoped certifications (`asset_category` set, `operational_asset=None`). Fix: When `asset_category is None` and `operational_asset.category` is non-blank, match `Q(operational_asset__isnull=True, asset_category__name__iexact=operational_asset.category) | Q(operational_asset__isnull=True, asset_category__code__iexact=operational_asset.category)`.
3. `apps/assets/views/AssetDocumentKnowledge/_helpers.py:28-35` — `apply_choice_filter` returns `qs.none()` for unrecognized GET choice parameters instead of ignoring invalid values (silently emptying the register on stale bookmarks or hand-edited URLs, contrary to NavERP's L11 rule in `apps/core/crud.py:163-173` and `apply_fk_filter` at lines 38-44; unsure vs Minor because sibling `apps/assets/views/AssetAnalytics/_helpers.py:22-29` uses the same clone — sweep with `rg -n "def apply_choice_filter" apps/assets/views/`). Fix: Return `qs` unchanged when `allowed_values is not None and val not in allowed_values`.
4. `apps/assets/views/AssetDocumentKnowledge/AssetDocuments.py:361-368` — `asset_document_edit` recalculates `revision_sequence` when `supersedes` changes without synchronizing `is_current_revision` as `asset_document_create` does at lines 307-312, leaving `is_current_revision=True` stale if a draft is edited to supersede an existing document (while line 311 marks brand-new unapproved standalone drafts `is_current_revision=True`, causing `detail.html:19-20` and `list.html:183` to badge drafts as Current). Fix: Sync `updated.is_current_revision = not bool(updated.supersedes_id)` in `asset_document_edit` (or keep `is_current_revision=False` on drafts until `asset_document_approve_release`).
5. `templates/assets/assetdocumentknowledge/asset_document/changes.html:21` — The Change Queue page's Export CSV link routes to `assets:asset_document_export_csv`, where `apps/assets/views/AssetDocumentKnowledge/AssetDocuments.py:165-168` exports all tenant `AssetDocument` rows instead of the change-control subset filtered in `asset_document_change_list` (`AssetDocuments.py:148-154`). Fix: Support `?scope=changes` in `asset_document_export_csv` to apply the `asset_document_change_list` filter and pass `&scope=changes` from `changes.html:21`.

### Minor
1. `apps/assets/management/commands/seed_assets.py:4241-4253` — Seeded Switchgear P&ID (`op2`, `electrical_diagram`) sets `supersedes=doc_rev_b` (the Centrifugal Chiller OEM Manual on `op1` seeded at lines 4206-4239), merging unrelated revision histories on detail view and causing approval of the Switchgear redline (`AssetDocuments.py:456-467`) to mark the Chiller Manual `superseded`. Fix: Leave `supersedes=None` and `revision_sequence=1` (e.g. `"Rev A"`) on the standalone Switchgear P&ID seed row, or create its own `Rev A` predecessor.
2. `apps/assets/models/AssetDocumentKnowledge/AssetDocuments.py:307-313` — `if size_bytes: self.file_size_bytes = size_bytes` leaves a stale non-zero `file_size_bytes` if an uploaded document is replaced with a 0-byte allowed file (`.txt`/`.csv`). Fix: Always assign `self.file_size_bytes = size_bytes` when refreshing `_committed` / checksum metadata on a readable uploaded file.
3. `apps/assets/models/AssetDocumentKnowledge/_validators.py:75` — `validate_supersedes_chain` walks ancestor rows via `type(instance).objects.filter(pk=next_id)` without constraining `tenant_id=instance.tenant_id` as defense-in-depth. Fix: Chain `.filter(tenant_id=instance.tenant_id)` when `getattr(instance, "tenant_id", None)` is present.
4. `apps/assets/views/AssetDocumentKnowledge/AssetDocuments.py:268,273` — Redundant `if hasattr(...)` fallbacks return `AssetDocument.objects.none()` for `operating_procedures` and `knowledge_articles` (same pattern in `AssetOperatingProcedures.py:140,145` returning `AssetOperatingProcedure.objects.none()`). Fix: Query the reverse manager directly without the mismatched `.none()` ternary.
5. `templates/assets/assetdocumentknowledge/asset_document/list.html:217-220` — List and change-queue (`changes.html:176-180`) tables render the Edit action whenever `{% if not item.is_locked %}` even when checked out by another user (unlike `detail.html:92`, which respects `can_edit`). Fix: Hide or disable the Edit icon when `item.checked_out_by_id` is set to another user and the current user is not a tenant admin.

### Done well
- Strict multi-tenant isolation and security hardening across all 4 models, forms, and download/CSV paths.

### Routing / Notes for Subsequent Passes
- `performance-reviewer`: KPI `.count()` aggregation in list views; iterative `supersedes`/`superseded_by` walks (up to 25 hops per direction).
- `security-reviewer`: Verify `access_classification` on `asset_document_download`; audit log action verbs across 11.16.
- `frontend-reviewer`: Checkout-aware Edit button on `list.html` / `changes.html`; UI/a11y parity across all 14 templates.

---

## Pass 2 — `explorer`

### Verdict
PASS WITH FINDINGS — `0` Critical, `1` Important, `4` Minor discrepancies found on `66c68399b9650309faea01195c456adbc9622c98...HEAD` for Module 11.16 (`AssetDocumentKnowledge`).

### Important
1. `apps/assets/models/AssetDocumentKnowledge/AssetOperatorCertifications.py:383-392` vs `apps/scm/models/AssetManagement/Assets.py:143` — `is_operator_certified()` reads `getattr(operational_asset, "asset_category", None)`, which is always `None` because `scm.Asset` only defines `category = models.CharField(max_length=120, blank=True)`, silently skipping category-scoped certifications. Fix: Resolve matching tenant `AssetCategory` (or query `asset_category__name__iexact` / `code__iexact`) when `asset_category is None` and `operational_asset.category` is non-blank.

### Minor
1. `templates/assets/assetdocumentknowledge/asset_document/changes.html:21` & `apps/assets/views/AssetDocumentKnowledge/AssetDocuments.py:148-154,165-168` — Change Queue "Export CSV" exports all tenant documents instead of the change-queue subset. Fix: Pass `&scope=changes` and apply the change-queue filter in `asset_document_export_csv`.
2. `apps/assets/management/commands/seed_assets.py:4206,4241-4253` — Seed data links Switchgear Electrical P&ID (`doc_rev_b`) via `supersedes` to the unrelated Centrifugal Chiller O&M Manual (`doc_rev_b` variable reuse / cross-asset lineage). Fix: Leave `supersedes=None` (`Rev A`, `revision_sequence=1`) or create a dedicated prior switchgear diagram.
3. `apps/assets/views/AssetDocumentKnowledge/AssetOperatingProcedures.py:110,135-146,270-286` vs `templates/assets/assetdocumentknowledge/asset_operating_procedure/print.html` — `asset_operating_procedure_print` omits `supersedes`/`safety_reviewer`/`maintenance_schedule` from `select_related` yet calls `_build_procedure_detail_context()`, running unused ancestor/descendant and reverse-relation queries when `print.html` renders only `{{ procedure }}`. Fix: Pass `{"procedure": proc}` directly with the needed `select_related`.
4. `apps/assets/views/AssetDocumentKnowledge/AssetDocuments.py:248-257,268,273` & `AssetOperatingProcedures.py:120-130,140,145` — (a) Unreachable `hasattr` ternary fallbacks use parent model `.none()` instead of target model; (b) linear `.first()` descendant walk misses branched draft revisions in `revision_history`. Fix: Query reverse managers directly and traverse descendants via bounded BFS queue (up to 25 nodes).

### Contract Checks Verified
- `manage.py check` clean (0 issues), `makemigrations assets --check --dry-run` clean.
- All 4 models, prefixes, constraints, `CHOICES`, `STATUS_CSS`, admin registrations, `__init__.py` re-exports, 50 routes, `LIVE_LINKS["11.16"]`, 167 `{% url %}` tags, 64 `reverse`/`redirect` calls, `overview.py` KPIs, AST helper calls, and filter dropdown keys verified.

---

## Pass 3 — `frontend-reviewer`

### Verdict
**CHANGES REQUESTED** — Module 11.16 (`AssetDocumentKnowledge`) templates have sound Django URL resolution, filter parameter handling, L9 pagination guards, L10 None-safety, 100% form-field coverage, and color-named badge compliance, but require fixes for an invented table CSS class (`.data-table` leaving all 12 tables unstyled), checkout-aware action gating & CSV export scope on the document lists, missing `@media print` rules on the SOP bench sheet, a vertical-stacked checkbox layout bug, icon-only button `aria-label`/`title` gaps, and physical LTR classes.

### Critical
1. `templates/assets/assetdocumentknowledge/` (12 occurrences: `asset_document/list.html:148`, `asset_document/changes.html:121`, `asset_document/detail.html:230`, `asset_operating_procedure/list.html:131`, `asset_operating_procedure/detail.html:188,223`, `asset_operating_procedure/print.html:55,90`, `asset_operator_certification/list.html:135`, `asset_knowledge_article/list.html:136`, `asset_knowledge_article/detail.html:183,213`) vs `static/css/theme.css:294-305` — Invented `.data-table` CSS class leaves all 12 Module 11.16 tables unstyled (`theme.css` defines `.table`, not `.data-table`). Fix: Replace `<table class="data-table">` with `<table class="table">` across all 12 occurrences (preserving `<div class="table-wrap">`).

### Important
1. `templates/assets/assetdocumentknowledge/asset_document/list.html:217-229` & `changes.html:171-182` — Checkout-aware Edit button gating missing on document repository & pending change queue (confirming `code-reviewer` routing note): guards Edit only with `{% if not item.is_locked %}`, omitting `item.checked_out_by_id` ownership / tenant-admin gating enforced by `asset_document_edit` and `detail.html`. Fix: Gate Edit link on `not item.checked_out_by_id or item.checked_out_by_id == request.user.id or request.user.is_superuser or request.user.is_tenant_admin` (plus add `aria-label`).
2. `templates/assets/assetdocumentknowledge/asset_document/changes.html:21` — Pending Change Queue CSV Export href drops `&scope=changes` expected by `AssetDocuments.py:165-168`, exporting the full repository instead of change-queue rows. Fix: Append `&scope=changes` to the export href in `changes.html:21`.
3. `templates/assets/assetdocumentknowledge/asset_operating_procedure/print.html:1-27` — SOP printable bench sheet extends `base.html` with zero `@media print` rules, printing `.sidebar`, `.topbar`, `.breadcrumb`, `.page-actions`, `.footer`, and `.customizer`. Fix: Add a `{% block extra_css %}` `@media print` block hiding chrome selectors and resetting `.main` margin/padding for print.
4. `templates/assets/assetdocumentknowledge/asset_operating_procedure/form.html:88-92` vs `static/css/theme.css:309` — Checkbox stacks vertically above label because `.form-group` sets `flex-direction: column` and Tailwind `.flex` does not override direction. Fix: Wrap checkbox + `<label class="form-label mb-0">` in `<div class="flex flex-row items-center gap-2">` inside `.form-group pt-6`.
5. `templates/assets/assetdocumentknowledge/asset_operating_procedure/list.html:117-119` & `asset_knowledge_article/list.html:122-124` — Icon-only filter `<button type="submit">` controls lack accessible text, `aria-label`, or `title`. Fix: Add `aria-label="Apply filters" title="Apply filters"` to both submit buttons.
6. `templates/assets/assetdocumentknowledge/{asset_document/list.html:159,207; changes.html:130,171; asset_operating_procedure/list.html:142,189; asset_operator_certification/list.html:145,196; asset_knowledge_article/list.html:147,190}` & `templates/assets/overview.html:236-263` — Physical LTR Tailwind classes break RTL layout (`text-right`, `border-l-4 border-l-*`, non-flipped `arrow-right`). Fix: Use `text-end`, `border-s-4 border-s-*`, and `rtl:rotate-180` on `arrow-right` icons.

### Minor
1. `templates/assets/assetdocumentknowledge/{asset_document/detail.html:121,135,144; asset_operating_procedure/detail.html:116; asset_operator_certification/detail.html:96}` vs `static/css/theme.css:266` — `.stat-card .stat-value` specificity `(0,2,0)` overrides `.text-base`/`.text-sm` `(0,1,0)`. Fix: Use `!text-base` / `!text-sm` for string/date/checksum KPI values.
2. `templates/assets/assetdocumentknowledge/{asset_operating_procedure/list.html:152; asset_operator_certification/list.html:156}` & `templates/assets/overview.html:239,246,253,260` — Bare `text-slate-400` lacks theme adaptation (`text-muted` adapts to both light/dark), and `overview.html` lacks `dark:group-hover:text-*-400`. Fix: Replace `text-slate-400` with `text-muted` and add `dark:group-hover:text-*-400` on `overview.html`.
3. `templates/assets/assetdocumentknowledge/*/form.html` (`asset_document/form.html:44,49,54,97,107`, `asset_operating_procedure/form.html:44,49,54,59,79,84`, `asset_operator_certification/form.html:44,54,59,141,151,166`, `asset_knowledge_article/form.html:44,49,54,59,69,74,88`) — Plain `*` required markers instead of `<span class="req">*</span>` styled in `theme.css:311`. Fix: Replace trailing ` *` with ` <span class="req">*</span>`.
4. Consistency & semantic polish: (a) `asset_document/list.html:183` uses `badge-info` for `Current Rev` instead of `badge-green` (`changes.html:148`, `detail.html:19,247`); (b) `asset_document/changes.html:171-182` omits the tenant-admin POST Delete form present on `list.html:220-227`; (c) `asset_operating_procedure/list.html:113` lacks `<label for="asop-filter-loto" class="sr-only">` matching `id="asop-filter-loto"`; (d) use `.table-actions`, `.form-actions`, `.th-actions` from `theme.css:305,321,418`.

### Done well
- Zero `{# #}` multi-line comment leaks, 100% color-named `theme.css` badges/stat-icons (`stat-icon.{blue,green,orange,purple,slate,red}`), L9 pagination guards + GET param preservation, L10 None-safe display, `|stringformat:"d"` FK filters, 100% `Meta.fields` + CSRF completeness, and nested template paths.

---

## Pass 4 — `performance-reviewer`

### Verdict
**Changes Required** — Module 11.16 uses pagination (`PAGE_SIZE = 15`), `F()` atomic counters, and single-query `.aggregate()` KPIs in `overview.py`, but has **chained `__str__` N+1 queries (L18)** across certification/SOP/RCA views and form dropdowns, **up-to-51-query iterative `supersedes` walks** (including an entirely wasted walk on the `print` view), **multi-query KPI `.count()` fan-out** on all four list views, **missing composite `Meta.indexes`** on hot `(tenant, ...)` orderings and filters, and **uncapped/unbuffered CSV exports** pulling large `TextField`/`JSONField` blobs.

### Critical
1. `apps/assets/views/AssetDocumentKnowledge/AssetOperatorCertifications.py:47-60,156,182-195`, `AssetOperatingProcedures.py:135-141`, `AssetKnowledgeArticles.py:183-198`, `apps/assets/forms/AssetDocumentKnowledge/AssetOperatorCertifications.py:109-117`, `AssetKnowledgeArticles.py:141-143` — Chained `__str__` N+1 queries (L18):
   - `_filter_certification_queryset`, `asset_operator_certification_detail`, and `_build_procedure_detail_context` (`certified_operators`) select `employee_profile` without `employee_profile__party` (`EmployeeProfile.__str__` accesses `self.party.name` -> +1 query/row). `asset_operator_certification_detail` also misses `hrm_certificate__employee__party` (+3 queries).
   - `asset_knowledge_article_detail` selects `incident_report` without `incident_report__asset` (`AssetIncidentReport.__str__` accesses `self.asset.number` -> +1 query).
   - `AssetOperatorCertificationForm.__init__` (`employee_profile`, `hrm_certificate`) and `AssetKnowledgeArticleForm.__init__` (`incident_report`) populate FK dropdowns without `.select_related(...)` (`+E + 2C` and `+K` queries on create/edit form renders).
   Fix: Add `employee_profile__party`, `hrm_certificate__employee__party`, and `incident_report__asset` to the respective view `select_related` lists, and chain `.select_related("party")` / `.select_related("employee__party")` / `.select_related("asset")` in the form `__init__` querysets.
2. `apps/assets/views/AssetDocumentKnowledge/AssetOperatingProcedures.py:106-158,270-291` & `AssetDocuments.py:235-258` vs `templates/assets/assetdocumentknowledge/asset_operating_procedure/print.html:1-127` — Wasted up-to-51-query revision-chain walk on `asset_operating_procedure_print` (calls `_build_procedure_detail_context` even though `print.html` never renders `revision_history`, `certified_operators`, or `linked_articles`) and unbatched iterative `supersedes`/`superseded_by_*` walks on both detail views pulling full `TextField`/`JSONField` rows. Fix: Pass `include_lineage=False` / lightweight context on `print` (1 query total); chain `"supersedes__supersedes__supersedes__supersedes"` in detail `select_related` and use `.only(...)` (or bounded `WITH RECURSIVE` / bounded BFS) for lineage rows.

### Important
1. `apps/assets/views/AssetDocumentKnowledge/{AssetDocuments.py:108-118, AssetOperatingProcedures.py:175-180, AssetOperatorCertifications.py:114-117, AssetKnowledgeArticles.py:100-114}` — Multi-query KPI `.count()` fan-out (4–6 separate `COUNT(*)`/`Sum` queries per list request, plus unused KPI counts calculated for `list.html` vs `changes.html`). Fix: Collapse each list view's KPI counts into a single `base_qs.aggregate(...)` using `Count("id", filter=Q(...))`.
2. `apps/assets/models/AssetDocumentKnowledge/{AssetDocuments.py:247,256-262, AssetOperatingProcedures.py:195,204-209, AssetOperatorCertifications.py:219-225, AssetKnowledgeArticles.py:232,241-247}` — Missing composite `Meta.indexes` on hot `(tenant, ...)` orderings and filter predicates:
   - `AssetDocument`: `(tenant, -updated_at)`, `(tenant, status, is_current_revision)`, `(tenant, access_classification)`, `(tenant, change_type)`, `(tenant, asset_category)`, `(tenant, org_unit)`.
   - `AssetOperatingProcedure`: `(tenant, -updated_at)`, `(tenant, status, next_review_date)`, `(tenant, operational_asset)`, `(tenant, asset_category)`, `(tenant, loto_required)`.
   - `AssetOperatorCertification`: `(tenant, proficiency_level)`, `(tenant, operational_asset)`, `(tenant, operating_procedure)`.
   - `AssetKnowledgeArticle`: `(tenant, -published_at, -updated_at)`, `(tenant, failure_mode)`.
   Fix: Add the composite `Meta.indexes` and generate the matching migration.
3. `apps/assets/views/AssetDocumentKnowledge/{AssetDocuments.py:165-206, AssetOperatingProcedures.py:198-237, AssetOperatorCertifications.py:135-172, AssetKnowledgeArticles.py:134-173}` — Uncapped/unbuffered CSV exports (`filtered_qs` lacks `[:10000].iterator(chunk_size=1000)`) and list/export querysets load heavy unused `TextField`/`JSONField` blobs and excessive `select_related` JOINs. Fix: Slice CSV exports `[:10000].iterator(chunk_size=1000)` with minimal `select_related`/`only(...)`; `.defer(...)` heavy `TextField`/`JSONField` bodies on list views and split list vs detail `select_related`.
4. `apps/assets/views/AssetDocumentKnowledge/AssetOperatorCertifications.py:470-497` — `asset_operator_certification_refresh_alerts` issues per-row `UPDATE` queries (`cert.sync_expiry_status(save=True)`) inside a loop plus a lazy FK lookup via `str(first_changed)`. Fix: Call `cert.sync_expiry_status(save=False, as_of=today)` and persist with `AssetOperatorCertification.objects.bulk_update(changed_certs, ["status", "updated_at"])`.

### Minor
1. `apps/assets/management/commands/seed_assets.py:4153-4155` — `_seed_tenant_11_16` runs 3 queries to get first two `Asset` rows instead of `list(Asset.objects.filter(tenant=tenant).order_by("pk")[:2])` (1 query).
2. `apps/assets/views/AssetDocumentKnowledge/AssetKnowledgeArticles.py:397-403` — Redundant `article.refresh_from_db(fields=["helpful_votes"])` before audit logging and redirect. Fix: Remove the extra `refresh_from_db`.
3. `apps/assets/views/AssetDocumentKnowledge/AssetDocuments.py:124-127,156` — Unused filter queryset keys (`categories`, `org_units`) passed to `changes.html`. Fix: Omit unused keys when building `changes.html` context.

### Suggested tests
- Add `django_assert_max_num_queries` regression tests for certification list/detail/form, KB article detail/form, procedure print/detail, document list/change-queue/detail, and `refresh_alerts` `bulk_update`.

### Done well
- `overview.py` uses single-query `.aggregate()` KPIs; `is_operator_certified` evaluates in 1 `EXISTS` SQL query; `view_count`/`helpful_votes` use atomic `F()`; pagination applies before slice; `ModelAdmin` defines `list_select_related`; seeder wraps inserts in `transaction.atomic()`.

---

## Pass 5 — `qa-smoke-tester` (Report-Only Runtime Audit)

### Verdict
**FAIL (Report-Only Phase 4 Pass 5 QA Review)** — **155 PASS / 17 FAIL** across 172 runtime smoke checks (`manage.py check`, `makemigrations --check --dry-run`, `migrate`, and idempotent `seed_assets` x2 all green). Zero source files modified; throwaway script and synthetic tenant cleaned up.

### Critical
1. `apps/assets/views/AssetDocumentKnowledge/_helpers.py:19-25` (`parse_pos_int`) — **9 FAILs**: Passing `?operational_asset=<5000-digit integer>` raises `ValueError: Exceeds the limit (4300) for integer string conversion` (HTTP 500) across all 5 list views (`asset_document_list`, `asset_document_change_list`, `asset_operating_procedure_list`, `asset_operator_certification_list`, `asset_knowledge_article_list`) and all 4 CSV exports.

### Important
1. `apps/assets/models/AssetDocumentKnowledge/AssetOperatorCertifications.py:383-392` vs `apps/scm/models/AssetManagement/Assets.py:143` — **1 FAIL**: `is_operator_certified(tenant=..., user=..., operational_asset=scm_asset)` returns `False` for category-scoped certifications because `scm.Asset` defines `category` (`CharField`), not `asset_category`.
2. `templates/assets/assetdocumentknowledge/asset_document/changes.html:21` & `apps/assets/views/AssetDocumentKnowledge/AssetDocuments.py:148-154,165-168` — **2 FAILs**: Change Queue Export CSV lacks `?scope=changes` and `asset_document_export_csv` does not apply the change-queue filter even when `?scope=changes` is passed, exporting approved baseline docs (`ADOC-00020`).
3. `apps/assets/management/commands/seed_assets.py:4241-4254` (line 4252) — **2 FAILs**: `ADOC-00003` (Switchgear P&ID) sets `supersedes=doc_rev_b` (`ADOC-00002`, Chiller OEM Manual), merging unrelated revision histories on detail view.
4. `apps/assets/models/AssetDocumentKnowledge/AssetDocuments.py:299-313` (line 310) — **1 FAIL**: `sync_file_metadata()` retains stale `file_size_bytes` when replacing attachment with a 0-byte file (`if size_bytes:` is falsy for `0`).

### Minor
1. `templates/assets/assetdocumentknowledge/asset_document/list.html:217-220` & `changes.html:176-180` — **2 FAILs**: Edit button appears for another non-admin user (`iso_other`) on checked-out documents because templates check only `{% if not item.is_locked %}`.

### Runtime Checks Verified
- 120/120 cross-tenant IDOR checks returned HTTP 404; 15/15 non-admin RBAC POST checks returned HTTP 403; 15/15 superuser (`tenant=None`) GET/POST checks returned HTTP 200; all 4 attachment downloads enforced `nosniff` + `attachment` + 404 on missing file + rejected `.svg` and `>20MB`; page-2 pagination + CSV formula injection neutralization passed.

---

## Pass 6 — `security-reviewer`

### Verdict
**CONDITIONAL PASS (3 Important, 5 Minor findings — 0 Critical).** Multi-tenant isolation, CSRF protection, XSS escaping, CSV formula neutralization, and file upload/download hardening are solid, but an intra-tenant privilege escalation on certification edits, unenforced `access_classification`, and unbounded `parse_pos_int` must be resolved.

### Important
1. `apps/assets/views/AssetDocumentKnowledge/AssetOperatorCertifications.py:249-287`, `apps/assets/models/AssetDocumentKnowledge/AssetOperatorCertifications.py:68,356-402` — Non-admin users can edit `active`/`expiring_soon` certifications (`@login_required` without `@tenant_admin_required`) and alter operator/qualification/expiry fields to self-grant or extend qualifications. Fix: Gate `asset_operator_certification_edit` with `@tenant_admin_required` and mirror in list/detail Edit UI.
2. `apps/assets/models/AssetDocumentKnowledge/AssetDocuments.py:37-42`, `apps/assets/views/AssetDocumentKnowledge/AssetDocuments.py:133,146,165,210,333,407,415,521,555,585`, `apps/assets/forms/AssetDocumentKnowledge/{AssetDocuments.py:34, AssetOperatingProcedures.py:42, AssetKnowledgeArticles.py:53}` — `AssetDocument.access_classification` (`restricted_eng`, `confidential`) is unenforced across views, CSV exports, downloads, and FK dropdowns. Fix: Enforce `readable_asset_document_q(user)` (`public_floor`, `internal_tech`, or `owner`/`reviewer`/`is_tenant_admin_user`) across all `AssetDocument` queries and form dropdowns.
3. `apps/assets/views/AssetDocumentKnowledge/_helpers.py:19-25` — Unbounded `parse_pos_int` triggers HTTP 500 (`OverflowError`/`ValueError`) on oversized integer FK query params. Fix: Cap digit length `<= 10` and `0 < val <= 2_147_483_647`.

### Minor
1. `AssetDocuments.py:298`, `AssetOperatingProcedures.py:295`, `AssetOperatorCertifications.py:218,470`, `AssetKnowledgeArticles.py:221` — Missing `request.tenant is None` redirect guard on create views and `refresh_alerts`.
2. `apps/assets/views/AssetDocumentKnowledge/AssetDocuments.py:415-491`, `list.html:217`, `changes.html:176` — `submit_review` and `approve_release` ignore active `checked_out_by` locks held by another user.
3. `apps/assets/forms/AssetDocumentKnowledge/{AssetDocuments.py:58, AssetOperatingProcedures.py:61, AssetOperatorCertifications.py:66, AssetKnowledgeArticles.py:73}` — Default `ClearableFileInput` exposes raw `MEDIA_URL` links on edit forms. Fix: Use `forms.FileInput(attrs={"class": "form-input"})`.
4. `apps/assets/models/AssetDocumentKnowledge/_validators.py:75` — `validate_supersedes_chain` omits `.filter(tenant_id=instance.tenant_id)`.
5. `apps/assets/admin.py:734-844` — 11.16 `ModelAdmin` classes omit `has_change_permission`/`has_delete_permission` `is_locked` guards.

---

## Consolidated Fix Checklist (Sorted Critical -> Important -> Minor)

> Instructions for `code-fixer`: Fix every `[ ]` item below in strict ID order (`C1` -> `C4`, then `I1` -> `I15`, then `M1` -> `M13`). Commit **one file per commit** (`git add '<path>'; git commit --only '<path>' -m '<msg>'`), mark each item `[x] fixed — <commit/note>` or `[~] skipped — <reason>`, run `makemigrations` + `migrate` after model index edits, verify `manage.py check`, `makemigrations --check --dry-run`, and `seed_assets` x2 cleanly, then commit the updated checklist itself.

### Critical
- [x] **C1** *(Pass 1 I1, Pass 5 C1, Pass 6 I3)* — `apps/assets/views/AssetDocumentKnowledge/_helpers.py:19-25`: Bound `parse_pos_int` to `.isascii()`, `.isdigit()`, `len(raw) <= 10`, and `0 < val <= 2_147_483_647` so oversized ints return `None` instead of HTTP 500 across all 9 list/export endpoints. *(fixed — `f9ad1fd2`)*
- [x] **C2** *(Pass 3 C1)* — `templates/assets/assetdocumentknowledge/` (12 occurrences across 9 templates): Replace invented `<table class="data-table">` with `<table class="table">`. *(fixed — `d007b15a`, `d5b237ed`, `0565dde1`, `d6b0a17b`, `d97ffe56`, `6ec9a5a7`, `4154639f`, `24d60f30`, `8e0ddba9`)*
- [x] **C3** *(Pass 4 C1)* — Eliminate chained `__str__` N+1 queries (L18): add `"employee_profile__party"` to `_filter_certification_queryset`, `_build_procedure_detail_context` (`certified_operators`), and `asset_operator_certification_detail`; add `"hrm_certificate__employee__party"` to `asset_operator_certification_detail`; add `"incident_report__asset"` to `asset_knowledge_article_detail`; chain `.select_related("party")` / `.select_related("employee__party")` in `AssetOperatorCertificationForm.__init__` and `.select_related("asset")` in `AssetKnowledgeArticleForm.__init__`. *(fixed — `98713af4`, `241cecd4`, `c1fc62a5`, `34786d78`, `334507a9`)*
- [x] **C4** *(Pass 2 M3/M4b, Pass 4 C2)* — `AssetOperatingProcedures.py` & `AssetDocuments.py`: On `asset_operating_procedure_print`, pass lightweight context skipping lineage, `certified_operators`, and `linked_articles` queries; on `asset_document_detail` and `_build_procedure_detail_context`, chain multi-hop `supersedes__supersedes__supersedes__supersedes` `select_related` and walk deeper ancestors + bounded BFS descendants (up to 25 nodes) with `.only(...)` lineage columns. *(fixed — `f6ed37a8`, `022833bb`)*

### Important
- [x] **I1** *(Pass 6 I1)* — `apps/assets/views/AssetDocumentKnowledge/AssetOperatorCertifications.py` + `asset_operator_certification/{list.html, detail.html}`: Gate `asset_operator_certification_edit` with `@tenant_admin_required` and gate Edit buttons on `can_manage` / admin permission in both templates. *(fixed — `e35a39d5`, `42cf30cc`, `25501a38`)*
- [x] **I2** *(Pass 6 I2)* — `apps/assets/models/AssetDocumentKnowledge/_validators.py`, `apps/assets/views/AssetDocumentKnowledge/{_helpers.py, AssetDocuments.py, AssetOperatingProcedures.py, AssetKnowledgeArticles.py}`, `apps/assets/forms/AssetDocumentKnowledge/{AssetDocuments.py, AssetOperatingProcedures.py, AssetKnowledgeArticles.py}`, SOP/KB detail templates: Enforce `readable_asset_document_q(user)` / `is_asset_document_readable(user, doc)` across all `AssetDocument` queries, downloads, workflow verbs, form dropdowns (`user=request.user`), and linked-doc UI links. *(fixed — `5d305474`, `dc95aa3e`, `7faa6acc`, `cc6456d9`, `6130e9ac`, `e66246a8`, `e804babd`, `38fc4900`, `c2e76519`, `baf2e174`)*
- [x] **I3** *(Pass 1 I2, Pass 2 I1, Pass 5 I1)* — `apps/assets/models/AssetDocumentKnowledge/AssetOperatorCertifications.py`: Fix `is_operator_certified()` category matching for `scm.Asset` (`category` CharField) by matching `Q(operational_asset__isnull=True, asset_category__name__iexact=cat_name) | Q(operational_asset__isnull=True, asset_category__code__iexact=cat_name)`. *(fixed — `a31091e1`)*
- [x] **I4** *(Pass 1 I3)* — `apps/assets/views/AssetDocumentKnowledge/_helpers.py`: Update `apply_choice_filter` to ignore unrecognized GET choice params (return `qs` unchanged) instead of returning `qs.none()`. *(fixed — `0e9fa24a`)*
- [x] **I5** *(Pass 1 I4)* — `apps/assets/views/AssetDocumentKnowledge/AssetDocuments.py`: Synchronize `updated.is_current_revision = not bool(updated.supersedes_id)` in `asset_document_edit` whenever `supersedes` changes. *(fixed — `e247cdf3`)*
- [x] **I6** *(Pass 1 I5, Pass 2 M1, Pass 3 I2, Pass 5 I2)* — `templates/assets/assetdocumentknowledge/asset_document/changes.html` & `apps/assets/views/AssetDocumentKnowledge/AssetDocuments.py`: Append `&scope=changes` on Change Queue Export CSV link and apply `_CHANGE_QUEUE_Q` filter in `asset_document_export_csv` when `request.GET.get("scope") == "changes"`. *(fixed — `a653fb2c`, `e5b22126`)*
- [x] **I7** *(Pass 1 M5, Pass 3 I1, Pass 5 M1, Pass 6 M2)* — `templates/assets/assetdocumentknowledge/asset_document/{list.html, changes.html}` & `apps/assets/views/AssetDocumentKnowledge/AssetDocuments.py`: Gate table Edit buttons on `not item.is_locked` + checkout ownership and `aria-label`; block `submit_review` and `approve_release` when checked out by another user (with explicit checkout-clear on admin override). *(fixed — `2b6ba316`, `a48ed908`, `3cb79765`)*
- [x] **I8** *(Pass 3 I3)* — `templates/assets/assetdocumentknowledge/asset_operating_procedure/print.html`: Add `{% block extra_css %}` `@media print` rules hiding chrome and resetting `.main` margins/padding. *(fixed — `177f738c`)*
- [x] **I9** *(Pass 3 I4)* — `templates/assets/assetdocumentknowledge/asset_operating_procedure/form.html`: Fix horizontal checkbox alignment using `<div class="form-group pt-6"><div class="flex flex-row items-center gap-2">...`. *(fixed — `12d7539b`)*
- [x] **I10** *(Pass 3 I5)* — `templates/assets/assetdocumentknowledge/asset_operating_procedure/list.html` & `asset_knowledge_article/list.html`: Add `aria-label="Apply filters" title="Apply filters"` to icon-only filter submit buttons. *(fixed — `0fd93691`, `be41b6b5`)*
- [x] **I11** *(Pass 3 I6)* — Replace physical LTR classes with RTL-safe `text-end`, `border-s-4 border-s-*`, and `rtl:rotate-180` across the 5 list/queue templates and `templates/assets/overview.html`. *(fixed — `6d1f86a0`, `edc91e49`, `cce07ed3`, `1cc26a35`, `42a7bb50`, `95f9f475`)*
- [x] **I12** *(Pass 4 I1)* — `apps/assets/views/AssetDocumentKnowledge/{AssetDocuments.py, AssetOperatingProcedures.py, AssetOperatorCertifications.py, AssetKnowledgeArticles.py}`: Collapse multi-query `.count()`/`Sum` KPI computations into single `base_qs.aggregate(...)` calls per list view. *(fixed — `e2a16bca`, `cb5496dc`, `85dcc792`, `2a7b30f8`)*
- [x] **I13** *(Pass 4 I2)* — `apps/assets/models/AssetDocumentKnowledge/{AssetDocuments.py, AssetOperatingProcedures.py, AssetOperatorCertifications.py, AssetKnowledgeArticles.py}` + migration `0023_assetdocument_idx_adoc_ten_upd_and_more.py`: Add composite `Meta.indexes` (`<= 30` chars) and generate/apply migration `0023`. *(fixed — `969dcfe4`, `b67e4b1b`, `e38ef587`, `2d8a9e4c`, `a73990e7`)*
- [x] **I14** *(Pass 4 I3)* — `apps/assets/views/AssetDocumentKnowledge/{AssetDocuments.py, AssetOperatingProcedures.py, AssetOperatorCertifications.py, AssetKnowledgeArticles.py}`: Use `filtered_qs[:10000].iterator(chunk_size=1000)` with minimal `select_related`/`only(...)` on all 4 CSV exports; `.defer(...)` blobs on list views and split list vs detail `select_related`. *(fixed — `221959a0`, `c6cbd7eb`, `a6a86e40`, `589d8ff1`)*
- [x] **I15** *(Pass 4 I4)* — `apps/assets/views/AssetDocumentKnowledge/AssetOperatorCertifications.py`: Replace per-row `.sync_expiry_status(save=True)` loop in `asset_operator_certification_refresh_alerts` with `sync_expiry_status(save=False, as_of=today)` + single `bulk_update(changed_certs, ["status", "updated_at"])`. *(fixed — `9ad918d0`)*

### Minor
- [x] **M1** *(Pass 1 M1, Pass 2 M2, Pass 5 I3)* — `apps/assets/management/commands/seed_assets.py`: Unlink Switchgear P&ID (`op2`) from Chiller Manual (`doc_rev_b`); set `supersedes=None`, `revision_sequence=1`, `revision_label="Rev A"`. *(fixed — `256cc019`)*
- [x] **M2** *(Pass 1 M2, Pass 5 I4)* — `apps/assets/models/AssetDocumentKnowledge/AssetDocuments.py`: Always assign `self.file_size_bytes = size_bytes` in `sync_file_metadata()` (including `0`-byte files). *(fixed — `af3bad7d`)*
- [x] **M3** *(Pass 1 M3, Pass 6 M4)* — `apps/assets/models/AssetDocumentKnowledge/_validators.py`: Add `.filter(tenant_id=instance.tenant_id)` inside `validate_supersedes_chain` when `instance.tenant_id` is present. *(fixed — `01850e80`)*
- [x] **M4** *(Pass 1 M4, Pass 2 M4a)* — `apps/assets/views/AssetDocumentKnowledge/{AssetDocuments.py, AssetOperatingProcedures.py}`: Remove dead `if hasattr(...) else <WrongModel>.objects.none()` ternary fallbacks. *(fixed — `c70ac538`, `e0941916`)*
- [x] **M5** *(Pass 3 M1)* — `templates/assets/assetdocumentknowledge/{asset_document/detail.html, asset_operating_procedure/detail.html, asset_operator_certification/detail.html}`: Change `.text-base`/`.text-sm` inside `.stat-card .stat-value` to `!text-base`/`!text-sm`. *(fixed — `ca5d28f7`, `6fbffa96`, `6e50d8b0`)*
- [x] **M6** *(Pass 3 M2)* — Replace bare `text-slate-400` with `text-muted` on `asset_operating_procedure/list.html` and `asset_operator_certification/list.html`, and add `dark:group-hover:text-*-400` on `templates/assets/overview.html`. *(fixed — `1fc70c6f`, `d206e583`, `0992f33b`)*
- [x] **M7** *(Pass 3 M3)* — Replace plain trailing ` *` required markers with ` <span class="req">*</span>` across all 4 `form.html` templates. *(fixed — `4b3e39a1`, `ccf2733b`, `3d51917b`, `be002f4a`)*
- [x] **M8** *(Pass 3 M4)* — Polish consistency: `asset_document/list.html` uses `badge-green` for `Current Rev`; `asset_document/changes.html` adds admin-gated POST Delete action; `asset_operating_procedure/list.html` adds `<label for="asop-filter-loto" class="sr-only">`; adopted `.table-actions`/`.form-actions`/`.th-actions !text-end` across lists and forms. *(fixed — `63efe4ad`, `f3929a40`, `53a757ed`, `fba3bb27`, `e8d65085`, `ca864aee`, `66bb83a4`, `7ef32115`, `6373f462`)*
- [x] **M9** *(Pass 4 M1)* — `apps/assets/management/commands/seed_assets.py`: Fetch `op1`/`op2` via `list(Asset.objects.filter(tenant=tenant).order_by("pk")[:2])` (1 query instead of 3). *(fixed — `351073e5`)*
- [x] **M10** *(Pass 4 M2)* — `apps/assets/views/AssetDocumentKnowledge/AssetKnowledgeArticles.py`: Remove redundant `article.refresh_from_db(fields=["helpful_votes"])` in `asset_knowledge_article_mark_helpful`. *(fixed — `7da4e04f`)*
- [x] **M11** *(Pass 4 M3)* — `apps/assets/views/AssetDocumentKnowledge/AssetDocuments.py`: Omit unused `categories` / `org_units` keys when building `changes.html` context (`include_repo_filters=False`). *(fixed — `8f13e578`)*
- [x] **M12** *(Pass 6 M1)* — Add `if request.tenant is None: messages.error(...); return redirect(...)` guard to all 4 create views (`AssetDocuments.py`, `AssetOperatingProcedures.py`, `AssetOperatorCertifications.py`, `AssetKnowledgeArticles.py`) and `asset_operator_certification_refresh_alerts`. *(fixed — `0a65e118`, `c76bb7a8`, `4e3f8b69`, `25b926af`)*
- [x] **M13** *(Pass 6 M3, M5)* — Use `forms.FileInput(attrs={"class": "form-input"})` on file fields in all 4 forms (`AssetDocuments.py`, `AssetOperatingProcedures.py`, `AssetOperatorCertifications.py`, `AssetKnowledgeArticles.py`); add `has_change_permission` and `has_delete_permission` `is_locked` (and `"revoked"` for certs) guards to the 4 11.16 `ModelAdmin` classes in `apps/assets/admin.py`. *(fixed — `1dddf192`, `32f9b500`, `2d1e9780`, `12e7e91d`, `6ae110ae`)*

### Fixer Notes
- **Clone-family observation (I4):** Sibling `apps/assets/views/AssetAnalytics/_helpers.py:22-29` (`apply_choice_filter`) still returns `qs.none()` on unrecognized `allowed_values`; left untouched to keep this fix pass scoped to 11.16.
- **Verification run (2026-11-12):** `manage.py check` (0 issues), `manage.py makemigrations --check --dry-run` (`No changes detected`), `manage.py seed_assets` x2 idempotency pass, and Django Client runtime verification across all 11.16 views, permissions, isolation rules, query counts, and form widgets passed cleanly.
