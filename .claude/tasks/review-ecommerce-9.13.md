# Review Findings: Sub-module 9.13 — Reviews & User-Generated Content

Reviewing changeset: `3fb041f95e45ff13427ac02c53583153e9d95fc2..e645586a1a7a5c1108438a6644a1981cede6d72b`

---

## 1. Code Reviewer Findings

### Critical
1. `apps/ecommerce/views/ReviewUgc/ProductReviews.py:91` — `write_audit_log` is called with incorrect kwargs (`tenant=...`, `model_name="ProductReview"`, `object_id=...`) instead of positional `user, obj, action`, raising `TypeError: write_audit_log() got an unexpected keyword argument 'model_name'` and 500ing on every review create, update, delete, and moderation. Fix: Call `write_audit_log(request.user, review, "create", {"number": review.number, "product": review.product.name, "rating": review.rating}, tenant=request.tenant)` (and similarly on lines 118, 145, 168).
2. `apps/ecommerce/views/ReviewUgc/ProductQuestionAnswers.py:89` — `write_audit_log` is called with incorrect kwargs (`tenant=...`, `model_name="ProductQuestionAnswer"`, `object_id=...`), raising `TypeError` and 500ing on every question submission, update, deletion, and response. Fix: Call `write_audit_log(request.user, question, "create", {"number": question.number, "product": question.product.name}, tenant=request.tenant)` (and similarly on lines 116, 143, 167).
3. `apps/ecommerce/views/ReviewUgc/VisualUgcMedia.py:87` — `write_audit_log` is called with incorrect kwargs (`tenant=...`, `model_name="VisualUgcMedia"`, `object_id=...`), raising `TypeError` and 500ing on every UGC asset create, update, and delete. Fix: Call `write_audit_log(request.user, media_item, "create", {"number": media_item.number, "media_type": media_item.media_type}, tenant=request.tenant)` (and similarly on lines 114, 141).
4. `apps/ecommerce/views/ReviewUgc/ReviewSentimentSummaries.py:84` — `write_audit_log` is called with incorrect kwargs (`tenant=...`, `model_name="ReviewSentimentSummary"`, `object_id=...`), raising `TypeError` and 500ing on every scorecard create, update, delete, and recalculation. Fix: Call `write_audit_log(request.user, summary, "create", {"number": summary.number, "product": summary.product.name}, tenant=request.tenant)` (and similarly on lines 111, 138, 155).

### Important
1. `templates/ecommerce/review_ugc/sentiment_summary/detail.html:95` — Star distribution progress bars use raw count `style="width: {{ summary.rating_5_count|default:0 }}%"` (and 4, 3, 2, 1 stars on lines 103, 111, 119, 127) rather than percentage of total reviews. Fix: Add `@property` helpers on `ReviewSentimentSummary` (`rating_5_pct`, etc.) calling `self.get_rating_pct(self.rating_5_count)` and bind `style="width: {{ summary.rating_5_pct|default:0 }}%"`.
2. `apps/ecommerce/views/ReviewUgc/ProductReviews.py:140` — `productreview_delete` and `productreview_moderate` (line 158) lack `@tenant_admin_required`, allowing non-admin users to moderate reviews or permanently delete customer feedback. Fix: Decorate `productreview_delete` and `productreview_moderate` with `@tenant_admin_required`.
3. `apps/ecommerce/views/ReviewUgc/ProductQuestionAnswers.py:138` — `productquestionanswer_delete` lacks `@tenant_admin_required`, allowing non-admin users to permanently delete customer questions. Fix: Add `@tenant_admin_required` decorator to `productquestionanswer_delete`.
4. `apps/ecommerce/views/ReviewUgc/VisualUgcMedia.py:136` — `visualugcmedia_delete` lacks `@tenant_admin_required`, allowing non-admin users to delete social proof media assets. Fix: Add `@tenant_admin_required` decorator to `visualugcmedia_delete`.
5. `apps/ecommerce/views/ReviewUgc/ReviewSentimentSummaries.py:133` — `reviewsentimentsummary_delete` lacks `@tenant_admin_required`, allowing non-admin users to delete aggregated product scorecards. Fix: Add `@tenant_admin_required` decorator to `reviewsentimentsummary_delete`.
6. `apps/ecommerce/forms/ReviewUgc/ProductReviews.py:73` — `clean()` does not validate that `variant` belongs to `product` when both are selected, allowing cross-product variant assignment. Fix: In `clean()`, add `if variant and product and variant.product != product: self.add_error("variant", "Selected variant does not belong to the chosen product.")`.
7. `apps/ecommerce/forms/ReviewUgc/VisualUgcMedia.py:62` — `clean()` does not validate that `tagged_variant` belongs to `tagged_product` when both are provided. Fix: In `clean()`, add `if tagged_variant and tagged_product and tagged_variant.product != tagged_product: self.add_error("tagged_variant", "Selected variant does not belong to the tagged product.")`.
8. `apps/ecommerce/forms/ReviewUgc/ReviewSentimentSummaries.py:12` — `ReviewSentimentSummaryForm` allows editing `product` on existing scorecards without re-running `recalculate()`, leaving metrics out of sync with the new product. Fix: In `__init__`, add `if self.instance and self.instance.pk: self.fields["product"].disabled = True`.

### Minor
1. `apps/ecommerce/views/ReviewUgc/ReviewSentimentSummaries.py:158` — Action verb `action="recalculate"` exceeds `AuditLog.action` `varchar(10)` limit (11 characters), triggering an error log and risk of MySQL strict-mode `DataError`. Fix: Pass `action="recalc"` (or `"update"`) with `"action": "recalculate"` inside `changes`.
2. `apps/ecommerce/views/ReviewUgc/ProductReviews.py:5` — Unused imports `get_object_or_404` and `ecommerce_scope` (line 14) are present; also unused `get_object_or_404` in `ProductQuestionAnswers.py:5`, `VisualUgcMedia.py:5`, and `ReviewSentimentSummaries.py:5`. Fix: Remove unused imports from all four view modules.
3. `apps/ecommerce/forms/ReviewUgc/ProductReviews.py:76` — `clean()` fails to reset `is_verified_purchase = False` when an order is unlinked on review edit. Fix: Add `else: self.instance.is_verified_purchase = False` when order is empty.
4. `apps/ecommerce/models/ReviewUgc/ReviewSentimentSummaries.py:76` — `recalculate()` only tallies `positive`, `neutral`, and `negative`, omitting `mixed` reviews from percentages and causing sentiment breakdown bars to total under 100%. Fix: Group `mixed` reviews into neutral or calculate a separate `mixed_sentiment_pct`.


---

## 2. Explorer Review Findings

### Critical
*None.*

### Important
1. `templates/ecommerce/review_ugc/product_review/detail.html:197` & `templates/ecommerce/review_ugc/product_question/detail.html:128` — Missing `display_name` on `CustomerAccountProfile` causes silent blank rendering (` (ECAP-00001)`). Fix: Update templates to use `{{ review.customer.customer.name|default:review.customer.number }}` or add `@property def display_name` on `CustomerAccountProfile`. Also add `"customer__customer"` to `select_related` in `productreview_detail` and `productquestionanswer_detail` views.
2. `apps/ecommerce/forms/ReviewUgc/ProductQuestionAnswers.py:62` — `ProductQuestionAnswerResponseForm` allows submitting empty answers when template labels it `Official Answer *`. Fix: In `ProductQuestionAnswerResponseForm.__init__`, set `self.fields["answer_text"].required = True`.
3. `apps/ecommerce/views/ReviewUgc/ProductQuestionAnswers.py:110` — `productquestionanswer_edit` does not record answer timestamp or respondent when an answer is provided or edited. Fix: In `productquestionanswer_edit`, populate `answered_at` and `answered_by_user` if `question.answer_text` is set and `answered_at` is empty.
4. `apps/ecommerce/forms/ReviewUgc/ReviewSentimentSummaries.py:27` — `ReviewSentimentSummaryForm` allows selecting already-summarized products on create, leading to database `IntegrityError` or validation error on the OneToOne relation. Fix: Filter out products with existing summaries on create (`self.fields["product"].queryset = self.fields["product"].queryset.filter(review_summary__isnull=True)`).

### Minor
1. `apps/ecommerce/views/ReviewUgc/ProductReviews.py:165` — `merchant_response_at` not cleared when reply is erased. Fix: Set `review.merchant_response_at = None` if `review.merchant_response` is empty.
2. `apps/ecommerce/views/ReviewUgc/ProductQuestionAnswers.py:178` — Response action does not pre-select "approved" status for pending questions. Fix: Set `initial["status"] = "approved"` when question is currently pending.
3. `templates/ecommerce/review_ugc/visual_ugc/detail.html:67` — `capitalize` filter distorts brand casing on media type display (e.g. TikTok Video). Fix: Remove `capitalize` filter.
4. `apps/ecommerce/views/ReviewUgc/ProductReviews.py:14` — Unused imports (`ecommerce_scope` in `ProductReviews.py` and `get_object_or_404` in all four view modules). Fix: Remove unused imports.


---

## 3. Frontend Review Findings

### Critical
*None.*

### Important
1. `templates/ecommerce/review_ugc/sentiment_summary/detail.html:95, 103, 111, 119, 127` — Star distribution progress bars use raw integer count instead of proportional percentage (`style="width: {{ summary.rating_5_count|default:0 }}%"`). Fix: Use Django's built-in `{% widthratio summary.rating_5_count summary.total_reviews 100 %}%` (or model property `rating_5_pct`).

### Minor
1. `templates/ecommerce/review_ugc/visual_ugc/list.html:121-127` & `templates/ecommerce/review_ugc/visual_ugc/detail.html:19-25` — `rights_status` badge check uses `{% else %}` for "Rejected" rather than explicit check and neutral fallback with `{{ item.get_rights_status_display }}`. Fix: Add explicit branch for `rejected` and fallback with `badge-slate`.
2. `templates/ecommerce/review_ugc/sentiment_summary/list.html:110` — Recalculate icon button missing accessible `title` and `aria-label` directly on the `<button>`. Fix: Add `title="Recalculate Metrics"` and `aria-label="Recalculate Metrics"` to the `<button>`.


---

## 4. Performance Review Findings

### Critical
*None.*

### Important
1. `apps/ecommerce/models/ReviewUgc/ReviewSentimentSummaries.py:54-82` — 9 separate `COUNT(*)` queries during scorecard recalculation. Fix: Replace multiple `.count()` calls with a single conditional `.aggregate()` query using `Count` and `Q(filter=...)`.
2. `apps/ecommerce/forms/ReviewUgc/ProductReviews.py:65-66` — 2N Chained N+1 queries when populating `order` and `customer` dropdowns in `ProductReviewForm`. Fix: Add `select_related("customer")` to both querysets in `ProductReviewForm.__init__`.
3. `apps/ecommerce/forms/ReviewUgc/ProductQuestionAnswers.py:52` — N+1 Chained queries when populating `customer` dropdown in `ProductQuestionAnswerForm`. Fix: Add `select_related("customer")` to `self.fields["customer"].queryset` in `ProductQuestionAnswerForm.__init__`.

### Minor
1. `apps/ecommerce/views/ReviewUgc/ProductReviews.py:78` & `apps/ecommerce/views/ReviewUgc/ProductQuestionAnswers.py:68` — Missing `customer__customer` in detail view `select_related`. Fix: Include `"customer__customer"` in `select_related`.
2. `apps/ecommerce/models/ReviewUgc/ProductReviews.py:98-102` & `ProductQuestionAnswers.py:53-56` — Missing composite index on `(tenant, status)` for moderation queues. Fix: Add composite index on `(tenant, status)` in both models.
3. `apps/ecommerce/models/ReviewUgc/VisualUgcMedia.py:54-57` — Missing index on `(tenant, media_type)`. Fix: Add composite index `(tenant, media_type)`.
4. `apps/ecommerce/views/ReviewUgc/` (all 4 list views) — Over-fetching heavy TextFields for product filter dropdowns. Fix: Use `.only("id", "name")`.


---

## 5. QA Smoke Tester Findings

### Critical
1. `apps/ecommerce/views/ReviewUgc/*.py` (all 4 view modules: `ProductReviews.py:91,118,145,168`, `ProductQuestionAnswers.py:89,117,143,167`, `VisualUgcMedia.py:87,114,141`, `ReviewSentimentSummaries.py:84,112,141,155`) — `write_audit_log()` signature mismatch (`TypeError: write_audit_log() got an unexpected keyword argument 'model_name'`) crashes all 15 POST actions across all 4 ReviewUgc views with HTTP 500. Fix: Change call signature to `write_audit_log(request.user, obj, action, changes, tenant=request.tenant)`.

### Important
1. `apps/ecommerce/views/ReviewUgc/ReviewSentimentSummaries.py:155` — Action verb `"recalculate"` (11 chars) exceeds `AuditLog.action` varchar(10) column limit. Fix: Change action verb to `"recalc"`.
