# Research — Module 3: Human Resource Management (HRM) — Sub-module 3.22 Training Management (hrm)

Scope note: this file researches **only** NavERP.md `3.22 Training Management`, i.e. the **Training Calendar /
Training Catalog / Classroom Training / Virtual Training / External Training** bullets. It deliberately excludes
LMS content-authoring/learning-paths/assessments/gamification/progress-tracking (owned by sibling `3.23 Learning
Management (LMS)`) and nomination/attendance/feedback/certificates/budget (owned by sibling `3.24 Training
Administration`) — those are called out under Deferred so the boundary is explicit.

## Leaders surveyed (with source links)
1. **SAP SuccessFactors Learning** — enterprise LMS with a dedicated Instructor-Led Training "Planner" for
   scheduling classes across locations/instructors — [SuccessFactors LMS overview](https://skillnation.in/posts/successfactors-learning-management/), [Process Attendance and Record Instructor-led Learning](https://help.sap.com/docs/SAP_Best_Practices/428168c77cf74b33bf8484b736150793/cfa3e4acd149402abeb1664572d6b56a.html), [SuccessFactors Learning User Help](https://help.sap.com/doc/00e5cdaba7f146f3bf046ea34a15a37a/2411/en-US/UserHelp_en-US.pdf)
2. **Cornerstone OnDemand** — talent/learning suite with ILT + vILT scheduling and a distinct Vendors/Instructors
   register — [Instructor Led Training (ILT) Quick Help](https://cornerstoneondemand.my.site.com/s/articles/Instructor-Led-Training-ILT-Quick-Help-Knowledge-Articles), [Instructors – Add](https://help.csod.com/help/csod_0/Content/ILT/Vendors_and_Instructors/Instructors_-_Add.htm)
3. **TalentLMS** — SMB-friendly LMS; simple ILT unit creation (choose webinar vs. classroom) and a personal
   training calendar with a live "Join" button — [TalentLMS Calendar](https://help.talentlms.com/hc/en-us/articles/15303959778460-How-to-work-with-the-TalentLMS-Calendar), [Create an ILT unit](https://help.talentlms.com/hc/en-us/articles/9651360955676-How-to-create-an-Instructor-Led-Training-ILT-unit)
4. **Docebo** — enterprise LMS with a Course → Session → Event ILT/VILT hierarchy and multi-vendor video
   conferencing integration (Zoom, Webex, Teams, GoToMeeting) — [Creating and managing ILT sessions](https://help.docebo.com/hc/en-us/articles/360020124099-Creating-and-Managing-ILT-and-VILT-Sessions), [Virtual Instructor-Led Training (VILT)](https://www.docebo.com/learning-network/blog/virtual-instructor-led-training/)
5. **Absorb LMS** — LMS with explicit venue/room capacity management, instructor/venue double-booking conflict
   detection, and separate external (customer/partner) training audiences — [Instructor-led training](https://www.absorblms.com/blog/instructor-led-training), [How to Create an Instructor Led Course (ILC)](https://support.absorblms.com/hc/en-us/articles/4552337175699-How-to-Create-an-Instructor-Led-Course-ILC)
6. **SAP Litmos** — mid-market LMS combining ILT + vILT scheduling in one workflow with manual location/instructor
   entry and Zoom/Webex/Teams integration — [Litmos platform](https://www.litmos.com/platform/enterprise-learning-management-system), [LMS Review: SAP Litmos](https://talentedlearning.com/lms-review-litmos-pro/)
7. **Training Orchestra** — a dedicated Training Management System (TMS, not an LMS) purpose-built for
   scheduling, resourcing, instructor/venue planning, and **budget/cost tracking** of ILT programs — [Training Management System](https://trainingorchestra.com/training-management-system/), [Budget and Cost Tracking](https://trainingorchestra.com/training-management-system/budget-and-cost-tracking/)
8. **Arlo** — dedicated training-management/course-scheduling software for training providers: venue booking,
   instructor/presenter availability, public course catalog, invoicing — [Training Course Scheduling System](https://www.arlo.co/features/training-course-scheduling-system), [Instructor-Led Training Management Software](https://www.arlo.co/use-cases/instructor-led-training-management-software)
9. **Zoho People (LMS)** — HRIS-embedded learning module with blended (classroom + virtual via Zoho Meeting)
   sessions, trainer/course feedback, and trainer role configuration — [Zoho People LMS](https://www.zoho.com/people/learning-management-system.html), [Zoho People LMS admin guide](https://www.zoho.com/people/help/adminguide/lms.html)
10. **360Learning** — collaborative LMS with live-training session management: one-click session creation,
    auto-generated webinar links, room booking/capacity, and hybrid (in-person + online) sessions — [Live/instructor-led training](https://360learning.com/solution/live-training/), [Hybrid Learning](https://360learning.com/solution/hybrid-learning/)

## Feature catalog — grouped by the 5 NavERP.md 3.22 bullets

### Training Calendar
- **Personal/shared upcoming-sessions calendar** — every user sees the ILT/vILT sessions they're registered for
  or can register for in one calendar view · seen in: TalentLMS, SAP SuccessFactors Learning · priority:
  table-stakes · spine: no new table — a date-filtered query view over the new `TrainingSession` model · buildable
  now
- **One-click join from the calendar entry** — a "Join" action appears on the calendar item and becomes active a
  short window before the session starts, linking straight to the meeting · seen in: TalentLMS · priority:
  differentiator · spine: reuses `TrainingSession.meeting_link` · buildable now (link + simple date-math gating;
  no live meeting-platform API call)
- **Session reminders/notifications** — automated emails at registration and again N hours/days before the
  session starts · seen in: SAP SuccessFactors Learning, TalentLMS, 360Learning, SAP Litmos · priority:
  table-stakes · spine: reuses `TrainingSession` dates, no new table · integration/later (needs an email/notify
  pipeline; data model supports it now)
- **Instructor/venue double-booking conflict detection** — warns the admin if the same instructor or room is
  already booked for an overlapping time slot · seen in: Absorb LMS · priority: differentiator · spine: reuse
  `TrainingSession` (overlap check on `instructor_employee`/`venue_name` in `clean()`) · buildable now
- **Public/embeddable course & event calendar widget** — an externally-facing calendar for a training provider's
  own website · seen in: Arlo · priority: differentiator · spine: n/a · integration/later (not applicable — NavERP
  is an internal ERP, no public storefront for this pass)

### Training Catalog
- **Browsable/searchable course catalog** — the master list of courses employees can be scheduled/nominated into
  · seen in: TalentLMS, Arlo, Zoho People · priority: table-stakes · spine: new table `TrainingCourse` · buildable
  now
- **Course categories for catalog filtering** — courses tagged by type (technical, compliance, leadership, …) so
  the catalog can be filtered · seen in: TalentLMS, Arlo (custom catalog filters) · priority: common · spine:
  `TrainingCourse.category` (choices) · buildable now
- **Certifications tied to a course** — a catalog entry can represent (or grant) a certification with a name and
  validity period · seen in: SAP SuccessFactors Learning, Workday (certification program) · priority: common ·
  spine: `TrainingCourse.is_certification` / `certification_name` / `certification_validity_months` · buildable
  now
- **Prerequisites & seat limits** — a course can require completion of a prior course and cap enrollment · seen
  in: SAP SuccessFactors Learning · priority: common · spine: `TrainingCourse.prerequisite_course` (self-FK,
  nullable) + `TrainingSession.capacity` · buildable now
- **Waitlist when a session is full** — learners can join a waitlist and are promoted as seats open up · seen in:
  SAP SuccessFactors Learning, Absorb LMS · priority: common · spine: reuses `TrainingSession.capacity`; the
  waitlist *queue* itself is a 3.24 Nomination concern · flag field buildable now, workflow deferred to 3.24
- **Internal vs. external course distinction in the catalog** — the catalog marks whether a course is run
  in-house or sourced from an external provider · seen in: Absorb LMS, Training Orchestra · priority: common ·
  spine: `TrainingCourse.provider_type` (choices) · buildable now

### Classroom Training
- **Session = a scheduled occurrence of a course** (course → session → event hierarchy) with its own date, room,
  instructor, capacity · seen in: Docebo, SAP SuccessFactors Learning · priority: table-stakes · spine: new table
  `TrainingSession` (FK `TrainingCourse`) · buildable now
- **Venue/room management with seating capacity** — record where a session runs and its max occupancy · seen in:
  Absorb LMS, Arlo · priority: table-stakes · spine: fields on `TrainingSession` (`venue_name`, `venue_address`,
  `capacity`) — no separate Venue master this pass · buildable now
- **Instructor assignment (with availability check)** — a session has one responsible instructor, and the system
  flags if they're double-booked · seen in: Cornerstone OnDemand, Arlo · priority: table-stakes · spine: reuse
  `hrm.EmployeeProfile` (internal instructor FK) · buildable now
- **Instructor tied to an approved vendor/provider** — instructors can be scoped to (only selectable under) the
  vendor they belong to · seen in: Cornerstone OnDemand · priority: common · spine: reuse `core.Party` (vendor
  role) via `TrainingSession.external_vendor` · buildable now
- **Walk-in registration on the day of class** — instructors can add attendees who show up without prior
  registration · seen in: SAP SuccessFactors Learning · priority: differentiator · spine: this is attendance
  capture — belongs to 3.24 Attendance Tracking · deferred to 3.24

### Virtual Training
- **Choose classroom vs. webinar per session** — the same ILT construct can be delivered in person or online ·
  seen in: TalentLMS, Docebo (VILT) · priority: table-stakes · spine: `TrainingSession.delivery_mode` (choices) ·
  buildable now
- **Videoconferencing platform + join-link fields** — a session stores which platform (Zoom/Teams/Webex/
  GoToMeeting/Google Meet) and the meeting link/ID · seen in: Docebo, SAP Litmos, 360Learning, Zoho People (Zoho
  Meeting) · priority: table-stakes · spine: `TrainingSession.meeting_platform` / `meeting_link` / `meeting_id` ·
  buildable now for the data fields; live API auto-provisioning is integration/later
- **Auto-generated webinar link on session creation** — the platform calls the conferencing tool's API to mint a
  join link automatically instead of pasting one in · seen in: 360Learning · priority: differentiator · spine:
  n/a · integration/later (requires Zoom/Teams/Webex API credentials per tenant)
- **Hybrid/blended sessions** — one session offered simultaneously in-person and online · seen in: 360Learning ·
  priority: differentiator · spine: reuse `TrainingSession` (`delivery_mode="blended"`) · buildable now (flag
  only — no dual-room seat-allocation logic this pass)
- **Digital attendance/e-signature captured through the conferencing tool** — self check-in synced from the
  webinar platform · seen in: 360Learning · priority: common · spine: this is attendance capture — belongs to
  3.24 Attendance Tracking · deferred to 3.24

### External Training
- **Vendor/provider register** — a maintained list of approved external training companies · seen in: Training
  Orchestra, Cornerstone OnDemand, Absorb LMS · priority: table-stakes · spine: **reuse `core.Party`
  (`PartyRole.role="vendor"`) — do not create a new HRM vendor-master table.** `accounting.VendorProfile` already
  exists as the AP-side 1:1 extension of `core.Party` for vendors; 3.22 should reference `core.Party` directly
  (optionally cross-referencing `accounting.VendorProfile` later if AP billing is wired up) rather than duplicate
  it · buildable now
- **Per-session cost tracking (estimated vs. actual)** — capture planned and actual spend for a given external
  session · seen in: Training Orchestra, Arlo (invoicing) · priority: table-stakes · spine: new fields on
  `TrainingSession` (`estimated_cost`, `actual_cost`, `currency` FK) reusing `accounting.Currency` · buildable now
- **Multi-currency, multi-site cost tracking** — costs recorded in local currency across training locations ·
  seen in: Training Orchestra · priority: differentiator · spine: reuse `accounting.Currency` FK · buildable now
  (field only; FX-normalized rollup reporting is later)
- **Cost-vs-performance / ROI reporting** — combines budget data with training outcomes/feedback to justify spend
  · seen in: Training Orchestra · priority: differentiator · spine: needs 3.24's Training Budget + Training
  Feedback data · deferred to 3.24
- **External learner/partner portal with its own billing** — a separate branded space for customer/partner
  (non-employee) training · seen in: Absorb LMS · priority: differentiator · spine: n/a — this is B2B customer
  education, not employee L&D · out of scope for NavERP's internal HRM module

## Recommended build scope (this pass — 2 models)

Two models fully cover all five 3.22 bullets while reusing the core spine for every party-like or money-like
concept (no new vendor/currency masters):

- **`TrainingCourse`** `[TRC-]` — the catalog (Training Catalog bullet).
  - `title`, `description`
  - `category` — choices: `technical`, `compliance`, `leadership`, `soft_skills`, `safety`, `onboarding`,
    `product`, `other` (justified by: browsable/filterable catalog — TalentLMS, Arlo)
  - `delivery_mode` — choices: `classroom`, `virtual`, `external`, `blended` (default/typical mode; the actual
    per-occurrence mode lives on `TrainingSession`) (justified by: classroom/webinar choice — TalentLMS, Docebo)
  - `provider_type` — choices: `internal`, `external` (justified by: internal vs. external catalog split — Absorb
    LMS, Training Orchestra)
  - `duration_hours` (decimal)
  - `is_certification` (bool), `certification_name`, `certification_validity_months` (justified by: certifications
    tied to courses — SAP SuccessFactors Learning, Workday)
  - `prerequisite_course` — self-FK, nullable (justified by: prerequisites — SAP SuccessFactors Learning)
  - `default_capacity` (int, optional — seeds new sessions) (justified by: enrollment limits — SAP SuccessFactors
    Learning)
  - `is_active` (bool)
  - Reuses: nothing external besides tenant scoping — this is a new HRM-owned master, analogous to how other
    modules own their own catalog/price-list tables.

- **`TrainingSession`** `[TRS-]` — the schedule/occurrence (Training Calendar + Classroom + Virtual + External
  bullets, unified via `delivery_mode`).
  - `course` — FK `TrainingCourse`
  - `delivery_mode` — choices: `classroom`, `virtual`, `external` (per-occurrence; can differ from the course's
    default) (justified by: course→session→event hierarchy — Docebo, SAP SuccessFactors Learning)
  - `status` — choices: `scheduled`, `confirmed`, `ongoing`, `completed`, `cancelled`, `postponed`
  - `start_datetime`, `end_datetime`, `timezone` (char)
  - `capacity` (int), `waitlist_enabled` (bool) (justified by: seat limits/waitlist — SAP SuccessFactors Learning,
    Absorb LMS)
  - Classroom fields: `venue_name`, `venue_address` (justified by: venue/room management — Absorb LMS, Arlo)
  - Virtual fields: `meeting_platform` (choices: `zoom`, `teams`, `webex`, `google_meet`, `gotomeeting`, `other`),
    `meeting_link` (URL), `meeting_id` (char) (justified by: videoconferencing integration — Docebo, SAP Litmos,
    360Learning, Zoho People)
  - Instructor: `instructor_employee` — FK `hrm.EmployeeProfile`, null/blank (internal trainer) (justified by:
    instructor assignment — Cornerstone OnDemand, Arlo); `external_instructor_name` (char, for a named
    vendor-side trainer who isn't an `EmployeeProfile`)
  - External/vendor: `external_vendor` — FK `core.Party`, null/blank, conceptually scoped to vendor-role parties
    (justified by: vendor register + vendor-linked instructors — Training Orchestra, Cornerstone OnDemand)
  - Cost: `estimated_cost`, `actual_cost` (decimal), `currency` — FK `accounting.Currency`, null/blank,
    `invoice_reference` (char) (justified by: per-session cost tracking, multi-currency — Training Orchestra,
    Arlo)
  - `notes` (text)
  - `clean()` guards (mirrors the existing HRM `clean()` convention): `end_datetime > start_datetime`; classroom
    sessions require `venue_name`; virtual sessions require `meeting_link`; external sessions require
    `external_vendor` or `external_instructor_name`; overlap check rejects a second session with the same
    `instructor_employee` (or same `venue_name`) in a conflicting time window (justified by: double-booking
    conflict detection — Absorb LMS).
  - Reuses: `hrm.EmployeeProfile` (instructor), `core.Party` (external vendor — no new vendor table), `accounting.
    Currency` (cost currency).

Both models are `TenantNumbered` (mirrors every other HRM entity) and give the `todo` agent everything needed to
build: a catalog list/CRUD, a session list/CRUD with classroom/virtual/external conditional fields, and a
calendar view that's just a filtered/sorted query over `TrainingSession.start_datetime`.

## Deferred (later passes / integrations)

- **3.23 Learning Management (LMS)** — Course Content (videos/documents/SCORM packages), Learning Paths
  (role-based journeys), Assessments (quizzes/tests), Gamification (badges/points/leaderboards), Progress
  Tracking (% completion/time spent). This is the *content and self-paced delivery* layer that sits on top of
  `TrainingCourse` — sibling sub-module, own pass.
- **3.24 Training Administration** — Nomination (employee nomination/approval workflow), Attendance Tracking
  (per-session per-employee attendance/completion — including "walk-in" and "e-signature check-in" noted above),
  Training Feedback (post-training evaluation forms), Certificates (auto-generated completion certificates),
  Training Budget (aggregate budget allocation & utilization reporting, which consumes the
  `estimated_cost`/`actual_cost` data captured on `TrainingSession` here). Sibling sub-module, own pass.
- **Dedicated Venue/Room master** — a first-class `TrainingVenue` model with capacity, amenities, and
  cross-session double-booking calendar (Absorb LMS, Arlo pattern) — deferred; `venue_name`/`venue_address` text
  fields + the `clean()` overlap guard cover v1 needs without a new table. Revisit if multi-room facility
  management becomes a recurring need (could align with Module 11 Asset/Facility management).
- **Multi-instructor / co-instructor per session** — Cornerstone OnDemand and Docebo support assigning a crew of
  instructors; deferred — a single `instructor_employee` is sufficient for v1.
- **Live videoconferencing API integration** (Zoom/Teams/Webex auto-provisioning of meeting links, attendee sync,
  webhook-driven attendance) — integration/later; this pass stores the platform/link as plain data entered by the
  session organizer, no live API calls.
- **Notification/reminder delivery pipeline** (registration confirmations, "N hours before" reminders) —
  integration/later; the data model (`start_datetime`) supports it, but the email/scheduling worker is a
  cross-module concern.
- **Formal vendor scorecard / accreditation extension** — Training Orchestra-style vendor performance tracking;
  deferred. If needed later, extend via a thin `TenantOwned` 1:1 profile on `core.Party` (mirroring
  `accounting.VendorProfile`) rather than a duplicate vendor table.
- **Public/embeddable course catalog & external learner portal with billing** (Arlo, Absorb LMS) — out of scope;
  NavERP 3.22 is an internal employee-training tool, not a training-provider storefront.
- **Cost-vs-performance / ROI reporting** — needs 3.24's Training Budget + Training Feedback data joined with the
  cost fields captured here; deferred to 3.24.
