"""Procurement 6.14 Spend Analytics & Reporting — the computed-page lane declares NO FORM.

The three pages this lane ships (``spend_dashboard``, ``category_spend``, ``spend_export``) are
GET-driven read-only reports. Their filter bar is a plain ``<form method="get">`` of ``<select>``
elements populated from the pinned ``*_choices`` context keys, and the one download route
(``spend_export_download``) reads the SAME GET parameters as the page it hangs off. Nothing here is
POSTed, nothing is saved, and there is no model to bind a ``ModelForm`` to — this lane declares no
table (see ``models/SpendAnalyticsReporting/SpendDashboards.py``).

That is the 6.11 / 6.12 precedent verbatim: ``FulfillmentBoards`` and ``ReceiptBoards`` ship no
forms module either, for the same reason.

**Why a GET filter bar needs no Form class.** A ``Form`` would buy validation, and validation is
exactly the wrong shape for a report URL anybody can hand-edit: ``?basis=xx&range=yy&vendor=abc``
must still render a 200 page with the filter skipped, never a bound form full of red text and never
a 500 (L11). The view layer therefore sanitizes each parameter against its own choice list and
guards every pk with ``apps.core.crud.as_db_int`` — a whitelist, which is stricter than a form
would have been, and which degrades to "filter ignored" instead of "page broken".

Nothing is exported; the package ``__init__`` has nothing to re-export from here.
"""

#: Nothing to re-export — stated explicitly so the Integrate phase's ``__init__`` block for this
#: sub-module skips this module rather than importing a name that was never here.
__all__ = []
