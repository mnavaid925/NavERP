# Review Findings — Sub-module 9.19: Integration & API Ecosystem (Module 9: eCommerce Management System, `ecommerce`)

- **Sub-module:** 9.19 Integration & API Ecosystem
- **Module:** 9 eCommerce Management System (`ecommerce`)
- **Review Range:** `636b2d8cf7801d9533df988cb907c334b25ed034...53dd659d`
- **Date:** 2026-11-03
- **Phase:** 4 Review (All 6 Reviewers Completed & Deduplicated)
- **Status:** Consolidated — Ready for Phase 5 (`code-fixer`)

---

## Consolidated Action Register (Prioritized: Critical → Important → Minor)

### Critical Findings (Must Fix First)

#### [ ] C1: Plaintext Secret Exposure in HTML DOM via `forms.PasswordInput(render_value=True)`
- **Files:**
  - `apps/ecommerce/forms/IntegrationApi/EcommerceConnectors.py` (Lines 39–42)
  - `apps/ecommerce/forms/IntegrationApi/WebhookSubscriptions.py` (Lines 39–45)
- **Severity:** Critical (CWE-312 / Secret Leakage)
- **Problem:** Both forms specify `PasswordInput(render_value=True)`, injecting third-party API secrets and webhook HMAC signing keys in cleartext into the HTML DOM and source code on edit views.
- **Remediation:**
  1. Change `render_value=True` to `render_value=False` (the default) on both widgets.
  2. Implement `clean_api_secret` in `EcommerceConnectorForm` and update `clean_secret_key` in `WebhookSubscriptionForm` to preserve the existing database secret if submitted blank on edit.
- **Status:** `[ ] open`

#### [ ] C2: Missing `@tenant_admin_required` Gate on Privileged Key & Connector Mutations
- **Files:**
  - `apps/ecommerce/views/IntegrationApi/ApiCredentials.py` (Lines 89, 139, 171, 192)
  - `apps/ecommerce/views/IntegrationApi/EcommerceConnectors.py` (Lines 154, 191, 223, 244)
  - `apps/ecommerce/views/IntegrationApi/WebhookSubscriptions.py` (Lines 85, 121, 153, 174)
- **Severity:** Critical (CWE-285 / Privilege Escalation, Lesson L27)
- **Problem:** All create, edit, delete, test, and revoke endpoints across API Credentials, Connectors, and Webhooks are decorated only with `@login_required`. Any authenticated tenant member can issue full admin server API keys, revoke production credentials, or alter gateway connections.
- **Remediation:** Import `tenant_admin_required` from `apps.core.decorators` and apply to all mutation views:
  - `api_credential_create`, `api_credential_edit`, `api_credential_delete`, `api_credential_revoke`
  - `ecommerce_connector_create`, `ecommerce_connector_edit`, `ecommerce_connector_delete`, `ecommerce_connector_test_connection`
  - `webhook_subscription_create`, `webhook_subscription_edit`, `webhook_subscription_delete`, `webhook_subscription_ping`
- **Status:** `[ ] open`

---

### Important Findings

#### [ ] I1: AuditLog Action Verb Exceeds `varchar(10)` Constraint
- **File:** `apps/ecommerce/views/IntegrationApi/EcommerceConnectors.py` (Lines 253–259)
- **Severity:** Important (Runtime Warning / Data Truncation)
- **Problem:** `action="test_connection"` is 15 characters, exceeding `AuditLog.action` (`varchar(10)`). The helper emits an error log and truncates the verb to `"test_conne"`.
- **Remediation:** Change to `action="test"` and put `"action_type": "test_connection"` in `changes`:
  ```python
  write_audit_log(
      request.user,
      connector,
      "test",
      changes={"action_type": "test_connection", "health_status": "healthy"},
      tenant=request.tenant,
  )
  ```
- **Status:** `[ ] open`

#### [ ] I2: Comma-Separated Scope Splitting Fails in Template
- **Files:**
  - `apps/ecommerce/models/IntegrationApi/ApiCredentials.py`
  - `templates/ecommerce/integration_api/api_credential/detail.html` (Lines 112–115)
- **Severity:** Important (Template Rendering Defect)
- **Problem:** `credential.scopes.split` defaults to whitespace splitting rather than comma splitting, rendering comma-separated scopes as one monolithic badge.
- **Remediation:** Add `@property def scopes_list(self): return [s.strip() for s in (self.scopes or "").split(",") if s.strip()]` on `ApiCredential` and iterate over `credential.scopes_list` in template.
- **Status:** `[ ] open`

#### [ ] I3: Connector List View: Missing Provider Dropdown and Pagination Parameter Loss
- **Files:**
  - `templates/ecommerce/integration_api/ecommerce_connector/list.html` (Lines 61–92, 218–228)
- **Severity:** Important (Filter Feature Omission & State Loss)
- **Problem:** The view supports filtering by `provider`, but the template filter `<form>` lacks `<select name="provider">`. Pagination links drop active `provider_filter`.
- **Remediation:** Add `<select name="provider">` in the filter bar and append `{% if provider_filter %}&provider={{ provider_filter }}{% endif %}` to pagination controls.
- **Status:** `[ ] open`

#### [ ] I4: Sync Job List View: Missing Direction and Trigger Dropdowns and Pagination Parameter Loss
- **Files:**
  - `templates/ecommerce/integration_api/integration_sync_job/list.html` (Lines 61–100, 221–231)
- **Severity:** Important (Filter Feature Omission & State Loss)
- **Problem:** The view filters by `direction` and `trigger_type`, but the template filter `<form>` lacks dropdowns for either. Pagination links drop active `direction_filter` and `trigger_filter`.
- **Remediation:** Add `<select name="direction">` and `<select name="trigger">` dropdowns to the filter bar and preserve them in pagination links.
- **Status:** `[ ] open`

#### [ ] I5: Server-Side Request Forgery (SSRF) Surface in Webhook and Connector URLs
- **Files:**
  - `apps/ecommerce/forms/IntegrationApi/WebhookSubscriptions.py` (Lines 67–73)
  - `apps/ecommerce/forms/IntegrationApi/EcommerceConnectors.py`
- **Severity:** Important (CWE-918 / SSRF Vector)
- **Problem:** `clean_target_url` only checks `http://` / `https://` without restricting loopback (`127.0.0.1`, `::1`), metadata (`169.254.169.254`), or private RFC 1918 subnets (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`). `EcommerceConnectorForm` lacks `clean_base_url`.
- **Remediation:** Implement defensive URL validation using `urllib.parse.urlparse` and `ipaddress.ip_address` to block localhost, metadata, and private IP ranges in both forms.
- **Status:** `[ ] open`

#### [ ] I6: Revocation Lifecycle Bypass and Tier Escalation in `ApiCredentialForm`
- **File:** `apps/ecommerce/forms/IntegrationApi/ApiCredentials.py` (Lines 8–31)
- **Severity:** Important (CWE-642 / State Manipulation)
- **Problem:** `status` can be changed from `"revoked"` back to `"active"` on edit, bypassing revocation. `tier` can be edited on existing instances, elevating storefront public keys to admin server keys.
- **Remediation:** In `clean_status`, forbid un-revoking a `"revoked"` credential. On edit (`if self.instance and self.instance.pk`), make `tier` disabled/read-only.
- **Status:** `[ ] open`

#### [ ] I7: Inadvertent Overwriting/Regeneration of Webhook Secret Keys
- **File:** `apps/ecommerce/forms/IntegrationApi/WebhookSubscriptions.py` (Lines 86–90)
- **Severity:** Important (Business Logic Invalidation)
- **Problem:** `clean_secret_key` generates a new random key whenever the field is empty, wiping out the existing HMAC secret on edit.
- **Remediation:** Preserve `self.instance.secret_key` when left blank on edit:
  ```python
  def clean_secret_key(self):
      val = self.cleaned_data.get("secret_key", "").strip()
      if not val:
          if self.instance and self.instance.pk and self.instance.secret_key:
              return self.instance.secret_key
          val = f"whsec_{secrets.token_hex(24)}"
      return val
  ```
- **Status:** `[ ] open`

#### [ ] I8: Missing `select_related` on Foreign Keys in Detail Views
- **Files:**
  - `apps/ecommerce/views/IntegrationApi/IntegrationSyncJobs.py` (Lines 98–106)
  - `apps/ecommerce/views/IntegrationApi/ApiCredentials.py` (Lines 74–82)
- **Severity:** Important (N+1 / Deferred Query Overhead)
- **Problem:** `integration_sync_job_detail` triggers deferred queries for `connector`, `triggered_by`, and `parent_job`. `api_credential_detail` triggers a deferred query for `created_by`.
- **Remediation:** Pass `select_related=("connector", "triggered_by", "parent_job")` and `select_related=("created_by",)` to `ecommerce_object`.
- **Status:** `[ ] open`

#### [ ] I9: Missing Composite Index on `(tenant, -created_at)` for `IntegrationSyncJob`
- **File:** `apps/ecommerce/models/IntegrationApi/IntegrationSyncJobs.py` (Lines 146–160)
- **Severity:** Important (Database Query Performance)
- **Problem:** Sync job lists and hub queries filter by `tenant` and order by `-created_at`. Without `(tenant, -created_at)`, PostgreSQL and MySQL cannot perform a reverse index scan and must filesort large job tables.
- **Remediation:** Add `models.Index(fields=["tenant", "-created_at"], name="idx_esyj_ten_created")` to `IntegrationSyncJob.Meta.indexes`.
- **Status:** `[ ] open`

---

### Minor Findings

#### [ ] M1: Undefined Theme Badge Class `.badge-purple`
- **Files:**
  - `templates/ecommerce/integration_api/integration_api_hub.html` (Line 309)
  - `templates/ecommerce/integration_api/api_credential/list.html` (Line 129)
- **Problem:** `.badge-purple` is not declared in `static/css/theme.css`.
- **Remediation:** Replace with `.badge-info` (primary indigo accent) or `.badge-slate`.
- **Status:** `[ ] open`

#### [ ] M2: Redundant B-Tree Index on `ApiCredential.client_id`
- **File:** `apps/ecommerce/models/IntegrationApi/ApiCredentials.py` (Lines 117–121)
- **Problem:** `client_id` has `unique=True`. `models.Index(fields=["client_id"], name="idx_eapc_client_id")` creates a duplicate index.
- **Remediation:** Remove `idx_eapc_client_id` from `Meta.indexes`.
- **Status:** `[ ] open`

#### [ ] M3: Defense-in-Depth Form Foreign Key Validation with `reject_foreign`
- **File:** `apps/ecommerce/forms/IntegrationApi/IntegrationSyncJobs.py` (Lines 58–64)
- **Problem:** `IntegrationSyncJobForm` lacks `reject_foreign` in `clean()` for parity with standard NavERP form hardening.
- **Remediation:** Add `reject_foreign(self, self.cleaned_data, ["connector"])` in `clean()`.
- **Status:** `[ ] open`

#### [ ] M4: Unbounded Query Evaluation on `child_retries` in `integration_sync_job_detail`
- **File:** `apps/ecommerce/views/IntegrationApi/IntegrationSyncJobs.py` (Line 100)
- **Problem:** `sync_job.child_retries.all().order_by("-created_at")` is un-sliced.
- **Remediation:** Limit retry history to `[:20]`.
- **Status:** `[ ] open`

#### [ ] M5: Over-Fetching on `connectors` Dropdown Queryset
- **File:** `apps/ecommerce/views/IntegrationApi/IntegrationSyncJobs.py` (Line 62)
- **Problem:** Filter dropdown loads full instances with large text fields.
- **Remediation:** Use `.only("id", "name")`.
- **Status:** `[ ] open`

#### [ ] M6: Redundant `COUNT(*)` Query Execution Across All List Views
- **Files:** `apps/ecommerce/views/IntegrationApi/{EcommerceConnectors,IntegrationSyncJobs,WebhookSubscriptions,ApiCredentials}.py`
- **Problem:** `Paginator` recalculates `count` dynamically even though `.aggregate(total_count=...)` already ran.
- **Remediation:** Pre-seed `paginator._count = total_count`.
- **Status:** `[ ] open`

#### [ ] M7: Missing Upper Bound on Timeout and Retries (DoS Hardening)
- **Files:**
  - `apps/ecommerce/forms/IntegrationApi/EcommerceConnectors.py`
  - `apps/ecommerce/forms/IntegrationApi/IntegrationSyncJobs.py`
- **Problem:** `timeout_seconds` and `max_retries` allow arbitrarily high integers.
- **Remediation:** Enforce reasonable max limits (timeout max 300s, retries max 20).
- **Status:** `[ ] open`

#### [ ] M8: Unrestricted Custom Request Headers & CRLF Injection Risk in `WebhookSubscription`
- **File:** `apps/ecommerce/forms/IntegrationApi/WebhookSubscriptions.py` (Lines 75–84)
- **Problem:** `clean_custom_headers` does not check for newline characters (`\r`, `\n`) or restrict hop-by-hop headers.
- **Remediation:** Validate that header keys and values are strings without newlines and block hop-by-hop headers.
- **Status:** `[ ] open`

#### [ ] M9: Icon-Only Action Buttons Screen Reader Accessibility
- **Files:**
  - `templates/ecommerce/integration_api/ecommerce_connector/list.html`
  - `templates/ecommerce/integration_api/integration_sync_job/list.html`
  - `templates/ecommerce/integration_api/webhook_subscription/list.html`
  - `templates/ecommerce/integration_api/api_credential/list.html`
- **Problem:** Icon-only action links have `title` but lack `aria-label`.
- **Remediation:** Add matching `aria-label` attributes to icon-only action links.
- **Status:** `[ ] open`

#### [~] M10: Third-Party Secret Storage Encryption at Rest (Deferred)
- **Reason:** Architectural hardening recommendation for production deployment; tracked in gaps file (`gaps-ecommerce-9.19.md`).
- **Status:** `[~] skipped — deferred to production security hardening / envelope encryption pass`

#### [~] M11: Missing `issued_to_party` FK on `ApiCredential` (Deferred)
- **Reason:** Module 0 spine integration enhancement; tracked in gaps file (`gaps-ecommerce-9.19.md`).
- **Status:** `[~] skipped — deferred to core party B2B wholesale expansion`

---

## Review Passes Summary Log

- **Pass 1 (Code Reviewer):** Analyzed models, forms, views, URLs, admin, navigation, seeder. Reported AuditLog length, scope splitting, filter omissions, SSRF, badge class.
- **Pass 2 (Explorer Reviewer):** Verified architecture, packaging, live link routes, multi-tenancy contracts. Identified redundant index on client_id, confirmed scope split and filter omissions.
- **Pass 3 (Frontend Reviewer):** Audited 13 templates for design-system compliance, comment leaks, None-safety, CSRF coverage. Flagged undefined `.badge-purple`, missing filter dropdowns, and pagination filter loss.
- **Pass 4 (Performance Reviewer):** Analyzed ORM queries, N+1 patterns, indexes, and database aggregation. Found missing `select_related` on detail views, missing composite index on sync jobs, and duplicate index on client_id.
- **Pass 5 (QA Smoke Tester):** Swept all 17 endpoints and 25 view actions runtime via test client. Zero 500s, 100% IDOR isolation (404), confirmed AuditLog runtime error log and template scope split bug.
- **Pass 6 (Security Reviewer):** Audited multi-tenancy, auth decorators, CSRF, secrets, SSRF, mass assignment. Found critical DOM secret leak (`render_value=True`), missing `@tenant_admin_required`, SSRF vectors, and credential lifecycle bypass.
