---
name: procurement
description: Work on the Procurement module (Module 6 — Procurement Management System). As-built = 6.1 User Dashboard & Portal (personalized overview with per-user widget preferences, Task & Alert Center with acknowledge/resolve lifecycle, quick requisition entry drafting into scm.PurchaseRequisition, audit-log-derived activity feed, self-service reports + own-requisitions CSV export). Use when the user asks to add/change/debug anything under apps/procurement or templates/procurement, extend the seed_procurement seeder, touch procurement sidebar wiring (LIVE_LINKS 6.1), or invokes /procurement.
---

# Procurement — Procurement Management System (Module 6)

App path: `apps/procurement`. Templates: `templates/procurement/`. URL prefix: `/procurement/`,
`app_name = "procurement"`. Mirrors `NavERP.md` "## 6. Procurement Management System" (19
sub-modules, 6.1–6.19).

**As-built: 6.1 only (1 of 19).** Build the next one with `/next-module` (it takes the lowest
`6.M` without a `LIVE_LINKS["6.M"]` entry) — see the reference apps `apps/crm`/`apps/accounting`
for the package layout and the mandatory Module Creation Sequence.

## Overview

6.1 is the people/workflow layer AROUND the procurement document spine. **The spine is SCM 4.1's**
(L29/L36): `scm.PurchaseRequisition`, `scm.PurchaseOrder`, `scm.GoodsReceiptNote`, `scm.RFQ` are
OWNED by `apps/scm` and this module EXTENDS them by FK/string reference — it declares no
requisition, PO or receipt table of its own, and its Quick Requisition Entry WRITES INTO
`scm.PurchaseRequisition` (header + one line in one transaction) before handing off to scm's
submit/approve views. The activity feed is `core.AuditLog` filtered to procurement content types;
there is no second feed table.

## Models (`apps/procurement/models/DashboardPortal/<Entity>.py`)

Shared base in `models/_base.py`: `TenantOwned` (tenant FK + timestamps, `related_name="+"`),
plus the usual toolkit imports and `ZERO`.

- **`ProcurementAlerts.py`** — `ProcurementAlert`. The Task & Alert Center inbox.
  - `kind`: deadline/approval/delivery/task; `severity`: info/warning/critical;
    `status`: open/acknowledged/resolved (`OPEN_STATUSES = ("open", "acknowledged")`).
  - Lifecycle verbs ONLY: `acknowledge(user)` (no-op off `open`, returns bool) and
    `resolve(user, note="")` (early-returns False when already resolved so who/when/note can
    never be restated). `status` is OFF the form.
  - `link_url` must be an internal path: `clean()` rejects anything not starting with a single
    `/`, any backslash (browsers canonicalize `\` → `/`, so `/\evil.com` IS protocol-relative),
    and scheme-relative forms. Rendered as href verbatim — keep that guard intact.
  - `is_overdue` = due_at past AND status still live. Badge css properties
    (`severity_css`/`status_css`/`kind_css`) return colour-named classes ONLY
    (badge-green/red/amber/info/muted/slate; L33).
  - No auto-number (not a document). Indexes: (tenant,status)/(tenant,kind)/(tenant,assigned_to)/
    (tenant,severity).
- **`WidgetPreferences.py`** — `WidgetPreference`. One row per (tenant, user, widget_key) with
  `is_visible`; **absence of a row MEANS visible** (the seeder seeds none). The widget registry
  lives on the model as `WIDGETS` (ordered dict key→label; keys: approvals/alerts/spend/deadlines/
  activity). Helpers: `hidden_keys(tenant,user)` and `save_choices(tenant,user,visible_keys)`
  (atomic upsert loop; deliberately NOT audited — personal layout pref, not business data).

## Views / URLs

`app_name = "procurement"`. Package layout one-to-one across models/forms/views/urls under
`DashboardPortal/`. Shared feed queryset builder in `views/_helpers.py`
(`procurement_activity_qs(tenant)` — AuditLog where content_type is app_label="procurement" OR
app_label="scm" AND model in `PROCUREMENT_CONTENT_MODELS`; append new sub-modules' model names
THERE as they land).

| Route | Name | Notes |
|---|---|---|
| `/procurement/` | `dashboard` | Landing = personalized overview; POSTs widget toggle back to itself |
| `/procurement/alerts/` (+ add/detail/edit/delete) | `alert_*` | Full CRUD; list floats open rows first via a Case annotation |
| `/procurement/alerts/<pk>/acknowledge/` `…/resolve/` | `alert_acknowledge`/`alert_resolve` | POST-only lifecycle verbs |
| `/procurement/quick-requisition/` | `quickreq_create` | One-screen fast track → drafts scm.PurchaseRequisition |
| `/procurement/activity/` (+ `<pk>/`) | `activity_list`/`activity_detail` | Feed over core.AuditLog; always windowed (30d default); scope=mine default; detail restricted to the SAME domain filter |
| `/procurement/reports/` (+ `export/`) | `report_index`/`report_export` | Computed personal usage/spend + 6-month TruncMonth trend; CSV of MY requisitions only |

Context-var contract: lists use `crud_list` (`object_list`/`page_obj`/`q` + each page's
`*_choices`); overview passes `stats` dict, `widgets` (list of {key,label,visible}),
`widget_form`, `pending_requisitions`, `my_open_alerts_list`, `upcoming_alerts`,
`due_requisitions`, `recent_activity`; quickreq passes `form`+`recent`; reports passes
`stats`/`by_status` (value,label,count triples)/`trend`/`recent_of_mine`.

## Templates

`templates/procurement/overview.html` (landing) +
`templates/procurement/dashboardportal/{alerts/{list,detail,form}.html, quickrequisition.html,
activity.html, activity_detail.html, reports.html}`. Standalone pages sit at sub-module level;
only alerts (a real entity) gets the entity folder. All extend `base.html`, use theme.css classes,
colour-named badges only, `{% include "partials/pagination.html" %}` on paginated lists.

## Seeder

`python manage.py seed_procurement` — idempotent per tenant (skips when alerts exist; `--flush`
deletes all). Seeds 6 alerts covering every kind/severity and walks two through the lifecycle so
every badge colour exists, assigned to the tenant's members; writes one `core.AuditLog` row per
alert (user=None → renders as "System") so the activity feed has a baseline. Creates NO
requisitions — run `seed_scm` first for populated approval/spend widgets.

## Conventions & gotchas

- Tenant scoping everywhere; superuser (`tenant=None`) sees empty data by design.
- Quick requisition: requester hardwired to `request.user`, status starts `draft`,
  `estimated_total` via `recalc_totals()` — never trust client totals. Quantity/price ceilings
  match the scm columns' Decimal(14,4)/(14,2) widths (MaxValueValidator) to avoid driver 500s.
- CSV export neutralizes formula injection (`_csv_safe` prefixes `'` on leading `=`/`+`/`-`/`@`);
  exports only `requester=request.user` rows (tenant-wide spend is 6.14's job).
- Widget saves are deliberately not audited (documented on `save_choices`).
- Tests: `apps/procurement/tests/` (`test_portal_{models,forms,views,security}.py` + conftest);
  run with `--no-migrations` for speed, e.g.
  `venv\Scripts\python.exe -m pytest apps\procurement\tests -q --no-migrations`.

## Sidebar wiring

`LIVE_LINKS["6.1"]` in `apps/core/navigation.py`: Personalized Overview → `procurement:dashboard`;
Task & Alert Center → `procurement:alert_list`; Quick Requisition Entry →
`procurement:quickreq_create`; Recent Activity Feed → `procurement:activity_list`;
Self-Service Reporting → `procurement:report_index`.

## Common tasks

- **Add a widget**: add the key to `WidgetPreference.WIDGETS` (order = render order), add the
  section to `templates/procurement/overview.html` behind `{% if w.visible and w.key == "…" %}`,
  compute its context in `Overview.dashboard`.
- **Raise alerts from a later sub-module**: import `ProcurementAlert` and create rows (optionally
  `write_audit_log`); do not fork the inbox.
- **New procurement sub-module**: new `DashboardPortal`-style folder per layer, re-export blocks,
  one `LIVE_LINKS["6.M"]` entry, extend `seed_procurement` idempotently, extend
  `PROCUREMENT_CONTENT_MODELS` if its documents should appear in the feed.
