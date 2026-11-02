# Research — Sub-module 9.16: Mobile Commerce (Module 9 — eCommerce Management System, `ecommerce`)

- **Sub-module:** 9.16 Mobile Commerce
- **Module:** 9 eCommerce Management System
- **Target app:** `apps/ecommerce` (extending the existing app created in 9.1 and extended through 9.15)
- **Research date:** 2026-11-02
- **Phase:** 1 Research only
- **Output file:** `.claude/tasks/research-ecommerce-9.16.md`

---

## 1. Executive Summary & Domain Architecture

Sub-module 9.16 delivers the **Mobile Commerce (mCommerce)** architecture for the NavERP eCommerce platform, providing unified governance for **Progressive Web Apps (PWA), Native Mobile Apps (iOS & Android), Mobile Wallet Payment Integrations (Apple Pay, Google Pay), Location-Based Services (Store Locator, In-Store Mode, Geofencing), and Social & Messaging Commerce (WhatsApp Business, WeChat Mini-Programs, Conversational Checkout)**.

In modern retail and Direct-to-Consumer (DTC) commerce, mobile devices account for over **70% of digital traffic and 60%+ of digital sales**. However, mobile browser conversion rates historically lag desktop by 40–50% due to slow page loads, difficult payment form fills, and friction-laden authentication. Market-leading mobile commerce platforms (such as Tapcart, Poq, NewStore, and PredictSpring) solve this by closing the gap between web, native apps, and brick-and-mortar stores:

1. **Progressive Web App (PWA) Foundation**:
   - Modern PWAs utilize a Web App Manifest (`manifest.json`) and Service Workers to provide an app-like experience directly within the mobile browser without requiring app store friction.
   - Key capabilities include home-screen installability, App Shell caching, offline catalog browsing with custom fallbacks, and Web Push notifications via the W3C Push API.
2. **Native App Excellence & Push Re-engagement**:
   - Native mobile apps (built via Swift/iOS and Kotlin/Android or React Native/Flutter) deliver 3x higher conversion rates and 2x higher retention than mobile web.
   - Native apps enable biometric authentication (Face ID, Touch ID, Android Biometrics), instant zero-friction checkout, and high-converting lockscreen Push Notifications (with deep links directly into products, collections, or flash sales) bypassing crowded email inboxes and social algorithms.
3. **Frictionless Mobile Payments & Express Wallets**:
   - Eliminating manual credit card entry is the single largest lever for mobile conversion. Modern mobile commerce orchestrates native express wallets—Apple Pay, Google Pay, Samsung Pay, and in-app stored balances—allowing one-tap biometrically verified checkouts in under 5 seconds.
4. **Location-Based Omnichannel Services (Proximity & Store Mode)**:
   - Modern enterprise retailers connect physical brick-and-mortar storefronts with digital mobile apps. 
   - Location-aware apps monitor user proximity via GPS and geofences. When a shopper enters a geofenced retail radius, the app triggers hyper-contextual "Store Mode" with local store inventory visibility, barcode scanning for reviews, and location-targeted promotions (Poq, NewStore).
5. **Conversational & Social Messaging Commerce**:
   - Customers increasingly interact and complete purchases within messaging channels like WhatsApp Business, WeChat, and Instagram DM.
   - Conversational commerce enables syncing structured product catalogs into messaging platforms, sending interactive multi-product carts, and dispatching pre-filled instant checkout links directly inside conversation threads (SleekFlow, charles).

### Architectural Boundary Rulings (L28, L29, L36, L37):
1. **Multi-Tenancy & Data Isolation (L28, L36)**:
   - All mobile commerce models inherit from `TenantNumbered` (`apps/ecommerce/models/_base.py`) with strict `tenant` (`core.Tenant`) isolation.
   - Device tokens, push campaigns, geofence rules, and app configurations are strictly partitioned by tenant.
2. **Financial Ledger & Payment Ownership (L29)**:
   - Module 9 `ecommerce` owns mobile payment method configuration and checkout session orchestration.
   - Module 2 `accounting` remains the authoritative financial general ledger. No double-entry bookkeeping tables exist in `ecommerce`; completed orders record transactions referencing verified accounting ledgers.
3. **Physical Locations & Warehouse Alignment**:
   - Sub-module 9.2 built `FulfillmentCenter` (`apps/ecommerce/models/InventoryStock/FulfillmentCenters.py`), which includes `center_type="retail_store"` and `supports_customer_pickup=True`.
   - 9.16 Location-Based Services anchors to `FulfillmentCenter` to connect digital store locators and geofences with physical retail nodes without duplicating warehouse entities.
4. **Customer Profile & Party Spine Integration**:
   - Mobile device registrations link to `ecommerce.CustomerAccountProfile` (built in 9.6) and unified identity `core.Party` (built in Module 0).
5. **Campaign & Deep-Link Routing**:
   - Push campaigns and geofence proximity alerts deep-link to verified catalog entities: `ecommerce.CatalogProduct` (9.1), `ecommerce.StoreCategory` (9.1), and `ecommerce.CouponPromotion` (9.3).

---

## 2. Repo State Checked First

### 2.1 Navigation & App Tree State
- **`apps/core/navigation.py` status:**
  - `"9.1"` is live: Product Catalog Management (`EPRD`, `PVR`, `ECAT`, `PRL`)
  - `"9.2"` is live: Inventory & Stock Management (`EFC`, `EAL`, `EBK`, `ESYN`)
  - `"9.3"` is live: Pricing & Promotion Engine (`EDPR`, `ECPN`, `EFLS`, `ECPM`)
  - `"9.4"` is live: Shopping Cart & Checkout (`ECRT`, `ECKS`, `ESHP`, `EPMC`)
  - `"9.5"` is live: Order Management System (`EORD`, `EFUL`, `ERMA`, `EORT`)
  - `"9.6"` is live: Customer Account & Profile (`ECAP`, `ECAD`, `EWSL`, `ECPR`)
  - `"9.7"` is live: Search & Product Discovery (`ESYM`, `ESFC`, `ESMR`, `ESQL`)
  - `"9.8"` is live: Personalization & Recommendation (`ESEG`, `EREC`, `EPEX`, `ESBE`)
  - `"9.9"` is live: Content Management System (`EPAG`, `EBLG`, `EBLK`, `EMED`)
  - `"9.10"` is live: Marketing & Campaign Management (`EMCP`, `EAFF`, `EARC`, `ESEO`)
  - `"9.11"` is live: Marketplace & Multi-Vendor (`EMKV`, `EVPL`, `EVCS`, `EVPO`, `EVSO`)
  - `"9.12"` is live: Subscription & Recurring Commerce (`ESPL`, `ESUB`, `ESBX`, `ESRT`)
  - `"9.13"` is live: Reviews & User-Generated Content (`EPRV`, `EPQA`, `EUGC`, `ERVM`)
  - `"9.14"` is live: Customer Service & Support (`ESTK`, `EKBA`, `ECLM`, `ECSF`)
  - `"9.15"` is live: Analytics & Business Intelligence (`EDSS`, `ECCM`, `EPMM`, `EATT`)
  - **Sub-module `"9.16"` Mobile Commerce** is the target under construction.
- **`apps/ecommerce/` package structure:**
  - Sub-module 9.16 will introduce package directory `MobileCommerce/` across `models/`, `forms/`, `views/`, `urls/`, and templates directory `templates/ecommerce/mobile/`.

### 2.2 As-Built Core Spine Entities (Grep Verified)
| Entity | Location | Status | 9.16 Usage |
|---|---|---|---|
| `core.Tenant` | `apps/core/models/Tenant.py:17` | **Present** | Strict workspace tenant isolation |
| `core.Party` | `apps/core/models/Party.py:5` | **Present** | Unified customer party identity for device registrations |
| `accounts.User` | `apps/accounts/models.py:52` | **Present** | Push campaign creator, mobile config administrator |
| `ecommerce.CustomerAccountProfile` | `apps/ecommerce/models/CustomerProfile/CustomerAccountProfiles.py:11` | **Present** | Mobile customer account linkage and biometric binding |
| `ecommerce.CatalogProduct` | `apps/ecommerce/models/ProductCatalog/CatalogProducts.py:8` | **Present** | Deep-link destination for push notifications & catalog sync |
| `ecommerce.StoreCategory` | `apps/ecommerce/models/ProductCatalog/StoreCategories.py:9` | **Present** | Category deep-link destination for mobile campaigns |
| `ecommerce.CouponPromotion` | `apps/ecommerce/models/PricingPromotion/CouponPromotions.py:10` | **Present** | Geofence proximity coupon & push campaign promotion |
| `ecommerce.FulfillmentCenter` | `apps/ecommerce/models/InventoryStock/FulfillmentCenters.py:6` | **Present** | Physical retail store anchor for store locator and geofencing |
| `ecommerce.PaymentMethodConfig` | `apps/ecommerce/models/CartCheckout/PaymentMethods.py:8` | **Present** | Mobile wallet and express checkout gateway provider |
| `ecommerce.EcommerceOrder` | `apps/ecommerce/models/OrderManagement/EcommerceOrders.py:10` | **Present** | Mobile order tracking and transactional push alerts |
| `ecommerce.Cart` | `apps/ecommerce/models/CartCheckout/Carts.py:11` | **Present** | Abandoned cart recovery push notifications and mobile web sync |

### 2.3 Prefix Collision Verification
All candidate prefixes checked across all models in the repository via `git grep -E '\b(EMAC|EMDR|EMPC|EMLR|EMGF|EMCC)\b'`:
- `EMAC`: 0 collisions in repository (**100% free**)
- `EMDR`: 0 collisions in repository (**100% free**)
- `EMPC`: 0 collisions in repository (**100% free**)
- `EMLR`: 0 collisions in repository (**100% free**)
- `EMGF`: 0 collisions in repository (**100% free**)
- `EMCC`: 0 collisions in repository (**100% free**)

Existing `EM*` prefixes in `apps/ecommerce`:
- `EMED`: MediaAssets (9.9)
- `EMCP`: MarketingCampaigns (9.10)
- `EMKV`: MarketplaceVendors (9.11)
No collisions exist with any proposed prefix.

---

## 3. Commercial Leaders Surveyed

### 1. Tapcart (tapcart.com)
- **Positioning**: The market leader in turn-key native iOS and Android mobile app development for direct-to-consumer (DTC) brands.
- **Key Capabilities**:
  - Drag-and-drop native mobile app layout builder with real-time preview.
  - Native 1-step checkout supporting Apple Pay, Google Pay, and Shop Pay with biometric Face ID authentication.
  - Automated push notification flows (abandoned cart, back-in-stock, price drop alerts).
  - TapAI for push copy generation and send-time optimization.
  - Deep-link architecture mapping push payloads directly to products, collections, and custom app views.
  - App Clips support enabling instant lightweight app experiences without full installation.
- **Feature Reference**: https://tapcart.com/features

### 2. Shopney (shopney.co)
- **Positioning**: Specialized mobile app builder for eCommerce stores focusing on conversational in-app clienteling and design flexibility.
- **Key Capabilities**:
  - In-app live chat connecting mobile shoppers directly with store support agents.
  - Rich push notifications with image attachments, emojis, and countdown timers.
  - Abandoned cart push notification automations with personalized item thumbnails.
  - Multi-currency, multi-language localization engine supporting regional mobile users.
  - Native Apple Pay and Google Pay express checkout integration.
- **Feature Reference**: https://shopney.co/features

### 3. Poq Commerce (poqcommerce.com)
- **Positioning**: MACH-certified, enterprise-grade native mobile app platform powering global omnichannel retailers (Cotton On, Belk, Missguided).
- **Key Capabilities**:
  - **In-Store Mode**: Dynamic app UI transformation triggered upon entering a physical store perimeter.
  - Geofence and proximity monitoring utilizing device location permissions.
  - In-store barcode scanner allowing shoppers to check local store stock, read verified reviews, and view alternative colors/sizes.
  - Click-and-collect (BOPIS) order tracking with curbside check-in notifications.
  - Native biometric login (Touch ID, Face ID, Android BiometricPrompt).
  - Composable API-first app commerce engine.
- **Feature Reference**: https://poqcommerce.com/platform

### 4. NewStore (newstore.com)
- **Positioning**: Omnichannel store and consumer mobile app platform bridging digital storefronts with brick-and-mortar retail execution.
- **Key Capabilities**:
  - Integrated consumer shopping app and store associate clienteling system.
  - Real-time store locator with live inventory availability per physical retail branch.
  - Geolocation-based proximity alerts and drive-to-store promotional messaging.
  - Frictionless mobile checkout with Apple Pay and contactless payment processing.
  - Curbside pickup arrival notifications alerting store fulfillment teams in real time.
- **Feature Reference**: https://newstore.com/platform/consumer-app

### 5. PredictSpring (predictspring.com)
- **Positioning**: Omnichannel mobile commerce and Modern POS platform providing unified PWA and native app commerce for global lifestyle brands.
- **Key Capabilities**:
  - Dual deployment: High-performance Progressive Web App (PWA) and native iOS/Android apps from a single configuration.
  - PWA Web App Manifest generation (`manifest.json`) and service worker offline asset caching.
  - Bluetooth beacon and GPS geofence rules for hyper-localized in-store engagement.
  - Real-time store inventory lookup and reserve-in-store workflows.
  - Mobile payment integration across digital wallets and stored value cards.
- **Feature Reference**: https://predictspring.com/omnichannel-commerce

### 6. VTEX Mobile & PWA Commerce (vtex.com)
- **Positioning**: Global enterprise headless commerce platform with native PWA framework and conversational commerce capabilities.
- **Key Capabilities**:
  - Headless PWA store framework with Service Worker caching and offline browsing fallbacks.
  - Social Selling & Conversational Commerce suite (assisted sales via WhatsApp and social messengers).
  - Pre-populated cart generation dispatched via WhatsApp, SMS, or QR code for 1-click checkout.
  - Geographic store network locator with intelligent click-and-collect routing.
- **Feature Reference**: https://vtex.com/us-en/conversational-commerce

### 7. OneSignal & Airship (onesignal.com / airship.com)
- **Positioning**: Industry-standard mobile push notification and messaging infrastructure providers.
- **Key Capabilities**:
  - Device token registry supporting Apple Push Notification service (APNs), Firebase Cloud Messaging (FCM), and W3C Web Push (VAPID).
  - Rich push messaging with banner images, action buttons, and sound customizations.
  - Deep-link payload routing to native app routes and PWA URLs.
  - Geofenced push messaging: triggering messages when a device enters, exits, or dwells in a geographical zone.
  - Push delivery, open, and conversion event tracking.
- **Feature Reference**: https://onesignal.com/push-notifications

### 8. SleekFlow & charles (sleekflow.io / charles.co)
- **Positioning**: Leading enterprise WhatsApp Business and conversational commerce platforms.
- **Key Capabilities**:
  - WhatsApp Business API integration with Meta Commerce Manager product catalog synchronization.
  - In-chat interactive cart building: customers browse products and add items to a virtual cart directly inside WhatsApp.
  - Instant checkout link generation: agents or automated bots dispatch pre-filled payment links in chat.
  - Automated conversational triggers: order status updates, back-in-stock alerts, and abandoned cart recovery sequences via WhatsApp.
- **Feature Reference**: https://sleekflow.io/features/social-commerce, https://charles.co/features

---

## 4. Feature Catalog (Sub-module 9.16 Only)

### 4.1 Progressive Web App (PWA)
- **Web App Manifest Generator** — Configures and serves the dynamic W3C Web App Manifest (`manifest.json`) controlling app name, short name, start URL, display mode (`standalone`, `fullscreen`, `minimal-ui`), theme color, background color, and home-screen app icons (192x192, 512x512).  
  · *Seen in*: PredictSpring, VTEX, Vue Storefront  
  · *Priority*: `table-stakes`  
  · *Spine*: New table `MobileAppConfig` (`EMAC`)  
  · *Status*: `buildable now` (Django endpoint serves dynamic JSON manifest)
- **Service Worker Cache Strategy Orchestration** — Configures browser caching behavior for mobile web assets: App Shell caching, stale-while-revalidate, network-first, or cache-first for catalog pages, stylesheets, and images.  
  · *Seen in*: PredictSpring, VTEX, Magento PWA Studio  
  · *Priority*: `table-stakes`  
  · *Spine*: Stored in `MobileAppConfig`  
  · *Status*: `buildable now`
- **Offline Browsing & Custom Fallback** — Allows users to view previously cached catalog products and store pages when mobile internet connectivity drops; serves a tenant-configured offline fallback page when requesting uncached content.  
  · *Seen in*: VTEX, PredictSpring, PWA Kit  
  · *Priority*: `table-stakes`  
  · *Spine*: Stored in `MobileAppConfig` (`pwa_offline_fallback_html`)  
  · *Status*: `buildable now`
- **Web App Shortcuts (Quick Actions)** — Configures manifest shortcuts allowing shoppers to long-press the installed home-screen icon to jump directly to Cart, Deals, or Search.  
  · *Seen in*: Vue Storefront, PredictSpring  
  · *Priority*: `common`  
  · *Spine*: Stored in `MobileAppConfig`  
  · *Status*: `buildable now`
- **W3C Web Push Notification Support** — Captures Web Push subscription endpoints and VAPID keys for browser-based push notifications without requiring an app store install.  
  · *Seen in*: OneSignal, PushEngage, Airship  
  · *Priority*: `table-stakes`  
  · *Spine*: Captured in `MobileDeviceRegistration` (`platform="pwa_web"`)  
  · *Status*: `buildable now`

### 4.2 Native Mobile Apps (iOS / Android)
- **Mobile Device Registration & Token Registry** — Registers mobile client installations across iOS, Android, and PWA, securely storing device UUID, push tokens (APNs for iOS, FCM for Android, WebPush endpoint), OS version, app version, and push permission state.  
  · *Seen in*: Tapcart, Shopney, OneSignal, Airship  
  · *Priority*: `table-stakes`  
  · *Spine*: New table `MobileDeviceRegistration` (`EMDR`), FK to `core.Tenant`, FK to `ecommerce.CustomerAccountProfile`, FK to `core.Party`  
  · *Status*: `buildable now`
- **Biometric Authentication Governance** — Controls policies for Face ID, Touch ID, and Android BiometricPrompt login, allowing authenticated mobile shoppers to re-enter the app and authorize checkouts biometrically.  
  · *Seen in*: Tapcart, Poq, NewStore  
  · *Priority*: `table-stakes`  
  · *Spine*: Configured in `MobileAppConfig`, tracked per device in `MobileDeviceRegistration` (`biometric_enrolled`)  
  · *Status*: `buildable now`
- **Push Notification Campaign Engine** — Broadcast and triggered mobile push messages supporting title, body, rich media banner images, badge count manipulation, and scheduling.  
  · *Seen in*: Tapcart, Shopney, Plobal Apps, OneSignal  
  · *Priority*: `table-stakes`  
  · *Spine*: New table `MobilePushCampaign` (`EMPC`), FK to `core.Tenant`  
  · *Status*: `buildable now`
- **Deep-Link Intent Routing** — Configures universal links and custom URL schemes (`navierp://`) routing push notifications directly to specific products (`CatalogProduct`), collections (`StoreCategory`), coupons (`CouponPromotion`), or custom landing pages.  
  · *Seen in*: Tapcart, Poq, Airship  
  · *Priority*: `table-stakes`  
  · *Spine*: Modeled in `MobilePushCampaign` with verified FKs  
  · *Status*: `buildable now`
- **Automated Behavioral Push Triggers** — Automatically dispatches push notifications on behavioral events: abandoned cart recovery (1 hour after session inactivity), price drop on favorited item, back-in-stock alert, and order shipment updates.  
  · *Seen in*: Tapcart, Shopney, Klaviyo Mobile  
  · *Priority*: `common`  
  · *Spine*: Modeled in `MobilePushCampaign` (`campaign_type` choices)  
  · *Status*: `buildable now`
- **App Version & Force-Update Management** — Tenant-configured minimum supported native app version and maintenance mode toggle to manage deprecated client versions.  
  · *Seen in*: Poq, Tapcart, NewStore  
  · *Priority*: `common`  
  · *Spine*: Modeled in `MobileAppConfig` (`minimum_supported_version`, `is_maintenance_mode`)  
  · *Status*: `buildable now`

### 4.3 Mobile Payment Integration
- **Apple Pay Merchant Configuration** — Configures Apple Pay web and in-app merchant identifiers, payment processing certificate validation status, and supported networks (Visa, Mastercard, Amex).  
  · *Seen in*: Tapcart, Poq, NewStore, Stripe Mobile  
  · *Priority*: `table-stakes`  
  · *Spine*: Modeled in `MobileAppConfig`, coordinated with `ecommerce.PaymentMethodConfig` (9.4)  
  · *Status*: `buildable now`
- **Google Pay & Android Wallet Integration** — Configures Google Pay gateway merchant IDs, supported authorization methods (`PAN_ONLY`, `CRYPTOGRAM_3DS`), and environment (Test/Production).  
  · *Seen in*: Tapcart, Shopney, PredictSpring  
  · *Priority*: `table-stakes`  
  · *Spine*: Modeled in `MobileAppConfig`  
  · *Status*: `buildable now`
- **One-Tap Express Mobile Checkout** — Enables skipping the multi-step checkout funnel for mobile users by invoking native sheet wallets directly from the product detail page or mini-cart.  
  · *Seen in*: Tapcart, Poq, Shopify Mobile  
  · *Priority*: `table-stakes`  
  · *Spine*: Modeled in `MobileAppConfig` (`enable_express_checkout`)  
  · *Status*: `buildable now`
- **Stored In-App Customer Balance / Wallet** — Enables store credit, loyalty balance, or gift card balance redemption during mobile checkout.  
  · *Seen in*: Poq, PredictSpring  
  · *Priority*: `common`  
  · *Spine*: Modeled in `MobileAppConfig` (`enable_in_app_wallet`)  
  · *Status*: `buildable now`

### 4.4 Location-Based Services
- **Store Locator & Pickup Node Directory** — Configures physical retail store locations with GPS coordinates (latitude/longitude), operating hours, distance radius, and click-and-collect (BOPIS) fulfillment capabilities.  
  · *Seen in*: Poq, NewStore, PredictSpring, VTEX  
  · *Priority*: `table-stakes`  
  · *Spine*: New table `MobileLocationRule` (`EMLR`), FK to `ecommerce.FulfillmentCenter` (reusing 9.2 physical store nodes)  
  · *Status*: `buildable now`
- **Geofence Proximity Rules** — Defines circular geographic boundaries around retail stores with configurable radius (e.g. 200m–1000m) and trigger events (`entry`, `exit`, `dwell`).  
  · *Seen in*: Poq, PredictSpring, NewStore, OneSignal Location  
  · *Priority*: `common`  
  · *Spine*: Modeled in `MobileLocationRule`  
  · *Status*: `buildable now`
- **In-Store Shopping Mode Activation** — Automatically toggles the mobile app into "Store Mode" when the customer enters a geofenced retail store, surfacing local store inventory, in-store aisle maps, and barcode scanning tools.  
  · *Seen in*: Poq, NewStore, Walmart Mobile App, Target App  
  · *Priority*: `differentiator`  
  · *Spine*: Modeled in `MobileLocationRule` (`enable_in_store_mode`)  
  · *Status*: `buildable now`
- **Local Inventory Availability Verification** — Allows mobile shoppers to check whether a specific SKU is physically on the shelves of the nearest store location before visiting.  
  · *Seen in*: NewStore, Poq, PredictSpring  
  · *Priority*: `table-stakes`  
  · *Spine*: Links `MobileLocationRule` to `FulfillmentCenter` (which anchors `InventoryAllocation` from 9.2)  
  · *Status*: `buildable now`
- **Geo-Targeted Proximity Promotions** — Triggers personalized welcome push notifications and exclusive in-store coupon promotions when a registered customer enters the geofence perimeter.  
  · *Seen in*: Poq, PredictSpring, Airship  
  · *Priority*: `common`  
  · *Spine*: Modeled in `MobileLocationRule`, FK to `ecommerce.CouponPromotion` (9.3)  
  · *Status*: `buildable now`
- **Curbside Pickup Arrival Alert** — Allows customers arriving for store pickup to broadcast their arrival coordinates, alerting store associates to bring orders to the curbside pickup zone.  
  · *Seen in*: NewStore, Target App, Curbside  
  · *Priority*: `common`  
  · *Spine*: Modeled in `MobileLocationRule` (`supports_curbside`)  
  · *Status*: `buildable now`

### 4.5 Social & Messaging Commerce
- **Conversational Checkout Link Generation** — Generates secure, pre-filled cart and checkout URLs that sales agents or automated bots dispatch to customers via WhatsApp, WeChat, Instagram DM, or SMS.  
  · *Seen in*: SleekFlow, charles, VTEX Social Selling  
  · *Priority*: `table-stakes`  
  · *Spine*: Leverages `ecommerce.CheckoutSession` (9.4) & `ecommerce.CustomerSupportTicket` (9.14)  
  · *Status*: `buildable now` (View helper & model action)
- **Meta / WhatsApp Product Catalog Synchronization Feed** — Generates standardized JSON/XML product catalog feeds mapped to Meta Commerce Manager and WeChat Mini-Programs for native in-app catalog browsing.  
  · *Seen in*: SleekFlow, charles, Wati  
  · *Priority*: `common`  
  · *Spine*: Reads `ecommerce.CatalogProduct` (9.1)  
  · *Status*: `buildable now` (Catalog feed endpoint)
- **In-Chat Cart & Order Status Messaging** — Automated transactional messaging dispatching order confirmations, tracking links, and delivery notices into messaging channels.  
  · *Seen in*: SleekFlow, charles, Klaviyo SMS  
  · *Priority*: `table-stakes`  
  · *Spine*: Anchors to `ecommerce.EcommerceOrder` (9.5) and `ecommerce.MobilePushCampaign`  
  · *Status*: `buildable now`

### 4.6 Beyond the Bullets (Enterprise Standouts)
- **App Clips & Instant Apps** — Lightweight app experiences triggered by NFC tags, QR codes, or Safari smart app banners allowing instant purchase without downloading the full binary.  
  · *Seen in*: Tapcart, Apple App Clips, Android Instant Apps  
  · *Priority*: `differentiator`  
  · *Spine*: Configured in `MobileAppConfig` (`app_clip_bundle_id`)  
  · *Status*: `buildable now`
- **Push Delivery & Conversion Performance Telemetry** — Tracks aggregate delivery success, open rates, click-through rates, and attributed revenue per mobile campaign.  
  · *Seen in*: Tapcart, OneSignal, Airship  
  · *Priority*: `common`  
  · *Spine*: Modeled in `MobilePushCampaign`  
  · *Status*: `buildable now`

---

## 5. Recommended Build Scope (This Pass — 4 Models)

To deliver a high-impact, production-grade mobile commerce spine that fully covers all 5 bullets in `NavERP.md` within the strict 1–4 model unit, we recommend the following **4 tenant-scoped models** for Sub-module 9.16:

```
apps/ecommerce/models/MobileCommerce/
├── MobileAppConfigs.py            (Model: MobileAppConfig, Prefix: EMAC)
├── MobileDeviceRegistrations.py   (Model: MobileDeviceRegistration, Prefix: EMDR)
├── MobilePushCampaigns.py         (Model: MobilePushCampaign, Prefix: EMPC)
└── MobileLocationRules.py          (Model: MobileLocationRule, Prefix: EMLR)
```

### Model 1: `MobileAppConfig` [EMAC]
- **Purpose**: Central configuration for tenant Progressive Web App (PWA) manifest settings, native mobile app metadata (iOS/Android), and mobile express wallet payment integrations.
- **Justified by Features**:
  - *Progressive Web App (PWA)*: App name, short name, start URL, display mode, theme/background colors, icon assets, service worker caching strategy, offline fallback HTML.
  - *Native Mobile Apps*: Bundle identifier, minimum supported version, maintenance mode, biometric authentication toggle.
  - *Mobile Payment Integration*: Apple Pay merchant identifier, Google Pay gateway merchant ID, express one-tap checkout toggle, in-app stored wallet toggle.
- **Key Fields**:
  - `number`: Auto-numbered with prefix `EMAC`
  - `name`: Display configuration title (e.g. "Primary Mobile Commerce Storefront")
  - `platform_type`: Choices (`all`, `pwa_only`, `native_only`, `hybrid`)
  - `bundle_identifier`: App bundle ID (e.g. "com.navierp.store")
  - **PWA Settings**:
    - `pwa_app_name`: String (e.g. "NavERP Fashion Store")
    - `pwa_short_name`: String (e.g. "NavFashion")
    - `pwa_start_url`: String (default "/")
    - `pwa_display_mode`: Choices (`standalone`, `fullscreen`, `minimal_ui`, `browser`)
    - `pwa_theme_color`: String (hex, e.g. "#2563eb")
    - `pwa_background_color`: String (hex, e.g. "#ffffff")
    - `pwa_icon_192`: String/URL
    - `pwa_icon_512`: String/URL
    - `pwa_offline_cache_strategy`: Choices (`cache_first`, `network_first`, `stale_while_revalidate`, `network_only`)
    - `pwa_offline_fallback_html`: Text (custom offline fallback page content)
  - **Native & Biometric Settings**:
    - `enable_biometric_login`: Boolean (Face ID / Touch ID / Android Biometrics)
    - `minimum_supported_version`: String (e.g. "1.0.0")
    - `is_maintenance_mode`: Boolean
    - `maintenance_message`: Text
  - **Mobile Express Payments**:
    - `enable_apple_pay`: Boolean
    - `apple_pay_merchant_id`: String (e.g. "merchant.com.navierp.store")
    - `enable_google_pay`: Boolean
    - `google_pay_merchant_id`: String
    - `enable_express_checkout`: Boolean (1-tap checkout from product page)
    - `enable_in_app_wallet`: Boolean (stored credit / loyalty balance)
  - `is_active`: Boolean
- **Verified FKs**:
  - `tenant` (`core.Tenant`)

### Model 2: `MobileDeviceRegistration` [EMDR]
- **Purpose**: Device registry capturing registered mobile client installations (iOS, Android, PWA), secure push notification tokens, biometric enrollment, and location permission states.
- **Justified by Features**:
  - *Native Mobile Apps*: Device token management (APNs, FCM), OS version, app version, badge count, active status.
  - *PWA*: W3C Web Push endpoint registration.
  - *Biometrics & Location*: Tracks whether biometric authentication is enrolled and location permission status.
- **Key Fields**:
  - `number`: Auto-numbered with prefix `EMDR`
  - `customer_profile`: FK to `ecommerce.CustomerAccountProfile` (null=True, blank=True)
  - `party`: FK to `core.Party` (null=True, blank=True)
  - `device_uuid`: String (unique client installation UUID)
  - `platform`: Choices (`ios`, `android`, `pwa_web`, `other`)
  - `device_model`: String (e.g. "iPhone 15 Pro", "Samsung Galaxy S24", "Desktop Chrome")
  - `os_version`: String (e.g. "iOS 18.2", "Android 15")
  - `app_version`: String (e.g. "1.4.0")
  - `push_token`: Text (APNs device token, FCM registration token, or WebPush endpoint)
  - `push_provider`: Choices (`apns`, `fcm`, `web_push`, `none`)
  - `push_enabled`: Boolean (whether user granted push permissions)
  - `location_permission_status`: Choices (`not_determined`, `denied`, `when_in_use`, `always`)
  - `biometric_enrolled`: Boolean (whether Face ID / Touch ID is active on device)
  - `last_latitude`: Decimal (max_digits=9, decimal_places=6, null=True, blank=True)
  - `last_longitude`: Decimal (max_digits=9, decimal_places=6, null=True, blank=True)
  - `badge_count`: PositiveIntegerField (default 0)
  - `last_active_at`: DateTimeField
  - `is_active`: Boolean
- **Verified FKs**:
  - `tenant` (`core.Tenant`)
  - `customer_profile` (`ecommerce.CustomerAccountProfile`)
  - `party` (`core.Party`)

### Model 3: `MobilePushCampaign` [EMPC]
- **Purpose**: Mobile push campaign creation and dispatch engine supporting marketing broadcasts, automated behavioral re-engagement triggers (abandoned cart, price drops, back-in-stock), rich media, deep links, and conversion telemetry.
- **Justified by Features**:
  - *Native Mobile Apps & PWA*: Rich push notifications with banner images, action links, and scheduling.
  - *Promotional Triggers*: Automated behavioral triggers (abandoned cart, price drop, back-in-stock, geofence welcome).
  - *Deep Linking*: Direct navigation to specific products, categories, or coupons.
  - *Conversion Tracking*: Delivery, open, click, and conversion revenue telemetry.
- **Key Fields**:
  - `number`: Auto-numbered with prefix `EMPC`
  - `title`: String (e.g. "⚡ Flash Sale: 30% Off New Arrivals!")
  - `body`: Text (e.g. "Tap to shop our limited-time summer drops before they sell out.")
  - `subtitle`: String (blank=True)
  - `campaign_type`: Choices:
    - `broadcast_promotional` ("Broadcast Promotional Campaign")
    - `abandoned_cart_recovery` ("Abandoned Cart Recovery")
    - `price_drop_alert` ("Price Drop Notification")
    - `back_in_stock_alert` ("Back in Stock Notification")
    - `order_status_update` ("Order Status Notification")
    - `geofence_proximity_alert` ("Geofence Proximity Alert")
    - `welcome_series` ("New App User Welcome")
  - `target_platform`: Choices (`all_platforms`, `ios_only`, `android_only`, `pwa_only`)
  - `deep_link_type`: Choices (`home`, `product`, `category`, `cart`, `coupon`, `custom_url`)
  - `target_product`: FK to `ecommerce.CatalogProduct` (null=True, blank=True)
  - `target_category`: FK to `ecommerce.StoreCategory` (null=True, blank=True)
  - `target_coupon`: FK to `ecommerce.CouponPromotion` (null=True, blank=True)
  - `custom_deep_link`: String (e.g. "navierp://promo/summer26")
  - `image_url`: String/URL (rich push banner image)
  - `badge_count_increment`: PositiveSmallIntegerField (default 1)
  - `scheduled_at`: DateTimeField (null=True, blank=True)
  - `sent_at`: DateTimeField (null=True, blank=True)
  - `status`: Choices (`draft`, `scheduled`, `sending`, `sent`, `cancelled`, `failed`)
  - **Telemetry Counters**:
    - `target_recipient_count`: PositiveIntegerField (default 0)
    - `sent_count`: PositiveIntegerField (default 0)
    - `delivered_count`: PositiveIntegerField (default 0)
    - `opened_count`: PositiveIntegerField (default 0)
    - `converted_count`: PositiveIntegerField (default 0)
    - `converted_revenue`: DecimalField (max_digits=12, decimal_places=2, default 0.00)
- **Verified FKs**:
  - `tenant` (`core.Tenant`)
  - `target_product` (`ecommerce.CatalogProduct`)
  - `target_category` (`ecommerce.StoreCategory`)
  - `target_coupon` (`ecommerce.CouponPromotion`)
  - `created_by` (`accounts.User`)

### Model 4: `MobileLocationRule` [EMLR]
- **Purpose**: Location-based services, physical retail store locator directory, and geofence rules triggering proximity alerts, in-store shopping mode, and local store inventory visibility.
- **Justified by Features**:
  - *Location-Based Services*: Store locator, geographic coordinates, operating hours, BOPIS (Buy Online Pick Up In Store) support.
  - *Geofencing & Proximity*: Circular geofence radius, dwell time triggers, entry/exit events.
  - *In-Store Mode*: Dynamic app UI transformation for shoppers inside physical stores.
  - *Geo-Targeted Promotions*: Proximity welcome push notifications with linked coupon promotions.
- **Key Fields**:
  - `number`: Auto-numbered with prefix `EMLR`
  - `name`: Rule/Store title (e.g. "Downtown Flagship Geofence & Store Locator")
  - `rule_type`: Choices:
    - `store_locator_only` ("Store Locator Only")
    - `geofence_entry` ("Geofence Entry Trigger")
    - `geofence_exit` ("Geofence Exit Trigger")
    - `geofence_dwell` ("Geofence Dwell Trigger (5+ mins)")
  - `fulfillment_center`: FK to `ecommerce.FulfillmentCenter` (null=True, blank=True, anchoring to physical store nodes from 9.2)
  - `store_name`: String (fallback or custom store display name)
  - `latitude`: DecimalField (max_digits=9, decimal_places=6)
  - `longitude`: DecimalField (max_digits=9, decimal_places=6)
  - `radius_meters`: PositiveIntegerField (default 500, range 50m to 10,000m)
  - `dwell_time_seconds`: PositiveIntegerField (default 300, for dwell triggers)
  - `supports_bopis`: Boolean (default True, Buy Online Pick Up In Store)
  - `supports_curbside`: Boolean (default False, Curbside Pickup)
  - `enable_in_store_mode`: Boolean (default True, activates in-store barcode/inventory UI)
  - `entry_notification_title`: String (e.g. "Welcome to NavERP Downtown!")
  - `entry_notification_body`: Text (e.g. "Enjoy 10% off your in-store purchase today.")
  - `linked_promotion`: FK to `ecommerce.CouponPromotion` (null=True, blank=True)
  - `is_active`: Boolean
- **Verified FKs**:
  - `tenant` (`core.Tenant`)
  - `fulfillment_center` (`ecommerce.FulfillmentCenter`)
  - `linked_promotion` (`ecommerce.CouponPromotion`)

---

## 6. Belongs to Sibling Sub-modules (Parked, Not Scoped Here)

To maintain strict architectural modularity and avoid duplicating logic across the suite, the following capabilities belong to sibling sub-modules:
- **Generic Payment Gateway Processing & Merchant Accounts**: Handled by Sub-module 9.4 Shopping Cart & Checkout (`PaymentMethodConfig`, `CheckoutSession`) and Module 2 `accounting`. 9.16 configures mobile-specific express wallet parameters (Apple Pay merchant ID, Google Pay gateway ID) rather than generic credit card processors.
- **Customer Support Live Chat & Help Desk**: Handled by Sub-module 9.14 Customer Service & Support (`CustomerSupportTicket` with `channel="chat"`). In-app support chat in mobile apps communicates via the 9.14 ticketing spine.
- **Mobile Analytics & App Funnel Drop-off**: Handled by Sub-module 9.15 Analytics & Business Intelligence (`AnalyticsBi`). 9.16 records operational push campaign delivery/open counters, while longitudinal cohort retention and marketing attribution belong to 9.15.
- **Physical Inventory Stock Moves & Warehouse Bin Allocations**: Handled by Module 5 Inventory Management and Sub-module 9.2 (`InventoryAllocation`). 9.16 store locator queries available inventory but does not manage physical stock movements.
- **B2B Mobile Quoting & Corporate Account Hierarchy**: Belongs to Sub-module 9.17 B2B & Wholesale Commerce.
- **Mobile Payment Fraud & Velocity Anomaly Detection**: Belongs to Sub-module 9.18 Fraud & Risk Management.

---

## 7. Deferred (Later Passes / Integrations)

The following advanced or external-dependent capabilities are cataloged for future passes:
1. **Live APNs / FCM Gateway Socket Dispatches**: Production push notifications require uploading `.p8` Apple Push Notification authentication keys and Google Firebase Service Account JSON credentials. In this pass, the push engine formats the exact APNs/FCM payloads, tracks status, and manages campaigns; actual live socket transmissions are queued via external workers.
2. **Apple Pay Merchant Identity Certificate Signing**: Requires Apple Developer account `.cer` validation and domain verification file hosting (`/.well-known/apple-developer-merchantid-domain-association`). The configuration model provides the merchant ID and validation status fields.
3. **Live WhatsApp Business Cloud API & WeChat Mini-Program Webhook Daemons**: Third-party messaging platforms require persistent webhook listener daemons and Meta Cloud API access tokens. In this pass, the conversational commerce URLs and Meta catalog feeds are generated as dynamic Django endpoints.
4. **Hardware Bluetooth Beacon Scanning**: Bluetooth Low Energy (BLE) iBeacon / Eddystone hardware proximity detection requires on-device native Bluetooth daemon code. The backend geofence model captures lat/lng and radius rules that translate directly to native geofence and beacon triggers.

---

## 8. Summary for Todo Agent

- **Target Sub-module**: 9.16 Mobile Commerce (`apps/ecommerce`)
- **Surveyed Commercial Leaders**: Tapcart, Shopney, Poq Commerce, NewStore, PredictSpring, VTEX Mobile/PWA, OneSignal/Airship, SleekFlow/charles.
- **Recommended 4-Model Scope**:
  1. `MobileAppConfig` (`EMAC`) — PWA manifest settings, native app metadata, and mobile express wallet payment integration.
  2. `MobileDeviceRegistration` (`EMDR`) — Registered client devices (iOS, Android, PWA), push tokens, biometrics, and location status.
  3. `MobilePushCampaign` (`EMPC`) — Push notifications with deep links to products/categories/coupons, automated behavioral triggers, and telemetry.
  4. `MobileLocationRule` (`EMLR`) — Physical store locator directory, circular geofence rules, in-store shopping mode, and proximity promotions.
- **Key Verified Reused Entities**: `core.Tenant`, `core.Party`, `ecommerce.CustomerAccountProfile`, `ecommerce.CatalogProduct`, `ecommerce.StoreCategory`, `ecommerce.CouponPromotion`, `ecommerce.FulfillmentCenter`.
- **All Proposed Prefixes Checked**: `EMAC`, `EMDR`, `EMPC`, `EMLR` — 0 collisions across repository.
- **Output Artifact**: `.claude/tasks/research-ecommerce-9.16.md`
