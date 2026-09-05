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

**Entity 3 (FraudAlert) claims three more**, checked the same way and against Entity 1's and
Entity 2's five:

* ``fraud-alerts/`` — the fraud register, its CRUD and the one disposition verb that carries all
  four transitions in its POST body
* ``fraud-scan/`` — the rule runner: GET is the window form plus the read-only thresholds, POST
  is the admin-only scan
* ``fraud-board/`` — open alerts by rule, severity and age

None is a prefix of any existing segment. ``fraud-scan/`` is deliberately not ``@require_POST``:
its GET leg writes nothing and renders the thresholds and the not-buildable-rule note that
everybody should be able to read, so only the POST leg is admin-gated, inside the view.

**Entity 4 (PolicyAttestation) claims four more**, checked the same way and against Entity 1's,
Entity 2's and Entity 3's eight:

* ``policies/`` — the policy ACKNOWLEDGMENT register and one detail page, plus the roster verb
  ``policies/<int:pk>/raise-attestations/``
* ``policy-attestations/`` — the sign-off ledger, its CRUD, and the two verbs
* ``my-policies/`` — the staff page: what the signed-in person still owes (L32, sidebar-reachable)
* ``policy-overdue/`` — the chase board

None is a prefix of any existing segment, and none collides with 6.19's ``procurement-policies/``:
Django matches path COMPONENTS, so those are simply different components. **Entity 4 registers NO
policy authoring** — ``ppolicy_create`` / ``_edit`` / ``_delete`` / ``_publish`` / ``_archive``
belong to 6.19, which owns ``procurement.ProcurementPolicy`` itself; 6.17 owns only the
acknowledgement ledger (contract §6a). ``policy-overdue/`` follows ``fraud-scan/`` in being
deliberately not ``@require_POST``: its GET leg writes nothing, and only its POST leg — which
raises one inbox item per overdue person — is admin-gated, inside the view.

**Entity 5 (AuditSeal, the last) claims two more**, checked the same way and against Entity 1's,
Entity 2's, Entity 3's and Entity 4's twelve:

* ``audit-trail/`` — the compliance register over ``core.AuditLog`` and its ``export/`` CSV
* ``audit-seals/`` — the seal register, one detail page, and the two verbs
  ``audit-seals/seal/`` and ``audit-seals/<int:pk>/verify/``

Neither is a prefix of any existing segment, and neither collides with 6.12's ``receipt-audit/``:
Django matches path COMPONENTS, so those are simply different components. ``audit-seals/seal/`` is
declared before ``audit-seals/<int:pk>/`` in its own module — first-match-wins is behaviour, and
the other order would resolve the verb as a request for a seal whose pk is the string "seal".
**Entity 5 registers NO edit and NO delete route**, which is the sub-module's one documented
deviation from the CRUD-completeness rule: a seal whose digest can be edited proves nothing, and
deleting a seal breaks exactly the chain it exists to protect (contract §3). Its two verbs are
gated in opposite directions on purpose — ``seal/`` is admin-only, ``verify/`` is deliberately not,
because a tamper check that only an administrator can run is a check nobody runs.

That completes 6.17: the splat list below grows, it is never rewritten.

``screening_batch`` is deliberately unregistered — see the note in ``Screenings.py``.
"""
from .Attestations import urlpatterns as _rcm_attestations
from .AuditTrail import urlpatterns as _rcm_audit_trail
from .FraudAlerts import urlpatterns as _rcm_fraud_alerts
from .FraudScan import urlpatterns as _rcm_fraud_scan
from .Policies import urlpatterns as _rcm_policies
from .RiskSignals import urlpatterns as _rcm_risk_signals
from .Screenings import urlpatterns as _rcm_screenings
from .ScreeningHits import urlpatterns as _rcm_screening_hits


urlpatterns = [
    *_rcm_screenings,      # screenings/ CRUD + clear/escalate/block + rescreening-due/
    *_rcm_screening_hits,  # screening-hits/ queue + dispose/
    *_rcm_risk_signals,    # risk-signals/ CRUD + review/ + risk-refresh-due/
    *_rcm_fraud_alerts,    # fraud-alerts/ CRUD + disposition/
    *_rcm_fraud_scan,      # fraud-scan/ runner + fraud-board/
    *_rcm_policies,        # policies/ register + raise-attestations/ + my-policies/ + policy-overdue/
    *_rcm_attestations,    # policy-attestations/ CRUD + sign/ + exempt/
    *_rcm_audit_trail,     # audit-trail/ register + export/ + audit-seals/ register + seal/ + verify/
]
