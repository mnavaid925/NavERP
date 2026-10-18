# Research — Sub-module 8.9: Sales Enablement (Module 8 — Sales Management System, `apps/sales`)

> Phase 1 output. Target: **8.9 Sales Enablement**. NavERP.md 8.9 = the five feature bullets reproduced verbatim in §2. All five are addressed.
> This research grounds 8.9 against verified as-built code in `apps/sales`, `apps/crm`, `apps/core`, and `apps/hrm`, and synthesizes specialized capabilities from 10 commercial market leaders.

---

## 1. Repo state checked first

### 1.1 Sibling sub-modules built so far in Module 8 (`apps/sales`)
Verification via `apps/core/navigation.py` `LIVE_LINKS` and model packages:
- **8.1 Lead Management** (`LIVE_LINKS["8.1"]`): `LeadScoreEvent`, `LeadQualification`, `LeadRoutingRule`, `LeadNurtureEnrollment`.
- **8.2 Opportunity & Pipeline Management** (`LIVE_LINKS["8.2"]`):
  * `Pipeline` (`PIPE-`), `PipelineStage` (with `entry_guidance`, `exit_guidance`, `stage_kind`, `crm_stage_key`).
  * `OpportunityPipelinePlacement`, `OpportunityTeamMember`.
  * **`CompetitorProfile` (`CMP-`)** in `apps/sales/models/CompetitiveIntelligence/CompetitiveIntelligence.py`: owns `party` (OneToOne to `core.Party`, organization), `aliases`, `website_url`, `description`, `market_positioning`, `strengths`, `weaknesses`, `differentiators`, `objection_handling`, `last_reviewed_on`, `is_active`.
  * `OpportunityCompetitor`: links `crm.Opportunity` to `CompetitorProfile` with deal relationship and positioning notes.
  * **`WinLossReason` (`WLR-`)** and **`OpportunityOutcome` (`OUT-`)** in `apps/sales/models/OpportunityOutcomes/OpportunityOutcomes.py`: stores append-only outcome tracking, reason codes, and competitor links.
- **8.3 Contact & Account Management** (`LIVE_LINKS["8.3"]`): `AccountClassification`, `AccountPlan` (`ACPL-`), `AccountStakeholder`, `PartyEnrichmentEvent`.
- **8.4 Sales Forecasting** (`LIVE_LINKS["8.4"]`): `ForecastPeriod` (`FCP-`), `ForecastSubmission` (`FCS-`), `ForecastAdjustment` (`FAD-`), `ForecastScenario` (`FSC-`).
- **8.5 Quote & Proposal Management (CPQ)** (`LIVE_LINKS["8.5"]`): `CPQQuote` (`CPQ-`), `CPQQuoteLine`, `ProductBundleOption` (`BND-`), `QuoteApprovalRule` (`QAR-`).
- **8.6 Order Management** (`LIVE_LINKS["8.6"]`): Commercial layer extending `scm.SalesOrder` (`SO-`) via `OrderValidationRule` (`OVR-`), `OrderHold` (`OHD-`), `OrderAmendment` (`AMD-`), `RevenueSchedule` (`RVS-`), `PerformanceObligation`.
- **8.7 Territory & Quota Management** (`LIVE_LINKS["8.7"]`): Extends `crm.Territory` (`TER-`) and `crm.SalesQuota` via `TerritoryRule` (`TRG-`), `AccountTerritoryAssignment` (`TAS-`), `TerritoryMember` (`TMB-`), `QuotaPlan` (`QPA-`).
- **8.8 Sales Activity & Task Management** (`LIVE_LINKS["8.8"]`): Extends CRM 1.5 activity stack via `ActivityType` (`ATY-`), `ActivityLog` (`SAL-`, 1:1 required FK to `crm.CommunicationLog`), `TaskTemplate` (`TTPL-`) + `TaskTemplateStep`, `SalesPlanCycle` (`SPC-`) + `ActivityGoal`.
- **8.9 Sales Enablement**: Next unbuilt sub-module (no entry in `LIVE_LINKS`, next migration is `0017`).

### 1.2 Core and Sibling models available to FK (verified via codebase grep)
- **`apps/sales`**:
  * `sales.CompetitorProfile` (`apps/sales/models/CompetitiveIntelligence/CompetitiveIntelligence.py`) — **CRITICAL RULING: 8.9 must EXTEND or coordinate with 8.2's existing `CompetitorProfile`, NOT re-declare it!**
  * `sales.OpportunityCompetitor` — deal-level competitive attachment.
  * `sales.WinLossReason` & `sales.OpportunityOutcome` — closed deal win/loss reasons.
  * `sales.Pipeline` & `sales.PipelineStage` — stage-based guidance links.
  * `sales.ActivityLog` (`SAL-`) — 8.8 sales activity attribution layer.
- **`apps/crm`**:
  * `crm.CommunicationLog` (`COM-`) (`apps/crm/models/ActivityManagement/CommunicationLogs.py`) — unified customer interaction record (`channel`, `duration_seconds`, `outcome`, `occurred_at`, `related_opportunity`, `party`, `owner`).
  * `crm.Opportunity` (`OPP-`) (`apps/crm/models/SalesForceAutomation/Opportunities.py`) — opportunity master.
- **`apps/core`**:
  * `core.Document` (`apps/core/models/Document.py`) — generic attachment with `file`, `name`, `classification`, `version`, `uploaded_at`.
  * `core.Party` (`apps/core/models/Party.py`) — customer and competitor organizations (`kind="organization"`).
  * `core.Tenant` — multi-tenant scoping.
- **`apps/accounts`**:
  * `accounts.User` (`settings.AUTH_USER_MODEL`) — reps, managers, coaches, content authors.
- **`apps/hrm`**:
  * `hrm.TrainingCourse` (`apps/hrm/models/TrainingManagement/Trainingcourse.py`) — optional link for enterprise LMS cross-referencing.

### 1.3 Auto-Number Prefixes Swept & Confirmed Free
Checked against all models across `apps/*/models/`:
- **`ECN`** (Enablement Content): **FREE** (avoided `ENC`, which is used by `hrm.LeaveManagement.Encashment`).
- **`SPB`** (Sales Playbook): **FREE**.
- **`SCTF`** (Sales Certification): **FREE** (avoided `SCR`, which is used by `scm.SupplierScorecards`; avoided `CERT`, which is used by `hrm.TrainingCertificate`).
- **`CSC`** (Coaching Scorecard): **FREE**.

---

## 2. The five NavERP.md 8.9 bullets, verbatim

1. **Content Repository & Search** — Battle cards, case studies, pitch decks, and product sheets with AI-powered search.
2. **Sales Playbooks & Guidance** — Step-by-step selling guidance, stage talk tracks, and objection handling scripts.
3. **Training & Certification Tracking** — Onboarding curricula, product certification, and compliance training records.
4. **Coaching & Call Recording** — Conversation intelligence, call transcription metadata/reviews, and manager coaching scorecards.
5. **Competitive Intelligence Library** — Competitor profiles, SWOT analyses, win/loss reports, and market positioning guides.

### Bullet-by-bullet verdict & boundary ruling

| Bullet | Already owned / built? | What 8.9 adds | Architectural Ruling |
|---|---|---|---|
| **1. Content Repository & Search** | `core.Document` owns file binary storage. DMS (Module 13) owns enterprise archives. | `EnablementContent` (`ECN-`) — sales collateral metadata, categorization, stage/persona targeting, external cloud URLs, tags, search indexing, and client-facing flags. | Reuses `core.Document` for file payloads. Does NOT re-declare a generic file storage engine. |
| **2. Sales Playbooks & Guidance** | `PipelineStage` in 8.2 has light `entry_guidance`/`exit_guidance`. | `SalesPlaybook` (`SPB-`) — comprehensive guided selling playbooks with deal type motions, verbatim talk tracks, discovery questions, and objection handling scripts. | References `sales.Pipeline` and `sales.PipelineStage`. Does not duplicate stage definitions. |
| **3. Training & Certification Tracking** | HRM 3.23–3.25 owns enterprise HR courses (`hrm.TrainingCourse`) and employee certificates (`hrm.TrainingCertificate`). | `SalesCertification` (`SCTF-`) — sales-specific rep readiness, product pitch accreditation, sales onboarding curricula, and commercial compliance records linked to `User`. | Reuses `User`. Does not duplicate HRM attendance rosters or payroll certification rules. Optional FK to `hrm.TrainingCourse`. |
| **4. Coaching & Call Recording** | CRM 1.5 owns `CommunicationLog`. Sales 8.8 owns `ActivityLog`. Telephony streaming is external/integration. | `CoachingScorecard` (`CSC-`) — manager coaching scorecards, rubric scoring (discovery, value prop, objection handling, closing), call recording URLs, and transcription summaries/metadata. | Extends `crm.CommunicationLog` and `sales.ActivityLog`. Real-time telephony bots and speech-to-text engines are external integration. |
| **5. Competitive Intelligence Library** | **`CompetitorProfile` (`CMP-`) is ALREADY BUILT in 8.2.** `OpportunityCompetitor`, `WinLossReason` (`WLR-`), and `OpportunityOutcome` (`OUT-`) are in 8.2. | Coordinates with 8.2's `CompetitorProfile` by linking battlecard `EnablementContent` to it; surfaces a Competitive Intelligence Library board compiling competitor SWOT, battlecards, and win/loss records. | **NO second `CompetitorProfile`!** 8.9 links collateral and playbooks to 8.2's existing competitor master. |

---

## 3. Leaders surveyed (with source links)

1. **Highspot** — Leading sales enablement platform unifying content governance, contextual playbooks, sales readiness paths, and buyer engagement analytics.  
   *Source:* [https://www.highspot.com/platform/](https://www.highspot.com/platform/)
2. **Seismic** — Enterprise enablement standard-bearer featuring sales content automation, interactive stage playbooks, continuous learning, and manager coaching scorecards.  
   *Source:* [https://seismic.com/product/](https://seismic.com/product/)
3. **Showpad** — Revenue enablement platform uniting content repositories, Showpad Coach (sales readiness and onboarding), guided selling playbooks, and buyer Shared Spaces.  
   *Source:* [https://www.showpad.com/products/](https://www.showpad.com/products/)
4. **Mindtickle** — Sales readiness and revenue productivity suite combining structured sales certifications, Call AI conversation intelligence, and rubric-based call scorecards.  
   *Source:* [https://www.mindtickle.com/platform/](https://www.mindtickle.com/platform/)
5. **Gong** — Conversation intelligence pioneer capturing web meetings, automated call transcription, talk-to-listen analytics, and structured manager coaching scorecards.  
   *Source:* [https://www.gong.io/conversation-intelligence/](https://www.gong.io/conversation-intelligence/)
6. **Salesloft (Conversations)** — Revenue workflow platform featuring conversation intelligence, customizable coaching scorecards, AI evaluation suggestions, and coaching analytics.  
   *Source:* [https://salesloft.com/platform/conversations/](https://salesloft.com/platform/conversations/)
7. **Outreach (Kaia)** — Live conversation intelligence providing real-time in-meeting Coach Cards, objection handling prompts, transcription, and post-call deal summaries.  
   *Source:* [https://www.outreach.io/platform/kaia](https://www.outreach.io/platform/kaia)
8. **Klue** — Premier competitive enablement platform providing multi-tile sales battlecards, competitor tracking, objection counters, and win/loss CRM sync.  
   *Source:* [https://klue.com/product/](https://klue.com/product/)
9. **Crayon** — Market and competitive intelligence platform providing automated competitor tracking, dynamic battlecards, SWOT analysis boards, and positioning guides.  
   *Source:* [https://www.crayon.co/platform](https://www.crayon.co/platform)
10. **Allego** — Sales enablement and readiness platform specializing in asynchronous video coaching, pitch rehearsal, interactive playbooks, and microlearning certifications.  
    *Source:* [https://www.allego.com/platform/](https://www.allego.com/platform/)

---

## 4. Feature catalog (this sub-module only)

### 4.1 Content Repository & Search (NavERP.md Bullet 1)
- **Centralized Enablement Asset Catalog** — Structured catalog for sales collateral: battle cards, pitch decks, case studies, product sheets, whitepapers, demo scripts, and solution briefs.  
  *Seen in:* Highspot, Seismic, Showpad  
  *Priority:* Table-stakes  
  *Spine:* New `EnablementContent` (`ECN-`), with optional FK to `core.Document` for file attachments. Buildable now.
- **Dual-Storage Collateral Linking (File vs Cloud URL)** — Support for uploaded files (`core.Document`) as well as cloud-hosted URLs (Google Slides, Notion, Figma, Loom, SharePoint) so assets aren't limited to static files.  
  *Seen in:* Highspot, Showpad  
  *Priority:* Common  
  *Spine:* `document` (FK `core.Document`) + `external_url` on `EnablementContent`. Buildable now.
- **Contextual Stage & Persona Tagging** — Tagging collateral by target buying persona (e.g. Economic Buyer, Technical Evaluator) and pipeline stage (`sales.PipelineStage`) to recommend content during deal progression.  
  *Seen in:* Highspot, Seismic  
  *Priority:* Common  
  *Spine:* `target_persona`, `pipeline_stage` (FK `sales.PipelineStage`), and `tags` on `EnablementContent`. Buildable now.
- **Client-Facing vs Internal Guidance Distinction** — Clear demarcation between customer-shareable assets (pitch decks, case studies) and internal-only confidential guidance (battle cards, pricing strategies).  
  *Seen in:* Highspot, Seismic, Showpad  
  *Priority:* Table-stakes  
  *Spine:* `is_client_facing` Boolean on `EnablementContent`. Buildable now.
- **Asset Versioning & Expiration Governance** — Storing version numbers, publication status (`draft`, `published`, `archived`), and review/expiration dates to prevent reps from pitching obsolete collateral.  
  *Seen in:* Seismic, Highspot  
  *Priority:* Common  
  *Spine:* `version`, `status`, `expires_on` on `EnablementContent`. Buildable now.
- **Collateral Usage & Engagement Counters** — Frozen counters recording internal view count and rep sharing count to surface top-performing assets.  
  *Seen in:* Highspot, Showpad  
  *Priority:* Common  
  *Spine:* `view_count`, `share_count` (editable=False) on `EnablementContent`. Buildable now.
- **AI-Powered Vector Semantic Search** — Full-text and vector-embedded search over collateral content.  
  *Seen in:* Highspot (Copilot), Seismic (Aura)  
  *Priority:* Differentiator  
  *Spine:* Keyword/tag search buildable now via Django `Q` objects; vector embeddings deferred to integration phase.

### 4.2 Sales Playbooks & Guidance (NavERP.md Bullet 2)
- **Structured Selling Playbooks** — Dedicated playbooks matching specific selling motions (`new_business`, `expansion`, `renewal`, `competitive_displacement`).  
  *Seen in:* Highspot, Seismic, Showpad, Allego  
  *Priority:* Table-stakes  
  *Spine:* New `SalesPlaybook` (`SPB-`). Buildable now.
- **Verbatim Stage Talk Tracks & Value Messaging** — Concrete, tested phrasing for reps to communicate value proposition, company positioning, and product differentiators at each stage.  
  *Seen in:* Highspot, Showpad, Outreach Kaia  
  *Priority:* Table-stakes  
  *Spine:* `talk_tracks` TextField on `SalesPlaybook`. Buildable now.
- **Prescriptive Discovery Question Frameworks** — Categorized discovery questions (budget, authority, need, timeline, technical architecture) to guide rep discovery calls.  
  *Seen in:* Mindtickle, Gong, Seismic  
  *Priority:* Common  
  *Spine:* `discovery_questions` TextField on `SalesPlaybook`. Buildable now.
- **Objection Handling Scripts & Battle Rebuttals** — Structured objection scripts matching common buyer pushbacks (pricing, timing, feature gaps, competitor preference) with recommended counters.  
  *Seen in:* Highspot, Klue, Seismic, Outreach  
  *Priority:* Table-stakes  
  *Spine:* `objection_scripts` TextField on `SalesPlaybook`. Buildable now.
- **Do's and Don'ts Best Practices Guide** — Practical field guidelines highlighting proven winning habits and critical landmines to avoid during the sales cycle.  
  *Seen in:* Highspot, Allego  
  *Priority:* Common  
  *Spine:* `do_and_dont` TextField on `SalesPlaybook`. Buildable now.
- **Pipeline Stage Alignment** — Aligning playbooks directly to `sales.Pipeline` and `sales.PipelineStage` so reps working an opportunity can access the active playbook directly.  
  *Seen in:* Seismic, Highspot  
  *Priority:* Common  
  *Spine:* `target_pipeline` (FK `sales.Pipeline`) and `target_stage` (FK `sales.PipelineStage`) on `SalesPlaybook`. Buildable now.

### 4.3 Training & Certification Tracking (NavERP.md Bullet 3)
- **Sales Readiness Curricula & Certification Tracking** — Centralized tracking of rep training milestones: new-hire onboarding curricula, product certifications, pitch accreditations, and regulatory compliance.  
  *Seen in:* Mindtickle, Showpad Coach, Brainshark, Allego  
  *Priority:* Table-stakes  
  *Spine:* New `SalesCertification` (`SCTF-`) linking `accounts.User`. Buildable now.
- **Multi-Category Sales Training Records** — Categorizing certifications into `onboarding`, `product_certification`, `methodology`, `compliance`, and `pitch_accreditation`.  
  *Seen in:* Mindtickle, Brainshark  
  *Priority:* Table-stakes  
  *Spine:* `category` CharField choices on `SalesCertification`. Buildable now.
- **Scoring & Pass/Fail Accreditation** — Capturing objective scores (0–100%) and certification grant status with evaluation date and approving manager.  
  *Seen in:* Mindtickle, Highspot  
  *Priority:* Table-stakes  
  *Spine:* `score`, `passed`, `certified_by` (FK `accounts.User`), `completed_date` on `SalesCertification`. Buildable now.
- **Certification Expiration & Re-certification Cycles** — Tracking expiry dates (`expires_on`) for compliance and annual product certifications to trigger re-certification workflows.  
  *Seen in:* Mindtickle, Brainshark  
  *Priority:* Common  
  *Spine:* `expires_on` DateField on `SalesCertification`. Buildable now.
- **HRM Enterprise Training Alignment (Optional Bridge)** — Linking sales readiness records to company-wide `hrm.TrainingCourse` without duplicating HRM's attendance rosters.  
  *Seen in:* Workday Learning / Mindtickle integrations  
  *Priority:* Common  
  *Spine:* Nullable FK `training_course` to `hrm.TrainingCourse`. Buildable now.
- **AI Virtual Pitch Practice & Roleplay Simulator** — Interactive AI simulations where reps practice pitches against simulated buyers with automated speech scoring.  
  *Seen in:* Mindtickle, Showpad Genie, Allego  
  *Priority:* Differentiator  
  *Spine:* Integration/deferred.

### 4.4 Coaching & Call Recording (NavERP.md Bullet 4)
- **Structured Manager Coaching Scorecards** — Rubric-based evaluation scorecards filled out by managers to coach reps on specific sales interactions.  
  *Seen in:* Gong, Salesloft Conversations, Mindtickle, Seismic  
  *Priority:* Table-stakes  
  *Spine:* New `CoachingScorecard` (`CSC-`) linking `crm.CommunicationLog` and `sales.ActivityLog`. Buildable now.
- **Standardized Multi-Dimensional Competency Rubric** — Structured scoring (1–5 scale) across key interaction dimensions: Discovery Depth, Value Proposition, Objection Handling, and Next Steps / Closing.  
  *Seen in:* Gong, Salesloft, Mindtickle  
  *Priority:* Table-stakes  
  *Spine:* `discovery_score`, `value_prop_score`, `objection_handling_score`, `next_steps_score`, and computed/entered `overall_score` on `CoachingScorecard`. Buildable now.
- **Conversation Intelligence Metadata & Transcription Excerpt** — Capturing call recording URL, transcript summary/snippets, customer sentiment, and talk-to-listen ratio.  
  *Seen in:* Gong, Salesloft, Outreach Kaia  
  *Priority:* Common  
  *Spine:* `call_recording_url`, `transcript_summary`, `sentiment`, `talk_ratio_pct` on `CoachingScorecard`. Buildable now.
- **Qualitative Coaching Feedback & Concrete Action Items** — Dedicated sections for manager feedback: observed strengths, growth areas, and agreed follow-up action items.  
  *Seen in:* Gong, Salesloft, Allego  
  *Priority:* Table-stakes  
  *Spine:* `strengths`, `growth_areas`, `action_items` on `CoachingScorecard`. Buildable now.
- **Coaching Workflow & Rep Acknowledgment** — Managing scorecard lifecycle (`draft`, `shared`, `acknowledged`) so reps can review and acknowledge manager feedback.  
  *Seen in:* Salesloft, Mindtickle  
  *Priority:* Common  
  *Spine:* `status` CharField on `CoachingScorecard`. Buildable now.
- **Automated Audio Capture & Real-Time Bot Telephony** — Web meeting recording bots (Zoom/Teams) and telephony recording engines.  
  *Seen in:* Gong, Outreach Kaia  
  *Priority:* Table-stakes in pure CI products  
  *Spine:* Telephony / CRM integration (deferred; 8.9 accepts recording URLs / document attachments).

### 4.5 Competitive Intelligence Library (NavERP.md Bullet 5)
- **Competitor Master Profile Coordination** — Coordination with 8.2's existing `CompetitorProfile` (`CMP-`), which already holds competitor description, market positioning, strengths, weaknesses, differentiators, and objection handling.  
  *Seen in:* Klue, Crayon, Highspot  
  *Priority:* Table-stakes  
  *Spine:* **REUSE 8.2 `sales.CompetitorProfile`**. 8.9 declares NO second competitor master!
- **Competitor Battlecard Linking** — Dedicated enablement content assets (`EnablementContent` with `content_type="battle_card"`) linked directly to `sales.CompetitorProfile`.  
  *Seen in:* Klue, Crayon, Highspot  
  *Priority:* Table-stakes  
  *Spine:* FK `competitor` on `EnablementContent` pointing to `sales.CompetitorProfile`. Buildable now.
- **Competitive Win/Loss Summary Tracking** — Aggregated win/loss track record and competitor loss reasons derived from 8.2's `OpportunityOutcome` and `WinLossReason`.  
  *Seen in:* Klue, DoubleCheck, Crayon  
  *Priority:* Common  
  *Spine:* Read-only aggregation over 8.2 `sales.OpportunityOutcome` + `sales.OpportunityCompetitor`. Buildable now.
- **Competitive Intelligence Library Hub & SWOT Board** — Read-only management board bringing together competitor profiles, SWOT matrices, battlecards, and win/loss records in one place.  
  *Seen in:* Klue, Crayon  
  *Priority:* Common  
  *Spine:* Read-only board view (`sales_competitive_intelligence_library`). Buildable now.
- **Automated Web & Market Signal Scraping** — Automated web crawlers detecting competitor pricing, website changes, and news.  
  *Seen in:* Crayon  
  *Priority:* Differentiator  
  *Spine:* External integration / deferred.

---

## 5. Ownership & Reuse-vs-Build Rulings (L29 / L36 / L37)

### 5.1 The Rulings Summary
Sub-module 8.9 adds four primary models, strictly tenant-scoped, and reuses existing spine and sibling entities:
1. **Competitors**: **REUSE `sales.CompetitorProfile` (8.2)**. 8.2 already owns `CompetitorProfile` (`CMP-`), `OpportunityCompetitor`, `WinLossReason` (`WLR-`), and `OpportunityOutcome` (`OUT-`). Declaring a `sales.Competitor` or `sales.BattleCardMaster` table would be a direct violation of L36/L37. 8.9 coordinates with 8.2 by linking battlecard collateral (`EnablementContent.competitor`) and playbooks to `sales.CompetitorProfile`.
2. **Interactions & Activities**: **REUSE `crm.CommunicationLog` (CRM 1.5) & `sales.ActivityLog` (Sales 8.8)**. 8.9 coaching scorecards evaluate calls and meetings already captured in `crm.CommunicationLog` and attributed in `sales.ActivityLog`. 8.9 declares NO second call log or interaction master.
3. **File Attachments**: **REUSE `core.Document` (Core 0)**. Collateral files (PDF decks, case studies, product sheets) are stored via `core.Document`. 8.9 provides the sales categorization, tagging, and guided selling layer above it.
4. **Pipelines & Stages**: **REUSE `sales.Pipeline` & `sales.PipelineStage` (Sales 8.2)**. Playbooks and collateral stage targeting FK into existing 8.2 pipeline stages.
5. **Users & Sales Reps**: **REUSE `accounts.User`**. Coachees, coaches, reps, and certifiers are `accounts.User` rows.

### 5.2 Reuse-vs-Build Mapping Table

| Feature / Entity | Verdict | Owner | Where it lives | How 8.9 uses it |
|---|---|---|---|---|
| Competitor Profiles | **REUSE** | **Sales 8.2** | `apps/sales/models/CompetitiveIntelligence/CompetitiveIntelligence.py` | `EnablementContent.competitor` FKs `sales.CompetitorProfile`. Competitive board reads it. |
| Win/Loss Outcomes & Reasons | **REUSE** | **Sales 8.2** | `apps/sales/models/OpportunityOutcomes/OpportunityOutcomes.py` | Competitive Intelligence board aggregates `sales.OpportunityOutcome` + `sales.WinLossReason`. |
| Customer Interaction Records | **REUSE** | **CRM 1.5** | `apps/crm/models/ActivityManagement/CommunicationLogs.py` | `CoachingScorecard.communication_log` FKs `crm.CommunicationLog`. |
| Sales Activity Attribution | **REUSE** | **Sales 8.8** | `apps/sales/models/SalesActivityTaskManagement/ActivityLogs.py` | `CoachingScorecard.activity_log` FKs `sales.ActivityLog`. |
| Opportunities & Deals | **REUSE** | **CRM 1.2** | `apps/crm/models/SalesForceAutomation/Opportunities.py` | Read via communication log / activity log links. |
| Pipelines & Stages | **REUSE** | **Sales 8.2** | `apps/sales/models/OpportunityPipeline/Pipelines.py` | `SalesPlaybook.target_pipeline` & `SalesPlaybook.target_stage` FK. |
| File Binary Storage | **REUSE** | **Core 0** | `apps/core/models/Document.py` | `EnablementContent.document` FKs `core.Document`. |
| Accounts & Competitor Parties | **REUSE** | **Core 0** | `apps/core/models/Party.py` | Read via `CompetitorProfile.party` (`kind="organization"`). |
| Users / Reps / Coaches | **REUSE** | **Accounts** | `apps/accounts/models/User.py` | `coachee`, `coach`, `rep`, `certified_by`, `owner` FKs. |
| Enterprise Training Master | **REUSE (Bridge)** | **HRM 3.23** | `apps/hrm/models/TrainingManagement/Trainingcourse.py` | `SalesCertification.training_course` optional bridge FK. |
| Sales Collateral & Battlecards | **BUILD NEW** | **Sales 8.9** | `apps/sales/models/SalesEnablement/EnablementContent.py` | `EnablementContent` (`ECN-`). |
| Guided Selling Playbooks | **BUILD NEW** | **Sales 8.9** | `apps/sales/models/SalesEnablement/SalesPlaybooks.py` | `SalesPlaybook` (`SPB-`). |
| Rep Readiness Certifications | **BUILD NEW** | **Sales 8.9** | `apps/sales/models/SalesEnablement/SalesCertifications.py` | `SalesCertification` (`SCTF-`). |
| Manager Coaching Scorecards | **BUILD NEW** | **Sales 8.9** | `apps/sales/models/SalesEnablement/CoachingScorecards.py` | `CoachingScorecard` (`CSC-`). |

---

## 6. Boolean combinations and preconditions (L39 / L44)

Every guard is formulated with both satisfying and violating paths:

| # | Model | Invariant / Guard | Positive Path (Must Succeed) | Negative Path (Must be Refused) |
|---|---|---|---|---|
| **G1** | `EnablementContent` | Battle cards must target a competitor | `content_type="battle_card"`, `competitor=profile_1` → saves | `content_type="battle_card"`, `competitor=None` → `ValidationError({"competitor": ...})` |
| **G2** | `EnablementContent` | Non-battlecard collateral must not require a competitor, but can optionally link | `content_type="case_study"`, `competitor=None` → saves | N/A (valid optional path) |
| **G3** | `EnablementContent` | Internal battle cards cannot be marked client-facing | `content_type="battle_card"`, `is_client_facing=False` → saves | `content_type="battle_card"`, `is_client_facing=True` → `ValidationError({"is_client_facing": ...})` |
| **G4** | `EnablementContent` | Must provide at least one asset source (file document, external URL, or description/guidance) | `document=doc_1`, `external_url=""` → saves; or `external_url="https://..."` → saves | `document=None`, `external_url=""`, `description=""` → `ValidationError` |
| **G5** | `EnablementContent` | Cross-tenant FK isolation on `document`, `competitor`, and `pipeline_stage` | Same tenant on all relations → saves | `document` or `competitor` from tenant B while saving for tenant A → `ValidationError` |
| **G6** | `SalesPlaybook` | `target_stage` must belong to `target_pipeline` if both are set | `target_stage` whose `pipeline == target_pipeline` → saves | `target_stage` from Pipeline X with `target_pipeline` set to Pipeline Y → `ValidationError({"target_stage": ...})` |
| **G7** | `SalesPlaybook` | Code uniqueness per tenant | `code="enterprise-meddpicc"` for tenant A → saves | Duplicate code in tenant A → `IntegrityError` / `ValidationError` |
| **G8** | `SalesCertification` | `status="certified"` requires `completed_date` and `passed=True` | `status="certified"`, `completed_date=today`, `passed=True` → saves | `status="certified"` with `completed_date=None` or `passed=False` → `ValidationError` |
| **G9** | `SalesCertification` | `status="assigned"` or `"in_progress"` cannot have a `completed_date` | `status="in_progress"`, `completed_date=None` → saves | `status="in_progress"`, `completed_date=today` → `ValidationError` |
| **G10** | `SalesCertification` | Expiration date must be after completion date | `completed_date=2026-10-01`, `expires_on=2027-10-01` → saves | `completed_date=2026-10-01`, `expires_on=2026-09-01` → `ValidationError({"expires_on": ...})` |
| **G11** | `SalesCertification` | Score bounded 0.00 to 100.00 | `score=Decimal("85.50")` → saves | `score=Decimal("105.00")` or `score=Decimal("-5.00")` → `ValidationError` |
| **G12** | `CoachingScorecard` | Same tenant across `communication_log`, `activity_log`, `coachee`, and `coach` | All entities belong to tenant A → saves | `communication_log` from tenant B → `ValidationError` |
| **G13** | `CoachingScorecard` | Activity log (if linked) must match the communication log | `activity_log.communication_log == communication_log` → saves | `activity_log` referencing a different communication log → `ValidationError({"activity_log": ...})` |
| **G14** | `CoachingScorecard` | Coach and coachee cannot be the same user (manager coaching vs self-review) | `coach=user_mgr`, `coachee=user_rep` → saves | `coach=user_rep`, `coachee=user_rep` → `ValidationError({"coach": ...})` |
| **G15** | `CoachingScorecard` | Rubric component scores must be integers 1 to 5; `talk_ratio_pct` 0 to 100 | `discovery_score=4`, `talk_ratio_pct=45` → saves | `discovery_score=6` or `talk_ratio_pct=110` → `ValidationError` |
| **G16** | `CoachingScorecard` | `overall_score` must be 1 to 100 | `overall_score=88` → saves | `overall_score=105` → `ValidationError` |

---

## 7. Recommended build scope (this pass — exactly 4 models)

### Model 1: `EnablementContent` [PREFIX: `ECN-`]
- **Purpose**: Serves **Bullet 1** (Content Repository & Search) and **Bullet 5** (Battlecards and competitive positioning collateral).
- **Justified by**: Highspot Content Spots, Seismic Content Repository, Showpad Experiences, Klue Battlecards.
- **Fields**:
  * `number` — auto-numbered with prefix `ECN` (TenantNumbered).
  * `title` — `CharField(max_length=255)`.
  * `description` — `TextField(blank=True)`.
  * `content_type` — `CharField(max_length=30, choices=CONTENT_TYPE_CHOICES)`:
    `battle_card` ("Battle Card"), `pitch_deck` ("Pitch Deck"), `case_study` ("Case Study"), `product_sheet` ("Product Sheet"), `whitepaper` ("Whitepaper"), `objection_script` ("Objection Script"), `solution_brief` ("Solution Brief"), `demo_guide` ("Demo Guide"), `email_template` ("Email Template").
  * `document` — `ForeignKey("core.Document", on_delete=models.SET_NULL, null=True, blank=True)`: generic file attachment for PDF/PPTX collateral.
  * `external_url` — `URLField(max_length=500, blank=True)`: link to cloud assets (Google Drive, Figma, Loom, Notion).
  * `competitor` — `ForeignKey("sales.CompetitorProfile", on_delete=models.SET_NULL, null=True, blank=True)`: connects battle cards and competitive guides to 8.2's `CompetitorProfile`.
  * `pipeline_stage` — `ForeignKey("sales.PipelineStage", on_delete=models.SET_NULL, null=True, blank=True)`: stage recommendation.
  * `target_persona` — `CharField(max_length=120, blank=True)`: e.g. "Economic Buyer", "Technical Evaluator", "End User".
  * `tags` — `TextField(blank=True)`: comma-separated keywords for search.
  * `is_client_facing` — `BooleanField(default=False)`: False = internal guidance; True = prospect-shareable.
  * `status` — `CharField(max_length=20, choices=STATUS_CHOICES, default="published")`: `draft`, `published`, `archived`.
  * `owner` — `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)`.
  * `version` — `CharField(max_length=20, default="1.0")`.
  * `view_count` — `PositiveIntegerField(default=0, editable=False)`.
  * `share_count` — `PositiveIntegerField(default=0, editable=False)`.
- **Constraints & Indexes**:
  * Unique `(tenant, number)`.
  * Indexes: `(tenant, content_type)`, `(tenant, status)`, `(tenant, competitor)`, `(tenant, is_client_facing)`. (All index names ≤ 30 characters).

### Model 2: `SalesPlaybook` [PREFIX: `SPB-`]
- **Purpose**: Serves **Bullet 2** (Sales Playbooks & Guidance: step-by-step selling guidance, stage talk tracks, and objection handling scripts).
- **Justified by**: Highspot Playbooks, Seismic Guided Selling, Showpad Playbooks, Outreach Coach Cards.
- **Fields**:
  * `number` — auto-numbered with prefix `SPB` (TenantNumbered).
  * `name` — `CharField(max_length=255)`.
  * `code` — `SlugField(max_length=60)`.
  * `description` — `TextField(blank=True)`.
  * `deal_type` — `CharField(max_length=30, choices=DEAL_TYPE_CHOICES, default="new_business")`:
    `new_business` ("New Business"), `expansion` ("Expansion / Upsell"), `renewal` ("Renewal"), `competitive_displacement` ("Competitive Displacement"), `general` ("General Motion").
  * `target_pipeline` — `ForeignKey("sales.Pipeline", on_delete=models.SET_NULL, null=True, blank=True)`.
  * `target_stage` — `ForeignKey("sales.PipelineStage", on_delete=models.SET_NULL, null=True, blank=True)`.
  * `selling_motion` — `CharField(max_length=120, blank=True)`: e.g. "Inbound SMB", "Enterprise MEDDPICC", "Channel Co-sell".
  * `talk_tracks` — `TextField(blank=True)`: verbatim stage talk tracks and value messaging.
  * `discovery_questions` — `TextField(blank=True)`: qualifying discovery questions.
  * `objection_scripts` — `TextField(blank=True)`: common objections and handling rebuttals.
  * `do_and_dont` — `TextField(blank=True)`: recommended best practices and landmines to avoid.
  * `status` — `CharField(max_length=20, choices=STATUS_CHOICES, default="active")`: `draft`, `active`, `archived`.
  * `is_active` — `BooleanField(default=True)`.
  * `owner` — `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)`.
- **Constraints & Indexes**:
  * Unique `(tenant, number)`, unique `(tenant, code)`.
  * Indexes: `(tenant, is_active)`, `(tenant, target_pipeline)`, `(tenant, target_stage)`.

### Model 3: `SalesCertification` [PREFIX: `SCTF-`]
- **Purpose**: Serves **Bullet 3** (Training & Certification Tracking: onboarding curricula, product certification, and compliance training records).
- **Justified by**: Mindtickle Readiness & Pitch Certification, Brainshark Readiness Scorecards, Showpad Coach.
- **Fields**:
  * `number` — auto-numbered with prefix `SCTF` (TenantNumbered).
  * `rep` — `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sales_certifications")`: the sales rep.
  * `name` — `CharField(max_length=255)`: title of certification / curriculum program.
  * `category` — `CharField(max_length=30, choices=CATEGORY_CHOICES, default="product_certification")`:
    `onboarding` ("New Hire Onboarding"), `product_certification` ("Product Certification"), `methodology` ("Sales Methodology (e.g. MEDDPICC)"), `compliance` ("Commercial Compliance / Legal"), `pitch_accreditation` ("Pitch & Demo Accreditation").
  * `status` — `CharField(max_length=20, choices=STATUS_CHOICES, default="assigned")`:
    `assigned` ("Assigned"), `in_progress` ("In Progress"), `certified` ("Certified"), `failed` ("Failed"), `expired` ("Expired"), `waived` ("Waived").
  * `score` — `DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(100)])`.
  * `passed` — `BooleanField(default=False)`.
  * `assigned_date` — `DateField(default=timezone.localdate)`.
  * `completed_date` — `DateField(null=True, blank=True)`.
  * `expires_on` — `DateField(null=True, blank=True)`.
  * `certified_by` — `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="issued_sales_certifications")`.
  * `training_course` — `ForeignKey("hrm.TrainingCourse", on_delete=models.SET_NULL, null=True, blank=True)`: optional cross-module link to enterprise HRM course.
  * `notes` — `TextField(blank=True)`.
- **Constraints & Indexes**:
  * Unique `(tenant, number)`.
  * Indexes: `(tenant, rep)`, `(tenant, status)`, `(tenant, category)`, `(tenant, expires_on)`.

### Model 4: `CoachingScorecard` [PREFIX: `CSC-`]
- **Purpose**: Serves **Bullet 4** (Coaching & Call Recording: conversation intelligence metadata, manager coaching scorecards, call transcription reviews).
- **Justified by**: Gong Coaching Scorecards, Salesloft Conversations, Mindtickle Call Coaching.
- **Fields**:
  * `number` — auto-numbered with prefix `CSC` (TenantNumbered).
  * `communication_log` — `ForeignKey("crm.CommunicationLog", on_delete=models.CASCADE, related_name="sales_coaching_scorecards")`: CRM 1.5 interaction being evaluated.
  * `activity_log` — `ForeignKey("sales.ActivityLog", on_delete=models.SET_NULL, null=True, blank=True, related_name="coaching_scorecards")`: 8.8 sales activity layer.
  * `coachee` — `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="coached_scorecards")`: rep evaluated.
  * `coach` — `ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="given_coaching_scorecards")`: manager/coach.
  * `call_recording_url` — `URLField(max_length=500, blank=True)`: audio/video recording URL.
  * `transcript_summary` — `TextField(blank=True)`: conversation intelligence summary or transcription snippet.
  * `sentiment` — `CharField(max_length=20, choices=SENTIMENT_CHOICES, blank=True)`: `positive`, `neutral`, `negative`, `mixed`.
  * `talk_ratio_pct` — `PositiveSmallIntegerField(null=True, blank=True, validators=[MaxValueValidator(100)])`: rep talk-to-listen percentage.
  * `discovery_score` — `PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)])`.
  * `value_prop_score` — `PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)])`.
  * `objection_handling_score` — `PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)])`.
  * `next_steps_score` — `PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)])`.
  * `overall_score` — `PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(100)])`: composite percentage score.
  * `strengths` — `TextField(blank=True)`: coach feedback on what the rep did well.
  * `growth_areas` — `TextField(blank=True)`: coach feedback on areas for improvement.
  * `action_items` — `TextField(blank=True)`: agreed next developmental actions.
  * `status` — `CharField(max_length=20, choices=STATUS_CHOICES, default="draft")`: `draft`, `shared`, `acknowledged`.
  * `coached_at` — `DateTimeField(default=timezone.now)`.
- **Constraints & Indexes**:
  * Unique `(tenant, number)`.
  * Indexes: `(tenant, coachee)`, `(tenant, coach)`, `(tenant, communication_log)`, `(tenant, status)`.

---

## 8. Read-only board candidates (no new models)

1. **`sales_enablement_content_hub`** (Content Repository & Search)  
   Serves **Bullet 1**. Filterable and searchable collateral library (battle cards, pitch decks, case studies, product sheets) with filters by content type, stage, competitor, persona, and text tags. Surfaces view/share counts.
2. **`sales_playbook_board`** (Sales Playbooks & Guidance)  
   Serves **Bullet 2**. Interactive guided selling interface displaying active playbooks filtered by deal type or pipeline stage, displaying talk tracks, discovery questions, objection handling scripts, and recommended collateral.
3. **`sales_readiness_board`** (Training & Certification Tracking)  
   Serves **Bullet 3**. Sales team readiness matrix showing rep-by-rep certification status across onboarding, product accreditation, and compliance; flags expired or upcoming-due certifications.
4. **`sales_coaching_workbench`** (Coaching & Call Recording)  
   Serves **Bullet 4**. Manager coaching dashboard displaying recent evaluated calls, score distributions across the 4 rubric dimensions (discovery, value prop, objections, next steps), talk ratio benchmarks, and pending reviews.
5. **`sales_competitive_intelligence_library`** (Competitive Intelligence Library)  
   Serves **Bullet 5**. Comprehensive CI library bringing together 8.2 `CompetitorProfile` records, their linked battlecard collateral (`EnablementContent`), SWOT summaries, and win/loss records (`sales.OpportunityOutcome` + `sales.OpportunityCompetitor`).

---

## 9. Belongs to sibling sub-modules (parked, not scoped here)

- **Competitor profile master CRUD & deal-level competitor attachment** → **Sales 8.2** (`OpportunityCompetitor`, `CompetitorProfile`). 8.9 links to it; does not re-declare it.
- **Win/loss outcome recording & closed deal loss reasons** → **Sales 8.2** (`OpportunityOutcome`, `WinLossReason`). 8.9 aggregates outcomes for CI cards; does not create a second outcome engine.
- **Deep econometric win/loss analytics & sales velocity trends** → **Sales 8.12** (Sales Analytics & Intelligence).
- **Activity & communication interaction logging** → **CRM 1.5** (`CommunicationLog`) and **Sales 8.8** (`ActivityLog`). 8.9 coaching scorecards link to them.
- **Enterprise-wide HR courses, classroom sessions, and employee certificates** → **HRM 3.23–3.25** (`TrainingCourse`, `TrainingSession`, `TrainingCertificate`). 8.9 only tracks sales rep readiness and sales-specific accreditation.
- **Customer onboarding playbooks & QBR templates** → **Sales 8.11** (Customer Success & Account Management). 8.9 covers pre-sale internal sales playbooks.
- **Customer contract generation & e-signature signing** → **CRM 1.9** (`ContractDocument`). 8.9 covers sales collateral and pitch decks via `core.Document`.

---

## 10. Deferred (later passes / integrations)

- **Real-Time Telephony Recording & Web Meeting Bots** — Live Zoom/Teams meeting recording bots and VoIP dialer media streaming require cloud telephony infrastructure and webhooks. Deferred to external telephony integration; 8.9 stores recording URLs and uploaded media links.
- **Automated AI Speech-to-Text Transcription Engine** — Deepgram / Whisper / AssemblyAI speech-to-text pipeline requires external API connectors. Deferred to integration phase; 8.9 provides the transcription summary and snippet fields.
- **Automated Market Signal & Web Crawling Engine** — Background scrapers monitoring competitor website changes, pricing updates, and press releases. Deferred to an integration worker pipeline.
- **AI-Powered Pitch Roleplay Simulator** — Interactive voice/chat simulation agent for practice pitches. Deferred to future AI enablement pass.

---

## 11. Verdict

Build **8.9 Sales Enablement** with **exactly 4 tenant-scoped models**:
1. `EnablementContent` (`ECN-`) — Content repository, battle cards, pitch decks, case studies, stage/persona targeting, competitor links, and `core.Document` attachment.
2. `SalesPlaybook` (`SPB-`) — Step-by-step selling playbooks with talk tracks, discovery frameworks, and objection handling scripts.
3. `SalesCertification` (`SCTF-`) — Sales readiness, onboarding curricula, product certification, and compliance tracking for sales reps (`User`).
4. `CoachingScorecard` (`CSC-`) — Rubric-based manager coaching scorecards over `crm.CommunicationLog` / `sales.ActivityLog`, call recording links, talk ratios, and CI transcript summaries.

Plus **5 read-only boards** mapping directly to the 5 NavERP.md feature bullets, with **zero duplicate competitor or activity masters**.
