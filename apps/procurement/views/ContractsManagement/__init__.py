"""Procurement 6.8 Contract Management — view re-exports."""
from .Amendments import (
    camendment_approve,
    camendment_create,
    camendment_detail,
    camendment_list,
    camendment_reject,
)
from .Clauses import (
    clause_create,
    clause_delete,
    clause_detail,
    clause_edit,
    clause_list,
)
from .Contracts import (
    contract_add_link,
    contract_add_signer,
    contract_create,
    contract_detail,
    contract_list,
    contract_remove_link,
    contract_remove_signer,
    contract_sign_page,
)
from .Milestones import (
    milestone_complete,
    milestone_create,
    milestone_delete,
    milestone_edit,
    milestone_list,
)
from .Renewals import renewals_board, renewals_run

__all__ = [
    "clause_list", "clause_detail", "clause_create", "clause_edit", "clause_delete",
    "contract_list", "contract_detail", "contract_create",
    "contract_add_link", "contract_remove_link",
    "contract_add_signer", "contract_remove_signer",
    "contract_sign_page",
    "camendment_list", "camendment_detail", "camendment_create",
    "camendment_approve", "camendment_reject",
    "milestone_list", "milestone_create", "milestone_edit",
    "milestone_complete", "milestone_delete",
    "renewals_board", "renewals_run",
]
