"""NavERP sidebar navigation — the single source of truth for the module menu.

`MODULE_CATALOG` mirrors NavERP.md: Dashboard + Modules 0-13, each with its
sub-modules. A child with a ``url`` (a ``namespace:name`` route) is *live*; a child
without one is a *roadmap* placeholder ("On the roadmap"). As later modules are built,
the `/next-module` flow simply fills in the ``url`` on the relevant children.

`resolve_nav(request)` turns the catalog into render-ready data: it safely reverses
each ``url`` (a missing route degrades to a roadmap item instead of 500-ing the whole
page), flags the active item, and marks its parent group open. Exposed to every
template via ``apps.core.context_processors.navigation``.
"""
from django.urls import NoReverseMatch, reverse

# Module 0 is realized by the foundation apps (core/accounts/tenants/dashboard); its
# children are the concrete pages we built, followed by the not-yet-built 0.x areas.
_MODULE_0_CHILDREN = [
    {"label": "Tenant Onboarding", "url": "tenants:onboarding"},
    {"label": "Subscriptions", "url": "tenants:subscription_list"},
    {"label": "Subscription Invoices", "url": "tenants:subscriptioninvoice_list"},
    {"label": "Custom Branding", "url": "tenants:brandingsetting_list"},
    {"label": "Encryption Keys", "url": "tenants:encryptionkey_list"},
    {"label": "Tenant Health", "url": "tenants:healthmetric_list"},
    {"label": "Users", "url": "accounts:user_list"},
    {"label": "Roles & Permissions", "url": "accounts:role_list"},
    {"label": "User Invites", "url": "accounts:invite_list"},
    {"label": "Organization Units", "url": "core:orgunit_list"},
    {"label": "Parties", "url": "core:party_list"},
    {"label": "Party Roles", "url": "core:partyrole_list"},
    {"label": "Addresses", "url": "core:address_list"},
    {"label": "Contact Methods", "url": "core:contactmethod_list"},
    {"label": "Relationships", "url": "core:partyrelationship_list"},
    {"label": "Employments", "url": "core:employment_list"},
    {"label": "Activities", "url": "core:activity_list"},
    {"label": "Documents", "url": "core:document_list"},
    {"label": "Audit Trail", "url": "core:auditlog_list"},
    # Remaining Module-0 sub-modules (roadmap):
    {"label": "Authentication & SSO"},
    {"label": "Data Security & Encryption"},
    {"label": "Privacy & Data Protection"},
    {"label": "System Configuration"},
    {"label": "Workflow & Approvals"},
    {"label": "Notifications"},
    {"label": "Integration & API"},
    {"label": "Localization & Regional"},
    {"label": "Backup & Recovery"},
    {"label": "Monitoring & Observability"},
    {"label": "Threat Protection"},
    {"label": "Compliance & Governance"},
]


def _roadmap(*labels):
    return [{"label": label} for label in labels]


MODULE_CATALOG = [
    {"key": "dashboard", "label": "Dashboard", "icon": "layout-dashboard", "url": "dashboard:home"},
    {
        "key": "m0", "num": "0", "label": "System Admin & Security", "icon": "shield-check",
        "children": _MODULE_0_CHILDREN,
    },
    {
        "key": "m1", "num": "1", "label": "Customer Relationship Mgmt", "icon": "contact",
        "children": _roadmap(
            "Core Data Management", "Sales Force Automation", "Marketing Automation",
            "Customer Service & Support", "Activity & Communication", "Analytics & Reporting",
            "Finance & Billing", "Project & Delivery", "Document & Contract",
            "Automation & Workflow", "Customer Success & Retention", "Inventory & Vendor",
        ),
    },
    {
        "key": "m2", "num": "2", "label": "Accounting & Finance", "icon": "landmark",
        "children": _roadmap(
            "Dashboard & Analytics", "General Ledger", "Accounts Payable", "Accounts Receivable",
            "Cash Management", "Fixed Assets", "Inventory & Cost", "Payroll Integration",
            "Project / Job Costing", "Multi-Entity & Consolidation", "Tax", "Reporting & Compliance",
            "Budgeting & Planning", "Audit & Controls", "Integration & API",
        ),
    },
    {
        "key": "m3", "num": "3", "label": "Human Resource Mgmt", "icon": "users-round",
        "children": _roadmap(
            "Employee Management", "Organizational Structure", "Onboarding", "Offboarding",
            "Recruitment & Hiring", "Attendance Management", "Leave Management", "Time Tracking",
            "Payroll Processing", "Statutory Compliance", "Performance Review",
            "Training & LMS", "Self-Service", "HR Reports & Analytics", "Compensation & Benefits",
        ),
    },
    {
        "key": "m4", "num": "4", "label": "Supply Chain Mgmt", "icon": "truck",
        "children": _roadmap(
            "Procurement", "Supplier Relationship", "Inventory", "Warehouse (WMS)",
            "Order Management (OMS)", "Transportation (TMS)", "Demand Planning",
            "Manufacturing", "Quality (QMS)", "Returns / Reverse Logistics", "Analytics",
        ),
    },
    {
        "key": "m5", "num": "5", "label": "Inventory Management", "icon": "package",
        "children": _roadmap(
            "Product & Catalog", "Vendor / Supplier", "Purchase Orders", "Receiving & Putaway",
            "Warehousing & Bins", "Inventory Tracking", "Stock Movement & Transfers",
            "Lot & Serial Tracking", "Order Fulfillment", "Returns (RMA)", "Stocktaking & Cycle Counts",
            "Multi-Location", "Forecasting", "Barcode & RFID", "Quality Control", "Reporting & Analytics",
        ),
    },
    {
        "key": "m6", "num": "6", "label": "Procurement", "icon": "shopping-cart",
        "children": _roadmap(
            "Dashboard & Portal", "Requisitions", "Approval Workflows", "Vendor Management",
            "Sourcing & Tendering", "RFx Management", "E-Auctions", "Contract Management",
            "Catalog Management", "Purchase Orders", "Goods Receipt & Inspection",
            "Invoice & Voucher", "Spend Analytics", "Budget & Cost", "Supplier Performance",
        ),
    },
    {
        "key": "m7", "num": "7", "label": "Project Management", "icon": "folder-kanban",
        "children": _roadmap(
            "Initiation & Charter", "Planning & Scheduling", "Resource Management",
            "Cost & Budget", "Risk & Issues", "Quality", "Scope & Requirements",
            "Task & Work", "Collaboration", "Documents", "Time Tracking",
            "Portfolio & Program", "Agile & Scrum", "Financial & Billing", "Reporting & BI",
        ),
    },
    {
        "key": "m8", "num": "8", "label": "Sales Management", "icon": "trending-up",
        "children": _roadmap(
            "Lead Management", "Opportunity & Pipeline", "Contact & Account", "Forecasting",
            "Quote & Proposal", "Order Management", "Territory & Quota", "Activity & Tasks",
            "Sales Enablement", "Incentive Compensation", "Customer Success", "Analytics",
            "Marketing Alignment", "Partner & Channel", "Contract & Subscription",
        ),
    },
    {
        "key": "m9", "num": "9", "label": "eCommerce", "icon": "store",
        "children": _roadmap(
            "Product Catalog", "Inventory & Stock", "Pricing & Promotions", "Cart & Checkout",
            "Order Management", "Customer Accounts", "Search & Discovery", "Personalization",
            "Content (CMS)", "Marketing & Campaigns", "Marketplace / Multi-Vendor",
            "Subscriptions", "Reviews & UGC", "Customer Service", "Analytics", "Mobile Commerce",
        ),
    },
    {
        "key": "m10", "num": "10", "label": "Business Intelligence", "icon": "bar-chart-3",
        "children": _roadmap(
            "Data Integration", "ETL / Pipelines", "Data Warehouse", "Data Modeling",
            "Data Quality", "Master Data (MDM)", "Catalog & Lineage", "Dashboards & Visualization",
            "Operational Reporting", "Self-Service Analytics", "KPI Scorecards", "OLAP",
            "Predictive Analytics", "AI & Augmented", "Conversational BI", "Alerts & Distribution",
        ),
    },
    {
        "key": "m11", "num": "11", "label": "Asset Management", "icon": "boxes",
        "children": _roadmap(
            "Procurement & Acquisition", "Inventory & Tracking", "Classification",
            "Depreciation & Financials", "Maintenance & Repair", "Performance & Utilization",
            "Condition Monitoring", "Warranty & Insurance", "Disposal & Retirement",
            "Lease & Rental", "Compliance", "Risk Management", "Mobile", "Analytics", "IT Assets (ITAM)",
        ),
    },
    {
        "key": "m12", "num": "12", "label": "Quality Management", "icon": "badge-check",
        "children": _roadmap(
            "Document Control", "Design Controls", "Risk Management (FMEA)", "CAPA",
            "Non-Conformance", "Supplier Quality", "Incoming QC", "In-Process QC",
            "Final / Outgoing QC", "Calibration", "Audit Management", "Training & Competency",
            "Complaint Handling", "Management Review", "Process Validation", "Traceability",
        ),
    },
    {
        "key": "m13", "num": "13", "label": "Document Management", "icon": "files",
        "children": _roadmap(
            "Creation & Authoring", "Version Control", "Approval Workflow", "Storage & Repository",
            "Metadata & Indexing", "Search & Discovery", "Security & Access", "Collaboration",
            "Records & Compliance", "Audit Trail", "Workflow Automation", "Mobile Access",
            "Archival & Preservation", "Electronic Forms", "Contract Lifecycle (CLM)",
        ),
    },
]


def resolve_nav(request):
    """Return render-ready sidebar sections with hrefs resolved and active flags set."""
    match = getattr(request, "resolver_match", None)
    current = None
    if match is not None:
        try:
            current = match.view_name  # e.g. "core:party_list"
        except Exception:  # pragma: no cover
            current = None

    sections = []
    for item in MODULE_CATALOG:
        node = {
            "key": item["key"],
            "label": item["label"],
            "icon": item.get("icon", "circle"),
            "num": item.get("num"),
            "href": _safe_reverse(item.get("url")),
            "url_name": item.get("url"),
            "is_active": bool(item.get("url") and item.get("url") == current),
            "children": [],
            "open": False,
        }
        for child in item.get("children", []):
            href = _safe_reverse(child.get("url"))
            is_active = bool(child.get("url") and child.get("url") == current)
            node["children"].append({
                "label": child["label"],
                "href": href,
                "live": href is not None,
                "is_active": is_active,
            })
            if is_active:
                node["open"] = True
        sections.append(node)
    return sections


def _safe_reverse(url_name):
    if not url_name:
        return None
    try:
        return reverse(url_name)
    except NoReverseMatch:
        return None
