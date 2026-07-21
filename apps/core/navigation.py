"""NavERP sidebar navigation — driven directly by NavERP.md.

The sidebar mirrors the catalog's three levels: **Module → Sub-module → Feature**.
Rather than duplicate that tree here, we **parse `NavERP.md`** (the single source of
truth) into modules → sub-modules → features, then overlay ``LIVE_LINKS`` to turn the
features that are actually built into clickable routes. Everything else renders as an
"On the roadmap" placeholder.

When a new module ships, add a ``"N.M"`` entry to ``LIVE_LINKS`` mapping its NavERP.md
feature names to ``namespace:name`` routes (and/or extra built pages) — no template or
parser changes needed.

``resolve_nav(request)`` produces render-ready data (hrefs safely reversed, active item
flagged, parent module/sub-module marked open). Exposed to every template via
``apps.core.context_processors.navigation``.
"""
import os
import re
from functools import lru_cache
from urllib.parse import parse_qsl

from django.conf import settings
from django.urls import NoReverseMatch, reverse

# Lucide icon per module number.
MODULE_ICONS = {
    0: "shield-check", 1: "contact", 2: "landmark", 3: "users-round", 4: "truck",
    5: "package", 6: "shopping-cart", 7: "folder-kanban", 8: "trending-up", 9: "store",
    10: "bar-chart-3", 11: "boxes", 12: "badge-check", 13: "files",
}

# Built pages, keyed by sub-module number ("N.M") → {feature label: route name}.
# A label that matches a NavERP.md feature lights that bullet up; a label that doesn't
# is appended to the sub-module as an extra live leaf (used for core master-data pages
# that aren't called out as Module-0 bullets).
LIVE_LINKS = {
    # 0.1 Tenant & Subscription Management
    "0.1": {
        "Tenant Onboarding": "tenants:onboarding",          # bullet
        "Subscription & Billing": "tenants:subscription_list",   # bullet
        "Subscription Invoices": "tenants:subscriptioninvoice_list",  # extra (part of billing)
        "Custom Branding": "tenants:brandingsetting_list",  # bullet
        "Tenant Health Monitoring": "tenants:healthmetric_list",  # bullet
    },
    # 0.2 Identity & Access Management (IAM)
    "0.2": {
        "Centralized User Directory": "accounts:user_list",       # bullet
        "Provisioning & De-Provisioning": "accounts:invite_list",  # bullet (user provisioning)
    },
    # 0.3 RBAC & Permissions
    "0.3": {
        "Roles & Role Hierarchies": "accounts:role_list",   # bullet
    },
    # 0.5 User & Organization Management
    "0.5": {
        "Organization & Hierarchy Modeling": "core:orgunit_list",  # bullet
        "User Profiles & Preferences": "accounts:profile",  # bullet
        "Employments": "core:employment_list",  # extra (no exact bullet; HRM owns lifecycle)
    },
    # 0.7 Data Security & Encryption  (encryption keys live here, not under 0.1)
    "0.7": {
        "Key & Secret Management": "tenants:encryptionkey_list",   # bullet (key create/rotate/revoke)
    },
    # 0.9 Audit Trail & Activity Logging
    "0.9": {
        "Immutable Audit Logs": "core:auditlog_list",   # bullet
        "Activities": "core:activity_list",  # extra (task/call/note log; sub-module = Activity Logging)
    },
    # 0.14 Master Data & Reference Configuration  (the shared Party master + records)
    "0.14": {
        "Master Data Governance": "core:party_list",    # bullet (customer/vendor masters = Party)
        "Party Roles": "core:partyrole_list",           # extra
        "Addresses": "core:address_list",               # extra
        "Contact Methods": "core:contactmethod_list",   # extra
        "Party Relationships": "core:partyrelationship_list",  # extra
        "Documents": "core:document_list",              # extra
    },
    # ========================= Module 1 — Customer Relationship Management (CRM)
    # 1.1 Core Data Management — Accounts/Contacts are core.Party lenses; Leads are CRM-owned.
    "1.1": {
        "Contacts": "crm:contact_list",                 # bullet (person Party lens)
        "Accounts (Companies)": "crm:account_list",     # bullet (organization Party lens)
        "Leads (Potential Customers)": "crm:lead_list", # bullet
    },
    # 1.2 Sales Force Automation (SFA) — all three bullets now live (recreated in detail).
    "1.2": {
        "Opportunity Management (Deals)": "crm:opportunity_list",  # bullet
        "Pipeline Board": "crm:opportunity_board",                 # extra (Kanban)
        "Product Catalog (Quoting)": "crm:product_list",           # bullet
        "Quotes": "crm:quote_list",                                # extra (quote builder)
        "Price Books": "crm:pricebook_list",                       # extra
        "Forecasting": "crm:forecast",                             # bullet (real forecast dashboard)
        "Sales Quotas": "crm:salesquota_list",                     # extra
        "Territories": "crm:territory_list",                       # extra
    },
    # 1.3 Marketing Automation — all three bullets now live (recreated in detail).
    "1.3": {
        "Campaign Management": "crm:campaign_list",          # bullet
        "Campaign Members": "crm:campaignmember_list",       # extra (target-list segmentation)
        "Email Marketing": "crm:emailcampaign_list",         # bullet
        "Email Templates": "crm:emailtemplate_list",         # extra (HTML template builder)
        "Landing Pages & Forms": "crm:landingpage_list",     # bullet
        "Form Submissions": "crm:formsubmission_list",       # extra (web-to-lead captures)
    },
    # 1.4 Customer Service & Support (Help Desk) — all three bullets now live (recreated in detail).
    "1.4": {
        "Case / Ticket Management": "crm:case_list",              # bullet
        "SLA Policies": "crm:slapolicy_list",                     # extra (SLA targets/breach)
        "Solutions & Knowledge Base": "crm:knowledgearticle_list",  # bullet
        "KB Categories": "crm:kbcategory_list",                   # extra (KB hierarchy)
        # Bullet → the STAFF-facing access-management page (any staff user can open it). The
        # customer-facing portal_case_list is login-gated to portal users and would bounce staff
        # to the dashboard, so it's the secondary link — mirrors the 1.12 Vendor/Partner Portal wiring.
        "Customer Self-Service Portal": "crm:customerportalaccess_list",  # bullet (portal access mgmt)
        "Customer Portal": "crm:portal_case_list",                # extra (customer-facing entry, gated)
    },
    # 1.5 Activity & Communication Management — all three bullets now live (recreated in detail).
    "1.5": {
        "Task Management": "crm:task_list",                       # bullet (to-dos + recurring tasks)
        "Calendar Integration": "crm:calendarevent_list",        # bullet (meetings + invite link + ICS)
        "Email & Call Integration": "crm:communicationlog_list", # bullet (call logging + email/BCC sync)
    },
    # 1.6 Analytics & Reporting — both bullets now live (recreated in detail):
    # saved per-user dashboards (live-computed widgets) + saved standard reports (+ snapshots).
    "1.6": {
        "Dashboards": "crm:dashboard_list",              # bullet (saved dashboards + live widgets)
        "Standard Reports": "crm:report_list",           # bullet (4 canned reports + snapshots)
        "Analytics Overview": "crm:overview",            # extra (module KPI landing page)
    },
    # 1.7 Finance & Billing Management — recreated in detail; all three bullets now live. The
    # real Invoice/Payment/RecurringInvoice ledger is OWNED by Accounting (Module 2, L29) — CRM
    # adds the deal-facing wrappers (DealInvoice/PaymentReceipt) over it (draft hand-off).
    "1.7": {
        "Invoicing": "crm:dealinvoice_list",                       # bullet (quote→invoice conversion)
        "Payment Tracking": "crm:paymentreceipt_list",            # bullet (receipts + ledger allocations)
        "Expense Tracking": "crm:expense_list",                   # bullet (deal cost → true margin)
        "Recurring Invoices": "accounting:recurringinvoice_list", # extra — subscription schedules live in the ledger
    },
    # 1.8 Project & Delivery Management (Post-Sale)
    # 1.8 recreated in detail — Resource Allocation now points at a REAL workload/capacity board
    # (was a stub → timesheet_list); a Kanban Project Board fulfils the "Gantt/Kanban views" bullet.
    "1.8": {
        "Projects": "crm:crmproject_list",                  # bullet
        "Time Tracking": "crm:timesheet_list",              # bullet
        "Resource Allocation": "crm:resource_workload",     # bullet — workload/capacity board (overbooked vs free)
        "Project Board": "crm:crmproject_board",            # extra (Kanban board)
        "Milestones": "crm:crmmilestone_list",              # extra
        "Allocations": "crm:resourceallocation_list",       # extra (capacity bookings)
    },
    # 1.9 Document & Contract Management
    # 1.9 recreated in detail — File Repository now points at a REAL versioned repository organized by
    # account/deal (was a stub → contractdocument_list); Document Generation renders template merge-vars.
    "1.9": {
        "E-Signatures": "crm:contractdocument_list",     # bullet (contract + signer tracking + sign flow)
        "Document Generation": "crm:doctemplate_list",   # bullet (merge-var templates → generate on the contract)
        "File Repository": "crm:document_repository",     # bullet (versioned contract repo by account)
    },
    # 1.10 Automation & Workflow Engine
    # 1.10 recreated in detail — Webhooks now a REAL endpoint registry + signed delivery log (was a
    # stub → workflowrule_list); rules now actually execute via a manual Run engine.
    "1.10": {
        "Trigger-Based Actions (If This, Then That)": "crm:workflowrule_list",  # bullet (now with a Run engine)
        "Approval Processes": "crm:approvalrequest_list",  # bullet
        "Webhooks": "crm:webhook_list",                  # bullet (endpoint registry + signed deliveries)
        "Workflow Logs": "crm:workflowlog_list",         # extra (rule-execution audit)
        "Webhook Deliveries": "crm:webhookdelivery_list",  # extra (delivery audit)
    },
    # 1.11 Customer Success & Retention
    "1.11": {
        "Onboarding Pipelines": "crm:onboardingplan_list",      # bullet
        "Onboarding Templates": "crm:onboardingtemplate_list",  # extra (reusable blueprints)
        "Health Scoring": "crm:healthscore_list",               # bullet
        "Surveys & Feedback (NPS)": "crm:survey_list",          # bullet
        "Survey Analytics": "crm:survey_results",               # extra (NPS aggregate)
    },
    # 1.12 Inventory & Vendor Management
    "1.12": {
        "Purchase Orders (POs)": "crm:crm_po_list",         # bullet
        "Stock Tracking": "crm:productstock_list",          # bullet (on-hand + low-stock alerts)
        "Vendor/Partner Portal": "crm:partnerportalaccess_list",  # bullet (portal access mgmt)
        "Partner Portal": "crm:portal_dashboard",           # extra (partner-facing entry)
    },
    # ========================= Module 2 — Accounting & Finance
    # 2.1 Dashboard & Analytics — the KPI/alert/quick-action overview + report links. The four
    # dashboard widgets are sections of one page, so each deep-links to its anchor (#fragment)
    # instead of all pointing at the same bare URL.
    "2.1": {
        "Executive Summary": "accounting:accounting_dashboard#executive-summary",  # bullet (KPI cards)
        "Cash Flow Widget": "accounting:accounting_dashboard#cash-flow",  # bullet (net-cash chart)
        "Alert Center": "accounting:accounting_dashboard#alert-center",   # bullet (overdue invoices/bills)
        "Quick Actions": "accounting:accounting_dashboard#quick-actions",  # bullet (header actions)
        "Custom Reports": "accounting:trial_balance",            # bullet (trial balance report)
        "Forecasting": "accounting:cash_forecast",               # bullet (cash-flow projection)
    },
    # 2.2 General Ledger (GL)
    "2.2": {
        "Chart of Accounts": "accounting:glaccount_list",        # bullet
        "Journal Entries": "accounting:journal_entry_list",      # bullet
        "Journal Approval": "accounting:journal_entry_list",     # bullet (post action = approval)
        "Period Close": "accounting:fiscal_period_list",         # bullet
        "Account Reconciliation": "accounting:trial_balance",    # bullet (balance verification)
        "Allocation Rules": "accounting:cost_allocation_list",   # bullet (automatic cost distribution)
        "Audit Trail": "core:auditlog_list",                     # bullet (immutable log)
        "Multi-currency Support": "accounting:exchange_rate_list",  # bullet
    },
    # 2.3 Accounts Payable (AP)
    "2.3": {
        "Vendor Management": "accounting:vendor_profile_list",   # bullet (Party vendor role + terms)
        "Bill Capture": "accounting:bill_list",                  # bullet
        "Bill Processing": "accounting:bill_list",               # bullet (approval routing)
        "Payment Processing": "accounting:payment_list",         # bullet
        "Payment Scheduling": "accounting:payment_schedule",     # bullet (discount-aware due-date schedule)
        "Aging Reports": "accounting:ap_aging",                  # bullet
        "Early Payment Discounts": "accounting:payment_term_list",  # bullet
    },
    # 2.4 Accounts Receivable (AR)
    "2.4": {
        "Customer Management": "accounting:customer_profile_list",  # bullet (Party customer role + credit)
        "Invoice Generation": "accounting:invoice_list",         # bullet
        "Recurring Invoicing": "accounting:recurringinvoice_list",  # bullet (subscription/cadence billing)
        "Payment Collection": "accounting:payment_list",         # bullet
        "Cash Application": "accounting:allocation_list",        # bullet (payment→invoice matching)
        "Collections Management": "accounting:ar_aging",         # bullet
        "Credit Management": "accounting:customer_profile_list",  # bullet (credit limits/holds)
        "Aging Analysis": "accounting:ar_aging",                 # bullet
    },
    # 2.5 Cash Management
    "2.5": {
        "Bank Account Management": "accounting:bank_account_list",  # bullet
        "Bank Feeds": "accounting:bank_transaction_list",        # bullet (CSV import / feed rows)
        "Reconciliation Engine": "accounting:reconciliation_list",  # bullet
        "Cash Positioning": "accounting:accounting_dashboard",   # bullet (live cash position)
        "Treasury Forecasting": "accounting:cash_forecast",      # bullet (short/long-term cash projection)
        "Inter-company Transfers": "accounting:intercompany_list",  # bullet (cross-entity fund movements)
    },
    # 2.6 Fixed Assets
    "2.6": {
        "Asset Register": "accounting:fixed_asset_list",         # bullet
        "Depreciation Engine": "accounting:fixed_asset_list",    # bullet (per-asset run action)
        "Disposals & Retirements": "accounting:asset_disposal_list",  # bullet
    },
    # 2.7 Inventory & Cost Management (the accounting slice — Item master arrives with Inventory)
    "2.7": {
        "Cost of Goods Sold": "accounting:cost_allocation_list",  # bullet (cost allocation/posting)
        "Cost Allocation": "accounting:cost_allocation_list",     # extra
    },
    # 2.8 Payroll Integration — Employee Master is owned by HRM (Module 3); the rest is the GL slice.
    "2.8": {
        "Employee Master": "hrm:employee_list",                  # bullet (HRIS = HRM employee directory)
        "Payroll Journal": "accounting:payroll_run_list",        # bullet
        "Payroll Reconciliation": "accounting:payroll_run_list",  # bullet
    },
    # 2.9 Project/Job Costing
    "2.9": {
        "Project Setup": "accounting:project_list",              # bullet
        "Time & Expense": "accounting:job_cost_entry_list",      # bullet (time/expense booked to a job)
        "Profitability Analysis": "accounting:project_list",     # bullet (budget vs actual on detail)
        "Job Cost Entries": "accounting:job_cost_entry_list",    # extra
    },
    # 2.10 Multi-Entity & Consolidation
    "2.10": {
        "Entity Management": "core:orgunit_list",                # bullet (entities = OrgUnits)
        "Inter-company Transactions": "accounting:intercompany_list",  # bullet
        "Currency Translation": "accounting:exchange_rate_list",  # bullet (FX rates drive translation)
        "Consolidation Engine": "accounting:intercompany_list",  # bullet (eliminations)
    },
    # 2.11 Tax
    "2.11": {
        "Sales Tax Engine": "accounting:tax_code_list",          # bullet
        "Tax Returns": "accounting:tax_return_list",             # bullet
        "Tax Calendar": "accounting:tax_return_list",            # bullet (filing due dates)
    },
    # 2.12 Reporting & Compliance
    "2.12": {
        "Financial Statements": "accounting:balance_sheet",      # bullet
        "Management Reports": "accounting:profit_and_loss",      # bullet (P&L = the management report)
        "Scheduled Reports": "accounting:scheduled_report_list",  # bullet
        "Dashboards": "accounting:accounting_dashboard",         # bullet
    },
    # 2.13 Budgeting & Planning
    "2.13": {
        "Budget Creation": "accounting:budget_list",             # bullet
        "Version Control": "accounting:budget_list",             # bullet (budget versions)
        "Variance Analysis": "accounting:budget_variance",       # bullet
    },
    # 2.14 Audit & Controls
    "2.14": {
        "SOX Controls": "accounting:internal_control_list",      # bullet
        "Audit Trail": "core:auditlog_list",                     # bullet (immutable log)
        "Access Controls": "accounts:role_list",                 # bullet (RBAC)
        "Document Management": "core:document_list",              # bullet
    },
    # 2.15 Integration & API — each connector category deep-links to the integrations list filtered
    # to that category (the IntegrationConfig list already supports ?category=).
    "2.15": {
        "Banking APIs": "accounting:integration_list?category=banking",      # bullet
        "Payment Gateways": "accounting:integration_list?category=payments",  # bullet
        "E-commerce": "accounting:integration_list?category=ecommerce",      # bullet
        "CRM": "accounting:integration_list?category=crm",                   # bullet
        "ERP": "accounting:integration_list?category=erp",                   # bullet
        "HRIS": "accounting:integration_list?category=hris",                 # bullet
        "Tax Software": "accounting:integration_list?category=tax",          # bullet
        "Document Storage": "accounting:integration_list?category=storage",  # bullet
        "Custom API": "accounting:integration_list",                         # bullet (full list)
    },
    # ========================= Module 3 — Human Resource Management (HRM)
    # 3.1 Employee Management — employee is core.Party + core.Employment + hrm.EmployeeProfile.
    "3.1": {
        "Employee Directory": "hrm:employee_list",       # bullet
        "Employee Profile": "hrm:employee_list",         # bullet (rich profile = detail page)
        "Employment Details": "hrm:employee_list",        # bullet (job/dept/manager on the profile)
        "Document Management": "hrm:employee_document_list",   # bullet (personnel-file vault)
        "Employee Lifecycle": "hrm:employee_lifecycle_list",  # bullet (dated job-history timeline)
        "HRM Overview": "hrm:hrm_overview",               # extra (module landing/dashboard)
    },
    # 3.2 Organizational Structure — rebuilt with the full entity set. Departments/cost-centers are
    # canonical core.OrgUnit nodes enriched by HRM companion profiles (head/owner/budget/code);
    # the org chart is derived from Employment.manager; Company Setup reads OrgUnit + branding.
    "3.2": {
        "Company Setup": "hrm:company_setup",              # bullet (company OrgUnit + branding)
        "Department Management": "hrm:department_list",    # bullet (OrgUnit + HRM dept profile/head)
        "Designation/Job Titles": "hrm:designation_list",  # bullet (job grade + salary band + JD)
        "Organization Chart": "hrm:org_chart",             # bullet (reporting-line / by-department)
        "Cost Centers": "hrm:costcenter_list",             # bullet (budget allocation + owner)
        "Job Grades": "hrm:jobgrade_list",                 # extra (grade catalog for designations)
    },
    # 3.3 Employee Onboarding — template→program→task model; Welcome Kit fields live on the program.
    "3.3": {
        "Onboarding Tasks": "hrm:onboardingprogram_list",       # bullet (tasks are managed on the program)
        "Document Collection": "hrm:onboardingdocument_list",   # bullet
        "Asset Allocation": "hrm:assetallocation_list",         # bullet
        "Orientation Schedule": "hrm:orientationsession_list",  # bullet
        "Welcome Kit": "hrm:onboardingprogram_list",            # bullet (welcome fields live on the program)
        "Onboarding Templates": "hrm:onboardingtemplate_list",  # extra (reusable checklist admin)
        "Template Tasks": "hrm:onboardingtemplatetask_list",    # extra (cross-template task catalog)
    },
    # 3.9 Attendance Management
    "3.9": {
        "Check-in/Check-out": "hrm:attendancerecord_list",  # bullet
        "Attendance Calendar": "hrm:attendancerecord_list",  # bullet (date-filtered list)
        "Attendance Regularization": "hrm:attendanceregularization_list",  # bullet (correction requests + approval)
        "Shift Management": "hrm:shift_list",                # bullet
        "Geofencing": "hrm:geofence_list",                  # bullet (GPS zones for field attendance)
        "Shift Assignments": "hrm:shiftassignment_list",     # extra (employee↔shift mapping)
    },
    # 3.10 Leave Management
    "3.10": {
        "Leave Types": "hrm:leavetype_list",             # bullet
        "Leave Policy": "hrm:leave_policy",              # bullet (accrual/carry-forward engine + config)
        "Leave Balance": "hrm:leaveallocation_list",     # bullet (per-employee allocation + balance)
        "Leave Application": "hrm:leaverequest_list",    # bullet
        "Leave Calendar": "hrm:leaverequest_list",       # bullet (request list as calendar source)
        "Leave Encashment": "hrm:leaveencashment_list",  # extra (encash unused balance → payout workflow)
    },
    # 3.11 Time Tracking
    "3.11": {
        "Timesheet": "hrm:timesheet_list",                          # bullet
        "Project Time Tracking": "hrm:timesheet_list",              # bullet (entries logged on the timesheet hub)
        "Billable Hours": "hrm:timesheet_utilization_report",       # bullet (billable/utilization report)
        "Overtime Tracking": "hrm:overtimerequest_list",            # bullet
        "Timesheet Approval": "hrm:timesheet_list?status=pending",  # bullet (pending-approval queue)
        "Project Time Report": "hrm:project_time_report",           # extra (logged hours vs project budget)
    },
    # 3.4 Employee Offboarding — resignation→clearance→F&F→letters. Experience Letter opens the
    # dedicated letters landing page (eligible cases + relieving/experience letter actions).
    "3.4": {
        "Resignation Management": "hrm:separationcase_list",   # bullet
        "Exit Interview": "hrm:exitinterview_list",            # bullet
        "Clearance Process": "hrm:clearanceitem_list",         # bullet
        "F&F Settlement": "hrm:finalsettlement_list",          # bullet
        "Experience Letter": "hrm:offboarding_letters",        # bullet (relieving + experience letters)
    },
    # 3.12 Holiday Management — all 3 NavERP.md bullets now live: the calendar, per-employee
    # floating-holiday elections (optional holidays + quota), and location/eligibility policies.
    "3.12": {
        "Holiday Calendar": "hrm:publicholiday_list",              # bullet
        "Floating Holidays": "hrm:floatingholidayelection_list",   # bullet
        "Holiday Policies": "hrm:holidaypolicy_list",              # bullet
    },
    # 3.13 Salary Structure — one PayComponent catalog serves 4 bullets; ?component_type= deep-links
    # let Variable Pay / Tax Components / Reimbursements each highlight on their filtered slice
    # (most-specific-match nav). Employee assignments are an extra live leaf.
    "3.13": {
        "Pay Components": "hrm:paycomponent_list",                                   # bullet
        "Salary Structure Templates": "hrm:salarystructuretemplate_list",            # bullet
        "Variable Pay": "hrm:paycomponent_list?component_type=variable",             # bullet
        "Tax Components": "hrm:paycomponent_list?component_type=statutory_deduction",  # bullet
        "Reimbursements": "hrm:paycomponent_list?component_type=reimbursement",      # bullet
        "Employee Salary Structures": "hrm:employeesalarystructure_list",            # extra
    },
    # 3.14 Payroll Processing — the PayrollCycle (run/approval) + Payslip (holds/arrears) surfaces serve
    # all 5 bullets; ?query deep-links keep Payroll Approval / Salary Holds / Bonus distinct on their slices.
    "3.14": {
        "Payroll Run": "hrm:payrollcycle_list",                              # bullet (calc engine / cycles)
        "Payroll Approval": "hrm:payrollcycle_list?status=pending_approval",  # bullet (approval queue)
        "Salary Holds": "hrm:payslip_list?on_hold=True",                     # bullet (held payslips)
        "Arrears Calculation": "hrm:payslip_list",                          # bullet (arrears entered per payslip)
        "Bonus Processing": "hrm:payrollcycle_list?cycle_type=bonus",        # bullet (bonus/off-cycle runs)
    },
    # 3.15 Statutory Compliance — StatutoryReturn (scheme-filtered) is the challan/return register
    # for the schemes computed IN payroll (PF/ESI/TDS), so those bullets deep-link to it; PT/LWF are
    # STATE-scoped config, so their bullets point at StatutoryStateRule (the state-wise slab/rule
    # table IS the PT/LWF surface the bullet describes). Mirrors 3.14's deep-linked ?query pattern.
    "3.15": {
        "PF Management": "hrm:statutoryreturn_list?scheme=pf",               # bullet (PF challan/return)
        "ESI Management": "hrm:statutoryreturn_list?scheme=esi",             # bullet (ESI contributions)
        "PT Management": "hrm:statutorystaterule_list?scheme=pt",            # bullet (state-wise PT slabs)
        "TDS Management": "hrm:statutoryreturn_list?scheme=tds_24q",         # bullet (Form 24Q / Form 16)
        "LWF Management": "hrm:statutorystaterule_list?scheme=lwf",          # bullet (state-wise LWF rules)
        "Statutory Configuration": "hrm:statutoryconfig_detail",             # extra (employer registrations/rates)
        "Statutory Identifiers": "hrm:employeestatutoryidentifier_list",     # extra (UAN/PF/ESI per employee)
        "Compliance Calendar": "hrm:statutory_compliance_calendar",          # extra (cross-scheme due-date view)
    },
    # 3.16 Tax & Investment — TaxRegimeConfig serves Tax Regime; InvestmentDeclaration serves Investment
    # Declaration; InvestmentProof (pending filter) serves Investment Proof; TaxComputation serves Tax
    # Computation; Form 16 Generation routes through the computation list (its detail links to the
    # form16_partb report — no standalone Form-16 model, per the reuse of StatutoryReturn(tds_form16)).
    "3.16": {
        "Tax Regime": "hrm:taxregimeconfig_list",                                   # bullet (old/new slabs + comparison)
        "Investment Declaration": "hrm:investmentdeclaration_list",                 # bullet (80C/80D/HRA/…)
        "Investment Proof": "hrm:investmentproof_list?verification_status=pending",  # bullet (upload + verify)
        "Tax Computation": "hrm:taxcomputation_list",                               # bullet (annual projection engine)
        "Form 16 Generation": "hrm:taxcomputation_list",                            # bullet (detail → Form 16 Part B)
        "Regime Comparison": "hrm:tax_regime_comparison",                           # extra (old-vs-new side-by-side)
    },
    # 3.17 Payout & Reports — PayoutBatch (generate/approve/disburse from a locked cycle) serves Bank
    # Integration; PayslipDistribution serves Payslip Generation; the payout-exceptions report + batch
    # payment-register serve Payment Register; BankReconciliation serves Reconciliation.
    "3.17": {
        "Bank Integration": "hrm:payoutbatch_list",                                 # bullet (disbursement batches + bank file)
        "Payslip Generation": "hrm:payslipdistribution_list",                       # bullet (digital payslip send/view/download)
        "Payment Register": "hrm:payout_exceptions",                                # bullet (exception/register reports; batch detail → register)
        "Reconciliation": "hrm:bankreconciliation_list",                            # bullet (bank statement match by UTR)
    },
    # 3.18 Goal Setting — first Performance-Management sub-module (OKR mechanics only; review
    # cycles/ratings/360/kudos/PIPs are later 3.19-3.21). Objective+KeyResult CRUD serve OKR/KPI
    # Management + Weight Assignment (KR weight editable on objective_detail); the objective_tree
    # serves Goal Alignment (cascade view); GoalPeriod serves Goal Timeline; the GoalCheckIn history
    # log serves Goal Tracking.
    "3.18": {
        "OKR/KPI Management": "hrm:objective_list",            # bullet (Objective + KeyResult CRUD)
        "Goal Alignment": "hrm:objective_tree",               # bullet (cascade/alignment tree view)
        "Weight Assignment": "hrm:objective_list",            # bullet (per-KR weight on objective_detail)
        "Goal Timeline": "hrm:goalperiod_list",               # bullet (quarterly/annual cycle catalog)
        "Goal Tracking": "hrm:goalcheckin_list",              # bullet (check-in history log)
    },
    # 3.19 Performance Review — second Performance-Management sub-module (formal appraisal cycles;
    # continuous feedback/kudos/1:1s are 3.20, PIP/coaching is 3.21). ReviewCycle serves Review
    # Cycles; the review list filtered by review_type serves Self-Assessment/Manager Review; the
    # unfiltered list (all review types incl. peer/upward) serves 360 Feedback; the calibration
    # board serves Calibration.
    "3.19": {
        "Review Cycles": "hrm:reviewcycle_list",                              # bullet (cycle catalog + phase machine)
        "Self-Assessment": "hrm:performancereview_list?review_type=self",     # bullet (self review_type slice)
        "Manager Review": "hrm:performancereview_list?review_type=manager",   # bullet (manager review_type slice)
        "360° Feedback": "hrm:performancereview_list",                        # bullet (all review types incl. peer/upward)
        "Calibration": "hrm:calibration_board",                               # bullet (calibration board)
    },
    # 3.20 Continuous Feedback — third Performance-Management sub-module: the ongoing/informal layer
    # (real-time kudos/appreciation/constructive feedback incl. a request-pull workflow + anonymous
    # masking; 1:1 meetings with shared/private notes + action items; a computed given/received/
    # requested feedback dashboard). PIP/warning-letters/coaching are 3.21. Real-time Feedback →
    # the Feedback CRUD; Anonymous Feedback → the is_anonymous=1 slice (most-specific match wins).
    "3.20": {
        "Real-time Feedback": "hrm:feedback_list",                            # bullet (Feedback CRUD, all types/visibility)
        "1:1 Meetings": "hrm:oneononemeeting_list",                           # bullet (OneOnOneMeeting + action items)
        "Feedback Dashboard": "hrm:feedback_dashboard",                       # bullet (given/received/requested computed view)
        "Anonymous Feedback": "hrm:feedback_list?is_anonymous=1",             # bullet (is_anonymous=True slice)
    },
    # 3.21 Performance Improvement — the FOURTH & FINAL Performance-Management sub-module (the
    # corrective-action / disciplinary layer): Performance Improvement Plans with an HR-approval
    # workflow, progressive warning letters, and manager-only coaching notes. The most confidential
    # HRM records — Coaching Notes intentionally has NO employee-facing view (coach/admin only).
    "3.21": {
        "PIP Management": "hrm:pip_list",                # bullet (PerformanceImprovementPlan CRUD + workflow)
        "Warning Letters": "hrm:warningletter_list",     # bullet (WarningLetter CRUD + issue/acknowledge/print)
        "Coaching Notes": "hrm:coachingnote_list",       # bullet (CoachingNote — coach/admin only)
    },
    # 3.22 Training Management — Instructor-Led Training scheduling/catalog (a NEW HRM domain, not a
    # Performance-Management continuation). Classroom/Virtual/External all resolve to filtered slices
    # of the one TrainingSession list (delivery_mode) so each highlights on its own page (most-specific
    # match wins). 3.23 Learning Management (LMS) and 3.24 Training Administration (nomination/
    # attendance/feedback/certificates/budget) are deferred sibling sub-modules, not built here.
    "3.22": {
        "Training Calendar": "hrm:training_calendar",                              # bullet (upcoming TrainingSession query view)
        "Training Catalog": "hrm:trainingcourse_list",                             # bullet (TrainingCourse CRUD)
        "Classroom Training": "hrm:trainingsession_list?delivery_mode=classroom",  # bullet (classroom slice)
        "Virtual Training": "hrm:trainingsession_list?delivery_mode=virtual",      # bullet (virtual slice)
        "External Training": "hrm:trainingsession_list?delivery_mode=external",    # bullet (external slice)
    },
    # 3.23 Learning Management (LMS) — the self-paced digital-learning layer on top of the 3.22
    # TrainingCourse catalog (no new course table). "Assessments" is a filtered slice of the Course
    # Content list (content_type=assessment) rather than a dedicated question-bank UI this pass;
    # "Gamification" is the computed points leaderboard (levels/leaderboard derived, not stored).
    # 3.24 Training Administration (nomination/attendance/feedback/certificates/budget) is deferred.
    "3.23": {
        "Course Content": "hrm:learningcontentitem_list",                              # bullet (LearningContentItem CRUD)
        "Learning Paths": "hrm:learningpath_list",                                     # bullet (LearningPath CRUD)
        "Assessments": "hrm:learningcontentitem_list?content_type=assessment",         # bullet (assessment-type slice)
        "Gamification": "hrm:learning_leaderboard",                                    # bullet (computed points leaderboard)
        "Progress Tracking": "hrm:learningprogress_list",                             # bullet (LearningProgress CRUD)
    },
    # 3.24 Training Administration — the operational/admin layer over 3.22 (TrainingSession) + 3.23
    # (LearningProgress): nomination + approval workflow, attendance, feedback, certificates. "Training
    # Budget" is a COMPUTED aggregate view (TrainingSession costs vs CostCenterProfile.budget_annual) —
    # no stored model. Final sub-module of the 3.22/3.23/3.24 training cluster.
    "3.24": {
        "Nomination": "hrm:trainingnomination_list",                # bullet (TrainingNomination CRUD + approval workflow)
        "Attendance Tracking": "hrm:trainingattendance_list",        # bullet (TrainingAttendance CRUD)
        "Training Feedback": "hrm:trainingfeedback_list",            # bullet (TrainingFeedback CRUD)
        "Certificates": "hrm:trainingcertificate_list",              # bullet (TrainingCertificate CRUD + issue/revoke/print)
        "Training Budget": "hrm:training_budget",                    # bullet (computed budget aggregate view)
    },
    # 3.25 Personal Information (Self-Service) — the ESS layer over the existing EmployeeProfile.
    # Profile Management/Contact Update get NO new model — they're the my_info hub + its direct-edit
    # form over EmployeeProfile's existing flat columns. Emergency Contacts/Bank Details/Family
    # Details are proper child tables lifting the 2-slot/1-slot flat-column limits. The
    # EmployeeInfoChangeRequest maker-checker workflow connecting all five is an extra live leaf.
    "3.25": {
        "Profile Management": "hrm:my_info",                        # bullet (ESS hub — view + employment context)
        "Contact Update": "hrm:my_info_edit",                       # bullet (direct-edit: address/personal email/mobile/photo)
        "Emergency Contacts": "hrm:emergencycontact_list",          # bullet (EmergencyContact CRUD, direct self-edit)
        "Bank Details": "hrm:employeebankaccount_list",             # bullet (EmployeeBankAccount CRUD, admin-gated writes)
        "Family Details": "hrm:familymember_list",                  # bullet (FamilyMember CRUD, admin-gated writes)
        "Change Requests": "hrm:changerequest_list",                # extra (EmployeeInfoChangeRequest maker-checker queue)
    },
    # 3.26 Request Management (Self-Service) — the employee request portal. Leave Requests /
    # Attendance Regularization reuse the existing 3.10/3.9 models verbatim (NO new model — this is
    # the second place their list URLs surface, alongside 3.9/3.10). Document Requests / ID Card
    # Request / Asset Requests are the three new request models (CRUD + submit/approve/reject +
    # fulfil/issue). My Requests is the unified ESS hub over all five request types.
    "3.26": {
        "Leave Requests": "hrm:leaverequest_list",                          # bullet (reuse 3.10 LeaveRequest, no new model)
        "Attendance Regularization": "hrm:attendanceregularization_list",   # bullet (reuse 3.9 AttendanceRegularization, no new model)
        "Document Requests": "hrm:documentrequest_list",                    # bullet (new DocumentRequest CRUD + workflow)
        "ID Card Request": "hrm:idcardrequest_list",                        # bullet (new IdCardRequest CRUD + workflow)
        "Asset Requests": "hrm:assetrequest_list",                          # bullet (new AssetRequest CRUD + workflow)
        "My Requests": "hrm:my_requests",                                   # extra (unified ESS hub over all five types)
    },
    # 3.27 Communication Hub — the internal employee-comms surface. Announcements (audience-targeted
    # admin posts), Birthday/Anniversary (a derived celebrations view, no model), Surveys (engagement
    # surveys + responses), Suggestions (employee idea box, admin-reviewed). Help Desk now resolves to
    # the dedicated 3.36 Helpdesk ticket list (built) — no longer the interim Suggestions box.
    "3.27": {
        "Announcements": "hrm:announcement_list",          # bullet (new Announcement CRUD + publish/pin/archive)
        "Birthday/Anniversary": "hrm:celebrations",        # bullet (derived view, no model)
        "Surveys": "hrm:survey_list",                      # bullet (new Survey + SurveyResponse engine)
        "Suggestions": "hrm:suggestion_list",              # bullet (new Suggestion, clones the 3.26 workflow)
        "Help Desk": "hrm:ticket_list",                    # bullet (now live — 3.36 Helpdesk tickets)
    },
    # 3.28 HR Reports — derived, read-only, @tenant_admin_required aggregate pages (no models). The
    # `hr_reports_index` landing hub is reachable from each report's Back link (not itself a bullet —
    # NavERP.md 3.28 has exactly 5 report bullets, each deep-linking to its drill-in report).
    "3.28": {
        "Headcount Report": "hrm:headcount_report",   # bullet (active/new-joins/exits, dept/designation/type)
        "Attrition Report": "hrm:attrition_report",   # bullet (SHRM annualized turnover, voluntary/involuntary, trend)
        "Diversity Report": "hrm:diversity_report",   # bullet (gender/age/tenure demographics, dept cross-tab)
        "Cost Reports": "hrm:cost_report",            # bullet (salary cost total + department-wise, CTC breakdown)
        "Hiring Reports": "hrm:hiring_report",        # bullet (time-to-hire/fill, source mix, funnel, offer accept %)
    },
    # 3.29 Attendance Reports — derived, read-only, @tenant_admin_required (no models). The
    # Utilization Report bullet REUSES the existing 3.11 timesheet_utilization_report (not rebuilt).
    "3.29": {
        "Attendance Summary": "hrm:attendance_summary_report",   # bullet (status breakdown + attendance %, trend)
        "Late/Early Departure": "hrm:late_early_report",         # bullet (late/early counts + avg mins, top offenders)
        "Absenteeism Report": "hrm:absenteeism_report",          # bullet (absence rate + frequent absentees, trend)
        "Overtime Report": "hrm:overtime_report",                # bullet (OT hours + pay-equivalent hours, no currency)
        "Utilization Report": "hrm:timesheet_utilization_report",  # bullet (REUSE 3.11 utilization report)
    },
    # 3.30 Leave Reports — derived, read-only, @tenant_admin_required (no models). Leave balance is
    # derived (allocated − used − encashed via _used_days_subquery). Comp-off has no first-class model.
    "3.30": {
        "Leave Register": "hrm:leave_register_report",   # bullet (employee×type grid: allocated/used/balance)
        "Leave Liability": "hrm:leave_liability_report", # bullet (encashable balance × rate, CTC/365 estimate fallback)
        "Comp-off Report": "hrm:comp_off_report",        # bullet (earned OT-comp-leave vs availed comp-off leave)
        "Leave Trend": "hrm:leave_trend_report",         # bullet (monthly leave-days by type/department, top takers)
    },
    # 3.31 Payroll Reports — derived, read-only, @tenant_admin_required (no models).
    # payroll_reports_index is the landing hub, not itself a bullet. cost_center_report has no direct
    # bullet either (NavERP.md's single "Cost Analysis" bullet covers both ctc_report and
    # cost_center_report) — reachable via the hub + a cross-link on ctc_report.html.
    "3.31": {
        "Salary Register": "hrm:salary_register_report",  # bullet (per-cycle earnings/deductions/net grid)
        "Tax Reports": "hrm:tax_report",                   # bullet (TDS/regime split, declarations, Form 16 register)
        "Statutory Reports": "hrm:statutory_report",       # bullet (PF/ESI/PT/LWF register, masked employee coverage)
        "Cost Analysis": "hrm:ctc_report",                 # bullet (structural CTC breakdown; cost_center_report cross-linked)
    },
    # 3.32 Analytics Dashboard — 2 new models (HRDashboard/HRDashboardWidget, mirrors CRM 1.6's
    # Analytics Dashboard mechanic) + 3 derived @tenant_admin_required views. Custom Dashboards ->
    # the CRUD list (any tenant user, @login_required); the other 3 bullets -> admin-only derived views.
    "3.32": {
        "Executive Dashboard": "hrm:executive_dashboard",   # bullet (curated KPI strip + alerts, admin-only)
        "Custom Dashboards": "hrm:hr_dashboard_list",        # bullet (saved widget dashboards, owner's + shared)
        "Predictive Analytics": "hrm:predictive_analytics",  # bullet (attrition-risk heuristic + hiring-needs projection, admin-only)
        "Benchmarking": "hrm:benchmarking",                  # bullet (period-over-period + vs-target scorecard, admin-only)
    },
    # 3.33 Asset Management — 2 new models (Asset, AssetMaintenance) + a nullable AssetAllocation.asset FK.
    # Asset Allocation deep-links into the register filtered to currently-assigned assets; Asset Return stays
    # on the existing 3.3 AssetAllocation list (its own system of record) filtered to returned; Depreciation
    # has no dedicated page — book value/accumulated depreciation are computed columns on the register itself.
    "3.33": {
        "Asset Register": "hrm:asset_list",                           # bullet (the central register)
        "Asset Allocation": "hrm:asset_list?status=assigned",          # bullet (register filtered to assigned)
        "Asset Return": "hrm:assetallocation_list?status=returned",    # bullet (existing 3.3 allocation list, filtered)
        "Maintenance": "hrm:assetmaintenance_list",                    # bullet (service/repair/AMC/warranty records)
        "Depreciation": "hrm:asset_list",                              # bullet (register w/ book-value column)
    },
    # 3.34 Expense Management — 3 new models (ExpenseCategory, ExpenseClaim, ExpenseClaimLine).
    # Approval Workflow deep-links to the "submitted" awaiting-action queue (manager_approved rows are one
    # status-dropdown click away); Reimbursement to the "approved" ready-to-pay queue; Policy Compliance to
    # the category list (where the limits/thresholds are configured — violations surface as claim badges).
    "3.34": {
        "Expense Categories": "hrm:expensecategory_list",
        "Expense Claims": "hrm:expenseclaim_list",
        "Approval Workflow": "hrm:expenseclaim_list?status=submitted",
        "Reimbursement": "hrm:expenseclaim_list?status=approved",
        "Policy Compliance": "hrm:expensecategory_list",
    },
    # 3.35 Travel Management — 3 new models (TravelPolicy, TravelRequest, TravelBooking); settlement reuses
    # hrm.ExpenseClaim (3.34). Booking Integration has no standalone page (bookings are inline rows under a
    # trip) so it deep-links to the request list. Travel Advance -> "approved" (advance actions actionable);
    # Travel Settlement -> "completed" (the closed-loop slice) — both one status-dropdown click from the list.
    "3.35": {
        "Travel Request": "hrm:travelrequest_list",
        "Booking Integration": "hrm:travelrequest_list",
        "Travel Policy": "hrm:travelpolicy_list",
        "Travel Advance": "hrm:travelrequest_list?status=approved",
        "Travel Settlement": "hrm:travelrequest_list?status=completed",
    },
    # 3.36 Helpdesk — the employee HR/IT/Admin/Facilities service desk. Ticket Management -> the central
    # ticket register; Ticket Categories -> the routing taxonomy (doubling as the KB taxonomy); SLA
    # Management -> the per-priority response/resolution target catalog (where SLAs are defined);
    # Knowledge Base -> the internal FAQ/self-help repository; Satisfaction Survey -> the CSAT-rated
    # tickets (?rated=1). An extra "SLA Breaches" leaf deep-links to open tickets past their SLA
    # (?sla=breached) — most-specific-match keeps it distinct from the bare Ticket Management list.
    "3.36": {
        "Ticket Management": "hrm:ticket_list",
        "Ticket Categories": "hrm:helpdeskcategory_list",
        "SLA Management": "hrm:helpdesksla_list",
        "Knowledge Base": "hrm:knowledgearticle_list",
        "Satisfaction Survey": "hrm:ticket_list?rated=1",
        "SLA Breaches": "hrm:ticket_list?sla=breached",
    },
    # 3.37 Compensation & Benefits — 4 of the 6 NavERP.md bullets are live; Compensation Planning
    # (merit/promotion cycles) and a formal monetary Rewards & Recognition are deferred (peer kudos
    # already ship in 3.20 Feedback/KudosBadge), so those two bullets stay roadmap placeholders.
    # Salary Benchmarking -> market-percentile catalog; Benefits Administration -> the benefit-plan
    # catalog; Flexible Benefits -> the opt-in/opt-out enrollment elections; Stock/ESOP Management ->
    # the equity-grant register (computed cliff/graded vesting).
    "3.37": {
        "Salary Benchmarking": "hrm:salarybenchmark_list",
        "Benefits Administration": "hrm:benefitplan_list",
        "Flexible Benefits": "hrm:employeebenefitenrollment_list",
        "Stock/ESOP Management": "hrm:equitygrant_list",
    },
    # 3.38 Talent Management & Succession Planning — 5 of the 6 bullets live. TWO of them need NO new
    # table and REUSE what already ships: "Talent Reviews" -> the 3.19 calibration board, and "Internal
    # Mobility" -> JobRequisition(posting_type=internal) from 3.5 (+ the 3.6 JobApplication pipeline).
    # "Retention Strategies" deep-links to the high-flight-risk member slice. "Career Pathing" is DEFERRED
    # (needs a CareerPath + EmployeeSkill taxonomy of its own), so it stays a roadmap placeholder.
    # Everything here is @tenant_admin_required — HiPo/9-box/flight-risk/bench data is HR-confidential.
    "3.38": {
        "Talent Pool": "hrm:talentpool_list",
        "Succession Planning": "hrm:successionplan_list",
        "Talent Reviews": "hrm:calibration_board",                            # REUSE (3.19)
        "Internal Mobility": "hrm:jobrequisition_list?posting_type=internal",  # REUSE (3.5/3.6)
        "Retention Strategies": "hrm:talentpoolmembership_list?flight_risk=high",
        "9-Box Grid": "hrm:talent_nine_box",                                  # extra (computed grid)
        "Talent Pool Members": "hrm:talentpoolmembership_list",               # extra
    },
    # 3.39 Compliance & Legal — all 6 bullets live, but "Disciplinary Actions" needs NO new model: it
    # REUSES the 3.21 WarningLetter (progressive discipline + issue/acknowledge + printable letter).
    # Labor Law Compliance deep-links to the labour-law slice of the one ComplianceRegister; Statutory
    # Registers is the same register unfiltered (muster rolls / wage registers / inspection reports).
    # Grievance is CONFIDENTIAL (own-vs-admin; is_anonymous masks the complainant from non-admins).
    "3.39": {
        "Labor Law Compliance": "hrm:complianceregister_list?register_type=labor_law_requirement",
        "Contract Management": "hrm:employmentcontract_list",
        "Policy Management": "hrm:hrpolicy_list",
        "Disciplinary Actions": "hrm:warningletter_list",                    # REUSE (3.21)
        "Grievance Handling": "hrm:grievance_list",
        "Statutory Registers": "hrm:complianceregister_list",
        "Policy Acknowledgments": "hrm:policyacknowledgment_list",           # extra
    },
    # 3.40 Workforce Planning — the demand side is the WorkforcePlan (+ its per-department lines), the
    # supply side is the EmployeeSkill inventory, and Gap/Analytics are derived views over both. Budget
    # Planning deep-links to the approved plans (that's the slice whose budget_impact is committed);
    # most-specific match wins, so it highlights on its own filtered page.
    "3.40": {
        "Demand Forecasting": "hrm:workforceplan_list",
        "Supply Analysis": "hrm:employeeskill_list",
        "Gap Analysis": "hrm:workforce_gap_analysis",
        "Budget Planning": "hrm:workforceplan_list?status=approved",
        "Scenario Planning": "hrm:workforcescenario_list",
        "Workforce Analytics": "hrm:workforce_analytics",
    },
    # 3.41 Employee Engagement & Wellbeing — an EXTENSION pass. "Engagement Surveys" deep-links to the NEW
    # SurveyActionPlan list (the one real gap this pass fills); pulse/eNPS survey DELIVERY itself stays
    # reachable via 3.27's own "Surveys" bullet (hrm:survey_list) — not duplicated here. The other four
    # bullets are program_type-filtered slices of the single WellbeingProgram catalog (the 3.40 "Budget
    # Planning" pattern: a query-string filter on the base entity's own list, most-specific match wins).
    "3.41": {
        "Engagement Surveys": "hrm:surveyactionplan_list",
        "Wellbeing Programs": "hrm:wellbeingprogram_list?program_type=wellness_challenge",
        "Work-Life Balance": "hrm:flexibleworkarrangement_list",
        "Employee Assistance": "hrm:wellbeingprogram_list?program_type=eap_counseling",
        "Culture & Values": "hrm:wellbeingprogram_list?program_type=culture_assessment",
        "Social Connect": "hrm:wellbeingprogram_list?program_type=team_event",
    },
    # 3.5 Job Requisition — authorization-to-hire hub, sequential approval chain, JD templates. The
    # list bullets deep-link to filtered slices of the one requisition list so each highlights on its
    # own page (most-specific match wins): Job Posting → the posted/published openings, Approval
    # Workflow → the pending-approval queue. Budget Management + Requisition Tracking are both the
    # full unfiltered list (budget columns / all-status tracking) so they co-highlight only there.
    "3.5": {
        "Job Posting": "hrm:jobrequisition_list?status=posted",                    # bullet (published openings)
        "Approval Workflow": "hrm:jobrequisition_list?status=pending_approval",    # bullet (pending queue)
        "Budget Management": "hrm:jobrequisition_list",                            # bullet (salary/cost columns)
        "Job Templates": "hrm:jobdescriptiontemplate_list",                        # bullet (reusable JD library)
        "Requisition Tracking": "hrm:jobrequisition_list",                         # bullet (all-status tracking)
    },
    # 3.6 Candidate Management — ATS candidate database, applications pipeline, talent-pool tags,
    # recruiting email templates + an append-only communication log, and the public career portal.
    # Resume Parser/Database/Search all resolve to the one candidate list (its filter bar covers
    # name/skill/resume-text search; NLP parsing is deferred) — they co-highlight on that page.
    "3.6": {
        "Application Portal": "hrm:application_list",           # bullet (applications pipeline — staff view)
        "Resume Parser": "hrm:candidate_list",                 # bullet (candidate DB w/ resume_text search)
        "Candidate Database": "hrm:candidate_list",            # bullet (talent pool + filters)
        "Resume Search": "hrm:candidate_list",                 # bullet (skill / full-text filter bar)
        "Candidate Communication": "hrm:communication_list",   # bullet (append-only email log)
        "Email Templates": "hrm:emailtemplate_list",           # extra (recruiting template library)
        "Talent Pool Tags": "hrm:candidatetag_list",           # extra (tag catalog)
        "Public Careers Page": "hrm:careers_list",             # extra (web-to-candidate portal)
    },
    # 3.7 Interview Process — interview scheduling + panel + structured scorecards over the 3.6
    # JobApplication spine. Scheduling/Panel/Reminders resolve to the interview list (panel is managed
    # on the interview detail; reminders are detail-page actions); Video Interview deep-links to the
    # video-mode filter (most-specific match highlights it distinctly); Feedback is its own scorecard
    # list. Live calendar/Zoom-Teams-Meet/SMS dispatch + AI scoring are deferred.
    "3.7": {
        "Interview Scheduling": "hrm:interview_list",          # bullet (calendar/slot list)
        "Interview Panel": "hrm:interview_list",               # bullet (panel managed on interview detail)
        "Interview Feedback": "hrm:interviewfeedback_list",    # bullet (structured scorecards)
        "Video Interview": "hrm:interview_list?mode=video",    # bullet (video-mode filtered slice)
        "Interview Reminders": "hrm:interview_list",           # bullet (invite/reminder = detail actions)
    },
    # 3.8 Offer Management — offer letter + multi-step approval + tracking + background check + pre-boarding
    # over the 3.6 JobApplication spine. Offer Letter Generation → the reusable letter-template library;
    # Offer Approval deep-links to the pending-approval queue (most-specific slice highlights it distinctly);
    # Offer Tracking → the all-status offer list; Background Verification → its own BGV records; Pre-boarding
    # → the accepted offers whose pre-boarding checklist is active (managed on the offer detail). Approval
    # chain + status machine mirror 3.5 Job Requisition; emails reuse the 3.6 candidate pipeline. Live
    # e-sign / background-check vendor APIs + acceptance-rate analytics are deferred.
    "3.8": {
        "Offer Letter Generation": "hrm:offerlettertemplate_list",     # bullet (letter-template library)
        "Offer Approval": "hrm:offer_list?status=pending_approval",    # bullet (pending-approval queue)
        "Offer Tracking": "hrm:offer_list",                            # bullet (all-status offer list)
        "Background Verification": "hrm:backgroundverification_list",  # bullet (BGV records)
        "Pre-boarding": "hrm:offer_list?status=accepted",              # bullet (accepted offers = active preboarding)
    },

    # ========================================= Module 4 — Supply Chain Management (SCM)
    # 4.1 owns the procure-to-pay transaction chain (PR → RFQ → quote award → PO → GRN → 3-way match
    # against accounting.Bill). Ownership note: NavERP-ERD.md originally listed PurchaseRequisition/
    # RFQ/VendorQuote/GoodsReceiptNote under Module 6 (Procurement); SCM ships first, so per the L29
    # "module that ships first owns the spine" precedent it owns them and Module 6 will EXTEND these
    # tables by FK (strategic sourcing, e-auctions, contract authoring, scorecards) rather than
    # re-declaring parallel schema. The ERD rows were updated to match.
    "4.1": {
        "Purchase Requisition": "scm:requisition_list",        # bullet (internal requests + approval + budget check)
        "Request for Quotation (RFQ)": "scm:rfq_list",         # bullet (multi-vendor RFQ + quote comparison)
        "Purchase Order (PO) Management": "scm:purchaseorder_list",  # bullet (generate/approve/amend/cancel)
        # The NavERP bullet asks for a supplier self-service portal. A real vendor login is deferred:
        # lesson L32 bars a STAFF sidebar bullet from pointing at a login-gated portal page, so this
        # points at the staff-side order list where acknowledgement/ship-date are recorded instead.
        "Vendor Portal": "scm:purchaseorder_list?status=sent",  # bullet (orders awaiting vendor acknowledgement)
        "Invoice Reconciliation": "scm:goodsreceipt_list",      # bullet (GRN + 3-way match vs accounting.Bill)
    },
    # 4.2 Supplier Relationship Management — SRM on the core.Party supplier spine (ships-first owner of
    # the supplier scorecard/contract/risk tables per L29; Module 6 extends by FK). Scorecards derive
    # delivery/quality/price/responsiveness from real 4.1 GRN + RFQQuote signals.
    "4.2": {
        "Supplier Onboarding": "scm:supplierprofile_list",       # bullet (qualification + due diligence)
        "Supplier Scorecard": "scm:scorecard_list",              # bullet (signal-derived performance rating)
        "Contract Management": "scm:contract_list",              # bullet (renewal alerts + T&C)
        "Supplier Catalog Management": "scm:catalog_list",       # bullet (free-text price lists, pending core.Item)
        "Risk Management": "scm:riskassessment_list",            # bullet (financial/geo/compliance/operational)
    },
    # 4.3 Inventory Management — SCM owns the inventory SPINE (Item/UOM/Location/StockMove/LotSerial)
    # ships-first (L29/L36); Module 5 Inventory will extend by FK. On-hand + valuation are DERIVED from
    # the append-only StockMove ledger, never stored.
    "4.3": {
        "Stock Control": "scm:item_list",                        # bullet (items + derived on-hand + lot/serial)
        "Warehouse Transfer": "scm:stocktransfer_list",          # bullet (between-location transfers, posts StockMove)
        "Stock Adjustment": "scm:stockadjustment_list",          # bullet (write-off/damage/cycle-count, posts StockMove)
        "Reorder Point Automation": "scm:reorder_alerts",        # bullet (low-stock alerts + one-click requisition)
        "Inventory Valuation": "scm:valuation_report",           # bullet (FIFO/LIFO/WAC over StockMove cost layers)
    },
    # 4.4 Warehouse Management — layered ON the 4.3 spine: bins are Locations (extended with
    # capacity/pick_sequence/abc_class), every movement posts through the same StockMove service, and
    # cycle counts resolve into the existing StockAdjustment rather than a second correction path.
    "4.4": {
        "Inbound Operations": "scm:putawaytask_list",            # bullet (receiving -> directed putaway)
        "Outbound Operations": "scm:picktask_list",              # bullet (wave/batch/zone picking + packing)
        "Bin/Location Management": "scm:location_list",          # bullet (the 4.3 locations, now with bin attributes)
        "Cycle Counting": "scm:cyclecounttask_list",             # bullet (scheduled counts -> StockAdjustment)
        "Yard Management": "scm:yardvisit_list",                 # bullet (trucks/trailers + dock doors)
    },
    # 4.5 OWNS the SalesOrder/SalesOrderLine document (ships-first, L28/L29/L36/L37): CRM built the
    # pre-order pipeline (Lead -> Opportunity -> Quote) across all twelve of its sub-modules and
    # deliberately never built an order, and Modules 8/9 don't exist. Module 8.6 "Order Management"
    # is a DIFFERENT, later feature set (amend/cancel with impact analysis, revenue recognition)
    # that will FK into this order rather than re-declare it. See research-scm-4.5.md.
    "4.5": {
        "Order Capture": "scm:salesorder_list",                       # bullet (manual entry + quote conversion)
        "Order Validation": "scm:salesorder_list?status=on_hold",     # bullet (the credit/fraud hold queue)
        "Order Allocation": "scm:salesorderallocation_list",          # bullet (soft reservations per location)
        "Backorder Management": "scm:salesorder_list?status=partially_fulfilled",  # bullet (part-covered orders)
        "Customer Notifications": "scm:salesorder_list?status=fulfilled",          # bullet (the notify hooks)
    },
    # 4.6 Transportation Management System (TMS) — Carrier master (spine-backed profile on core.Party),
    # Load (route + cube utilization), Shipment (append-only TrackingEvent log + POD), FreightInvoice
    # (3-way freight audit → drafts an accounting.Bill, L29). Route Planning and Load Optimization are
    # two facets of the same Load page (they co-highlight — the Load detail carries both the route stops
    # and the derived weight/volume utilization headline).
    "4.6": {
        "Route Planning": "scm:load_list",                # bullet (loads + ordered route stops)
        "Freight Audit & Payment": "scm:freightinvoice_list",  # bullet (billed-vs-contract match → Bill draft)
        "Carrier Management": "scm:carrier_list",         # bullet (3PL master + rate cards + scorecard)
        "Shipment Tracking": "scm:shipment_list",         # bullet (status/GPS event log + POD)
        "Load Optimization": "scm:load_list",             # bullet (cube utilization on the load detail)
    },
}

_MODULE_RE = re.compile(r"^##\s+(\d+)\.\s+(.+?)\s*$")
_SUB_RE = re.compile(r"^###\s+(\d+\.\d+)\s+(.+?)\s*$")
_FEATURE_RE = re.compile(r"^\s*-\s+\*\*(.+?)\*\*")


@lru_cache(maxsize=1)
def parse_catalog():
    """Parse NavERP.md into [{num, title, submodules:[{num, title, features:[name]}]}].

    Cached for the process lifetime (the catalog is static at runtime). Returns [] if the
    file is missing so the sidebar degrades to just the Dashboard link.
    """
    path = os.path.join(settings.BASE_DIR, "NavERP.md")
    modules, current_mod, current_sub = [], None, None
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                mod = _MODULE_RE.match(line)
                if mod:
                    current_mod = {"num": mod.group(1), "title": mod.group(2).strip(), "submodules": []}
                    modules.append(current_mod)
                    current_sub = None
                    continue
                if current_mod is None:
                    continue
                sub = _SUB_RE.match(line)
                if sub:
                    current_sub = {"num": sub.group(1), "title": sub.group(2).strip(), "features": []}
                    current_mod["submodules"].append(current_sub)
                    continue
                feat = _FEATURE_RE.match(line)
                if feat and current_sub is not None:
                    current_sub["features"].append(feat.group(1).strip())
    except OSError:
        return []
    return modules


def resolve_nav(request):
    """Build the render-ready sidebar tree (Dashboard + Module → Sub-module → Feature)."""
    match = getattr(request, "resolver_match", None)
    current = getattr(match, "view_name", None) if match is not None else None
    current_get = getattr(request, "GET", None)

    sections = [{
        "kind": "link",
        "label": "Dashboard",
        "icon": "layout-dashboard",
        "href": _safe_reverse("dashboard:home"),
        "is_active": _is_active("dashboard:home", current),
    }]

    for mod in parse_catalog():
        mod_node = {
            "kind": "module",
            "label": f'{mod["num"]}. {mod["title"]}',
            "icon": MODULE_ICONS.get(int(mod["num"]), "circle"),
            "submodules": [],
            "open": False,
        }
        for sub in mod["submodules"]:
            live_map = LIVE_LINKS.get(sub["num"], {})
            features, used = [], set()
            for name in sub["features"]:
                url = live_map.get(name)
                features.append(_feature_node(name, url))
                if url:
                    used.add(name)
            # Extra built pages not present as NavERP.md bullets.
            for name, url in live_map.items():
                if name not in used:
                    features.append(_feature_node(name, url))

            # "Most-specific match wins" within the sub-module: the bullet whose ?query best matches
            # the current request is highlighted (only it), so sibling bullets sharing one route but
            # differing by ?query no longer all light up together (e.g. 3.5's status filters, 2.15's
            # ?category= integrations). Ties on the same score (identical hrefs, or #fragment-only
            # differences the server can't see) still co-highlight — that's unavoidable, not a bug.
            _mark_active(features, current, current_get)

            sub_open = any(f["is_active"] for f in features)
            mod_node["submodules"].append({
                "label": f'{sub["num"]} {sub["title"]}',
                "features": features,
                "open": sub_open,
            })
            if sub_open:
                mod_node["open"] = True
        sections.append(mod_node)
    return sections


def _feature_node(name, url):
    href = _safe_reverse(url) if url else None
    # ``url`` (with its ?query/#fragment suffix) is kept for the active-scoring pass; ``is_active``
    # is filled in by ``_mark_active`` once all the sub-module's features are known.
    return {"label": name, "url": url, "href": href, "live": href is not None, "is_active": False}


def _mark_active(features, current, current_get):
    """Flag the active feature(s) in one sub-module by "most-specific match wins": score each
    feature against the current route + query string, then mark the highest scorers active. A
    route-only (or #fragment) bullet scores 0; a ``?query`` bullet whose params all match the
    request scores by the number of params (so it beats the bare route on its filtered page) and a
    bullet whose query conflicts with the request is disqualified."""
    scores = [_match_score(f["url"], current, current_get) for f in features]
    best = max((s for s in scores if s >= 0), default=-1)
    for feat, score in zip(features, scores):
        feat["is_active"] = best >= 0 and score == best


def _route_name(url_name):
    """Strip an optional ``?query`` / ``#fragment`` suffix, returning just the route name."""
    cut = len(url_name)
    for sep in ("?", "#"):
        i = url_name.find(sep)
        if i != -1:
            cut = min(cut, i)
    return url_name[:cut], url_name[cut:]


# A route-match strength larger than any namespaced base-name length, so an EXACT route match always
# outscores a sub-route (prefix) match — and so a longer (more specific) entity prefix outscores a
# shorter one without an action allowlist to maintain.
_EXACT_ROUTE = 1_000_000


def _route_score(url_name, current):
    """Route-match strength of a feature's route against the current view, ignoring ``?query``/
    ``#fragment``:

      * ``-1``            — no match.
      * ``len(base)``     — ``current`` is a CRUD/secondary sub-route of this list (e.g. ``..._detail``,
                            ``..._edit``, ``..._import``). Scored by base length so the **longest**
                            (most specific) prefix wins: on ``payment_term_detail`` the
                            ``payment_term_list`` bullet (longer base) beats the ``payment_list`` one.
      * ``_EXACT_ROUTE``  — an exact route match, which always beats any sub-route. So a page that has
                            its own bullet (``payment_schedule``, ``budget_variance``,
                            ``employee_document_list``) is never co-highlighted by a sibling list whose
                            name it merely shares a prefix with.
    """
    if not url_name or not current:
        return -1
    name, _ = _route_name(url_name)
    if current == name:
        return _EXACT_ROUTE
    base = name[:-5] if name.endswith("_list") else name
    if current.startswith(base + "_"):
        return len(base)
    return -1


def _is_active(url_name, current):
    """True if `current` is this route or a sub-route of it (ignoring any ``?query``/``#fragment``).
    Coarse route-gate used directly for the single Dashboard top-link; sub-module bullets get the
    finer ``_match_score`` / ``_mark_active`` precision (exact beats a prefix, longest prefix wins,
    and ``?query`` siblings are disambiguated against the request's query string)."""
    return _route_score(url_name, current) >= 0


def _match_score(url_name, current, current_get):
    """Score a feature's ``url`` against the current request for the "most-specific match wins" pass.

    ``-1`` when the route doesn't match OR a ``?query`` param the bullet pins conflicts with / is
    absent from ``request.GET`` (disqualified). Otherwise the route-match strength from
    ``_route_score`` (exact ≫ longest sub-route prefix) plus the number of ``?query`` params the
    bullet pins that the request satisfies — so a filter bullet beats the bare route on its own
    filtered page, an exact route beats a sub-route, and a longer entity prefix beats a shorter one.
    Route-only and ``#fragment`` bullets carry no query, so siblings differing only by fragment (the
    2.1 dashboard widgets) or by an identical href tie and co-highlight — unavoidable, not a bug."""
    base_score = _route_score(url_name, current)
    if base_score < 0:
        return -1
    _, suffix = _route_name(url_name)
    if not suffix.startswith("?"):
        return base_score  # route-only or #fragment — the baseline match
    params = parse_qsl(suffix[1:])
    if not params:
        return base_score
    if current_get is None:
        return -1  # the bullet pins a filter but we can't see the request's query → not the active one
    for key, value in params:
        if current_get.get(key) != value:
            return -1  # this filtered bullet doesn't describe the current page
    return base_score + len(params)


def _safe_reverse(url_name):
    """Reverse a ``namespace:name`` route. Supports an optional ``?query`` and/or ``#fragment``
    suffix so a feature can deep-link to a filtered view or a section of an already-built page
    (e.g. the dashboard widgets, or the integrations list scoped to one category)."""
    if not url_name:
        return None
    name, suffix = _route_name(url_name)
    try:
        href = reverse(name)
    except NoReverseMatch:
        return None
    return href + suffix
