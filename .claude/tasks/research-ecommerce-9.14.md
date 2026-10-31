# Research — Sub-module 9.14: Customer Service & Support (Module 9 — eCommerce Management System, `ecommerce`)

- **Sub-module:** 9.14 Customer Service & Support
- **Module:** 9 eCommerce Management System
- **Target app:** `apps/ecommerce` (extending the existing app created in 9.1 and extended through 9.13)
- **Research date:** 2026-10-31
- **Phase:** 1 Research only
- **Output file:** `.claude/tasks/research-ecommerce-9.14.md`

---

## 1. Executive Summary & Domain Architecture

Sub-module 9.14 delivers the **Help Desk & Omnichannel Ticket Management, Live Chat & Conversational Bot Handoff, Self-Service Knowledge Base & FAQs, Order Inquiry & Issue Resolution (WISMO, Damage Claims, Refunds), and Customer Feedback & NPS Scoring Engine** for the NavERP eCommerce platform.

In retail and direct-to-consumer (DTC) eCommerce, customer support is fundamentally different from generic IT helpdesks or B2B CRM case management:
- **Order & Shipment Centricity**: Between 40% and 60% of all eCommerce support inquiries are **WISMO** ("Where Is My Order?") requests, followed by damaged package claims, missing components, return/exchange authorizations, and cancellation requests. Support tools must display real-time order status, carrier tracking, and line-item details directly inside the ticket workspace.
- **Deflection Through Self-Service**: Leading platforms (Richpanel, Gorgias) deflect up to 50% of routine inbound volume by enabling customers to look up order tracking, initiate damage claims with photo uploads, and request exchanges via branded self-service widgets without agent intervention.
- **Strict Response & Resolution SLAs**: Modern retail shoppers expect first response times within minutes for chat and hours for email. Clear SLA target calculation, countdown timers, and escalation triggers prevent customer churn and negative reviews.
- **Closed-Loop CSAT/NPS Feedback**: Post-resolution customer satisfaction (CSAT) scoring (1–5 stars) and store Net Promoter Scores (0–10 NPS) automatically trigger supervisory follow-ups for unhappy customers (detractors), salvaging at-risk customer relationships.

### Architectural Boundary Rulings (L28, L29, L36, L37):
1. **Catalog & Order Management Integration (L36/L37)**:
   - Tickets link directly to **`ecommerce.EcommerceOrder`** (`EORD-`, 9.5) and specific items to **`ecommerce.CatalogProduct`** (`EPRD-`, 9.1).
   - Return and exchange requests interface with **`ecommerce.ReturnMerchandiseAuthorization`** (`ERMA-`, 9.5).
   - Shopper identity attaches to **`ecommerce.CustomerAccountProfile`** (`ECAP-`, 9.6) and unified Core Spine **`core.Party`** and **`accounts.User`**. Guest shoppers are supported via verified email/phone lookups.
   - Financial adjustments and refunds are recorded as authorized resolution actions on claims; actual GL ledger postings are owned by Module 2 `accounting` (no duplicate financial ledgers, L29).
2. **Clear Sibling & Module Boundaries**:
   - **CRM 1.4 (`apps/crm/models/CustomerService/Cases.py`)**: B2B CRM customer support (`Case`, `CASE-`) centered on corporate accounts and sales agreements. 9.14 is consumer eCommerce support centered on orders, shipments, carts, and merchandise claims.
   - **HRM 3.36 (`apps/hrm/models/Helpdesk/Helpdeskticket.py`)**: Internal employee HR helpdesk (`HelpdeskTicket`, `TKT-`).
   - **Sub-module 9.5 (Order Management)**: Owns order fulfillment, tracking status, and warehouse return processing (`ERMA`). 9.14 provides the support ticket interface, customer claims intake, and dispute resolution.
   - **Sub-module 9.10 (Marketing Campaign)**: Owns outbound marketing campaigns. 9.14 owns transactional support interactions and CSAT survey distribution.
   - **Sub-module 9.13 (Reviews & UGC)**: Owns public on-page product reviews and ratings. 9.14 handles private 1-on-1 customer service inquiries and service feedback.
3. **Multi-Tenancy & Data Isolation**:
   All support tickets, knowledge articles, claims, and feedback records inherit from `TenantNumbered` (`apps/ecommerce/models/_base.py`) with strict `tenant` (`core.Tenant`) isolation.
4. **Base Class & Prefix Discipline**:
   All 4 models inherit from `TenantNumbered`, implementing thread-safe auto-number generation, audit timestamps, and strictly unique prefixes.

---

## 2. Repo State Checked First

### 2.1 Navigation & App Tree State
- **`apps/core/navigation.py`:**
  - `"9.1"` is live: Product Catalog Management (`EPRD`, `PVR`, `ECAT`, `PRL`)
  - `"9.2"` is live: Inventory & Stock Management (`EFC`, `EAL`, `EBK`, `ESYN`)
  - `"9.3"` is live: Pricing & Promotion Engine (`EDPR`, `ECPN`, `EFLS`, `ECPM`)
  - `"9.4"` is live: Shopping Cart & Checkout (`ECRT`, `ECKS`, `ESHP`, `EPMC`)
  - `"9.5"` is live: Order Management System (`EORD`, `EFUL`, `ERMA`, `EORT`)
  - `"9.6"` is live: Customer Account & Profile (`ECAP`, `ECAD`, `EWSL`, `ECPR`)
  - `"9.7"` is live: Search & Product Discovery (`ESYM`, `ESFC`, `ESMR`, `ESQL`)
  - `"9.8"` is live: Personalization & Recommendation (`ESEG`, `EREC`, `EPEX`, `ESBE`)
  - `"9.10"` is live: Marketing & Campaign Management (`EMCP`, `EAFF`, `EARC`, `ESEO`)
  - `"9.11"` is live: Marketplace & Multi-Vendor (`EMKV`, `EVPL`, `EVCS`, `EVPO`, `EVSO`)
  - `"9.12"` is live: Subscription & Recurring Commerce (`ESPL`, `ESUB`, `ESBX`, `ESRT`)
  - `"9.13"` is live: Reviews & User-Generated Content (`EPRV`, `EPQA`, `EUGC`, `ERVM`)
  - Sub-module `"9.14"` currently has no `LIVE_LINKS` entries yet.
- **`apps/ecommerce/` package structure:**
  - Sub-module 9.14 will add package directory `CustomerSupport/` across `models/`, `forms/`, `views/`, `urls/`, and `templates/ecommerce/customer_support/`.

### 2.2 As-Built Core Spine Entities (Grep Verified)
| Entity | Location | Status | 9.14 Usage |
|---|---|---|---|
| `core.Tenant` | `apps/core/models/Tenant.py:17` | **Present** | Strict workspace tenant isolation |
| `core.Party` | `apps/core/models/Party.py:5` | **Present** | Unified customer party identity |
| `core.Address` | `apps/core/models/Address.py:5` | **Present** | Verified shipping/billing address records |
| `core.ContactMethod` | `apps/core/models/ContactMethod.py:5` | **Present** | Customer email and phone contact points |
| `accounts.User` | `apps/accounts/models.py:52` | **Present** | Assigned support agents, team leads, moderators |
| `ecommerce.CustomerAccountProfile` | `apps/ecommerce/models/CustomerProfile/CustomerAccountProfiles.py:11` | **Present** | Registered shopper profile anchor |
| `ecommerce.EcommerceOrder` | `apps/ecommerce/models/OrderManagement/EcommerceOrders.py:10` | **Present** | Order context for support tickets and claims |
| `ecommerce.EcommerceOrderLine` | `apps/ecommerce/models/OrderManagement/EcommerceOrders.py:247` | **Present** | Line-item identification for damage/missing items |
| `ecommerce.CatalogProduct` | `apps/ecommerce/models/ProductCatalog/CatalogProducts.py:8` | **Present** | Target product for inquiries or knowledge links |
| `ecommerce.ReturnMerchandiseAuthorization` | `apps/ecommerce/models/OrderManagement/ReturnMerchandiseAuthorizations.py:9` | **Present** | Cross-link to return and exchange workflows |

### 2.3 Prefix Collision Verification
All candidate prefixes checked across all models in the repository via `git grep -E '\b(ESTK|EKBA|ECLM|ECSF)\b'`:
- `ESTK`: 0 collisions in repository (100% free)
- `EKBA`: 0 collisions in repository (100% free)
- `ECLM`: 0 collisions in repository (100% free)
- `ECSF`: 0 collisions in repository (100% free)

---

## 3. Commercial Leaders Surveyed

### 1. Gorgias (gorgias.com)
- **Positioning**: The premier customer service platform built natively for eCommerce brands (Shopify, BigCommerce, Magento).
- **Key Capabilities**: Deep customer sidebar displaying order history and tracking in real time, in-ticket refund/cancel/address change actions without leaving the interface, automated WISMO macro deflection, AI response suggestions, and SLA countdowns.

### 2. Richpanel (richpanel.com)
- **Positioning**: eCommerce self-service customer portal and helpdesk designed to emulate Amazon's automated customer service experience.
- **Key Capabilities**: Customer self-service portal deflecting 40–60% of routine inquiries, guided flows for order tracking, damage claims with photo uploads, exchange-first return workflows, and automated refund rules with policy-capped approval thresholds.

### 3. Gladly (gladly.com)
- **Positioning**: People-first conversational customer service platform organizing interactions around lifelong customer timelines rather than disconnected tickets.
- **Key Capabilities**: Continuous omnichannel customer conversation thread (email, chat, SMS, phone), live side-by-side cart and order journey context, unified AI and human agent collaboration notes, and topic-based message grouping.

### 4. Zendesk for Retail (zendesk.com)
- **Positioning**: Enterprise global leader in omnichannel ticketing, SLA management, and customer service operations.
- **Key Capabilities**: Configurable SLA policies with first-reply and resolution time tracking, automated breach escalations, canned macros with automated ticket updates, post-resolution CSAT surveys, and Zendesk Guide self-service knowledge base.

### 5. Kustomer (kustomer.com)
- **Positioning**: Modern CRM-first conversational support platform optimized for high-growth direct-to-consumer eCommerce brands.
- **Key Capabilities**: Chronological customer timeline incorporating orders as custom objects (KObjects), omnichannel conversation routing, instant order lookups by tracking number or email, and dynamic SLA sorting prioritizing soonest-to-expire tickets.

### 6. Help Scout (helpscout.com)
- **Positioning**: Human-centric customer support platform featuring shared inboxes, contextual docs, and integrated live chat.
- **Key Capabilities**: The Beacon embeddable widget providing in-context knowledge base search before ticket submission, shared agent collaboration inbox with private notes, live chat with handoff, and 1-click in-email CSAT surveys.

### 7. eDesk (edesk.com)
- **Positioning**: Multichannel eCommerce helpdesk built specifically for sellers operating across online stores and marketplaces (Amazon, eBay, Walmart, Shopify).
- **Key Capabilities**: Native order matching pulling order details directly into the ticket, marketplace 24-hour SLA countdown timers with breach alerts, automated inquiry categorization, and multilingual translation.

### 8. Freshdesk (Freshworks for eCommerce) (freshworks.com/freshdesk)
- **Positioning**: Scalable omnichannel customer support software with Freddy AI bots and scenario automations.
- **Key Capabilities**: AI-powered conversational chatbot with order lookup deflection, omnichannel ticketing, SLA management policies with escalation rules, knowledge base management, and customer satisfaction reporting.

---

## 4. Feature Catalog (Sub-Module 9.14 Only)

### 4.1 Help Desk & Ticket Management
- **Omnichannel Inbound Ingestion** — Consolidate customer inquiries from email, web contact forms, storefront live chat, customer self-service portal, and marketplaces into a centralized queue · seen in: Gorgias, Zendesk, eDesk · priority: `table-stakes` · spine: new table `CustomerSupportTicket` · buildable now.
- **Priority & SLA Target Tracking** — Dynamic calculation of first-response due time and resolution due time based on ticket priority (Low, Medium, High, Urgent), with automated SLA breach detection and countdown tracking · seen in: Zendesk, eDesk, Kustomer · priority: `table-stakes` · spine: new table `CustomerSupportTicket` · buildable now.
- **Lifecycle Ticket Status Workflow** — Structured ticket lifecycle progression (`new` -> `open` -> `pending_customer` -> `waiting_carrier` -> `resolved` -> `closed`, plus `cancelled`) · seen in: Gorgias, Zendesk, Help Scout · priority: `table-stakes` · spine: new table `CustomerSupportTicket` · buildable now.
- **In-Ticket eCommerce Order Context** — Direct side-by-side linking of the ticket to the customer's `EcommerceOrder`, displaying order date, shipping status, carrier tracking link, total, and line items without tab-switching · seen in: Gorgias, Richpanel, eDesk · priority: `table-stakes` · spine: FK to `ecommerce.EcommerceOrder` · buildable now.
- **Automated Queue Routing & Agent Assignment** — Route tickets by category (shipping, returns, billing, technical) to specific agents or teams · seen in: Zendesk, Freshdesk · priority: `common` · spine: FK to `accounts.User` · buildable now.
- **Internal Agent Notes & Collaboration** — Private internal notes within the ticket view invisible to the shopper, enabling cross-departmental coordination · seen in: Help Scout, Gorgias, Gladly · priority: `common` · spine: new table `CustomerSupportTicket` · buildable now.

### 4.2 Live Chat & Chatbot
- **Live Chat Session & Channel Tagging** — Capture live chat conversations with session parameters, customer source URL, and referrer · seen in: Gorgias, Help Scout, Freshdesk · priority: `table-stakes` · spine: new table `CustomerSupportTicket` (channel="chat") · buildable now.
- **Chatbot Order Lookup & Deflection** — Automated bot workflow that looks up order status via order number and postal code/email, deflecting human agent involvement · seen in: Richpanel, Gorgias, Freshdesk · priority: `common` · spine: services querying `ecommerce.EcommerceOrder` · buildable now.
- **Bot-to-Human Agent Handoff** — Seamless transition from automated chatbot dialogue to live support agent with full transcript context · seen in: Gorgias, Gladly, Help Scout · priority: `common` · spine: new table `CustomerSupportTicket` · buildable now.

### 4.3 Self-Service Knowledge Base
- **Knowledge Article & FAQ Publishing** — Structured repository of articles, FAQs, shipping policies, sizing charts, and return guides categorized with SEO slugs · seen in: Zendesk Guide, Help Scout Docs, Freshdesk · priority: `table-stakes` · spine: new table `KnowledgeBaseArticle` · buildable now.
- **Deflection & Content Feedback Loop** — Track article view counts and capture customer votes ("Was this helpful? Yes/No") to evaluate deflection efficiency · seen in: Zendesk, Help Scout · priority: `common` · spine: new table `KnowledgeBaseArticle` · buildable now.
- **Target Audience & Featured Content** — Control article visibility by audience segment (public storefront, registered members, B2B wholesale) and pin critical policies · seen in: Help Scout Docs, Zendesk · priority: `common` · spine: new table `KnowledgeBaseArticle` · buildable now.
- **Instant Search Keyword Indexing** — Keyword and search synonym tagging enabling rapid auto-complete search within self-service widgets · seen in: Zendesk, Help Scout · priority: `table-stakes` · spine: new table `KnowledgeBaseArticle` · buildable now.

### 4.4 Order Inquiry & Issue Resolution
- **WISMO (Where Is My Order) Automation** — Quick order lookup displaying carrier tracking number, fulfillment status, and carrier delivery updates · seen in: Gorgias, Richpanel, Kustomer · priority: `table-stakes` · spine: service integration with `ecommerce.EcommerceOrder` & `OrderFulfillment` · buildable now.
- **Structured Damage & Defect Claims** — Formal claims submission for damaged in transit, defective merchandise, wrong items shipped, or missing components with photographic evidence and claimed amounts · seen in: Richpanel, Gorgias · priority: `table-stakes` · spine: new table `OrderIssueClaim` · buildable now.
- **Carrier Loss & Dispute Tracking** — Manage investigations for lost-in-transit shipments with carrier dispute reference numbers and follow-up notes · seen in: Richpanel, eDesk · priority: `common` · spine: new table `OrderIssueClaim` · buildable now.
- **Policy-Capped Resolution Authorizations** — Authorize claims resolutions (reshipment replacement, full refund, partial refund, or store credit) with supervisor approval thresholds · seen in: Richpanel, Gorgias · priority: `common` · spine: new table `OrderIssueClaim` · buildable now.
- **Return Workflow Handoff** — Cross-reference authorized returns to `ecommerce.ReturnMerchandiseAuthorization` for warehouse check-in · seen in: Richpanel, Gorgias · priority: `table-stakes` · spine: FK to `ecommerce.ReturnMerchandiseAuthorization` · buildable now.

### 4.5 Customer Feedback & NPS
- **Automated Post-Resolution CSAT Survey** — Trigger 1–5 star customer satisfaction surveys upon ticket resolution, capturing satisfaction with agent response and issue resolution · seen in: Zendesk, Help Scout, Freshdesk · priority: `table-stakes` · spine: new table `CustomerSatisfactionSurvey` · buildable now.
- **Store-Wide NPS (Net Promoter Score)** — Capture 0–10 scale Net Promoter Scores (Promoters 9–10, Passives 7–8, Detractors 0–6) to evaluate brand loyalty · seen in: Gorgias, Zendesk · priority: `common` · spine: new table `CustomerSatisfactionSurvey` · buildable now.
- **Closed-Loop Detractor Escalation Workflow** — Automatically flag negative feedback (ratings ≤ 2 stars or NPS detractors) for supervisor intervention with follow-up tracking · seen in: Zendesk, Help Scout · priority: `differentiator` · spine: new table `CustomerSatisfactionSurvey` · buildable now.
- **Support Agent Performance Analytics** — Benchmark agent satisfaction ratings, average response times, and first-contact resolution rates · seen in: Zendesk, Freshdesk, Help Scout · priority: `common` · spine: new table `CustomerSatisfactionSurvey` · buildable now.

### 4.6 Beyond the Bullets (Modern eCommerce Standards)
- **Customer Lifetime Value (LTV) Badge in Support** — Surface total customer lifetime spend and VIP status directly in the ticket header to prioritize high-value shoppers · seen in: Gorgias, Gladly · priority: `common` · spine: reads from `ecommerce.CustomerAccountProfile` · buildable now.
- **Strict Multi-Tenant Scoping & GDPR Redaction** — Ensure customer conversations, claims, and surveys are strictly tenant-isolated and support privacy redactions · seen in: Zendesk, Gorgias · priority: `table-stakes` · spine: `TenantNumbered` inheritance · buildable now.

---

## 5. Recommended Build Scope (This Pass — 4 Models)

To fulfill all 5 feature bullets of Sub-module 9.14 while maintaining the strictly verified 1–4 model build unit, the following 4 tenant-scoped models are recommended:

### 1. `CustomerSupportTicket` (`NUMBER_PREFIX = "ESTK"`)
- **Justified by**: Help Desk & Ticket Management, Live Chat & Chatbot (Channel tagging, Bot handoff), Order Inquiry Context.
- **Inheritance**: `TenantNumbered` (`apps/ecommerce/models/_base.py`)
- **Key Fields**:
  - `number`: Auto-generated identifier (`ESTK-#####`).
  - `customer`: FK to `ecommerce.CustomerAccountProfile` (`on_delete=models.SET_NULL`, null=True, blank=True, related_name="support_tickets").
  - `order`: FK to `ecommerce.EcommerceOrder` (`on_delete=models.SET_NULL`, null=True, blank=True, related_name="support_tickets").
  - `assigned_agent`: FK to `settings.AUTH_USER_MODEL` (`on_delete=models.SET_NULL`, null=True, blank=True, related_name="assigned_ecommerce_tickets").
  - `subject`: `CharField(max_length=255)`.
  - `customer_name`: `CharField(max_length=150)` (captures guest name if unauthenticated).
  - `customer_email`: `EmailField()` (captures contact email).
  - `customer_phone`: `CharField(max_length=32, blank=True)`.
  - `channel`: `CharField(max_length=20, choices=CHANNEL_CHOICES, default="email")` (`email`, `chat`, `web_form`, `portal`, `marketplace`, `phone`).
  - `category`: `CharField(max_length=30, choices=CATEGORY_CHOICES, default="general")` (`order_tracking_wismo`, `return_refund`, `damaged_defective`, `shipping_delivery`, `product_inquiry`, `payment_billing`, `account_access`, `general`).
  - `priority`: `CharField(max_length=15, choices=PRIORITY_CHOICES, default="medium")` (`low`, `medium`, `high`, `urgent`).
  - `status`: `CharField(max_length=25, choices=STATUS_CHOICES, default="new")` (`new`, `open`, `pending_customer`, `waiting_carrier`, `resolved`, `closed`, `cancelled`).
  - `initial_message`: `TextField()` (description of the customer's initial inquiry).
  - `resolution_summary`: `TextField(blank=True)` (staff explanation of how the issue was resolved).
  - `internal_notes`: `TextField(blank=True)` (internal staff-only collaborative notes).
  - `sla_first_response_due_at`: `DateTimeField(null=True, blank=True)`.
  - `sla_resolution_due_at`: `DateTimeField(null=True, blank=True)`.
  - `first_responded_at`: `DateTimeField(null=True, blank=True)`.
  - `resolved_at`: `DateTimeField(null=True, blank=True)`.
  - `is_sla_breached`: `BooleanField(default=False)`.
  - `is_bot_handled`: `BooleanField(default=False)`.
  - `bot_handoff_reason`: `CharField(max_length=100, blank=True)`.

### 2. `KnowledgeBaseArticle` (`NUMBER_PREFIX = "EKBA"`)
- **Justified by**: Self-Service Knowledge Base, FAQ Management, Troubleshooting Guides, AI-Powered Search Assistance.
- **Inheritance**: `TenantNumbered` (`apps/ecommerce/models/_base.py`)
- **Key Fields**:
  - `number`: Auto-generated identifier (`EKBA-#####`).
  - `title`: `CharField(max_length=255)`.
  - `slug`: `SlugField(max_length=255)`.
  - `category`: `CharField(max_length=30, choices=CATEGORY_CHOICES, default="shipping_delivery")` (`shipping_delivery`, `returns_refunds`, `ordering_payment`, `product_sizing`, `account_security`, `troubleshooting`, `promotions`).
  - `summary`: `TextField(max_length=500)` (plain text snippet for search results).
  - `content`: `TextField()` (full rich/markdown documentation content).
  - `status`: `CharField(max_length=15, choices=STATUS_CHOICES, default="draft")` (`draft`, `published`, `archived`).
  - `target_audience`: `CharField(max_length=25, choices=AUDIENCE_CHOICES, default="all_visitors")` (`all_visitors`, `registered_customers`, `b2b_wholesale`).
  - `is_featured`: `BooleanField(default=False)` (pins article to top of help center).
  - `view_count`: `PositiveIntegerField(default=0)`.
  - `helpful_votes`: `PositiveIntegerField(default=0)`.
  - `unhelpful_votes`: `PositiveIntegerField(default=0)`.
  - `keywords`: `CharField(max_length=255, blank=True)` (comma-delimited keywords for search autocomplete).
  - `author`: FK to `settings.AUTH_USER_MODEL` (`on_delete=models.SET_NULL`, null=True, blank=True, related_name="authored_ecommerce_articles").

### 3. `OrderIssueClaim` (`NUMBER_PREFIX = "ECLM"`)
- **Justified by**: Order Inquiry & Issue Resolution (WISMO escalations, damage claims, and refund processing).
- **Inheritance**: `TenantNumbered` (`apps/ecommerce/models/_base.py`)
- **Key Fields**:
  - `number`: Auto-generated identifier (`ECLM-#####`).
  - `order`: FK to `ecommerce.EcommerceOrder` (`on_delete=models.CASCADE, related_name="issue_claims"`).
  - `customer`: FK to `ecommerce.CustomerAccountProfile` (`on_delete=models.SET_NULL`, null=True, blank=True, related_name="order_claims"`).
  - `ticket`: FK to `CustomerSupportTicket` (`on_delete=models.SET_NULL`, null=True, blank=True, related_name="order_claims"`).
  - `claim_type`: `CharField(max_length=30, choices=CLAIM_TYPE_CHOICES, default="damaged_item")` (`damaged_item`, `lost_in_transit`, `wrong_item`, `missing_parts`, `defective_product`, `late_delivery`).
  - `status`: `CharField(max_length=25, choices=STATUS_CHOICES, default="submitted")` (`submitted`, `under_review`, `carrier_investigation`, `approved`, `rejected`, `completed`).
  - `claimed_amount`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))`.
  - `approved_amount`: `DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))`.
  - `resolution_action`: `CharField(max_length=30, choices=RESOLUTION_CHOICES, default="pending")` (`pending`, `replacement_reship`, `full_refund`, `partial_refund`, `store_credit`, `repair`, `rejected`).
  - `carrier_tracking_number`: `CharField(max_length=100, blank=True)`.
  - `photo_evidence_url`: `URLField(max_length=500, blank=True)` (link to uploaded image evidence of damaged box/item).
  - `customer_notes`: `TextField()`.
  - `decision_notes`: `TextField(blank=True)` (staff justification for approval/rejection).
  - `reviewed_by`: FK to `settings.AUTH_USER_MODEL` (`on_delete=models.SET_NULL`, null=True, blank=True, related_name="reviewed_order_claims"`).
  - `resolved_at`: `DateTimeField(null=True, blank=True)`.

### 4. `CustomerSatisfactionSurvey` (`NUMBER_PREFIX = "ECSF"`)
- **Justified by**: Customer Feedback & NPS, Satisfaction Scoring, Closed-Loop Feedback Workflows.
- **Inheritance**: `TenantNumbered` (`apps/ecommerce/models/_base.py`)
- **Key Fields**:
  - `number`: Auto-generated identifier (`ECSF-#####`).
  - `ticket`: FK to `CustomerSupportTicket` (`on_delete=models.SET_NULL`, null=True, blank=True, related_name="satisfaction_surveys"`).
  - `order`: FK to `ecommerce.EcommerceOrder` (`on_delete=models.SET_NULL`, null=True, blank=True, related_name="satisfaction_surveys"`).
  - `customer`: FK to `ecommerce.CustomerAccountProfile` (`on_delete=models.SET_NULL`, null=True, blank=True, related_name="satisfaction_surveys"`).
  - `survey_type`: `CharField(max_length=25, choices=SURVEY_TYPE_CHOICES, default="ticket_csat")` (`ticket_csat`, `order_delivery_csat`, `storefront_nps`).
  - `rating_score`: `PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(10)])` (1–5 for CSAT, 0–10 for NPS).
  - `sentiment`: `CharField(max_length=15, choices=SENTIMENT_CHOICES, default="neutral")` (`positive`, `neutral`, `negative`).
  - `feedback_comment`: `TextField(blank=True)`.
  - `agent_rated`: FK to `settings.AUTH_USER_MODEL` (`on_delete=models.SET_NULL`, null=True, blank=True, related_name="rated_support_surveys"`).
  - `follow_up_status`: `CharField(max_length=25, choices=FOLLOW_UP_CHOICES, default="not_required")` (`not_required`, `pending_review`, `contacted_customer`, `resolved_closed_loop`).
  - `follow_up_notes`: `TextField(blank=True)`.
  - `reviewed_by`: FK to `settings.AUTH_USER_MODEL` (`on_delete=models.SET_NULL`, null=True, blank=True, related_name="reviewed_support_surveys"`).

---

## 6. Belongs to Sibling Sub-Modules (Parked, Not Scoped Here)

- **Return Merchandise Authorizations (RMA) & Restocking** (`ERMA-`) → Belongs to **9.5 Order Management System** (already built).
- **Public Product Reviews, Ratings & Community Q&A** (`EPRV-`, `EPQA-`, `EUGC-`) → Belongs to **9.13 Reviews & UGC** (already built).
- **Outbound Marketing Broadcasts & Abandoned Cart Recovery** (`EMCP-`) → Belongs to **9.10 Marketing & Campaign Management** (already built).
- **Marketplace Vendor Direct Inquiries & Dispute Resolution** (`EMKV-`) → Belongs to **9.11 Marketplace Management** (already built).
- **B2B Corporate Account Case Management** (`CASE-`) → Belongs to **CRM 1.4 Customer Service & Support** (already built).
- **Internal Employee Helpdesk Ticketing** (`TKT-`) → Belongs to **HRM 3.36 Helpdesk** (already built).

---

## 7. Deferred (Later Passes / Integrations)

- **Real-Time WebSockets Live Chat Engine**: Django Channels or third-party WebSocket broker for sub-second chat updates. The data model supports chat transcripts and session flags today; full live socket push runs later.
- **Third-Party Telephony / IVR Integration**: Inbound/outbound voice call logs (Twilio, Aircall).
- **Automated External Carrier Claims API**: EDI / API filing of shipping claims directly with FedEx, UPS, or DHL.
- **AI Large Language Model (LLM) Draft Generation**: Live OpenAI/Anthropic API connectors for automated answer drafting.
