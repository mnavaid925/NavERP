"""Global search — a small, defensive registry over the key records of every module.

`run_search` is shared by the live-suggestions endpoint (header dropdown) and the full results page.
Every query is tenant-scoped. Each target is isolated in try/except so a missing model/route/field can
never 500 search — that target is simply skipped.
"""
from django.apps import apps
from django.db.models import Q
from django.urls import reverse

# Each target: model "app.Model"; fields searched with OR icontains; optional filters; title/subtitle
# are dotted attribute paths resolved per row; url is the detail route (reversed with the row pk).
SEARCH_TARGETS = [
    {"model": "core.Party", "group": "Accounts", "icon": "building-2",
     "fields": ["name"], "filters": {"kind": "organization"},
     "title": "name", "subtitle": None, "url": "crm:account_detail"},
    {"model": "core.Party", "group": "Contacts", "icon": "user",
     "fields": ["name"], "filters": {"kind": "person"},
     "title": "name", "subtitle": None, "url": "crm:contact_detail"},
    {"model": "crm.Lead", "group": "Leads", "icon": "user-plus",
     "fields": ["number", "name", "company", "email"],
     "title": "name", "subtitle": "company", "url": "crm:lead_detail"},
    {"model": "crm.Opportunity", "group": "Opportunities", "icon": "target",
     "fields": ["number", "name"], "title": "name", "subtitle": "number", "url": "crm:opportunity_detail"},
    {"model": "crm.Case", "group": "Cases", "icon": "life-buoy",
     "fields": ["number", "subject"], "title": "subject", "subtitle": "number", "url": "crm:case_detail"},
    {"model": "crm.Quote", "group": "Quotes", "icon": "file-text",
     "fields": ["number", "name"], "title": "name", "subtitle": "number", "url": "crm:quote_detail"},
    {"model": "crm.CrmTask", "group": "Tasks", "icon": "check-square",
     "fields": ["number", "subject"], "title": "subject", "subtitle": "number", "url": "crm:task_detail"},
    {"model": "crm.Product", "group": "Products", "icon": "package",
     "fields": ["number", "name", "sku"], "title": "name", "subtitle": "sku", "url": "crm:product_detail"},
    {"model": "crm.Campaign", "group": "Campaigns", "icon": "megaphone",
     "fields": ["number", "name"], "title": "name", "subtitle": "number", "url": "crm:campaign_detail"},
    {"model": "crm.ContractDocument", "group": "Contracts", "icon": "file-signature",
     "fields": ["number", "name"], "title": "name", "subtitle": "number", "url": "crm:contractdocument_detail"},
    {"model": "accounting.Invoice", "group": "Invoices", "icon": "file-text",
     "fields": ["number", "party__name"], "select_related": ["party"],
     "title": "number", "subtitle": "party.name", "url": "accounting:invoice_detail"},
    {"model": "accounting.Bill", "group": "Bills", "icon": "receipt",
     "fields": ["number", "party__name"], "select_related": ["party"],
     "title": "number", "subtitle": "party.name", "url": "accounting:bill_detail"},
    {"model": "accounting.Payment", "group": "Payments", "icon": "banknote",
     "fields": ["number", "party__name"], "select_related": ["party"],
     "title": "number", "subtitle": "party.name", "url": "accounting:payment_detail"},
    {"model": "accounting.GLAccount", "group": "GL Accounts", "icon": "book-open",
     "fields": ["code", "name"], "title": "name", "subtitle": "code", "url": "accounting:glaccount_detail"},
    {"model": "hrm.EmployeeProfile", "group": "Employees", "icon": "id-card",
     "fields": ["number", "party__name", "work_email"], "select_related": ["party"],
     "title": "party.name", "subtitle": "number", "url": "hrm:employee_detail"},
    {"model": "hrm.LeaveRequest", "group": "Leave Requests", "icon": "plane",
     "fields": ["number", "employee__party__name"], "select_related": ["employee__party"],
     "title": "number", "subtitle": "employee.party.name", "url": "hrm:leaverequest_detail"},
]

MIN_QUERY_LEN = 2


def _resolve(obj, path):
    """Resolve a dotted attribute path to a string ("" if any link is missing)."""
    if not path:
        return ""
    cur = obj
    for part in path.split("."):
        cur = getattr(cur, part, None)
        if cur is None:
            return ""
    return str(cur)


def _term_q(fields, term):
    q = Q()
    for f in fields:
        q |= Q(**{f + "__icontains": term})
    return q


def run_search(tenant, q, per_target=5, total_cap=8):
    """Return grouped matches: [{group, icon, items: [{title, subtitle, url}]}], tenant-scoped."""
    groups = []
    q = (q or "").strip()
    if tenant is None or len(q) < MIN_QUERY_LEN:
        return groups
    for target in SEARCH_TARGETS:
        if len(groups) >= total_cap:
            break
        try:
            model = apps.get_model(target["model"])
            qs = model.objects.filter(tenant=tenant)
            if target.get("filters"):
                qs = qs.filter(**target["filters"])
            qs = qs.filter(_term_q(target["fields"], q))
            if target.get("select_related"):
                qs = qs.select_related(*target["select_related"])
            qs = qs.order_by("-id")[:per_target]
            items = []
            for obj in qs:
                try:
                    url = reverse(target["url"], args=[obj.pk])
                except Exception:  # noqa: BLE001 — a route gap shouldn't drop the whole group
                    continue
                items.append({
                    "title": _resolve(obj, target["title"]) or _resolve(obj, "number") or str(obj),
                    "subtitle": _resolve(obj, target.get("subtitle")),
                    "url": url,
                })
            if items:
                groups.append({"group": target["group"], "icon": target["icon"], "items": items})
        except Exception:  # noqa: BLE001 — one bad target never breaks global search
            continue
    return groups
