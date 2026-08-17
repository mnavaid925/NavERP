"""SCM 4.19 Integration & API Gateway — ``WebhookSubscription`` views: the outbound event rules.

Six function-based views — list / create / detail / edit / delete / rotate-secret — over the
tenant-scoped register of *"when X happens, POST it to this URL"* standing instructions. This list is
the target of the 4.19 sidebar's **Webhooks** bullet, and it is the only page in the sub-module from
which the delivery log is reached (``scm:webhookdelivery_list?subscription=<pk>``) — that log takes no
sidebar key of its own, by the ``ClientRateCard`` / ``ReorderRule`` / ``PortalActivity`` rule: a table
reached from the page that uses it does not need a bullet.

--------------------------------------------------------------------------------------------------
NOTHING HERE SENDS ANYTHING
--------------------------------------------------------------------------------------------------
There is no HTTP client in this module and none anywhere under ``apps/scm`` for 4.19 — no
``requests``, ``urllib``, ``httpx`` or ``http.client``. Creating a subscription records a rule;
rotating its secret writes a prefix + hash; nothing fires, nothing retries on a clock, and no
counter decrements. There is deliberately **no "test delivery" action** for the same reason there is
no reveal view: a test button is an outbound HTTP request from the server to a tenant-supplied URL,
which is exactly the SSRF surface the model's ``target_url`` comment defers until an allow-list and a
private-IP block exist.

--------------------------------------------------------------------------------------------------
THE ONE THING ``crud_list`` CANNOT DO FOR THIS PAGE
--------------------------------------------------------------------------------------------------
``crud_list``'s ``(param, lookup, is_int)`` spec applies a GET value DIRECTLY as an ORM lookup value.
``?status=active`` is not a value ``is_active`` can take — ``active → True`` / ``inactive → False``
is a TRANSLATION, not a lookup — so it is applied to the queryset in :func:`webhooksubscription_list`
**before** ``crud_list`` is called, and therefore, like every declared filter, before pagination. Any
other value is IGNORED: a hand-edited ``?status=banana`` narrows nothing and returns 200, never 500
(L11). This is the ``FinanceIntegration/DutyTariffs.py`` precedent, applied to the same shape of
column.

The other three filters (``trigger_entity`` / ``trigger_event`` / ``payload_format``) are plain
CharField equality and go through ``crud_list``'s own spec. They are STRING compares in the template
— ``{% if request.GET.trigger_entity == value %}`` — never ``|stringformat:"d"`` (which is for pk
params; **this page has no pk filter at all**) and never ``|slugify``.

--------------------------------------------------------------------------------------------------
THE ROTATED SECRET IS REVEALED THROUGH A POP-ONCE SESSION KEY, **NOT** THROUGH ``messages`` (L25)
--------------------------------------------------------------------------------------------------
This is a deliberate, documented deviation from the frozen contract, which specified
``messages.success`` carrying the plaintext. L25 forbids exactly that, in those words: *"A one-time
secret must NOT be surfaced via the messages framework (it persists in the session store)."* The
messages framework serialises to the session backend, so a flashed plaintext lingers in
``django_session`` until some later render consumes it — readable from a database dump, a backup or a
hijacked session, and liable to be copied into logs.

So :func:`webhooksubscription_rotate_secret` writes ``request.session["_whk_secret_reveal"] =
{"pk": …, "secret": …}`` and :func:`webhooksubscription_detail` ``pop``s it into the ADDITIVE context
key ``plaintext_once``. The flash message still fires but carries no secret. This is byte-for-byte
the shipped sibling ``accounting.integration_rotate_key`` /``integration_detail`` pair, which is the
tie-break the build brief names: match the sibling sub-module and say so.

``plaintext_once`` is ADDITIVE — no contracted key is renamed, removed or repurposed, so a template
that ignores it renders exactly as specified. To surface the value, the detail template needs a copy
box gated on ``{% if plaintext_once %}``. **Until it has one, a rotated secret is never displayed.**
That costs nothing operationally in this pass — nothing signs, so the plaintext has no consumer — but
it is the one thing about this module a template pass still has to finish.

--------------------------------------------------------------------------------------------------
CONTEXT-VAR CONTRACT (pinned, L7 — the templates are written by a separate agent, so EVERY key each
page consumes is listed here, not merely the row variable)
--------------------------------------------------------------------------------------------------
``scm/integration/webhooksubscription/list.html``
    ``object_list`` (THE ROW VAR — never ``subscriptions``, which is the DELIVERY list's dropdown
    queryset), ``page_obj``, ``q`` — all from ``crud_list``; guard prev/next with
    ``has_previous``/``has_next`` (L9). Filter widgets: ``entity_choices``, ``event_choices``,
    ``format_choices``, ``status_choices``. Header chips: ``stats`` with EXACTLY ``total`` /
    ``active`` / ``inactive`` / ``failing`` (ints).

``scm/integration/webhooksubscription/form.html`` (shared create + edit)
    ``form``, ``is_edit`` — plus ``obj`` **on the edit path only**. ``crud_create`` passes no ``obj``,
    so every ``{{ obj.* }}`` must sit inside ``{% if is_edit %}`` or the create page renders blank
    fragments (L7/L8: a missing context name renders empty at HTTP 200, which is why it survives a
    status-only smoke test).

``scm/integration/webhooksubscription/detail.html``
    ``obj``, ``recent_deliveries``, ``delivery_stats`` (EXACTLY ``total`` / ``pending`` / ``success``
    / ``failed`` / ``exhausted`` / ``simulated``), ``is_tenant_admin``, and the additive
    ``plaintext_once`` described above.

Badges are COLOUR-NAMED ``theme.css`` classes only — ``badge-green`` / ``badge-red`` / ``badge-amber``
/ ``badge-info`` / ``badge-muted`` / ``badge-slate``. ``badge-success`` / ``badge-danger`` /
``badge-warning`` DO NOT EXIST and render as completely unstyled text (L33, shipped four times).
"""
from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._helpers import _is_tenant_admin, _need_tenant

from apps.scm.forms import WebhookSubscriptionForm
from apps.scm.models import WebhookDelivery, WebhookSubscription
# BY NAME, never `import *` — see the note in the models entity module. `_choices.py` is owned and
# created by the `IntegrationEndpoints` entity; this module only reads from it.
from apps.scm.models.IntegrationApiGateway._choices import (
    PAYLOAD_FORMAT_CHOICES,
    WEBHOOK_ENTITY_CHOICES,
    WEBHOOK_EVENT_CHOICES,
)


#: The ``?status=`` vocabulary for this page. A LITERAL, not a model constant, because
#: ``WebhookSubscription`` has **no ``status`` column at all** — it has ``is_active``, and these two
#: strings are the URL spelling of that boolean. Passed to the template as ``status_choices`` so the
#: widget and the view can never disagree about the two values. (``DutyTariffs.py`` precedent.)
STATUS_CHOICES = [("active", "Active"), ("inactive", "Inactive")]

#: How ``?status`` maps onto the column. Anything not in here is ignored — see the module docstring.
_STATUS_TO_ACTIVE = {"active": True, "inactive": False}

#: How many delivery rows the detail page's panel shows. A queryset SLICE, so the DATABASE applies the
#: LIMIT — it bounds what is FETCHED, not merely what is rendered (L40 §1: a guard that first builds
#: the whole thing IS the payload). Deliveries accumulate one row per attempt forever, so an
#: unbounded panel is a page that gets slower every week it is left alone.
MAX_PANEL_ROWS = 10

#: The session key the one-time secret reveal travels on. Read (and POPPED) by
#: :func:`webhooksubscription_detail`; written only by :func:`webhooksubscription_rotate_secret`.
#: See the module docstring for why this is not a flash message (L25).
_REVEAL_SESSION_KEY = "_whk_secret_reveal"


def _delivery_qs(tenant, subscription_pk):
    """Every delivery attempt for one subscription, TENANT-SCOPED FIRST.

    Both terms matter and the order they are written in is the readable statement of why:
    ``tenant=`` is the authorisation boundary, ``subscription_id=`` is the selection. Filtering only
    on the subscription pk would answer for another workspace's rule whenever a pk was guessed — the
    detail page's 404 would still fire, but the panel's queryset is built BEFORE ``crud_detail``
    resolves the object, so it must not depend on that 404 for its scoping.

    Takes the pk rather than the object because ``crud_detail`` fetches the object itself; asking for
    it here would mean reading the same row twice.
    """
    return WebhookDelivery.objects.filter(tenant=tenant, subscription_id=subscription_pk)


# =================================================================================================
# The register
# =================================================================================================
@login_required
def webhooksubscription_list(request):
    """Every outbound event rule in the workspace.

    **Filter GET params**, every one applied BEFORE pagination:

    * ``q`` — free text (icontains, OR'd) over ``name`` / ``number`` / ``target_url``.
    * ``status`` — ``active`` | ``inactive``, TRANSLATED onto ``is_active`` here because
      ``crud_list`` cannot express a mapping. Any other value narrows nothing and returns 200 (L11).
    * ``trigger_entity`` / ``trigger_event`` / ``payload_format`` — exact CharField matches through
      ``crud_list``'s own spec. String compares in the template; ``|stringformat:"d"`` would be
      wrong (it is for pk params, and this page has none).

    **Context**, exhaustively — ``object_list`` / ``page_obj`` / ``q`` from ``crud_list``, plus
    ``entity_choices`` / ``event_choices`` / ``format_choices`` / ``status_choices`` for the four
    widgets and ``stats`` for the header chips.

    ``stats`` is computed over the WHOLE workspace queryset, never the filtered page: *"3 rules are
    failing"* is a fact somebody acts on, and a figure that moved as you browsed or filtered would be
    worse than no figure. One ``aggregate()`` call, four conditional counts — no alias here collides
    with a model field name (``active`` is not ``is_active``), which is the trap that turns a shared
    aggregate into a ``FieldError``.

    **No ``select_related``**, deliberately: this model has no foreign key beyond ``tenant``, so
    there is no join for a row or a ``__str__`` to walk. Per-row reads are all plain columns and
    ``get_*_display`` labels, plus :attr:`~apps.scm.models.WebhookSubscription.masked`, which is a
    pure property over two columns the row already carries and queries nothing.
    """
    tenant = request.tenant
    qs = WebhookSubscription.objects.filter(tenant=tenant)

    # The translation `crud_list` cannot do. Applied to the queryset, so it is honoured before
    # pagination exactly like every declared filter; an unrecognised value falls through untouched.
    wanted = _STATUS_TO_ACTIVE.get(request.GET.get("status", "").strip())
    if wanted is not None:
        qs = qs.filter(is_active=wanted)

    stats = WebhookSubscription.objects.filter(tenant=tenant).aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(is_active=True)),
        inactive=Count("id", filter=Q(is_active=False)),
        # "Failing" is the counter's own state, not a threshold comparison: nothing in this pass
        # increments `consecutive_failures`, so this chip reads 0 until a transport pass exists —
        # which is the honest answer, not a bug.
        failing=Count("id", filter=Q(consecutive_failures__gt=0)))

    return crud_list(
        request, qs, "scm/integration/webhooksubscription/list.html",
        search_fields=("name", "number", "target_url"),
        filters=(
            ("trigger_entity", "trigger_entity", False),
            ("trigger_event", "trigger_event", False),
            ("payload_format", "payload_format", False),
        ),
        extra_context={
            "entity_choices": WEBHOOK_ENTITY_CHOICES,
            "event_choices": WEBHOOK_EVENT_CHOICES,
            "format_choices": PAYLOAD_FORMAT_CHOICES,
            "status_choices": STATUS_CHOICES,
            "stats": {key: value or 0 for key, value in stats.items()},
        })


# =================================================================================================
# CRUD
# =================================================================================================
@login_required
def webhooksubscription_create(request):
    """Add an event rule. ``crud_create`` stamps the tenant, writes the audit row and redirects.

    ``_need_tenant`` refuses FIRST so the message steers back to this list rather than to the
    dashboard: the superuser has ``tenant=None`` BY DESIGN and every scm view filters by tenant, so
    creating here would otherwise mint an orphan row nobody can see.

    ``WebhookSubscriptionForm`` ALSO stamps the tenant (through ``TenantUniqueMixin``), and that is
    not redundancy — ``crud_create`` assigns ``obj.tenant`` only AFTER ``is_valid()``, so without the
    form-side stamp the ``("tenant", "name")`` uniqueness check would validate an instance whose
    ``tenant_id`` is ``None``, which is the exact case Django skips. It would be dead code on the
    create path, and the create path is the one a duplicate name arrives on.

    Context: ``form``, ``is_edit`` (``False``). **``obj`` does not exist on this path** — every
    ``{{ obj.* }}`` in the shared form template must sit inside ``{% if is_edit %}``.
    """
    if _need_tenant(request):
        return redirect("scm:webhooksubscription_list")
    return crud_create(request, form_class=WebhookSubscriptionForm,
                       template="scm/integration/webhooksubscription/form.html",
                       success_url="scm:webhooksubscription_list")


@login_required
def webhooksubscription_detail(request, pk):
    """One rule: its trigger, its target, its secret's fingerprint and its recent attempts.

    Context keys, exhaustively (the template is written by a separate agent):

    * ``obj`` — the :class:`~apps.scm.models.WebhookSubscription`, from ``crud_detail``. Render
      ``obj.masked`` for the signing secret, or *Not set* when it is blank. **Never render
      ``obj.signing_secret_hash``** — a digest is still the credential's fingerprint, and publishing
      it hands an offline attacker their verification oracle.
    * ``recent_deliveries`` — the last :data:`MAX_PANEL_ROWS` attempts, newest first. The full log is
      one link away at ``scm:webhookdelivery_list?subscription={{ obj.pk }}``.
    * ``delivery_stats`` — a dict with EXACTLY ``total`` / ``pending`` / ``success`` / ``failed`` /
      ``exhausted`` / ``simulated`` (ints). **DERIVED on read by one ``aggregate()``, never stored**
      (L29): a cached counter beside an append-only log is a second source of truth for a fact the
      log already answers, and the two disagree the first time a write is rolled back.
    * ``is_tenant_admin`` — gates the rotate-secret and delete buttons. Both actions are
      ``@tenant_admin_required``, and hiding a button a member's POST would be refused anyway is
      courtesy, not the control: the decorator is the control.
    * ``plaintext_once`` — the freshly rotated secret, shown exactly once, or ``None``. ADDITIVE to
      the frozen contract; see the module docstring for why the reveal travels on a pop-once session
      key rather than a flash message (L25), and what the template still needs to render it.

    The pop happens on EVERY visit to this page, which is what makes "exactly once" true: a refresh
    finds the key already gone. It is keyed on the pk so a reveal cannot bleed onto a different
    subscription's page.
    """
    deliveries = _delivery_qs(request.tenant, pk)

    stats = deliveries.aggregate(
        total=Count("id"),
        pending=Count("id", filter=Q(status="pending")),
        success=Count("id", filter=Q(status="success")),
        failed=Count("id", filter=Q(status="failed")),
        exhausted=Count("id", filter=Q(status="exhausted")),
        simulated=Count("id", filter=Q(status="simulated")))

    reveal = request.session.pop(_REVEAL_SESSION_KEY, None)
    plaintext_once = reveal["secret"] if reveal and reveal.get("pk") == pk else None

    return crud_detail(
        request, model=WebhookSubscription, pk=pk,
        template="scm/integration/webhooksubscription/detail.html",
        extra_context={
            # An explicit TOTAL order on the slice. `Meta.ordering` already says the same thing, but
            # a panel that takes the first N rows must not depend on a tie being broken the same way
            # twice — two attempts written in the same tick would otherwise be free to swap.
            "recent_deliveries": deliveries.order_by("-triggered_at", "-id")[:MAX_PANEL_ROWS],
            "delivery_stats": {key: value or 0 for key, value in stats.items()},
            "is_tenant_admin": _is_tenant_admin(request.user),
            "plaintext_once": plaintext_once,
        })


@login_required
def webhooksubscription_edit(request, pk):
    """Correct a rule: retarget it, change what fires it, switch it off.

    No status ladder and no edit gate, deliberately — a subscription is CONFIGURATION, not a document
    with a lifecycle. Nothing it has already "done" can be restated by editing it either, because
    every :class:`~apps.scm.models.WebhookDelivery` row snapshots its own ``event`` and payload
    excerpt at the moment it was written; changing the rule changes what the NEXT attempt would carry
    and nothing that is already in the log.

    ``success_url`` is the LIST route, not the detail one. ``crud_edit`` finishes with a bare
    ``redirect(success_url)`` and passes no arguments, so a route requiring ``pk`` would raise
    ``NoReverseMatch`` — on the SUCCESS path, after the row had already been written.

    Context: ``form``, ``obj``, ``is_edit`` (``True``).
    """
    return crud_edit(request, model=WebhookSubscription, pk=pk,
                     form_class=WebhookSubscriptionForm,
                     template="scm/integration/webhooksubscription/form.html",
                     success_url="scm:webhooksubscription_list")


@login_required
@tenant_admin_required
@require_POST
def webhooksubscription_delete(request, pk):
    """Delete a rule **and its whole delivery log**. POST-only; tenant-admin only.

    ``WebhookDelivery.subscription`` is ``CASCADE``, so this is the one destructive verb in the
    sub-module that takes evidence with it — every attempt ever recorded against this rule goes in
    the same statement. The attempts are counted BEFORE the delete so the follow-up message can say
    how much went, rather than leaving somebody to discover it; the confirm dialog in the template
    says the same thing before the POST is sent.

    That cascade is correct rather than a hazard to work around: a delivery row records an attempt to
    honour a rule, so it is telemetry about the rule and has no independent meaning once the rule is
    gone. The softer move — clearing ``is_active`` — stops the rule dead while keeping every row
    readable, and the message steers there.

    ``@tenant_admin_required`` because a webhook target is an egress path out of the workspace, so
    who may remove one is workspace configuration (L27). It already wraps ``@login_required``
    internally; both are written out so the gate reads at a glance rather than needing the decorator
    module open.

    ``crud_delete`` writes the audit row BEFORE deleting. Wrapping the pair in
    ``transaction.atomic()`` rolls that row back with a delete that then fails, so the trail can
    never record something that did not happen.
    """
    with transaction.atomic():
        # Counted inside the transaction, before the delete, so the number reported is the number
        # actually removed rather than a figure read a moment earlier.
        delivery_count = _delivery_qs(request.tenant, pk).count()
        response = crud_delete(request, model=WebhookSubscription, pk=pk,
                               success_url="scm:webhooksubscription_list")

    if delivery_count:
        messages.info(request, f"{delivery_count} delivery record"
                               f"{'' if delivery_count == 1 else 's'} went with it. To stop a rule "
                               f"without losing its history, clear its Active box instead.")
    else:
        messages.info(request, "To stop a rule without losing its history, clear its Active box "
                               "instead — an inactive subscription fires nothing and stays readable.")
    return response


# =================================================================================================
# The one privileged verb
# =================================================================================================
@login_required
@tenant_admin_required
@require_POST
def webhooksubscription_rotate_secret(request, pk):
    """Mint a new signing secret, store its prefix + hash, and reveal the plaintext exactly once.

    **This fires no HTTP request.** There is no test delivery, no reveal view and no way to read the
    value back afterwards — see the module docstring. Rotation here means "the registered credential
    marker changed", which is all a pass with no transport can honestly mean by it.

    What happens, in order:

    1. ``generate_secret()`` — ``secrets.token_urlsafe(24)`` from the CSPRNG, never ``random`` and
       never a uuid4 hex.
    2. ``set_signing_secret()`` stores ONLY ``plaintext[:8]`` and its SHA-256 digest. The plaintext
       never reaches the database.
    3. ``save(update_fields=…)`` — narrow on purpose. A full ``save()`` would write back every
       in-memory column, including any a concurrent edit had just changed; ``updated_at`` is
       ``auto_now`` so it only fires when it is IN the list.
    4. The audit row is written INSIDE the transaction, with ``{"signing_secret": "rotated"}`` —
       **never the plaintext, and never the hash**. An audit trail is immutable and outlives any
       later encryption pass, so anything copied into it is copied there permanently.
    5. The plaintext goes into a pop-once SESSION key for the redirect target to render, and the
       flash message deliberately carries no secret (L25).

    ``@tenant_admin_required`` for the L27 reason: rotating a credential is workspace configuration,
    not ordinary member work.
    """
    obj = get_object_or_404(WebhookSubscription, pk=pk, tenant=request.tenant)

    plaintext = WebhookSubscription.generate_secret()
    with transaction.atomic():
        obj.set_signing_secret(plaintext)
        obj.save(update_fields=["signing_secret_prefix", "signing_secret_hash", "updated_at"])
        # This view does not go through the `crud_*` helpers, which audit automatically — so it
        # audits itself. A privileged credential change with no trail is the one write in this module
        # that would be invisible afterwards.
        write_audit_log(request.user, obj, "update", changes={"signing_secret": "rotated"})

    request.session[_REVEAL_SESSION_KEY] = {"pk": obj.pk, "secret": plaintext}
    messages.success(request, "Signing secret rotated — the new value is shown once on this page. "
                              "Copy it now; it cannot be retrieved again.")
    return redirect("scm:webhooksubscription_detail", pk=pk)
