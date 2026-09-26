# Review Findings: Sub-module 8.5 Quote & Proposal Management (CPQ)

Base commit: `35a9d1d9be1b6035ae0e1312eafb023fd947f883`
Head commit: `aec817df30d4c2d4eb784363ae8953e2f0f61239`

Reviewers executed serially:
1. `code-reviewer`
2. `explorer`
3. `frontend-reviewer`
4. `performance-reviewer`
5. `qa-smoke-tester`
6. `security-reviewer`

---

## Critical

- [x] **C1**: `apps/sales/views/QuoteProposalCPQ/*.py` — Universal `write_audit_log` parameter transposition across all mutating views (`write_audit_log(user, obj, action, changes=None, tenant=None)` called as `write_audit_log(request.user, "action_string", "ModelName", obj.id, changes_str)`), crashing with `AttributeError` on every POST workflow. (fixed: corrected parameter ordering passing instance `obj` and structured changes dictionary across all CPQ mutating views)
- [x] **C2**: `apps/sales/forms/QuoteProposalCPQ/CPQQuotes.py:51-52` — `CPQQuoteForm.__init__` filters `Party.objects.filter(tenant=self.tenant, is_active=True)`, raising `FieldError` because `Party` has no `is_active` field. Crashes quote create and edit with HTTP 500. (fixed: removed non-existent `is_active` filter from `Party` querysets in `CPQQuoteForm.__init__`)
- [ ] **C3**: `apps/sales/cpq_services.py:415-440` — SCM `SalesOrder` / `SalesOrderLine` spine contract mismatch in `cpq_convert_to_sales_order`: `currency` must be `Currency` instance, field name is `total` not `total_amount`, no `created_by` on `SalesOrder`, line has `sales_order` not `order`, `quantity_ordered` not `quantity`, `line_total` is property not DB column, no `notes` column on line, requires `quote.account` validation.
- [ ] **C4**: `apps/sales/views/QuoteProposalCPQ/QuoteOperations.py:419-469` — Guided selling wizard crashes on `Product.list_price` (`AttributeError`, model field is `unit_price`) and crashes with `IntegrityError` when creating quote without opportunity due to `currency=None` on non-nullable `CPQQuote.currency`.
- [ ] **C5**: `apps/sales/cpq_services.py:285-395` & `templates/sales/quote_proposal_cpq/operations/proposal_preview.html:36` — Stored XSS in proposal generation via unescaped dynamic model fields (`quote.signer_name`, `line.description`, `quote.terms_and_conditions`) rendered via `{{ proposal_html|safe }}`.
- [ ] **C6**: `templates/sales/quote_proposal_cpq/**/*.html` — Nullable FK `owner` dereferenced inside `default` filter argument (`{{ q.owner.get_full_name|default:q.owner.username }}` in `cpqquote/list.html:183`, `approval_queue.html:112`, `approval_action.html:46`, `portal.html:62,176`), causing 500 when `owner` is None (Lesson L10).
- [ ] **C7**: `apps/sales/views/QuoteProposalCPQ/QuoteOperations.py:288-336` — Public portal lacks view-level status and expiration guards on `quote_portal_sign` and `quote_portal_toggle_line` (allows signing or modifying draft, rejected, or expired quotes).
- [ ] **C8**: `apps/sales/views/QuoteProposalCPQ/QuoteOperations.py:38-144` — Missing view-level status guards: `quote_submit_approval` lacks check for `quote.status in ["draft", "rejected"]`; `quote_approval_action` lacks check for `quote.approval_status == "pending"`.
- [ ] **C9**: `apps/sales/views/QuoteProposalCPQ/QuoteOperations.py:414-416` — Guided selling wizard allows line injection and recalculation on locked/approved quotes when `quote_id` is supplied without checking `quote.is_editable`.
- [ ] **C10**: `apps/sales/views/QuoteProposalCPQ/QuoteOperations.py:184-210` — Unbounded $O(N)$ N+1 query loop and missing pagination in `quote_version_list` (executes individual query per quote group family).
- [ ] **C11**: `apps/sales/views/QuoteProposalCPQ/CPQQuotes.py:134`, `QuoteOperations.py:270`, `cpq_services.py:62-66` — Passive write amplification on HTTP GET: `cpq_recalc_quote_totals(quote, save=True)` triggers sequential `line.save()` updates on read requests.
- [ ] **C12**: `apps/sales/models/QuoteProposalCPQ/QuoteApprovalRules.py:88-91` & `apps/sales/cpq_services.py:118-121` — Approval rule evaluation executes repeated `quote.lines.filter(...)` per active rule instead of computing `max_line_disc` once.

---

## Important

- [ ] **I1**: `apps/sales/models/QuoteProposalCPQ/*.py` — Missing database-level unique constraints on `(tenant, number)` for `CPQQuote`, `ProductBundleOption`, and `QuoteApprovalRule`.
- [ ] **I2**: `apps/sales/views/QuoteProposalCPQ/*.py` — Unhandled 500 `ValueError` on non-numeric query parameters (`?opportunity=abc`, `?bundle=xyz`) in list and guided selling views. Guard with `.isdigit()`.
- [ ] **I3**: `templates/sales/quote_proposal_cpq/**/*.html` — Incomplete query parameter preservation on pagination links in `cpqquote/list.html`, `productbundleoption/list.html`, `quoteapprovalrule/list.html`.
- [ ] **I4**: `templates/sales/quote_proposal_cpq/**/*.html` — Non-existent theme CSS class `badge-purple` used in `cpqquote/list.html`, `cpqquote/detail.html`, `productbundleoption/list.html`, `version_list.html`. Replace with `badge-info`.
- [ ] **I5**: `apps/sales/views/QuoteProposalCPQ/QuoteOperations.py:451-456` — Hand-parsed numeric input in guided selling lacks `is_finite()` and non-positive check for `qty`.
- [ ] **I6**: `apps/sales/views/QuoteProposalCPQ/QuoteOperations.py:410-478` — Multi-model creation in guided selling wizard is not wrapped in `transaction.atomic()`.
- [ ] **I7**: `apps/sales/views/QuoteProposalCPQ/CPQQuotes.py:200-206` — Incomplete status guard on `cpq_quote_delete`: only checks `converted`, allowing deletion of approved, in-review, or presented quotes.
- [ ] **I8**: `templates/sales/quote_proposal_cpq/**/*.html` — Missing POST-Delete action in `cpqquote/detail.html` and `cpqquoteline/detail.html`; missing View (`eye`) action in `cpqquoteline/list.html`.
- [ ] **I9**: `apps/sales/views/QuoteProposalCPQ/*.py` — Missing `select_related("parent_line")` in line queries and missing `select_related("currency")` in rule detail.
- [ ] **I10**: `apps/sales/views/QuoteProposalCPQ/*.py` — Multiple independent `COUNT(*)` queries for dashboard stat cards instead of unified conditional `.aggregate()`.
- [ ] **I11**: `apps/sales/cpq_services.py:175-226, 430-438` — Use `bulk_create` / `bulk_update` in `cpq_create_revision` and `cpq_convert_to_sales_order` instead of per-row insert loops.
- [ ] **I12**: `apps/sales/models/QuoteProposalCPQ/*.py` — Missing composite database indexes for `(tenant, number)`, `(tenant, approval_status)`, and `(tenant, is_active)`.
- [ ] **I13**: `apps/sales/views/QuoteProposalCPQ/QuoteOperations.py:76, 221, 343` — Operational dashboards (`quote_approval_queue`, `quote_proposal_board`, `quote_conversion_board`) lack pagination.
- [ ] **I14**: `apps/sales/forms/QuoteProposalCPQ/*.py` — Missing `required=False` on optional form fields (`min_margin_pct`, `list_price`, `discount_pct`, `tax_pct`).
- [ ] **I15**: `apps/sales/views/QuoteProposalCPQ/QuoteOperations.py:252-255` — State mutation on HTTP GET in `quote_generate_proposal`: auto-transitions status to `presented`. Keep preview read-only.

---

## Minor

- [ ] **M1**: `apps/sales/views/QuoteProposalCPQ/CPQQuoteLines.py:15-32` — Remove dead metric count queries in `cpq_quote_line_list` where `stats` is unused in template.
- [ ] **M2**: `apps/sales/models/QuoteProposalCPQ/*.py` — Chained `__str__` queries on `CPQQuoteLine` (`self.quote.number`) and `ProductBundleOption` (`self.bundle_product.name`).
- [ ] **M3**: `templates/sales/quote_proposal_cpq/**/*.html` — Missing standard `.empty-state` wrapper in `cpqquoteline/list.html` and `proposal_board.html`.
- [ ] **M4**: `templates/sales/quote_proposal_cpq/cpqquote/list.html:167` & `detail.html:30` — Render `draft` status with canonical `badge-info` instead of fallback `badge-muted`.
- [ ] **M5**: `apps/sales/cpq_services.py:239-240` — Version comparison dictionary keyed strictly by `description` is lossy when identical descriptions exist.
- [ ] **M6**: `apps/sales/views/QuoteProposalCPQ/QuoteOperations.py:485` — Unvalidated `preselect_quote_id` passed to template context without tenant ownership check.
- [ ] **M7**: `apps/sales/views/QuoteProposalCPQ/QuoteOperations.py:167-169` — Add cross-record revision check in `quote_compare_versions` (`quote_a.quote_group_id == quote_b.quote_group_id`).
- [ ] **M8**: `apps/sales/forms/QuoteProposalCPQ/CPQQuotes.py:29` — Exclude `owner` from `CPQQuoteForm` or guard ownership reassignment to tenant admins.
- [ ] **M9**: `apps/sales/management/commands/seed_sales.py` — Move 8.5 CPQ seeding into its own helper `_seed_cpq` and update completion/help output strings.
