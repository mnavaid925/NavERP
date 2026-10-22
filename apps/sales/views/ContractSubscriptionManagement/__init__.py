"""Sales 8.15 — ContractSubscriptionManagement views package."""
from apps.sales.views.ContractSubscriptionManagement.ContractObligations import (
    contract_obligation_breach,
    contract_obligation_create,
    contract_obligation_delete,
    contract_obligation_detail,
    contract_obligation_edit,
    contract_obligation_fulfill,
    contract_obligation_list,
)
from apps.sales.views.ContractSubscriptionManagement.ContractSubscriptionWorkspaces import (
    contract_subscription_workspace,
)
from apps.sales.views.ContractSubscriptionManagement.CustomerContracts import (
    customer_contract_activate,
    customer_contract_create,
    customer_contract_delete,
    customer_contract_detail,
    customer_contract_edit,
    customer_contract_execute_auto_renew,
    customer_contract_generate_renewal_quote,
    customer_contract_list,
)
from apps.sales.views.ContractSubscriptionManagement.CustomerSubscriptions import (
    customer_subscription_cancel,
    customer_subscription_create,
    customer_subscription_delete,
    customer_subscription_detail,
    customer_subscription_edit,
    customer_subscription_list,
    customer_subscription_pause,
    customer_subscription_resume,
    customer_subscription_upgrade,
)
from apps.sales.views.ContractSubscriptionManagement.RenewalAutomations import (
    renewal_automation_dashboard,
)
from apps.sales.views.ContractSubscriptionManagement.UsageMeterRecords import (
    usage_meter_record_calculate,
    usage_meter_record_create,
    usage_meter_record_delete,
    usage_meter_record_detail,
    usage_meter_record_edit,
    usage_meter_record_invoice,
    usage_meter_record_list,
)

__all__ = [
    "customer_contract_list",
    "customer_contract_create",
    "customer_contract_detail",
    "customer_contract_edit",
    "customer_contract_delete",
    "customer_contract_activate",
    "customer_contract_generate_renewal_quote",
    "customer_contract_execute_auto_renew",
    "customer_subscription_list",
    "customer_subscription_create",
    "customer_subscription_detail",
    "customer_subscription_edit",
    "customer_subscription_delete",
    "customer_subscription_pause",
    "customer_subscription_resume",
    "customer_subscription_cancel",
    "customer_subscription_upgrade",
    "usage_meter_record_list",
    "usage_meter_record_create",
    "usage_meter_record_detail",
    "usage_meter_record_edit",
    "usage_meter_record_delete",
    "usage_meter_record_calculate",
    "usage_meter_record_invoice",
    "contract_obligation_list",
    "contract_obligation_create",
    "contract_obligation_detail",
    "contract_obligation_edit",
    "contract_obligation_delete",
    "contract_obligation_fulfill",
    "contract_obligation_breach",
    "contract_subscription_workspace",
    "renewal_automation_dashboard",
]
