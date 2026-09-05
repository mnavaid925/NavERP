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
and no route in this app uses a converter in its **first** path component: all 63 current first
segments are literals, so no module can shadow another's namespace. Re-check these three against
the concurrently-built 6.16 segments before wiring (L43).

(The neighbouring sub-modules' docstrings state this as "the app registers no greedy ``<str:…>``
converter anywhere", which is **false** — 6.8 registers one at
``ContractsManagement/Contracts.py`` ``contract-sign/<str:token>/``. The conclusion survives
because that converter sits *behind* a literal first segment and so shadows nothing outside
itself, but the premise as written is disprovable by one grep, and ~50 files now repeat it. It is
stated correctly here; correcting the other copies is an app-wide docs pass, not this
sub-module's to fork.)

**Entity 2 (SupplierRiskSignal) claims two more**, checked the same way and against Entity 1's
three:

* ``risk-signals/`` — the monitoring register, its CRUD and the review verb
* ``risk-refresh-due/`` — the refresh board

Neither is a prefix of any existing segment. ``risk-signals/<int:pk>/`` additionally has to stay
in step with ``RiskSignals.alert_link``, which builds the ``ProcurementAlert.link_url`` that a
raised deterioration points at.

Later entities of this sub-module append their own modules here (``FraudAlerts``, ``FraudScan``,
``Policies``, ``Attestations``, ``AuditTrail``) with their own segments; the splat list below
grows, it is never rewritten.

``screening_batch`` is deliberately unregistered — see the note in ``Screenings.py``.
"""
from .RiskSignals import urlpatterns as _rcm_risk_signals
from .Screenings import urlpatterns as _rcm_screenings
from .ScreeningHits import urlpatterns as _rcm_screening_hits


urlpatterns = [
    *_rcm_screenings,      # screenings/ CRUD + clear/escalate/block + rescreening-due/
    *_rcm_screening_hits,  # screening-hits/ queue + dispose/
    *_rcm_risk_signals,    # risk-signals/ CRUD + review/ + risk-refresh-due/
]
