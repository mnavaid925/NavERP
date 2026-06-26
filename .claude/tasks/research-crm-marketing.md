# Research — Module 1.3: Marketing Automation (crm)

> Scope: CRM sub-module 1.3 only — Campaign Management, Email Marketing, Landing Pages & Forms.
> Extension context: `apps/crm` already exists. `Campaign` (CAM-) is already a thin model.
> Accounts/Contacts are `core.Party`. We extend, not rebuild.

---

## Leaders surveyed

1. **HubSpot Marketing Hub** — all-in-one CRM-native marketing platform, industry benchmark for mid-market — https://www.hubspot.com/products/marketing/campaigns
2. **Salesforce Account Engagement (Pardot)** — B2B-focused marketing automation, tightly coupled to Salesforce CRM — https://www.salesforce.com/marketing/b2b-automation/
3. **Adobe Marketo Engage** — enterprise-grade multi-stream nurture + smart-list segmentation — https://genesysgrowth.com/blog/marketo-engage-complete-guide
4. **ActiveCampaign** — SMB-to-mid-market visual automation builder with deep behavioral triggers — https://ventureharbour.com/activecampaign-review/
5. **Mailchimp** — ubiquitous email-first platform with drag-and-drop builder and multivariate testing — https://mailchimp.com/features/ab-testing/
6. **Klaviyo** — flow-based automation with rich segmentation and multi-type sign-up forms — https://www.klaviyo.com/features/flows
7. **Brevo (formerly Sendinblue)** — affordable full-stack: campaigns + automation + landing pages + forms — https://www.brevo.com/
8. **Zoho Campaigns / Zoho CRM web forms** — tightly integrated with Zoho CRM, round-robin lead routing, analytics — https://www.zoho.com/campaigns/features.html
9. **GetResponse** — autoresponder-first platform with landing page builder and A/B testing — https://www.getresponse.com/features
10. **Unbounce** — dedicated landing-page-and-form specialist with AI smart-traffic variant routing — https://unbounce.com/product/features/

---

## Feature catalog by sub-module

---

### 1.3.A Campaign Management

- **Multi-type campaigns** — campaign records carry a `type` field distinguishing Email, Webinar, Event, Digital Ad, Direct Mail, Social, and Other. Already in existing `Campaign.TYPE_CHOICES` — no new table needed, but the enhanced model must carry all downstream FKs.
  · seen in: HubSpot, Pardot, Marketo, ActiveCampaign, Zoho Campaigns
  · priority: **table-stakes**
  · spine: reuse `crm.Campaign` (enhance, do not duplicate)
  · buildable now

- **Budget planned vs. actual** — `budget_planned` and `budget_actual` decimal fields with derived variance. Already in existing `Campaign`; confirmed correct by all surveyed leaders.
  · seen in: HubSpot, Pardot, Marketo, Zoho Campaigns
  · priority: **table-stakes**
  · spine: reuse `crm.Campaign`
  · buildable now

- **Target list (audience) with per-member status** — a campaign has a related collection of recipients (Parties/Leads); each membership record tracks whether that recipient was sent to, opened, clicked, bounced, or unsubscribed. HubSpot calls this "Campaign Contacts"; Marketo calls it "Program Members"; Pardot calls it "List Members". This is the critical join table between a campaign and its audience.
  · seen in: HubSpot, Pardot, Marketo, ActiveCampaign, Zoho Campaigns, Klaviyo
  · priority: **table-stakes**
  · spine: new table `CampaignMember` — FK to `crm.Campaign` + FK to `core.Party` (contact) or nullable FK to `crm.Lead` (pre-converted prospect)
  · buildable now

- **Campaign goal / objective field** — textual or choice-based field on the campaign record stating the goal (brand awareness, lead generation, nurture, retention). HubSpot supports goal-interval tracking ("15 influenced contacts per week"); Marketo and Pardot use it for outcome reporting.
  · seen in: HubSpot, Pardot, Marketo
  · priority: **common**
  · spine: add `goal` choice field on `crm.Campaign`
  · buildable now

- **ROI analysis (actual_revenue vs budget_actual)** — computed property: `(actual_revenue - budget_actual) / budget_actual × 100`. Already modeled as a `@property` on existing `Campaign`. Enhancement: add `influenced_leads` count (derived from `CampaignMember`) and `converted_leads` count for a richer ROI panel.
  · seen in: HubSpot, Pardot, Marketo, Zoho
  · priority: **table-stakes**
  · spine: reuse `crm.Campaign.roi`; influenced/converted are aggregate queries over `CampaignMember`
  · buildable now

- **Campaign-to-opportunity attribution** — existing `Opportunity.campaign` FK already wires revenue attribution. Enhancement: `CampaignMember` records for contacts that convert to leads/opportunities should be marked `converted=True` to power multi-touch attribution reports.
  · seen in: HubSpot, Pardot, Marketo, Salesforce
  · priority: **common**
  · spine: reuse existing `Opportunity.campaign` FK; add `converted` bool on `CampaignMember`
  · buildable now

- **Campaign cloning / re-use** — ability to duplicate a past campaign (name, type, budget fields, target list) as a starting template for a new one. Pardot and HubSpot both support this. Implementation is a service function + view action, no new table.
  · seen in: HubSpot, Pardot, Marketo, ActiveCampaign
  · priority: **common**
  · spine: no new table; a service function copies Campaign + CampaignMembers
  · buildable now

- **Multi-channel campaign asset grouping** — HubSpot's Campaigns tool groups emails, landing pages, and forms under one campaign umbrella for attribution. Implementation: FK from `EmailCampaign` and `LandingPage` back to `Campaign`.
  · seen in: HubSpot, Marketo (Programs), Pardot
  · priority: **common**
  · spine: FK on `EmailCampaign.campaign` and `LandingPage.campaign` pointing to `crm.Campaign`
  · buildable now

---

### 1.3.B Email Marketing

- **HTML email template builder (drag-and-drop)** — a saved, reusable HTML template with merge-tag variables for personalization. All ten leaders offer this. In-browser visual editing is an **integration/later** item (requires a JS rich-editor like GrapeJS or Unlayer); what we model now is the template record with its HTML body and the merge-tag inventory.
  · seen in: HubSpot, Mailchimp, ActiveCampaign, Klaviyo, Brevo, Zoho, GetResponse, Constant Contact
  · priority: **table-stakes**
  · spine: new table `EmailTemplate` (TPL-EMAIL- prefix) — `name`, `subject_default`, `html_body` (TextField), `preview_text`, `from_name_default`, `from_email_default`, `template_type` (choice: general/welcome/drip/event/transactional), `is_active` bool, `owner` FK, `campaign` nullable FK
  · buildable now (raw HTML textarea); drag-and-drop builder = integration/later

- **Email blast / one-shot campaign send** — a scheduled or immediate single send to a target list, tracked by a dedicated send record (not a drip sequence). Each blast references a template, a campaign, a send datetime, and accumulates aggregate metrics. Mailchimp calls this a "Campaign"; HubSpot calls it a "Marketing Email"; Pardot calls it an "Email Send".
  · seen in: Mailchimp, HubSpot, Pardot, Brevo, Zoho, Constant Contact, GetResponse
  · priority: **table-stakes**
  · spine: new table `EmailCampaign` (ECAM- prefix) — `name`, `campaign` FK, `template` FK, `status` (draft/scheduled/sending/sent/cancelled), `scheduled_at`, `sent_at`, `from_name`, `from_email`, `reply_to_email`, `recipients_count`, `delivered_count`, `opens_count`, `unique_opens_count`, `clicks_count`, `unique_clicks_count`, `bounces_count`, `unsubscribes_count`, `spam_reports_count`
  · buildable now (metrics stored as counter fields, no live ESP)

- **Automated drip campaign (multi-step email sequence)** — a time-ordered sequence of email sends where each step fires after a delay or trigger. ActiveCampaign calls these "Automation Workflows"; Marketo calls them "Engagement Programs with Streams"; Klaviyo calls them "Flows". Modeled as a parent `EmailCampaign` with `drip_type=sequence` plus ordered `Drip Step` children.
  · seen in: ActiveCampaign, Marketo, Klaviyo, HubSpot, Pardot (Engagement Studio), Brevo, GetResponse (Autoresponder)
  · priority: **table-stakes**
  · spine: new table `DripStep` — FK to `EmailCampaign`, `order` int, `delay_days` int, `delay_hours` int, `template` FK, `status` (active/paused/skipped), `subject_override`, `sent_count`, `opens_count`, `clicks_count`; parent `EmailCampaign.campaign_type` = 'drip'
  · buildable now

- **A/B split testing on email sends** — a single campaign send is split into variant groups (A and B, sometimes C). What can be tested (per Mailchimp, HubSpot, Klaviyo, ActiveCampaign): subject line, from name, email content/template, send time. Winner is determined by: open rate, click rate, or manual selection after a holding period.
  · seen in: Mailchimp (up to 8 variants), HubSpot, Klaviyo, ActiveCampaign, Pardot, Brevo, GetResponse, Constant Contact
  · priority: **table-stakes**
  · spine: new table `ABVariant` — FK to `EmailCampaign`, `variant_label` (A/B/C), `test_variable` (choice: subject_line/from_name/content/send_time), `value_override` (CharField for subject/from_name override or JSON for send_time), `template` nullable FK (for content variant), `send_pct` decimal (percent of list receiving this variant), `is_winner` bool, `opens_count`, `clicks_count`, `open_rate` decimal, `click_rate` decimal, `winner_criteria` (choice: open_rate/click_rate/manual), `winner_selected_at` datetime
  · buildable now

- **Per-recipient email tracking (delivery event log)** — each `CampaignMember` tracks the per-send lifecycle: delivered, opened (with datetime + count), clicked (with datetime + count), bounced (hard/soft), unsubscribed, spam-flagged. This is the row-level equivalent of the aggregate counters on `EmailCampaign`. Marketo, HubSpot, Klaviyo all maintain this per-contact history.
  · seen in: Marketo, HubSpot, Klaviyo, ActiveCampaign, Pardot, Mailchimp
  · priority: **table-stakes**
  · spine: per-recipient status fields on `CampaignMember`: `email_status` (choice: pending/sent/delivered/opened/clicked/bounced_hard/bounced_soft/unsubscribed/spam), `opened_at` datetime, `clicked_at` datetime, `open_count` int, `click_count` int, `bounce_type` (choice: hard/soft/none), `unsubscribed_at` datetime
  · buildable now

- **Contact-level unsubscribe / suppression** — when a recipient unsubscribes (CampaignMember status → unsubscribed), that contact should be globally suppressed from future sends. Modeled as a boolean flag on `ContactProfile` or a separate `Unsubscribe` record with datetime and source campaign.
  · seen in: all ten leaders
  · priority: **table-stakes**
  · spine: add `is_email_opted_out` bool + `opted_out_at` datetime on `crm.ContactProfile`; filter future sends to exclude opted-out contacts
  · buildable now

- **Send-time optimization (best time to send)** — Mailchimp, ActiveCampaign, Brevo, Klaviyo, and GetResponse all offer predictive send-time: choosing the send time per contact based on past open history. In NavERP this is a future AI/integration feature; we model the field (`preferred_send_hour` int on `CampaignMember` or ContactProfile) but do not implement the algorithm now.
  · seen in: Mailchimp, ActiveCampaign, Brevo, Klaviyo
  · priority: **differentiator**
  · spine: no new table; field stub on CampaignMember
  · integration/later (algorithm requires historical data)

- **Engagement scoring / lead score bump** — email opens and clicks increment the `Lead.score` or a future contact-level score. ActiveCampaign assigns configurable point values per event (open +1 pt, key-page visit +3 pts). Wire-up to existing `Lead.score` is a service function, no new table.
  · seen in: ActiveCampaign, Marketo, Pardot, HubSpot
  · priority: **common**
  · spine: service function that bumps `crm.Lead.score` when CampaignMember event recorded; no new table
  · buildable now (service layer)

---

### 1.3.C Landing Pages & Forms

- **Landing page record** — a named, tenant-scoped page associated with a campaign, carrying an offer description, a public slug/URL token, status (draft/published/archived), and conversion metrics (views, submissions). HubSpot, Unbounce, Brevo, GetResponse, and ActiveCampaign all model this as a first-class entity.
  · seen in: HubSpot, Unbounce, ActiveCampaign, Brevo, GetResponse, Pardot, Marketo, Zoho
  · priority: **table-stakes**
  · spine: new table `LandingPage` (LP- prefix) — `name`, `campaign` nullable FK, `slug` (unique per tenant, URL-safe), `status` (draft/published/archived), `headline`, `body_html` (page content, raw HTML for now), `cta_label`, `page_views` int, `form_submissions` int (denormalized counter), `owner` FK, `published_at` datetime
  · buildable now

- **Web form builder attached to landing page** — every landing page has an associated web-to-lead form. The form defines which fields to collect (name, company, email, phone, message, custom fields). Zoho CRM web forms, HubSpot forms, and Unbounce all model forms as configurable field sets. For NavERP: a `WebForm` entity owns ordered `FormField` definitions; `FormSubmission` stores captured values.
  · seen in: HubSpot, Zoho CRM, Pardot, ActiveCampaign, Unbounce, Brevo, Klaviyo, GetResponse
  · priority: **table-stakes**
  · spine: `LandingPage` carries an implicit form (one-to-one); alternatively a `WebForm` FK on `LandingPage` for reuse. Fields defined as JSON or ordered child records. For NavERP single-pass: store `form_fields` as JSONField on `LandingPage` (ordered list of {name, field_type, required, placeholder}) — avoids a separate `FormField` model until needed.
  · buildable now (JSONField approach); separate FormField model = next-pass refinement

- **Standard form field types** — across all leaders, form field types include: text (single-line), textarea (multi-line), email, phone, number, select (dropdown), checkbox, date, hidden field. Klaviyo supports pop-up, flyout, embedded, and multi-step forms. Unbounce supports two-step forms and content-gating. For NavERP: `form_fields` JSONField entries carry `field_type` choices.
  · seen in: HubSpot, ActiveCampaign, Zoho, Unbounce, Klaviyo, Brevo, GetResponse
  · priority: **table-stakes**
  · spine: `form_fields` JSONField on `LandingPage`; no separate table in this pass
  · buildable now

- **Form submission capture (web-to-lead)** — when a visitor submits the form, a `FormSubmission` record is created with: captured field values (as JSON), source IP, UTM parameters (source/medium/campaign), referrer URL, and submitted_at datetime. All leaders record this. The submission then triggers lead creation or updates an existing `Lead`.
  · seen in: HubSpot, Pardot, Zoho CRM, Marketo, ActiveCampaign, Unbounce, Brevo
  · priority: **table-stakes**
  · spine: new table `FormSubmission` (FS- prefix) — FK to `LandingPage`, `data` JSONField (captured values), `ip_address`, `referrer_url`, `utm_source`, `utm_medium`, `utm_campaign`, `utm_term`, `utm_content`, `submitted_at`, `created_lead` nullable FK to `crm.Lead` (set after lead-creation service runs), `status` (choice: new/processed/duplicate/spam)
  · buildable now

- **Auto lead creation from form submission** — when a FormSubmission arrives, a service creates or updates a `Lead` record (name/email/company from captured data, source=web, campaign FK). HubSpot, Pardot, and Zoho all do this automatically. Implementation: a `process_submission(submission)` service function that calls `Lead.objects.get_or_create(tenant, email=…)` and fills fields.
  · seen in: HubSpot, Pardot, Zoho CRM, Marketo, ActiveCampaign, Brevo
  · priority: **table-stakes**
  · spine: service function; sets `FormSubmission.created_lead`; reuses existing `crm.Lead`
  · buildable now

- **Lead routing by owner / geography** — after a form submission creates a lead, routing rules determine which sales rep (User) is assigned as owner. Zoho uses round-robin; Pardot uses territory rules (geography/industry); HubSpot uses assignment rules (round-robin, property matching). For NavERP: `LandingPage.default_owner` FK to User (simplest); optionally a `routing_rule` choice field (choices: manual/round_robin/owner_match) with `routing_filter` JSONField for criteria (country/state/company_size).
  · seen in: HubSpot, Pardot, Marketo, Zoho CRM, Unbounce (Smart Traffic = page variant routing)
  · priority: **common**
  · spine: `default_owner` FK + `routing_rule` choice + `routing_filter` JSONField on `LandingPage`; lead assignment service reads these
  · buildable now (manual + round_robin); geography matching = later

- **Form A/B testing (page variant testing)** — Unbounce's core feature: two page variants (A/B) with configurable traffic splits; winner determined by conversion rate. Zoho web forms also support A/B on fields/CTAs. For NavERP: a minimal `page_variant` choice on `LandingPage` (control / variant_a / variant_b) with a `parent_page` self-FK; conversion rate is derived from `form_submissions / page_views`. Full traffic-split routing is a later-pass feature.
  · seen in: Unbounce, Zoho CRM, GetResponse
  · priority: **differentiator**
  · spine: `page_variant` choice + `parent_page` self-FK + `traffic_pct` decimal on `LandingPage`
  · buildable now (data model only); smart traffic routing = integration/later

- **UTM / source attribution on submissions** — all leaders capture UTM parameters (source, medium, campaign, term, content) from the landing page URL at the time of submission, enabling campaign attribution. These are simple CharField/URLField columns on `FormSubmission`.
  · seen in: HubSpot, Pardot, Marketo, ActiveCampaign, Unbounce, Brevo, Mailchimp
  · priority: **table-stakes**
  · spine: utm_* fields on `FormSubmission`
  · buildable now

- **Thank-you / redirect URL after submission** — HubSpot, Unbounce, and ActiveCampaign all configure a post-submission redirect or thank-you message. For NavERP: `success_redirect_url` URLField + `success_message` TextField on `LandingPage`.
  · seen in: HubSpot, Unbounce, ActiveCampaign, Brevo
  · priority: **common**
  · spine: two fields on `LandingPage`
  · buildable now

- **Spam/bot prevention on forms** — Zoho, HubSpot, and most others use honeypot fields or CAPTCHA. For NavERP: `captcha_enabled` bool on `LandingPage` (surfaced as a render hint for the template).
  · seen in: HubSpot, Zoho, Pardot, Unbounce
  · priority: **common**
  · spine: `captcha_enabled` bool on `LandingPage`
  · buildable now (field stub; real CAPTCHA = integration/later)

---

## Recommended build scope (this pass — 6 models)

All six are tenant-scoped. Prefixes follow NavERP convention.

### 1. Enhance `crm.Campaign` (existing CAM- model — no new table)

Fields to ADD:
- `goal` — CharField, choices: `lead_gen`, `brand_awareness`, `nurture`, `retention`, `event_promo`, `other`; maps to 1.3.A goal/objective feature
- `members_count` — PositiveIntegerField (denormalized, updated via signal or service when CampaignMembers added)

Rationale: Campaign cloning, ROI analytics, and multi-asset grouping all hang off the existing record. New downstream entities (`EmailCampaign`, `LandingPage`) FK into it.

---

### 2. `CampaignMember` (CMEM-) — target-list segmentation + per-recipient tracking

Maps to: 1.3.A target list segmentation, 1.3.B per-recipient tracking, unsubscribe suppression

Fields:
- `tenant` FK
- `campaign` FK → `crm.Campaign`
- `party` nullable FK → `core.Party` (converted contact)
- `lead` nullable FK → `crm.Lead` (pre-conversion prospect)
- `email_address` — EmailField (denormalized from party/lead at add-time so tracking survives later edits)
- `status` — choices: `pending`, `sent`, `delivered`, `opened`, `clicked`, `bounced_hard`, `bounced_soft`, `unsubscribed`, `spam`
- `added_at` — DateTimeField (auto)
- `opened_at` — DateTimeField (null)
- `clicked_at` — DateTimeField (null)
- `open_count` — PositiveIntegerField default 0
- `click_count` — PositiveIntegerField default 0
- `bounce_type` — choices: `none`, `hard`, `soft`
- `unsubscribed_at` — DateTimeField (null)
- `converted` — BooleanField default False (set when member becomes Opportunity)

Constraint: `unique_together(tenant, campaign, party)` and `unique_together(tenant, campaign, lead)` — one membership per person per campaign.

---

### 3. `EmailTemplate` (ETPL-) — reusable HTML template

Maps to: 1.3.B drag-and-drop template builder (raw HTML now; visual editor = later)

Fields:
- `tenant` FK
- `name` — CharField
- `template_type` — choices: `general`, `welcome`, `drip`, `event`, `transactional`, `newsletter`
- `subject_default` — CharField (default subject line for campaigns using this template)
- `preview_text` — CharField (email preview snippet shown in inbox)
- `from_name_default` — CharField
- `from_email_default` — EmailField
- `html_body` — TextField (raw HTML with `{{ contact.first_name }}` merge tags)
- `is_active` — BooleanField default True
- `owner` FK → User
- `campaign` nullable FK → `crm.Campaign`
- `times_used` — PositiveIntegerField default 0 (bumped when EmailCampaign references this template)

---

### 4. `EmailCampaign` (ECAM-) — email blast or drip-series parent + aggregate metrics

Maps to: 1.3.B blast send, drip campaigns, A/B testing (through ABVariant children), open/click/bounce/unsubscribe tracking

Fields:
- `tenant` FK
- `campaign` FK → `crm.Campaign`
- `template` FK → `EmailTemplate` (nullable if A/B variants each have their own template)
- `name` — CharField
- `campaign_type` — choices: `blast`, `drip`, `ab_test`
- `status` — choices: `draft`, `scheduled`, `sending`, `sent`, `paused`, `cancelled`
- `scheduled_at` — DateTimeField (null)
- `sent_at` — DateTimeField (null)
- `from_name` — CharField
- `from_email` — EmailField
- `reply_to` — EmailField (blank)
- `subject` — CharField (blast subject; overridden per-variant in ab_test mode)
- `recipients_count` — PositiveIntegerField default 0
- `delivered_count` — PositiveIntegerField default 0
- `opens_count` — PositiveIntegerField default 0
- `unique_opens_count` — PositiveIntegerField default 0
- `clicks_count` — PositiveIntegerField default 0
- `unique_clicks_count` — PositiveIntegerField default 0
- `bounces_count` — PositiveIntegerField default 0
- `unsubscribes_count` — PositiveIntegerField default 0
- `spam_reports_count` — PositiveIntegerField default 0
- `owner` FK → User

Derived properties:
- `open_rate` = unique_opens_count / delivered_count
- `click_rate` = unique_clicks_count / delivered_count
- `bounce_rate` = bounces_count / recipients_count
- `unsubscribe_rate` = unsubscribes_count / delivered_count

Drip-specific: child `DripStep` records (see below) when `campaign_type = drip`.

---

### 4a. `DripStep` (child of EmailCampaign, no number prefix — inline) — drip sequence steps

Maps to: 1.3.B automated drip campaigns, step-level metrics

Fields:
- `tenant` FK
- `email_campaign` FK → `EmailCampaign` (cascade)
- `order` — PositiveSmallIntegerField
- `delay_days` — PositiveIntegerField default 0
- `delay_hours` — PositiveIntegerField default 0
- `template` FK → `EmailTemplate`
- `subject_override` — CharField (blank — overrides template's default)
- `status` — choices: `active`, `paused`, `skipped`
- `sent_count` — PositiveIntegerField default 0
- `opens_count` — PositiveIntegerField default 0
- `clicks_count` — PositiveIntegerField default 0

---

### 4b. `ABVariant` (child of EmailCampaign, no number prefix — inline) — A/B test variants

Maps to: 1.3.B A/B testing (subject line / from name / content / send time)

Fields:
- `tenant` FK
- `email_campaign` FK → `EmailCampaign` (cascade)
- `variant_label` — choices: `A`, `B`, `C`
- `test_variable` — choices: `subject_line`, `from_name`, `content`, `send_time`
- `subject_override` — CharField (blank — used when test_variable = subject_line)
- `from_name_override` — CharField (blank — used when test_variable = from_name)
- `template` nullable FK → `EmailTemplate` (used when test_variable = content)
- `send_time_override` — TimeField (null — used when test_variable = send_time)
- `send_pct` — DecimalField (percent of list receiving this variant, e.g. 50.00)
- `recipients_count` — PositiveIntegerField default 0
- `opens_count` — PositiveIntegerField default 0
- `clicks_count` — PositiveIntegerField default 0
- `open_rate` — DecimalField (computed, stored for display)
- `click_rate` — DecimalField (computed, stored for display)
- `winner_criteria` — choices: `open_rate`, `click_rate`, `manual`
- `is_winner` — BooleanField default False
- `winner_selected_at` — DateTimeField (null)

---

### 5. `LandingPage` (LP-) — campaign landing page with embedded web form definition

Maps to: 1.3.C landing page creator, web form builder, A/B variant page, lead routing

Fields:
- `tenant` FK
- `campaign` nullable FK → `crm.Campaign`
- `name` — CharField
- `slug` — SlugField (unique per tenant; used in the public URL `/lp/<slug>/`)
- `status` — choices: `draft`, `published`, `archived`
- `headline` — CharField
- `body_html` — TextField (page body raw HTML)
- `cta_label` — CharField default "Submit"
- `success_message` — TextField (shown after submit when no redirect)
- `success_redirect_url` — URLField (blank)
- `form_fields` — JSONField (ordered list of {name, label, field_type, required, placeholder}) — field_type choices: text/email/phone/textarea/select/checkbox/date/hidden
- `routing_rule` — choices: `manual`, `round_robin`, `owner_match`
- `routing_filter` — JSONField (criteria for owner_match: {country, state, company_size})
- `default_owner` FK → User (used when routing_rule = manual)
- `captcha_enabled` — BooleanField default False
- `page_views` — PositiveIntegerField default 0
- `form_submissions_count` — PositiveIntegerField default 0 (denormalized counter)
- `page_variant` — choices: `control`, `variant_a`, `variant_b` (blank = not a variant)
- `parent_page` self-FK → `LandingPage` (null — set when this is a variant of another page)
- `traffic_pct` — DecimalField (percent of traffic sent to this variant; 100 for non-variant pages)
- `published_at` — DateTimeField (null, set when status → published)
- `owner` FK → User

---

### 6. `FormSubmission` (FS-) — captured lead data from a landing page form

Maps to: 1.3.C web-to-lead capture, UTM attribution, auto-lead-creation, spam filtering

Fields:
- `tenant` FK
- `landing_page` FK → `LandingPage`
- `data` — JSONField (key-value dict of captured form field values)
- `ip_address` — GenericIPAddressField (null)
- `referrer_url` — URLField (blank)
- `utm_source` — CharField (blank)
- `utm_medium` — CharField (blank)
- `utm_campaign` — CharField (blank)
- `utm_term` — CharField (blank)
- `utm_content` — CharField (blank)
- `submitted_at` — DateTimeField (auto_now_add)
- `status` — choices: `new`, `processed`, `duplicate`, `spam`
- `created_lead` nullable FK → `crm.Lead` (set by process_submission service)
- `notes` — TextField (blank — for manual reviewer notes)

Service: `process_submission(submission)` — reads `data['email']`, runs `Lead.objects.get_or_create(tenant, email=…)`, sets `created_lead`, updates `landing_page.form_submissions_count`, then optionally adds the lead to the parent `CampaignMember` list.

---

## Deferred (later passes / integrations)

- **Real ESP integration (actual email delivery)** — sending emails via SendGrid, Mailgun, AWS SES, Postmark. Requires async task queue (Celery) and API keys. NavERP models the data/metrics structures now; actual delivery is flagged for Module 0's integration layer or a dedicated integration module.

- **Drag-and-drop HTML visual builder** — in-browser WYSIWYG editor (GrapeJS, Unlayer, or Unlayer-react embed). The `html_body` TextField accepts raw HTML now; the visual editor is an integration/later frontend feature.

- **Send-time optimization / predictive send** — algorithm requires historical open-time data per contact. Model stub (`preferred_send_hour`) is noted but algorithm deferred until enough send data exists.

- **Smart Traffic / AI page routing** — Unbounce's ML-based visitor-to-variant routing. The `page_variant` + `traffic_pct` data model is in place; real-time ML routing is a future feature.

- **Progressive profiling on forms** — Marketo feature: hiding already-known fields and collecting new ones across visits. Requires cookie/session tracking of known contact data. Deferred to next pass.

- **Behavioral web-tracking (site events)** — ActiveCampaign and Klaviyo fire automation triggers based on page-visit events logged by a JS snippet. Requires an event-ingestion endpoint and async processor. Deferred.

- **SMS / WhatsApp channel** — ActiveCampaign 2025 added WhatsApp; Brevo supports SMS. Out of scope for this Django-only pass.

- **Multi-touch revenue attribution** — HubSpot's "influenced contacts" and Marketo's attribution models (first-touch, last-touch, U-shape) require aggregating CampaignMember + Opportunity data across time. The data model is ready; the report is deferred to Module 10 BI.

- **Separate `FormField` model** — the `form_fields` JSONField on `LandingPage` covers the current use case. If form-builder complexity grows (conditional logic, field reordering UI), a normalized `FormField` child model should be added in a later pass.

- **Transactional email (order confirmations, receipts)** — Mailchimp and Brevo support transactional emails. NavERP's transactional flows belong to Module 2 (Accounting) and Module 9 (eCommerce), not this CRM marketing sub-module.

- **Geography-based lead routing algorithm** — `routing_filter` JSONField is modeled; the matching service (IP-to-geo lookup + territory table) is deferred. Round-robin routing is implementable now.

- **CAPTCHA enforcement** — `captcha_enabled` bool is modeled; wiring to Google reCAPTCHA v3 or hCaptcha requires an API key and front-end JS, deferred to integration layer.
