---
name: crm
description: Work on the CRM module (Module 1 — 1.1–1.6 leads/opportunities/campaigns/cases/KB/tasks + accounts/contacts; 1.2 sales force automation = opportunities + splits + Kanban pipeline board, product catalog + price books + quote builder (printable), territories + sales quotas + forecast dashboard; 1.3 marketing automation = campaigns + campaign-members + email-templates + email-campaigns + landing-pages + form-submissions (public web-to-lead); 1.4 customer service = cases (SLA/breach + conversation thread + CSAT) + SLA policies + knowledge base (categories/feedback) + customer self-service portal (login) + public case-status & KB pages; 1.6 analytics & reporting = saved per-user dashboards + live-computed widgets (KPI/gauge/bar/line/pie/table) + standard reports (sales activity/performance/funnel/service) + report snapshots; 1.7 finance & billing = deal invoices (one-click quote→invoice conversion that drafts an accounting.Invoice — draft hand-off, L29) + payment receipts (printable + Stripe/PayPal/Razorpay gateway metadata) + expenses (billable flag / true-margin); 1.8 project & delivery = projects (deal→project convert + derived progress%/overdue + Kanban board with status-move) + milestones (sub-tasks) + timesheets (billable + owner-submit/admin-approve, status OFF the form) + resource allocation (capacity bookings + a workload board flagging overbooked vs free capacity); 1.9 document & contract = e-signatures (contracts + per-signer public token sign flow) + document generation (DocTemplate merge-vars rendered into a contract via an isolated escaping-only engine — no include/extends/load/safe, SSTI-safe; admin-gated authoring) + file repository (DocumentVersion immutable revisions + file uploads + a repo organized by account/deal); 1.10 automation & workflow = trigger-based actions (a real bounded rule-execution engine — admin Run evaluates a rule's conditions through a concrete-column allowlist and fires webhook/approval/log actions, one Workflow Log per match) + approval processes + webhooks (write-only HMAC signing secret + immutable signed delivery log; outbound HTTP deferred behind an SSRF guard); 1.11–1.12 onboarding/health-scores/surveys, product stock/purchase-orders/partner-portal). Use when the user asks to add/change/debug anything under apps/crm or templates/crm, extend the CRM seeder, touch CRM sidebar wiring (LIVE_LINKS 1.1–1.12), or invokes /crm.
---

# CRM Module (Module 1, sub-modules 1.1–1.12)

Customer Relationship Management. Reuses the unified core spine (NavERP-ERD.md): **Accounts and
Contacts are `core.Party`** (one record, many roles) — CRM adds only its own domain tables and FKs
into core **by string**. App path: `apps/crm/`. Templates: `templates/crm/`. URL prefix: `/crm/`
(`app_name="crm"`). Mounted in `config/urls.py`; app in `INSTALLED_APPS` as `apps.crm`.

Covers: 1.1 Core Data Management (Contacts/Accounts/Leads), 1.2 SFA (Opportunities; Forecasting →
overview), 1.3 Marketing (Campaigns), 1.4 Customer Service (Cases + Knowledge Base), 1.5 Activity
(Tasks), 1.6 Analytics & Reporting (saved per-user dashboards + live widgets, standard reports +
snapshots — recreated in detail, see §1.6). Quoting/Forecasting detail and the marketing
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
| `Opportunity` | `OPP-` | name, stage(prospecting/qualification/proposal/negotiation/closed_won/closed_lost), **forecast_category**(omitted/pipeline/best_case/commit/closed), amount, probability(0–100), close_date, **competitor**, **loss_reason**, **lost_at**(system), **stage_changed_at**(system via from_db/save), next_step, description; props `weighted_amount`, `is_open`, `is_won`; `OPEN_STAGES` | `account`/`primary_contact`→`core.Party`, `owner`→User, `source_lead`→`crm.Lead`, `campaign`→`crm.Campaign`, **territory**→`crm.Territory` (1.2 detail below) |
| `Campaign` | `CAM-` | name, type, **objective**(awareness/lead_gen/nurture/conversion/event/retention), status(planned/active/paused/completed/cancelled), **parent_campaign**(self-FK), start/end_date, budget_planned/actual, expected/actual_revenue, target_size, **utm_source/medium/campaign**, description; prop `roi` | `owner`→User, `parent_campaign`→self (1.3 detail below) |
| `Case` | `CASE-` | subject, type, priority(low/medium/high/critical), status(new/open/in_progress/waiting/resolved/closed), origin, description, due_at(manual), resolved_at(system), **sla_policy** + system **first_response_due/first_responded_at/resolution_due/closed_at** + **satisfaction_rating/comment/at** (CSAT) + **public_token**; props `is_open`/`is_overdue`/**is_response_overdue**/**is_resolution_overdue**; `save()` stamps resolved_at/closed_at + computes SLA dues + token (1.4 detail below) | `account`/`contact`→`core.Party`, `owner`→User, `sla_policy`→`crm.SlaPolicy` |
| `KnowledgeArticle` | `KB-` | title, category(legacy free-text), **kb_category** FK, slug, body, visibility(internal/external), status(draft/published/archived), views_count(system), **helpful_count/not_helpful_count**(system), **public_token**; prop `is_public`(published+external); `save()` generates token | `owner`→User, `kb_category`→`crm.KbCategory` |
| `CrmTask` | `TASK-` | subject, type(todo/call/email/meeting/follow_up), priority(low/medium/high), status(open/in_progress/done/cancelled), due_date, description, completed_at(system); **recurrence**(none/daily/weekly/monthly) + **recurrence_interval** + **recurrence_until** + **recurrence_parent**(self-FK, system); prop `is_overdue`; `save()` stamps/clears `completed_at` **and atomically spawns the next open occurrence on the open→done transition** (`_next_due`/`_spawn_next_occurrence`; monthly clamps month-end via stdlib `calendar`; idempotent) | `owner`→User, `party`→`core.Party`, `related_opportunity`→`crm.Opportunity`, **`related_case`→`crm.Case`** (1.5 detail below) |
| `CalendarEvent` | `EVT-` | title, event_type(meeting/call/demo/deadline/reminder/other), start, end, all_day, location, video_url, status(scheduled/confirmed/cancelled/completed), sync_source(manual/google/outlook/ical), reminder_minutes, description, **public_token**(system, editable=False); props `is_past`/`duration_display`; `save()` generates token | `owner`→User, `party`→`core.Party`, `related_opportunity`→`crm.Opportunity`, `related_case`→`crm.Case` |
| `EventAttendee` | — (plain child) | event(related_name `attendees`), party, name, email, rsvp_status(no_response/accepted/declined/tentative), is_organizer, responded_at(system); `save()` NULLs blank email + stamps `responded_at` on RSVP; `unique_together(event, email)` | `event`→`crm.CalendarEvent`, `party`→`core.Party` |
| `CommunicationLog` | `COM-` | channel(call/email/sms/note/meeting), direction(inbound/outbound), subject, body, occurred_at, duration_seconds, outcome(connected/voicemail/no_answer/busy/wrong_number), logged_via(manual/bcc_dropbox/voip/sync), email_message_id(system); props `duration_display`(mm:ss)/`is_call` | `party`→`core.Party`, `owner`→User, `related_opportunity`→`crm.Opportunity`, `related_case`→`crm.Case` |
| `AnalyticsDashboard` | `DASH-` | **1.6** saved per-user dashboard: name, description, is_shared, is_default, layout(one/two/three); prop `widget_count`; ordering `["-is_default","name"]` (see §1.6) | `owner`→User |
| `DashboardWidget` | — (plain child) | **1.6** tile: title, metric(20 choices→`analytics.WIDGET_METRICS`), chart_type(kpi/gauge/bar/line/pie/doughnut/table), date_range(last_7/30/90/quarter/year/all), size(small/medium/large/full), target_value, position; ordering `["position","id"]`; computed LIVE by `analytics.compute_widget` | `dashboard`→`crm.AnalyticsDashboard` (related_name `widgets`, CASCADE) |
| `AnalyticsReport` | `RPT-` | **1.6** saved standard report: name, description, report_type(sales_activity/sales_performance/funnel/service), date_range, group_by(month/week/owner/priority/stage), is_favorite, **last_run_at**(system, editable=False); computed LIVE by `analytics.compute_report` | `owner`→User |
| `ReportSnapshot` | — (plain child) | **1.6** frozen point-in-time run: title, generated_at(auto), summary(JSON KPI list), data(JSON columns/rows/chart_*); rendered as-stored (no recompute); ordering `["-generated_at"]` | `report`→`crm.AnalyticsReport` (related_name `snapshots`, CASCADE), `generated_by`→User |

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
  `knowledgearticle`, `task`, `calendarevent`, `communicationlog` (+ the 1.7–1.12 entities). 1.5 also adds
  inline `event_attendee_add`/`_delete` (POST) and the public token routes `event_invite`/`event_ics` (no
  login) — see §1.5.
- **1.6** adds `dashboard_*` (+ `widget_create`/`widget_edit`/`widget_delete`/`widget_move <pk>/<direction>`),
  `report_*` (+ POST `report_favorite`, `report_snapshot`), and `snapshot_detail`/`snapshot_delete` — see §1.6.
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
(`opportunity/ territory/ product/ pricebook/ quote/ salesquota/` + standalone `pipeline.html`/`forecast.html`
+ `quote/print.html` — see §1.2), `marketing/` (`campaign/ campaignmember/ emailtemplate/ emailcampaign/ landingpage/
formsubmission/` + standalone public `landing_public.html` — see §1.3), `service/` (`case/ knowledgearticle/
slapolicy/ kbcategory/ customerportalaccess/` + standalone public `case_public.html`/`kb_public.html` + portal
`portal_case_list/detail/form.html` — see §1.4), `activities/` (`task/ calendarevent/ communicationlog/` +
standalone public `event_invite.html` — see §1.5),
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
gains firmographics/contact details without `--flush`), seeds **§1.3 marketing data** via `_seed_marketing`
(self-guards on `EmailTemplate`), **§1.2 SFA data** via `_seed_sfa` (self-guards on `Product`), and **§1.4
help-desk data** via `_seed_service` (self-guards on `SlaPolicy`), **§1.5 activity data** via
`_seed_activities` (self-guards on `CalendarEvent`), and **§1.6 analytics data** via `_seed_analytics`
(self-guards on `AnalyticsDashboard`: 2 dashboards w/ 7+4 widgets, 4 reports, a baseline snapshot). Prints the demo-login
reminder and the `admin`-has-no-tenant warning. Run after `seed_core`/`seed_accounts`/`seed_tenants`.

## Sidebar wiring (`apps/core/navigation.py` → `LIVE_LINKS`)

Keys must match the `NavERP.md` §1 feature bullets verbatim to light up:
- `1.1`: Contacts → `crm:contact_list`; Accounts (Companies) → `crm:account_list`; Leads (Potential
  Customers) → `crm:lead_list`
- `1.2` (recreated in detail — all 3 bullets live): Opportunity Management (Deals) → `crm:opportunity_list`;
  Pipeline Board → `crm:opportunity_board`; Product Catalog (Quoting) → `crm:product_list`; Quotes →
  `crm:quote_list`; Price Books → `crm:pricebook_list`; Forecasting → `crm:forecast`; Sales Quotas →
  `crm:salesquota_list`; Territories → `crm:territory_list` (see "§1.2 Sales Force Automation" section)
- `1.3` (recreated in detail — all 3 bullets live): Campaign Management → `crm:campaign_list`; Campaign Members
  → `crm:campaignmember_list`; Email Marketing → `crm:emailcampaign_list`; Email Templates →
  `crm:emailtemplate_list`; Landing Pages & Forms → `crm:landingpage_list`; Form Submissions →
  `crm:formsubmission_list` (see "§1.3 Marketing Automation" section)
- `1.4` (recreated in detail — all 3 bullets live): Case / Ticket Management → `crm:case_list`; SLA Policies →
  `crm:slapolicy_list`; Solutions & Knowledge Base → `crm:knowledgearticle_list`; KB Categories →
  `crm:kbcategory_list`; **Customer Self-Service Portal → `crm:customerportalaccess_list`** (the staff-facing
  access-management page — the customer-facing `portal_case_list` is login-gated and would bounce staff to the
  dashboard, so it's the secondary "Customer Portal" extra link; mirrors the 1.12 Vendor/Partner Portal wiring)
  (see "§1.4 Customer Service & Support" section)
- `1.5` (recreated in detail — all 3 bullets live): Task Management → `crm:task_list`; Calendar Integration →
  `crm:calendarevent_list`; Email & Call Integration → `crm:communicationlog_list` (the public
  `event_invite`/`event_ics` token pages are NOT sidebar targets — L32) (see "§1.5 Activity & Communication" section)
- `1.6` (recreated in detail — both bullets live): Dashboards → `crm:dashboard_list`; Standard Reports →
  `crm:report_list`; + extra Analytics Overview → `crm:overview` (the module KPI landing) (see "§1.6 Analytics & Reporting" section)

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

# §1.2 Sales Force Automation (recreated in detail)

The thin single-`Opportunity` 1.2 was rebuilt to cover all three NavERP.md §1.2 bullets. Migrations `0008`
(Opportunity columns + 7 tables), `0009`/`0010`/`0011` (SalesQuota territory unique + index, percentage
validators). Models in the same `apps/crm/models.py`:

| Model | Prefix | Bullet | Key fields / behavior | Reuse |
|-------|--------|--------|-----------------------|-------|
| `Opportunity` (enhanced) | `OPP-` | Opportunity Management | + `forecast_category`, `competitor`, `loss_reason`, `lost_at` + `stage_changed_at` (system, via `from_db`/`save()` — stamps on stage change / closed_lost), `territory`. Board + advance action. | `territory`→Territory |
| `OpportunitySplit` | — (plain) | commission/credit splits | `opportunity`(CASCADE, `related_name="splits"`), `user`, `split_type`(revenue/overlay), `percentage`(0–100); `clean()` rejects ≤0 and revenue sum >100%; prop `split_amount`. Inline on opp detail. | `user`→User |
| `Territory` | `TER-` | Forecasting (by territory) | name, region, segment, `parent`(self-FK hierarchy), `manager`, is_active | `parent`→self, `manager`→User |
| `Product` | `PRD-` | Product Catalog | name, sku, product_type(good/service/subscription), unit_price, cost, tax_pct, is_active; prop `margin_pct`. CRM-owned (→ core.Item later), distinct from 1.12 ProductStock. | — |
| `PriceBook` | `PB-` | price books for regions/tiers | name, currency_code, region, tier, `price_adjustment_pct`(±%; floored at −100), is_default; `adjusted_price(base)`. (PriceBookEntry per-product override = future.) | — |
| `Quote` | `QUO-` | Quoting | `opportunity`(SET_NULL, `related_name="quotes"`), `account`→Party, `price_book`, **system**: status(draft/sent/accepted/declined/expired) + subtotal/tax_total/total + sent_at/accepted_at (all excluded from form), discount_pct, valid_until, currency_code, terms; `recalc_totals()` sums lines **in Python** (Decimal-safe — NOT `F()/100`, which integer-divides on SQLite); props `is_open`/`is_expired`. | `price_book`→PriceBook |
| `QuoteLine` | — (plain) | line items/discounts/tax | `quote`(CASCADE, `related_name="lines"`), `product`(SET_NULL), description, quantity, unit_price, discount_pct, tax_pct, order; props `line_subtotal`/`line_tax`/`line_total`. Inline on quote detail; defaults unit_price from product × price-book adjustment. | `product`→Product |
| `SalesQuota` | `QTA-` | quota vs. actual | `owner`, `territory`, period_type(month/quarter/year), period_year, period_number, target_amount; `unique_together(tenant,owner,territory,period_type,period_year,period_number)` + form dup guard. | `owner`→User, `territory`→Territory |

**Routes (`urls.py`):** standard `<entity>_list/_create/_detail/_edit/_delete` (delete POST-only) for
`territory`/`product`/`pricebook`/`quote`/`salesquota`. Custom: `opportunity_board` (Kanban GET),
`opportunity_advance`, `opportunitysplit_add`/`_remove`; `quoteline_add`/`_remove` (atomic + `recalc_totals`),
`quote_send`/`_accept`/`_decline`, `quote_print` (login-gated); `forecast` (dashboard).

**Views & actions (`views.py`):** all `@login_required`, tenant-scoped, `crud_*` helpers. `opportunity_detail`
recreated (splits panel w/ inline add + revenue total, quotes panel, tasks). `opportunity_board` — one grouped
aggregate for per-stage count/total + a slice per column. `opportunity_advance` — forward stage flow; closed_won
sets probability 100 + forecast_category closed; fixed-allowlist redirect (no open redirect). Quote actions are
system-managed state transitions (status/totals/timestamps never from the form). `forecast` aggregates DB-side
(weighted pipeline by forecast_category + quota attainment matched per (owner,territory)). **Quote send/accept/
decline + opportunity_advance stay `@login_required`** (rep-owned pipeline; audit-logged) — not admin-gated.

**Forms (`forms.py`):** `OpportunityForm` (+ forecast_category/competitor/loss_reason/territory; lost_at/
stage_changed_at excluded). `QuoteForm` excludes status + subtotal/tax_total/total + sent_at/accepted_at.
`SalesQuotaForm.clean()` blocks duplicate (owner+territory+period). Inline `QuoteLineForm`/`OpportunitySplitForm`.
Percentage/discount/tax fields carry Min/Max validators (no negative/over-100 values).

**Templates (`templates/crm/sales/`):** entity folders `opportunity/ territory/ product/ pricebook/ quote/
salesquota/` (each list/detail/form; quote also `print.html`) + standalone `pipeline.html` (Kanban board) and
`forecast.html` (dashboard, Chart.js via overview's json_script pattern). Quote detail = the quote builder
(inline lines, recalculated totals, send/accept/decline). Never `|safe`; quote terms via `linebreaksbr`.

**Seeder:** `_seed_sfa(tenant)` runs unconditionally (self-guards on `Product`): 2 territories, 3 catalog
products, 2 price books, opportunity splits, a recalculated quote with lines, 2 sales quotas; enriches the first
opp with territory/competitor/forecast. Backfills without `--flush`.

**Tests:** `apps/crm/tests/test_sfa.py` (235 tests).

---

# §1.4 Customer Service & Support / Help Desk (recreated in detail)

The basic `Case` + `KnowledgeArticle` were rebuilt to cover all three NavERP.md §1.4 bullets. Migration `0012`
(Case + KnowledgeArticle columns + 4 tables). Models in the same `apps/crm/models.py`:

| Model | Prefix | Bullet | Key fields / behavior | Reuse |
|-------|--------|--------|-----------------------|-------|
| `SlaPolicy` | `SLA-` | SLA deadline warnings | name, is_active, is_default; per-priority **hour** targets `response_{low,medium,high,critical}` + `resolution_{...}`; `targets_for(priority)`→(resp_h, res_h). **CRUD `@tenant_admin_required`** (tenant-wide config). | — |
| `Case` (enhanced) | `CASE-` | Case / Ticket Management | + `sla_policy`, system `first_response_due`/`first_responded_at`/`resolution_due`/`closed_at` + CSAT `satisfaction_rating`/`_comment`/`_at` + `public_token`; `save()` computes dues (once, when blank — skips the lazy-load when both set) + stamps closed_at + token; props `is_response_overdue`/`is_resolution_overdue`. | `sla_policy`→SlaPolicy |
| `CaseComment` | — (plain) | conversation thread | `case`(CASCADE, `related_name="comments"`), `author`, `author_name`, `body`, `is_public` (customer reply vs internal note). Portal/public adds force `is_public=True`; first **public** reply stamps `Case.first_responded_at` (atomic). | `author`→User |
| `KbCategory` | `KBC-` | Solutions & KB | name, slug, `parent`(self-FK), order, is_active. | `parent`→self |
| `KnowledgeArticle` (enhanced) | `KB-` | Solutions & KB | + `kb_category`, `helpful_count`/`not_helpful_count` (system), `public_token`, slug; prop `is_public`(published+external). | `kb_category`→KbCategory |
| `CustomerPortalAccess` | `CSP-` | Self-Service Portal | `customer_party`→Party, `portal_user` OneToOne→User, `can_submit_cases`, accepted_at, is_active. Mirrors PartnerPortalAccess. **CRUD `@tenant_admin_required`** (granting a portal login = IAM). | `customer_party`→Party |

**Routes (`urls.py`):** standard `<entity>_list/_create/_detail/_edit/_delete` (delete POST-only) for
`slapolicy`/`kbcategory`/`customerportalaccess`. Custom: `case_comment_add`. **Public** (no login):
`cases/track/<token>/` (case_public), `kb/<token>/` (kb_public) + `kb/<token>/helpful/` (kb_helpful).
**Portal** (login): `portal/cases/` (list), `portal/cases/new/` (create), `portal/cases/<pk>/` (detail).

**Views & actions (`views.py`):** all `@login_required`, tenant-scoped, `crud_*` helpers. `case_detail` recreated
(SLA breach banners + comments thread + inline internal/public add). `case_comment_add` stamps first_responded_at
via an atomic `filter().update()`. **Public** `case_public(token)` — status + public-only comments + reply + CSAT
(submitted-once via atomic update); `kb_public(token)` — only published+external resolves (else 404), F() view
count; `kb_helpful(token)` — POST-only F() vote. **Portal** — `_customer_portal_access` gate (mirrors
`_portal_access`); `portal_case_list/detail` strictly scope to the user's own `customer_party` (null-party
rejected — no `Q(account=None)` leak); `portal_case_create` forces account=customer_party + origin=portal +
default SLA. **SlaPolicy + CustomerPortalAccess create/edit/delete are `@tenant_admin_required`.**

**Forms (`forms.py`):** `CaseForm` (+ sla_policy; SLA timers/closed_at/CSAT/public_token excluded),
`KnowledgeArticleForm` (+ kb_category; helpful counts/public_token excluded), `SlaPolicyForm`, `KbCategoryForm`
(self-parent exclusion), `CustomerPortalAccessForm`, inline `CaseCommentForm`, plain `PublicSatisfactionForm`/
`PublicCommentForm` for the public page.

**Templates (`templates/crm/service/`):** recreated `case/` + `knowledgearticle/`; entity folders `slapolicy/
kbcategory/ customerportalaccess/` (list/detail/form); standalone **public** `case_public.html`/`kb_public.html`
(extend `base_auth.html`, escaped via `linebreaksbr`, never `|safe`); standalone **portal** `portal_case_list/
detail/form.html` (extend `base.html`). Internal notes (`is_public=False`) never render on the public/portal pages.

**Seeder:** `_seed_service(tenant)` runs unconditionally (self-guards on `SlaPolicy`): a default SlaPolicy, 2 KB
categories, internal+public comments on the first case, article category links, public-token backfill on existing
cases/articles, and a CustomerPortalAccess (portal_user unassigned by default — assign a user to demo the login).

**Tests:** `apps/crm/tests/test_helpdesk.py` (198 tests).

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

# §1.5 Activity & Communication Management (recreated in detail)

The thin single-`CrmTask` 1.5 was rebuilt to cover all three NavERP.md §1.5 bullets. Migrations `0013`
(CrmTask recurrence/related_case + the 3 new models) + `0014` (`public_token` editable=False). All templates
under `templates/crm/activities/`.

- **Task Management** (`CrmTask`, enhanced) — to-dos **+ automated recurring tasks**. On the **open→done
  transition** `save()` (wrapped in `transaction.atomic`) spawns the next open occurrence via
  `_spawn_next_occurrence()`: copies the task, advances `due_date` by `recurrence_interval`
  (`_next_due`; monthly clamps to the month's last day with stdlib `calendar`, since `python-dateutil`
  isn't installed), links it to the series origin (`recurrence_parent`), stops past `recurrence_until`, and
  guards against a duplicate at the same next due date. `CrmTaskForm` makes `recurrence`/`recurrence_interval`
  optional (`clean_*` coerce blank → none/1), so a simple to-do needs no recurrence choice. Routes `crm:task_*`.
- **Calendar Integration** (`CalendarEvent` [EVT] + `EventAttendee`) — meeting scheduling, **invite links**,
  Google/Outlook/iCal **sync** (modeled as `sync_source` provenance + a real ICS export — OAuth push is
  deferred). Full CRUD `crm:calendarevent_*`; attendees managed **inline on the event detail**
  (`crm:event_attendee_add`/`_delete`, POST; upsert by event+email). Two **public token** pages (no login,
  `public_token` bearer, `# WARNING` rate-limit note): `crm:event_invite` (event details + public **RSVP**
  upsert by email, **first-response-wins** so a shared-token visitor can't overwrite a recorded answer) and
  `crm:event_ics` (RFC-5545 `text/calendar` download — UTC times, `;,\n` escaped, 75-octet line folding).
- **Email & Call Integration** (`CommunicationLog` [COM]) — one unified activity-history record: call logging
  (duration/outcome) **and** email sync via BCC dropbox (`logged_via` provenance; `email_message_id` dedup).
  Full CRUD `crm:communicationlog_*`; filters channel/direction/logged_via. (Body-search is kept — matches the
  app-wide TextField-search pattern, e.g. Expense/Timesheet/Survey/PO.)

Seeder `_seed_activities` (self-guards on `CalendarEvent`): a weekly recurring task + a spawned occurrence,
4 calendar events with 2–3 attendee RSVPs each, 6 communication logs (calls/emails/note/SMS). Tests:
`apps/crm/tests/test_activities.py` (137). **Deferred** (see `todo.md`): OAuth calendar push, live BCC mail
engine, VoIP/recording, email open/click tracking, per-invitee tokens, and a `recurrence_anchor_day` to fix
monthly last-day drift on subsequent spawns.

# §1.6 Analytics & Reporting (recreated in detail)

The stub 1.6 (both bullets pointing at `crm:overview`) was rebuilt into a real sub-module covering both
NavERP.md §1.6 bullets. Migration `0015` added 4 models. **The whole compute layer lives in
`apps/crm/analytics.py`** — `models.py` owns only the field choice lists and never imports `analytics.py`
(one-way edge → no circular import). Every figure is a **read-only aggregation over existing CRM data**
(Opportunity/Case/Lead/Campaign/CrmTask/CommunicationLog); nothing stores a derived number except
`ReportSnapshot`, which deliberately freezes one run for trend history.

- **Dashboards** (`AnalyticsDashboard` [DASH] + `DashboardWidget`) — saved, per-user dashboards whose widgets are
  **computed live on render** (real-time). `dashboard_detail` loops the widgets, calls `analytics.compute_widget`
  per tile, and renders KPI cards / gauges (HTML + `.progress` bar) / tables (HTML) directly, while bar/line/
  pie/doughnut series go to Chart.js via one `json_script` (`dash-charts`) the JS iterates. `layout` (one/two/
  three cols) drives a CSS-grid `repeat(cols, minmax(200px,1fr))`; `size` → column span (computed in the view).
  Widget order is `position`; **`widget_move <pk>/<direction>`** (POST) reorders via `bulk_update` (normalizes to
  0..n-1). `is_shared`/`is_default` are **tenant-wide → only tenant admins see those form fields** (`can_share`
  kwarg on `AnalyticsDashboardForm`; `dashboard_create`/`_edit` are hand-written to pass it).
- **Standard Reports** (`AnalyticsReport` [RPT] + `ReportSnapshot`) — 4 canned `report_type`s computed by
  `analytics.compute_report`: `sales_activity` (opps created / tasks done / comms logged per period, line),
  `sales_performance` (top performers: owner | deals won | revenue | avg, bar), `funnel` (stage count/value +
  drop-off %, single grouped query + Python cumulative roll-up), `service` (cases / resolved / avg resolution &
  first-response hours / avg CSAT by priority-or-period, bar). `report_detail` computes live, stamps
  `last_run_at` (via `.update()`, never `save()`), lists snapshots (capped 50, JSON cols `.only()`-deferred).
  **`report_favorite`** (POST toggle) and **`report_snapshot`** (POST → freezes `compute_report` output into
  `ReportSnapshot.summary`/`.data` JSON, atomic) are the custom actions; `snapshot_detail` re-renders the stored
  JSON with no recompute.

`analytics.WIDGET_METRICS` is the single source of truth for widget compute (key → kind scalar/series/table +
allowed chart types + resolver); `DashboardWidgetForm.clean()` rejects a chart_type the metric can't render, and
`AnalyticsReportForm.clean()` rejects a `group_by` the report_type doesn't honour (e.g. service ≠ owner). Date
windows: `analytics.range_bounds(key)` (filters `created_at`; `_compute_service` averages durations in Python on
purpose — `Avg(DurationField)` is float-µs on SQLite vs timedelta on MariaDB).

Seeder `_seed_analytics` (self-guards on `AnalyticsDashboard`): a "Sales Command Center" (3-col, 7 widgets:
KPIs + gauge + bar/line/doughnut + a top-performers table) and a "Service Desk" (2-col, 4 widgets), the 4
standard reports, and a baseline snapshot of the top-performers report. Tests:
`apps/crm/tests/test_analytics.py` (173). **Deferred** (see `todo.md`): drag-and-drop JS layout builder,
scheduled email delivery, PDF/CSV export, cross-object custom report builder, nightly auto-snapshot, and the
larger-scale indexes (`Opportunity(tenant,owner)`, `Campaign(tenant,actual_revenue)`,
`ReportSnapshot(tenant,report,generated_at)`) + a per-request shared-base-queryset cache for many-widget dashboards.

# Sub-modules 1.7–1.12 (extension — finance/delivery/docs/automation/success/vendor)

Added as an extension pass on the **same `apps/crm` app** (one big `models.py`, `forms.py`, `views.py`,
`urls.py`, `admin.py`, `seed_crm.py`). Migration `0005` created the original 18 tables; later migrations
added the recreations: `0016` **1.7** (`DealInvoice`, `PaymentReceipt`, `Expense.is_billable`), `0017`–`0018`
**1.8** (`ResourceAllocation` + project fields), `0019`–`0020` **1.9** (`DocumentVersion` + contract fields),
`0021`–`0022` **1.10** (`Webhook` + `WebhookDelivery`; `WorkflowLog` `(tenant,rule,-fired_at)` index). **Spine status:**
**Accounting (Module 2) is now built and owns the financial ledger** (`accounting.Invoice/InvoiceLine/
Payment/PaymentAllocation/RecurringInvoice/Currency`), so **1.7 was recreated to REUSE it** — the CRM layer
adds the deal-facing wrappers (`DealInvoice`/`PaymentReceipt`) and the quote→invoice conversion creates a
**draft** `accounting.Invoice`; issuing/GL-posting + confirmed cash-application stay in Accounting (**draft
hand-off**, lesson L29 — never a second ledger). **Still future:** `Item/StockMove` (Inventory 5),
`PurchaseOrder/GoodsReceipt` (Procurement 6) — so **1.12** still ships **CRM-owned**
`PurchaseOrder`/`PurchaseOrderLine`/`ProductStock`. `Expense.currency_code` stays a CharField; health
scoring derives from CRM signals. See `.claude/tasks/todo.md`.

## Models (1.7–1.12) — all `TenantNumbered` unless noted

| Model | Prefix | Sub-mod | Key fields / behavior | Reuse |
|-------|--------|---------|-----------------------|-------|
| `DealInvoice` | `DINV-` | 1.7 | **CRM wrapper over the accounting ledger** — links a deal (opportunity/quote/account) to the `accounting.Invoice` it generated. `invoice` FK is **editable=False** (set by the conversion action / manual create view, never a normal form field). Read-through props `invoice_number/invoice_status/invoice_total/amount_paid/balance_due` **guard a None invoice**. List annotates `amt_paid`/`bal_due` via a `Subquery` (no per-row N+1). | `opportunity`/`quote`→crm, `account`→Party, `invoice`→**accounting.Invoice**, `recurring_invoice`→**accounting.RecurringInvoice** |
| `PaymentReceipt` | `RCPT-` | 1.7 | customer receipt for a (partial/milestone) payment on a deal invoice; **printable** (`receipt.html`, `window.print()`); `METHOD` + `GATEWAY`(manual/stripe/paypal/razorpay) + `gateway_txn_id` metadata; optional `payment` link **scoped to the tenant's inbound payments** | `deal_invoice`→DealInvoice(CASCADE), `payment`→**accounting.Payment**(SET_NULL) |
| `Expense` | `EXP-` | 1.7 | category, amount, **currency_code**(char), expense_date, **`is_billable`** (true=re-billed to client → excluded from true margin), **receipt** FileField (allowlist+20MB via `clean_receipt`), status(draft/submitted/approved/rejected), **submitted_by/approved_by/status are system-set — NOT in the form** | `opportunity`/`project`→crm, submitted_by/approved_by→User |
| `CrmProject` | `PRJ-` | 1.8 | name, status(planning/active/on_hold/completed/cancelled), start/end_date, budget, owner, description; **derived props** `progress_pct` (completed÷total milestones — list view annotates `ms_total`/`ms_done` to avoid N+1) + `is_overdue` | `account`→Party, `source_opportunity`→Opportunity |
| `CrmMilestone` | `MS-` | 1.8 | title, kind(milestone/task), status(not_started/in_progress/completed/blocked), order, `parent`(self-FK subtasks), `completed_at`(system via `save()`); shown on the **Kanban board** + moved via `crmmilestone_move` | `project`→CrmProject(CASCADE), assignee→User |
| `Timesheet` | `TS-` | 1.8 | date, hours, is_billable; **status + approved_by are system-managed — NOT in the form** (advanced only by submit/approve/reject; closes a self-approve gap). edit/delete restricted to draft/rejected; submit gated to owner/admin | `project`(CASCADE)/`milestone`→crm, employee→User, client→Party |
| `ResourceAllocation` | `RA-` | 1.8 | **capacity booking** — assignee, role, `hours_per_week`, start/end_date(null=ongoing), status(planned/active/completed/cancelled); `overlap_hours(win_start,win_end)` prorates planned hours; feeds the **workload board** (planned vs logged vs 40h/wk capacity → overbooked/free). Form `clean`: end≥start | `project`→CrmProject(CASCADE), assignee→User |
| `DocTemplate` | `TPL-` | 1.9 | name, template_type(nda/proposal/contract/quote/receipt), `body`(merge-var HTML, deferred on list) , is_active | owner→User |
| `ContractDocument` | `CTR-` | 1.9 | name, status(draft/sent/viewed/signed/declined/expired/archived), current_version, body_snapshot(deferred on list), signed_at/expires_at; **status/current_version/body_snapshot are system-managed — NOT in the form** (body_snapshot is GENERATED from the template or captured as a version) | `template`→DocTemplate, opportunity→crm, account→Party |
| `SignerRecord` | — (plain) | 1.9 | per-signer: signer_name/email, `token`(secrets.token_urlsafe(32)), order(auto in view), viewed_at/signed_at/declined_at/ip_address | `contract`→ContractDocument(CASCADE) |
| `DocumentVersion` | — (plain) | 1.9 | **immutable contract revision** (File Repository / version control): version_no, body_snapshot, **file**(FileField, allowlisted), change_note, created_by; `unique_together(tenant,contract,version_no)`. **list+detail only — never edited**; created by generate / version_add | `contract`→ContractDocument(CASCADE), created_by→User |
| `WorkflowRule` | `WFR-` | 1.10 | name, is_active, trigger_entity/event/field/value, `conditions`/`actions` JSONField (declarative; **interpreted by the engine, never `eval()`'d**), delay_value/unit. **Authoring + Run are `@tenant_admin_required`** | owner→User |
| `WorkflowLog` | — (plain) | 1.10 | append-only: record_label, status(success/failed/skipped), fired_at, error_msg. **Read-only — list+detail only, no create/edit/delete**; `(tenant,status)`/`(tenant,fired_at)`/`(tenant,rule,-fired_at)` indexes | `rule`→WorkflowRule(SET_NULL) |
| `ApprovalRequest` | `APR-` | 1.10 | subject, record_label, status(pending/approved/rejected/expired), threshold_field/value, approved_at/rejected_at(system), reason; prop `is_pending` | rule→WorkflowRule, approver/requested_by→User |
| `Webhook` | `WH-` | 1.10 | name, target_url, trigger_entity/event (reuse WorkflowRule choices), **`secret`** (write-only HMAC key — PasswordInput render_value=False, masked via `secret_masked`, excluded from admin + redacted in audit; blank-on-edit keeps it), is_active, `headers` JSONField (validated flat str dict, no CRLF), description; prop `secret_masked` (••••+last4); `(tenant,is_active)`/`(tenant,trigger_entity)` indexes | — |
| `WebhookDelivery` | — (plain) | 1.10 | **immutable signed-delivery log**: event, payload(JSON), signature(HMAC-SHA256 hex), status(pending/success/failed/simulated), response_code, error_msg, created_at. **list+detail only — system-created** (Test action or a rule's webhook action); `(tenant,webhook)`/`(tenant,status)` indexes | `webhook`→Webhook(CASCADE, `related_name="deliveries"`) |
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

Standard `<entity>_list/_create/_detail/_edit/_delete` (delete POST-only) for: `dealinvoice`,
`paymentreceipt`, `expense`, `crmproject`, `crmmilestone`, `timesheet`, `resourceallocation`, `doctemplate`, `contractdocument`,
`workflowrule`, `approvalrequest`, `onboardingplan`, `healthscore`, `survey`, `productstock`, `crm_po`
(PurchaseOrder), `partnerportalaccess`. `workflowlog` is **list+detail only** (read-only). Custom actions
(all `@require_POST` unless noted):
- **1.7 Invoicing:** `dealinvoice_from_quote(quote_pk)` (accepted-quote → draft `accounting.Invoice` + InvoiceLines + DealInvoice, `transaction.atomic`, **idempotent** guard, folds per-line + quote-level discount + tax so `invoice.total == quote.total`). `dealinvoice_create`/`_edit` are **custom** (not `crud_*`) so the `editable=False` `invoice` link is set on create and popped on edit. The deal-invoice detail's "Issue invoice" button POSTs to `accounting:invoice_post` (**admin-gated in the template**; GL posting stays in Accounting).
- **1.7 Payments:** `paymentreceipt_print` (GET — standalone printable `receipt.html`, `window.print()`).
- **Expense:** `expense_submit` (owner, draft→submitted), `expense_approve`/`expense_reject` (**`@tenant_admin_required`**).
- **1.8 Projects/Resource:** `opportunity_to_project` (won opp → CrmProject, **idempotent** guard on `source_opportunity`). `crmproject_board` (Kanban — milestones bucketed by status) + `crmmilestone_move` (status-move, value **whitelisted** against STATUS_CHOICES, tenant-scoped). `resource_workload` (capacity board — planned allocations [prorated via `overlap_hours`] vs logged timesheets [excl. rejected] vs 40 h/wk capacity, overbooked flag; 2–3 aggregate queries, no per-person N+1). `resourceallocation_*` CRUD.
- **1.8 Timesheet workflow:** `timesheet_submit` (**owner or admin only**, draft→submitted), `timesheet_approve`/`timesheet_reject` (**`@tenant_admin_required`**); `timesheet_edit`/`timesheet_delete` restricted to **draft/rejected** (no post-approval mutation/erase). `status`/`approved_by` are OFF `TimesheetForm` — closes the self-approve gap.
- **1.9 E-Sign:** `contractdocument_add_signer`/`_remove_signer`; `contractdocument_send` (draft→sent, needs body + ≥1 signer); **public** `sign_document(token)` (no login; `select_for_update` against double-sign; refuses expired; sets `viewed_at`/`signed_at`/`declined_at`, flips contract→signed when all signed).
- **1.9 Generation:** `contractdocument_generate` (renders the linked DocTemplate body's merge-vars into `body_snapshot` via the **isolated `_DOC_ENGINE`** + string-only `_safe_doc_context` → SSTI-safe; **draft-only**; captures a DocumentVersion). `doctemplate_create`/`_edit`/`_delete` are **`@tenant_admin_required`** (server-rendered authoring).
- **1.9 File Repository:** `contractdocument_version_add` (file upload → new DocumentVersion; blocked on signed/declined), `documentversion_detail` (read-only), `document_repository` (contracts by account/deal + version counts).
- **1.10 Engine:** `workflowrule_run` (**`@tenant_admin_required`**, POST) → `_run_rule` maps trigger_entity→model, loads ≤50 recent tenant records, evaluates conditions via `_eval_conditions`/`_safe_record_field` (**allowlist: concrete non-relation columns only** — no method/property/FK/`pk`/token access; ops eq/ne/gt/lt/gte/lte/contains/icontains), fires actions (webhook→`_deliver_webhook` HMAC-signs a payload + records a WebhookDelivery; approval→ApprovalRequest; else logged), one WorkflowLog per matched record inside a **per-record `transaction.atomic()` savepoint** (a failing record can't poison the failure log). `workflowrule_create`/`_edit`/`_delete` are **`@tenant_admin_required`** (rules are executable).
- **1.10 Webhooks:** `webhook_list`/`_detail` (`@login_required`); `webhook_create`/`_edit`/`_delete` + `webhook_test` (**`@tenant_admin_required`**; Test records a signed `manual.test` delivery); `webhookdelivery_list`/`_detail` (read-only). `_deliver_webhook` does **NO outbound HTTP** — records + HMAC-signs only; the real POST is deferred behind a `# WARNING (SSRF)` guard (https-only, resolve-once + pin-IP to block DNS-rebinding, port 443, no redirects, timeout, capped read).
- **1.10 Approvals:** `approvalrequest_approve`/`_reject` (**`@tenant_admin_required`**).
- **1.11:** `onboardingstep_add`/`_complete`(toggle)/`_delete`; `recompute_health_score`; `health_config_edit` (**`@tenant_admin_required`**); **public** `survey_respond(token)` (no login; clamps score 0–10, caps feedback 4000, no re-submit).
- **1.12:** `crm_po_add_line`/`_remove_line` (atomic + `recalc_total`), `crm_po_receive` (**`@tenant_admin_required`** — bumps `ProductStock.on_hand_qty` via `F()`, blocks received/cancelled); partner-facing `portal_dashboard`/`portal_po_list`/`portal_stock` (gated by `_portal_access` = PartnerPortalAccess pinned to `request.tenant`; non-portal users redirect).

## Security conventions (1.7–1.12) — important

- **System-managed fields are excluded from their ModelForm** (prevents mass-assignment self-approval/forgery): `Expense.status/submitted_by/approved_by`, **`Timesheet.status/approved_by`** (1.8 — status moved off the form), **`ContractDocument.status/current_version/body_snapshot`** (1.9 — body_snapshot is generated, not typed), `ProductStock.on_hand_qty`, **`Webhook.secret`** (1.10 — write-only; blank-on-edit keeps the stored value). Set them only in the dedicated action views.
- **Server-side document generation is sandboxed** (1.9): user-authored `DocTemplate.body` renders via `_DOC_ENGINE` — an isolated `Engine` whose builtins are restricted libraries carrying every Django default tag/filter EXCEPT `loader_tags` and the `safe`/`safeseq`/`json_script`/`autoescape` escape-bypass members, with `libraries={}`, `dirs=[]`, `app_dirs=False`, against a STRING-ONLY context (`_safe_doc_context`, no model instances). A body therefore can't `{% include %}`/`{% extends %}`/`{% load %}`, disable escaping, or traverse model attrs/methods; `body_snapshot` is rendered ESCAPED (no `|safe`). Authoring is `@tenant_admin_required`.
- **Privileged actions are `@tenant_admin_required`:** expense approve/reject, **timesheet approve/reject**, approval approve/reject, `crm_po_receive` (inventory mutation), `health_config_edit` (tenant-wide config). Day-to-day CRUD stays `@login_required`; **timesheet submit is owner-or-admin**, and timesheet edit/delete are blocked once approved.
- **File upload** (`Expense.receipt`): `ExpenseForm.clean_receipt` mirrors `core.DocumentForm` (extension allowlist + 20 MB cap) — blocks `.html`/`.svg` same-origin XSS.
- **Public endpoints** (`sign_document`, `survey_respond`): unguessable `secrets.token_urlsafe` tokens, `get_object_or_404(token=…)`, CSRF-protected (`{% csrf_token %}`, not exempt), extend `base_auth.html`. `body_snapshot` rendered **escaped** (no `|safe`).
- **No `|safe`/`eval`/raw SQL** anywhere in the new code. WorkflowRule conditions/actions are stored JSON, **interpreted** by the 1.10 engine (never `eval()`'d): condition fields are read through `_safe_record_field`, an **allowlist of concrete non-relation columns** (rejects methods/`@property`/FK objects/`pk`/token fields), and the operator set is a closed enum. `Webhook.secret` is write-only (HMAC signing key — masked, never rendered/logged/audited); `_deliver_webhook` performs **no outbound request** (SSRF-deferred); `WebhookForm.clean_headers` rejects non-dict/non-string/CRLF headers.

## Seeder + sidebar (1.7–1.12)

`seed_crm` gained `_seed_extension(tenant)` (runs after base data; guarded by `Expense.exists()`): seeds
projects+milestones+timesheets, expenses, doc templates+contracts+signers, workflow rules+log+approvals,
onboarding plan+steps, surveys + `compute_health_score` per org party, product stock + a purchase order +
lines, and a PartnerPortalAccess (note: `portal_user=None` by default — assign a user to demo the portal).
`seed_crm` also gained **`_seed_finance17(tenant)`** (runs **after** `_seed_sfa` since it needs a quote;
guarded by `DealInvoice.exists()`): marks a seeded quote accepted, converts it to a draft
`accounting.Invoice` + `DealInvoice`, and records a partial Stripe `PaymentReceipt`; fresh seeds also flag
one expense `is_billable`. **`_seed_resource18(tenant)`** (after `_seed_extension`; guarded by
`ResourceAllocation.exists()`) books seeded users onto the project incl. one **overbooked** person so the
workload board has data. **`_seed_documents19(tenant)`** (after `_seed_extension`; guarded by
`DocumentVersion.exists()`) creates a draft contract rendered from a template + two captured versions so the
File Repository + version history have data.
`LIVE_LINKS` (`apps/core/navigation.py`) wires 1.7 (**Invoicing**→`dealinvoice_list`, **Payment
Tracking**→`paymentreceipt_list`, **Expense Tracking**→`expense_list`, + **Recurring Invoices**→
`accounting:recurringinvoice_list` extra), 1.8 (**Resource Allocation**→`resource_workload` (the real workload board, was a stub) + **Project Board**(Kanban)/Milestones/Allocations extras), 1.9 (**File Repository**→`document_repository` (real versioned repo by account, was a stub) + E-Signatures/Document Generation), 1.10 (Trigger-Based Actions→`workflowrule_list` (real Run engine)/Approval Processes/**Webhooks**→`webhook_list` (real endpoint registry, was a stub→workflowrule_list) + Workflow Logs & Webhook Deliveries extras),
1.11 (Onboarding Pipelines/Health Scoring/Surveys & Feedback (NPS)), 1.12 (Purchase Orders/Stock Tracking/
Vendor-Partner Portal + Partner Portal extra).

## Performance notes (1.7–1.12)

List views `select_related` the FKs their templates render and **defer large TextFields** not shown on lists
(`DocTemplate.body`, `ContractDocument.body_snapshot`, `WorkflowLog.error_msg`); `onboardingplan_list`
`prefetch_related("steps")` so `progress_pct` doesn't N+1; filter dropdowns use `.only(...)`; portal
list views are paginated. `PurchaseOrder.recalc_total()` / `compute_health_score` aggregate DB-side.
**1.7:** `dealinvoice_list` annotates confirmed `amt_paid`/`bal_due` via a correlated `Subquery` (instead of
the per-row `balance_due` property) so the list is a **constant** query count regardless of rows;
`dealinvoice_detail` precomputes paid/balance once (no double aggregate). Both deal-invoice/receipt lists
`select_related` the FKs their rows render.
**1.8:** `resource_workload` is 2–3 aggregate queries (allocations + grouped timesheet hours + a name lookup
for timesheet-only users) — proration is in Python (date-overlap math), no per-person N+1; `crmproject_board`
evaluates the milestone qs once and buckets by status in Python (no per-column re-query) and scans the
projects list in Python for `selected_project`; `crmproject_list` annotates `ms_total`/`ms_done` (so
`progress_pct` doesn't query per row) with an explicit `order_by`; `ResourceAllocation` has
`(tenant,status)`/`(tenant,start_date)`/`(tenant,end_date)` indexes for the workload window filter.
**1.9:** `document_repository` annotates `version_count` (Count) with an explicit `order_by` + defers
`body_snapshot`; `contractdocument_generate` `select_related`s template/account/opportunity/owner (no lazy
FK queries on render); `ContractDocument` gained a `(tenant,account)` index for the repository account filter.
**1.10:** `_run_rule` reads only concrete columns (allowlist) so iterating ≤50 records triggers no per-record FK
lazy-load, and hoists the active-webhook query out of the record loop; `webhook_list` annotates `delivery_count`
(Count) with an explicit `order_by`; `WorkflowLog` gained a `(tenant,rule,-fired_at)` index for the rule-detail
recent-logs query (and `workflowlog_list` no longer `defer()`s the `error_msg` it displays).
