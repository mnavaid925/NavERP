"""SCM 4.15 Cold Chain Management — the three COMPUTED report pages: ``cold-storage-report/``,
``cold-chain-compliance/`` and ``reefer-board/``.

Each is a single GET page derived from rows that already exist — no new table, no new column, and
therefore no create/edit/delete route and no ``<int:pk>`` at all (the ``pm_forecast`` /
``sparepart_list`` / ``labor_board`` precedent). Every option each page takes is a QUERY STRING, so
none of them adds a route beyond the one below:

* ``cold-storage-report/`` — ``?view=&storage_condition=&location=&expiring_within=``
* ``cold-chain-compliance/`` — ``?date_from=&date_to=&monitor=&status=&assessment=&format=csv``
* ``reefer-board/`` — ``?q=&criticality=&pm_due=&range=``

COLLISION CHECK — all three prefixes checked against the WHOLE concatenated urlconf, not merely
against this block:

* ``cold-storage-report/`` and ``cold-chain-compliance/`` — nothing anywhere in ``scm`` starts with
  ``cold`` except 4.15's own ``cold-chain-monitors/``. Django matches WHOLE path components and never
  splits one at a hyphen, so the three are unrelated segments and none can shadow another. Do NOT
  "tidy" any of them to look like another.
* ``cold-chain-compliance/`` is a DISTINCT whole component from 4.12's ``compliance-requirements/``
  and ``compliance-checks/``, and from its report routes. They are also different things: 4.12
  tracks trade licences and ESG obligations, this one is the temperature record.
* ``reefer-board/`` — nothing anywhere starts with ``reefer``. It is a separate component from
  4.14's ``labor-board/``, which is the other computed board in this app.

None of the three introduces a greedy ``<str:…>`` converter, and there is no ``<int:pk>`` route in
this module, so there is nothing here that could swallow a literal.

WHY THESE ARE PAGES AND NOT TABLES — the headline fact about 4.15:

* **Cold Storage Inventory is 4.3, filtered.** On-hand is the live SUM of the append-only
  ``StockMove`` ledger, the condition mismatch comes from the two ``storage_condition`` columns,
  expiry from ``LotSerial.expiry_date`` and quarantine from ``LotSerial.status`` — which **4.9's
  non-conformance verb writes and 4.15 only READS**. There is no zone table and no shelf-life table.
* **Compliance Reporting is a computed page plus three stored columns.** The excursion log is 4.15's
  own rows filtered by window; the profile is derived over ``TemperatureReading``; the audit trail is
  ``core.AuditLog`` — there is no second audit table. The only persistent artefact is the monitor's
  calibration triple. **The page must not claim Part 11 / Annex 11 conformance.**
* **Maintenance of Reefers is a board over 4.13, and 4.15 declares ZERO maintenance entities.** A
  reefer is DERIVED as *an ``Asset`` with an active ``ColdChainMonitor``*, which needs no change to
  4.13 at all and cannot go stale the way a hand-set ``asset_type`` would. **4.15 adds NO route under
  ``assets/``, ``maintenance-plans/`` or ``maintenance-work-orders/``** — 4.13's urlconf is untouched.
"""
from django.urls import path

from apps.scm import views

urlpatterns = [
    # Cold on-hand, condition mismatches, FEFO expiry, quarantined lots and unmonitored cold storage.
    path("cold-storage-report/", views.cold_storage_report, name="cold_storage_report"),
    # The excursion log + calibration status + per-monitor % time in range and MKT (+ ?format=csv).
    path("cold-chain-compliance/", views.cold_chain_compliance_report,
         name="cold_chain_compliance_report"),
    # One row per reefer: cargo temperature, open excursions, 4.13's PM due status, open jobs, the
    # run-hours meter and the warranty chip.
    path("reefer-board/", views.reefer_board, name="reefer_board"),
]
