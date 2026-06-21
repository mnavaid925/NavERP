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
    # 1.2 Sales Force Automation (SFA)
    "1.2": {
        "Opportunity Management (Deals)": "crm:opportunity_list",  # bullet
        "Forecasting": "crm:overview",                  # bullet (weighted pipeline on the overview)
    },
    # 1.3 Marketing Automation
    "1.3": {
        "Campaign Management": "crm:campaign_list",      # bullet
    },
    # 1.4 Customer Service & Support (Help Desk)
    "1.4": {
        "Case / Ticket Management": "crm:case_list",         # bullet
        "Solutions & Knowledge Base": "crm:knowledgearticle_list",  # bullet
    },
    # 1.5 Activity & Communication Management
    "1.5": {
        "Task Management": "crm:task_list",              # bullet
    },
    # 1.6 Analytics & Reporting
    "1.6": {
        "Dashboards": "crm:overview",                    # bullet
        "Standard Reports": "crm:overview",              # bullet
    },
    # 1.7 Finance & Billing Management — only Expense Tracking is built; Invoicing &
    # Payment Tracking need the Accounting ledger (Module 2, not built) → stay roadmap.
    "1.7": {
        "Expense Tracking": "crm:expense_list",          # bullet
    },
    # 1.8 Project & Delivery Management (Post-Sale)
    "1.8": {
        "Projects": "crm:crmproject_list",               # bullet
        "Time Tracking": "crm:timesheet_list",           # bullet
        "Resource Allocation": "crm:timesheet_list",     # bullet (workload via employee filter)
        "Milestones": "crm:crmmilestone_list",           # extra (project Gantt/Kanban board)
    },
    # 1.9 Document & Contract Management
    "1.9": {
        "E-Signatures": "crm:contractdocument_list",     # bullet (contract + signer tracking)
        "Document Generation": "crm:doctemplate_list",   # bullet (merge-variable templates)
        "File Repository": "crm:contractdocument_list",  # bullet (versioned contract documents)
    },
    # 1.10 Automation & Workflow Engine
    "1.10": {
        "Trigger-Based Actions (If This, Then That)": "crm:workflowrule_list",  # bullet
        "Approval Processes": "crm:approvalrequest_list",  # bullet
        "Webhooks": "crm:workflowrule_list",             # bullet (webhook is a rule action type)
        "Workflow Logs": "crm:workflowlog_list",         # extra (rule-execution audit)
    },
    # 1.11 Customer Success & Retention
    "1.11": {
        "Onboarding Pipelines": "crm:onboardingplan_list",  # bullet
        "Health Scoring": "crm:healthscore_list",           # bullet
        "Surveys & Feedback (NPS)": "crm:survey_list",      # bullet
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
        "HRM Overview": "hrm:hrm_overview",               # extra (module landing/dashboard)
    },
    # 3.2 Organizational Structure — Designations are HRM-owned; departments reuse core.OrgUnit.
    "3.2": {
        "Designation/Job Titles": "hrm:designation_list",  # bullet
        "Department Management": "core:orgunit_list",      # bullet (OrgUnit reuse)
    },
    # 3.9 Attendance Management
    "3.9": {
        "Check-in/Check-out": "hrm:attendancerecord_list",  # bullet
        "Attendance Calendar": "hrm:attendancerecord_list",  # bullet (date-filtered list)
        "Shift Management": "hrm:shift_list",                # bullet
        "Shift Assignments": "hrm:shiftassignment_list",     # extra (employee↔shift mapping)
    },
    # 3.10 Leave Management
    "3.10": {
        "Leave Types": "hrm:leavetype_list",             # bullet
        "Leave Balance": "hrm:leaveallocation_list",     # bullet (per-employee allocation + balance)
        "Leave Application": "hrm:leaverequest_list",    # bullet
        "Leave Calendar": "hrm:leaverequest_list",       # bullet (request list as calendar source)
    },
    # 3.12 Holiday Management
    "3.12": {
        "Holiday Calendar": "hrm:publicholiday_list",    # bullet
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
                features.append(_feature_node(name, url, current))
                if url:
                    used.add(name)
            # Extra built pages not present as NavERP.md bullets.
            for name, url in live_map.items():
                if name not in used:
                    features.append(_feature_node(name, url, current))

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


def _feature_node(name, url, current):
    href = _safe_reverse(url) if url else None
    return {"label": name, "href": href, "live": href is not None,
            "is_active": _is_active(url, current)}


def _route_name(url_name):
    """Strip an optional ``?query`` / ``#fragment`` suffix, returning just the route name."""
    cut = len(url_name)
    for sep in ("?", "#"):
        i = url_name.find(sep)
        if i != -1:
            cut = min(cut, i)
    return url_name[:cut], url_name[cut:]


def _is_active(url_name, current):
    """True if `current` is this route or one of its CRUD sub-routes (detail/edit/...).

    A ``name?query`` / ``name#fragment`` value matches on the route name alone. Note: bullets that
    share one route but differ only by ``?query``/``#fragment`` (the 2.1 dashboard widgets, the 2.15
    integration categories) therefore ALL highlight together on that page — the resolver match
    carries no query string, and URL fragments are never sent to the server, so a single-bullet
    highlight isn't derivable here (review F4, accepted limitation)."""
    if not url_name or not current:
        return False
    name, _ = _route_name(url_name)
    if current == name:
        return True
    base = name[:-5] if name.endswith("_list") else name
    return current.startswith(base + "_")


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
