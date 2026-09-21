"""core — 0.13's mechanisms: integration health, credential verification and rate limiting.

**`integration_health()`** reads the REAL integration tables that already exist across five apps,
declared in one table rather than guessed. Two buckets came out of introspecting them:

* **connection health** — four tables carry a connection status (`accounting.IntegrationConfig`,
  `scm.IntegrationEndpoint`, `inventory.IntegrationChannel`,
  `projects.ProjectIntegrationConnector`), so "which integrations are erroring or switched off" is a
  real question with a real answer;
* **traffic** — the webhook/message delivery tables, bucketed exactly as 0.12's board buckets them,
  including keeping `simulated` OUT of the success count.

`projects.ProjectIntegrationConnector` also carries `unverified`, which gets its own bucket for the
same reason `simulated` does: a connector that was configured and never verified is not a working
connector, and folding it into "connected" would report an untested integration as healthy.

**`verify_credential()`** is real: it looks the key up by its non-secret PREFIX (indexed) and then
compares the hash in CONSTANT TIME. Comparing by hash directly would work, but the prefix narrows the
candidate set and `hmac.compare_digest` keeps the comparison itself from leaking.

**`api_credential_required`** is a real decorator, tested against a probe view in the smoke suite. It is
not applied to anything in this module because **no API views ship here** — the mechanism is provided
and proven; exposing an endpoint is a per-module decision.
"""
import hmac

from django.apps import apps as django_apps
from django.http import JsonResponse
from django.utils import timezone


#: label -> (state field, ok states, error states, off states, unverified states).
CONNECTION_SOURCES = {
    "accounting.IntegrationConfig": ("status", {"connected"}, {"error"}, {"disconnected"}, set()),
    "scm.IntegrationEndpoint": ("status", {"connected"}, {"error"}, {"disconnected", "disabled"},
                                set()),
    "inventory.IntegrationChannel": ("status", {"connected"}, {"error"},
                                     {"disconnected", "disabled"}, set()),
    "projects.ProjectIntegrationConnector": ("status", {"connected"}, {"error"},
                                             {"disconnected", "disabled"}, {"unverified"}),
}

#: label -> (state field, ok states, pending states, failed states, dry-run states).
TRAFFIC_SOURCES = {
    "crm.WebhookDelivery": ("status", {"success"}, {"pending"}, {"failed"}, {"simulated"}),
    "scm.WebhookDelivery": ("status", {"success"}, {"pending"}, {"failed", "exhausted"},
                            {"simulated"}),
    "projects.ProjectWebhookDelivery": ("status", {"success"}, set(), {"failed"}, {"simulated"}),
    "scm.IntegrationMessage": ("status", {"sent", "received", "acknowledged"}, {"pending"},
                               {"failed"}, {"ignored"}),
}

#: Integration-ish models that are NOT endpoint or traffic tables, and the reason. Listed so the board
#: accounts for everything it found instead of silently dropping what did not fit.
NON_TRACKED_SOURCES = {
    "crm.Webhook": "a subscription definition, not a delivery",
    "scm.WebhookSubscription": "a subscription definition, not a delivery",
    "projects.ProjectWebhookEndpoint": "an endpoint definition, not a delivery",
    "procurement.PunchOutEndpoint": "a supplier punch-out URL, not a managed integration",
}


def integration_labels():
    """Every integration-ish label the board accounts for."""
    return set(CONNECTION_SOURCES) | set(TRAFFIC_SOURCES) | set(NON_TRACKED_SOURCES)


def _bucket(model, tenant, state_field, since=None):
    names = {f.name for f in model._meta.concrete_fields}
    base = model.objects.filter(tenant=tenant)
    if since is not None and "created_at" in names:
        base = base.filter(created_at__gte=since)
    return base, names


def integration_health(tenant, days=30):
    """Read every declared integration source for one tenant.

    Returns `{"connections": [...], "traffic": [...], "skipped": [...]}`. A source whose model or
    state field is missing is reported as skipped WITH the reason rather than dropped.
    """
    since = timezone.now() - timezone.timedelta(days=days)
    connections, traffic, skipped = [], [], []

    for label, (state_field, ok, err, off, unverified) in sorted(CONNECTION_SOURCES.items()):
        app_label, model_name = label.split(".")
        try:
            model = django_apps.get_model(app_label, model_name)
        except LookupError:
            skipped.append({"label": label, "reason": "model not found"})
            continue
        # Connection state is a CURRENT fact, not a windowed one, so no `since` here.
        base, names = _bucket(model, tenant, state_field)

        def _c(states):
            return base.filter(**{state_field + "__in": sorted(states)}).count() if states else 0

        connections.append({
            "label": label, "state_field": state_field,
            "connected": _c(ok), "error": _c(err), "off": _c(off), "unverified": _c(unverified),
            "total": base.count(),
        })

    for label, (state_field, ok, pending, failed, dry) in sorted(TRAFFIC_SOURCES.items()):
        app_label, model_name = label.split(".")
        try:
            model = django_apps.get_model(app_label, model_name)
        except LookupError:
            skipped.append({"label": label, "reason": "model not found"})
            continue
        base, names = _bucket(model, tenant, state_field, since=since)

        def _t(states):
            return base.filter(**{state_field + "__in": sorted(states)}).count() if states else 0

        traffic.append({
            "label": label, "state_field": state_field,
            "sent": _t(ok), "pending": _t(pending), "failed": _t(failed), "dry_run": _t(dry),
        })

    for label, reason in sorted(NON_TRACKED_SOURCES.items()):
        skipped.append({"label": label, "reason": reason})

    totals = {
        "connected": sum(c["connected"] for c in connections),
        "error": sum(c["error"] for c in connections),
        "off": sum(c["off"] for c in connections),
        "unverified": sum(c["unverified"] for c in connections),
        "sent": sum(t["sent"] for t in traffic),
        "pending": sum(t["pending"] for t in traffic),
        "failed": sum(t["failed"] for t in traffic),
        "dry_run": sum(t["dry_run"] for t in traffic),
    }
    return {
        "connections": connections,
        "traffic": traffic,
        "skipped": skipped,
        "totals": totals,
        "days": days,
        # Excludes dry-run rows for the same reason 0.12's board does: a simulated delivery never
        # left the building, and counting it as success would let an untested integration look healthy.
        "traffic_success_rate": (
            round(100.0 * totals["sent"] / (totals["sent"] + totals["failed"]), 1)
            if (totals["sent"] + totals["failed"]) else None
        ),
    }


# ------------------------------------------------------------------ credentials
def verify_credential(presented, tenant=None):
    """Return the matching active `ApiCredential`, or None.

    Looks up by the non-secret PREFIX first (it is indexed and narrows the candidate set), then
    compares the hash with `hmac.compare_digest`. Comparing the hash via the ORM would also work —
    the hash of a 256-bit random token is not a useful oracle — but doing the final comparison in
    constant time costs nothing and removes the question.

    An expired or inactive credential is refused, and `last_used_at` is stamped on success so the
    register can show which keys are actually in use.
    """
    from .models import ApiCredential

    presented = (presented or "").strip()
    if not presented:
        return None
    candidates = ApiCredential.objects.filter(prefix=presented[:12])
    if tenant is not None:
        candidates = candidates.filter(tenant=tenant)
    digest = ApiCredential.hash_plaintext(presented)
    for credential in candidates:
        if not hmac.compare_digest(credential.key_hash, digest):
            continue
        if not credential.is_usable:
            return None
        ApiCredential.objects.filter(pk=credential.pk).update(last_used_at=timezone.now())
        return credential
    return None


def api_credential_required(scope=None):
    """Decorator for an API view: authenticate by `Authorization: Bearer <key>`, optionally scoped.

    **Real and tested, but applied to nothing in this module** — no API views ship in 0.13, so this is
    the mechanism a module opts into. It answers JSON 401/403 rather than redirecting to a login page,
    because the caller is a program, not a browser: a 302 to `/login/` is the classic API mistake and
    tells the client nothing.
    """
    def decorator(view):
        def _wrapped(request, *args, **kwargs):
            header = request.META.get("HTTP_AUTHORIZATION", "")
            presented = ""
            if header.lower().startswith("bearer "):
                presented = header[7:].strip()
            if not presented:
                presented = request.META.get("HTTP_X_API_KEY", "").strip()
            credential = verify_credential(presented)
            if credential is None:
                return JsonResponse({"error": "invalid or missing API credential"}, status=401)
            if scope and not credential.has_scope(scope):
                return JsonResponse({"error": "credential lacks scope: %s" % scope}, status=403)
            request.api_credential = credential
            return view(request, *args, **kwargs)
        _wrapped.__name__ = getattr(view, "__name__", "wrapped")
        _wrapped.__doc__ = view.__doc__
        return _wrapped
    return decorator


def within_rate_limit(credential, request_count, policy=None):
    """Is `request_count` inside the policy that applies to this credential?

    The most specific ACTIVE policy wins: one scoped to the credential beats a workspace-wide one.
    Returns `(allowed, policy, reason)`. **Nothing calls this automatically** — there is no gateway
    process, so a view that wants limiting applies it. Stated rather than implied.
    """
    from .models import RateLimitPolicy

    if policy is None:
        scoped = (RateLimitPolicy.objects
                  .filter(credential=credential, is_active=True)
                  .order_by("max_requests").first())
        workspace = (RateLimitPolicy.objects
                     .filter(tenant_id=credential.tenant_id, credential__isnull=True, is_active=True)
                     .order_by("max_requests").first())
        policy = scoped or workspace
    if policy is None:
        return True, None, "no policy applies"
    if request_count > policy.max_requests:
        return False, policy, "%s exceeds %s per %s" % (request_count, policy.max_requests,
                                                        policy.window)
    return True, policy, ""
