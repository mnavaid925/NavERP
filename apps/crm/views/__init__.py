"""CRM views package — split from the former monolithic apps/crm/views.py.

One sub-package per CRM sub-module (1.1-1.12), one module per entity. This __init__
re-exports every view + the private helpers imported elsewhere, so the apps/crm/urls/ package
(`from apps.crm import views`, `views.<name>`) and external importers keep working unchanged.

Adding a view: put it in its entity module, then add it to the re-export block below — otherwise
`views.<name>` in the URLconf raises AttributeError.
"""

# 1.1 Core Data Management
from .CoreData.Accounts import (
    account_list,
    account_detail,
    account_create,
    account_edit,
    account_delete,
)
from .CoreData.Contacts import (
    contact_list,
    contact_detail,
    contact_create,
    contact_edit,
    contact_delete,
)
from .CoreData.Leads import (
    lead_list,
    lead_create,
    lead_detail,
    lead_edit,
    lead_delete,
    lead_convert,
)

# 1.2 Sales Force Automation
from .SalesForceAutomation.Opportunities import (
    opportunity_list,
    opportunity_create,
    opportunity_detail,
    opportunity_edit,
    opportunity_delete,
    opportunity_board,
    opportunity_advance,
    opportunitysplit_add,
    opportunitysplit_remove,
)
from .SalesForceAutomation.Territories import (
    territory_list,
    territory_create,
    territory_detail,
    territory_edit,
    territory_delete,
)
from .SalesForceAutomation.Products import (
    product_list,
    product_create,
    product_detail,
    product_edit,
    product_delete,
)
from .SalesForceAutomation.PriceBooks import (
    pricebook_list,
    pricebook_create,
    pricebook_detail,
    pricebook_edit,
    pricebook_delete,
)
from .SalesForceAutomation.Quotes import (
    quote_list,
    quote_create,
    quote_detail,
    quote_edit,
    quote_delete,
    quote_print,
    quoteline_add,
    quoteline_remove,
    quote_send,
    quote_accept,
    quote_decline,
)
from .SalesForceAutomation.SalesQuotas import (
    salesquota_list,
    salesquota_create,
    salesquota_detail,
    salesquota_edit,
    salesquota_delete,
)
from .SalesForceAutomation.Forecast import (
    forecast,
)

# 1.3 Marketing Automation
from .MarketingAutomation.Campaigns import (
    campaign_list,
    campaign_create,
    campaign_detail,
    campaign_edit,
    campaign_delete,
)
from .MarketingAutomation.CampaignMembers import (
    campaignmember_list,
    campaignmember_create,
    campaignmember_detail,
    campaignmember_edit,
    campaignmember_delete,
    campaignmember_add,
    campaignmember_remove,
)
from .MarketingAutomation.EmailTemplates import (
    emailtemplate_list,
    emailtemplate_create,
    emailtemplate_detail,
    emailtemplate_edit,
    emailtemplate_delete,
)
from .MarketingAutomation.EmailCampaigns import (
    emailcampaign_list,
    emailcampaign_create,
    emailcampaign_detail,
    emailcampaign_edit,
    emailcampaign_delete,
    emailcampaign_send,
)
from .MarketingAutomation.LandingPages import (
    landingpage_list,
    landingpage_create,
    landingpage_detail,
    landingpage_edit,
    landingpage_delete,
    landingpage_publish,
    landing_public,
)
from .MarketingAutomation.FormSubmissions import (
    formsubmission_list,
    formsubmission_detail,
    formsubmission_delete,
    formsubmission_convert,
)

# 1.4 Customer Service & Support
from .CustomerService.Cases import (
    case_list,
    case_create,
    case_detail,
    case_edit,
    case_delete,
    case_comment_add,
)
from .CustomerService.KnowledgeBase import (
    knowledgearticle_list,
    knowledgearticle_create,
    knowledgearticle_detail,
    knowledgearticle_edit,
    knowledgearticle_delete,
)
from .CustomerService.SlaPolicies import (
    slapolicy_list,
    slapolicy_create,
    slapolicy_detail,
    slapolicy_edit,
    slapolicy_delete,
)
from .CustomerService.KbCategories import (
    kbcategory_list,
    kbcategory_create,
    kbcategory_detail,
    kbcategory_edit,
    kbcategory_delete,
)
from .CustomerService.CustomerPortalAccess import (
    customerportalaccess_list,
    customerportalaccess_create,
    customerportalaccess_detail,
    customerportalaccess_edit,
    customerportalaccess_delete,
)
from .CustomerService.PublicPages import (
    case_public,
    kb_public,
    kb_helpful,
)
from .CustomerService.CustomerPortal import (
    portal_case_list,
    portal_case_detail,
    portal_case_create,
)

# 1.5 Activity & Communication Management
from .ActivityManagement.Tasks import (
    task_list,
    task_create,
    task_detail,
    task_edit,
    task_delete,
)
from .ActivityManagement.CalendarEvents import (
    calendarevent_list,
    calendarevent_create,
    calendarevent_detail,
    calendarevent_edit,
    calendarevent_delete,
    event_attendee_add,
    event_attendee_delete,
    event_invite,
    event_ics,
)
from .ActivityManagement.CommunicationLogs import (
    communicationlog_list,
    communicationlog_create,
    communicationlog_detail,
    communicationlog_edit,
    communicationlog_delete,
)

# 1.6 Analytics & Reporting
from .AnalyticsReporting.Overview import (
    overview,
)
from .AnalyticsReporting.Dashboards import (
    dashboard_list,
    dashboard_create,
    dashboard_detail,
    dashboard_edit,
    dashboard_delete,
)
from .AnalyticsReporting.Widgets import (
    widget_create,
    widget_edit,
    widget_delete,
    widget_move,
)
from .AnalyticsReporting.Reports import (
    report_list,
    report_create,
    report_detail,
    report_edit,
    report_delete,
    report_favorite,
    report_snapshot,
)
from .AnalyticsReporting.Snapshots import (
    snapshot_detail,
    snapshot_delete,
)

# 1.7 Finance & Billing Management
from .FinanceBilling.Expenses import (
    expense_list,
    expense_create,
    expense_detail,
    expense_edit,
    expense_delete,
    expense_submit,
    expense_approve,
    expense_reject,
)
from .FinanceBilling.DealInvoices import (
    dealinvoice_list,
    dealinvoice_from_quote,
    dealinvoice_create,
    dealinvoice_detail,
    dealinvoice_edit,
    dealinvoice_delete,
)
from .FinanceBilling.PaymentReceipts import (
    paymentreceipt_list,
    paymentreceipt_create,
    paymentreceipt_detail,
    paymentreceipt_edit,
    paymentreceipt_delete,
    paymentreceipt_print,
)

# 1.8 Project & Delivery Management
from .ProjectDelivery.Projects import (
    crmproject_list,
    crmproject_create,
    crmproject_detail,
    crmproject_edit,
    crmproject_delete,
    opportunity_to_project,
    crmproject_board,
)
from .ProjectDelivery.Milestones import (
    crmmilestone_list,
    crmmilestone_create,
    crmmilestone_detail,
    crmmilestone_edit,
    crmmilestone_delete,
    crmmilestone_move,
)
from .ProjectDelivery.Timesheets import (
    timesheet_list,
    timesheet_create,
    timesheet_detail,
    timesheet_edit,
    timesheet_delete,
    timesheet_submit,
    timesheet_approve,
    timesheet_reject,
)
from .ProjectDelivery.ResourceAllocation import (
    DEFAULT_WEEKLY_CAPACITY,
    resourceallocation_list,
    resourceallocation_create,
    resourceallocation_detail,
    resourceallocation_edit,
    resourceallocation_delete,
    resource_workload,
)

# 1.9 Document & Contract Management
from .DocumentContract.DocTemplates import (
    doctemplate_list,
    doctemplate_create,
    doctemplate_detail,
    doctemplate_edit,
    doctemplate_delete,
)
from .DocumentContract.Contracts import (
    contractdocument_list,
    contractdocument_create,
    contractdocument_detail,
    contractdocument_edit,
    contractdocument_delete,
    contractdocument_add_signer,
    contractdocument_remove_signer,
    sign_document,
    contractdocument_generate,
    contractdocument_version_add,
    contractdocument_send,
)
from .DocumentContract.DocumentVersions import (
    documentversion_detail,
    document_repository,
)

# 1.10 Automation & Workflow Engine
from .AutomationWorkflow.WorkflowRules import (
    workflowrule_list,
    workflowrule_create,
    workflowrule_detail,
    workflowrule_edit,
    workflowrule_delete,
    workflowrule_run,
)
from .AutomationWorkflow.Webhooks import (
    webhook_list,
    webhook_create,
    webhook_detail,
    webhook_edit,
    webhook_delete,
    webhook_test,
    webhookdelivery_list,
    webhookdelivery_detail,
)
from .AutomationWorkflow.WorkflowLogs import (
    workflowlog_list,
    workflowlog_detail,
)
from .AutomationWorkflow.Approvals import (
    approvalrequest_list,
    approvalrequest_create,
    approvalrequest_detail,
    approvalrequest_edit,
    approvalrequest_delete,
    approvalrequest_approve,
    approvalrequest_reject,
)

# 1.11 Customer Success & Retention
from .CustomerSuccess.OnboardingPlans import (
    onboardingplan_list,
    onboardingplan_create,
    onboardingplan_detail,
    onboardingplan_edit,
    onboardingplan_delete,
    onboardingstep_add,
    onboardingstep_complete,
    onboardingstep_delete,
    onboardingstep_edit,
)
from .CustomerSuccess.OnboardingTemplates import (
    onboardingtemplate_list,
    onboardingtemplate_create,
    onboardingtemplate_detail,
    onboardingtemplate_edit,
    onboardingtemplate_delete,
    onboardingtemplatestep_add,
    onboardingtemplatestep_edit,
    onboardingtemplatestep_delete,
    onboardingtemplate_apply,
)
from .CustomerSuccess.HealthScores import (
    healthscore_list,
    healthscore_create,
    healthscore_detail,
    healthscore_edit,
    healthscore_delete,
    recompute_health_score,
    recompute_all_health_scores,
    health_config_edit,
)
from .CustomerSuccess.Surveys import (
    survey_list,
    survey_create,
    survey_detail,
    survey_edit,
    survey_delete,
    survey_results,
    survey_send,
    survey_respond,
)

# 1.12 Inventory & Vendor Management
from .InventoryVendor.ProductStock import (
    productstock_list,
    productstock_create,
    productstock_detail,
    productstock_edit,
    productstock_delete,
)
from .InventoryVendor.PurchaseOrders import (
    crm_po_list,
    crm_po_create,
    crm_po_detail,
    crm_po_edit,
    crm_po_delete,
    crm_po_add_line,
    crm_po_remove_line,
    crm_po_receive,
)
from .InventoryVendor.PartnerPortalAccess import (
    partnerportalaccess_list,
    partnerportalaccess_create,
    partnerportalaccess_detail,
    partnerportalaccess_edit,
    partnerportalaccess_delete,
)
from .InventoryVendor.PartnerPortal import (
    portal_dashboard,
    portal_po_list,
    portal_stock,
)

# private helpers imported by external modules (seed_crm, tests)
from .DocumentContract.Contracts import _render_doc_body  # noqa: F401
from .AutomationWorkflow._engine import _safe_record_field, _eval_conditions, _run_rule  # noqa: F401
