# Gaps Register: eCommerce Sub-module 9.14 (Customer Service & Support)

> **Context**: Sub-module 9.14 delivers omnichannel customer helpdesk tickets (`CustomerSupportTicket`), self-service help center articles (`KnowledgeBaseArticle`), order issue & transit damage dispute claims (`OrderIssueClaim`), and customer satisfaction surveys (`CustomerSatisfactionSurvey`).
> All core CRUD operations, multi-tenancy isolation, SLA calculations, helpfulness voting, dispute adjudication, and closed-loop feedback workflows are implemented, tested (176 green tests), and documented.

---

### GAP-9.14-01: Real-Time WebSockets Live Chat Engine
- **Owner**: `ecommerce` / Frontend / Realtime Messaging Agent
- **Waiting For / Blocked On**: Platform-wide Django Channels / ASGI Redis infrastructure and WebSocket broker deployment.
- **Status**: `- [~]` Deferred (HTTP/HTMX views provide synchronous conversational messaging in this pass).
- **Done When**: Django Channels consumers enable bi-directional instant messaging between shopper and support staff with typing indicators and online presence tracking.

### GAP-9.14-02: Third-Party Telephony & Voice IVR Call Recording
- **Owner**: `ecommerce` / Telephony Integration Agent
- **Waiting For / Blocked On**: External provider API credentials (Twilio Flex / Aircall / Amazon Connect) and encrypted audio storage bucket configuration.
- **Status**: `- [~]` Deferred (Phone support channels currently record intake metadata and staff notes).
- **Done When**: Inbound/outbound call webhooks automatically attach call recordings, audio player widgets, and AI transcription summaries to `CustomerSupportTicket`.

### GAP-9.14-03: Direct Carrier Claims API Dispatch
- **Owner**: `ecommerce` / `scm` Logistics Integration Agent
- **Waiting For / Blocked On**: Carrier EDI/REST web services integration for FedEx, UPS, and DHL claims filing.
- **Status**: `- [~]` Deferred (Staff adjudicates and manages claims natively in NavERP).
- **Done When**: Approved `OrderIssueClaim` records with carrier tracking numbers can automatically dispatch electronic claim filings to carrier portals.

### GAP-9.14-04: LLM Generative Draft Assistance for Tickets
- **Owner**: `ecommerce` / `apps/ai` Module 23
- **Waiting For / Blocked On**: Module 23 (AI & Intelligent Automation) agent integration.
- **Status**: `- [~]` Deferred (Waiting for Module 23 AI provider pipeline).
- **Done When**: Support agents can generate suggested response drafts from ticket history and knowledge base articles using one-click prompt templates.
