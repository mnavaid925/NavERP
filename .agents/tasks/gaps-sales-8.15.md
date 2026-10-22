# Gap Register — Sub-module 8.15: Contract & Subscription Management (Module 8: Sales Management System)

> Tracks features, third-party integrations, and automated pipelines deferred to future passes or external services.

---

### GAP-sales-8.15-01: Third-Party Electronic Signature Webhook Integration
- **Owner**: `sales:8.15` (Contract & Subscription Management)
- **Waiting For / Blocked On**: DocuSign / Adobe Sign / HelloSign API developer account credentials and secure webhook gateway endpoint in NavERP.
- **Status**: `- [ ]` Open / Unresolved
- **Done When**: E-signature envelopes can be dispatched via external REST API, multi-signer signature flows captured, and completed signature certificates auto-attached to `CustomerContract.document` via webhook callback.

---

### GAP-sales-8.15-02: High-Throughput Streaming Event Ingestion Engine
- **Owner**: `sales:8.15` (Contract & Subscription Management)
- **Waiting For / Blocked On**: Dedicated event streaming broker (Apache Kafka or AWS Kinesis) and asynchronous worker consumer.
- **Status**: `- [ ]` Open / Unresolved
- **Done When**: Sub-second customer application events (API calls, storage heartbeats, active sessions) are ingested in real-time and aggregated periodically into `UsageMeterRecord.reported_usage` without web process overhead.

---

### GAP-sales-8.15-03: Automated Payment Gateway Credit Card Processing
- **Owner**: `sales:8.15` / `accounting:2.6` (Payment Processing)
- **Waiting For / Blocked On**: Integration with Stripe Payments / Adyen vault tokens and customer saved payment methods.
- **Status**: `- [ ]` Open / Unresolved
- **Done When**: Recurring subscriptions trigger automatic credit card or ACH direct debit charges at term renewal, capturing payment confirmation and clearing accounting receivables.

---

### GAP-sales-8.15-04: AI-Assisted Contract Parser & Third-Party Redline OCR
- **Owner**: `sales:8.15` / `ai:23` (AI & Intelligent Automation)
- **Waiting For / Blocked On**: NavERP Module 23 AI model endpoints and document OCR pipeline.
- **Status**: `- [ ]` Open / Unresolved
- **Done When**: Customer-provided third-party contract PDF files can be uploaded, analyzed by LLM, extracting key liability terms, indemnification limits, and flagging non-standard clauses into `CustomerContract.special_terms` and `redline_notes`.

---

### GAP-sales-8.15-05: Automated Cloud Infrastructure Telemetry Ingestion for SLAs
- **Owner**: `sales:8.15` (Contract & Subscription Management)
- **Waiting For / Blocked On**: Cloud provider monitoring APIs (AWS CloudWatch / Datadog / New Relic / Pingdom).
- **Status**: `- [ ]` Open / Unresolved
- **Done When**: Automated daily or monthly polling calculates real uptime percentages, comparing against `ContractObligation.target_metric`, and auto-triggering breach service credit penalties when availability falls below contractual SLA benchmarks.
