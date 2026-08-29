"""Procurement 6.11 Order Fulfillment & Tracking — the two COMPUTED fulfillment boards.

**Real-time Freight Tracking** and **Delivery Confirmation** are the two NavERP.md bullets that
describe a *view* of work in flight, not a new document. Both are therefore rendered exactly the
way 6.10's ``purchaseordermanagement/linetracking.html`` is: a read-only board over rows that
already exist — here every :class:`~apps.procurement.models.AdvancedShipmentNotice` in the
workspace — with **zero new state, zero writes and zero migration impact**. There is no model file
and no forms file in this lane.

Two decisions worth recording, because a reviewer will otherwise look for the missing tables:

* *Freight tracking* is **owned by SCM 4.6** (``scm.Shipment`` + ``scm.TrackingEvent``). This board
  never creates a shipment and never appends a tracking event: it SELECTS the ASN, follows the
  optional ``shipment`` link, and READS the projections 4.6 maintains
  (``current_status_text`` / ``last_known_location`` / ``eta``) through the ASN's own
  ``tracking_status_text`` / ``location_display`` / ``eta_display`` properties, which fall back to
  the supplier-declared carrier + expected date when no TMS shipment is linked. Duplicating a
  second freight log inside procurement would give the buyer two ETAs that disagree.
* *Delivery confirmation* posts to the ASN entity's existing
  ``procurement:asn_confirm_delivery`` verb (with ``next=confirmation`` so the redirect returns
  here). Defining a second confirm path would mean two places that stamp the POD block, and only
  one of them would keep the double-submit guard.

Both views are ``@login_required`` and open to any workspace member — a board that hides rows from
the people chasing the delivery is a board nobody uses. Neither is ``@tenant_admin_required``
because neither mutates anything.
"""
from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone

from apps.procurement.models import AdvancedShipmentNotice
from apps.procurement.views._common import *  # noqa: F401,F403
from apps.scm.models import Carrier


#: Every FK a board row (or a row's ``__str__``) touches, including the chained hops:
#: ``purchase_order.vendor`` for the PO column and ``carrier.party`` because ``Carrier.name`` is a
#: property off ``party.name``. Without ``carrier__party`` a 15-row page costs 15 extra queries.
_BOARD_SELECT_RELATED = (
    "purchase_order",
    "purchase_order__vendor",
    "carrier",
    "carrier__party",
    "shipment",
)

#: Tabs on the delivery-confirmation board. Sanitized against this list, so ``?due=zzz`` falls back
#: to "today" and still renders 200 rather than 500ing on an unknown branch.
BUCKET_CHOICES = [
    ("today", "Due today"),
    ("overdue", "Overdue"),
    ("awaiting", "Awaiting arrival"),
    ("confirmed", "Confirmed (7 days)"),
]
_BUCKET_KEYS = {key for key, _label in BUCKET_CHOICES}
DEFAULT_BUCKET = "today"

#: How far back the "Confirmed" tab looks. Matches the label in BUCKET_CHOICES.
CONFIRMED_WINDOW_DAYS = 7


def _carrier_choices(tenant):
    """Carriers for the ``?carrier=`` widget — ordered by the party name the label renders."""
    return (Carrier.objects.filter(tenant=tenant)
            .select_related("party")
            .order_by("party__name"))


@login_required
def inbound_tracking(request):
    """Real-time freight tracking — every in-flight ASN, soonest expected arrival first.

    A single read-only board; the only row action is View (the ASN detail page).
    """
    # The po_line_tracking precedent: a tenant-less user (the superuser has tenant=None) would see
    # an empty board and no explanation, so say why BEFORE running a query.
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace to view inbound tracking.")
        return redirect("dashboard:home")

    today = timezone.localdate()
    in_flight = AdvancedShipmentNotice.IN_FLIGHT_STATUSES

    # Stat cards come from ONE aggregate over the join-free tenant queryset. Built off the bare
    # manager rather than the board queryset below because aggregate() does not strip unused
    # select_related joins — it would drag five LEFT JOINs through a whole-tenant COUNT.
    totals = AdvancedShipmentNotice.objects.filter(tenant=request.tenant).aggregate(
        in_flight=Count("id", filter=Q(status__in=in_flight)),
        late=Count("id", filter=Q(status__in=in_flight,
                                  expected_delivery_date__lt=today)),
        # isnull on a forward FK compares the local column — no join is added for this one.
        unlinked=Count("id", filter=Q(status__in=in_flight, shipment__isnull=True)),
        arriving_today=Count("id", filter=Q(status__in=in_flight,
                                            expected_delivery_date=today)),
    )

    qs = (AdvancedShipmentNotice.objects
          .filter(tenant=request.tenant, status__in=in_flight)
          .select_related(*_BOARD_SELECT_RELATED)
          .order_by("expected_delivery_date", "-id"))

    # ?late=1 is a plain boolean toggle, not a (param, lookup, is_int) filter — it compares a
    # column against today rather than against a GET value, so it is applied here, BEFORE
    # crud_list paginates. Filtering after pagination would make the page counts lie.
    if request.GET.get("late", "").strip() == "1":
        qs = qs.filter(expected_delivery_date__lt=today)

    return crud_list(
        request, qs, "procurement/orderfulfillment/inbound_tracking.html",
        search_fields=["number", "supplier_reference", "tracking_number",
                       "purchase_order__number"],
        filters=[
            ("status", "status", False),
            ("carrier", "carrier_id", True),
        ],
        extra_context={
            # Only the statuses this board can actually show: the queryset above is hard-limited
            # to IN_FLIGHT_STATUSES, so offering Draft / Delivered / Cancelled in the dropdown
            # would be three options that silently return an empty board.
            "status_choices": [(value, label)
                               for value, label in AdvancedShipmentNotice.STATUS_CHOICES
                               if value in AdvancedShipmentNotice.IN_FLIGHT_STATUSES],
            "carriers": _carrier_choices(request.tenant),
            "stats": {
                "in_flight": totals["in_flight"],
                "late": totals["late"],
                "unlinked": totals["unlinked"],
                "arriving_today": totals["arriving_today"],
            },
        },
    )


@login_required
def delivery_confirmation(request):
    """The arrivals queue — ASNs bucketed by when they were due, with an inline confirm form.

    The form the template renders posts to ``procurement:asn_confirm_delivery`` (the ASN entity's
    own POST-only verb, which re-checks the in-flight guard inside its row lock and no-ops on a
    double submit). This view itself writes nothing.
    """
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace to view the delivery queue.")
        return redirect("dashboard:home")

    today = timezone.localdate()
    in_flight = AdvancedShipmentNotice.IN_FLIGHT_STATUSES
    confirmed_since = timezone.now() - timedelta(days=CONFIRMED_WINDOW_DAYS)

    # Sanitize the tab: anything unrecognized falls back to the default instead of raising.
    bucket = request.GET.get("due", "").strip()
    if bucket not in _BUCKET_KEYS:
        bucket = DEFAULT_BUCKET

    # The four bucket predicates, defined once and reused for both the queryset and the stat
    # cards, so a tab can never disagree with the number on the card above it.
    awaiting_q = (Q(status__in=in_flight)
                  & (Q(expected_delivery_date__gt=today)
                     | Q(expected_delivery_date__isnull=True)))
    bucket_q = {
        "today": Q(status__in=in_flight, expected_delivery_date=today),
        "overdue": Q(status__in=in_flight, expected_delivery_date__lt=today),
        "awaiting": awaiting_q,
        "confirmed": Q(status="delivered", delivered_at__gte=confirmed_since),
    }

    totals = AdvancedShipmentNotice.objects.filter(tenant=request.tenant).aggregate(
        due_today=Count("id", filter=bucket_q["today"]),
        overdue=Count("id", filter=bucket_q["overdue"]),
        awaiting=Count("id", filter=awaiting_q),
        confirmed_7d=Count("id", filter=bucket_q["confirmed"]),
    )

    # ``confirmed_by`` on top of the shared list, not inside it: the Confirmed tab renders
    # ``row.confirmed_by.get_full_name`` for every row (one User fetch each without this), while
    # inbound_tracking never touches the column and would only gain a pointless LEFT JOIN.
    qs = (AdvancedShipmentNotice.objects
          .filter(tenant=request.tenant)
          .filter(bucket_q[bucket])
          .select_related(*_BOARD_SELECT_RELATED, "confirmed_by")
          .order_by("expected_delivery_date", "-id"))

    return crud_list(
        request, qs, "procurement/orderfulfillment/delivery_confirmation.html",
        search_fields=["number", "supplier_reference", "purchase_order__number"],
        extra_context={
            "bucket": bucket,
            "bucket_choices": BUCKET_CHOICES,
            "condition_choices": AdvancedShipmentNotice.CONDITION_CHOICES,
            "stats": {
                "due_today": totals["due_today"],
                "overdue": totals["overdue"],
                "awaiting": totals["awaiting"],
                "confirmed_7d": totals["confirmed_7d"],
            },
        },
    )
