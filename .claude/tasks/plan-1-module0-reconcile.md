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

---

## 0.4 Authentication & Single Sign-On (SSO) — CLOSED OUT 2026-09-19

**Verdict: 0 of 5 bullets mapped, and the feature set was entirely absent** — no MFA, no federation,
no credential policy, no session register, no risk scoring. Session idle/absolute timeouts DID exist
(settings + `SessionTimeoutMiddleware`), but there was no way to see or kill a session.

| bullet | verdict |
|---|---|
| Multi-Factor Authentication (MFA) | **partial → built**: TOTP implemented; SMS/email OTP, push and FIDO2/WebAuthn **declared not built** |
| SSO & Federation | **NOT built — and left UNMAPPED on purpose.** SAML 2.0 / OAuth-OIDC need an IdP library and a configured IdP. The bullet renders as the roadmap pill it actually is; pointing it at the MFA page would have marked federation "live" by aliasing an unrelated feature. |
| Password & Credential Policies | **partial → built**: complexity + rotation; breach-corpus check and passwordless **declared not built** |
| Session Management | **built** — timeouts existed; the register and revocation are new |
| Adaptive & Risk-Based Auth | **partial → built**: IP/device/recent-failure heuristic; geo-IP and behavioural analysis **declared not built** |

### What was built

`MfaDevice` (TOTP, secret stored via `core.crypto` Fernet — reversible because verification needs the
real bytes), `PasswordPolicy` (**`is_enforced` defaults False**), `PasswordHistory`, `UserSession`,
`LoginAttempt`; `apps/accounts/security.py` (RFC 6238 TOTP + the risk score); the login step-up; the
session register with revocation; the risk register; the credential-policy editor; a computed security
hub. Migration `accounts.0004`.

### Verification

- **TOTP verified against all six RFC 6238 Appendix B test vectors — 6/6 match**, before anything was
  built on it. A TOTP bug is a lockout bug.
- `temp/smoke_04.py` — **70 checks, 0 failures**, re-entrant. The two checks that matter most: a user
  WITHOUT a device signs in exactly as before, and a user WITH one is **not** signed in by their
  password alone.
- **`apps/accounts/tests apps/core/tests apps/tenants/tests` — 340 passed, 0 failed.** This is the
  regression gate that matters, because the change touches the login path for every module.

### Two bugs the smoke probe caught (both would have shipped)

1. **`login(request, user)` raised `ValueError: You have multiple authentication backends configured`**
   — a user fetched from the DB has no `.backend` attribute; only `authenticate()` sets it. The
   authenticating backend is now carried in the session.
2. **Every failed login was written with `tenant=NULL`** and therefore never appeared in any
   workspace's risk register — precisely the case the register exists to show. `authenticate()` returns
   `None` for both "no such account" and "wrong password", so the identifier is now resolved back to an
   account to attribute the attempt. An identifier matching NO account is still recorded, just
   unattributed — honest, since a shared-schema design cannot guess the tenant.

### Probe-vs-code discipline worth carrying

Three smoke failures looked like code bugs and were probe bugs — and one looked like a probe bug and was
a code bug. Specifically: **`203.0.113.x` / `198.51.100.x` are TEST-NET documentation ranges that
Python's `ipaddress` classifies as PRIVATE**, so `is_public_ip()` correctly rejected them and the probe's
"risky" client scored zero. Use a genuinely routable address (e.g. `8.8.8.8`) to exercise risk scoring.

### Design decisions that keep this safe on a foundation app

- The step-up triggers on the **existence of a confirmed device**, so a user without one is untouched.
- A device is **unconfirmed until a code verifies**, so a mistyped secret cannot lock anyone out.
- `PasswordPolicy.is_enforced` is **False** by default; enabling it is an explicit admin act.
- A `UserSession` with **no row is never touched**, so sessions predating the model keep working.
- Session revocation **deletes the Django session row** (`SESSION_ENGINE` is the db backend) rather than
  adding a per-request middleware to the hot path.
- **No MFA device is seeded** — a confirmed device on a demo account would make it unable to sign in
  without a code nobody can tell the user.

---

## 0.6 Application Module Administration & Access Scope — CLOSED OUT 2026-09-19

**Verdict: 0 of 13 bullets mapped and no access-scope layer existed at all.** Its thirteen bullets
are thirteen *per-module* access scopes (CRM record/territory access, HRM personnel-data masking, DMS
folder ACLs, …), and they share ONE shape.

### The design decision that mattered

A registry alone would be **decoration** — a config table nothing reads, which is the failure mode I
criticised in 0.1. So the build is a registry PLUS one real enforcement point:

- `apps/core/scoping.py` — `apply_data_scope()` narrows a queryset by the configured scope;
  `mask_for()` applies a field mask. Both are pure functions, unit-testable.
- `crud_list()` gained an **opt-in** `scope_module` / `scope_owner_field` hook, applied **before**
  search/filters/pagination (narrowing after pagination would return short pages and a lying count).
- `core:activity_list` is wired as the **proof**, chosen because `Activity.owner` exists and the view
  is member-facing. The probe proves it in situ: at `data_scope=own` a member sees only their own
  activities, an admin still sees all, and a disabled scope restores everything.

**One view, not 150, on purpose.** Retrofitting row-level security across every existing list means
auditing each for the correct owner field, and a wrong guess silently empties a register. The access
matrix reports which modules enforce, so the gap is visible rather than implied.

### Bullet-by-bullet

| bullet | verdict |
|---|---|
| 13 × per-module access scopes | **built** as one registry (24 rows/tenant from the catalog) + the enforcement mechanism. **The finer half of each bullet is NOT built** and is named on each scope's page: consent management, e-signature (21 CFR Part 11), retention locks, check-in/out, PCI scope isolation, dataset certification, BOM/routing change control. |
| Segregation of duties (Accounting) | **not built here** — procurement 6.3's `ApprovalDelegation` is a different concern (L36); `requires_approval` is recorded, not enforced by an approval engine. |
| Row-/column-level security (BI) | **partial** — row scoping exists as a mechanism; **column-level is not built**. |

### Verification

`temp/smoke_06.py` — **56 checks, 0 failures**, re-entrant. Includes the in-situ enforcement proof.
`apps/core apps/accounts apps/tenants apps/crm` — **2455 passed, 0 failed**; the gate matters because
`crud_list` is used by ~150 sub-modules.

### Three bugs found while building

1. **The decorator-order bug again** — `module_scope_delete` and `field_mask_delete` had
   `@tenant_admin_required` ABOVE `@require_POST`, so a member's GET got 403 instead of the house 405.
   Caught by the probe; both fixed with the reason in a docstring.
2. **The tenant-wide seeder guard again** — I called `_seed_module_scopes` from `_seed_tenant`, which
   the loop SKIPS for any tenant that already has spine data, so the first run created **zero** scope
   rows. Same trap as usage metering in `seed_tenants`. Moved outside the guard with its own guard.
3. **Two wrong slugs in the `?module=` deep-links** — `crm` (the slug is the whole title,
   `customerrelationshipmanagementcrm`) and a typo in `ecommercememanagementsystem`. Both would have
   produced a **silently empty register**, which is exactly what a filtered lens hides. Caught by
   verifying the derived slugs against `LIVE_LINKS` before trusting them.

### Probe-vs-code, again both ways

`apply_data_scope` returned an un-narrowed queryset in the direct-call checks while the view-level
checks passed — because the probe set `scope.is_enabled = True` **without saving**, and the function
correctly reads a fresh row from the DB. A missing `.save()` in the probe, not a code bug. Separately,
an assertion of `== 1` was wrong because the tenant has ~200 seeded activities many of which the test
member already owns; asserting the **invariant** (a strict subset, every row owned by the actor) is
the right shape and does not depend on seed volume.

### Also worth carrying

`Activity.Meta.ordering` is `["-due_at", "-created_at"]` and **MySQL sorts NULLs LAST in a DESC
order**, so newly created rows with no `due_at` land behind 199 seeded ones and never appear on page
1 of a list. A probe that asserts on rendered page-1 content must narrow with `?q=` or set the sort
field, or it will fail for a reason that has nothing to do with the code under test.

---

## 0.8 Privacy & Data Protection — CLOSED OUT 2026-09-19

**Verdict: 0 of 5 bullets mapped and no privacy layer existed at all.** A grep for
`consent|gdpr|dsar|retention` across `apps/` found nothing but unrelated uses of the words.

### What was built (migration `core.0007`)

| bullet | what ships |
|---|---|
| 1 Consent & Preference Management | `ConsentPurpose` (tenant-defined lawful purposes) + `ConsentRecord` (one row per EVENT) + a computed **consent matrix** |
| 2 Data Subject Rights (DSAR) | `DataSubjectRequest` with a **real statutory clock** + verify/complete/refuse/withdraw verbs |
| 3 Retention & Disposal Policies | `RetentionPolicy` + `DisposalRecord` + a computed **retention board** |
| 4 PII Discovery & Classification | `PiiClassification` data map + `scan_pii_fields()` + a human confirm/dismiss step |
| 5 Regulatory Coverage | `RegulatoryFramework` per-tenant enablement, which is what drives the DSAR window |

### The four decisions that make this honest rather than decorative

1. **A withdrawal ADDS a consent row; it never edits the grant.** The history IS the evidence, and
   the effective state is DERIVED from the latest event (`current_consent()`) rather than stored as a
   flag a withdrawal could fail to update. An expired grant reads as no consent.
2. **A DSAR with no framework enabled gets NO due date.** `statutory_window_days()` returns `None`
   rather than a default 30, because a deadline the workspace cannot point at a regime for is a
   fabricated obligation. Verified: the seeded DSARs have `due_at IS NULL` because no framework is
   enabled. Enabling GDPR (30) and CCPA (45) together yields **30** — the strictest wins.
3. **Completion is BLOCKED until identity is verified.** Verification is a verb with a required note,
   not a checkbox on a create form. Releasing or erasing personal data on an unverified request is the
   failure this sub-module exists to prevent.
4. **Automated destruction is NOT implemented, and the page says why.** Destroying data is a one-way
   door, the repo has no scheduler, and 7.10 already established that "delete" here does not erase
   bytes — Django never unlinks a `FileField` on row delete. A destruction feature reporting success
   while the file survived would be actively dishonest. The board IDENTIFIES and the disposal register
   EVIDENCES; the act is out of band.

### The retention board refuses to report a misleading zero

Where a policy cannot be evaluated it says **why** instead of showing `0`: a model with no
`created_at` column, a model with no `tenant` column, a category with no model pinned, or a label that
does not resolve. A zero that means "cannot tell" is the most dangerous number a compliance board can
show, and the seeded "Customer contacts" policy demonstrates the case on purpose.

### Two false-positive classes found by probing the PII scan (284 → 177 candidates)

1. `model._meta.get_fields()` returns **reverse relations and M2M accessors** as well as fields, named
   after the related model's `related_name` — so the first pass reported `core.Tenant.health_metrics`,
   `core.OrgUnit.procurement_routing_rules` and 280 similar accessors that hold no data at all. Now
   iterates `concrete_fields`; every entry is verified to be a real column.
2. A bare `location` pattern matched **46 warehouse locations** (`qc_location`, `dock_location`,
   `quarantine_location`, `from_location`, …). A bin is not a person's whereabouts, and a map full of
   noise gets ignored — which is the failure mode every PII scanner ever shipped has. The pattern is
   narrowed to genuinely personal names and `is_`/`has_` flags are skipped.

The scan is also **non-destructive on re-run**: a row a human has confirmed or dismissed is never
touched, because silently reverting a judgement is how a data map becomes untrustworthy and then
unused. Verified by confirming one row, dismissing another, re-scanning, and asserting both survive.

### Verification

`temp/smoke_08.py` — **89 checks, 0 failures**, re-entrant. `apps/core apps/accounts apps/tenants
apps/crm` — **2455 passed, 0 failed**.

### Declared NOT built (on the pages, not just here)

No automatic personal-data collation, so a DSAR access/portability request is driven to completion but
the bundle is assembled by hand. No destruction of any kind. No data-residency **enforcement** (the
region is recorded only). No consent-enforcement middleware — recording a withdrawal does not by itself
stop a module from mailing someone. No encryption at rest (0.7).

### Probe lesson

A consent-expiry assertion failed because the probe back-dated an expired grant onto a purpose whose
latest event was already a withdrawal — so the check read the withdrawal, not the expiry. **A
derived-from-latest query needs its own isolated fixture**; reusing a purpose with other events tests
the ordering, not the rule.

---

## 0.10 System Configuration & Settings — CLOSED OUT 2026-09-19

**Verdict: 0 of 5 bullets mapped and no configuration layer existed.** Migration `core.0008`.

| bullet | what ships |
|---|---|
| 1 Global & Tenant Settings | `SettingDefinition` (registry + default) + `SettingValue` (per-tenant override) + a computed overview that shows each value WITH its source |
| 2 Feature Flags & Toggles | `FeatureFlag` — the row is the per-tenant toggle, `applies_to_plan` the plan scope, `exempt_roles` the user-group scope |
| 3 Numbering & Sequence Management | `NumberingScheme` (config) + a computed **reconciliation board** |
| 4 Business Calendar & Fiscal Periods | `BusinessCalendar` + `Holiday` + a computed calendar board |
| 5 Custom Fields & Form Builder | `CustomFieldDefinition` + `CustomFieldValue` + per-type validation |

### The two L36 boundaries this sub-module had to respect

1. **`next_number()` owns allocation.** Every document number in the repo is minted by it, and
   `TenantNumbered` calls it for every PO/PR/RFQ/GRN/SO/… A second allocator would be a second source
   of truth for the same counter. So 0.10 CONFIGURES prefixes and RECONCILES them against what models
   actually mint — it never mints anything.
2. **`accounting.FiscalPeriod` owns periods and period-close.** The business calendar board owns the
   WORKING WEEK and links out to the accounting periods rather than re-declaring them; a second period
   table would split the ledger's calendar from the business one.

### The four decisions that make it honest

1. **`get_setting()` reports WHICH it read.** A tenant with no override row is not missing a setting —
   it is taking the default. The overview shows a "Default" vs "Overridden" badge, because a page that
   shows a value without its source cannot answer the only question an operator has.
2. **Clearing an override DELETES the row** rather than storing an empty string, so the workspace goes
   back to inheriting instead of reading as an explicit empty value.
3. **An unknown feature key resolves to OFF.** Defaulting to True would mean a typo in a template
   silently ships a half-built feature.
4. **The numbering board states its own blind spot on the page.** It reads the `NUMBER_PREFIX` class
   attribute, so a model minting through its own `save()` with a hardcoded literal is invisible.

### A false negative found by probing the board

The board reported **SINV as "configured but nothing mints it"** — which was wrong.
`tenants.SubscriptionInvoice` predates `TenantNumbered` and its `save()` calls
`next_number(SubscriptionInvoice, self.tenant, "SINV")` directly. `LITERAL_PREFIX_MODELS` now merges
that case in, so the board reports `SINV` as **in use**, and the page names the model behind it.
Remaining configured-only: only the deliberately-unused `ZZZ` the seeder plants.

### A trap that made two forms unusable (caught by the smoke probe, three times)

**A model `JSONField` gets a `forms.JSONField`, which validates the input as JSON in `to_python` —
BEFORE any `clean_<field>` or `clean()` runs.** So an operator typing `a, b` for `choices`, or `a` as a
custom value, failed validation and the conversion code never executed. `choices` on both definition
forms and `value` on the value form are now redeclared as `CharField`. **When you add a `clean_*` for a
JSONField, redeclare the form field or the clean never runs.**

### Verification

`temp/smoke_10.py` — **80 checks, 0 failures**, re-entrant. `apps/core apps/accounts apps/tenants
apps/crm` — **2455 passed, 0 failed**.

### Declared NOT built (on the pages, not just here)

Settings are not a `django.conf.settings` replacement — `get_setting()` only resolves registered keys,
so a typo returns the caller's default rather than inventing a value. Numbering configures but never
allocates. Fiscal periods and period-close live in accounting. Custom-field values are keyed without a
foreign key (a deleted parent leaves an orphan) and **no module renders them yet** — a module must opt
in, the same shape 0.6's data scoping uses.

---

## 0.11 Workflow & Approval Administration — CLOSED OUT 2026-09-21

**Verdict: 0 of 5 bullets mapped — and the decisive finding was that 0.11 must NOT build an engine.**
An inventory found **~71 approval/workflow/escalation models already in the repo** across six apps
(`procurement.ApprovalRoutingRule`, `procurement.EscalationPolicy`, `crm.WorkflowRule`,
`inventory.TransferApproval`, `hrm.OfferApproval`, `projects.ProjectApprovalGate`, …). Every one
decides its own routing and writes its own decision rows. A platform engine would be the L36 mistake
at the largest possible scale, so 0.11 owns the three things nobody owns instead.

| bullet | what ships |
|---|---|
| 1 Visual Workflow Designer | `WorkflowDefinition` + `WorkflowStep` — the REGISTRY: which processes exist, which engine backs each, what routing it is *supposed* to follow |
| 2 Approval Hierarchies & Limits | `WorkflowStep` (tiers + thresholds, documented) + `ApprovalLimit` (platform thresholds per role) |
| 3 Escalation & SLA Rules | `SlaRule` — the generic one the non-procurement modules never had |
| 4 Business Rules Engine | `BusinessRule` + `BusinessRuleLog` + a real evaluator and a test-run page |
| 5 Process Monitoring | a COMPUTED board reading the **real** approval tables of other apps |

### The probing finding that shaped the monitoring board

`approval_backlog()` reads eight declared approval sources. Introspecting their choices showed that
**only five are in-flight queues** — the other three (`inventory.PurchaseOrderApproval`,
`inventory.TransferApproval`, `procurement.RequisitionApproval`) record only
`decision = approved|rejected` with **no waiting state at all**. Every row in those is already
decided; the in-flight state lives on the PARENT record. Reporting them as a backlog would have been
a fabricated queue, so they are reported as decided-volume with the reason. Four further models
(execution logs, SLA definitions) are listed with why they are not queues, so the board accounts for
all twelve rather than silently dropping half.

Real data on the board: **6 open items across 5 queues, 4 breached at 48h**, oldest 2225h.

### What is deliberately NOT done, and why

- **No workflow engine, and no drag-and-drop canvas.** Steps are an ordered register, not a designer.
- **`WorkflowStep` is not enforced.** A step claiming to control routing would be a second source of
  truth against the engine that actually decides.
- **Nothing executes.** `evaluate_rules()` returns matches in priority order and performs no action;
  the caller acts and reports back via `BusinessRuleLog.action_taken`. There is no cross-module action
  executor, because one would mean reaching into 71 other engines and mutating their rows.
- **No escalation fires and nothing auto-approves.** The repo has no scheduler, so an auto-approve SLA
  rule would be a promise nothing keeps. The board is where an overdue item becomes visible.
- **Bottleneck analysis is counts and oldest-item age only** — no per-approver timing, cycle-time
  trend or throughput history, because the approval tables do not carry the decision timestamps.

### Two design details that carry weight

- **`engine_label` is a validated string, not a ContentType FK.** `WorkflowDefinitionForm` refuses a
  label naming no model — the registry only has value if it can be checked against something, and a
  typo would silently make a process unmonitorable. The monitor then flags any active definition whose
  engine is not a queue it reads.
- **`BusinessRuleLog.rule` is `SET_NULL`, not `CASCADE`.** The log is the evidence that a rule fired;
  retiring a rule must not erase the record of what it did. Verified: deleting a rule leaves its logs
  with `rule_id IS NULL`.

### Verification

`temp/smoke_11.py` — **80 checks, 0 failures**, re-entrant. `apps/core apps/accounts apps/tenants
apps/crm` — **2455 passed, 0 failed**. Migration `core.0009`.

### Trap caught by the probe

`annotate()` with an aggregate leaves the queryset **unordered for pagination**, raising
`UnorderedObjectListWarning` and able to yield inconsistent pages — `Meta.ordering` alone is not
enough. Both annotated lists now carry an explicit `order_by`.

### Environment note

MySQL was down at session start (no service registered; `mysqld` needed a manual start and performed
crash recovery from a checkpoint). Started with `MSYS_NO_PATHCONV=1 mysqld.exe
--defaults-file="C:\xampp\mysql\bin\my.ini"` — without `MSYS_NO_PATHCONV` Git Bash mangles the path to
`\c\xampp\...` and mysqld aborts on "Could not open required defaults file".
