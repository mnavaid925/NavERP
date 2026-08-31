"""6.14 Spend Analytics & Reporting views.

No re-export block — the app-level ``apps/procurement/views/__init__.py`` imports these entity
modules directly and re-exports every view name from there, which is what makes ``views.<name>``
resolve for the URLconf package.

Six modules: three entity lanes (``SpendClassificationRules``, ``MaverickFindings``,
``SpendReports``) and three computed-page lanes (``SpendDashboards`` — the dashboard, category
analysis and export; ``ClassificationWorkbench``; ``MaverickDashboard``). The computed lanes own
no table and write nothing, with the single exception of ``maverick_scan``, which is POST-only and
``@tenant_admin_required``.
"""
