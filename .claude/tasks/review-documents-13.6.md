# Review Findings — Sub-module 13.6: Search & Discovery (`apps/documents/`)

**Review Range**: `6bfd379460b8cd647e9b660725aae976be71bd62...HEAD`
**Target App**: `apps/documents/`
**Reviewers Executed Serially**: `code-reviewer` -> `explorer` -> `frontend-reviewer` -> `performance-reviewer` -> `qa-smoke-tester` -> `security-reviewer`

---

## Critical Findings

- [ ] **C1**: Active session token exposure in search query log telemetry and detail template.
  - **Location**: `templates/documents/search_discovery/document_search_query_log/detail.html:161` & `apps/documents/views/SearchDiscovery/SearchHub.py:173`
  - **Why it is exploitable**: Active Django session keys (`request.session.session_key`) are recorded in telemetry logs and rendered unmasked in cleartext in the query log detail template, allowing users to harvest live session credentials.
  - **Fix**: Redact or remove session key in detail template and do not log active raw session keys in cleartext.

- [ ] **C2**: Insecure Direct Object Reference (IDOR) & visibility bypass in Saved Search detail and run.
  - **Location**: `apps/documents/views/SearchDiscovery/DocumentSavedSearches.py:77,170`
  - **Why it is exploitable**: `document_saved_search_detail` and `document_saved_search_run` retrieve saved searches without enforcing visibility rules, allowing any user in the tenant to inspect private saved queries and execute them, altering run counters and telemetry.
  - **Fix**: Enforce visibility authorization (`owner == request.user`, tenant admin/superuser, `public`, or matching `shared_department`). Return `HttpResponseForbidden` if unauthorized.

- [ ] **C3**: Unhandled `IntegrityError` (500) on duplicate Search Alert subscription.
  - **Location**: `apps/documents/forms/SearchDiscovery/DocumentSearchAlerts.py:38` & `apps/documents/views/SearchDiscovery/DocumentSearchAlerts.py:104`
  - **Why it is exploitable**: Unique constraint `(tenant, saved_search, subscriber)` is enforced in DB, but duplicate submissions bypass form validation and trigger an unhandled 500 server crash on `save()`.
  - **Fix**: Validate against duplicate subscription in `DocumentSearchAlertForm.clean()` with a clean form validation error.

---

## Important Findings

- [ ] **I1**: Missing Tenant Admin authorization on organization-wide search telemetry & analytics.
  - **Location**: `apps/documents/views/SearchDiscovery/DocumentSearchQueryLogs.py:15,60,91`
  - **Why it is exploitable**: Standard non-admin employees can inspect organization-wide search histories, user research queries, IP metadata, and search analytics.
  - **Fix**: Decorate `document_search_query_log_list`, `document_search_query_log_detail`, and `document_search_analytics` with `@tenant_admin_required`.

- [ ] **I2**: Missing object-level authorization on Search Synonym modification and deletion.
  - **Location**: `apps/documents/views/SearchDiscovery/DocumentSearchSynonyms.py:103,128`
  - **Why it is exploitable**: `document_search_synonym_edit` and `document_search_synonym_delete` do not verify whether `search_synonym.created_by == request.user` or if the user is a tenant admin, allowing any user to alter dictionary rules.
  - **Fix**: Check `search_synonym.created_by == request.user` or `request.user.is_tenant_admin` before permitting edits or deletions.

- [ ] **I3**: Information disclosure in Search Alert form dropdown.
  - **Location**: `apps/documents/forms/SearchDiscovery/DocumentSearchAlerts.py:32`
  - **Why it is exploitable**: `DocumentSearchAlertForm.__init__` filters `saved_search` only by `tenant` and `is_active=True`, exposing other users' private saved searches in the form dropdown.
  - **Fix**: Pass `user=request.user` into form and filter dropdown by accessible saved searches.

- [ ] **I4**: Cross-Site Scripting (XSS) via unescaped variables in inline JavaScript confirm handlers.
  - **Location**: `templates/documents/search_discovery/document_saved_search/list.html:192`, `document_search_synonym/detail.html:33`, and `document_search_synonym/list.html:153`
  - **Why it is exploitable**: User-controlled entity attributes (`item.name`, `search_synonym.term`, and `item.term`) are rendered directly inside JS string literals in inline `onsubmit="return confirm('...')"`.
  - **Fix**: Apply the Django `|escapejs` filter to all variables inside inline JS confirm dialogs.

- [ ] **I5**: Open redirect via unvalidated `HTTP_REFERER` in toggle views.
  - **Location**: `apps/documents/views/SearchDiscovery/DocumentSavedSearches.py:206` & `apps/documents/views/SearchDiscovery/DocumentSearchAlerts.py:185`
  - **Why it is exploitable**: `document_saved_search_toggle_pin` and `document_search_alert_toggle_active` redirect directly to `request.META.get("HTTP_REFERER")` without validating host or scheme.
  - **Fix**: Validate referer with `url_has_allowed_host_and_scheme(referer, allowed_hosts={request.get_host()})`.

- [ ] **I6**: Synchronous single-row `save()` inside synonym expansion loop on read path.
  - **Location**: `apps/documents/views/SearchDiscovery/SearchHub.py:76`
  - **Why it is problematic**: Executes N synchronous DB updates within a GET request loop, causing write latency on read requests.
  - **Fix**: Collect matched synonym IDs and execute a single atomic bulk update: `DocumentSearchSynonym.objects.filter(id__in=matched_syn_ids).update(hit_count=models.F("hit_count") + 1)`.

- [ ] **I7**: Unidirectional synonym expansion logic bug.
  - **Location**: `apps/documents/views/SearchDiscovery/SearchHub.py:71`
  - **Why it is problematic**: Unidirectional synonyms expand bidirectionally because condition tests `qw in syn_terms` for all terms instead of checking `qw == syn.term.lower().strip()`.
  - **Fix**: For unidirectional synonyms (`is_bidirectional=False`), only expand when the query word matches the canonical term.

- [ ] **I8**: Inflated facet counts & Cartesian join multiplicity on `base_facets_qs`.
  - **Location**: `apps/documents/views/SearchDiscovery/SearchHub.py:188-190`
  - **Why it is problematic**: Joining to `DocumentVersion` without `distinct=True` counts multiple version rows per document.
  - **Fix**: Add `distinct=True` to `Count("id", distinct=True)`.

- [ ] **I9**: Redundant KPI aggregate queries in `document_search_analytics`.
  - **Location**: `apps/documents/views/SearchDiscovery/DocumentSearchQueryLogs.py:94-103`
  - **Why it is problematic**: Issues 3 separate queries against the same table.
  - **Fix**: Combine into a single conditional aggregate query (`total=Count("id")`, `zero_results=Count(...)`, `avg_latency=Avg(...)`).

- [ ] **I10**: Unused `authors` queryset queried on every `search_hub` load.
  - **Location**: `apps/documents/views/SearchDiscovery/SearchHub.py:208,252`
  - **Why it is problematic**: Loads all users from DB on every search request even though author dropdown is not rendered.
  - **Fix**: Remove `authors` query and context entry.

- [ ] **I11**: Filter parameter mismatch on Saved Search run.
  - **Location**: `apps/documents/views/SearchDiscovery/SearchHub.py:103`
  - **Why it is problematic**: Saved searches store `"document_type"`, but `SearchHub.py` checks only `request.GET.get("doc_type")`.
  - **Fix**: Check both `request.GET.get("doc_type") or request.GET.get("document_type")`.

- [ ] **I12**: Missing composite indexes on hot tenant query paths.
  - **Location**: `apps/documents/models/SearchDiscovery/DocumentSearchQueryLogs.py:70-79`, `DocumentSearchAlerts.py:98-103`, `DocumentSearchSynonyms.py:66-71`
  - **Why it is problematic**: Unindexed table scans on frequent queries (`(tenant, user, -created_at)`, `(tenant, subscriber, -created_at)`, `(tenant, is_active, term)`).
  - **Fix**: Add composite indexes to model `Meta.indexes`.

- [ ] **I13**: `--flush` in `seed_documents.py` omits 13.6 models.
  - **Location**: `apps/documents/management/commands/seed_documents.py:51`
  - **Why it is problematic**: Leaves orphaned data when running `seed_documents --flush`.
  - **Fix**: Include `DocumentSearchAlert`, `DocumentSavedSearch`, `DocumentSearchSynonym`, and `DocumentSearchQueryLog` in flush deletion list.

- [ ] **I14**: Facet parameter dropping across refinements, folder selector, and CSV export.
  - **Location**: `templates/documents/search_discovery/search_hub.html:158,172,186,201,233`
  - **Why it is problematic**: Facet links and export link do not preserve `folder` and `sort_by`.
  - **Fix**: Preserve `folder` and `sort_by` in facet refinement links and export link.

- [ ] **I15**: Missing accessible form labels on omni search input and folder filter select.
  - **Location**: `templates/documents/search_discovery/search_hub.html:38,198`
  - **Why it is problematic**: Screen readers cannot identify inputs.
  - **Fix**: Add accessible `<label class="sr-only">` or `aria-label`.

- [ ] **I16**: Non-standard `stat-icon red` used in query log templates.
  - **Location**: `templates/documents/search_discovery/document_search_query_log/{analytics,list}.html:42`
  - **Why it is problematic**: Violates theme.css palette rule L33.
  - **Fix**: Replace with standard `stat-icon orange`.

---

## Minor Findings

- [ ] **M1**: View context variable naming contract discrepancy in Search Hub.
  - **Location**: `apps/documents/views/SearchDiscovery/SearchHub.py:246`
  - **Fix**: Provide both `results_count` (contract name) alongside `total_count`, and `nlp_intent_chips` alongside `intent_chips`.

- [ ] **M2**: Hardcoded redirect path in `document_saved_search_run`.
  - **Location**: `apps/documents/views/SearchDiscovery/DocumentSavedSearches.py:189`
  - **Fix**: Replace `f"/documents/search/?{encoded}"` with `f"{reverse('documents:search_hub')}?{encoded}"`.

- [ ] **M3**: Form does not consume `request.GET.get("query_text")` passed from Search Hub.
  - **Location**: `apps/documents/views/SearchDiscovery/DocumentSavedSearches.py:113`
  - **Fix**: Initialize form with `initial={"query_text": request.GET.get("query_text", "")}`.

- [ ] **M4**: Form does not consume `request.GET.get("term")` passed from Analytics.
  - **Location**: `apps/documents/views/SearchDiscovery/DocumentSearchSynonyms.py:90`
  - **Fix**: Initialize form with `initial={"term": request.GET.get("term", "")}`.

- [ ] **M5**: Validate `isinstance` for parsed JSON in model helper methods.
  - **Location**: `apps/documents/models/SearchDiscovery/DocumentSavedSearches.py:122` & `DocumentSearchAlerts.py:120`
  - **Fix**: Add `isinstance(data, dict)` check before `.get()`.

- [ ] **M6**: Missing `list_select_related` in Django Admin definitions for 13.6 models.
  - **Location**: `apps/documents/admin.py:192-222`
  - **Fix**: Add `list_select_related` on ModelAdmin classes to eliminate N+1 queries.

- [ ] **M7**: Redundant queries in `search_export_csv` audit log.
  - **Location**: `apps/documents/views/SearchDiscovery/SearchHub.py:319-331`
  - **Fix**: Use in-memory first document from sliced list instead of issuing `qs.exists()` and `qs.first()`.

- [ ] **M8**: Separate count queries in `document_search_query_log_list`.
  - **Location**: `apps/documents/views/SearchDiscovery/DocumentSearchQueryLogs.py:38-39`
  - **Fix**: Combine `total_count` and `zero_result_count` into one conditional aggregate query.

- [ ] **M9**: Dark mode styling on omni search input.
  - **Location**: `templates/documents/search_discovery/search_hub.html:44`
  - **Fix**: Add `dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100`.

- [ ] **M10**: Icon-only buttons missing `aria-label`.
  - **Location**: `templates/documents/search_discovery/*/{list,search_hub}.html`
  - **Fix**: Add explicit `aria-label` alongside `title`.

- [ ] **M11**: Add inline `document_search_synonym_toggle_active` action and route.
  - **Location**: `apps/documents/views/SearchDiscovery/DocumentSearchSynonyms.py` & `apps/documents/urls/SearchDiscovery/DocumentSearchSynonyms.py`
  - **Fix**: Add POST-only toggle view and URL route for 1-click status change.
