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
    "0.1": {
        "Tenant Onboarding": "tenants:onboarding",
        "Subscription & Billing": "tenants:subscription_list",
        "Subscription Invoices": "tenants:subscriptioninvoice_list",
        "Tenant Isolation & Security": "tenants:encryptionkey_list",
        "Custom Branding": "tenants:brandingsetting_list",
        "Tenant Health Monitoring": "tenants:healthmetric_list",
    },
    "0.2": {
        "Centralized User Directory": "accounts:user_list",
        "Provisioning & De-Provisioning": "accounts:invite_list",
    },
    "0.3": {
        "Roles & Role Hierarchies": "accounts:role_list",
    },
    "0.5": {
        "Organization & Hierarchy Modeling": "core:orgunit_list",
        "User Profiles & Preferences": "accounts:profile",
        "Employee/User Lifecycle Sync": "core:employment_list",
    },
    "0.9": {
        "Immutable Audit Logs": "core:auditlog_list",
        "User Activity Tracking": "core:activity_list",
    },
    "0.14": {
        "Master Data Governance": "core:party_list",
        "Party Roles": "core:partyrole_list",
        "Addresses": "core:address_list",
        "Contact Methods": "core:contactmethod_list",
        "Party Relationships": "core:partyrelationship_list",
        "Documents": "core:document_list",
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


def _is_active(url_name, current):
    """True if `current` is this route or one of its CRUD sub-routes (detail/edit/...)."""
    if not url_name or not current:
        return False
    if current == url_name:
        return True
    base = url_name[:-5] if url_name.endswith("_list") else url_name
    return current.startswith(base + "_")


def _safe_reverse(url_name):
    if not url_name:
        return None
    try:
        return reverse(url_name)
    except NoReverseMatch:
        return None
