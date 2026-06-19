# NavERP — Build Prompt

## Goal

1. Build **NavERP**, a multi-tenant **Enterprise Resource Planning (ERP)** platform — Django (backend) + Tailwind CSS + HTMX (frontend).
2. Create a clean, intuitive, fully responsive, unique dashboard design with a **blue and white** theme.
3. Multi-tenant application (tenant-scoped data; `tenant=request.tenant` on every query).
4. Create login, registration, and forgot-password pages.
5. Create user management, user invite, and user profile (IAM/RBAC — Module 0).
6. Proper migrations for all tables.
7. Seed fake/demo data via idempotent seeders.
8. Create a `.env` file for the MySQL (XAMPP) database connection — DB name **`nav_erp`**.
9. Always keep `README.md` up to date.
10. **`NavERP.md`** is the master module catalog (modules 0–13) for planning; **`NavERP-ERD.md`** is the unified core data model (the `Party` + two-ledger spine every module reuses).
11. The sidebar menu mirrors the `NavERP.md` modules and sub-modules; the design follows the attached reference image.

## Architecture (read `NavERP-ERD.md` first)

- **Unified core, no duplication.** Customers/vendors/suppliers/employees/leads/contacts are `PartyRole`s on a single `Party`. Items/UOM/price lists/locations/currencies/GL accounts/tax codes are shared masters. Every inventory effect posts to `StockMove`, every financial effect to `JournalEntry`/`JournalLine` (append-only) — on-hand quantities and balances are **derived**, never stored editable.
- **Module 0 — System Admin & Security** is the cross-cutting foundation: build it first as the apps `core` (Tenant, TenantMiddleware, navigation `MODULE_CATALOG` 0–13, AuditLog, decorators, the unified-core masters + ledgers), `accounts` (User/Role/Permission/UserInvite + email-or-username auth + IAM/RBAC), `tenants` (subscription/billing/branding/encryption keys/health), and `dashboard` (KPI aggregation). Modules 1–13 are domain apps built on top via the `/next-module` skill.

## Dashboard Requirements

Layout Features:

-  Clean, Intuitive and Fully Responsive Unique Design
-    Vertical, Horizontal & Detached
-    Light & Dark Modes
-    Fluid & Boxed Width
-    Fixed & Scrollable Positions
-    Light & Dark Topbars
-    Default, Compact, Small Icon & Icon Hovered Sidebars
-    Light & Colored Sidebars
-    LTR & RTL supported
-    Preloader option

Browser Compatibility:

-    Chrome (Windows, Mac, Linux)
-    Firefox (Windows, Mac, Linux)
-    Safari (Mac)
-    Microsoft Edge
-    And other WebKit browsers

## NavERP module catalog (see `NavERP.md` for full sub-modules)

The first module to implement is **Module 0 — System Admin & Security** (the foundation above). Its 0.1 sub-module:

## 0.1 Tenant & Subscription Management
| Sub-Module | Description |
|------------|-------------|
| Tenant Onboarding | Self-service registration, domain provisioning, and initial configuration wizard |
| Subscription & Billing | Plan management, usage metering, invoicing, and payment gateway integration |
| Tenant Isolation & Security | Database/schema isolation, encryption keys, and cross-tenant data leak prevention |
| Custom Branding | White-labeling, custom logos, themes, and email templates per tenant |
| Tenant Health Monitoring | Resource usage tracking, audit logs, and tenant-level system performance alerts |

After Module 0, build modules 1–13 (CRM, Accounting & Finance, HRM, SCM, Inventory, Procurement, Project Management, Sales, eCommerce, BI, Asset Management, Quality, Document Management) one at a time with the `/next-module` skill — each as a Django app under `apps/<slug>` reusing the unified core.
