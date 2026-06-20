---
name: crm
description: Work on the CRM module (Module 1 — leads, opportunities, campaigns, cases, knowledge base, tasks; accounts/contacts are core.Party + CRM AccountProfile/ContactProfile with full CRUD). Use when the user asks to add/change/debug anything under apps/crm or templates/crm, extend the CRM seeder, touch CRM sidebar wiring (LIVE_LINKS 1.1–1.6), or invokes /crm.
---

# CRM Module (Module 1, sub-modules 1.1–1.6)

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
| `Campaign` | `CAM-` | name, type, status(planned/active/paused/completed/cancelled), start/end_date, budget_planned/actual, expected/actual_revenue, target_size, description; prop `roi` | `owner`→User |
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

## Templates (`templates/crm/`)

Extend `base.html`; use the `theme.css` design system. Per CRUD model: `<entity>_list.html`
(filter-bar with `q` + status/FK selects reflecting `request.GET`, Actions column view/edit/delete-
POST+confirm+csrf, pagination via `partials/pagination.html`, empty-state), `<entity>_detail.html`
(`detail-grid` + actions + back link), `<entity>_form.html` (shared create/edit, generic
`{% for field in form %}` in `.form-grid`). Plus `account_list/detail/form`,
`contact_list/detail/form` (Party + profile; CRM-native New/Edit/Delete; delete buttons wrapped in
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
gains firmographics/contact details without `--flush`). Prints the demo-login reminder and the
`admin`-has-no-tenant warning. Run after `seed_core`/`seed_accounts`/`seed_tenants`.

## Sidebar wiring (`apps/core/navigation.py` → `LIVE_LINKS`)

Keys must match the `NavERP.md` §1 feature bullets verbatim to light up:
- `1.1`: Contacts → `crm:contact_list`; Accounts (Companies) → `crm:account_list`; Leads (Potential
  Customers) → `crm:lead_list`
- `1.2`: Opportunity Management (Deals) → `crm:opportunity_list`; Forecasting → `crm:overview`
- `1.3`: Campaign Management → `crm:campaign_list`
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
  `forms.py` (unless system-set); surface in the `*_detail.html`/`*_form.html`/`*_list.html`;
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
