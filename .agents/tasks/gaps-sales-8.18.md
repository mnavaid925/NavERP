# Gap Register — Sub-module 8.18: Integration & API Hub (Module 8: Sales Management System)

> Tracks features, transports, and execution runtimes deferred to future passes or external services.
> Entries are IMMUTABLE: close by ticking `- [x]` with the resolving commit SHA or passing test —
> never delete an entry.

---

### GAP-sales-8.18-01: Outbound HTTP network dispatcher & celery queue
- **Verbatim from plan**: Zero outbound HTTP is executed this pass; `SalesSyncRun.status = "simulated"` is the honest diagnostic state. Real live network synchronization requires an asynchronous worker queue (Celery/Redis or RQ) and network retry mechanics.
- **Owner**: `sales:8.18` (Integration Hub runtime)
- **Waiting For / Blocked On**: Production background queue worker infrastructure and tenant-configured network egress gateways.
- **Status**: `- [ ]` Open / Unresolved
- **Done When**: `SalesSyncRun` dispatches real outbound HTTP requests (REST/SOAP/GraphQL) via background tasks, handles exponential backoff, and records real remote HTTP status codes instead of `simulated`.

---

### GAP-sales-8.18-02: Live OAuth2 token refresh handshake & interactive authorization dance
- **Verbatim from plan**: Credentials (API tokens, client secrets, basic auth) are safely encrypted at rest using `apps.core.crypto.encrypt`. Live browser-based 3-legged OAuth2 authorization flows (redirect callbacks, PKCE, token refresh cron) are deferred.
- **Owner**: `sales:8.18` (OAuth2 Client)
- **Waiting For / Blocked On**: Public callback URL infrastructure and registered OAuth2 app credentials per vendor (Salesforce, HubSpot, Slack, DocuSign).
- **Status**: `- [ ]` Open / Unresolved
- **Done When**: An admin can initiate an interactive OAuth2 handshake from `SalesIntegrationConnector`, obtain access/refresh tokens through a callback route, and tokens auto-refresh upon expiry.

---

### GAP-sales-8.18-03: Real-time WebRTC/SIP telephony streaming & call audio recording
- **Verbatim from plan**: Telephony system connector logs call metadata and synchronizes activities. Real-time WebRTC audio streaming, softphone soft-client dialers, and audio file recording ingestion are deferred.
- **Owner**: `sales:8.18` / `sales:8.8` (Sales Activity Management)
- **Waiting For / Blocked On**: Telephony media server / WebRTC gateway and object storage bucket for large audio recordings.
- **Status**: `- [ ]` Open / Unresolved
- **Done When**: An in-browser dialer connects via WebRTC to Twilio/Zoom Phone, streams call audio, and automatically records audio attachments on sales activity logs.

---

### GAP-sales-8.18-04: Snowflake/BigQuery native direct-query pipeline
- **Verbatim from plan**: BI data warehouse feed sync jobs export transactional and aggregate snapshots in structured JSON. Direct Snowflake/BigQuery streaming ingestion or DB-to-DB JDBC pipes are deferred.
- **Owner**: `sales:8.18` / `bi` (Module 10 Business Intelligence)
- **Waiting For / Blocked On**: Native cloud warehouse SDKs and dedicated data lake replication infra.
- **Status**: `- [ ]` Open / Unresolved
- **Done When**: Sales snapshot datasets push directly into a Snowflake or BigQuery stage or warehouse table via authenticated database connectors.

---

### GAP-sales-8.18-05: Embedded in-browser biometric signing canvas & PandaDoc CLM iframe
- **Verbatim from plan**: E-signature connector tracks envelope IDs, remote recipient status, and signing milestones. Rendering interactive third-party CLM iframes or an embedded canvas for drawing biometric signatures in NavERP is deferred.
- **Owner**: `sales:8.18` / `sales:8.15` (Contract & Subscription Management)
- **Waiting For / Blocked On**: Embedded signing session tokens and iframe integration agreements with DocuSign/PandaDoc.
- **Status**: `- [ ]` Open / Unresolved
- **Done When**: Customers can complete legally binding signatures directly inside a secure NavERP customer portal view via embedded vendor widgets.
