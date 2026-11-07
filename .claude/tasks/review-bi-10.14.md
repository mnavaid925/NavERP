# 6-Lane Review Findings & Action Register — Sub-module 10.14: AI & Augmented Analytics (apps/bi)

Changeset under review: `831d4a2fa67f1876bab24a5541f0e35ea4ec45e9...HEAD` (focusing on Sub-module 10.14 `AiAugmentedAnalytics` additions)

---

## Executive Summary & Action Register

All six review lanes (`code-reviewer`, `explorer`, `frontend-reviewer`, `performance-reviewer`, `qa-smoke-tester`, `security-reviewer`) were executed serially. Findings have been deduplicated, categorized by severity (Critical → Important → Minor), and assigned deterministic action IDs.

### Critical Priority
- [x] **C1**: fixed in e46f3add — Corrected write_audit_log(request.user, obj, action, changes={...}, tenant=request.tenant) call signature and ensured action <= 10 chars across all 16 mutating views in apps/bi/views/AiAugmentedAnalytics/*.py.

### Important Priority
- [x] **I1**: fixed in ef4baf98 — Applied @tenant_admin_required decorator to all 4 delete views in apps/bi/views/AiAugmentedAnalytics/*.py.
- [x] **I2**: fixed in 82138837 — Validated next redirect parameter using url_has_allowed_host_and_scheme(url=next_url, allowed_hosts={request.get_host()}) in action views (augmented_insight_triage, smart_data_prep_suggestion_action, analytics_recommendation_interact).
- [x] **I3**: fixed in f423ad77 — Added clean_target_url() validation to AnalyticsRecommendationForm restricting target_url to relative paths starting with /, and added rel="noopener noreferrer" to external links in templates.
- [x] **I4**: fixed in 572efa4a — Wrapped all 16 mutating views in apps/bi/views/AiAugmentedAnalytics/*.py with @transaction.atomic.
- [x] **I5**: fixed in b6ed9367 — Aggregated key_drivers count in augmented_insight_list context and displayed key_driver_count in list.html.
- [x] **I6**: fixed in c7e989d4 — Created sub-package __init__.py files re-exporting entity classes for models, forms, and views in AiAugmentedAnalytics.
- [ ] **I7**: Add state transition guards and ownership checks in action views: guard `smart_data_prep_suggestion_action` against modifying suggestions already `applied`, and verify user ownership/admin in `analytics_recommendation_interact`.
- [ ] **I8**: Add `select_related` to `bi_object` calls in mutating views (`SmartDataPrepSuggestions.py` for `target_table`, `AnalyticsRecommendations.py` for `user`) to prevent secondary lazy `__str__` queries during audit logging.
- [ ] **I9**: Add `.only("id", "name")` to `WarehouseTable.objects.filter(tenant=request.tenant).order_by("name")` in `apps/bi/views/AiAugmentedAnalytics/SmartDataPrepSuggestions.py:30`.

### Minor Priority
- [ ] **M1**: Remove unused imports in `apps/bi/views/AiAugmentedAnalytics/*.py` (`Decimal`, `get_object_or_404`, `timezone`).
- [ ] **M2**: Add `<input type="hidden" name="next" value="{{ request.get_full_path }}">` to table quick action forms in `smart_data_prep_suggestion/list.html` and `text_sentiment_analysis/list.html`.
- [ ] **M3**: Add matching `id` and `for` attributes on search and filter inputs across list templates.
- [ ] **M4**: Add dark mode contrast utilities for active filter pills and card callouts in `feed.html` (`dark:bg-slate-800`, `dark:text-indigo-300`).
- [ ] **M5**: Add composite index `models.Index(fields=["tenant", "-created_at"], name="idx_bsdp_ten_created")` to `SmartDataPrepSuggestion.Meta.indexes`.
- [ ] **M6**: Add explicit decimal step `step="0.01"` and bounds for polarity and subjectivity score widgets in `TextSentimentAnalysisForm`.

---

## Lane Review Outputs

### Pass 1: Code Reviewer (`code-reviewer`)
- **Verdict**: PASS WITH FIXES (0 Critical, 6 Important, 3 Minor)
- **Critical**: None
- **Important**:
  1. `apps/bi/{models,forms,views}/AiAugmentedAnalytics/__init__.py` — Missing package `__init__.py` files in sub-module directories re-exporting entity classes.
  2. `apps/bi/views/AiAugmentedAnalytics/{AugmentedInsights,SmartDataPrepSuggestions,TextSentimentAnalyses,AnalyticsRecommendations}.py` — Missing `@tenant_admin_required` decorator on all 4 delete views (`augmented_insight_delete`, `smart_data_prep_suggestion_delete`, `text_sentiment_analysis_delete`, `analytics_recommendation_delete`).
  3. `apps/bi/views/AiAugmentedAnalytics/{AugmentedInsights,SmartDataPrepSuggestions,AnalyticsRecommendations}.py` — Potential open redirect via unvalidated `next` parameter in mutating views (`augmented_insight_triage`, `smart_data_prep_suggestion_action`, `analytics_recommendation_interact`). Verify with `url_has_allowed_host_and_scheme`.
  4. `apps/bi/forms/AiAugmentedAnalytics/AnalyticsRecommendations.py` & templates — Missing protocol/path validation for `AnalyticsRecommendation.target_url`. Add `clean_target_url()` ensuring starts with `/` or valid scheme.
  5. `apps/bi/views/AiAugmentedAnalytics/*.py` — Missing `transaction.atomic` wrapping mutating actions and audit log writes.
  6. `apps/bi/views/AiAugmentedAnalytics/SmartDataPrepSuggestions.py:188` — Missing status transition guard on `smart_data_prep_suggestion_action` (prevent transitions once `applied`).
- **Minor**:
  1. Unused imports in view modules (`Decimal`, `get_object_or_404`, `timezone`).
  2. `templates/bi/ai_augmented_analytics/augmented_insight/list.html:58` — Stat card Key Drivers reflects page size rather than total count.
  3. Table action forms missing `next` hidden input (`smart_data_prep_suggestion/list.html:178`, `text_sentiment_analysis/list.html:165`).

### Pass 2: Architecture & Contract Explorer (`explorer`)
- **Verdict**: PASS WITH FINDINGS (0 Critical, 3 Important, 2 Minor)
- **Critical**: None
- **Important**:
  1. `apps/bi/{models,forms,views}/AiAugmentedAnalytics/__init__.py` — Missing sub-package `__init__.py` files re-exporting entity modules.
  2. `apps/bi/models/AiAugmentedAnalytics/*.py` — Omission of explicit `db_table` in Meta (`bi_augmented_insight`, `bi_smart_data_prep_suggestion`, `bi_text_sentiment_analysis`, `bi_analytics_recommendation`).
  3. `templates/bi/ai_augmented_analytics/augmented_insight/list.html:58` & `AugmentedInsights.py` — Stat card Key Drivers reflects current page length instead of total tenant count `key_driver_count`.
- **Minor**:
  1. `apps/bi/forms/AiAugmentedAnalytics/TextSentimentAnalyses.py` — Widget input type step and decimal bounds for `polarity_score` and `subjectivity_score`.
  2. `templates/bi/ai_augmented_analytics/{smart_data_prep_suggestion,text_sentiment_analysis}/list.html` — Missing `next` hidden field on quick action forms.

### Pass 3: Frontend Reviewer (`frontend-reviewer`)
- **Verdict**: PASS WITH FINDINGS (0 Critical, 1 Important, 4 Minor)
- **Critical**: None
- **Important**:
  1. `templates/bi/ai_augmented_analytics/augmented_insight/list.html:58` — Stat card Key Drivers renders `{{ insights|length }}` (current page slice) rather than total tenant count (`key_driver_count`).
- **Minor**:
  1. `templates/bi/ai_augmented_analytics/{smart_data_prep_suggestion,text_sentiment_analysis}/list.html` — Missing explicit `<input type="hidden" name="next">` on inline action forms.
  2. List filter forms accessibility — Missing `for` / `id` pairing on search & filter inputs across list templates.
  3. `feed.html:34-50` — Dark mode contrast utilities for active filter pills and card callouts (`dark:bg-slate-800`, `dark:text-indigo-300`).
  4. `analytics_recommendation/{list,detail}.html` — External asset links (`target_url`) should include `rel="noopener noreferrer"`.

### Pass 4: Performance Reviewer (`performance-reviewer`)
- **Verdict**: PASS WITH FINDINGS (0 Critical, 4 Important, 3 Minor)
- **Critical**: None
- **Important**:
  1. `apps/bi/views/AiAugmentedAnalytics/*.py` — Missing `@transaction.atomic` (or `with transaction.atomic():`) wrapping 16 mutating views and corresponding `write_audit_log` calls.
  2. `templates/bi/ai_augmented_analytics/augmented_insight/list.html:58` & `AugmentedInsights.py:24-29` — Stat card Key Drivers renders current page slice length (`{{ insights|length }}`); add `key_drivers=Count("id", filter=Q(insight_type="key_driver"))` to `qs.aggregate()` in view and pass `key_driver_count` to context.
  3. `apps/bi/views/AiAugmentedAnalytics/{SmartDataPrepSuggestions,AnalyticsRecommendations}.py` — Lazy foreign-key queries triggered by `__str__` traversal during `write_audit_log` in mutating views (`target_table` on `SmartDataPrepSuggestion`, `user` on `AnalyticsRecommendation`). Add `select_related` to `bi_object` calls.
  4. `apps/bi/views/AiAugmentedAnalytics/SmartDataPrepSuggestions.py:30` — Unprojected `WarehouseTable` query in `smart_data_prep_suggestion_list` filter dropdown; add `.only("id", "name")`.
- **Minor**:
  1. `apps/bi/models/AiAugmentedAnalytics/SmartDataPrepSuggestions.py:65-68` — Add composite index on `(tenant, -created_at)` for default ordering performance.
  2. `apps/bi/forms/AiAugmentedAnalytics/*.py` — Unprojected foreign key queryset evaluation in form select fields.
  3. `templates/bi/ai_augmented_analytics/feed.html:95-114` — Ensure triage micro-actions in feed digest wrap triage update and audit log in `transaction.atomic`.

### Pass 5: QA Smoke Tester (`qa-smoke-tester`)
- **Verdict**: FAIL (1 Critical, 2 Important, 2 Minor)
- **Critical**:
  1. `apps/bi/views/AiAugmentedAnalytics/*.py` (16 callsites) — `write_audit_log()` signature mismatch. Views pass unsupported kwargs (`model_name`, `object_id`, `object_repr`, `details`), raising `TypeError` and HTTP 500 on all mutating POST operations (create, edit, delete, triage, recalculate, action). Correct signature is `write_audit_log(user, obj, action, changes=None, tenant=None)`.
- **Important**:
  1. `apps/bi/views/AiAugmentedAnalytics/{AugmentedInsights,SmartDataPrepSuggestions,TextSentimentAnalyses,AnalyticsRecommendations}.py` — Missing `@tenant_admin_required` on all 4 delete views.
  2. `templates/bi/ai_augmented_analytics/augmented_insight/list.html:58` & `AugmentedInsights.py` — Stat card Key Drivers reflects current page slice rather than total count.
- **Minor**:
  1. Action views unvalidated `next` redirect target (`augmented_insight_triage`, `smart_data_prep_suggestion_action`, `analytics_recommendation_interact`).
  2. Missing hidden `next` input on inline table quick actions in list views.

### Pass 6: Security Reviewer (`security-reviewer`)
- **Verdict**: FAIL (1 Critical, 3 Important, 2 Minor)
- **Critical**:
  1. `write_audit_log()` Signature Mismatch Causing Audit Trail Failure / 500 Crashes across 16 callsites in `apps/bi/views/AiAugmentedAnalytics/*.py`.
- **Important**:
  1. Broken Access Control: Missing `@tenant_admin_required` on Destructive Deletions (`augmented_insight_delete`, `smart_data_prep_suggestion_delete`, `text_sentiment_analysis_delete`, `analytics_recommendation_delete`).
  2. Open Redirect Vulnerability via Unvalidated `next` Parameter (CWE-601) in `augmented_insight_triage`, `smart_data_prep_suggestion_action`, `analytics_recommendation_interact`.
  3. Stored XSS / Protocol Injection in `AnalyticsRecommendation.target_url` (CWE-79 / CWE-601).
- **Minor**:
  1. AuditLog action length truncation (action > 10 chars, e.g. `prep_accept`, `rec_dismiss`) & non-atomic mutations.
  2. Missing state transition and ownership guards in `smart_data_prep_suggestion_action` (allow changes once `applied`) and `analytics_recommendation_interact` (allow any user to interact with others' recommendations).
