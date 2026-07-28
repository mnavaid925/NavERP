"""SCM 4.10 Returns Management — ReturnReason form (the reason-code master)."""
from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.forms._common import TenantUniqueMixin
from apps.scm.models import ReturnReason


class ReturnReasonForm(TenantUniqueMixin, TenantModelForm):
    """Every field on this master is user-owned — there is no computed block to exclude.

    ``TenantUniqueMixin`` is what makes the ``("tenant", "code")`` constraint actually validate on
    the form: without it a duplicate code passes ``is_valid()`` and then raises an uncaught
    ``IntegrityError`` (a 500) on save, on the most ordinary mistake a user can make.
    """

    class Meta:
        model = ReturnReason
        fields = ["code", "name", "fault_party", "allows_refund", "allows_store_credit",
                  "allows_exchange", "allows_repair", "waives_return_fee", "blocks_restock",
                  "suggested_disposition", "requires_photo", "raises_nonconformance",
                  "follow_up_question", "sort_order", "is_active"]

    def clean(self):
        cleaned = super().clean()
        # Mirrors ReturnReason.clean(). Duplicated on the form so the message lands on a FIELD
        # rather than in the non-field block — the model check is the backstop for the admin, the
        # seeder and any future API writer.
        if not any(cleaned.get(name) for name in ("allows_refund", "allows_store_credit",
                                                  "allows_exchange", "allows_repair")):
            self.add_error("allows_refund",
                           "This reason would offer the customer no outcome at all — allow at "
                           "least one of refund, store credit, exchange or repair.")
        if cleaned.get("blocks_restock") and cleaned.get("suggested_disposition") == "restock":
            self.add_error("suggested_disposition",
                           "This reason blocks restocking, so it cannot also suggest it.")
        return cleaned
