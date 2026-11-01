# Review Findings — Sub-module 9.14: Customer Service & Support (Module 9: eCommerce Management System)

- **Target App:** `apps/ecommerce/`
- **Sub-module:** 9.14 Customer Service & Support
- **Review Range:** `09e6bd0b18b2b5b7100e3982583d62734e7838ae...1c4ae804330e529a6bbae58c0fddf97c6ffa4c34`
- **Review Date:** 2026-11-01
- **Status:** Consolidated & Deduplicated

---

## Critical Findings

- [ ] **C1** — Fatal Runtime TypeError on Form Validation (HTTP 500 and IDOR validation failure) in Support ModelForms
  - **Files:**
    - `apps/ecommerce/forms/CustomerSupport/CustomerSupportTickets.py:84-85`
    - `apps/ecommerce/forms/CustomerSupport/OrderIssueClaims.py:72-74`
    - `apps/ecommerce/forms/CustomerSupport/CustomerSatisfactionSurveys.py:65-67`
  - **Issue:** `reject_foreign` is called as `reject_foreign(self, "<field>", self.tenant)`. But `apps/ecommerce/forms/_common.py:23` defines `reject_foreign(form, cleaned, names)` iterating `for name in names:`. Passing `self.tenant` in 3rd position raises `TypeError: 'Tenant' object is not iterable` and crashes with HTTP 500 on any submission.
  - **Fix:** Replace calls with `reject_foreign(self, cleaned, ["customer", "order"])` (and matching lists for claim and survey).

- [ ] **C2** — Stored XSS / DOM Injection via Inline `onerror` Event Handler in Claim Detail Template
  - **File:** `templates/ecommerce/customer_support/claim/detail.html:80`
  - **Issue:** Direct string interpolation of `{{ claim.photo_evidence_url }}` into an inline JavaScript `onerror="...innerHTML='...<a href=\'{{ claim.photo_evidence_url }}\'>...'"` event handler enables stored XSS via crafted quote/script breakout payloads.
  - **Fix:** Remove the inline `onerror` attribute and JS DOM injection. Render the preview using a standard image container and rely on the already provided external link below.

---

## Important Findings

- [ ] **I1** — Inexistent `grand_total` Attribute on `ticket.order` and `claim.order` causing Silent Blank Rendering
  - **Files:**
    - `templates/ecommerce/customer_support/ticket/detail.html:153`
    - `templates/ecommerce/customer_support/claim/detail.html:138`
  - **Issue:** `EcommerceOrder` defines `total_amount` (`grand_total` only exists on `Cart`). This causes order total to render silently blank (`Total: $ • Status: ...`).
  - **Fix:** Change `ticket.order.grand_total` and `claim.order.grand_total` to `.total_amount`.

- [ ] **I2** — Deletion Audit Logging Records `object_id=None` across all 4 Delete Views
  - **Files:**
    - `apps/ecommerce/views/CustomerSupport/CustomerSupportTickets.py:150-157`
    - `apps/ecommerce/views/CustomerSupport/KnowledgeBaseArticles.py:130-137`
    - `apps/ecommerce/views/CustomerSupport/OrderIssueClaims.py:131-138`
    - `apps/ecommerce/views/CustomerSupport/CustomerSatisfactionSurveys.py:132-139`
  - **Issue:** `write_audit_log` is called after `obj.delete()`. Django clears `obj.pk` to `None` upon deletion, so `AuditLog.object_id` is recorded as `None`.
  - **Fix:** Move `write_audit_log(...)` to execute before `obj.delete()`.

- [ ] **I3** — Unscoped Database Update and Unnecessary Cache Flush in Knowledge Base Detail View
  - **File:** `apps/ecommerce/views/CustomerSupport/KnowledgeBaseArticles.py:64-65`
  - **Issue:** `update(view_count=F("view_count") + 1)` is not scoped to `tenant=request.tenant`. Calling `article.refresh_from_db()` flushes `fields_cache` and triggers extra database queries.
  - **Fix:** Add `tenant=request.tenant` to the update query, increment `article.view_count += 1` in memory, and remove `refresh_from_db()`.

- [ ] **I4** — Chained N+1 Queries in Customer Support Views via `CustomerAccountProfile.__str__`
  - **Files:**
    - `apps/ecommerce/views/CustomerSupport/OrderIssueClaims.py:17-19, 64`
    - `apps/ecommerce/views/CustomerSupport/CustomerSatisfactionSurveys.py:17-19, 64`
    - `apps/ecommerce/views/CustomerSupport/CustomerSupportTickets.py:65`
  - **Issue:** `CustomerAccountProfile.__str__` accesses `self.customer` (`core.Party`), causing extra queries unless `"customer__customer"` is pre-fetched.
  - **Fix:** Use `"customer__customer"` in `select_related` across list and detail views.

- [ ] **I5** — Non-existent Utility Classes `text-primary` and `border-primary` in Templates (Lesson L13)
  - **Files:** `templates/ecommerce/customer_support/{ticket,article,claim,survey}/{list,detail}.html`
  - **Issue:** `text-primary` and `border-primary` do not exist in `theme.css`.
  - **Fix:** Replace with `text-brand` (or `text-blue-600`) and `border-brand-500` / `border-blue-600`.

- [ ] **I6** — Dark Mode Contrast Issues on Hardcoded Slate Utilities in Cards
  - **Files:** `templates/ecommerce/customer_support/{ticket,article,claim,survey}/{list,detail,form}.html`
  - **Issue:** Text styled with `text-slate-900`, `text-slate-800`, `text-slate-700` inside `.card` elements without dark variants has poor contrast in dark theme.
  - **Fix:** Add `dark:text-slate-100` / `dark:text-slate-200` to headings and prominent labels.

- [ ] **I7** — Missing Composite Indexes for High-Frequency Filter Combinations
  - **Files:** `apps/ecommerce/models/CustomerSupport/{CustomerSupportTickets,OrderIssueClaims,CustomerSatisfactionSurveys,KnowledgeBaseArticles}.py`
  - **Issue:** Hot filter queries lack composite indexes: `(tenant, channel)` on tickets, `(tenant, claim_type)` on claims, `(tenant, sentiment)` on surveys, and `(tenant, target_audience)` on articles.
  - **Fix:** Add `models.Index` definitions to `Meta.indexes`, generate migration, and apply it.

- [ ] **I8** — Missing Non-Negative Validation on Financial Claim Amounts
  - **Files:**
    - `apps/ecommerce/models/CustomerSupport/OrderIssueClaims.py:65-76`
    - `apps/ecommerce/forms/CustomerSupport/OrderIssueClaims.py:37-38`
  - **Issue:** Negative amounts are not prevented on `claimed_amount` and `approved_amount`.
  - **Fix:** Add `MinValueValidator(Decimal("0.00"))` to model fields and validate non-negative in `OrderIssueClaimForm.clean()`.

- [ ] **I9** — CSAT and NPS Rating Boundary Mismatch and Detractor Validation
  - **Files:**
    - `apps/ecommerce/models/CustomerSupport/CustomerSatisfactionSurveys.py:55-58`
    - `apps/ecommerce/forms/CustomerSupport/CustomerSatisfactionSurveys.py:34`
  - **Issue:** CSAT surveys allow scores up to 10 (>5 breaks UI `8 / 5`), while NPS enforces min 1 which rejects valid detractor rating of 0.
  - **Fix:** Set model `MinValueValidator(0)` and `MaxValueValidator(10)`, and in `CustomerSatisfactionSurveyForm.clean()` enforce 1-5 for CSAT and 0-10 for NPS.

- [ ] **I10** — Automatic Sentiment Recalculation Overwrites Staff Overrides
  - **File:** `apps/ecommerce/models/CustomerSupport/CustomerSatisfactionSurveys.py:96-110`
  - **Issue:** `CustomerSatisfactionSurvey.save()` unconditionally recalculates `sentiment`, wiping out manual supervisor adjustments.
  - **Fix:** Only compute auto-sentiment if `not self.sentiment` or if `self.sentiment == "neutral"`.

- [ ] **I11** — Survey List NPS Score Color Thresholds Contradict Sentiment
  - **File:** `templates/ecommerce/customer_support/survey/list.html:111-120`
  - **Issue:** Score color conditional uses `>= 8` green and `>= 6` amber, conflicting with NPS definitions.
  - **Fix:** Align with `detail.html` by styling the score directly via `survey.sentiment` (`text-green-700` if positive, `text-amber-600` if neutral, `text-red-700` if negative).

---

## Minor Findings

- [ ] **M1** — Intra-Tenant Cross-Shopper Consistency Validation in Forms
  - **Files:** `apps/ecommerce/forms/CustomerSupport/{CustomerSupportTickets,OrderIssueClaims,CustomerSatisfactionSurveys}.py`
  - **Issue:** When both `customer` and `order` are selected, `order.customer_id` should match `customer.customer_id`.
  - **Fix:** In `clean()`, raise validation error if both are provided and `order.customer_id != customer.customer_id`.

- [ ] **M2** — Sidebar Live Chat Link Missing Query Filter Parameter
  - **File:** `apps/core/navigation.py:2788`
  - **Issue:** `"Live Chat & Chatbot"` in `LIVE_LINKS["9.14"]` links to ticket list without `?channel=chat`.
  - **Fix:** Update route target to `"ecommerce:customersupportticket_list?channel=chat"`.

- [ ] **M3** — Ticket Status Badges in List View Missing Default Fallback
  - **File:** `templates/ecommerce/customer_support/ticket/list.html:140-155`
  - **Issue:** Status badge checks lack fallback `{% else %}` rendering `{{ ticket.get_status_display }}`.
  - **Fix:** Add `{% elif ticket.status == 'cancelled' %}` and `{% else %}<span class="badge badge-slate">{{ ticket.get_status_display }}</span>{% endif %}`.

- [ ] **M4** — KB Article List Table Header Reads `Helpful Ratio` but Displays Raw Count
  - **File:** `templates/ecommerce/customer_support/article/list.html:81`
  - **Issue:** Column header says `Helpful Ratio` while cell renders `{{ article.helpful_votes }} / {{ article.unhelpful_votes }}`.
  - **Fix:** Change column header to `Helpful / Unhelpful`.

- [ ] **M5** — Ticket `resolved_at` Not Cleared on Reopening
  - **File:** `apps/ecommerce/models/CustomerSupport/CustomerSupportTickets.py:118-120`
  - **Issue:** Reopening a ticket from `resolved` to `open` retains the old `resolved_at` timestamp.
  - **Fix:** Set `self.resolved_at = None` if `self.status not in ["resolved", "closed"]`.

- [ ] **M6** — Physical Directional Classes in Survey Detail and Ticket List Violate RTL Layout
  - **Files:** `templates/ecommerce/customer_support/survey/detail.html:63`, `ticket/list.html:137`
  - **Issue:** Uses `border-l-4`, `pl-4`, `ml-1`.
  - **Fix:** Replace with logical `border-s-4`, `ps-4`, `ms-1`.

- [ ] **M7** — Detail Pages Lack Explicit "Back to List" Action in Header
  - **Files:** `templates/ecommerce/customer_support/{ticket,article,claim,survey}/detail.html`
  - **Issue:** Detail pages only have Edit and Delete buttons in `.page-actions`.
  - **Fix:** Add `<a href="{% url 'ecommerce:<entity>_list' %}" class="btn btn-outline"><i data-lucide="arrow-left"></i> Back</a>`.

- [ ] **M8** — Unconstrained User Query in Ticket List Filter
  - **File:** `apps/ecommerce/views/CustomerSupport/CustomerSupportTickets.py:59`
  - **Issue:** `User.objects.filter(is_active=True)` retrieves all auth columns.
  - **Fix:** Add `.only("id", "username", "first_name", "last_name")`.

- [ ] **M9** — Large Markdown `content` Column Loaded on KB Article List View
  - **File:** `apps/ecommerce/views/CustomerSupport/KnowledgeBaseArticles.py:17`
  - **Issue:** Full article markdown body fetched during list pagination.
  - **Fix:** Add `.defer("content")`.

- [ ] **M10** — Photo Evidence URL Missing Explicit URL Scheme Validation
  - **File:** `apps/ecommerce/models/CustomerSupport/OrderIssueClaims.py:83`
  - **Issue:** `photo_evidence_url` doesn't restrict schemes to `["http", "https"]`.
  - **Fix:** Add `validators=[URLValidator(schemes=["http", "https"])]`.
