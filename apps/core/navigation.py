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
    # 4.7 Demand Planning & Forecasting — DemandForecast (+ its period waterfall) is the spine;
    # SeasonalityProfile doubles as the promotional-event window; DemandSignal is the short-horizon
    # sensing log; and Safety Stock Calculation points at a computed REPORT over the 4.3 ReorderRule
    # that 4.7 extended (the scm:reorder_alerts / scm:valuation_report precedent — a bullet may be a
    # report rather than a CRUD list).
    "4.7": {
        "Sales Forecasting": "scm:demandforecast_list",          # bullet (statistical forecast + period grid)
        "Seasonality Analysis": "scm:seasonalityprofile_list",   # bullet (seasonal curves AND promo events)
        "Demand Sensing": "scm:demandsignal_list",               # bullet (short-horizon signal triage log)
        # Deliberately the FULL list, not `?status=proposed`: the sidebar entry is the sub-module's
        # home, and the queue is one chip on that page. Filtering here would hide the accepted and
        # rejected history behind a link labelled "Collaborative Planning".
        "Collaborative Planning": "scm:forecastadjustment_list", # bullet (consensus + its review queue)
        "Safety Stock Calculation": "scm:safety_stock_report",   # bullet (computed policy over ReorderRule)
    },
    "4.8": {
        "Bill of Materials (BOM)": "scm:billofmaterials_list",      # bullet (versioned recipes + explosion)
        "Production Scheduling": "scm:production_schedule",         # bullet (infinite-capacity load board)
        "Work Order Management": "scm:workorder_list",              # bullet (the run lifecycle)
        "Material Resource Planning (MRP)": "scm:mrp_report",       # bullet (netting → make/buy suggestions)
        # The time-log list, not the work-centre master: the bullet is about TRACKING machine time,
        # labour time and progress, and that is what the log records. Work centres are reachable
        # from it and from the schedule board.
        "Shop Floor Control": "scm:productiontimelog_list",         # bullet (machine/labour/downtime log)
    },
    # 4.9 Quality Management System — InspectionPlan is the criteria master (no sidebar key: it is a
    # master reached from the inspection list, the WorkCenter / ReorderRule precedent) and doubles
    # as the audit checklist. QualityInspection is the execution record whose results are
    # SNAPSHOTTED, so editing a plan can never rewrite a past certificate. NonConformance is the ONE
    # finding register fed by inspections, receipts, production, suppliers and audits alike — audit
    # findings are NCR rows with source="audit", not a second table. Scrap posts an `adjustment`
    # StockMove (no new move type); quarantine flips LotSerial.status and posts NOTHING; SCM posts
    # no JournalEntry (L29). "Certificate of Analysis (CoA)" points at a computed REPORT over the
    # outgoing inspections (the scm:mrp_report / scm:safety_stock_report / scm:valuation_report
    # precedent — a bullet may be a report rather than a CRUD list).
    "4.9": {
        "Quality Inspection": "scm:qualityinspection_list",              # bullet (criteria + execution)
        "Non-Conformance Reports (NCR)": "scm:nonconformance_list",      # bullet (the finding register)
        "Corrective and Preventive Action (CAPA)": "scm:capaaction_list",  # bullet (RCA → tasks → verify)
        "Audit Management": "scm:qualityaudit_list",                     # bullet (schedule → findings → CAPA)
        "Certificate of Analysis (CoA)": "scm:coa_report",               # bullet (computed issue/print page)
    },
    # 4.10 Returns Management (Reverse Logistics) — ReturnReason and ReturnPolicy are masters with no
    # sidebar key (the InspectionPlan / WorkCenter / ReorderRule precedent), reached from the return
    # portal console. ReturnDisposition is the receiving bench and the ONLY thing in 4.10 that touches
    # the ledger: restock posts a POSITIVE `receipt` at a graded, written-down cost; everything else
    # posts nothing off the bench. Refund Processing points at a computed settlement QUEUE that drafts
    # an accounting.Invoice(kind="credit_note", status="draft") and stops — SCM posts no JournalEntry
    # (L29). "Return Portal" points at the STAFF console, not the token page: L32 bars a staff sidebar
    # bullet from pointing at a customer-facing page (this app already applied that at 4.1's
    # "Vendor Portal").
    "4.10": {
        "Return Merchandise Authorization (RMA)": "scm:returnauthorization_list",  # bullet (authorise + approve)
        "Refund Processing": "scm:refund_queue",                                   # bullet (computed settlement queue)
        "Disposition Management": "scm:returndisposition_list",                    # bullet (the receiving bench)
        "Return Portal": "scm:return_portal",                                      # bullet (STAFF console — L32)
        "Warranty Claims": "scm:warrantyclaim_list",                               # bullet (supplier recovery)
    },
    # 4.11 Supply Chain Analytics — all five bullets are COMPUTED pages. That is not a shortcut: the
    # survey of thirteen control-tower/spend-analytics products found the same shape in every one of
    # them, and the only things they store are metric targets, point-in-time snapshots and alert
    # instances carrying human acknowledgement state. So 4.11's three models are cross-cutting
    # machinery rather than one table per bullet, and none of them takes a sidebar key: KpiTarget and
    # KpiSnapshot are masters reached from the analytics pages (the InspectionPlan / WorkCenter /
    # ReorderRule / ReturnReason precedent), and the alert inbox `scm:supplychainalert_list` is
    # reached from the open-count chip in every analytics page header.
    #
    # 4.11 is READ-ONLY over every sub-module that precedes it: it writes no StockMove and no
    # JournalEntry. (Written as "4.1-4.10" when 4.11 shipped; 4.12 and 4.13 have landed since and
    # the statement still holds, so the range is now stated as a rule rather than a list that goes
    # stale on every release.) 4.13's `maintenance` moves are visible to 4.11's inventory
    # recency metrics and deliberately excluded from its COGS ones — see
    # `apps/scm/analytics.py` OUTBOUND_MOVE_TYPES vs COGS_MOVE_TYPES. "Financial
    # Reporting" is an OPERATIONAL margin estimate over SCM rows and says so on the page — the
    # statutory P&L belongs to apps.accounting (L29). "Predictive Analytics" is a deterministic,
    # fully explainable weighted composite rendered with its own component arithmetic; genuine
    # ML/AutoML is Module 10's 10.13, and the page deliberately never says "AI".
    #
    # The dashboard BUILDER stays out: 10.8 owns drag-and-drop canvases and 10.11 owns a
    # formula-authored KPI library, so 4.11 ships a CLOSED metric registry instead.
    "4.11": {
        "Inventory Dashboards":  "scm:inventory_analytics",   # bullet (turnover, dead stock, aging buckets)
        "Procurement Analytics": "scm:spend_analytics",       # bullet (spend cube + savings + supplier trend)
        "Logistics KPIs":        "scm:logistics_kpis",        # bullet (OTD/OTIF, freight/unit, utilization)
        "Financial Reporting":   "scm:margin_analytics",      # bullet (margin + cost-to-serve — NOT the ledger)
        "Predictive Analytics":  "scm:disruption_risk",       # bullet (explainable composite + spike detection)
    },
    # 4.12 Contract & Compliance Management. "Contract Repository" points at 4.2's EXISTING
    # scm:contract_list rather than standing up a second contract table: SupplierContract already
    # carries party, type (incl. nda/sla and now logistics), status, dates, value, currency, terms
    # and the renewal window, and 4.12 adds only the amendment hierarchy + owner it was missing.
    # Same precedent as 4.4 pointing its "Bin/Location Management" bullet at 4.3's scm:location_list.
    #
    # The carbon-footprint report is reached from a chip in the Sustainability list header rather
    # than from a sixth key — 4.12 has five bullets in NavERP.md and the sidebar mirrors it exactly.
    #
    # 4.12 writes no StockMove and no JournalEntry. The tonne-km figure is an OPERATIONAL estimate
    # from published per-mode factors and says so on its own page; statutory emissions disclosure is
    # not SCM's to make. Audit findings and remediation stay with 4.9 (NonConformance/CapaAction) —
    # a failed compliance check links out by reference rather than growing a second finding table.
    "4.12": {
        "Contract Repository":     "scm:contract_list",                  # bullet (4.2's list, extended)
        "Compliance Tracking":     "scm:compliancerequirement_list",     # bullet (the obligation register)
        "Trade Documentation":     "scm:tradedocument_list",             # bullet (BoL / CI / packing list)
        "License Management":      "scm:tradelicense_list",              # bullet (register + balance + expiry)
        "Sustainability Tracking": "scm:sustainabilityassessment_list",  # bullet (ESG + carbon report chip)
    },
    # 4.13 Asset Management — the maintenance side of the plant, and the L36 ownership call is that
    # `scm.Asset` IS the operational asset spine. Module 11 (Asset Management) EXTENDS this table
    # rather than standing up a second one, exactly as 4.12 extended 4.2's SupplierContract instead
    # of growing a parallel contract register. One machine, one row, one code.
    #
    # **`MaintenanceWorkOrder` is NOT 4.8's `WorkOrder`.** They share four letters and nothing else:
    # 4.8's WorkOrder MAKES product — it explodes a BOM, consumes components and produces finished
    # goods through `consumption`/`production` stock moves — while 4.13's MaintenanceWorkOrder
    # REPAIRS a machine, consumes spares through a `maintenance` move and carries the downtime,
    # failure codes and labour that every reliability figure (MTBF/MTTR/availability) is derived
    # from. Two tables, two prefixes (`work-orders/` vs `maintenance-work-orders/`, distinct whole
    # path components), two sidebar bullets in two different sub-modules. Merging them would put a
    # production schedule and a breakdown queue in one list.
    #
    # **"Spare Parts Inventory" is a COMPUTED page over 4.3, not a table.** There is no `SparePart`
    # model: a spare part is an `scm.Item` flagged `is_spare_part`, its on-hand is the live SUM of
    # the append-only `StockMove` ledger (nothing stored to drift from it) and its min/max come from
    # the same `ReorderRule` the buyer already maintains. A second parts catalogue would be a second
    # thing to keep in step with the ledger. Precedent: 4.4 points its "Bin/Location Management"
    # bullet at 4.3's `scm:location_list`, and 4.12 points "Contract Repository" at 4.2's list.
    #
    # **"Asset Depreciation" is a COMPUTED report over `accounting.FixedAsset`.** Acquisition cost,
    # accumulated depreciation, method and useful life belong to apps.accounting, which also posts
    # the depreciation JOURNAL; 4.13 READS those figures, stores none of them, recomputes none of
    # them and posts NO JournalEntry (L29). The page's own contribution is the SCM half — issued
    # parts at the cost they were drawn at, plus labour, plus contractor charges — and the
    # repair-vs-replace ratio between the two. Two writers of one accumulated figure is exactly how
    # the two numbers on the two pages come to disagree.
    #
    # NO sidebar key for `MeterReading`, `AssetSparePart`, `MaintenanceWorkOrderPart` or
    # `MaintenanceWorkOrderTask` — NavERP.md gives 4.13 five bullets and the sidebar mirrors it
    # exactly. The reading log is reached from the asset's meter panel and from
    # `scm:meterreading_list`; the three children are panels on their parent's detail page. That is
    # the WorkCenter / ReorderRule / ReturnReason / InspectionPlan precedent: a master or child
    # reached from the page that uses it takes no bullet of its own. The PM forecast board
    # (`scm:pm_forecast`) is likewise reached from a chip in the Preventive Maintenance list header
    # rather than from a sixth key.
    "4.13": {
        "Asset Registry":         "scm:asset_list",                   # bullet (the plant register + 360° page)
        "Preventive Maintenance": "scm:maintenanceplan_list",         # bullet (PM programme + generate)
        "Breakdown Maintenance":  "scm:maintenanceworkorder_list",    # bullet (the job ladder + downtime)
        "Spare Parts Inventory":  "scm:sparepart_list",               # bullet (COMPUTED over 4.3 — no table)
        "Asset Depreciation":     "scm:asset_depreciation_report",    # bullet (COMPUTED over accounting)
    },
    # 4.14 Labor Management. Five bullets, five staff-facing pages, and three of the five are worth
    # explaining because the obvious reading of each is the wrong one.
    #
    # **"Time & Attendance" does NOT point at an attendance table, because HRM already owns one.**
    # `hrm.AttendanceRecord` is unique per (tenant, employee, date) with punch times, derived hours,
    # geofence and biometric source — it answers "did this person come to work today". A second table
    # answering the same question is how two systems come to disagree about whether somebody was
    # there. `scm:laborsession_list` is the layer BENEATH it: a shift at a warehouse whose minutes are
    # split into booked activity intervals, which is what an LMS measures and what a one-row-per-day
    # attendance record structurally cannot hold. `LaborSession.work_date` is deliberately the same
    # grain as `AttendanceRecord.date` so the two can be reconciled in a report — WITHOUT a FK.
    # `apps/scm` contains zero `hrm.*` references and this sub-module did not add the first.
    #
    # **"Payroll Integration" is a read-only CSV hand-off, not a posting.** `scm:labor_payroll_export`
    # aggregates approved sessions per worker per period and writes NOTHING — not to `hrm.*`, not to
    # `accounting.*`. It is not merely being cautious: `accounting.PayrollRun` is a whole-company
    # period ACCRUAL with no employee lines and no hours columns, so "drafting" one from warehouse
    # labour would be wrong rather than redundant. Contrast 4.6's freight audit, which DOES draft an
    # `accounting.Bill` — because a Bill is a document with lines and a payee, and a PayrollRun isn't.
    #
    # **"Task Assignment" is a COMPUTED console over 4.4's EXISTING tables.** `PickTask`,
    # `PutawayTask` and `CycleCountTask` already carry `assigned_to`, a status and lifecycle stamps,
    # so `scm:labor_board` groups and re-assigns those rows and 4.14 declares NO task table and adds
    # NO second assignee column (migration 0024 has no `AddField` at all, which is the evidence).
    # Same precedent as 4.13's "Spare Parts Inventory" computing over 4.3 and 4.4's "Bin/Location
    # Management" pointing at 4.3's `scm:location_list`.
    #
    # **"Performance Tracking" points at the standards library** rather than at a figures page,
    # because the engineered standard is what makes productivity measurable at all — units per hour
    # with nothing to compare it against is trivia. The scorecard itself (`scm:labor_scorecard`) is
    # reached from a chip in that list's header, the `pm_forecast` precedent.
    #
    # NO sidebar key for `LaborActivity` or `LaborPlanLine` — NavERP.md gives 4.14 five bullets and
    # the sidebar mirrors it exactly. Activities are a panel on their session (and have their own
    # list page reached from there); plan lines are the grid on their plan. That is the established
    # WorkCenter / ReorderRule / ReturnReason / InspectionPlan / KpiTarget rule: a child or master
    # reached from the page that uses it takes no bullet of its own.
    "4.14": {
        "Labor Planning":       "scm:laborplan_list",         # bullet (volume -> required headcount)
        "Time & Attendance":    "scm:laborsession_list",      # bullet (the warehouse SHIFT, not HR)
        "Task Assignment":      "scm:labor_board",            # bullet (COMPUTED over 4.4 - no table)
        "Performance Tracking": "scm:laborstandard_list",     # bullet (the library + scorecard chip)
        "Payroll Integration":  "scm:labor_payroll_export",   # bullet (CSV hand-off - zero writes)
    },
    # --- 4.15 Cold Chain Management ---
    # Five bullets, five pages, and THREE of the five are COMPUTED pages rather than tables — which is
    # the headline fact about this sub-module and the reason the mapping below needs explaining.
    #
    # **"Temperature Monitoring" points at the MONITOR register, not at the reading ledger.** A
    # monitoring point is "one device, watching one thing, from one date, against these limits", and
    # that row is what a user configures, retires and calibrates. `TemperatureReading` is the
    # append-only interval log underneath it (~17.5k rows per monitor per year) and has no edit and no
    # delete by design; it is reached from the monitor it belongs to and from
    # `scm:temperaturereading_list`, exactly as 4.13's `MeterReading` log is. A ledger takes no bullet
    # of its own — the WorkCenter / ReorderRule / ReturnReason / InspectionPlan / KpiTarget rule.
    #
    # **"Cold Storage Inventory" is 4.3 FILTERED, and declares no table.** On-hand is the live SUM of
    # the append-only `StockMove` ledger, the condition mismatch is the two `storage_condition`
    # columns disagreeing, expiry is `LotSerial.expiry_date` and quarantine is `LotSerial.status` —
    # which **4.9's non-conformance verb writes and 4.15 only READS**. Same precedent as 4.13's
    # "Spare Parts Inventory" computing over 4.3 rather than forking a second parts master.
    #
    # **"Compliance Reporting" is a computed page plus three stored columns** (the monitor's
    # calibration triple). The excursion log is 4.15's own rows filtered by window, the temperature
    # profile is derived over `TemperatureReading` through `apps/scm/coldchain.py`, and the audit
    # trail is `core.AuditLog` — there is no second audit table. The page states its own NON-CLAIM:
    # it is not a validated 21 CFR Part 11 / EU Annex 11 system.
    #
    # **"Maintenance of Reefers" is a BOARD over 4.13, and 4.15 declares ZERO maintenance entities.**
    # A reefer is DERIVED as *an `Asset` with an active `ColdChainMonitor`* — no `reefer` asset type
    # and deliberately never one, because a hand-set type goes stale the day a unit is repurposed
    # while "has a live probe pointed at it" cannot. Every maintenance column on it is 4.13's own.
    "4.15": {
        "Temperature Monitoring":  "scm:coldchainmonitor_list",           # bullet (the monitor register)
        "Excursion Management":    "scm:temperatureexcursion_list",       # bullet (the triage queue)
        "Cold Storage Inventory":  "scm:cold_storage_report",             # bullet (COMPUTED over 4.3)
        "Compliance Reporting":    "scm:cold_chain_compliance_report",    # bullet (COMPUTED + CSV)
        "Maintenance of Reefers":  "scm:reefer_board",                    # bullet (COMPUTED over 4.13)
    },
    # 4.16 Customer Portal. Five bullets, five STAFF-reachable pages — and the staff/customer split
    # is the whole design decision here, so it is worth stating rather than inferring.
    #
    # **Every bullet points at a STAFF page (L32).** The sidebar is the staff application; a bullet
    # that opened a login-gated customer page would be a dead end for the person clicking it, since
    # a staff user has no `crm.CustomerPortalAccess` row and `_portal_account()` would refuse them
    # at the first step. The gated customer surface (`scm:portal_home` and its seven siblings) is
    # reached BY CUSTOMERS at `/scm/portal/`, and by staff only through the render-as preview. Same
    # resolution 4.1's "Vendor Portal" and 4.10's "Return Portal" already reached.
    #
    # **"Order Tracking" and "Catalog Browsing" are COMPUTED pages, not tables** — the `labor_board`
    # / `sparepart_list` precedent. 4.16 declares NO order table, NO shipment table and NO catalog
    # table: 4.5 owns the order, 4.6 owns tracking and POD, 4.3 owns the item and the append-only
    # ledger that on-hand is derived from. `portal_order_tracking` exists because it JOINS 4.5 to
    # 4.6 in one row, which neither module's own list page shows; `portal_catalog_preview` renders
    # one customer's projection server-side (# SECURITY: render-as, never authenticate-as).
    #
    # **"Account Management" points at `portalaccount_list`, not at a customer profile page.** The
    # bullet is about MANAGING accounts — enablement, entitlements, who has never logged in — and
    # L32 bars a staff bullet from targeting the login-gated `portal_profile`.
    #
    # **NO sidebar key for `PortalActivity`.** NavERP.md gives 4.16 five bullets and the sidebar
    # mirrors it exactly. The activity log is a panel on the account detail page and has its own
    # list page reached from there. That is the established WorkCenter / ReorderRule / ReturnReason
    # / InspectionPlan / KpiTarget / MeterReading rule: a child or master reached from the page that
    # uses it takes no bullet of its own.
    "4.16": {
        "Order Tracking":     "scm:portal_order_tracking",      # bullet (COMPUTED join of 4.5 + 4.6 - no table)
        "Account Management": "scm:portalaccount_list",         # bullet (the enablement + entitlement console)
        "Document Retrieval": "scm:portaldocumentshare_list",   # bullet (what was shared, and the proof it was fetched)
        "Support Ticketing":  "scm:portalorderinquiry_list",    # bullet (the triage queue over crm.Case)
        "Catalog Browsing":   "scm:portal_catalog_preview",     # bullet (staff as-seen-by-customer-X, render-as)
    },
    # 4.17 Third-Party Logistics (3PL) Management. Five bullets in NavERP.md, five keys here, and
    # every one of them lands on a page that exists.
    #
    # **NO sidebar key for `ClientRateCard`.** The rate card is the pricing a billing run is
    # calculated against, reached from the client detail page, from the billing-run list and from
    # the client list — the same WorkCenter / ReorderRule / ReturnReason / KpiTarget / MeterReading /
    # PortalActivity rule every sub-module before this one follows: a master reached from the page
    # that uses it takes no bullet of its own. Adding a sixth key here would put a link in the
    # sidebar that NavERP.md does not name.
    #
    # "Client Integration" points at the CLIENT LIST rather than at a sync console, because there is
    # no sync console to point at and inventing a dead link is worse than pointing at the real thing
    # (L32). `integration_mode`, `client_system`, `edi_partner_id`, `edi_qualifier` and
    # `last_synced_at` are a field block ON `LogisticsClient` — the client list filters by
    # integration mode and the detail page shows the block, so this bullet is where a user actually
    # configures and inspects the connection today.
    "4.17": {
        "Client Billing":               "scm:clientbillingrun_list",     # bullet (ledger-derived run -> DRAFT accounting.Invoice)
        "Client Inventory Segregation": "scm:client_inventory_report",   # bullet (COMPUTED over Item.owner_client + StockMove - no table)
        "SLA Management":               "scm:clientsla_list",            # bullet (recompute derives the achievement, never typed)
        "Client Integration":           "scm:logisticsclient_list",      # bullet (the EDI/API field block lives on the client master)
        "Warehouse Rental Management":  "scm:client_space_report",       # bullet (COMPUTED - committed space beside reserved bins)
    },
    # 4.18 Finance & Accounting Integration. THREE of these five bullets are READ-ONLY COMPUTED
    # pages, and that is the sub-module's central ruling rather than a shortcut: what we owe and what
    # we are owed already exist as POINTERS into `apps/accounting` from six shipped models, so an AP
    # table, an AR table or a budget table here would be a second copy of the same money that drifts
    # the first time Accounting voids something (L29). Every target below is a real STAFF-facing page
    # that renders today; none is a placeholder (L32).
    "4.18": {
        "Accounts Payable":         "scm:finance_payables",          # bullet (READ-ONLY register over 4.1 GoodsReceiptNote.bill + 4.6 FreightInvoice.bill + 4.18 LandedCostVoucher.bill - no AP table)
        "Accounts Receivable":      "scm:finance_receivables",       # bullet (READ-ONLY register over 4.5 SalesOrder.invoice + 4.17 ClientBillingRun.invoice + 4.10 ReturnAuthorization.credit_note - no AR table)
        "Landed Cost Calculation":  "scm:landedcostvoucher_list",    # bullet (the one genuinely new capability - voucher + charges + derived allocations)
        "Budgeting":                "scm:finance_budget_variance",   # bullet (COMPUTED over accounting.BudgetLine.org_unit vs PR/PO commitments vs freight+landed actuals - no Budget table)
        "Tax Management":           "scm:dutytariff_list",           # bullet (HS x origin duty master; sales/VAT/GST stays accounting.TaxCode, FK'd from the charge line)
    },
    # NO sidebar key for `LandedCostCharge` or `LandedCostAllocation`, and none for the landed-cost
    # variance report: the charges are reached from the voucher detail page and the allocations are a
    # derived ledger shown there too — the `ClientRateCardLine` / `ReorderRule` / `ReturnReason` /
    # `MeterReading` rule. A sidebar entry per child row would list plumbing, not features.
    # 4.19 Integration & API Gateway. The first FOUR bullets are four CATEGORY-SCOPED ROUTES over one
    # `IntegrationEndpoint` table — `integrationendpoint_erp_list` and its three siblings all bind
    # the same view with `category` pinned by the route's extra-options dict. That is deliberate and
    # it is the honest shape: ERP, e-commerce, IoT and EDI are four kinds of the same thing (a
    # registered connection with a transport, an auth method and a health state), so four tables
    # would be one table copied four times with the copies free to drift. Pinning the category in the
    # ROUTE rather than in a query string is what keeps each bullet a real page with its own heading
    # and its own header chips — a `?category=` link is a filter a user loses on the next click.
    # Every target below renders today; none is a placeholder (L32).
    "4.19": {
        "ERP Integration":        "scm:integrationendpoint_erp_list",        # bullet (category-pinned route: SAP / Oracle / NetSuite / Dynamics connections)
        "E-commerce Integration": "scm:integrationendpoint_ecommerce_list",  # bullet (category-pinned route: Shopify / Magento / WooCommerce / Amazon)
        "IoT Gateway":            "scm:integrationendpoint_iot_list",        # bullet (category-pinned route: RFID readers / scanners / sensor gateways)
        "EDI Management":         "scm:integrationendpoint_edi_list",        # bullet (category-pinned route: VAN / AS2 interchange + the X12 exchange log)
        "Webhooks":               "scm:webhooksubscription_list",            # bullet (the standing push rules; their attempt log hangs off each rule's detail page)
    },
    # --- Module 5 Inventory Management System ---------------------------------------------------
    # 5.1 Product & Catalog Management. The SKU master and its hierarchical categorization are
    # 4.3's `scm.Item` / `scm.ItemCategory` (L36: extend the spine, never re-declare it), so those
    # two bullets point AT the owning module's live pages. What 5.1 itself adds is the catalog
    # layer around that spine — typed attributes, sell-side price rows, imagery & documents.
    "5.1": {
        "SKU Management":              "scm:item_list",
        "Product Categorization":      "scm:category_list",
        "Product Attributes":          "inventory:itemattribute_list",
        "Pricing & Costing":           "inventory:itemprice_list",
        "Product Imagery & Documents": "inventory:productfile_list",
    },
    # 5.2 Vendor / Supplier Management. Three of the four bullets are ALREADY the 4.2 SRM pages —
    # the supplier spine (directory/scorecard/contract) is owned by SCM per L36, and re-declaring
    # any of it here would be a second master for the same vendor. The one genuine gap is the
    # conversation itself, so 5.2's only new table is the inventory.VendorCommunication log.
    "5.2": {
        "Supplier Directory":            "scm:supplierprofile_list",          # bullet (4.2 SRM master)
        "Supplier Performance Tracking": "scm:scorecard_list",                # bullet (4.2 signal-derived)
        "Contract & Terms Management":   "scm:contract_list",                 # bullet (terms on the contract; lead time/MOQ on catalog lines)
        "Vendor Communication Log":      "inventory:vendorcommunication_list",  # bullet (the new log)
    },
    # 5.3 Purchase Order (PO) Management. The PO DOCUMENT is 4.1's scm.PurchaseOrder (L36:
    # extend the spine, never re-declare it) - manual drafting and status tracking point AT
    # the spine's own pages. What SCM's built-in lifecycle lacks is the management layer this
    # sub-module adds: reorder-point AUTO-drafting into spine orders, multi-tier approval
    # ROUTING (rules + per-tier decisions; scm's approve is a single signature), and an
    # email/EDI dispatch log (scm's send is a bare status flip with no proof of transmission).
    "5.3": {
        "PO Creation & Drafting":         "scm:purchaseorder_create",   # bullet (the spine's full creation form)
        "Auto-Draft from Reorder Points": "inventory:reorderdraft",     # extra (reorder rules -> draft spine POs)
        "Approval Workflows":             "inventory:approval_queue",   # bullet (multi-tier routing + decision trail)
        "PO Dispatch":                    "inventory:dispatch_list",    # bullet (email/EDI transmission log)
        "PO Tracking":                    "scm:purchaseorder_list",     # bullet (Draft/Sent/Partially Received/Closed live on the spine)
    },
    # 5.4 Receiving & Putaway. Bullets 1-3 are SCM-owned (L29/L36): the GRN document, its
    # three-way match machine and 4.9's receiving inspections already exist - the sidebar
    # points AT them. The genuine gap is bullet 4: "directed" putaway has a strategy label
    # on scm.PutawayTask but no engine, so inventory owns the rule table + a computed
    # suggestions page over open tasks (zero writes into SCM; overrides happen there).
    "5.4": {
        "Goods Receipt Note (GRN)":       "scm:goodsreceipt_list",          # bullet (4.1 document)
        "Three-Way Matching":             "scm:goodsreceipt_list",          # bullet (match_status badges live there)
        "Quality Inspection (Receiving)": "scm:qualityinspection_list",     # bullet (4.9 QMS)
        "Putaway Logic":                  "inventory:putaway_suggestions",  # bullet (computed queue; rules CRUD linked from its header)
    },
    # 5.5 Warehousing & Bin Management. The warehouse/zone/aisle/rack/bin STRUCTURE is
    # 4.3's self-referential scm.Location tree (L36 - extend the spine, never re-declare
    # it), so the structure bullet points AT the spine's own pages. What nothing else
    # records is the per-bin capacity ENVELOPE (weight AND volume AND quantity - the one
    # generic Location.capacity number cannot say "full by weight before full by count"),
    # a layout map computed over that tree plus the ledger, and the bypass-storage
    # cross-dock flow whose two legs post into the same append-only StockMove book.
    "5.5": {
        "Warehouse Structure":      "scm:location_list",           # bullet (4.3's location tree master)
        "Bin Capacity Management":  "inventory:bincapacity_list",  # bullet (per-bin weight/volume/qty envelopes)
        "Warehouse Mapping":        "inventory:warehousemap",      # bullet (computed layout page - declares no table)
        "Cross-Docking":            "inventory:crossdockorder_list",  # bullet (dock-to-dock flow posting StockMoves)
    },
    # 5.6 Inventory Tracking & Control. The QUANTITY spine is 4.3's append-only StockMove
    # ledger and its FIFO/LIFO/WAC cost-layer walk already lives on scm's valuation report
    # (L36 - point at it, never re-declare it). What this sub-module adds is the CONTROL
    # layer around that ledger: real-time availability derived from every claim on stock
    # (4.5 allocations + reservations), a status classification for damaged/expired/held
    # units, and general-purpose soft locks against any reference.
    "5.6": {
        "Real-Time Stock Levels":   "inventory:stocklevels",       # bullet (computed page - on-hand/allocated/available/on-order)
        "Stock Status Management":  "inventory:stockstatus_list",  # bullet (active/damaged/expired/on-hold classifications)
        "Inventory Valuation":      "scm:valuation_report",        # bullet (4.3's FIFO/LIFO/WAC cost-layer walk owns this)
        "Inventory Reservations":   "inventory:reservation_list",  # bullet (RSV- soft claims vs SO/job/project)
    },
    # 5.7 Stock Movement & Transfers. The movement DOCUMENT is 4.3's scm.StockTransfer
    # (L36 - extend the spine, never re-declare it): drafting and execution stay on its
    # SCM pages, whose complete action still posts the paired StockMove legs (the spine
    # grew a pending_approval/approved pair of governed states plus a nullable route FK
    # for exactly this). What this sub-module adds is the governance around that
    # document: the board classifies every movement live into inter- vs intra-warehouse,
    # tiered approval rules gate who may move stock, and the routing catalog says how.
    "5.7": {
        "Inter-Warehouse Transfers":   "inventory:transfer_board?scope=inter",   # bullet (board lens over the spine register)
        "Intra-Warehouse Transfers":   "inventory:transfer_board?scope=intra",   # bullet (same ledger, within one warehouse root)
        "Transfer Approval Workflow":  "inventory:transfer_queue",               # bullet (tiered sign-off; TA- decision rows)
        "Transfer Routing":            "inventory:transferroute_list",           # bullet (routing catalog + transit windows)
    },
    # 5.8 Lot & Serial Number Tracking. The lot/serial ROWS are 4.3's scm.LotSerial
    # (L36 - point at it, never re-declare it), so Serial Number Tracking maps straight
    # at that master. What nothing else provides is the management layer around it:
    # pattern-based batch NUMBER generation (the spine's create form is free-typed), an
    # expiry/FEFO board that turns per-SKU shelf-life policy into a do-not-ship line
    # over the ledger, and recall tracing that walks the append-only book backward and
    # forward through transformation references.
    "5.8": {
        "Lot/Batch Generation":           "inventory:lotrule_list",   # bullet (rules CRUD + one-click mint into scm.LotSerial)
        "Serial Number Tracking":         "scm:lotserial_list",       # bullet (4.3's lot/serial master owns the rows)
        "Shelf-Life & Expiry Management": "inventory:fefo_board",     # bullet (FEFO pick order + policies linked from its header)
        "Traceability & Genealogy":       "inventory:traceability",   # bullet (computed recall trace over StockMove)
    },
    # 5.11 Stocktaking & Cycle Counting. The count EXECUTION spine is 4.4's
    # scm.CycleCountTask (+lines): blind server-side expected snapshots and
    # reconciliation into exactly one StockAdjustment (L36 - point at it, never
    # re-declare it), so the Blind Counts bullet maps straight at that master.
    # What nothing else provides is the recurring CALENDAR (programs minting spine
    # sheets on a daily/weekly/monthly cadence over zones or ABC classes), the
    # warehouse-wide FREEZE event that spawns one sheet per bin and holds until
    # every sheet closes, and the analysis lens over counted-vs-expected variance.
    "5.11": {
        "Full Physical Inventory":         "inventory:physicalinventory_list",  # bullet (PHY- freeze event orchestrating spine sheets)
        "Cycle Count Scheduling":          "inventory:countprogram_list",       # bullet (CTP- recurring cadence minting spine sheets)
        "Blind Counts":                    "scm:cyclecounttask_list",           # bullet (4.4 execution master owns blind counting)
        "Variance Analysis & Adjustments": "inventory:variance_report",         # bullet (computed page - no table of its own)
    },
    # 5.13 Inventory Forecasting & Planning. The FORECAST and the MATH are SCM 4.7's:
    # DemandForecast predicts, SeasonalityProfile carries the index curve, ReorderRule
    # computes safety stock / reorder point and is the only writer that may promote
    # them (L36 - point at it, never re-declare it), so Demand Forecasting maps straight
    # at the spine's list. What inventory adds is the DECISION layer: a seasonality-aware
    # stock target plan per SKU, and the review board over each rule's live-vs-computed
    # parameter gap with a tenant-admin apply into the spine's own writer.
    "5.13": {
        "Demand Forecasting":              "scm:demandforecast_list",        # bullet (4.7 forecast master owns prediction)
        "Reorder Point (ROP) Calculation": "inventory:planning_board",       # bullet (computed page over rules' live-vs-computed gap)
        "Safety Stock Calculation":        "inventory:planning_board",       # bullet (same board - computed SS column + gated apply)
        "Seasonality Planning":            "inventory:stocklevelplan_list",  # bullet (SLP- seasonal targets applying SCM index curves)
    },
    # 5.9 Order Management & Fulfillment. The order DOCUMENT and its fulfilment lifecycle are
    # 4.5's scm.SalesOrder (credit checks, soft allocations, backorders) with 4.4 PickTask doing
    # the picking and 4.6 TMS owning carriers/shipments (L36 - point at them, never re-declare).
    # What nothing else records is Wave Planning: grouping orders into picker-efficient waves -
    # inventory adds FulfillmentWave [WAV-] + membership rows pointing AT spine orders, a
    # computed board, and zero SCM writes (release/close/cancel are wave-side bookkeeping only).
    "5.9": {
        "Sales Order Processing":   "scm:salesorder_list",   # bullet (4.5's order spine + full lifecycle)
        "Pick, Pack, Ship Workflow": "scm:picktask_list",    # bullet (4.4 guided picks + packing data; 4.6 dispatch)
        "Wave Planning":            "inventory:wave_board",  # bullet (computed wave board; wave CRUD linked from it)
        "Shipping Integration":     "scm:carrier_list",      # bullet (4.6 carrier master + rate cards; label APIs deferred)
    },
    # 5.10 Returns Management (RMA). The primary RMA document and financial/ledger postings
    # belong to SCM 4.10 (ReturnAuthorization, ReturnDisposition, refund settlement queue) per L36:
    # point RMA and Credit/Refund bullets at the spine. What 5.10 adds is the warehouse floor
    # receiving inspection layer (checklists, condition grading, restock eligibility) and the
    # automated disposition routing engine directing returned items to warehouse locations.
    "5.10": {
        "Return Merchandise Authorization": "scm:returnauthorization_list",        # bullet (4.10 spine master)
        "Return Inspection":                "inventory:returninspection_list",     # bullet (warehouse inspection records & checklists)
        "Disposition Routing":             "inventory:dispositionrule_list",       # bullet (routing rules + suggested destination bins)
        "Credit/Refund Processing":         "scm:refund_queue",                    # bullet (4.10 settlement queue into accounting)
    },
    # --- Module 6 Procurement Management System -------------------------------------------------

    # 6.1 User Dashboard & Portal. The requisition/PO documents the portal reads and writes are
    # 4.1's `scm.PurchaseRequisition` / `scm.PurchaseOrder` (L36: extend the spine, never
    # re-declare it) — the Quick Requisition Entry bullet lands on the fast-track form that drafts
    # INTO that spine, and the activity feed is `core.AuditLog` filtered to procurement content
    # types, so no bullet needs a second copy of either table.
    "6.1": {
        "Personalized Overview":   "procurement:dashboard",       # bullet (the landing page itself)
        "Task & Alert Center":     "procurement:alert_list",      # bullet (the alert inbox + its acknowledge/resolve actions)
        "Quick Requisition Entry": "procurement:quickreq_create", # bullet (one-screen fast track drafting into scm.PurchaseRequisition)
        "Recent Activity Feed":    "procurement:activity_list",   # bullet (core.AuditLog scoped to procurement documents)
        "Self-Service Reporting":  "procurement:report_index",    # bullet (personal usage/spend report + own-requisitions CSV)
    },
    # 6.2 Requisition Management. The requisition DOCUMENTS stay 4.1's scm.PurchaseRequisition
    # (L36), so the Creation bullet maps to the spine's own full form (item descriptions,
    # quantities, required dates and account codes — exactly what the bullet names) rather than a
    # second copy of it; the other four bullets land on 6.2's management layer around that spine.
    "6.2": {
        "Requisition Creation":            "scm:requisition_create",           # bullet (4.1's full creation form on the spine)
        "Requisition Tracking":            "procurement:req_list",             # bullet (register + draft→approval→PO tracking detail)
        "Duplicate Requisition Check":     "procurement:req_list?dupes=1",     # bullet (register filtered to flagged rows; reasons on each detail)
        "Requisition Templates":           "procurement:template_list",        # bullet (recurring-order blueprints + apply-into-draft)
        "Requisition Cancellation/Amendment": "procurement:amendment_list",    # bullet (request → admin approve/reject workflow)
    },
    # NO sidebar key for `IntegrationMessage`, `WebhookDelivery` or the exceptions cockpit, and each
    # omission has its own reason rather than one blanket one. The two LOGS are reached from the page
    # that uses them — the endpoint detail page's recent-messages panel and the subscription detail
    # page's recent-attempts panel, which deep-links `webhookdelivery_list?subscription=<pk>` — the
    # `ClientRateCardLine` / `ReorderRule` / `ReturnReason` / `MeterReading` / `PortalActivity` rule.
    # `integration_exceptions` is a REPORT over those messages rather than a NavERP.md feature
    # bullet, and this dict maps bullets to pages; it is linked from the endpoint list and from every
    # failed message. A sidebar entry per log and per report would list plumbing, not features.
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
