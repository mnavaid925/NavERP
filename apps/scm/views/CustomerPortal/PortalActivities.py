"""SCM 4.16 Customer Portal — ``PortalActivity``: the append-only evidence trail, LIST + DETAIL.

**THE ABSENT CREATE, EDIT AND DELETE VIEWS ARE A DECISION, NOT AN OMISSION.** This module ships no
``portalactivity_create``, no ``_edit`` and no ``_delete``; there is no form module for the model,
no route for any of them, and the list template carries **no Actions column at all**. A reviewer
should not "complete" this CRUD. The reasons, each of which is enough on its own:

* **The model is append-only.** ``PortalActivity.record()`` is the single writer and it is called
  only from the gated customer surface — a row is written once and never touched again. That is not
  tidiness, it is the entire value of the table: evidence that can be revised after the dispute
  starts is not evidence, and *"we published that POD on the 3rd and you downloaded it on the 4th"*
  is the sentence this table exists to make defensible.
* **Every field the model declares is ``editable=False``** (``PortalActivities.py:60-104``), so
  there is nothing for a ``ModelForm`` to render. A create/edit page here would be an empty form.
* **A staff-written row would corrupt the one number the table supports.** The log's denominator is
  "how much did the customer actually serve themselves"; a hand-typed activity is a self-service
  figure somebody typed.
* **Precedent, already shipped:** ``StockMoveAdmin`` and ``MeterReadingAdmin`` in ``apps/scm/
  admin.py`` refuse add/change/delete for exactly this reason, 4.3's ``stock_ledger`` and 4.13's
  ``meterreading_list`` are read-only pages of the same shape, and 4.15's ``TemperatureReading``
  ships list + detail + a filing path with no edit and no delete.

A wrong activity row is not corrected — it is *what happened*. The staff-side mutation trail is
``core.AuditLog``, written by ``write_audit_log`` from the ``crud_*`` helpers, and it stays exactly
where it is: its ``ACTION_CHOICES`` are ``create``/``update``/``delete`` only and cannot express a
customer READ, which is why 4.16 keeps this table at all.

--------------------------------------------------------------------------------------------------
THE PAGE IS ALWAYS WINDOWED — AND WHERE THE UNWINDOWED QUESTION IS ANSWERED
--------------------------------------------------------------------------------------------------
This is the fastest-growing table in the sub-module (every order view, every tracking check and
every document download by every portal user writes one row), so :func:`portalactivity_list` always
applies a date window and says so on the page. Narrowing to one account does **not** exempt it: an
account filter narrows the rows but does not bound them, which was the 4.15 reading-log finding.

The one question a window would answer wrongly — *"has this customer EVER logged in?"* — is
deliberately not asked here. ``PortalAccount.has_never_logged_in`` answers it unwindowed with a
single ``EXISTS``, and the enablement console on ``portalaccount/list.html`` is where it is read.

The window is resolved by the SHARED ``_report_window`` in ``apps/scm/views/_helpers.py`` — the one
implementation every dated page in ``scm`` goes through. A fourth private copy of a date parser is
how two of them ended up with incompatible signatures under the same name.

--------------------------------------------------------------------------------------------------
Context-var contract (pinned, L7 — the templates are written by a separate agent, so EVERY key each
page consumes is listed here, not merely the list variable):
--------------------------------------------------------------------------------------------------
* ``scm/portal/portalactivity/list.html`` — ``object_list`` + ``page_obj`` + ``q`` (from
  ``crud_list``), plus ``action_choices`` (list of ``(value, label)`` pairs), ``action`` (the
  RESOLVED token — bind the ``<select>`` to THIS, never to ``request.GET.action``),
  ``portal_accounts`` (queryset for the pk dropdown — compare with ``|stringformat:"d"``, **never**
  ``|slugify``), ``window`` (dict), ``window_days`` (int), ``window_defaulted`` (bool) and
  ``append_only_note`` (str). Filter inputs are named ``q`` / ``action`` / ``portal_account`` /
  ``date_from`` / ``date_to``. **No Add button, no Edit, no Delete, no Actions column** — render the
  row and a View link, and print ``append_only_note`` so the absence reads as the decision it is.
* ``scm/portal/portalactivity/detail.html`` — ``obj``, ``targets``, ``target_note``,
  ``previous_activity``, ``next_activity``, ``is_latest`` and ``append_only_note``. **Actions
  sidebar: Back to List only** — no Edit button, no Delete form.

Badge colour comes from the model's own ``action_css`` property (``_choices.PORTAL_ACTION_CSS``), so
the list badge and the detail badge cannot drift apart. Only the six classes that exist in
``theme.css`` may appear — ``badge-green / badge-red / badge-amber / badge-info / badge-muted /
badge-slate``. ``badge-success`` / ``badge-danger`` / ``badge-warning`` DO NOT EXIST in this project
and render as completely unstyled text (L33).

**Every derived figure renders ``None`` as an em dash, never as ``0`` and never as blank** —
``ip_address`` (not captured), ``user`` (a token visitor has no login, which is a real recordable
event rather than a gap) and both neighbours on the detail page.
"""
from datetime import datetime, time, timedelta

from apps.scm.views._common import *  # noqa: F401,F403
# The SHARED window resolver — see the module docstring. It applies L11 to the two date boxes for
# free: `?date_from=lastweek`, `?date_from=2026-02-30` and a value outside the analytics bounds all
# fall back to the default rather than raising on a URL anybody can type into the address bar.
from apps.scm.views._helpers import _report_window

from apps.scm.models import PORTAL_ACTION_CHOICES, PortalAccount, PortalActivity


#: 30 rather than the app-wide 15 — the ``stock_ledger`` / ``meterreading_list`` /
#: ``temperaturereading_list`` precedent: this is a high-volume append-only trail people SCAN for a
#: sequence ("logged in, opened the order, downloaded the POD"), not a register they page through
#: one record at a time.
ACTIVITY_PER_PAGE = 30

#: The default window when the page is opened with neither date. A month is long enough to cover
#: "what did this customer do about that delivery" and short enough that the first page is not an
#: OFFSET walk of a year of reads. ``window_defaulted`` tells the page to SAY it defaulted — a
#: silent default is indistinguishable from a page that ignored what was asked.
DEFAULT_WINDOW_DAYS = 30

#: The valid ``?action=`` tokens, derived from the vocabulary the column is declared with rather
#: than restated — the filter offering exactly what the column accepts stays a fact instead of a
#: coincidence that survives until somebody adds a ninth action.
_ACTION_VALUES = {value for value, _label in PORTAL_ACTION_CHOICES}

#: Presentation for the model's own ``TARGET_FIELDS`` — ``field -> (label, url name)``. **Which
#: pointers exist is the MODEL's business** (:attr:`PortalActivity.TARGET_FIELDS`); this dict only
#: says how each one is printed and where it links. :func:`_targets` walks the model's tuple and
#: falls back to a humanised label with NO url for anything missing here, so a fourth pointer added
#: to the model later still appears on the page — unlinked — instead of silently vanishing from it.
TARGET_PRESENTATION = {
    "sales_order": ("Sales order", "scm:salesorder_detail"),
    "shipment": ("Shipment", "scm:shipment_detail"),
    "document_share": ("Document share", "scm:portaldocumentshare_detail"),
}

#: ``action -> the pointer column that action NATURALLY carries``, and nothing else. Read only by
#: :func:`_target_note`, to tell the two silences apart: an action that never had a pointer
#: (``login`` describes a session, ``view_catalog`` a whole page) versus one that should have had
#: one and now shows none — every pointer is ``SET_NULL``, so a target that was deleted leaves
#: exactly this trace. The two deserve different sentences; conflating them is how a reader decides
#: the log is unreliable.
#:
#: ``raise_inquiry`` and ``request_return`` are deliberately ABSENT: both do produce a record, but
#: in tables ``PortalActivity`` has no pointer column for (``TARGET_FIELDS`` is three), so their
#: reference lives in the denormalised ``object_label`` and a missing pointer is not evidence of
#: anything having been deleted.
NATURAL_TARGETS = {
    "view_order": "sales_order",
    "track_shipment": "shipment",
    "download_document": "document_share",
}

#: Printed as a banner on BOTH pages. One constant rather than two hand-typed paragraphs, so the
#: list and the detail cannot end up explaining the table differently.
PORTAL_LOG_NOTE = (
    "This log is append-only: a row is written once by the customer portal and is never edited or "
    "deleted — there is no Add, Edit or Delete here, on purpose. It records what a CUSTOMER READ, "
    "which core.AuditLog deliberately cannot express (its vocabulary is create / update / delete, "
    "and a read is not a mutation dressed differently). Staff changes to portal records still go "
    "to the audit log exactly as before; the two tables answer two questions and neither replaces "
    "the other."
)


# ==================================================================================== small helpers
def _aware_bounds(date_from, date_to):
    """A date pair as the inclusive AWARE datetime range covering both days end to end.

    ``created_at`` is a ``DateTimeField`` while the two filter boxes post plain dates, so somebody
    has to widen one into the other. A bare ``2026-08-04`` on the UPPER bound resolves to MIDNIGHT
    and would silently drop every activity recorded during the day somebody asked for — on a page
    whose whole job is "what did this customer do on the 4th", that is the answer being wrong.

    An explicit aware range rather than ``created_at__date__gte``: ``__date`` compiles to
    ``CONVERT_TZ`` on MariaDB and returns NULL when the timezone tables are not loaded, which on
    XAMPP they are not (the 4.12 carbon-report finding). It also cannot use
    ``scm_pact_tnt_acct_at_idx`` — a function of a column is not a range on it — and on the
    fastest-growing table in the sub-module that is the difference between an index range scan and a
    walk.

    Module-local, matching the five existing copies (``AssetManagement/Reports.py:397``,
    ``ColdChainManagement/{Reports,ColdChainMonitors,TemperatureReadings,TemperatureExcursions}``).
    It belongs in ``views/_helpers.py`` next to ``_report_window``; promoting it means editing a
    file three concurrent sessions share, so it is flagged for the orchestrator rather than done
    here.
    """
    start = datetime.combine(date_from, time.min)
    end = datetime.combine(date_to, time.max)
    if timezone.is_naive(start):
        start = timezone.make_aware(start)
        end = timezone.make_aware(end)
    return start, end


def _resolved_action(raw):
    """A ``?action=`` value that is really one of ours, or ``""``.

    Validated here rather than handed to ``crud_list``'s equality leg because the two failure modes
    are not the same. An unknown pk (``?portal_account=999``) plausibly means "a row that is not
    yours", and an empty page is the honest answer. An unknown ACTION cannot mean anything — the
    vocabulary is closed and known in-process — so filtering on it would render an empty page while
    the ``<select>`` showed "All", i.e. the page silently disagreeing with its own filter bar. It
    narrows NOTHING instead, and the resolved value is echoed back for the select to bind to (the
    ``laborstandard_list`` / ``temperaturereading_list`` posture, L11's rule applied to a string).
    """
    raw = (raw or "").strip()
    return raw if raw in _ACTION_VALUES else ""


def _target_reference(target):
    """A short staff-side reference for a pointed-at row — its number, else its title/name.

    ``number`` first because all three targets are ``TenantNumbered`` and the number is what
    somebody quotes back ("SO-00012", "PDS-00004"). Reading the attribute rather than ``str()``
    also keeps this query-free: ``SalesOrder.__str__`` walks ``customer``, and printing a reference
    must not cost a join per row.
    """
    for attr in ("number", "title", "name"):
        value = getattr(target, attr, "")
        if value:
            return str(value)
    return str(target)


def _targets(activity):
    """The pointers this row actually carries, as a list of dicts — possibly empty.

    Walks :attr:`PortalActivity.TARGET_FIELDS` (the MODEL's tuple) so the set of pointers has one
    definition, and reads ``<field>_id`` first so a ``None`` pointer costs no query at all.

    Each dict: ``field`` (the column name), ``label`` (human), ``obj`` (the instance),
    ``reference`` (a short string) and ``url_name`` (a named route, or ``""`` — render an
    unlinked reference when it is blank rather than dropping the row).
    """
    rows = []
    for field in PortalActivity.TARGET_FIELDS:
        if getattr(activity, f"{field}_id", None) is None:
            continue
        target = getattr(activity, field, None)
        if target is None:
            # The pointer id is set but the row is gone — only reachable on a torn read, and it
            # takes the same answer as a NULL pointer rather than an AttributeError in a template.
            continue
        label, url_name = TARGET_PRESENTATION.get(
            field, (field.replace("_", " ").capitalize(), ""))
        rows.append({
            "field": field,
            "label": label,
            "obj": target,
            "reference": _target_reference(target),
            "url_name": url_name,
        })
    return rows


def _target_note(activity, targets):
    """Why this row points at nothing — or ``""`` when it points at something.

    Two silences, two sentences: see :data:`NATURAL_TARGETS`. Neither claims more than we know — a
    pointer that is NULL today cannot be distinguished from one that was never set, because
    ``SET_NULL`` leaves no trace, and the note says exactly that instead of asserting a deletion.
    """
    if targets:
        return ""
    label = activity.get_action_display().lower()
    if activity.action in NATURAL_TARGETS:
        return (
            f"This row records “{label}” but carries no pointer. Either none was recorded, "
            "or the record it pointed at has since been deleted — every pointer on this table is "
            "SET_NULL, so an activity row outlives the thing it is about and leaves no trace of "
            "which of the two happened. The recorded label is what remains, which is precisely why "
            "it is stored on the row rather than looked up.")
    return (
        f"This action points at no record by design: “{label}” describes a session or a "
        "whole page rather than one row, and anything it did produce (an inquiry, a return "
        "request) lives in a table this log has no pointer column for. The label is the reference.")


# ========================================================================================= the list
@login_required
def portalactivity_list(request):
    """The customer-activity trail — always windowed, always paginated, never editable.

    **Filter GET params** (all applied BEFORE ``crud_list`` paginates; a filter applied afterwards
    would page over the unfiltered set and quietly show the wrong rows on page 2):

    * ``q`` — free text over ``object_label``, the account's ``number`` and the customer's ``name``.
      ``ip_address`` is deliberately NOT searched: it is a ``GenericIPAddressField``, which is a
      ``varchar`` on this stack (MySQL) but an ``inet`` on PostgreSQL, where ``icontains`` is a
      database error rather than a narrow result. An evidence trail must not carry a filter that
      works only on the developer's laptop.
    * ``action`` — one of ``PORTAL_ACTION_CHOICES``, resolved through :func:`_resolved_action` so a
      junk value narrows nothing and the ``<select>`` shows "All".
    * ``portal_account`` — a pk, through ``crud_list``'s ``is_int`` leg, which runs ``as_db_int``:
      ``?portal_account=abc``, ``?portal_account=²`` (a Unicode superscript — ``isdigit()`` says
      yes, ``int()`` says no) and ``?portal_account=99999999999999999999`` (converts fine, then
      overflows inside the driver) all SKIP the filter rather than raise (L11).
    * ``date_from`` / ``date_to`` — ``YYYY-MM-DD``, inclusive of both days, on ``created_at``.

    **The page is ALWAYS bounded** — see the module docstring for why, and for where the unwindowed
    "have they ever logged in?" question is answered instead.

    ``select_related`` covers every FK a row renders: ``portal_account`` (whose ``__str__`` is
    ``number · customer``, so ``portal_account__customer`` is needed too — without it a page of
    30 rows is 30 extra queries for one column) and ``user``. L18.

    ``order_by`` is STATED rather than inherited from ``Meta``. It is the same ``-created_at`` plus
    an explicit ``-id`` tie-break, which makes it a TOTAL order: a seeder or a fast client can land
    several rows in the same second, and without the tie-break the row on the boundary of page 1
    can reappear on page 2.
    """
    today = timezone.localdate()
    window = _report_window(request.GET, today - timedelta(days=DEFAULT_WINDOW_DAYS - 1), today)
    start, end = _aware_bounds(window["date_from"], window["date_to"])

    queryset = (PortalActivity.objects
                .filter(tenant=request.tenant,
                        created_at__gte=start, created_at__lte=end)
                .select_related("portal_account", "portal_account__customer", "user")
                .order_by("-created_at", "-id"))

    action = _resolved_action(request.GET.get("action"))
    if action:
        queryset = queryset.filter(action=action)

    return crud_list(
        request, queryset, "scm/portal/portalactivity/list.html",
        search_fields=["object_label", "portal_account__number", "portal_account__customer__name"],
        # `is_int=True` -> the L11 guard above. `action` is pre-applied, so it is NOT repeated here.
        filters=[("portal_account", "portal_account_id", True)],
        extra_context={
            "action_choices": PORTAL_ACTION_CHOICES,
            # The RESOLVED token, not request.GET — a junk `?action=browsed` narrowed nothing, so
            # the select must show "All" rather than an option that did not happen.
            "action": action,
            # `select_related("customer")` because PortalAccount.__str__ walks it, and every option
            # in the dropdown prints one (L18 — a dropdown is a page of rows too). Ordered by the
            # customer name rather than Meta's `-created_at`: a person picking from a list looks for
            # a company, not for whichever account was configured most recently.
            "portal_accounts": (PortalAccount.objects.filter(tenant=request.tenant)
                                .select_related("customer")
                                .order_by("customer__name", "number")),
            # ONE dict rather than six loose keys: `date_from` as a resolved date and `date_from` as
            # the raw string a user typed are different things, and two context keys one letter
            # apart is how a template ends up echoing the wrong one back into its own input.
            "window": window,
            "window_days": DEFAULT_WINDOW_DAYS,
            # Neither end was supplied, so the page is showing its own default window and must say
            # so. A window that appeared without being asked for reads as "there is nothing older".
            "window_defaulted": not (window["date_from_raw"] or window["date_to_raw"]),
            "append_only_note": PORTAL_LOG_NOTE,
        },
        per_page=ACTIVITY_PER_PAGE,
    )


# ======================================================================================= the detail
@login_required
def portalactivity_detail(request, pk):
    """One recorded action, what it pointed at, and where it sits in that account's trail.

    Scoped on ``tenant`` **and** ``portal_account__tenant``. The two cannot disagree today —
    ``record()`` takes the tenant from the account itself — but a child fetched by its own pk alone
    is exactly the lookup that stops being safe the day somebody adds a second write path, and
    stating both costs nothing.

    Context, exhaustively:

    * ``obj`` — the :class:`~apps.scm.models.PortalActivity`, with ``portal_account`` (and its
      customer), ``user`` and all three pointers joined. Badge colour is ``obj.action_css``;
      ``obj.ip_address`` and ``obj.user`` are ``None`` for a token visitor and MUST render as an em
      dash, never as blank and never as "unknown user" — an unauthenticated download IS a real,
      recordable event (see the ``user`` field comment on the model).
    * ``targets`` — a LIST of dicts, one per pointer this row actually carries, **possibly empty**:
      ``field`` (str — ``sales_order`` / ``shipment`` / ``document_share``), ``label`` (str),
      ``obj`` (the instance), ``reference`` (str — its number) and ``url_name`` (str — a named
      route, or ``""``: render the reference unlinked when it is blank).
    * ``target_note`` — str, ``""`` when ``targets`` is non-empty. Print it INSTEAD of an empty
      table: it says which of the two silences this is (an action that never had a pointer, or one
      whose target has gone), which is the whole reason ``object_label`` is denormalised.
    * ``previous_activity`` / ``next_activity`` — the neighbouring rows for the SAME account, or
      ``None`` at either end of the trail. This is what turns a single row into a sequence: "signed
      in, opened SO-00012, downloaded the POD" is the reading that answers a dispute, and it is one
      indexed probe in each direction on ``scm_pact_tnt_acct_at_idx``.
    * ``is_latest`` — bool; ``True`` when nothing newer exists for this account.
    * ``append_only_note`` — str.

    **Actions sidebar: Back to List only.** No Edit button and no Delete form — there are no such
    routes, and offering a button the app will 404 on is the 4.11 finding.

    The explicit ``tenant=request.tenant`` on the two neighbour probes narrows nothing (the rows are
    reached through an account that is already this workspace's) and is deliberate: ``tenant_id`` is
    the LEADING column of the composite index, so a query that states only the account opens the
    plain FK index and then filesorts — the ``MeterReading`` lesson, recorded on the model's own
    ``Meta.indexes``.
    """
    obj = get_object_or_404(
        PortalActivity.objects.select_related(
            "portal_account", "portal_account__customer", "user",
            "sales_order", "shipment", "document_share"),
        pk=pk, tenant=request.tenant, portal_account__tenant=request.tenant)

    # The `-created_at, -pk` tie-break mirrors Meta.ordering deliberately: several rows can share a
    # timestamp (a page that records two reads in one second is normal), and "the previous activity"
    # has to be one deterministic row rather than whichever one the database felt like returning.
    siblings = (PortalActivity.objects
                .filter(tenant=request.tenant, portal_account_id=obj.portal_account_id)
                .exclude(pk=obj.pk)
                .select_related("portal_account"))
    older = Q(created_at__lt=obj.created_at) | Q(created_at=obj.created_at, pk__lt=obj.pk)
    newer = Q(created_at__gt=obj.created_at) | Q(created_at=obj.created_at, pk__gt=obj.pk)
    previous_activity = siblings.filter(older).order_by("-created_at", "-pk").first()
    next_activity = siblings.filter(newer).order_by("created_at", "pk").first()

    targets = _targets(obj)

    return render(request, "scm/portal/portalactivity/detail.html", {
        "obj": obj,
        "targets": targets,
        "target_note": _target_note(obj, targets),
        "previous_activity": previous_activity,
        "next_activity": next_activity,
        "is_latest": next_activity is None,
        "append_only_note": PORTAL_LOG_NOTE,
    })


# ==================================================================================================
# NOTHING FOLLOWS, AND THAT IS THE POINT.
#
# There is no `portalactivity_create`, no `_edit` and no `_delete` in this module, no form class in
# `apps/scm/forms/CustomerPortal/`, and no route for any of them in
# `apps/scm/urls/CustomerPortal/PortalActivities.py` — only `portalactivity_list` and
# `portalactivity_detail`. The model is append-only and every field it declares is `editable=False`,
# so there is nothing for a ModelForm to render and nothing a staff member may legitimately restate:
# these rows are the record of what a CUSTOMER did, and a staff-written one would be a self-service
# figure somebody typed. `StockMoveAdmin` and `MeterReadingAdmin` take the same posture in
# `apps/scm/admin.py`, and `admin.py` registers PortalActivity read-only for the same reason.
#
# If a later pass wants to "complete the CRUD" here, the answer is no. If a row is wrong, that is
# what the log says happened; the staff-side mutation trail is `core.AuditLog`.
# ==================================================================================================
