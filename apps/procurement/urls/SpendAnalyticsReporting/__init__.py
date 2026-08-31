"""6.14 Spend Analytics & Reporting URL patterns — one module per views module.

``app_name`` is set once in ``apps/procurement/urls/__init__.py``; this package only concatenates
its five entity/page modules' ``urlpatterns``.

Django resolves FIRST-MATCH-WINS, so ordering is behaviour. Within each module the literal routes
precede the ``<int:pk>`` ones; here the whole-segment groups are simply listed in reading order.
Five first segments are claimed by this sub-module, every one of them a new whole component
checked against the inventory in ``apps/procurement/urls/__init__.py``: ``spend/`` (with the
literal children ``categories/``, ``classification/``, ``maverick/``, ``maverick/scan/``,
``export/`` and ``export/download/``), ``spend-rules/``, ``maverick-findings/``,
``spend-reports/`` and ``spend-report-snapshots/``. ``spend-rules/`` and ``spend-reports/`` are
NOT prefixes of ``spend/`` — Django matches path components, not string prefixes.

This app registers no greedy ``<str:…>`` converter anywhere, so there is no cross-module shadowing
surface to reason about.
"""
from .ClassificationWorkbench import urlpatterns as _sar_workbench
from .MaverickDashboard import urlpatterns as _sar_maverickboard
from .MaverickFindings import urlpatterns as _sar_maverickfindings
from .SpendClassificationRules import urlpatterns as _sar_rules
from .SpendDashboards import urlpatterns as _sar_dashboards
from .SpendReports import urlpatterns as _sar_reports


urlpatterns = [
    *_sar_dashboards,        # spend/ , spend/categories/ , spend/export/ (+ download)
    *_sar_workbench,         # spend/classification/
    *_sar_maverickboard,     # spend/maverick/ (+ scan, POST-only, tenant admin)
    *_sar_rules,             # spend-rules/ CRUD + preview
    *_sar_maverickfindings,  # maverick-findings/ CRUD + disposition
    *_sar_reports,           # spend-reports/ CRUD + verbs, spend-report-snapshots/
]
