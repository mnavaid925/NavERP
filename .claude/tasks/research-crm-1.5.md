# Research — CRM Sub-module 1.5: Activity & Communication Management (crm)

## Leaders surveyed (with source links)

1. **Salesforce Sales Cloud** — market-leading CRM with Activities (Tasks/Events), Einstein Activity Capture auto-sync, and an Activity Timeline panel — https://massmailer.io/blog/salesforce-activity-tracking-guide/
2. **HubSpot CRM** — free-tier CRM with Tasks, Meetings scheduler (booking link + calendar sync), built-in VoIP Calling, sequences, and unified contact timeline — https://www.hubspot.com/products/sales/schedule-meeting
3. **Zoho CRM** — full-stack CRM with Activities module, recurring tasks, SalesInbox BCC email logging, and Google/Outlook/Apple calendar sync — https://www.zoho.com/crm/calendar.html
4. **Pipedrive** — pipeline-first CRM with Activity Calendar, Smart Email BCC dropbox, Scheduler (meeting booking link), and Caller (VoIP with auto-log) — https://www.pipedrive.com/en/features/activity-calendar
5. **Microsoft Dynamics 365 Sales** — enterprise CRM with server-side Exchange/Outlook sync, appointment ICS, Teams meeting creation, open/past activity views — https://learn.microsoft.com/en-us/dynamics365/sales/manage-activities
6. **Freshsales (Freshworks CRM)** — mid-market CRM with built-in VoIP phone (90+ countries), email open/click tracking, activity timeline with engagement events — https://www.techradar.com/reviews/freshsales-crm-review
7. **Salesloft** — sales engagement platform with multi-channel cadences, call disposition/sentiment logging, recording URLs, and calendar widget for deal context — https://www.salesloft.com/platform/cadence-automation
8. **Outreach** — sales engagement platform with automatic call disposition logging, call recording/transcription, CRM activity sync, and recurring cadence scheduling — https://www.outreach.ai/resources/blog/crm-call-recording
9. **Calendly** — meeting scheduling tool with public booking links, single-use invite links, ICS file delivery, double-booking prevention, and Google/Outlook/Office 365 sync — https://calendly.com/scheduling/calendar-connections
10. **SuiteCRM / Zoho recurring tasks reference** — open-source CRM with recurring task extension covering daily/weekly/monthly/yearly recurrence patterns and series-vs-instance editing — https://store.suitecrm.com/addons/recurring-tasks-extension

---

## Feature catalog by sub-module

### 1.5.1 Task Management

- **Task types / categories** — Tasks are typed (call, email, meeting, follow-up, to-do) so filters and dashboards can break down activity by kind. Seen in: Salesforce, HubSpot, Zoho CRM, Pipedrive, Freshsales. Priority: table-stakes. Spine: existing `CrmTask.type` already covers this. Buildable now.

- **Priority and due date** — Every task carries a priority (low/medium/high) and a due_date, enabling overdue detection and list sorting. Seen in: Salesforce, HubSpot, Zoho CRM, Pipedrive, Freshsales, Dynamics 365. Priority: table-stakes. Spine: existing `CrmTask.priority` + `CrmTask.due_date`. Buildable now.

- **Status lifecycle with completion timestamp** — Statuses (open/in_progress/done/cancelled) with a system-set `completed_at` on completion and clearing on re-open. Seen in: Salesforce, HubSpot, Zoho CRM, Pipedrive. Priority: table-stakes. Spine: existing `CrmTask.status` + `CrmTask.completed_at`. Buildable now.

- **Relation to core entities** — Tasks link to a contact/account (core.Party), an opportunity (Opportunity), and an owner (User). Seen in: Salesforce, HubSpot, Zoho CRM, Pipedrive, Freshsales. Priority: table-stakes. Spine: existing `CrmTask.party` + `CrmTask.related_opportunity` + `CrmTask.owner`. Buildable now.

- **Open Activities vs Activity History panel** — The canonical separation: a list of upcoming/pending tasks ("Open Activities") paired with a list of completed/past tasks ("Activity History") on each record. Status-based automatic move: done/cancelled items fall to history; open/in-progress remain in the upcoming list. Seen in: Salesforce (explicit related-list split), HubSpot (timeline filter), Dynamics 365, Zoho CRM, Pipedrive. Priority: table-stakes. Spine: derived query on `CrmTask.status`; no new table needed — a view-layer concept. Buildable now.

- **Recurring tasks (series)** — A task can be marked to repeat on a schedule: daily / weekly / monthly / yearly, with a recurrence interval and end condition (never / after N occurrences / on date). The entire series is stored as a template + generated instances, or a single pattern row that spawns next instance on complete. Seen in: Salesforce (Repeat This Task after due/completed date, weekly capped at 53), Zoho CRM (custom daily/weekly/monthly/yearly patterns with weekend exclusion, business-day adjustment, bulk creation across records), SuiteCRM extension (daily/weekly/monthly/yearly, custom interval). Priority: common. Spine: new fields on `CrmTask` — `is_recurring`, `recurrence_rule` (daily/weekly/monthly/yearly), `recurrence_interval`, `recurrence_end_type` (never/count/date), `recurrence_end_count`, `recurrence_end_date`, `recurrence_parent` (self-FK to first task in series). Buildable now.

- **Spawn-next-on-complete pattern** — When a recurring task is marked done, the system automatically creates the next instance (offset from completed_date or due_date, per Salesforce's "after date completed" mode). Seen in: Salesforce ("After date completed" option), SuiteCRM extension. Priority: common. Spine: logic in `CrmTask.save()` — if `is_recurring` and status goes to done, create next sibling. Buildable now.

- **Reminder / due-time field** — A `due_time` (time-of-day) or `reminder_at` (datetime) to support notifications. Seen in: Salesforce, HubSpot (task reminder datetime), Zoho CRM (reminder on recurring tasks with apply-to-all-or-this pattern), Freshsales. Priority: common. Spine: new field `reminder_at` (DateTimeField, nullable) on `CrmTask`. Buildable now.

- **Related Case link** — Tasks can be associated with a support case in addition to opportunities, for activity tracking within the customer service workflow. Seen in: Salesforce, HubSpot, Zoho CRM. Priority: should. Spine: new optional FK `related_case` on `CrmTask`. Buildable now.

### 1.5.2 Calendar Integration

- **Calendar event entity** — A structured meeting/event record (separate from a task) with a subject, start/end datetime, location, and linked party/opportunity. Seen in: Salesforce (Event object), HubSpot (Meetings), Zoho CRM (Events in Activities), Pipedrive (Activity type=meeting), Dynamics 365 (Appointment). Priority: table-stakes. Spine: new `CalendarEvent` model, tenant-scoped, with FKs into `core.Party` + `Opportunity`. Buildable now.

- **Attendee list with RSVP** — Events have a many-to-many attendee list, each with an RSVP status: accepted / declined / tentative / no-response. The ICS/iCalendar standard (RFC-5545) defines these states; Dynamics 365 and Google Calendar both surface them. Seen in: Dynamics 365 (appointment attendee sync with Exchange), Zoho CRM (attendees become event participants), Google Calendar API (accepted/declined/tentative/needsAction), Calendly (invitee RSVP via confirmation email). Priority: common. Spine: new `EventAttendee` child model (event FK + party FK + rsvp_status choices). Buildable now.

- **Public booking / invite link** — A shareable URL that lets an external contact choose an open time slot, generating the event automatically and sending an ICS confirmation. The link is driven by an unguessable token (as used by LandingPage.public_token in this codebase). Seen in: HubSpot Meetings (booking link eliminating scheduling back-and-forth), Pipedrive Scheduler (define weekly availability, generate link, auto-send invite), Calendly (shareable booking link with single-use variant), Freshsales (appointment scheduling link via Calendly integration), Salesloft (meetings calendar widget in email). Priority: common. Spine: `CalendarEvent.booking_token` (char 64, unique, nullable, generated once); a public booking page reads availability and creates the event. Buildable now (the public page is a Django view with no external OAuth needed).

- **ICS / iCalendar export** — An `.ics` file download that recipients open in any calendar app (Outlook, Google Calendar, Apple Calendar) to save the event. Calendly sends an ICS file with every email confirmation. Dynamics 365 documents sending ICS to customers. Priority: common. Spine: no new field; a Django view generates the ICS payload from `CalendarEvent` fields on demand. Buildable now.

- **Two-way calendar sync source tagging** — Track which external calendar system the event was sourced from or last synced to (google / outlook / ical / manual). Used for provenance and to avoid duplicate creation when syncing. Seen in: Salesforce Einstein Activity Capture (syncs with Outlook/Google and links back), Zoho CRM (Google/Outlook/Office365/Apple sync), Pipedrive (Google + Outlook two-way sync), Dynamics 365 (Exchange server-side sync). Priority: common. Spine: `CalendarEvent.sync_source` (choices: manual/google/outlook/ical); `CalendarEvent.external_uid` (char, nullable) for matching on re-sync. Buildable now (stores provenance; actual OAuth push is integration/later).

- **Reminder / notification** — A lead-time reminder (e.g., 15 min / 1 hour / 1 day before) sent to organizer and attendees. Seen in: Zoho CRM (email reminders for participants who haven't responded), Salesforce, HubSpot, Pipedrive (automated reminder notifications), Calendly (scheduling notifications). Priority: common. Spine: `CalendarEvent.reminder_minutes` (PositiveSmallIntegerField, nullable, default 15). Buildable now (the email send is integration/later; the field drives a future task).

- **Video conference URL** — A link to a Zoom/Teams/Meet video call auto-generated or manually entered for the event. Seen in: HubSpot Meetings (Zoom/GoTo integration), Pipedrive (Zoom/Microsoft Teams/Google Meet), Dynamics 365 Teams meeting creation, Calendly. Priority: should. Spine: `CalendarEvent.video_url` (URLField, blank). Buildable now (store the URL; auto-generation is integration/later).

- **Event status / outcome** — Track whether an event was completed, cancelled, no-show, or rescheduled. Seen in: HubSpot (completion/cancellation/no-show counts), Dynamics 365 (Free/Busy/Completed/Cancelled states), Freshsales (activity timeline). Priority: should. Spine: `CalendarEvent.status` choices (scheduled/completed/cancelled/no_show/rescheduled). Buildable now.

### 1.5.3 Email & Call Integration

- **Unified communication log** — A single model capturing all channel interactions (email, call, SMS, note) against a party/opportunity so the activity timeline is one query. Seen in: HubSpot (calls, emails, meetings, notes, SMS, LinkedIn, WhatsApp on one timeline), Freshsales (real-time activity feed), Salesloft (every email/call/meeting on contact timeline), Outreach (call recording + email threads in single deal view). Priority: table-stakes. Spine: new `CommunicationLog` model. Buildable now.

- **Channel types** — Distinguish call / email / SMS / note / voicemail / chat per log entry. Seen in: HubSpot (calls, communications, emails, meetings, notes, postal mail, tasks), Salesloft (cadence steps: call, email, LinkedIn, SMS), Outreach (call + email + meeting cadence steps). Priority: table-stakes. Spine: `CommunicationLog.channel` choices (call/email/sms/note/voicemail/chat/other). Buildable now.

- **Direction (inbound / outbound)** — Whether the communication was initiated by the rep (outbound) or received from the contact (inbound). Standard across all VoIP/email log integrations. Seen in: HubSpot (call: Inbound/Outbound; email: Incoming/Outgoing), Salesloft (30+ activity properties including direction), Outreach (inbound/outbound call mapping), VoIP CRM integration standards. Priority: table-stakes. Spine: `CommunicationLog.direction` choices (inbound/outbound). Buildable now.

- **Call duration** — Duration in seconds of a completed call. Core field for call activity analytics (average talk time, rep productivity). Seen in: HubSpot (call duration in milliseconds), Salesloft (length of call in seconds, synced to CRM), Outreach (duration field), Freshsales (call log), Pipedrive Caller (automatic log with duration). Priority: table-stakes for calls. Spine: `CommunicationLog.duration_seconds` (PositiveIntegerField, nullable, call-only). Buildable now.

- **Call outcome / disposition** — Categorize what happened on a call: connected / voicemail / no-answer / busy / wrong-number. Salesloft uses "disposition" separately from "sentiment." Outreach defaults to "No Answer" when not logged. HubSpot has customizable call outcome. Seen in: Salesloft (disposition: connected/voicemail/no-answer, sentiment: positive/neutral/negative), Outreach (disposition required before next activity, default "No Answer"), HubSpot (call outcome customizable), Pipedrive Caller (outcome logged automatically). Priority: table-stakes for calls. Spine: `CommunicationLog.outcome` choices (connected/voicemail/no_answer/busy/wrong_number/other) — nullable (only relevant for calls). Buildable now.

- **Email BCC dropbox address** — A per-tenant unique email address that, when BCC'd on any outgoing email, automatically logs that email to the matching contact's timeline. Each product has its own scheme: Pipedrive uses a universal domain address + per-deal addresses; HubSpot uses a per-user BCC address; Zoho SalesInbox has drag-and-drop. The log record stores the raw BCC address used. Seen in: HubSpot (BCC logs to contact + company + 5 most recent open deals), Pipedrive Smart BCC (auto-links if single open deal; creates contact if new; manual link otherwise), Zoho SalesInbox (drag-and-drop email to create leads/contacts/deals), SuiteCRM. Priority: common. Spine: `CommunicationLog.logged_via` choices (manual/bcc_dropbox/voip_auto/api/email_sync). No full BCC server needed for Phase 1 — a tenant `bcc_dropbox_address` config field and a webhook/forwarding handler is sufficient. Integration/later for the mail-receive engine; model is buildable now.

- **Email subject and body snippet** — For logged emails, store the subject and a trimmed body preview so the timeline is readable without expanding each row. Seen in: HubSpot (from/to, subject, BCC recipients), Zoho SalesInbox (full email), Pipedrive Smart BCC (Mail tab inbox). Priority: common. Spine: `CommunicationLog.subject` (CharField), `CommunicationLog.body_snippet` (TextField, blank). Buildable now.

- **Message-ID deduplication** — Store the email's `Message-ID` header to prevent the same email being logged twice (e.g., via both BCC and manual forward). Seen in: HubSpot (implicit through email logging engine), described as a critical gap in mid-market CRMs. Priority: should. Spine: `CommunicationLog.message_id` (CharField max 255, blank, db_indexed per tenant). Buildable now.

- **Call recording URL** — A link to the audio recording stored externally (Twilio/Aircall/Ringover). The CRM stores the URL; the audio lives in the VoIP platform's storage. Seen in: HubSpot (recording URL property), Salesloft (conversation recording URL logged to CRM), Outreach (automatically imports recordings from Orum/Nooks), Freshsales (built-in call recording). Priority: common. Spine: `CommunicationLog.recording_url` (URLField, blank). Integration/later for the recording; field is buildable now.

- **VoIP provenance tag** — Which VoIP or email system generated the log (twilio/aircall/ringcentral/hubspot_voip/manual). Used to know whether the record is a draft (manual) or a verified auto-log. Seen in: HubSpot (call source: VoIP/Zoom), Salesloft (activity source synced to CRM), Outreach (Orum/Nooks provenance). Priority: should. Spine: folded into `CommunicationLog.logged_via` choices listed above. Buildable now.

- **Association to contact, opportunity, and case** — Each log entry links to a party (contact/account), optionally to an opportunity, and optionally to a case (for service call-backs). Seen in: HubSpot (auto-associated to contact + company + open deals), Pipedrive Smart BCC (contact + deal auto-link), Salesforce (linked to contact/lead/opportunity). Priority: table-stakes. Spine: `CommunicationLog.party` (FK core.Party), `CommunicationLog.opportunity` (FK Opportunity, nullable), `CommunicationLog.case` (FK Case, nullable). Buildable now.

- **Open/click tracking metadata** — For outbound emails, store whether the email was opened and whether a link was clicked. HubSpot BCC alone does NOT provide tracking; only connected-inbox or sequence emails track opens/clicks. Seen in: HubSpot (open rate, click rate, reply rate on email properties — only for connected/sequence emails), Freshsales (open and click notifications), Zoho SalesInbox (template open/click analytics), Salesloft (open/click/reply synced to timeline). Priority: differentiator (requires email send engine). Spine: `CommunicationLog.opened_at` (DateTimeField, nullable), `CommunicationLog.clicked_at` (DateTimeField, nullable). Fields buildable now; population requires integration/later email send.

- **Sentiment / call notes** — A free-text notes field per log entry plus an optional call sentiment (positive / neutral / negative). Seen in: Salesloft (sentiment field separate from disposition), Outreach (notes captured during call, AI summary after), HubSpot (internal call notes). Priority: should. Spine: `CommunicationLog.notes` (TextField, blank), `CommunicationLog.sentiment` choices (positive/neutral/negative, nullable). Buildable now.

---

## Recommended build scope (this pass — 4 models)

### 1. `CrmTask` [ENHANCE — existing model]
Existing fields are correct. Add the following to cover researched features:
- `reminder_at` — DateTimeField, nullable, blank — for HubSpot/Zoho/Salesforce-style task reminder datetime
- `related_case` — FK to `crm.Case`, SET_NULL, null/blank — task linkable to a support case (Salesforce/HubSpot pattern)
- `is_recurring` — BooleanField, default False — flag this task as the head of a recurring series
- `recurrence_rule` — CharField max 10, choices: `daily/weekly/monthly/yearly`, blank — recurrence frequency (Zoho/Salesforce)
- `recurrence_interval` — PositiveSmallIntegerField, default 1 — "every N days/weeks/months" (Zoho custom intervals)
- `recurrence_end_type` — CharField max 10, choices: `never/count/date`, blank — termination rule (Zoho: never/after X times/on date)
- `recurrence_end_count` — PositiveSmallIntegerField, nullable, blank — number of occurrences when end_type=count
- `recurrence_end_date` — DateField, nullable, blank — end date when end_type=date
- `recurrence_parent` — self-FK SET_NULL, null/blank, related_name `recurrence_children` — links spawned instances back to the head task (Salesforce series model)
- `save()` logic: when status transitions to `done` and `is_recurring=True` (and `recurrence_parent` is None or self is the current head), spawn next instance offset from `due_date` by interval

### 2. `CalendarEvent` [NEW — number-prefixed EVT]
Tenant-scoped event/meeting, linked to the unified spine. Fields:
- `tenant` — FK core.Tenant (TenantNumbered abstract base)
- `number` — auto-assigned with prefix `EVT`
- `subject` — CharField 255
- `event_type` — CharField choices: `meeting/demo/call/webinar/training/other` — event categorization
- `status` — CharField choices: `scheduled/completed/cancelled/no_show/rescheduled` — lifecycle (HubSpot/Dynamics pattern)
- `start_at` — DateTimeField — event start
- `end_at` — DateTimeField, nullable — event end (null = all-day / TBD)
- `location` — CharField 255, blank — physical location or video URL placeholder
- `video_url` — URLField, blank — Teams/Zoom/Meet link (HubSpot Meetings/Pipedrive pattern)
- `party` — FK core.Party, SET_NULL, null/blank — primary contact/account (spine reuse)
- `opportunity` — FK crm.Opportunity, SET_NULL, null/blank — linked deal
- `case` — FK crm.Case, SET_NULL, null/blank — linked support case
- `owner` — FK AUTH_USER_MODEL, SET_NULL, null/blank — organizer/rep
- `sync_source` — CharField choices: `manual/google/outlook/ical` — provenance (Einstein Activity Capture / Pipedrive sync pattern)
- `external_uid` — CharField 255, blank — calendar UID for dedup on re-sync
- `reminder_minutes` — PositiveSmallIntegerField, nullable, default 15 — lead-time reminder (Zoho/HubSpot/Salesforce)
- `booking_token` — CharField 64, unique, blank, auto-generated via `secrets.token_urlsafe(32)` — public invite/booking link (HubSpot Meetings/Pipedrive Scheduler/Calendly pattern)
- `description` — TextField, blank
- `created_at`, `updated_at` — auto timestamps

### 3. `EventAttendee` [NEW — child of CalendarEvent]
One row per attendee per event. Not numbered. Fields:
- `tenant` — FK core.Tenant
- `event` — FK CalendarEvent CASCADE, related_name `attendees`
- `party` — FK core.Party, SET_NULL, null/blank — CRM contact/account (spine reuse)
- `attendee_name` — CharField 255 — display snapshot (survives party deletion)
- `attendee_email` — EmailField, blank — used for ICS delivery and BCC matching
- `rsvp_status` — CharField choices: `no_response/accepted/declined/tentative` — iCalendar RFC-5545 standard states (Google Calendar, Dynamics 365, Calendly)
- `responded_at` — DateTimeField, nullable, system-set when rsvp_status changes from no_response
- `is_organizer` — BooleanField, default False — marks the meeting organizer among attendees
- `created_at` — DateTimeField auto_now_add

### 4. `CommunicationLog` [NEW — number-prefixed CLOG]
Unified interaction record for the activity history/timeline. Fields:
- `tenant` — FK core.Tenant (TenantNumbered abstract base)
- `number` — auto-assigned with prefix `CLOG`
- `channel` — CharField choices: `call/email/sms/note/voicemail/chat/other` — interaction channel (HubSpot unified activity type)
- `direction` — CharField choices: `inbound/outbound`, blank — who initiated (HubSpot inbound/outgoing; Salesloft 30+ properties)
- `subject` — CharField 255, blank — email subject or call topic
- `body_snippet` — TextField, blank — email body preview or call description / note text
- `notes` — TextField, blank — freeform internal notes / call summary (HubSpot notes; Outreach AI summary stored here)
- `sentiment` — CharField choices: `positive/neutral/negative`, blank, nullable — call/conversation sentiment (Salesloft disposition+sentiment split)
- `outcome` — CharField choices: `connected/voicemail/no_answer/busy/wrong_number/other`, blank, nullable — call-only disposition (Salesloft/Outreach/HubSpot customizable outcome)
- `duration_seconds` — PositiveIntegerField, nullable — call duration (HubSpot milliseconds→seconds; Salesloft seconds; standard VoIP field)
- `recording_url` — URLField, blank — VoIP call recording link (HubSpot recording URL; Salesloft conversation URL; Outreach recording)
- `logged_via` — CharField choices: `manual/bcc_dropbox/voip_auto/api/email_sync` — provenance tag (HubSpot BCC vs connected-inbox; Pipedrive Smart BCC; Freshsales auto-log)
- `message_id` — CharField 255, blank, db_indexed per tenant — email Message-ID header for deduplication
- `opened_at` — DateTimeField, nullable — first email open timestamp (HubSpot/Freshsales/Salesloft open tracking)
- `clicked_at` — DateTimeField, nullable — first link click timestamp (HubSpot/Salesloft click tracking)
- `party` — FK core.Party, SET_NULL, null/blank — contact/account (spine reuse; HubSpot auto-associates to contact + company)
- `opportunity` — FK crm.Opportunity, SET_NULL, null/blank — linked deal (HubSpot: 5 most recent open deals; Pipedrive Smart BCC auto-link)
- `case` — FK crm.Case, SET_NULL, null/blank — linked support case (Salesforce/HubSpot service call-back log)
- `calendar_event` — FK CalendarEvent, SET_NULL, null/blank — the scheduled event this log records an outcome for (post-meeting note)
- `owner` — FK AUTH_USER_MODEL, SET_NULL, null/blank — rep who made/received the interaction
- `logged_at` — DateTimeField, default timezone.now — the actual interaction time (may differ from created_at for retrospective logging)
- `created_at`, `updated_at` — auto timestamps

---

## Deferred (later passes / integrations)

- **Live email send/receive engine** — A full SMTP/IMAP mail-receive handler to process inbound BCC dropbox emails is an external integration. The `logged_via=bcc_dropbox` field and `message_id` dedup field are ready; the mail-receive webhook is deferred.
- **OAuth calendar push (Google / Outlook two-way sync)** — `CalendarEvent.sync_source` and `external_uid` store provenance; actual event push/pull via Google Calendar API or MS Graph API is an external OAuth integration deferred to a later pass.
- **Email open/click tracking pixels** — `opened_at` / `clicked_at` fields are modeled; the tracking pixel server and email send engine are out of scope for a Django-only pass.
- **VoIP dialer integration (Twilio/Aircall/Ringcentral)** — `duration_seconds`, `recording_url`, `logged_via=voip_auto`, `outcome` fields are modeled; the real-time call webhook handler is deferred.
- **AI call transcription and summary** — Outreach/Salesloft AI summaries (post-call transcript → AI summary) stored in `notes`; transcription pipeline is integration/later.
- **Round-robin meeting scheduling** — HubSpot / Calendly team round-robin distribution is a view-layer feature above the `CalendarEvent.booking_token` foundation; deferred.
- **SMS gateway send** — `CommunicationLog.channel=sms` is modeled for logging inbound/outbound SMS; the send gateway (Twilio SMS) is integration/later.
- **Business-hours calendar for SLA / task due calculation** — Zoho CRM supports business-day adjustment on recurring tasks (skip weekends, skip holidays). Deferred alongside the SLA policy business-hours calendar already deferred in 1.4.
- **Bulk recurring task creation across multiple records** — Zoho supports creating a recurring task simultaneously on multiple contact/deal records. Deferred; single-record recurrence ships first.
- **Email sequence / cadence engine** — Salesloft/Outreach multi-step automated outreach sequences that spawn tasks + emails over time are a full sub-system. `CrmTask.is_recurring` + `CommunicationLog` provide the data foundation; the sequence engine itself is a separate sub-module (1.10 Workflow Engine already has WorkflowRule/WorkflowLog).
