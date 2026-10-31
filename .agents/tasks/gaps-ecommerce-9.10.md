# Gap Register — Sub-module 9.10: Marketing & Campaign Management (Module 9: eCommerce Management System, `ecommerce`)

## Summary
- **Module Slug**: `ecommerce` (Sub-module 9.10)
- **Status**: Complete — Built, reviewed (6 reviewers), fixed (25/25 findings resolved), 69 tests green.
- **Review File**: [`.claude/tasks/review-ecommerce-9.10.md`](file:///c:/xampp/htdocs/NavERP/.claude/tasks/review-ecommerce-9.10.md)

---

## Gaps & Deferred Items

### GAP-ecommerce-9.10-01: Outbound External Messaging Transports (SMTP / SMS / WebPush)
- **Owner**: `ecommerce` / Infrastructure
- **Waiting For / Blocked On**: Production cloud messaging gateways (AWS SES / SendGrid for email, Twilio / Sinch for SMS, APNs / FCM for push notifications).
- **Status**: `[~]` Deferred to production deployment / integration phase.
- **Done When**: Outbound celery or background task workers connect to live external messaging APIs and update `delivered_count`, `opened_count`, and `clicked_count` via webhooks.

### GAP-ecommerce-9.10-02: Live Social Catalog Webhooks & Bidirectional Meta/TikTok Sync
- **Owner**: `ecommerce` (Sub-module 9.10 & 9.11)
- **Waiting For / Blocked On**: External Meta Graph API & TikTok Shop API merchant account credentials.
- **Status**: `[~]` Deferred — Syndicated RFC-compliant product JSON feed endpoint (`ecommerce:social_commerce_feed`) is live and operational for feed consumption.
- **Done When**: Bidirectional webhooks receive off-platform purchases and map them into `EcommerceOrder`.

### GAP-ecommerce-9.10-03: Automated External Mass Payout Gateway (PayPal / Wise)
- **Owner**: `accounting` (Module 2) / `ecommerce` (Sub-module 9.10 & 9.11)
- **Waiting For / Blocked On**: Module 2 Payment Gateway Disbursal API connectors.
- **Status**: `[~]` Deferred — Commission calculations, approval gates, and clawbacks are fully tracked in 9.10 and ready for AP voucher posting.
- **Done When**: Batch payout execution posts directly to Module 2 GL cash clearing account and dispatches via PayPal/Wise API.
