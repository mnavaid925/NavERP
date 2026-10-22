# Gap Register — Sub-module 8.16: Mobile Sales (Module 8: Sales Management System)

> Tracks features, third-party mobile integrations, and background streaming pipelines deferred to future passes or external services.

---

### GAP-sales-8.16-01: Native iOS (Swift) & Android (Kotlin) Compiled Mobile Apps
- **Owner**: `sales:8.16` (Mobile Sales)
- **Waiting For / Blocked On**: Mobile app store distribution credentials (Apple Developer Program / Google Play Console) and compilation toolchains (Xcode / Android Studio).
- **Status**: `- [ ]` Open / Unresolved
- **Done When**: Native application wrappers (iOS / Android) are compiled and packaged with offline SQLite caching layers, consuming NavERP JSON API endpoints and distributing via enterprise MDM or app stores.

---

### GAP-sales-8.16-02: Live WebRTC Two-Way Telephony Audio Engine
- **Owner**: `sales:8.16` / `sales:8.18` (Integration Hub)
- **Waiting For / Blocked On**: WebRTC media streaming gateway or Twilio / Asterisk SIP trunking infrastructure.
- **Status**: `- [ ]` Open / Unresolved
- **Done When**: Field reps can conduct live VoIP calls directly within the browser/app UI with two-way media streaming, audio recording storage, and real-time transcription, supplementing the native `tel:` click-to-dial flow.

---

### GAP-sales-8.16-03: Direct Apple APNs & Google FCM Push Socket Relay
- **Owner**: `sales:8.16` / `sales:8.18` (Integration Hub)
- **Waiting For / Blocked On**: APNs p8 certificate keys and Google Firebase Cloud Messaging (FCM) service account credentials.
- **Status**: `- [ ]` Open / Unresolved
- **Done When**: Dispatched `MobileDealAlert` records trigger automated background HTTP/2 pushes to Apple APNs and Google FCM push servers, causing native smartphone lock-screen banners to light up immediately.

---

### GAP-sales-8.16-04: High-Frequency Background GPS Fleet Tracking
- **Owner**: `sales:8.16` / `scm:4.4` (Fleet & Logistics)
- **Waiting For / Blocked On**: Real-time vehicle telematics / OBD-II device ingestion or continuous battery-optimized background location streaming services.
- **Status**: `- [ ]` Open / Unresolved
- **Done When**: Continuous real-time GPS breadcrumbs are tracked and mapped onto route maps to provide live rep location visualization, rather than point-in-time check-in/out timestamps.

---

### GAP-sales-8.16-05: Telephony Carrier Ringless Voicemail Server Injection
- **Owner**: `sales:8.16` / `crm:1.5` (Activity Management)
- **Waiting For / Blocked On**: Carrier telecommunications server injection gateway (e.g. Stratics Networks, Kixie, or Slybroadcast API).
- **Status**: `- [ ]` Open / Unresolved
- **Done When**: Field reps can drop pre-recorded voicemail audio directly into a customer's voicemail server without ringing their telephone handset, automatically logging outcome to `crm.CommunicationLog`.
