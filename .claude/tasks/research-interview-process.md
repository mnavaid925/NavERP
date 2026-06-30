# Research — Module 3, Sub-module 3.7: Interview Process (hrm)

## Scope
This research covers **3.7 Interview Process only** — specifically:
- Interview Scheduling (calendar, slot booking)
- Interview Panel (assign interviewers, round management)
- Interview Feedback (rating forms, feedback collection)
- Video Interview (Zoom/Teams/Meet integration)
- Interview Reminders (automated email/SMS reminders)

The existing 3.5/3.6 recruiting spine (`JobRequisition`, `CandidateProfile`, `JobApplication`,
`CandidateEmailTemplate`, `CandidateCommunication`) is already built and must be reused as the anchor.
Interviews attach to a `JobApplication` (FK by string). Interviewers are `accounts.User` / `hrm.EmployeeProfile`.

---

## Leaders surveyed (with source links)

1. **Greenhouse** — structured-hiring-first ATS; industry benchmark for scorecards and interview kits
   — https://www.greenhouse.com/interviewing-decision-making & https://support.greenhouse.io/hc/en-us/articles/4414777492891-Scorecard-overview
2. **Lever (Talent Relationship Management)** — ATS + CRM with self-schedule links, AI Interview Companion,
   panel scheduling across time zones
   — https://www.lever.co/ & https://help.lever.co/hc/en-us/articles/20087302635421-Scheduling-interviews
3. **Ashby** — modern all-in-one ATS; anti-anchoring feedback blinding, briefing views, AI feedback summaries
   — https://www.ashbyhq.com/platform/recruiting/ats
4. **SmartRecruiters** — enterprise TA suite; native video interviewing, up-to-20-competency scorecards,
   automated reminders, real-time calendar sync
   — https://www.smartrecruiters.com/resources/glossary/interview-scorecard/
5. **Workable** — SMB-friendly ATS; interview kits (thumbs/stars/numbers rating), per-stage one-evaluation rule,
   bias-reduction feedback blinding, template management
   — https://help.workable.com/hc/en-us/articles/115012304987-Creating-and-using-an-interview-kit-scorecard
6. **Zoho Recruit** — SMB/mid-market ATS; formal/video/log interview types, built-in Zoho Meeting,
   Teams/Google Meet links, star/thumb rating, hire-recommendation statuses (Strongly Hired → Strongly Rejected)
   — https://help.zoho.com/portal/en/kb/recruit/module-set-up/interviews/articles/how-to-schedule-interviews-in-zoho-recruit
   & https://help.zoho.com/portal/en/kb/recruit/module-set-up/interviews/articles/interview-evaluation
7. **Recruitee (Tellent)** — pipeline-focused ATS; automatic Zoom/Meet/Teams link generation on schedule,
   WhatsApp reminders, anonymous candidate review, AI evaluation insights
   — https://recruitee.com/interviewing
8. **GoodTime Hire** — dedicated enterprise interview-scheduling orchestration platform; AI interviewer
   selection/load balancing, shadow/reverse-shadow training automation, SMS/WhatsApp messaging, candidate portal
   — https://goodtime.io/products/hire/automated-interview-scheduling/
9. **Workday Recruiting** — enterprise HCM with built-in interview scheduling, scorecard reminders, Teams/Slack
   feedback exchange, native calendar integration
   — https://research.com/software/reviews/workday-recruiting
10. **Spark Hire** — specialized one-way + live video interview platform; pre-set questions, AI transcription +
    summary, AI scoring on 6 dimensions, ATS sync
    — https://www.sparkhire.com/video-interviews/software/

---

## Feature catalog by sub-module

### 3.7.1 Interview Scheduling

- **Scheduled interview record (date/time/duration/location)** — the core object: a named interview event tied
  to an application, recording when/where it happens and its mode (in-person/phone/video).
  Seen in: all 10 products.
  Priority: table-stakes.
  Spine: new table `Interview` FK → `hrm.JobApplication`, `accounts.User` (scheduled_by).
  Buildable now.

- **Interview mode / type** — distinguishes in-person, phone screen, video call, one-way video, and panel
  (multiple interviewers at once). Zoho uses formal/video/log; all others have at least in-person vs. video.
  Seen in: Greenhouse, Lever, Zoho Recruit, Workable, Recruitee, SmartRecruiters.
  Priority: table-stakes.
  Spine: `mode` CharField on `Interview` (in_person / phone / video / one_way_video).
  Buildable now.

- **Interview round / sequence number** — assigns a stage order (Round 1 - Phone Screen, Round 2 - Technical,
  Round 3 - Final Panel) so multiple interviews on one application are orderable and linkable.
  Seen in: Greenhouse, Lever, Ashby, SmartRecruiters, Workday.
  Priority: table-stakes.
  Spine: `round_number` PositiveSmallIntegerField on `Interview`.
  Buildable now.

- **Self-scheduling / candidate slot booking** — sends the candidate a link to pick from available slots
  (requires real calendar-sync). Greenhouse, Lever, Ashby, Workable, BambooHR, Recruitee all support it.
  NavERP scope: store the `candidate_availability_link` text field for an external Calendly/similar URL;
  manual slot booking in the form. Full calendar-sync is deferred.
  Seen in: Greenhouse, Lever, Ashby, BambooHR, Recruitee, GoodTime.
  Priority: common.
  Spine: `candidate_self_schedule_url` URLField on `Interview` (stores the link; dispatch deferred).
  Integration/later for live calendar sync; metadata field buildable now.

- **Calendar integration (two-way)** — syncs interviewer and candidate calendars (Google Calendar, Outlook)
  so the interview appears on both sides without manual entry. Requires OAuth/calendar API.
  Seen in: all 10 products.
  Priority: table-stakes (as a capability) — but the OAuth plumbing is an integration.
  Spine: store `calendar_event_id` CharField on `Interview` for future sync. Integration/later.

- **Video meeting link / provider metadata** — stores the Zoom/Teams/Google Meet URL attached to a video
  interview. Recruitee auto-generates this on save; NavERP stores it manually with provider enum.
  Seen in: Greenhouse, Lever, Ashby, SmartRecruiters, Workable, Recruitee, Zoho Recruit, BambooHR.
  Priority: table-stakes.
  Spine: `video_provider` CharField (zoom/teams/meet/other/none) + `meeting_url` URLField on `Interview`.
  Buildable now.

- **Interview status workflow** — tracks lifecycle: scheduled → confirmed → in_progress → completed →
  cancelled / no_show / rescheduled. All products surface this.
  Seen in: all 10 products.
  Priority: table-stakes.
  Spine: `status` CharField with choices on `Interview`.
  Buildable now.

- **Duration (minutes)** — stores the planned length of the interview session.
  Seen in: Lever, Greenhouse, Zoho Recruit, Workable, GoodTime.
  Priority: table-stakes.
  Spine: `duration_minutes` PositiveSmallIntegerField on `Interview`.
  Buildable now.

- **Location / room** — physical room or address for in-person interviews; optional free-text.
  Seen in: Zoho Recruit, SmartRecruiters, Workable, BambooHR.
  Priority: common.
  Spine: `location` CharField (free-text) on `Interview`.
  Buildable now.

- **AI-assisted slot recommendation (load balancing)** — GoodTime's signature feature: AI picks interviewers
  based on availability, past load, and seniority. Way beyond one-Django-pass scope.
  Seen in: GoodTime, Greenhouse (2025 AI), Lever.
  Priority: differentiator.
  Defer.

### 3.7.2 Interview Panel (Interviewer Assignment)

- **Interviewer assignment (M2M interviewers per interview)** — each interview has one or more interviewers,
  each with a defined role (lead, shadow, note-taker). Greenhouse, Lever, Ashby, Workday all support role labels.
  Seen in: all 10 products.
  Priority: table-stakes.
  Spine: new through-table `InterviewPanelist` (Interview FK, User FK, role CharField, RSVP status).
  Buildable now.

- **Interviewer role on panel** — labels like Lead Interviewer, Technical Interviewer, HR Interviewer,
  Shadow/Observer. Greenhouse supports "recruiter/hiring manager as default role". Lever supports note-taker.
  Seen in: Greenhouse, Lever, Ashby, GoodTime, Workday.
  Priority: common.
  Spine: `role` CharField on `InterviewPanelist` (lead / interviewer / shadow / observer).
  Buildable now.

- **RSVP / confirmation status per panelist** — tracks whether each interviewer accepted, declined, or is
  pending. Zoho Recruit calls it "RSVP status". Important for knowing who actually confirmed.
  Seen in: Greenhouse, Lever, Zoho Recruit, GoodTime, Workday.
  Priority: common.
  Spine: `rsvp_status` CharField on `InterviewPanelist` (pending / accepted / declined).
  Buildable now.

- **Interviewer briefing / prep notes** — Ashby's "briefing views": per-panelist instructions attached to the
  interview plan, telling each interviewer what to cover. Lever allows "personalized notes in calendar event".
  Seen in: Ashby, Lever, Greenhouse (interview kits).
  Priority: common.
  Spine: `briefing_notes` TextField on `InterviewPanelist` (per-interviewer instructions).
  Buildable now.

- **Shadow / training designation** — GoodTime tracks whether a panelist is an interviewer-in-training
  (shadow or reverse-shadow). Adds readiness logic. Beyond simple CRUD for now.
  Seen in: GoodTime.
  Priority: differentiator.
  Defer (simple `is_shadow` BooleanField is buildable; full readiness tracking deferred).

- **Interviewer load balancing (AI)** — GoodTime's AI distributes interview load evenly. Requires analytics.
  Seen in: GoodTime.
  Priority: differentiator.
  Defer.

- **Feedback blinding (anti-anchoring)** — interviewers cannot see each other's feedback until they submit
  their own. Ashby calls this their most-cited bias-reduction feature; Workable and Greenhouse also support it.
  Seen in: Ashby, Greenhouse, Workable, Lever.
  Priority: common.
  Spine: enforced by view logic — a panelist's `InterviewFeedback` is only visible to others after they have
  submitted their own. No extra field needed; query logic in the view.
  Buildable now.

### 3.7.3 Interview Feedback (Scorecard / Evaluation)

- **Feedback / scorecard record** — structured evaluation submitted by each panelist after an interview.
  One per panelist per interview. Contains competency ratings, open notes, and overall recommendation.
  Seen in: all 10 products.
  Priority: table-stakes.
  Spine: new table `InterviewFeedback` (Interview FK, submitted_by User FK, submitted_at, overall_recommendation).
  Buildable now.

- **Overall hire recommendation** — a single top-level verdict: Greenhouse uses "Definitely Not / No / Yes /
  Strong Yes"; Zoho uses "Strongly Hired / Hired / On Hold / Rejected / Strongly Rejected"; Workable uses
  thumbs or stars. NavERP should adopt a 5-level scale: strong_no / no / maybe / yes / strong_yes.
  Seen in: all 10 products.
  Priority: table-stakes.
  Spine: `overall_recommendation` CharField with choices on `InterviewFeedback`.
  Buildable now.

- **Competency / attribute ratings (scorecard lines)** — structured criteria (e.g., "Problem Solving",
  "Communication", "Technical Skills") rated per criterion. Greenhouse calls them "focus attributes";
  Workable supports up to N per kit; SmartRecruiters supports up to 20 competencies.
  Seen in: Greenhouse, Workable, SmartRecruiters, Lever, Zoho Recruit, Recruitee.
  Priority: table-stakes.
  Spine: new table `FeedbackCriterion` (InterviewFeedback FK, criterion_name, rating IntegerField 1–5, notes).
  Buildable now.

- **Rating scale** — Greenhouse: 4-option recommendation; Workable: thumbs / stars / numbers; Zoho: 1–5 stars
  or thumb. NavERP: standardize on 1–5 integer per criterion, plus a top-level 5-label recommendation.
  Seen in: all products with scorecards.
  Priority: table-stakes.
  Spine: `rating` PositiveSmallIntegerField (1–5) on `FeedbackCriterion`.
  Buildable now.

- **Free-text notes per criterion** — interviewers can add a note below each criterion rating, explaining
  the score. Greenhouse calls this "key takeaways section". Workable: "+Add note" per topic.
  Seen in: Greenhouse, Workable, SmartRecruiters, Ashby.
  Priority: common.
  Spine: `notes` TextField (blank=True) on `FeedbackCriterion`.
  Buildable now.

- **Overall free-text summary** — a concluding paragraph separate from per-criterion notes. Greenhouse's
  "key takeaways" section; Zoho's "Overall Comments".
  Seen in: Greenhouse, Zoho Recruit, Workable, Lever.
  Priority: table-stakes.
  Spine: `summary` TextField on `InterviewFeedback`.
  Buildable now.

- **Feedback submission timing (submitted_at, is_submitted flag)** — distinguishes a draft in progress from
  a formally submitted scorecard. Enables the feedback-blinding rule (don't show to others until submitted).
  Seen in: Greenhouse (editable up to 30 days), Workable (one per stage per user), Ashby.
  Priority: common.
  Spine: `is_submitted` BooleanField + `submitted_at` DateTimeField on `InterviewFeedback`.
  Buildable now.

- **AI scorecard summarization** — Greenhouse 2025 AI summarizes all scorecards on the candidate profile,
  surfaces agreement/disagreement. Ashby highlights strengths/weaknesses automatically.
  Seen in: Greenhouse, Ashby, Lever, Recruitee.
  Priority: differentiator.
  Defer (requires LLM API).

### 3.7.4 Video Interview

- **Video meeting URL + provider stored on Interview** — minimal viable: store a URL and a provider
  enum (zoom/teams/meet/other). Recruitee auto-generates it; NavERP stores it manually for now.
  Seen in: Greenhouse, Lever, Ashby, Workable, SmartRecruiters, Recruitee, Zoho Recruit, BambooHR.
  Priority: table-stakes.
  Spine: `video_provider` + `meeting_url` on `Interview` (described above).
  Buildable now.

- **One-way / async video interview** — candidates record answers to pre-set questions on their own schedule
  (Spark Hire, HireVue, Zoho Recruit "Recorded Video Interview"). Requires a video-hosting service.
  Seen in: Spark Hire, HireVue, Zoho Recruit, SmartRecruiters.
  Priority: differentiator (for synchronous NavERP; async video is a third-party concern).
  Defer — note as an external-platform integration (Spark Hire / HireVue embed).

- **Native video conferencing** — SmartRecruiters 2025 added native video; Zoho uses Zoho Meeting.
  NavERP will not build a WebRTC conferencing stack — always link out.
  Seen in: SmartRecruiters, Zoho Recruit.
  Priority: differentiator / integration.
  Defer.

- **Zoom/Teams/Meet OAuth auto-link generation** — Recruitee and BambooHR generate meeting links
  automatically on interview save by calling the video provider's API.
  Seen in: Recruitee, BambooHR, Zoho Recruit, Workable.
  Priority: common (as an integration) — the data field is buildable now; the OAuth call is deferred.
  Spine: `meeting_url` URLField stores whatever was auto-generated or manually entered.
  Integration/later for OAuth.

- **AI video scoring (one-way)** — Spark Hire AI scores on Communication, Comprehension, Enthusiasm, etc.;
  HireVue Interview Insights surfaces key moments.
  Seen in: Spark Hire, HireVue.
  Priority: differentiator.
  Defer.

### 3.7.5 Interview Reminders

- **Candidate invite email on schedule** — when an interview is created/confirmed, send an invite to the
  candidate via the existing `CandidateCommunication` + `CandidateEmailTemplate` infrastructure (3.6).
  Seen in: all 10 products.
  Priority: table-stakes.
  Spine: reuse `hrm.CandidateCommunication` (application FK, channel=email, template=interview_invite type).
  Buildable now — add `interview_invite` to `EMAIL_TEMPLATE_TYPE_CHOICES` if not present; POST action on
  the interview detail page triggers the send and logs to `CandidateCommunication`.

- **Interviewer notification on assignment** — when a panelist is added, send them an email notification
  (subject, date/time, candidate name, briefing link).
  Seen in: Greenhouse, Lever, Workable, SmartRecruiters, Recruitee.
  Priority: table-stakes.
  Spine: standard Django `send_mail` from the `InterviewPanelist` save action; no new model needed.
  Buildable now.

- **Pre-interview reminder (N hours/days before)** — automatic reminder sent to candidate and/or interviewers
  a configured time before the interview. Lever allows configuring "how often feedback reminders go out".
  Seen in: Greenhouse, Lever, Workable, SmartRecruiters, Recruitee, GoodTime.
  Priority: common.
  Spine: `reminder_sent_at` DateTimeField (nullable) on `Interview` to record when the reminder was dispatched;
  actual delivery logic deferred to a Celery task / management command. Metadata field buildable now.

- **Feedback reminder (after interview, to panelists who haven't submitted)** — Lever configures how often
  reminders go out post-interview; Greenhouse has scorecard reminder functionality; Workday has built-in
  scorecard reminder.
  Seen in: Greenhouse, Lever, Workday, Recruitee.
  Priority: common.
  Spine: `feedback_reminder_sent_at` DateTimeField (nullable) on `Interview`; logic deferred to async task.
  Metadata field buildable now.

- **SMS / WhatsApp reminders** — GoodTime and Recruitee support mobile-channel reminders. Requires gateway.
  Seen in: GoodTime, Recruitee.
  Priority: differentiator / integration.
  Defer.

---

## Recommended build scope (this pass — 4 models)

The four models below cover all five 3.7 feature bullets, map to real list/detail/form CRUD pages, are
tenant-scoped, and reuse the existing HRM recruiting spine.

### Model 1: `Interview` [INTV-]
**The scheduled interview event** — one record per round of interviewing for an application.

Core fields justified by research:
- `tenant` FK → `core.Tenant` (tenant-scoped, mandatory)
- `number` CharField (INTV-00001, unique per tenant — TenantNumbered pattern)
- `application` FK → `hrm.JobApplication` (the application this interview belongs to; CASCADE)
- `title` CharField(200) — e.g. "Technical Round 1", "HR Final"
- `round_number` PositiveSmallIntegerField (1-based; defines ordering within an application)
- `mode` CharField choices: `in_person` / `phone` / `video` / `one_way_video`
- `status` CharField choices: `scheduled` / `confirmed` / `in_progress` / `completed` / `cancelled` / `no_show` / `rescheduled`
- `scheduled_at` DateTimeField (UTC; display in tenant local time)
- `duration_minutes` PositiveSmallIntegerField (default 60)
- `location` CharField(255, blank=True) — room name or address for in-person
- `video_provider` CharField choices: `zoom` / `teams` / `meet` / `other` / `none`
- `meeting_url` URLField(blank=True) — the video conference link (manually entered; OAuth deferred)
- `calendar_event_id` CharField(255, blank=True) — placeholder for future calendar sync
- `candidate_self_schedule_url` URLField(blank=True) — Calendly/similar link for self-scheduling
- `interviewer_instructions` TextField(blank=True) — panel-wide briefing visible to all interviewers
- `scheduled_by` FK → `accounts.User` (SET_NULL, nullable)
- `reminder_sent_at` DateTimeField(null=True) — records when pre-interview reminder was dispatched
- `feedback_reminder_sent_at` DateTimeField(null=True) — records when post-interview feedback nudge was sent
- `notes` TextField(blank=True) — recruiter internal notes

Meta: `unique_together (tenant, number)`, index `(tenant, application)`, index `(tenant, status)`,
index `(tenant, scheduled_at)`.

List page: interview list per application (sub-list on application detail + standalone list with filters).
CRUD: create/edit/detail/delete.

### Model 2: `InterviewPanelist` [no number — child of Interview]
**The M2M through-table for panelist assignment** — one row per interviewer per interview.

Core fields justified by research:
- `tenant` FK → `core.Tenant`
- `interview` FK → `hrm.Interview` (CASCADE)
- `interviewer` FK → `accounts.User` (the panelist; SET_NULL → blank if user deleted)
- `role` CharField choices: `lead` / `interviewer` / `shadow` / `observer`
- `rsvp_status` CharField choices: `pending` / `accepted` / `declined`
- `briefing_notes` TextField(blank=True) — per-panelist prep instructions (Ashby briefing view pattern)
- `notified_at` DateTimeField(null=True) — when the assignment email was sent

Meta: `unique_together (interview, interviewer)` — no double-assignment per interview; index `(tenant, interview)`.

No standalone list page — managed as an inline on the `Interview` detail/form page.
Actions: assign panelist (POST), update RSVP (POST), remove panelist (POST).

### Model 3: `InterviewFeedback` [no standalone number — child of Interview + panelist]
**The structured scorecard / evaluation** — one submission per panelist per interview.

Core fields justified by research:
- `tenant` FK → `core.Tenant`
- `interview` FK → `hrm.Interview` (CASCADE)
- `panelist` FK → `hrm.InterviewPanelist` (CASCADE; links back to the assigned slot)
- `submitted_by` FK → `accounts.User` (denormalized for query convenience; SET_NULL)
- `overall_recommendation` CharField choices: `strong_no` / `no` / `maybe` / `yes` / `strong_yes`
  (maps to Greenhouse's "Definitely Not/No/Yes/Strong Yes" + Zoho's mid-tier "On Hold → maybe")
- `summary` TextField(blank=True) — free-text overall summary / key takeaways paragraph
- `is_submitted` BooleanField(default=False) — draft vs. formally submitted (enables feedback blinding)
- `submitted_at` DateTimeField(null=True)

Meta: `unique_together (interview, panelist)` — one feedback per panelist per interview; index `(tenant, interview)`.

List page: feedback list on Interview detail page (all panelists' submissions visible to recruiter/admin;
panelists see only their own until they submit — anti-anchoring logic in the view).
Actions: submit feedback form (GET/POST), view feedback summary on Interview detail.

### Model 4: `FeedbackCriterion` [no number — child of InterviewFeedback]
**A per-competency line on a scorecard** — N rows per feedback submission.

Core fields justified by research:
- `tenant` FK → `core.Tenant`
- `feedback` FK → `hrm.InterviewFeedback` (CASCADE)
- `criterion_name` CharField(150) — e.g. "Problem Solving", "Communication", "Culture Fit"
- `rating` PositiveSmallIntegerField(null=True) — 1 (poor) to 5 (excellent)
- `notes` TextField(blank=True) — free-text note for this criterion

Meta: `unique_together (feedback, criterion_name)`, index `(tenant, feedback)`.

No standalone list/form — created inline during feedback submission. The feedback form renders N criterion
rows (pre-populated from a configurable default set, or added ad-hoc by the interviewer).

---

## Email template types to add (extend existing CandidateEmailTemplate choices)

Two new `template_type` values should be added to the existing `EMAIL_TEMPLATE_TYPE_CHOICES`:
- `interview_invite` — "Interview Invitation" (for sending to candidates when interview is scheduled)
- `interview_reminder` — "Interview Reminder" (pre-interview reminder to candidate and/or interviewers)

The send-reminder action on the Interview detail page creates a `CandidateCommunication` record (as 3.6 does
for other stage emails), so no new communication model is needed.

---

## Deferred / future passes

- **Live calendar sync (Google Calendar / Outlook OAuth)** — requires OAuth2 flow, webhook-based event
  updates, two-way sync. Store `calendar_event_id` field now; implement later. (Seen: all products)
- **Zoom/Teams/Meet OAuth auto-link generation** — store `meeting_url` now, auto-generate via provider API
  later. Recruitee, BambooHR, Workable all do this. (Seen: Recruitee, BambooHR, Workable)
- **Candidate self-scheduling portal** — live slot picker backed by real calendar availability.
  Store `candidate_self_schedule_url` now for Calendly/external. (Seen: Greenhouse, Lever, Ashby, GoodTime)
- **SMS / WhatsApp reminders** — requires Twilio/WhatsApp Business API gateway. (Seen: GoodTime, Recruitee)
- **One-way / async video interviews** — candidates record answers to pre-set questions; requires video
  hosting (Spark Hire, HireVue embed). (Seen: Spark Hire, HireVue, Zoho, SmartRecruiters)
- **AI scorecard summarization** — LLM-powered summary of all panelist feedback. (Seen: Greenhouse, Ashby, Lever)
- **AI video scoring** — Spark Hire/HireVue score one-way video on communication, enthusiasm, etc. (Deferred)
- **Interviewer load balancing (AI)** — GoodTime-style AI-driven interviewer selection. (Deferred)
- **Interview kit / question bank templates** — re-usable sets of `FeedbackCriterion` names per job type,
  so scorecards are pre-populated consistently. Simple table; could be added in the same pass or next pass.
- **Scorecard editing window** — Greenhouse allows editing up to 30 days post-submission (admin-only).
  Keep `is_submitted` flag; add a time-window guard in a future pass.
- **Celery/async reminder dispatch** — `reminder_sent_at` and `feedback_reminder_sent_at` fields are built now;
  the actual Celery beat task that reads those fields and fires emails is a separate infrastructure pass.
