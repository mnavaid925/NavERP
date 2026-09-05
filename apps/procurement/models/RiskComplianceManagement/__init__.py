"""Procurement 6.17 Risk & Compliance Management — sub-package init (docstring-only).

Re-exports live in ``apps/procurement/models/__init__.py`` — the app-level package is the single
re-export point (6.13/6.14/6.15 precedent).

Entity modules, all five of them:

* ``Screenings`` — the sanctions / denied-party screening register (``ComplianceScreening``), its
  potential-match children (``ScreeningHit``) and the list vocabulary the two share.
* ``RiskSignals`` — ``SupplierRiskSignal``, one bureau observation of a supplier's financial
  health, with the scale table that decides which way is up and the deterioration alert it raises.
* ``FraudAlerts`` — ``FraudAlert`` and the six-rule ``scan()`` detector, its normalisers/maskers
  and its deterministic dedupe keys.
* ``Policies`` — ``PolicyAttestation``, the sign-off ledger over 6.19's ``ProcurementPolicy``
  (which this module reads and never re-declares).
* ``AuditSeals`` — ``AuditSeal``, the hash chain over ``core.AuditLog``, with the PINNED
  ``canonical_line`` serialisation every seal ever taken depends on.
"""
