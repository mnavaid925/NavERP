"""core — 0.12's mechanisms: delivery tracking, channel resolution and template rendering.

Three jobs, each kept out of the views so it is testable with fixed inputs.

**`delivery_stats()`** reads the REAL delivery tables that already exist across the repo, declared in
one table rather than guessed. Two findings from introspecting them shaped it:

* **`procurement.DeliverySchedule` is NOT a message delivery.** Its name matches, and a naive scan
  would have counted physical goods shipments (`planned/confirmed/shipped/received/cancelled`) as
  notifications. It is listed with the reason instead.
* **`simulated` is a distinct bucket, not a success.** `crm.WebhookDelivery`,
  `scm.WebhookDelivery` and `projects.ProjectWebhookDelivery` all carry it, and it means the delivery
  was a DRY RUN — nothing left the building. Folding it into "sent" would let a workspace that has
  never actually sent anything report a 100% success rate, which is the most dangerous number this
  board could show.

**`resolve_channels()`** combines the platform routing rules with one member's preferences. A
preference row is an explicit opt-out; absence means "take the rule's default", which is why the
result reports which of the two decided.

**`render_template()`** renders a stored template body. The context is restricted to a plain dict of
primitives and autoescaping is on — stated here because a stored template is authored content, and
"we render whatever it says against whatever we pass" is a real injection surface if the context is
ever a model instance.
"""
from django.apps import apps as django_apps
from django.template import Context, Template, TemplateSyntaxError
from django.utils import timezone

#: label -> (state field, ok states, pending states, failed states, simulated states).
#:
#: Verified by introspecting each model's choices rather than assumed.
DELIVERY_SOURCES = {
    "crm.WebhookDelivery": ("status", {"success"}, {"pending"}, {"failed"}, {"simulated"}),
    "scm.WebhookDelivery": ("status", {"success"}, {"pending"}, {"failed", "exhausted"},
                            {"simulated"}),
    "projects.ProjectWebhookDelivery": ("status", {"success"}, set(), {"failed"}, {"simulated"}),
    "inventory.NotificationDelivery": ("status", {"sent"}, {"queued"}, {"failed"}, set()),
    "scm.IntegrationMessage": ("status", {"sent", "received", "acknowledged"}, {"pending"},
                               {"failed"}, {"ignored"}),
}

#: Delivery-ish models that are NOT message deliveries, and the reason. Listed so the board accounts
#: for every one it found rather than silently dropping the ones that did not fit.
NON_DELIVERY_SOURCES = {
    "procurement.DeliverySchedule": "a physical goods delivery, not a message",
    "projects.ProjectNotification": "a notification with no delivery state to track",
    "projects.ChannelMessage": "a chat message with no delivery state to track",
}


def delivery_labels():
    """Every delivery-ish label the board accounts for."""
    return set(DELIVERY_SOURCES) | set(NON_DELIVERY_SOURCES)


def delivery_stats(tenant, days=30):
    """Count the real delivery rows per source, in four buckets.

    `simulated` is kept separate from `sent` on purpose — see the module docstring. A source whose
    model or state field is missing is reported as skipped WITH the reason.
    """
    since = timezone.now() - timezone.timedelta(days=days)
    rows, skipped = [], []
    totals = {"sent": 0, "pending": 0, "failed": 0, "simulated": 0, "total": 0}

    for label, (state_field, ok, pending, failed, simulated) in sorted(DELIVERY_SOURCES.items()):
        app_label, model_name = label.split(".")
        try:
            model = django_apps.get_model(app_label, model_name)
        except LookupError:
            skipped.append({"label": label, "reason": "model not found"})
            continue
        names = {f.name for f in model._meta.concrete_fields}
        if "tenant" not in names or state_field not in names:
            skipped.append({"label": label, "reason": "no tenant or state field"})
            continue

        base = model.objects.filter(tenant=tenant)
        if "created_at" in names:
            base = base.filter(created_at__gte=since)

        def _count(states):
            # The key must be built by concatenation, NOT with a "%s" placeholder: a dict key is not
            # a format string, so `{"%s__in": ...}` is literally a lookup on a field named `%s`.
            return base.filter(**{state_field + "__in": sorted(states)}).count() if states else 0

        row = {
            "label": label,
            "state_field": state_field,
            "sent": _count(ok),
            "pending": _count(pending),
            "failed": _count(failed),
            "simulated": _count(simulated),
        }
        row["total"] = row["sent"] + row["pending"] + row["failed"] + row["simulated"]
        for key in totals:
            totals[key] += row[key] if key in row else 0
        rows.append(row)

    for label, reason in sorted(NON_DELIVERY_SOURCES.items()):
        skipped.append({"label": label, "reason": reason})

    return {
        "rows": rows,
        "skipped": skipped,
        "totals": totals,
        "days": days,
        # A success rate that EXCLUDES simulated rows, because including them would inflate it.
        "real_success_rate": (
            round(100.0 * totals["sent"] / (totals["sent"] + totals["failed"]), 1)
            if (totals["sent"] + totals["failed"]) else None
        ),
    }


def resolve_channels(tenant, event, user=None):
    """Which channels this event should reach `user` on, and why.

    Returns a list of dicts with `rule`, `channel`, `enabled` and `decided_by`:
      * `decided_by="preference"` — the member has an explicit opt-out or opt-in for this event and
        channel;
      * `decided_by="rule"` — no preference row exists, so the rule's default applies.

    Saying WHICH of the two decided is the point: a member who opted out and a member who never
    expressed a preference both end up not being messaged, but only one of them chose that, and an
    operator investigating "why didn't I get this?" needs to know which.
    """
    from .models import NotificationPreference, NotificationRule

    rules = (NotificationRule.objects
             .filter(tenant=tenant, event=event, is_active=True)
             .select_related("channel", "template", "audience_role")
             .order_by("priority", "name"))
    resolved = []
    for rule in rules:
        if not rule.channel.is_enabled:
            resolved.append({"rule": rule, "channel": rule.channel, "enabled": False,
                             "decided_by": "channel_disabled"})
            continue
        pref = None
        if user is not None:
            pref = NotificationPreference.objects.filter(
                tenant=tenant, user=user, event=event, channel_kind=rule.channel.kind).first()
        if pref is not None:
            resolved.append({"rule": rule, "channel": rule.channel, "enabled": pref.is_enabled,
                             "decided_by": "preference"})
        else:
            resolved.append({"rule": rule, "channel": rule.channel, "enabled": True,
                             "decided_by": "rule"})
    return resolved


def render_template(template_or_body, context):
    """Render a stored template against a context. Returns (text, error).

    Autoescaping is ON (Django's default for `Template`), so a value in the context cannot inject
    markup. The context is expected to be a plain dict of primitives: passing a model instance would
    hand a template author every attribute on it, including relations, which is why the callers in
    this app only ever pass dicts.

    A syntax error returns the error rather than raising — a broken stored template must not 500 the
    page that renders it, and the operator needs to see which template is broken.
    """
    body = getattr(template_or_body, "body", template_or_body) or ""
    try:
        return Template(body).render(Context(context or {})), ""
    except TemplateSyntaxError as exc:
        return "", "Template syntax error: %s" % exc
