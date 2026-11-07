# Consolidated Review Findings: Sub-module 10.15 Natural Language & Conversational BI

**Scope**: Changeset `BASE (ff2b961f0e086fc09a9b9f15d9bb168ae8976b9d) ... HEAD`  
**Reviewers Executed**: 6 of 6 (Code Reviewer, Explorer, Frontend Reviewer, Performance Reviewer, QA Smoke Tester, Security Reviewer)  
**Status**: Deduplicated, prioritized, and ready for Phase 5 (`code-fixer`)

---

## Summary of Findings

| Severity | Total | Status |
|----------|-------|--------|
| Critical | 0     | 0 open |
| Important| 16    | 16 open|
| Minor    | 11    | 11 open|
| **Total**| **27**| **27 open** |

---

## Critical Findings
*None.* (Zero 500 server crashes, zero unhandled 404s on valid tenant data, and 100% tenant boundary isolation verified).

---

## Important Findings

- [ ] **I1** — `apps/bi/views/ConversationalBi/SearchDiscoveryIndexes.py:192` — **Decimal NaN/Infinity Input Guard (Lesson L35)**: `search_discovery_index_reweight` parses numeric input with `Decimal(weight_val)` without an `is_finite()` guard. Non-finite values (`"NaN"`, `"Infinity"`) crash DB persistence or comparison.  
  *Fix*: Immediately following `new_weight = Decimal(weight_val)`, add:
  ```python
  if not new_weight.is_finite():
      raise InvalidOperation("Non-finite Decimal rejected")
  ```

- [ ] **I2** — `templates/bi/conversational_bi/narrative_explanation/list.html:102, 114, 226, 229` & `apps/bi/views/ConversationalBi/NarrativeExplanations.py:55` — **Filter Parameter Mismatch**: The template dropdown submits `name="artifact"` and pagination links propagate `&artifact=...`, but `narrative_explanation_list` view reads `request.GET.get("artifact_type")`. Artifact filtering is silently ignored.  
  *Fix*: Align template dropdown to `name="artifact_type"` (and `request.GET.artifact_type`), and update view to accept both `request.GET.get("artifact_type") or request.GET.get("artifact", "")`.

- [ ] **I3** — `templates/bi/conversational_bi/search_discovery_index/detail.html:180` — **Referenced Model Attribute Access on ReportDefinition**: Template renders `{{ index.report.title }}`, but `ReportDefinition` model defines `name` (not `title`), rendering the report link silently blank.  
  *Fix*: Replace `{{ index.report.title }}` with `{{ index.report.name }}`.

- [ ] **I4** — `templates/bi/conversational_bi/search_discovery_index/detail.html:192` — **Referenced Model Attribute Access on BusinessGlossaryTerm**: Template renders `{{ index.glossary_term.term }}`, but `BusinessGlossaryTerm` model defines `name` (not `term`), rendering the glossary link silently blank.  
  *Fix*: Replace `{{ index.glossary_term.term }}` with `{{ index.glossary_term.name }}`.

- [ ] **I5** — `apps/bi/management/commands/seed_bi.py:88` — **Incomplete Seeder `--flush` Cleanup**: The `if flush:` block fails to delete the four 10.15 models (`NarrativeExplanation`, `SearchDiscoveryIndex`, `NaturalLanguageQuery`, `BiConversationSession`), leaving orphaned records after flush and blocking idempotent re-seed.  
  *Fix*: Add `.delete()` calls for all 4 models inside the atomic flush block before referenced parent models.

- [ ] **I6** — `apps/bi/views/ConversationalBi/BiConversationSessions.py:336` & `templates/bi/conversational_bi/chat_workspace.html:186` — **Assistant Workspace Ask Redirect & Open Redirect Guard**: `bi_conversation_session_ask` unconditionally redirects to `bi:bi_conversation_session_detail` without inspecting `next`, forcefully ejecting users from the chat assistant workspace.  
  *Fix*: Add `<input type="hidden" name="next" value="{{ request.get_full_path }}">` in `chat_workspace.html` form, and in `bi_conversation_session_ask` validate `next_url = request.POST.get("next") or request.META.get("HTTP_REFERER")` with `url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()})`.

- [ ] **I7** — `templates/bi/conversational_bi/search_discovery_index/detail.html:48` and `templates/bi/conversational_bi/search_discovery_index/hub.html:83, 154` — **Model Property Drift on Asset Type Badge**: Templates query `type_badge_color`, but `SearchDiscoveryIndex` model defines `asset_type_badge_color`, leaving badges unstyled.  
  *Fix*: Update templates to use `asset_type_badge_color` AND add `@property def type_badge_color(self): return self.asset_type_badge_color` to `SearchDiscoveryIndex`.

- [ ] **I8** — `templates/bi/conversational_bi/natural_language_query/detail.html:149` & `templates/bi/conversational_bi/search_discovery_index/detail.html:101` — **Invalid Theme Badge Classes (Lesson L33)**: `badge-purple` and `badge-indigo` are not defined in `theme.css:286-291` and render unstyled.  
  *Fix*: Replace with valid palette classes (`badge-info` / `badge-slate`).

- [ ] **I9** — `templates/bi/conversational_bi/narrative_explanation/list.html:123` & `templates/bi/conversational_bi/search_discovery_index/list.html:111` — **Design System Table Container Class**: `.table-responsive` does not exist in `theme.css`.  
  *Fix*: Replace `<div class="table-responsive">` with `<div class="table-wrap">`.

- [ ] **I10** — `templates/bi/conversational_bi/narrative_explanation/list.html:33` & `templates/bi/conversational_bi/search_discovery_index/list.html:33` — **Design System Stat Cards & Grid Classes**: Replace non-standard `.stats-grid` with standard grid classes `grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6`, and standardize stat-icon classes (`stat-icon blue/green/purple/orange`).

- [ ] **I11** — `apps/bi/views/ConversationalBi/BiConversationSessions.py:88, 122` — **N+1 Queries on `turn.user` in Thread Detail and Chat Workspace**: `turns` evaluated without `.select_related("user")`, causing 1+N queries when rendering user initials in conversation streams.  
  *Fix*: Add `.select_related("user")` to `session.queries` and `active_session.queries`.

- [ ] **I12** — `apps/bi/views/ConversationalBi/BiConversationSessions.py:113` — **Missing Eager Loading on Active Session**: `sessions` loaded without `.select_related("user", "primary_semantic_model")` in `bi_chat_workspace`.  
  *Fix*: Add `.select_related("user", "primary_semantic_model")` to `sessions` query in `bi_chat_workspace`.

- [ ] **I13** — `apps/bi/views/ConversationalBi/SearchDiscoveryIndexes.py:226, 242` — **Unbounded QuerySet Evaluation in Discovery Hub**: `results = matched` evaluated via `len(results)` in template without slice.  
  *Fix*: Slice `results = matched[:24]`, pass `result_count = matched.count()`, and use `{{ result_count }}` in `hub.html:74`.

- [ ] **I14** — `apps/bi/views/ConversationalBi/BiConversationSessions.py:113` — **Unbounded Conversation Session Drawer**: `sessions` loads all threads without limit in `bi_chat_workspace`.  
  *Fix*: Limit drawer query to `sessions[:50]`.

- [ ] **I15** — `apps/bi/views/ConversationalBi/NarrativeExplanations.py:207-217` — **Missing `transaction.atomic()` in Publish Action**: `save` and `write_audit_log` execute without atomic transaction.  
  *Fix*: Wrap in `with transaction.atomic():`.

- [ ] **I16** — `apps/bi/views/ConversationalBi/BiConversationSessions.py:118-120` — **Multi-Tenant IDOR Fallback on Explicit Session Param**: When passing `?session=<foreign_tenant_id>`, falling back to `sessions.first()` returns HTTP 200 with another session rather than failing closed.  
  *Fix*: Use `get_object_or_404(sessions, pk=int(active_session_id))` when `active_session_id` is supplied, so unauthorized foreign access raises 404.

---

## Minor Findings

- [ ] **M1** — `templates/bi/conversational_bi/search_explorer.html` — **Orphan Template Cleanup**: File is unrouted and superseded by `search_discovery_index/hub.html`.  
  *Fix*: Delete `templates/bi/conversational_bi/search_explorer.html`.

- [ ] **M2** — `templates/bi/conversational_bi/narrative_explanation/list.html:201` & `templates/bi/conversational_bi/search_discovery_index/list.html:195` — **Empty State Container in Table Row**: Missing `.empty-state` wrapper in `{% empty %}` table row.  
  *Fix*: Wrap content in `<div class="empty-state text-center py-12">`.

- [ ] **M3** — `templates/bi/conversational_bi/narrative_explanation/list.html:184-194` & `templates/bi/conversational_bi/search_discovery_index/list.html:174-188` — **Table Action Buttons Styling**: Invented `btn-ghost` class used.  
  *Fix*: Replace with standard `btn btn-icon`.

- [ ] **M4** — `apps/bi/views/ConversationalBi/SearchDiscoveryIndexes.py:244-246` — **Category Extraction Query Joins**: Redundant table joins on category extraction query.  
  *Fix*: Use clean tenant-filtered queryset:
  ```python
  categories = list(
      SearchDiscoveryIndex.objects.filter(tenant=request.tenant)
      .exclude(category="")
      .values_list("category", flat=True)
      .distinct()
      .order_by("category")
  )
  ```

- [ ] **M5** — `apps/bi/views/ConversationalBi/NaturalLanguageQueries.py:95` & `apps/bi/views/ConversationalBi/SearchDiscoveryIndexes.py:82` — **Detail View Lazy Lookups**: Detail views perform lazy lookups on frequently displayed FKs.  
  *Fix*: Pass `select_related(...)` to `bi_object`.

- [ ] **M6** — `apps/bi/models/ConversationalBi/SearchDiscoveryIndexes.py:122-127` — **Composite Index for Curated Discovery Ranking**: Missing composite index `(tenant, is_featured, -relevance_weight)`.  
  *Fix*: Add composite index to `Meta.indexes`.

- [ ] **M7** — `apps/bi/views/ConversationalBi/SearchDiscoveryIndexes.py:239-241` — **Tenant Scope Defense-in-Depth on Telemetry Query**: Query omits `tenant=request.tenant`.  
  *Fix*: Include `tenant=request.tenant` in update query.

- [ ] **M8** — `apps/bi/forms/ConversationalBi/SearchDiscoveryIndexes.py:75-77` — **Protocol-Relative URL Validation**: `clean_target_url` allows `//malicious-url`.  
  *Fix*: Disallow URLs starting with `//`.

- [ ] **M9** — `apps/bi/forms/ConversationalBi/NarrativeExplanations.py:16, 30` — **Mass Assignment on Status in NarrativeForm**: Exclude `status` from `Meta.fields` to enforce dedicated publish action.

- [ ] **M10** — `chat_workspace.html:188`, `detail.html:163`, `hub.html:44` — **Accessibility Form Labels / aria-labels**: Standalone inputs lack matching label or `aria-label`.  
  *Fix*: Add `aria-label="Ask a question"` / `aria-label="Search analytical assets"`.

- [ ] **M11** — `.claude/tasks/contract-bi-10.15.md` Section 3 & 4 — **Contract Documentation for Chat Workspace**: Document `bi_chat_workspace` route and context keys in contract.
