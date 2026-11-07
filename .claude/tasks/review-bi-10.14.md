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


