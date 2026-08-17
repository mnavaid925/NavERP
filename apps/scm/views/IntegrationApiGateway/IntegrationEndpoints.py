"""SCM 4.19 Integration & API Gateway — ``IntegrationEndpoint`` views: the CONNECTION REGISTER.

This is the sub-module's root screen and the target of FOUR of the five 4.19 sidebar bullets. "ERP
Integration", "E-commerce Integration", "IoT Gateway" and "EDI Management" are four **distinct
category-scoped route names resolving to ONE view** through Django's extra-options dict, so the EDI
person lands on the trading-partner register rather than on a mixed list — while the data stays in
one table discriminated by ``category``, which is the compression ``accounting.IntegrationConfig``
already made. Four near-identical tables would be four copies of the same credential, transport and
lifecycle columns, and the copy that gets missed on the next change is the one that keeps a stale
rule.

--------------------------------------------------------------------------------------------------
WHAT THIS MODULE DELIBERATELY DOES NOT DO
--------------------------------------------------------------------------------------------------
**No outbound HTTP exists anywhere in 4.19.** There is no "test connection" view, no reveal view and
no sync verb, and none may be added without first adding an allow-list plus a private-IP block
(RFC1918, loopback, 169.254.0.0/16, IPv6 ULA) and DNS-rebinding re-resolution — ``endpoint_url`` is a
tenant-editable URL the server would fetch, which is textbook SSRF. :func:`integrationendpoint_rotate_credential`
mints a credential and stores a marker; it dials nothing.

**Nothing here writes ``LogisticsClient``.** 4.19 adds no column to it, takes no route beneath
``logistics-clients/`` and re-declares none of its five integration columns (constraint A). The
client's EDI identifiers are READ through ``obj.effective_interchange_id`` /
``obj.effective_interchange_qualifier``. 4.17 created ``LogisticsClient.last_synced_at`` for a future
transport pass to write; this pass does not write it, because there is no sync to timestamp.

--------------------------------------------------------------------------------------------------
Context-var contract (pinned, L7 — the templates are written by a separate agent, so EVERY key each
page consumes is listed, not merely the list variable):
--------------------------------------------------------------------------------------------------
* ``scm/integration/integrationendpoint/list.html`` — ``object_list`` + ``page_obj`` + ``q`` (from
  ``crud_list``); the seven filter vocabularies ``category_choices`` / ``system_choices`` /
  ``direction_choices`` / ``transport_choices`` / ``status_choices`` / ``environment_choices`` /
  ``lifecycle_choices`` (**note the last key is ``lifecycle_choices`` while its GET param is
  ``lifecycle_stage``**); ``active_category`` (str — ``"erp"``/``"ecommerce"``/``"iot"``/``"edi"`` on
  a category route, else ``""``); and ``stats`` (dict, keys ``total`` / ``connected`` / ``error`` /
  ``disabled`` / ``active``). Every filter here is a STRING compare —
  ``{% if request.GET.status == value %}selected{% endif %}`` — so ``|stringformat:"d"`` appears
  nowhere on this page and ``|slugify`` is wrong everywhere.
* ``scm/integration/integrationendpoint/detail.html`` — ``obj``, ``recent_messages``,
  ``message_stats``, ``is_tenant_admin``. See :func:`integrationendpoint_detail`.
* ``scm/integration/integrationendpoint/form.html`` — ``form`` + ``is_edit`` (+ ``obj`` on the EDIT
  path only, from ``crud_edit``; ``crud_create`` passes no ``obj``, so every ``{{ obj.* }}`` must sit
  inside ``{% if is_edit %}`` or it renders a blank fragment).

Badge classes: only the colour-named ones exist in ``static/css/theme.css`` — ``badge-green`` /
``badge-red`` / ``badge-amber`` / ``badge-info`` / ``badge-muted`` / ``badge-slate``.
``badge-success`` / ``badge-warning`` / ``badge-danger`` DO NOT EXIST and render as completely
unstyled text (L33, already shipped four times).
"""
from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._helpers import _is_tenant_admin, _need_tenant

from apps.scm.forms import IntegrationEndpointForm
from apps.scm.models import IntegrationEndpoint, IntegrationMessage
# BY NAME rather than reading the vocabularies back off `_meta.get_field(...).choices` — that is what
# keeps "the filter offers exactly what the column accepts" a fact rather than a coincidence.
from apps.scm.models.IntegrationApiGateway._choices import (
    ENDPOINT_CATEGORY_CHOICES,
    ENDPOINT_DIRECTION_CHOICES,
    ENDPOINT_STATUS_CHOICES,
    ENDPOINT_SYSTEM_CHOICES,
    ENVIRONMENT_CHOICES,
    LIFECYCLE_STAGE_CHOICES,
    TRANSPORT_CHOICES,
)

#: How many exchange-log rows the detail page's panel shows. A queryset SLICE, so the DATABASE
#: applies it — it bounds what is FETCHED, not merely what is rendered (L40 §1: a guard that first
#: builds the whole thing is the payload, not a guard). ``IntegrationMessage`` accumulates one row per
#: exchange forever, so an unbounded panel is a page that gets slower every week it is left alone.
RECENT_MESSAGE_ROWS = 10


def _detail(pk):
    """The one redirect target every refusal in this module answers with."""
    return redirect("scm:integrationendpoint_detail", pk=pk)


# ======================================================================================= the list
@login_required
def integrationendpoint_list(request, category=None):
    """The connection register — the ONE view behind all five list routes.

    ``category`` does NOT come from the query string. It arrives from Django's extra-options dict on
    the four category routes (``{"category": "erp"}`` and friends), so it is code-controlled and can
    only ever be one of the four literals; the plain ``integration-endpoints/`` route passes nothing
    and ``active_category`` is then ``""``.

    The pinned category is applied to the queryset BEFORE ``crud_list`` paginates. A filter applied
    afterwards would page over the unfiltered set and quietly show the wrong rows on page 2 — which
    on a category route would mean EDI partners appearing on the IoT page.

    All seven GET filters are plain string columns, so none needs the ``is_int`` L11 guard and a
    hand-edited junk value narrows to nothing rather than raising (``crud_list`` hands the string
    straight to a ``CharField`` lookup and still catches ``ValueError``/``ValidationError`` out of
    ``.filter()``). On a category route the template renders the category ``<select>`` pre-selected
    and locked, so a conflicting ``?category=`` is only reachable by hand-editing the URL; it then
    narrows to nothing — a 200 with an empty list, never a 500.

    ``stats`` is counted over the ROUTE's whole queryset — the tenant's connections, scoped by the
    pinned category and by nothing else. Never over the searched/filtered page: "2 connections in
    error" is a fact somebody has to act on, and recomputing it per filter would make the number
    change as you browse. Scoping it to the pinned category is the honest reading of the same rule:
    on the EDI page, "12 total" must mean 12 EDI connections, and on the unpinned route this IS the
    whole tenant queryset.

    ``select_related`` covers every FK a row reads INCLUDING the chained hop:
    ``LogisticsClient.__str__`` is ``f"{code} · {party}"``, so rendering ``obj.logistics_client``
    walks ``party`` and without ``logistics_client__party`` that is one extra query per row.

    ``.defer("notes")`` drops the one ``TextField`` no list column renders — only the detail page and
    the form read it. ``defer`` touches the SELECT list ONLY, so every filter above is unaffected.
    """
    active_category = category or ""

    base = IntegrationEndpoint.objects.filter(tenant=request.tenant)
    if active_category:
        base = base.filter(category=active_category)

    queryset = (base
                .select_related("partner_party", "logistics_client", "logistics_client__party",
                                "location")
                .defer("notes")
                # STATED, not inherited. It is Meta.ordering, which is already a total order
                # (`name` + `id`), so page 2 is deterministic rather than depending on row order.
                .order_by("name", "id"))

    stats = base.aggregate(
        total=Count("id"),
        connected=Count("id", filter=Q(status="connected")),
        error=Count("id", filter=Q(status="error")),
        disabled=Count("id", filter=Q(status="disabled")),
        active=Count("id", filter=Q(is_active=True)),
    )

    return crud_list(
        request, queryset, "scm/integration/integrationendpoint/list.html",
        # `notes` is deliberately NOT searched: the box on this page is for finding a connection, and
        # matching an internal note would return a row whose visible columns contain nothing the user
        # typed, which reads as a bug.
        search_fields=["name", "number", "external_account_ref", "interchange_id",
                       "device_identifier"],
        filters=[("category", "category", False),
                 ("system", "system", False),
                 ("direction", "direction", False),
                 ("transport", "transport", False),
                 ("status", "status", False),
                 ("environment", "environment", False),
                 ("lifecycle_stage", "lifecycle_stage", False)],
        extra_context={
            "category_choices": ENDPOINT_CATEGORY_CHOICES,
            "system_choices": ENDPOINT_SYSTEM_CHOICES,
            "direction_choices": ENDPOINT_DIRECTION_CHOICES,
            "transport_choices": TRANSPORT_CHOICES,
            "status_choices": ENDPOINT_STATUS_CHOICES,
            "environment_choices": ENVIRONMENT_CHOICES,
            # The key is `lifecycle_choices` while the GET param is `lifecycle_stage`. Pinned, not a
            # typo — renaming either half silently blanks the widget or drops the filter (L7).
            "lifecycle_choices": LIFECYCLE_STAGE_CHOICES,
            "active_category": active_category,
            "stats": stats,
        },
    )


# ======================================================================================= the CRUD
@login_required
def integrationendpoint_create(request):
    """Register one connection. The row IS its configuration — there is no lifecycle verb.

    ``crud_create`` stamps the tenant, audits and refuses a tenant-less user; ``_need_tenant`` is
    still called FIRST so the refusal lands back on this module's list rather than on the dashboard.

    No credential is entered here. ``credential_prefix``/``credential_hash`` are ``editable=False``,
    so they are structurally unreachable from any ModelForm (L20/L22) —
    :func:`integrationendpoint_rotate_credential` is their only writer, and it runs after the row
    exists.

    Success returns to the LIST rather than the new detail page, matching every other scm create.
    """
    if _need_tenant(request):
        return redirect("scm:integrationendpoint_list")
    return crud_create(request, form_class=IntegrationEndpointForm,
                       template="scm/integration/integrationendpoint/form.html",
                       success_url="scm:integrationendpoint_list")


@login_required
def integrationendpoint_detail(request, pk):
    """One connection, its credential marker and the tail of its exchange log.

    Context keys, exhaustively (the templates are written by a separate agent):

    * ``obj`` — the :class:`~apps.scm.models.IntegrationEndpoint`, with ``partner_party``,
      ``logistics_client``, ``location`` and ``spec_document`` joined. The page renders
      ``obj.masked`` (or the literal "Not set") and ``obj.effective_interchange_id`` /
      ``obj.effective_interchange_qualifier`` — **never** ``obj.interchange_id`` /
      ``obj.interchange_qualifier`` (those are blank whenever a 3PL client is linked, by constraint
      A) and **never** ``obj.credential_hash`` or ``obj.credential_prefix`` directly: a digest on a
      page is a digest in a screenshot, and it is offline-attackable against a weak secret.
    * ``recent_messages`` — the last :data:`RECENT_MESSAGE_ROWS` ``IntegrationMessage`` rows for this
      connection, newest ``occurred_at`` first, with ``purchase_order`` and ``sales_order`` joined.
    * ``message_stats`` — a dict with exactly ``total`` / ``pending`` / ``sent`` / ``received`` /
      ``acknowledged`` / ``failed`` / ``ignored``, all ints. DERIVED by one aggregate on read and
      never stored (L29).
    * ``is_tenant_admin`` — bool, gates the rotate-credential and delete buttons. Both routes behind
      them are ``@tenant_admin_required``, so this only decides whether a member is shown a button
      that would refuse them; hiding it is courtesy, the decorator is the boundary.

    Both panels are keyed on ``endpoint_id=pk`` **plus** ``tenant=request.tenant`` rather than on the
    fetched object, which lets them run alongside ``crud_detail``'s own fetch instead of forcing a
    second one. The tenant term is what makes that safe: a pk from another workspace matches no
    message rows here AND 404s in ``crud_detail``, so nothing leaks either way.

    QUERIES: one for the connection, one for the panel, one for the aggregate. Flat — not one per row.
    """
    messages_qs = IntegrationMessage.objects.filter(tenant=request.tenant, endpoint_id=pk)

    recent_messages = list(
        messages_qs.select_related("purchase_order", "sales_order")
        .order_by("-occurred_at", "-id")[:RECENT_MESSAGE_ROWS])

    message_stats = messages_qs.aggregate(
        total=Count("id"),
        pending=Count("id", filter=Q(status="pending")),
        sent=Count("id", filter=Q(status="sent")),
        received=Count("id", filter=Q(status="received")),
        acknowledged=Count("id", filter=Q(status="acknowledged")),
        failed=Count("id", filter=Q(status="failed")),
        ignored=Count("id", filter=Q(status="ignored")),
    )

    return crud_detail(
        request, model=IntegrationEndpoint, pk=pk,
        template="scm/integration/integrationendpoint/detail.html",
        select_related=("partner_party", "logistics_client", "logistics_client__party", "location",
                        "spec_document"),
        extra_context={
            "recent_messages": recent_messages,
            "message_stats": message_stats,
            "is_tenant_admin": _is_tenant_admin(request.user),
        },
    )


@login_required
def integrationendpoint_edit(request, pk):
    """Change a connection's configuration. Every field on the form is editable, always.

    There is no status ladder and no frozen state here: the row is configuration rather than a
    document, so there is no history for an edit to rewrite — and an edit CANNOT rewrite the exchange
    log, because ``IntegrationMessage`` is append-only and snapshots what actually crossed the
    boundary.

    The columns an edit genuinely cannot reach are the two credential columns and the four
    system-maintained ones (``consecutive_failures``, ``last_run_at``, ``last_success_at``,
    ``last_seen_at``). All six are ``editable=False``, which keeps them off the form automatically
    rather than relying on the field list staying correct (L20/L22).

    Success returns to the LIST: ``crud_edit`` issues a plain ``redirect(success_url)`` with no
    kwargs, so a detail route (which needs ``pk``) is not a valid target for it.
    """
    return crud_edit(request, model=IntegrationEndpoint, pk=pk,
                     form_class=IntegrationEndpointForm,
                     template="scm/integration/integrationendpoint/form.html",
                     success_url="scm:integrationendpoint_list")


@login_required
@tenant_admin_required
@require_POST
def integrationendpoint_delete(request, pk):
    """Delete a connection **and its entire exchange log with it**. Admin-only, POST-only.

    ``IntegrationMessage.endpoint`` is the sub-module's one ``CASCADE``: a log line has no life
    without the connection it crossed, so deleting the endpoint destroys every message recorded
    against it — the evidence of what was exchanged with that partner, which nothing reconstructs.
    That is why this verb is ``@tenant_admin_required`` while ``integrationmessage_reprocess`` is
    not: deleting a trading-partner link is an administrative act, not day-to-day operations.

    ``@require_POST`` means a GET is a 405 rather than a silent deletion, and ``crud_delete`` is
    self-defending on top of that (it only mutates on POST even if a decorator is ever dropped).

    The message count is taken BEFORE the delete, while the rows still exist to be counted, and
    reported afterwards as an ``info`` line — ``crud_delete`` already flashed the green bar, and two
    success banners for one action is the 4.13 double-message finding. The info line is the one with
    something the green bar cannot express: what ELSE just went.

    Status guards live in views, not only in templates — hiding a button does not stop a direct POST.
    Here the guard IS the decorator, and the template's ``is_tenant_admin`` check merely avoids
    showing a member a button that would 403 them.
    """
    obj = get_object_or_404(IntegrationEndpoint, pk=pk, tenant=request.tenant)
    message_count = IntegrationMessage.objects.filter(
        tenant=request.tenant, endpoint_id=pk).count()
    label = str(obj)

    with transaction.atomic():
        response = crud_delete(request, model=IntegrationEndpoint, pk=pk,
                               success_url="scm:integrationendpoint_list")

    if message_count:
        messages.info(
            request,
            f"Removed with {label}: {message_count} exchange log row(s). That record of what "
            "crossed the boundary with this partner cannot be reconstructed.")
    return response


# ================================================================================ the one action
@login_required
@tenant_admin_required
@require_POST
def integrationendpoint_rotate_credential(request, pk):
    """Mint a new credential, store only a marker for it, and show the plaintext ONCE.

    **This performs no network call of any kind.** There is no provider to tell, because 4.19 ships
    no transport — rotating here records that a NEW credential is the one in force and hands the
    operator the value to paste into the partner's console themselves.

    What is stored is a 12-char prefix and a SHA-256 digest, and the module docstring on
    ``IntegrationEndpoint`` explains at length why that is right HERE and wrong in general (a key you
    must USE needs encryption at rest, not hashing; hashing is correct only because nothing signs and
    nothing dials). The plaintext exists in this function's local scope and in exactly one flash
    message, then it is gone: **there is no reveal view and there must not be one.**

    ``write_audit_log`` records that a rotation happened and NEVER the value — ``crud.py``'s
    ``_SENSITIVE_AUDIT_FIELDS`` redaction protects the ``crud_*`` paths, but this is a hand-rolled
    save that bypasses them, so the redaction is done here by simply never putting the secret in the
    payload. An audit trail is immutable and would outlive any later encryption-at-rest migration.

    ``save(update_fields=…)`` is narrow on purpose — a full ``save()`` would write back every
    in-memory column, including any a concurrent edit had just changed. ``updated_at`` is
    ``auto_now``, so it only fires when it is IN the list.

    The save and its audit row share one ``transaction.atomic()``: a failure between them would
    otherwise leave a rotated credential nobody can attribute, which on a credential change is
    precisely the record that has to exist.
    """
    obj = get_object_or_404(IntegrationEndpoint, pk=pk, tenant=request.tenant)

    plaintext = IntegrationEndpoint.generate_credential()
    obj.set_credential(plaintext)

    with transaction.atomic():
        obj.save(update_fields=["credential_prefix", "credential_hash", "updated_at"])
        write_audit_log(request.user, obj, "update", changes={"credential": "rotated"})

    messages.success(
        request,
        f"New credential for {obj.number}: {plaintext} — copy it now. It is shown once and is not "
        "stored; only a prefix and a one-way digest are kept, so it cannot be recovered from here.")
    return _detail(pk)
