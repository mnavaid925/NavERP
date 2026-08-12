"""SCM 4.16 Customer Portal — ``PortalOrderInquiry`` views: the staff triage queue and its three verbs.

**This is the console for the WISMO queue.** ``PortalOrderInquiry`` wraps ``crm.Case``, so these
pages are deliberately thin over two owners: CRM owns the case lifecycle (status, priority, owner,
the thread, the SLA clocks, CSAT) and SCM owns the supply-chain context and the outcome. **Nothing
in this module writes ``case.status``, recomputes an SLA, or invents a customer-facing label** — the
first is CRM's queue to manage, the second is read off the case (:attr:`PortalOrderInquiry.sla_state`)
and the third comes from ``CUSTOMER_STATUS_MAP`` through ``obj.customer_status_label`` /
``obj.customer_status_css``.

--------------------------------------------------------------------------------------------------
WHY CREATE IS HAND-ROLLED AND EDIT IS NOT
--------------------------------------------------------------------------------------------------
``crud_create`` does ``form.save(commit=False)`` -> stamp tenant -> ``save()``. That path cannot open
an inquiry, because an inquiry has no meaning without its ``crm.Case`` and the ``case`` FK is NOT
NULL. :meth:`PortalOrderInquiry.open_for` is the **single writer of that case** — it derives
``origin``, the case ``type`` and the account party server-side, resolves the tenant's default
``SlaPolicy``, and rolls the case back if the inquiry fails validation. So the create view calls it
and maps any ``ValidationError`` back onto the form (:func:`_apply_validation_error`). **Do not
hand-build a ``Case`` here** — a second writer is a second set of rules about who a ticket belongs
to, and that one is an authorisation decision.

``source="staff"`` is passed as a literal from this module and ``raised_by`` is ``request.user``.
Both columns are ``editable=False``, so a crafted ``source=portal&raised_by=<pk>`` in the POST body
never reaches ``cleaned_data`` at all — the forcing here is what makes the value TRUE, not merely
what stops the attack. That figure is the denominator of every self-service claim 4.16 makes.

Edit goes through ``crud_edit`` unchanged: by then the case exists, ``PortalOrderInquiryForm``
removes ``subject``/``description`` (they are the case's columns, not this model's), and the six
workflow columns are ``editable=False`` and therefore absent from the form.

--------------------------------------------------------------------------------------------------
THE THREE VERBS, AND WHAT IS LEGAL WHEN
--------------------------------------------------------------------------------------------------
The verbs bypass ``crud_edit``, so **each writes its own audit row** — a verb that changes state
with no trail is exactly the gap ``write_audit_log`` exists to close, and here the state it changes
is the answer a customer was given. Every audit row is written INSIDE the lock, so a failure between
the commit and the log cannot leave a resolved inquiry with nobody's name on it::

    resolve       open -> <a RESOLVABLE_OUTCOMES value>   (refuses a second resolution: no-op)
    reopen        resolved -> open                        (no-op when already open)
    raise return  any state, given a linkable RMA         (re-linking the SAME rma is a no-op)

``rma_raised`` is deliberately NOT in ``RESOLVABLE_OUTCOMES``: it is a claim about a DOCUMENT, and
only :meth:`~PortalOrderInquiry.link_return` — which has the return in its hand — may set it.
:func:`portalorderinquiry_detail` hands the template ``can_resolve`` / ``can_reopen`` /
``can_raise_return`` read from the *same* conditions the verbs enforce, so a button and the route
behind it cannot disagree about whether a move is available (the 4.11 finding).

The row is taken ``FOR UPDATE`` inside ``transaction.atomic()`` before any verb runs: two POSTs (a
double-click, a retry, a replay) would otherwise both read ``outcome="open"`` and each stamp
``resolved_at``, and the second stamp is the one that survives.

--------------------------------------------------------------------------------------------------
THE DERIVED ``sla`` BUCKET — ONE RULE, TWO DIALECTS, WIRED SO THEY CANNOT DRIFT
--------------------------------------------------------------------------------------------------
``breached`` / ``due_soon`` / ``ok`` / ``none`` is not a column and must never become one: it is a
question about two deadlines and the clock, so a stored flag would need something running every
night to stay true (4.14's ``effective`` filter, 4.13's ``warranty`` filter — same reasoning).

:func:`_sla_buckets` is the SQL dialect of :attr:`PortalOrderInquiry.sla_state`. The list page's
badge is **annotated from those very Q objects** (:func:`_sla_annotations`) rather than read from the
Python property, which makes "the row the filter put in a bucket renders that bucket's chip" a
structural fact instead of a discipline. The labels and colours both come from one place —
:data:`SLA_LABELS` here and ``PortalOrderInquiry.SLA_STATE_CSS`` on the model — so the list chip and
the detail chip cannot be styled differently.

Every predicate in :func:`_sla_buckets` is written POSITIVELY (no ``~Q``) on purpose. The columns are
nullable, negation over a nullable column is three-valued, and "NOT (due < now)" quietly drops every
row where ``due`` is NULL — which is precisely the ``none`` bucket. Spelling the complements out is
longer and is the only version that partitions the table.

--------------------------------------------------------------------------------------------------
Context-var contract (pinned, L7 — the templates are written by a separate agent, so EVERY key each
page consumes is listed here, not merely the list variable):
--------------------------------------------------------------------------------------------------
* ``scm/portal/portalorderinquiry/list.html`` — ``object_list`` + ``page_obj`` + ``q`` (from
  ``crud_list``). Each row in ``object_list`` carries the annotations ``sla_label`` and ``sla_css``
  (**read those, never recompute a bucket in the template**) alongside the model's own
  ``inquiry_type_css`` / ``outcome_css`` / ``customer_status_label`` / ``customer_status_css`` /
  ``age_days``. Filter context: ``inquiry_type_choices`` / ``outcome_choices`` /
  ``requested_resolution_choices`` / ``source_choices`` / ``sla_choices`` (all lists of
  ``(value, label)`` pairs), ``portal_accounts`` and ``sales_orders`` (querysets for the two pk
  dropdowns — compare with ``|stringformat:"d"``, NEVER ``|slugify``), and ``sla`` (the RESOLVED
  bucket, ``""`` when the param is absent or junk — bind the select to THIS, not to
  ``request.GET.sla``). Header chips: ``stats``, a dict with keys ``open`` / ``breached`` /
  ``due_soon`` / ``from_portal``, counted over the WHOLE workspace so the figure does not move as you
  filter. Filter params: ``q`` / ``inquiry_type`` / ``outcome`` / ``requested_resolution`` /
  ``source`` (strings — compare with ``request.GET.<param>`` directly), ``sales_order`` /
  ``portal_account`` (pks) and ``sla``.
* ``scm/portal/portalorderinquiry/form.html`` — ``form`` + ``is_edit`` (+ ``obj`` on the edit path,
  from ``crud_edit``), plus ``order_bound_labels`` (a list of the type LABELS that require an order).
* ``scm/portal/portalorderinquiry/detail.html`` — see :func:`portalorderinquiry_detail`'s docstring
  for the full key list; it is long enough to belong beside the code that builds it.

Badge colours come from the model's own ``*_css`` properties and from the ``sla_css`` annotation.
``badge-success`` / ``badge-warning`` / ``badge-danger`` DO NOT EXIST in theme.css and render as
completely unstyled text (L33).

None of the routes here is ``@tenant_admin_required`` — triaging a support ticket is ordinary work,
and gating it would push agents into the Django admin, which has no audit trail worth the name. The
three verbs and delete are ``@require_POST``, so every button is a ``<form method="post">`` with
``{% csrf_token %}``.
"""
from datetime import timedelta

from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._helpers import _need_tenant

from apps.scm.forms import PortalOrderInquiryForm
from apps.scm.models import (INQUIRY_OUTCOME_CHOICES, INQUIRY_SOURCE_CHOICES, INQUIRY_TYPE_CHOICES,
                             ORDER_BOUND_INQUIRY_TYPES, PortalAccount, PortalOrderInquiry,
                             REQUESTED_RESOLUTION_CHOICES, ReturnAuthorization, SalesOrder)
# Not re-exported from `apps.scm.models` (it is a bound, not a vocabulary), so it is imported from
# the module that declares it. `open_for()` already truncates `Case.description` to this; the same
# cap is applied to the resolve note here because `_comment()` does NOT truncate, and `body` is a
# TextField with no ceiling — a hostile POST could otherwise park a megabyte in the customer's thread.
from apps.scm.models.CustomerPortal.PortalOrderInquiries import MAX_CASE_DESCRIPTION

#: The four derived SLA buckets and their words. **Not a model vocabulary and never a column** — see
#: the module docstring. The colours live on ``PortalOrderInquiry.SLA_STATE_CSS`` (the model already
#: owns them for its ``sla_state_css`` property); keeping the labels here and the colours there is
#: not a split, it is the same rule the ``_choices.py`` convention applies everywhere else: a
#: vocabulary read from one direction stays where it is used, and the model is already the one place
#: the colour is decided.
SLA_CHOICES = [
    ("breached", "SLA breached"),
    ("due_soon", "Due soon"),
    ("ok", "On track"),
    ("none", "No SLA policy"),
]

SLA_LABELS = dict(SLA_CHOICES)

#: The order the annotated ``CASE WHEN`` ladder tests the buckets in. The four are mutually exclusive
#: by construction (see :func:`_sla_buckets`), so the order is documentation rather than precedence —
#: but it is stated because a later edit that makes two of them overlap would silently start
#: depending on it.
SLA_BUCKET_ORDER = ("breached", "due_soon", "ok", "none")

#: How many candidate returns the detail page's "raise return" picker offers. A queryset SLICE, so
#: the DATABASE applies it — it bounds what is FETCHED, not merely what is rendered. One more than
#: the cap is read so the page can say it is showing a window without paying for a second COUNT.
MAX_PICKER_ROWS = 50

#: How much of the case thread the triage page shows. The full conversation lives on CRM's own case
#: page and this is a window onto it, not a second thread page (§4: 4.16 builds no second thread).
MAX_THREAD_ROWS = 20


# ================================================================================== small helpers
def _detail(pk):
    """The one redirect target every verb and refusal in this module answers with."""
    return redirect("scm:portalorderinquiry_detail", pk=pk)


def _sla_buckets(now):
    """The four SLA buckets as Q objects — the SQL dialect of ``PortalOrderInquiry.sla_state``.

    The two are the same rule written twice because they answer for different things (a queryset the
    database has not sent yet vs. a row already in hand), and they are kept adjacent so a change to
    one is visibly a change to both. The list page's badge is annotated from THESE (see
    :func:`_sla_annotations`), so a row this puts in ``breached`` cannot render an "On track" chip.

    **Every predicate is positive — there is not one ``~Q`` below, and that is the whole trick.**
    ``first_response_due`` / ``first_responded_at`` / ``resolution_due`` are all nullable, so
    ``NOT (due < now)`` is NULL for a row with no deadline and silently drops it: the ``none`` bucket
    would leak into nothing and the four buckets would stop partitioning the table. The complements
    are therefore spelled out (``IS NULL`` OR ``already answered`` OR ``still in the future``), which
    is longer and is the only version that is total.

    The mirror of the Python property, clause by clause:

    * ``none`` — neither deadline exists, i.e. no policy was resolved when the case was opened.
      Deliberately distinct from ``ok``: a case nobody promised anything about is not a case that is
      meeting a promise.
    * ``breached`` — CRM's own ``is_response_overdue`` / ``is_resolution_overdue``, both of which
      already encode "and the case is still open". 4.16 recomputes no SLA of its own.
    * ``due_soon`` — open, has a policy, not breached, and the nearest deadline still to be met falls
      inside ``SLA_DUE_SOON_HOURS``. A first response already given stops counting, because the clock
      it belonged to has been stopped.
    * ``ok`` — everything else that has a policy: either the case is closed (a closed case cannot be
      overdue) or no live deadline is inside the window. ``not approaching`` IMPLIES ``not breached``
      — a deadline further out than ``soon`` is by definition further out than ``now`` — which is why
      ``ok`` needs no breach term of its own.

    Local CRM import at call time: ``apps/scm`` does not import ``apps/crm`` at module scope (the
    ``ReturnsManagement/Reports.py`` precedent). ``Case.OPEN_STATUSES`` is read rather than restated,
    so CRM adding a seventh triage status moves this filter with it.
    """
    from apps.crm.models import Case

    soon = now + timedelta(hours=PortalOrderInquiry.SLA_DUE_SOON_HOURS)
    closed_statuses = [value for value, _label in Case.STATUS_CHOICES
                       if value not in Case.OPEN_STATUSES]

    is_open = Q(case__status__in=Case.OPEN_STATUSES)
    is_closed = Q(case__status__in=closed_statuses)

    has_policy = Q(case__first_response_due__isnull=False) | Q(case__resolution_due__isnull=False)
    no_policy = Q(case__first_response_due__isnull=True) & Q(case__resolution_due__isnull=True)

    # The response clock is only running while a due date exists AND nobody has replied yet.
    response_running = Q(case__first_response_due__isnull=False,
                         case__first_responded_at__isnull=True)
    response_late = response_running & Q(case__first_response_due__lt=now)
    response_soon = response_running & Q(case__first_response_due__lte=soon)
    # The positive complement of `response_soon`: no clock at all, already answered, or a deadline
    # beyond the window.
    response_not_soon = (Q(case__first_response_due__isnull=True)
                         | Q(case__first_responded_at__isnull=False)
                         | Q(case__first_response_due__gt=soon))

    resolution_late = Q(case__resolution_due__isnull=False, case__resolution_due__lt=now)
    resolution_soon = Q(case__resolution_due__isnull=False, case__resolution_due__lte=soon)
    resolution_not_soon = Q(case__resolution_due__isnull=True) | Q(case__resolution_due__gt=soon)

    breached = is_open & (response_late | resolution_late)
    # `not_breached` here is the positive complement of the two LATE terms, for the same nullability
    # reason as above.
    not_breached = ((Q(case__first_response_due__isnull=True)
                     | Q(case__first_responded_at__isnull=False)
                     | Q(case__first_response_due__gte=now))
                    & (Q(case__resolution_due__isnull=True) | Q(case__resolution_due__gte=now)))

    return {
        "breached": breached,
        "due_soon": is_open & has_policy & not_breached & (response_soon | resolution_soon),
        "ok": has_policy & (is_closed | (is_open & response_not_soon & resolution_not_soon)),
        "none": no_policy,
    }


def _sla_annotations(buckets):
    """``sla_label`` + ``sla_css`` as SQL ``CASE WHEN`` ladders over :func:`_sla_buckets`.

    **This is why the list badge and the list filter cannot disagree**: both are the same four Q
    objects, so the chip is not a second opinion about the row — it is the filter, printed. The
    alternative (reading ``obj.sla_state`` in the template) cannot even render the label, because a
    Django template cannot subscript a dict with a variable key, and the branch-per-bucket workaround
    would put a second copy of the vocabulary in the HTML.

    ``models.Case`` / ``models.When``, spelled through the ``models`` namespace deliberately:
    ``Case`` is also the name of the CRM model this whole module reads, and a bare ``Case`` here
    would be the most confusing import in the file.

    The ``default`` is unreachable — the four buckets are exhaustive — and is present because an SQL
    ``CASE`` with no ``ELSE`` yields NULL, which would render as a blank badge rather than as
    anything a reader could act on.

    Takes the already-built ``buckets`` dict rather than rebuilding it: the badge, the filter and the
    header counts are then literally the same four objects in one request, not three constructions
    that merely ought to agree.
    """
    return {
        "sla_label": models.Case(
            *[models.When(buckets[name], then=models.Value(SLA_LABELS[name]))
              for name in SLA_BUCKET_ORDER],
            default=models.Value(SLA_LABELS["none"]), output_field=models.CharField()),
        "sla_css": models.Case(
            *[models.When(buckets[name], then=models.Value(PortalOrderInquiry.SLA_STATE_CSS[name]))
              for name in SLA_BUCKET_ORDER],
            default=models.Value("badge-muted"), output_field=models.CharField()),
    }


def _apply_sla_filter(queryset, value, buckets):
    """Narrow to one SLA bucket. Returns ``(queryset, resolved_value)``.

    A junk or absent value narrows NOTHING and is echoed back as ``""`` — the ``crud_list`` posture
    on a bad filter (L11): skip it, never 500, and never silently show a filtered page while the
    select claims a bucket was chosen. ``?sla=breached%00`` and ``?sla=²`` both land here as "not one
    of the four keys" and are simply dropped.
    """
    if value in buckets:
        return queryset.filter(buckets[value]), value
    return queryset, ""


def _sla_chip(obj):
    """``(label, css)`` for one fetched row — the Python dialect, used by the detail page only.

    Reads ``obj.sla_state`` (the model property, which reads CRM's own overdue predicates) and pairs
    it with the same two maps the list annotation uses, so the detail chip and the list chip are the
    same words in the same colour. A 2-tuple rather than two context keys so the label and its colour
    are handed over together and cannot be paired up wrongly by the template.
    """
    state = obj.sla_state
    return SLA_LABELS.get(state, SLA_LABELS["none"]), obj.sla_state_css


def _apply_validation_error(form, exc):
    """Fold a model-side ``ValidationError`` back onto the form. Never raises.

    ``open_for()`` runs ``full_clean()``, so its refusals arrive as field errors for columns like
    ``sales_order`` or ``quantity_affected`` — but also, potentially, for ``source`` or ``__all__``,
    which are NOT fields on ``PortalOrderInquiryForm``. ``form.add_error("source", …)`` raises
    ``ValueError`` in that case, turning a validation refusal into a 500. Anything the form cannot
    show against a field is therefore attached as a non-field error, where the user still reads it.
    """
    payload = getattr(exc, "error_dict", None)
    if payload is None:
        form.add_error(None, exc)
        return
    for field, errors in payload.items():
        form.add_error(field if field in form.fields else None, errors)


def _order_bound_labels():
    """The LABELS of the inquiry types that require an order, for the form's help text.

    Read off ``ORDER_BOUND_INQUIRY_TYPES`` — the same tuple ``PortalOrderInquiry.clean()`` refuses
    against — so the hint on the form and the rule that rejects the submission cannot come to
    disagree about which types those are. Labels rather than raw values, because the user is reading
    a dropdown, not the database.
    """
    labels = dict(INQUIRY_TYPE_CHOICES)
    return [labels[value] for value in ORDER_BOUND_INQUIRY_TYPES if value in labels]


def _context_rows(obj):
    """The supply-chain context as rows the template renders without four branches of its own.

    Each dict has the keys ``label`` / ``value`` / ``url_name`` / ``pk`` / ``owner``. ``url_name`` is
    ``""`` for the order line, which has no page of its own — the template guards on it rather than
    assuming every row links somewhere.

    ``owner`` is the one-line note saying **which sub-module owns the document**, and it is built here
    rather than typed into the HTML for the reason the whole model exists: 4.16 points at these rows,
    it does not own any of them, and a page that quietly implied otherwise is how a later pass ends up
    "fixing" an order from inside the portal console.

    Only rows that exist are returned, so an empty list is a real answer ("a general inquiry with no
    order behind it") and the template prints its empty state instead of four em dashes.
    """
    rows = []
    if obj.sales_order_id:
        rows.append({
            "label": "Sales order", "value": str(obj.sales_order),
            "url_name": "scm:salesorder_detail", "pk": obj.sales_order_id,
            "owner": "4.5 Order Management owns this order — 4.16 only points at it.",
        })
    if obj.sales_order_line_id:
        rows.append({
            "label": "Order line", "value": str(obj.sales_order_line),
            "url_name": "", "pk": None,
            "owner": "A line of the order above; it has no page of its own.",
        })
    if obj.shipment_id:
        rows.append({
            "label": "Shipment", "value": str(obj.shipment),
            "url_name": "scm:shipment_detail", "pk": obj.shipment_id,
            "owner": "4.6 Transportation Management owns this shipment, its tracking events and "
                     "its POD.",
        })
    if obj.invoice_id:
        rows.append({
            "label": "Invoice", "value": str(obj.invoice),
            "url_name": "accounting:invoice_detail", "pk": obj.invoice_id,
            "owner": "2.4 Accounts Receivable owns this invoice — SCM computes no AR of its own and "
                     "this is a read-only pointer.",
        })
    if obj.return_authorization_id:
        rows.append({
            "label": "Return authorisation", "value": str(obj.return_authorization),
            "url_name": "scm:returnauthorization_detail", "pk": obj.return_authorization_id,
            "owner": "4.10 Returns Management owns this RMA — 4.16 raises no return document of its "
                     "own.",
        })
    return rows


def _return_candidates(obj):
    """The returns this inquiry may legally be linked to. Returns ``(list, truncated)``.

    Scoped exactly the way :meth:`PortalOrderInquiry.link_return` refuses — same tenant, and the same
    customer when this inquiry HAS one — so the picker offers nothing the verb would then reject
    (the 4.11 finding). It is not the security boundary: the verb re-checks both, because a narrowed
    dropdown has never held against a crafted POST.

    ``obj.customer`` is ``None`` for a staff-filed inquiry with neither a portal account nor an order.
    That is "unknown", never "matches anything" — but ``link_return`` genuinely does allow any
    same-tenant RMA in that case (it has nothing to compare against), so the picker offers the same
    set the verb accepts rather than a narrower one that would hide a legal move.

    The already-linked return is excluded once the outcome says ``rma_raised``, because re-linking it
    is precisely the no-op the verb returns ``{}`` for — offering it would be a button that does
    nothing and audits nothing.
    """
    queryset = (ReturnAuthorization.objects.filter(tenant_id=obj.tenant_id)
                .select_related("customer"))
    customer = obj.customer
    if customer is not None:
        queryset = queryset.filter(customer=customer)
    if obj.outcome == "rma_raised" and obj.return_authorization_id:
        queryset = queryset.exclude(pk=obj.return_authorization_id)
    rows = list(queryset[:MAX_PICKER_ROWS + 1])
    truncated = len(rows) > MAX_PICKER_ROWS
    del rows[MAX_PICKER_ROWS:]
    return rows, truncated


def _run_verb(request, pk, *, action, apply_fn, success, noop):
    """Lock, run the model verb, audit inside the lock, flash, redirect — what all three verbs share.

    ``apply_fn(obj)`` calls the model method and returns its ``{field: [before, after]}`` diff, or
    ``{}`` when nothing changed. The model is the only writer of ``outcome`` / ``resolved_at`` /
    ``return_authorization``; this function adds the concurrency guard, the audit row and the words.

    **The row is taken FOR UPDATE and the verb runs inside the transaction.** Two POSTs — a
    double-click, a retry, a replay — would otherwise both read ``outcome="open"``, both pass
    ``is_open``, and each stamp ``resolved_at``; the second stamp is the one that survives and the
    "how long did we take?" figure becomes fiction. ``select_for_update()`` is called WITHOUT
    ``select_related``: every column the three verbs read (``outcome``, ``tenant_id``, ``case_id``,
    ``return_authorization_id``) is local, and locking the joined ``crm.Case`` row as a side effect
    would let an SCM triage button block a CRM agent editing the same ticket.

    **The audit row is written inside the lock, not after it** (the ``_status_transition`` fix): a
    failure between the commit and the log otherwise leaves an inquiry resolved with nobody's name on
    it, which on this model is a customer answer nobody can be asked about.

    A wrong VALUE (an outcome that is not resolvable, a cross-customer RMA) raises ``ValidationError``
    from the model and becomes an error message; a wrong STATE (resolving twice, reopening an open
    row) is a silent no-op and becomes ``noop``. Only the first is the caller's mistake, and the two
    must not be reported with the same words.

    The object is resolved BEFORE anything else, so a cross-tenant pk answers **404 rather than a
    302** that would leak "there is a row there, you just cannot move it" (the 4.12 finding).
    """
    try:
        with transaction.atomic():
            obj = get_object_or_404(PortalOrderInquiry.objects.select_for_update(),
                                    pk=pk, tenant=request.tenant)
            changes = apply_fn(obj)
            if changes:
                write_audit_log(request.user, obj, "update", {"action": action, **changes})
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
        return _detail(pk)

    if not changes:
        messages.info(request, noop)
    else:
        # Flashed AFTER the commit, so a message describing the new state can never survive a
        # rollback of the change it describes.
        messages.success(request, success(obj))
    return _detail(pk)


# ======================================================================================= the list
@login_required
def portalorderinquiry_list(request):
    """The triage queue: search, six column filters and one derived SLA bucket.

    EVERY filter is applied BEFORE ``crud_list`` paginates. A filter applied afterwards would page
    over the unfiltered set and quietly show the wrong rows on page 2.

    The two pk filters go through ``crud_list``'s ``is_int=True`` spec, which applies the L11 guard:
    ``?portal_account=abc``, ``?portal_account=²`` (a Unicode superscript — ``isdigit()`` says yes,
    ``int()`` says no) and ``?portal_account=99999999999999999999`` (converts fine, then overflows
    inside the driver) all SKIP the filter rather than raise on a URL anybody can type into the
    address bar. ``?sla=`` is the one filter that spec cannot express — it is a pair of deadline
    comparisons across a join, not an equality — so it is pre-applied through
    :func:`_apply_sla_filter` and the RESOLVED value is echoed back for the select to bind to.

    Search covers ``number``, the case ``subject`` (the human title — nobody remembers ``PIQ-00007``)
    and the order number, which is what a customer quotes on the phone.

    ``stats`` is counted over the WHOLE workspace rather than the filtered page, on purpose: "4
    breached" is a fact somebody has to act on, and recomputing it per filter would make the number
    change as you browse. ``from_portal`` is the deflection denominator — how much of this queue the
    customers filed themselves — and is only meaningful because ``source`` is forced server-side.

    The two dropdown querysets are deliberately narrow. ``sales_orders`` lists only orders that
    actually HAVE an inquiry: filtering by an order with none returns an empty page, so offering the
    workspace's entire order book would be a dropdown whose every other option is a dead end (and an
    unbounded one on a busy tenant).
    """
    now = timezone.now()
    # Built ONCE and shared by the badge, the filter and the header counts, so the three cannot be
    # three constructions that merely ought to agree.
    buckets = _sla_buckets(now)

    queryset = (PortalOrderInquiry.objects.filter(tenant=request.tenant)
                .select_related("case", "portal_account", "portal_account__customer",
                                "sales_order", "sales_order__customer")
                # The one TextField no list row renders. `defer` touches the SELECT list ONLY, so the
                # search below is unaffected — and `case__subject` must NOT be deferred, because it
                # is exactly what it searches.
                .defer("case__description")
                .annotate(**_sla_annotations(buckets))
                # STATED, not inherited. Meta.ordering is `-created_at` alone, which is not a total
                # order: two inquiries filed in the same tick would page non-deterministically, so
                # `-id` is appended to make page 2 reproducible.
                .order_by("-created_at", "-id"))

    queryset, sla = _apply_sla_filter(queryset, (request.GET.get("sla") or "").strip(), buckets)

    stats = PortalOrderInquiry.objects.filter(tenant=request.tenant).aggregate(
        open=Count("id", filter=Q(outcome="open")),
        breached=Count("id", filter=buckets["breached"]),
        due_soon=Count("id", filter=buckets["due_soon"]),
        from_portal=Count("id", filter=Q(source="portal")),
    )

    return crud_list(
        request, queryset, "scm/portal/portalorderinquiry/list.html",
        search_fields=["number", "case__subject", "sales_order__number"],
        filters=[("inquiry_type", "inquiry_type", False),
                 ("outcome", "outcome", False),
                 ("requested_resolution", "requested_resolution", False),
                 ("source", "source", False),
                 # is_int=True -> the L11 guard above.
                 ("sales_order", "sales_order_id", True),
                 ("portal_account", "portal_account_id", True)],
        extra_context={
            "inquiry_type_choices": INQUIRY_TYPE_CHOICES,
            "outcome_choices": INQUIRY_OUTCOME_CHOICES,
            "requested_resolution_choices": REQUESTED_RESOLUTION_CHOICES,
            "source_choices": INQUIRY_SOURCE_CHOICES,
            "sla_choices": SLA_CHOICES,
            # The RESOLVED bucket, not request.GET — a junk `?sla=urgent` narrowed nothing, so the
            # select must show "All" rather than an option that did not happen.
            "sla": sla,
            # `__str__` on both walks `customer`, so both need the join or the dropdown costs one
            # query per option — checked, not assumed.
            "portal_accounts": (PortalAccount.objects.filter(tenant=request.tenant)
                                .select_related("customer")),
            "sales_orders": (SalesOrder.objects
                             .filter(tenant=request.tenant, portal_inquiries__isnull=False)
                             .select_related("customer").distinct()),
            "stats": stats,
        },
    )


# ======================================================================================= the CRUD
@login_required
def portalorderinquiry_create(request):
    """File an inquiry for a customer. Hand-rolled, because ``open_for()`` writes the ``crm.Case``.

    ``crud_create`` cannot be used here and the reason is structural rather than stylistic: the
    ``case`` FK is NOT NULL, and the case has to be created, typed, attributed to a party and given
    the tenant's default SLA policy before the inquiry can even be validated.
    :meth:`PortalOrderInquiry.open_for` does all of that in one ``transaction.atomic()`` — so a
    rejected submission rolls the case back instead of leaving an orphaned, customer-visible ticket
    in the CRM queue — and it is the SINGLE writer of that case for the staff path, the portal path
    and the seeder alike.

    ``source="staff"`` is a literal here and ``raised_by`` is ``request.user``. Both are
    ``editable=False``, so a POST carrying ``source=portal&raised_by=<pk>&outcome=rejected&
    resolved_at=…&case=<other pk>&return_authorization=<pk>`` sets **none** of them — they never
    reach ``cleaned_data``, and ``open_for()``'s ``CONTEXT_FIELDS`` whitelist refuses them a second
    time even if a future caller forwarded ``request.POST`` too eagerly.

    ``subject`` and ``description`` are non-model fields on the form (they are the case's columns);
    they are read out of ``cleaned_data`` and handed to ``open_for()`` as arguments.

    Redirects to the DETAIL page rather than the list, because the next thing anyone does after
    filing an inquiry is triage it, and the detail page is where the three verbs live.
    """
    if _need_tenant(request):
        return redirect("scm:portalorderinquiry_list")

    if request.method == "POST":
        form = PortalOrderInquiryForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            data = form.cleaned_data
            try:
                obj = PortalOrderInquiry.open_for(
                    tenant=request.tenant,
                    portal_account=data.get("portal_account"),
                    subject=data.get("subject", ""),
                    description=data.get("description", ""),
                    user=request.user,
                    # Forced server-side. See the docstring — this figure is the denominator of every
                    # self-service claim the sub-module makes.
                    source="staff",
                    **{name: data[name] for name in PortalOrderInquiry.CONTEXT_FIELDS
                       if name in data},
                )
            except ValidationError as exc:
                # open_for() runs full_clean() with the case attached, so it can refuse things the
                # form alone could not see. Those refusals belong on the fields that caused them.
                _apply_validation_error(form, exc)
            else:
                # crud_create would have written this; the hand-rolled path must not lose it.
                write_audit_log(request.user, obj, "create",
                                {"case": str(obj.case), "source": obj.source,
                                 "inquiry_type": obj.inquiry_type})
                messages.success(request, f"{obj.number} opened — support case {obj.case.number} "
                                          "was created with it.")
                return redirect("scm:portalorderinquiry_detail", pk=obj.pk)
    else:
        form = PortalOrderInquiryForm(tenant=request.tenant)

    return render(request, "scm/portal/portalorderinquiry/form.html", {
        "form": form,
        "is_edit": False,
        "order_bound_labels": _order_bound_labels(),
    })


@login_required
def portalorderinquiry_edit(request, pk):
    """Correct the supply-chain context. The case, the outcome and the provenance are untouchable.

    ``crud_edit`` unchanged, and that is safe here in a way it was not on create: by now the case
    exists, ``PortalOrderInquiryForm`` REMOVES ``subject``/``description`` on a bound instance (a
    field that silently discards what the user typed is worse than an absent one — the conversation
    continues on the case's own thread), and ``case`` / ``outcome`` / ``resolved_at`` /
    ``return_authorization`` / ``source`` / ``raised_by`` are ``editable=False`` and therefore absent
    from every ModelForm automatically. ``crud_edit`` writes the audit diff.

    Editing is allowed in EVERY outcome, including a resolved one. Deliberately: the context columns
    say what the inquiry was ABOUT, and discovering after the fact that a damage claim was against a
    different line is a correction somebody must be able to make. Nothing here can move the outcome,
    so a "closed" inquiry cannot be quietly re-opened through the edit form.
    """
    return crud_edit(request, model=PortalOrderInquiry, pk=pk,
                     form_class=PortalOrderInquiryForm,
                     template="scm/portal/portalorderinquiry/form.html",
                     success_url="scm:portalorderinquiry_list",
                     extra_context={"order_bound_labels": _order_bound_labels()})


@login_required
def portalorderinquiry_detail(request, pk):
    """Triage one inquiry: the context it is about, the SLA it is under, and the legal next moves.

    **The page shows BOTH statuses side by side, and that is its most important job.** The internal
    ``case.status`` is the agent queue's word; ``obj.customer_status_label`` is what the customer is
    actually being shown (``CUSTOMER_STATUS_MAP`` — the three triage states collapse to one customer
    word on purpose). Rendering only one of them is how somebody ends up telling a customer their
    ticket is "In Progress" when the portal has been saying "Awaiting your reply" for three days.

    Context keys, exhaustively (the templates are written by a separate agent):

    * ``obj`` — the :class:`~apps.scm.models.PortalOrderInquiry`, every context FK joined. Badges:
      ``obj.inquiry_type_css`` / ``obj.outcome_css`` / ``obj.customer_status_css``. Figures:
      ``obj.age_days`` (``None`` on an unsaved row — print an em dash, never ``0``).
    * ``case`` — the wrapped ``crm.Case``, for the internal status, priority, owner and the SLA
      timestamps. **Read here, computed nowhere:** ``first_response_due`` / ``first_responded_at`` /
      ``resolution_due`` / ``satisfaction_rating`` are all CRM's, and 4.16 recomputes no SLA and runs
      no CSAT survey. Link the thread with ``{% url 'crm:case_detail' case.pk %}``.
    * ``customer`` — the ``core.Party`` this inquiry is about, or ``None`` when a staff member filed a
      general one. ``None`` means UNKNOWN, never "matches anything".
    * ``context_rows`` — a list of dicts, keys ``label`` / ``value`` / ``url_name`` / ``pk`` /
      ``owner``. ``url_name`` is ``""`` for the order line (it has no page); guard on it. ``owner`` is
      the one-line note naming the sub-module that OWNS that document — render it, it is the point.
      An empty list is a real answer and gets the empty state, not four em dashes.
    * ``sla_chip`` — a plain ``(label, css)`` 2-tuple: render ``sla_chip.0`` and ``sla_chip.1``.
      ``sla_state`` is the raw ``breached`` / ``due_soon`` / ``ok`` / ``none`` token for a
      conditional. ``none`` means nobody promised anything and is deliberately not ``ok``.
    * ``case_comments`` — up to :data:`MAX_THREAD_ROWS` of the most recent comments, oldest-first for
      reading, each with ``is_public`` (**a False one is an INTERNAL note — this is a staff page, but
      the flag must still be shown, or an agent cannot tell what the customer has already read**),
      ``author_name``, ``body`` and ``created_at``. ``case_comment_count`` is the true total and
      ``case_comments_truncated`` says the window hid some; the full thread is CRM's page.
    * **Action gates** — ``can_resolve`` / ``can_reopen`` / ``can_raise_return``, read from the same
      conditions the three verbs enforce. Render ONLY the legal moves: offering a button the view will
      refuse is the 4.11 finding.
    * ``resolvable_outcomes`` — the ``(value, label)`` pairs the resolve dropdown may offer.
      ``rma_raised`` is absent by construction: it is a claim about a document, and only the raise-
      return verb (which has the RMA in hand) may set it, so the badge always has something to click.
    * ``return_candidates`` — the RMAs the raise-return picker may offer (already tenant- and
      customer-scoped exactly as the verb refuses), ``return_candidates_truncated`` (bool) and
      ``max_picker_rows``.
    * ``max_note_length`` — the ceiling to put on the resolve note's ``maxlength``; the view truncates
      to it regardless, because a ``CaseComment.body`` is an unbounded TextField.

    The confirm text on every POST button must contain **no apostrophe and no ``{{ }}``-interpolated
    user data** — HTML decodes ``&#39;`` inside an attribute before the JS engine sees it, which
    silently disables the guard (L42). Use ``obj.number`` (a system-generated ``PIQ-`` string) only.
    """
    obj = get_object_or_404(
        PortalOrderInquiry.objects.select_related(
            "case", "case__sla_policy", "case__owner",
            "portal_account", "portal_account__customer",
            "sales_order", "sales_order__customer", "sales_order_line", "sales_order_line__item",
            "shipment", "invoice", "return_authorization", "return_authorization__customer"),
        pk=pk, tenant=request.tenant)

    candidates, candidates_truncated = _return_candidates(obj)

    # The thread window. Local CRM import for the same reason the model uses one: apps/scm does not
    # import apps/crm at module scope. Sliced in the DATABASE (it bounds what is FETCHED, not merely
    # what is rendered) and taken newest-first so the slice keeps the RECENT end, then reversed in
    # Python so the page reads top-to-bottom like a conversation.
    from apps.crm.models import CaseComment
    thread = (CaseComment.objects.filter(tenant_id=obj.tenant_id, case_id=obj.case_id)
              .select_related("author").order_by("-created_at", "-id")[:MAX_THREAD_ROWS])
    comments = list(reversed(list(thread)))
    comment_count = CaseComment.objects.filter(tenant_id=obj.tenant_id, case_id=obj.case_id).count()

    return render(request, "scm/portal/portalorderinquiry/detail.html", {
        "obj": obj,
        "case": obj.case,
        "customer": obj.customer,

        "context_rows": _context_rows(obj),

        "sla_chip": _sla_chip(obj),
        "sla_state": obj.sla_state,

        "case_comments": comments,
        "case_comment_count": comment_count,
        "case_comments_truncated": comment_count > len(comments),

        # The exact conditions the three verbs enforce — see each one's docstring.
        "can_resolve": obj.is_open,
        "can_reopen": not obj.is_open,
        "can_raise_return": bool(candidates),

        "resolvable_outcomes": [(value, label) for value, label in INQUIRY_OUTCOME_CHOICES
                                if value in PortalOrderInquiry.RESOLVABLE_OUTCOMES],
        "return_candidates": candidates,
        "return_candidates_truncated": candidates_truncated,
        "max_picker_rows": MAX_PICKER_ROWS,
        "max_note_length": MAX_CASE_DESCRIPTION,
    })


@login_required
@require_POST
def portalorderinquiry_delete(request, pk):
    """Delete the inquiry. **The customer's case survives, and the message says so.**

    ``PortalOrderInquiry.case`` is CASCADE in the other direction — deleting the CASE takes the
    inquiry with it, because without its case this row has no thread, no SLA and no customer-visible
    conversation. Deleting the INQUIRY does not touch the case, and must not: the customer's ticket,
    their words and every reply they have already read are CRM's, and an SCM console quietly deleting
    a support conversation is not a delete anybody intended to make.

    What is destroyed is the supply-chain context — which order, which line, which parcel, what was
    claimed and how it ended. Nothing reconstructs that, so the case is named in the follow-up message
    while the row still exists to name it.

    Not admin-gated: triage is ordinary agent work, and gating it would push people into the Django
    admin, which leaves a thinner trail than this does. The audit row is written INSIDE the
    transaction so it rolls back with a failed delete rather than recording a deletion that did not
    happen.
    """
    obj = get_object_or_404(PortalOrderInquiry.objects.select_related("case"),
                            pk=pk, tenant=request.tenant)
    number = obj.number
    case_label = str(obj.case) if obj.case_id else ""

    with transaction.atomic():
        write_audit_log(request.user, obj, "delete")
        obj.delete()

    messages.success(request, f"{number} deleted.")
    if case_label:
        messages.info(request, f"Support case {case_label} is unaffected — the conversation, the SLA "
                               "clocks and everything the customer has already read belong to CRM "
                               "and stay there. Only the order, line, shipment and invoice context "
                               "recorded here is gone.")
    return redirect("scm:portalorderinquiry_list")


# ================================================================================ the three verbs
@login_required
@require_POST
def portalorderinquiry_resolve(request, pk):
    """Close the inquiry with an outcome, optionally replying to the customer.

    POST body: ``outcome`` (one of ``PortalOrderInquiry.RESOLVABLE_OUTCOMES``) and an optional
    ``note``.

    **The note is a PUBLIC ``CaseComment``**, not an internal one and not a column on this model:
    the customer asked a question and this is the reply, so it goes in the thread they can actually
    read. It is truncated to :data:`MAX_CASE_DESCRIPTION` here because
    ``PortalOrderInquiry._comment()`` does not truncate and ``CaseComment.body`` is a TextField with
    no ceiling — the same cap ``open_for()`` already applies to the case description, so the bound
    does not depend on which door the text came through.

    A second resolution is refused by the model as a **no-op**, not an error: the first resolver's
    answer is the one the customer was given, and letting a later press blank ``resolved_at`` would
    make "how long did we take?" unanswerable. Reopening first is the supported way to change an
    answer, which is exactly what the no-op message says.

    ``rma_raised`` is not offered and is refused by the model, because it is a claim about a document
    — an inquiry badged "RMA raised" with no return to click is a lie the list page repeats forever.
    """
    outcome = (request.POST.get("outcome") or "").strip()
    note = (request.POST.get("note") or "").strip()[:MAX_CASE_DESCRIPTION]
    return _run_verb(
        request, pk, action="resolve",
        apply_fn=lambda obj: obj.resolve(request.user, outcome, note),
        success=lambda obj: f"{obj.number} resolved as {obj.get_outcome_display().lower()}."
                            + (" Your note was posted to the customer's thread." if note else ""),
        noop="That inquiry has already been resolved. Reopen it first if the answer has changed — "
             "that keeps the original resolution time honest.",
    )


@login_required
@require_POST
def portalorderinquiry_reopen(request, pk):
    """Put a resolved inquiry back in the queue.

    Clears ``outcome`` and ``resolved_at`` and nothing else. ``return_authorization`` is deliberately
    LEFT IN PLACE: the RMA is a document that exists in the world, and reopening the conversation
    about it does not un-raise it.

    No-op when it is already open. There is no ``reopened_by`` column on purpose — it would be null on
    almost every row, would only ever remember the LAST reopen, and the audit row this writes already
    holds the whole sequence.
    """
    return _run_verb(
        request, pk, action="reopen",
        apply_fn=lambda obj: obj.reopen(request.user),
        success=lambda obj: f"{obj.number} reopened. The support case is CRM's and was not touched — "
                            "set its status there if the agent queue should move too.",
        noop="That inquiry is already open.",
    )


@login_required
@require_POST
def portalorderinquiry_raise_return(request, pk):
    """Link 4.10's ``ReturnAuthorization`` and record the outcome as ``rma_raised``.

    POST body: ``return_authorization`` (the pk of an EXISTING RMA).

    **This verb raises no return document.** 4.16 builds no second RMA — ``rma_raised`` is a claim
    about 4.10's document, and the FK is what makes the badge honest. Create the return in 4.10
    (``scm:returnauthorization_create``, or the customer's own ``scm:portal_return_create``) and link
    it here.

    The pk goes through ``as_db_int`` for the same reason every filter does (L11): ``abc``, ``²`` and
    a 21-digit number are all "not a pk" and must not reach ``.filter()``, where the third one raises
    inside the driver. A pk that resolves to nothing in THIS workspace takes the same message as a
    missing one — the two are indistinguishable on purpose, so this route cannot be used to probe
    whether another tenant's RMA id exists.

    **The RMA is resolved INSIDE :func:`_run_verb`, after the inquiry has been fetched, and that
    ordering is the security-relevant part.** Resolving it first — the obvious way to write this —
    means a POST with a missing or junk ``return_authorization`` is answered with a message and a 302
    *before* anyone checks that the inquiry belongs to this workspace, so another tenant's pk replies
    "there is a row there, you just cannot move it" while every sibling route replies 404 (the 4.12
    finding). Raising the refusal from inside ``apply_fn`` keeps the 404 first and still produces the
    same sentence for the operator.

    :meth:`~PortalOrderInquiry.link_return` then re-checks the tenant AND the customer and refuses a
    mismatch, and that refusal is an authorisation rule rather than a typo check: linking another
    customer's return here would publish its number, dates and disposition on this customer's portal
    inquiry. The picker is scoped the same way, but a narrowed dropdown has never held against a
    crafted POST, so the refusal lives where the write happens.

    Re-linking a DIFFERENT return is allowed — an agent correcting a mis-link is a real event and the
    audit diff records what it replaced. Re-linking the same one is the no-op.
    """
    rma_pk = as_db_int(request.POST.get("return_authorization"))

    def _link(obj):
        rma = None
        if rma_pk is not None:
            rma = (ReturnAuthorization.objects.select_related("customer")
                   .filter(pk=rma_pk, tenant=request.tenant).first())
        if rma is None:
            # A ValidationError rather than an early return, so the refusal travels the same path as
            # the model's own — and so it cannot be raised before the 404 above it.
            raise ValidationError(
                "Pick a return authorisation from this workspace. Create the return in Returns "
                "Management first if it does not exist yet — 4.16 links an existing RMA, it never "
                "raises a second one.")
        return obj.link_return(rma, request.user)

    return _run_verb(
        request, pk, action="raise_return",
        apply_fn=_link,
        # `obj.return_authorization` is the row link_return just assigned in memory, so naming it
        # costs no query and cannot name a different return than the one that was actually linked.
        success=lambda obj: f"{obj.number} is now linked to {obj.return_authorization.number} and "
                            "marked RMA raised. The return itself is Returns Management's document "
                            "— settle it there.",
        noop="That return is already linked to this inquiry.",
    )
