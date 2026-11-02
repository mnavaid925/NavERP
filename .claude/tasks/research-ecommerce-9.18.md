# Research — Sub-module 9.18: Fraud & Risk Management (Module 9 — eCommerce Management System, `ecommerce`)

- **Sub-module:** 9.18 Fraud & Risk Management
- **Module:** 9 eCommerce Management System
- **Target app:** `apps/ecommerce` (extending the existing app created in 9.1 and extended through 9.17)
- **Research date:** 2026-11-02
- **Phase:** 1 Research only
- **Output file:** `.claude/tasks/research-ecommerce-9.18.md`

---

## 1. Executive Summary & Domain Architecture

Sub-module 9.18 delivers enterprise **Fraud & Risk Management** for NavERP eCommerce, providing a multi-layered trust, safety, and dispute resolution architecture to protect online revenue, customer accounts, and regulatory compliance.

Modern e-commerce merchants face escalating threats from sophisticated automated bot attacks, card testing, stolen credentials, account takeovers (ATO), policy abuse, friendly fraud, and payment chargebacks. Market-leading digital trust and risk platforms (such as Sift, Riskified, Signifyd, Forter, Stripe Radar, Kount/Equifax, SEON, Cybersource, Accertify, and Ravelin) protect digital businesses through five core capabilities:

1. **Transaction Fraud Detection & Velocity Checking**:
   - Multi-point rule evaluations at checkout verifying Address Verification Service (AVS) match status, Card Verification Value (CVV) checks, card-testing velocity limits, and transaction amount thresholds.
   - High-velocity order frequency spikes across IPs, devices, or cards trigger automated interventions before goods are fulfilled or funds captured.
2. **Multi-Factor Risk Scoring & Signal Evaluation**:
   - Comprehensive risk scoring (0–100 scale) synthesizing behavioral anomalies, device fingerprint consistency, IP proxy/VPN/TOR detection, geolocation mismatches between billing address and physical IP, and high-risk domain patterns.
   - Tiered risk bands (`low`, `medium`, `high`, `critical`) drive automated decisions: instant approval, step-up authentication (3D Secure / OTP challenge), manual fraud analyst review queue, or hard decline.
3. **Chargeback & Dispute Lifecycle Management**:
   - Centralized tracking of formal card-network disputes (Visa, Mastercard, Amex, PayPal) across their full regulatory lifecycle (`inquiry`, `dispute_received`, `evidence_under_review`, `representment_submitted`, `won`, `lost`, `accepted`).
   - Standardized reason code categorization (fraud/unauthorized, goods not received, credit not processed, significantly not as described), evidence collection collation (delivery signatures, tracking logs, customer communications, IP logs), deadline tracking, and merchant win-rate performance metrics.
4. **Account Takeover (ATO) Prevention & Credential Defense**:
   - Continuous authentication monitoring detecting credential stuffing, rapid failed login spikes, impossible-travel geographic logins, and suspicious profile/password edits.
   - Automated defensive playbooks including session termination, forced password resets, multi-factor challenge escalations, and proactive security notifications.
5. **Compliance Screening & AML/Sanctions Monitoring**:
   - Pre-transaction and account-level screening against Office of Foreign Assets Control (OFAC) sanctions, Specially Designated Nationals (SDN), Politically Exposed Persons (PEP), and export control restriction lists.
   - Anti-Money Laundering (AML) transaction monitoring catching structuring patterns, rapid fund movement, and high-risk jurisdiction flags.

### Architectural Boundary Rulings (L28, L29, L36, L37):
1. **Multi-Tenancy & Data Isolation (L28, L36)**:
   - All Fraud & Risk models inherit from `TenantNumbered` (`apps/ecommerce/models/_base.py`) with strict `tenant` (`core.Tenant`) isolation.
   - Rules, risk assessments, disputes, and security alerts are strictly partitioned per tenant.
2. **Financial Ledger & Payment Ownership (L29)**:
   - Module 9 `ecommerce` handles checkout fraud screening, dispute evidence workflows, and ATO alerts.
   - Module 2 `accounting` remains the sole authoritative financial general ledger (`Invoice`, `Payment`, `JournalEntry`). Dispute chargeback fees and settlement debits integrate with `accounting.Payment` / `accounting.Invoice` without creating secondary bookkeeping ledgers inside `ecommerce`.
3. **Core Spine & User Integration (L28)**:
   - Links to `core.Party` for customer/business entity identity.
   - Links to `settings.AUTH_USER_MODEL` for monitored accounts and fraud analyst reviewers.
   - Logs administrative interventions via `core.AuditLog`.
4. **Order & Checkout Integration (9.4 / 9.5)**:
   - Evaluates carts/orders from `ecommerce.Cart` (9.4) and links risk assessments directly to `ecommerce.EcommerceOrder` (9.5).
   - Dispute records link to `ecommerce.EcommerceOrder` (9.5) and order fulfillment tracking.

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
  - `"9.8"` is live: Personalization & Recommendation Engine (`EREC`, `EUSR`, `EACF`, `ECST`)
  - `"9.9"` is live: Content Management System (`ECMP`, `EBLP`, `EBNR`, `ENAV`)
  - `"9.10"` is live: Marketing & Campaign Management (`EMCP`, `ECPN`, `EABT`, `EADF`)
  - `"9.11"` is live: Marketplace & Multi-Vendor (`EVND`, `EVPL`, `EVST`, `EVCO`)
  - `"9.12"` is live: Subscription & Recurring Commerce (`ESBP`, `ECSB`, `ESBO`, `ESBD`)
  - `"9.13"` is live: Reviews & User-Generated Content (`EPRV`, `EQNA`, `EUGC`, `ERVR`)
  - `"9.14"` is live: Customer Service & Support (`ECST`, `ELCS`, `ESKB`, `ESLA`)
  - `"9.15"` is live: Analytics & Business Intelligence (`EATT`, `ECMT`, `EPMM`, `ECKM`)
  - `"9.16"` is live: Mobile Commerce (`EMAC`, `EMDR`, `EMPC`, `EMLR`)
  - `"9.17"` is live: B2B & Wholesale Commerce (`EBCA`, `EBCU`, `EBQR`, `EBQT`)
  - `"9.18"`: Target sub-module (Fraud & Risk Management) — to be built now.

### 2.2 Spine Entities Verified to Exist (Grep Evidence)
- `apps/core/models/`:
  - `Tenant`: verified (`apps/core/models/Tenant.py`)
  - `Party`: verified (`apps/core/models/Party.py`)
  - `User`: verified via `django.conf.settings.AUTH_USER_MODEL`
  - `Address`: verified (`apps/core/models/Address.py`)
  - `AuditLog`: verified (`apps/core/models/AuditLog.py`)
- `apps/accounting/models/`:
  - `Currency`: verified (`apps/accounting/models/GeneralLedger/Currencies.py`)
  - `Invoice`: verified (`apps/accounting/models/AccountsReceivable/Invoices.py`)
  - `Payment`: verified (`apps/accounting/models/CashBank/Payments.py`)
- `apps/ecommerce/models/`:
  - `EcommerceOrder`: verified (`apps/ecommerce/models/OrderManagement/EcommerceOrders.py`)
  - `CustomerAccountProfile`: verified (`apps/ecommerce/models/CustomerProfile/CustomerAccountProfiles.py`)
  - `Cart`: verified (`apps/ecommerce/models/CartCheckout/Carts.py`)
  - `B2bCompanyAccount`: verified (`apps/ecommerce/models/B2bWholesale/B2bCompanyAccounts.py`)

---

## 3. Leaders Surveyed (with Source Links)

1. **Sift (Digital Trust & Safety)**
   - *Enterprise standard for digital trust, account defense, and dispute resolution.*
   - Sources: [Sift Payment Protection](https://sift.com/products/payment-protection), [Sift Account Defense](https://sift.com/products/account-defense), [Sift Dispute Management](https://sift.com/products/dispute-management).
   - Key capabilities: Dynamic risk scoring, machine-learned behavioral fingerprints, proactive ATO alerts, automated chargeback evidence compilation, configurable velocity rules.

2. **Riskified**
   - *Pioneer in machine learning e-commerce fraud decisioning and guaranteed chargeback protection.*
   - Sources: [Riskified Decisions](https://www.riskified.com/fraud-prevention/), [Riskified Chargeback Guarantee](https://www.riskified.com/chargeback-guarantee/).
   - Key capabilities: Real-time approve/decline verdicts, AVS/CVV failure contextualization, proxy/VPN anomaly detection, full liability shift workflows.

3. **Signifyd**
   - *Market leader in commerce protection and end-to-end dispute recovery.*
   - Sources: [Signifyd Commerce Protection Platform](https://www.signifyd.com/products/), [Signifyd Dispute Center](https://www.signifyd.com/products/dispute-recovery/).
   - Key capabilities: Automated decision engine, representment management with win-rate analytics, customer intent profiling, cross-merchant identity network.

4. **Forter**
   - *Global trust platform delivering real-time fraud assessment across payments and accounts.*
   - Sources: [Forter Payment Protection](https://www.forter.com/products/payment-protection/), [Forter Account Protection](https://www.forter.com/products/account-protection/).
   - Key capabilities: Sub-second risk scoring, identity graph matching, account takeover prevention, policy abuse mitigation, smart dispute packet assembly.

5. **Stripe Radar**
   - *Embedded machine learning fraud detection built directly into payment infrastructure.*
   - Sources: [Stripe Radar Documentation](https://stripe.com/radar), [Radar Custom Rules](https://stripe.com/docs/radar/rules).
   - Key capabilities: Radar risk score (0–99), customizable boolean rule engine (allow, review, block, 3DS), AVS/CVC verification codes, device fingerprinting, dispute lifecycle webhooks.

6. **Kount (an Equifax company)**
   - *Pioneering fraud management and identity verification network.*
   - Sources: [Kount Command & Control](https://kount.com/solutions/fraud-prevention/).
   - Key capabilities: Omnichannel risk analytics, VIP whitelists and negative blacklists, manual review console, chargeback alert network integration.

7. **SEON (Fraud Fighters)**
   - *Modern digital footprinting and AML/sanctions screening engine.*
   - Sources: [SEON Fraud Prevention](https://seon.io/), [SEON AML & PEP Screening](https://seon.io/aml-pep-screening/).
   - Key capabilities: Device fingerprint hashes, email & phone social signal enrichment, velocity checks, real-time sanctions and PEP compliance watchlists.

8. **Cybersource / Visa Acceptance Solutions**
   - *Enterprise fraud management and payer authentication platform.*
   - Sources: [Cybersource Decision Manager](https://www.cybersource.com/en-us/solutions/fraud-and-risk-management/decision-manager.html).
   - Key capabilities: Visa risk insights, 3D Secure 2.x orchestration, case management workbench for fraud analysts, automated dispute representment.

9. **Accertify (an American Express company)**
   - *Comprehensive merchant risk, dispute management, and account security suite.*
   - Sources: [Accertify Fraud Management](https://www.accertify.com/fraud-management/).
   - Key capabilities: Highly configurable rule engine, automated chargeback response builder, device intelligence, community consortium data.

10. **Ravelin**
    - *Specialized fraud detection, ATO defense, and voucher abuse platform.*
    - Sources: [Ravelin Online Payment Fraud](https://www.ravelin.com/products/fraud-detection).
    - Key capabilities: Graph network analysis, ATO pattern detection, chargeback prediction, dynamic 3DS routing.

---

## 4. Feature Catalog (Sub-Module 9.18)

### 4.1 Transaction Fraud Detection
- **Configurable Velocity Rules** — Evaluate order frequency per IP, email, credit card token, or shipping address over 1h/24h/7d windows · seen in: Sift, Stripe Radar, Kount, SEON · priority: `table-stakes` · spine: new table `FraudRule` · buildable now.
- **AVS & CVV Verification Validation** — Systematic validation of card verification values (`match`, `no_match`, `not_checked`) and street/postal address verification codes · seen in: Stripe Radar, Cybersource, Riskified · priority: `table-stakes` · spine: new table `TransactionRiskAssessment` · buildable now.
- **Transaction Amount & High-Risk Thresholds** — Flagging orders exceeding standard single-order or cumulative velocity thresholds · seen in: Stripe Radar, Accertify · priority: `table-stakes` · spine: new table `FraudRule` · buildable now.
- **Blacklist / Whitelist Screening** — Exact match lists for high-risk or trusted IP addresses, email domains, phone numbers, and countries · seen in: Kount, Signifyd, SEON · priority: `table-stakes` · spine: new table `FraudRule` · buildable now.

### 4.2 Machine Learning Risk Scoring
- **Composite Risk Score (0–100 Scale)** — Normalized risk score combining rule evaluations, behavioral anomalies, and risk factor weights · seen in: Sift, Stripe Radar, Forter, SEON · priority: `table-stakes` · spine: new table `TransactionRiskAssessment` · buildable now.
- **Risk Tiering & Recommended Action** — Automatic classification into `low`, `medium`, `high`, `critical` with clear operational recommendations (`approve`, `review`, `challenge`, `block`) · seen in: Sift, Riskified, Signifyd · priority: `table-stakes` · spine: new table `TransactionRiskAssessment` · buildable now.
- **Device & Connection Intelligence** — Tracking device fingerprint hashes, IP proxy/VPN detection, and geolocation vs billing country mismatches · seen in: SEON, Forter, Kount · priority: `common` · spine: new table `TransactionRiskAssessment` · buildable now.
- **Manual Review Workbench** — Dedicated fraud analyst queue for transactions held in review state with resolution tracking (`approved_by_analyst`, `declined_by_analyst`) · seen in: Sift, Cybersource, Accertify · priority: `table-stakes` · spine: new table `TransactionRiskAssessment` · buildable now.

### 4.3 Chargeback Management
- **Full Dispute Lifecycle Tracking** — Comprehensive status progression (`inquiry`, `dispute_received`, `evidence_under_review`, `representment_submitted`, `won`, `lost`, `accepted`) · seen in: Sift, Signifyd, Stripe Radar, Cybersource · priority: `table-stakes` · spine: new table `ChargebackDispute` · buildable now.
- **Standardized Reason Code Categorization** — Formal dispute reason codes (fraud/unauthorized, goods not received, credit not processed, product defective/not as described) · seen in: Stripe, Visa/Mastercard, Signifyd · priority: `table-stakes` · spine: new table `ChargebackDispute` · buildable now.
- **Evidence Dossier Compilation** — Tracking customer communications, delivery confirmation details, proof of purchase, and representment cover letters · seen in: Sift, Signifyd, Forter · priority: `table-stakes` · spine: new table `ChargebackDispute` · buildable now.
- **Financial & Deadlines Accounting** — Tracking dispute amount, fees, currency (`accounting.Currency`), response due dates, and dispute win/loss outcomes · seen in: Stripe, Signifyd, Accertify · priority: `table-stakes` · spine: new table `ChargebackDispute` (FK `accounting.Currency`, `ecommerce.EcommerceOrder`) · buildable now.

### 4.4 Account Takeover (ATO) Prevention
- **Credential Stuffing & Brute-Force Detection** — Tracking rapid login failures, spray attacks, and compromised credential usage · seen in: Sift, Forter, Ravelin · priority: `table-stakes` · spine: new table `AccountSecurityAlert` · buildable now.
- **Suspicious Session & Impossible Travel Alerts** — Flagging anomalous logins across distant geographic locations or suspicious device changes · seen in: Sift, SEON · priority: `common` · spine: new table `AccountSecurityAlert` · buildable now.
- **Automated Defensive Interventions** — Configurable immediate responses: lock account, force password reset, invalidate active sessions, challenge MFA · seen in: Sift, Forter, Ravelin · priority: `table-stakes` · spine: new table `AccountSecurityAlert` · buildable now.

### 4.5 Compliance Screening
- **Sanctions & PEP Watchlist Screening** — Match evaluation against OFAC, PEP, and global watchlists for individuals and business entities · seen in: SEON, Accertify · priority: `common` · spine: new table `AccountSecurityAlert` (screening alert types) · buildable now.
- **AML Transaction Monitoring Flags** — Detection of suspicious transaction velocity patterns, structured payment splitting, and high-risk regulatory corridors · seen in: SEON, Accertify · priority: `common` · spine: new table `AccountSecurityAlert` · buildable now.

---

## 5. Recommended Build Scope (This Pass — 4 Models)

To deliver a production-grade enterprise fraud and risk suite within the clean 1–4 model scope of `/next-module`, sub-module 9.18 implements four dedicated tenant-scoped models in `apps/ecommerce/models/FraudRisk/`:

1. **`FraudRule`** [Prefix: `EFRR-`] (`apps/ecommerce/models/FraudRisk/FraudRules.py`)
   - **Purpose**: Configurable fraud detection rule engine defining evaluation conditions (velocity, IP/proxy, country mismatch, order amount, card velocity, email domain), risk score penalty weights, scope (checkout, login, registration), and automated action (`allow`, `flag_review`, `challenge_3ds`, `block`).
   - **Key Fields**: `rule_code`, `name`, `rule_scope`, `rule_type`, `condition_operator`, `threshold_value`, `risk_score_impact`, `action_to_take`, `is_active`, `priority_order`, `description`.

2. **`TransactionRiskAssessment`** [Prefix: `ETRA-`] (`apps/ecommerce/models/FraudRisk/TransactionRiskAssessments.py`)
   - **Purpose**: Comprehensive risk assessment record generated for checkout orders and payment transactions. Evaluates composite risk score (0–100), risk tier (`low`, `medium`, `high`, `critical`), AVS/CVV status, IP/device signals, geo mismatches, velocity counts, automated verdict, and manual analyst review decisions.
   - **Key Fields**: `order` (FK `ecommerce.EcommerceOrder`, optional/protect), `customer_party` (FK `core.Party`, optional), `risk_score` (0–100), `risk_tier`, `recommended_action`, `actual_decision`, `avs_result_code`, `cvv_result_code`, `ip_address`, `device_fingerprint`, `is_proxy_or_vpn`, `is_geo_mismatch`, `triggered_rules_summary`, `analyst_user`, `analyst_notes`, `evaluated_at`.

3. **`ChargebackDispute`** [Prefix: `ECBD-`] (`apps/ecommerce/models/FraudRisk/ChargebackDisputes.py`)
   - **Purpose**: Formal dispute, inquiry, and chargeback case record managing representment workflows, reason codes, evidence compilation, response deadlines, and dispute win/loss tracking.
   - **Key Fields**: `order` (FK `ecommerce.EcommerceOrder`), `currency` (FK `accounting.Currency`), `dispute_amount`, `fee_amount`, `gateway_dispute_id`, `reason_category`, `reason_code`, `stage`, `evidence_due_date`, `evidence_summary`, `representment_notes`, `representment_submitted_at`, `closed_at`, `outcome_notes`.

4. **`AccountSecurityAlert`** [Prefix: `EASA-`] (`apps/ecommerce/models/FraudRisk/AccountSecurityAlerts.py`)
   - **Purpose**: Real-time security incident record for Account Takeover (ATO) attempts, credential stuffing, suspicious logins, and sanctions/PEP compliance screening hits.
   - **Key Fields**: `user` (FK `settings.AUTH_USER_MODEL`, optional), `party` (FK `core.Party`, optional), `alert_type` (`suspicious_login`, `credential_stuffing`, `brute_force`, `impossible_travel`, `sanctions_screening_hit`, `aml_structuring`), `severity` (`low`, `medium`, `high`, `critical`), `status` (`new`, `investigating`, `resolved_safe`, `confirmed_threat`, `dismissed`), `automated_action_taken` (`none`, `force_password_reset`, `lock_account`, `challenge_mfa`, `notify_user`), `ip_address`, `user_agent`, `details`, `resolved_by` (FK `settings.AUTH_USER_MODEL`), `resolved_at`.

### Prefix Collision Check
- `EFRR`: Verified 0 collisions across repository.
- `ETRA`: Verified 0 collisions across repository.
- `ECBD`: Verified 0 collisions across repository.
- `EASA`: Verified 0 collisions across repository.

---

## 6. Belongs to Sibling Sub-Modules (Parked, Not Scoped Here)
- **General Customer Profile Management** → 9.6 Customer Account & Profile (`CustomerAccountProfile`, `CustomerAddress`).
- **Core Order Fulfillment & RMAs** → 9.5 Order Management System (`EcommerceOrder`, `OrderFulfillment`, `OrderRma`).
- **Wholesale Net Terms & Company Accounts** → 9.17 B2B & Wholesale Commerce (`B2bCompanyAccount`, `B2bCompanyUser`).
- **Authoritative Accounting General Ledger & Payment Vouchers** → Module 2 Accounting (`Invoice`, `Payment`, `JournalEntry`).

---

## 7. Deferred (Later Passes / External Integrations)
- **Live 3D Secure 2.3 biometric challenge daemon** — Simulated via web views and standard test vectors without external bank redirect dependencies.
- **External real-time OFAC / World-Check API subscription** — Local compliance screening rule evaluation implemented without third-party API subscription costs.
- **Biometric mouse/keystroke behavioral analysis JS daemon** — Modeled via device fingerprinting and behavioral anomaly scoring fields.
