# Research — Module 3: HRM — 3.27 Communication Hub (hrm)

## Scope recap
NavERP.md 3.27 bullets: **Announcements** (company news/updates), **Birthday/Anniversary** (celebrations, wishes),
**Surveys** (employee engagement surveys), **Suggestions** (idea submission box), **Help Desk** (HR ticket system
— DEFERRED to the dedicated future 3.36 Helpdesk sub-module; not researched further here beyond noting the
deferral). Approved build scope (this research maps to it, does not re-propose a different shape):
`Announcement [ANN-]`, `Celebrations` (derived view, no model), `Survey [SUR-]` + `SurveyResponse`,
`Suggestion [SUG-]` (reuses the 3.26 employee-request workflow shape).

## Leaders surveyed (with source links)
1. **Workday Peakon Employee Voice** — enterprise continuous-listening/engagement-survey platform with AI-summarized
   feedback, bundled with Workday's core HCM (birthdays/anniversaries/holidays surfaced via Workday+Viva
   integration) — [Peakon overview](https://www.workday.com/en-us/products/employee-voice/overview.html), [Workday+Viva](https://blog.workday.com/en-us/workday-microsoft-viva-integration.html)
2. **BambooHR** — SMB HRIS with a "Celebrations" home-page widget (birthdays/anniversaries), manager pre-day
   reminder emails, confetti eCards, and an Announcements widget for time-sensitive company news —
   [Calendar/mobile app](https://help.bamboohr.com/s/article/540970), [Employee Birthday eCards](https://www.bamboohr.com/product-updates/employee-birthday-ecards), [5 Lesser Known Features](https://www.bamboohr.com/blog/5-lesser-known-bamboohr-features)
3. **Zoho Connect** (Zoho People's intranet companion) — announcements with schedule-in-advance, pin-to-top,
   mandatory-read tracking + reminders to non-readers, reactions/comments engagement analytics, multilingual
   translation — [Zoho Connect features](https://www.zoho.com/connect/features.html), [Feeds for employee communication](https://www.zoho.com/connect/feeds-for-employee-communication.html)
4. **Culture Amp** — engagement-survey specialist: confidential-not-anonymous "Engagement" surveys (personal
   links, aggregate-only reporting with a minimum group-size threshold) vs. fully anonymous "Inclusion" surveys;
   configurable eNPS question on an 11-point scale — [Engagement survey guide](https://support.cultureamp.com/en/articles/7048327-engagement-attributed-survey-guide-for-participants), [Inclusion survey FAQ](https://support.cultureamp.com/en/articles/7048328-inclusion-survey-participant-faqs)
5. **Workleap Officevibe** — SMB pulse-survey/engagement tool: short weekly pulse questions, eNPS with
   highlights/areas-for-improvement analysis, anonymous-by-default responses (written feedback only surfaced once
   a group hits a minimum-respondent threshold) — [Pulse survey features](https://workleap.com/features/pulse-survey/), [Understanding scores/reports](https://help.workleap.com/en/articles/10281693-understand-workleap-officevibe-scores-and-survey-reports)
6. **Keka HR** — Indian HRIS with an Announcements module (targeting/scheduling, mobile authoring, publish-now or
   schedule-later) plus a live company feed for praise/posts/celebrations — [Using Announcements](https://help.keka.com/hc/en-us/articles/39946767085329-Using-Announcements-to-Engage-Your-Employees), [Keka features (G2)](https://www.g2.com/products/keka/features)
7. **Darwinbox** — Indian/APAC HRIS "Engage"/VibeX module: automated birthday/anniversary/time-off broadcast
   announcements driven off existing people data, customizable pulse surveys + org-wide polls, integrated social
   recognition wall — [Employee Engagement Software](https://darwinbox.com/products/employee-engagement), [Engage: surveys & engagement index](https://darwinbox.com/en-us/products/engage)
8. **greytHR** — Indian SMB HRIS: "Upcoming Birthdays" home-page card + birthday/anniversary alert emails
   (configurable event handlers), an employee-controlled "Wish Me On" date-of-wishing override, a Bulletin Board
   for company-wide postings, and an "Engage" module for posts/polls/kudos — [Bulletin board](https://admin-help.greythr.com/admin/answers/123073447/), [Engage](https://admin-help.greythr.com/admin/answers/121562153/), [Birthday list](https://greythr.freshdesk.com/support/solutions/articles/1060000049127-how-can-admin-view-the-employees-birthday-list-)
9. **Staffbase** — enterprise internal-comms/intranet: editorial approval workflow, scheduling, audience
   targeting/segmentation, multi-language, and explicit **read receipts** on posts — [Simpplr vs Staffbase](https://www.softwareadvice.com/employee-communication-tools/simpplr-profile/vs/staffbase/), [Top internal announcement software](https://axerosolutions.com/insights/top-internal-announcement-software/)
10. **Simpplr** — enterprise employee-experience platform: personalized news feeds, announcement scheduling +
    categorization, campaign management (draft/schedule/target/track performance) — [Simpplr vs Staffbase](https://www.softwarereviews.com/categories/employee-communications/compare/staffbase-vs-simpplr), [Simpplr review](https://www.workvivo.com/internal-communications/simpplr-review/)
11. *(bonus, cited for suggestion-box specifics)* **SuggestionOx / Workhub / Qandle IdeaBox** — dedicated
    idea-management tools: category tags, anonymous submission, upvote/downvote, kanban-style status columns
    (submitted → under review → approved/rejected → implemented), two-way anonymous follow-up threads —
    [SuggestionOx](https://suggestionox.com/), [Workhub Suggestions](https://www.workhub.com/features/suggestions/), [Qandle IdeaBox](https://www.qandle.com/ideabox.html)
12. *(bonus, cited for eNPS/question-type specifics)* **Lattice** — Pulse + Engagement surveys: multiple-choice,
    Likert-scale, open-ended question types; eNPS on a 0–10 scale always asked first when included; comment
    follow-up on rating questions — [Pulse Survey Software](https://lattice.com/platform/engagement/pulse-surveys), [Measure eNPS in Pulse Surveys](https://help.lattice.com/hc/en-us/articles/360062072293-Measure-eNPS-in-Pulse-Surveys)
13. *(bonus, cited for HRIS-embedded birthday/anniversary precedent)* **SAP SuccessFactors Employee Central** —
    standard "Birthday and Work Anniversary" home-page tile, computed from Job Data (hire date) and Personal
    Info (birth date), surfaced N days ahead (no new table — pure derived read) —
    [Birthday/anniversary tile](https://help.sap.com/docs/successfactors-platform/managing-sap-successfactors-user-experience/enabling-birthday-and-work-anniversary-reminders-on-home-page)

*(≈10 primary leaders (1–10) plus 3 secondary sources (11–13) cited for specific feature detail not covered as
cleanly by the primary 10 — suggestion-box workflow, survey question-type taxonomy, and the derived-tile pattern.)*

## Feature catalog by build entity

### Announcement [ANN-]
- **Audience targeting (all / department / designation)** — restrict who sees a post · seen in: Staffbase,
  Simpplr, Keka, LearningPath 3.23 precedent (target_department/target_designation) · priority: table-stakes
  · spine: reuse `core.OrgUnit[kind=department]` + `hrm.Designation` (exactly the 3.23 LearningPath pattern —
  no new audience/group table) · buildable now
- **Pin to top of feed** — keep an important post above the normal reverse-chron order · seen in: Zoho Connect
  ("pin it up high"), Keka · priority: common · spine: new field `is_pinned` on Announcement · buildable now
- **Draft → Published → Archived lifecycle** — author drafts before it's visible; retire old posts without
  deleting · seen in: Staffbase (approval/editorial workflow), Simpplr (campaign draft/schedule/track) · priority:
  table-stakes · spine: new `status` field on Announcement (no separate workflow table needed — mirrors the
  simple `draft/pending/approved` shape used across 3.26) · buildable now
- **Schedule for future publish** — author now, goes live later · seen in: Zoho Connect, Keka ("publish now or
  schedule for later"), Simpplr, Staffbase (editorial calendars) · priority: common · spine: new field
  `publish_at`/`starts_at` · buildable now (a `published_at`-vs-`now()` check in the list view/queryset; no
  background scheduler needed for a first pass — can compute "live" as `status=published and (not expires_at or
  expires_at>=today)`)
- **Optional expiry date** — announcement auto-hides after a date (e.g. event has passed) · seen in: Simpplr
  (categorization/lifecycle), Staffbase (campaign end dates implied by editorial calendar) · priority: common
  · spine: new field `expires_at` · buildable now
- **Category / type tagging** (news, policy, event, hr-update, celebration) — organize the feed · seen in:
  Simpplr ("scheduling and categorization"), BambooHR (announcement widget mixes categories) · priority: common
  · spine: new `category` choice field · buildable now
- **Mandatory-read tracking + reminders to non-readers** — flag a post as must-read, track who has/hasn't opened
  it, nudge stragglers · seen in: Zoho Connect ("mark posts as mandatory... track who has read them, send
  reminders"), Staffbase (read receipts) · priority: differentiator · spine: would need a new join table
  (`AnnouncementRead`: announcement FK + employee FK + read_at) — **deferred**, out of scope for the 4-model pass
  (adds a 5th model + a reminder job)
- **Reactions / comments / engagement analytics** — likes, comment threads, view counts on a post · seen in:
  Zoho Connect ("comments, reactions, views"), Keka (praise/posts feed), Darwinbox (Vibe social feed) · priority:
  differentiator · spine: would need a generic reaction/comment table shared across the module (feels like a
  future 3.27-v2 "social" layer, not core comms) — **deferred**
  as-a-comms-secondary-object, not "the announcement itself" for a first pass
- **Multi-language / translation** — auto-translate posts for a distributed workforce · seen in: Zoho Connect
  · priority: differentiator · integration/later (needs a translation service)
- **Delivery channel (in-app / email / digital signage / mobile push)** — where the post is pushed · seen in:
  BambooHR (email alert), Staffbase (intranet + email + mobile app), Simpplr (personalized feed) · priority:
  common but **integration/later** — this pass ships in-app only; email/push notification fan-out is a later
  integration layer (reuses the existing notification/email infra from other modules, doesn't need new fields on
  Announcement beyond maybe a boolean `notify_by_email` toggle, which we defer to keep the model lean)
- **Author + published-by tracking** — who wrote/approved it · seen in: all editorial-workflow leaders (Staffbase,
  Simpplr) · priority: table-stakes · spine: reuse `settings.AUTH_USER_MODEL` (author is an HR/admin user, not
  necessarily an EmployeeProfile) — mirrors `DocumentRequest.approver` pattern · buildable now

### Celebrations (derived — NO model)
- **Upcoming birthdays list/widget** — "coming up this week" feed sourced from stored DOB · seen in: BambooHR
  ("Celebrations" widget/feed), greytHR ("Upcoming Birthdays" card), Darwinbox (automated birthday broadcast),
  SAP SuccessFactors (standard tile, 5-day lookahead) · priority: table-stakes · spine: **pure read** off
  `hrm.EmployeeProfile.date_of_birth` — no new table, confirms the approved derived-view shape · buildable now
- **Upcoming work-anniversary list/widget** — years-of-service milestones · seen in: BambooHR, greytHR, Darwinbox,
  SAP SuccessFactors (same tile covers both) · priority: table-stakes · spine: **pure read** off
  `core.Employment.hired_on` (computing tenure years = today.year - hired_on.year, adjusted) — no new table
  · buildable now
- **Manager pre-day reminder (T-1 notification)** — manager gets a heads-up the day before a direct report's
  birthday/anniversary · seen in: BambooHR (explicit T-1 manager email) · priority: common · integration/later
  (needs the email/notification dispatch layer — the *data* (DOB/hired_on) already supports computing "tomorrow's
  celebrations", so this is a scheduled-job concern layered on the derived view, not a new field)
  needed for the widget itself
- **Confetti / celebration eCard, kudos/wish posting** — a social "wish them well" action tied to the date ·
  seen in: BambooHR (birthday eCard), greytHR (Engage kudos/greetings), Darwinbox (Vibe recognition) · priority:
  differentiator · **out-of-scope** for this pass — recognition/kudos already exists elsewhere in HRM (3.19/3.20
  Kudos & Feedback per repo history: `KudosBadge`); Celebrations here is display-only, no new interaction model
- **Employee-controlled wish date** — employee can hide/adjust the date shown to colleagues (privacy) · seen in:
  greytHR ("Wish Me On") · priority: nice-to-have · spine: would reuse `EmployeeProfile` (a `show_birthday_publicly`
  boolean) — **deferred**; not required for a first derived-view pass, note as a possible future field on
  EmployeeProfile (not a new model)

### Survey [SUR-] + SurveyResponse
- **Question types: rating scale, single-choice, open text** — the three core question shapes · seen in: Lattice
  (multiple-choice/Likert/open-ended), Culture Amp (rating-scale factors), Officevibe (weekly rating questions)
  · priority: table-stakes · spine: new field `questions` (structured JSON list `[{type, text, choices?}]`) on
  Survey — matches the approved "questions as structured JSON" build scope exactly · buildable now
- **eNPS-style 0–10 recommend question** — a specific Net-Promoter-flavored rating question, tracked over time ·
  seen in: Lattice (0–10 scale, asked first), Culture Amp (11-point scale), Officevibe (0–10 "how likely to
  recommend") · priority: differentiator (a few standouts formalize it as a distinct metric; most others just
  treat it as one rating-type question in the JSON) · spine: no new field needed — it's simply a `rating` question
  in the JSON `questions` list with `min=0,max=10`; a later analytics pass can special-case it by question text/id
  · buildable now (as a question type, not a schema feature)
- **Draft → Open → Closed lifecycle** — author builds it, opens the response window, closes it · seen in: every
  survey leader (implicit in "response window"/"survey cycle" language — Officevibe "during this cycle", Culture
  Amp survey scheduling) · priority: table-stakes · spine: new `status` field on Survey · buildable now
- **Response window (open/close dates)** — scheduled start/end for accepting responses · seen in: Culture Amp,
  Officevibe (weekly pulse cadence), Darwinbox (org-wide polls "whenever needed") · priority: common · spine:
  new `opens_at`/`closes_at` fields on Survey · buildable now
- **One response per employee (respond-once)** — prevent duplicate submissions · seen in: implicit in every
  platform's per-user survey-link model (Culture Amp's "personal link", Officevibe's per-user pulse) · priority:
  table-stakes · spine: `unique_together` on `SurveyResponse(survey, employee)` — matches approved "employee
  responds once" build scope · buildable now
- **Optional anonymity** — responses collected without a visible identity, vs. confidential-but-attributed ·
  seen in: Culture Amp (distinguishes confidential-Engagement vs. fully-anonymous-Inclusion surveys), Officevibe
  (anonymous by default, written comments gated behind a minimum-respondent count) · priority: table-stakes ·
  spine: new `is_anonymous` boolean on Survey; `SurveyResponse.employee` FK is still stored (needed for the
  respond-once constraint and admin oversight) but the **results/report view suppresses the employee identity**
  when `is_anonymous=True` — this is a display-layer rule, not a schema difference (matches the approved "optional
  anonymous" scope without needing a nullable-employee hack) · buildable now
- **Minimum-group-size reporting threshold (k-anonymity)** — don't show aggregate breakdowns for groups smaller
  than N, to protect anonymity · seen in: Culture Amp (explicit reporting-minimum setting), Officevibe (5-response
  minimum before comments surface) · priority: differentiator · spine: could be a per-tenant setting or a
  hardcoded constant in the results view — **nice-to-have**, not required for a first pass since anonymity is
  already enforced at the identity-display layer
- **Results/analytics aggregation (per-question averages, response-rate, trend over survey cycles)** — the
  dashboard admins see after responses come in · seen in: all survey leaders (Culture Amp survey reporting,
  Officevibe scores/heatmap, Lattice eNPS trend) · priority: table-stakes · spine: computed at the view layer from
  `SurveyResponse.answers` JSON (aggregate rating averages, choice-frequency counts, text-answer list) — no new
  model, matches "results aggregated" in approved scope · buildable now
- **AI-summarized open-text feedback** — auto-summarize free-text comments · seen in: Workday Peakon (Illuminate
  AI summaries) · priority: differentiator · integration/later (external AI service)
- **Survey templates / pre-built question libraries** — reusable question sets (annual engagement, exit,
  pulse) · seen in: Culture Amp, Lattice (Pulse vs Engagement templates) · priority: common · **deferred** — the
  structured-JSON `questions` field already lets an admin copy/reuse a prior survey's JSON manually; a dedicated
  template model is over-scope for this pass

### Suggestion [SUG-]
- **Category tagging** (process improvement, cost saving, workplace, HR policy, other) — classify the idea ·
  seen in: Qandle IdeaBox, Workhub, SuggestionOx (category/theme grouping) · priority: table-stakes · spine: new
  `category` choice field on Suggestion · buildable now
- **Optional anonymous submission** — submit without revealing identity to reviewers · seen in: SuggestionOx,
  Workhub, EngageWith ("select whether workers can remain anonymous") · priority: common · spine: same
  display-layer pattern as Survey — `is_anonymous` boolean; `employee` FK still stored (needed since Suggestion
  reuses the 3.26 employee-request `TenantNumbered` shape, which is inherently employee-attributed for the
  workflow/notifications) and identity is suppressed in admin-facing list/detail when flagged · buildable now
- **Status workflow: draft → pending → approved(Accepted)/rejected/cancelled → implemented** — exactly the
  approved build-scope lifecycle · seen in: Qandle IdeaBox / Workhub ("pending, approved, implemented, declined"),
  mirrors NavERP's own 3.26 `DocumentRequest`/`IdCardRequest`/`AssetRequest` draft→pending→approved/rejected/
  cancelled→fulfilled shape (same `OPEN_STATUSES` pattern) · priority: table-stakes · spine: new `status` field
  + `OPEN_STATUSES = ("draft","pending")` constant, reusing the 3.26 `TenantNumbered` request pattern verbatim
  (reviewer = `AUTH_USER_MODEL` FK, `decision_note`, `decided_at`/`approved_at`) · buildable now
- **Reviewer decision note** — admin explains the accept/reject decision · seen in: implicit in every
  approve/reject workflow (DocumentRequest.decision_note precedent) · priority: table-stakes · spine: reuse the
  3.26 `decision_note` field name/shape · buildable now
- **Upvote / downvote or peer support count** — colleagues vote an idea up to signal support/prioritization ·
  seen in: SuggestionOx, EngageWith ("virtual suggestion box with anonymous voting"), Qandle IdeaBox · priority:
  differentiator · spine: would need a new `SuggestionVote` join table (suggestion FK + employee FK, unique
  together) — **deferred**, adds a 5th/6th model; note as a natural v2 extension once Suggestion ships
- **Two-way anonymous follow-up thread** — reviewer can ask a clarifying question and get an anonymous reply back
  · seen in: SuggestionOx ("two-way anonymous communication") · priority: differentiator · **deferred** — needs a
  comment/thread model; out of scope for a first pass (the single `decision_note` field covers the MVP
  reviewer-response case)
- **Recognition / reward on implementation** — the employee who suggested an implemented idea gets a kudos/points
  · seen in: Vantage Circle, Workhub · priority: nice-to-have · spine: could reuse HRM's existing `KudosBadge`/
  recognition model (from 3.19/3.20) when a Suggestion moves to `implemented` — **deferred**, a manual cross-link
  for now, not a new FK
- **Implementation outcome notes / linked initiative** — what actually happened after acceptance · seen in:
  Workhub (assign tasks, set deadlines, follow up) · priority: common · spine: new `implementation_note` text
  field + `implemented_at` timestamp on Suggestion (mirrors `DocumentRequest.fulfilled_at`/`output_file` tail-state
  pattern) · buildable now

### Help Desk — DEFERRED
Per the approved build scope, Help Desk (HR ticket system) is explicitly **out of scope** for 3.27 and reserved
for the dedicated future **3.36 Helpdesk** sub-module (Ticket Management, Ticket Categories, SLA Management,
Knowledge Base, Satisfaction Survey — confirmed present verbatim in NavERP.md 3.36). No further product research
was performed on full ticketing systems (Zendesk/Freshdesk-style) for this pass; only noted for the record.

## Recommended build scope (this pass — 4 models, matching the approved shape)

- **Announcement [ANN-]** (`TenantNumbered`) — fields justified by the catalog above:
  `title`, `body` (rich text/markdown-capable TextField), `category` (choice: news/policy/event/hr_update/
  celebration/other), `audience_scope` (choice: all/department/designation — Zoho Connect/Staffbase targeting),
  `audience_department` (FK `core.OrgUnit`, `limit_choices_to={"kind":"department"}`, null/blank — LearningPath
  3.23 precedent), `audience_designation` (FK `hrm.Designation`, null/blank — same precedent), `status` (choice:
  draft/published/archived — Staffbase/Simpplr editorial lifecycle), `is_pinned` (bool — Zoho Connect/Keka pin),
  `publish_at` (DateTimeField, when it goes/went live — Keka/Zoho Connect/Staffbase scheduling), `expires_at`
  (DateTimeField, null/blank — Simpplr categorization/lifecycle), `author` (FK `AUTH_USER_MODEL` — editorial
  ownership, mirrors `DocumentRequest.approver` FK shape). No new audience/group table — reuses `core.OrgUnit` +
  `hrm.Designation` exactly like LearningPath.

- **Survey [SUR-]** (`TenantNumbered`) — fields: `title`, `description`, `questions` (JSONField, structured list
  of `{type: rating|text|single_choice, text, choices?}` — Lattice/Culture Amp/Officevibe question-type coverage,
  matches approved scope verbatim), `status` (choice: draft/open/closed), `opens_at`/`closes_at` (DateTimeField,
  null/blank — Culture Amp/Officevibe response-window pattern), `is_anonymous` (bool — Culture Amp Inclusion-vs-
  Engagement / Officevibe anonymous-by-default pattern), `created_by` (FK `AUTH_USER_MODEL`).

- **SurveyResponse** (`TenantOwned`, child of Survey) — fields: `survey` (FK, CASCADE), `employee` (FK
  `hrm.EmployeeProfile`, CASCADE — respond-once via `unique_together=("survey","employee")`), `answers` (JSONField,
  `{question_index: answer}` map mirroring `questions` shape), `submitted_at` (auto_now_add). Identity is stored
  for the respond-once constraint and admin oversight but **suppressed in the results/report display** when
  `survey.is_anonymous=True` (display-layer rule, no separate anonymous/non-anonymous schema).

- **Suggestion [SUG-]** (`TenantNumbered`, reusing the 3.26 employee-request shape verbatim) — fields:
  `employee` (FK `hrm.EmployeeProfile`, CASCADE), `category` (choice: process_improvement/cost_saving/workplace/
  hr_policy/other — IdeaBox/Workhub/SuggestionOx category pattern), `title`, `description`, `is_anonymous` (bool
  — display-layer suppression like Survey), `status` (choice: draft/pending/approved/rejected/cancelled/
  implemented; `OPEN_STATUSES = ("draft","pending")` — exact 3.26 `DocumentRequest`/`AssetRequest` lifecycle
  precedent), `reviewer` (FK `AUTH_USER_MODEL`, SET_NULL, null/blank — mirrors `DocumentRequest.approver`),
  `decision_note` (TextField, blank — mirrors `DocumentRequest.decision_note`), `decided_at` (DateTimeField, null/
  blank), `implementation_note` (TextField, blank — Workhub "assign tasks, follow up" outcome tracking),
  `implemented_at` (DateTimeField, null/blank, editable=False — mirrors `DocumentRequest.fulfilled_at` tail-state
  pattern, set only by the audited "mark implemented" action).

- **Celebrations** — NOT a model. A view-only page (mirrors the existing 3.26 "My Requests" hub — view-only,
  links out, no table) that queries: upcoming birthdays via
  `EmployeeProfile.objects.filter(tenant=..., date_of_birth__month=..., date_of_birth__day__gte=...)` (or a
  month/day window comparison for "next N days" across year boundaries) and upcoming anniversaries via
  `core.Employment.hired_on` month/day comparison joined through `EmployeeProfile`. No new table — confirmed by
  every leader surveyed (BambooHR, greytHR, Darwinbox, SAP SuccessFactors all compute this as a derived
  tile/widget off existing HR data, never a stored "celebration" record).

## Deferred (later passes / integrations)

- **Announcement read receipts / mandatory-read tracking + reminder nudges** (Zoho Connect, Staffbase) — needs a
  new `AnnouncementRead` join table + a reminder job; a 5th model, out of scope for this pass.
- **Announcement reactions/comments/view-count social layer** (Zoho Connect, Keka, Darwinbox Vibe) — a
  generic engagement layer better suited to a future cross-module "social" pass, not core comms.
- **Multi-language/auto-translate announcements** (Zoho Connect) — external translation service integration.
- **Email/push/digital-signage delivery fan-out for announcements** (BambooHR email alerts, Staffbase multi-
  channel) — reuses existing notification infra later; ships in-app-only this pass.
- **Manager T-1 celebration reminder emails** (BambooHR) — a scheduled-job/notification concern layered on the
  derived Celebrations view; the underlying data (DOB/hired_on) already supports it.
- **Employee-controlled "wish me on" privacy toggle** (greytHR) — a possible future `EmployeeProfile` field, not
  needed for the first derived-view pass.
- **Birthday/anniversary eCards, kudos/wish posting tied to celebrations** (BambooHR, greytHR, Darwinbox) —
  NavERP already has a Kudos/recognition model elsewhere in HRM (3.19/3.20); Celebrations here stays display-only.
- **Survey minimum-group-size (k-anonymity) reporting threshold** (Culture Amp, Officevibe) — nice-to-have
  refinement on top of the already-enforced identity-suppression rule.
- **AI-summarized open-text survey feedback** (Workday Peakon Illuminate) — external AI service integration.
- **Survey question templates / reusable libraries** (Culture Amp, Lattice) — the structured JSON `questions`
  field already supports manual reuse; a dedicated template model is over-scope.
- **Suggestion upvote/downvote and peer-support counts** (SuggestionOx, EngageWith, Qandle) — needs a new
  `SuggestionVote` join table; natural v2 extension.
- **Suggestion two-way anonymous follow-up threads** (SuggestionOx) — needs a comment/thread model.
- **Suggestion-to-recognition auto-link on implementation** (Vantage Circle, Workhub) — could reuse the existing
  Kudos model later via a manual cross-reference; not a new FK this pass.
- **Help Desk (HR ticket system)** — fully deferred to the future dedicated **3.36 Helpdesk** sub-module (Ticket
  Management, Categories, SLA, Knowledge Base, Satisfaction Survey) per NavERP.md; not designed here.
