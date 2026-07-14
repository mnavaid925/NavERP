"""CRM URLconf package — split from the former monolithic apps/crm/urls.py.

One sub-package per CRM sub-module (1.1-1.12), one module per entity, mirroring
apps/crm/views/. Each entity module exposes its own ``urlpatterns`` list; this __init__
concatenates them GROUPED BY ENTITY and keeps ``app_name = "crm"``, so every ``crm:<name>``
reverse and ``include("apps.crm.urls")`` in config/urls.py is unchanged.

ORDER — read this before adding a route. Grouping by entity is NOT the monolith's original
sequence: the old flat urls.py interleaved a few routes across entities (``cases/track/<str:token>/``
sat inside the ``cases/`` block, ``kb/<str:token>/`` after the ``knowledge/`` block,
``milestones/<int:pk>/move/`` after ``workload/``, ``sign/<str:token>/`` after
``document-repository/``), so 35 of the 304 routes changed index in the split. That reorder was
verified NON-SHADOWING — every greedy converter pattern (``<str:>``/``<slug:>``) sits under a unique
static prefix, and all 304 routes resolve and reverse exactly as before (``<int:pk>`` can't swallow
``cases/track/…``; ``<str:>`` never crosses a ``/``).

Django is first-match-wins, so ordering IS behaviour: when you add a route with a greedy converter,
check it against the WHOLE concatenated list below, not just its own entity module. Within a module,
keep literal routes before ``<int:pk>`` ones (e.g. ``projects/board/`` before ``projects/<int:pk>/``).
"""
from .AnalyticsReporting.Overview import urlpatterns as _analyticsreporting_overview
from .CoreData.Leads import urlpatterns as _coredata_leads
from .SalesForceAutomation.Opportunities import urlpatterns as _salesforceautomation_opportunities
from .SalesForceAutomation.Territories import urlpatterns as _salesforceautomation_territories
from .SalesForceAutomation.Products import urlpatterns as _salesforceautomation_products
from .SalesForceAutomation.PriceBooks import urlpatterns as _salesforceautomation_pricebooks
from .SalesForceAutomation.Quotes import urlpatterns as _salesforceautomation_quotes
from .SalesForceAutomation.SalesQuotas import urlpatterns as _salesforceautomation_salesquotas
from .SalesForceAutomation.Forecast import urlpatterns as _salesforceautomation_forecast
from .MarketingAutomation.Campaigns import urlpatterns as _marketingautomation_campaigns
from .MarketingAutomation.CampaignMembers import urlpatterns as _marketingautomation_campaignmembers
from .MarketingAutomation.EmailTemplates import urlpatterns as _marketingautomation_emailtemplates
from .MarketingAutomation.EmailCampaigns import urlpatterns as _marketingautomation_emailcampaigns
from .MarketingAutomation.LandingPages import urlpatterns as _marketingautomation_landingpages
from .MarketingAutomation.FormSubmissions import urlpatterns as _marketingautomation_formsubmissions
from .CustomerService.Cases import urlpatterns as _customerservice_cases
from .CustomerService.PublicPages import urlpatterns as _customerservice_publicpages
from .CustomerService.SlaPolicies import urlpatterns as _customerservice_slapolicies
from .CustomerService.KnowledgeBase import urlpatterns as _customerservice_knowledgebase
from .CustomerService.KbCategories import urlpatterns as _customerservice_kbcategories
from .CustomerService.CustomerPortalAccess import urlpatterns as _customerservice_customerportalaccess
from .CustomerService.CustomerPortal import urlpatterns as _customerservice_customerportal
from .ActivityManagement.Tasks import urlpatterns as _activitymanagement_tasks
from .ActivityManagement.CalendarEvents import urlpatterns as _activitymanagement_calendarevents
from .ActivityManagement.CommunicationLogs import urlpatterns as _activitymanagement_communicationlogs
from .CoreData.Accounts import urlpatterns as _coredata_accounts
from .CoreData.Contacts import urlpatterns as _coredata_contacts
from .FinanceBilling.Expenses import urlpatterns as _financebilling_expenses
from .FinanceBilling.DealInvoices import urlpatterns as _financebilling_dealinvoices
from .FinanceBilling.PaymentReceipts import urlpatterns as _financebilling_paymentreceipts
from .ProjectDelivery.Projects import urlpatterns as _projectdelivery_projects
from .ProjectDelivery.Milestones import urlpatterns as _projectdelivery_milestones
from .ProjectDelivery.Timesheets import urlpatterns as _projectdelivery_timesheets
from .ProjectDelivery.ResourceAllocation import urlpatterns as _projectdelivery_resourceallocation
from .DocumentContract.DocTemplates import urlpatterns as _documentcontract_doctemplates
from .DocumentContract.Contracts import urlpatterns as _documentcontract_contracts
from .DocumentContract.DocumentVersions import urlpatterns as _documentcontract_documentversions
from .AutomationWorkflow.WorkflowRules import urlpatterns as _automationworkflow_workflowrules
from .AutomationWorkflow.Webhooks import urlpatterns as _automationworkflow_webhooks
from .AutomationWorkflow.WorkflowLogs import urlpatterns as _automationworkflow_workflowlogs
from .AutomationWorkflow.Approvals import urlpatterns as _automationworkflow_approvals
from .CustomerSuccess.OnboardingPlans import urlpatterns as _customersuccess_onboardingplans
from .CustomerSuccess.OnboardingTemplates import urlpatterns as _customersuccess_onboardingtemplates
from .CustomerSuccess.HealthScores import urlpatterns as _customersuccess_healthscores
from .CustomerSuccess.Surveys import urlpatterns as _customersuccess_surveys
from .InventoryVendor.ProductStock import urlpatterns as _inventoryvendor_productstock
from .InventoryVendor.PurchaseOrders import urlpatterns as _inventoryvendor_purchaseorders
from .InventoryVendor.PartnerPortalAccess import urlpatterns as _inventoryvendor_partnerportalaccess
from .InventoryVendor.PartnerPortal import urlpatterns as _inventoryvendor_partnerportal
from .AnalyticsReporting.Dashboards import urlpatterns as _analyticsreporting_dashboards
from .AnalyticsReporting.Widgets import urlpatterns as _analyticsreporting_widgets
from .AnalyticsReporting.Reports import urlpatterns as _analyticsreporting_reports
from .AnalyticsReporting.Snapshots import urlpatterns as _analyticsreporting_snapshots

app_name = "crm"

urlpatterns = [
    *_analyticsreporting_overview,  # AnalyticsReporting/Overview
    *_coredata_leads,  # CoreData/Leads
    *_salesforceautomation_opportunities,  # SalesForceAutomation/Opportunities
    *_salesforceautomation_territories,  # SalesForceAutomation/Territories
    *_salesforceautomation_products,  # SalesForceAutomation/Products
    *_salesforceautomation_pricebooks,  # SalesForceAutomation/PriceBooks
    *_salesforceautomation_quotes,  # SalesForceAutomation/Quotes
    *_salesforceautomation_salesquotas,  # SalesForceAutomation/SalesQuotas
    *_salesforceautomation_forecast,  # SalesForceAutomation/Forecast
    *_marketingautomation_campaigns,  # MarketingAutomation/Campaigns
    *_marketingautomation_campaignmembers,  # MarketingAutomation/CampaignMembers
    *_marketingautomation_emailtemplates,  # MarketingAutomation/EmailTemplates
    *_marketingautomation_emailcampaigns,  # MarketingAutomation/EmailCampaigns
    *_marketingautomation_landingpages,  # MarketingAutomation/LandingPages
    *_marketingautomation_formsubmissions,  # MarketingAutomation/FormSubmissions
    *_customerservice_cases,  # CustomerService/Cases
    *_customerservice_publicpages,  # CustomerService/PublicPages
    *_customerservice_slapolicies,  # CustomerService/SlaPolicies
    *_customerservice_knowledgebase,  # CustomerService/KnowledgeBase
    *_customerservice_kbcategories,  # CustomerService/KbCategories
    *_customerservice_customerportalaccess,  # CustomerService/CustomerPortalAccess
    *_customerservice_customerportal,  # CustomerService/CustomerPortal
    *_activitymanagement_tasks,  # ActivityManagement/Tasks
    *_activitymanagement_calendarevents,  # ActivityManagement/CalendarEvents
    *_activitymanagement_communicationlogs,  # ActivityManagement/CommunicationLogs
    *_coredata_accounts,  # CoreData/Accounts
    *_coredata_contacts,  # CoreData/Contacts
    *_financebilling_expenses,  # FinanceBilling/Expenses
    *_financebilling_dealinvoices,  # FinanceBilling/DealInvoices
    *_financebilling_paymentreceipts,  # FinanceBilling/PaymentReceipts
    *_projectdelivery_projects,  # ProjectDelivery/Projects
    *_projectdelivery_milestones,  # ProjectDelivery/Milestones
    *_projectdelivery_timesheets,  # ProjectDelivery/Timesheets
    *_projectdelivery_resourceallocation,  # ProjectDelivery/ResourceAllocation
    *_documentcontract_doctemplates,  # DocumentContract/DocTemplates
    *_documentcontract_contracts,  # DocumentContract/Contracts
    *_documentcontract_documentversions,  # DocumentContract/DocumentVersions
    *_automationworkflow_workflowrules,  # AutomationWorkflow/WorkflowRules
    *_automationworkflow_webhooks,  # AutomationWorkflow/Webhooks
    *_automationworkflow_workflowlogs,  # AutomationWorkflow/WorkflowLogs
    *_automationworkflow_approvals,  # AutomationWorkflow/Approvals
    *_customersuccess_onboardingplans,  # CustomerSuccess/OnboardingPlans
    *_customersuccess_onboardingtemplates,  # CustomerSuccess/OnboardingTemplates
    *_customersuccess_healthscores,  # CustomerSuccess/HealthScores
    *_customersuccess_surveys,  # CustomerSuccess/Surveys
    *_inventoryvendor_productstock,  # InventoryVendor/ProductStock
    *_inventoryvendor_purchaseorders,  # InventoryVendor/PurchaseOrders
    *_inventoryvendor_partnerportalaccess,  # InventoryVendor/PartnerPortalAccess
    *_inventoryvendor_partnerportal,  # InventoryVendor/PartnerPortal
    *_analyticsreporting_dashboards,  # AnalyticsReporting/Dashboards
    *_analyticsreporting_widgets,  # AnalyticsReporting/Widgets
    *_analyticsreporting_reports,  # AnalyticsReporting/Reports
    *_analyticsreporting_snapshots,  # AnalyticsReporting/Snapshots
]
