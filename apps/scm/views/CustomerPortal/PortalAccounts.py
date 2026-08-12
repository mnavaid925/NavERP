"""SCM 4.16 Customer Portal — ``PortalAccount`` views: the staff ENABLEMENT CONSOLE.

This is the sub-module's root screen. ``PortalAccount`` is not a login — the login binding is
``crm.CustomerPortalAccess`` and 4.16 declares no second one — so a customer is only actually *on*
the portal when THREE separate things line up: an active CRM access row exists for one of their
users, that access row names their party, and an active ``PortalAccount`` configures what that party
may see (``apps/scm/views/_helpers.py::_portal_account`` is the one place that chain is walked).
Every one of the three can be true on its own while the customer still sees nothing, and each of the
three is administered on a different screen. **The list below exists to make that failure visible**:
an account with no bound users, or with users who have never once signed in, is a portal somebody
switched on and nobody ever opened, and until it is on a page it is invisible.

--------------------------------------------------------------------------------------------------
THE PERFORMANCE RULE THIS MODULE IS WRITTEN AROUND
--------------------------------------------------------------------------------------------------
``PortalAccount`` exposes ``linked_user_count`` and ``has_never_logged_in`` as PER-ROW properties.
Both are correct and both are meant for a single row on a detail page. **Neither may be read from
the list view or from ``list.html``** — 15 rows a page × two properties is 30 extra queries for one
screen, which is exactly the 4.13 ``asset_list`` finding, and the fact that the ORM makes it read
nicely in a template is what makes it easy to ship.

The list therefore annotates the same four facts as CORRELATED SCALAR SUBQUERIES
(:data:`_LAST_LOGIN_AT`, :data:`_OPEN_INQUIRY_COUNT`, :func:`_live_share_count`,
:func:`_linked_user_count`), which the database evaluates once per RETURNED row and which — unlike a
joined ``Count()`` — force no ``GROUP BY``, cannot fan out against each other, and leave
``QuerySet.ordered`` True so the paginator does not warn (``views/_common.py``'s standing rule, and
the ``_OPEN_JOB_COUNT`` note in ``AssetManagement/Assets.py``).

**The annotation is deliberately named ``linked_users`` and NOT ``linked_user_count``.** It cannot
be called ``linked_user_count``: assigning an annotation of that name onto each row would raise
``AttributeError`` on the read-only property. The trap that leaves behind is that
``{{ obj.linked_user_count }}`` in ``list.html`` would still RENDER — correctly, one query per row —
so nothing would ever look broken. Read ``obj.linked_users``; the same goes for
``obj.last_login_at`` in place of ``obj.has_never_logged_in``.

--------------------------------------------------------------------------------------------------
DELETE IS THE DANGEROUS VERB HERE, AND IT IS PROTECTED FROM TWO SIDES
--------------------------------------------------------------------------------------------------
``PortalOrderInquiry.portal_account`` is ``PROTECT`` (an inquiry is evidence and must not lose its
account), while ``PortalDocumentShare.portal_account`` and ``PortalActivity.portal_account`` are
``CASCADE`` — so a delete that gets through takes the whole share register and the entire append-only
customer read log with it, and nothing reconstructs either. :func:`portalaccount_delete` therefore
pre-checks the inquiry count for a sentence somebody can act on, ALSO catches ``ProtectedError`` in
case a row is filed between the check and the delete (the 4.10 ``currency_delete`` finding), and
steers to ``is_active=False`` — which is the move that actually solves the problem, because
``_portal_account()`` puts ``is_active`` IN the lookup and one save kills the customer's portal
without destroying a single row of evidence.

--------------------------------------------------------------------------------------------------
Context-var contract (pinned, L7 — the templates are written by a separate agent, so EVERY key each
page consumes is listed here, not merely the list variable):
--------------------------------------------------------------------------------------------------
* ``scm/portal/portalaccount/list.html`` — ``object_list`` + ``page_obj`` + ``q`` (from
  ``crud_list``). **Per-ROW annotations** (read these, never the model properties — see above):
  ``linked_users`` (int, ACTIVE CRM portal logins bound to this customer, ``0`` is normal on a fresh
  account), ``open_inquiries`` (int), ``live_shares`` (int — neither revoked nor expired) and
  ``last_login_at`` (``datetime`` or ``None``; **``None`` renders as "Never signed in"**, never as a
  blank cell and never as an em dash on its own — that cell is the console's headline).
  Filter context: ``stock_display_choices`` / ``catalog_scope_choices`` / ``price_basis_choices``
  (lists of ``(value, label)`` pairs) and ``customers`` (queryset for the pk dropdown — compare with
  ``|stringformat:"d"``, NEVER ``|slugify``). Header chips: ``stats``, a dict with keys ``total`` /
  ``active`` / ``inactive`` / ``never_logged_in`` / ``unlinked``. Filter params: ``q`` /
  ``stock_display`` / ``catalog_scope`` / ``price_basis`` (strings — compare against
  ``request.GET.<param>`` directly), ``is_active`` (option values are the strings ``True`` /
  ``False``, which is what ``crud_list`` maps to real booleans) and ``customer`` (pk).
  **Do NOT render ``obj.catalog_categories.all`` on this page** — it is a many-to-many and that is a
  query per row for a detail nobody triages by; the scope label
  (``obj.get_catalog_scope_display``) is what the column is for.
* ``scm/portal/portalaccount/form.html`` — ``form`` + ``is_edit`` (+ ``obj`` on the edit path, from
  ``crud_edit``).
* ``scm/portal/portalaccount/detail.html`` — see :func:`portalaccount_detail`'s docstring for the
  full key list; it is long enough to belong beside the code that builds it.

Badge classes come from the ``_choices.py`` ``*_CSS`` maps and the models' own ``*_css`` properties
(``PortalActivity.action_css``, ``PortalDocumentShare.doc_type_css``,
``PortalOrderInquiry.outcome_css`` / ``inquiry_type_css`` / ``sla_state_css``). Only the six
colour-named classes exist in ``theme.css``: ``badge-green`` / ``badge-red`` / ``badge-amber`` /
``badge-info`` / ``badge-muted`` / ``badge-slate``. ``badge-success`` / ``badge-warning`` /
``badge-danger`` DO NOT EXIST and render as completely unstyled text (L33).

:func:`portalaccount_delete` is ``@tenant_admin_required``, so wrap that button in
``{% if request.user.is_superuser or request.user.is_tenant_admin %}`` — showing a member a button
they will 403 on is the 4.11 finding.
"""
# ProtectedError is a db-layer exception, not a model, so it is imported from django directly rather
# than through `_common`'s star (the `AssetManagement/Assets.py:80` precedent).
from django.db.models import ProtectedError
# Coalesce, because a correlated COUNT subquery answers NULL — not 0 — for an account with no
# matching child rows at all, and every one of these lands in a numeric badge.
from django.db.models.functions import Coalesce

from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._helpers import _need_tenant

from apps.scm.forms import PortalAccountForm
from apps.scm.models import (CATALOG_SCOPE_CHOICES, PortalAccount, PortalActivity,
                             PortalDocumentShare, PortalOrderInquiry, PRICE_BASIS_CHOICES,
                             STOCK_DISPLAY_CHOICES)

#: How many rows each panel on the detail page shows. A queryset SLICE, so the DATABASE applies it —
#: it bounds what is FETCHED, not merely what is rendered (L40 §1: a guard that first builds the
#: whole thing is the payload, not a guard). The activity log in particular is append-only and grows
#: forever, so an unbounded panel is a page that gets slower every week it is left alone.
MAX_PANEL_ROWS = 20

#: The ``PortalActivity.action`` token that means "this customer actually opened the portal".
#: Written once here and read by :data:`_LAST_LOGIN_AT` so the list's "never signed in" column and
#: ``PortalAccount.has_never_logged_in`` (which hard-codes the same token) cannot come to different
#: conclusions about the same account.
LOGIN_ACTION = "login"

#: The six entitlement booleans, in the order the detail page reads them, with the words the chips
#: use. A tuple here rather than six branches in the template: the labels are decided once, and a
#: seventh entitlement added to the model is one line in this file instead of an edit hunt through
#: two templates. The help text is pulled off the FIELD itself in :func:`_entitlements`, so the chip
#: explanation and the form's explanation are literally the same string and cannot drift.
ENTITLEMENT_FIELDS = (
    ("can_track_shipments", "Order tracking & POD"),
    ("can_view_invoices", "Invoice history"),
    ("can_view_documents", "Document library"),
    ("can_raise_inquiries", "Raise inquiries"),
    ("can_request_returns", "Request returns"),
    ("show_credit_and_balance", "Credit & balance"),
)


# ================================================================================== small helpers
def _detail(pk):
    """The one redirect target every refusal in this module answers with."""
    return redirect("scm:portalaccount_detail", pk=pk)


def _portal_customer_qs(tenant):
    """The parties behind the list's ``?customer=`` dropdown.

    Deliberately NARROWER than the form's ``_customer_parties()``: the form offers every party
    tagged as a customer because any of them could be given a portal, but a FILTER may only offer
    values that can actually return a row. A dropdown listing 400 customers of which 6 have a portal
    account is 394 options whose only possible outcome is an empty page (the 4.11 finding, read from
    the filter side).

    ``PortalAccount`` carries ``unique_together ("tenant", "customer")``, so the reverse join can
    match at most one row per party and no ``.distinct()`` is owed here — stated because the shape
    normally does need one, and a reviewer is entitled to know it was checked rather than forgotten.
    """
    if tenant is None:
        return Party.objects.none()
    return Party.objects.filter(tenant=tenant, scm_portal_accounts__isnull=False).order_by("name")


def _live_share_q(now):
    """"Still readable out there", as a ``Q`` — the SQL dialect of ``PortalDocumentShare.is_live``.

    The property (``not is_revoked and not is_expired``) and this predicate are the same rule
    written twice because they answer for different things: one for a row already in hand, one for a
    queryset the database has not sent yet. They are kept in one place each and named after each
    other so a change to the definition of "live" is visibly a change to both — a count that says 3
    live shares beside a list rendering 2 live badges is a page arguing with itself.

    ``expires_at__gt=now`` rather than ``__gte``: ``is_expired`` is ``expires_at <= now``, so the
    instant of expiry belongs to the expired side on both sides of the mirror.
    """
    return Q(revoked_at__isnull=True) & (Q(expires_at__isnull=True) | Q(expires_at__gt=now))


#: When this account's customer last actually signed in — a correlated scalar ``Subquery``, and the
#: one annotation the enablement console is built around. ``NULL`` means *never*, which is the whole
#: point: an account nobody has ever opened looks identical to a healthy one on every other column.
#:
#: It replaces ``PortalAccount.has_never_logged_in`` for list use and is strictly more informative —
#: the property answers a yes/no, this answers "when", and "when" subsumes it (``None`` -> never).
#:
#: ``tenant`` is correlated with ``OuterRef("tenant_id")`` rather than closed over as a literal
#: because this is a module-level constant with no request in scope; it resolves to the outer row's
#: own tenant, so the subquery can never reach across a workspace. It is also not redundant:
#: ``PortalActivity``'s ``(tenant, portal_account, created_at)`` index has ``tenant`` as its LEADING
#: column, so a lookup that omits it cannot open that index at all (the ``MeterReading`` lesson,
#: restated in the model's own ``Meta``).
#:
#: ``.order_by("-created_at")`` is STATED even though ``Meta.ordering`` already says it: a
#: ``values(...)[:1]`` subquery is "the first row" and which row that is must not be inherited.
_LAST_LOGIN_AT = (PortalActivity.objects
                  .filter(tenant=OuterRef("tenant_id"), portal_account=OuterRef("pk"),
                          action=LOGIN_ACTION)
                  .order_by("-created_at")
                  .values("created_at")[:1])

#: How many inquiries are still open against this account, as a correlated scalar ``Subquery``.
#:
#: **Why not the obvious ``Count("inquiries", filter=Q(inquiries__outcome="open"))``.** The joined
#: form turns the whole account query into an aggregate query, which forces a ``GROUP BY`` the
#: paginator's ``.count()`` cannot collapse, drags ``Meta.ordering`` into that GROUP BY, and makes
#: ``QuerySet.ordered`` report False so the paginator warns. A second joined aggregate beside it
#: would additionally multiply the outer rows against each other (the 4.8 ``WorkCenter`` finding) —
#: and this list carries three of them. A correlated subquery cannot fan out.
#:
#: ``.order_by()`` is load-bearing: ``PortalOrderInquiry.Meta.ordering`` is ``["-created_at"]`` and
#: an inherited ORDER BY column would be dragged into the subquery's own GROUP BY, splitting the
#: count per timestamp — i.e. answering 1 for an account with nine open inquiries.
_OPEN_INQUIRY_COUNT = (PortalOrderInquiry.objects
                       .filter(tenant=OuterRef("tenant_id"), portal_account=OuterRef("pk"),
                               outcome="open")
                       .order_by()
                       .values("portal_account")
                       .annotate(n=Count("id"))
                       .values("n")[:1])


def _live_share_count(now):
    """Live document shares per account, as a coalesced correlated ``Subquery``.

    A function rather than a module constant because "live" is relative to a clock and the clock has
    to be the one the rest of the page was rendered against — a constant would freeze ``now`` at
    import time, and the count would drift a little further from the truth every day the process
    stayed up. See :data:`_OPEN_INQUIRY_COUNT` for why this is not a joined ``Count``, and
    :func:`_live_share_q` for the definition it shares with the model property.
    """
    return Coalesce(
        models.Subquery(
            PortalDocumentShare.objects
            .filter(_live_share_q(now), tenant=OuterRef("tenant_id"), portal_account=OuterRef("pk"))
            .order_by()
            .values("portal_account")
            .annotate(n=Count("id"))
            .values("n")[:1],
            output_field=models.IntegerField()),
        models.Value(0), output_field=models.IntegerField())


def _linked_user_count():
    """Active ``crm.CustomerPortalAccess`` logins per account, as a coalesced correlated ``Subquery``.

    The SQL twin of ``PortalAccount.linked_user_count`` — same three predicates (this workspace,
    this customer party, ``is_active=True``), so the number on the list and the number on the detail
    page are the same fact computed in two dialects rather than two opinions.

    **The join is through the PARTY, not through a foreign key**, and there is no other way to write
    it: ``CustomerPortalAccess`` points at ``core.Party``, ``PortalAccount`` points at
    ``core.Party``, and neither knows the other exists. That is the design (4.16 builds no second
    login binding, because two bindings can disagree about which party a user is — an authorisation
    bug by construction), and this correlated subquery is what reading it costs.

    **Local import, following ``ReturnsManagement/Reports.py``: SCM does not import CRM at module
    scope.** A function rather than a constant for exactly that reason — a module-level constant
    would have to run the import at load time, which is the thing being avoided.

    ``0`` is the NORMAL state of a freshly enabled account, not an error: staff configure the portal
    first and bind the people afterwards. It is worth surfacing anyway, because an account that
    stays at 0 is one nobody can log into.
    """
    from apps.crm.models import CustomerPortalAccess
    return Coalesce(
        models.Subquery(
            CustomerPortalAccess.objects
            .filter(tenant=OuterRef("tenant_id"), customer_party=OuterRef("customer_id"),
                    is_active=True)
            # `.order_by()` for the reason spelled out on _OPEN_INQUIRY_COUNT: CustomerPortalAccess
            # also carries `Meta.ordering = ["-created_at"]`.
            .order_by()
            .values("customer_party")
            .annotate(n=Count("id"))
            .values("n")[:1],
            output_field=models.IntegerField()),
        models.Value(0), output_field=models.IntegerField())


def _entitlements(account):
    """The six entitlement booleans as a list of dicts — one place, so no template types a label.

    Keys per row: ``field`` (the model field name), ``label`` (:data:`ENTITLEMENT_FIELDS`),
    ``granted`` (bool) and ``help_text`` (**read off the model field**, so the chip's explanation is
    the same sentence the form shows and the two can never drift).

    ``show_credit_and_balance`` is in the same list as the other five on purpose even though it is
    the only one that defaults False: an entitlement panel that quietly omits the money switch is
    the panel somebody reads to answer "is this customer seeing our balances?".
    """
    return [{"field": name,
             "label": label,
             "granted": bool(getattr(account, name)),
             "help_text": PortalAccount._meta.get_field(name).help_text}
            for name, label in ENTITLEMENT_FIELDS]


# ======================================================================================= the list
@login_required
def portalaccount_list(request):
    """The enablement console: search, five filters, four annotations, five header chips.

    EVERY filter is applied BEFORE ``crud_list`` paginates. A filter applied afterwards would page
    over the unfiltered set and quietly show the wrong rows on page 2.

    ``?customer=`` goes through ``crud_list``'s ``is_int=True`` spec, which applies the L11 guard:
    ``?customer=abc``, ``?customer=²`` (a Unicode superscript — ``isdigit()`` says yes, ``int()``
    says no) and ``?customer=99999999999999999999`` (converts fine, then overflows inside the
    driver) all SKIP the filter rather than raise on a URL anybody can type into the address bar.
    ``?is_active=`` is handled by the same spec's boolean mapping — ``.filter(is_active="False")``
    would otherwise coerce through ``bool("False") == True`` and silently return every row — and a
    junk ``?is_active=maybe`` is caught inside ``crud_list`` and skipped.

    **Four annotations, and not one of them is a join** — see the module docstring for the whole
    argument, and read them off the row as ``linked_users`` / ``open_inquiries`` / ``live_shares`` /
    ``last_login_at``. ``obj.linked_user_count`` and ``obj.has_never_logged_in`` exist on the model,
    render perfectly in a template, and are a query per row each: this page must not use them.

    ``.defer("welcome_message", "notes")`` drops the two ``TextField``s no list row renders (only
    the detail page and the form read them). ``defer`` touches the SELECT list ONLY, so every filter
    below is unaffected.

    ``stats`` is counted over the WHOLE workspace rather than the filtered page, on purpose: "4
    accounts never signed in" is a fact somebody has to act on, and recomputing it per filter would
    make the number change as you browse. The two interesting chips each cost one extra query and
    are worth it — ``never_logged_in`` and ``unlinked`` are the two ways a portal can be switched on
    and still be invisible to the customer, and both are scoped to ACTIVE accounts because a
    deliberately deactivated account is not a problem to chase.
    """
    now = timezone.now()

    queryset = (PortalAccount.objects.filter(tenant=request.tenant)
                .select_related("customer")
                .defer("welcome_message", "notes")
                .annotate(
                    linked_users=_linked_user_count(),
                    open_inquiries=Coalesce(
                        models.Subquery(_OPEN_INQUIRY_COUNT, output_field=models.IntegerField()),
                        models.Value(0), output_field=models.IntegerField()),
                    live_shares=_live_share_count(now),
                    # ANY inquiry, not just an open one — this is what the Delete button must be
                    # gated on, because `portalaccount_delete` refuses on the TOTAL count (an
                    # inquiry is the record of an argument about an order and must keep the account
                    # it was raised under, whether or not it is still open).
                    #
                    # Gating the row's bin on `open_inquiries` instead meant an account with zero
                    # open and one resolved inquiry showed a button the route would then refuse:
                    # handled, never a 500, but still the 4.11 shape — the list and the detail page
                    # disagreeing about the same action. `Exists` rather than a sixth `Count`
                    # subquery, so it costs one correlated semi-join that stops at the first match
                    # instead of aggregating the whole child table.
                    has_inquiries=models.Exists(
                        PortalOrderInquiry.objects.filter(
                            tenant=models.OuterRef("tenant_id"),
                            portal_account=models.OuterRef("pk"))),
                    # No Coalesce: NULL is the ANSWER here ("never signed in"), not a missing zero.
                    last_login_at=models.Subquery(_LAST_LOGIN_AT,
                                                  output_field=models.DateTimeField()),
                )
                # STATED, not inherited. It is Meta.ordering plus a `-id` tie-break, which makes it
                # a total order so page 2 is deterministic — `created_at` alone is not unique, and
                # two accounts enabled in the same second could otherwise swap pages between loads.
                .order_by("-created_at", "-id"))

    # The chips, over the unfiltered workspace. One aggregate for three of them...
    base = PortalAccount.objects.filter(tenant=request.tenant)
    stats = base.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(is_active=True)),
        inactive=Count("id", filter=Q(is_active=False)),
    )
    # ...and one query each for the two that are subquery-shaped. Both reuse the SAME expressions
    # the rows are annotated with, so a chip can never disagree with the column under it.
    stats["never_logged_in"] = (
        base.filter(is_active=True)
        .annotate(last_login_at=models.Subquery(_LAST_LOGIN_AT,
                                                output_field=models.DateTimeField()))
        .filter(last_login_at__isnull=True).count())
    stats["unlinked"] = (base.filter(is_active=True)
                         .annotate(linked_users=_linked_user_count())
                         .filter(linked_users=0).count())

    return crud_list(
        request, queryset, "scm/portal/portalaccount/list.html",
        # `notes` and `welcome_message` are deliberately NOT searched: the search box on this page
        # is for finding a customer, and matching an internal note would return an account whose
        # visible columns contain nothing the user typed, which reads as a bug.
        search_fields=["number", "customer__name", "support_email"],
        filters=[("is_active", "is_active", False),
                 ("stock_display", "stock_display", False),
                 ("catalog_scope", "catalog_scope", False),
                 ("price_basis", "price_basis", False),
                 # is_int=True -> the L11 guard above.
                 ("customer", "customer_id", True)],
        extra_context={
            # The same lists the form renders from, named directly rather than read back off
            # `_meta.get_field(...).choices` — that is what keeps "the filter offers exactly what
            # the column accepts" a fact rather than a coincidence.
            "stock_display_choices": STOCK_DISPLAY_CHOICES,
            "catalog_scope_choices": CATALOG_SCOPE_CHOICES,
            "price_basis_choices": PRICE_BASIS_CHOICES,
            "customers": _portal_customer_qs(request.tenant),
            "stats": stats,
        },
    )


# ======================================================================================= the CRUD
# @tenant_admin_required, matching `_delete` below and CRM's `customerportalaccess_create`, whose
# decorator comment reads "granting a customer a portal login that reads their cases is an IAM
# action". This row decides more than that one does: `show_credit_and_balance` publishes the
# workspace's AR balance, credit limit and payment terms to an outsider; `can_view_invoices`
# publishes the invoice history; `stock_display="exact_quantity"` plus `show_by_location` publishes
# per-warehouse quantities, which tells a competitor buying one pallet exactly where our position
# sits; and `catalog_scope="all_active"` plus `price_basis` publishes the catalogue and prices.
#
# At plain `@login_required` any member of the workspace — a warehouse clerk, an intern — could set
# all of that for any customer with no admin in the loop. The model's own help text says
# `show_credit_and_balance` is "exposed only when someone deliberately turns them on"; until this
# decorator, "someone" was anybody with a login. Gating DELETE while leaving CREATE and EDIT open
# guarded the cheap half of the decision and left the expensive one open (L27).
@tenant_admin_required
def portalaccount_create(request):
    """Switch the portal on for one customer. This row IS the configuration — there is no lifecycle.

    ``crud_create`` stamps the tenant, audits and refuses a tenant-less user; ``_need_tenant`` is
    still called first so the refusal lands back on this module's list rather than the dashboard.

    ``PortalAccountForm`` ALSO stamps the tenant onto the unsaved instance (``TenantUniqueMixin``),
    and that is not redundancy: ``crud_create`` assigns ``obj.tenant`` only AFTER ``is_valid()``, so
    without the form-side stamp both ``PortalAccount.clean()``'s cross-tenant ship-to guard and the
    ``("tenant", "customer")`` uniqueness check would validate an instance whose ``tenant_id`` is
    None — and the uniqueness one is the rule a user breaks by hand (enabling the same company
    twice), which without the mixin passes ``is_valid()`` and then raises an uncaught
    ``IntegrityError`` on ``save()``.

    Success returns to the LIST rather than the new detail page, matching every other scm create.
    It also happens to be the right answer for this form: ``default_ship_to`` is empty until the
    account has a customer to scope the addresses to, so the natural next step really is "save, find
    it, edit" — which is what the field's own help text tells the user.
    """
    if _need_tenant(request):
        return redirect("scm:portalaccount_list")
    return crud_create(request, form_class=PortalAccountForm,
                       template="scm/portal/portalaccount/form.html",
                       success_url="scm:portalaccount_list")


# @tenant_admin_required for the same reason as `_create` above — and MORE so, because edit is the
# verb that flips `show_credit_and_balance` from False to True on an account that already has a
# bound, active portal login reading it.
@tenant_admin_required
def portalaccount_edit(request, pk):
    """Change what this customer sees. Every field on the form is editable, always.

    There is no status ladder and no frozen state here, deliberately: the row is configuration
    rather than a document, so there is no history for an edit to rewrite. What an edit DOES do is
    take effect on the customer's very next page load — turning ``can_view_invoices`` off closes
    that surface immediately, because ``_portal_account()`` re-reads this row on every gated request
    rather than caching it into a session.

    ``activated_on`` is ``editable=False`` and absent from the form: it is evidence of when
    enablement first happened, stamped once by ``PortalAccount.save()`` and never restamped, so a
    deactivate/reactivate cycle cannot rewrite the adoption date the console reports.
    """
    return crud_edit(request, model=PortalAccount, pk=pk, form_class=PortalAccountForm,
                     template="scm/portal/portalaccount/form.html",
                     success_url="scm:portalaccount_list")


@login_required
def portalaccount_detail(request, pk):
    """The 360°: what this account is entitled to, who is bound to it, and what it has actually done.

    Context keys, exhaustively (the templates are written by a separate agent):

    * ``obj`` — the :class:`~apps.scm.models.PortalAccount`, with ``customer`` and
      ``default_ship_to`` joined. **``core.Address`` has ``kind`` / ``line1`` / ``city`` /
      ``country`` and NO postal-code field** — no label on this page may imply one exists.
    * ``entitlements`` — a list of dicts from :func:`_entitlements`, keys ``field`` / ``label`` /
      ``granted`` / ``help_text``. Render ``granted`` as ``badge-green`` vs ``badge-muted``; there
      is no ``badge-success`` (L33).
    * ``catalog_categories`` — a LIST of the ``scm.ItemCategory`` rows on the M2M (already
      evaluated; do not re-query it). Empty is normal unless ``obj.catalog_scope == "categories"``,
      which the form refuses to save with an empty set.
    * **Who can actually log in** — ``portal_users`` (a LIST of ``crm.CustomerPortalAccess`` rows
      for this customer, active ones first, each with ``portal_user`` joined — link them to
      ``crm:customerportalaccess_detail``; ``access.portal_user`` may be ``None``, which is a
      misconfigured binding worth showing rather than hiding), ``portal_users_truncated`` (bool) and
      ``linked_user_count`` (int — ACTIVE bindings only, from the model's own property, so the
      number here and the ``linked_users`` column on the list agree). **An account with
      ``linked_user_count == 0`` has nobody who can sign in**, however complete its configuration —
      say so on the page.
    * **Adoption** — ``last_login_at`` (``datetime`` or ``None``) and ``has_never_logged_in``
      (bool, straight off the model). ``None``/True renders as "Never signed in", never as a blank.
    * **Recent activity** — ``recent_activity`` (a LIST of :class:`PortalActivity`, newest first,
      capped at ``panel_limit``; badge class is each row's ``action_css``) and ``activity_count``
      (int, the account's whole log). The log is append-only: **no edit, no delete, no Actions
      column on these rows.**
    * **Live shares** — ``live_shares`` (a LIST of :class:`PortalDocumentShare` that are neither
      revoked nor expired, capped; badge class ``doc_type_css``), ``live_share_count`` and
      ``share_count`` (ints — every share ever published for this account, including dead ones).
      **``public_token`` must not be rendered here** — a share's link belongs on that share's own
      detail page and nowhere else.
    * **Open inquiries** — ``open_inquiries`` (a LIST of :class:`PortalOrderInquiry` with
      ``outcome="open"``, capped, with ``sales_order`` / ``case`` joined; each row also carries its
      own ``sla_state`` / ``sla_state_css`` and ``customer_status_label`` /
      ``customer_status_css`` — render the customer-facing status NEXT TO the internal one, never
      instead of it), ``open_inquiry_count`` and ``inquiry_count`` (int, all inquiries ever raised
      under this account — this is the number that blocks a delete).
    * ``panel_limit`` — the row cap the three panels were sliced at, so the page can say it is
      showing a window rather than a total.
    * ``can_delete`` (bool) — False when ``inquiry_count`` is non-zero, mirroring exactly what
      :func:`portalaccount_delete` refuses. Offering a button the view will refuse is the 4.11
      finding. Delete is ALSO tenant-admin only, so wrap it in
      ``{% if request.user.is_superuser or request.user.is_tenant_admin %}`` as well.

    **The standing note this page must carry:** the ``notify_on_*`` toggles and ``preferred_channel``
    are STORED PREFERENCES. 4.16 dispatches nothing — no email, no SMS, no webhook — exactly as
    ``SalesOrder.confirmation_sent_at`` and its siblings have sat unfired since 4.5. A page that
    shows three green "notify" chips without saying so is a page that promises a message nobody
    sends.
    """
    now = timezone.now()
    obj = get_object_or_404(
        PortalAccount.objects.select_related("customer", "default_ship_to"),
        pk=pk, tenant=request.tenant)

    # --- who can actually log in ------------------------------------------------------------------
    # The CRM side of the binding, read (never written) from here — 4.16 administers no login.
    # INACTIVE bindings are included on purpose: "this customer has three logins and all three are
    # switched off" is the exact diagnosis somebody opens this page to make, and a panel that
    # filtered them out would show an empty list under an account that looks fully configured.
    # Local import, following ReturnsManagement/Reports.py: SCM does not import CRM at module scope.
    from apps.crm.models import CustomerPortalAccess
    accesses = list(CustomerPortalAccess.objects
                    .filter(tenant=request.tenant, customer_party=obj.customer_id)
                    .select_related("portal_user")
                    .order_by("-is_active", "-created_at")[:MAX_PANEL_ROWS + 1])
    accesses_truncated = len(accesses) > MAX_PANEL_ROWS
    del accesses[MAX_PANEL_ROWS:]

    # --- the panels -------------------------------------------------------------------------------
    # Every one of these states `tenant=` even though it is reached through an object already proved
    # to be this workspace's. It narrows nothing and it is the house idiom for two reasons: it holds
    # the module-wide scoping rule mechanically, and PortalActivity's own Meta says its
    # (tenant, portal_account, created_at) index has tenant as the LEADING column — a query through
    # the related manager alone cannot open it and falls back to a filesort.
    # Fetch MAX+1 and only pay for the COUNT when the slice actually hid something — otherwise the
    # list length IS the count, and a round trip to learn what we already hold is a query for
    # nothing. `portaldocumentshare_detail` already does it this way; this is that shape copied.
    recent_activity = list(obj.activities.filter(tenant=request.tenant)
                           .select_related("user")[:MAX_PANEL_ROWS + 1])
    activity_truncated = len(recent_activity) > MAX_PANEL_ROWS
    del recent_activity[MAX_PANEL_ROWS:]
    activity_count = (obj.activities.filter(tenant=request.tenant).count()
                      if activity_truncated else len(recent_activity))

    live_shares = list(obj.document_shares.filter(_live_share_q(now), tenant=request.tenant)
                       [:MAX_PANEL_ROWS])
    # ONE aggregate for both share figures rather than two counts: "3 of 11 still readable" is the
    # sentence an audit asks for, and the pair must be computed against the same snapshot.
    share_stats = obj.document_shares.filter(tenant=request.tenant).aggregate(
        total=Count("id"), live=Count("id", filter=_live_share_q(now)))

    open_inquiries = list(obj.inquiries.filter(tenant=request.tenant, outcome="open")
                          .select_related("sales_order", "case")[:MAX_PANEL_ROWS])
    inquiry_stats = obj.inquiries.filter(tenant=request.tenant).aggregate(
        total=Count("id"), open=Count("id", filter=Q(outcome="open")))

    return render(request, "scm/portal/portalaccount/detail.html", {
        "obj": obj,

        "entitlements": _entitlements(obj),
        # Evaluated here rather than left as `obj.catalog_categories.all` in the template, so the
        # page's query count is decided in the view and stays visible to whoever reads it.
        "catalog_categories": list(obj.catalog_categories.all()),

        "portal_users": accesses,
        "portal_users_truncated": accesses_truncated,
        # The model's own property, deliberately: ONE row, ONE query, and it guarantees this number
        # is the same fact the list's `linked_users` annotation computes in SQL. (The list may not
        # do this — see the module docstring.)
        "linked_user_count": obj.linked_user_count,

        # Read off the panel we already fetched rather than paid for again: `recent_activity` is
        # newest-first and unfiltered by action, so the first login row in it IS the last login...
        # except when the window is full of newer non-login rows, which is why this asks the
        # database directly. One indexed query for the console's headline fact is the right price.
        "last_login_at": (PortalActivity.objects
                          .filter(tenant=request.tenant, portal_account=obj,
                                  action=LOGIN_ACTION)
                          .values_list("created_at", flat=True).first()),
        "has_never_logged_in": obj.has_never_logged_in,

        "recent_activity": recent_activity,
        "activity_count": activity_count,

        "live_shares": live_shares,
        "live_share_count": share_stats["live"] or 0,
        "share_count": share_stats["total"] or 0,

        "open_inquiries": open_inquiries,
        "open_inquiry_count": inquiry_stats["open"] or 0,
        "inquiry_count": inquiry_stats["total"] or 0,

        "panel_limit": MAX_PANEL_ROWS,

        # The exact condition portalaccount_delete enforces — one statement of the rule, read by the
        # button and by the route behind it, so the two cannot disagree (the 4.10 finding).
        "can_delete": not inquiry_stats["total"],
    })


@tenant_admin_required
@require_POST
def portalaccount_delete(request, pk):
    """Delete a portal account — refused while inquiries reference it, and loud about the rest.

    **Read the consequence before the code.** ``PortalOrderInquiry.portal_account`` is ``PROTECT``,
    but ``PortalDocumentShare.portal_account`` and ``PortalActivity.portal_account`` are both
    ``CASCADE`` — so a delete that gets through destroys the entire share register and the whole
    append-only customer read log for this customer. That log is the only thing that can answer "we
    published the POD on the 3rd and you downloaded it on the 4th", and nothing reconstructs it.
    Hence: admin-gated, counted before the fact, and stated out loud afterwards.

    **The right move is almost always ``is_active=False``**, and both refusals say so. Deactivating
    is not a soft-delete dressed up: ``_portal_account()`` puts ``is_active`` IN the resolver's
    lookup, so one save shuts the customer's portal — every gated page, every live share link —
    while leaving every row of evidence readable.

    **Two guards for one hazard, on purpose.** The pre-check produces the sentence a user can act on
    ("4 inquiries reference this account"); the ``ProtectedError`` catch is what stops an inquiry
    filed between the check and the delete from becoming an uncaught 500 on a mainline delete path
    (the 4.10 ``currency_delete`` finding, priced in advance rather than after). The catch is
    generic rather than an enumeration of models: nothing but ``PortalOrderInquiry`` protects this
    table today, and an enumeration would go stale silently — as a 500.

    ``transaction.atomic()`` wraps the delegated delete so the audit row ``crud_delete`` writes
    BEFORE deleting rolls back with a delete that then fails, rather than recording a deletion that
    did not happen.
    """
    obj = get_object_or_404(PortalAccount.objects.select_related("customer"),
                            pk=pk, tenant=request.tenant)

    inquiries = obj.inquiries.filter(tenant=request.tenant).count()
    if inquiries:
        messages.error(
            request,
            f"{obj.number} is referenced by {inquiries} order inquiry/inquiries and cannot be "
            "deleted — an inquiry is the record of an argument about an order, and it must keep the "
            "account it was raised under. Untick 'Active' on this account instead: that closes the "
            "customer's portal and every live document link immediately, and keeps the trail.")
        return _detail(pk)

    # Counted BEFORE the delete, while the rows still exist to be counted.
    shares = obj.document_shares.filter(tenant=request.tenant).count()
    activities = obj.activities.filter(tenant=request.tenant).count()
    label = f"{obj.number} · {obj.customer}"

    try:
        with transaction.atomic():
            response = crud_delete(request, model=PortalAccount, pk=pk,
                                   success_url="scm:portalaccount_list")
    except ProtectedError as exc:
        blockers = sorted({protected._meta.verbose_name for protected in exc.protected_objects})
        messages.error(
            request,
            f"{obj.number} is still referenced by {', '.join(blockers)} and cannot be deleted — "
            "untick 'Active' instead, which closes the portal without destroying the record.")
        return _detail(pk)

    # No second success banner: `crud_delete` already flashed one, and two green bars for one action
    # is the 4.13 double-message finding. The name of what went is carried by the info line below,
    # which is the one that actually has something to say.
    if shares or activities:
        messages.info(
            request,
            f"Removed with {label}: {shares} document share(s) and {activities} portal activity "
            "row(s). Any link already sent out for those shares is now dead, and the activity log "
            "was append-only — it cannot be reconstructed.")
    return response
