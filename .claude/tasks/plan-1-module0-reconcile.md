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
| 0.2 Identity & Access Management | 5 | 2 | not yet classified |
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
