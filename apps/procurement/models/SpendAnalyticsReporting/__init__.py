"""6.14 Spend Analytics & Reporting models.

Deliberately NO re-export block here — the 6.13 ``InvoiceVoucherManagement`` precedent.
``apps/procurement/analytics.py`` and this sub-module's view modules import these entity MODULES
directly, and ``apps/procurement/models/__init__.py`` does the same, so a re-export ``__init__``
would give the same three model classes two import paths and a chance to be half-initialised at
URLconf import time. The app-level ``models/__init__.py`` re-exports all four models; that is the
contract.

``SpendDashboards.py`` declares no model at all: **Spend Dashboards**, **Category Spend Analysis**
and **Data Export & Visualization** are computed views over rows other sub-modules own. The file
exists so the four layers stay symmetrical and a reviewer finds a stated reason rather than a gap.
"""
