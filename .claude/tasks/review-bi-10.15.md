# Consolidated Review Findings: Sub-module 10.15 Natural Language & Conversational BI

**Scope**: Changeset `BASE (ff2b961f0e086fc09a9b9f15d9bb168ae8976b9d) ... HEAD`  
**Reviewers Executed**: 6 of 6 (Code Reviewer, Explorer, Frontend Reviewer, Performance Reviewer, QA Smoke Tester, Security Reviewer)  
**Status**: All 27 findings burned down and resolved by `code-fixer`

---

## Summary of Findings

| Severity | Total | Status |
|----------|-------|--------|
| Critical | 0     | 0 open |
| Important| 16    | 0 open (16 fixed) |
| Minor    | 11    | 0 open (11 fixed) |
| **Total**| **27**| **0 open (27 fixed)** |

---

## Critical Findings
*None.* (Zero 500 server crashes, zero unhandled 404s on valid tenant data, and 100% tenant boundary isolation verified).

---

## Important Findings

- [x] **I1** — `apps/bi/views/ConversationalBi/SearchDiscoveryIndexes.py:192` — **Decimal NaN/Infinity Input Guard (Lesson L35)**: `search_discovery_index_reweight` parses numeric input with `Decimal(weight_val)` without an `is_finite()` guard. Non-finite values (`"NaN"`, `"Infinity"`) crash DB persistence or comparison.  
  *Fix*: Immediately following `new_weight = Decimal(weight_val)`, add:
  ```python
  if not new_weight.is_finite():
      raise InvalidOperation("Non-finite Decimal rejected")
  ```
  *Status*: [x] fixed — `62d603da fix(bi): guard against non-finite Decimal in search index reweight (I1)`

- [x] **I2** — `templates/bi/conversational_bi/narrative_explanation/list.html:102, 114, 226, 229` & `apps/bi/views/ConversationalBi/NarrativeExplanations.py:55` — **Filter Parameter Mismatch**: The template dropdown submits `name="artifact"` and pagination links propagate `&artifact=...`, but `narrative_explanation_list` view reads `request.GET.get("artifact_type")`. Artifact filtering is silently ignored.  
  *Fix*: Align template dropdown to `name="artifact_type"` (and `request.GET.artifact_type`), and update view to accept both `request.GET.get("artifact_type") or request.GET.get("artifact", "")`.  
  *Status*: [x] fixed — `df063f81 fix(bi): accept both artifact_type and artifact filter params in narrative explanation list (I2)` & `76d98691 fix(bi): align artifact filter input name and pagination links to artifact_type (I2)`

- [x] **I3** — `templates/bi/conversational_bi/search_discovery_index/detail.html:180` — **Referenced Model Attribute Access on ReportDefinition**: Template renders `{{ index.report.title }}`, but `ReportDefinition` model defines `name` (not `title`), rendering the report link silently blank.  
  *Fix*: Replace `{{ index.report.title }}` with `{{ index.report.name }}`.  
  *Status*: [x] fixed — `7fa1cd03 fix(bi): access name instead of title for ReportDefinition in search index detail (I3)`

- [x] **I4** — `templates/bi/conversational_bi/search_discovery_index/detail.html:192` — **Referenced Model Attribute Access on BusinessGlossaryTerm**: Template renders `{{ index.glossary_term.term }}`, but `BusinessGlossaryTerm` model defines `name` (not `term`), rendering the glossary link silently blank.  
  *Fix*: Replace `{{ index.glossary_term.term }}` with `{{ index.glossary_term.name }}`.  
  *Status*: [x] fixed — `bd6395f0 fix(bi): access name instead of term for BusinessGlossaryTerm in search index detail (I4)`

- [x] **I5** — `apps/bi/management/commands/seed_bi.py:88` — **Incomplete Seeder `--flush` Cleanup**: The `if flush:` block fails to delete the four 10.15 models (`NarrativeExplanation`, `SearchDiscoveryIndex`, `NaturalLanguageQuery`, `BiConversationSession`), leaving orphaned records after flush and blocking idempotent re-seed.  
  *Fix*: Add `.delete()` calls for all 4 models inside the atomic flush block before referenced parent models.  
  *Status*: [x] fixed — `ce9ed43b fix(bi): add 10.15 models to seeder flush cleanup (I5)`

- [x] **I6** — `apps/bi/views/ConversationalBi/BiConversationSessions.py:336` & `templates/bi/conversational_bi/chat_workspace.html:186` — **Assistant Workspace Ask Redirect & Open Redirect Guard**: `bi_conversation_session_ask` unconditionally redirects to `bi:bi_conversation_session_detail` without inspecting `next`, forcefully ejecting users from the chat assistant workspace.  
  *Fix*: Add `<input type="hidden" name="next" value="{{ request.get_full_path }}">` in `chat_workspace.html` form, and in `bi_conversation_session_ask` validate `next_url = request.POST.get("next") or request.META.get("HTTP_REFERER")` with `url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()})`.  
  *Status*: [x] fixed — `b0fe45d4 fix(bi): respect next redirect with host validation in bi_conversation_session_ask (I6)` & `aceee8a7 fix(bi): preserve workspace location via next parameter in chat workspace ask form (I6)`

- [x] **I7** — `templates/bi/conversational_bi/search_discovery_index/detail.html:48` and `templates/bi/conversational_bi/search_discovery_index/hub.html:83, 154` — **Model Property Drift on Asset Type Badge**: Templates query `type_badge_color`, but `SearchDiscoveryIndex` model defines `asset_type_badge_color`, leaving badges unstyled.  
  *Fix*: Update templates to use `asset_type_badge_color` AND add `@property def type_badge_color(self): return self.asset_type_badge_color` to `SearchDiscoveryIndex`.  
  *Status*: [x] fixed — `38d4057a fix(bi): add type_badge_color property alias on SearchDiscoveryIndex (I7)`, `d35922b8 fix(bi): use asset_type_badge_color in search discovery index detail (I7)`, & `8c917f53 fix(bi): use asset_type_badge_color property in discovery hub template (I7)`

- [x] **I8** — `templates/bi/conversational_bi/natural_language_query/detail.html:149` & `templates/bi/conversational_bi/search_discovery_index/detail.html:101` — **Invalid Theme Badge Classes (Lesson L33)**: `badge-purple` and `badge-indigo` are not defined in `theme.css:286-291` and render unstyled.  
  *Fix*: Replace with valid palette classes (`badge-info` / `badge-slate`).  
  *Status*: [x] fixed — `c3b280d3 fix(bi): replace invalid badge-purple with badge-info in NL query detail (I8)` & `e69451e8 fix(bi): replace invalid badge-indigo with badge-info in search index detail (I8)`

- [x] **I9** — `templates/bi/conversational_bi/narrative_explanation/list.html:123` & `templates/bi/conversational_bi/search_discovery_index/list.html:111` — **Design System Table Container Class**: `.table-responsive` does not exist in `theme.css`.  
  *Fix*: Replace `<div class="table-responsive">` with `<div class="table-wrap">`.  
  *Status*: [x] fixed — `2eed6c87 fix(bi): replace non-standard table-responsive with table-wrap in narrative list (I9)` & `2fda9cb7 fix(bi): replace non-standard table-responsive with table-wrap in search index list (I9)`

- [x] **I10** — `templates/bi/conversational_bi/narrative_explanation/list.html:33` & `templates/bi/conversational_bi/search_discovery_index/list.html:33` — **Design System Stat Cards & Grid Classes**: Replace non-standard `.stats-grid` with standard grid classes `grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6`, and standardize stat-icon classes (`stat-icon blue/green/purple/orange`).  
  *Status*: [x] fixed — `87c87624 fix(bi): standardize stat grid and stat-icon colors in narrative list (I10)` & `7360e4e8 fix(bi): standardize stat grid and color-named stat-icon classes in search index list (I10)`

- [x] **I11** — `apps/bi/views/ConversationalBi/BiConversationSessions.py:88, 122` — **N+1 Queries on `turn.user` in Thread Detail and Chat Workspace**: `turns` evaluated without `.select_related("user")`, causing 1+N queries when rendering user initials in conversation streams.  
  *Fix*: Add `.select_related("user")` to `session.queries` and `active_session.queries`.  
  *Status*: [x] fixed — `273042de perf(bi): eager load user on queries in thread detail and chat workspace (I11)`

- [x] **I12** — `apps/bi/views/ConversationalBi/BiConversationSessions.py:113` — **Missing Eager Loading on Active Session**: `sessions` loaded without `.select_related("user", "primary_semantic_model")` in `bi_chat_workspace`.  
  *Fix*: Add `.select_related("user", "primary_semantic_model")` to `sessions` query in `bi_chat_workspace`.  
  *Status*: [x] fixed — `f8f24f33 perf(bi): eager load user and primary_semantic_model in chat workspace sessions (I12)`

- [x] **I13** — `apps/bi/views/ConversationalBi/SearchDiscoveryIndexes.py:226, 242` — **Unbounded QuerySet Evaluation in Discovery Hub**: `results = matched` evaluated via `len(results)` in template without slice.  
  *Fix*: Slice `results = matched[:24]`, pass `result_count = matched.count()`, and use `{{ result_count }}` in `hub.html:74`.  
  *Status*: [x] fixed — `22d1570c perf(bi): slice discovery hub search results to 24 and pass result_count (I13)` & `f9db714b perf(bi): use result_count context variable in discovery hub template (I13)`

- [x] **I14** — `apps/bi/views/ConversationalBi/BiConversationSessions.py:113` — **Unbounded Conversation Session Drawer**: `sessions` loads all threads without limit in `bi_chat_workspace`.  
  *Fix*: Limit drawer query to `sessions[:50]`.  
  *Status*: [x] fixed — `ebb7c648 perf(bi): limit chat workspace drawer session list to 50 items (I14)`

- [x] **I15** — `apps/bi/views/ConversationalBi/NarrativeExplanations.py:207-217` — **Missing `transaction.atomic()` in Publish Action**: `save` and `write_audit_log` execute without atomic transaction.  
  *Fix*: Wrap in `with transaction.atomic():`.  
  *Status*: [x] fixed — `a20a7feb fix(bi): wrap narrative publish action in transaction.atomic (I15)`

- [x] **I16** — `apps/bi/views/ConversationalBi/BiConversationSessions.py:118-120` — **Multi-Tenant IDOR Fallback on Explicit Session Param**: When passing `?session=<foreign_tenant_id>`, falling back to `sessions.first()` returns HTTP 200 with another session rather than failing closed.  
  *Fix*: Use `get_object_or_404(sessions, pk=int(active_session_id))` when `active_session_id` is supplied, so unauthorized foreign access raises 404.  
  *Status*: [x] fixed — `7dbe1a0b security(bi): raise 404 on invalid or foreign tenant session parameter in chat workspace (I16)`

---

## Minor Findings

- [x] **M1** — `templates/bi/conversational_bi/search_explorer.html` — **Orphan Template Cleanup**: File is unrouted and superseded by `search_discovery_index/hub.html`.  
  *Fix*: Delete `templates/bi/conversational_bi/search_explorer.html`.  
  *Status*: [x] fixed — `50883eea chore(bi): delete orphan unrouted search_explorer.html template (M1)`

- [x] **M2** — `templates/bi/conversational_bi/narrative_explanation/list.html:201` & `templates/bi/conversational_bi/search_discovery_index/list.html:195` — **Empty State Container in Table Row**: Missing `.empty-state` wrapper in `{% empty %}` table row.  
  *Fix*: Wrap content in `<div class="empty-state text-center py-12">`.  
  *Status*: [x] fixed — `600d0d62 style(bi): wrap empty state in standard empty-state class in narrative list (M2)` & `22e5dca6 style(bi): wrap empty state in standard empty-state class in search index list (M2)`

- [x] **M3** — `templates/bi/conversational_bi/narrative_explanation/list.html:184-194` & `templates/bi/conversational_bi/search_discovery_index/list.html:174-188` — **Table Action Buttons Styling**: Invented `btn-ghost` class used.  
  *Fix*: Replace with standard `btn btn-icon`.  
  *Status*: [x] fixed — `75852ee0 style(bi): replace btn-ghost with standard btn-icon in narrative list (M3)` & `a3b4f34e style(bi): replace btn-ghost with standard btn-icon in search index list (M3)`

- [x] **M4** — `apps/bi/views/ConversationalBi/SearchDiscoveryIndexes.py:244-246` — **Category Extraction Query Joins**: Redundant table joins on category extraction query.  
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
  *Status*: [x] fixed — `9bb570ec perf(bi): avoid redundant table joins in category extraction query (M4)`

- [x] **M5** — `apps/bi/views/ConversationalBi/NaturalLanguageQueries.py:95` & `apps/bi/views/ConversationalBi/SearchDiscoveryIndexes.py:82` — **Detail View Lazy Lookups**: Detail views perform lazy lookups on frequently displayed FKs.  
  *Fix*: Pass `select_related(...)` to `bi_object`.  
  *Status*: [x] fixed — `77f2310b perf(bi): pass select_related to bi_object in natural language query detail (M5)` & `8352e126 perf(bi): pass select_related to bi_object in search discovery index detail (M5)`

- [x] **M6** — `apps/bi/models/ConversationalBi/SearchDiscoveryIndexes.py:122-127` — **Composite Index for Curated Discovery Ranking**: Missing composite index `(tenant, is_featured, -relevance_weight)`.  
  *Fix*: Add composite index to `Meta.indexes`.  
  *Status*: [x] fixed — `096768db perf(bi): add composite index (tenant, is_featured, -relevance_weight) to SearchDiscoveryIndex (M6)` & `60a96899 feat(bi): create migration for SearchDiscoveryIndex composite index (M6)`

- [x] **M7** — `apps/bi/views/ConversationalBi/SearchDiscoveryIndexes.py:239-241` — **Tenant Scope Defense-in-Depth on Telemetry Query**: Query omits `tenant=request.tenant`.  
  *Fix*: Include `tenant=request.tenant` in update query.  
  *Status*: [x] fixed — `e4e088f4 security(bi): scope search hit count telemetry update to request.tenant (M7)`

- [x] **M8** — `apps/bi/forms/ConversationalBi/SearchDiscoveryIndexes.py:75-77` — **Protocol-Relative URL Validation**: `clean_target_url` allows `//malicious-url`.  
  *Fix*: Disallow URLs starting with `//`.  
  *Status*: [x] fixed — `6ca5601a security(bi): disallow protocol-relative URLs in clean_target_url (M8)`

- [x] **M9** — `apps/bi/forms/ConversationalBi/NarrativeExplanations.py:16, 30` — **Mass Assignment on Status in NarrativeForm**: Exclude `status` from `Meta.fields` to enforce dedicated publish action.  
  *Status*: [x] fixed — `c201a2ef security(bi): exclude status from NarrativeExplanationForm fields to prevent mass assignment (M9)` & `4ec87524 style(bi): remove excluded status field from narrative explanation form template (M9)`

- [x] **M10** — `chat_workspace.html:188`, `detail.html:163`, `hub.html:44` — **Accessibility Form Labels / aria-labels**: Standalone inputs lack matching label or `aria-label`.  
  *Fix*: Add `aria-label="Ask a question"` / `aria-label="Search analytical assets"`.  
  *Status*: [x] fixed — `6e1a01a5 accessibility(bi): add aria-label to chat workspace question input (M10)`, `c39df8ae accessibility(bi): add aria-label to chat input in conversation session detail (M10)`, & `81409ba8 accessibility(bi): add aria-label to search input in discovery hub (M10)`

- [x] **M11** — `.claude/tasks/contract-bi-10.15.md` Section 3 & 4 — **Contract Documentation for Chat Workspace**: Document `bi_chat_workspace` route and context keys in contract.  
  *Status*: [x] fixed — `94a89641 docs(bi): document bi_chat_workspace route and context contract (M11)`
