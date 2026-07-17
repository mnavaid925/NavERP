"""SCM 4.1 Procurement Management — PurchaseRequisitions forms."""
from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.forms._common import _active_currencies
from apps.scm.models import (
    PurchaseRequisition,
    PurchaseRequisitionLine,
)


class PurchaseRequisitionForm(TenantModelForm):
    class Meta:
        model = PurchaseRequisition
        # `status` EXCLUDED — it advances via the approve/reject/convert actions, never by hand.
        # `requester` EXCLUDED — set to request.user on create, so a requisition cannot be raised
        # in someone else's name. `estimated_total` is derived from lines.
        fields = ["title", "org_unit", "budget", "currency", "required_by", "justification", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _active_currencies(self)
        # org_unit / budget target models both carry a tenant FK, so TenantModelForm has already
        # scoped them.


class PurchaseRequisitionLineForm(TenantModelForm):
    class Meta:
        model = PurchaseRequisitionLine
        fields = ["item_description", "sku_hint", "uom_hint", "quantity", "estimated_unit_price",
                  "gl_account", "needed_by"]


PurchaseRequisitionLineFormSet = inlineformset_factory(
    PurchaseRequisition, PurchaseRequisitionLine, form=PurchaseRequisitionLineForm,
    extra=2, can_delete=True,
)
