"""6.17 Risk & Compliance Management URL patterns — one module per views module.

``app_name`` is set once in ``apps/procurement/urls/__init__.py``; this package only concatenates
its entity/page modules' ``urlpatterns``.

**Entity 1 (ComplianceScreening + ScreeningHit) claims three first segments**, every one of them
a new whole component checked against the inventory in ``apps/procurement/urls/__init__.py``:

* ``screenings/`` — the register, its CRUD, the three decision verbs, and the
  ``screenings/<int:pk>/hits/add/`` child route
* ``screening-hits/`` — the cross-screening resolution queue and the adjudication verb
* ``rescreening-due/`` — the re-screening board

None is a prefix of any other segment in the app — Django matches path components, not strings —
and this app registers no greedy ``<str:…>`` converter anywhere, so there is no cross-module
shadowing surface to reason about. Re-check these three against the concurrently-built 6.16
segments before wiring (L43).

Later entities of this sub-module append their own modules here (``RiskSignals``,
``FraudAlerts``, ``FraudScan``, ``Policies``, ``Attestations``, ``AuditTrail``) with their own
segments; the splat list below grows, it is never rewritten.

``screening_batch`` is deliberately unregistered — see the note in ``Screenings.py``.
"""
from .Screenings import urlpatterns as _rcm_screenings
from .ScreeningHits import urlpatterns as _rcm_screening_hits


urlpatterns = [
    *_rcm_screenings,      # screenings/ CRUD + clear/escalate/block + rescreening-due/
    *_rcm_screening_hits,  # screening-hits/ queue + dispose/
]
