"""6.14 Spend Analytics & Reporting forms.

No re-export block — same reason as the models sub-package: the app-level
``apps/procurement/forms/__init__.py`` imports these entity modules directly.

Two lanes here declare no form and say so in their own docstrings:
``SpendDashboards.py`` (the three computed pages are GET-driven reports whose filter bar is a
plain ``<select>`` group sanitised against a whitelist in the view — stricter than a ``Form``, and
it degrades a junk parameter to "filter ignored" instead of a page full of red text), and
``SpendReportSnapshot``, which has no form by design: a snapshot exists to freeze a computed
result, and a hand-typed one would be a figure with no run behind it.
"""
