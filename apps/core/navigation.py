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
