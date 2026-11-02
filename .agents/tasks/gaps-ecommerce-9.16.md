# Gaps Register: eCommerce Sub-module 9.16 (Mobile Commerce)

> **Context**: Sub-module 9.16 delivers Progressive Web App (PWA) manifest generation and offline caching configurations (`MobileAppConfig`), mobile device registration and token tracking (`MobileDeviceRegistration`), rich mobile push notification campaigns with simulation and conversion attribution (`MobilePushCampaign`), physical store locator and circular geofencing proximity rules (`MobileLocationRule`), and a centralized Mobile Commerce Command Hub console (`mobile_hub`).
> All core CRUD operations, multi-tenancy isolation (`tenant=request.tenant`), sargable query optimization, compound unique constraint validations, PWA JSON endpoints, device telemetry pings, dispatch simulations, and role-based permissions are implemented, reviewed by 6 serial reviewers, burned down with 0 open findings, tested (135 dedicated tests in 9.16, 1,392 green tests across the full eCommerce test suite), and documented.

---

### GAP-9.16-01: Direct Persistent Push Socket Delivery Worker (APNs / FCM)
- **Owner**: `ecommerce` / Background Worker Infrastructure
- **Waiting For / Blocked On**: Celery/Redis background queue workers and production Apple Developer / Google Firebase Cloud Messaging credentials.
- **Status**: `- [~]` Deferred (Push campaigns generate structured notification payloads, track lifecycle states, simulate recipient dispatch, and record conversion attribution).
- **Done When**: Background worker service actively connects to APNs HTTP/2 and FCM v1 REST APIs to stream push payloads to physical devices.

### GAP-9.16-02: Apple Pay Merchant Certificate PKI Verification
- **Owner**: `ecommerce` / Payment Operations
- **Waiting For / Blocked On**: Production Apple Developer Merchant ID certificate (.cer / .pem) and domain association validation file hosted at `/.well-known/apple-developer-merchantid-domain-association`.
- **Status**: `- [~]` Deferred (Apple Pay merchant identifier and express checkout flags configured and exposed via mobile app config and manifest).
- **Done When**: Automated merchant validation handshake endpoint signs payment session tokens via cryptographic merchant certificates.

### GAP-9.16-03: Real-Time Omnichannel Messaging Webhooks (WhatsApp / WeChat Mini-Program)
- **Owner**: `ecommerce` / Sub-module 9.19 Integration & API Ecosystem
- **Waiting For / Blocked On**: Sub-module 9.19 webhook event router and messaging BSP accounts.
- **Status**: `- [~]` Deferred (Deep links and conversational checkout URLs generated for SMS, WhatsApp, and social commerce sharing).
- **Done When**: Inbound customer messages from WhatsApp Cloud API or WeChat Mini-Programs parse directly into Cart and Order checkout flows.

### GAP-9.16-04: Bluetooth Low Energy (BLE) Micro-Location Beacon Hardware Integration
- **Owner**: `ecommerce` / Mobile Hardware Client SDK
- **Waiting For / Blocked On**: Physical retail store BLE beacon hardware deployment (iBeacon / Eddystone) and mobile client native SDKs.
- **Status**: `- [~]` Deferred (Proximity rules and store locator operate via circular GPS geofencing with Haversine radius calculations).
- **Done When**: Mobile client app transmits detected BLE UUIDs/minor/major pairs to server to trigger in-store aisle-level micro-location promotions.

### GAP-9.16-05: Conversational AI Checkout Chatbot
- **Owner**: `ecommerce` / Module 23 (`apps/ai`) AI & Intelligent Automation
- **Waiting For / Blocked On**: Module 23 conversational LLM agent execution framework.
- **Status**: `- [~]` Deferred (Mobile hub provides conversational checkout link generator with preloaded cart parameters).
- **Done When**: Automated natural language assistant converses with shoppers in-app to build carts and trigger one-tap express checkouts.
