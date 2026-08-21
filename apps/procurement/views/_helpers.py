"""Private helpers shared by the procurement portal pages.

The activity feed over ``core.AuditLog`` is rendered on TWO pages — the overview widget and the
full Recent Activity Feed — so its queryset builder lives here rather than being duplicated with
the two definitions inevitably drifting. Helpers used by exactly one entity stay in that entity's
module.
"""
from django.db.models import Q

from apps.core.models import AuditLog

#: The audit trail is filtered to PROCUREMENT-relevant content types, not "everything the tenant
#: did": the feed answers "what happened to the things I buy". Requisition / PO / GRN / RFQ rows
#: are written by 4.1's views through the shared CRUD helpers; ``procurementalert`` covers this
#: module's own rows. The list is the whitelist — new procurement sub-modules append their models'
#: lowercase table names here as they land.
PROCUREMENT_CONTENT_MODELS = (
    "purchaserequisition",
    "purchaseorder",
    "goodsreceiptnote",
    "rfq",
    "rfqquote",
    "procurementalert",
)

#: Printed on both feed surfaces. One constant so the two cannot explain the trail differently.
ACTIVITY_FEED_NOTE = (
    "This feed is derived from the append-only audit trail — one row per create, update or "
    "delete on procurement documents. It is never edited or deleted here; corrections appear as "
    "new entries, which is what makes the sequence trustworthy."
)


def procurement_activity_qs(tenant):
    """Procurement-relevant ``core.AuditLog`` rows for a tenant, newest first.

    ``select_related`` covers every column the feed renders (user name, content-type label) —
    without it a full page of rows costs two queries PER ROW. The explicit ``-id`` tie-break makes
    the order TOTAL so a row never repeats or vanishes across a page boundary.
    """
    return (AuditLog.objects
            .filter(tenant=tenant)
            .filter(Q(content_type__app_label="procurement")
                    | Q(content_type__app_label="scm",
                        content_type__model__in=PROCUREMENT_CONTENT_MODELS))
            .select_related("user", "content_type")
            .order_by("-at", "-id"))
