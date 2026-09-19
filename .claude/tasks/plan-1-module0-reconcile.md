# Module 0 reconcile — Plan 1 Step 0

**Started:** 2026-09-19 · **Scope:** classify every unmapped bullet of module 0's 7 LIVE sub-modules
before building anything new. **Status:** 0.1 done; 0.2/0.3/0.5/0.7/0.9/0.14 still to classify.

## Method

For each of module 0's live sub-modules, compare its `### N.M` bullets in `NavERP.md` against its
`LIVE_LINKS["N.M"]` keys. An unmapped bullet is either **(a) built in code but never surfaced as a
sidebar leaf**, or **(b) genuinely absent** — never assume either; grep the app for the feature and
classify. `LIVE_LINKS` alone is not evidence a feature exists, and its absence is not evidence it does
not (7.10 shipped a `LIVE_LINKS` entry over 21 missing templates).

## Coverage table (from `LIVE_LINKS`, 2026-09-19)

| sub-module | bullets | mapped | verdict |
|---|---|---|---|
| 0.1 Tenant & Subscription | 5 | 4 → **5** | **DONE — see below** |
| 0.2 Identity & Access Management | 5 | 2 → **5** | **DONE — see below** |
| 0.3 RBAC & Permissions | 5 | 1 | not yet classified |
| 0.5 User & Organization | 5 | 2 | not yet classified |
| 0.7 Data Security & Encryption | 5 | 1 | not yet classified |
| 0.9 Audit Trail & Activity Logging | 5 | 1 | not yet classified |
| 0.14 Master Data & Reference Config | 5 | 1 | not yet classified |

`NavERP.md:90-96` claims IAM/RBAC/User&Org/Audit are "substantially realized by `accounts` + `core`".
That is a claim, not a finding — each of the 24 unmapped bullets needs the same treatment 0.1 got below.

---

## 0.1 Tenant & Subscription Management — CLOSED OUT 2026-09-19

**Verdict: 4 of 5 bullets were genuinely done; the 5th was realized but unsurfaced; and two
sub-features named by bullets 1–2 were genuinely absent.** So this was not "one nav line" — it was two
real gaps plus a surfacing gap.

### Bullet-by-bullet

| bullet | sub-feature | verdict |
|---|---|---|
| 1 Tenant Onboarding | self-service registration | **built** — `TenantRegisterForm` in `accounts` |
| | **domain provisioning** | **ABSENT** → built (see gap 1) |
| | initial configuration wizard | **built** — `tenants:onboarding` |
| 2 Subscription & Billing | plan management | **built** — `Subscription` |
| | **usage metering** | **ABSENT** → built (see gap 2) |
| | invoicing | **built** — `SubscriptionInvoice` |
| | payment gateway | **built** — Stripe checkout + webhook |
| 3 Tenant Isolation & Security | database/schema isolation | **built, architectural** — shared schema + tenant FK + `core.middleware.TenantMiddleware` |
| | encryption keys | **built but surfaced under 0.7** — `tenants:encryptionkey_list` is 0.7's leaf |
| | cross-tenant leak prevention | **built** — per-view scoping, tested in every module's security lane |
| | *a 0.1 surface for the bullet* | **ABSENT** → built (see gap 3) |
| 4 Custom Branding | white-label, logos, themes | **built** — `BrandingSetting` |
| | per-tenant email templates | **partial** — only `email_from_name` + `email_footer`; full templating NOT built (belongs to 0.12) |
| 5 Tenant Health Monitoring | resource usage tracking | **built** — `users/storage_mb/api_calls/db_rows/uptime_pct` |
| | audit logs | **built** — `core.AuditLog` |
| | performance alerts | **built** — `ok/warning/critical` status |

### Gaps closed

1. **Domain provisioning** — `core.Tenant.domain` + `DOMAIN` validator; migration `core.0005`; collected in
   the onboarding wizard, with a duplicate-claim pre-check so a unique-constraint violation is a field
   error rather than an `IntegrityError` 500.
2. **Usage metering** — `tenants.UsageRecord` + `PLAN_ALLOWANCES`; migration `tenants.0004`; full CRUD,
   `usagerecord_mark_billed`, freeze-on-billed, seeder rows.
3. **Isolation surface** — `tenants:isolation_overview`, a computed page (no model) reporting the isolation
   strategy, key posture and a per-table tenant-FK audit; plus the `LIVE_LINKS["0.1"]` leaf for bullet 3
   and an extra leaf for usage metering.

**Not closed, deliberately:** per-tenant email *templates* (bullet 4's second half) is 0.12's delivery
layer, not 0.1's; it is recorded here rather than silently counted as done.

### Verification

`temp/smoke_01.py` — **59 checks, 0 failures**. Covers anonymous refusal, all new pages, the derived
allowance/overage maths (including the enterprise *unmetered* path returning `None` rather than 0), the
freeze-on-billed guard, the mark-billed verb's invoice precondition, GET→405 on both POST-only verbs,
cross-tenant IDOR 404, the member GET→405 / POST→403 distinction, the domain validator (invalid and
duplicate), and junk params (`?metric=²`, `?billed=maybe`, `?q=%00`, `?page=999`, `?page=abc`).

`manage.py check` clean. `temp/audit_integrity.py` — checks 2, 3, 5, 6 pass; check 4 transiently failed
while the concurrent 7.17 session had its views committed but its templates unwritten (not our defect).

### Defects found and fixed during the work

- **`require_POST` was below `tenant_admin_required`** on both new POST-only verbs, so a non-admin
  member's GET would be answered 403 by the role check before the method check ran. House standard is
  405 for a wrong method regardless of role (7.7's ruling). **The pre-existing tenants verbs
  (`encryptionkey_rotate`, `subscription_mark_paid`) still carry the old order — not swept here.**
- **A tenant-wide seeder guard hid new entities.** `seed_tenants` skipped any tenant that already had a
  subscription, so usage metering seeded only for brand-new workspaces; on the existing DB Acme and
  Globex got no usage rows. Split into `_seed_subscription` / `_seed_usage` with independent guards.
- **`.alert` / `.alert-info` / `.alert-warning` do not exist in `static/css/theme.css`.** An initial draft
  of the detail template used them and would have rendered unstyled. The house notice pattern is
  `<p class="text-muted">` (or `.text-warn` / `.text-ok` / `.text-danger`).

### Next

Classify 0.2, 0.3, 0.5, 0.7, 0.9 and 0.14 by the same method, then build module 0's 14 unbuilt
sub-modules per `plan-remaining-1-module0-submodules.md`.

---

## 0.2 Identity & Access Management — CLOSED OUT 2026-09-19

**Verdict: the biggest single-sub-module gap in module 0 — 3 of 5 bullets entirely absent, and the
4th only half-built.** `LIVE_LINKS["0.2"]` mapped 2 of 5 bullets, and a grep for
`deprovision|bulk|elevat|access_request|attest|certification|scim` across `apps/accounts/*.py`
returned **nothing at all** — no de-provisioning, no bulk import, no elevation, no access request,
no attestation, no SCIM.

### Bullet-by-bullet

| bullet | sub-feature | verdict |
|---|---|---|
| 1 Centralized User Directory | unified store, lifecycle states | **built** — `User` with `active/suspended/archived` |
| 2 Provisioning & De-Provisioning | invite-based onboarding | **built** — `UserInvite` + tokenized accept |
| | **de-provisioning / offboarding** | **ABSENT** → built |
| | **bulk user import/export** | **ABSENT** → built |
| | SCIM provisioning | **ABSENT — declared, not built** |
| 3 Access Request & Approval | self-service requests, approval workflow, time-bound grants | **ABSENT (all three)** → built |
| 4 Access Certification & Reviews | periodic reviews, attestation campaigns, orphan detection | **ABSENT (all three)** → built |
| 5 Privileged Access Management | JIT elevation | **ABSENT** → built |
| | credential vaulting, session recording | **ABSENT — declared, not built** |

### Gaps closed

1. **Bullet 3 — `AccessRequest`** (migration `accounts.0003`). Request, decision and time-bound grant
   on ONE row, because splitting them would let a decision and its grant drift apart.
   `access_request_approve` grants the role AND stamps `granted_until` in one atomic block; rejection
   requires a stated reason. A **self-service lens scoped to `request.user`** (not to the tenant) is
   what makes the "self-service" half real.
2. **Bullet 4 — `AccessReview` + `AccessReviewItem`**. `arv_generate` materialises one line per member
   in scope, snapshotting the role held *now*; it is idempotent, so a second generate cannot wipe an
   attestation. `ari_revoke` **actually revokes** — it clears the member's role when it still matches
   the snapshot and leaves it alone when the role has since changed. Plus a COMPUTED
   **orphan-account board** over four shapes.
3. **Bullet 5 — `ElevationGrant`**. A time-boxed window with a stated reason. Approving **does not**
   flip `is_tenant_admin`: the repo has no scheduler, so a privilege that granted itself on a timer
   would never come back off. `is_live` derives whether the window is open.
4. **Bullet 2's missing half** — `user_deprovision` (status + role + live elevations + pending
   requests closed in one atomic action), `UserImportBatch` (staged validate → review → commit, with
   line-numbered errors), and a CSV export writing exactly the importer's columns.

### Verification

`temp/smoke_02.py` — **112 checks, 0 failures**, re-entrant (it clears its own fixtures, so it is a
real gate from any prior state). Covers anonymous refusal, every new page, the full request lifecycle
including the reject-requires-a-note rule and "a decided request cannot be re-decided", self-service
isolation between two members, the elevation window, the certification decision pair including both
revoke branches (role matches → cleared; role changed → left alone), re-generate not resetting a
decision, the four orphan shapes, the import validate/commit split with unusable passwords, the export
header matching the import columns, de-provisioning, cross-tenant IDOR 404, and member-GET → **405**
on all 11 POST-only verbs.

`manage.py check accounts core tenants` clean; `makemigrations --check` clean.

### Declared NOT built (recorded rather than faked)

- **SCIM provisioning** (bullet 2) — no SCIM endpoint, no IdP sync.
- **Credential vaulting** and **session recording** (bullet 5) — no secret is stored, nothing captures
  a session. Named on the elevation page itself so the absence reads as a decision.

### Notes

- **`apps/accounts` is still the last FLAT app** (`models.py`/`forms.py`/`views.py`/`urls.py`) while
  `core` and `tenants` are packages. New entities were appended flat to match the app rather than
  starting a half-package; 69 modules import `from apps.accounts.models import …`, so converting it is
  a separate refactor that must keep that path working. **Flagged, not done.**
- Bullet 2's exact text in `NavERP.md` is `Privileged Access Management (PAM)` — mapping the label
  without the `(PAM)` suffix leaves the bullet showing as unmapped.

### Next

Classify 0.3, 0.5, 0.7, 0.9 and 0.14 by the same method, then build module 0's 14 unbuilt sub-modules
per `plan-remaining-1-module0-submodules.md`.

---

## Step 0 COMPLETE — the remaining five classified (2026-09-19)

Method: for each unmapped bullet, grep the owning app for the feature. An unmapped bullet is
**built-but-unsurfaced** (add a leaf) or **absent** (real work) — never assume either.

### 0.3 RBAC & Permissions — 1/5 mapped · **3 absent, 1 partial**

| bullet | verdict |
|---|---|
| Roles & Role Hierarchies | **built** — `Role` with `permissions` M2M, `is_system` |
| Granular Permission Sets | **partial** — `Permission` catalog + role bundling exist; no screen/field/action-level enforcement |
| Row- & Field-Level Security | **ABSENT** |
| Segregation of Duties (SoD) | **ABSENT** — no conflict rules, no toxic-combination detection |
| Delegation & Temporary Access | **ABSENT** here. NOTE: procurement 6.3's `ApprovalDelegation` is a *different* concern (dated DOA grants stamped onto approval signatures) and must not be re-declared — L36 boundary. 0.2's new `AccessRequest.granted_until` is the time-bound-access half and could be the delegation vehicle. |

### 0.5 User & Organization Management — 2/5 mapped · **3 absent**

| bullet | verdict |
|---|---|
| Organization & Hierarchy Modeling | **built** — `core.OrgUnit` |
| User Profiles & Preferences | **built** — `accounts:profile` |
| Groups & Distribution Lists | **ABSENT** as a domain concept. `User.groups` exists only via Django's `PermissionsMixin` (unused by the app UI); no dynamic membership rules, no distribution lists. |
| Employee/User Lifecycle Sync | **ABSENT** — no HRM joiners/movers/leavers sync. `User.party` + `core.Employment` are the join points. |
| Guest & External User Access | **ABSENT** as a general concept. Several modules have their OWN portal-access tables (crm 1.4 `VendorPortalAccess`-style, scm 4.16 customer portal, 6.4 `VendorPortalAccess`, 7.14 `ClientPortalAccess`) — 0.5 must unify or explicitly point at them, not add a fifth. |

### 0.7 Data Security & Encryption — 1/5 mapped · **4 absent**

| bullet | verdict |
|---|---|
| Encryption at Rest & in Transit | **ABSENT** (infrastructure: MariaDB/TLS config, not app code) |
| Key & Secret Management | **built** — `tenants.EncryptionKey` (prefix + SHA-256 only; plaintext never stored) |
| Data Masking & Anonymization | **ABSENT** as a framework. There are *per-model* masks (`IntegrationConfigs.masked()`, `Webhooks.secret_masked`, HRM's `masked_account_number()`) but no generic masking/tokenization layer. |
| Data Loss Prevention (DLP) | **ABSENT** |
| Tenant Data Isolation | **realized** architecturally (shared schema + tenant FK + middleware) and now *surfaced* by 0.1's `tenants:isolation_overview`. Consider whether 0.7 should own that leaf instead of 0.1 — currently 0.1 does. |

### 0.9 Audit Trail & Activity Logging — 1/5 mapped · **4 absent**

| bullet | verdict |
|---|---|
| Immutable Audit Logs | **built** — `core.AuditLog` (append-only by convention; NOT tamper-evident — no hash chain) |
| User Activity Tracking | **built** — `core:activity_list` |
| Administrative Change Logs | **ABSENT as a lens** — the data is in `AuditLog` (role/permission/config changes are logged) but there is no admin-change-specific view |
| Audit Search & Reporting | **partial** — `core:auditlog_list` has search/filter; no scheduled reports, no evidence export |
| Log Retention & Forwarding | **ABSENT** — no retention policy, no SIEM forwarding |

### 0.14 Master Data & Reference Configuration — 1/5 mapped · **3 absent, 1 partial**

| bullet | verdict |
|---|---|
| Shared Reference Data | **partial / by design** — the masters exist but in their OWNING modules: `accounting.Currency`, `accounting.TaxCode`, `scm.UOM`, `inventory.UomConversion`. There is no central registry, and per L36 there should not be one — 0.14 should INDEX them, not re-declare them. |
| Master Data Governance | **built** — `core:party_list` + roles/addresses/contacts/relationships |
| Data Import/Export Tools | **ABSENT** as a generic tool. Per-module imports exist (6.9 catalog upload, 0.2's new `UserImportBatch`); nothing generic. |
| Code & Picklist Management | **ABSENT** — choices are hard-coded per model, no configurable dropdowns |
| Cross-Reference Mapping | **ABSENT** — no external-to-internal ID mapping table |

## What this changes about the plan

**Nothing is built-but-unsurfaced.** Every unmapped bullet in 0.3/0.5/0.7/0.9/0.14 is genuinely absent
or only partial — unlike 0.1, where bullet 3 was realized and merely unsurfaced. So these five are real
builds, not nav additions. Two boundaries to respect when building:

- **0.3 delegation** vs procurement 6.3's `ApprovalDelegation` (L36 — do not re-declare).
- **0.5 guest/external access** vs the four existing per-module portal tables (unify or point, never add a fifth).
- **0.7 tenant isolation** — 0.1 now owns that leaf; decide the owner before duplicating.
- **0.14 shared reference data** — index the owning modules' masters, never re-declare them (L36).
