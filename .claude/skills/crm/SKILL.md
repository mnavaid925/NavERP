---
name: crm
description: Work on the CRM module (Module 1 — 1.1–1.6 leads/opportunities/campaigns/cases/KB/tasks + accounts/contacts; 1.3 marketing automation = campaigns + campaign-members + email-templates + email-campaigns + landing-pages + form-submissions (public web-to-lead); 1.7–1.12 expenses, projects/milestones/timesheets, doc templates/contracts+e-sign, workflow rules/approvals, onboarding/health-scores/surveys, product stock/purchase-orders/partner-portal). Use when the user asks to add/change/debug anything under apps/crm or templates/crm, extend the CRM seeder, touch CRM sidebar wiring (LIVE_LINKS 1.1–1.12), or invokes /crm.
---

# CRM Module (Module 1, sub-modules 1.1–1.12)

Customer Relationship Management. Reuses the unified core spine (NavERP-ERD.md): **Accounts and
Contacts are `core.Party`** (one record, many roles) — CRM adds only its own domain tables and FKs
into core **by string**. App path: `apps/crm/`. Templates: `templates/crm/`. URL prefix: `/crm/`
(`app_name="crm"`). Mounted in `config/urls.py`; app in `INSTALLED_APPS` as `apps.crm`.

Covers: 1.1 Core Data Management (Contacts/Accounts/Leads), 1.2 SFA (Opportunities; Forecasting →
overview), 1.3 Marketing (Campaigns), 1.4 Customer Service (Cases + Knowledge Base), 1.5 Activity
(Tasks), 1.6 Analytics (overview dashboard). Quoting/Forecasting detail and the marketing
email-builder / self-service portal / calendar-VoIP integrations are deferred to later passes /
the Sales module (Module 8) per `NavERP.md`.

## Models (`apps/crm/models.py`)

All 6 owned models inherit the abstract **`TenantNumbered`** base: `tenant` FK (`related_name="+"`),
auto per-tenant `number` assigned in `save()` via `apps.core.utils.next_number` with retry-on-
`IntegrityError` (mirrors `tenants.SubscriptionInvoice`), `created_at`/`updated_at`. Each concrete
model sets `NUMBER_PREFIX`, `STATUS_CHOICES` (where applicable), `Meta.ordering`,
`unique_together=("tenant","number")`, and two indexes (`(tenant, status|stage)` + `(tenant,
created_at)`; CrmTask uses `(tenant, due_date, created_at)`).

| Model | Prefix | Key fields | Core reuse |
|-------|--------|------------|------------|
| `Lead` | `LEAD-` | name, company, title, email, phone, source, rating(hot/warm/cold), status(new/contacted/qualified/unqualified/converted/recycled), score(0–100), est_value, owner, description, converted_party | `owner`→`accounts.User`, `converted_party`→`core.Party` |
| `Opportunity` | `OPP-` | name, stage(prospecting/qualification/proposal/negotiation/closed_won/closed_lost), amount, probability(0–100), close_date, next_step, description; props `weighted_amount`, `is_open`, `is_won`; `OPEN_STAGES` | `account`/`primary_contact`→`core.Party`, `owner`→User, `source_lead`→`crm.Lead`, `campaign`→`crm.Campaign` |
| `Campaign` | `CAM-` | name, type, **objective**(awareness/lead_gen/nurture/conversion/event/retention), status(planned/active/paused/completed/cancelled), **parent_campaign**(self-FK), start/end_date, budget_planned/actual, expected/actual_revenue, target_size, **utm_source/medium/campaign**, description; prop `roi` | `owner`→User, `parent_campaign`→self (1.3 detail below) |
| `Case` | `CASE-` | subject, type, priority(low/medium/high/critical), status(new/open/in_progress/waiting/resolved/closed), origin, description, due_at(SLA), resolved_at(system); props `is_open`/`is_overdue`; `OPEN_STATUSES`; `save()` stamps/clears `resolved_at` | `account`/`contact`→`core.Party`, `owner`→User |
| `KnowledgeArticle` | `KB-` | title, category, body, visibility(internal/external), status(draft/published/archived), views_count(system) | `owner`→User |
| `CrmTask` | `TASK-` | subject, type, priority(low/medium/high), status(open/in_progress/done/cancelled), due_date, description, completed_at(system); prop `is_overdue`; `OPEN_STATUSES`; `save()` stamps/clears `completed_at` | `owner`→User, `party`→`core.Party`, `related_opportunity`→`crm.Opportunity` |

**System-set fields kept out of forms:** `number`, `resolved_at`, `completed_at`, `views_count`,
`converted_party`. **Decimal note:** `weighted_amount`/`roi` cast to `Decimal` so they're correct on
freshly-created (un-round-tripped) instances.

**Accounts & Contacts (1.1) are `core.Party`** — not CRM-owned tables. CRM adds two one-to-one
extension models (plain `models.Model`, NOT `TenantNumbered`; `tenant` FK set in the view):
- **`AccountProfile`** (OneToOne org `core.Party`, `related_name="crm_account_profile"`):
  industry(choices)/website(URL)/phone/email/annual_revenue/employee_count/`parent_account`→Party/
  address_line/city/state/postal/country/source(=`Lead.SOURCE_CHOICES`)/owner→User/description.
  Indexes `(tenant, industry)`, `(tenant, source)`, `(tenant, parent_account)`.
- **`ContactProfile`** (OneToOne person `core.Party`, `related_name="crm_contact_profile"`):
  job_title/department/email/phone/mobile/`account`→Party(employer)/address_*/linkedin(URL)/source/
  owner→User/description. Indexes `(tenant, source)`, `(tenant, account)`.

The Party holds `name`/`tax_id`/`kind`; the profile holds the rich fields. Reverse accessor
`party.crm_account_profile` / `party.crm_contact_profile` (Django's RelatedObjectDoesNotExist
subclasses AttributeError, so `getattr(obj, "crm_account_profile", None)` and `{% if obj.crm_account_profile %}`
are safe when no profile exists — e.g. a seeded vendor org or converted-lead party). `INDUSTRY_CHOICES`
is a module-level constant in `models.py`. `website`/`linkedin` use `forms.URLField(assume_scheme="https")`.

## URLs / routes (`apps/crm/urls.py`, `app_name="crm"`)

- Per CRUD model — `<entity>_list`, `<entity>_create`, `<entity>_detail`, `<entity>_edit`,
  `<entity>_delete` (delete is POST-only) — for `lead`, `opportunity`, `campaign`, `case`,
  `knowledgearticle`, `task`.
- Custom: `crm:overview` (module landing, `/crm/`), `crm:lead_convert` (POST). **Accounts & Contacts
  have full CRUD**, keyed by **Party pk**: `crm:account_list/_create/_detail/_edit/_delete` and
  `crm:contact_*` (delete is POST-only **and `@tenant_admin_required`** — see Views). "View in Core"
  links to `core:party_detail`.

## Views (`apps/crm/views.py`)

Function-based, `@login_required` (CRM is day-to-day work — not `@tenant_admin_required`), tenant-
scoped. CRUD delegates to `apps.core.crud` helpers (`crud_list`/`_create`/`_detail`/`_edit`/
`_delete`); deletes + `lead_convert` are `@require_POST`. Notable:
- `lead_convert` — atomic: creates org `Party`+`PartyRole(customer)` (if `company`), person
  `Party`+`PartyRole(contact)` (+`ContactMethod` if email), and an `Opportunity(source_lead=lead)`;
  sets `lead.status="converted"`, `converted_party`; writes audit logs; redirects to the opportunity.
  Idempotent (already-converted → info message, no dupes).
- `knowledgearticle_detail` — `F("views_count")+1` atomic update (bypasses `save()`).
- `overview` — DB-side aggregates (`Sum`/`Count` with `Q` filters, no Python row loops) for open
  leads, weighted pipeline forecast, win rate, open cases/tasks, active campaigns + stage/rating
  charts (`json_script` + `{% block extra_js %}` Chart.js, ids `stageChart`/`ratingChart`).
- Detail reverse-relation sub-queries are **explicitly** `Model.objects.filter(tenant=request.tenant,
  fk=obj)` (defense-in-depth; never the bare reverse manager).
- **Accounts/Contacts** — full CRUD over `core.Party` + the profile. `account_create`/`_edit`
  orchestrate **Party + AccountProfile atomically** (form binds to existing-or-new profile so the
  INSERT is inside `transaction.atomic()`; `name`/`tax_id` written to the Party from `cleaned_data`).
  `account_detail` shows the profile + `child_accounts` (`parent_account=obj`) + `stakeholders`
  (ContactProfiles whose `account=obj`). List querysets `select_related` the profile **and its
  second-hop FKs** (`crm_account_profile__owner`, `crm_contact_profile__account`) to avoid N+1; list
  filters traverse `crm_account_profile__industry/source`. **`account_delete`/`contact_delete` are
  `@tenant_admin_required`** (not `@login_required`) — deleting the shared `core.Party` cascades the
  profile/roles/addresses and SET_NULLs opportunities/cases, a cross-module blast radius, so it's
  admin-only and the delete buttons are hidden from non-admins in the templates.

## Templates (`templates/crm/<submodule>/<entity>/<page>.html`)

**One folder per sub-module, then one folder per entity, with a bare `list/detail/form.html` page filename**
(CLAUDE.md "Template Folder Structure"): `directory/` (entity folders `contact/ account/ lead/`), `sales/`
(`opportunity/`), `marketing/` (`campaign/ campaignmember/ emailtemplate/ emailcampaign/ landingpage/
formsubmission/` + standalone public `landing_public.html` — see §1.3), `service/` (`case/ knowledgearticle/`), `activities/` (`task/`),
`finance/` (`expense/`), `projects/` (`crmproject/ crmmilestone/ timesheet/`), `documents/` (`contractdocument/
doctemplate/` + standalone `sign_document.html`), `workflow/` (`workflowrule/ approvalrequest/ workflowlog/`),
`success/` (`onboardingplan/ healthscore/ survey/` + standalone `survey_respond.html`/`health_config`), `vendor/`
(`crm_po/ productstock/ partnerportalaccess/` + standalone `portal_dashboard.html`/`portal_stock.html`). The module
landing `overview.html` stays at the `templates/crm/` root. So a view renders e.g. `"crm/directory/lead/list.html"`.

Extend `base.html`; use the `theme.css` design system. Per CRUD model, an entity folder with `list.html`
(filter-bar with `q` + status/FK selects reflecting `request.GET`, Actions column view/edit/delete-
POST+confirm+csrf, pagination via `partials/pagination.html`, empty-state), `detail.html`
(`detail-grid` + actions + back link), `form.html` (shared create/edit, generic
`{% for field in form %}` in `.form-grid`). Plus `account/{list,detail,form}`,
`contact/{list,detail,form}` (Party + profile; CRM-native New/Edit/Delete; delete buttons wrapped in
`{% if request.user.is_superuser or request.user.is_tenant_admin %}`; "View in Core" →
`core:party_detail`), and `overview.html`. Badges use exact model choice values with
`{{ obj.get_<field>_display }}` fallback text. The opportunity list FK filter compares
`request.GET.account == acc.pk|stringformat:"d"`.

## Seeder (`apps/crm/management/commands/seed_crm.py`)

`venv\Scripts\python.exe manage.py seed_crm` — idempotent (skips a tenant that already has `Lead`
rows). Reuses existing core Parties (first org as `account`, first person as `contact`) rather than
inventing duplicates. Per tenant: 2 campaigns, 3 leads, 4 opportunities (varied stages incl. one
closed_won), 3 cases, 2 KB articles, 3 tasks. `owner` = tenant admin. Also idempotently **backfills
an `AccountProfile`/`ContactProfile`** onto the first org/person Party per tenant via
`_backfill_profiles` (runs every time, independent of the lead-exists guard, so existing demo data
gains firmographics/contact details without `--flush`), and seeds **§1.3 marketing data** via
`_seed_marketing` (also unconditional, self-guards on `EmailTemplate` — see the §1.3 section). Prints the
demo-login reminder and the `admin`-has-no-tenant warning. Run after `seed_core`/`seed_accounts`/`seed_tenants`.

## Sidebar wiring (`apps/core/navigation.py` → `LIVE_LINKS`)

Keys must match the `NavERP.md` §1 feature bullets verbatim to light up:
- `1.1`: Contacts → `crm:contact_list`; Accounts (Companies) → `crm:account_list`; Leads (Potential
  Customers) → `crm:lead_list`
- `1.2`: Opportunity Management (Deals) → `crm:opportunity_list`; Forecasting → `crm:overview`
- `1.3` (recreated in detail — all 3 bullets live): Campaign Management → `crm:campaign_list`; Campaign Members
  → `crm:campaignmember_list`; Email Marketing → `crm:emailcampaign_list`; Email Templates →
  `crm:emailtemplate_list`; Landing Pages & Forms → `crm:landingpage_list`; Form Submissions →
  `crm:formsubmission_list` (see "§1.3 Marketing Automation" section)
- `1.4`: Case / Ticket Management → `crm:case_list`; Solutions & Knowledge Base →
  `crm:knowledgearticle_list`
- `1.5`: Task Management → `crm:task_list`
- `1.6`: Dashboards → `crm:overview`; Standard Reports → `crm:overview`

## Conventions & gotchas

- **Tenant scoping is mandatory** on every query (CLAUDE.md) — including reverse-relation sub-queries
  in detail views. `request.tenant=None` (superuser) → empty results by design; log in as
  `admin_acme`/`password`.
- **Context-var contract** (from `crud.py`): list → `object_list`+`page_obj`+`q` (+ the view's
  filter `*_choices`/FK querysets); detail/edit → `obj`; form → `form`+`is_edit`.
- **Accounts/Contacts identity = `core.Party`** (no duplicate master table). CRM owns only the
  `AccountProfile`/`ContactProfile` extensions + full CRUD that manages Party + profile together.
  **Deleting an account/contact deletes the shared Party** (cross-module impact) → admin-only.
- Auto-number collisions retry 5× inside `transaction.atomic()`; numbering is per-tenant per-prefix.
- `related_name="+"` on the abstract tenant FK means no `tenant.crm_leads` reverse accessor — always
  `Lead.objects.filter(tenant=...)`.

## Common tasks

- **Add a field to a model:** edit `apps/crm/models.py`; add to the matching `Meta.fields` in
  `forms.py` (unless system-set); surface in the entity's `detail.html`/`form.html`/`list.html`;
  `makemigrations crm` + `migrate`. Commit one file per commit.
- **Add a filter:** pass the choices/queryset in the view's `crud_list` `extra_context` and add a
  `<select>` to the list template reflecting `request.GET` (pk filters use `|stringformat:"d"` + the
  int-guard tuple `("param","field_id",True)`).
- **Add a new model + CRUD:** subclass `TenantNumbered` (set `NUMBER_PREFIX`); add a `TenantModelForm`;
  add 5 CRUD views via the `crud_*` helpers (+ `@require_POST` delete); add routes; add 3 templates;
  register in `admin.py`; extend `seed_crm.py`; `makemigrations`/`migrate`; wire `LIVE_LINKS` if it
  maps to a `NavERP.md` bullet.
- **Extend the seeder:** add rows inside `_seed_tenant`; keep the `Lead`-exists idempotency guard.
- **Run the tests:** `venv\Scripts\python.exe -m pytest apps/crm -q` (SQLite via `config.settings_test`).

---

# §1.3 Marketing Automation (recreated in detail)

The thin single-`Campaign` 1.3 was rebuilt to cover all three NavERP.md §1.3 bullets. Migrations `0006`
(Campaign columns + 5 tables) and `0007` (CampaignMember `(tenant, created_at)` index). Models added to the
same `apps/crm/models.py`:

| Model | Prefix | Bullet | Key fields / behavior | Reuse |
|-------|--------|--------|-----------------------|-------|
| `Campaign` (enhanced) | `CAM-` | Campaign Management | + `objective`, `parent_campaign`(self-FK), `utm_source/medium/campaign`; member/response stats computed in `campaign_detail` via one `.aggregate(Count, Count filter=responded)` (not stored) | `parent_campaign`→self |
| `CampaignMember` | — (plain, tenant-scoped) | target-list segmentation | `campaign`(CASCADE, `related_name="members"`), `party`→core.Party, `lead`→crm.Lead, member_name/email, status(targeted/sent/opened/clicked/responded/converted/bounced/unsubscribed), `responded_at`(system — `save()` stamps on responded/converted), notes; `RESPONDED_STATUSES` | `party`→Party, `lead`→Lead |
| `EmailTemplate` | `EMT-` | Email Marketing | name, category, subject, preheader, `body`(HTML+merge vars, **deferred** on list, shown ESCAPED), from_name/email, is_active | `owner`→User |
| `EmailCampaign` | `BLAST-` | Email Marketing (drip+A/B+tracking) | `campaign`(CASCADE, `related_name="email_campaigns"`), `template`+`variant_template`(A/B), is_ab_test, send_type(one_time/drip/ab_test), status(draft/scheduled/sending/sent/paused/cancelled), scheduled_at, **system**: sent_at + recipients/sent/opened/clicked/bounced/unsubscribed_count; props delivered_count/open_rate/click_rate/bounce_rate (Decimal-safe) | `template`→EmailTemplate |
| `LandingPage` | `LP-` | Landing Pages & Forms | name, `campaign`(SET_NULL, `related_name="landing_pages"`), slug, **`public_token`**(auto `token_urlsafe(32)` in `save()`, unique, system), headline/subheadline/`body`, capture_phone/company/message, cta_label, status(draft/published/archived), `routing_owner`→User, lead_source(=`Lead.SOURCE_CHOICES`), `submission_count`(system, F()-bumped); prop is_published | `campaign`→Campaign |
| `FormSubmission` | — (plain) | web-to-lead captures | `landing_page`(CASCADE, `related_name="submissions"`), name/email/phone/company/message, status(new/routed/converted/spam), routed_to→User, converted_lead→Lead, ip_address; **read-mostly** (list+detail+delete+convert, no create/edit form — mirrors WorkflowLog) | — |

**Routes (`urls.py`):** standard `<entity>_list/_create/_detail/_edit/_delete` (delete POST-only) for
`campaignmember`/`emailtemplate`/`emailcampaign`/`landingpage`; `formsubmission_list/_detail/_delete/_convert`
(read-mostly). Custom: `campaignmember_add`(inline on campaign)/`campaignmember_remove`; `emailcampaign_send`;
`landingpage_publish`; `formsubmission_convert`; **public** `path("p/<str:token>/", landing_public)`.

**Views & actions (`views.py`):** `campaign_detail` recreated — funnel `.aggregate` + members(≤50, "View all"
>50)/email-campaigns/landing-pages/opportunities panels. Privileged actions are **`@tenant_admin_required`**:
`emailcampaign_send` (snapshots recipients from members via a **race-safe conditional `.update()`** that claims
the row; advances targeted→sent; system-sets metrics+sent_at) and `landingpage_publish` (draft↔published toggle —
publishing exposes a public URL). `formsubmission_convert` (atomic) creates a routed `Lead` (idempotent).
**Public `landing_public(token)`** — no login, only `status="published"` resolves (else 404), CSRF via template,
body rendered ESCAPED (`|linebreaks`), input caps, Post/Redirect/Get (`?submitted=1`), `_client_ip` = REMOTE_ADDR
only (XFF is spoofable; proxy caveat noted).

**Forms (`forms.py`):** `CampaignForm` (+ objective/parent_campaign/utm_*, self-parent excluded) + per-model forms.
**System-managed fields excluded from forms (mass-assignment guard):** `EmailCampaignForm` excludes `status` +
all metric counters + `sent_at`; `LandingPageForm` excludes `status` + `public_token` + `submission_count`;
`CampaignMemberForm` excludes `responded_at`. `PublicLeadForm` is a **plain `forms.Form`** (no tenant binding) with
length caps for the public endpoint.

**Templates (`templates/crm/marketing/`):** entity folders `campaign/ campaignmember/ emailtemplate/
emailcampaign/ landingpage/ formsubmission/` (each `list/detail/form.html`; formsubmission has no `form.html`) +
standalone public `landing_public.html` (extends `base_auth.html`). EmailTemplate body shown as escaped `<pre>`
source; never `|safe` anywhere. Admin-only buttons (Send / Publish / Unpublish) wrapped in
`{% if request.user.is_superuser or request.user.is_tenant_admin %}`.

**Seeder:** `_seed_marketing(tenant)` runs unconditionally (like `_backfill_profiles`), self-guards on
`EmailTemplate.objects.filter(tenant=...).exists()` so existing seeded DBs backfill 1.3 data **without `--flush`**.
Reuses the tenant's first Campaign + existing Party/Lead rows; seeds members (`bulk_create`, pre-stamped
responded_at), 1 template, 1 sent blast (with metrics), 1 published landing page, 2 submissions (one converted).

**Tests:** `apps/crm/tests/test_marketing.py` (193 tests — invariants, form exclusions, CRUD, admin-gated
send/publish, public endpoint, IDOR/FK-injection, N+1 budgets).

---

# Sub-modules 1.7–1.12 (extension — finance/delivery/docs/automation/success/vendor)

Added as an extension pass on the **same `apps/crm` app** (one big `models.py`, `forms.py`, `views.py`,
`urls.py`, `admin.py`, `seed_crm.py`). Migration `0005` created the 18 tables. **Spine-gap note:** the
unified-core masters (`core.Item/Currency/Invoice/Payment/PurchaseOrder/StockMove`) are **not built
yet** (Accounting/Inventory/Procurement = future modules 2/5/6), so 1.12 ships **CRM-owned**
`PurchaseOrder`/`PurchaseOrderLine`/`ProductStock`, `Expense.currency_code` is a CharField, and health
scoring derives from existing CRM signals. See `.claude/tasks/todo.md` "Spine-gap adaptation". When those
modules land, migrate these onto the spine.

## Models (1.7–1.12) — all `TenantNumbered` unless noted

| Model | Prefix | Sub-mod | Key fields / behavior | Reuse |
|-------|--------|---------|-----------------------|-------|
| `Expense` | `EXP-` | 1.7 | category, amount, **currency_code**(char), expense_date, **receipt** FileField (allowlist+20MB via `clean_receipt`), status(draft/submitted/approved/rejected), **submitted_by/approved_by/status are system-set — NOT in the form** | `opportunity`/`project`→crm, submitted_by/approved_by→User |
| `CrmProject` | `PRJ-` | 1.8 | name, status(planning/active/on_hold/completed/cancelled), start/end_date, budget, owner, description | `account`→Party, `source_opportunity`→Opportunity |
| `CrmMilestone` | `MS-` | 1.8 | title, kind(milestone/task), status(not_started/in_progress/completed/blocked), order, `parent`(self-FK subtasks), `completed_at`(system via `save()`) | `project`→CrmProject(CASCADE), assignee→User |
| `Timesheet` | `TS-` | 1.8 | date, hours, is_billable, status; (approved_by is NOT in the form) | `project`(CASCADE)/`milestone`→crm, employee→User, client→Party |
| `DocTemplate` | `TPL-` | 1.9 | name, template_type(nda/proposal/contract/quote/receipt), `body`(merge-var HTML, deferred on list) , is_active | owner→User |
| `ContractDocument` | `CTR-` | 1.9 | name, status(draft/sent/viewed/signed/declined/expired/archived), current_version, body_snapshot(deferred on list), signed_at/expires_at; **status/current_version are system-managed — NOT in the form** | `template`→DocTemplate, opportunity→crm, account→Party |
| `SignerRecord` | — (plain) | 1.9 | per-signer: signer_name/email, `token`(secrets.token_urlsafe(32)), order(auto in view), viewed_at/signed_at/declined_at/ip_address | `contract`→ContractDocument(CASCADE) |
| `WorkflowRule` | `WFR-` | 1.10 | name, is_active, trigger_entity/event/field/value, `conditions`/`actions` JSONField (declarative, **never eval'd**), delay_value/unit | owner→User |
| `WorkflowLog` | — (plain) | 1.10 | append-only: record_label, status(success/failed/skipped), fired_at, error_msg(deferred on list). **Read-only — list+detail only, no create/edit/delete** | `rule`→WorkflowRule(SET_NULL) |
| `ApprovalRequest` | `APR-` | 1.10 | subject, record_label, status(pending/approved/rejected/expired), threshold_field/value, approved_at/rejected_at(system), reason; prop `is_pending` | rule→WorkflowRule, approver/requested_by→User |
| `OnboardingPlan` | `CS-` | 1.11 | name, status(active/completed/on_hold/cancelled), target_date, completed_at; prop `progress_pct`(from steps) | account→Party, owner→User |
| `OnboardingStep` | — (plain) | 1.11 | order(auto in view), title, assignee, due_date, completed_at; inline on plan detail | `plan`→OnboardingPlan(CASCADE) |
| `HealthScore` | `HS-` | 1.11 | score(0–100), tier(green/yellow/red), `breakdown` JSON; `unique_together(tenant,account)` **and** `(tenant,number)`; written by `compute_health_score()` | account→Party |
| `HealthScoreConfig` | — (plain, OneToOne tenant) | 1.11 | weight_tickets/nps/tasks/engagement, red/yellow_threshold (singleton per tenant) | — |
| `Survey` | `NPS-` | 1.11 | survey_type(nps/csat/ces), trigger, score(0–10), `classification`(auto in `save()` for NPS), `token`(auto in `save()`), sent_at/responded_at | account/contact→Party, related_case→Case |
| `ProductStock` | `STK-` | 1.12 | name, sku, **on_hand_qty (system-managed via PO receipt — NOT in the form)**, reorder_level, unit_cost, is_active; prop `is_low_stock` | — |
| `PurchaseOrder` | `PO-` | 1.12 | status(draft/sent/received/cancelled), order/expected_date, `total_amount`(via `recalc_total()`), received_at(system); `recalc_total()` = DB-side Sum(qty×price) | vendor→Party(org), owner→User |
| `PurchaseOrderLine` | — (plain) | 1.12 | item_name, quantity, unit_price, order(auto in view); prop `line_total` | `purchase_order`(CASCADE)/`product`→crm |
| `PartnerPortalAccess` | `PRT-` | 1.12 | access_level(read_only/lead_register/full), can_view_stock, can_register_leads, accepted_at, is_active | partner_party→Party, `portal_user`→User(OneToOne) |

**Service fn `compute_health_score(party, tenant)`** (`models.py`, wrapped in `transaction.atomic()`):
derives a 0–100 score from `crm.Case` (open/overdue), latest `crm.Survey` NPS, `crm.CrmTask` completion,
and open `crm.Opportunity` engagement, weighted by `HealthScoreConfig`; `update_or_create`s one row per
account. Called by `recompute_health_score` view + the seeder. (No invoice/payment signal — Accounting
not built.)

## URLs / views (1.7–1.12)

Standard `<entity>_list/_create/_detail/_edit/_delete` (delete POST-only) for: `expense`, `crmproject`,
`crmmilestone`, `timesheet`, `doctemplate`, `contractdocument`, `workflowrule`, `approvalrequest`,
`onboardingplan`, `healthscore`, `survey`, `productstock`, `crm_po` (PurchaseOrder), `partnerportalaccess`.
`workflowlog` is **list+detail only** (read-only). Custom actions (all `@require_POST`):
- **Expense:** `expense_submit` (owner, draft→submitted), `expense_approve`/`expense_reject` (**`@tenant_admin_required`**).
- **1.8:** `opportunity_to_project` (won opp → CrmProject, **idempotent** guard on `source_opportunity`).
- **1.9:** `contractdocument_add_signer`/`_remove_signer`; **public** `sign_document(token)` (no login; `select_for_update` against double-sign; refuses expired; sets `viewed_at`/`signed_at`/`declined_at`, flips contract→signed when all signed).
- **1.10:** `approvalrequest_approve`/`_reject` (**`@tenant_admin_required`**).
- **1.11:** `onboardingstep_add`/`_complete`(toggle)/`_delete`; `recompute_health_score`; `health_config_edit` (**`@tenant_admin_required`**); **public** `survey_respond(token)` (no login; clamps score 0–10, caps feedback 4000, no re-submit).
- **1.12:** `crm_po_add_line`/`_remove_line` (atomic + `recalc_total`), `crm_po_receive` (**`@tenant_admin_required`** — bumps `ProductStock.on_hand_qty` via `F()`, blocks received/cancelled); partner-facing `portal_dashboard`/`portal_po_list`/`portal_stock` (gated by `_portal_access` = PartnerPortalAccess pinned to `request.tenant`; non-portal users redirect).

## Security conventions (1.7–1.12) — important

- **System-managed fields are excluded from their ModelForm** (prevents mass-assignment self-approval/forgery): `Expense.status/submitted_by/approved_by`, `Timesheet.approved_by`, `ContractDocument.status/current_version`, `ProductStock.on_hand_qty`. Set them only in the dedicated action views.
- **Privileged actions are `@tenant_admin_required`:** expense approve/reject, approval approve/reject, `crm_po_receive` (inventory mutation), `health_config_edit` (tenant-wide config). Day-to-day CRUD stays `@login_required`.
- **File upload** (`Expense.receipt`): `ExpenseForm.clean_receipt` mirrors `core.DocumentForm` (extension allowlist + 20 MB cap) — blocks `.html`/`.svg` same-origin XSS.
- **Public endpoints** (`sign_document`, `survey_respond`): unguessable `secrets.token_urlsafe` tokens, `get_object_or_404(token=…)`, CSRF-protected (`{% csrf_token %}`, not exempt), extend `base_auth.html`. `body_snapshot` rendered **escaped** (no `|safe`).
- **No `|safe`/`eval`/raw SQL** anywhere in the new code; WorkflowRule conditions/actions are stored JSON, never executed.

## Seeder + sidebar (1.7–1.12)

`seed_crm` gained `_seed_extension(tenant)` (runs after base data; guarded by `Expense.exists()`): seeds
projects+milestones+timesheets, expenses, doc templates+contracts+signers, workflow rules+log+approvals,
onboarding plan+steps, surveys + `compute_health_score` per org party, product stock + a purchase order +
lines, and a PartnerPortalAccess (note: `portal_user=None` by default — assign a user to demo the portal).
`LIVE_LINKS` (`apps/core/navigation.py`) wires 1.7 (Expense Tracking only — Invoicing/Payment need
Accounting), 1.8 (Projects/Time Tracking/Resource Allocation + Milestones extra), 1.9 (E-Signatures/Document
Generation/File Repository), 1.10 (Trigger-Based Actions/Approval Processes/Webhooks + Workflow Logs extra),
1.11 (Onboarding Pipelines/Health Scoring/Surveys & Feedback (NPS)), 1.12 (Purchase Orders/Stock Tracking/
Vendor-Partner Portal + Partner Portal extra).

## Performance notes (1.7–1.12)

List views `select_related` the FKs their templates render and **defer large TextFields** not shown on lists
(`DocTemplate.body`, `ContractDocument.body_snapshot`, `WorkflowLog.error_msg`); `onboardingplan_list`
`prefetch_related("steps")` so `progress_pct` doesn't N+1; filter dropdowns use `.only(...)`; portal
list views are paginated. `PurchaseOrder.recalc_total()` / `compute_health_score` aggregate DB-side.
