# Contract — NavERP 8.1 Lead Management

- App: `sales` (new app, first sub-module)
- Sub-module: `8.1 Lead Management`
- Base SHA: `b18d08fbca4a38eabf9e444b025fb9c4eba4bd34`
- Research: `.claude/tasks/research-sales-8.1.md`
- Plan: `.claude/tasks/todo.md` (8.1 block)
- Scope: exactly four Sales-owned models; no duplicate lead, opportunity, campaign, territory, task, or conversion writer.

## Ownership and integration rules

1. `crm.Lead` is the canonical lead. `crm.Opportunity` is the canonical opportunity. CRM's existing conversion remains the only writer of Party, ContactMethod, PartyRole, and Opportunity rows.
2. `crm.LandingPage`, `crm.FormSubmission`, `crm.Campaign`, `crm.CampaignMember`, and `crm.EmailCampaign` remain CRM-owned. `crm.Territory` remains the territory master. `crm.CrmTask` is the follow-up task store.
3. `accounts.User` is the owner pool. `core.ConsentPurpose` is a tenant-scoped purpose reference. `accounting.Currency` is global and is never tenant-filtered.
4. Every Sales model has `tenant`; every view and related read uses `tenant=request.tenant`. Cross-tenant FK/M2M values fail as form errors or 404s.
5. Score events are append-only. CRM `Lead.score` and `Lead.rating` are cached projections changed by the Sales scoring service, not by the ordinary CRM lead form.
6. Nurture enrollment records state and a consent-purpose/evidence reference only. It does not send email, create a ConsentRecord, or create a campaign.
7. Routing is a deterministic domain service. It does not use `eval`, dynamic imports, relation traversal, arbitrary model lookup, or network calls while locks are held.
8. `LeadQualification` is a OneToOne current assessment. Archiving reuses the row; it is not replaced with a second row for the same lead.

## Local bases

`apps/sales/models/_base.py` exports:

- `TenantEventOwned`: `tenant` FK `core.Tenant`, `CASCADE`, `related_name="+"`, `db_index=True`; immutable `created_at`; no `updated_at`.
- `TenantOwned`: tenant FK plus `created_at` and `updated_at`.
- `TenantNumbered`: `number` max 20, editable false, per-tenant retrying `next_number` allocation.

## Model contract

### `LeadScoreEvent`

File: `apps/sales/models/LeadManagement/LeadScoreEvents.py`.

Fields: `tenant`; `lead` (`crm.Lead`, `PROTECT`); `signal_category`; `event_type`; `score_delta` signed -100..100; `source_kind`; `source_ref` blank opaque text; `reason` blank text; nullable `effective_until`; nullable/blank `idempotency_key`; nullable self-FK `corrects_event`; `occurred_at` system default now; nullable `recorded_by`; immutable `created_at`.

Choices:

- `SIGNAL_CATEGORY_CHOICES = behavioral, demographic, qualification, manual, decay, correction`.
- `EVENT_TYPE_CHOICES = form_submitted, email_open, email_click, web_visit, content_download, event_attendance, meeting_booked, demo_request, call_connected, reply_received, fit_match, fit_mismatch, unsubscribe, manual_adjustment, decay, correction`.
- `SOURCE_KIND_CHOICES = form_submission, campaign_member, communication_log, qualification, web_tracking, api, manual`.

Constraints: unique `(tenant, idempotency_key)`; indexes `(tenant, lead, -occurred_at)`, `(tenant, event_type, -occurred_at)`, `(tenant, source_kind, source_ref)`. Manual and correction events require a nonblank reason. A correction must reference an event for the same tenant and lead, never itself.

Scoring service: default event deltas are `form_submitted=5`, `email_open=2`, `email_click=8`, `web_visit=1`, `content_download=6`, `event_attendance=4`, `meeting_booked=10`, `demo_request=15`, `call_connected=8`, `reply_received=12`, `fit_match=20`, `fit_mismatch=-15`, `unsubscribe=-25`, `decay=-5`; manual and correction require a caller delta. Sum only events whose `occurred_at` is not future and whose `effective_until` is null or future. Clamp the projection to 0..100; bands are cold 0..39, warm 40..69, hot 70..100. Update the CRM projection in the same transaction and audit the append/projection.

### `LeadQualification`

File: `apps/sales/models/LeadManagement/LeadQualifications.py`.

Fields: `tenant`; OneToOne `lead` (`crm.Lead`, `PROTECT`); `framework`; `status`; blank `country_code`, `region`, `city`, `industry`; nullable positive `employee_count`; `seniority`; `budget_status`; nullable `budget_amount`; nullable global `budget_currency`; `authority_level`; `need_summary`; nullable `expected_purchase_on`; `economic_buyer`; `decision_criteria`; `decision_process`; `technical_requirements`; `pain_points`; `success_metrics`; `disqualification_reason`; nullable `assessed_by`; system `assessed_at`; nullable `next_review_on`; `notes`; timestamps.

Choices:

- `FRAMEWORK_CHOICES = bant, meddic, both`.
- `STATUS_CHOICES = unassessed, partially_qualified, qualified, disqualified, archived`.
- `SENIORITY_CHOICES = unknown, individual_contributor, manager, director, executive, owner`.
- `BUDGET_STATUS_CHOICES = unknown, not_confirmed, confirmed, adequate, insufficient`.
- `AUTHORITY_LEVEL_CHOICES = unknown, influencer, user, manager, director, executive, owner`.

Validation: selected framework must have `need_summary` and `expected_purchase_on` before qualified; MEDDIC/both additionally need economic buyer, decision criteria, and decision process; BANT/both need known budget and authority. Disqualified needs a reason. Terminal decisions need an assessor. A budget amount needs a currency; country codes normalize to two uppercase letters. The same tenant is required for the lead and assessor. Status changes append compensating score events and project qualified/unqualified to the CRM lead.

### `LeadRoutingRule`

File: `apps/sales/models/LeadManagement/LeadRoutingRules.py`.

Fields: `tenant`; unique-per-tenant `name`; `description`; `is_active`; positive `priority`; `match_mode`; JSON `conditions`; `is_catch_all`; `assignment_mode`; nullable `default_owner`; nullable `territory`; `eligible_owners` M2M; nullable `fallback_owner`; nullable positive `max_open_leads`; system `cursor`; system `last_assigned_owner`; system `last_assigned_at`; timestamps.

Choices: `MATCH_MODE_CHOICES = all, any`; `ASSIGNMENT_MODE_CHOICES = fixed_owner, territory_manager, round_robin`.

Conditions: at most 20 objects, raw JSON at most 16 KiB. Each object has only `field`, `operator`, and scalar `value`; no nested values, extra keys, or strings over 255. Allowed fields: `source`, `status`, `rating`, `score`, `est_value`, `owner_id`, `company`, `title`, `email_present`, `phone_present`, `qualification_status`, `framework`, `country_code`, `region`, `city`, `industry`, `employee_count`, `seniority`, `budget_status`, `authority_level`, `expected_purchase_on`. Allowed operators: `eq`, `ne`, `in`, `not_in`, `contains`, `icontains`, `gt`, `gte`, `lt`, `lte`, `is_set`, `is_empty`. Empty conditions require `is_catch_all=True`.

Mode validation: fixed requires `default_owner`; territory_manager requires `territory` with a manager; round_robin requires at least one same-tenant eligible owner. Optional fallback must be same tenant. Resolution order is active `(priority, id)`, first match wins. Fixed uses the default, territory uses the configured territory manager, and round robin locks the rule and lead, uses stable owner PK order and cursor, skips owners over `max_open_leads`, and advances state only when the lead owner changes. No match or no eligible owner is reported as unrouted. A persisted run updates only the CRM lead owner, creates one bounded `crm.CrmTask`, and writes audit evidence in one transaction.

### `LeadNurtureEnrollment`

File: `apps/sales/models/LeadManagement/LeadNurtureEnrollments.py`.

Fields: `tenant`; `lead` (`crm.Lead`, `PROTECT`); `email_campaign` (`crm.EmailCampaign`, `PROTECT`); auto `number` prefix `LNE`; `status`; `trigger_kind`; nullable `score_at_enrollment`; nullable `consent_purpose`; `consent_evidence`; nullable `owner`; system `started_at`, `last_touch_at`, `touch_count`, `completed_at`; `next_touch_at`; `exit_reason`; `notes`; timestamps.

Choices:

- `STATUS_CHOICES = pending, active, paused, completed, cancelled, replied, converted`.
- `TRIGGER_KIND_CHOICES = manual, score_threshold, form_source, qualification, recycled`.
- `EXIT_REASON_CHOICES = qualified, disqualified, replied, converted, unsubscribed, bounced, cancelled, completed, manual`.

Unique `(tenant, lead, email_campaign)`; indexes `(tenant, status, next_touch_at)` and `(tenant, email_campaign, status)`. Same-tenant lead/campaign/purpose/owner is mandatory. Activation requires a non-converted lead, a same-tenant CRM campaign with `send_type='drip'`, an active purpose, evidence when that purpose is optional, and a score snapshot. The row is the enrollment state only; no worker or ESP is implied. Lifecycle transitions are explicit POST verbs and terminal exits require a reason.

## Forms

All tenant-owned ModelForms inherit `TenantModelForm` and use same-tenant validation. `accounting.Currency` is treated as global.

- `LeadScoreAdjustmentForm(forms.Form)`: `lead`, `score_delta` -100..100, required `reason`.
- `LeadScoreCorrectionForm(forms.Form)`: `lead`, tenant/lead-scoped `corrects_event`, `score_delta` -100..100, required `reason`.
- `LeadQualificationForm`: `lead`, `framework`, geography/firmographics, budget fields, authority, MEDDIC/need fields, `next_review_on`, `notes`; lead disabled on edit; excludes tenant, status, disqualification reason, assessor, system stamps.
- `LeadQualificationDecisionForm`: `status` limited to `partially_qualified`, `qualified`, `disqualified`, `archived`; `disqualification_reason`; `notes`.
- `LeadRoutingRuleForm`: `name`, `description`, `is_active`, `priority`, `match_mode`, `conditions`, `is_catch_all`, `assignment_mode`, `default_owner`, `territory`, `eligible_owners`, `fallback_owner`, `max_open_leads`; excludes tenant, cursor, last assignment, stamps.
- `LeadRoutingPreviewForm` and `LeadRoutingRunForm`: tenant-scoped `lead`.
- `LeadNurtureEnrollmentForm`: tenant-scoped `lead`, drip `email_campaign`, `trigger_kind`, `consent_purpose`, `consent_evidence`, `owner`, `notes`; excludes tenant, number, status, score snapshot, system timestamps/counters, exit reason.
- `LeadNurtureActivationForm`: optional `next_touch_at`.
- `LeadNurtureExitForm`: transition-compatible `exit_reason` and optional `notes`.

## Views and exact context keys

- `lead_overview`: `stats`, `leads`, `qualifications`, `routing_rules`, `enrollments`, `latest_score_events`, `duplicate_warnings`, `recent_activity`.
- `lead_score_event_list`: `object_list`, `page_obj`, `q`, `date_from`, `date_to`, `signal_category_choices`, `event_type_choices`, `source_kind_choices`, `leads`.
- `lead_score_event_detail`: `obj`, `lead`, `projection_score`, `projection_rating`.
- `lead_score_event_adjust` and `lead_score_event_correct`: POST-only; no GET context; redirect on success or validation failure.
- `lead_score_event_recompute`: POST-only; `lead_id`; no GET context.
- `lead_qualification_list`: `object_list`, `page_obj`, `q`, `status_choices`, `framework_choices`, `seniority_choices`, `budget_status_choices`, `authority_level_choices`, `assessors`, `review_due`, `leads`.
- qualification create/edit: `form`, `is_edit`, `leads`, and `obj` on edit.
- qualification detail: `obj`, `lead`, `score_events`, `enrollments`, `routing_preview`, `decision_form`.
- qualification action views: `obj`, `form`, `leads`; POST-only except route preview.
- `lead_routing_rule_list`: `object_list`, `page_obj`, `q`, `assignment_mode_choices`, `match_mode_choices`, `active_choices`, `territories`, `users`.
- routing create/edit: `form`, `obj` on edit, `is_edit`, `territories`, `users`.
- routing detail: `obj`, `eligible_owners`, `leads`, `preview_form`, `preview_result`.
- routing toggle/run are POST-only; no GET context.
- `lead_nurture_enrollment_list`: `object_list`, `page_obj`, `q`, `status_choices`, `trigger_kind_choices`, `drip_campaigns`, `owners`, `next_touch`, `leads`.
- nurture create/edit: `form`, `obj` on edit, `is_edit`, `leads`, `drip_campaigns`, `consent_purposes`, `owners`.
- nurture detail: `obj`, `lead`, `email_campaign`, `consent_purpose`, `activation_form`, `exit_form`.
- nurture lifecycle views: `obj` and `exit_form` where an invalid transition is rendered; successful transitions redirect.

List filters are applied before pagination: score `signal_category`, `event_type`, `source_kind`, `lead`, `date_from`, `date_to`; qualification `status`, `framework`, `country`, `region`, `seniority`, `budget_status`, `authority_level`, `assessor`, `review_due`; routing `active`, `assignment_mode`, `match_mode`, `territory`, `priority`; nurture `status`, `trigger_kind`, `email_campaign`, `owner`, `next_touch`. All FK controls receive tenant-scoped querysets and use `|stringformat:"d"` in templates.

## URL names and order

`apps/sales/urls/__init__.py` sets `app_name='sales'` and concatenates literal-first routes from Overview, LeadScoreEvents, LeadQualifications, LeadRoutingRules, LeadNurtureEnrollments.

- `lead_overview`: `overview/`; `lead_handoff`: `leads/<int:pk>/handoff/`.
- `lead_score_event_list`, `_detail`, `_adjust`, `_correct`, `_recompute`.
- `lead_qualification_list`, `_create`, `_detail`, `_edit`, `_delete`, `_partial`, `_qualify`, `_disqualify`, `_recalculate`, `_route_preview`.
- `lead_routing_rule_list`, `_create`, `_detail`, `_edit`, `_delete`, `_toggle`, `_preview`, `_run`.
- `lead_nurture_enrollment_list`, `_create`, `_detail`, `_edit`, `_delete`, `_activate`, `_pause`, `_resume`, `_complete`, `_cancel`, `_reply`, `_convert_exit`.

## Templates

- `templates/sales/leadmanagement/leadscoreevent/list.html`, `detail.html`.
- `templates/sales/leadmanagement/leadqualification/{list,detail,form}.html`.
- `templates/sales/leadmanagement/leadroutingrule/{list,detail,form}.html`.
- `templates/sales/leadmanagement/leadnurtureenrollment/{list,detail,form}.html`.
- `templates/sales/overview.html` with `id="handoff"`.

Use only `badge-green`, `badge-red`, `badge-amber`, `badge-info`, `badge-muted`, and `badge-slate`; use `detail-grid`/`detail-item`; guard nullable values; include search, filters, pagination, actions, CSRF, and confirmation. No score-event create/edit/delete affordance exists.

## Integration and verification

- New app files are written before settings/URL wiring.
- Re-export every model/form/view; register admin; extend CRM lead form/admin/conversion service only with surgical edits.
- `seed_sales` creates/reuses a drip EmailCampaign and the four records per tenant, is no-op on second run, and states that no ESP/worker is present.
- `LIVE_LINKS['8.1']` maps the five exact NavERP labels to staff-reachable routes and adds Sales extras.
- Run `makemigrations sales`, `migrate`, `seed_sales` twice, `manage.py check`, reverse every route, smoke content/filter/pagination/IDOR/action-method checks, then the full unfiltered `apps/sales/tests` suite.
