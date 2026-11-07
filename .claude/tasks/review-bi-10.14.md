# 6-Lane Review Findings & Action Register — Sub-module 10.14: AI & Augmented Analytics (apps/bi)

Changeset under review: `831d4a2fa67f1876bab24a5541f0e35ea4ec45e9...HEAD` (focusing on Sub-module 10.14 `AiAugmentedAnalytics` additions)

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



