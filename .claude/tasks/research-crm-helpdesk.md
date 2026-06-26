# Research — Module 1 CRM §1.4: Customer Service & Support (Help Desk)
## Sub-module scope: Case/Ticket Management · Solutions & Knowledge Base · Customer Self-Service Portal

---

## Leaders surveyed

1. **Zendesk Support** — market-leading enterprise help desk with omnichannel ticketing, SLA engine, and AI KB — https://www.zendesk.com/service/help-desk-software/ticketing-system/
2. **Freshdesk** — mid-market help desk with priority-tiered SLA policies, CSAT, and customer portal — https://www.freshworks.com/helpdesk/software/
3. **Salesforce Service Cloud** — CRM-native case management with entitlement/SLA management and Einstein KB — https://www.salesforce.com/service/cloud/guide/
4. **Zoho Desk** — affordable multi-channel help desk with hierarchical KB, ASAP portal plug-in, and Zia AI — https://www.zoho.com/desk/compare-helpdesk-software.html
5. **Intercom** — AI-first help desk with FRT/NRT/TTR/TTC SLA metrics, Fin AI KB, and workflow-driven SLA triggers — https://www.intercom.com/helpdesk/tickets
6. **HubSpot Service Hub** — CRM-native ticketing with FRT/close SLA goals, KB, and authenticated customer portal — https://www.hubspot.com/products/service
7. **Jira Service Management (JSM)** — developer-centric ITSM/help desk with category-based KB, CSAT, and customer portal with request queues — https://www.atlassian.com/software/jira/service-management/features/service-desk
8. **ServiceNow CSM** — enterprise CSM with entitlements, SLA timers, case threading, AI virtual agent, and community self-service — https://www.servicenow.com/products/customer-service-management.html
9. **Help Scout** — email-centric shared inbox help desk with FRT/resolution SLA policies, Docs KB, and Beacon widget portal — https://www.helpscout.com/
10. **Front** — collaborative inbox help desk with internal notes/threads, SLA countdown, and conversation-centric workflows — https://front.app/ (via surveyed comparisons)

---

## Feature catalog by NavERP.md sub-module

### 1.4.1 Case / Ticket Management

- **Priority-tiered SLA targets (FRT + resolution time per priority)** — each of Urgent/High/Medium/Low gets its own first-response target and resolution target in hours/minutes; SLA timers start at ticket creation · seen in: Freshdesk, Zendesk, Zoho Desk, Intercom, HubSpot Service Hub, ServiceNow · priority: **table-stakes** · spine: new table `SlaPolicy` (per-tenant, per-priority rows); `Case.sla_policy FK` + `Case.first_response_due_at` + `Case.resolution_due_at` computed on case create/update · **buildable now**

- **SLA first-response breach detection** — system stamps `Case.first_response_at` when first public agent reply is posted; if no reply before `first_response_due_at` the case is flagged breached · seen in: Freshdesk, Zendesk, HubSpot, ServiceNow, Intercom · priority: **table-stakes** · spine: adds `first_response_at` + `first_response_breached` bool to `Case` · **buildable now**

- **SLA resolution breach detection** — stamps `Case.resolution_due_at`; when case not resolved by that time `resolution_breached` is flagged; `is_overdue` property already exists on Case (reuse/extend it) · seen in: Freshdesk, Zendesk, Zoho Desk, JSM, Help Scout, HubSpot · priority: **table-stakes** · spine: extends existing `Case.due_at` to use policy-computed deadline; adds `resolution_breached` bool · **buildable now**

- **Case conversation thread (public reply vs internal note)** — per-case ordered comment log with two roles: (a) public reply — visible to customer, sent in portal; (b) internal note — agent-only, never shown to customer; both support rich text; visual distinction (e.g. yellow background on internal note) · seen in: Zendesk (yellow background), Freshdesk (private/public toggle), Zoho Desk, Help Scout, Front, JSM, HubSpot, ServiceNow · priority: **table-stakes** · spine: new table `CaseComment` (per-case, per-tenant: `kind` public/internal, `body`, `author FK User`, `created_at`) · **buildable now**

- **Case type / origin tracking** — origin field (email/phone/portal/web/chat) already on `Case.origin`; type field (question/problem/incident/feature_request) already on `Case.type` — no new fields needed · seen in: Salesforce Service Cloud, Zoho Desk, Freshdesk · priority: **table-stakes** · spine: reuses existing `Case` fields · already built

- **Ticket/case status workflow (Open → In Progress → Waiting → Resolved → Closed)** — multi-step status machine; "waiting on customer" status pauses SLA timer in leading products · seen in: Zendesk, Freshdesk, Zoho Desk, ServiceNow, Help Scout · priority: **table-stakes** · spine: `Case.status` choices already built (`new/open/in_progress/waiting/resolved/closed`); SLA pause logic: when `status=waiting`, SLA timers stop counting · **buildable now** (pause logic in SLA compute service)

- **SLA policy assignment per-priority** — `SlaPolicy` table with `priority` key so each case inherits its targets from `SlaPolicy.filter(priority=case.priority)` at creation time · seen in: Freshdesk (4 priorities with individual targets), Zendesk (per-priority matrix), Intercom (workflow-applied), HubSpot (priority-based) · priority: **table-stakes** · spine: new table `SlaPolicy` with per-priority rows (or a single-row-per-policy table with priority as a field) · **buildable now**

- **SLA breach visual warnings** — in the case list/detail, a color-coded timer shows time remaining (green → orange → red → breached); countdown based on `resolution_due_at - now()` · seen in: Intercom (grey/orange/red), Zendesk, Freshdesk, JSM · priority: **common** · spine: computed from `Case.resolution_due_at` — no new fields; template property · **buildable now**

- **Case satisfaction / CSAT rating** — when case closes, a 1–5 star satisfaction score + optional comment field is recorded against the case (triggered by close event); score + comment stored on `Case` · seen in: Freshdesk, Zendesk, Zoho Desk, JSM, HubSpot Service Hub, ServiceNow · priority: **common** · spine: adds `csat_score` (1–5 tinyint, nullable), `csat_comment` (TextField), `csat_submitted_at` (DateTimeField) to `Case` · **buildable now**

- **Public case status tracking (no-login token)** — each case gets an unguessable `public_token`; a public (unauthenticated) URL shows subject, status, priority, last-updated, and agent's latest public reply; mirrors `LandingPage.public_token` + `survey_respond` patterns already in CRM · seen in: Freshdesk ("public ticket URL" placeholder in email notifications), Zoho Desk (public ticket links), Help Scout (email link to ticket) · priority: **common** · spine: adds `public_token` (unique, secrets.token_urlsafe(32)) to `Case`; public view at `case_public/<token>/` · **buildable now**

- **Assignment / ownership** — `Case.owner FK User` already exists; agent assignment triggers SLA first-response timer · already built

- **Business hours / calendar hours SLA toggle** — SLA targets can be calculated in either "calendar hours" (24/7) or "business hours" (Mon–Fri 9–5). Business hours calendar support requires a separate BusinessHours/Holiday model · seen in: Freshdesk, Zendesk, Help Scout, HubSpot · priority: **common** · spine: adds `hours_mode` choice (calendar/business) to `SlaPolicy`; business-hours calendar is a separate Holiday/BusinessHours table · **deferred** (the holiday/schedule table adds scope; ship `hours_mode=calendar` only in this pass; business-hours SLA in later extension)

- **SLA escalation notifications (breach alerts to manager)** — when first response or resolution SLA breaches, auto-notify a supervisor/manager via in-app notification or email · seen in: Freshdesk (multi-level escalation from Pro plan), Zendesk, JSM, ServiceNow · priority: **common** · spine: would use `Notification` model (Module 0 infra); tie-in to workflow engine (1.10 `WorkflowRule`) which already exists · **deferred to workflow/notification pass** — the data fields (breach booleans) are built now; the notification dispatch uses existing `WorkflowRule` engine

- **Round-robin / skill-based ticket assignment** — automatic routing of new cases to agents based on availability, workload, or skill tags · seen in: Freshdesk, Zoho Desk (Zia routing), Zendesk · priority: **differentiator** · spine: new assignment-rule table; complex rules engine · **deferred** (out of scope for this pass)

- **Merge duplicate cases** — combine two cases that report the same issue into one, linking all replies under the primary ticket · seen in: Freshdesk, Zendesk, Zoho Desk · priority: **common** · spine: adds `merged_into FK Case` to `Case` (nullable self-FK) · **deferred** (low priority for initial helpdesk pass; add in extension)

- **Macros / canned responses** — pre-saved reply templates that agents apply to tickets with one click · seen in: Zendesk, Freshdesk, Zoho Desk · priority: **common** · spine: new `CannedResponse` table (per-tenant, title + body) · **deferred** (nice-to-have; not in core 6 entities)

---

### 1.4.2 Solutions & Knowledge Base

- **KB category hierarchy (parent → child)** — hierarchical category structure (Category > Section/Subcategory > Article) lets customers navigate by topic; Zoho Desk uses Category > Sections > Subsections; JSM uses categories; Zendesk uses sections; all allow 2–3 levels · seen in: Zoho Desk (3-level hierarchy), JSM (categories), Freshdesk (categories + folders), Zendesk (categories + sections) · priority: **table-stakes** · spine: new table `KbCategory` (per-tenant, `name`, `slug`, `parent FK self`, `order int`); `KnowledgeArticle.category FK KbCategory` replaces existing `category CharField` · **buildable now**

- **Article visibility toggle (internal vs external)** — `KnowledgeArticle.visibility` choices `internal/external` already exist on the model; "external" = public-facing portal; "internal" = agent-only. Zendesk extends this with "agents-and-admins", "signed-in users", and "everyone" tiers; we simplify to internal/external for this pass · seen in: Zendesk (3+ visibility tiers), Freshdesk (internal/external toggle), Zoho Desk, JSM, HubSpot · priority: **table-stakes** · spine: `KnowledgeArticle.visibility` already built; no new fields for basic toggle · already built (enhance display)

- **Article draft / published / archived status workflow** — `KnowledgeArticle.status` choices `draft/published/archived` already exist; published articles appear in portal and agent search; draft = internal-only preview · seen in: Zendesk, Freshdesk, Zoho Desk, JSM · priority: **table-stakes** · spine: already built · already built

- **Article helpful/not-helpful feedback (thumbs up/down)** — customers or agents vote on article usefulness; running tallies of helpful_count / not_helpful_count stored on the article · seen in: Zoho Desk (likes/dislikes), JSM (voted as helpful = deflected request metric), Zendesk (article votes), HubSpot, Help Scout (Docs reactions) · priority: **common** · spine: adds `helpful_count` (PositiveIntegerField, default 0) + `not_helpful_count` (PositiveIntegerField, default 0) to `KnowledgeArticle`; F()-incremented on portal vote endpoint · **buildable now**

- **Article view counter** — `KnowledgeArticle.views_count` already exists; incremented on each detail view (internal + portal) · already built

- **Article public access token** — a public (no-login) URL to share individual KB articles externally (for "external" visibility articles served without requiring portal login). Mirrors `LandingPage.public_token`/`survey_respond` pattern · seen in: Zoho Desk (Help Center public URL), Freshdesk (portal public URLs), HubSpot (KB articles public by default) · priority: **common** · spine: adds `public_token` (unique, nullable, secrets.token_urlsafe(32)) to `KnowledgeArticle`; generated only when `visibility=external`; served at `kb_public/<token>/` · **buildable now**

- **Article-to-case linking (suggest related articles on case create)** — when an agent creates or views a case, the system suggests relevant KB articles based on keyword match; agents can link an article to a case · seen in: Zendesk, Freshdesk, Zoho Desk (Zia suggestions), JSM (article deflection), ServiceNow · priority: **common** · spine: adds `KnowledgeArticle` M2M to `Case` as a `suggested_articles` or simple JSONField list — simpler: add `related_article FK KnowledgeArticle nullable` to Case, or a many-to-many through table · **deferred** — the per-case article suggestion requires a search/text-match service; add in a later pass; the data model plumbing (category + article) ships now

- **Article version history / revert** — track previous versions of an article body for rollback · seen in: Zoho Desk, Zendesk, Freshdesk · priority: **differentiator** · spine: new `KbArticleVersion` table (article FK, body snapshot, edited_by, created_at) · **deferred** (versioning adds significant scope; not in core 6)

- **Multi-language KB support** — translate articles into multiple languages; per-locale variants · seen in: Zoho Desk (50+ languages), Zendesk · priority: **differentiator** · **deferred** (localization is a cross-cutting Module 0 concern)

---

### 1.4.3 Customer Self-Service Portal

- **Customer portal login (authenticated view own cases)** — a portal login scoped to a specific `core.Party` (customer organization or contact); lets the customer see all their cases, add replies, and submit new tickets; mirrors the `PartnerPortalAccess` + `portal_user OneToOneField User` pattern already in CRM §1.12 · seen in: HubSpot (login-required portal), Zendesk, Freshdesk, Zoho Desk, JSM · priority: **table-stakes** · spine: new table `CustomerPortalAccess` (per-tenant, `party FK core.Party`, `portal_user OneToOneField User`, `is_active bool`, `accepted_at DateTimeField`); shares pattern with existing `PartnerPortalAccess` · **buildable now**

- **Portal ticket submission** — authenticated portal customer can create a new case (subject, description, priority); case gets `origin=portal` and linked to the customer's `Party` automatically · seen in: Freshdesk, Zoho Desk, HubSpot, JSM, Zendesk · priority: **table-stakes** · spine: reuses `Case` model; portal `case_create` view behind `CustomerPortalAccess` check, pre-fills `account=customer.party`, sets `origin=portal` · **buildable now**

- **Portal case status tracking (authenticated)** — customer sees their case list filtered to their party, with status badges, priority, last updated; can click in to see the public reply thread · seen in: Freshdesk, HubSpot, Zoho Desk, JSM, Zendesk · priority: **table-stakes** · spine: portal list view filters `Case.objects.filter(tenant=..., account=portal_user.party)` + public CaseComments only (kind=public) · **buildable now**

- **Portal reply to case** — authenticated customer can add a reply from within the portal; this creates a `CaseComment(kind='public', is_customer_reply=True)`; moves case status back from Waiting → Open · seen in: HubSpot, Freshdesk, Zendesk, Zoho Desk · priority: **table-stakes** · spine: `CaseComment` gains a `is_customer_reply BooleanField` (default False); portal reply view creates public comment and updates Case.status from waiting → open · **buildable now**

- **Public (no-login) case status page by token** — unauthenticated URL (`/cases/track/<token>/`) shows case subject, status, priority, and the latest public agent reply; customer gets this link in their confirmation; they can check status without logging in · seen in: Freshdesk (public ticket URL placeholder), Zoho Desk (public ticket links), Help Scout (ticket email link) · priority: **common** · spine: `Case.public_token` field (see §1.4.1 above); public view exposes only subject/status/priority/last-public-comment · **buildable now**

- **Portal KB access (search + browse)** — authenticated portal customer can browse and search `KnowledgeArticle` where `visibility=external AND status=published`; reduces ticket submission volume · seen in: HubSpot, Zoho Desk, JSM, Freshdesk, Zendesk, Help Scout · priority: **table-stakes** · spine: reuses `KnowledgeArticle`; portal KB list/search view filters `visibility=external, status=published` · **buildable now** (view-only; search is simple q-filter)

- **Portal case CSAT submission** — when case is resolved/closed, customer can submit a CSAT rating (1–5 stars + optional comment) from within the portal or via the public token URL · seen in: Freshdesk, Zendesk, Zoho Desk, HubSpot, JSM · priority: **common** · spine: `Case.csat_score`, `Case.csat_comment`, `Case.csat_submitted_at` fields (see §1.4.1); portal CSAT submit endpoint; also submittable via `case_public/<token>/csat/` without login · **buildable now**

- **Community forums** — public discussion forum for peer-to-peer support; separate from the KB · seen in: Zoho Desk, Zendesk, ServiceNow · priority: **differentiator** · **deferred** (forum is a distinct sub-product; well out of scope for this pass)

- **Live chat / chatbot on portal** — embedded chat widget or AI bot answers questions in real time before creating a ticket · seen in: Zoho Desk (ASAP widget + Zia), Intercom (Fin AI), Freshdesk (Freddy AI) · priority: **differentiator** · **deferred** (real-time chat is an external integration — no WebSocket in this Django stack today)

- **Email-to-ticket ingestion** — inbound email to a support mailbox automatically creates a Case · seen in: Freshdesk, Zendesk, Help Scout, Zoho Desk · priority: **table-stakes** in commercial products · **deferred** — we model `Case.origin=email` as a choice but the actual mailbox polling is an external integration (celery beat + IMAP); data model is ready; delivery is out of scope

- **Omnichannel (social / SMS / WhatsApp / telephony)** — cases from Facebook, Twitter, WhatsApp, phone · seen in: Zoho Desk, Freshdesk Omni, ServiceNow · priority: **differentiator** · **deferred** (external channel integration)

- **AI answer-bot / ticket deflection** — AI auto-responds to tickets with KB suggestions before routing to agent · seen in: Freshdesk (Freddy), Intercom (Fin AI), Zoho Desk (Zia), Zendesk (AI agents) · priority: **differentiator** · **deferred** (requires LLM integration)

- **Automations / macros engine for helpdesk** — rule-based auto-assignment, auto-status-change, canned responses · seen in: Freshdesk, Zendesk · priority: **common** · **deferred** — the existing `WorkflowRule` (1.10) already covers trigger-based actions; wire `Case` trigger entity to it in the workflow pass

- **Business hours / holiday calendar for SLA** — SLA timers pause outside business hours; holiday schedule excluded · seen in: Freshdesk, Zendesk, Help Scout · priority: **common** · **deferred** — `SlaPolicy.hours_mode` stub ships now (always `calendar`); full business-hours schedule table deferred to a later extension pass

---

## Recommended build scope (this pass — 6 entities)

### 1. Enhance `Case` (existing model — add fields)
Fields to add (all justified by competitive research above):
- `sla_policy FK SlaPolicy` (nullable, SET_NULL) — links case to the policy applied at creation
- `first_response_due_at DateTimeField` (nullable) — system-computed from `SlaPolicy.first_response_hours` at case creation
- `first_response_at DateTimeField` (nullable) — system-set when first `CaseComment(kind='public', is_customer_reply=False)` is posted
- `first_response_breached BooleanField` (default False) — set when first_response_at > first_response_due_at or due is past and no response yet
- `resolution_due_at DateTimeField` (nullable) — system-computed from `SlaPolicy.resolution_hours` at case creation (replaces/augments generic `due_at`)
- `resolution_breached BooleanField` (default False) — set when unresolved past resolution_due_at
- `csat_score PositiveSmallIntegerField` (nullable, 1–5) — customer satisfaction rating (post-close)
- `csat_comment TextField` (blank=True) — optional free-text CSAT feedback
- `csat_submitted_at DateTimeField` (nullable) — system-set on submission
- `public_token CharField(64, unique=True, blank=True)` — unguessable URL-safe token for public status page; generated in `save()` via `secrets.token_urlsafe(32)`
Justification: Freshdesk/Zendesk/HubSpot all provide dual SLA targets (FRT + resolution) per priority, breach detection, CSAT on close, and public ticket URL.

### 2. `SlaPolicy` [SLA-] (new model)
Fields:
- `tenant FK core.Tenant`
- `number CharField(20, editable=False)` — `SLA-00001` via `next_number`
- `name CharField(255)` — e.g. "Standard SLA", "VIP SLA"
- `priority CharField(10, choices=LOW/MEDIUM/HIGH/CRITICAL)` — one policy row per priority level (unique_together: tenant + priority)
- `first_response_hours DecimalField(max_digits=6, decimal_places=2)` — target first response time in hours; stored as decimal (e.g. 0.5 = 30 min)
- `resolution_hours DecimalField(max_digits=6, decimal_places=2)` — target resolution time in hours
- `hours_mode CharField(10, choices=calendar/business, default=calendar)` — timer mode (business hours deferred; always calendar in this pass)
- `is_active BooleanField(default=True)`
- `created_at / updated_at`
Justification: Freshdesk sets Urgent/High/Medium/Low FRT + resolution in hours; Zendesk sets per-priority targets; HubSpot similarly. ServiceNow calls these "entitlements". All products ship 4 priority-mapped SLA rows.

### 3. `CaseComment` (new model)
Fields:
- `tenant FK core.Tenant`
- `case FK Case` (on_delete=CASCADE, related_name='comments')
- `kind CharField(10, choices=public/internal, default=public)` — internal = agent-only; public = visible to customer in portal
- `is_customer_reply BooleanField(default=False)` — True when posted by a portal customer (triggers status waiting→open)
- `body TextField` — comment content (agent internal note or public reply)
- `author FK settings.AUTH_USER_MODEL` (nullable, SET_NULL) — null for future system-generated replies
- `created_at DateTimeField(auto_now_add=True)`
Justification: Universal across all 10 surveyed products (Zendesk yellow-bg internal notes, Freshdesk private/public toggle, JSM internal/public comments, Help Scout notes/replies, Front). The internal/public distinction is the single most universal differentiator in help-desk threading.

### 4. `KbCategory` (new model)
Fields:
- `tenant FK core.Tenant`
- `name CharField(255)`
- `slug SlugField(160)` — for URL routing
- `parent FK self` (nullable, SET_NULL, related_name='children') — enables 2-level hierarchy (Category → Section)
- `order PositiveSmallIntegerField(default=0)` — display ordering
- `is_active BooleanField(default=True)`
- `created_at / updated_at`
unique_together: (tenant, slug)
Justification: Zoho Desk (Category > Sections > Subsections, 3 levels), JSM (categories), Freshdesk (categories + folders), Zendesk (categories + sections) — all have at least 2-level KB organization. The existing `KnowledgeArticle.category CharField` is replaced by this FK.

### 5. Enhance `KnowledgeArticle` (existing model — add/change fields)
Fields to add:
- `category FK KbCategory` (nullable, SET_NULL, related_name='articles') — replaces existing `category CharField(120)` field (migration: copy existing string to KbCategory.name, set FK)
- `helpful_count PositiveIntegerField(default=0)` — F()-incremented; not editable
- `not_helpful_count PositiveIntegerField(default=0)` — F()-incremented; not editable
- `public_token CharField(64, unique=True, blank=True, null=True)` — generated only when `visibility=external`; allows direct no-login URL sharing
Justification: Zoho Desk (likes/dislikes + usage metrics), JSM (voted-as-helpful = deflection metric), Zendesk (article votes), HubSpot KB votes. Category FK replaces the flat string with the new `KbCategory` hierarchy.

### 6. `CustomerPortalAccess` [CPORT-] (new model)
Fields:
- `tenant FK core.Tenant`
- `number CharField(20, editable=False)` — `CPORT-00001` via `next_number`
- `party FK core.Party` (the customer organization or contact) — (unique_together: tenant + party)
- `portal_user OneToOneField settings.AUTH_USER_MODEL` (nullable) — the Django User account for the customer; mirrors `PartnerPortalAccess.portal_user`
- `is_active BooleanField(default=True)`
- `accepted_at DateTimeField` (nullable) — system-set when customer first logs in / activates
- `notes CharField(255, blank=True)` — internal notes about this portal access grant
- `created_at / updated_at`
Justification: HubSpot (login-required customer portal showing own tickets + KB), Freshdesk (customer accounts with ticket access), Zoho Desk (client portal with moderated sign-up), JSM (customer-facing request portal). All require a mapping between the CRM customer identity (`Party`) and a login credential (`User`), which is exactly what `PartnerPortalAccess` (§1.12) models for partners — replicated here with helpdesk-specific access scope (view own cases, submit ticket, rate CSAT, access external KB).

---

## Deferred (later passes / integrations)

- **Email-to-ticket ingestion (IMAP/SMTP mailbox polling)** — data model (`Case.origin=email`) ships now; live email ingestion via Celery beat + IMAP is an external integration; out of scope for a single Django pass
- **Live chat / chatbot / omnichannel (WhatsApp, SMS, social)** — requires WebSocket or third-party channel integration; model `Case.origin` choices already capture these as values; delivery is deferred
- **AI answer-bot / ticket deflection (Freddy, Fin AI, Zia)** — needs LLM integration; deferred until AI pass
- **Macros / canned responses** — new `CannedResponse` table; wire into portal reply form; deferred to a helpdesk extension pass (WorkflowRule already handles automation)
- **Round-robin / skill-based assignment rules** — assignment-engine table; deferred to workflow extension
- **Merge duplicate cases** — self-FK `merged_into` on `Case`; deferred; low-priority
- **Business hours / holiday calendar for SLA timers** — `SlaPolicy.hours_mode` stub ships with `calendar` only; a separate `BusinessHours`/`HolidaySchedule` model and SLA-pause logic deferred to extension
- **SLA escalation notifications** — breach booleans ship now; email/in-app notification dispatch uses existing `WorkflowRule` engine (1.10); wire-in deferred to the notification/workflow pass
- **Article version history / rollback** — `KbArticleVersion` table; deferred; Zoho Desk and Zendesk feature but not essential for initial KB
- **Multi-language KB** — localization is a Module 0 cross-cutting concern; deferred
- **Community forums** — separate sub-product; deferred
- **Article-to-case suggestion / search relevance** — text-matching service to surface relevant KB on case creation; deferred to search/AI pass
- **CSAT survey email delivery** — CSAT data fields ship now; the actual post-close email delivery (auto-send when case closes) requires SMTP notification integration; deferred to notification pass
- **SLA escalation email to manager** — breach fields ship now; email delivery deferred to workflow/notification pass

---

## Source links used

- [Zendesk ticketing system features](https://www.zendesk.com/service/help-desk-software/ticketing-system/)
- [Freshdesk help desk software](https://www.freshworks.com/helpdesk/software/)
- [Freshdesk SLA policies — understanding](https://support.freshdesk.com/support/solutions/articles/37626-understanding-sla-policies)
- [Freshdesk public ticket links](https://support.freshdesk.com/support/solutions/articles/52265-providing-public-ticket-links-for-easy-access)
- [Freshdesk private notes](https://support.freshdesk.com/en/support/solutions/articles/37580-private-notes-for-internal-sharing)
- [Salesforce Service Cloud features overview](https://levelshift.com/blogs/salesforce-service-cloud-features)
- [Zoho Desk compare help desk software](https://www.zoho.com/desk/compare-helpdesk-software.html)
- [Zoho Desk knowledge base software](https://www.zoho.com/desk/knowledge-base-software.html)
- [Intercom SLA configuration](https://www.intercom.com/help/en/articles/6546152-set-slas-for-conversations-and-tickets)
- [Intercom help desk tickets](https://www.intercom.com/helpdesk/tickets)
- [HubSpot SLA management](https://www.hubspot.com/products/service/sla-management)
- [HubSpot customer portal](https://www.hubspot.com/products/service/customer-portal)
- [Jira Service Management features](https://www.atlassian.com/software/jira/service-management/features/service-desk)
- [JSM knowledge base categories](https://support.atlassian.com/jira-service-management-cloud/docs/feature-an-knowledge-base-article/)
- [ServiceNow CSM features](https://www.servicenow.com/products/customer-service-management.html)
- [Help Scout SLA policies](https://docs.helpscout.com/article/1751-create-and-manage-service-level-agreements-slas)
- [Zendesk SLA policy structure](https://support.zendesk.com/hc/en-us/articles/4408829459866-Defining-SLA-policies)
- [Zendesk internal notes vs public replies](https://www.eesel.ai/blog/zendesk-ticket-internal-vs-public-comment)
- [Zendesk article visibility / user segments](https://support.zendesk.com/hc/en-us/articles/4408824005914-Setting-view-permissions-on-articles-with-user-segments)
- [CSAT features in help desk software](https://surveymars.com/knowledge/the-6-best-help-desk-software-with-built-in-csat-surveys/)
