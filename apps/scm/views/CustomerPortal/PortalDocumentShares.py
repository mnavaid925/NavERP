"""SCM 4.16 Customer Portal — ``PortalDocumentShare`` views: the share register and the kill switch.

**This is the staff side of the sub-module's access-control table.** Every other 4.16 page renders a
projection of rows the customer already owns; a share hands out a *file*, sometimes to a bearer who
is not logged in at all. So these five CRUD routes plus one verb are not ordinary master-data
screens — they are the console where somebody grants, times out and kills read access to another
company's paperwork, and the decisions below are all about who may do which of those.

--------------------------------------------------------------------------------------------------
THE TOKEN NEVER REACHES A PAGE, A LOG LINE OR A MESSAGE
--------------------------------------------------------------------------------------------------
``PortalDocumentShare.public_token`` is a bearer credential (``secrets.token_urlsafe(32)``, minted
once in ``save()``), and it is the only thing standing between a URL and a customer's documents.
Nothing in this module puts it — or a URL built from it — into a template context, a
``messages.*`` string or an ``AuditLog.changes`` dict. Both querysets below ``.defer("public_token")``
so the staff pages do not even *load* the column.

**The defer is exposure reduction, not an access control** — a template that named
``obj.public_token`` would simply re-fetch it — which is why the rule is also stated where the
templates are written (§6: the list page must not render the token in a column or a tooltip).

**There is deliberately no "copy link" context key, on the list page OR the detail page.** Such a key
would put the credential into rendered staff HTML, and from there into browser cache, screenshots,
print-to-PDF, and any proxy that logs response bodies — for a value nobody can rotate. It is also
unnecessary: the customer reaches a live share through their own gated portal documents page, which
is where ``scm:portal_document_download`` is legitimately linked. If a hand-out affordance is ever
genuinely needed, it must be its own ``@tenant_admin_required`` view that returns the URL on demand
and writes an audit row recording the reveal — never a context variable on a page anyone can
screenshot.

--------------------------------------------------------------------------------------------------
# WARNING (security) — WHY ``portaldocumentshare_edit`` IS ``@tenant_admin_required``
--------------------------------------------------------------------------------------------------
``expires_at`` and ``revoked_at`` are two halves of ONE control: *how much longer may this bearer
token fetch this customer's document?* ``revoked_at`` is ``editable=False`` and written only by
:func:`portaldocumentshare_revoke`, which is ``@require_POST`` + ``@tenant_admin_required``.
``expires_at`` is on ``PortalDocumentShareForm``. Left at plain ``@login_required``, edit would let
any tenant member **blank ``expires_at`` — blank means never expires — on a share only an admin may
revoke**. That is not a milder version of revoking: an unrevokable-in-practice permanent link is
strictly worse than an un-revoked one, and it is precisely the permanent read access ``expires_at``
was added to abolish (4.10's documented residual risk, ``ReturnsManagement/Reports.py:41-42``). The
full argument lives in ``apps/scm/forms/CustomerPortal/PortalDocumentShares.py``'s module docstring;
this decorator is the other half of it, and **removing it re-opens the hole the column exists to
close.**

The general shape, worth carrying to the next module: *any field a form exposes whose authoritative
writer is a staff-gated verb is a privilege-escalation bypass by construction.*

:func:`portaldocumentshare_delete` is admin-gated for the neighbouring reason — deleting a share
kills the link (fine) **and destroys the download evidence with it** (not fine), so it is revoke plus
loss of the record, and it cannot sit below revoke on the ladder.

**# WARNING (residual, stated rather than hidden): ``portaldocumentshare_create`` is deliberately
left at plain ``@login_required``, so an ordinary member can still MINT a share with a blank
``expires_at``.** Publishing a document to a customer is the module's ordinary business operation and
gating it would make 4.16 an admin-only tool. The two paths are not equivalent, which is what makes
the split defensible: a create is *visible* — it writes a ``create`` audit row and lands at the top
of a register ordered ``-created_at``, wearing its state chip — whereas an edit silently grants
immortality to a months-old row that moves nowhere on any screen and that nobody is looking at. If a
tenant wants shares admin-only end to end, the fix is one decorator on the create view; it is a
policy choice, not a missing guard.

--------------------------------------------------------------------------------------------------
THE STATE FILTER AND THE STATE CHIP ARE THE SAME SQL
--------------------------------------------------------------------------------------------------
``live`` / ``expired`` / ``revoked`` is a question about two nullable timestamps *and the clock*, not
a stored column, and it must never become one: the answer changes by time passing, so a column would
need something running every minute to stay true — and stale in the direction that says a dead link
is live. :func:`_apply_state_filter` (the WHERE clause) and :func:`_annotate_state` (the CASE
expressions the chip renders) are built from **the same three ``Q`` objects**, so a row the filter
puts in a bucket cannot render a different bucket's chip. That is the ``_effective_state`` /
``_apply_effective_filter`` pattern from 4.14, with the Python half deleted rather than duplicated —
the detail view annotates the very same expressions onto its single row, so this module has exactly
one definition of the state and no second dialect to keep in sync.

**"Expires soon" is a REFINEMENT of ``live``, never a fourth bucket.** ``?state=live`` returns rows
whose ``share_state`` is ``live``, some of which wear the amber "Expires soon" chip; the filter
vocabulary stays the three values §3.3 pins. The label and the colour are annotated onto the row
because a Django template cannot subscript a dict, and the alternative — a template picking its own
badge class — is how the same value ends up styled two ways on two pages.

Badge classes are the colour-named theme.css six only: ``badge-green / badge-red / badge-amber /
badge-info / badge-muted / badge-slate``. ``badge-success`` / ``badge-danger`` / ``badge-warning``
**do not exist in this project and render as completely unstyled text** (L33).

--------------------------------------------------------------------------------------------------
Context-var contract (pinned, L7 — the templates are written by a separate agent, so EVERY key each
page consumes is listed here, not merely the list variable):
--------------------------------------------------------------------------------------------------
* ``scm/portal/portaldocumentshare/list.html`` — ``object_list`` + ``page_obj`` + ``q`` (from
  ``crud_list``). **Each row carries four annotations**: ``share_state`` (``live`` / ``expired`` /
  ``revoked`` — the filter vocabulary), ``expiring_soon`` (bool; only ever True on a ``live`` row),
  ``state_label`` and ``state_css`` (render these two as the chip — never derive a colour in the
  template). Filter context: ``doc_type_choices`` and ``state_choices`` (lists of ``(value, label)``
  pairs), ``portal_accounts`` (the queryset behind the pk dropdown — compare with
  ``|stringformat:"d"``, NEVER ``|slugify``) and ``state`` (the RESOLVED bucket, ``""`` when the
  param is absent or junk — bind the select to THIS, not to ``request.GET.state``). Header chips:
  ``stats``, a dict with keys ``live`` / ``expiring`` / ``expired`` / ``revoked`` / ``never_opened``,
  plus ``expiring_soon_days``. Filter params: ``q`` / ``doc_type`` / ``state`` (strings) and
  ``portal_account`` (pk).
* ``scm/portal/portaldocumentshare/form.html`` — ``form`` + ``is_edit`` (+ ``obj`` on the edit path),
  plus ``pointer_field_names`` (the six pointer field names, in declaration order — group those
  inputs and state the exactly-one rule ABOVE them), ``doc_type_matrix`` (a list of dicts with keys
  ``doc_type`` / ``label`` / ``pointer`` / ``pointer_label``) and ``max_expiry_days``.
* ``scm/portal/portaldocumentshare/detail.html`` — see :func:`portaldocumentshare_detail`'s docstring
  for the full key list; it is long enough to belong beside the code that builds it.

``portaldocumentshare_edit``, ``_delete`` and ``_revoke`` are ``@tenant_admin_required``, so wrap
those three buttons in ``{% if request.user.is_superuser or request.user.is_tenant_admin %}`` —
showing a member a button they will 403 on is the 4.11 finding. Confirm text uses the ``PDS-`` number
and nothing else: an apostrophe or an interpolated user string inside ``onclick="return confirm(…)"``
is decoded by the HTML parser before the JS engine sees it and silently disables the guard (L42).
"""
import datetime

from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._helpers import _need_tenant

# Not in `_common` (nothing shipped in scm has needed a CASE expression in a list query before) and
# imported AFTER the star import so these names cannot be shadowed by it.
from django.db.models import BooleanField, Case, CharField, Value, When
from django.urls import NoReverseMatch, reverse

from apps.scm.forms import PortalDocumentShareForm
from apps.scm.models import (MAX_SHARE_EXPIRY_DAYS, PortalAccount, PortalActivity,
                             PortalDocumentShare, SHARE_DOC_TYPE_CHOICES, SHARE_DOC_TYPE_FIELDS,
                             SHARE_POINTER_FIELDS)

#: How far ahead a live share starts wearing the amber "Expires soon" chip. A constant rather than
#: something derived per row: the question the register answers is "what do I have to renew or let
#: die this week", and a horizon that varied by row could not be totalled into the header chip.
#: Seven days because that is one working week of notice — long enough to act, short enough that the
#: amber count is a real to-do list rather than permanent decoration.
EXPIRING_SOON_DAYS = 7

#: The three derived buckets, and the ONLY values ``?state=`` accepts. **Not a model vocabulary and
#: never a column** — see the module docstring: the answer changes by the clock moving, so storing it
#: would need a job to keep it true and would go stale in the dangerous direction.
SHARE_STATE_CHOICES = [
    ("live", "Live — can be fetched now"),
    ("expired", "Expired — lapsed on its own"),
    ("revoked", "Revoked — killed by an admin"),
]

#: The chip words. Short here, unlike the select's labels above: a badge sits in a table cell and the
#: explanation belongs in the filter, not repeated on every row.
SHARE_STATE_LABELS = {
    "live": "Live",
    "expired": "Expired",
    "revoked": "Revoked",
}

#: Colour per bucket. Only the six classes that exist in theme.css (L33). Green is "currently valid",
#: matching ``STOCK_BAND_CSS["in"]`` — the register's normal, working state. **Red is deliberately
#: unused here**: red is reserved for a row somebody must act on, and neither an expired nor a
#: revoked share needs anything doing to it. The one row that does need action is the live share
#: about to lapse, and that is the amber one.
SHARE_STATE_CSS = {
    "live": "badge-green",
    "expired": "badge-slate",
    "revoked": "badge-muted",
}

#: The refinement chip for a live share inside :data:`EXPIRING_SOON_DAYS`. Its ``share_state`` is
#: still ``live`` — see the module docstring.
EXPIRING_SOON_LABEL = "Expires soon"
EXPIRING_SOON_CSS = "badge-amber"

#: pointer -> the url name of the page that OWNS that record. 4.16 owns none of the six: the
#: invoice belongs to ``accounting``, the contract to ``crm``, the rest to their own scm sub-modules,
#: and the detail page LINKS OUT rather than re-rendering somebody else's row. Resolved through
#: :func:`_target_url`, which swallows ``NoReverseMatch`` — a url renamed in another app must degrade
#: to an un-linked label, never a 500 on a page that only wanted to show a name.
TARGET_URL_NAMES = {
    "document": "core:document_detail",
    "invoice": "accounting:invoice_detail",
    "shipment": "scm:shipment_detail",
    "trade_document": "scm:tradedocument_detail",
    "contract": "crm:contractdocument_detail",
    "quality_inspection": "scm:qualityinspection_detail",
}

#: How many activity rows the detail page's evidence panel shows. A queryset SLICE, so the DATABASE
#: bounds what is FETCHED rather than what is rendered (L40 §1). One more than the cap is read so the
#: page can say it is showing a window without paying for a second COUNT.
MAX_ACTIVITY_ROWS = 25

#: Joined by both list and detail. The six pointers are select_related TOGETHER because
#: ``target_label`` walks whichever one is set: without them a 15-row page costs 15 extra queries
#: (one per row — only ever one pointer is populated), with them it costs six LEFT JOINs on one
#: query. The 4.13 ``asset_list`` finding, in its other direction.
_TARGET_JOINS = ("portal_account", "portal_account__customer") + SHARE_POINTER_FIELDS


# ================================================================================== state — one rule
# The three Q objects below are THE definition of the three buckets. Both the WHERE clause
# (_apply_state_filter) and the CASE expressions (_annotate_state) are built from these same
# objects, which is what makes "the filter and the badge cannot disagree" a fact about the code
# rather than a promise in a comment.

#: Revoked wins over everything, including an expiry that has also passed: revocation is a deliberate
#: act with a timestamp somebody may have to defend, and collapsing it into "expired" would erase who
#: decided what.
_REVOKED_Q = Q(revoked_at__isnull=False)


def _live_q(now):
    """Neither revoked nor lapsed. ``expires_at`` NULL is live forever — that is what blank means."""
    return Q(revoked_at__isnull=True) & (Q(expires_at__isnull=True) | Q(expires_at__gt=now))


def _expired_q(now):
    """Lapsed on its own and not revoked.

    The ``revoked_at__isnull=True`` half is redundant inside :func:`_annotate_state` (the CASE tests
    revoked first) and **required** here, where this predicate is used standalone as a filter — a
    share that was revoked and then also lapsed must appear under ``revoked``, in exactly one bucket,
    or the three counts stop summing to the register.
    """
    return Q(revoked_at__isnull=True, expires_at__lte=now)


def _expiring_q(now, horizon):
    """Live, has a date, and that date is inside the notice window — the amber refinement."""
    return Q(revoked_at__isnull=True, expires_at__gt=now, expires_at__lte=horizon)


def _annotate_state(queryset, now):
    """Attach ``share_state`` / ``expiring_soon`` / ``state_label`` / ``state_css`` to every row.

    Four CASE expressions in the SELECT rather than a Python pass over the page, for a reason that is
    structural rather than about speed: ``crud_list`` paginates AND renders in one call, so there is
    no seam at which a view could hang a chip on each row (the 4.14 ``effective_chip`` trick needs a
    hand-rolled ``paginate``). Annotating keeps the shipped ``crud_list`` contract intact and — the
    part that actually matters — computes the chip from the same predicates the filter uses, in the
    same statement, so the two can never drift.

    The words and the colour are annotated rather than handed over as dicts because a Django template
    cannot subscript one; the alternative is a template inventing its own badge class, which is how a
    value ends up styled one way on the list and another on the detail page (L33).

    Order is revoked -> expired -> expiring -> live and the first two are mutually exclusive with the
    third by construction; the order is stated anyway, because a reader must not have to prove that
    to know which chip a doubly-dead row wears.
    """
    horizon = now + datetime.timedelta(days=EXPIRING_SOON_DAYS)
    revoked, expired, expiring = _REVOKED_Q, _expired_q(now), _expiring_q(now, horizon)
    return queryset.annotate(
        share_state=Case(
            When(revoked, then=Value("revoked")),
            When(expired, then=Value("expired")),
            default=Value("live"),
            output_field=CharField(),
        ),
        expiring_soon=Case(
            When(expiring, then=Value(True)),
            default=Value(False),
            output_field=BooleanField(),
        ),
        state_label=Case(
            When(revoked, then=Value(SHARE_STATE_LABELS["revoked"])),
            When(expired, then=Value(SHARE_STATE_LABELS["expired"])),
            When(expiring, then=Value(EXPIRING_SOON_LABEL)),
            default=Value(SHARE_STATE_LABELS["live"]),
            output_field=CharField(),
        ),
        state_css=Case(
            When(revoked, then=Value(SHARE_STATE_CSS["revoked"])),
            When(expired, then=Value(SHARE_STATE_CSS["expired"])),
            When(expiring, then=Value(EXPIRING_SOON_CSS)),
            default=Value(SHARE_STATE_CSS["live"]),
            output_field=CharField(),
        ),
    )


def _apply_state_filter(queryset, value, now):
    """Narrow to one bucket. Returns ``(queryset, resolved_value)``.

    A junk or absent ``?state=`` narrows NOTHING and is echoed back as ``""`` — the ``crud_list``
    posture on a bad filter (L11): skip it, never 500, and never leave the select claiming a bucket
    that did not happen. ``?state=live%00`` and ``?state=<script>`` take the same path as
    ``?state=banana``: no branch matches, so nothing is filtered.
    """
    if value == "live":
        return queryset.filter(_live_q(now)), value
    if value == "expired":
        return queryset.filter(_expired_q(now)), value
    if value == "revoked":
        return queryset.filter(_REVOKED_Q), value
    return queryset, ""


# ================================================================================== small helpers
def _detail(pk):
    """The one redirect target every verb and refusal in this module answers with."""
    return redirect("scm:portaldocumentshare_detail", pk=pk)


def _target_url(share):
    """A link to the page that OWNS this share's target, or ``None``.

    ``None`` is a first-class answer twice over: the pointer may be empty (every pointer is
    ``SET_NULL``, so a deleted target is a real state) and another app may have renamed its route.
    Neither is worth a 500 on a page whose only ambition was to print a name, so ``NoReverseMatch``
    is swallowed and the template falls back to an un-linked ``target_label``.
    """
    pointer = share.pointer_field
    name = TARGET_URL_NAMES.get(pointer)
    target = share.target if name else None
    if target is None:
        return None
    try:
        return reverse(name, args=[target.pk])
    except NoReverseMatch:
        return None


def _form_context():
    """The static help the create and edit pages need to state the exactly-one rule ABOVE the fields.

    Built from ``SHARE_DOC_TYPE_FIELDS`` — the same table ``clean()`` validates against and the form
    scopes its dropdowns from — so the matrix printed on the page cannot disagree with the rule that
    will refuse the save. Three hand-written copies of that table would be three chances to disagree
    about which column a ``coa`` lives in (the model docstring's rule 1).
    """
    labels = dict(SHARE_DOC_TYPE_CHOICES)
    return {
        # Strings, not BoundFields: `crud_create` builds the form itself, so extra_context is
        # computed before a form object exists. The template groups the six with
        # `{% if field.name in pointer_field_names %}`.
        "pointer_field_names": list(SHARE_POINTER_FIELDS),
        "doc_type_matrix": [
            {"doc_type": doc_type,
             "label": labels.get(doc_type, doc_type),
             "pointer": pointer,
             "pointer_label": PortalDocumentShare.POINTER_LABELS[pointer]}
            for doc_type, pointer in SHARE_DOC_TYPE_FIELDS.items()
        ],
        "max_expiry_days": MAX_SHARE_EXPIRY_DAYS,
    }


# ======================================================================================= the list
@login_required
def portaldocumentshare_list(request):
    """The share register: what was handed out, whether it can still be fetched, and how often it was.

    EVERY filter is applied BEFORE ``crud_list`` paginates — ``?state=`` here by hand because it is a
    two-column comparison against the clock rather than an equality, ``doc_type`` and
    ``portal_account`` through ``crud_list``'s own spec. A filter applied afterwards would page over
    the unfiltered set and quietly show the wrong rows on page 2.

    ``portal_account`` goes through the ``is_int=True`` spec, which applies the L11 guard:
    ``?portal_account=abc``, ``?portal_account=²`` (a Unicode superscript — ``isdigit()`` says yes,
    ``int()`` says no) and ``?portal_account=99999999999999999999`` (converts fine, then overflows
    inside the driver) all SKIP the filter rather than raise on a URL anybody can type into the
    address bar.

    ``.defer("public_token")`` — the credential is not loaded for a page that must never print it.
    See the module docstring: this reduces exposure, it does not enforce anything.

    ``stats`` is counted over the WHOLE workspace rather than the filtered page, on purpose: "4 live
    shares expiring this week" is a fact somebody has to act on, and recomputing it per filter would
    make the number move as you browse. ``never_opened`` is the one worth having beside the others —
    a live share nobody has ever fetched is either a link that never reached the customer or a
    document they did not need, and both are worth knowing before renewing it.
    """
    now = timezone.now()

    queryset = (PortalDocumentShare.objects.filter(tenant=request.tenant)
                .select_related(*_TARGET_JOINS)
                .defer("public_token")
                # STATED, not inherited. Meta.ordering is `-created_at` alone, which is not a total
                # order — two shares published in the same tick would page nondeterministically. The
                # `-id` tie-break is what makes page 2 reproducible.
                .order_by("-created_at", "-id"))

    queryset, state = _apply_state_filter(queryset, (request.GET.get("state") or "").strip(), now)
    queryset = _annotate_state(queryset, now)

    horizon = now + datetime.timedelta(days=EXPIRING_SOON_DAYS)
    stats = PortalDocumentShare.objects.filter(tenant=request.tenant).aggregate(
        live=Count("id", filter=_live_q(now)),
        expiring=Count("id", filter=_expiring_q(now, horizon)),
        expired=Count("id", filter=_expired_q(now)),
        revoked=Count("id", filter=_REVOKED_Q),
        never_opened=Count("id", filter=_live_q(now) & Q(first_viewed_at__isnull=True)),
    )

    return crud_list(
        request, queryset, "scm/portal/portaldocumentshare/list.html",
        # `title` is the customer-facing label and `number` is what staff quote at each other. The
        # customer's own name is searched through the account so "everything we ever sent Acme" is
        # one query in the search box rather than a two-step through the account list.
        search_fields=["title", "number", "portal_account__customer__name"],
        filters=[("doc_type", "doc_type", False),
                 # is_int=True -> the L11 guard above.
                 ("portal_account", "portal_account_id", True)],
        extra_context={
            "doc_type_choices": SHARE_DOC_TYPE_CHOICES,
            "state_choices": SHARE_STATE_CHOICES,
            # The RESOLVED bucket, not request.GET — a junk `?state=soon` narrowed nothing, so the
            # select must show "All" rather than an option that did not happen.
            "state": state,
            # Ordered by customer name rather than by Meta.ordering (`-created_at`): newest-first is
            # right for a register and useless in a picker somebody is scanning for a company.
            # select_related because PortalAccount.__str__ walks `customer`, and an unjoined dropdown
            # is one query per option.
            "portal_accounts": (PortalAccount.objects.filter(tenant=request.tenant)
                                .select_related("customer").order_by("customer__name", "number")),
            "stats": stats,
            "expiring_soon_days": EXPIRING_SOON_DAYS,
        },
    )


# ======================================================================================= the CRUD
@login_required
def portaldocumentshare_create(request):
    """Publish one document to one portal account.

    Hand-rolled rather than delegated to ``crud_create``, for two reasons that both have to hold:

    1. **``shared_by`` must be stamped server-side.** It is ``editable=False`` and its help text says
       so — "who published this" is evidence, and a value a POST body can carry is not evidence.
       ``crud_create`` has no hook for it.
    2. **The instance must already carry the tenant when ``full_clean()`` runs.** ``crud_create``
       assigns ``obj.tenant`` only AFTER ``is_valid()``, and ``TenantModelForm`` does not stamp it
       either — so on the create path ``PortalDocumentShare.clean()``'s block (d) would find
       ``tenant_id is None`` and **skip itself**. Block (d) is the authorisation rule of the whole
       sub-module (*the target belongs to this tenant AND to this account's customer*), and create is
       exactly the path that would otherwise publish customer B's invoice to customer A's portal.
       The form narrows its six pointer dropdowns to the account's own records, but a narrowed
       dropdown has never held against a crafted POST — the model check is the one that does, and
       passing a tenant-stamped ``instance=`` is what lets it run. This is the same conclusion 4.14
       reached for ``LaborStandardForm``'s overlap guard, arrived at from the other side.

    Redirects to the DETAIL page rather than the list: the thing a person needs immediately after
    publishing is the expiry, the audience and the revoke button, all of which are on that page.
    """
    if _need_tenant(request):
        return redirect("scm:portaldocumentshare_list")

    if request.method == "POST":
        form = PortalDocumentShareForm(request.POST, request.FILES, tenant=request.tenant,
                                       instance=PortalDocumentShare(tenant=request.tenant))
        if form.is_valid():
            obj = form.save(commit=False)
            # Both already true on the instance handed to the form; restated because this is the
            # line a reader checks, and because `commit=False` returns whatever the form built.
            obj.tenant = request.tenant
            obj.shared_by = request.user
            obj.save()
            # No `changes` diff on a create — the row IS the diff, and a dict of every field would
            # be the one place a future editable pointer could smuggle something sensitive into the
            # immutable log. `public_token` is `editable=False` so it can never be in `changed_data`
            # anyway (the model docstring's rule 4), and this path does not build one at all.
            write_audit_log(request.user, obj, "create")
            messages.success(
                request,
                f"{obj.number} published to {obj.portal_account.customer}. The link is a bearer "
                "credential — anyone it is forwarded to can fetch this document until it expires or "
                "is revoked.")
            return _detail(obj.pk)
    else:
        # `?portal_account=<pk>` pre-selects the audience, and that is not merely a convenience:
        # the six pointer dropdowns can only be narrowed to "this customer's own documents" once
        # the account is known, so without it the unbound form legitimately offers nothing to
        # share. The account detail page links here with the param for exactly that reason; a
        # visitor arriving without one picks the account, submits, and the bound re-render fills
        # the pointers in. `as_db_int` is applied inside the form, so junk in the query string
        # leaves the dropdowns empty rather than raising.
        form = PortalDocumentShareForm(tenant=request.tenant,
                                       initial={"portal_account": request.GET.get("portal_account")},
                                       instance=PortalDocumentShare(tenant=request.tenant))

    ctx = {"form": form, "is_edit": False}
    ctx.update(_form_context())
    return render(request, "scm/portal/portaldocumentshare/form.html", ctx)


@tenant_admin_required
def portaldocumentshare_edit(request, pk):
    """Edit a share — **admin-only, and that is a security requirement, not a convention.**

    ``expires_at`` is on this form and ``revoked_at`` is written only by the admin-gated revoke verb.
    They answer the same question, so they are gated the same way; at plain ``@login_required`` any
    tenant member could blank ``expires_at`` (blank = never expires) on a share only an admin may
    revoke. The full argument is in this module's docstring and in the form's, and it is the reason
    this decorator differs from every other ``_edit`` in ``apps/scm``. **Do not "normalise" it.**

    ``crud_edit`` is safe here where ``crud_create`` was not: it fetches the row with
    ``tenant=request.tenant`` and hands it to the form as ``instance``, so ``tenant_id`` is set
    before ``full_clean()`` and the ownership block runs. It also records ``_changed(form)`` into
    ``AuditLog.changes`` — which is what makes an extension of ``expires_at`` a visible act rather
    than a silent one, and is half of why the gate above is sufficient rather than merely nominal.

    **Editing a revoked share is allowed and is a no-op for access.** The download view's state guard
    lives in the LOOKUP (``revoked_at__isnull=True``), so no expiry date can bring a revoked link
    back. Refusing the edit would add a rule that protects nothing and would block correcting a
    title on a row somebody still has to read in a dispute.
    """
    return crud_edit(request, model=PortalDocumentShare, pk=pk,
                     form_class=PortalDocumentShareForm,
                     template="scm/portal/portaldocumentshare/form.html",
                     success_url="scm:portaldocumentshare_list",
                     extra_context=_form_context())


@login_required
def portaldocumentshare_detail(request, pk):
    """The grant, its lifetime, and the proof of what was fetched.

    Hand-rolled rather than ``crud_detail`` because the row needs the state annotations — the same
    CASE expressions the list uses, so the chip on this page and the chip in the register are
    literally one definition (see the module docstring).

    ``trade_document__document`` is joined on top of the six pointers: ``file_field`` resolves
    ``document.file`` for that type, which is one hop further than the pointer itself, and without
    the join ``has_file`` would cost an extra query on exactly the rows that have a file.

    Context keys, exhaustively (the templates are written by a separate agent):

    * ``obj`` — the :class:`~apps.scm.models.PortalDocumentShare`, carrying the four state
      annotations ``share_state`` (``live`` / ``expired`` / ``revoked``), ``expiring_soon`` (bool),
      ``state_label`` and ``state_css``. Render the chip from the last two; the type badge is
      ``obj.doc_type_css`` with ``obj.get_doc_type_display``. **``obj.public_token`` is deferred and
      must not be named by the template** — see the module docstring.
    * **The target** — ``pointer`` (which of the six columns is set: ``invoice`` / ``shipment`` /
      ``trade_document`` / ``contract`` / ``quality_inspection`` / ``document``, or ``""``),
      ``pointer_label`` (the human name of that column, ``""`` when there is none), ``target`` (the
      object itself, or ``None``), ``target_label`` (its own reference — a number or a name, never a
      storage path) and ``target_url`` (the owning app's detail page, or ``None`` — link only when
      it is not ``None``). ``target_missing`` is True when every pointer is NULL: all six are
      ``SET_NULL``, so a deleted target is a real state and not a bug, and the share should be
      revoked rather than left pointing at nothing.
    * **What the download does** — ``has_file`` (True when a file streams; False when the target is
      a RENDERED page instead — an invoice, a contract and a CoA have no file on disk, and a
      shipment records POD as a fact rather than a scan).
    * **Lifetime** — ``expires_in_days`` (int, or ``None`` when the share has no expiry or is
      already dead — print an em dash, never ``0``, which would read as "expires today"),
      ``max_expiry_days`` and ``expiring_soon_days`` (for the wording of the expiry card).
    * **Evidence** — ``activities`` (up to :data:`MAX_ACTIVITY_ROWS` ``PortalActivity`` rows for THIS
      share, newest first; each has ``created_at`` / ``action`` / ``get_action_display`` /
      ``action_css`` / ``user`` (may be ``None`` — an anonymous bearer is a real, recordable visitor)
      / ``ip_address`` / ``object_label``), ``activities_truncated`` (bool) and ``activity_count``.
      The counters on ``obj`` itself — ``download_count`` / ``first_viewed_at`` /
      ``last_downloaded_at`` — are the summary; this panel is the itemisation.
    * **Action gate** — ``can_revoke`` (False once already revoked; the verb's own guard is in the
      UPDATE's WHERE clause, so this only stops the page offering a button that would do nothing).
      Revoke, Edit and Delete are ALL tenant-admin only, so wrap all three in
      ``{% if request.user.is_superuser or request.user.is_tenant_admin %}`` as well.
    """
    now = timezone.now()
    queryset = _annotate_state(
        (PortalDocumentShare.objects.filter(tenant=request.tenant)
         .select_related(*_TARGET_JOINS, "trade_document__document", "shared_by")
         .defer("public_token")),
        now)
    obj = get_object_or_404(queryset, pk=pk)

    pointer = obj.pointer_field
    # The evidence panel. `document_share` is declared `related_name="+"`, so there is no reverse
    # accessor by design and the query is stated the long way; the explicit `tenant=` narrows
    # nothing (the share is already this workspace's) and is the house idiom because it is what
    # opens the (tenant, portal_account, created_at) index rather than the bare FK one.
    activities = list(PortalActivity.objects
                      .filter(tenant=request.tenant, document_share=obj)
                      .select_related("user")[:MAX_ACTIVITY_ROWS + 1])
    truncated = len(activities) > MAX_ACTIVITY_ROWS
    del activities[MAX_ACTIVITY_ROWS:]
    # The COUNT is only paid for when the slice actually hid something — otherwise the list length
    # IS the count, and a round trip to learn what we already hold is a query for nothing.
    activity_count = (PortalActivity.objects.filter(tenant=request.tenant, document_share=obj).count()
                      if truncated else len(activities))

    return render(request, "scm/portal/portaldocumentshare/detail.html", {
        "obj": obj,

        "pointer": pointer,
        "pointer_label": PortalDocumentShare.POINTER_LABELS.get(pointer, ""),
        "target": obj.target,
        "target_label": obj.target_label,
        "target_url": _target_url(obj),
        "target_missing": not pointer,

        "has_file": obj.file_field is not None,

        # None rather than 0 when there is nothing to count down: "no expiry" and "expires today"
        # are different facts and a shared `0` would merge them (the 4.11 lesson).
        "expires_in_days": ((obj.expires_at - now).days
                            if obj.share_state == "live" and obj.expires_at else None),
        "max_expiry_days": MAX_SHARE_EXPIRY_DAYS,
        "expiring_soon_days": EXPIRING_SOON_DAYS,

        "activities": activities,
        "activities_truncated": truncated,
        "activity_count": activity_count,

        # The exact condition the verb enforces — a second revoke updates 0 rows and says so, so
        # this only keeps the page from offering a button that cannot do anything.
        "can_revoke": not obj.is_revoked,
    })


@tenant_admin_required
@require_POST
def portaldocumentshare_delete(request, pk):
    """Delete a share — admin-gated, and almost always the wrong verb.

    **Deleting is revoke plus the destruction of the evidence.** Revoking kills the link and keeps
    ``download_count`` / ``first_viewed_at`` / ``last_downloaded_at`` — the three columns that make
    *"we published that POD on the 3rd and they downloaded it on the 4th"* defensible. Deleting
    removes those with the row, which is why it cannot sit on a lower rung than
    :func:`portaldocumentshare_revoke`: a member who may not kill a link certainly may not erase the
    record that it existed and was used. The message says so rather than leaving it to be discovered.

    ``PortalActivity.document_share`` is ``SET_NULL``, so the customer-side log SURVIVES this: each
    row keeps its ``object_label`` and its timestamp and merely loses the pointer. That is the whole
    reason the label is denormalised there — a log whose oldest rows read "downloaded a document"
    with no document is not evidence of anything.

    No state guard and no ``select_for_update``: unlike 4.14's status ladder there is no illegal
    starting state for a delete, so there is nothing for a lock to make atomic. The audit row is
    written before the delete, while the object still has a pk to record.
    """
    obj = get_object_or_404(
        PortalDocumentShare.objects.select_related("portal_account__customer").defer("public_token"),
        pk=pk, tenant=request.tenant)
    number, title, downloads = obj.number, obj.title, obj.download_count
    write_audit_log(request.user, obj, "delete")
    obj.delete()

    messages.success(request, f"{number} · {title} deleted. The link no longer resolves.")
    if downloads:
        messages.info(
            request,
            f"Its download record went with it — {downloads} retrieval(s) can no longer be proved "
            "from this row. The customer activity log keeps its own entries, which name the document "
            "but no longer point at the share. Revoking, rather than deleting, is what keeps that "
            "evidence intact.")
    return redirect("scm:portaldocumentshare_list")


# ========================================================================================= the verb
@tenant_admin_required
@require_POST
def portaldocumentshare_revoke(request, pk):
    """Kill the link. Admin-gated, POST-only, and idempotent by construction.

    Admin-gated because this is the module's access-control switch in the direction that matters
    least to the customer and most to us: an over-eager revoke is a support call, but the ABILITY to
    revoke is what makes handing out a bearer token defensible at all, and its counterpart
    ``expires_at`` is gated identically on the edit form (see the module docstring).

    **No lock, no re-read, no ``if not obj.revoked_at``.** ``PortalDocumentShare.revoke()`` is a
    single conditional UPDATE whose guard is in its own WHERE clause
    (``revoked_at__isnull=True``), so it is already TOCTOU-safe and there is nothing for a
    ``select_for_update`` to protect — unlike 4.14's status ladder, which reads a column, decides,
    and writes. Two admins pressing the button a moment apart cannot both "win": the second call
    updates 0 rows and returns False, which is why the revocation timestamp — evidence of when
    access actually stopped — can never be quietly moved forward.

    **The audit row is written only when this call is the one that revoked.** A second press must not
    leave an ``AuditLog`` entry claiming a revocation that did not happen; the log would then record
    two moments of stopping access, and only one of them would be true.

    ``obj.number`` and the customer's name are the only things in the messages. The token is not, and
    a revoke message is exactly the kind of place a "here is the dead link" convenience would put it.
    """
    obj = get_object_or_404(
        PortalDocumentShare.objects.select_related("portal_account__customer").defer("public_token"),
        pk=pk, tenant=request.tenant)

    if not obj.revoke(user=request.user):
        messages.info(
            request,
            f"{obj.number} was already revoked on {obj.revoked_at:%d %b %Y %H:%M}. Nothing changed — "
            "the first revocation is the one on the record.")
        return _detail(pk)

    # `changes` carries the action slug (matching the trail 4.12/4.13/4.14 leave, so the log stays
    # filterable) and the timestamp. It carries NOTHING ELSE: `public_token` would not be redacted
    # by `_SENSITIVE_AUDIT_FIELDS` — that list tests an EXACT name match on `token` — and the only
    # thing keeping the credential out of the immutable log is that nothing ever puts it there.
    write_audit_log(request.user, obj, "update",
                    {"action": "revoke", "revoked_at": obj.revoked_at.isoformat()})
    messages.success(
        request,
        f"{obj.number} revoked. The link now 404s for anyone holding it, including "
        f"{obj.portal_account.customer} — a revoked share is indistinguishable from a wrong token, "
        "so it leaks not even its own existence. The download record is kept.")
    return _detail(pk)
