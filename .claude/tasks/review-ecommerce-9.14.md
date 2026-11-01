# Review Findings — Sub-module 9.14: Customer Service & Support (Module 9: eCommerce Management System)

- **Target App:** `apps/ecommerce/`
- **Sub-module:** 9.14 Customer Service & Support
- **Review Range:** `09e6bd0b18b2b5b7100e3982583d62734e7838ae...1c4ae804330e529a6bbae58c0fddf97c6ffa4c34`
- **Review Date:** 2026-11-01
- **Status:** Consolidated & Deduplicated

---

## Critical Findings

- [x] **C1** — Fatal Runtime TypeError on Form Validation (HTTP 500 and IDOR validation failure) in Support ModelForms — fixed in `9cd8eae7` fix(ecommerce): correct reject_foreign argument order in CustomerSupportTicketForm; `5b03572a` fix(ecommerce): correct reject_foreign argument order in OrderIssueClaimForm; `66498023` fix(ecommerce): correct reject_foreign argument order in CustomerSatisfactionSurveyForm
  - **Files:**
    - `apps/ecommerce/forms/CustomerSupport/CustomerSupportTickets.py:84-85`
    - `apps/ecommerce/forms/CustomerSupport/OrderIssueClaims.py:72-74`
    - `apps/ecommerce/forms/CustomerSupport/CustomerSatisfactionSurveys.py:65-67`
  - **Issue:** `reject_foreign` is called as `reject_foreign(self, "<field>", self.tenant)`. But `apps/ecommerce/forms/_common.py:23` defines `reject_foreign(form, cleaned, names)` iterating `for name in names:`. Passing `self.tenant` in 3rd position raises `TypeError: 'Tenant' object is not iterable` and crashes with HTTP 500 on any submission.
  - **Fix:** Replace calls with `reject_foreign(self, cleaned, ["customer", "order"])` (and matching lists for claim and survey).

- [x] **C2** — Stored XSS / DOM Injection via Inline `onerror` Event Handler in Claim Detail Template — fixed in `f399ebf2` fix(ecommerce): remove inline onerror handler in claim detail to prevent XSS
  - **File:** `templates/ecommerce/customer_support/claim/detail.html:80`
  - **Issue:** Direct string interpolation of `{{ claim.photo_evidence_url }}` into an inline JavaScript `onerror="...innerHTML='...<a href=\'{{ claim.photo_evidence_url }}\'>...'"` event handler enables stored XSS via crafted quote/script breakout payloads.
  - **Fix:** Remove the inline `onerror` attribute and JS DOM injection. Render the preview using a standard image container and rely on the already provided external link below.

---

## Important Findings

- [x] **I1** — Inexistent `grand_total` Attribute on `ticket.order` and `claim.order` causing Silent Blank Rendering — fixed in `d583a765` fix(ecommerce): reference total_amount instead of non-existent grand_total on ticket order; `d46433dd` fix(ecommerce): reference total_amount instead of non-existent grand_total on claim order
  - **Files:**
    - `templates/ecommerce/customer_support/ticket/detail.html:153`
    - `templates/ecommerce/customer_support/claim/detail.html:138`
  - **Issue:** `EcommerceOrder` defines `total_amount` (`grand_total` only exists on `Cart`). This causes order total to render silently blank (`Total: $ • Status: ...`).
  - **Fix:** Change `ticket.order.grand_total` and `claim.order.grand_total` to `.total_amount`.

- [x] **I2** — Deletion Audit Logging Records `object_id=None` across all 4 Delete Views — fixed in `6e8c5311` fix(ecommerce): record audit log before ticket deletion so object_id is preserved; `63588a61` fix(ecommerce): record audit log before knowledge base article deletion; `afcb2fd5` fix(ecommerce): record audit log before order issue claim deletion; `14e8b970` fix(ecommerce): record audit log before customer satisfaction survey deletion
  - **Files:**
    - `apps/ecommerce/views/CustomerSupport/CustomerSupportTickets.py:150-157`
    - `apps/ecommerce/views/CustomerSupport/KnowledgeBaseArticles.py:130-137`
    - `apps/ecommerce/views/CustomerSupport/OrderIssueClaims.py:131-138`
    - `apps/ecommerce/views/CustomerSupport/CustomerSatisfactionSurveys.py:132-139`
  - **Issue:** `write_audit_log` is called after `obj.delete()`. Django clears `obj.pk` to `None` upon deletion, so `AuditLog.object_id` is recorded as `None`.
  - **Fix:** Move `write_audit_log(...)` to execute before `obj.delete()`.

- [x] **I3** — Unscoped Database Update and Unnecessary Cache Flush in Knowledge Base Detail View — fixed in `25cca776` fix(ecommerce): scope view_count update to tenant and avoid cache-flushing refresh_from_db
  - **File:** `apps/ecommerce/views/CustomerSupport/KnowledgeBaseArticles.py:64-65`
  - **Issue:** `update(view_count=F("view_count") + 1)` is not scoped to `tenant=request.tenant`. Calling `article.refresh_from_db()` flushes `fields_cache` and triggers extra database queries.
  - **Fix:** Add `tenant=request.tenant` to the update query, increment `article.view_count += 1` in memory, and remove `refresh_from_db()`.

- [x] **I4** — Chained N+1 Queries in Customer Support Views via `CustomerAccountProfile.__str__` — fixed in `ac0913d7` perf(ecommerce): select_related customer__customer to eliminate N+1 queries in claim views; `c673c196` perf(ecommerce): select_related customer__customer to eliminate N+1 queries in survey views; `54385c08` perf(ecommerce): select_related customer__customer to eliminate N+1 queries in ticket views
  - **Files:**
    - `apps/ecommerce/views/CustomerSupport/OrderIssueClaims.py:17-19, 64`
    - `apps/ecommerce/views/CustomerSupport/CustomerSatisfactionSurveys.py:17-19, 64`
    - `apps/ecommerce/views/CustomerSupport/CustomerSupportTickets.py:65`
  - **Issue:** `CustomerAccountProfile.__str__` accesses `self.customer` (`core.Party`), causing extra queries unless `"customer__customer"` is pre-fetched.
  - **Fix:** Use `"customer__customer"` in `select_related` across list and detail views.

- [x] **I5** — Non-existent Utility Classes `text-primary` and `border-primary` in Templates (Lesson L13) — fixed in `053b8e22` fix(ecommerce): replace non-existent text-primary with text-brand in article list; `74fe5aef` fix(ecommerce): replace non-existent text-primary with text-brand in claim detail; `f27183c4` fix(ecommerce): replace non-existent text-primary with text-brand in claim list; `9bb529b5` fix(ecommerce): replace non-existent primary utility classes with brand classes in survey detail; `b84d1459` fix(ecommerce): replace non-existent text-primary with text-brand in survey list; `26ae9ed1` fix(ecommerce): replace non-existent text-primary with text-brand in ticket detail; `93745632` fix(ecommerce): replace non-existent text-primary with text-brand in ticket list
  - **Files:** `templates/ecommerce/customer_support/{ticket,article,claim,survey}/{list,detail}.html`
  - **Issue:** `text-primary` and `border-primary` do not exist in `theme.css`.
  - **Fix:** Replace with `text-brand` (or `text-blue-600`) and `border-brand-500` / `border-blue-600`.

- [x] **I6** — Dark Mode Contrast Issues on Hardcoded Slate Utilities in Cards — fixed in `ea6e3242` fix(ecommerce): add dark mode text utility variants in article detail; `4fec63ab` fix(ecommerce): add dark mode text utility variants in article form; `1391d1b3` fix(ecommerce): add dark mode text utility variants in article list; `f854aab2` fix(ecommerce): add dark mode text utility variants in claim detail; `659ba067` fix(ecommerce): add dark mode text utility variants in claim form; `c0ea0fdd` fix(ecommerce): add dark mode text utility variants in claim list; `5469c4a6` fix(ecommerce): add dark mode text utility variants in survey detail; `6d87d0d1` fix(ecommerce): add dark mode text utility variants in survey form; `8933f25f` fix(ecommerce): add dark mode text utility variants in survey list; `d606844e` fix(ecommerce): add dark mode text utility variants in ticket detail; `4066f1c4` fix(ecommerce): add dark mode text utility variants in ticket form; `5edc6c9d` fix(ecommerce): add dark mode text utility variants in ticket list
  - **Files:** `templates/ecommerce/customer_support/{ticket,article,claim,survey}/{list,detail,form}.html`
  - **Issue:** Text styled with `text-slate-900`, `text-slate-800`, `text-slate-700` inside `.card` elements without dark variants has poor contrast in dark theme.
  - **Fix:** Add `dark:text-slate-100` / `dark:text-slate-200` to headings and prominent labels.

- [x] **I7** — Missing Composite Indexes for High-Frequency Filter Combinations — fixed in `72573d9d` feat(ecommerce): add composite index on tenant and channel for CustomerSupportTicket; `4d970ee6` feat(ecommerce): add composite index on tenant and claim_type for OrderIssueClaim; `9d9679c5` feat(ecommerce): add composite index on tenant and sentiment for CustomerSatisfactionSurvey; `b4181d9e` feat(ecommerce): add composite index on tenant and target_audience for KnowledgeBaseArticle; `06e25f34` feat(ecommerce): add migration for 9.14 support composite indexes
  - **Files:** `apps/ecommerce/models/CustomerSupport/{CustomerSupportTickets,OrderIssueClaims,CustomerSatisfactionSurveys,KnowledgeBaseArticles}.py`
  - **Issue:** Hot filter queries lack composite indexes: `(tenant, channel)` on tickets, `(tenant, claim_type)` on claims, `(tenant, sentiment)` on surveys, and `(tenant, target_audience)` on articles.
  - **Fix:** Add `models.Index` definitions to `Meta.indexes`, generate migration, and apply it.

- [x] **I8** — Missing Non-Negative Validation on Financial Claim Amounts — fixed in `842c4fa9` feat(ecommerce): add MinValueValidator to claimed_amount and approved_amount in OrderIssueClaim; `75f1af9a` fix(ecommerce): validate claimed_amount and approved_amount are non-negative in OrderIssueClaimForm; `0d1dd66f` feat(ecommerce): add migration for non-negative claim amount validators
  - **Files:**
    - `apps/ecommerce/models/CustomerSupport/OrderIssueClaims.py:65-76`
    - `apps/ecommerce/forms/CustomerSupport/OrderIssueClaims.py:37-38`
  - **Issue:** Negative amounts are not prevented on `claimed_amount` and `approved_amount`.
  - **Fix:** Add `MinValueValidator(Decimal("0.00"))` to model fields and validate non-negative in `OrderIssueClaimForm.clean()`.

- [x] **I9** — CSAT and NPS Rating Boundary Mismatch and Detractor Validation — fixed in `98ea72e2` feat(ecommerce): adjust rating_score MinValueValidator to 0 to support NPS detractor ratings; `c12c49cf` fix(ecommerce): enforce CSAT 1-5 and NPS 0-10 bounds in CustomerSatisfactionSurveyForm; `81f684ef` feat(ecommerce): add migration for survey rating_score minimum bound of 0
  - **Files:**
    - `apps/ecommerce/models/CustomerSupport/CustomerSatisfactionSurveys.py:55-58`
    - `apps/ecommerce/forms/CustomerSupport/CustomerSatisfactionSurveys.py:34`
  - **Issue:** CSAT surveys allow scores up to 10 (>5 breaks UI `8 / 5`), while NPS enforces min 1 which rejects valid detractor rating of 0.
  - **Fix:** Set model `MinValueValidator(0)` and `MaxValueValidator(10)`, and in `CustomerSatisfactionSurveyForm.clean()` enforce 1-5 for CSAT and 0-10 for NPS.

- [x] **I10** — Automatic Sentiment Recalculation Overwrites Staff Overrides — fixed in `071b9524` fix(ecommerce): prevent auto-sentiment from overwriting staff manual overrides
  - **File:** `apps/ecommerce/models/CustomerSupport/CustomerSatisfactionSurveys.py:96-110`
  - **Issue:** `CustomerSatisfactionSurvey.save()` unconditionally recalculates `sentiment`, wiping out manual supervisor adjustments.
  - **Fix:** Only compute auto-sentiment if `not self.sentiment` or if `self.sentiment == "neutral"`.

- [x] **I11** — Survey List NPS Score Color Thresholds Contradict Sentiment — fixed in `626ab07e` fix(ecommerce): align survey list rating score color styling with sentiment
  - **File:** `templates/ecommerce/customer_support/survey/list.html:111-120`
  - **Issue:** Score color conditional uses `>= 8` green and `>= 6` amber, conflicting with NPS definitions.
  - **Fix:** Align with `detail.html` by styling the score directly via `survey.sentiment` (`text-green-700` if positive, `text-amber-600` if neutral, `text-red-700` if negative).

---

## Minor Findings

- [x] **M1** — Intra-Tenant Cross-Shopper Consistency Validation in Forms — fixed in `4f7f0cfa` fix(ecommerce): validate customer and order consistency in CustomerSupportTicketForm; `0e2c5219` fix(ecommerce): validate customer and order consistency in OrderIssueClaimForm; `302420aa` fix(ecommerce): validate customer and order consistency in CustomerSatisfactionSurveyForm
  - **Files:** `apps/ecommerce/forms/CustomerSupport/{CustomerSupportTickets,OrderIssueClaims,CustomerSatisfactionSurveys}.py`
  - **Issue:** When both `customer` and `order` are selected, `order.customer_id` should match `customer.customer_id`.
  - **Fix:** In `clean()`, raise validation error if both are provided and `order.customer_id != customer.customer_id`.

- [x] **M2** — Sidebar Live Chat Link Missing Query Filter Parameter — fixed in `6f07b971` fix(core): add channel=chat query param to Live Chat sidebar route in LIVE_LINKS 9.14
  - **File:** `apps/core/navigation.py:2788`
  - **Issue:** `"Live Chat & Chatbot"` in `LIVE_LINKS["9.14"]` links to ticket list without `?channel=chat`.
  - **Fix:** Update route target to `"ecommerce:customersupportticket_list?channel=chat"`.

- [x] **M3** — Ticket Status Badges in List View Missing Default Fallback — fixed in `9df3658a` fix(ecommerce): add explicit cancelled check and default status badge fallback in ticket list
  - **File:** `templates/ecommerce/customer_support/ticket/list.html:140-155`
  - **Issue:** Status badge checks lack fallback `{% else %}` rendering `{{ ticket.get_status_display }}`.
  - **Fix:** Add `{% elif ticket.status == 'cancelled' %}` and `{% else %}<span class="badge badge-slate">{{ ticket.get_status_display }}</span>{% endif %}`.

- [x] **M4** — KB Article List Table Header Reads `Helpful Ratio` but Displays Raw Count — fixed in `4f535ff1` fix(ecommerce): rename table header Helpful Ratio to Helpful / Unhelpful in article list
  - **File:** `templates/ecommerce/customer_support/article/list.html:81`
  - **Issue:** Column header says `Helpful Ratio` while cell renders `{{ article.helpful_votes }} / {{ article.unhelpful_votes }}`.
  - **Fix:** Change column header to `Helpful / Unhelpful`.

- [x] **M5** — Ticket `resolved_at` Not Cleared on Reopening — fixed in `03fe6748` fix(ecommerce): clear resolved_at timestamp when reopening support ticket
  - **File:** `apps/ecommerce/models/CustomerSupport/CustomerSupportTickets.py:118-120`
  - **Issue:** Reopening a ticket from `resolved` to `open` retains the old `resolved_at` timestamp.
  - **Fix:** Set `self.resolved_at = None` if `self.status not in ["resolved", "closed"]`.

- [x] **M6** — Physical Directional Classes in Survey Detail and Ticket List Violate RTL Layout — fixed in `95b40b85` fix(ecommerce): replace physical border-l-4 and pl-4 with logical border-s-4 and ps-4 in survey detail; `5e621644` fix(ecommerce): replace physical ml-1 with logical ms-1 for SLA Breached badge in ticket list
  - **Files:** `templates/ecommerce/customer_support/survey/detail.html:63`, `ticket/list.html:137`
  - **Issue:** Uses `border-l-4`, `pl-4`, `ml-1`.
  - **Fix:** Replace with logical `border-s-4`, `ps-4`, `ms-1`.

- [x] **M7** — Detail Pages Lack Explicit "Back to List" Action in Header — fixed in `999d9ed5` fix(ecommerce): add Back to List action in ticket detail header; `943aa3a7` fix(ecommerce): add Back to List action in article detail header; `ac9a725e` fix(ecommerce): add Back to List action in claim detail header; `a2cc2c0b` fix(ecommerce): add Back to List action in survey detail header
  - **Files:** `templates/ecommerce/customer_support/{ticket,article,claim,survey}/detail.html`
  - **Issue:** Detail pages only have Edit and Delete buttons in `.page-actions`.
  - **Fix:** Add `<a href="{% url 'ecommerce:<entity>_list' %}" class="btn btn-outline"><i data-lucide="arrow-left"></i> Back</a>`.

- [x] **M8** — Unconstrained User Query in Ticket List Filter — fixed in `47f30cdc` perf(ecommerce): constrain User query in ticket list with only id, username, and names
  - **File:** `apps/ecommerce/views/CustomerSupport/CustomerSupportTickets.py:59`
  - **Issue:** `User.objects.filter(is_active=True)` retrieves all auth columns.
  - **Fix:** Add `.only("id", "username", "first_name", "last_name")`.

- [x] **M9** — Large Markdown `content` Column Loaded on KB Article List View — fixed in `3394f10a` perf(ecommerce): defer heavy content markdown column in article list view
  - **File:** `apps/ecommerce/views/CustomerSupport/KnowledgeBaseArticles.py:17`
  - **Issue:** Full article markdown body fetched during list pagination.
  - **Fix:** Add `.defer("content")`.

- [x] **M10** — Photo Evidence URL Missing Explicit URL Scheme Validation — fixed in `b979046f` feat(ecommerce): add URLValidator restricting scheme to http and https on photo_evidence_url; `fc80c931` feat(ecommerce): add migration for photo_evidence_url URLValidator
  - **File:** `apps/ecommerce/models/CustomerSupport/OrderIssueClaims.py:83`
  - **Issue:** `photo_evidence_url` doesn't restrict schemes to `["http", "https"]`.
  - **Fix:** Add `validators=[URLValidator(schemes=["http", "https"])]`.
