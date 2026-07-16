"""HRM 3.17 Payout & Reports — _helpers views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403


def _recompute_batch_status(batch):
    """Re-derive a disbursed batch's status from its CURRENT payments: any failed/returned →
    partially_disbursed, else disbursed. Only applies post-disburse (a draft/approved batch keeps its
    status; a reconciled batch stays reconciled). The one place the derivation lives."""
    if batch.status not in ("disbursed", "partially_disbursed"):
        return
    has_failed = batch._current_payments().filter(status__in=["failed", "returned"]).exists()
    new_status = "partially_disbursed" if has_failed else "disbursed"
    if batch.status != new_status:
        batch.status = new_status
        batch.save(update_fields=["status", "updated_at"])


def _mark_sent(dist, user):
    emp = dist.payslip.employee
    dist.sent_to_email = emp.work_email or emp.personal_email or ""
    dist.status = "sent"
    dist.sent_at = timezone.now()
    dist.sent_by = user
    dist.save(update_fields=["sent_to_email", "status", "sent_at", "sent_by", "updated_at"])
