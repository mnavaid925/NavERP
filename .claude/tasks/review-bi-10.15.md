# Review Findings: Sub-module 10.15 Natural Language & Conversational BI

## 1. Code Reviewer
**Verdict**: Commit after fixing Important findings. Sub-module 10.15 has robust multi-tenancy, clean package structures, and thorough audit logging, but carries a numeric input guard defect (L35), a filter GET parameter mismatch, missing model attributes in templates, and an incomplete `--flush` seeder implementation.

### Important
1. `apps/bi/views/ConversationalBi/SearchDiscoveryIndexes.py:192` — `search_discovery_index_reweight` parses numeric input with `Decimal(weight_val)` without an `is_finite()` guard, allowing `"NaN"` input to parse and crash database persistence during comparison/write (Lesson L35). Fix: Add `if not new_weight.is_finite(): raise InvalidOperation` immediately following `new_weight = Decimal(weight_val)` in the `try` block.
2. `templates/bi/conversational_bi/narrative_explanation/list.html:102` — Filter parameter mismatch: template dropdown submits `name="artifact"` (and pagination propagates `&artifact=...`), but `narrative_explanation_list` view (`apps/bi/views/ConversationalBi/NarrativeExplanations.py:55`) reads `request.GET.get("artifact_type")`, silently ignoring artifact filtering. Fix: Read `request.GET.get("artifact_type") or request.GET.get("artifact", "")` in `narrative_explanation_list` or align template `name` to `"artifact_type"`.
3. `templates/bi/conversational_bi/search_discovery_index/detail.html:180` — Referenced model attribute does not exist: `index.report.title` is rendered for `ReportDefinition`, but `ReportDefinition` has `name` (not `title`), causing the linked report title to render silently blank. Fix: Replace `{{ index.report.title }}` with `{{ index.report.name }}`.
4. `templates/bi/conversational_bi/search_discovery_index/detail.html:192` — Referenced model attribute does not exist: `index.glossary_term.term` is rendered for `BusinessGlossaryTerm`, but `BusinessGlossaryTerm` has `name` (not `term`), causing the linked glossary term to render silently blank. Fix: Replace `{{ index.glossary_term.term }}` with `{{ index.glossary_term.name }}`.
5. `apps/bi/management/commands/seed_bi.py:88` — The `if flush:` block fails to delete any of the four 10.15 models (`NarrativeExplanation`, `SearchDiscoveryIndex`, `NaturalLanguageQuery`, `BiConversationSession`), leaving orphaned records with nullified foreign keys after a flush and preventing proper re-seeding due to the existence check on line 3757. Fix: Add `.delete()` calls for all four 10.15 models inside the `with transaction.atomic():` flush block before their referenced parent models.
6. `apps/bi/views/ConversationalBi/BiConversationSessions.py:336` — In `bi_conversation_session_ask`, the view unconditionally redirects to `bi:bi_conversation_session_detail` without inspecting `next` / HTTP_REFERER, which kicks users out of `chat_workspace.html` into the thread detail page whenever they ask a question from the workspace assistant. Fix: Check `next_url = request.POST.get("next") or request.META.get("HTTP_REFERER")` validated with `url_has_allowed_host_and_scheme` before falling back to `bi_conversation_session_detail`, and add a hidden `next` input to `chat_workspace.html:186`.

### Minor
1. `templates/bi/conversational_bi/search_discovery_index/detail.html:48` — Model property mismatch: `detail.html:48` and `hub.html:83, 154` query `type_badge_color`, but `SearchDiscoveryIndex` defines `asset_type_badge_color`, causing the asset type badge class to evaluate to empty and render uncolored. Fix: Update templates to use `asset_type_badge_color` or alias `type_badge_color` on `SearchDiscoveryIndex`.
2. `templates/bi/conversational_bi/natural_language_query/detail.html:149` — Non-standard theme classes `badge-purple` (`natural_language_query/detail.html:149`, `NaturalLanguageQueries.py:206`) and `badge-indigo` (`search_discovery_index/detail.html:101`) are used, which are absent from `theme.css:286-291` and render unstyled (Lesson L33). Fix: Standardize on supported palette classes (`badge-info`, `badge-slate`, `badge-muted`).
3. `templates/bi/conversational_bi/search_explorer.html:1` — Orphan template file committed in changeset that is neither mapped in `urls/` nor rendered by any view in `apps/bi/`. Fix: Remove the unused file or wire it to an explicit view.

## 2. Explorer (Contract Compliance)
**Verdict**: Commit after fixing Important findings. High adherence to frozen contract across all 4 models, 4 forms, 23 URL routes, and pinned view context keys.

### Important
1. `templates/bi/conversational_bi/narrative_explanation/list.html:102` — Filter Parameter Contract Mismatch: Section 4.3 pins `artifact_choices`. Template dropdown submits `name="artifact"` but view reads `request.GET.get("artifact_type")`. Fix: Change `list.html:102` to `name="artifact_type"` (and `request.GET.artifact_type == val`) or update view to inspect both.
2. `templates/bi/conversational_bi/search_discovery_index/detail.html:180` — Non-Existent Attribute Access: `index.report.title` rendered for `ReportDefinition`, but model has `name`. Fix: Replace `{{ index.report.title }}` with `{{ index.report.name }}`.
3. `templates/bi/conversational_bi/search_discovery_index/detail.html:192` — Non-Existent Attribute Access: `index.glossary_term.term` rendered for `BusinessGlossaryTerm`, but model has `name`. Fix: Replace `{{ index.glossary_term.term }}` with `{{ index.glossary_term.name }}`.
4. `apps/bi/models/ConversationalBi/*.py` — Omission of Explicit `db_table` Pinned in Contract: Models omitted explicit `db_table` declarations (`bi_natural_language_query`, `bi_conversation_session`, etc.), defaulting to Django's standard auto-naming. Fix: Note/accept standard Django names or add explicit `db_table`.

### Minor
1. `templates/bi/conversational_bi/search_discovery_index/detail.html:48` and `hub.html:83, 154` — Model Property Name Mismatch: `type_badge_color` queried vs `asset_type_badge_color` defined. Fix: Alias `type_badge_color` on `SearchDiscoveryIndex`.
2. `templates/bi/conversational_bi/natural_language_query/detail.html:149` & `search_discovery_index/detail.html:101` — Non-Standard Palette Badge Classes: `badge-purple` and `badge-indigo` not in `theme.css`. Fix: Replace with `badge-info` / `badge-slate`.
3. `templates/bi/conversational_bi/search_explorer.html` — Orphan Template File: Committed file not mapped to route. Fix: Remove orphan template.
4. `contract-bi-10.15.md` Section 3 & 4 — Unpinned Convenience Route & Context: `bi_chat_workspace` not explicitly in Section 3/4 table. Fix: Update contract to document workspace route.

## 3. Frontend Reviewer
**Verdict**: High quality interactive chat interface, but requires alignment with theme.css design system standards (table-wrap, stat-icon color names, badge classes, and property naming).

### Important
1. `templates/bi/conversational_bi/natural_language_query/detail.html:149` & `search_discovery_index/detail.html:101` — Invalid Theme Badge Classes (L33): `badge-purple` and `badge-indigo` do not exist in `theme.css`. Fix: Replace with `badge-info` or `badge-slate`.
2. `templates/bi/conversational_bi/search_discovery_index/detail.html:48` & `hub.html:83, 154` — Model Property Drift: `type_badge_color` queried, but model defines `asset_type_badge_color`. Fix: Use `asset_type_badge_color` (and alias property on model).
3. `templates/bi/conversational_bi/narrative_explanation/list.html:123` & `search_discovery_index/list.html:111` — Non-existent CSS Class `.table-responsive`: NavERP standardizes table containers on `.table-wrap`. Fix: Replace `table-responsive` with `table-wrap`.
4. `templates/bi/conversational_bi/narrative_explanation/list.html:33` & `search_discovery_index/list.html:33` — Design System Palette Bypass on Stat Cards & Undefined `.stats-grid`: Replace `.stats-grid` with standard grid classes, and use theme.css stat-icon variants (`stat-icon blue/green/purple/orange`).
5. `templates/bi/conversational_bi/narrative_explanation/list.html:201` & `search_discovery_index/list.html:195` — Missing `.empty-state` container wrapper in `{% empty %}` table row.

### Minor
1. `templates/bi/conversational_bi/bi_conversation_session/detail.html:163`, `chat_workspace.html:188`, `hub.html:44` — Accessibility: Missing `<label>` / `aria-label` on search/chat inputs.


